/* CPU Tape Echo: fixed-point, allocation-free. One playback head, fixed
 * DRIVE=0. FREE has a Q24.8 motor; BEAT snaps with a bounded crossfade.
 * Economy model: two biquads plus a record FIR, block-rate glide, two simple
 * modulation oscillators. No physical-cell or transport-history model.
 * Only the stock delay's current track ring is used, through its uncached
 * alias. The stock DMA commits record[] after this function returns. */
#include "cpu.h"
#include "cpu_tables.h"
_Static_assert(sizeof(TapeState) == 200, "cpu_hooks.s allocation: 8 x 200 bytes");

static uint32_t minimum(uint32_t a, uint32_t b) { return a < b ? a : b; }
static int32_t clip(int32_t a) {
    return a > 8388607 ? 8388607 : a < -8388608 ? -8388608 : a;
}
/* Signed fractional EMAC, MACSR=0xa0 as established by stock 0x400031c4.
 * acc0 is cleared on every read. Stock saves/restores ALL EMAC state around
 * the entire delay routine. The host path is an independent arithmetic oracle. */
static inline int32_t mul31(int32_t a, int32_t b) {
#ifdef __m68k__
    int32_t out;
    __asm__ volatile ("mac.l %1,%2,%%acc0\n\tmovclr.l %%acc0,%0"
                      : "=d"(out) : "d"(a), "d"(b));
    return out;
#else
    return (int32_t)(((int64_t)a * b) >> 31);
#endif
}
static int32_t gain(uint32_t knob) {
    return (int32_t)(minimum(knob, 127) * 16909320u); /* <= INT32_MAX */
}
/* Audio in the tape/filters is Q6.26 (three more bits than the old Q23
 * loop). Four-FS bounded filter histories and coefficient L1 < 8 keep
 * every partial sum in int32. Biquad coefficients are signed Q2.30. */
#ifdef __m68k__
/* Hand-scheduled two-sample EMAC kernel; same fraction-saving arithmetic
 * as the native oracle below. Input is already bounded to +/-4 FS. */
void te_filter_block(int32_t *, const int32_t *, int32_t *);
#define filter_block te_filter_block
#else
static void filter_block(int32_t *buffer, const int32_t *c, int32_t *z) {
    int32_t x1=z[0], x2=z[1], y1=z[2], y2=z[3], error=z[4];
    const int32_t b0=c[0], b1=c[1], b2=c[2], a1=c[3], a2=c[4];
    for (unsigned i=0;i<TE_FRAMES;++i) {
    int32_t x=buffer[i];
    if (x > 268435456) x = 268435456;
    if (x < -268435456) x = -268435456;
    int32_t doubled=x*2, y=doubled;
    /* One accumulator/read for the whole section. Carry its eight low bits
     * to the next sample (fraction saving): repeated truncation in a 106 Hz
     * recursive section otherwise creates an audible DC/limit-cycle floor.
     * Only acc0 is changed; acc1..3 and their extension bits are preserved. */
    int64_t accumulator = error + (((int64_t)doubled*b0) >> 23)
        + (((int64_t)x1*b1) >> 23) + (((int64_t)x2*b2) >> 23)
        + (((int64_t)y1*a1) >> 23) + (((int64_t)y2*a2) >> 23);
    y = (int32_t)(accumulator >> 8); error=(uint32_t)accumulator & 255;
    if (y > 268435456) { y = 268435456; error=0; }
    if (y < -268435456) { y = -268435456; error=0; }
    x2=x1; x1=doubled; y2=y1; y1=y*2;
    buffer[i]=y;
    }
    z[0]=x1; z[1]=x2; z[2]=y1; z[3]=y2; z[4]=error;
}
#endif
static int32_t amplify(int32_t x, int32_t q28) { return 8 * mul31(x,q28); }
static int32_t saturate(int32_t x) {
    unsigned a = x < 0 ? (unsigned)-x : (unsigned)x;
    if (a >= 536870912) a = 536870911;
    unsigned i = a >> 18;
    int32_t y = te_curve[i] + mul31(te_curve[i+1]-te_curve[i], (a & 262143u) << 13);
    return x < 0 ? -y : y;
}
static uint32_t random32(TapeState *s) {
    s->rng ^= s->rng << 13; s->rng ^= s->rng >> 17; s->rng ^= s->rng << 5;
    return s->rng;
}
/* Full-period 32-bit LCG. Hiss uses the high signed word through mul31;
 * never its short-period low bits. Three integer instructions replace
 * the per-sample xorshift; flutter keeps its original generator. */
static uint32_t hiss_random(TapeState *s) {
    s->rng=s->rng*1664525u+1013904223u;
    return s->rng;
}
static int32_t sine(uint32_t phase) {
    unsigned i = phase >> 22;
    return te_sine[i] + mul31(te_sine[i+1]-te_sine[i], (phase & 4194303u) << 9);
}
/* TIME's 128 automation values select twelve bands in BEAT. All divisions
 * fit the four-second ring down to the stock minimum tempo (30 BPM).
 * Keep time_fmt.s's names/band mapping in lockstep with this table. */
static const uint8_t clocks2[12] = {3,4,6,8,12,16,18,24,32,36,48,72};

uint32_t te_target(const TapeParams *p, uint32_t tempo) {
    if (tempo < 720 || tempo > 7200) tempo = 2880;
    uint32_t target = (2048u + 64u * minimum(p->time, 127)) << 8;
    if (p->sync) {
        /* samples = 44100*60*(MIDI clocks*2)/(2*tempo24). Split the
         * quotient to keep Q24.8 precision without a 64-bit divide. */
        uint32_t n = 1323000u * clocks2[(minimum(p->time, 127)*12u) >> 7];
        target = (n / tempo) * 256u + (n % tempo) * 256u / tempo;
    }
    /* Include wow and the neighbouring interpolation sample. */
    uint32_t limit = (TE_RING - 1024u) << 8;
    return minimum(target, limit);
}

static int32_t read_head(volatile int32_t *ring, uint32_t write,
                         uint32_t delay, uint32_t valid) {
    unsigned whole = delay >> 8, frac = delay & 255;
    /* Exclude all tape recorded by a previously selected effect. This is
     * also the startup clear: bounded work, no 1.4 MB memset in the ISR. */
    if (whole + 1u > valid) return 0;
    unsigned newer = write >= whole ? write - whole : write + TE_RING - whole;
    unsigned older = newer ? newer - 1 : TE_RING - 1;
    int32_t a = ring[2u * newer] >> 5, b = ring[2u * older] >> 5;
    return a + mul31(b - a, (int32_t)(frac << 23));
}

/* Contiguous-head fast path. Use an advancing fractional read position
 * instead of rebuilding/clamping/checking each head's delay each sample.
 * The caller proves the whole block is valid history and in delay bounds.
 * Linear interpolation from older->newer is integer-identical to the
 * general path's newer->older interpolation (including negative samples). */
#ifdef __m68k__
void te_read_linear(int32_t *, volatile int32_t *, int32_t, int32_t, int32_t);
#endif
static void read_settled(int32_t *restrict out, volatile int32_t *restrict ring,
                         uint32_t write, uint32_t delay, int32_t wobble,
                         int32_t step) {
    int32_t base=(int32_t)(write*256u-delay);
    const int32_t ring_units=TE_RING*256;
    int32_t end=wobble+16*step;
    int32_t lo=base-((wobble>end?wobble:end)>>8);
    int32_t hi=base+15*256-((wobble<end?wobble:end)>>8);
    if (hi<0) { base+=ring_units;lo+=ring_units;hi+=ring_units; }
    else if (lo>=ring_units) { base-=ring_units;lo-=ring_units;hi-=ring_units; }
    if (lo>=0 && hi<(int32_t)((TE_RING-1)*256)) {
#ifdef __m68k__
        te_read_linear(out,ring,base,wobble,step);
#else
        for (unsigned i=0;i<TE_FRAMES;++i) {
            wobble+=step;
            uint32_t position=(uint32_t)(base-(wobble>>8)), index=position>>8;
            int32_t a=ring[2*index]>>5,b=ring[2*index+2]>>5;
            out[i]=a+mul31(b-a,(position&255u)<<23);
            base+=256;
        }
#endif
        return;
    }
    for (unsigned i=0;i<TE_FRAMES;++i) {
        wobble += step;
        int32_t position=base-(wobble>>8);
        if (position<0) position += TE_RING*256;
        else if (position>=(int32_t)(TE_RING*256)) position -= TE_RING*256;
        unsigned index=(uint32_t)position >> 8;
        unsigned next=index+1 == TE_RING ? 0 : index+1;
        int32_t a=ring[2*index]>>5, b=ring[2*next]>>5;
        int32_t sample=a+mul31(b-a,((uint32_t)position&255u)<<23);
        out[i] = sample;
        base += 256;
    }
}

/* A linear delay ramp serves FREE motor movement, WOW, and each end of a
 * BEAT crossfade. Prove history/bounds once, then use the same assembly
 * reader whether TIME is moving or stationary. Slow fallback is confined
 * to not-yet-recorded history or clamping, never ordinary knob movement. */
static void render_head(int32_t *out, volatile int32_t *ring, uint32_t write,
                        uint32_t position, int32_t offset, int32_t step,
                        uint32_t valid) {
    int32_t end=offset+16*step;
    int32_t lo=(int32_t)position+((offset<end?offset:end)>>8);
    int32_t hi=(int32_t)position+((offset>end?offset:end)>>8);
    if (lo>=32*256 && hi<=(int32_t)((TE_RING-2)*256) && ((unsigned)hi>>8)+1<=valid) {
        read_settled(out,ring,write,position,offset,step);
    } else if (lo<32*256 || ((unsigned)lo>>8)+1<=valid+15) {
        for (unsigned i=0;i<TE_FRAMES;++i) {
            offset+=step;
            int32_t delay=(int32_t)position+(offset>>8);
            if (delay<32*256) delay=32*256;
            if (delay>(int32_t)((TE_RING-2)*256)) delay=(TE_RING-2)*256;
            out[i]=read_head(ring,write+i,delay,valid+i);
        }
    } else for (unsigned i=0;i<TE_FRAMES;++i) out[i]=0;
}

/* Keep constant gains and the PRNG in registers through the block. Knob
 * ramps use the general loop below; this path changes no arithmetic. */
#ifndef __m68k__
static __attribute__((noinline)) void record_settled(TapeState *restrict s,
        const int32_t *restrict playback, int32_t *restrict audio,
        int32_t *restrict recording) {
    const int32_t drive=te_record_gain[0], feedback=s->feedback, makeup=te_makeup[0];
    const int32_t noise=s->hiss>>16, mix=s->mix;
    uint32_t rng=s->rng;
    for (unsigned i=0;i<TE_FRAMES;++i) {
        int32_t wet=playback[i], l=audio[2*i]>>5, r=audio[2*i+1]>>5;
        rng=rng*1664525u+1013904223u;
        int32_t rec=amplify((l+r)/2,drive)+amplify(wet,feedback)+mul31(noise,(int32_t)rng);
        if (rec>268435456) rec=268435456;
        if (rec<-268435456) rec=-268435456;
        recording[i]=rec;
        if (!mix) continue;
        wet=amplify(wet,makeup);
        int32_t left,right;
        if (mix==2147483640) {
            /* Full wet is mono. Drop the old dry-dependent one-Q23-LSB
             * interpolation quirk, clip once, and duplicate the result. */
            left=right=clip(wet>>3);
        } else {
            left=clip((l+mul31(wet-l,mix))>>3);
            right=clip((r+mul31(wet-r,mix))>>3);
        }
        audio[2*i]=(int32_t)((uint32_t)left<<8);
        audio[2*i+1]=(int32_t)((uint32_t)right<<8);
    }
    s->rng=rng;
}
#else
void te_record_block(TapeState *, const int32_t *, int32_t *, int32_t *,
                     int32_t, int32_t, int32_t);
void te_finish_record(const int32_t *, int32_t *, int32_t *, const int32_t *);
void te_record_wet_finish(TapeState *, const int32_t *, int32_t *, int32_t *);
#endif

void te_process(TapeState *restrict s, const TapeParams *restrict p,
                volatile int32_t *restrict ring, uint32_t write,
                int32_t *restrict audio, int32_t *restrict record) {
    if (p->tempo >= 720 && p->tempo <= 7200) s->tempo = p->tempo;
    if (s->tempo < 720 || s->tempo > 7200) s->tempo = 2880;
    uint32_t target = te_target(p, s->tempo);
    unsigned age = minimum(p->age,127);
    int32_t mix = gain(p->mix), wow = gain(p->wow);
    int32_t feedback = te_feedback[minimum(p->feedback,127)];
    if (!s->active) {
        /* Also clear every filter/oscillator after dirty-state effect entry. */
        uint32_t tempo = s->tempo;
        uint32_t *words = (uint32_t *)s;
        for (unsigned j=0;j<sizeof(*s)/4;++j) words[j]=0;
        s->tempo = tempo; s->position = target;
        s->rng = 0x6d2b79f5;
        s->mix = mix; s->feedback = feedback;
        s->age = age << 16; s->wow = wow;
        s->hiss = te_hiss[age] << 16;
        s->flutter = 751934170u;
        s->flutter_rate=s->flutter_target=973915;
        s->mode = !!p->sync;
    }
    /* Never restart a live fade: rapid locks/knob edits are coalesced to
     * the latest target at the next boundary (at most 2*512 samples).
     * Only this transition has two reads; there is one normal echo head.
     * No waits, allocation, ring clear, or global/shared transition state. */
    if (!s->fade_left && (p->sync || s->mode != !!p->sync)) {
        if (s->position != target) {
            s->fade_from = s->position;
            s->fade_left = TE_FADE;
            s->position = target;
        }
        s->mode = !!p->sync;
    }
    /* Tone is a slow control, not audio timing. Design/ramp it once per
     * 64 samples (~1.45 ms); TIME/WOW positions and gain ramps still run
     * every block/sample. This bounds the cost of simultaneous AGE/TIME
     * edits, not only the steady-state benchmark. */
    if (!((s->control_clock++ + p->lane) & 3u) || !s->active) {
    /* Tonal speed follows the running motor, clamped to the pedal's range. */
    uint32_t speed=s->cached_speed;
    unsigned update_corner=!s->active, update_worn=!s->active;
    /* Tone is not timing: updating at 32-sample delay bins avoids repeated
     * division/interpolation while TIME moves. Coefficients still ramp. */
    if (!s->active || s->cached_position != s->position>>13) {
        speed = 1156055040u / (s->position >> 8); /* .4*44100 / delay, Q16 */
        if (speed < 65536) speed = 65536;
        if (speed > 524288) speed = 524288;
        update_corner |= speed != s->cached_speed;
        s->cached_speed=speed; s->cached_position=s->position>>13;
        s->cached_index=(speed-65536)>>13;
    }
    unsigned index=s->cached_index;
    unsigned worn = (unsigned)s->age >> 16;
    update_worn |= worn != s->cached_age; s->cached_age=worn;
    if (update_corner || update_worn) for (unsigned j=0;j<5;++j) {
        int32_t c=te_tone[worn*57+index][j];
        if (index<56) c+=mul31(te_tone[worn*57+index+1][j]-c,(speed&8191u)<<18);
        s->filter_targets[0][j]=c;
    }
    /* The /8 step at quarter control rate retains roughly the old /32
     * smoothing time. Skip settled coefficients until tone changes. */
    if (update_corner || update_worn || s->filter_pending) {
        s->filter_pending=0;
        for (unsigned k=0;k<1;++k) for (unsigned j=0;j<5;++j) {
            int32_t delta=s->active ? (s->filter_targets[k][j]-s->coefficients[k][j])/8
                                    : s->filter_targets[k][j];
            s->coefficients[k][j]+=delta;
            s->filter_pending |= delta!=0;
        }
    }
    }
    s->active = 1;
    /* ~12 ms gain ramps; no gain reset or phase reset at FREE/BEAT changes. */
    int32_t dm = (mix-s->mix)/512, df = (feedback-s->feedback)/512;
    int32_t da = ((int32_t)(age<<16)-s->age)/512, dw = (wow-s->wow)/512;
    int32_t dn = ((te_hiss[age]<<16)-s->hiss)/512;
    /* Two cheap oscillators: 0.8 Hz wow, gently randomized ~8..12 Hz
     * flutter. No travel-time integration, speed-dependent oscillator
     * divisions, capstan harmonic or drift oscillator. At WOW=44 this
     * retains about eight cents RMS; AGE increases the flutter component. */
    s->phase += 16u*77913u;
    s->flutter_rate += ((int32_t)s->flutter_target-(int32_t)s->flutter_rate)/16;
    uint32_t old=s->flutter;
    s->flutter+=16u*s->flutter_rate;
    if (s->flutter<old) s->flutter_target=779132u+(random32(s)&0x3ffffu);
    int32_t wobble_step = -s->wobble/16;
    if (s->wow || s->wobble) {
        int32_t wow_amp=mul31(159*256,s->wow);
        int32_t flutter_amp=mul31(256+8*(s->age>>16),s->wow);
        int32_t w=2*mul31(wow_amp,sine(s->phase))
                 +2*mul31(flutter_amp,sine(s->flutter));
        wobble_step = (w*256 - s->wobble)/16;
    }
    /* A snapped time changes the integrated wow offset. Do not traverse
     * that offset in one block: bound acceleration as well as velocity.
     * Normal low-rate wow is below these bounds; a mode/TIME jump is not. */
    if (wobble_step>s->wobble_step+128) wobble_step=s->wobble_step+128;
    if (wobble_step<s->wobble_step-128) wobble_step=s->wobble_step-128;
    if (wobble_step>8192) wobble_step=8192;
    if (wobble_step<-8192) wobble_step=-8192;
    s->wobble_step=wobble_step;
    int32_t playback[TE_FRAMES], recording[TE_FRAMES];
    uint32_t position=s->position;
    int32_t motor_step=0;
    if (!p->sync && !s->fade_left && position!=target) {
        int32_t error=(int32_t)target-(int32_t)position;
        /* One slew calculation per block. No motor acceleration model or
         * fractional velocity state. Fractional read positions still ramp
         * linearly through the block, so the read head never jumps. */
        int32_t movement=error/64;
        if (!movement) movement=error>0?1:-1;
        if (movement>512) movement=512;
        if (movement<-512) movement=-512;
        s->position=position+movement;
        motor_step=movement*16;
    }
    render_head(playback,ring,write,position,s->wobble,wobble_step+motor_step,s->valid);
    if (s->fade_left) {
        /* Reuse the later record scratch; there is no third audio array. */
        render_head(recording,ring,write,s->fade_from,s->wobble,wobble_step,s->valid);
        uint32_t blend=(TE_FADE-s->fade_left)<<22;
        for (unsigned i=0;i<TE_FRAMES;++i) {
            playback[i]=recording[i]+mul31(playback[i]-recording[i],(int32_t)blend);
            blend+=1u<<22;
        }
        s->fade_left-=TE_FRAMES;
    }
    s->wobble+=16*wobble_step;
    /* All heads are >=32 samples behind this uncommitted block: playback
     * and record filters can be batched without changing feedback causality. */
    filter_block(playback,te_fixed[1],s->filters[1]);
    filter_block(playback,s->coefficients[0],s->filters[2]);
#ifdef __m68k__
    if (s->mix==2147483640 && !(dm|df|dn)) {
        te_record_wet_finish(s,playback,audio,record);
    } else {
        te_record_block(s,playback,audio,recording,dm,df,dn);
        te_finish_record(recording,record,s->filters[0],te_curve);
    }
#else
    if (!(dm|df|dn)) record_settled(s,playback,audio,recording);
    else for (unsigned i=0;i<TE_FRAMES;++i) {
        s->mix += dm; s->feedback += df;
        s->hiss += dn;
        int32_t wet=playback[i];
        int32_t l = audio[2*i] >> 5, r = audio[2*i+1] >> 5;
        int32_t hiss = mul31(s->hiss >> 16,(int32_t)hiss_random(s));
        recording[i] = amplify((l+r)/2,te_record_gain[0]) + amplify(wet,s->feedback) + hiss;
        /* Only the input to the record chain can exceed the filter bound.
         * Playback is bounded by the tape curve/head normalization; every
         * filter clamps its output. Hoist the input clamp out of the kernels. */
        if (recording[i]>268435456) recording[i]=268435456;
        if (recording[i]<-268435456) recording[i]=-268435456;
        wet = amplify(wet,te_makeup[0]);
        if (s->mix) {
            int32_t left = clip((l + mul31(wet - l, s->mix)) >> 3);
            int32_t right = clip((r + mul31(wet - r, s->mix)) >> 3);
            audio[2*i] = (int32_t)((uint32_t)left << 8);
            audio[2*i+1] = (int32_t)((uint32_t)right << 8);
        }
    }
    /* [1,6,1]/8 record FIR: unity DC gain, no multiplies, no recursive
     * state/limit cycles. The combined playback table compensates its
     * different top-end slope; the tape curve itself is unchanged. */
    int32_t x1=s->filters[0][0], x2=s->filters[0][1];
    for (unsigned i=0;i<TE_FRAMES;++i) {
        int32_t x=recording[i];
        int32_t shaped=x1+((x-2*x1+x2)>>3);
        x2=x1; x1=x;
        int32_t rec = saturate(shaped);
        record[2*i] = record[2*i+1] = (int32_t)((uint32_t)rec << 5);
    }
    s->filters[0][0]=x1; s->filters[0][1]=x2;
#endif
    s->age += 16*da; s->wow += 16*dw;
    /* Exact dry must not leave a tiny ramp residual forever. */
    if (!mix && s->mix < 512) s->mix = 0;
    if (!wow && s->wow < 512) s->wow = 0;
    s->valid = minimum(s->valid + TE_FRAMES, TE_RING - 1);
}

#ifndef TE_HOST
#define U32(a) (*(volatile uint32_t *)(a))
unsigned te_cpu_frame(uint32_t *sp) {
    unsigned track = sp[112/4];
    volatile uint8_t *setup = (volatile uint8_t *)sp[76/4];
    if (track >= 8) return 0;
    TapeState *s = &te_states[track];
    if (setup[7] != 0x15 || *(volatile uint8_t *)sp[108/4] == 7) {
        s->active = 0;
        return 0;
    }
    volatile uint16_t *knobs = (volatile uint16_t *)sp[72/4];
    TapeParams p = {knobs[0] >> 8, knobs[1] >> 8, knobs[2] >> 8,
                    knobs[4] >> 8, knobs[5] >> 8,
                    knobs[3] >> 8, U32(0x8000181c), track};
    uint32_t base = 0x4f502c10u + track * TE_STRIDE;
    uint32_t write = (sp[48/4] - base) >> 3;
    if (write > TE_RING - TE_FRAMES) { s->active = 0; return 0; }
    /* Stock 0x40003624 toggles these two scratch buffers after prefetching
     * the NEXT track into the other one. Skipping that toggle would overwrite
     * an in-flight DMA read and break every following stock-delay track. */
    U32(0x800000e8) ^= U32(0x40003626);
    /* The stock filter usually drains acc0. We bypass it, so establish the
     * same empty accumulator before the first multiply. */
    __asm__ volatile ("move.l #0,%%acc0" ::: "memory");
    te_process(s, &p, (volatile int32_t *)base, write,
               (int32_t *)sp[96/4], (int32_t *)U32(0x800000e8));
    U32(0x80006180) += 68; /* stock filter's per-track state iterator */
    return 1;
}
#endif
