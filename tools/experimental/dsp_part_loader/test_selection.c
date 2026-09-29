/* Unit test of the actual firmware guard, including asynchronous cancellation.
 * The backend and stock setter are test doubles, not a DSP loading proof. */
#include <assert.h>
#include <string.h>
#include "selection.h"
#include "transfer.h"
static struct dl_selection context;
static int prepare_result=DL_SELECT_READY, poll_result=DL_SELECT_WAIT;
static unsigned calls,applied,cancelled,committed;
static uint32_t latest;
volatile uint32_t dl_modal_pending;
unsigned dl_selection_capture(unsigned slot,unsigned row,struct dl_selection *out) {
    *out=context; out->slot=slot; if(slot==2) out->row=row; return 1;
}
int dl_selection_prepare(const struct dl_selection *request,uint32_t t) {
    assert(t && t!=latest); latest=t; ++calls;
    assert(!memcmp(request->before,context.before,16));
    assert(!memcmp(request->target,context.target,16));
    return prepare_result;
}
int dl_selection_poll(uint32_t t) { assert(t==latest); return poll_result; }
void dl_selection_commit(uint32_t t) { assert(t==latest); ++committed; }
void dl_selection_cancel(uint32_t t) { assert(t==latest); ++cancelled; }
void dl_selection_apply(unsigned slot,unsigned row) {
    assert((slot==2 ? dl_selection_part_guard(row) : dl_selection_guard(slot))==1); ++applied;
    memcpy(context.before,context.target,16);
    if(slot==2) context.part=row;
    dl_selection_applied();
}
int main(void) {
    context.bank=1; context.track=0;
    assert(dl_selection_guard(0)==1 && calls==0); /* unchanged */
    context.target[0]=4;
    prepare_result=DL_SELECT_MEMORY;
    assert(dl_selection_guard(0)==0 && context.before[0]==0 && dl_modal_pending==2);
    prepare_result=DL_SELECT_PROCESSING;
    assert(dl_selection_guard(0)==0 && context.before[0]==0 && dl_modal_pending==3);
    prepare_result=DL_SELECT_READY;
    assert(dl_selection_guard(0)==1 && context.before[0]==0);
    assert(committed==0); dl_selection_applied(); assert(committed==1);
    /* A guard grants permission; only the original setter performs writes. */
    prepare_result=DL_SELECT_WAIT;
    assert(dl_selection_guard(0)==0);
    unsigned n=calls;
    assert(dl_selection_guard(0)==0 && calls==n); /* duplicate request */
    dl_selection_tick(); assert(applied==0 && context.before[0]==0);
    poll_result=DL_SELECT_READY; dl_selection_tick();
    assert(applied==1 && context.before[0]==4);
    context.target[0]=12; assert(dl_selection_guard(0)==0);
    ++context.part; dl_selection_tick(); assert(applied==1); /* never replay into another Part */
    assert(dl_selection_cancelled==1);
    assert(dl_selection_guard(0)==0);
    ++context.row; dl_selection_tick(); assert(applied==1);
    assert(dl_selection_cancelled==2);
    assert(dl_selection_guard(0)==0);
    context.before[7]=16; dl_selection_tick(); assert(applied==1); /* other-track change */
    assert(dl_selection_cancelled==3);
    context.track=4; context.target[12]=12;
    assert(dl_selection_guard(1)==0);
    poll_result=DL_SELECT_MEMORY; dl_selection_tick();
    assert(dl_modal_pending==2 && applied==1 && context.before[12]==0);
    assert(cancelled==6 && dl_selection_refused==3);
    /* Manual Part selection uses the same transaction, before pattern linkage. */
    prepare_result=DL_SELECT_WAIT; poll_result=DL_SELECT_READY;
    context.part=0;
    assert(dl_selection_part_guard(1)==0 && context.part==0);
    dl_selection_tick(); assert(context.part==1 && applied==2);
    assert(dl_selection_part_guard(2)==0);
    ++context.pattern; dl_selection_tick(); assert(context.part==1 && applied==2);
    return 0;
}
