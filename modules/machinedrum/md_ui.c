/* The Machinedrum's editor on the stock pages (WP-D4, WP-D5, WP-D6).
 *
 * The MD track is a FLEX track with a signature (md_machine.s). Its editor
 * is the stock UI, with the MD state mirrored in and out once a frame:
 *
 *  - the page: the PLAYBACK descriptor the MD track uses is a copy of
 *    FLEX's (made here at run time from the image in RAM, so no Elektron
 *    byte is in the repository) with the selected part's engine: SYN 1-6
 *    on page 1, SYN 7, SYN 8, VOL, PAN and ENG on page 2 (SRC SETUP), every
 *    slot 0..127 on a plain dial. Its values are the track's FLEX slot in
 *    the Part; a knob turn lands there, and this reads it back into the
 *    selected part;
 *  - the lane: the MD track's own OT trig mask in the UI pattern shows the
 *    selected part's lane. Grid recording, live recording, the trig LEDs
 *    and the step pages all edit that mask; this copies an edit back into
 *    the MD pattern, and a new selection or pattern into the mask;
 *  - the part: holding the MD track's key and pressing a trig selects that
 *    part and plays it (md_machine.s md_trig_key -> md_ui_select);
 *  - the name: where stock names the track's machine, an MD track shows
 *    the selected part and its engine, "P05 TRX-SD" (md_ui_name).
 *
 * Interrupt context (md_ctl_chunk): reads of the Part and pattern race the
 * UI task byte by byte, which a mirror tolerates; the writes happen only
 * on a selection, engine, pattern or track change. */
#include "md_ctl.h"

_Static_assert(sizeof(MdUi) == 40 + MD_DESC_BYTES + 2, "md_ctl_tail.s ui allocation");
_Static_assert(sizeof(MdFocus) == 1456, "md_ui_tail.s focus allocation");

#define U8(a) (*(volatile uint8_t *)(a))
#define U32(a) (*(volatile uint32_t *)(a))

enum {
    OT_BANK_PTR = 0x46c82456u,       /* the UI bank's blob */
    OT_PART_IDX = 0x100b14cfu,       /* the active Part */
    OT_UI_TRACK = 0x100b14ccu,       /* the selected track */
    OT_UI_BANK = 0x80000002u,
    OT_UI_PATTERN = 0x80000004u,
    OT_PART_OFF = 0x8ed80u,
    OT_PART_STRIDE = 0x18b2u,
    OT_SRAM_PART = 0x100a4eceu,
    OT_PAGE1 = 0x2au,                /* + track x 30 + machine x 6 */
    OT_PAGE2 = 0x1dau,
    OT_SIG = 0x2au + 18u,            /* NEIGHBOR's page-1 slot: md_machine.s */
    OT_LANE = 0x80000810u,           /* + track x 72: the live lane */
    OT_LANE_P2 = 0x20u,
    OT_PATTERN_STRIDE = 0x8ed8u,
    OT_TRACK_STRIDE = 0x91au,
    OT_FLEX_E = 0x400d3176u,         /* stock FLEX playback descriptor (E) */
    OT_FLEX_P = 0x400d31aeu,
    OT_EMPTY_P = 0x400d34d2u,        /* NEIGHBOR's page: stock's entries 5 and 6 */
    OT_PB_TABLE = 0x400d5f38u,       /* seven entries, by machine row */
    OT_ENC_CFG = 0x46c7dedeu,        /* per-encoder config, 20 bytes a slot */
    OT_ENC_STRIDE = 20u,
    OT_SETUP_EDIT = 0x4003a474u,     /* the SRC SETUP window's editor */
    OT_SETUP_ROW = 0x460d5c30u,      /* the machine row that window edits */
};
#define FLEX 1u
#define MD_ROW 5u                    /* md_machine.s: MACHINEDRUM's row in both lists */

/* Descriptor fields, E-relative (PARAM_PAGES.md section 2). */
enum { D_ABBR = 0x3c, D_NAME = 0x41, D_PNAME = 0x4e, D_DEFAULT = 0x96, D_MIN = 0xa2,
       D_COUNT = 0xd2, D_FMT = 0x102, D_WIDGET = 0x132, D_EN_HI = 0x38 + 0x18a,
       D_EN_LO = 0x38 + 0x18e };

static void put32(uint8_t *p, uint32_t v) {
    p[0] = (uint8_t)(v >> 24); p[1] = (uint8_t)(v >> 16);
    p[2] = (uint8_t)(v >> 8); p[3] = (uint8_t)v;
}

static unsigned is_md(const volatile uint8_t *part, unsigned t) {
    const volatile uint8_t *s = part + OT_SIG + 30u * t;
    return part[0x22 + t] == FLEX && s[0] == 'M' && s[1] == 'D' && s[2] == 1;
}

/* The engine choices on ENG: GND--- and every playable engine, by id. */
static unsigned choices(uint8_t *out) {
    unsigned n = 0;
    for (unsigned id = 0; id < MD_ENGINE_IDS; ++id)
        if (!id || md_engine_ok(id)) {
            if (out) out[n] = (uint8_t)id;
            ++n;
        }
    return n;
}

static unsigned choice_of(unsigned id) {
    uint8_t list[MD_ENGINE_IDS];
    unsigned n = choices(list);
    for (unsigned i = 0; i < n; ++i)
        if (list[i] == id) return i;
    return 0;
}

static unsigned engine_of(unsigned choice) {
    uint8_t list[MD_ENGINE_IDS];
    unsigned n = choices(list);
    return choice < n ? list[choice] : 0;
}

/* ENG's formatter (stock signature: buf, value): four characters, "T-BD". */
void md_eng_fmt(char *buf, int value) {
    unsigned id = engine_of((unsigned)value);
    const char *name = md_engines[id].name;
    if (!id) { buf[0] = buf[1] = buf[2] = buf[3] = '-'; buf[4] = 0; return; }
    buf[0] = name[0] == 'E' ? 'E' : name[0];
    buf[1] = '-';
    buf[2] = name[4];
    buf[3] = name[5];
    buf[4] = 0;
}

static void set_name(uint8_t *field, const char *src, unsigned len) {
    for (unsigned i = 0; i < 6; ++i)
        field[i] = (uint8_t)(i < len && src[i] ? src[i] : 0);
}

/* Build the MD page for engine `id`: a copy of FLEX's descriptor, every
 * slot 0..127 on a plain dial, names and defaults from the engine. */
static void build_desc(MdUi *u, unsigned id) {
    uint8_t *e = u->desc;
    const volatile uint8_t *flex = (const volatile uint8_t *)OT_FLEX_E;
    for (unsigned i = 0; i < MD_DESC_BYTES; ++i) e[i] = flex[i];
    set_name(e + D_ABBR, "SYN", 5);
    set_name(e + D_NAME, "SYNTH", 6);
    const MdEngine *eng = &md_engines[id];
    static const char *const page2[4] = {"VOL", "PAN", "ENG", "BURN"};
    uint32_t lo = 0, hi = 0;
    for (unsigned k = 0; k < 12; ++k) {
        const char *name;
        unsigned len = 4, on = 1, def = 0, count = 128;
        uint32_t fmt = 0;
        if (k < MD_SYN) {
            unsigned s = k < 6 ? k : k;        /* SYN k+1 */
            name = eng->names[s];
            def = eng->defaults[s];
            if (!name[0]) { name = "---"; on = 0; }
        } else {
            name = page2[k - MD_SYN];
            if (k == 8) def = 100;
            if (k == 9) def = 64;
            if (k == 10) { count = choices(0); fmt = (uint32_t)md_eng_fmt; def = 0; }
            if (k == 11 && !MD_BURN_BUILD) { name = "---"; on = 0; }
        }
        set_name(e + D_PNAME + 6 * k, name, len);
        e[D_DEFAULT + k] = (uint8_t)def;
        put32(e + D_MIN + 4 * k, 0);
        put32(e + D_COUNT + 4 * k, count);
        put32(e + D_FMT + 4 * k, fmt);
        put32(e + D_WIDGET + 4 * k, 0);
        if (k < 8) lo |= (uint32_t)on << (4 * k);
        else hi |= (uint32_t)on << (4 * (k - 8));
    }
    put32(e + D_EN_LO, lo);
    put32(e + D_EN_HI, hi);
    u->desc_engine = (uint8_t)id;
    md_desc_p = (uint32_t)(e + 0x38);
}

/* The twelve page values of part p: SYN 1-8, VOL, PAN, ENG, 0; the order
 * of the MD page's slots (page 1 = 0..5, page 2 = 6..11). */
static void page_values(unsigned p, uint8_t v[12]) {
    const MdPart *part = &md_kit_cur()->part[p];
    for (unsigned i = 0; i < MD_SYN; ++i) v[i] = part->syn[i];
    v[8] = part->vol;
    v[9] = part->pan;
    v[10] = (uint8_t)choice_of(part->engine);
    v[11] = MD_BURN_BUILD ? (uint8_t)(md_burn & 0x7f) : 0;
}

static volatile uint8_t *page_byte(volatile uint8_t *part, unsigned t, unsigned k) {
    unsigned base = k < 6 ? OT_PAGE1 : OT_PAGE2;
    return part + base + 30u * t + 6u * FLEX + (k < 6 ? k : k - 6);
}

static void write_page(volatile uint8_t *part, volatile uint8_t *sram, unsigned t,
                       const uint8_t v[12]) {
    volatile uint8_t *lane = (volatile uint8_t *)(OT_LANE + 72u * t);
    for (unsigned k = 0; k < 12; ++k) {
        *page_byte(part, t, k) = v[k];
        *page_byte(sram, t, k) = v[k];
        lane[k < 6 ? k : OT_LANE_P2 + k - 6] = v[k];
    }
}

/* An engine change loads the descriptor defaults, as the MD's assignment
 * does (MACHINEDRUM_MACHINE.md section 12). */
static void set_engine(MdPart *part, unsigned id) {
    if (id && !md_engine_ok(id)) id = 0;
    part->engine = (uint8_t)id;
    for (unsigned i = 0; i < MD_SYN; ++i)
        part->syn[i] = id ? md_engines[id].defaults[i] : 0;
}

static void page_mirror(MdUi *u, volatile uint8_t *part, volatile uint8_t *sram,
                        unsigned t, unsigned kit) {
    unsigned p = u->sel & (MD_PARTS - 1);
    MdPart *kp = &md_kit_cur()->part[p];
    if (u->shown_sel != p || u->shown_track != t || u->shown_part != kit
        || u->shown_engine != kp->engine || u->desc_engine != kp->engine) {
        build_desc(u, kp->engine);
        page_values(p, u->snap);
        write_page(part, sram, t, u->snap);
        u->shown_sel = (uint8_t)p;
        u->shown_track = (uint8_t)t;
        u->shown_part = (uint8_t)kit;
        u->shown_engine = kp->engine;
        u->redraw = 1;
        return;
    }
    for (unsigned k = 0; k < 12; ++k) {
        uint8_t now = *page_byte(part, t, k);
        if (now == u->snap[k]) continue;
        u->snap[k] = now;
        if (k < MD_SYN) kp->syn[k] = now & 0x7f;
        else if (k == 8) kp->vol = now & 0x7f;
        else if (k == 9) kp->pan = now & 0x7f;
        else if (k == 10) {
            set_engine(kp, engine_of(now));
            u->shown_engine = 0xff;          /* next frame: new names, values */
        }
        else if (k == 11 && MD_BURN_BUILD) md_burn = now & 0x7f;
    }
}

static void lane_mirror(MdUi *u, unsigned t) {
    unsigned bank = U8(OT_UI_BANK) & 15, pattern = U8(OT_UI_PATTERN) & 15;
    unsigned p = u->sel & (MD_PARTS - 1);
    volatile uint8_t *mask = (volatile uint8_t *)(U32(OT_BANK_PTR)
        + pattern * OT_PATTERN_STRIDE + t * OT_TRACK_STRIDE);
    MdPattern *pat = &md_patterns[bank * 16 + pattern];
    /* The OT's mask: a big-endian 64-bit word, step s = bit s. */
    if (u->lane_sel != p || u->lane_track != t || u->lane_bank != bank
        || u->lane_pattern != pattern) {
        for (unsigned b = 0; b < 8; ++b) {
            uint32_t w = pat->trig[p][b < 4 ? 1 : 0];
            uint8_t v = (uint8_t)(w >> (8 * (3 - (b & 3))));
            mask[b] = v;
            u->lane_snap[b] = v;
        }
        u->lane_sel = (uint8_t)p;
        u->lane_track = (uint8_t)t;
        u->lane_bank = (uint8_t)bank;
        u->lane_pattern = (uint8_t)pattern;
        return;
    }
    unsigned changed = 0;
    for (unsigned b = 0; b < 8; ++b)
        if (mask[b] != u->lane_snap[b]) { u->lane_snap[b] = mask[b]; changed = 1; }
    if (!changed) return;
    uint32_t hi = 0, lo = 0;
    for (unsigned b = 0; b < 4; ++b) {
        hi = hi << 8 | u->lane_snap[b];
        lo = lo << 8 | u->lane_snap[b + 4];
    }
    pat->trig[p][0] = lo;
    pat->trig[p][1] = hi;
}

static void make_name(MdUi *u) {
    unsigned p = u->sel & (MD_PARTS - 1);
    const char *name = md_engines[md_kit_cur()->part[p].engine].name;
    char *o = md_ui_name;
    o[0] = 'P';
    o[1] = (char)('0' + (p + 1) / 10);
    o[2] = (char)('0' + (p + 1) % 10);
    o[3] = ' ';
    for (unsigned i = 0; i < 6; ++i) o[4 + i] = name[i] ? name[i] : ' ';
    o[10] = 0;
    (void)u;
}

/* Stock turns an encoder's accumulated delta << 8 into steps of a per-slot
 * divisor (0x4003249c): 256 for a 0..127 knob, 819 for a select under 128
 * values, so ENG on SETUP's E would take about four detents per engine
 * (measured under the port, 25 Sep 2026). While that window edits the MD
 * track, one detent is one engine; the stock divisor comes back when it
 * edits anything else. */
static void eng_gearing(MdUi *u, unsigned md_page) {
    volatile uint32_t *e = (volatile uint32_t *)(OT_ENC_CFG + 4 * OT_ENC_STRIDE);
    if (e[0] != OT_SETUP_EDIT) return;
    if (md_page) {
        if (e[2] != 256u) { u->eng_div = (uint16_t)e[2]; e[2] = 256u; }
    } else if (u->eng_div && e[2] == 256u && e[4] < 128u) {
        e[2] = u->eng_div;
        u->eng_div = 0;
    }
}

void md_ui_select(unsigned key) {
    md_ui.sel = (uint8_t)(key & (MD_PARTS - 1));
    md_trig_request |= 1u << md_ui.sel;      /* play it, as the MD's pads do */
}

/* ---- WP-D7: MD focus -------------------------------------------------
 * The MD track's SRC page is the kit editor (the user's choice, 28 Sep
 * 2026). An input layer (md_ui_tail.s) takes the sixteen trig keys and YES
 * while that page is on screen with nothing open over it: a trig selects
 * and plays its part, as the MD's pads do, and YES opens the list of
 * engines. The rest of the OT is stock:
 *  - the layer is pushed only while the base layer is alone in the list
 *    (a window, menu or popup each adds its own: under the port 28 Sep
 *    2026, SRC SETUP's is 0x400bb7b4 over the base 0x400c090a), and a key
 *    acts only while nothing is above the layer;
 *  - a trig goes to stock with REC on, in any trig mode but 0 (holding
 *    PTN, BANK or a scene key changes it: patterns, banks, scenes) or with
 *    FUNC held; mode 0 is stock's manual trig of tracks 1-8 and the MIDI
 *    tracks (0x40044584), which the MD's pads replace on this page only;
 *  - a release goes where its press went (MAINMENU.md 6b: a swallowed
 *    release leaves the trig held and the sequencer will not stop).
 * The dispatcher calls a key handler (code, edge): 1 press, 0 release
 * (measured under the port on 0x40060ce0). */
enum {
    OT_PAGE_KIND = 0x46c7d8d8u,      /* SRC 0, LFO 1, AMP 2, FX1 3, FX2 4 */
    OT_LAYERS = 0x460d165cu,         /* the input layer list, the base first */
    OT_KEY_CACHE = 0x46c7d8deu,      /* + code x 24: press, release, repeat */
    OT_GRID_REC = 0x460d1736u,
    OT_TRIG_MODE = 0x460d16f0u,
    OT_KEY_ROWS = 0x46100b18u,       /* held keys: row code >> 3, bit code & 7 */
    OT_LAYER_PUSH = 0x40031494u,
    OT_LAYER_POP = 0x4003146cu,
    OT_LIST_OPEN = 0x4006d94cu,      /* (count, sel, &sel, labels, callbacks) */
    OT_DRAW_PAGE = 0x4004d780u,      /* the main page (a page switch: 0x4005577e) */
    OT_DRAW_KNOBS = 0x4004d948u,     /* (slot): its knobs, -1 all */
    KEY_YES = 0x31u, KEY_FUNC = 0x2du,
};
typedef void (*KeyFn)(unsigned code, unsigned edge);
typedef void (*LayerFn)(volatile uint32_t *layer);
typedef void (*ListFn)(unsigned n, unsigned sel, uint32_t *selp,
                       const char **labels, void (**cbs)(void));

static unsigned held(unsigned code) {
    return U8(OT_KEY_ROWS + (code >> 3)) >> (code & 7) & 1u;
}

/* The list closes itself, stores the selection and then calls this. */
static void eng_pick(void) {
    MdFocus *f = &md_focus;
    if (f->eng_sel < f->eng_n)
        set_engine(&md_kit_cur()->part[md_ui.sel & (MD_PARTS - 1)], f->ids[f->eng_sel]);
}

static void eng_list(void) {
    MdFocus *f = &md_focus;
    if (!f->eng_n) {
        f->eng_n = (uint8_t)choices(f->ids);
        for (unsigned i = 0; i < f->eng_n; ++i) {
            const char *name = md_engines[f->ids[i]].name;
            for (unsigned c = 0; c < 6; ++c)
                f->names[i][c] = name[0] && name[c] ? name[c] : '-';
            f->names[i][6] = 0;
            f->labels[i] = f->names[i];
            f->cbs[i] = eng_pick;
        }
    }
    f->eng_sel = choice_of(md_kit_cur()->part[md_ui.sel & (MD_PARTS - 1)].engine);
    ((ListFn)OT_LIST_OPEN)(f->eng_n, f->eng_sel, &f->eng_sel, f->labels, f->cbs);
}

void md_layer_key(unsigned code, unsigned edge) {
    MdFocus *f = &md_focus;
    unsigned k = code < 16 ? code : 16u, bit = 1u << k;
    if (edge == 1) {
        if (f->on && !md_layer[0] && !U32(OT_GRID_REC) && !held(KEY_FUNC)
            && (k == 16 || !U32(OT_TRIG_MODE))) {
            f->mine |= bit;
            if (k < 16) md_ui_select(code);
            else eng_list();
            return;
        }
    } else if (f->mine & bit) {
        if (!edge) f->mine &= ~bit;
        return;
    }
    uint32_t h = f->saved[k][edge == 1 ? 0 : edge == 0 ? 1 : 2];
    if (h + 1u > 1u) ((KeyFn)h)(code, edge);       /* 0: none (-1 is never cached) */
}

/* The UI task's display loop, once a tick (md_ui_tail.s md_tick_hook).
 * It also redraws the page when the interrupt side rebuilt it (a new part,
 * engine or kit: md_ui.redraw) the way a page switch draws it (0x4005577e:
 * the page, then every knob), and only while the layer is on top, so the
 * MD page is never drawn over a window. Stock's manual trig redraws screen
 * regions 7 and 0 instead (0x400502d4), which are the play state and the
 * bottom line, not the knobs (octemu, 28 Sep 2026). */
void md_ui_tick(void) {
    MdFocus *f = &md_focus;
    unsigned t = md_ui_md_track;
    unsigned want = t < 4 && U8(OT_UI_TRACK) == t && U8(OT_PAGE_KIND) == 0;
    if (f->on) {
        if ((!want || md_layer[0]) && !f->mine) {
            ((LayerFn)OT_LAYER_POP)(md_layer);
            f->on = 0;
        }
    } else {
        volatile uint32_t *base = (volatile uint32_t *)U32(OT_LAYERS);
        if (!want || !base || base[0]) return;      /* something over the base */
        for (unsigned k = 0; k < MD_FOCUS_KEYS; ++k)
            for (unsigned e = 0; e < 3; ++e)
                f->saved[k][e] = U32(OT_KEY_CACHE + 24u * (k < 16 ? k : KEY_YES) + 4u * e);
        md_layer[0] = 0;
        ((LayerFn)OT_LAYER_PUSH)(md_layer);
        f->on = 1;
    }
    if (f->on && !md_layer[0] && md_ui.redraw) {       /* as a page switch */
        md_ui.redraw = 0;
        ((void (*)(void))OT_DRAW_PAGE)();
        ((void (*)(int))OT_DRAW_KNOBS)(-1);
    }
}

/* Once a frame, before the producer: find the MD track, then mirror. */
unsigned md_ui_frame(void) {
    MdUi *u = &md_ui;
    unsigned part_idx = U8(OT_PART_IDX) & 3;
    volatile uint8_t *part = (volatile uint8_t *)(U32(OT_BANK_PTR) + OT_PART_OFF
                                                  + part_idx * OT_PART_STRIDE);
    volatile uint8_t *sram = (volatile uint8_t *)(OT_SRAM_PART + part_idx * OT_PART_STRIDE);
    int t = -1;
    for (unsigned i = 0; i < 4; ++i)
        if (is_md(part, i)) { t = (int)i; break; }
    md_ui_md_track = (uint32_t)t;
    if (t < 0) {
        md_ui_md_type = 0;
        U32(OT_PB_TABLE + 4 * MD_ROW) = OT_EMPTY_P;
        u->shown_sel = u->lane_sel = 0xff;
        eng_gearing(u, 0);
        return 0;
    }
    md_ui_md_type = (uint32_t)(part + 0x22 + t);
    make_name(u);
    page_mirror(u, part, sram, (unsigned)t, md_kit_index);   /* bank x 4 + part */
    /* The SETUP window's readers index the table by its cursor, on the
     * selected track: MACHINEDRUM's row is the MD page while that is the
     * MD track, which opens on that row (md_machine.s md_setup_open);
     * md_resolve_pb serves every track's own page by itself. */
    unsigned md_shown = U8(OT_UI_TRACK) == (unsigned)t && md_desc_p;
    U32(OT_PB_TABLE + 4 * MD_ROW) = md_shown ? md_desc_p : OT_EMPTY_P;
    eng_gearing(u, md_shown && U32(OT_SETUP_ROW) == MD_ROW);
    lane_mirror(u, (unsigned)t);
    return (unsigned)t + 1;
}
