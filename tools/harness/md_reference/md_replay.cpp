// md_replay: the Machinedrum's voice DSP outside the Machinedrum.
//
// A bare DSP56303 (the reference fork's dsp56kEmu, configured as md::Dsp
// configures it) is loaded from an md_profile capture: the producer's memory
// and registers at a slot-0 loop head. It then runs the original voice loop
// (P:6b..e7) with every I/O wait skipped. Before each slot it writes what
// the host sent since the previous slot (the capture's host stream, decoded
// into Y writes; the voice state is the emulator's own), runs to P:b5 (the
// engine's render has returned), compares the 32 rendered words with the
// reference's, and resumes past the frame-sync poll (P:bb..bf) and the
// output DMA wait (P:cf). No host port, no ESSI link, no ColdFire.
//
// Writing the reference's record words instead hides faults: the record's
// 64 words hold voice state too (engine 0x44 keeps its sample pointer in
// word 12), and overwriting them from the log restored state a relocated
// run had got wrong.
//
// Diagnostics: MD_REPLAY_STATEDIFF=<n> and MD_REPLAY_OUTDIFF=<n> print the
// first <n> differing records and blocks; MD_REPLAY_BLOCKS=<n> stops early;
// MD_REPLAY_KEEP_OLD=1 and MD_REPLAY_WIPE=<start>-<end> (with --reloc) keep
// the old regions, or wipe only part of them.
// MD_REPLAY_READS=<file> (only in a build with -DMD_REPLAY_READS, whose
// emulator carries the g_mdReadHook read hook; see md_reads.sh): for every
// word of the MD's external RAM 0x100000-0x14ffff, the spaces the DSP read
// it through (P, X, Y) while the blocks ran, as runs "<start> <end> <PXY>".
// Instruction fetches do not go through the hook.
//
// MD_REPLAY_ACCESS=<file> (same build): every data read and write, by the PC
// of the instruction that made it, as runs "<pc> <P|X|Y> <r|w> <lo> <hi>
// <count>" over internal X/Y and the external RAM, after a "# blocks <n>"
// line and the executed PCs as "E <lo> <hi>" runs (end exclusive);
// md_flip.py reads it. With MD_REPLAY_INIT_ONLY=1 it runs only the boot init
// (P:100057..10008d) at MD addresses, records that, and stops.
//
// MD_REPLAY_VALUES=<file> with MD_REPLAY_VALUE_BLOCK=<n> records RAM read
// values made by instructions in one block (interpreter build only). Use
// MD_REPLAY_VALUE_BLOCK=all for every block; MD_REPLAY_VALUE_ADDR=X:15
// limits the trace to one RAM address.
//
//   md_replay <capture dir> [--reloc] [--driver] [--init] [out.wav slot]
//
// --reloc applies <capture dir>/reloc.txt (md_relocate.py) after loading the
// snapshot: each region is copied to its new place (M within P, T from the
// external RAM into private X or Y), the patched words are written, and the
// old region is filled with 0xa5a5a5, so any address the relocation missed
// reads garbage or jumps into it.
//
// Prints matching/mismatching blocks per slot. Exit 0 when every block of
// every slot is bit-identical.

#include "dsp56kEmu/dsp.h"
#include "dsp56kEmu/memory.h"
#include "dsp56kEmu/peripherals.h"
#include "dsp56kEmu/jitconfig.h"
#include "dsp56kEmu/disasm.h"
#include "dsp56kEmu/opcodes.h"

#include <algorithm>
#include <array>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <map>
#include <sstream>
#include <string>
#include <unordered_map>
#include <vector>

#ifdef MD_REPLAY_READS
namespace
{
	constexpr dsp56k::TWord g_readLo = 0x100000, g_readHi = 0x150000;
	std::vector<uint8_t> g_readFlags;

	// MD_REPLAY_ACCESS=<file> (same build): every data access the executing
	// instruction made, by PC, space and direction, for md_flip.py. The PC is
	// set by the exec hook (one interpreted instruction per dsp.exec()) and
	// cleared after each exec, so the replay's own snapshot and host-stream
	// pokes are never charged to an instruction. Internal X/Y (below 0x10000),
	// the OT window (g_winLo..g_winHi) and the external RAM (g_readLo..g_readHi)
	// are kept; peripherals are not.
	// Written as "<pc> <P|X|Y> <r|w> <lo> <hi> <count>" runs (end exclusive),
	// count being the key's total accesses, repeated on each of its runs.
	constexpr dsp56k::TWord g_noPc = 0xffffffff, g_intHi = 0x10000, g_winLo = 0x30000, g_winHi = 0x40000;
	dsp56k::TWord g_curPc = g_noPc;
	dsp56k::Memory* g_valueMemory = nullptr;
	FILE* g_valueFile = nullptr;
	size_t g_valueBlock = SIZE_MAX, g_valueTarget = SIZE_MAX;
	bool g_valueFilter = false;
	dsp56k::EMemArea g_valueFilterArea = dsp56k::MemArea_X;
	dsp56k::TWord g_valueFilterAddr = 0;
	bool g_access = false;
	struct AccessBits
	{
		std::vector<uint64_t> in, ext, win;	// bitmaps: 0..g_intHi, g_readLo..g_readHi, g_winLo..g_winHi
		uint64_t count = 0;
	};
	std::unordered_map<uint64_t, AccessBits> g_accessMap;	// (pc << 8 | area << 1 | write)
	std::vector<uint8_t> g_executed;	// every PC the exec hook saw, below g_readHi

	void recordAccess(dsp56k::EMemArea _area, dsp56k::TWord _offset, bool _write)
	{
		if(g_curPc == g_noPc)
			return;
		const bool internal = _offset < g_intHi;
		// The OT-side window (0x30000..0x3ffff) is where a relocated run keeps
		// the sine, code and some tables; it is kept with the external RAM.
		const bool window = _offset >= g_winLo && _offset < g_winHi;
		if(!internal && !window && (_offset < g_readLo || _offset >= g_readHi))
			return;
		auto& b = g_accessMap[static_cast<uint64_t>(g_curPc) << 8 | static_cast<uint64_t>(_area) << 1 | (_write ? 1 : 0)];
		auto& bits = internal ? b.in : window ? b.win : b.ext;
		if(bits.empty())
			bits.assign(((internal ? g_intHi : window ? g_winHi - g_winLo : g_readHi - g_readLo) + 63) / 64, 0);
		const auto i = internal ? _offset : window ? _offset - g_winLo : _offset - g_readLo;
		bits[i >> 6] |= 1ull << (i & 63);
		++b.count;
	}

	void onRead(dsp56k::EMemArea _area, dsp56k::TWord _offset)
	{
		if(g_access)
			recordAccess(_area, _offset, false);
		if(g_valueFile && g_curPc != g_noPc && g_valueBlock != SIZE_MAX &&
			(g_valueTarget == SIZE_MAX || g_valueBlock == g_valueTarget) &&
			(!g_valueFilter || (_area == g_valueFilterArea && _offset == g_valueFilterAddr)) &&
			(_offset < g_intHi || (_offset >= g_winLo && _offset < g_winHi) ||
			 (_offset >= g_readLo && _offset < g_readHi)))
		{
			// The hook precedes Memory::get's return. Mirror only RAM reads
			// with the hook disabled, so the lookup cannot recurse.
			dsp56k::g_mdReadHook = nullptr;
			const auto value = g_valueMemory->get(_area, _offset);
			dsp56k::g_mdReadHook = onRead;
			const char area = _area == dsp56k::MemArea_P ? 'P' : _area == dsp56k::MemArea_X ? 'X' : 'Y';
			std::fprintf(g_valueFile, "%zu %06x %c %06x %06x\n", g_valueBlock, g_curPc, area, _offset, value);
		}
		if(_offset < g_readLo || _offset >= g_readHi)
			return;
		g_readFlags[_offset - g_readLo] |= _area == dsp56k::MemArea_P ? 1 : _area == dsp56k::MemArea_X ? 2 : 4;
	}

	void onWrite(dsp56k::EMemArea _area, dsp56k::TWord _offset)
	{
		if(g_access)
			recordAccess(_area, _offset, true);
	}

	void onExecAccess(dsp56k::DSP* _dsp)
	{
		g_curPc = _dsp->getPC().toWord();
		if(g_curPc < g_executed.size())
			g_executed[g_curPc] = 1;
	}

	void writeAccess(const char* _path, const std::string& _header)
	{
		dsp56k::g_mdReadHook = nullptr;
		dsp56k::g_mdWriteHook = nullptr;
		g_access = false;
		std::vector<uint64_t> keys;
		for(const auto& [k, b] : g_accessMap)
			keys.push_back(k);
		std::sort(keys.begin(), keys.end());
		FILE* f = std::fopen(_path, "w");
		if(!f)
			return;
		std::fprintf(f, "# %s\n", _header.c_str());
		// "E <lo> <hi>": the executed PCs (instruction starts), as runs.
		for(dsp56k::TWord i = 0; i < g_executed.size();)
		{
			if(!g_executed[i])
			{
				++i;
				continue;
			}
			dsp56k::TWord j = i;
			while(j < g_executed.size() && g_executed[j])
				++j;
			std::fprintf(f, "E %06x %06x\n", i, j);
			i = j;
		}
		static const char* areas[3] = {"P", "X", "Y"};
		for(const auto k : keys)
		{
			const auto& b = g_accessMap[k];
			const auto pc = static_cast<dsp56k::TWord>(k >> 8);
			const auto* area = areas[(k >> 1) & 0x7f];
			const char rw = (k & 1) ? 'w' : 'r';
			for(const auto* bits : {&b.in, &b.win, &b.ext})
			{
				const dsp56k::TWord base = bits == &b.in ? 0 : bits == &b.win ? g_winLo : g_readLo;
				const auto n = static_cast<dsp56k::TWord>(bits->size() * 64);
				for(dsp56k::TWord i = 0; i < n;)
				{
					if(!((*bits)[i >> 6] >> (i & 63) & 1))
					{
						++i;
						continue;
					}
					dsp56k::TWord j = i;
					while(j < n && ((*bits)[j >> 6] >> (j & 63) & 1))
						++j;
					std::fprintf(f, "%06x %s %c %06x %06x %llu\n", pc, area, rw, base + i, base + j,
						static_cast<unsigned long long>(b.count));
					i = j;
				}
			}
		}
		std::fclose(f);
	}
}
#endif

using namespace dsp56k;

namespace
{
	constexpr TWord g_pMemSize = 0x800000, g_xyMemSize = 0x800000, g_bridgedAddr = 0x020000;
	constexpr uint32_t g_snapP = 0x150000, g_snapXY = 0x20000;

	struct Entry
	{
		char kind;
		uint32_t slot;
		std::vector<TWord> words;
	};

	// MD_REPLAY_FETCH=1 (meaningful only in an interpreter build, where the
	// exec hook sees every instruction): count the program words fetched
	// from the engine code regions, where the OT would fetch them from the
	// shared window at one wait state each (AN3653 §2.4). A rep'd
	// instruction is fetched once, as on the chip; a do loop's body once
	// per iteration (no instruction cache on the DSP5672x).
	struct Fetch
	{
		const dsp56k::Opcodes opcodes;
		dsp56k::Disassembler dis{opcodes};
		std::unordered_map<TWord, TWord> len;
		uint64_t engineWords = 0, engineInstructions = 0, otherInstructions = 0;
		std::unordered_map<TWord, uint64_t> perPc;	// MD_REPLAY_FETCH=2: words fetched per address
	};
	Fetch* g_fetch = nullptr;
	bool g_fetchPerPc = false;

	bool inEngineCode(TWord _pc)
	{
		return (_pc >= 0x100000 && _pc < 0x148000) || (_pc >= 0x30000 && _pc < 0x40000);
	}

	// The empty slot's render (P:10008f..10009a): 32 zeros and a busy-wait of
	// ~3,200 fetches, the MD's pacing; an OT driver does not call it. Its
	// cycles and fetches are left out.
	TWord g_emptyLo = 0x10008f, g_emptyHi = 0x10009a;	// moved with --reloc
	bool inEmptyRender(TWord _pc) { return _pc >= g_emptyLo && _pc <= g_emptyHi; }
	uint64_t g_lastCycles = 0, g_emptyCycles = 0;
	TWord g_lastPc = 0;

	void onExecFetch(DSP* _dsp)
	{
		const auto pc = _dsp->getPC().toWord();
		const uint64_t c = _dsp->getCycles();
		if(inEmptyRender(g_lastPc))
			g_emptyCycles += c - g_lastCycles;
		g_lastCycles = c;
		g_lastPc = pc;
		if(inEmptyRender(pc))
			return;
		if(!inEngineCode(pc))
		{
			++g_fetch->otherInstructions;
			return;
		}
		auto it = g_fetch->len.find(pc);
		if(it == g_fetch->len.end())
		{
			std::string text;
			const auto& m = _dsp->memory();
			const auto l = g_fetch->dis.disassemble(text, m.get(MemArea_P, pc), m.get(MemArea_P, pc + 1), 0, 0, pc);
			it = g_fetch->len.emplace(pc, l ? l : 1).first;
		}
		g_fetch->engineWords += it->second;
		++g_fetch->engineInstructions;
		if(g_fetchPerPc)
			g_fetch->perPc[pc] += it->second;
	}

	std::vector<Entry> readLog(const std::string& _path)
	{
		std::vector<Entry> out;
		std::ifstream in(_path);
		std::string line;
		while(std::getline(in, line))
		{
			std::istringstream ss(line);
			Entry e;
			ss >> e.kind;
			if(e.kind == 'C' || e.kind == 'W')
				ss >> std::hex >> e.slot >> std::dec;	// the host word, not a slot
			else
				ss >> e.slot;
			std::string w;
			while(ss >> w)
				e.words.push_back(static_cast<TWord>(std::stoul(w, nullptr, 16)));
			out.push_back(std::move(e));
		}
		return out;
	}
}

int main(int _argc, char** _argv)
{
	if(_argc < 2)
	{
		std::cerr << "usage: md_replay <capture dir> [out.wav slot]\n";
		return 2;
	}
	const std::string dir = _argv[1];
	// Flags right after the capture dir: --reloc, --driver (either order).
	bool reloc = false, driver = false, init = false;
	while(_argc > 2 && (std::string(_argv[2]) == "--reloc" || std::string(_argv[2]) == "--driver" || std::string(_argv[2]) == "--init"))
	{
		const std::string flag = _argv[2];
		if(flag == "--reloc") reloc = true;
		else if(flag == "--driver") driver = true;
		else init = true;
		for(int i = 2; i + 1 < _argc; ++i)
			_argv[i] = _argv[i + 1];
		--_argc;
	}
	if(init && !reloc)
	{
		std::cerr << "--init requires --reloc\n";
		return 2;
	}
	if(init && driver)
	{
		std::cerr << "--init and --driver are separate modes\n";
		return 2;
	}

	DefaultMemoryValidator validator;
	std::vector<TWord> buffer(Memory::calcMemSize(g_pMemSize, g_xyMemSize, g_bridgedAddr), 0);
	Memory memory(validator, g_pMemSize, g_xyMemSize, g_bridgedAddr, buffer.data());
	PeripheralsNop periphNop;
	Peripherals56303 periphX;
	DSP dsp(memory, &periphX, &periphNop);

	auto config = dsp.getJit().getConfig();
	config.aguSupportBitreverse = true;
	config.linkJitBlocks = false;
	config.dynamicPeripheralAddressing = false;
	config.dynamicFastInterrupts = true;
	config.maxInstructionsPerBlock = 32;
	dsp.getJit().setConfig(config);

	// Memory: P, then internal X and Y, exactly as md_profile wrote them.
	std::vector<TWord> snapX(g_snapXY), snapY(g_snapXY);
	{
		FILE* f = std::fopen((dir + "/snapshot.bin").c_str(), "rb");
		if(!f)
		{
			std::cerr << "no snapshot in " << dir << "\n";
			return 1;
		}
		auto load = [&](EMemArea _a, uint32_t _n)
		{
			for(uint32_t i = 0; i < _n; ++i)
			{
				uint32_t w;
				if(std::fread(&w, 4, 1, f) != 1)
				{
					std::cerr << "short snapshot\n";
					std::exit(1);
				}
				memory.set(_a, i, w);
			}
		};
		load(MemArea_P, g_snapP);
		load(MemArea_X, g_snapXY);
		load(MemArea_Y, g_snapXY);
		for(TWord i = 0; i < g_snapXY; ++i)
		{
			snapX[i] = memory.get(MemArea_X, i);
			snapY[i] = memory.get(MemArea_Y, i);
		}
		std::fclose(f);
	}
	{
		std::ifstream r(dir + "/regs.txt");
		int e;
		std::string v;
		while(r >> e >> v)
		{
			const auto val = std::stoull(v, nullptr, 16);
			if(e == Reg_A || e == Reg_B)
			{
				TReg56 t;
				t.var = static_cast<int64_t>(val);
				dsp.writeReg(static_cast<EReg>(e), t);
			}
			else
				dsp.writeReg(static_cast<EReg>(e), TReg24(static_cast<TWord>(val)));
		}
	}
	std::vector<std::array<TWord, 3>> moves;
	std::map<TWord, TWord> vmap;	// the loop's Y words, when moved (V lines)
	struct XyMove { EMemArea area; TWord oldStart, oldEnd, newStart; };
	std::vector<XyMove> xyMoves;
	TWord initPiStart = 0, initPiEnd = 0;
	if(reloc)
	{
		std::ifstream in(dir + "/reloc.txt");
		std::string kind, a, b, c;
		std::vector<std::array<TWord, 2>> tableMoves;	// T sources, wiped like M's
		size_t written = 0;
		while(in >> kind)
		{
			if(kind == "M")
			{
				in >> a >> b >> c;
				moves.push_back({static_cast<TWord>(std::stoul(a, nullptr, 16)), static_cast<TWord>(std::stoul(b, nullptr, 16)),
					static_cast<TWord>(std::stoul(c, nullptr, 16))});
				const auto& m = moves.back();
				for(TWord i = 0; i < m[1] - m[0]; ++i)
					memory.set(MemArea_P, m[2] + i, memory.get(MemArea_P, m[0] + i));
			}
			else if(kind == "V")
			{
				in >> a >> b;
				const auto o = static_cast<TWord>(std::stoul(a, nullptr, 16)), n = static_cast<TWord>(std::stoul(b, nullptr, 16));
				memory.set(MemArea_Y, n, memory.get(MemArea_Y, o));
				memory.set(MemArea_Y, o, 0xa5a5a5);
				vmap[o] = n;
			}
			else if(kind == "Q")
			{
				std::string areaName;
				in >> areaName >> a >> b >> c;
				const auto area = areaName == "X" ? MemArea_X : MemArea_Y;
				const auto oldStart = static_cast<TWord>(std::stoul(a, nullptr, 16));
				const auto oldEnd = static_cast<TWord>(std::stoul(b, nullptr, 16));
				const auto newStart = static_cast<TWord>(std::stoul(c, nullptr, 16));
				xyMoves.push_back({area, oldStart, oldEnd, newStart});
				for(TWord i = 0; i < oldEnd - oldStart; ++i)
					memory.set(area, newStart + i, memory.get(area, oldStart + i));
				for(TWord i = oldStart; i < oldEnd; ++i)
					memory.set(area, i, 0xa5a5a5);
				written += oldEnd - oldStart;
			}
			else if(kind == "I")
			{
				in >> a >> b;
				initPiStart = static_cast<TWord>(std::stoul(a, nullptr, 16));
				initPiEnd = static_cast<TWord>(std::stoul(b, nullptr, 16));
			}
			else if(kind == "T")
			{
				// A table from the MD's external RAM into private X or Y.
				std::string areaName;
				in >> areaName >> a >> b >> c;
				const auto area = areaName == "X" ? MemArea_X : MemArea_Y;
				const auto oldStart = static_cast<TWord>(std::stoul(a, nullptr, 16));
				const auto oldEnd = static_cast<TWord>(std::stoul(b, nullptr, 16));
				const auto newStart = static_cast<TWord>(std::stoul(c, nullptr, 16));
				for(TWord i = 0; i < oldEnd - oldStart; ++i)
					memory.set(area, newStart + i, memory.get(MemArea_P, oldStart + i));
				tableMoves.push_back({oldStart, oldEnd});
				written += oldEnd - oldStart;
			}
			else if(kind == "H")
				in >> a >> b;
			else if(kind == "Z")
			{
				in >> a >> b;
				for(TWord i = static_cast<TWord>(std::stoul(a, nullptr, 16)); i < std::stoul(b, nullptr, 16); ++i)
					memory.set(MemArea_P, i, 0xa5a5a5);
			}
			else
			{
				in >> a >> b;
				const auto area = kind == "X" ? MemArea_X : kind == "Y" ? MemArea_Y : MemArea_P;
				memory.set(area, static_cast<TWord>(std::stoul(a, nullptr, 16)), static_cast<TWord>(std::stoul(b, nullptr, 16)));
				++written;
			}
		}
		// MD_REPLAY_KEEP_OLD=1 leaves the old regions intact: a relocated run that
		// then matches points at a missed reference, one that still differs at a
		// wrong patch.
		// MD_REPLAY_WIPE=<start>-<end> wipes only that old range (a bisection aid).
		if(const char* only = std::getenv("MD_REPLAY_WIPE"))
		{
			const std::string r = only;
			const auto dash = r.find('-');
			for(TWord i = std::stoul(r.substr(0, dash), nullptr, 16); i < std::stoul(r.substr(dash + 1), nullptr, 16); ++i)
				memory.set(MemArea_P, i, 0xa5a5a5);
		}
		else if(!std::getenv("MD_REPLAY_KEEP_OLD"))
		{
			for(const auto& m : moves)
				for(TWord i = m[0]; i < m[1]; ++i)
					memory.set(MemArea_P, i, 0xa5a5a5);
			for(const auto& m : tableMoves)
				for(TWord i = m[0]; i < m[1]; ++i)
					memory.set(MemArea_P, i, 0xa5a5a5);
		}
		std::cout << "relocated " << moves.size() << " code spans and " << tableMoves.size() << " tables, "
			<< written << " patched words; old regions wiped\n";
	}
	// Map host writes and snapshot record bases when the OT voice records move
	// from the MD's low Y/X block into the proposed private voice home.
	auto moveXY = [&](EMemArea area, TWord address)
	{
		for(auto it = xyMoves.rbegin(); it != xyMoves.rend(); ++it)
			if(it->area == area && address >= it->oldStart && address < it->oldEnd)
				return it->newStart + address - it->oldStart;
		return address;
	};
	auto moveP = [&](TWord address)
	{
		for(auto it = moves.rbegin(); it != moves.rend(); ++it)
			if(address >= (*it)[0] && address < (*it)[1])
				return (*it)[2] + address - (*it)[0];
		return address;
	};
	for(const auto& m : xyMoves)
		if(m.area == MemArea_Y)
			for(TWord i = 0; i < m.oldEnd - m.oldStart; ++i)
				snapY[m.newStart + i] = snapY[m.oldStart + i];
	// Where the empty slot's render lives now (a later move, a hot unit,
	// takes precedence over its region's).
	for(auto it = moves.rbegin(); it != moves.rend(); ++it)
	{
		const auto& m = *it;
		if(0x10008f >= m[0] && 0x10009a < m[1])
		{
			g_emptyLo = m[2] + (0x10008f - m[0]);
			g_emptyHi = m[2] + (0x10009a - m[0]);
			break;
		}
	}
	// --driver: <capture dir>/driver.bin and driver.sym (md_driver.py) replace
	// the MD loop. The snapshot stands at a slot-0 loop head, which is the
	// driver's md_slot with the same loop words; the replay stops at md_slot
	// and md_done where it stopped at P:6b and P:b5, and there is no I/O to
	// step past.
	TWord slotPc = 0x6b, donePc = 0xb5, enterPc = 0, idlePc = 0xffffff;
	if(driver)
	{
		std::map<std::string, TWord> syms;
		{
			std::ifstream in(dir + "/driver.sym");
			std::string k, v;
			while(in >> k >> v)
				syms[k] = static_cast<TWord>(std::stoul(v, nullptr, 16));
		}
		std::ifstream in(dir + "/driver.bin");
		std::string w;
		TWord at = syms.at("md_enter");
		while(in >> w)
			memory.set(MemArea_P, at++, static_cast<TWord>(std::stoul(w, nullptr, 16)));
		slotPc = syms.at("md_slot");
		donePc = syms.at("md_done");
		enterPc = syms.at("md_enter");
		idlePc = syms.at("md_idle");
		// The driver's storage (driver.cfg): it starts on the first half,
		// with the MD's 36 words that outlive a period taken from the
		// snapshot (X:$a0-$bf, then Y:$1e-$21, as md_leave stores them).
		std::map<std::string, TWord> cfg;
		{
			std::ifstream cin(dir + "/driver.cfg");
			std::string k, v;
			while(cin >> k >> v)
				cfg[k] = static_cast<TWord>(std::stoul(v, nullptr, 16));
		}
		memory.set(MemArea_Y, cfg.at("HALF"), 0);
		// MDSAVE holds the MD's low image as md_leave stores it: the whole
		// X:0-$ff then Y:0-$13f (576 words) when driver.cfg says MDFULL, else
		// X:$a0-$bf then Y:$1e-$21 (36).
		if(cfg.count("MDFULL") && cfg.at("MDFULL"))
		{
			for(TWord k = 0; k < 0x100; ++k)
				memory.set(MemArea_Y, cfg.at("MDSAVE") + k, memory.get(MemArea_X, k));
			for(TWord k = 0; k < 0x140; ++k)
				memory.set(MemArea_Y, cfg.at("MDSAVE") + 0x100 + k, memory.get(MemArea_Y, k));
		}
		else
		{
			for(TWord k = 0; k < 32; ++k)
				memory.set(MemArea_Y, cfg.at("MDSAVE") + k, memory.get(MemArea_X, 0xa0 + k));
			for(TWord k = 0; k < 4; ++k)
				memory.set(MemArea_Y, cfg.at("MDSAVE") + 32 + k, memory.get(MemArea_Y, 0x1e + k));
		}
		// The MD loop is not used: fill it, so nothing can fall back into it.
		for(TWord a = 0x64; a < 0xe8; ++a)
			memory.set(MemArea_P, a, 0xa5a5a5);
		std::cout << "driver: " << (at - syms.at("md_enter")) << " words at " << std::hex << syms.at("md_enter") << std::dec << "\n";
	}
	dsp.setPC(driver ? enterPc : slotPc);

	const auto log = readLog(dir + "/log.txt");
	// A capture that logs each slot's words after the render ("S" lines)
	// says which words the host wrote: those that differ at the next P:6b.
	// Without them, the first 16 words are taken as the host's.
	// Captures since the host stream was logged carry it as "C <vector>" and
	// "W <word>" lines: a packet is W <dest>, C 0x12, W <count-1>, then the
	// words, which the handler's DMA writes to Y:<dest>... . Each write goes
	// in before the next slot's P:6b after it was sent, so a packet that
	// arrives while a slot renders reaches that slot next time round.
	struct Group
	{
		const Entry* rec = nullptr;
		const Entry* ref = nullptr;
		const Entry* state = nullptr;
		std::vector<std::pair<TWord, TWord>> writes;
	};
	std::vector<Group> groups;
	bool hostStream = false;
	{
		std::vector<std::pair<TWord, TWord>> pending;
		TWord lastW = 0, dest = 0, count = 0, done = 0;
		bool open = false, expectCount = false;
		for(const auto& e : log)
		{
			if(e.kind == 'C' || e.kind == 'W')
			{
				hostStream = true;
				const TWord v = e.slot;	// readLog puts the first field in slot
				if(e.kind == 'C')
				{
					open = v == 0x12;
					expectCount = open;
					dest = lastW;
					count = done = 0;
				}
				else if(expectCount)
				{
					count = v + 1;
					expectCount = false;
				}
				else if(open && done < count)
					pending.emplace_back(dest + done++, v);
				else
					lastW = v;
			}
			else if(e.kind == 'R')
			{
				groups.push_back({&e, nullptr, nullptr, std::move(pending)});
				pending.clear();
			}
			else if(e.kind == 'O' && !groups.empty())
				groups.back().ref = &e;
			else if(e.kind == 'S' && !groups.empty())
				groups.back().state = &e;
		}
		if(!groups.empty() && !groups.back().ref)
			groups.pop_back();
	}
	std::map<uint32_t, std::vector<TWord>> after;	// slot -> words after its last render
	auto y = [&](TWord _a) { return memory.get(MemArea_Y, _a); };
	// A loop word's address, moved or not.
	auto lv = [&](TWord _a) { const auto it = vmap.find(_a); return it == vmap.end() ? _a : it->second; };

	// MD_REPLAY_WATCH=<pc>[,<pc>...] prints every register whenever a block
	// starts at one of those addresses (a routine's entry is one), with
	// MD_REPLAY_WATCH_MAX (default 8) prints in all.
	std::vector<TWord> watch;
	if(const char* w = std::getenv("MD_REPLAY_WATCH"))
	{
		std::stringstream ss(w);
		std::string item;
		while(std::getline(ss, item, ','))
			watch.push_back(static_cast<TWord>(std::stoul(item, nullptr, 16)));
	}
	int watchLeft = std::getenv("MD_REPLAY_WATCH_MAX") ? std::atoi(std::getenv("MD_REPLAY_WATCH_MAX")) : 8;
	const size_t watchTargetBlock = std::getenv("MD_REPLAY_WATCH_BLOCK") ?
		std::stoull(std::getenv("MD_REPLAY_WATCH_BLOCK")) : SIZE_MAX;
	size_t watchCurrentBlock = SIZE_MAX;
	auto dumpRegs = [&](TWord _pc)
	{
		std::printf("watch %06x:", _pc);
		for(int e = Reg_X0; e <= Reg_M7; ++e)
		{
			TReg24 v;
			if(e == Reg_A2 || e == Reg_B2 || e == Reg_SSH || e == Reg_SSL)
				continue;
			if(dsp.readReg(static_cast<EReg>(e), v))
				std::printf(" %d=%06x", e, v.toWord());
		}
		for(int e : {Reg_A, Reg_B})
		{
			TReg56 v;
			if(dsp.readReg(static_cast<EReg>(e), v))
				std::printf(" %s=%014llx", e == Reg_A ? "A" : "B", static_cast<unsigned long long>(v.var & 0xffffffffffffffull));
		}
		std::printf("\n");
	};

	// Run until the PC reaches one of _stops (checked at block boundaries).
	auto runTo = [&](std::initializer_list<TWord> _stops) -> TWord
	{
		for(uint64_t n = 0; n < 2'000'000; ++n)
		{
			const auto pc = dsp.getPC().toWord();
			if(watchLeft > 0 && (watchTargetBlock == SIZE_MAX || watchCurrentBlock == watchTargetBlock))
				for(auto w : watch)
					if(pc == w)
					{
						dumpRegs(pc);
						--watchLeft;
						// MD_REPLAY_WATCH_DUMP=<file>: X and Y 0..$1fff at the first hit.
						static bool dumped = false;
						if(const char* f = std::getenv("MD_REPLAY_WATCH_DUMP"); f && !dumped)
						{
							dumped = true;
							FILE* o = std::fopen(f, "w");
							for(TWord a = 0; a < 0x2000; ++a)
								std::fprintf(o, "%06x %06x\n", memory.get(MemArea_X, a), memory.get(MemArea_Y, a));
							std::fclose(o);
						}
					}
			for(auto s : _stops)
				if(pc == s)
					return pc;
			// The loop reports its slot to the host every fourth slot (P:73);
			// nobody reads the host port here, so drain it or the write blocks.
			while(periphX.getHI08().hasTX())
				periphX.getHI08().readTX();
		dsp.exec();
#ifdef MD_REPLAY_READS
			g_curPc = g_noPc;
#endif
		}
		std::cerr << "no stop reached, pc " << std::hex << dsp.getPC().toWord() << "\n";
		std::exit(1);
	};

	if(init)
	{
		TWord sineDest = 0;
		TWord voiceXDest = 0, voiceYDest = 0;
		for(const auto& m : moves)
			if(m[0] == 0x140000 && m[1] == 0x148000)
				sineDest = m[2];
		for(const auto& m : xyMoves)
		{
			if(m.area == MemArea_X && m.oldStart == 0x800 && m.oldEnd == 0xc00)
				voiceXDest = m.newStart;
			if(m.area == MemArea_Y && m.oldStart == 0x800 && m.oldEnd == 0xc00)
				voiceYDest = m.newStart;
		}
		if(!sineDest || !voiceXDest || !voiceYDest || initPiEnd <= initPiStart)
		{
			std::cerr << "reloc.txt has no complete --init layout ranges\n";
			return 2;
		}

		const TWord sineWords = 0x8000, voiceWords = 0x400, piWords = initPiEnd - initPiStart;
		std::vector<TWord> sineRef(sineWords), piRef(piWords);
		for(TWord i = 0; i < sineWords; ++i)
			sineRef[i] = memory.get(MemArea_P, 0x148000 + i);
		for(TWord i = 0; i < piWords; ++i)
			piRef[i] = memory.get(MemArea_P, 0x135600 + i);
		// The relocated init owns these destinations. Start them empty even if
		// the capture snapshot happened to contain a previous run's state.
		for(TWord i = 0; i < sineWords; ++i)
			memory.set(MemArea_P, sineDest + i, 0);
		for(TWord i = 0; i < piWords; ++i)
			memory.set(MemArea_P, initPiStart + i, 0);
		for(TWord i = 0; i < voiceWords; ++i)
		{
			memory.set(MemArea_X, voiceXDest + i, 0);
			memory.set(MemArea_Y, voiceYDest + i, 0);
		}

		const TWord initPc = moveP(0x100057), initReturn = moveP(0x10008d);
		// The straight-line init ends in an RTS.  Keep the replay's stop at
		// that instruction instead of allowing a JIT block to execute the RTS
		// and return through the snapshot's unrelated stack.
		auto initConfig = dsp.getJit().getConfig();
		initConfig.maxInstructionsPerBlock = 1;
		dsp.getJit().setConfig(initConfig);
		dsp.setPC(initPc);
		runTo({initReturn});
		size_t sineBad = 0, piBad = 0, voiceXBad = 0, voiceYBad = 0;
		for(TWord i = 0; i < sineWords; ++i)
			if(memory.get(MemArea_P, sineDest + i) != sineRef[i])
				++sineBad;
		for(TWord i = 0; i < piWords; ++i)
			if(memory.get(MemArea_P, initPiStart + i) != piRef[i])
				++piBad;
		for(TWord i = 0; i < voiceWords; ++i)
		{
			if(memory.get(MemArea_X, voiceXDest + i) != snapX[0x800 + i])
				++voiceXBad;
			if(memory.get(MemArea_Y, voiceYDest + i) != snapY[0x800 + i])
				++voiceYBad;
		}
		std::cout << "init: sine " << (sineWords - sineBad) << "/" << sineWords
			<< " pi " << (piWords - piBad) << "/" << piWords
			<< " voice-X " << (voiceWords - voiceXBad) << "/" << voiceWords
			<< " voice-Y " << (voiceWords - voiceYBad) << "/" << voiceWords << "\n";
		return sineBad || piBad || voiceXBad || voiceYBad ? 3 : 0;
	}

	// At every period boundary (slot 0's P:6b, before the host's writes):
	//
	// MD_REPLAY_FOOTPRINT=1 records which words changed since the previous
	// boundary, in internal X and Y (0..0xfff) and the external RAM past the
	// samples (P:135206..13ffff, P:148000..14ffff), and prints them as ranges.
	//
	// MD_REPLAY_POISON=<area>:<start>-<end>[,...] (hex, end exclusive, areas
	// X, Y, P) fills those ranges with garbage, as the OT's own code would
	// leave them. An output that stays bit-identical means no word there
	// carries anything from one period to the next. The loop's own words
	// (Y:140-142, Y:153-162, X:202, X:243, X:256) are kept: on the OT they
	// belong to the driver that replaces the loop. MD_REPLAY_POISON_ONCE=1
	// poisons only at the first boundary, which tests for tables the
	// voice code reads but never writes.
	struct Range { EMemArea area; TWord start, end; };
	std::vector<Range> poison;
	if(const char* spec = std::getenv("MD_REPLAY_POISON"))
	{
		std::stringstream ss(spec);
		std::string item;
		while(std::getline(ss, item, ','))
		{
			const auto colon = item.find(':'), dash = item.find('-');
			const char a = item[0];
			poison.push_back({a == 'X' ? MemArea_X : a == 'Y' ? MemArea_Y : MemArea_P,
				static_cast<TWord>(std::stoul(item.substr(colon + 1, dash - colon - 1), nullptr, 16)),
				static_cast<TWord>(std::stoul(item.substr(dash + 1), nullptr, 16))});
		}
	}
	const bool poisonOnce = std::getenv("MD_REPLAY_POISON_ONCE") != nullptr;
	const bool footprint = std::getenv("MD_REPLAY_FOOTPRINT") != nullptr;
	const std::vector<Range> tracked = {{MemArea_X, 0, 0x1000}, {MemArea_Y, 0, 0x1000},
		{MemArea_P, 0x135206, 0x140000}, {MemArea_P, 0x148000, 0x150000}};
	std::vector<std::vector<TWord>> lastSeen;
	std::vector<std::vector<uint8_t>> changed;
	size_t periods = 0;
	uint32_t lcg = 0x12345;
	Fetch fetch;
	if(std::getenv("MD_REPLAY_FETCH"))
	{
		g_fetch = &fetch;
		g_fetchPerPc = std::string(std::getenv("MD_REPLAY_FETCH")) == "2";
		g_execHook = &onExecFetch;
	}
	struct PeriodCost { uint64_t cycles, words, instructions; };
	std::vector<PeriodCost> periodCosts;
	uint64_t lastCycles = 0, lastWords = 0, lastIns = 0;
	auto atPeriod = [&]()
	{
		if(g_fetch)
		{
			const uint64_t c = dsp.getCycles() - g_emptyCycles;
			const uint64_t ins = fetch.engineInstructions + fetch.otherInstructions;
			if(periods)
				periodCosts.push_back({c - lastCycles, fetch.engineWords - lastWords, ins - lastIns});
			lastCycles = c;
			lastWords = fetch.engineWords;
			lastIns = ins;
		}
		if(footprint)
		{
			if(lastSeen.empty())
				for(const auto& r : tracked)
				{
					lastSeen.emplace_back(r.end - r.start);
					changed.emplace_back(r.end - r.start, 0);
				}
			for(size_t t = 0; t < tracked.size(); ++t)
				for(TWord a = tracked[t].start; a < tracked[t].end; ++a)
				{
					const auto v = memory.get(tracked[t].area, a);
					auto& l = lastSeen[t][a - tracked[t].start];
					if(periods && v != l)
						changed[t][a - tracked[t].start] = 1;
					l = v;
				}
		}
		if(!poison.empty() && (!poisonOnce || periods == 0))
		{
			const std::vector<std::pair<EMemArea, TWord>> keep = {{MemArea_Y, lv(0x140)}, {MemArea_Y, lv(0x141)}, {MemArea_Y, lv(0x142)},
				{MemArea_X, 0x202}, {MemArea_X, 0x243}, {MemArea_X, 0x256}};
			std::vector<TWord> kept;
			for(const auto& [a, w] : keep)
				kept.push_back(memory.get(a, w));
			std::vector<TWord> engines;
			for(TWord k = 0; k < 16; ++k)
				engines.push_back(memory.get(MemArea_Y, lv(0x153 + k)));
			for(const auto& r : poison)
				for(TWord a = r.start; a < r.end; ++a)
				{
					lcg = lcg * 1103515245u + 12345u;
					memory.set(r.area, a, (lcg >> 8) & 0xffffff);
				}
			for(size_t k = 0; k < keep.size(); ++k)
				memory.set(keep[k].first, keep[k].second, kept[k]);
			for(TWord k = 0; k < 16; ++k)
				memory.set(MemArea_Y, lv(0x153 + k), engines[k]);
		}
		++periods;
	};

#ifdef MD_REPLAY_READS
	const char* readsPath = std::getenv("MD_REPLAY_READS");
	const char* accessPath = std::getenv("MD_REPLAY_ACCESS");
	const char* valuesPath = std::getenv("MD_REPLAY_VALUES");
	if(valuesPath)
	{
		const char* block = std::getenv("MD_REPLAY_VALUE_BLOCK");
		if(!block || !(g_valueFile = std::fopen(valuesPath, "w")))
		{
			std::cerr << "MD_REPLAY_VALUES needs a writable path and MD_REPLAY_VALUE_BLOCK\n";
			return 2;
		}
		g_valueTarget = std::string(block) == "all" ? SIZE_MAX : std::stoull(block);
		if(const char* addr = std::getenv("MD_REPLAY_VALUE_ADDR"))
		{
			char area = 0;
			unsigned value = 0;
			if(std::sscanf(addr, "%c:%x", &area, &value) != 2 ||
			   (area != 'P' && area != 'X' && area != 'Y'))
			{
				std::cerr << "MD_REPLAY_VALUE_ADDR must be P|X|Y:hex-address\n";
				return 2;
			}
			g_valueFilter = true;
			g_valueFilterArea = area == 'P' ? dsp56k::MemArea_P :
			                    area == 'X' ? dsp56k::MemArea_X : dsp56k::MemArea_Y;
			g_valueFilterAddr = value;
		}
		g_valueMemory = &memory;
	}
	if(readsPath || accessPath || valuesPath)
	{
		g_readFlags.assign(g_readHi - g_readLo, 0);
		dsp56k::g_mdReadHook = onRead;
		dsp56k::g_mdWriteHook = onWrite;
	}
	if(accessPath || valuesPath)
	{
		g_access = accessPath != nullptr;
		if(g_access)
			g_executed.assign(g_readHi, 0);
		if(g_fetch)
			g_execHook = [](DSP* _dsp) { onExecAccess(_dsp); onExecFetch(_dsp); };
		else
			g_execHook = [](DSP* _dsp) { onExecAccess(_dsp); };
	}
	// MD_REPLAY_INIT_ONLY=1 (with MD_REPLAY_ACCESS, at MD addresses): run the
	// boot init once (P:100057 to its RTS at P:10008d) on the capture's
	// snapshot, record its accesses and stop. The replay proper never runs
	// init, so its access file cannot show the space init writes through.
	if(accessPath && std::getenv("MD_REPLAY_INIT_ONLY"))
	{
		if(reloc)
		{
			std::cerr << "MD_REPLAY_INIT_ONLY runs at MD addresses; drop --reloc\n";
			return 2;
		}
		dsp.setPC(0x100057);
		runTo({0x10008d});
		writeAccess(accessPath, "init");
		std::cout << "init: accesses recorded\n";
		return 0;
	}
#endif
	std::map<uint32_t, std::array<uint64_t, 2>> stats;	// slot -> {match, mismatch}
	size_t firstBad = SIZE_MAX;
	std::vector<float> wav;
	const int wavSlot = _argc > 3 ? std::atoi(_argv[3]) : -1;

	// MD_REPLAY_BLOCKS=<n> stops after n blocks (a bisection aid).
	const size_t maxBlocks = std::getenv("MD_REPLAY_BLOCKS") ? std::stoul(std::getenv("MD_REPLAY_BLOCKS")) : groups.size();
	for(size_t i = 0; i < groups.size() && i < maxBlocks; ++i)
	{
		watchCurrentBlock = i;
		if(std::getenv("MD_REPLAY_PROGRESS") && i % 256 == 0)
			std::cerr << "replay block " << i << "/" << std::min(maxBlocks, groups.size()) << "\n";
#ifdef MD_REPLAY_READS
		g_valueBlock = i;
#endif
		const auto& g = groups[i];
		const auto& rec = *g.rec;
		const auto& ref = *g.ref;
		if(rec.slot != ref.slot)
		{
			std::cerr << "log out of step at block " << i << "\n";
			return 1;
		}
		// The driver returns to the "dispatcher" after each half: fill low
		// memory with garbage, as the OT's own code would leave it, and call
		// it again.
		// MD_REPLAY_FRAME_KEEP=<area>:<start>-<end>[,...] leaves those words
		// alone (a bisection aid for what the MD needs across frames).
		static const std::vector<Range> frameKeep = [&]
		{
			std::vector<Range> r;
			if(const char* spec = std::getenv("MD_REPLAY_FRAME_KEEP"))
			{
				std::stringstream ss(spec);
				std::string item;
				while(std::getline(ss, item, ','))
				{
					const auto colon = item.find(':'), dash = item.find('-');
					r.push_back({item[0] == 'X' ? MemArea_X : MemArea_Y,
						static_cast<TWord>(std::stoul(item.substr(colon + 1, dash - colon - 1), nullptr, 16)),
						static_cast<TWord>(std::stoul(item.substr(dash + 1), nullptr, 16))});
				}
			}
			return r;
		}();
		auto kept = [&](EMemArea _a, TWord _w)
		{
			for(const auto& k : frameKeep)
				if(k.area == _a && _w >= k.start && _w < k.end)
					return true;
			return false;
		};
		while(runTo({slotPc, idlePc}) == idlePc)
		{
			for(TWord a = 0; a < 0x100; ++a)
			{
				lcg = lcg * 1103515245u + 12345u;
				if(!kept(MemArea_X, a))
					memory.set(MemArea_X, a, (lcg >> 8) & 0xffffff);
			}
			for(TWord a = 0; a < 0x140; ++a)
			{
				lcg = lcg * 1103515245u + 12345u;
				if(!kept(MemArea_Y, a))
					memory.set(MemArea_Y, a, (lcg >> 8) & 0xffffff);
			}
			dsp.setPC(enterPc);
		}
		if(y(lv(0x142)) != rec.slot)
		{
			std::cerr << "slot mismatch at block " << i << ": emulator " << y(lv(0x142)) << ", log " << rec.slot << "\n";
			return 1;
		}
		if(rec.slot == 0)
			atPeriod();
		// Only what the host wrote goes in; the rest of the slot's 64 words is
		// the voice's own state, which the emulator carries forward itself.
		const auto base = y(lv(0x141));
		// MD_REPLAY_STATEDIFF=<n>: before overwriting the record, compare all 64
		// words with the reference's (a moved address counts as equal to its new
		// place) and print the first <n> slots whose state differs.
		static int stateDiffs = std::getenv("MD_REPLAY_STATEDIFF") ? std::atoi(std::getenv("MD_REPLAY_STATEDIFF")) : 0;
		if(stateDiffs > 0)
		{
			auto mapped = [&](TWord _v)
			{
				for(const auto& m : moves)
					if(_v >= m[0] && _v < m[1])
						return m[2] + (_v - m[0]);
				return _v;
			};
			std::string diffs;
			for(size_t k = 0; k < 64 && k < rec.words.size(); ++k)
			{
				const auto e = y(base + static_cast<TWord>(k));
				if(e != rec.words[k] && e != mapped(rec.words[k]))
				{
					char b[64];
					std::snprintf(b, sizeof b, " [%zu] emu %06x ref %06x", k, e, rec.words[k]);
					diffs += b;
				}
			}
			if(!diffs.empty())
			{
				std::printf("state block %zu slot %u:%s\n", i, rec.slot, diffs.c_str());
				--stateDiffs;
			}
		}
		if(hostStream)
		{
			for(const auto& [a, v] : g.writes)
				memory.set(MemArea_Y, moveXY(MemArea_Y, a), v);
		}
		else if(g.state)
		{
			// Older captures: a word that differs from the slot's words after
			// its last render was written by the host in between (blind to a
			// write that lands during the render).
			auto& prev = after[rec.slot];
			if(prev.empty())
				prev.assign(snapY.begin() + base, snapY.begin() + base + 64);
			for(size_t k = 0; k < 64 && k < rec.words.size(); ++k)
				if(rec.words[k] != prev[k])
					memory.set(MemArea_Y, base + static_cast<TWord>(k), rec.words[k]);
			prev = g.state->words;
		}
		else
			for(size_t k = 0; k < 16 && k < rec.words.size(); ++k)
				memory.set(MemArea_Y, base + static_cast<TWord>(k), rec.words[k]);
		runTo({donePc});
		const auto out = y(lv(0x140));
		bool same = true;
		for(uint32_t k = 0; k < 32; ++k)
		{
			const auto w = y(out + k);
			if(w != ref.words[k])
				same = false;
			if(static_cast<int>(rec.slot) == wavSlot)
			{
				const int32_t s = static_cast<int32_t>(w << 8) >> 8;
				wav.push_back(static_cast<float>(s) / 8388608.0f);
			}
		}
		static int outDiffs = std::getenv("MD_REPLAY_OUTDIFF") ? std::atoi(std::getenv("MD_REPLAY_OUTDIFF")) : 0;
		if(!same && outDiffs > 0)
		{
			--outDiffs;
			std::printf("out block %zu slot %u:", i, rec.slot);
			for(uint32_t k = 0; k < 32; ++k)
				if(y(out + k) != ref.words[k])
					std::printf(" %u:%06x/%06x", k, y(out + k), ref.words[k]);
			std::printf("\n");
		}
		++stats[rec.slot][same ? 0 : 1];
		if(!same && firstBad == SIZE_MAX)
			firstBad = i;

		if(driver)
			continue;
		// Past the I/O: slot 0 polls the frame sync (P:bb), every slot waits
		// for the output DMA (P:cf).
		if(runTo({0xbb, 0xcf}) == 0xbb)
		{
			dsp.writeReg(Reg_B1, TReg24((memory.get(MemArea_X, 0x202) ^ 2) & 2));
			dsp.setPC(0xc0);
			runTo({0xcf});
		}
		dsp.setPC(0xd5);
	}

	if(footprint)
	{
		for(size_t t = 0; t < tracked.size(); ++t)
		{
			const char c = tracked[t].area == MemArea_X ? 'X' : tracked[t].area == MemArea_Y ? 'Y' : 'P';
			size_t total = 0;
			std::string runs;
			for(TWord a = tracked[t].start; a < tracked[t].end;)
			{
				if(!changed[t][a - tracked[t].start]) { ++a; continue; }
				TWord e = a;
				while(e < tracked[t].end && changed[t][e - tracked[t].start])
					++e;
				char b[32];
				std::snprintf(b, sizeof b, " %x-%x", a, e - 1);
				runs += b;
				total += e - a;
				a = e;
			}
			std::printf("footprint %c: %zu words changed between periods:%s\n", c, total, runs.c_str());
		}
	}

	if(g_fetch && !periodCosts.empty())
	{
		// Per sample, over the worst 10 ms (14 periods of 32 samples), as
		// md_profile's peakWorkPerSample; the replay skips every I/O wait, so
		// its cycles are all work.
		const size_t w = 14;
		double peakCycles = 0, wordsAtPeak = 0, peakWords = 0, sumCycles = 0, sumWords = 0;
		for(size_t i = 0; i + w <= periodCosts.size(); ++i)
		{
			double c = 0, wd = 0;
			for(size_t k = i; k < i + w; ++k)
			{
				c += periodCosts[k].cycles;
				wd += periodCosts[k].words;
			}
			c /= 32.0 * w;
			wd /= 32.0 * w;
			if(c > peakCycles) { peakCycles = c; wordsAtPeak = wd; }
			peakWords = std::max(peakWords, wd);
		}
		for(const auto& p : periodCosts) { sumCycles += p.cycles; sumWords += p.words; }
		const double n = 32.0 * periodCosts.size();
		std::printf("fetch: %zu periods; per sample: mean %.1f cycles, %.1f engine words fetched; "
			"worst 10 ms %.1f cycles with %.1f words fetched (most words in any 10 ms: %.1f)\n",
			periodCosts.size(), sumCycles / n, sumWords / n, peakCycles, wordsAtPeak, peakWords);
		if(g_fetchPerPc)
		{
			std::vector<std::pair<uint64_t, TWord>> top;
			for(const auto& [pc, w] : fetch.perPc)
				top.emplace_back(w, pc);
			std::sort(top.rbegin(), top.rend());
			for(size_t k = 0; k < top.size() && k < 12; ++k)
				std::printf("fetch pc %06x: %llu words\n", top[k].second, static_cast<unsigned long long>(top[k].first));
			// How much of the fetch traffic the hottest instructions carry, by
			// the program words they occupy (what private P would have to hold).
			uint64_t all = 0, acc = 0, words = 0;
			for(const auto& t : top)
				all += t.first;
			size_t mark = 0;
			const uint64_t marks[] = {256, 512, 1024, 2048, 2724, 4096};
			for(const auto& [w, pc] : top)
			{
				acc += w;
				words += fetch.len[pc];
				while(mark < 6 && words >= marks[mark])
					std::printf("fetch hottest %llu words carry %.1f%%\n", static_cast<unsigned long long>(marks[mark++]), 100.0 * acc / all);
			}
			std::printf("fetch all %llu words executed\n", static_cast<unsigned long long>(words));
			if(FILE* f = std::fopen((dir + "/fetch.txt").c_str(), "w"))
			{
				for(const auto& [w, pc] : top)
					std::fprintf(f, "%06x %u %llu\n", pc, fetch.len[pc], static_cast<unsigned long long>(w));
				std::fclose(f);
			}
		}
	}

#ifdef MD_REPLAY_READS
	if(g_valueFile)
		std::fclose(g_valueFile);
	g_valueFile = nullptr;
	if(readsPath)
	{
		dsp56k::g_mdReadHook = nullptr;
		if(FILE* f = std::fopen(readsPath, "w"))
		{
			static const char* names[8] = {"-", "P", "X", "PX", "Y", "PY", "XY", "PXY"};
			for(TWord i = 0; i < g_readFlags.size();)
			{
				TWord j = i;
				while(j < g_readFlags.size() && g_readFlags[j] == g_readFlags[i])
					++j;
				if(g_readFlags[i])
					std::fprintf(f, "%06x %06x %s\n", g_readLo + i, g_readLo + j, names[g_readFlags[i]]);
				i = j;
			}
			std::fclose(f);
		}
	}
	if(accessPath)
	{
		uint64_t blocks = 0;
		for(const auto& [slot, s] : stats)
			blocks += s[0] + s[1];
		writeAccess(accessPath, "blocks " + std::to_string(blocks));
	}
#endif
	// Where the replay wrote memory: every word that now differs from the
	// snapshot, as runs, to <capture dir>/written.txt.
	{
		FILE* f = std::fopen((dir + "/snapshot.bin").c_str(), "rb");
		FILE* w = std::fopen((dir + "/written.txt").c_str(), "w");
		auto diff = [&](EMemArea _a, uint32_t _n, char _c)
		{
			int64_t runStart = -1, last = -2;
			for(uint32_t i = 0; i < _n; ++i)
			{
				uint32_t v;
				if(std::fread(&v, 4, 1, f) != 1)
					break;
				if(memory.get(_a, i) != v)
				{
					if(i != last + 1)
					{
						if(runStart >= 0)
							std::fprintf(w, "%c %06llx %06llx\n", _c, (long long)runStart, (long long)last);
						runStart = i;
					}
					last = i;
				}
			}
			if(runStart >= 0)
				std::fprintf(w, "%c %06llx %06llx\n", _c, (long long)runStart, (long long)last);
		};
		diff(MemArea_P, g_snapP, 'P');
		diff(MemArea_X, g_snapXY, 'X');
		diff(MemArea_Y, g_snapXY, 'Y');
		std::fclose(f);
		std::fclose(w);
	}

	uint64_t good = 0, bad = 0;
	for(const auto& [slot, s] : stats)
	{
		good += s[0];
		bad += s[1];
		if(s[1])
			std::cout << "slot " << slot << ": " << s[0] << " identical, " << s[1] << " differ\n";
	}
	std::cout << "blocks: " << good << " identical, " << bad << " differ";
	if(firstBad != SIZE_MAX)
		std::cout << " (first difference at block " << firstBad << ")";
	std::cout << "\n";

	if(_argc > 3 && !wav.empty())
	{
		FILE* f = std::fopen(_argv[2], "wb");
		const uint32_t n = static_cast<uint32_t>(wav.size()), bytes = n * 2;
		auto u32 = [&](uint32_t v) { std::fwrite(&v, 4, 1, f); };
		auto u16 = [&](uint16_t v) { std::fwrite(&v, 2, 1, f); };
		std::fwrite("RIFF", 1, 4, f); u32(36 + bytes); std::fwrite("WAVEfmt ", 1, 8, f);
		u32(16); u16(1); u16(1); u32(44100); u32(88200); u16(2); u16(16);
		std::fwrite("data", 1, 4, f); u32(bytes);
		for(auto s : wav)
		{
			const auto v = static_cast<int16_t>(std::max(-1.0f, std::min(1.0f, s)) * 32767.0f);
			std::fwrite(&v, 2, 1, f);
		}
		std::fclose(f);
	}
	return bad ? 3 : 0;
}
