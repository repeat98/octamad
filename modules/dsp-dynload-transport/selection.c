/* Guard stock FX selectors BEFORE their Part/shadow/live writes. No new UI.
 * Backend calls run only on the UI task. A pending request is replayed only
 * while its complete original selection context still matches. */
#include "selection.h"
#include "transfer.h"
#include <stddef.h>
volatile uint32_t dl_selection_requested=0, dl_selection_completed=0;
volatile uint32_t dl_selection_cancelled=0, dl_selection_refused=0;
static struct dl_selection queued={0};
/* A deferred PASTE replays from this copy: the caller consumes the clipboard
 * as soon as the stock routine returns. */
static uint8_t paste[6322]={0};
static uint32_t serial=0, token=0, applying=0;
static unsigned pending=0, replay=0;
#ifdef DL_NATIVE_TEST
extern unsigned dl_selection_capture(unsigned,unsigned,uintptr_t,struct dl_selection *);
extern void dl_selection_apply(unsigned,unsigned,uintptr_t);
#else
static unsigned dl_selection_capture(unsigned slot,unsigned row,uintptr_t source,struct dl_selection *s) {
    volatile uint8_t *part;
    uint32_t descriptor;
    s->bank=*(volatile uint32_t *)0x46c82456u;
    s->bank_index=*(volatile uint8_t *)0x80000002u;
    s->pattern=*(volatile uint8_t *)0x80000004u;
    s->part=*(volatile uint8_t *)0x80000003u;
    s->track=*(volatile uint8_t *)0x80000000u;
    s->slot=slot; s->source=source;
    s->row=slot>=2 ? row : *(volatile uint32_t *)(slot ? 0x460d5ca8u : 0x460d5c94u);
    if(slot>DL_PART_RESET || s->part>3 || s->track>7 || s->row>=32 || !s->bank) return 0;
    if(slot>=2 && row>3) return 0;
    /* Before: the Part being edited (a Part routine's own), else the active Part. */
    part=(volatile uint8_t *)(uintptr_t)(s->bank+0x8ed80u+(slot>2 ? row : s->part)*6322u);
    for(unsigned i=0;i<16;++i) s->target[i]=s->before[i]=part[i];
    for(unsigned i=0;i<8;++i) s->target_source[i]=s->before_source[i]=part[0x22+i];
    if(slot==2 || slot==DL_PART_PASTE ||
       (slot==DL_PART_RELOAD && *(volatile uint8_t *)(uintptr_t)(s->bank+0x9b312u+row))) {
        /* The target Part, the pasted image, or the saved copy stock reloads
         * (0x4004aab4 changes nothing while its saved-valid flag is clear). */
        if(slot==DL_PART_PASTE && !source) return 0;
        part=(volatile uint8_t *)(slot==DL_PART_PASTE ? source :
              (uintptr_t)(s->bank+(slot==2 ? 0x8ed80u : 0x9504au)+row*6322u));
        for(unsigned i=0;i<16;++i) s->target[i]=part[i];
        for(unsigned i=0;i<8;++i) s->target_source[i]=part[0x22+i];
    } else if(slot==DL_PART_RESET) {
        /* Stock's Part initialiser (0x40005638) sets every FX1 and FX2 slot
         * from these two bytes and each track's source to 0. */
        for(unsigned i=0;i<16;++i)
            s->target[i]=*(volatile uint8_t *)(i<8 ? 0x400d47adu : 0x400d4ad1u);
        for(unsigned i=0;i<8;++i) s->target_source[i]=0;
    } else if(slot<2) {
        descriptor=((volatile uint32_t *)(slot ? 0x400d6090u : 0x400d6060u))[s->row];
        if(!descriptor) return 0;
        uint32_t id=*(volatile uint32_t *)(uintptr_t)descriptor;
        if(id>31) return 0;
        s->target[slot*8+s->track]=(uint8_t)id;
    }
    return 1;
}
static void dl_selection_apply(unsigned slot,unsigned row,uintptr_t source) {
    if(slot==2) { ((void (*)(unsigned))0x4004a8a4u)(row); return; }
    if(slot==DL_PART_PASTE) { ((void (*)(uintptr_t,unsigned))0x40029a4cu)(source,row); return; }
    if(slot==DL_PART_RELOAD) { ((unsigned (*)(unsigned))0x4004aab4u)(row); return; }
    if(slot==DL_PART_RESET) { ((void (*)(unsigned))0x4004a9d0u)(row); return; }
    ((void (*)(void))(slot ? 0x40052474u : 0x400526e4u))();
}
#endif
static unsigned same(const struct dl_selection *a,const struct dl_selection *b) {
    if(a->bank!=b->bank || a->bank_index!=b->bank_index || a->pattern!=b->pattern ||
       a->part!=b->part || a->track!=b->track ||
       a->slot!=b->slot || a->row!=b->row || a->source!=b->source) return 0;
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
static unsigned guard(unsigned slot,unsigned row,uintptr_t source) {
    struct dl_selection request;
    if(!dl_selection_capture(slot,row,source,&request)) {
        refusal(DL_SELECT_UNAVAILABLE); return 0;
    }
    if(replay) {
        if(!same(&queued,&request)) return 0;
        applying=token; return 1;
    }
    if(pending) {
        /* A paste of the same image matches its snapshot's target, not its
         * pointer: compare it as the replay would see it. */
        if(slot==DL_PART_PASTE) request.source=(uintptr_t)paste;
        if(same(&queued,&request)) return 2;
        request.source=source;
        cancel();
    }
    if(slot==2) { if(request.row==request.part) return 1; }
    else if(slot>2) {
        /* An inactive Part only changes data; the pattern guards capture it
         * again before any later publication. */
        if(request.row!=request.part) return 1;
        unsigned change=0;
        for(unsigned i=0;i<16;++i) change|=request.before[i]!=request.target[i];
        for(unsigned i=0;i<8;++i) change|=request.before_source[i]!=request.target_source[i];
        if(!change) return 1;
    }
    else if(request.before[slot*8+request.track]==request.target[slot*8+request.track]) return 1;
    if(++serial==0) ++serial;
    token=serial;
    ++dl_selection_requested;
    int result=dl_selection_prepare(&request,token);
    if(result==DL_SELECT_READY) { applying=token; return 1; }
    if(result!=DL_SELECT_WAIT) {
        dl_selection_cancel(token); refusal(result); return 0;
    }
    if(slot==DL_PART_PASTE) {
        for(unsigned i=0;i<sizeof paste;++i)
            ((volatile uint8_t *)paste)[i]=((const volatile uint8_t *)source)[i];
        request.source=(uintptr_t)paste;
    }
    /* Volatile byte stores keep the freestanding compiler from introducing a
     * libc memcpy when the request structure grows. */
    for(unsigned i=0;i<sizeof queued;++i)
        ((volatile uint8_t *)&queued)[i]=((const uint8_t *)&request)[i];
    pending=1;
    return 2;
}
unsigned dl_selection_guard(unsigned slot) { return guard(slot,0,0)==1; }
unsigned dl_selection_part_guard(unsigned part) { return guard(2,part,0)==1; }
unsigned dl_selection_part_edit_guard(unsigned kind,unsigned part,uintptr_t source) {
    return kind>=DL_PART_PASTE && kind<=DL_PART_RESET ? guard(kind,part,source) : 0;
}
void dl_selection_applied(void) {
    if(applying) {
        dl_selection_commit(applying); applying=0; ++dl_selection_completed;
    }
}
void dl_selection_tick(void) {
    struct dl_selection current;
    if(!pending) return;
    if(!dl_selection_capture(queued.slot,queued.row,queued.source,&current) || !same(&queued,&current)) {
        cancel(); return;
    }
    int result=dl_selection_poll(token);
    if(result==DL_SELECT_WAIT) return;
    if(result!=DL_SELECT_READY) { cancel(); refusal(result); return; }
    /* Re-enter the real stock setter, including its normal dirty bits, defaults
     * and live publication. The entry guard checks context again during replay. */
    replay=1; dl_selection_apply(queued.slot,queued.row,queued.source); replay=0;
    pending=0;
}
