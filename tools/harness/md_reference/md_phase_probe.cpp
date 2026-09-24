// Firmware-free regression for the reference JIT's 48-bit X/DO-loop failure.
// Expected: (0x1800 >> 1 >> 4) * 32 = 0x1800, fractional part zero.
// --interpreter and --single-step must pass. --jit exposes the reference
// fork 1378c430's failure; do not use its multi-instruction JIT as an oracle.
// The words below were assembled from this original test program:
// move #>$100,x1
// move #>$20,x0
// move #>$400,r6
// move y:(r6+$7),a
// asr a
// move y:(r6+$10),x0
// add x0,a
// asr #$4,a,a
// move y:(r6+$3),y0
// move y:(r6+$12),b
// move y:(r6+$13),b0
// move a1,x1
// move a0,x0
// move b1,r3
// add x,b
// and #>$7fff,b
// do #31,finish
// add x,b
// and #>$7fff,b
// finish:
// move b1,y:>$500
// move b0,y:>$501
// jmp $200
#include "dsp56kEmu/dsp.h"
#include "dsp56kEmu/memory.h"
#include "dsp56kEmu/peripherals.h"
#include "dsp56kEmu/jitconfig.h"
#include <cstdio>
#include <string>
#include <vector>

using namespace dsp56k;

int main(int argc, char** argv)
{
    const std::string mode = argc == 2 ? argv[1] : "--interpreter";
    if(mode != "--interpreter" && mode != "--single-step" && mode != "--jit")
        return 2;
    DefaultMemoryValidator validator;
    std::vector<TWord> buffer(Memory::calcMemSize(0x20000, 0x10000, 0x10000), 0);
    Memory memory(validator, 0x20000, 0x10000, 0x10000, buffer.data());
    PeripheralsNop nop;
    Peripherals56303 px;
    DSP dsp(memory, &px, &nop);
    auto cfg = dsp.getJit().getConfig();
    cfg.maxInstructionsPerBlock = mode == "--single-step" ? 1 : 32;
    cfg.linkJitBlocks = false;
    dsp.getJit().setConfig(cfg);
    const TWord program[] = {
        0x45f400, 0x000100, 0x44f400, 0x000020, 0x66f400, 0x000400,
        0x021efe, 0x200022, 0x0246b4, 0x200040, 0x0c1c08, 0x020ef6,
        0x024ebf, 0x024ef9, 0x218500, 0x210400, 0x21b300, 0x200028,
        0x0140ce, 0x007fff, 0x061f80, 0x000118, 0x200028, 0x0140ce,
        0x007fff, 0x5d7000, 0x000500, 0x597000, 0x000501, 0x0c0200,
    };
    TWord at = 0x100;
    for(auto word : program)
        memory.set(MemArea_P, at++, word);
    memory.set(MemArea_Y, 0x407, 0x1800);
    memory.set(MemArea_Y, 0x403, 0x5fffff);
    dsp.setPC(0x100);
    for(int n = 0; n < 1000 && dsp.getPC().toWord() != 0x200; ++n)
    {
        if(mode == "--interpreter") dsp.execInterpreter();
        else dsp.exec();
    }
    const auto high = memory.get(MemArea_Y, 0x500);
    const auto low = memory.get(MemArea_Y, 0x501);
    const bool ok = dsp.getPC().toWord() == 0x200 && high == 0x1800 && low == 0;
    std::printf("phase %s: %s, got %06x:%06x, expected 001800:000000\n",
                mode.c_str(), ok ? "PASS" : "FAIL", high, low);
    return ok ? 0 : 1;
}
