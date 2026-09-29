/* Diagnostic backend for the isolated transfer remix ONLY.
 * Its selectable stock effects are resident already. This does not allocate,
 * unload, or declare new algorithms ready. dl_probe_selection_result lets the
 * emulator gate exercise refusal/pending paths before a dynamic backend lands.
 * Never use this adapter for a remix containing nonresident effects. */
#include "selection.h"
volatile int32_t dl_probe_selection_result=DL_SELECT_READY;
static uint32_t current=0;
static const uint32_t resident=(1u<<0)|(1u<<4)|(1u<<5)|(1u<<8)|(1u<<12)|
    (1u<<13)|(1u<<16)|(1u<<17)|(1u<<18)|(1u<<19)|(1u<<24)|(1u<<28);
int dl_selection_prepare(const struct dl_selection *s,uint32_t token) {
    for(unsigned i=0;i<16;++i)
        if(s->target[i]>31 || !(resident & (1u<<s->target[i])))
            return DL_SELECT_UNAVAILABLE;
    for(unsigned i=0;i<8;++i)
        if(s->target_source[i]>4) return DL_SELECT_UNAVAILABLE;
    current=token;
    return dl_probe_selection_result;
}
int dl_selection_poll(uint32_t token) {
    return token==current ? dl_probe_selection_result : DL_SELECT_UNAVAILABLE;
}
void dl_selection_cancel(uint32_t token) { if(token==current) current=0; }

void dl_selection_commit(uint32_t token) { if(token==current) current=0; }

void dl_residency_tick(void) {}
