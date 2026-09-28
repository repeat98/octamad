/* Circuit-informed reduced models, Q23 state / Q15 coefficients, 2x rate.
 * 808: triggered damped band-pass, short frequency jump, delayed excitation,
 *      weak pitch sigh, passive tone pole. Ringing state survives a retrigger.
 * 909: phase-reset oscillator, independent pitch/VCA envelopes, sine shaping,
 *      short filtered noise/click attack. No sample playback.
 * Component-level matching against real units remains a qualification gate.
 */
#include "engine.h"
#include "tables.inc"
#define ONE 8388608
const uint8_t ab_defaults[AB_PARAMS] = {64, 80, 80, 64, 64, 0, 0, 64, 127, 64, 64, 0};
unsigned ab_lpf_frequency(unsigned value) { return (unsigned)ab_lpf_freq[value&127]; }
/* Split multiply avoids libgcc's 64-bit helpers on the ColdFire. The largest
 * low product is 32767*32768; both partial products fit signed 32 bits. */
static int32_t mul(int32_t x, int32_t k) {
    return (x >> 15) * k + ((x & 32767) * k >> 15);
}
/* Q23 loss with retained fractional error. Without this carry, a long
 * envelope stops decaying once its decrement falls below one state LSB. */
static int32_t loss(int32_t x, int32_t k, int32_t *remainder) {
    int32_t hi=(x >> 12)*k;
    int32_t lo=(x & 4095)*k+(hi & 2047)*4096+*remainder;
    *remainder=lo & (ONE-1);
    return (hi >> 11)+(lo >> 23);
}
/* Error feedback keeps signed integrators unbiased at sub-LSB steps.
 * A plain arithmetic shift rounds negative steps down and positive steps
 * toward zero, creating DC offsets and undamped fixed-point limit cycles. */
static int32_t step(int32_t x, int32_t k, int32_t *remainder) {
    int32_t lo=(x & 32767)*k+*remainder;
    *remainder=lo & 32767;
    return (x >> 15)*k+(lo >> 15);
}
/* Free-running 31-stage noise, taps 31/13, as wired by IC32/IC33.
 * Approximate 300 kHz clock, averaged into each 88.2 kHz interval.
 * This reduced-rate integration is not a transistor/clock-tolerance model.
 * Never reseed on a hit or when an envelope becomes inaudible. */
static int32_t noise_tick(AbVoice *v) {
    v->noise_clock+=300000;
    int32_t sum=0, count=0;
    while(v->noise_clock>=88200) {
        v->noise_clock-=88200;
        uint32_t feedback=((v->noise>>30)^(v->noise>>12))&1u;
        v->noise=((v->noise<<1)|feedback)&0x7fffffffu;
        sum+=(v->noise&1u) ? ONE : -ONE;
        ++count;
    }
    v->noise_lp+=step(sum/count-v->noise_lp,7000,&v->noise_remainder);
    return v->noise_lp;
}
static int32_t limit(int32_t x, int32_t max) {
    return x > max ? max : (x < -max ? -max : x);
}
static int32_t soft(int32_t x) {
    x = limit(x, ONE);
    int32_t x2 = mul(x, x >> 8);
    return x - mul(x2, x >> 8) / 3;
}
void ab_reset(AbVoice *v) {
    v->low=v->band=v->env=v->pitch=v->tone=v->dc=v->click=0;
    v->output_lp=v->output_remainder=0;
    v->phase=0; v->noise=0x6d2b79f5u; v->age=0; v->noise_clock=0;
    v->previous=0; v->band_remainder=v->env_remainder=0; v->model=0; v->active=0; v->pulse=0; v->quiet=0;
    v->pitch_remainder=v->click_remainder=v->tone_remainder=v->dc_remainder=0;
    v->low_remainder=v->step_remainder=0;
    v->shaper=v->shaper_remainder=0;
    v->click_rise=v->click_edge=v->noise_lp=0;
    v->rise_remainder=v->edge_remainder=v->noise_remainder=0;
}
void ab_trigger(AbVoice *v, const uint8_t p[AB_PARAMS]) {
    unsigned model = p[6] ? 1 : 0;
    if (v->model != model) {
        /* Model changes are applied at the next hit. Keep the output pole
         * continuous while discarding the other circuit's internal state. */
        v->low=v->band=0;
        v->low_remainder=v->step_remainder=v->band_remainder=0;
        v->shaper=v->shaper_remainder=0;
        v->click_rise=v->click_edge=0;
        v->rise_remainder=v->edge_remainder=0;
    }
    v->model=model; v->active=1; v->age=0; v->pulse=model ? 264 : 88;
    v->env=ONE; v->pitch=ONE; v->click=ONE;
    v->env_remainder=v->pitch_remainder=v->click_remainder=0; v->quiet=0;
    if (model) v->phase=0x40000000u;
}
int32_t ab_sample(AbVoice *v, const uint8_t p[AB_PARAMS]) {
    /* Even a silent voice has a running noise circuit. Keep its filtered
     * state so elapsed time changes the next attack naturally. */
    int32_t noise_a=noise_tick(v), noise_b=noise_tick(v);
    if (!v->active) return 0;
    unsigned tune=p[0]&127, decay=p[1]&127, tone=p[2]&127;
    unsigned attack=p[3]&127, sweep=p[4]&127, accent=p[7]&127;
    int32_t out=0;
    for (unsigned os=0; os<2; ++os) {
        int32_t y;
        if (!v->model) {
            /* Frequency doubles during the pulse, followed by the small
             * leakage-induced sigh. SWEEP=64 is the nominal contour. */
            int32_t k=ab_k[tune];
            int32_t bend = v->age < 500 ? ONE : (v->pitch >> 4);
            k += (mul(bend, k) * (int32_t)sweep) >> 14;
            /* R162=4.7k, R163=100k, C40=0.15uF: 0.673 ms low
             * shelf, with a 4..14 V trigger (ONE represents 14 V).
             * Matched RC pole at 88.2 kHz; negative diode transfer is
             * the interpolated DAFx-14 Eq. 4 approximation. Preserve the
             * capacitor state across hits, as with the resonator. */
            int32_t trigger=v->pulse ? 2396745+(int32_t)accent*47180 : 0;
            int32_t excitation=trigger-mul(v->shaper,31297);
            v->shaper+=step(trigger-v->shaper,547,&v->shaper_remainder);
            if(excitation<0) {
                unsigned x=(unsigned)-excitation;
                unsigned i=x>>15;
                excitation=i>=256 ? ab_diode[256] : ab_diode[i]+
                    mul(ab_diode[i+1]-ab_diode[i],(int32_t)(x&32767));
            }
            if (v->age==500) v->band=limit(v->band + (int32_t)(attack+32)*16384, ONE);
            /* Semi-implicit state variable band-pass. Damping coefficient
             * includes k, so DECAY controls time rather than cycles. */
            int32_t damp=loss(v->band, 2*ab_loss[decay], &v->band_remainder);
            v->band=limit(v->band+step(excitation-v->low,k,&v->step_remainder)-damp, ONE);
            v->low=limit(v->low+step(v->band,k,&v->low_remainder),ONE);
            y=v->band;
            /* Feedthrough of the shaped trigger is part of the attack. */
            y += mul(excitation,(int32_t)attack*256)/16;
        } else {
            uint32_t inc=ab909_inc[tune];
            int32_t bend=mul(v->pitch,ab909_bend[tune]>>8);
            bend=mul(bend,ab909_depth[sweep])*4;
            bend=mul(bend,ab909_tune_gain[tone])*2;
            inc+=(uint32_t)bend;
            /* The reference VCO is held at its positive crest throughout
             * the 3 ms reset pulse. It rings immediately on release. */
            if(!v->pulse) {
                /* A short reset-release ramp fits the first cycle without
                 * shifting the later pitch envelope or the click event. */
                if(v->age<352) inc=(uint32_t)mul((int32_t)inc,(int32_t)(v->age-264)*372);
                v->phase+=inc;
            }
            /* 909 integrator/Schmitt VCO -> triangle -> diode sine shaper.
             * The cubic approximates that static transfer, not a second
             * envelope on the 808 resonator. PITCH, TUNE and TDEP are independent controls. */
            int32_t phase=(int32_t)(v->phase >> 8);
            int32_t tri=phase < 0x400000 ? 2*phase
                : (phase < 0xc00000 ? 2*(ONE-phase) : 2*(phase-2*ONE));
            int32_t s=soft(tri); s+=s/2;
            y=v->pulse ? 0 : mul(mul(s,v->env>>8),16384+(int32_t)accent*128);
            int32_t noise=os ? noise_b : noise_a;
            if(v->pulse) {
                v->click_rise+=step(ONE-v->click_rise,512,&v->rise_remainder);
                y-=v->click_rise/16+mul(v->click_rise,(int32_t)attack*80);
            } else {
                /* Let the trigger-shaper capacitor discharge between hits. */
                v->click_rise-=step(v->click_rise,512,&v->rise_remainder);
            }
            if(v->age==264) v->click_edge=ONE;
            y+=v->click_edge/3+45*mul(v->click_edge,(int32_t)attack*512)/16;
            y+=mul(mul(noise/4,v->click>>8),(int32_t)attack*192);
            v->click_edge-=step(v->click_edge,3500,&v->edge_remainder);
            /* Measured VCA: near-flat body until ~60 ms, then the
             * DECAY-controlled release. The init setting releases fast. */
            v->env-=loss(v->env,v->age<5292 ? 63 : ab909_amp_loss[decay],&v->env_remainder);
        }
        if (v->pulse) --v->pulse;
        v->pitch -= v->model ? loss(v->pitch,ab909_pitch_loss[tone],&v->pitch_remainder)
                            : step(v->pitch,7,&v->pitch_remainder);
        v->click -= step(v->click,130,&v->click_remainder);
        /* Output tone and AC coupling; states persist across retriggers.
         * 909: 4 kHz pole (Q15 at 88.2 kHz) rounds the reset edge and
         * attack noise. Oscillator, pitch and VCA envelopes are unchanged. */
        v->tone += step(y-v->tone,v->model ? 8125 : ab_tone[tone],&v->tone_remainder);
        v->dc += step(v->tone-v->dc,v->model ? 2 : 12,&v->dc_remainder);
        int32_t coupled=v->tone-v->dc;
        /* Main-output RC is separate from the calibrated voice bandwidth.
         * Keep the capacitor tracking in bypass; switching cannot recall a
         * stale tail. Position 64 is the drawn nominal network, 0 bypass. */
        int32_t lp_k=ab_lpf_coef[p[8]&127];
        v->output_lp+=step(coupled-v->output_lp,lp_k,&v->output_remainder);
        out += v->model && p[8] ? v->output_lp : coupled;
        ++v->age;
    }
    /* Retire only after every audible energy store is below -96 dBFS
     * for 256 output samples. Inspect internal energy, before stock AMP: track volume must not change the circuit lifetime. */
    int quiet_body=v->model ? v->env<=128 :
        (v->low>=-128 && v->low<=128 && v->band>=-128 && v->band<=128);
    if(!v->pulse && v->age>500 && quiet_body && v->click<=128 && v->click_edge<=128 &&
       v->output_lp>=-128 && v->output_lp<=128 &&
       v->tone>=-128 && v->tone<=128 && v->dc>=-128 && v->dc<=128) {
        if(++v->quiet>=256) { v->active=0; return 0; }
    } else v->quiet=0;
    out=mul(out/2,v->model ? 17500 : 18000); /* Fixed source headroom; volume lives on AMP. */
    out=limit(out,ONE-1);
    /* Bound the tiny fixed-point residual independently of arithmetic Z. */
    if (v->age > 88200u*40u) { v->active=0; return 0; }
    v->previous=out;
    return out;
}
