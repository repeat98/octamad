// md_forms: the instruction form the emulator's own decoder assigns to each
// word, for md_flip.py (which X/Y accesses have a twin in the other space).
//
//   md_forms < lines           each line "<addr> <word> [<word b>]" (hex)
//
// prints one line per input line:
//   <addr> <word> <non-parallel pattern | ->  <move pattern | ->  <alu pattern | ->
// The patterns are the 24-character OpcodeInfo strings of opcodeinfo.h
// ("01dd0dddW1MMMRRR????????" is Movex_ea); md_flip.py maps them back to the
// enum names by reading that header, so the classification rests on the
// emulator's decode tables rather than on a hand-written copy of them.

#include "dsp56kEmu/opcodes.h"

#include <cstdio>
#include <iostream>
#include <sstream>
#include <string>

int main()
{
	const dsp56k::Opcodes opcodes;
	std::string line;
	while(std::getline(std::cin, line))
	{
		std::istringstream in(line);
		std::string addr, word;
		if(!(in >> addr >> word) || word.find_first_not_of("0123456789abcdefABCDEF") != std::string::npos)
			continue;
		const auto op = static_cast<dsp56k::TWord>(std::stoul(word, nullptr, 16));
		const dsp56k::OpcodeInfo* np = nullptr;
		const dsp56k::OpcodeInfo* mv = nullptr;
		const dsp56k::OpcodeInfo* alu = nullptr;
		if(dsp56k::Opcodes::isNonParallelOpcode(op))
			np = opcodes.findNonParallelOpcodeInfo(op);
		else
		{
			mv = opcodes.findParallelMoveOpcodeInfo(op);
			alu = opcodes.findParallelAluOpcodeInfo(op);
		}
		std::printf("%s %06x %s %s %s\n", addr.c_str(), op,
			np ? np->m_opcode : "-", mv ? mv->m_opcode : "-", alu ? alu->m_opcode : "-");
	}
	return 0;
}
