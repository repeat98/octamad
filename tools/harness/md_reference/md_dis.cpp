// md_dis: decode every address of the given P ranges of an md_profile
// snapshot as if an instruction starts there, one line per address:
//   <addr> <len> <wordA> <wordB> <text>
// md_relocate.py walks this table (recursive descent) to tell code from data.
//
//   md_dis <snapshot.bin> <start>-<end> [...]   (hex, end exclusive)

#include "dsp56kEmu/disasm.h"
#include "dsp56kEmu/opcodes.h"

#include <cstdio>
#include <cstdlib>
#include <iostream>
#include <string>
#include <vector>

int main(int _argc, char** _argv)
{
	if(_argc < 3)
	{
		std::cerr << "usage: md_dis <snapshot.bin> <start>-<end> [...]\n";
		return 2;
	}
	constexpr uint32_t snapP = 0x150000;
	std::vector<uint32_t> p(snapP + 2, 0);
	FILE* f = std::fopen(_argv[1], "rb");
	if(!f || std::fread(p.data(), 4, snapP, f) != snapP)
	{
		std::cerr << "cannot read P from " << _argv[1] << "\n";
		return 1;
	}
	std::fclose(f);

	const dsp56k::Opcodes opcodes;
	dsp56k::Disassembler dis(opcodes);
	for(int a = 2; a < _argc; ++a)
	{
		const std::string r = _argv[a];
		const auto dash = r.find('-');
		const uint32_t start = std::stoul(r.substr(0, dash), nullptr, 16);
		const uint32_t end = std::stoul(r.substr(dash + 1), nullptr, 16);
		for(uint32_t pc = start; pc < end && pc < snapP; ++pc)
		{
			std::string text;
			const auto len = dis.disassemble(text, p[pc], p[pc + 1], 0, 0, pc);
			std::printf("%06x %u %06x %06x %s\n", pc, len, p[pc], p[pc + 1], text.c_str());
		}
	}
	return 0;
}
