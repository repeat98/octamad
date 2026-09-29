#ifndef DL_SELECTION_H
#define DL_SELECTION_H
#include <stdint.h>
enum { DL_SELECT_READY=1, DL_SELECT_WAIT=0, DL_SELECT_MEMORY=-1,
       DL_SELECT_PROCESSING=-2, DL_SELECT_UNAVAILABLE=-3 };
struct dl_selection {
    uint32_t bank, bank_index, pattern, part, track, slot, row;
    uint8_t before[16], target[16];
    uint8_t before_source[8], target_source[8];
};
/* Backend receives the entire target effect set, not just the changed id.
 * READY means code, state and dispatch are prepared on all affected cores.
 * WAIT must not mutate the current Part. Cancel invalidates the token.
 * Commit is notified only after the original stock setter returns; this is
 * not a DSP frame-boundary activation or a retirement acknowledgement.
 * This is a firmware interface; the diagnostic probe has no dynamic backend. */
int dl_selection_prepare(const struct dl_selection *, uint32_t token);
int dl_selection_poll(uint32_t token);
void dl_selection_cancel(uint32_t token);
void dl_selection_commit(uint32_t token);
void dl_selection_applied(void);
unsigned dl_selection_guard(unsigned slot);
unsigned dl_selection_part_guard(unsigned part);
void dl_selection_tick(void);
extern volatile uint32_t dl_selection_requested, dl_selection_completed;
extern volatile uint32_t dl_selection_cancelled, dl_selection_refused;
#endif
