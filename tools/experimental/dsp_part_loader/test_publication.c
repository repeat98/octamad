#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "publication.h"
#include "selection.h"
uint8_t dl_pub_memory[256];
volatile uint32_t dl_modal_pending;
extern volatile uint32_t dl_publication_prepared,dl_publication_refused,dl_publication_deferred;
static uint8_t parts[16][16];
static int reply=DL_SELECT_WAIT,ready,prepare_reply=DL_SELECT_WAIT;
static unsigned prepared,cancelled,armed,requeued;
unsigned capture(unsigned b,unsigned p,uint8_t *ids,uint8_t *src) {
    if(b || p>=16)return 0;
    memcpy(ids,parts[p],16);memset(src,1,8);return 1;
}
int dl_publication_idle(void) { return 1; }
void requeue(unsigned b,unsigned p) { ++requeued;dl_pub_memory[0xbf]=b;dl_pub_memory[0xc0]=p; }
int dl_publication_ready(const uint8_t *ids) { (void)ids;return ready; }
int dl_publication_prepare(const uint8_t *ids,const uint8_t *src,uint32_t token) {
    (void)ids;(void)src;assert(token);++prepared;return prepare_reply;
}
int dl_publication_poll(uint32_t token) { assert(token);return reply; }
void dl_publication_arm(uint32_t token) { assert(token);++armed; }
void dl_selection_cancel(uint32_t token) { assert(token);++cancelled; }
int main(void) {
    dl_pub_memory[0xc0]=1;parts[1][0]=12;
    dl_publication_tick();assert(prepared==1);
    assert(!dl_pattern_boundary());assert(dl_pub_memory[0xc0]==0 && dl_publication_deferred==1);
    dl_publication_tick();assert(!armed && !requeued);
    reply=DL_SELECT_READY;dl_publication_tick();assert(armed==1 && requeued==1);
    ready=1;assert(dl_pattern_boundary());dl_pub_memory[0xbe]=1;
    dl_publication_tick();dl_publication_tick();assert(prepared==1); /* No stale missed replay. */
    ready=0;reply=DL_SELECT_MEMORY;dl_pub_memory[0xc0]=2;
    dl_publication_tick();dl_publication_tick();
    assert(dl_publication_refused==1 && dl_modal_pending==2 && dl_pub_memory[0xc0]==1);
    assert(cancelled==1);
    reply=DL_SELECT_WAIT;dl_pub_memory[0xc0]=3;dl_publication_tick();
    parts[3][1]=28;dl_publication_tick();assert(cancelled==2 && armed==1);
    /* ISR reaches the boundary before the UI ever observes this request. */
    dl_pub_memory[0xc0]=4;assert(!dl_pattern_boundary());
    dl_publication_tick();reply=DL_SELECT_READY;dl_publication_tick();
    assert(requeued==2 && dl_pub_memory[0xc0]==4);
    ready=1;assert(dl_pattern_boundary());dl_pub_memory[0xbe]=4;dl_publication_tick();
    dl_pub_memory[0xc0]=5;ready=0;reply=DL_SELECT_WAIT;dl_publication_tick();
    dl_pub_memory[0xc0]=6;dl_publication_tick();assert(cancelled==3);
    prepare_reply=DL_SELECT_UNAVAILABLE;dl_pub_memory[0xc0]=7;
    assert(!dl_pattern_boundary());dl_publication_tick();
    unsigned attempts=prepared;dl_publication_tick();assert(prepared==attempts);
    assert(dl_publication_refused==2);
    puts("PASS: pre-publication deadline, deferred replay, capacity refusal and stale-context cancellation");
}
