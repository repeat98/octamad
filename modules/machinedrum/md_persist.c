/* The Machinedrum's persistence (WP-E1): the 64 kits (one per OT Part) and
 * the 256 patterns (one per OT pattern) follow stock's own two levels,
 * measured under octemu over the gdbstub on 25 Sep 2026:
 *
 *  - SRAM. The resident bank's working state lives in battery-backed SRAM:
 *    stock copies a bank there when it becomes resident (0x4000faf0, at a
 *    bank change and when a project load reads it) and restores it at boot
 *    (0x40025770), before it loads the other fifteen banks from the card
 *    (0x400905d4 with the resident bank's bit clear, mask 0xfffe). The MD's
 *    slice of the resident bank (4 kits, 16 patterns: 6,912 bytes) is kept
 *    in SRAM the same way: copied when stock copies the bank, refreshed 128
 *    bytes a frame (a full pass every 54 frames, about 20 ms), and taken
 *    back at the boot load.
 *  - The card. Stock saves a bank file (0x400917c8) when a bank stops being
 *    resident, on SYNC TO CARD and on SAVE; machinedrum.work, with all 64
 *    kits and 256 patterns, is written after each of those. SAVE then
 *    copies every .work file to .strd (0x40016388) and RELOAD copies back;
 *    the copy of markers.* takes machinedrum.* with it.
 *
 * The SRAM block is at 0x100fa000 (6,928 bytes). No stock instruction
 * references 0x100f859c..0x100ffeff (a census of the OS's SRAM operands,
 * 25 Sep 2026: 0x100f8598, the global changed flag, is the last below it,
 * the settings block at 0x100fff00 the first above it) and a used
 * session's NVRAM is zero there; free by inference, not by a stock map.
 * A magic word and the project's path hash guard it: a block from another
 * project or another OS is ignored.
 *
 * A project without an MD file loads empty kits (the default kit is set
 * when the MD is assigned) and empty patterns. A file whose sum fails is
 * kept as machinedrum.bad and read as empty.
 *
 * Not kept: the saved Part copies (RELOAD PART / BANK restore the Part's
 * page bytes, not the MD kit). */
#include "md_ctl.h"

#define U8(a) (*(volatile uint8_t *)(a))

enum {
    OT_UI_BANK = 0x80000002u,        /* the resident bank */
    MD_SRAM_BASE = 0x100fa000u,
    MD_SRAM_MAGIC = 0x4d445331u,     /* 'MDS1' */
    MD_FILE_MAGIC = 0x4d44524du,     /* 'MDRM' */
    MD_FILE_VERSION = 1u,
    MD_BANK_KITS = 4u,
    MD_BANK_PATTERNS = 16u,
    MD_SLICE_KITS = MD_BANK_KITS * sizeof(MdKit),
    MD_SLICE_BYTES = MD_SLICE_KITS + MD_BANK_PATTERNS * sizeof(MdPattern),
    MD_MIRROR_STEP = 128u,           /* bytes a frame */
    MD_IO_BYTES = 4096u,             /* the buffered file's sector buffer */
    MD_PATH = 272u,
};

typedef struct {
    uint32_t magic, bank, project, reserved;
    MdKit kits[MD_BANK_KITS];
    MdPattern patterns[MD_BANK_PATTERNS];
} MdSram;

typedef struct {
    uint32_t magic, version, kit_bytes, kits, pattern_bytes, patterns, reserved[2];
} MdFileHead;                        /* then the kits, the patterns, a u32 sum */

/* Stock's buffered file object: fd, buffer, size, position, flushes, mode. */
typedef struct { uint32_t w[8]; } StockFile;

typedef struct {
    uint32_t ready;                  /* a project load has set the kits up */
    uint32_t mirror_bank, mirror_pos, project;
    uint32_t writes, reads, errors, bad;
    StockFile file;
    char path[MD_PATH], path2[MD_PATH];
    uint8_t chunk[512];              /* what is being written or read */
    uint8_t io[MD_IO_BYTES];
} MdPersist;

_Static_assert(sizeof(MdSram) == 16 + 768 + 6144, "SRAM block");
_Static_assert(sizeof(MdFileHead) == 32, "file header");
_Static_assert(sizeof(MdPersist) == 32 + 32 + 2 * 272 + 512 + 4096, "md_persist_tail.s allocation");

extern MdPersist md_persist;
#define SRAM ((volatile MdSram *)MD_SRAM_BASE)

/* Stock, called as C: every one takes its arguments on the stack and
 * returns in d0 (declared integer, so gcc reads d0, never a0). */
typedef int32_t (*StOpen)(StockFile *, const char *, const char *, void *, uint32_t);
typedef int32_t (*StIo)(StockFile *, void *, uint32_t);
typedef int32_t (*StClose)(StockFile *);
typedef uint32_t (*StProjDir)(uint32_t, uint32_t);
#define ST_OPEN ((StOpen)0x40016864u)
#define ST_READ ((StIo)0x40016564u)
#define ST_WRITE ((StIo)0x400166b8u)
#define ST_CLOSE ((StClose)0x4001677cu)
#define ST_PROJDIR ((StProjDir)0x40025230u)
int32_t md_copy_stock(const char *dst, const char *src, uint32_t flag);  /* md_persist_tail.s */

static uint32_t fnv(uint32_t h, const volatile uint8_t *b, uint32_t n) {
    while (n--) { h ^= *b++; h *= 16777619u; }
    return h;
}

static uint32_t project_hash(void) {
    const char *dir = (const char *)ST_PROJDIR(0, 0);
    uint32_t h = 2166136261u;
    for (unsigned n = 0; dir && dir[n] && n < MD_PATH; ++n) { h ^= (uint8_t)dir[n]; h *= 16777619u; }
    return h;
}

static void copy_bytes(volatile uint8_t *dst, const volatile uint8_t *src, uint32_t n) {
    while (n--) *dst++ = *src++;
}

static void zero_bytes(volatile uint8_t *dst, uint32_t n) {
    while (n--) *dst++ = 0;
}

/* dir + "/" + name, or: the directory of `beside` (up to `base`) + name. */
static char *path_in(char *out, const char *dir, unsigned dir_len, const char *name) {
    unsigned n = 0;
    while (n < dir_len && dir[n] && n < MD_PATH - 32) { out[n] = dir[n]; ++n; }
    if (n && out[n - 1] != '/') out[n++] = '/';
    while (*name && n < MD_PATH - 1) out[n++] = *name++;
    out[n] = 0;
    return out;
}

static char *project_path(char *out, const char *name) {
    const char *dir = (const char *)ST_PROJDIR(0, 0);
    unsigned len = 0;
    while (dir && dir[len]) ++len;
    return path_in(out, dir ? dir : "", len, name);
}

static volatile uint8_t *slice_kits(unsigned bank) {
    return (volatile uint8_t *)&md_kits[(bank & 15) * MD_BANK_KITS];
}

static volatile uint8_t *slice_patterns(unsigned bank) {
    return (volatile uint8_t *)&md_patterns[(bank & 15) * MD_BANK_PATTERNS];
}

/* Keep what a file or SRAM hands back inside the ranges the producer and
 * the editor assume. */
static void sanitize_kit(MdKit *kit) {
    for (unsigned p = 0; p < MD_PARTS; ++p) {
        MdPart *part = &kit->part[p];
        if (part->engine >= MD_ENGINE_IDS) part->engine = 0;
        part->vol &= 0x7f;
        part->pan &= 0x7f;
        part->flags &= MD_PART_MUTE;
        for (unsigned i = 0; i < MD_SYN; ++i) part->syn[i] &= 0x7f;
    }
}

static void sanitize_pattern(MdPattern *pat) {
    for (unsigned i = 0; i < MD_LOCKS; ++i) {
        MdLock *l = &pat->lock[i];
        if (l->part >= MD_PARTS || l->step >= MD_STEPS || l->param >= MD_LOCK_PARAMS) {
            l->part = MD_LOCK_FREE;
            continue;
        }
        l->value &= 0x7f;
    }
}

static void sanitize_bank(unsigned bank) {
    for (unsigned k = 0; k < MD_BANK_KITS; ++k)
        sanitize_kit(&md_kits[(bank & 15) * MD_BANK_KITS + k]);
    for (unsigned q = 0; q < MD_BANK_PATTERNS; ++q)
        sanitize_pattern(&md_patterns[(bank & 15) * MD_BANK_PATTERNS + q]);
}

/* ---- SRAM --------------------------------------------------------------- */
static void slice_to_sram(unsigned bank, uint32_t project) {
    MdPersist *p = &md_persist;
    volatile MdSram *s = SRAM;
    s->magic = 0;                    /* the ISR's mirror stops at once */
    copy_bytes((volatile uint8_t *)s->kits, slice_kits(bank), MD_SLICE_KITS);
    copy_bytes((volatile uint8_t *)s->patterns, slice_patterns(bank),
               MD_BANK_PATTERNS * sizeof(MdPattern));
    s->bank = bank & 15;
    s->project = project;
    p->mirror_bank = bank & 15;
    p->mirror_pos = 0;
    s->magic = MD_SRAM_MAGIC;
}

static unsigned sram_holds(unsigned bank, uint32_t project) {
    volatile MdSram *s = SRAM;
    return s->magic == MD_SRAM_MAGIC && s->bank == (bank & 15) && s->project == project;
}

static void sram_to_slice(unsigned bank) {
    volatile MdSram *s = SRAM;
    copy_bytes(slice_kits(bank), (volatile uint8_t *)s->kits, MD_SLICE_KITS);
    copy_bytes(slice_patterns(bank), (volatile uint8_t *)s->patterns,
               MD_BANK_PATTERNS * sizeof(MdPattern));
    sanitize_bank(bank);
}

/* Interrupt context, once a frame: 128 more bytes of the resident slice. */
void md_persist_frame(void) {
    MdPersist *p = &md_persist;
    if (!p->ready) return;           /* boot: SRAM holds the newer copy until the load */
    volatile MdSram *s = SRAM;
    unsigned bank = p->mirror_bank;
    if (s->magic != MD_SRAM_MAGIC || s->bank != bank) return;
    unsigned o = p->mirror_pos;
    const volatile uint32_t *src;
    volatile uint32_t *dst;
    if (o < MD_SLICE_KITS) {
        src = (const volatile uint32_t *)(slice_kits(bank) + o);
        dst = (volatile uint32_t *)((volatile uint8_t *)s->kits + o);
    } else {
        src = (const volatile uint32_t *)(slice_patterns(bank) + o - MD_SLICE_KITS);
        dst = (volatile uint32_t *)((volatile uint8_t *)s->patterns + o - MD_SLICE_KITS);
    }
    for (unsigned i = 0; i < MD_MIRROR_STEP / 4; ++i) dst[i] = src[i];
    o += MD_MIRROR_STEP;
    p->mirror_pos = o >= MD_SLICE_BYTES ? 0 : o;
}

/* ---- the card ----------------------------------------------------------- */
static unsigned put(MdPersist *p, const volatile uint8_t *src, uint32_t n, uint32_t *sum) {
    while (n) {
        uint32_t k = n < sizeof p->chunk ? n : sizeof p->chunk;
        copy_bytes(p->chunk, src, k);    /* the ISR may edit: sum what is written */
        *sum = fnv(*sum, p->chunk, k);
        if (ST_WRITE(&p->file, p->chunk, k) < 0) return 0;
        src += k;
        n -= k;
    }
    return 1;
}

static void file_write(void) {
    MdPersist *p = &md_persist;
    MdFileHead h = { MD_FILE_MAGIC, MD_FILE_VERSION, sizeof(MdKit), MD_KITS,
                     sizeof(MdPattern), MD_PATTERNS, {0, 0} };
    uint32_t sum = 2166136261u;
    project_path(p->path, "machinedrum.work");
    if (ST_OPEN(&p->file, p->path, "w", p->io, sizeof p->io) < 0) { ++p->errors; return; }
    unsigned ok = ST_WRITE(&p->file, &h, sizeof h) >= 0
        && put(p, (const volatile uint8_t *)md_kits, sizeof(MdKit) * MD_KITS, &sum)
        && put(p, (const volatile uint8_t *)md_patterns, sizeof(MdPattern) * MD_PATTERNS, &sum)
        && ST_WRITE(&p->file, &sum, sizeof sum) >= 0;
    if (ST_CLOSE(&p->file) < 0) ok = 0;
    if (ok) ++p->writes; else ++p->errors;
}

/* Read n bytes; keep them at dst when keep, else only sum them. */
static unsigned take(MdPersist *p, volatile uint8_t *dst, uint32_t n, unsigned keep, uint32_t *sum) {
    while (n) {
        uint32_t k = n < sizeof p->chunk ? n : sizeof p->chunk;
        if (ST_READ(&p->file, p->chunk, k) <= 0) return 0;
        *sum = fnv(*sum, p->chunk, k);
        if (keep) { copy_bytes(dst, p->chunk, k); dst += k; }
        n -= k;
    }
    return 1;
}

/* Pass 1 sums the whole file; pass 2, only if it is sound, reads the banks
 * in `mask` into place. Returns 1 when those banks came from the file. */
static unsigned file_read(unsigned mask) {
    MdPersist *p = &md_persist;
    MdFileHead h;
    uint32_t sum, stored;
    project_path(p->path, "machinedrum.work");
    for (unsigned pass = 0; pass < 2; ++pass) {
        if (ST_OPEN(&p->file, p->path, "r", p->io, sizeof p->io) < 0) return 0;  /* no file */
        sum = 2166136261u;
        unsigned ok = ST_READ(&p->file, &h, sizeof h) > 0 && h.magic == MD_FILE_MAGIC
            && h.version == MD_FILE_VERSION && h.kit_bytes == sizeof(MdKit) && h.kits == MD_KITS
            && h.pattern_bytes == sizeof(MdPattern) && h.patterns == MD_PATTERNS;
        for (unsigned k = 0; ok && k < MD_KITS; ++k)
            ok = take(p, (volatile uint8_t *)&md_kits[k], sizeof(MdKit),
                      pass && ((mask >> (k >> 2)) & 1), &sum);
        for (unsigned q = 0; ok && q < MD_PATTERNS; ++q)
            ok = take(p, (volatile uint8_t *)&md_patterns[q], sizeof(MdPattern),
                      pass && ((mask >> (q >> 4)) & 1), &sum);
        if (ok) ok = ST_READ(&p->file, &stored, sizeof stored) > 0 && stored == sum;
        ST_CLOSE(&p->file);
        if (!ok) {
            ++p->bad;
            if (!pass) {                 /* keep the damaged file for the user */
                project_path(p->path2, "machinedrum.bad");
                md_copy_stock(p->path2, p->path, 0);
            }
            return 0;
        }
    }
    ++p->reads;
    return 1;
}

static void clear_banks(unsigned mask) {
    for (unsigned b = 0; b < 16; ++b)
        if ((mask >> b) & 1) {
            zero_bytes(slice_kits(b), MD_SLICE_KITS);
            zero_bytes(slice_patterns(b), MD_BANK_PATTERNS * sizeof(MdPattern));
            for (unsigned q = 0; q < MD_BANK_PATTERNS; ++q)
                for (unsigned i = 0; i < MD_LOCKS; ++i)
                    md_patterns[b * MD_BANK_PATTERNS + q].lock[i].part = MD_LOCK_FREE;
        }
}

/* ---- the hooks (md_persist_tail.s), in the tasks that run stock's ------ */

/* After stock's project load (0x400905d4) read the banks in `mask`. At boot
 * the resident bank is not in it: stock restored it from SRAM, and so does
 * this, when the block is this project's. */
void md_persist_loaded(uint32_t mask) {
    MdPersist *p = &md_persist;
    unsigned bank = U8(OT_UI_BANK) & 15;
    uint32_t project = project_hash();
    mask &= 0xffffu;
    unsigned from_sram = !((mask >> bank) & 1) && sram_holds(bank, project);
    unsigned want = from_sram ? mask : mask | (1u << bank);
    if (file_read(want)) {
        for (unsigned b = 0; b < 16; ++b)
            if ((want >> b) & 1) sanitize_bank(b);
    } else {
        clear_banks(want);
    }
    if (from_sram) sram_to_slice(bank);
    slice_to_sram(bank, project);
    p->project = project;
    p->ready = 1;
}

/* After stock copied bank `bank` into SRAM (0x4000faf0): it is resident. */
void md_persist_sram_saved(uint32_t bank) {
    MdPersist *p = &md_persist;
    if (!p->ready) return;           /* before the first load: md_persist_loaded does it */
    slice_to_sram(bank, project_hash());
}

/* After stock saved banks to the card (0x400917c8). */
void md_persist_bank_saved(int32_t result) {
    if (!md_persist.ready || result < 0) return;
    file_write();
}

static const char *base_name(const char *path) {
    const char *b = path;
    for (const char *s = path; *s; ++s)
        if (*s == '/') b = s + 1;
    return b;
}

static unsigned is_markers(const char *name) {
    static const char m[] = "markers.";
    for (unsigned i = 0; i < sizeof m - 1; ++i)
        if (name[i] != m[i]) return 0;
    return 1;
}

/* After stock copied a file (0x40016388(dst, src, 0)): SAVE's .work -> .strd
 * and RELOAD's .strd -> .work take machinedrum.* with markers.*. */
void md_persist_copied(const char *dst, const char *src, int32_t result) {
    MdPersist *p = &md_persist;
    if (result < 0 || !dst || !src) return;
    const char *sb = base_name(src), *db = base_name(dst);
    if (!is_markers(sb) || !is_markers(db)) return;
    char name[24];
    static const char md[] = "machinedrum.";
    unsigned n = 0;
    for (; md[n]; ++n) name[n] = md[n];
    for (const char *e = sb + 8; *e && n < sizeof name - 1; ++e) name[n++] = *e;
    name[n] = 0;
    path_in(p->path, src, (unsigned)(sb - src), name);
    n = sizeof md - 1;
    for (const char *e = db + 8; *e && n < sizeof name - 1; ++e) name[n++] = *e;
    name[n] = 0;
    path_in(p->path2, dst, (unsigned)(db - dst), name);
    md_copy_stock(p->path2, p->path, 0);
}
