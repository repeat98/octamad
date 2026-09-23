// Differential execution of the shipped loop, not a C arithmetic surrogate.
#include <array>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iterator>
#include <vector>
#include "machine.h"
#include "mc68k/Musashi/m68k.h"
#include "mc68k/cpuState.h"

constexpr uint32_t stack = 0x47100000, stop = 0x47200000;
constexpr uint32_t helper = 0x47080000, capture = 0x47090000, scratch = 0x80006960;
static unsigned run(ot::Machine& m, uint32_t pc, uint32_t end) {
    m68k_set_reg(m.getCpuState(), M68K_REG_PC, pc);
    unsigned n = 0;
    while(m.pc() != end && n < 20000) { ++n; if(!m.step()) break; }
    if(m.pc() != end) { std::fprintf(stderr, "Stopped at %08x, expected %08x\n", m.pc(), end); std::exit(1); }
    return n;
}
struct Result {
    std::array<uint32_t,17> regs;
    std::array<uint32_t,8> emac;
    std::vector<uint32_t> ram;
    unsigned instructions;
};
static Result execute(ot::Machine& m, unsigned count, unsigned pattern, unsigned mode,
                      uint32_t capturePc) {
    auto cpu=m.getCpuState();
    m68k_set_reg(cpu,M68K_REG_SR,0x2700);
    m68k_set_reg(cpu,M68K_REG_SP,stack); m.write32(stack,stop);
    // Each Machine shares the emulator's EMAC globals: reinitialize for EVERY run.
    m.write32(helper+2,mode); // immediate operand of probe_init's MOVE #mode,MACSR
    run(m,helper,stop);
    for(unsigned r=0;r<16;++r) m68k_set_reg(cpu,m68k_register_t(M68K_REG_D0+r),0x13570000+r);
    m68k_set_reg(cpu,M68K_REG_SP,stack); m.write32(stack+48,count);
    m68k_set_reg(cpu,M68K_REG_A0,0x80006974);
    m68k_set_reg(cpu,M68K_REG_D0,pattern==0 ? 0 : pattern==1 ? 0x7fffffff : 0x80000000);
    m68k_set_reg(cpu,M68K_REG_D1,pattern==0 ? 0 : pattern==2 ? 0x7fffffff : 0x80000000);
    uint32_t rng=0x7a8b9c0d ^ count;
    for(unsigned i=0;i<788;++i) {
        rng^=rng<<13; rng^=rng>>17; rng^=rng<<5;
        uint32_t x=pattern==0 ? 0 : pattern==1 ? 0x7fffffff : pattern==2 ? 0x80000000 :
                   pattern==3 ? (i%2 ? 0x80000000 : 0x7fffffff) : pattern==4 ? rng : (i==5 ? 0x7fffffff : 0);
        m.write32(scratch+4*i,x);
    }
    run(m,0x40098474,0x40098494); // original coefficient/accumulator/counter setup
    Result result{};
    result.instructions=run(m,0x40098494,0x400984be);
    for(unsigned r=0;r<16;++r) result.regs[r]=m68k_get_reg(cpu,m68k_register_t(M68K_REG_D0+r));
    result.regs[16]=m68k_get_reg(cpu,M68K_REG_SR);
    for(unsigned i=0;i<788;++i) result.ram.push_back(m.read32(scratch+4*i));
    m68k_set_reg(cpu,M68K_REG_A3,capture); m.write32(stack,stop);
    run(m,capturePc,stop);
    for(unsigned i=0;i<8;++i) result.emac[i]=m.read32(capture+4*i);
    return result;
}
int main(int argc,char** argv) {
    if(argc!=5) { std::fprintf(stderr,"usage: probe STOCK PATCHED HELPER CAPTURE_PC\n"); return 2; }
    auto read=[](const char* path) {
        std::ifstream input(path,std::ios::binary);
        return std::vector<uint8_t>{std::istreambuf_iterator<char>(input),{}};
    };
    ot::Machine stock(read(argv[1])), patched(read(argv[2]));
    std::ifstream f(argv[3],std::ios::binary);
    std::vector<uint8_t> code{std::istreambuf_iterator<char>(f),{}};
    if(code.empty()) return 2;
    for(unsigned i=0;i<code.size();++i) { stock.write8(helper+i,code[i]); patched.write8(helper+i,code[i]); }
    const auto capturePc=uint32_t(std::strtoul(argv[4],nullptr,0));
    uint64_t before=0,after=0; unsigned cases=0;
    for(unsigned mode : {0x20u,0x60u,0xa0u,0xb0u})
    for(unsigned count=0;count<=768;++count) for(unsigned pattern=0;pattern<6;++pattern) {
        auto a=execute(stock,count,pattern,mode,capturePc);
        auto b=execute(patched,count,pattern,mode,capturePc);
        if(a.regs!=b.regs || a.emac!=b.emac || a.ram!=b.ram) {
            std::fprintf(stderr,"Mismatch count=%u pattern=%u MACSR=%x regs=%d emac=%d ram=%d\n",
                         count,pattern,mode,a.regs!=b.regs,a.emac!=b.emac,a.ram!=b.ram); return 1;
        }
        if(count>=16 && b.instructions>=a.instructions) return 1;
        before+=a.instructions; after+=b.instructions; ++cases;
    }
    std::printf("  [PASS] %u loop cases: counts 0..768, six signal/history patterns, four MACSR modes; all D/A, SR, EMAC and guarded RAM identical\n",cases);
    std::printf("  [PASS] loop instructions: %llu -> %llu (%.3f%% fewer); not hardware cycles\n",
                (unsigned long long)before,(unsigned long long)after,100.0*(before-after)/before);
}
