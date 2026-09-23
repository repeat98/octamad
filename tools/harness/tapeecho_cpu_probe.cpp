// Execute the shipped ColdFire adapter and full stock delay routine. The
// native C engine is an arithmetic oracle, not a replacement for execution.
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iterator>
#include <map>
#include <memory>
#include <sstream>
#include <string>
#include <vector>
#include "machine.h"
#include "periph.h"
#include "mc68k/Musashi/m68k.h"
#include "mc68k/cpuState.h"
extern "C" {
#ifdef TE_HALF_RATE
#include "../../modules/tapeecho_half/cpu.h"
#else
#include "../../modules/tapeecho/cpu.h"
#endif
}
#include "../../modules/tapeecho/cpu_tables.h"
static std::vector<uint8_t> read(const char *p) {
    std::ifstream f(p, std::ios::binary);
    return {std::istreambuf_iterator<char>(f), std::istreambuf_iterator<char>()};
}
static constexpr uint32_t stack = 0x47100000, endpc = 0x47200000;
// Direct-kernel instruction ceilings (regression limits, not hardware cycles).
static constexpr unsigned READER_FIXED_CEILING=165, READER_MOVING_CEILING=250,
    FADE_EXTRA=90, FILTER_CEILING=420, TAPE_CEILING=1000;
static std::map<uint32_t,uint64_t>* activeProfile=nullptr;
static std::vector<uint32_t>* activeTrace=nullptr;
static unsigned run(ot::Machine& m, uint32_t pc, uint32_t until, unsigned max = 100000) {
    m68k_set_reg(m.getCpuState(), M68K_REG_PC, pc);
    unsigned n = 0;
    while (m.pc() != until && n++ < max) {
        if(activeProfile)++(*activeProfile)[m.pc()];
        if(activeTrace)activeTrace->push_back(m.pc());
        if (!m.step()) break;
    }
    if (m.pc() != until) {
        std::fprintf(stderr, "Execution stopped at %08x, wanted %08x after %u instructions\n", m.pc(), until, n);
        std::exit(1);
    }
    return n;
}
static void init(ot::Machine& m) {
    m68k_set_reg(m.getCpuState(), M68K_REG_SR, 0x2700);
    m68k_set_reg(m.getCpuState(), M68K_REG_SP, stack);
    m.write32(stack, endpc);
    run(m, 0x40002f44, endpc, 5000000);
}
static void load(ot::Machine& m, const std::vector<uint8_t>& raw, uint32_t base) {
    for (unsigned i = 0; i < raw.size(); ++i) m.write8(base + i, raw[i]);
}
static void formatter_tests(ot::Machine& m) {
    const uint32_t descriptor=m.read32(0x400d5fdc+0x15*4);
    const uint32_t fmt=m.read32(descriptor+0xca), part=0x47d00000, buffer=0x47c00000;
    const char* names[]={"1/64","1/32T","1/32","1/16T","1/16","1/8T",
                        "1/16.","1/8","1/4T","1/8.","1/4","1/4."};
    m.write32(0x46c82456,part);
    for(unsigned bankpart=0;bankpart<4;++bankpart) for(unsigned track=0;track<8;++track)
    for(unsigned sync=0;sync<2;++sync) for(unsigned time=0;time<128;++time) {
        m.write8(0x80000003,bankpart);m.write8(0x80000000,track);
        // Set the other tracks to the opposite mode: selected track only.
        for(unsigned t=0;t<8;++t)m.write8(part+bankpart*6322+0x8eeb0+t*24,t==track?sync:!sync);
        m68k_set_reg(m.getCpuState(),M68K_REG_SP,stack);
        m.write32(stack,endpc);m.write32(stack+4,buffer);m.write32(stack+8,time);
        run(m,fmt,endpc);
        std::string got;for(unsigned i=0;i<16 && m.read8(buffer+i);++i)got+=char(m.read8(buffer+i));
        std::string want=sync?names[time*12/128]:std::to_string((2048+64*time)*10/441);
        if(got!=want || m68k_get_reg(m.getCpuState(),M68K_REG_SP)!=stack+4) {
            std::fprintf(stderr,"TIME formatter failed part %u track %u mode %u time %u: %s/%s\n",bankpart,track,sync,time,got.c_str(),want.c_str());std::exit(1);
        }
    }
    m.write32(0x46c82456,0);m.write8(0x80000003,0);m.write8(0x80000000,0);
    std::puts("  [PASS] shipped TIME formatter: 128 values, both modes, all eight tracks and four Parts; selected-track labels and stack ABI");
}
// Exercise the shipped assembly independently of normal audio levels:
// read-out saturation, fractional carry, every output mode, gain ramps,
// callee-saved registers, and head reads at either end of the contiguous
// ring region. Expected values come from the native oracle's own kernels.
#ifndef TE_HALF_RATE
static void kernel_tests(ot::Machine& m) {
    std::ifstream symbols("out/tapeecho-cpu/profile-symbols.txt");
    uint32_t filter=0,reader=0,tape=0,address; char type; std::string name,line;
    while(std::getline(symbols,line)) {
        std::istringstream fields(line);
        if(!(fields>>std::hex>>address>>type>>name))continue;
        if(name=="te_filter_block")filter=address;
        if(name=="te_read_linear")reader=address;
        if(name=="te_tape_block")tape=address;
    }
    if(!filter||!reader||!tape){std::fprintf(stderr,"missing assembly kernel symbols\n");std::exit(1);}
    constexpr uint32_t buffer=0x47000000,coeff=buffer+128,history=coeff+32,ring=0x4f502c10;
    uint32_t rng=0x12345678;
    auto random=[&]() {rng^=rng<<13;rng^=rng>>17;rng^=rng<<5;return rng;};
    auto call=[&](uint32_t pc) {
        m68k_set_reg(m.getCpuState(),M68K_REG_SP,stack);m.write32(stack,endpc);
        run(m,0x400031c4,0x400031ca);
        for(unsigned i=2;i<15;++i)if(i!=8&&i!=9)
            m68k_set_reg(m.getCpuState(),m68k_register_t(M68K_REG_D0+i),0x12340000+i);
        unsigned instructions=run(m,pc,endpc);
        if(m68k_get_reg(m.getCpuState(),M68K_REG_SP)!=stack+4){std::fprintf(stderr,"kernel stack mismatch\n");std::exit(1);}
        for(unsigned i=2;i<15;++i)if(i!=8&&i!=9)
            if(m68k_get_reg(m.getCpuState(),m68k_register_t(M68K_REG_D0+i))!=0x12340000+i){std::fprintf(stderr,"kernel saved register %u mismatch\n",i);std::exit(1);}
        return instructions;
    };
    // Both filter sections: random histories/carries, tone rows from the
    // shipped table, and full-range inputs that drive both read-outs into
    // saturation in both directions.
    unsigned positive=0,negative=0,filterPeak=0;
    for(unsigned test=0;test<1024;++test) {
        const int32_t *lp=te_tone[random()%(sizeof(te_tone)/sizeof(te_tone[0]))];
        int32_t z[8],expected[16];
        for(unsigned j=0;j<6;++j)z[j]=test%4==3?int32_t(random()):int32_t(random())/4;
        z[6]=random()&255;z[7]=random()&255;
        for(unsigned j=0;j<3;++j)m.write32(coeff+4*j,lp[j]);
        for(unsigned j=0;j<8;++j)m.write32(history+4*j,z[j]);
        for(unsigned j=0;j<16;++j) {
            int32_t x=test%4==0?int32_t(0x7fffffff):test%4==1?int32_t(0x80000000):int32_t(random())/2;
            if(test%4==3)x=int32_t(random());
            m.write32(buffer+4*j,x);expected[j]=x;
        }
        te_host_filter_block(expected,lp,z);
        for(unsigned j=0;j<16;++j){positive+=expected[j]==0x7fffffff;negative+=expected[j]==int32_t(0x80000000);}
        m.write32(buffer-4,0x13579bdf);m.write32(buffer+64,0x2468ace0);
        m.write32(stack+4,buffer);m.write32(stack+8,coeff);m.write32(stack+12,history);
        filterPeak=std::max(filterPeak,call(filter));
        for(unsigned j=0;j<16;++j)if(int32_t(m.read32(buffer+4*j))!=expected[j]) {
            std::fprintf(stderr,"filter kernel mismatch case %u sample %u: %d/%d\n",test,j,int32_t(m.read32(buffer+4*j)),expected[j]);std::exit(1);
        }
        for(unsigned j=0;j<8;++j)if(int32_t(m.read32(history+4*j))!=z[j]){std::fprintf(stderr,"filter history mismatch case %u word %u\n",test,j);std::exit(1);}
        if(m.read32(buffer-4)!=0x13579bdf||m.read32(buffer+64)!=0x2468ace0){std::fprintf(stderr,"filter kernel overwrote guard\n");std::exit(1);}
    }
    if(!positive||!negative){std::fprintf(stderr,"filter saturation not exercised\n");std::exit(1);}
    std::printf("  [PASS] fused filter kernel: 1024 blocks, %u/%u saturated outputs, carries/histories/ABI/guards\n",positive,negative);
    // Record/FIR/curve/output: settled full wet, MIX, MIX=0 and gain ramps
    // (including a MIX ramp that reaches zero), full-range wet and dry.
    unsigned modes[4]={0,0,0,0},recordSaturation=0,outputSaturation=0,tapePeak=0;
    for(unsigned test=0;test<1024;++test) {
        constexpr auto audio=buffer+512,st=buffer+1024,rec=buffer+2048,wet=buffer+3072;
        TapeState s{};s.rng=random();s.feedback=te_feedback[random()%128];
        const unsigned mode=test%4;
        s.mix=mode==0?0:mode==1?2147483640:(random()%128)*16909320u;
        s.hiss=te_hiss[random()%128]<<16;
        s.filters[0][0]=int32_t(random())/8;s.filters[0][1]=int32_t(random())/8;
        int32_t dm=0,df=0,dn=0;
        if(mode==3) {
            dm=test%16==3?-s.mix/8:(int32_t((random()%128)*16909320u)-s.mix)/512;
            df=(te_feedback[random()%128]-s.feedback)/512;
            dn=((te_hiss[random()%128]<<16)-s.hiss)/512;
        }
        ++modes[mode==3?3:!s.mix?0:s.mix==2147483640?1:2];
        int32_t wetIn[16],audioIn[32],expectedAudio[32],expectedRecord[32];
        for(unsigned j=0;j<16;++j)wetIn[j]=test%3==0?int32_t(random()):int32_t(random())/8;
        for(unsigned j=0;j<32;++j)audioIn[j]=expectedAudio[j]=random();
        TapeState expectedState=s;
        te_host_tape_block(&expectedState,wetIn,expectedAudio,expectedRecord,dm,df,dn);
        for(unsigned j=0;j<16;++j)recordSaturation+=std::abs(double(expectedRecord[2*j]))>=te_tape_curve[2040];
        for(unsigned j=0;j<32;++j)outputSaturation+=expectedAudio[j]==0x7fffffff||expectedAudio[j]==int32_t(0x80000000);
        const auto words=reinterpret_cast<const uint32_t*>(&s);
        for(unsigned k=0;k<sizeof(s)/4;++k)m.write32(st+4*k,words[k]);
        for(unsigned j=0;j<16;++j)m.write32(wet+4*j,wetIn[j]);
        for(unsigned j=0;j<32;++j){m.write32(audio+4*j,audioIn[j]);m.write32(rec+4*j,0xdeadbeef);}
        m.write32(rec-4,0x13579bdf);m.write32(rec+128,0x2468ace0);
        m.write32(audio-4,0x13579bdf);m.write32(audio+128,0x2468ace0);
        m.write32(stack+4,st);m.write32(stack+8,wet);m.write32(stack+12,audio);m.write32(stack+16,rec);
        m.write32(stack+20,dm);m.write32(stack+24,df);m.write32(stack+28,dn);
        tapePeak=std::max(tapePeak,call(tape));
        for(unsigned j=0;j<32;++j)if(int32_t(m.read32(audio+4*j))!=expectedAudio[j]){std::fprintf(stderr,"tape output mismatch %u/%u (mode %u)\n",test,j,mode);std::exit(1);}
        for(unsigned j=0;j<32;++j)if(int32_t(m.read32(rec+4*j))!=expectedRecord[j]){std::fprintf(stderr,"tape record mismatch %u/%u (mode %u)\n",test,j,mode);std::exit(1);}
        const auto after=reinterpret_cast<const uint32_t*>(&expectedState);
        for(unsigned k=0;k<sizeof(s)/4;++k)if(m.read32(st+4*k)!=after[k]){std::fprintf(stderr,"tape state mismatch %u/%u\n",test,k);std::exit(1);}
        if(m.read32(rec-4)!=0x13579bdf||m.read32(rec+128)!=0x2468ace0||
           m.read32(audio-4)!=0x13579bdf||m.read32(audio+128)!=0x2468ace0){std::fprintf(stderr,"tape kernel overwrote guard\n");std::exit(1);}
    }
    if(!recordSaturation||!outputSaturation){std::fprintf(stderr,"tape saturation not exercised\n");std::exit(1);}
    std::printf("  [PASS] fused tape kernel: 1024 blocks (%u dry, %u full wet, %u mix, %u ramp), %u curve-limit records, %u clipped outputs, state/ABI/guards\n",
                modes[0],modes[1],modes[2],modes[3],recordSaturation,outputSaturation);
    // Capture a shared counter by value: Machine outlives this function.
    // Count longword loads: the emulator performs a multiply-with-load's
    // 32-bit load as two 16-bit reads, the second at +2.
    auto reads=std::make_shared<unsigned>(0);
    m.addReadWatch(ring-0x08000000,ring-0x08000000+8*TE_RING,
                  [reads](uint32_t a,uint8_t,uint32_t,uint32_t){*reads+=!(a&3);});
    unsigned fixedPeak=0,movingPeak=0,fadeFixedPeak=0,fadeMovingPeak=0;
    for(unsigned test=0;test<2048;++test) {
        // Half the blocks are a BEAT crossfade's outgoing head: out[] holds
        // the incoming head and the weight runs from any fade position.
        const int32_t blend=test%8<4 ? -1 : int32_t((random()%497)<<22);
        int32_t base=((test&1)?TE_RING-18:1)*256+(random()&255);
        int32_t wobble=int32_t(random()%257)-128,step=int32_t(random()%129)-64;
        if(test>=512) {
            // Include negative and beyond-ring anchors that modulation pulls
            // into valid history; exercise the full motor + wow step range.
            static constexpr int offsets[]={-160,-64,-1,0,1,64,160};
            int offset=offsets[(test/4)%7];
            base=((test&1)?TE_RING-24:3)*256+(random()&255)+offset*256;
            wobble=offset*65536+int32_t(random()%513)-256;
            step=int32_t(random()%32769)-16384;
        }
        if(test%4<2)step=0; // Fixed readers must cover fractional and signed offsets too.
        if(!test)wobble=step=0;
        int32_t expected[16]; unsigned expectedReads=0,previousIndex=~0u;
        for(unsigned j=0;j<TE_RING;++j)if(j<28||j>TE_RING-28)m.write32(ring+8*j,random());
        static std::vector<int32_t> host(TE_RING*2);
        int32_t w=wobble;
        for(unsigned j=0;j<16;++j) {
            int32_t initial=int32_t(random())/8;m.write32(buffer+4*j,initial);expected[j]=initial;
            w+=step;uint32_t position=base+j*256-(w>>8),index=position>>8;
            if(index>=TE_RING-1) {
                std::fprintf(stderr,"invalid reader fixture %u/%u: index %u\n",test,j,index);std::exit(1);
            }
            expectedReads += j && index==previousIndex+1 ? 1 : 2;
            previousIndex=index;
            host[2*index]=int32_t(m.read32(ring+8*index));
            host[2*index+2]=int32_t(m.read32(ring+8*index+8));
        }
        te_host_read_linear(expected,host.data(),base,wobble,step,blend);
        m.write32(stack+4,buffer);m.write32(stack+8,ring);m.write32(stack+12,base);
        m.write32(stack+16,wobble);m.write32(stack+20,step);m.write32(stack+24,blend);
        *reads=0;unsigned cost=call(reader);
        auto& peak=blend<0 ? (step?movingPeak:fixedPeak) : (step?fadeMovingPeak:fadeFixedPeak);
        peak=std::max(peak,cost);
        if(*reads!=expectedReads){std::fprintf(stderr,"reader SDRAM traffic mismatch %u/%u\n",*reads,expectedReads);std::exit(1);}
        for(unsigned j=0;j<16;++j)if(int32_t(m.read32(buffer+4*j))!=expected[j]) {
            std::fprintf(stderr,"reader kernel mismatch case %u sample %u\n",test,j);std::exit(1);
        }
    }
    if(fixedPeak>READER_FIXED_CEILING||movingPeak>READER_MOVING_CEILING||
       fadeFixedPeak>READER_FIXED_CEILING+FADE_EXTRA||fadeMovingPeak>READER_MOVING_CEILING+FADE_EXTRA||
       filterPeak>FILTER_CEILING||tapePeak>TAPE_CEILING) {
        std::fprintf(stderr,"kernel instruction regression: reader fixed %u/%u, moving %u/%u (plain/crossfade), filter %u, tape %u\n",
                     fixedPeak,fadeFixedPeak,movingPeak,fadeMovingPeak,filterPeak,tapePeak);std::exit(1);
    }
    std::printf("  [PASS] kernel instruction ceilings: reader fixed %u/%u, moving %u/%u; crossfading reader fixed %u/%u, moving %u/%u; filters %u/%u, tape %u/%u (not hardware cycles)\n",
                fixedPeak,READER_FIXED_CEILING,movingPeak,READER_MOVING_CEILING,
                fadeFixedPeak,READER_FIXED_CEILING+FADE_EXTRA,fadeMovingPeak,READER_MOVING_CEILING+FADE_EXTRA,
                filterPeak,FILTER_CEILING,tapePeak,TAPE_CEILING);
    std::puts("  [PASS] reader: 2048 boundary blocks (signed/outside-ring anchors, fixed/moving heads, plain and crossfading), callee-saved registers");
    std::puts("  [PASS] reader data-load counts match overlap reuse: settled block reads 17 uncached words instead of 32");
}
#endif
// The boot-only Machine deliberately has no peripheral models. Attach the
// production descriptor/completion model plus a synchronous RAM DMA mover.
// This proves addresses/order/bytes, NOT cache coherency or bus timing.
static void dma_model(ot::Machine& m, ot::Edma& dma) {
    m.setPeripheralHandlers(
        [&](uint32_t a, uint8_t n, uint32_t& v) {
            if(a<ot::Edma::g_base || a>=ot::Edma::g_tcd+512) return false;
            v=dma.read(a,n); return true;
        },
        [&](uint32_t a,uint8_t n,uint32_t v) {
            if(a>=ot::Edma::g_base && a<ot::Edma::g_tcd+512) dma.write(a,n,v,false);
        });
    dma.setDataHooks({},[&](uint32_t ch) {
        auto src=dma.tcdField(ch,0,4), dst=dma.tcdField(ch,16,4);
        auto size=dma.tcdField(ch,8,4)*dma.minorLoops(ch);
        if(size>144) { std::fprintf(stderr,"bad delay DMA size %u\n",size); std::exit(1); }
        std::vector<uint8_t> b(size);
        for(unsigned i=0;i<size;++i) b[i]=m.read8(src+i);
        for(unsigned i=0;i<size;++i) m.write8(dst+i,b[i]);
    });
}
static void benchmark(const std::vector<uint8_t>& image,const std::vector<uint8_t>& raw,uint32_t base,uint32_t state,bool stress=false) {
    struct Case { const char* name; unsigned tapes,mode,wow; bool patched; };
    std::vector<Case> cases={
        {"stock DELAY x8 (original firmware)",0,0,0,false},
        {"stock DELAY x8 (patched firmware)",0,0,0,true},
        {"Tape x1, head 1, WOW=0 + stock x7",1,0,0,true},
        {"Tape x1, head 1, WOW=44 + stock x7",1,0,44,true},
        {"Tape x2, moving FREE TIME, WOW=44 + stock x6",2,1,44,true},
        {"Tape x2, changing BEAT TIME, WOW=44 + stock x6",2,2,44,true},
        {"Tape x3, settled TIME, WOW=44 + stock x5",3,0,44,true},
        {"Tape x3, moving FREE TIME, WOW=44 + stock x5",3,1,44,true},
        {"Tape x3, changing BEAT TIME, WOW=44 + stock x5",3,2,44,true},
        {"Tape x8, head 1, WOW=0",8,0,0,true},
        {"Tape x8, head 1, WOW=44",8,0,44,true},
        {"Tape x8, settled MIX=0, WOW=44",8,7,44,true},
        {"Tape x8, moving FREE TIME, WOW=44",8,1,44,true},
        {"Tape x8, changing BEAT TIME, WOW=44",8,2,44,true},
        {"Tape x8, moving FREE TIME, MIX=90",8,3,44,true},
        {"Tape x8, all controls moving, FREE/BEAT/tempo",8,4,127,true},
        {"Tape x8, all controls moving, full synthetic history",8,5,127,true},
    };
    // Synchronized edits deliberately align work across tracks. Full history
    // avoids the cheap not-yet-recorded path. MIX=90 is the shipped default.
    const char* controlNames[]={"TIME", "FDBK", "WOW", "AGE", "SYNC", "MIX"};
    std::vector<std::string> stressNames;
    stressNames.reserve(20);
    if(stress) {
        cases.resize(2);
        stressNames.emplace_back("Tape x8, settled MIX=90, full history");
        cases.push_back({stressNames.back().c_str(),8,99,44,true});
        for(unsigned i=0;i<6;++i) {
            stressNames.emplace_back(std::string("Tape x8, endpoint reversals: ")+controlNames[i]);
            cases.push_back({stressNames.back().c_str(),8,100+i,44,true});
        }
        stressNames.emplace_back("Tape x8, all controls endpoint reversals, FREE");
        cases.push_back({stressNames.back().c_str(),8,106,44,true});
        stressNames.emplace_back("Tape x8, all controls endpoint reversals, BEAT");
        cases.push_back({stressNames.back().c_str(),8,107,44,true});
    }
    std::ifstream symbols(std::getenv("TE_PROFILE_SYMBOLS") ? std::getenv("TE_PROFILE_SYMBOLS") :
#ifdef TE_HALF_RATE
        "out/tapeecho-half/profile-symbols.txt"
#else
        "out/tapeecho-cpu/profile-symbols.txt"
#endif
    );
    std::map<uint32_t,std::string> names; std::string line;
    while(std::getline(symbols,line)) {
        std::istringstream fields(line);uint32_t address;char type;std::string name;
        if(fields>>std::hex>>address>>type>>name && (type=='t'||type=='T')) names[address]=name;
    }
    auto reportProfile=[&](const Case& test, unsigned blocks,
                           const std::map<uint32_t,uint64_t>& samples) {
        std::map<std::string,uint64_t> totals;
        for(auto [pc,count]:samples) {
            auto next=names.upper_bound(pc);
            std::string name="stock routine/buffering";
            if(pc>=base && pc<base+raw.size() && next!=names.begin())name=std::prev(next)->second;
            totals[name]+=count;
        }
        std::vector<std::pair<std::string,uint64_t>> ordered(totals.begin(),totals.end());
        std::sort(ordered.begin(),ordered.end(),[](const auto& a,const auto& b){return a.second>b.second;});
        uint64_t total=0;for(const auto& item:ordered)total+=item.second;
        for(const auto& [name,count]:ordered) {
            double perBlock=double(count)/blocks;
            double perTape=test.tapes?perBlock/test.tapes:0;
            std::printf("  [PROFILE] %s: %-26s %7.1f/block, %6.1f/Tape, %5.1f%% full routine\n",
                        test.name,name.c_str(),perBlock,perTape,100.*count/total);
        }
    };
    const unsigned stateStride=std::getenv("TE_STATE_STRIDE") ? std::strtoul(std::getenv("TE_STATE_STRIDE"),nullptr,0) : sizeof(TapeState);
    double baseline=0;
    for(const auto& test:cases) {
        ot::Machine m(test.patched?image:read("out/raw/section_3_MAIN_OS.bin"));
        ot::Edma dma;dma_model(m,dma);
        if(test.patched)load(m,raw,base);
        init(m);
        unsigned peak=0,minimum=~0u,loadingPeak=0,peakFrame=0;
        std::vector<unsigned> costs;
        std::vector<uint32_t> trace,peakTrace;
        trace.reserve(50000);unsigned long long total=0;
        constexpr unsigned warmup=1500,measured=1000;
        constexpr unsigned profileBlocks=64;
        const bool detailed=test.tapes==1 || (test.tapes==8 &&
            ((test.mode==0 && test.wow==44) || test.mode>=1));
        std::map<uint32_t,uint64_t> detailedProfile;
        for(unsigned frame=0;frame<warmup+measured;++frame) {
            if((test.mode==5 || test.mode>=99) && frame==warmup) {
                // Eliminate startup's history-not-yet-recorded shortcuts.
                // This is a synthetic stress fixture, not a natural render.
                for(unsigned t=0;t<8;++t) {
                    m.write32(state+t*stateStride+offsetof(TapeState,valid),TE_RING-1);
                    for(unsigned n=0;n<TE_RING;++n) {
                        int32_t v=std::sin(n*.17+t)*0x40000000;
                        m.write32(0x4f502c10+t*TE_STRIDE+n*8,v);
                        m.write32(0x4f502c14+t*TE_STRIDE+n*8,v);
                    }
                }
            }
            unsigned slot=frame&3,audioSlot=frame&1;
            m.write32(0x800000e0,audioSlot);m.write32(0x80004804,slot);
            const bool allControls=test.mode==4 || test.mode==5;
            m.write32(0x8000181c,allControls ? (30+(frame/32)%271)*24 : 2880);
            for(unsigned t=0;t<8;++t) {
                // Load instances successively, including a third onto
                // already-running tape tracks (the reported failure).
                bool tape=t<test.tapes && frame>=t*128;
                auto knobs=0x80001a00+slot*96+t*12,setup=0x80001b80+slot*64+t*8;
                for(unsigned i=0;i<8;++i)m.write8(setup+i,0);
                m.write8(setup+7,tape?0x15:8);m.write8(0x80000eb4+audioSlot*8+t,1);
                const unsigned stockValues[]={60,64,127,0,127,127};
                const unsigned time=test.mode && test.mode!=7 ? (frame/8+t*17)%128 : 60;
                unsigned tapeValues[]={time,
                    allControls ? (frame/7+t*19)%128 : 64,
                    allControls ? (frame/11+t*23)%128 : test.wow,
                    allControls ? (frame/9+t*29)%128 : 64,
                    allControls ? (frame/41)%2 : test.mode==2?1u:0u,
                    allControls ? (frame/13+t*31)%128 : test.mode==3?90u:test.mode==7?0u:127u};
                // Alternating endpoint jumps: every block, every 16 blocks,
                // then every 64 blocks to cover immediate and settling work.
                const unsigned period=frame<warmup?16:(frame-warmup<256?1:frame-warmup<512?16:64);
                const unsigned extreme=((frame/period)&1)?127:0;
                if(test.mode>=99) {
                    tapeValues[0]=60; tapeValues[5]=90;
                    if(test.mode>=100 && test.mode<106)
                        tapeValues[test.mode-100]=test.mode==104?extreme/127:extreme;
                    if(test.mode==108) tapeValues[0]=extreme;
                    if(test.mode>=106) {
                        for(unsigned i=0;i<6;++i)tapeValues[i]=extreme;
                        tapeValues[4]=test.mode==107; // BEAT forces head crossfades.
                    }
                }
                for(unsigned i=0;i<6;++i)m.write16(knobs+2*i,(tape?tapeValues[i]:stockValues[i])<<8);
                if(!tape)m.write8(setup+2,127);
                for(unsigned i=0;i<32;++i) {
                    int32_t sample=std::sin((frame*16+i/2)*.0627+t+(i&1)*.7)*0x20000000;
                    m.write32(0x80003190+audioSlot*1024+t*128+4*i,sample);
                }
            }
            m68k_set_reg(m.getCpuState(),M68K_REG_SP,stack);m.write32(stack,endpc);
            activeProfile=!stress && detailed && frame>=warmup && frame<warmup+profileBlocks
                ? &detailedProfile : nullptr;
            trace.clear();
            activeTrace=stress && frame>=warmup ? &trace : nullptr;
            unsigned instructions=run(m,0x400031a0,endpc,250000);
            activeTrace=nullptr;
            activeProfile=nullptr;
            if(frame%128==0 && frame/128<test.tapes)loadingPeak=std::max(loadingPeak,instructions);
            if(frame>=warmup) {
                costs.push_back(instructions);
                if(instructions>peak) { peakFrame=frame-warmup; peakTrace=trace; }
                total+=instructions;peak=std::max(peak,instructions);minimum=std::min(minimum,instructions);
            }
        }
        double mean=double(total)/measured;
        if(!test.patched)baseline=mean;
        std::printf("  [BENCH] %s: mean %.1f, min %u, peak %u instructions/full 8-track 16-sample routine; %.3fx stock\n",
                    test.name,mean,minimum,peak,mean/baseline);
        if(test.tapes)std::printf("  [LOAD] %s: peak %u instructions on an instance-selection frame\n",test.name,loadingPeak);
        if(detailed && !stress)reportProfile(test,profileBlocks,detailedProfile);
        // Optional per-PC listing for one case (TE_PC_DUMP=file, TE_PC_CASE=name).
        if(detailed && !stress && std::getenv("TE_PC_DUMP") && std::getenv("TE_PC_CASE") &&
           !std::strcmp(test.name,std::getenv("TE_PC_CASE"))) {
            if(FILE* f=std::fopen(std::getenv("TE_PC_DUMP"),"w")) {
                for(auto [pc,count]:detailedProfile)
                    std::fprintf(f,"%08x %.2f\n",pc,double(count)/profileBlocks/(test.tapes?test.tapes:1));
                std::fclose(f);
            }
        }
        if(stress) {
            std::sort(costs.begin(),costs.end());
            std::printf("  [SPIKE] %s: p95 %u, p99 %u, peak %u at measured block %u; peak/mean %.3f\n",
                test.name,costs[949],costs[989],peak,peakFrame,peak/mean);
            std::map<uint32_t,uint64_t> worst;
            for(auto pc:peakTrace)++worst[pc];
            if(std::getenv("TE_PC_DUMP") && std::getenv("TE_PC_CASE") &&
               !std::strcmp(test.name,std::getenv("TE_PC_CASE"))) {
                if(FILE* f=std::fopen(std::getenv("TE_PC_DUMP"),"w")) {
                    for(auto [pc,count]:worst)std::fprintf(f,"%08x %.2f\n",pc,double(count)/test.tapes);
                    std::fclose(f);
                }
            }
            std::puts("  [PEAK PROFILE] Executed functions on this case's worst measured block:");
            reportProfile(test,1,worst);
        }
        // Per-scenario regression ceilings, not a hardware deadline. The
        // 36k combined BEAT ceiling rejects the pre-compaction 36,424 peak.
        // Keep cheaper individual controls under their own limits as well.
        if(stress && test.mode>=99) {
            constexpr unsigned limits[]={26000,26500,27000,26000,27300,31900,
                27000,27500,33000};
            if(peak>=limits[test.mode-99]) {
                std::fprintf(stderr,"Parameter spike regression: %s peak %u >= %u\n",
                    test.name,peak,limits[test.mode-99]);std::exit(1);
            }
        }
        // Fixed OCTACLID3 reference: 27,582 instructions for this complete
        // moving-TIME routine. Require >30% savings, not just a new number.
        if(test.tapes==3 && test.mode==1 && mean>=19300) {
            std::fprintf(stderr,"Economy three-instance moving-TIME budget exceeded (19300)\n");std::exit(1);
        }
        // Instruction regression ceilings, NOT available CPU cycles. Keep
        // the full-history/all-controls path bounded as well as TIME-only.
        if(!stress && test.tapes==8 && peak >= (test.mode>=4 ? 35000u : 30000u)) {
            std::fprintf(stderr,"Eight-instance instruction regression budget exceeded\n");std::exit(1);
        }
        std::fflush(stdout);
    }
    std::puts("  [BENCH] Same 44.1kHz/16-sample routine and modelled DMA; 1500 warm-up + 1000 measured blocks, stereo tone, active wet/feedback. Host wall time, DSP cost, cache misses and DMA/bus stalls excluded; NOT hardware CPU percent.");
}
int main(int argc, char **argv) {
    if (argc != 5 && argc != 6) { std::fprintf(stderr, "probe IMAGE RUNTIME BASE STATE [--benchmark|--stress]\n"); return 2; }
    auto image = read(argv[1]), raw = read(argv[2]);
    uint32_t base = std::strtoul(argv[3], nullptr, 16), state = std::strtoul(argv[4], nullptr, 16);
    if(argc==6) {
        if(std::strcmp(argv[5],"--benchmark") && std::strcmp(argv[5],"--stress"))return 2;
        benchmark(image,raw,base,state,!std::strcmp(argv[5],"--stress"));return 0;
    }
    ot::Machine m(image); ot::Edma dma; dma_model(m,dma); load(m, raw, base); init(m);
    // The real reset must clear previously used state, not merely boot zeros.
    for (unsigned i = 0; i < 8*sizeof(TapeState); ++i) m.write8(state + i, 0xa5);
    init(m);
    for (unsigned i = 0; i < 8*sizeof(TapeState); ++i) if (m.read8(state+i)) return 1;
    std::puts("  [PASS] stock delay reset clears every CPU Tape Echo state byte");
    formatter_tests(m);
#ifndef TE_HALF_RATE
    kernel_tests(m);
#endif

    // Set stock's saved-frame locals exactly as its preceding code does.
    // Start near the physical ring end, so this also crosses the wrap seam.
    TapeState states[8] = {};
    std::vector<std::vector<int32_t>> rings(8, std::vector<int32_t>(TE_RING * 2));
    unsigned write = TE_RING - 160, peak = 0;
    const unsigned frames = 2300;
    for (unsigned frame = 0; frame < frames; ++frame) {
        if(frame==2000) {
            // A second, synthetic full-history phase covers long BEAT
            // targets and an active-history wrap, not startup silence.
            write=TE_RING-160;
            for(unsigned t=0;t<8;++t) {
                states[t].valid=TE_RING-1;
                m.write32(state+t*sizeof(TapeState)+offsetof(TapeState,valid),TE_RING-1);
                for(unsigned n=0;n<TE_RING;++n) {
                    int32_t v=std::sin(n*.17+t)*0x40000000;
                    rings[t][2*n]=rings[t][2*n+1]=v;
                    m.write32(0x4f502c10+t*TE_STRIDE+n*8,v);
                    m.write32(0x4f502c14+t*TE_STRIDE+n*8,v);
                }
            }
        }
        for (unsigned t = 0; t < 8; ++t) {
            unsigned slot = frame & 3;
            uint32_t knobs = 0x80001a00 + slot*96 + t*12;
            uint32_t setup = 0x80001b80 + slot*64 + t*8;
            uint32_t audio = 0x80003190 + (frame&1)*1024 + t*128;
            uint32_t ring = 0x4f502c10 + t*TE_STRIDE;
            TapeParams p{(frame/8+t*17)%128, t == 7 ? 120u : 0u, frame > 1800 ? 60u : 0u,
                          frame >= 900 && frame < 1500 ? 1u : 0u,
                          t == 0 ? 0u : 127u, 30, 2880};
            if (frame >= 1900) { p.tempo = (30+(frame/8)%271)*24; p.sync=1; }
            if (frame >= 2000) {
                p.feedback=(frame/7+t*19)%128;p.wow=(frame/11+t*23)%128;
                p.mix=(frame/13+t*31)%128;p.sync=(frame/41)%2;
            }
            p.age=(frame/8+t*13)%128;
            p.lane=t;
            unsigned values[] = {p.time,p.feedback,p.wow,p.age,p.sync,p.mix};
            // Execute the stock producer-to-consumer copy for the six page-1
            // words. Both frame buffers and all four queue slots are covered.
            const uint32_t frameRecord=0x80000110+(frame&1)*512+t*64;
            for(unsigned i=0;i<6;++i)m.write16(frameRecord+24+2*i,values[i]<<8);
            m.write16(frameRecord+56,0x15);
            m.write32(0x800000e0,frame&1);m.write32(0x80004800,slot);
            m.write8(0x8000184b,0);
            run(m,0x4000d0ea,0x4000d15a);
            m.write8(0x80000eb4+t,1); m.write32(0x8000181c,p.tempo);
            m.write32(stack+72,knobs); m.write32(stack+76,setup); m.write32(stack+92,setup);
            m.write32(stack+96,audio); m.write32(stack+108,0x80000eb4+t);
            m.write32(stack+112,t); m.write32(stack+48,ring+write*8);
            uint32_t scratch = t&1 ? 0x800039a0 : 0x80003ae0;
            m.write32(0x800000e8,scratch); m.write32(0x80006180,0x80005f60+t*68);
            int32_t in[32], out[32], rec[32];
            for (unsigned i=0;i<32;++i) {
                // Channel-asymmetric signed audio, including sub-24-bit dry data.
                in[i] = int32_t(std::sin((frame*16+i/2)*0.1417+t)*0x20000000) + (i&1 ? 12345 : -6789);
#ifdef TE_HALF_RATE
                // Exercise converter overshoot/clamps with full-range input,
                // independently of the lower-level benchmark tone.
                if(frame>=2100)in[i]=uint32_t(frame*1664525u+i*1013904223u+t*69069u);
#endif
                out[i] = in[i]; m.write32(audio+4*i,in[i]);
            }
            te_process(&states[t], &p, rings[t].data(), write, out, rec);
            m68k_set_reg(m.getCpuState(), M68K_REG_SP, stack);
            // Execute stock's actual MACSR setup, then this image's detour.
            run(m,0x400031c4,0x400031ca);
            unsigned n = run(m,0x4000361a,0x4000377a);
            peak = std::max(peak,n);
            if (m68k_get_reg(m.getCpuState(),M68K_REG_SP)!=stack ||
                m.read32(0x800000e8)!=(scratch^0x340) ||
                m.read32(0x80006180)!=0x80005f60+(t+1)*68) return 1;
            for (unsigned i=0;i<32;++i) {
                int32_t a = m.read32(audio+4*i), r = m.read32((scratch^0x340)+4*i);
                if (a!=out[i] || r!=rec[i]) {
                    std::fprintf(stderr,"oracle mismatch frame %u track %u sample %u: audio %d/%d record %d/%d\n",
                                 frame,t,i,a,out[i],r,rec[i]); return 1;
                }
                rings[t][write*2+i]=rec[i]; m.write32(ring+write*8+4*i,rec[i]);
            }
            const uint32_t *s = reinterpret_cast<const uint32_t *>(&states[t]);
            for (unsigned i=0;i<sizeof(TapeState)/4;++i) if (m.read32(state+t*sizeof(TapeState)+4*i)!=s[i]) {
                std::fprintf(stderr,"state mismatch frame %u track %u word %u: %08x/%08x\n",frame,t,i,m.read32(state+t*sizeof(TapeState)+4*i),s[i]); return 1;
            }
        }
        write += 16; if (write == TE_RING) write = 0;
    }
    std::printf("  [PASS] all 8 CPU instances match native arithmetic bit-for-bit (%u blocks; TIME/AGE sweeps, FREE/BEAT, tempo, wow, feedback, stock page-1 staging, ring wrap)\n",frames);
    std::printf("  [METER] peak %u instructions/16-sample track callback (not hardware cycles)\n",peak);
    // A regression budget, NOT a real-time CPU certification. Hardware
    // timing still includes the rest of the OS, cache and memory stalls.
    if(peak>5000) { std::fprintf(stderr,"Tape callback exceeded 5000-instruction regression budget\n"); return 1; }
    std::puts("  [PASS] CPU callback remains below its 5000-instruction regression budget, including full-history/all-control edits");
    // Non-Tape Echo must replay stock instructions and preserve all other
    // registers and EMAC accumulators; exiting an effect invalidates history.
    m.write8(m.read32(stack+76)+7,8);
    uint32_t regs[16];
    for(unsigned i=0;i<16;++i) {
        regs[i]=i==15?stack:0x12000000+4*i;
        m68k_set_reg(m.getCpuState(),m68k_register_t(M68K_REG_D0+i),regs[i]);
    }
    run(m,0x4000361a,0x40003624);
    for(unsigned i=0;i<16;++i) {
        uint32_t expected=i==0?m.read32(0x800000e8):i==13?m.read32(stack+92):regs[i];
        if(m68k_get_reg(m.getCpuState(),m68k_register_t(M68K_REG_D0+i))!=expected) return 1;
    }
    if(m.read32(state+7*sizeof(TapeState))) return 1;
    std::puts("  [PASS] stock DELAY fallback preserves registers and invalidates Tape Echo history");

    // Run the COMPLETE stock delay routine, not just a fabricated callback,
    // to pin stack offsets, prefetch toggling, ring positions and DMA commits.
    init(m);
    ot::Machine stock(read("out/raw/section_3_MAIN_OS.bin"));
    ot::Edma stockDma; dma_model(stock,stockDma); init(stock);
    for (unsigned frame=0;frame<1600;++frame) {
        unsigned slot=frame&3, audioSlot=frame&1;
      for(auto* machine:{&m,&stock}) {
        auto& m=*machine;
        m.write32(0x800000e0,audioSlot); m.write32(0x80004804,slot);
        m.write32(0x8000181c,(30+(frame/8)%271)*24);
        for (unsigned t=0;t<8;++t) {
            auto knobs=0x80001a00+slot*96+t*12, setup=0x80001b80+slot*64+t*8;
            for(unsigned i=0;i<8;++i) m.write8(setup+i,0);
            m.write8(setup+7,t&1?8:0x15); m.write8(0x80000eb4+audioSlot*8+t,1);
            for(unsigned i=0;i<6;++i) m.write16(knobs+2*i, i==5?0:65<<8);
            m.write16(knobs+6,0); m.write16(knobs+8,0);
            if (!(t&1)) {
                m.write16(knobs,((frame/4+t*17)%128)<<8);
                m.write16(knobs+8,((frame/40)%2)<<8);
            }
            if(t&1) {
                const unsigned values[]={1,0,127,0,127,127};
                for(unsigned i=0;i<6;++i) m.write16(knobs+2*i,values[i]<<8);
                m.write8(setup+2,127);
            }
            for(unsigned i=0;i<32;++i) m.write32(0x80003190+audioSlot*1024+t*128+4*i,0x10000000+t*0x1000+i*256);
        }
        m68k_set_reg(m.getCpuState(),M68K_REG_SP,stack); m.write32(stack,endpc);
        run(m,0x400031a0,endpc,250000);
      }
        for(unsigned t=0;t<8;++t) {
            if(m.read32(0x80005f9c+t*68)!=(frame+1)*128) return 1;
            if(!(t&1)) for(unsigned i=0;i<32;++i) {
                auto a=m.read32(0x80003190+audioSlot*1024+t*128+4*i);
                if(a!=0x10000000+t*0x1000+i*256) { std::fprintf(stderr,"full path dry mismatch\n"); return 1; }
            }
            else for(unsigned i=0;i<32;++i) {
                auto a=0x80003190+audioSlot*1024+t*128+4*i;
                if(m.read32(a)!=stock.read32(a)) {
                    std::fprintf(stderr,"stock delay changed track %u frame %u sample %u: %08x/%08x\n",t,frame,i,m.read32(a),stock.read32(a));
                    for(unsigned j=0;j<68;j+=4) if(m.read32(0x80005f60+t*68+j)!=stock.read32(0x80005f60+t*68+j))
                        std::fprintf(stderr,"stock state +%u: %08x/%08x\n",j,m.read32(0x80005f60+t*68+j),stock.read32(0x80005f60+t*68+j));
                    return 1;
                }
            }
            for(unsigned i=0;i<32;++i) if(t&1) {
                auto a=0x4f502c10+t*TE_STRIDE+frame*128+i*4;
                if(m.read32(a)!=stock.read32(a)) { std::fprintf(stderr,"stock ring corrupted\n"); return 1; }
            }
        }
    }
    std::puts("  [PASS] complete CPU frame + DMA: mixed Tape Echo/DELAY, four control slots, both audio buffers, exact dry, ring advances; stock DELAY audio and recorded rings bit-identical to stock firmware");
}
