/* Original Euclidean rhythm / envelope engine. No floating point, allocation,
 * runtime library calls, or private copy of the tempo clock. Compile to the
 * checked-in ColdFire assembly with generate_control.py. */
#include "control.h"
_Static_assert(sizeof(EuClock) == 20, "hooks.s clock allocation");
_Static_assert(sizeof(EuState) == 164, "hooks.s instance allocation");

static uint32_t min_u(uint32_t a, uint32_t b) { return a < b ? a : b; }

void eu_clock_start(EuClock *c, uint32_t now) {
    c->now = now;
    c->quantum = c->remainder = 0;
    ++c->epoch;
    c->initialized = 1;
}

void eu_clock_update(EuClock *c, uint32_t now) {
    if (!c->initialized) { eu_clock_start(c, now); return; }
    /* Signed subtraction tolerates the 32-bit clock wrapping (~34 s at
     * 120 BPM), and the small backwards corrections of external clock. */
    int32_t delta = (int32_t)(now - c->now);
    c->now = now;
    int32_t rem = (int32_t)c->remainder + delta;
    while (rem < 0) { --c->quantum; rem += EU_QUANTUM; }
    while (rem >= (int32_t)EU_QUANTUM) { ++c->quantum; rem -= EU_QUANTUM; }
    c->remainder = (uint32_t)rem;
}

uint32_t eu_random(uint32_t *state) {
    uint32_t x = *state;
    x ^= x << 13; x ^= x >> 17; x ^= x << 5;
    *state = x;
    return x >> 17;
}

unsigned eu_pulse(unsigned i, unsigned n, unsigned k) {
    /* E(3,8) = 10010010, first pulse at zero. Clamped by the caller. */
    return k && (i * k) % n < k;
}

static uint32_t swing_at(const EuParams *p, uint32_t q) {
    unsigned step_q = 2u * p->scale;
    unsigned step = q / step_q;
    unsigned frac = q % step_q;
    unsigned a = step % p->length, b = (a + 1) % p->length;
    unsigned ma = a < 32 ? (p->mask_lo >> a) & 1 : (p->mask_hi >> (a - 32)) & 1;
    unsigned mb = b < 32 ? (p->mask_lo >> b) & 1 : (p->mask_hi >> (b - 32)) & 1;
    /* Stock 0x4009d3e0: swing raw (display - 50) * 52920 * scale.
     * Interpolate the offsets for the 1/32 subdivision. The swing grid
     * belongs to the track, never to the rotated Euclidean cycle. */
    uint32_t full = p->swing * 52920u * p->scale;
    return full / step_q * (ma * (step_q - frac) + mb * frac);
}

static uint16_t interpolate(unsigned from, unsigned to, uint32_t t, uint32_t duration) {
    if (!duration || t >= duration) return (uint16_t)to;
    /* Durations use clock >> 16: at the slowest supported track/rate,
     * max decay is 124032 units, so the unsigned product fits 32 bits. */
    if (to >= from) return from + (to - from) * t / duration;
    return from - (from - to) * t / duration;
}

uint16_t eu_process(EuState *s, const EuClock *c, const EuParams *p,
                    uint32_t elapsed, unsigned running, unsigned identity) {
    unsigned n = min_u(p->steps, 64); if (!n) n = 1;
    unsigned k = min_u(p->pulses, n);
    unsigned mode = min_u(p->mode, 3);
    uint32_t period = p->scale << min_u(p->rate, 4);
    if (!period) period = 6;

    if (!s->initialized) {
        s->rng = 0x6d2b79f5u ^ (0x9e3779b9u * (identity + 1));
        for (unsigned i = 0; i < 64; ++i) s->values[i] = eu_random(&s->rng);
        s->level = s->origin = s->target = 0;
        s->epoch = c->epoch - 1;
        s->initialized = 1;
    }
    if (s->epoch != c->epoch) {
        s->epoch = c->epoch;
        s->next = 0;
        s->age = 0xffffffffu;
        s->level = s->origin = s->target = 0;
        s->period = period;
        s->mode = mode;
        s->active = 0;
    } else if (period != s->period) {
        /* Quantize a rate / track-scale edit to its next master-grid point.
         * Never play a backlog of pulses when the new division is shorter. */
        s->next = (c->quantum / period + 1) * period;
        s->period = period;
    }
    if (mode != s->mode) {
        s->mode = mode;
        s->origin = s->target = s->level;
        s->age = 0;
        s->active = mode >= 2;
    }
    /* Quarter-clock units cover the longest attack + decay (nine steps at
     * 1/8 track speed and RATE 1/2), which exceeds the raw 32-bit clock.
     * Firmware frame deltas are tempo24 * 16, so this loses no precision. */
    elapsed >>= 2;
    s->age = elapsed > 0xffffffffu - s->age ? 0xffffffffu : s->age + elapsed;

    if (running) {
        /* At most a few events can fit in an audio frame. Bound catch-up
         * after selecting the effect mid-song; position remains anchored. */
        if ((int32_t)(c->quantum - s->next) > (int32_t)(2 * period))
            s->next = (c->quantum / period + 1) * period;
        for (unsigned budget = 0; budget < 3; ++budget) {
            int32_t distance = (int32_t)(s->next - c->quantum) * (int32_t)EU_QUANTUM
                             + (int32_t)swing_at(p, s->next) - (int32_t)c->remainder;
            if (distance > 0) break;
            unsigned index = ((s->next / period) % n + n - p->rotate % n) % n;
            s->next += period;
            if (!eu_pulse(index, n, k)) continue;
            ++s->triggers;
            s->origin = s->level;
            s->age = (uint32_t)-distance >> 2;
            s->active = 1;
            if (mode >= 2) {
                if (mode == 2) s->values[index] = eu_random(&s->rng);
                s->target = s->values[index];
            }
        }
    }

    if (!running || !k) {
        /* Stop and zero pulses settle to the base filter. The random table
         * survives stops and restarts; LOOP therefore remains repeatable. */
        s->active = 0;
        s->level = 0;
    } else if (s->active) {
        /* Derive only the timing this output mode consumes. These divisions
         * used to run for every instance on every frame: RAND/LOOP paid for
         * ENV decay, and an inactive or stopped effect paid for all of it. */
        uint32_t duration = (period * EU_QUANTUM) >> 16;
        uint32_t attack = duration * p->attack * p->attack / 16129u;
        uint32_t age = s->age >> 14;
        if (mode == 0) {
            /* Keep the original short range through one step. The upper half
             * opens out to eight steps, allowing tails to cross rests. */
            uint32_t decay;
            if (p->decay < 64)
                decay = duration * (p->decay + 1u) * (p->decay + 1u) / 4096u;
            else {
                unsigned tail = p->decay - 63u;
                decay = duration + duration * 7u * tail * tail / 4096u;
            }
            if (!decay) decay = 1;
            if (age < attack) s->level = interpolate(s->origin, EU_MAX, age, attack);
            else {
                unsigned ramp = interpolate(EU_MAX, 0, age - attack, decay);
                s->level = ramp * ramp / EU_MAX; /* curved, finite decay */
            }
        } else if (mode == 1) {
            uint32_t length = duration * (p->decay + 1u) / 128u;
            if (!length) length = 1;
            uint32_t edge = min_u(attack, length / 2);
            s->level = age < length ? interpolate(0, EU_MAX, age, edge)
                                  : interpolate(EU_MAX, 0, age - length, edge);
        } else {
            s->level = interpolate(s->origin, s->target, age, attack);
        }
    }
    int32_t depth = (int32_t)p->depth - 16384;
    int32_t cutoff = p->freq + depth * (int32_t)s->level / 16384;
    return cutoff < 0 ? 0 : cutoff > 32512 ? 32512 : (uint16_t)cutoff;
}

#ifndef EUCLID_NATIVE
extern EuClock eu_clock;
extern EuState eu_states[16];

#define U8(a) (*(volatile uint8_t *)(a))
#define U32(a) (*(volatile uint32_t *)(a))

/* Sequencer records and settings, named after tools/emu/emu_rtos.py and
 * docs/firmware/EXTERNAL.md section 9.3. Keep the two bases explicit: the
 * scale-mode and global values belong to the pattern record; the remaining
 * values belong to TRAC. */
enum {
    EU_BANK_BLOB = 0x400e21e0u,
    EU_BANK_STRIDE = 635712u,
    EU_PATTERN_STRIDE = 36568u,
    EU_TRACK_STRIDE = 2330u,
    EU_TEMPO24 = 0x8000181cu,
    EU_TRANSPORT = 0x800065b8u,
    EU_SEQ_BANK = 0x800065bdu,
    EU_SEQ_PATTERN = 0x800065beu,
    EU_FRAME_CLOCK = 0x46104cf0u,
    EU_PATTERN_LENGTH = 0x8e53u,
    EU_PATTERN_SCALE = 0x8e54u,
    EU_PATTERN_SCALE_MODE = 0x8e55u,
    EU_TRACK_SWING_MASK_HI = 0x40u,
    EU_TRACK_SWING_MASK_LO = 0x44u,
    EU_TRACK_LENGTH = 0x50u,
    EU_TRACK_SCALE = 0x51u,
    EU_TRACK_SWING = 0x52u,
};

/* Called AFTER the stock parameter builder, scene interpolation and LFOs.
 * Only FREQ in a Euclid slot is replaced. Every other slot/id is untouched.
 * Record halfwords 6..11 = FX1, 12..17 = FX2; p2 = 18..20 / 24..26. */
void eu_publish(uint16_t *record, unsigned track) {
    unsigned running = U32(EU_TRANSPORT) == 1;
    eu_clock_update(&eu_clock, U32(EU_FRAME_CLOCK));
    if (record[27] != EU_ID && record[28] != EU_ID) {
        eu_states[2 * track].initialized = 0;
        eu_states[2 * track + 1].initialized = 0;
        return;
    }
    volatile uint8_t *pattern = (volatile uint8_t *)(EU_BANK_BLOB
        + U8(EU_SEQ_BANK) * EU_BANK_STRIDE
        + U8(EU_SEQ_PATTERN) * EU_PATTERN_STRIDE);
    volatile uint8_t *tr = pattern + track * EU_TRACK_STRIDE;
    const unsigned scales[7] = {3, 4, 6, 8, 12, 24, 48};
    unsigned per_track = pattern[EU_PATTERN_SCALE_MODE];
    unsigned scale_idx = per_track ? tr[EU_TRACK_SCALE]
                                   : pattern[EU_PATTERN_SCALE];
    unsigned length = per_track ? tr[EU_TRACK_LENGTH]
                                : pattern[EU_PATTERN_LENGTH];
    unsigned scale = scales[scale_idx < 7 ? scale_idx : 2];
    length = length && length <= 64 ? length : 16;
    unsigned swing = min_u(tr[EU_TRACK_SWING], 30);
    uint32_t mask_hi = *(volatile uint32_t *)(tr + EU_TRACK_SWING_MASK_HI);
    uint32_t mask_lo = *(volatile uint32_t *)(tr + EU_TRACK_SWING_MASK_LO);
    uint32_t elapsed = U32(EU_TEMPO24) * 16u;
    for (unsigned fx = 0; fx < 2; ++fx) {
        EuState *s = &eu_states[2 * track + fx];
        if (record[27 + fx] != EU_ID) { s->initialized = 0; continue; }
        unsigned h = 6 + 6 * fx, b = 36 + 12 * fx;
        uint8_t *bytes = (uint8_t *)record;
        EuParams p;
        p.freq = record[h]; p.depth = record[h + 2];
        p.decay = record[h + 3] >> 8;
        p.steps = (record[h + 4] >> 8) + 1;
        p.pulses = record[h + 5] >> 8;
        p.rotate = bytes[b]; p.rate = bytes[b + 1];
        p.attack = bytes[b + 3];
        p.mode = bytes[b + 4];
        p.scale = scale; p.length = length; p.swing = swing;
        p.mask_hi = mask_hi; p.mask_lo = mask_lo;
        record[h] = eu_process(s, &eu_clock, &p, elapsed, running,
                               2 * track + fx);
    }
}

void eu_publish_frame(void) {
    uint16_t *record = (uint16_t *)(0x80000110u + (U32(0x800000e0) & 1u) * 512u);
    for (unsigned track = 0; track < 8; ++track)
        eu_publish(record + track * 32, track);
}
#endif
