/* Prepare queued sequencer targets on the UI task. The sequencer boundary only
 * inspects acknowledged residency; it never allocates, transfers or blocks. */
#include "publication.h"
#include "selection.h"
#include "transfer.h"
static uint32_t serial=0x40000000u,token=0;
static volatile unsigned pending=0,bank=0,pattern=0,deferred=0;
static volatile uint32_t missed=0;
static uint8_t ids[16]={0},sources[8]={0};
volatile uint32_t dl_publication_prepared=0,dl_publication_deferred=0,dl_publication_refused=0;
#ifndef DL_NATIVE_TEST
#define BYTE(a) (*(volatile uint8_t *)(uintptr_t)(a))
static unsigned capture(unsigned b,unsigned p,uint8_t out[16],uint8_t src[8]) {
    if(b>=16 || p>=16) return 0;
    uintptr_t base=0x400e21e0u+b*635712u;
    unsigned part=BYTE(base+p*36568u+0x8e57u);
    if(part>=4) return 0;
    base+=0x8ed80u+part*6322u;
    for(unsigned i=0;i<16;++i) out[i]=BYTE(base+i);
    for(unsigned i=0;i<8;++i) { src[i]=BYTE(base+0x22+i);if(src[i]>4)return 0; }
    return 1;
}
static void requeue(unsigned b,unsigned p) {
    ((void (*)(unsigned,unsigned,unsigned,int,unsigned))0x400a0570u)(b,p,0,-1,0);
}
#else
extern uint8_t dl_pub_memory[];
#define BYTE(a) dl_pub_memory[(a)-0x80006500u]
extern unsigned capture(unsigned,unsigned,uint8_t *,uint8_t *);
extern void requeue(unsigned,unsigned);
#endif
static void hold_current(void) {
#ifndef DL_NATIVE_TEST
    uint16_t sr;
    __asm__ volatile("move.w %%sr,%0\n\tmove.w #0x2700,%%sr" : "=d"(sr) : : "memory","cc");
#endif
    BYTE(0x800065bfu)=BYTE(0x800065bdu);
    BYTE(0x800065c0u)=BYTE(0x800065beu);
#ifndef DL_NATIVE_TEST
    __asm__ volatile("move.w %0,%%sr" : : "d"(sr) : "memory","cc");
#endif
}
static void fail(int why) {
    ++dl_publication_refused;
    dl_modal_pending=why==DL_SELECT_MEMORY ? 2:why==DL_SELECT_PROCESSING ? 3:1;
}
unsigned dl_pattern_boundary(void) {
    uint8_t target[16],source[8];
    unsigned b=BYTE(0x800065bfu),p=BYTE(0x800065c0u);
    if(b>=16 || p>=16) return 1; /* Stock's no-next-pattern sentinel. */
    if(capture(b,p,target,source) && dl_publication_ready(target)) return 1;
    /* Keep the current pattern running. The UI remembers the requested target
     * before replacing the queued pair and requeues it after preparation. */
    missed=0x10000u|(b<<8)|p;
    if(pending && b==bank && p==pattern) deferred=1;
    ++dl_publication_deferred;
    hold_current();return 0;
}
/* Stopped requests publish immediately in stock. Keep their five arguments in
 * a mailbox and replay only after an acknowledged preparation. The writer may
 * be a sequencer callback; it never allocates or reads files. */
#ifndef DL_NATIVE_TEST
static volatile uint32_t immediate_version=0,immediate_args[5]={0},immediate_kind=0,immediate_next=0;
static volatile uint32_t immediate_seen=0,immediate_passthrough=0;
static uint32_t immediate_token=0,immediate_saved[5]={0},immediate_saved_kind=0,immediate_saved_next=0;
volatile uint32_t dl_chain_deferred=0,dl_chain_restarted=0,dl_chain_dropped=0;
volatile uint32_t dl_publication_superseded=0;
static uint32_t next_pair(void) { return (uint32_t)BYTE(0x800065bfu)<<8|BYTE(0x800065c0u); }
static volatile unsigned immediate_pending=0;
static unsigned project_active(void);
extern void dl_pattern_post_body(unsigned,unsigned,unsigned,int,unsigned);
/* Kind 0 replays a pattern request; kind 1 replays a chain restart. */
static void immediate_request(const uint32_t *args,unsigned passthrough,unsigned kind) {
    uint16_t sr;
    __asm__ volatile("move.w %%sr,%0\n\tmove.w #0x2700,%%sr" : "=d"(sr) : : "memory","cc");
    ++immediate_version;
    for(unsigned i=0;i<5;++i)immediate_args[i]=args[i];
    immediate_passthrough=passthrough;immediate_kind=kind;immediate_next=next_pair();
    ++immediate_version;
    __asm__ volatile("move.w %0,%%sr" : : "d"(sr) : "memory","cc");
}
unsigned dl_pattern_request_guard(const uint32_t *args) {
    uint8_t target[16],src[8];
    unsigned pass=*(volatile uint32_t *)0x800065b8u==1 || args[1]==0xffffffffu;
    if(!pass) {
        if(!capture(args[0],args[1],target,src)) { fail(DL_SELECT_UNAVAILABLE);return 0; }
        pass=dl_publication_ready(target);
    }
    if(pass) {
        /* A newer already-resident/queued request supersedes a deferred one;
         * otherwise that old request would unexpectedly replay later. */
        if(immediate_pending || immediate_version!=immediate_seen) immediate_request(args,1,0);
        return 1;
    }
    if(project_active()) { fail(DL_SELECT_UNAVAILABLE);return 0; }
    immediate_request(args,0,0);return 0;
}
/* STOP on a playing chain stores chain[0] as the running pattern (0x400a11c6)
 * BEFORE it requests that pattern, so the request guard is too late for it.
 * Admit the whole restart at 0x400a11ba instead. Refusal stops on the current
 * pattern with the chain untouched; the UI task replays the restart once its
 * Part is prepared. Runs wherever STOP runs; never allocates or waits. */
unsigned dl_chain_stop_guard(void) {
    extern volatile uint32_t dl_residency_enabled;
    uint8_t target[16],src[8];
    uint32_t args[5]={(uint32_t)(int8_t)BYTE(0x800065bdu),(uint32_t)(int8_t)BYTE(0x80006555u),
                      0,0xffffffffu,0};
    if(!dl_residency_enabled) return 1;
    unsigned known=capture(args[0],args[1],target,src);
    if(known && dl_publication_ready(target)) return 1;
    ++dl_chain_deferred;
    if(!known || project_active()) { fail(DL_SELECT_UNAVAILABLE);return 0; }
    immediate_request(args,0,1);return 0;
}
/* The deferred restart is still the latest intent only while the sequencer
 * stays stopped on the same chain. */
static unsigned chain_current(void) {
    return *(volatile uint32_t *)0x800065b8u==0 && *(volatile uint32_t *)0x80006546u &&
           (uint32_t)(int8_t)BYTE(0x800065bdu)==immediate_saved[0] &&
           (uint32_t)(int8_t)BYTE(0x80006555u)==immediate_saved[1];
}
/* Stock 0x400a11ba-0x400a1292, the STOP handler's chain branch without the
 * stop tail that already ran: each statement is one stock store or call. */
static void chain_restart(void) {
    volatile uint32_t *const at=(volatile uint32_t *)0x8000654au;
    *at=0;
    uint32_t first=*(volatile uint32_t *)0x80006552u;
    BYTE(0x800065beu)=(uint8_t)first;
    ((void (*)(int,int))0x400a1030u)((int8_t)BYTE(0x800065bdu),(int8_t)first);
    uint32_t next=*at+1;*at=next;
    BYTE(0x800065c0u)=BYTE(0x80006555u+next*4);
    *(volatile uint32_t *)0x80006630u=0;
    uint32_t o=(uint32_t)(int8_t)BYTE(0x800065c0u)*36568u+(uint32_t)(int8_t)BYTE(0x800065bdu)*635712u;
    *(volatile int32_t *)0x80006634u=BYTE(0x400eb035u+o) ? *(volatile int16_t *)(uintptr_t)(0x400eb030u+o)
                                                         : (int8_t)BYTE(0x400eb033u+o);
    if((int32_t)next>=*(volatile int32_t *)0x8000654eu) *at=0;
    BYTE(0x400d8165u)=BYTE(0x800065beu);
    ((void (*)(uint32_t,uint32_t))0x40000c3cu)(0x460d17aeu,0x400d8164u);
}
static unsigned immediate_tick(void) {
    uint32_t version=immediate_version;
    if(version&1u)return 1;
    if(version!=immediate_seen) {
        if(immediate_pending)dl_selection_cancel(immediate_token);
        /* A replayed request's token may be armed and already published;
         * never let a later capture failure cancel it. */
        immediate_token=0;
        if(pending) { dl_selection_cancel(token);pending=0;missed=0; }
        for(unsigned i=0;i<5;++i)immediate_saved[i]=immediate_args[i];
        immediate_saved_kind=immediate_kind;immediate_saved_next=immediate_next;
        unsigned pass=immediate_passthrough;
        if(version!=immediate_version)return 1;
        immediate_seen=version;immediate_pending=pass ? 0:1;
        if(pass)return 1;
    }
    if(!immediate_pending)return 0;
    if(immediate_saved_kind && !chain_current()) {
        dl_selection_cancel(immediate_token);immediate_pending=0;++dl_chain_dropped;return 1;
    }
    /* A deferral reorders the request after whatever happened meanwhile. A
     * queued pair changed since then (a chain add, a queued change after PLAY)
     * is newer intent: replaying the old request would overwrite it. */
    if(!immediate_saved_kind && next_pair()!=immediate_saved_next) {
        dl_selection_cancel(immediate_token);immediate_pending=0;++dl_publication_superseded;return 1;
    }
    uint8_t target[16],src[8];
    if(!capture(immediate_saved[0],immediate_saved[1],target,src)) {
        dl_selection_cancel(immediate_token);immediate_pending=0;fail(DL_SELECT_UNAVAILABLE);return 1;
    }
    if(immediate_pending==1) {
        extern int dl_publication_idle(void);
        if(!dl_publication_idle())return 1;
        if(++serial==0)serial=0x40000001u;
        immediate_token=serial;
        for(unsigned i=0;i<16;++i)ids[i]=target[i];
        for(unsigned i=0;i<8;++i)sources[i]=src[i];
        int r=dl_publication_prepare(ids,sources,immediate_token);
        if(r<0) { immediate_pending=0;fail(r);return 1; }
        immediate_pending=2;
    }
    unsigned equal=1;
    for(unsigned i=0;i<16;++i)if(ids[i]!=target[i])equal=0;
    for(unsigned i=0;i<8;++i)if(sources[i]!=src[i])equal=0;
    if(!equal) { dl_selection_cancel(immediate_token);immediate_pending=1;return 1; }
    int r=dl_publication_poll(immediate_token);
    if(r==DL_SELECT_WAIT)return 1;
    if(r!=DL_SELECT_READY) {
        dl_selection_cancel(immediate_token);immediate_pending=0;fail(r);return 1;
    }
    if(version!=immediate_version)return 1;
    dl_publication_arm(immediate_token);++dl_publication_prepared;
    /* Clear first: a chain restart re-enters the request guard, which must
     * see no pending request to supersede. */
    immediate_pending=0;
    if(immediate_saved_kind) { ++dl_chain_restarted;chain_restart();return 1; }
    dl_pattern_post_body(immediate_saved[0],immediate_saved[1],immediate_saved[2],
                         (int)immediate_saved[3],immediate_saved[4]);
    return 1;
}
#endif
#ifndef DL_NATIVE_TEST
static unsigned project_tick(void);
#endif
void dl_publication_tick(void) {
#ifndef DL_NATIVE_TEST
    if(project_tick() || immediate_tick()) return;
#endif
    unsigned b=BYTE(0x800065bfu),p=BYTE(0x800065c0u);
    unsigned live_b=BYTE(0x800065bdu),live_p=BYTE(0x800065beu);
    if(pending) {
        if(!((b==bank && p==pattern) || (deferred && b==live_b && p==live_p))) {
            dl_selection_cancel(token);pending=0;return;
        }
        uint8_t now[16]={0},src[8]={0};unsigned equal=capture(bank,pattern,now,src);
        for(unsigned i=0;i<16;++i) if(now[i]!=ids[i]) equal=0;
        for(unsigned i=0;i<8;++i) if(src[i]!=sources[i]) equal=0;
        if(!equal) { dl_selection_cancel(token);pending=0;return; }
        if(pending==2) { if(live_b==bank && live_p==pattern) pending=0;return; }
        int r=dl_publication_poll(token);
        if(r==DL_SELECT_WAIT) return;
        if(r!=DL_SELECT_READY) {
            dl_selection_cancel(token);fail(r);hold_current();missed=0;pending=0;return;
        }
        dl_publication_arm(token);++dl_publication_prepared;pending=2;
        if(deferred) { missed=0;requeue(bank,pattern); }
        return;
    }
    unsigned retry=0;
    if(missed && b==live_b && p==live_p) { b=(missed>>8)&255;p=missed&255;retry=1; }
    else if(missed) missed=0;
    if(b>=16 || p>=16 || (b==live_b && p==live_p)) return;
    if(!capture(b,p,ids,sources)) { fail(DL_SELECT_UNAVAILABLE);hold_current();missed=0;return; }
    bank=b;pattern=p;deferred=retry;
    if(++serial==0) serial=0x40000001u;
    token=serial;
    int r=dl_publication_prepare(ids,sources,token);
    if(r==DL_SELECT_UNAVAILABLE && !dl_publication_idle()) return; /* Busy: retry. */
    if(r<0) { fail(r);hold_current();missed=0;return; }
    missed=0;pending=1;
}

/* A LOAD PROJECT request is deferred before its command is posted. File reads
 * and allocation run on the UI task, never from a sequencer interrupt. */
#ifndef DL_NATIVE_TEST
static volatile unsigned project_pending=0,project_authorized=0,project_done=0;
static uint32_t project_token=0;
static volatile int project_result=0;
static char project_name[256]={0},project_path[260]={0};
static struct dl_project_target project_target={0};
volatile uint32_t dl_project_admitted=0,dl_project_refused=0,dl_project_completed=0;
extern unsigned dl_project_post_body(const char *);
extern int dl_publication_idle(void);
static unsigned copy_name(char *to,const char *from,unsigned cap) {
    for(unsigned i=0;i<cap;++i) { char c=from[i];to[i]=c;if(!c)return i>0; }
    return 0;
}
unsigned dl_project_guard(const char *name) {
    /* The engine callback can finish before the next UI tick. Complete its
     * admission before accepting the next user request. This entry is UI-only. */
    dl_publication_finish();
    if(!name || project_pending) return 0;
    if(!copy_name(project_name,name,sizeof project_name)) { fail(DL_SELECT_UNAVAILABLE);return 0; }
    const char *path=((const char *(*)(unsigned,const char *))0x40025230u)(0,name);
    if(!copy_name(project_path,path,sizeof project_path)) { fail(DL_SELECT_UNAVAILABLE);return 0; }
    project_done=0;project_authorized=0;
    __asm__ volatile("" ::: "memory");project_pending=1;
    return 1;
}
unsigned dl_project_engine_guard(const uint8_t *message) {
    if(!project_authorized) { ++dl_project_refused;fail(DL_SELECT_UNAVAILABLE);return 0; }
    for(unsigned i=0;i<sizeof project_name;++i) {
        if(message[i+1]!=(uint8_t)project_name[i]) { ++dl_project_refused;fail(DL_SELECT_UNAVAILABLE);return 0; }
        if(!project_name[i]) return 1;
    }
    return 0;
}
void dl_project_finished(int result) { project_result=result;project_done=1; }
void dl_publication_finish(void) {
    if(project_pending==4 && project_done) project_tick();
}
static unsigned project_active(void) { return project_pending && !(project_pending==4 && project_done); }
static unsigned project_tick(void) {
    if(!project_pending) return 0;
    if(pending) { dl_selection_cancel(token);pending=0;missed=0; }
    if(immediate_pending) {
        dl_selection_cancel(immediate_token);immediate_pending=0;immediate_seen=immediate_version;
    }
    if(project_pending==1) {
        dl_selection_cancel(immediate_token);
        dl_selection_cancel(token);
        if(!dl_project_metadata(project_path,&project_target)) {
            ++dl_project_refused;fail(DL_SELECT_UNAVAILABLE);project_pending=0;return 1;
        }
        project_pending=2;
    }
    if(project_pending==2) {
        if(!dl_publication_idle()) return 1;
        if(++serial==0) serial=0x40000001u;
        project_token=serial;
        int r=dl_publication_prepare(project_target.ids,project_target.source,project_token);
        if(r<0) { ++dl_project_refused;fail(r);project_pending=0;return 1; }
        project_pending=3;
    }
    if(project_pending==3) {
        int r=dl_publication_poll(project_token);
        if(r==DL_SELECT_WAIT) return 1;
        if(r!=DL_SELECT_READY) {
            dl_selection_cancel(project_token);++dl_project_refused;fail(r);project_pending=0;return 1;
        }
        project_authorized=1;project_pending=4;++dl_project_admitted;
        if(!dl_project_post_body(project_name)) {
            project_authorized=0;dl_selection_cancel(project_token);project_pending=0;fail(DL_SELECT_UNAVAILABLE);
        }
        return 1;
    }
    if(project_pending==4 && project_done) {
        const volatile uint8_t *live=(const volatile uint8_t *)0x80000ec4u;
        unsigned equal=1;for(unsigned i=0;i<16;++i) if(live[i]!=project_target.ids[i]) equal=0;
        if(equal && project_result>0) { dl_selection_commit(project_token);++dl_project_completed; }
        else {
            /* A partial stock load can already use either set. Retain both;
             * cancelling here could unbind code that the failed load selected. */
            project_authorized=0;project_pending=5;fail(DL_SELECT_UNAVAILABLE);return 1;
        }
        project_authorized=0;project_pending=0;
    }
    return 1;
}
#endif
