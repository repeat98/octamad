#include <assert.h>
#include <string.h>
#include "allocator.h"
#include "selection.h"
#include "transfer.h"
#include "publication.h"
struct code { const uint32_t *words; const uint16_t *relocations; uint16_t count,init,proc,relocation_count; };
const struct dl_package dl_catalog[32]={[0]={0,1,0,3,1,1,0},[12]={282,1,0,3,0,1,0},
    [16]={207,1,0,3,0,1,0},[20]={0,1,0,2,1,1,1},[21]={0,1,0,2,1,1,1},[28]={932,1,0,1,0,1,0}};
static const uint32_t words[932]={0};
const struct code dl_codes[2][32]={
    {[12]={words,0,282,0,5,0},[16]={words,0,207,0,17,0},[28]={words,0,932,51,80,0}},
    {[12]={words,0,282,0,5,0},[16]={words,0,207,0,17,0},[28]={words,0,932,51,80,0}}};
volatile uint32_t dl_pool_base[2]={0,0},dl_pool_words[2]={0,0},dl_modal_pending;
const uint32_t dl_stub_at_boot=0;
const uint32_t dl_pmap16=1;   /* the buffer planner runs only under the 16K map */
extern volatile uint32_t dl_residency_words[2],dl_residency_commits,dl_residency_rollbacks;
extern void dl_residency_tick(void);
static int status[2]={-2,-2};
static unsigned uploads,binds,unbinds,fail_unbind,probes,stubs,restores,bases;
static unsigned base_entry[8],base_value[8],fail_base;
int dl_upload_start(unsigned c,const struct dl_upload *u) {
    assert(status[c]==-2 && u->offset>=64 && u->offset+u->count<=1408);
    ++uploads; status[c]=1; return 1;
}
int dl_command_start(unsigned c,unsigned op,unsigned id,unsigned init,unsigned proc) {
    assert(c<2 && status[c]==-2 && id<32); (void)init;(void)proc;
    status[c]=1;
    if(op==DL_PROBE) { ++probes;dl_pool_words[c]=1408;dl_pool_base[c]=c ? 0xdc0:0x1000; }
    if(op==DL_BIND) ++binds;
    if(op==DL_BASE) { assert(id<8 && proc<256); base_entry[bases&7]=c*8+id; base_value[bases&7]=proc<<16|init; ++bases;
                      if(fail_base) { --fail_base; status[c]=-1; } }
    if(op==DL_UNBIND) ++restores;
    if(op==DL_BYPASS) ++stubs;
    if(op==DL_UNBIND || op==DL_BYPASS) { ++unbinds; if(fail_unbind) { --fail_unbind;status[c]=-1; } }
    return 1;
}
int dl_job_status(unsigned c) { return status[c]; }
void dl_job_release(unsigned c) { assert(status[c]);status[c]=-2; }
static void settle(void) { for(unsigned n=0;n<300;++n) dl_residency_tick(); }
static void ready(unsigned token) {
    for(unsigned n=0;n<300;++n) {
        int r=dl_selection_poll(token); if(r==DL_SELECT_READY) return;
        assert(r==DL_SELECT_WAIT);
    }
    assert(!"backend did not prepare");
}
int main(void) {
    struct dl_selection s={0};
    assert(dl_selection_prepare(&s,99)==DL_SELECT_WAIT);ready(99);
    dl_selection_commit(99);settle();
    assert(probes==0 && uploads==0 && dl_pool_base[0]==0 && dl_pool_base[1]==0);
    for(unsigned i=0;i<8;++i) s.target[i]=12;
    assert(dl_selection_prepare(&s,1)==DL_SELECT_WAIT);ready(1);
    assert(probes==2 && uploads==2 && binds==2 && dl_residency_words[0]==0 && dl_residency_words[1]==0);
    /* Armed: 16 and 28, unused by this target, dispatch to the stub on both cores. */
    assert(stubs==4);
    assert(dl_publication_ready(s.target));
    uint8_t wrong[16]={0};wrong[0]=28;assert(!dl_publication_ready(wrong));
    /* Committed and retiring the outgoing set: the committed set stays bound. */
    dl_selection_commit(1);assert(dl_publication_ready(s.target));settle();
    assert(dl_publication_ready(s.target));
    assert(dl_residency_words[0]==282 && dl_residency_words[1]==282 && dl_residency_commits==2);
    s.target[0]=28;s.target[1]=16;
    assert(dl_selection_prepare(&s,2)==DL_SELECT_MEMORY); /* genuine 1421 > 1344 */
    assert(uploads==2 && binds==2 && dl_residency_words[1]==282);
    s.target[1]=12;
    assert(dl_selection_prepare(&s,3)==DL_SELECT_WAIT);
    uint8_t eq[16]={12,12,12,12,12,12,12,12};
    assert(dl_publication_ready(eq)); /* live, and kept by the open transaction */
    ready(3);
    dl_selection_cancel(3);assert(!dl_publication_ready(s.target));settle();
    assert(dl_residency_rollbacks==1 && dl_residency_words[1]==282);
    assert(dl_selection_prepare(&s,4)==DL_SELECT_WAIT);ready(4);
    dl_selection_commit(4);settle();
    assert(dl_residency_words[1]==1214 && dl_residency_words[0]==282);
    memset(wrong,0,16);wrong[8]=28;assert(!dl_publication_ready(wrong)); /* Wrong FX slot. */
    memset(s.target,0,16);
    assert(dl_selection_prepare(&s,5)==DL_SELECT_WAIT);
    assert(!dl_publication_ready(eq)); /* live, but this transaction retires it */
    ready(5);
    fail_unbind=1;dl_selection_commit(5);
    uint8_t outgoing[16]={28,12,12,12,12,12,12,12};
    assert(!dl_publication_ready(outgoing)); /* retiring code is never published */
    dl_residency_tick();dl_residency_tick();
    assert(dl_residency_words[1]==1214 && dl_residency_words[0]==282);
    memset(wrong,0,16);wrong[8]=28;assert(!dl_publication_ready(wrong)); /* Wrong FX slot. */ /* failure cannot free live code */
    settle();
    assert(dl_residency_words[0]==0 && dl_residency_words[1]==0 && unbinds>=5);
    assert(restores==0); /* retiring never restores an original entry */
    /* Y buffers (the 16K map: core 0's FX2 blocks are 0x4000, 0x30000, 0x34000;
     * 0x8000 is half gone). Ids 20 and 21 read their base (resident, like a
     * pinned stock reverb). Every slot is known and free by now. Core 0's FX2
     * entries 1, 3, 5, 7 (tracks 5..8) hold stock's 0x4000 0x8000 0x30000 0x34000. */
    unsigned b0;
    memset(s.target,0,16); s.target[13]=20;            /* track 6: the first free block */
    b0=bases; assert(dl_selection_prepare(&s,7)==DL_SELECT_WAIT); ready(7);
    assert(bases==b0+1 && base_entry[b0&7]==3 && base_value[b0&7]==0x4000); /* before ready */
    dl_selection_commit(7); settle();
    s.target[12]=20;                                   /* track 5: 0x4000 is 13's, 0x8000 is gone */
    b0=bases; assert(dl_selection_prepare(&s,8)==DL_SELECT_WAIT); ready(8);
    assert(bases==b0+1 && base_entry[b0&7]==1 && base_value[b0&7]==0x30000);
    dl_selection_commit(8); settle();
    s.target[14]=20;                                   /* cancelled: written, then restored */
    b0=bases; assert(dl_selection_prepare(&s,9)==DL_SELECT_WAIT); ready(9);
    assert(bases==b0+1 && base_entry[b0&7]==5 && base_value[b0&7]==0x34000);
    dl_selection_cancel(9); settle();
    assert(bases==b0+2 && base_entry[(b0+1)&7]==5 && base_value[(b0+1)&7]==0x30000);
    b0=bases; assert(dl_selection_prepare(&s,10)==DL_SELECT_WAIT); ready(10);   /* all three */
    dl_selection_commit(10); settle();
    /* A fourth FX2 reader on core 0 never fits; nothing is uploaded, bound or written. */
    s.target[15]=20; b0=bases; unsigned up=uploads,bi=binds;
    assert(dl_selection_prepare(&s,11)==DL_SELECT_MEMORY);
    assert(bases==b0 && uploads==up && binds==bi);
    /* 12 from 20 to 21: its outgoing block stays held until 20 retires: refused;
     * released first, then taken. */
    s.target[15]=0; s.target[12]=21; b0=bases;
    assert(dl_selection_prepare(&s,12)==DL_SELECT_MEMORY && bases==b0);
    s.target[12]=0; assert(dl_selection_prepare(&s,13)==DL_SELECT_WAIT); ready(13);
    dl_selection_commit(13); settle();
    s.target[12]=21; b0=bases;
    assert(dl_selection_prepare(&s,14)==DL_SELECT_WAIT); ready(14);
    assert(bases==b0);                                 /* entry 1 already holds the freed block */
    dl_selection_commit(14); settle();
    /* A table write that fails cancels the transition: not ready, and it retries cleanly. */
    s.target[9]=20; fail_base=1; b0=bases;             /* core 1 track 2: entry 3, 0x8000 -> 0x4000 */
    assert(dl_selection_prepare(&s,15)==DL_SELECT_WAIT);
    int r=DL_SELECT_WAIT;
    for(unsigned n=0;n<300 && r==DL_SELECT_WAIT;++n) r=dl_selection_poll(15);
    assert(r!=DL_SELECT_READY && r!=DL_SELECT_WAIT && bases==b0+1 && base_entry[b0&7]==8+3);
    settle();
    b0=bases; assert(dl_selection_prepare(&s,16)==DL_SELECT_WAIT); ready(16);
    assert(bases==b0+1 && base_entry[b0&7]==8+3 && base_value[b0&7]==0x4000);
    return 0;
}
