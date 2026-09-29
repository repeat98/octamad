/* Bounded, independent-of-source frame transport. The first firmware gate
 * proves delivery/acknowledgement before granting any executable-memory write.
 * Buffers are accessed via the uncached alias on ColdFire, by DMA and software.
 */
#include "transfer.h"
#include "selection.h"
volatile uint16_t dl_tx[2][DL_WORDS]={{0}}, dl_rx[2][32]={{0}};
volatile uint32_t dl_frames=0, dl_accepted[2]={0}, dl_rejected[2]={0}, dl_errors=0;
volatile uint32_t dl_request_probe=0, dl_request_stage=0, dl_modal_pending=0, dl_modal_shown=0;
static uint16_t sequence[2]={0}, pending[2]={0}, age[2]={0};
static uint32_t requests=0, stages=0;
volatile uint32_t dl_pool_base[2]={0,0};
struct job {
    struct dl_upload upload;
    uint32_t expected;
    uint16_t position, opcode, id, init, proc;
    volatile uint16_t state; /* 0 idle, 1 queued, 2 running, 3 done, 4 failed */
};
static struct job jobs[2]={0};
static void publish(void) { __asm__ volatile("" ::: "memory"); }
int dl_upload_start(unsigned c,const struct dl_upload *u) {
    if(c>1 || jobs[c].state || !dl_pool_base[c] || !u || !u->words || !u->count ||
       u->offset<DL_CODE_START || u->offset+u->count>DL_RUNTIME_WORDS ||
       (u->relocation_count && !u->relocations)) return 0;
    for(unsigned i=0;i<u->count;++i) if(u->words[i]>0xffffffu) return 0;
    for(unsigned i=0;i<u->relocation_count;++i)
        if((u->relocations[i]&0x7fff)>=u->count || (i && (u->relocations[i]&0x7fff)<=(u->relocations[i-1]&0x7fff))) return 0;
    jobs[c].upload.words=u->words; jobs[c].upload.relocations=u->relocations;
    jobs[c].upload.count=u->count; jobs[c].upload.relocation_count=u->relocation_count;
    jobs[c].upload.offset=u->offset; jobs[c].position=0; jobs[c].opcode=DL_WRITE;
    publish(); jobs[c].state=1; return 1;
}
int dl_command_start(unsigned c,unsigned op,unsigned id,unsigned init,unsigned proc) {
    if(c>1 || jobs[c].state || id>=32 ||
       (op!=DL_PROBE && op!=DL_BIND && op!=DL_UNBIND && op!=DL_BYPASS)) return 0;
    if(op==DL_BIND && (init<DL_CODE_START || proc<DL_CODE_START ||
                       init>=DL_RUNTIME_WORDS || proc>=DL_RUNTIME_WORDS)) return 0;
    jobs[c].opcode=op; jobs[c].id=id; jobs[c].init=init; jobs[c].proc=proc;
    publish(); jobs[c].state=1; return 1;
}
int dl_job_status(unsigned c) {
    if(c>1) return -1;
    unsigned state=jobs[c].state;
    publish(); return state==3 ? 1 : state==4 ? -1 : state ? 0 : -2;
}
void dl_job_release(unsigned c) {
    if(c<2 && jobs[c].state>=3) { publish(); jobs[c].state=0; }
}
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
    if(jobs[c].state==2) {
        struct job *j=&jobs[c];
        if(opcode==DL_WRITE) {
            unsigned n=j->upload.count-j->position;
            if(n>DL_DATA) n=DL_DATA;
            t[4]=n; t[5]=j->upload.offset+j->position; j->expected=0;
            for(unsigned i=0;i<n;++i) {
                unsigned index=j->position+i;
                uint32_t value=j->upload.words[index];
                for(unsigned r=0;r<j->upload.relocation_count;++r)
                    if((j->upload.relocations[r]&0x7fff)==index) {
                        uint32_t base=dl_pool_base[c]+j->upload.offset;
                        value=(j->upload.relocations[r]&0x8000) ? value-base : value+base;
                    }
                value&=0xffffffu;
                t[8+2*i]=(uint16_t)(value>>8); t[9+2*i]=(uint16_t)(value&255);
                j->expected=(j->expected+value)&0xffffffu;
            }
        } else if(opcode==DL_BIND || opcode==DL_UNBIND || opcode==DL_BYPASS) {
            t[4]=j->id; t[5]=j->init; t[7]=j->proc;
        }
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
                unsigned valid=r[2]==0 && r[3]==c;
                if(jobs[c].state==2 && jobs[c].opcode==DL_WRITE)
                    valid=valid && (((uint32_t)r[5]<<16)|r[4])==jobs[c].expected;
                if(valid) {
                    ++dl_accepted[c];
                    if(r[6] && r[6]<0x2000 && r[7]==DL_RUNTIME_WORDS) dl_pool_base[c]=r[6];
                } else { ++dl_rejected[c]; ++dl_errors; dl_modal_pending=1; }
                if(jobs[c].state==2) {
                    if(!valid) jobs[c].state=4;
                    else if(jobs[c].opcode==DL_WRITE) {
                        unsigned n=jobs[c].upload.count-jobs[c].position;
                        if(n>DL_DATA) n=DL_DATA;
                        jobs[c].position+=n;
                        jobs[c].state=jobs[c].position==jobs[c].upload.count ? 3 : 1;
                    } else jobs[c].state=3;
                }
                pending[c]=0;
                UNCACHED(dl_tx[c])[0]=0;
            } else if(++age[c]>=64) {
                ++dl_errors; pending[c]=0; UNCACHED(dl_tx[c])[0]=0;
                if(jobs[c].state==2) jobs[c].state=4;
                dl_modal_pending=1;
            }
        }
    }
    for(unsigned c=0;c<2;++c) if(!pending[c] && jobs[c].state==1) {
        jobs[c].state=2; packet(c,jobs[c].opcode);
    }
    if(dl_request_probe!=requests && !pending[0] && !pending[1] && !jobs[0].state && !jobs[1].state) {
        requests=dl_request_probe;
        packet(0,DL_PROBE); packet(1,DL_PROBE);
    }
    if(dl_request_stage!=stages && !pending[0] && !pending[1] && !jobs[0].state && !jobs[1].state) {
        stages=dl_request_stage;
        packet(0,DL_STAGE); packet(1,DL_STAGE);
    }
    return pending[0] || pending[1];
}
/* UI-task-only. A DMA interrupt must never call a popup function. */
extern void dl_residency_tick(void);
void dl_ui(void) {
    dl_selection_tick();
    dl_residency_tick();
    if(dl_modal_pending) {
        unsigned reason=dl_modal_pending;
        dl_modal_pending=0;
        ++dl_modal_shown;
        const char *text=reason==2 ? "DSP MEMORY FULL" :
                         reason==3 ? "DSP OVERLOAD" : "DSP LOAD FAILED";
        dl_show_message(text,0x30);
    }
}
