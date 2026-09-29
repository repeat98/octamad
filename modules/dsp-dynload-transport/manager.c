/* Real P residency and transport backend. The first runtime deliberately keeps
 * each algorithm's static dispatch as rollback storage. Binding a relocated
 * identical implementation changes neither knobs nor r7 state. Do not reclaim
 * those static spans until every pre-publication Part path is qualified. */
#include "allocator.h"
#include "selection.h"
#include "transfer.h"
#include "publication.h"
struct code { const uint32_t *words; const uint16_t *relocations;
              uint16_t count,init,proc,relocation_count; };
extern const struct dl_package dl_catalog[32];
extern const struct code dl_codes[2][32];
static struct dl_allocator allocator={0};
static uint8_t desired[16]={0};
#ifndef DL_NATIVE_TEST
static uint8_t observed[16]={0};
static unsigned observed_valid=0;
static uint32_t auto_serial=0x80000000u;
#endif
static unsigned initialized=0,phase=0,cursor=0,waiting=0,automatic=0,cancelling=0;
static uint32_t current=0;
static int result=0;
volatile uint32_t dl_residency_enabled=1; /* Test/control bypass; static originals required. */
volatile uint32_t dl_residency_commits=0,dl_residency_rollbacks=0,dl_residency_failures=0;
volatile uint32_t dl_residency_words[2]={0};
/* Distinct live sets seen running a managed id without bound relocated code. */
volatile uint32_t dl_unguarded=0;
/* Guard preparation/monitoring runs on the UI task. ISR owns only transport. */
static void bytes(void *d,const void *s,unsigned n) {
    volatile uint8_t *to=d; const uint8_t *from=s;
    for(unsigned i=0;i<n;++i) to[i]=from[i];
}
static void begin(const uint8_t *ids,uint32_t token,unsigned is_auto) {
    bytes(desired,ids,16); current=token; automatic=is_auto;
    result=DL_SELECT_WAIT; phase=1; cursor=0; waiting=0; cancelling=0;
}
static void report(int error) {
    result=error; ++dl_residency_failures;
    if(automatic) dl_modal_pending=error==DL_SELECT_MEMORY ? 2 : error==DL_SELECT_PROCESSING ? 3 : 1;
}
static void rollback(void) { cancelling=1; }
static void counts(void) {
    for(unsigned c=0;c<2;++c) {
        unsigned words=0;
        for(unsigned p=0;p<32;++p) if(allocator.live[c][p].present) words+=allocator.live[c][p].words;
        dl_residency_words[c]=words;
    }
}
static unsigned needed(unsigned index,unsigned mode) {
    unsigned c=index/32,p=index%32;
    if(mode==6) return allocator.live[c][p].present && !allocator.target[c][p].present;
    return allocator.target[c][p].present && !allocator.live[c][p].present;
}
static void advance(void) {
    if(!phase) return;
    if(phase==1) {
        /* Pinned-only boot/project sets need no DSP transaction. In particular,
         * do not make stock loading depend on a clock before any code upload. */
        unsigned probe=0;
        for(unsigned i=0;i<16;++i)
            if(desired[i]<32 && !dl_catalog[desired[i]].resident) probe=1;
        if(!probe && !waiting) cursor=2;
        if(waiting) {
            int s=dl_job_status(cursor);
            if(!s) return;
            dl_job_release(cursor); waiting=0;
            if(s<0 || !dl_pool_base[cursor]) { report(DL_SELECT_UNAVAILABLE); phase=0; return; }
            ++cursor;
        }
        while(cursor<2 && dl_pool_base[cursor]) ++cursor;
        if(cursor<2) { waiting=dl_command_start(cursor,DL_PROBE,0,0,0); return; }
        if(cancelling) { phase=0; return; }
        if(!initialized) {
            /* Algorithms still execute the original stock scheduling path.
             * No additional overlapping instances are created by rebinding;
             * existing DSP processing is reserved outside this P-only pool. */
            dl_allocator_init(&allocator,dl_catalog,DL_RUNTIME_WORDS-DL_CODE_START,
                              DL_RUNTIME_WORDS-DL_CODE_START,0,0);
            initialized=1;
        }
        int r=dl_allocator_prepare(&allocator,desired,current);
        if(r<0) {
            report(r==DL_ALLOC_MEMORY || r==DL_ALLOC_TRANSITION ? DL_SELECT_MEMORY :
                   r==DL_ALLOC_CYCLES ? DL_SELECT_PROCESSING : DL_SELECT_UNAVAILABLE);
            phase=0; return;
        }
        phase=2; cursor=0;
    }
    if(phase==5) { /* Prepared, waiting for the original stock setter. */
        if(cancelling) { phase=7; cursor=0; }
        else {
#ifndef DL_NATIVE_TEST
            if(automatic==2) {
                const volatile uint8_t *live=(const volatile uint8_t *)0x80000ec4u;
                unsigned equal=1;
                for(unsigned i=0;i<16;++i) if(live[i]!=desired[i]) equal=0;
                if(equal) { dl_selection_commit(current);return; }
            }
#endif
            return;
        }
    }
    if(waiting) {
        unsigned c=cursor/32;
        int s=dl_job_status(c);
        if(!s) return;
        dl_job_release(c); waiting=0;
        if(s<0) {
            report(DL_SELECT_UNAVAILABLE);
            if(phase==6 || phase==7) {
                /* Never free memory after an unacknowledged unbind. Retry it;
                 * the original binding may still execute on that core. */
                return;
            }
            cancelling=1;
        }
        ++cursor;
    }
    if(cancelling && phase!=7) { phase=7; cursor=0; }
    unsigned mode=phase;
    while(cursor<64 && !needed(cursor,mode)) ++cursor;
    if(cursor<64) {
        unsigned c=cursor/32,p=cursor%32;
        const struct code *code=&dl_codes[c][p];
        unsigned offset=DL_CODE_START+allocator.target[c][p].offset;
        if(mode==2) {
            struct dl_upload u={code->words,code->relocations,code->count,code->relocation_count,offset};
            waiting=dl_upload_start(c,&u);
        } else waiting=dl_command_start(c,mode==3 ? DL_BIND:DL_UNBIND,p,
                                         offset+code->init,offset+code->proc);
        if(!waiting) { report(DL_SELECT_UNAVAILABLE); cancelling=1; }
        return;
    }
    cursor=0;
    if(mode==2) { phase=3; return; }
    if(mode==3) {
        for(unsigned c=0;c<2;++c) if(allocator.required & (1u<<c)) dl_allocator_ack(&allocator,current,c);
        phase=5; result=DL_SELECT_READY;
        if(automatic) {
            dl_allocator_commit(&allocator,current); phase=6; ++dl_residency_commits; counts();
        }
    } else if(mode==6) { dl_allocator_retire(&allocator,current); phase=0; counts(); }
    else if(mode==7) { dl_allocator_cancel(&allocator,current); phase=0; ++dl_residency_rollbacks; counts(); }
}
int dl_selection_prepare(const struct dl_selection *s,uint32_t token) {
    if(!dl_residency_enabled) return DL_SELECT_READY;
#ifndef DL_NATIVE_TEST
    dl_publication_finish();
#endif
    /* Drain completed/pinned-only bookkeeping without waiting for a DSP job.
     * A real outstanding transfer still returns busy and retains its owner. */
    advance();advance();
    if(phase) return DL_SELECT_UNAVAILABLE;
    for(unsigned i=0;i<8;++i) if(s->target_source[i]>4) return DL_SELECT_UNAVAILABLE;
    begin(s->target,token,0); advance(); return result;
}
int dl_selection_poll(uint32_t token) {
    if(token!=current) return DL_SELECT_UNAVAILABLE;
    advance(); return result;
}
void dl_selection_cancel(uint32_t token) { if(token==current && phase && phase!=6) rollback(); }
void dl_selection_commit(uint32_t token) {
    if(token!=current || phase!=5 || result!=DL_SELECT_READY) return;
    if(dl_allocator_commit(&allocator,current)!=1) { report(DL_SELECT_UNAVAILABLE); return; }
    phase=6; cursor=0; ++dl_residency_commits; counts();
}
#ifndef DL_NATIVE_TEST
/* Every managed id in the live set runs bound relocated code: a committed
 * placement that is not being retired, or an acknowledged target of a ready
 * transaction (a guarded route publishes before its commit). */
static unsigned bound(const volatile uint8_t *ids) {
    for(unsigned i=0;i<16;++i) {
        unsigned p=ids[i],c=(i&7)<4 ? 1:0;
        if(p>=32 || dl_catalog[p].resident) continue;
        if(allocator.live[c][p].present && (phase!=6 || allocator.target[c][p].present)) continue;
        if(phase==5 && result==DL_SELECT_READY && !cancelling && allocator.target[c][p].present) continue;
        return 0;
    }
    return 1;
}
static uint8_t unsafe[16]={0};
static unsigned unsafe_valid=0;
/* Tripwire, every UI tick: a live set with unbound managed code reached the
 * DSP through a route no guard covers, and the static originals ran it. Zero
 * on every route is the condition for reclaiming them. A set that appears and
 * goes again between two ticks is not seen. */
static void tripwire(void) {
    const volatile uint8_t *ids=(const volatile uint8_t *)0x80000ec4u;
    if(bound(ids)) { unsafe_valid=0; return; }
    unsigned same=unsafe_valid;
    for(unsigned i=0;i<16;++i) if(ids[i]!=unsafe[i]) same=0;
    if(same) return;
    for(unsigned i=0;i<16;++i) unsafe[i]=ids[i];
    unsafe_valid=1; ++dl_unguarded;
}
#endif
void dl_residency_tick(void) {
    if(!dl_residency_enabled) return;
    advance();
#ifndef DL_NATIVE_TEST
    dl_publication_tick();
    tripwire();
    if(phase) return;
    /* Observe the actual live set, including automatic pattern/project paths.
     * Static originals remain valid while preparation runs or if it refuses.
     * This observer is NOT authorization to reclaim those fallback spans. */
    const volatile uint8_t *ids=(const volatile uint8_t *)0x80000ec4u;
    unsigned changed=!observed_valid;
    for(unsigned i=0;i<16;++i) if(ids[i]!=observed[i]) changed=1;
    if(!changed) return;
    for(unsigned i=0;i<16;++i) observed[i]=ids[i];
    observed_valid=1;
    if(++auto_serial==0) auto_serial=0x80000000u;
    begin(observed,auto_serial,1);
#endif
}

/* Publication guard owns this token through the first use of its target. */
int dl_publication_prepare(const uint8_t ids[16],const uint8_t sources[8],uint32_t token) {
    if(phase) return DL_SELECT_UNAVAILABLE;
    for(unsigned i=0;i<8;++i) if(sources[i]>4) return DL_SELECT_UNAVAILABLE;
    begin(ids,token,0);advance();return result;
}
int dl_publication_poll(uint32_t token) { return dl_selection_poll(token); }
void dl_publication_arm(uint32_t token) {
    if(current==token && phase==5 && result==DL_SELECT_READY) automatic=2;
}
int dl_publication_ready(const uint8_t ids[16]) {
    if(!dl_residency_enabled) return 1;
    unsigned managed=0;
    for(unsigned i=0;i<16;++i) {
        unsigned p=ids[i];
        if(p>=32 || !dl_catalog[p].qualified || !(dl_catalog[p].slots & (i<8 ? 1:2))) return 0;
        if(!dl_catalog[p].resident) managed=1;
    }
    /* Pinned-only targets cannot race arena retirement, including boot/setup
     * calls before the runtime has initialized its first managed allocation. */
    if(!managed) return 1;
    if(!initialized || (phase!=0 && phase!=5 && phase!=6)) return 0;
    if(phase==5) {
        if(result!=DL_SELECT_READY || cancelling) return 0;
        for(unsigned i=0;i<16;++i) if(ids[i]!=desired[i]) return 0;
    }
    for(unsigned i=0;i<16;++i) {
        unsigned p=ids[i],c=(i&7)<4 ? 1:0;
        if(p>=32 || !dl_catalog[p].qualified || !(dl_catalog[p].slots & (i<8 ? 1:2))) return 0;
        if(dl_catalog[p].resident) continue;
        /* Committed and retiring its outgoing placements: the committed set
         * stays bound, so publishing it is safe before retirement ends. */
        if(phase==6) { if(allocator.target[c][p].present) continue; return 0; }
        if(allocator.live[c][p].present) continue;
        if(phase==5 && result==DL_SELECT_READY && allocator.target[c][p].present) continue;
        return 0;
    }
    return 1;
}
int dl_publication_idle(void) { return phase==0; }
