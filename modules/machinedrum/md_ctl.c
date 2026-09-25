/* The Machinedrum's control engine: kit state and the record producer
 * (WP-C4). See md_ctl.h for the MD behaviour it reproduces. */
#include "md_ctl.h"
#include "md_pan.inc"                /* md_pan_q15[128], generate_ctl.py */

_Static_assert(sizeof(MdPart) == 12, "md_ctl_tail.s kit allocation");
_Static_assert(sizeof(MdKit) == 192, "md_ctl_tail.s kit allocation");
_Static_assert(sizeof(MdEngine) == 52, "handler_build.py engine rows");
_Static_assert(sizeof(MdRun) == 1344 + 192 + 20 + 8 + 4 + 2 * (3 + MD_MBOX_HW + 3),
               "md_ctl_tail.s runtime allocation");
_Static_assert(sizeof(MdPattern) == 384, "md_ctl_tail.s pattern allocation");
_Static_assert(sizeof(MdClock) == 20, "md_ctl_tail.s clock allocation");
_Static_assert(sizeof(MdSeq) == 16 + 32 + 160 + 4, "md_ctl_tail.s sequencer allocation");

/* The OT's sequencer records, as Euclid reads them (modules/euclid). */
enum {
    OT_BANK_BLOB = 0x400e21e0u,
    OT_BANK_STRIDE = 635712u,
    OT_PATTERN_STRIDE = 36568u,
    OT_TRACK_STRIDE = 2330u,
    OT_TRANSPORT = 0x800065b8u,      /* a long: 1 while playing */
    OT_SEQ_BANK = 0x800065bdu,
    OT_SEQ_PATTERN = 0x800065beu,
    OT_FRAME_CLOCK = 0x46104cf0u,
    OT_PATTERN_LENGTH = 0x8e53u,
    OT_PATTERN_SCALE = 0x8e54u,
    OT_PATTERN_SCALE_MODE = 0x8e55u,
    OT_TRACK_SWING_MASK_HI = 0x40u,
    OT_TRACK_SWING_MASK_LO = 0x44u,
    OT_TRACK_LENGTH = 0x50u,
    OT_TRACK_SCALE = 0x51u,
    OT_TRACK_SWING = 0x52u,
    OT_UI_BANK = 0x80000002u,        /* the resident bank */
    OT_PART_IDX = 0x100b14cfu,       /* the active Part */
};
#define U8(a) (*(volatile uint8_t *)(a))
#define U32(a) (*(volatile uint32_t *)(a))

/* Gain at full VOL, centred: the proof mix's 1/4 per part, so sixteen
 * parts at full scale cannot clip the Q23 sum (md_glue.asm gmixlp). The
 * constant is 127^2 * 32768 * sqrt(2)... / 0x200000 rounded: vol^2 * pan
 * / 252 is 0x200000 * (vol/127)^2 * (pan/32768) within 0.01%. */
#define MD_GAIN_DIV 252u

unsigned md_engine_ok(unsigned id) {
    return id < MD_ENGINE_IDS && md_engines[id].handler
        && (md_engines[id].flags & MD_ENGINE_PLAYABLE);
}

uint32_t md_gain(unsigned vol, unsigned pan, unsigned right, unsigned muted) {
    if (muted) return 0;
    if (vol > 127) vol = 127;
    if (pan > 127) pan = 127;
    unsigned q = md_pan_q15[right ? 127 - pan : pan];
    return (uint32_t)vol * vol * q / MD_GAIN_DIV;
}

void md_params(const MdPart *part, const MdSeq *q, unsigned p, uint16_t out[MD_SYN]) {
    /* The MD's voice update: live kit byte << 7 (0x20afac-0x20afb4); a
     * locked value replaces the kit's until the part's next trig. */
    for (unsigned i = 0; i < MD_SYN; ++i) {
        unsigned v = (q->lock_mask[p] >> i) & 1 ? q->lock_val[p][i] : part->syn[i];
        out[i] = (uint16_t)((v & 0x7f) << 7);
    }
}

/* The kit a Part starts with (a choice, not the MD's: its boot kit holds
 * E12 machines, which the OT cannot play). Eight TRX voices and eight empty
 * parts: every assigned engine renders on every period whether it sounds
 * or not, and a full sixteen-engine kit's cost on core 1 is not measured on
 * the unit yet (WP-A6), so the default stays at half. Descriptor defaults,
 * VOL 100, PAN centre, as an MD engine assignment sets them. */
static const uint8_t md_default_engines[MD_PARTS] = {
    0x10, 0x11, 0x16, 0x17, 0x13, 0x14, 0x15, 0x18,   /* TRX BD SD CH OH CP RS CB CY */
};

/* A kit nothing was ever assigned to: every part GND--- at VOL 0. A kit
 * the user made always has a VOL (an engine assignment sets 100). */
unsigned md_kit_empty(const MdKit *kit) {
    for (unsigned p = 0; p < MD_PARTS; ++p)
        if (kit->part[p].engine || kit->part[p].vol) return 0;
    return 1;
}

void md_default_kit(MdKit *kit) {
    for (unsigned p = 0; p < MD_PARTS; ++p) {
        MdPart *part = &kit->part[p];
        unsigned id = md_default_engines[p];
        part->engine = (uint8_t)id;
        part->vol = 100;
        part->pan = 64;
        part->flags = 0;
        for (unsigned i = 0; i < MD_SYN; ++i)
            part->syn[i] = md_engine_ok(id) ? md_engines[id].defaults[i] : 0;
    }
}

/* ---- the clock: Euclid's, the firmware's own units ---------------------- */
void md_clock_start(MdClock *c, uint32_t now) {
    c->now = now;
    c->quantum = c->remainder = 0;
    ++c->epoch;
    c->initialized = 1;
}

void md_clock_update(MdClock *c, uint32_t now) {
    if (!c->initialized) { md_clock_start(c, now); return; }
    int32_t delta = (int32_t)(now - c->now);
    c->now = now;
    int32_t rem = (int32_t)c->remainder + delta;
    while (rem < 0) { --c->quantum; rem += MD_QUANTUM; }
    while (rem >= (int32_t)MD_QUANTUM) { ++c->quantum; rem -= MD_QUANTUM; }
    c->remainder = (uint32_t)rem;
}

/* ---- the lanes ----------------------------------------------------------- */
typedef struct {
    unsigned scale, length, swing;
    uint32_t mask_lo, mask_hi;
} MdGrid;

static void parent_grid(MdGrid *g, unsigned track) {
    volatile uint8_t *pattern = (volatile uint8_t *)(OT_BANK_BLOB
        + U8(OT_SEQ_BANK) * OT_BANK_STRIDE + U8(OT_SEQ_PATTERN) * OT_PATTERN_STRIDE);
    volatile uint8_t *tr = pattern + track * OT_TRACK_STRIDE;
    static const uint8_t scales[7] = {3, 4, 6, 8, 12, 24, 48};
    unsigned per_track = pattern[OT_PATTERN_SCALE_MODE];
    unsigned scale_idx = per_track ? tr[OT_TRACK_SCALE] : pattern[OT_PATTERN_SCALE];
    unsigned length = per_track ? tr[OT_TRACK_LENGTH] : pattern[OT_PATTERN_LENGTH];
    g->scale = scales[scale_idx < 7 ? scale_idx : 2];
    g->length = length && length <= MD_STEPS ? length : 16;
    g->swing = tr[OT_TRACK_SWING] < 30 ? tr[OT_TRACK_SWING] : 30;
    g->mask_hi = *(volatile uint32_t *)(tr + OT_TRACK_SWING_MASK_HI);
    g->mask_lo = *(volatile uint32_t *)(tr + OT_TRACK_SWING_MASK_LO);
}

/* Euclid's swing_at (stock 0x4009d3e0): the delay of the step at q quanta. */
static uint32_t swing_at(const MdGrid *g, uint32_t q, uint32_t period) {
    unsigned step = q / period % g->length;
    unsigned m = step < 32 ? (g->mask_lo >> step) & 1 : (g->mask_hi >> (step - 32)) & 1;
    return m ? g->swing * 52920u * g->scale : 0;
}

static void fire(MdSeq *q, unsigned step, unsigned bank_pattern) {
    const MdPattern *pat = &md_patterns[bank_pattern];
    uint16_t mask = 0;
    for (unsigned p = 0; p < MD_PARTS; ++p)
        if ((pat->trig[p][step >> 5] >> (step & 31)) & 1) mask |= (uint16_t)(1u << p);
    if (!mask) return;
    uint16_t held_gain = 0;
    for (unsigned p = 0; p < MD_PARTS; ++p)
        if ((mask >> p) & 1) {
            if (q->lock_mask[p] & ((1u << MD_LOCK_VOL) | (1u << MD_LOCK_PAN)))
                held_gain |= (uint16_t)(1u << p);
            q->lock_mask[p] = 0;
        }
    for (unsigned i = 0; i < MD_LOCKS; ++i) {
        const MdLock *l = &pat->lock[i];
        if (l->part >= MD_PARTS || l->step != step || l->param >= MD_LOCK_PARAMS
            || !((mask >> l->part) & 1))
            continue;
        q->lock_mask[l->part] |= (uint16_t)(1u << l->param);
        q->lock_val[l->part][l->param] = l->value & 0x7f;
        if (l->param >= MD_LOCK_VOL) held_gain |= (uint16_t)(1u << l->part);
    }
    md_run.trig |= mask;
    md_run.lock_gain |= held_gain;
    ++q->steps;
}

void md_seq_frame(MdSeq *q, const MdClock *c, unsigned running) {
    MdGrid g;
    parent_grid(&g, q->parent);
    uint32_t period = 2u * g.scale;            /* one track step, in quanta */
    unsigned bank_pattern = (U8(OT_SEQ_BANK) & 15) * 16u + (U8(OT_SEQ_PATTERN) & 15);
    if (q->epoch != c->epoch) {                /* PLAY: step 1 on stock's anchor */
        q->epoch = c->epoch;
        q->next = 0;
        q->period = period;
        q->steps = 0;
    } else if (period != q->period) {          /* a scale edit: the next grid point */
        q->next = (c->quantum / period + 1) * period;
        q->period = period;
    }
    q->running = (uint8_t)running;
    if (!running) return;
    /* Selecting the machine mid-song: join at the next step, no backlog. */
    if ((int32_t)(c->quantum - q->next) > (int32_t)(2 * period))
        q->next = (c->quantum / period + 1) * period;
    /* One frame early: the record reaches core 1 on the next frame, and the
     * driver renders it at the slot's next half-period. */
    int32_t ahead = (int32_t)(U32(MD_TEMPO24) * 16u);
    for (unsigned budget = 0; budget < 3; ++budget) {
        int32_t distance = (int32_t)(q->next - c->quantum) * (int32_t)MD_QUANTUM
                         + (int32_t)swing_at(&g, q->next, period) - (int32_t)c->remainder;
        if (distance > ahead) break;
        unsigned step = q->next / period % g.length;
        q->next += period;
        q->last_step = (uint8_t)step;
        q->pattern = (uint8_t)bank_pattern;
        fire(q, step, bank_pattern);
    }
}

static unsigned same_part(const MdPart *a, const MdPart *b) {
    const uint8_t *x = (const uint8_t *)a, *y = (const uint8_t *)b;
    for (unsigned i = 0; i < sizeof(MdPart); ++i)
        if (x[i] != y[i]) return 0;
    return 1;
}

static void clear_record(uint32_t *record) {
    for (unsigned i = 0; i < MD_RECORD_LONGS; ++i) record[i] = 0;
}

/* Take requests set by other contexts: or.l into memory is one
 * instruction, but reading and clearing is two, so mask interrupts. */
static uint32_t take_trig_requests(void) {
    uint16_t sr;
    __asm__ volatile ("move.w %%sr,%0\n\tmove.w #0x2700,%%sr" : "=d"(sr));
    uint32_t bits = md_trig_request;
    md_trig_request = 0;
    __asm__ volatile ("move.w %0,%%sr" : : "d"(sr));
    return bits & 0xffffu;
}

/* Apply kit edits: an engine change starts from a zeroed record (the MD
 * keeps the previous machine's words; nothing sent depends on them, since
 * every handler writes the words it returns), a synthesis change rebuilds
 * the record, and VOL/PAN/mute change the gain pair. */
static void apply_kit(MdRun *r) {
    for (unsigned p = 0; p < MD_PARTS; ++p) {
        const MdPart *now = &md_kit_cur()->part[p];
        MdPart *was = &r->shadow[p];
        if (r->started && same_part(now, was)) continue;
        if (!r->started || now->engine != was->engine) {
            clear_record(r->record[p]);
            r->resend |= 1u << p;
        }
        for (unsigned i = 0; i < MD_SYN; ++i)
            if (!r->started || now->syn[i] != was->syn[i]) r->resend |= 1u << p;
        if (!r->started || now->vol != was->vol || now->pan != was->pan
            || ((now->flags ^ was->flags) & MD_PART_MUTE))
            r->gains |= 1u << p;
        *was = *now;
    }
    r->started = 1;
}

/* Run the part's handler as the MD's voice update does: the trigger flag in
 * word 0 during the call, the returned count, and the id + 1 on the wire. */
static unsigned build_record(MdRun *r, unsigned p, unsigned trig) {
    unsigned id = r->shadow[p].engine;
    if (!md_engine_ok(id)) id = 0;              /* silent: GND--- */
    uint16_t params[MD_SYN];
    md_params(&r->shadow[p], &md_lanes, p, params);
    uint32_t *record = r->record[p];
    record[0] = trig ? 1u : 0u;
    unsigned count = md_engines[id].handler(record, params);
    if (count > MD_RECORD_LONGS) count = MD_RECORD_LONGS;
    return count;
}

static void part_gains(const MdRun *r, unsigned p, uint32_t *left, uint32_t *right) {
    const MdPart *s = &r->shadow[p];
    unsigned vol = s->vol, pan = s->pan, held = md_lanes.lock_mask[p];
    if ((held >> MD_LOCK_VOL) & 1) vol = md_lanes.lock_val[p][MD_LOCK_VOL];
    if ((held >> MD_LOCK_PAN) & 1) pan = md_lanes.lock_val[p][MD_LOCK_PAN];
    unsigned muted = s->flags & MD_PART_MUTE;
    *left = md_gain(vol, pan, 0, muted);
    *right = md_gain(vol, pan, 1, muted);
}

typedef struct {
    uint16_t *body;                  /* packet halfwords, after the header */
    unsigned used, npkt;
} Chunk;

static unsigned room(const Chunk *c, unsigned words) {
    return c->used + 2 + 2 * words <= MD_MBOX_HW - 3 && c->npkt < 64;
}

static void put(Chunk *c, unsigned dest, const uint32_t *words, unsigned n,
                uint32_t first) {
    uint16_t *o = c->body + c->used;
    *o++ = (uint16_t)dest;
    *o++ = (uint16_t)n;
    for (unsigned i = 0; i < n; ++i) {
        uint32_t w = (i == 0 ? first : words[i]) & 0xffffffu;
        *o++ = (uint16_t)(w >> 16);
        *o++ = (uint16_t)w;
    }
    c->used += 2 + 2 * n;
    ++c->npkt;
}

const uint16_t *md_ctl_chunk(void) {
    MdRun *r = &md_run;
    /* The first blocks after boot never reach the glue: the DSP's frame
     * dispatch starts a few frames after the ColdFire's (measured under the
     * port, WP-C1: the first block is not taken, two frames have no FX
     * call). Hold everything until it runs; a kit activated then would
     * otherwise lose its first trigs and gains. */
    if (++r->frames < MD_START_FRAMES) return 0;
    md_handler_sram_word = *(volatile uint32_t *)MD_TEMPO24;
    /* The Part the UI shows has its own kit; a Part change is a kit change,
     * which apply_kit sends like any edit. */
    md_kit_index = (U8(OT_UI_BANK) & 15) * 4u + (U8(OT_PART_IDX) & 3);
    md_persist_frame();
    /* Is a Part's MD track packed? The frame builder's hook says which. */
    unsigned parent = md_ui_frame();
    md_parent_track = 0;
    if (parent) {
        md_lanes.parent = (uint8_t)(parent - 1);
        r->parent_age = 1;           /* 0: never seen (zeroed at boot) */
    } else if (r->parent_age && r->parent_age < 255) {
        ++r->parent_age;
    }
    unsigned machine = r->parent_age && r->parent_age <= 8;
    if (machine && md_kit_empty(md_kit_cur()))
        md_default_kit(md_kit_cur());   /* a Part's first MD assignment */
    unsigned active = md_kit_active || machine;
    if (active) {
        md_clock_update(&md_clock, U32(OT_FRAME_CLOCK));
        md_seq_frame(&md_lanes, &md_clock, U32(OT_TRANSPORT) == 1);
        apply_kit(r);
        r->trig |= (uint16_t)take_trig_requests();
        r->gains |= r->lock_gain;    /* a trig's VOL/PAN lock, or its release */
        r->lock_gain = 0;
    } else {
        r->trig = r->resend = r->gains = 0;
        r->started = 0;              /* activation applies the whole kit */
    }

    Chunk c = { r->chunk + 3, 0, 0 };
    /* 1. Gains: the setter's (md_gain_set) and the kit's VOL/PAN. */
    for (unsigned p = 0; p < MD_PARTS; ++p) {
        uint32_t bit = 1u << p;
        if (!((md_gain_dirty | r->gains) & bit)) continue;
        if (c.used + 8 > MD_MBOX_HW - 3 || c.npkt + 2 > 64) { ++r->deferred; break; }
        uint32_t left, right;
        if (md_gain_dirty & bit) {
            left = md_gain_values[p][0];
            right = md_gain_values[p][1];
            md_gain_dirty &= ~bit;
        } else {
            part_gains(r, p, &left, &right);
            r->gains &= (uint16_t)~bit;
        }
        put(&c, MD_GAIN_LEFT + p, &left, 1, left);
        put(&c, MD_GAIN_RIGHT + p, &right, 1, right);
    }
    /* 2. Trigs, then 3. edited records; what does not fit waits a frame. */
    for (unsigned pass = 0; pass < 2; ++pass) {
        uint16_t *mask = pass ? &r->resend : &r->trig;
        for (unsigned p = 0; p < MD_PARTS && *mask; ++p) {
            uint16_t bit = (uint16_t)(1u << p);
            if (!(*mask & bit)) continue;
            if (!room(&c, MD_RECORD_LONGS)) { ++r->deferred; break; }
            unsigned trig = pass == 0;
            unsigned n = build_record(r, p, trig);
            unsigned id = md_engine_ok(r->shadow[p].engine) ? r->shadow[p].engine : 0;
            uint32_t first = trig && r->record[p][0] ? id + 1 : 0;
            put(&c, MD_VOICE_BASE + 0x40u * p, r->record[p], n, first);
            r->record[p][0] = 0;          /* sent: the next record is not a trig */
            *mask &= (uint16_t)~bit;
            r->resend &= (uint16_t)~bit;  /* a trig record carries any edit */
            if (trig) ++r->trigs;
        }
    }
    /* 4. One idle refresh a frame: the part's last words and its gain pair
     * again, not a trig. The MD resends every voice about every 384 samples
     * (12 periods); a refresh here also repairs a block the DSP did not
     * take, so only a trig can be lost for good. */
    if (active && !c.npkt) {
        unsigned p = r->refresh++ & (MD_PARTS - 1);
        uint32_t left, right;
        part_gains(r, p, &left, &right);
        put(&c, MD_GAIN_LEFT + p, &left, 1, left);
        put(&c, MD_GAIN_RIGHT + p, &right, 1, right);
        unsigned n = build_record(r, p, 0);
        put(&c, MD_VOICE_BASE + 0x40u * p, r->record[p], n, 0);
    }
    if (!c.npkt) return 0;
    r->packets += c.npkt;
    r->chunk[0] = 0;                 /* flags: no half sync */
    r->chunk[1] = (uint16_t)c.npkt;
    r->chunk[2] = (uint16_t)c.used;
    uint16_t *end = c.body + c.used;
    end[0] = 0; end[1] = 0xffff; end[2] = 0;   /* md_feed's end marker */
    return r->chunk;
}
