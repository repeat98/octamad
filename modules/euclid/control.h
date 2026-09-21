/* Euclid's integer control engine. Clock units are the firmware's own:
 * one quarter note = 63,504,000, independent of BPM. */
#ifndef EUCLID_CONTROL_H
#define EUCLID_CONTROL_H
#include <stdint.h>
#define EU_QUANTUM 1323000u
#define EU_MAX 32767u
#define EU_ID 0x1du

typedef struct {
    uint32_t now, quantum, remainder, epoch, initialized;
} EuClock;

typedef struct {
    /* age uses quarter-clock units; next and period use EU_QUANTUM. */
    uint32_t epoch, next, period, age, rng, triggers;
    uint16_t values[64];
    uint16_t level, origin, target;
    uint8_t initialized, mode, active;
    uint16_t reserved;
} EuState;

typedef struct {
    uint16_t freq, depth;  /* unsigned Q15, depth centered at 16384 */
    uint8_t steps, pulses, rotate, rate, attack, decay, mode;
    uint8_t scale, length, swing;
    uint16_t reserved;
    uint32_t mask_lo, mask_hi;
} EuParams;

void eu_clock_start(EuClock *c, uint32_t now);
void eu_clock_update(EuClock *c, uint32_t now);
uint32_t eu_random(uint32_t *state);
unsigned eu_pulse(unsigned index, unsigned steps, unsigned pulses);
uint16_t eu_process(EuState *s, const EuClock *c, const EuParams *p,
                    uint32_t elapsed, unsigned running, unsigned identity);
#endif
