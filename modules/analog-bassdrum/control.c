/* Native source renderer + stock-page registration, derived from the measured
 * Machinedrum Part/chooser seams and the stock kind-table renderer ABI.
 * The synthesis is upstream of AMP and both FX slots: 808 and 909 on the DSP via ab_glue.asm.
 */
#include "engine.h"
#define U8(a) (*(volatile uint8_t *)(uintptr_t)(a))
#define U32(a) (*(volatile uint32_t *)(uintptr_t)(a))
#define BANK 0x46c82456u
#define PART_IDX 0x100b14cfu
#define PART_OFF 0x8ed80u
#define PART_STRIDE 0x18b2u
#define SIG 60u
#define DESC_SIZE 0x1cau
static AbVoice voices[8] = {{0}};
static uint8_t desc[2][DESC_SIZE] = {{0}};
uint32_t ab_desc_p = 0;
uint32_t ab_render_calls = 0, ab_hits = 0;
static unsigned signed_track(const volatile uint8_t *part, unsigned t) {
    const volatile uint8_t *s=part+SIG+30*t;
    return t<8 && part[0x22+t]==1 && s[0]=='A' && s[1]=='B' && s[2]==1;
}
/* Development CPU admission: two voices. All tracks are addressable;
 * more than two simultaneous DSP voices have not been timing-qualified. */
unsigned ab_admit_track(const volatile uint8_t *part, unsigned track) {
    unsigned count=0;
    for(unsigned t=0;t<8;++t) if(t!=track && signed_track(part,t)) ++count;
    return track<8 && count<2;
}
static unsigned admitted_voice(const volatile uint8_t *part, unsigned track) {
    unsigned count=0;
    for(unsigned t=0;t<track;++t) if(signed_track(part,t)) ++count;
    return count<2;
}
static volatile uint8_t *part_base(void) {
    return (volatile uint8_t *)(uintptr_t)(U32(BANK)+PART_OFF+(U8(PART_IDX)&3)*PART_STRIDE);
}
/* Track double-tap must not open FLEX's sample pool for a synthesized source. */
unsigned ab_selected_source(void) {
    unsigned track=U8(0x100b14ccu);
    return !U8(0x80000015u) && track<8 && signed_track(part_base(),track);
}
unsigned ab_type(unsigned type, const volatile uint8_t *ptr) {
    volatile uint8_t *part=part_base();
    uintptr_t t=(uintptr_t)ptr-(uintptr_t)(part+0x22);
    return type==1 && t<8 && signed_track(part,(unsigned)t) ? 5 : type;
}
static void put32(uint8_t *p,uint32_t v) {
    p[0]=(uint8_t)(v>>24); p[1]=(uint8_t)(v>>16); p[2]=(uint8_t)(v>>8); p[3]=(uint8_t)v;
}
static void text(uint8_t *p,const char *s,unsigned n) {
    unsigned i=0; for (;i+1<n && s[i];++i) p[i]=(uint8_t)s[i];
    for (;i<n;++i) p[i]=0;
}
void ab_model_fmt(char *out,int value) {
    out[0]=value ? '9':'8'; out[1]='0'; out[2]=out[0]; out[3]=0;
}
void ab_lpf_fmt(char *out,int value) {
    if(!value) { text((uint8_t*)out,"OFF",4); return; }
    if(value==64) { text((uint8_t*)out,"ORIG",5); return; }
    unsigned hz=ab_lpf_frequency((unsigned)value),n=0;
    char digits[5];
    do { digits[n++]=(char)('0'+hz%10); hz/=10; } while(hz && n<5);
    unsigned i=0; while(n) out[i++]=digits[--n]; out[i]=0;
}
static uint32_t page_for(unsigned model) {
    if (!ab_desc_p) {
        const volatile uint8_t *src=(const volatile uint8_t *)0x400d3176u;
        static const char *const names[2][12]={
            {"PITCH","DECAY","TONE","ATK","SWEEP","SAT","MODEL","ACCNT","LPF","LOW","HIGH","---"},
            {"PITCH","DECAY","TUNE","ATK","TDEP","SAT","MODEL","ACCNT","LPF","LOW","HIGH","---"}
        };
        for(unsigned m=0;m<2;++m) {
            uint8_t *d=desc[m];
            for(unsigned i=0;i<DESC_SIZE;++i) d[i]=src[i];
            text(d+0x3c,"SYN",5); text(d+0x41,"ANALOG BD",13);
            for(unsigned i=0;i<12;++i) {
                text(d+0x4e + 6*i,names[m][i],6);
                d[0x96+i]=ab_defaults[i];
                put32(d+0xa2+4*i,0);
                put32(d+0xd2+4*i,i==6?2:128);
                put32(d+0x102+4*i,i==6?(uint32_t)(uintptr_t)ab_model_fmt:(i==8 ? (uint32_t)(uintptr_t)ab_lpf_fmt:0));
                put32(d+0x132+4*i,i==6 ? 0x400477d4u : 0);
                put32(d+0x162+4*i,0);
            }
            put32(d+0x1c2,0x111); put32(d+0x1c6,0x11111111u);
        }
        ab_desc_p=(uint32_t)(uintptr_t)(desc[0]+0x38);
    }
    return (uint32_t)(uintptr_t)(desc[model!=0]+0x38);
}
uint32_t ab_track_page(const volatile uint8_t *type_ptr) {
    volatile uint8_t *part=part_base();
    uintptr_t track=(uintptr_t)type_ptr-(uintptr_t)(part+0x22);
    return page_for(track<8 ? part[0x1da+6+30*track] : 0);
}
void ab_ui_tick(void) {
    if(U32(BANK)<0x40000000u || U32(BANK)>=0x48000000u) {
        U32(0x400d5f38u+5*4)=page_for(0); return;
    }
    volatile uint8_t *part=part_base();
    U32(0x400d5f38u+5*4)=ab_track_page(part+0x22+(U8(0x100b14ccu)&7));
}
/* Validator temporarily sees stock FLEX defaults for every AB track. All
 * twelve original bytes are restored. Every other Part byte is checked by
 * stock's real validator. The assembly trampoline skips our own detour. */
extern int ab_stock_validate(void *part);
int ab_validate_part(uint8_t *part) {
    uint8_t saved[8][12]; unsigned mask=0;
    const volatile uint8_t *stock=(const volatile uint8_t *)0x400d320cu;
    for(unsigned t=0;t<8;++t) if(signed_track(part,t)) {
        mask|=1u<<t;
        for(unsigned k=0;k<12;++k) {
            unsigned at=(k<6?0x2a:0x1da)+30*t+6+k%6;
            saved[t][k]=part[at]; part[at]=stock[k];
        }
    }
    int result=ab_stock_validate(part);
    for(unsigned t=0;t<8;++t) if(mask&(1u<<t))
        for(unsigned k=0;k<12;++k) {
            unsigned at=(k<6?0x2a:0x1da)+30*t+6+k%6;
            part[at]=saved[t][k];
        }
    return result;
}
/* ABI measured at 4000d430/4000d518. Every track is rendered twice per
 * frame around its event's sample offset; the second call has end=16.
 * Header: source count, ring start, Q26 source rate, Q26 read position.
 * Stock transport converts the high 24 bits of each L/R long to DSP words.
 */
int ab_render(unsigned track,unsigned ping,unsigned start,unsigned end) {
    if(track>=8 || !signed_track(part_base(),track)) {
        if(track<8) ab_reset(&voices[track]);
        return ((int (*)(unsigned,unsigned,unsigned,unsigned))0x40004008u)(track,ping,start,end);
    }
    unsigned admitted=admitted_voice(part_base(),track);
    ++ab_render_calls;
    volatile uint32_t *cursor=(volatile uint32_t *)(uintptr_t)U32(0x80001c80u);
    volatile uint32_t *rs=(volatile uint32_t *)(uintptr_t)U32(0x800062a4u);
    volatile uint16_t *fp=(volatile uint16_t *)(uintptr_t)U32(0x800062a8u);
    uint8_t p[12];
    for(unsigned k=0;k<12;++k) {
        p[k]=k<6 ? (uint8_t)(fp[k]>>8)
                 : U8(0x80000810u+72*track+0x20+k-6);
    }
    /* The stock builder calls twice, before and after the event offset.
     * Reserve the same space as FLEX so every later track keeps its record
     * boundary. Once the second segment exists, replace the start with a
     * control record: two signature halves, trig flag, then twelve knobs.
     * The transport sends each long as high/low 16-bit DSP words. */
    if(admitted) {
        unsigned n=end>start && end<=16 ? end-start:0;
        for(unsigned i=0;i<4+2*n;++i) cursor[i]=0;
        if(end==16) {
            /* On the first hit the first renderer can still be stock FLEX.
             * Use the packer's fixed slot, not that second call's cursor. */
            volatile uint32_t *record=(volatile uint32_t *)(uintptr_t)
                (0x80001c90u+(ping&1)*0xa80u+336u*track);
            unsigned trig=(U8(0x46104d0cu+track)&16)!=0;
            record[0]=0xab090000u; record[1]=0x09090000u|trig;
            record[2]=record[3]=0;
            for(unsigned k=0;k<6;++k) record[4+k]=((uint32_t)p[2*k]<<16)|p[2*k+1];
            if(trig) ++ab_hits;
        }
        U32(0x80001c80u)=(uint32_t)(uintptr_t)(cursor+4+2*n);
        ab_reset(&voices[track]);
        return 0;
    }
    AbVoice *v=&voices[track];
    if(!v->noise || !admitted) ab_reset(v);
    if(admitted && end==16 && (U8(0x46104d0cu+track)&16)) {
        ab_trigger(v,p); ++ab_hits;
    }
    unsigned n=end>start && end<=16 ? end-start:0;
    unsigned pos=rs[8]&63;
    cursor[0]=n; cursor[1]=pos; cursor[2]=0x04000000u; cursor[3]=pos<<26;
    for(unsigned i=0;i<n;++i) {
        uint32_t sample=(uint32_t)ab_sample(v,p)<<8;
        cursor[4+2*i]=sample; cursor[5+2*i]=sample;
    }
    rs[8]=(pos+n)&63; rs[0]=rs[8]<<26; rs[1]=0; rs[9]=0x04000000u;
    U32(0x80001c80u)=(uint32_t)(uintptr_t)(cursor+4+2*n);
    return 0;
}
