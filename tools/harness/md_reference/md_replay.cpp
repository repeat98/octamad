// md_replay: the Machinedrum's voice DSP outside the Machinedrum.
//
// A bare DSP56303 (the reference fork's dsp56kEmu, configured as md::Dsp
// configures it) is loaded from an md_profile capture: the producer's memory
// and registers at a slot-0 loop head. It then runs the original voice loop
// (P:6b..e7) with every I/O wait skipped: before each slot it writes the
// record the reference had at that slot, runs to P:b5 (the engine's render
// has returned), compares the 32 rendered words with the reference's, and
// resumes past the frame-sync poll (P:bb..bf) and the output DMA wait (P:cf).
// No host port, no ESSI link, no ColdFire.
//
//   md_replay <capture dir> [out.wav slot]
//
// Prints matching/mismatching blocks per slot. Exit 0 when every block of
// every slot is bit-identical.

#include "dsp56kEmu/dsp.h"
#include "dsp56kEmu/memory.h"
#include "dsp56kEmu/peripherals.h"
#include "dsp56kEmu/jitconfig.h"

#include <array>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <map>
#include <sstream>
#include <string>
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

	std::vector<Entry> readLog(const std::string& _path)
	{
		std::vector<Entry> out;
		std::ifstream in(_path);
		std::string line;
		while(std::getline(in, line))
		{
			std::istringstream ss(line);
			Entry e;
			ss >> e.kind >> e.slot;
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
	dsp.setPC(0x6b);

	const auto log = readLog(dir + "/log.txt");
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

	std::map<uint32_t, std::array<uint64_t, 2>> stats;	// slot -> {match, mismatch}
	size_t firstBad = SIZE_MAX;
	std::vector<float> wav;
	const int wavSlot = _argc > 3 ? std::atoi(_argv[3]) : -1;

	for(size_t i = 0; i + 1 < log.size(); i += 2)
	{
		const auto& rec = log[i];
		const auto& ref = log[i + 1];
		if(rec.kind != 'R' || ref.kind != 'O' || rec.slot != ref.slot)
		{
			std::cerr << "log out of step at line " << i << "\n";
			return 1;
		}
		runTo({0x6b});
		if(y(0x142) != rec.slot)
		{
			std::cerr << "slot mismatch at line " << i << ": emulator " << y(0x142) << ", log " << rec.slot << "\n";
			return 1;
		}
		const auto base = y(0x141);
		for(size_t k = 0; k < rec.words.size(); ++k)
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
		++stats[rec.slot][same ? 0 : 1];
		if(!same && firstBad == SIZE_MAX)
			firstBad = i / 2;

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
