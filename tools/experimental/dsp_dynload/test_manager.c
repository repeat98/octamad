#include <assert.h>
#include <string.h>
#include "allocator.h"
#include "selection.h"
#include "transfer.h"
#include "publication.h"
struct code { const uint32_t *words; const uint16_t *relocations; uint16_t count,init,proc,relocation_count; };
const struct dl_package dl_catalog[32]={[0]={0,1,0,3,1,1},[12]={282,1,0,3,0,1},
    [16]={207,1,0,3,0,1},[28]={932,1,0,1,0,1}};
static const uint32_t words[932]={0};
const struct code dl_codes[2][32]={
    {[12]={words,0,282,0,5,0},[16]={words,0,207,0,17,0},[28]={words,0,932,51,80,0}},
    {[12]={words,0,282,0,5,0},[16]={words,0,207,0,17,0},[28]={words,0,932,51,80,0}}};
volatile uint32_t dl_pool_base[2]={0,0},dl_modal_pending;
extern volatile uint32_t dl_residency_words[2],dl_residency_commits,dl_residency_rollbacks;
extern void dl_residency_tick(void);
static int status[2]={-2,-2};
static unsigned uploads,binds,unbinds,fail_unbind,probes,stubs,restores;
int dl_upload_start(unsigned c,const struct dl_upload *u) {
    assert(status[c]==-2 && u->offset>=64 && u->offset+u->count<=1408);
    ++uploads; status[c]=1; return 1;
}
int dl_command_start(unsigned c,unsigned op,unsigned id,unsigned init,unsigned proc) {
    assert(c<2 && status[c]==-2 && id<32); (void)init;(void)proc;
    status[c]=1;
    if(op==DL_PROBE) { ++probes;dl_pool_base[c]=c ? 0xdc0:0x1000; }
    if(op==DL_BIND) ++binds;
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
    return 0;
}
