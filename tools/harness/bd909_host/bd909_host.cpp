// bd909_host -- run the Analog Bassdrum DSP engine alone, block by block.
//
// The generator is not an FX-slot effect, so dsp_host's dispatcher model does
// not fit it. This host loads the assembled code and its data, then calls the
// block routine once per 16-sample block exactly as dsp_host calls an effect
// (the emulator's own jsr, single-stepped back to a sentinel), and meters the
// executed instructions per block. Instructions, not cycles (CHIP.md §2).
//
//   bd909_host -code gen.bin -org HEX -entry HEX [-init HEX] -data data.txt
//              -script blocks.txt -out out.raw [-meter meter.txt] [-frames 16]
//
// data.txt   lines "X|Y|P <hex addr> <hex word> ..." loaded before init.
// blocks.txt one line per block: twelve knob values 0..127 and a trigger
//            offset (-1 = none). Knob k lands at X:PBLK+k as the value, the
//            trigger at X:PBLK+12 (offset, or $ffffff for none).
// -input     int32 samples (one per frame) put at X:AUDIO as L,R before each
//            call: the desk stage's gate feeds it its own signal.
// Registers on entry: r0 = X:AUDIO (interleaved L,R), r5 = STATE (X and Y),
// r6 = PBLK, n7 = frames. The routine returns with rts.
// out.raw    the L,R words of every block, int32 little-endian, sign-extended.
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

#include "dsp56kEmu/dsp.h"
#include "dsp56kEmu/memory.h"
#include "dsp56kEmu/peripherals.h"

using namespace dsp56k;

namespace {
class AllowAll : public IMemoryValidator {
public:
    bool memValidateAccess(EMemArea, TWord, bool) const override { return true; }
};
const TWord SENTINEL = 0x03f000, PBLK = 0x000100, AUDIO = 0x000000, STATE = 0x000200;

// Executed instructions, from the emulator's own counter: a hardware DO loop
// runs to completion inside ONE execInterpreter() call (dsp_host's meter).
long call(DSP& dsp, TWord pc) {
    dsp.setPC(SENTINEL);
    dsp.jsr(pc);
    const uint64_t i0 = dsp.getInstructionCounter();
    for (long i = 0; i < 20000000; ++i) {
        if (dsp.getPC().toWord() == SENTINEL) return long(dsp.getInstructionCounter() - i0);
        dsp.execInterpreter();
    }
    std::cerr << "no return from " << std::hex << pc << " (pc=" << dsp.getPC().toWord() << ")\n";
    std::exit(3);
}
}

int main(int argc, char** argv) {
    std::string code, data, script, out, meterPath, statePath, inputPath;
    TWord org = 0, entry = 0, init = 0; bool haveInit = false; int frames = 16;
    for (int i = 1; i + 1 < argc; i += 2) {
        std::string k = argv[i], v = argv[i + 1];
        if (k == "-code") code = v;
        else if (k == "-org") org = std::strtoul(v.c_str(), nullptr, 16);
        else if (k == "-entry") entry = std::strtoul(v.c_str(), nullptr, 16);
        else if (k == "-init") { init = std::strtoul(v.c_str(), nullptr, 16); haveInit = true; }
        else if (k == "-data") data = v;
        else if (k == "-script") script = v;
        else if (k == "-out") out = v;
        else if (k == "-meter") meterPath = v;
        else if (k == "-frames") frames = std::atoi(v.c_str());
        else if (k == "-state") statePath = v;   // X:STATE..+63 and Y:STATE..+63 after each block
        else if (k == "-input") inputPath = v;   // int32 LE samples, one per frame, into X:AUDIO (L and R)
        else { std::cerr << "unknown option " << k << "\n"; return 2; }
    }
    if (code.empty() || script.empty() || out.empty()) {
        std::cerr << "usage: bd909_host -code gen.bin -org HEX -entry HEX [-init HEX] -data data.txt -script blocks.txt -out out.raw [-meter m.txt]\n";
        return 2;
    }
    AllowAll validator;
    Memory mem(validator, 0x080000, 0x800000, 0x200000);
    Peripherals56362 px; Peripherals56367 py;
    DSP dsp(mem, &px, &py);

    std::ifstream cf(code, std::ios::binary);
    std::vector<unsigned char> blob((std::istreambuf_iterator<char>(cf)), {});
    if (blob.empty() || blob.size() % 3) { std::cerr << "bad code blob " << code << "\n"; return 2; }
    // dsp_asm writes the payloads' packing: 24-bit words, little-endian
    for (size_t w = 0; w < blob.size() / 3; ++w)
        mem.set(MemArea_P, org + TWord(w), blob[3*w] | (blob[3*w+1] << 8) | (blob[3*w+2] << 16));
    mem.set(MemArea_P, SENTINEL, 0x000000);   // nop; never executed

    if (!data.empty()) {
        std::ifstream df(data); std::string line;
        while (std::getline(df, line)) {
            std::istringstream ls(line); std::string sp; std::string a;
            if (!(ls >> sp >> a)) continue;
            EMemArea area = sp == "X" ? MemArea_X : sp == "Y" ? MemArea_Y : MemArea_P;
            TWord addr = std::strtoul(a.c_str(), nullptr, 16); std::string w;
            while (ls >> w) mem.set(area, addr++, std::strtoul(w.c_str(), nullptr, 16) & 0xffffff);
        }
    }
    auto setRegs = [&] {
        dsp.regs().r[0].var = AUDIO; dsp.regs().r[5].var = STATE; dsp.regs().r[6].var = PBLK;
        dsp.regs().n[7].var = frames;
        for (int k = 0; k < 8; ++k) dsp.regs().m[k].var = 0xffffff;
    };
    long initInstr = 0;
    if (haveInit) { setRegs(); initInstr = call(dsp, init); }

    std::vector<int32_t> input;
    if (!inputPath.empty()) {
        std::ifstream inf(inputPath, std::ios::binary);
        std::vector<char> raw((std::istreambuf_iterator<char>(inf)), {});
        input.resize(raw.size() / 4); std::memcpy(input.data(), raw.data(), input.size() * 4);
    }
    std::ifstream sf(script); std::ofstream of(out, std::ios::binary);
    std::ofstream mf; if (!meterPath.empty()) mf.open(meterPath);
    std::ofstream stf; if (!statePath.empty()) stf.open(statePath);
    std::string line; long block = 0, maxN = 0, sum = 0;
    while (std::getline(sf, line)) {
        std::istringstream ls(line); int v[13];
        for (int k = 0; k < 13; ++k) if (!(ls >> v[k])) { std::cerr << "bad script line " << block << "\n"; return 2; }
        for (int k = 0; k < 12; ++k) mem.set(MemArea_X, PBLK + k, TWord(v[k] & 0x7f));
        mem.set(MemArea_X, PBLK + 12, v[12] < 0 ? 0xffffff : TWord(v[12]));
        for (int s = 0; s < frames && !input.empty(); ++s) {
            const size_t at = size_t(block) * frames + s;
            const TWord w = TWord(at < input.size() ? input[at] : 0) & 0xffffff;
            mem.set(MemArea_X, AUDIO + 2 * s, w); mem.set(MemArea_X, AUDIO + 2 * s + 1, w);
        }
        setRegs();
        long n = call(dsp, entry);
        for (int s = 0; s < 2 * frames; ++s) {
            int32_t w = int32_t(mem.get(MemArea_X, AUDIO + s) << 8) >> 8;
            of.write(reinterpret_cast<char*>(&w), 4);
        }
        if (mf) mf << n << "\n";
        if (stf) {
            for (int k = 0; k < 64; ++k) stf << std::hex << mem.get(MemArea_X, STATE + k) << ' ';
            for (int k = 0; k < 64; ++k) stf << std::hex << mem.get(MemArea_Y, STATE + k) << ' ';
            stf << "\n";
        }
        maxN = std::max(maxN, n); sum += n; ++block;
    }
    std::printf("blocks %ld  init %ld  max %ld instr/block (%.1f/sample)  mean %.1f/sample\n",
                block, initInstr, maxN, double(maxN) / frames, double(sum) / std::max(1L, block) / frames);
    return 0;
}
