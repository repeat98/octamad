/* Bounded, independent-of-source frame transport. The first firmware gate
 * proves delivery/acknowledgement before granting any executable-memory write.
 * Buffers are accessed via the uncached alias on ColdFire, by DMA and software.
 */
#include "transfer.h"
volatile uint16_t dl_tx[2][DL_WORDS]={{0}}, dl_rx[2][32]={{0}};
volatile uint32_t dl_frames=0, dl_accepted[2]={0}, dl_rejected[2]={0}, dl_errors=0;
volatile uint32_t dl_request_probe=0, dl_request_stage=0, dl_modal_pending=0, dl_modal_shown=0;
static uint16_t sequence[2]={0}, pending[2]={0}, age[2]={0};
static uint32_t requests=0, stages=0;
#ifdef DL_NATIVE_TEST
#define UNCACHED(p) (p)
extern void dl_show_message(const char *, unsigned);
#else
#define UNCACHED(p) ((volatile uint16_t *)((uintptr_t)(p)+0x08000000u))
#define dl_show_message ((void (*)(const char *,unsigned))0x4005a2b8u)
#endif
static void packet(unsigned c, unsigned opcode) {
    volatile uint16_t *t=UNCACHED(dl_tx[c]);
    uint16_t sum=0;
    for(unsigned i=0;i<DL_WORDS;++i) t[i]=0;
    if(++sequence[c]==0) ++sequence[c];
    t[0]=DL_MAGIC; t[1]=sequence[c]; t[2]=(uint16_t)opcode;
    t[3]=(uint16_t)c; t[4]=DL_DATA;
    for(unsigned i=0;i<DL_DATA;++i) {
        uint32_t v=(0x123456u+0x513579u*i+sequence[c]+c)&0xffffffu;
        t[8+2*i]=(uint16_t)(v>>8); t[9+2*i]=(uint16_t)(v&255);
    }
    for(unsigned i=0;i<DL_WORDS;++i) sum=(uint16_t)(sum+t[i]);
    t[6]=(uint16_t)-sum;
    pending[c]=sequence[c]; age[c]=0;
}
unsigned dl_frame(void) {
    ++dl_frames;
    for(unsigned c=0;c<2;++c) {
        volatile uint16_t *r=UNCACHED(dl_rx[c]);
        if(pending[c]) {
            if(r[0]==DL_ACK && r[1]==pending[c]) {
                if(r[2]==0 && r[3]==c) ++dl_accepted[c];
                else { ++dl_rejected[c]; ++dl_errors; dl_modal_pending=1; }
                pending[c]=0;
                UNCACHED(dl_tx[c])[0]=0;
            } else if(++age[c]>=64) {
                ++dl_errors; pending[c]=0; UNCACHED(dl_tx[c])[0]=0;
                dl_modal_pending=1;
            }
        }
    }
    if(dl_request_probe!=requests && !pending[0] && !pending[1]) {
        requests=dl_request_probe;
        packet(0,DL_PROBE); packet(1,DL_PROBE);
    }
    if(dl_request_stage!=stages && !pending[0] && !pending[1]) {
        stages=dl_request_stage;
        packet(0,DL_STAGE); packet(1,DL_STAGE);
    }
    return pending[0] || pending[1];
}
/* UI-task-only. A DMA interrupt must never call a popup function. */
void dl_ui(void) {
    if(dl_modal_pending) {
        unsigned reason=dl_modal_pending;
        dl_modal_pending=0;
        ++dl_modal_shown;
        const char *text=reason==2 ? "DSP MEMORY FULL" :
                         reason==3 ? "DSP OVERLOAD" : "DSP LOAD FAILED";
        dl_show_message(text,0x30);
    }
}
