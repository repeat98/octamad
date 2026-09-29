/* Shared source descriptor defaults and LPF display mapping. */
#ifndef AB_ENGINE_H
#define AB_ENGINE_H
#include <stdint.h>
enum { AB_PARAMS = 12 };
unsigned ab_lpf_frequency(unsigned value);
extern const uint8_t ab_defaults[AB_PARAMS];
#endif
