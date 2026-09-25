/* The Machinedrum's control engine on the Octatrack ColdFire (WP-C4).
 *
 * One MD instance: a 16-part kit (engine, eight synthesis parameters, VOL,
 * PAN, mute), the MD's own per-engine descriptor handlers (WP-C2, linked
 * from the user's OS at build time), and the record producer that feeds
 * the WP-C1 transport. The MD's voice update (0x20ad9a in MD OS 1.63) is
 * the model:
 *   - a part's parameters reach its handler as 16-bit words, value << 7
 *     (the MD's live kit bytes shifted at 0x20afb0);
 *   - word 0 of the record is the trigger flag before the call (1 on a
 *     trig) and the engine id + 1 when a triggering record is sent (the
 *     SRAM sender at 0x1000550); 0 otherwise;
 *   - the handler returns the number of record words to send (the MD
 *     stores it in its count array 0x1001574 and sends that many);
 *   - the record goes to Y:0x800 + 0x40 * part (the MD's table 0x24ef14).
 * The MD's mixer DSP is not loaded: VOL and PAN become the OT-side gain
 * pair (md_glue.asm's GAIN/GAINR tables) with the MD's squared VOL law
 * (0x20b2c0: vol^2 >> 17) and a constant-power PAN (a choice; the MD's
 * mixer pan law is not read).
 *
 * No floating point, no runtime library calls, no .bss: the platform
 * runtime is an objcopy'd image, so every mutable word is explicit zeroed
 * storage in md_ctl_tail.s. Compile to the checked-in md_ctl.s with
 * generate_ctl.py. */
#ifndef MD_CTL_H
#define MD_CTL_H
#include <stdint.h>

#define MD_PARTS 16
#define MD_SYN 8
#define MD_ENGINE_IDS 0x49u          /* ids 0x00..0x48: GND through P-I */
#define MD_RECORD_LONGS 21           /* 84 bytes, the MD's per-track record */
#define MD_MBOX_HW 448               /* layout.py mbox_a: the block's halfwords */
#define MD_VOICE_BASE 0x800u         /* the MD's Y voice-record address */
#define MD_GAIN_LEFT 0xc00u          /* md_glue.asm: sixteen left, then right */
#define MD_GAIN_RIGHT 0xc10u
#define MD_TEMPO24 0x8000181cu       /* OT tempo: BPM x 24, latched per frame */
#define MD_START_FRAMES 16u          /* frames held after boot (md_ctl_chunk) */

/* Part flags. */
#define MD_PART_MUTE 0x01u

typedef struct {
    uint8_t engine;                  /* MD machine id; 0 = GND--- (silent) */
    uint8_t vol;                     /* 0..127 */
    uint8_t pan;                     /* 0..127, 64 = centre */
    uint8_t flags;                   /* MD_PART_* */
    uint8_t syn[MD_SYN];             /* synthesis parameters 1..8, 0..127 */
} MdPart;

typedef struct {
    MdPart part[MD_PARTS];
} MdKit;

/* One kit per OT Part (WP-E1): bank x 4 + part, as the Part itself. */
#define MD_KITS 64

/* Generated at build time from the user's MD OS (handler_build.py): one
 * row per machine id 0x00..0x48, zero where the id is not a machine. */
typedef uint32_t (*MdHandler)(uint32_t *record, const uint16_t *params);
typedef struct {
    MdHandler handler;               /* 0: no machine with this id */
    uint8_t defaults[MD_SYN];
    char names[MD_SYN][4];           /* four characters, not terminated */
    uint8_t flags;                   /* MD_ENGINE_* */
    uint8_t family;                  /* MD_FAMILY_* */
    char name[6];                  /* engine name, six characters (e.g. TRX-BD) */
} MdEngine;

#define MD_ENGINE_PLAYABLE 0x01u     /* the OT image can render it */
enum { MD_FAMILY_NONE, MD_FAMILY_GND, MD_FAMILY_TRX, MD_FAMILY_EFM,
       MD_FAMILY_E12, MD_FAMILY_PI };

/* The embedded sequencer (WP-D2's spec, WP-D3). One pattern per OT
 * pattern; the lanes use the parent track's clock, length, scale and swing.
 * A lock is (step, part, parameter, value): parameter 0..7 = SYN 1..8,
 * 8 = VOL, 9 = PAN; part 0xff marks a free entry. */
#define MD_STEPS 64
#define MD_LOCKS 64
#define MD_PATTERNS 256
#define MD_LOCK_PARAMS 10
#define MD_LOCK_VOL 8
#define MD_LOCK_PAN 9
#define MD_LOCK_FREE 0xffu
typedef struct { uint8_t step, part, param, value; } MdLock;
typedef struct {
    uint32_t trig[MD_PARTS][2];      /* bit s of lane p: [p][s >> 5] >> (s & 31) */
    MdLock lock[MD_LOCKS];
} MdPattern;

/* The firmware's clock units: one quarter note = 63,504,000 (Euclid's
 * EU_QUANTUM, 1/48 of a quarter, is the step grid's unit). */
#define MD_QUANTUM 1323000u
typedef struct {
    uint32_t now, quantum, remainder, epoch, initialized;
} MdClock;

typedef struct {
    uint32_t epoch;                  /* the clock epoch the lanes follow */
    uint32_t next;                   /* the next step, in quanta since PLAY */
    uint32_t period;                 /* one step, in quanta */
    uint32_t steps;                  /* steps played since PLAY */
    uint16_t lock_mask[MD_PARTS];    /* the held locks of each part's trig */
    uint8_t lock_val[MD_PARTS][MD_LOCK_PARAMS];
    uint8_t parent;                  /* 0..3, the MD track this frame */
    uint8_t running;
    uint8_t last_step;               /* the step index last played */
    uint8_t pattern;                 /* bank * 16 + pattern last played */
} MdSeq;

typedef struct {
    uint32_t record[MD_PARTS][MD_RECORD_LONGS];
    MdPart shadow[MD_PARTS];         /* the kit as last applied */
    uint32_t frames, packets, trigs, deferred, refused;
    uint16_t trig;                   /* trigs waiting to be sent */
    uint16_t resend;                 /* records whose words changed */
    uint16_t gains;                  /* gain pairs to send */
    uint8_t refresh;                 /* the next part for the idle refresh */
    uint8_t started;
    uint8_t parent_age;              /* 1 + frames since an MD track was packed; 0 never */
    uint8_t kit_ready;               /* unused since kits follow the Part (WP-E1) */
    uint16_t lock_gain;              /* parts whose gain follows a lock */
    uint16_t chunk[3 + MD_MBOX_HW + 3];  /* md_feed format, terminated */
} MdRun;

/* The stock-page editor's per-frame mirror and descriptor. The first 40
 * bytes are control and snapshots; the descriptor is copied from FLEX at
 * run time, so no firmware data is checked into this repository. */
#define MD_DESC_BYTES 0x1cau
typedef struct {
    uint8_t sel, shown_sel, shown_track, shown_part, shown_engine, desc_engine;
    uint8_t lane_sel, lane_track, lane_bank, lane_pattern;
    uint8_t snap[12], lane_snap[8];
    uint16_t eng_div;                /* SETUP E's stock divisor while ENG is geared */
    uint8_t pad[8];
    uint8_t desc[MD_DESC_BYTES + 2];
} MdUi;

extern MdUi md_ui;
extern volatile uint32_t md_desc_p, md_ui_md_track, md_ui_md_type;
extern char md_ui_name[12];
unsigned md_ui_frame(void);
void md_ui_select(unsigned key);

/* The engine table, the kits and the runtime (md_ctl_tail.s, handlers.s). */
extern const MdEngine md_engines[MD_ENGINE_IDS];
extern MdKit md_kits[MD_KITS];
/* The kit of the Part the UI shows (resident bank x 4 + active part), set
 * once a frame by md_ctl_chunk; the editor and the producer use it. */
extern volatile uint32_t md_kit_index;
static inline MdKit *md_kit_cur(void) { return &md_kits[md_kit_index & (MD_KITS - 1)]; }
unsigned md_kit_empty(const MdKit *kit);
extern MdRun md_run;
extern MdClock md_clock;
extern MdSeq md_lanes;
extern MdPattern md_patterns[MD_PATTERNS];
/* md_machine.s's frame hook: 1 + the MD track (T1..T4 = 1..4) each time the
 * frame builder packs an MD track, 0 otherwise; the producer clears it. */
extern volatile uint32_t md_parent_track;
extern volatile uint32_t md_trig_request; /* bits 0..15: parts to trigger */
/* Nonzero once a kit is in md_kit (assignment or project load). Until then
 * only md_gain_set's pairs are sent, and the glue's fixed-trigger proof
 * stays in charge: its first voice packet would retire it. */
extern volatile uint32_t md_kit_active;
extern uint32_t md_handler_sram_word;     /* the E12 handlers' tempo input */
/* md_xport.s's gain setter state: a dirty part is sent before any record. */
extern volatile uint32_t md_gain_dirty;
extern uint32_t md_gain_values[MD_PARTS][2];

/* The producer: called once per frame by md_xport.s (interrupt context).
 * Returns a chunk in md_feed's format, or 0 when nothing is to be sent. */
const uint16_t *md_ctl_chunk(void);

/* WP-E1 (md_persist.c): the resident bank's SRAM mirror, a little every
 * frame. The card side runs in the tasks that save and load the project. */
void md_persist_frame(void);

/* The PLAY hooks (md_ctl_tail.s) restart the lanes on stock's anchor. */
void md_clock_start(MdClock *c, uint32_t now);
void md_clock_update(MdClock *c, uint32_t now);
/* One frame of the sequencer: request this frame's trigs, set the locks. */
void md_seq_frame(MdSeq *q, const MdClock *c, unsigned running);

/* Pure helpers, exposed for the host tests. */
unsigned md_engine_ok(unsigned id);
uint32_t md_gain(unsigned vol, unsigned pan, unsigned right, unsigned muted);
void md_params(const MdPart *part, const MdSeq *q, unsigned p, uint16_t out[MD_SYN]);
void md_default_kit(MdKit *kit);
#endif
