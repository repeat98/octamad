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
//
//   md_replay <capture dir> [--reloc] [out.wav slot]
//
// --reloc applies <capture dir>/reloc.txt (md_relocate.py) after loading the
// snapshot: each region is copied to its new place, the patched words are
// written, and the old region is filled with 0xa5a5a5, so any address the
// relocation missed reads garbage or jumps into it.
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
	bool inEmptyRender(TWord _pc) { return _pc >= 0x10008f && _pc <= 0x10009a; }
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
	const bool reloc = _argc > 2 && std::string(_argv[2]) == "--reloc";
	if(reloc)
	{
		for(int i = 2; i + 1 < _argc; ++i)
			_argv[i] = _argv[i + 1];
		--_argc;
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
	std::vector<TWord> snapY(g_snapXY);
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
			snapY[i] = memory.get(MemArea_Y, i);
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
	if(reloc)
	{
		std::ifstream in(dir + "/reloc.txt");
		std::string kind, a, b, c;
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
			for(const auto& m : moves)
				for(TWord i = m[0]; i < m[1]; ++i)
					memory.set(MemArea_P, i, 0xa5a5a5);
		std::cout << "relocated " << moves.size() << " regions, " << written << " patched words; old regions wiped\n";
	}
	dsp.setPC(0x6b);

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

	// Run until the PC reaches one of _stops (checked at block boundaries).
	auto runTo = [&](std::initializer_list<TWord> _stops) -> TWord
	{
		for(uint64_t n = 0; n < 2'000'000; ++n)
		{
			const auto pc = dsp.getPC().toWord();
			for(auto s : _stops)
				if(pc == s)
					return pc;
			// The loop reports its slot to the host every fourth slot (P:73);
			// nobody reads the host port here, so drain it or the write blocks.
			while(periphX.getHI08().hasTX())
				periphX.getHI08().readTX();
			dsp.exec();
		}
		std::cerr << "no stop reached, pc " << std::hex << dsp.getPC().toWord() << "\n";
		std::exit(1);
	};

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
			const std::vector<std::pair<EMemArea, TWord>> keep = {{MemArea_Y, 0x140}, {MemArea_Y, 0x141}, {MemArea_Y, 0x142},
				{MemArea_X, 0x202}, {MemArea_X, 0x243}, {MemArea_X, 0x256}};
			std::vector<TWord> kept;
			for(const auto& [a, w] : keep)
				kept.push_back(memory.get(a, w));
			std::vector<TWord> engines;
			for(TWord k = 0; k < 16; ++k)
				engines.push_back(memory.get(MemArea_Y, 0x153 + k));
			for(const auto& r : poison)
				for(TWord a = r.start; a < r.end; ++a)
				{
					lcg = lcg * 1103515245u + 12345u;
					memory.set(r.area, a, (lcg >> 8) & 0xffffff);
				}
			for(size_t k = 0; k < keep.size(); ++k)
				memory.set(keep[k].first, keep[k].second, kept[k]);
			for(TWord k = 0; k < 16; ++k)
				memory.set(MemArea_Y, 0x153 + k, engines[k]);
		}
		++periods;
	};

	std::map<uint32_t, std::array<uint64_t, 2>> stats;	// slot -> {match, mismatch}
	size_t firstBad = SIZE_MAX;
	std::vector<float> wav;
	const int wavSlot = _argc > 3 ? std::atoi(_argv[3]) : -1;

	// MD_REPLAY_BLOCKS=<n> stops after n blocks (a bisection aid).
	const size_t maxBlocks = std::getenv("MD_REPLAY_BLOCKS") ? std::stoul(std::getenv("MD_REPLAY_BLOCKS")) : groups.size();
	for(size_t i = 0; i < groups.size() && i < maxBlocks; ++i)
	{
		const auto& g = groups[i];
		const auto& rec = *g.rec;
		const auto& ref = *g.ref;
		if(rec.slot != ref.slot)
		{
			std::cerr << "log out of step at block " << i << "\n";
			return 1;
		}
		runTo({0x6b});
		if(y(0x142) != rec.slot)
		{
			std::cerr << "slot mismatch at block " << i << ": emulator " << y(0x142) << ", log " << rec.slot << "\n";
			return 1;
		}
		if(rec.slot == 0)
			atPeriod();
		// Only what the host wrote goes in; the rest of the slot's 64 words is
		// the voice's own state, which the emulator carries forward itself.
		const auto base = y(0x141);
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
				memory.set(MemArea_Y, a, v);
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

		runTo({0xb5});
		const auto out = y(0x140);
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
