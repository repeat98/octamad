/* Original fixed-point bass drum models. No firmware or recorded samples. */
#ifndef AB_ENGINE_H
#define AB_ENGINE_H
#include <stdint.h>
enum { AB_RATE = 44100, AB_PARAMS = 12 };
/* SRC: PITCH DECAY TONE/TUNE ATTACK SWEEP/TDEP unused; SETUP: MODEL ACCENT ... */
typedef struct {
    int32_t low, band, env, pitch, tone, dc, click;
    uint32_t phase, noise, age, noise_clock;
    int32_t previous, band_remainder, env_remainder;
    int32_t pitch_remainder, click_remainder, tone_remainder, dc_remainder;
    int32_t low_remainder, step_remainder;
    int32_t shaper, shaper_remainder;
    int32_t click_rise, click_edge, noise_lp;
    int32_t rise_remainder, edge_remainder, noise_remainder;
    int32_t output_lp, output_remainder;
    unsigned model, active, pulse, quiet;
} AbVoice;
unsigned ab_lpf_frequency(unsigned value);
extern const uint8_t ab_defaults[AB_PARAMS];
void ab_reset(AbVoice *v);
void ab_trigger(AbVoice *v, const uint8_t p[AB_PARAMS]);
int32_t ab_sample(AbVoice *v, const uint8_t p[AB_PARAMS]);
#endif
