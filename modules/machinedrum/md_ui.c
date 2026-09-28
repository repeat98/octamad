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
_Static_assert(sizeof(MdFocus) == 296, "md_ui_tail.s focus allocation");

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
    OT_DRAW_PAGE = 0x4004d780u,      /* the main page (a page switch: 0x4005577e) */
    OT_DRAW_KNOBS = 0x4004d948u,     /* (slot): its knobs, -1 all */
    KEY_YES = 0x31u, KEY_FUNC = 0x2du,
};
typedef void (*KeyFn)(unsigned code, unsigned edge);
typedef void (*LayerFn)(volatile uint32_t *layer);
static unsigned held(unsigned code) {
    return U8(OT_KEY_ROWS + (code >> 3)) >> (code & 7) & 1u;
}

/* ---- WP-D8: the ENGINE window ---------------------------------------
 * YES on the MD track's SRC page opens it at the menu window's size
 * (118 x 64, as tempo-bus's): the selected part's engines by family on the
 * left, the highlighted engine's description and its eight parameter names
 * on the right. UP/DOWN move, LEFT/RIGHT change family, LEVEL scrolls, a
 * trig selects that part, FUNC+YES previews (md_preview: the part plays the
 * highlighted engine with its defaults, the kit unchanged), YES takes it,
 * NO leaves. It is made and closed the way the stock scrolling list makes
 * its popup (0x4006d94c, 0x4006d754) and drawn with the calls its refresh
 * makes (0x4006d784): the surface is the window + 36, {w, h}, y counted
 * from the bottom, a text's y its bottom row, rows 7 pixels apart. */
enum {
    OT_WIN_NEW = 0x4005829cu,        /* (w, h, 0, 0, 3, closed) -> the window */
    OT_WIN_SHOW = 0x40056f4cu,       /* (window) */
    OT_WIN_FREE = 0x40055db4u,       /* (&window): frees it, zeroes the cell */
    OT_SCREEN_DIRTY = 0x46c7c72cu,
    OT_CLEAR = 0x40035624u,          /* (surface) */
    OT_FONT = 0x400ba876u,
    OT_TEXT = 0x40012bd8u,           /* (font, surface, x, y, limit, text) */
    OT_RULE = 0x40011910u,           /* (surface, x, y, x2, 1) */
    OT_INVERT = 0x40012254u,         /* (surface, x1, top, x2, bottom, -1) */
    WIN_W = 118, WIN_H = 64, ROWS = 6,
    KEY_UP = 0x33u, KEY_DOWN = 0x20u, KEY_LEFT = 0x34u, KEY_RIGHT = 0x21u, KEY_NO = 0x32u,
};
typedef void (*TextFn)(uint32_t font, uint32_t surf, int x, int y, int limit, const char *t);

static void text(uint32_t surf, int x, int y, const char *t) {
    ((TextFn)OT_TEXT)(OT_FONT, surf, x, y, -1, t);
}

static void name6(char *o, unsigned id) {
    const char *n = md_engines[id].name;
    for (unsigned i = 0; i < 6; ++i) o[i] = n[i] ? n[i] : ' ';
    o[6] = 0;
}

/* Ours, not the MD's: what the name and the parameter names make certain. */
static const char *eng_desc(unsigned id) {
    static const char keys[] = "BDB2SDS2XTCPRSCBCHOHHHCYMACLRCCCSNNSIM--";
    static const char *const say[] = {
        "Bass drum", "Bass drum 2", "Snare drum", "Snare drum 2", "Tom", "Hand clap",
        "Rim shot", "Cowbell", "Closed hi-hat", "Open hi-hat", "Hi-hat", "Cymbal",
        "Maracas", "Claves", "Ride cymbal", "Crash cymbal", "Sine", "Noise", "Impulse",
        "Silent"};
    const char *n = md_engines[id].name;
    for (unsigned i = 0; i < sizeof say / sizeof say[0]; ++i)
        if (keys[2 * i] == n[4] && keys[2 * i + 1] == n[5]) return say[i];
    return "Percussion";
}

static const char *fam_name(unsigned id) {
    switch (id >> 4) {
    case 0: return "GND  basic tones";
    case 1: return "TRX  analog drums";
    case 2: return "EFM  FM drums";
    case 4: return "P-I  physical models";
    default: return "";
    }
}

static unsigned fam_first(const MdFocus *f, unsigned i) {
    while (i && f->ids[i - 1] >> 4 == f->ids[i] >> 4) --i;
    return i;
}

static unsigned fam_end(const MdFocus *f, unsigned i) {
    unsigned fam = f->ids[i] >> 4u;
    while (i < f->n && f->ids[i] >> 4u == fam) ++i;
    return i;
}

static void eng_draw(void) {
    MdFocus *f = &md_focus;
    if (!f->win) return;
    uint32_t surf = f->win + 36;
    int h = (int)U32(surf + 4);
    ((void (*)(uint32_t))OT_CLEAR)(surf);
    char buf[16], nm[8];
    unsigned p = md_ui.sel & (MD_PARTS - 1), id = f->ids[f->cur];
    /* the header: the part, then the family (nothing against the right
     * edge, which the screen clips; about 4 pixels a character) */
    buf[0] = 'P'; buf[1] = (char)('0' + (p + 1) / 10); buf[2] = (char)('0' + (p + 1) % 10);
    buf[3] = 0;
    text(surf, 3, h - 9, buf);
    text(surf, 24, h - 9, fam_name(id));
    ((void (*)(uint32_t, int, int, int, int))OT_RULE)(surf, 2, h - 12, WIN_W - 3, 1);
    /* the family's engines, the cursor inverted */
    unsigned first = fam_first(f, f->cur), end = fam_end(f, f->cur);
    if (f->top < first || f->top > f->cur) f->top = (uint8_t)(f->cur < first + ROWS ? first : f->cur);
    if (f->cur >= f->top + ROWS) f->top = (uint8_t)(f->cur - ROWS + 1);
    for (unsigned r = 0; r < ROWS && f->top + r < end; ++r) {
        int y = h - 20 - 7 * (int)r;
        unsigned i = f->top + r;
        name6(nm, f->ids[i]);
        text(surf, 4, y, nm);
        if (i == f->cur)
            ((void (*)(uint32_t, int, int, int, int, int))OT_INVERT)(surf, 2, y + 5, 42, y - 1, -1);
    }
    /* the highlighted engine: what it is and its parameters */
    text(surf, 48, h - 20, eng_desc(id));
    const MdEngine *e = &md_engines[id];
    for (unsigned r = 0; r < 4; ++r)
        for (unsigned c = 0; c < 2; ++c) {
            const char *pn = e->names[2 * r + c];
            unsigned k = 0;
            for (; k < 4 && pn[k]; ++k) buf[k] = pn[k];
            buf[k] = 0;
            if (k) text(surf, 48 + 26 * (int)c, h - 29 - 7 * (int)r, buf);
        }
    text(surf, 48, 2, "FUNC+YES:PLAY");
    U32(OT_SCREEN_DIRTY) = 1;
}

void md_eng_close(void) {
    MdFocus *f = &md_focus;
    if (!f->win) return;
    ((void (*)(volatile uint32_t *))OT_WIN_FREE)(&f->win);
    ((LayerFn)OT_LAYER_POP)(md_eng_layer);
    md_preview = 0;
    U32(OT_SCREEN_DIRTY) = 1;
    md_ui.redraw = 1;
}

static void eng_open(void) {
    MdFocus *f = &md_focus;
    if (f->win) return;
    if (!f->n) f->n = (uint8_t)choices(f->ids);
    f->cur = (uint8_t)choice_of(md_kit_cur()->part[md_ui.sel & (MD_PARTS - 1)].engine);
    f->top = 0xff;
    f->win_mine = 0;
    f->win = ((uint32_t (*)(int, int, int, int, int, void (*)(void)))OT_WIN_NEW)
             (WIN_W, WIN_H, 0, 0, 3, md_eng_close);
    if (!f->win) return;
    ((void (*)(uint32_t))OT_WIN_SHOW)(f->win);
    md_eng_layer[0] = 0;
    ((LayerFn)OT_LAYER_PUSH)(md_eng_layer);
    eng_draw();
}

static void eng_move(int d) {
    MdFocus *f = &md_focus;
    int i = (int)f->cur + d;
    if (i < 0) i = 0;
    if (i >= (int)f->n) i = (int)f->n - 1;
    f->cur = (uint8_t)i;
    eng_draw();
}

/* The window's keys (md_ui_tail.s md_eng_layer). */
void md_eng_key(unsigned code, unsigned edge) {
    MdFocus *f = &md_focus;
    if (code < 16) {                                  /* trigs: the part */
        unsigned bit = 1u << code;
        if (edge == 1 && !U32(OT_GRID_REC) && !held(KEY_FUNC) && !U32(OT_TRIG_MODE)) {
            f->win_mine |= bit;
            md_ui_select(code);
            f->cur = (uint8_t)choice_of(md_kit_cur()->part[code].engine);
            if (md_preview >> 31) md_preview = 0;
            eng_draw();
        } else if (edge != 1 && (f->win_mine & bit)) {
            if (!edge) f->win_mine &= ~bit;
        } else {
            ((KeyFn)0x40060ce0u)(code, edge);         /* stock's trig handler */
        }
        return;
    }
    if (edge != 1 && !(edge == 2 && (code == KEY_UP || code == KEY_DOWN))) return;
    unsigned p = md_ui.sel & (MD_PARTS - 1);
    switch (code) {
    case KEY_UP: eng_move(-1); break;
    case KEY_DOWN: eng_move(1); break;
    case KEY_LEFT: {
        unsigned first = fam_first(f, f->cur);
        f->cur = (uint8_t)(first ? fam_first(f, first - 1) : first);
        eng_draw();
        break;
    }
    case KEY_RIGHT: {
        unsigned end = fam_end(f, f->cur);
        if (end < f->n) f->cur = (uint8_t)end;
        eng_draw();
        break;
    }
    case KEY_YES:
        if (held(KEY_FUNC)) {                         /* preview */
            md_preview = 0x80000000u | p << 8 | f->ids[f->cur];
            md_trig_request |= 1u << p;
        } else {                                      /* take it */
            MdPart *kp = &md_kit_cur()->part[p];
            if (kp->engine != f->ids[f->cur]) set_engine(kp, f->ids[f->cur]);
            md_eng_close();
        }
        break;
    case KEY_NO: md_eng_close(); break;
    default: break;                                   /* held while open */
    }
}

void md_eng_level(unsigned index, int delta) {
    (void)index;
    if (delta) eng_move(delta > 0 ? 1 : -1);
}

void md_layer_key(unsigned code, unsigned edge) {
    MdFocus *f = &md_focus;
    unsigned k = code < 16 ? code : 16u, bit = 1u << k;
    if (edge == 1) {
        if (f->on && !md_layer[0] && !U32(OT_GRID_REC) && !held(KEY_FUNC)
            && (k == 16 || !U32(OT_TRIG_MODE))) {
            f->mine |= bit;
            if (k < 16) md_ui_select(code);
            else eng_open();
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
