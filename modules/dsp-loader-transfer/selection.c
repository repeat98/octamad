/* Guard stock FX selectors BEFORE their Part/shadow/live writes. No new UI.
 * Backend calls run only on the UI task. A pending request is replayed only
 * while its complete original selection context still matches. */
#include "selection.h"
#include "transfer.h"
#include <stddef.h>
volatile uint32_t dl_selection_requested, dl_selection_completed;
volatile uint32_t dl_selection_cancelled, dl_selection_refused;
static struct dl_selection queued;
static uint32_t serial, token, applying;
static unsigned pending, replay;
#ifdef DL_NATIVE_TEST
extern unsigned dl_selection_capture(unsigned,unsigned,struct dl_selection *);
extern void dl_selection_apply(unsigned,unsigned);
#else
static unsigned dl_selection_capture(unsigned slot,unsigned row,struct dl_selection *s) {
    volatile uint8_t *part;
    uint32_t descriptor;
    s->bank=*(volatile uint32_t *)0x46c82456u;
    s->bank_index=*(volatile uint8_t *)0x80000002u;
    s->pattern=*(volatile uint8_t *)0x80000004u;
    s->part=*(volatile uint8_t *)0x80000003u;
    s->track=*(volatile uint8_t *)0x80000000u;
    s->slot=slot;
    s->row=slot==2 ? row : *(volatile uint32_t *)(slot ? 0x460d5ca8u : 0x460d5c94u);
    if(slot>2 || s->part>3 || s->track>7 || s->row>=32 || !s->bank) return 0;
    part=(volatile uint8_t *)(uintptr_t)(s->bank+0x8ed80u+s->part*6322u);
    for(unsigned i=0;i<16;++i) s->target[i]=s->before[i]=part[i];
    for(unsigned i=0;i<8;++i) s->target_source[i]=s->before_source[i]=part[0x22+i];
    if(slot==2) {
        if(row>3) return 0;
        part=(volatile uint8_t *)(uintptr_t)(s->bank+0x8ed80u+row*6322u);
        for(unsigned i=0;i<16;++i) s->target[i]=part[i];
        for(unsigned i=0;i<8;++i) s->target_source[i]=part[0x22+i];
    } else {
        descriptor=((volatile uint32_t *)(slot ? 0x400d6090u : 0x400d6060u))[s->row];
        if(!descriptor) return 0;
        uint32_t id=*(volatile uint32_t *)(uintptr_t)descriptor;
        if(id>31) return 0;
        s->target[slot*8+s->track]=(uint8_t)id;
    }
    return 1;
}
static void dl_selection_apply(unsigned slot,unsigned row) {
    if(slot==2) { ((void (*)(unsigned))0x4004a8a4u)(row); return; }
    ((void (*)(void))(slot ? 0x40052474u : 0x400526e4u))();
}
#endif
static unsigned same(const struct dl_selection *a,const struct dl_selection *b) {
    if(a->bank!=b->bank || a->bank_index!=b->bank_index || a->pattern!=b->pattern ||
       a->part!=b->part || a->track!=b->track ||
       a->slot!=b->slot || a->row!=b->row) return 0;
    for(unsigned i=0;i<16;++i)
        if(a->before[i]!=b->before[i] || a->target[i]!=b->target[i]) return 0;
    for(unsigned i=0;i<8;++i)
        if(a->before_source[i]!=b->before_source[i] || a->target_source[i]!=b->target_source[i]) return 0;
    return 1;
}
static void refusal(int reason) {
    ++dl_selection_refused;
    dl_modal_pending=reason==DL_SELECT_MEMORY ? 2 :
                     reason==DL_SELECT_PROCESSING ? 3 : 1;
}
static void cancel(void) {
    dl_selection_cancel(token); pending=0; ++dl_selection_cancelled;
}
static unsigned guard(unsigned slot,unsigned row) {
    struct dl_selection request;
    if(!dl_selection_capture(slot,row,&request)) {
        refusal(DL_SELECT_UNAVAILABLE); return 0;
    }
    if(replay) {
        if(!same(&queued,&request)) return 0;
        applying=token; return 1;
    }
    if(pending) {
        if(same(&queued,&request)) return 0;
        cancel();
    }
    if(slot==2) { if(request.row==request.part) return 1; }
    else if(request.before[slot*8+request.track]==request.target[slot*8+request.track]) return 1;
    if(++serial==0) ++serial;
    token=serial;
    ++dl_selection_requested;
    int result=dl_selection_prepare(&request,token);
    if(result==DL_SELECT_READY) { applying=token; return 1; }
    if(result!=DL_SELECT_WAIT) {
        dl_selection_cancel(token); refusal(result); return 0;
    }
    /* Volatile byte stores keep the freestanding compiler from introducing a
     * libc memcpy when the request structure grows. */
    for(unsigned i=0;i<sizeof queued;++i)
        ((volatile uint8_t *)&queued)[i]=((const uint8_t *)&request)[i];
    pending=1;
    return 0;
}
unsigned dl_selection_guard(unsigned slot) { return guard(slot,0); }
unsigned dl_selection_part_guard(unsigned part) { return guard(2,part); }
void dl_selection_applied(void) {
    if(applying) {
        dl_selection_commit(applying); applying=0; ++dl_selection_completed;
    }
}
void dl_selection_tick(void) {
    struct dl_selection current;
    if(!pending) return;
    if(!dl_selection_capture(queued.slot,queued.row,&current) || !same(&queued,&current)) {
        cancel(); return;
    }
    int result=dl_selection_poll(token);
    if(result==DL_SELECT_WAIT) return;
    if(result!=DL_SELECT_READY) { cancel(); refusal(result); return; }
    /* Re-enter the real stock setter, including its normal dirty bits, defaults
     * and live publication. The entry guard checks context again during replay. */
    replay=1; dl_selection_apply(queued.slot,queued.row); replay=0;
    pending=0;
}
