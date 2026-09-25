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
constexpr uint32_t state = 0x470a0000, source = 0x470b0000;
constexpr uint32_t irqStack = 0x47110000;
static unsigned debugCount=0, debugPattern=0, debugTable=0, debugMode=0;
static unsigned run(ot::Machine& m, uint32_t pc, uint32_t end, unsigned budget=20000) {
    m68k_set_reg(m.getCpuState(), M68K_REG_PC, pc);
    unsigned n = 0;
    while(m.pc() != end && n < budget) { ++n; if(!m.step()) break; }
    if(m.pc() != end) { std::fprintf(stderr, "Stopped at %08x, expected %08x after %u instructions (%s); case count=%u pattern=%u table=%u MACSR=%x\n", m.pc(), end,n,m.why().c_str(),debugCount,debugPattern,debugTable,debugMode); std::exit(1); }
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
// Execute the stock frame IRQ's actual EMAC save and restore instructions
// around a clobber, then restore the interrupted CPU register frame. This is
// a targeted context-switch probe, not a simulation of the whole audio ISR.
static void preempt(ot::Machine& m) {
    auto cpu=m.getCpuState();
    std::array<uint32_t,16> regs{};
    for(unsigned r=0;r<16;++r)
        regs[r]=m68k_get_reg(cpu,m68k_register_t(M68K_REG_D0+r));
    const auto sr=m68k_get_reg(cpu,M68K_REG_SR), pc=m.pc();
    m68k_set_reg(cpu,M68K_REG_SR,0x2700);
    m68k_set_reg(cpu,M68K_REG_SP,irqStack);
    m68k_set_reg(cpu,M68K_REG_A1,irqStack+220);
    m68k_set_reg(cpu,M68K_REG_D0,0);
    m68k_set_reg(cpu,M68K_REG_D1,0);
    run(m,0x4000ac98,0x4000acb4); // stock: MACSR->0, save all EMAC state
    m68k_set_reg(cpu,M68K_REG_SP,irqStack); m.write32(irqStack,stop);
    run(m,helper,stop);             // interrupt body clobbers all accumulators
    m68k_set_reg(cpu,M68K_REG_SP,irqStack);
    run(m,0x4000d964,0x4000d982); // stock: restore EMAC, MACSR last
    m68k_set_reg(cpu,M68K_REG_SR,sr);
    for(unsigned r=0;r<16;++r)
        m68k_set_reg(cpu,m68k_register_t(M68K_REG_D0+r),regs[r]);
    m68k_set_reg(cpu,M68K_REG_PC,pc);
}
// Exercise the public function boundary, including conversion, length clamp,
// history/envelope writes, return value, stack and both memory guards.
static Result executeFull(ot::Machine& m, unsigned count, unsigned pattern,
                          unsigned table, unsigned mode, uint32_t capturePc,
                          unsigned preemptStep=0) {
    debugCount=count; debugPattern=pattern; debugTable=table; debugMode=mode;
    auto cpu=m.getCpuState();
    m68k_set_reg(cpu,M68K_REG_SR,0x2700);
    m68k_set_reg(cpu,M68K_REG_SP,stack); m.write32(stack,stop);
    m.write32(helper+2,mode);
    run(m,helper,stop);
    uint32_t rng=0x62e5a419u ^ count ^ (pattern<<16) ^ (table<<24) ^ mode;
    auto next=[&rng]() { rng^=rng<<13; rng^=rng>>17; rng^=rng<<5; return rng; };
    for(unsigned r=0;r<16;++r)
        m68k_set_reg(cpu,m68k_register_t(M68K_REG_D0+r),next());
    m68k_set_reg(cpu,M68K_REG_SR,0x2700);
    m68k_set_reg(cpu,M68K_REG_SP,stack);
    for(unsigned i=0;i<28;++i) m.write32(state-16+4*i,next());
    m.write32(state,1024+pattern*17);
    m.write32(state+4,1024+pattern*17);
    for(unsigned i=0;i<800;++i) m.write32(scratch-16+4*i,next());
    for(unsigned i=0;i<800;++i) {
        const uint32_t sample=pattern==0 ? 0 : pattern==1 ? 0x7fffffff :
            pattern==2 ? 0x80000000 : pattern==3 ? (i&1 ? 0x80000000 : 0x7fffffff) : next();
        m.write32(source-16+4*i,sample);
    }
    for(unsigned i=0;i<40;++i) m.write32(stack-64+4*i,next());
    m.write32(stack,stop);
    m.write32(stack+4,state);
    m.write32(stack+8,source);
    m.write32(stack+12,count);
    m.write32(stack+16,table*23);
    m.write32(stack+20,table);
    m.write32(stack+24,pattern&3); // all four apparent format selectors
    Result result{};
    if(!preemptStep) result.instructions=run(m,0x40098388,stop,100000);
    else {
        m68k_set_reg(cpu,M68K_REG_PC,0x40098388);
        while(m.pc()!=stop && result.instructions<100000) {
            if(result.instructions==preemptStep) preempt(m);
            ++result.instructions;
            if(!m.step()) break;
        }
        if(m.pc()!=stop || result.instructions<=preemptStep) {
            std::fprintf(stderr,"Interrupted full routine did not return (PC=%08x)\n",m.pc());
            std::exit(1);
        }
    }
    for(unsigned r=0;r<16;++r)
        result.regs[r]=m68k_get_reg(cpu,m68k_register_t(M68K_REG_D0+r));
    result.regs[16]=m68k_get_reg(cpu,M68K_REG_SR);
    for(unsigned i=0;i<28;++i) result.ram.push_back(m.read32(state-16+4*i));
    for(unsigned i=0;i<800;++i) result.ram.push_back(m.read32(scratch-16+4*i));
    for(unsigned i=0;i<800;++i) result.ram.push_back(m.read32(source-16+4*i));
    for(unsigned i=0;i<40;++i) result.ram.push_back(m.read32(stack-64+4*i));
    m68k_set_reg(cpu,M68K_REG_A3,capture);
    m68k_set_reg(cpu,M68K_REG_SP,stack); m.write32(stack,stop);
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
    const auto stockImage=read(argv[1]), patchedImage=read(argv[2]);
    ot::Machine stock(stockImage), patched(patchedImage);
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
    unsigned fullCases=0;
    for(unsigned mode : {0x20u,0x60u,0xa0u,0xb0u})
    for(unsigned count : {0u,1u,2u,3u,4u,7u,8u,9u,16u,31u,64u,127u,256u,511u,768u,769u,0xffffffffu})
    for(unsigned pattern=0;pattern<6;++pattern) for(unsigned table=0;table<8;++table) {
        const auto a=executeFull(stock,count,pattern,table,mode,capturePc);
        const auto b=executeFull(patched,count,pattern,table,mode,capturePc);
        if(a.regs!=b.regs || a.emac!=b.emac || a.ram!=b.ram) {
            std::fprintf(stderr,"Full-routine mismatch count=%u pattern=%u table=%u MACSR=%x regs=%d emac=%d ram=%d\n",
                         count,pattern,table,mode,a.regs!=b.regs,a.emac!=b.emac,a.ram!=b.ram); return 1;
        }
        ++fullCases;
    }
    std::printf("  [PASS] %u complete-routine cases: count boundaries/clamp, dirty history, input/stack guards, eight tables, four MACSR modes\n",fullCases);
    unsigned irqCases=0;
    for(unsigned mode : {0x20u,0x60u,0xa0u,0xb0u})
    for(unsigned step : {50u,1000u,2000u}) {
        const auto a=executeFull(stock,256,4,3,mode,capturePc,step);
        const auto b=executeFull(patched,256,4,3,mode,capturePc,step);
        if(a.regs!=b.regs || a.emac!=b.emac || a.ram!=b.ram) {
            std::fprintf(stderr,"Preempted full-routine mismatch step=%u MACSR=%x\n",step,mode); return 1;
        }
        ++irqCases;
    }
    std::printf("  [PASS] %u preempted complete-routine cases: stock guest EMAC save/restore across clobber\n",irqCases);
    // The loop-only gate never observes this post-loop store. A broken image
    // must be rejected by the complete-routine comparison.
    auto wrongImage=patchedImage;
    const auto broken=0x40098530-ot::Machine::g_imageBase;
    if(wrongImage.size()<broken+4 || wrongImage[broken]!=0x25 || wrongImage[broken+1]!=0x41 ||
       wrongImage[broken+2]!=0x00 || wrongImage[broken+3]!=0x2c)
        return 2;
    wrongImage[broken]=0x4e; wrongImage[broken+1]=0x71;
    wrongImage[broken+2]=0x4e; wrongImage[broken+3]=0x71;
    ot::Machine wrong(wrongImage);
    for(unsigned i=0;i<code.size();++i) wrong.write8(helper+i,code[i]);
    const auto correct=executeFull(stock,64,4,3,0x20,capturePc);
    const auto incorrect=executeFull(wrong,64,4,3,0x20,capturePc);
    if(correct.regs==incorrect.regs && correct.emac==incorrect.emac && correct.ram==incorrect.ram) {
        std::fprintf(stderr,"Negative control missed a removed post-loop store\n"); return 1;
    }
    std::printf("  [PASS] negative control: removed post-loop store changes complete-routine state\n");
    // The relocated eight-way body also needs an independent negative
    // control. Its first MSAC at 0x400d6b90 is a203 0900; 0800 makes it
    // MAC with the same operands. Keep the mutation only in guest memory.
    auto wrongLoopImage=patchedImage;
    const auto macExt=0x400d6b92-ot::Machine::g_imageBase;
    if(wrongLoopImage.size()<macExt+2 || wrongLoopImage[macExt]!=0x09 || wrongLoopImage[macExt+1]!=0x00)
        return 2;
    wrongLoopImage[macExt]=0x08;
    ot::Machine wrongLoop(wrongLoopImage);
    for(unsigned i=0;i<code.size();++i) wrongLoop.write8(helper+i,code[i]);
    for(unsigned count : {8u,9u}) {
        const auto a=execute(stock,count,4,0x20,capturePc);
        const auto b=execute(wrongLoop,count,4,0x20,capturePc);
        if(a.regs==b.regs && a.emac==b.emac && a.ram==b.ram) {
            std::fprintf(stderr,"Negative control missed relocated MSAC mutation at count=%u\n",count);
            return 1;
        }
    }
    std::printf("  [PASS] negative control: relocated MSAC-to-MAC mutation fails at counts 8 and 9\n");
}
