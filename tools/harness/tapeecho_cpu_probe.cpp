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
#include "../../modules/tapeecho/cpu.h"
}
#include "../../modules/tapeecho/cpu_tables.h"
static std::vector<uint8_t> read(const char *p) {
    std::ifstream f(p, std::ios::binary);
    return {std::istreambuf_iterator<char>(f), std::istreambuf_iterator<char>()};
}
static constexpr uint32_t stack = 0x47100000, endpc = 0x47200000;
static bool profiling=false;
static std::map<uint32_t,unsigned> profile;
static unsigned run(ot::Machine& m, uint32_t pc, uint32_t until, unsigned max = 100000) {
    m68k_set_reg(m.getCpuState(), M68K_REG_PC, pc);
    unsigned n = 0;
    while (m.pc() != until && n++ < max) {
        if(profiling)++profile[m.pc()];
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
// both filter clamps, fractional carry, callee-saved registers, and head
// reads at either end of the contiguous ring region.
static void kernel_tests(ot::Machine& m) {
    std::ifstream symbols("out/tapeecho-cpu/profile-symbols.txt");
    uint32_t filter=0,reader=0,recorder=0,finish=0,curve=0,address; char type; std::string name,line;
    while(std::getline(symbols,line)) {
        std::istringstream fields(line);
        if(!(fields>>std::hex>>address>>type>>name))continue;
        if(name=="te_filter_block")filter=address;
        if(name=="te_read_linear")reader=address;
        if(name=="te_record_block")recorder=address;
        if(name=="te_finish_record")finish=address;
        if(name=="te_curve")curve=address;
    }
    if(!filter||!reader||!recorder||!finish||!curve){std::fprintf(stderr,"missing assembly kernel symbols\n");std::exit(1);}
    constexpr uint32_t buffer=0x47000000,coeff=buffer+128,history=coeff+32,ring=0x4f502c10;
    uint32_t rng=0x12345678;unsigned positive=0,negative=0;
    auto random=[&]() {rng^=rng<<13;rng^=rng>>17;rng^=rng<<5;return rng;};
    auto call=[&](uint32_t pc) {
        m68k_set_reg(m.getCpuState(),M68K_REG_SP,stack);m.write32(stack,endpc);
        run(m,0x400031c4,0x400031ca);
        for(unsigned i=2;i<15;++i)if(i!=8&&i!=9)
            m68k_set_reg(m.getCpuState(),m68k_register_t(M68K_REG_D0+i),0x12340000+i);
        run(m,pc,endpc);
        if(m68k_get_reg(m.getCpuState(),M68K_REG_SP)!=stack+4){std::fprintf(stderr,"kernel stack mismatch\n");std::exit(1);}
        for(unsigned i=2;i<15;++i)if(i!=8&&i!=9)
            if(m68k_get_reg(m.getCpuState(),m68k_register_t(M68K_REG_D0+i))!=0x12340000+i){std::fprintf(stderr,"kernel saved register %u mismatch\n",i);std::exit(1);}
    };
    for(unsigned test=0;test<1024;++test) {
        const int32_t *c=test%3==0?te_fixed[test%2]:test%3==1?te_corner[test%225]:te_worn[test%128];
        int32_t z[5],expected[16];
        for(unsigned j=0;j<4;++j)z[j]=(int32_t(random())/8)*2;
        z[4]=random()&255;
        for(unsigned j=0;j<5;++j) {m.write32(coeff+4*j,c[j]);m.write32(history+4*j,z[j]);}
        for(unsigned j=0;j<16;++j) {
            int32_t x=test%4==0?268435456:test%4==1?-268435456:int32_t(random())/8;
            m.write32(buffer+4*j,x);
            int64_t acc=z[4]+((int64_t(x*2)*c[0])>>23);
            for(unsigned k=0;k<4;++k)acc+=(int64_t(z[k])*c[k+1])>>23;
            int32_t y=acc>>8;z[4]=uint32_t(acc)&255;
            if(y>268435456){y=268435456;z[4]=0;++positive;}
            if(y<-268435456){y=-268435456;z[4]=0;++negative;}
            z[1]=z[0];z[0]=x*2;z[3]=z[2];z[2]=y*2;expected[j]=y;
        }
        m.write32(stack+4,buffer);m.write32(stack+8,coeff);m.write32(stack+12,history);call(filter);
        for(unsigned j=0;j<16;++j)if(int32_t(m.read32(buffer+4*j))!=expected[j]) {
            std::fprintf(stderr,"filter kernel mismatch case %u sample %u\n",test,j);std::exit(1);
        }
        for(unsigned j=0;j<5;++j)if(int32_t(m.read32(history+4*j))!=z[j]){std::fprintf(stderr,"kernel history mismatch case %u word %u\n",test,j);std::exit(1);}
    }
    if(!positive||!negative)std::exit(1);
    unsigned recordClamps=0,mixClamps=0;
    for(unsigned test=0;test<1024;++test) {
        constexpr auto audio=buffer+512,st=buffer+1024,rec=buffer+2048;
        TapeState s{};s.rng=random();s.feedback=te_feedback[random()%128];
        s.mix=test%4==0?0:test%4==1?2147483640:(random()%128)*16909320u;
        s.hiss=te_hiss[random()%128]<<16;
        int32_t dm=0,df=0,dn=0;
        if(test%4==3) {
            dm=(int32_t((random()%128)*16909320u)-s.mix)/512;
            df=(te_feedback[random()%128]-s.feedback)/512;
            dn=((te_hiss[random()%128]<<16)-s.hiss)/512;
        }
        const auto words=reinterpret_cast<const uint32_t*>(&s);
        for(unsigned k=0;k<sizeof(s)/4;++k)m.write32(st+4*k,words[k]);
        int32_t expectedAudio[32],expectedRecord[16];
        auto mul=[](int32_t x,int32_t y){return int32_t((int64_t(x)*y)>>31);};
        auto clip=[&](int32_t x){if(x>8388607||x<-8388608)++mixClamps;return std::clamp(x,-8388608,8388607);};
        for(unsigned j=0;j<16;++j) {
            int32_t wet=int32_t(random())/8;
            m.write32(buffer+4*j,wet);
            int32_t left=random(),right=random();m.write32(audio+8*j,left);m.write32(audio+8*j+4,right);
            s.mix+=dm;s.feedback+=df;s.hiss+=dn;s.rng=s.rng*1664525u+1013904223u;
            int32_t l=left>>5,r=right>>5;
            int32_t value=8*mul((l+r)/2,te_record_gain[0])+8*mul(wet,s.feedback)+mul(s.hiss>>16,s.rng);
            if(value>268435456||value<-268435456)++recordClamps;
            expectedRecord[j]=std::clamp(value,-268435456,268435456);
            wet=8*mul(wet,te_makeup[0]);
            if(s.mix) {
                left=uint32_t(clip((l+mul(wet-l,s.mix))>>3))<<8;
                right=uint32_t(clip((r+mul(wet-r,s.mix))>>3))<<8;
            }
            expectedAudio[2*j]=left;expectedAudio[2*j+1]=right;
        }
        m.write32(rec-4,0x13579bdf);m.write32(rec+64,0x2468ace0);
        m.write32(stack+4,st);m.write32(stack+8,buffer);m.write32(stack+12,audio);m.write32(stack+16,rec);
        m.write32(stack+20,dm);m.write32(stack+24,df);m.write32(stack+28,dn);call(recorder);
        for(unsigned j=0;j<32;++j)if(int32_t(m.read32(audio+4*j))!=expectedAudio[j]){std::fprintf(stderr,"record mix kernel mismatch %u/%u\n",test,j);std::exit(1);}
        for(unsigned j=0;j<16;++j)if(int32_t(m.read32(rec+4*j))!=expectedRecord[j]){std::fprintf(stderr,"record kernel mismatch %u/%u\n",test,j);std::exit(1);}
        for(unsigned k=0;k<sizeof(s)/4;++k)if(m.read32(st+4*k)!=words[k]){std::fprintf(stderr,"record state mismatch %u/%u\n",test,k);std::exit(1);}
        if(m.read32(rec-4)!=0x13579bdf||m.read32(rec+64)!=0x2468ace0){std::fprintf(stderr,"record kernel overwrote guard\n");std::exit(1);}
        constexpr auto finalRecord=buffer+3072;
        int32_t x1=int32_t(random())/8,x2=int32_t(random())/8,expectedFinal[16];
        m.write32(history,x1);m.write32(history+4,x2);
        for(unsigned j=0;j<16;++j) {
            int32_t x=expectedRecord[j],shaped=x1+((x-2*x1+x2)>>3);
            x2=x1;x1=x;
            uint32_t a=shaped<0?-shaped:shaped,index=a>>18;
            int32_t y=te_curve[index]+mul(te_curve[index+1]-te_curve[index],(a&262143u)<<13);
            expectedFinal[j]=uint32_t(shaped<0?-y:y)<<5;
        }
        m.write32(finalRecord-4,0x13579bdf);m.write32(finalRecord+128,0x2468ace0);
        m.write32(stack+4,rec);m.write32(stack+8,finalRecord);
        m.write32(stack+12,history);m.write32(stack+16,curve);call(finish);
        for(unsigned j=0;j<32;++j)if(int32_t(m.read32(finalRecord+4*j))!=expectedFinal[j/2]){std::fprintf(stderr,"FIR/curve kernel mismatch %u/%u\n",test,j);std::exit(1);}
        if(int32_t(m.read32(history))!=x1||int32_t(m.read32(history+4))!=x2||
           m.read32(finalRecord-4)!=0x13579bdf||m.read32(finalRecord+128)!=0x2468ace0){std::fprintf(stderr,"FIR/curve state/guard mismatch\n");std::exit(1);}
    }
    if(!recordClamps||!mixClamps)std::exit(1);
    std::printf("  [PASS] record/mix kernel: 1024 gain/ramp cases, %u record clamps, %u mix clamps, state/ABI/guards\n",recordClamps,mixClamps);
    std::puts("  [PASS] FIR/curve kernel: 1024 clamped-input/random-history blocks, stereo output, state/ABI/guards");
    // Capture a shared counter by value: Machine outlives this function.
    auto reads=std::make_shared<unsigned>(0);
    m.addReadWatch(ring-0x08000000,ring-0x08000000+8*TE_RING,
                  [reads](uint32_t,uint8_t,uint32_t,uint32_t){++*reads;});
    for(unsigned test=0;test<512;++test) {
        int32_t base=((test&1)?TE_RING-18:1)*256+(random()&255);
        int32_t wobble=int32_t(random()%257)-128,step=int32_t(random()%129)-64;
        if(!test)wobble=step=0;
        int32_t expected[16]; unsigned expectedReads=0,previousIndex=~0u;
        for(unsigned j=0;j<TE_RING;++j)if(j<20||j>TE_RING-20)m.write32(ring+8*j,random());
        int32_t w=wobble;
        for(unsigned j=0;j<16;++j) {
            int32_t initial=int32_t(random())/8;m.write32(buffer+4*j,initial);
            w+=step;uint32_t position=base+j*256-(w>>8),index=position>>8;
            if(index>=TE_RING-1)std::exit(1);
            int32_t a=int32_t(m.read32(ring+8*index))>>5,b=int32_t(m.read32(ring+8*(index+1)))>>5;
            int32_t sample=a+((int64_t(b-a)*((position&255)<<23))>>31);
            expected[j]=sample;
            expectedReads += j && index==previousIndex+1 ? 1 : 2;
            previousIndex=index;
        }
        m.write32(stack+4,buffer);m.write32(stack+8,ring);m.write32(stack+12,base);
        m.write32(stack+16,wobble);m.write32(stack+20,step);
        *reads=0;call(reader);
        if(*reads!=expectedReads){std::fprintf(stderr,"reader SDRAM traffic mismatch %u/%u\n",*reads,expectedReads);std::exit(1);}
        for(unsigned j=0;j<16;++j)if(int32_t(m.read32(buffer+4*j))!=expected[j]) {
            std::fprintf(stderr,"reader kernel mismatch case %u sample %u\n",test,j);std::exit(1);
        }
    }
    std::puts("  [PASS] assembly kernels: 1024 filter blocks (both clamps/carry), 512 boundary reader blocks, callee-saved registers");
    std::puts("  [PASS] reader data-load counts match overlap reuse: settled block reads 17 uncached words instead of 32");
}
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
static void benchmark(const std::vector<uint8_t>& image,const std::vector<uint8_t>& raw,uint32_t base,uint32_t state) {
    struct Case { const char* name; unsigned tapes,mode,wow; bool patched; };
    const Case cases[]={
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
        {"Tape x8, moving FREE TIME, WOW=44",8,1,44,true},
        {"Tape x8, changing BEAT TIME, WOW=44",8,2,44,true},
        {"Tape x8, moving FREE TIME, MIX=90",8,3,44,true},
        {"Tape x8, all controls moving, FREE/BEAT/tempo",8,4,127,true},
        {"Tape x8, all controls moving, full synthetic history",8,5,127,true},
    };
    double baseline=0;
    for(const auto& test:cases) {
        ot::Machine m(test.patched?image:read("out/raw/section_3_MAIN_OS.bin"));
        ot::Edma dma;dma_model(m,dma);
        if(test.patched)load(m,raw,base);
        init(m);
        unsigned peak=0,minimum=~0u,loadingPeak=0;unsigned long long total=0;
        constexpr unsigned warmup=1500,measured=1000;
        for(unsigned frame=0;frame<warmup+measured;++frame) {
            if(test.mode==5 && frame==warmup) {
                // Eliminate startup's history-not-yet-recorded shortcuts.
                // This is a synthetic stress fixture, not a natural render.
                for(unsigned t=0;t<8;++t) {
                    m.write32(state+t*sizeof(TapeState)+offsetof(TapeState,valid),TE_RING-1);
                    for(unsigned n=0;n<TE_RING;++n) {
                        int32_t v=std::sin(n*.17+t)*0x40000000;
                        m.write32(0x4f502c10+t*TE_STRIDE+n*8,v);
                        m.write32(0x4f502c14+t*TE_STRIDE+n*8,v);
                    }
                }
            }
            unsigned slot=frame&3,audioSlot=frame&1;
            m.write32(0x800000e0,audioSlot);m.write32(0x80004804,slot);
            m.write32(0x8000181c,test.mode>=4 ? (30+(frame/32)%271)*24 : 2880);
            for(unsigned t=0;t<8;++t) {
                // Load instances successively, including a third onto
                // already-running tape tracks (the reported failure).
                bool tape=t<test.tapes && frame>=t*128;
                auto knobs=0x80001a00+slot*96+t*12,setup=0x80001b80+slot*64+t*8;
                for(unsigned i=0;i<8;++i)m.write8(setup+i,0);
                m.write8(setup+7,tape?0x15:8);m.write8(0x80000eb4+audioSlot*8+t,1);
                const unsigned stockValues[]={60,64,127,0,127,127};
                const unsigned time=test.mode ? (frame/8+t*17)%128 : 60;
                const unsigned tapeValues[]={time,
                    test.mode>=4 ? (frame/7+t*19)%128 : 64,
                    test.mode>=4 ? (frame/11+t*23)%128 : test.wow,
                    test.mode>=4 ? (frame/9+t*29)%128 : 64,
                    test.mode>=4 ? (frame/41)%2 : test.mode==2?1u:0u,
                    test.mode>=4 ? (frame/13+t*31)%128 : test.mode==3?90u:127u};
                for(unsigned i=0;i<6;++i)m.write16(knobs+2*i,(tape?tapeValues[i]:stockValues[i])<<8);
                if(tape){m.write8(setup,51);m.write8(setup+1,64);}
                else m.write8(setup+2,127);
                for(unsigned i=0;i<32;++i) {
                    int32_t sample=std::sin((frame*16+i/2)*.0627+t+(i&1)*.7)*0x20000000;
                    m.write32(0x80003190+audioSlot*1024+t*128+4*i,sample);
                }
            }
            m68k_set_reg(m.getCpuState(),M68K_REG_SP,stack);m.write32(stack,endpc);
            profiling=test.tapes==2 && test.mode==1 && frame==warmup;
            unsigned instructions=run(m,0x400031a0,endpc,250000);
            profiling=false;
            if(frame%128==0 && frame/128<test.tapes)loadingPeak=std::max(loadingPeak,instructions);
            if(frame>=warmup) {
                total+=instructions;peak=std::max(peak,instructions);minimum=std::min(minimum,instructions);
            }
        }
        double mean=double(total)/measured;
        if(!test.patched)baseline=mean;
        std::printf("  [BENCH] %s: mean %.1f, min %u, peak %u instructions/full 8-track 16-sample routine; %.3fx stock\n",
                    test.name,mean,minimum,peak,mean/baseline);
        if(test.tapes)std::printf("  [LOAD] %s: peak %u instructions on an instance-selection frame\n",test.name,loadingPeak);
        // Fixed OCTACLID3 reference: 27,582 instructions for this complete
        // moving-TIME routine. Require >30% savings, not just a new number.
        if(test.tapes==3 && test.mode==1 && mean>=19300) {
            std::fprintf(stderr,"Economy three-instance moving-TIME budget exceeded (19300)\n");std::exit(1);
        }
        // Instruction regression ceilings, NOT available CPU cycles. Keep
        // the full-history/all-controls path bounded as well as TIME-only.
        if(test.tapes==8 && peak >= (test.mode>=4 ? 35000u : 30000u)) {
            std::fprintf(stderr,"Eight-instance instruction regression budget exceeded\n");std::exit(1);
        }
        std::fflush(stdout);
    }
    std::ifstream symbols("out/tapeecho-cpu/profile-symbols.txt");
    std::map<uint32_t,std::string> names; std::string line;
    while(std::getline(symbols,line)) {
        std::istringstream fields(line);uint32_t address;char type;std::string name;
        if(fields>>std::hex>>address>>type>>name && (type=='t'||type=='T')) names[address]=name;
    }
    std::map<std::string,unsigned> totals;
    for(auto [pc,count]:profile) {
        auto next=names.upper_bound(pc);
        std::string name="stock routine/buffering";
        if(pc>=base && pc<base+raw.size() && next!=names.begin())name=std::prev(next)->second;
        totals[name]+=count;
    }
    for(auto [name,count]:totals) std::printf("  [PROFILE] two moving Tape + six stock: %s %u instructions\n",name.c_str(),count);
    std::puts("  [BENCH] Same 44.1kHz/16-sample routine and modelled DMA; 1500 warm-up + 1000 measured blocks, stereo tone, active wet/feedback. Host wall time, DSP cost, cache misses and DMA/bus stalls excluded; NOT hardware CPU percent.");
}
int main(int argc, char **argv) {
    if (argc != 5 && argc != 6) { std::fprintf(stderr, "probe IMAGE RUNTIME BASE STATE [--benchmark]\n"); return 2; }
    auto image = read(argv[1]), raw = read(argv[2]);
    uint32_t base = std::strtoul(argv[3], nullptr, 16), state = std::strtoul(argv[4], nullptr, 16);
    if(argc==6) {
        if(std::strcmp(argv[5],"--benchmark"))return 2;
        benchmark(image,raw,base,state);return 0;
    }
    ot::Machine m(image); ot::Edma dma; dma_model(m,dma); load(m, raw, base); init(m);
    // The real reset must clear previously used state, not merely boot zeros.
    for (unsigned i = 0; i < 8*sizeof(TapeState); ++i) m.write8(state + i, 0xa5);
    init(m);
    for (unsigned i = 0; i < 8*sizeof(TapeState); ++i) if (m.read8(state+i)) return 1;
    std::puts("  [PASS] stock delay reset clears every CPU Tape Echo state byte");
    formatter_tests(m);
    kernel_tests(m);

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
            for (unsigned i=0;i<6;++i) m.write16(knobs+2*i, values[i]<<8);
            // Obsolete setup DRIVE/AGE bytes vary deliberately: the audio
            // engine must use page-1 AGE and ignore the old detail page.
            m.write8(setup,frame%128); m.write8(setup+1,(frame+64)%128); m.write8(setup+7,0x15);
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
    std::printf("  [PASS] all 8 CPU instances match native arithmetic bit-for-bit (%u blocks; TIME/AGE sweeps, FREE/BEAT, tempo, wow, feedback, ring wrap, obsolete setup bytes ignored)\n",frames);
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
