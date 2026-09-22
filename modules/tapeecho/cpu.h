#ifndef OCTABAM_TAPE_CPU_H
#define OCTABAM_TAPE_CPU_H
#include <stdint.h>
#define TE_FRAMES 16u
#define TE_RING 176400u
#define TE_STRIDE 1411328u
#define TE_FADE 512u
typedef struct {
    uint32_t active, valid, position, tempo, phase, rng;
    int32_t mix, feedback, age, wow, hiss;
    int32_t filters[3][5], coefficients[1][5];
    uint32_t flutter, flutter_rate, flutter_target;
    int32_t wobble, wobble_step;
    uint32_t fade_from, fade_left, mode;
    uint32_t cached_position, cached_age, cached_speed, cached_index, filter_pending;
    int32_t filter_targets[1][5];
    uint32_t control_clock;
} TapeState;
typedef struct {
    uint32_t time, feedback, wow, sync, mix, age, tempo;
    uint32_t lane; /* track index: stagger slow tone work across instances */
} TapeParams;
void te_process(TapeState *, const TapeParams *, volatile int32_t *ring,
                uint32_t write, int32_t *audio, int32_t *record);
uint32_t te_target(const TapeParams *, uint32_t tempo);
extern TapeState te_states[8];
/* Returns nonzero only when the stock track loop must skip its DSP-era mix. */
unsigned te_cpu_frame(uint32_t *stock_stack);
#endif
