// CF BURN: run the COMPLETE stock eight-track delay routine (0x400031a0) on
// the built image and on pristine stock, frame by frame, and prove
//   1. INERT   every on-chip SRAM word 0x80000000..0x8000ffff, the stack, the
//              ring bytes each track wrote, and every returned CPU register
//              equal stock's, with and without CF BURN tracks, whatever the
//              knobs. (The routine's epilogue restores EMAC from the compared
//              SRAM/stack; the hook has no EMAC instruction.)
//   2. EXACT   executed instructions = stock + 75 + 5*k + 10*N, with k the
//              CF BURN tracks and N = sum of BURN*STEP + FINE over them, in
//              this frame's control snapshot only, knob = high byte.
//   3. SEEING  the comparison fails on a single flipped bit, and one FINE
//              step moves the count by exactly BODY.
// The DMA model moves bytes synchronously (tapeecho_cpu_probe.cpp): it proves
// addresses, order and bytes, not cycles. No hardware timing is claimed.
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iterator>
#include <string>
#include <vector>
#include "machine.h"
#include "periph.h"
#include "mc68k/Musashi/m68k.h"
#include "mc68k/cpuState.h"

static std::vector<uint8_t> read(const char *p) {
    std::ifstream f(p, std::ios::binary);
    return {std::istreambuf_iterator<char>(f), std::istreambuf_iterator<char>()};
}
static constexpr uint32_t stack = 0x47100000, endpc = 0x47200000;
static constexpr uint32_t ring0 = 0x4f502c10, stride = 1411328;
static unsigned ID, STEP, BODY;
static unsigned fails = 0;

static unsigned run(ot::Machine& m, uint32_t pc, uint32_t until, unsigned max) {
    m68k_set_reg(m.getCpuState(), M68K_REG_PC, pc);
    unsigned n = 0;
    while (m.pc() != until && n++ < max) if (!m.step()) break;
    if (m.pc() != until) {
        std::fprintf(stderr, "execution stopped at %08x, wanted %08x after %u instructions\n", m.pc(), until, n);
        std::exit(1);
    }
    return n;
}
static void dma_model(ot::Machine& m, ot::Edma& dma) {
    m.setPeripheralHandlers(
        [&](uint32_t a, uint8_t n, uint32_t& v) {
            if (a < ot::Edma::g_base || a >= ot::Edma::g_tcd + 512) return false;
            v = dma.read(a, n); return true;
        },
        [&](uint32_t a, uint8_t n, uint32_t v) {
            if (a >= ot::Edma::g_base && a < ot::Edma::g_tcd + 512) dma.write(a, n, v, false);
        });
    dma.setDataHooks({}, [&](uint32_t ch) {
        auto src = dma.tcdField(ch, 0, 4), dst = dma.tcdField(ch, 16, 4);
        auto size = dma.tcdField(ch, 8, 4) * dma.minorLoops(ch);
        if (size > 144) { std::fprintf(stderr, "bad delay DMA size %u\n", size); std::exit(1); }
        std::vector<uint8_t> b(size);
        for (unsigned i = 0; i < size; ++i) b[i] = m.read8(src + i);
        for (unsigned i = 0; i < size; ++i) m.write8(dst + i, b[i]);
    });
}
static void reset(ot::Machine& m) {   // the stock delay reset, as boot runs it
    m68k_set_reg(m.getCpuState(), M68K_REG_SR, 0x2700);
    m68k_set_reg(m.getCpuState(), M68K_REG_SP, stack);
    m.write32(stack, endpc);
    run(m, 0x40002f44, endpc, 5000000);
}

struct Track { uint8_t id; uint8_t knob[6]; };
struct Frame { Track t[4][8]; uint32_t seed; };   // all four control snapshots

static uint32_t xorshift(uint32_t& r) { r ^= r << 13; r ^= r >> 17; r ^= r << 5; return r; }

// Stage one frame into a machine exactly as the routine's callers leave it.
static void stage(ot::Machine& m, const Frame& f, unsigned frame, uint32_t garbage) {
    unsigned snap = frame & 3, ping = frame & 1;
    m.write32(0x800000e0, ping);
    m.write32(0x80004804, snap);
    m.write32(0x8000181c, (60 + frame % 200) * 24);
    uint32_t r = f.seed;
    for (unsigned s = 0; s < 4; ++s) for (unsigned t = 0; t < 8; ++t) {
        auto setup = 0x80001b80 + s * 64 + t * 8, knobs = 0x80001a00 + s * 96 + t * 12;
        for (unsigned i = 0; i < 7; ++i) m.write8(setup + i, 0);
        m.write8(setup + 2, f.t[s][t].knob[5] & 1 ? 127 : 0);   // TAPE on/off
        m.write8(setup + 7, f.t[s][t].id);
        // High byte = the knob; the low byte is left to vary (the hook must
        // ignore it) -- `garbage` differs per frame but is the same in both
        // machines.
        for (unsigned i = 0; i < 6; ++i)
            m.write16(knobs + 2 * i, uint16_t(f.t[s][t].knob[i] << 8 | ((garbage >> i) & 0xff)));
    }
    for (unsigned t = 0; t < 8; ++t) {
        m.write8(0x80000eb4 + ping * 8 + t, 1);
        for (unsigned i = 0; i < 32; ++i)
            m.write32(0x80003190 + ping * 1024 + t * 128 + 4 * i, xorshift(r) >> (i & 3));
    }
}

static unsigned expectedExtra(const Frame& f, unsigned frame, unsigned& k, unsigned& n) {
    unsigned snap = frame & 3; k = n = 0;
    for (unsigned t = 0; t < 8; ++t) if (f.t[snap][t].id == ID) {
        ++k; n += f.t[snap][t].knob[0] * STEP + f.t[snap][t].knob[1];
    }
    return 75 + 5 * k + BODY * n;
}

// Everything the routine could have touched, compared byte for byte.
static bool same(ot::Machine& a, ot::Machine& b, const uint32_t pos[8], std::string& why) {
    for (uint32_t x = 0x80000000; x < 0x80010000; x += 4)
        if (a.read32(x) != b.read32(x)) { char s[64]; std::snprintf(s, 64, "SRAM %08x", x); why = s; return false; }
    for (uint32_t x = stack - 1024; x <= stack; x += 4)
        if (a.read32(x) != b.read32(x)) { char s[64]; std::snprintf(s, 64, "stack %08x", x); why = s; return false; }
    for (unsigned t = 0; t < 8; ++t) for (unsigned i = 0; i < 128; i += 4) {
        auto x = ring0 + t * stride + pos[t] + i;
        if (a.read32(x) != b.read32(x)) { char s[64]; std::snprintf(s, 64, "ring track %u +%u", t + 1, i); why = s; return false; }
    }
    for (int r = M68K_REG_D0; r <= M68K_REG_A7; ++r)
        if (m68k_get_reg(a.getCpuState(), m68k_register_t(r)) != m68k_get_reg(b.getCpuState(), m68k_register_t(r))) {
            why = "register " + std::to_string(r - M68K_REG_D0); return false;
        }
    if ((m68k_get_reg(a.getCpuState(), M68K_REG_SR) & 0xff1f) != (m68k_get_reg(b.getCpuState(), M68K_REG_SR) & 0xff1f)) {
        why = "SR"; return false;
    }
    return true;
}

// Liveness of the comparison: the stock DELAY tracks must write nonzero ring
// words and change their audio, or "identical" compares two silences.
static unsigned liveRing = 0, liveWet = 0;

// Run `frames` frames of one scenario on both machines. Returns false on the
// first mismatch (state or count) with a message.
static bool scenario(ot::Machine& img, ot::Machine& stock, const char* name,
                     unsigned frames, Frame (*make)(unsigned), bool quiet = false) {
    for (unsigned frame = 0; frame < frames; ++frame) {
        Frame f = make(frame);
        uint32_t garbage = 0x9e3779b9u * (frame + 1);
        uint32_t pos[8];
        for (unsigned t = 0; t < 8; ++t) pos[t] = stock.read32(0x80005f9c + 68 * t);
        stage(img, f, frame, garbage);
        stage(stock, f, frame, garbage);
        std::vector<uint32_t> input;
        for (unsigned x = 0; x < 256; ++x) input.push_back(stock.read32(0x80003190 + (frame & 1) * 1024 + 4 * x));
        unsigned counts[2];
        unsigned i = 0;
        for (auto* m : {&img, &stock}) {
            m68k_set_reg(m->getCpuState(), M68K_REG_SP, stack);
            m->write32(stack, endpc);
            for (int r = M68K_REG_D0; r < M68K_REG_A7; ++r)
                m68k_set_reg(m->getCpuState(), m68k_register_t(r), 0x51000000u + r);
            counts[i++] = run(*m, 0x400031a0, endpc, 4000000);
        }
        std::string why;
        if (!same(img, stock, pos, why)) {
            if (!quiet) std::fprintf(stderr, "%s: frame %u differs from stock at %s\n", name, frame, why.c_str());
            return false;
        }
        for (unsigned t = 0; t < 8; ++t) if (f.t[frame & 3][t].id == 8) {
            for (unsigned i = 0; i < 128; i += 4) liveRing += stock.read32(ring0 + t * stride + pos[t] + i) != 0;
            for (unsigned i = 0; i < 32; ++i)
                liveWet += stock.read32(0x80003190 + (frame & 1) * 1024 + t * 128 + 4 * i) != input[t * 32 + i];
        }
        unsigned k, n, want = expectedExtra(f, frame, k, n);
        if (counts[0] - counts[1] != want) {
            if (!quiet) std::fprintf(stderr, "%s: frame %u costs stock+%u, expected stock+%u (k=%u, N=%u)\n",
                                     name, frame, counts[0] - counts[1], want, k, n);
            return false;
        }
    }
    return true;
}

static void check(const char* what, bool ok) {
    fails += !ok;
    std::printf("  [%s] %s\n", ok ? "PASS" : "FAIL", what);
    std::fflush(stdout);
}

// ---- scenarios -------------------------------------------------------------
// Live DELAY on some tracks (ring history, feedback, time moves), other ids on
// the rest; CF BURN where a scenario puts it.
static Track delayTrack(unsigned frame, unsigned t) {
    Track x{8, {uint8_t((frame / 3 + 17 * t) % 128), 90, 100, 64, 0, uint8_t(t & 1)}};
    return x;
}
static Track otherTrack(unsigned t) {
    static const uint8_t ids[] = {0x00, 0x04, 0x15, 0x12, 0x00, 0x1c, 0x16, 0x0c};
    Track x{ids[t], {uint8_t(t * 13), uint8_t(t * 7), 127, 0, 64, 3}};
    return x;
}
static Frame base(unsigned frame) {
    Frame f{};
    f.seed = 0x1234567u + frame * 7919;
    for (unsigned s = 0; s < 4; ++s) for (unsigned t = 0; t < 8; ++t)
        f.t[s][t] = t % 3 == 0 ? delayTrack(frame, t) : otherTrack(t);
    return f;
}
static Frame inert(unsigned frame) { return base(frame); }

static const uint8_t GRID[][2] = {{0,0},{0,1},{1,0},{1,127},{2,63},{64,0},{127,0},{127,127},{0,127},{33,5}};
static constexpr unsigned GRIDN = sizeof(GRID) / sizeof(GRID[0]);
static Frame single(unsigned frame) {        // one CF BURN track, every track in turn
    Frame f = base(frame);
    unsigned t = (frame / GRIDN) % 8, g = frame % GRIDN;
    for (unsigned s = 0; s < 4; ++s) {
        f.t[s][t].id = uint8_t(ID);
        f.t[s][t].knob[0] = GRID[g][0]; f.t[s][t].knob[1] = GRID[g][1];
    }
    return f;
}
static Frame all8(unsigned frame) {          // every track carries CF BURN
    Frame f = base(frame);
    for (unsigned s = 0; s < 4; ++s) for (unsigned t = 0; t < 8; ++t) {
        f.t[s][t].id = uint8_t(ID);
        f.t[s][t].knob[0] = uint8_t(frame == 5 ? 127 : (frame * 29 + t * 11) % 128);
        f.t[s][t].knob[1] = uint8_t(frame == 5 ? 127 : (frame * 7 + t * 53) % 128);
    }
    return f;
}
static Frame decoy(unsigned frame) {         // other snapshots scream; this one whispers
    Frame f = base(frame);
    unsigned snap = frame & 3;
    for (unsigned s = 0; s < 4; ++s) for (unsigned t = 0; t < 8; ++t) if (s != snap) {
        f.t[s][t].id = uint8_t(ID); f.t[s][t].knob[0] = 127; f.t[s][t].knob[1] = 127;
    }
    f.t[snap][(frame + 3) % 8].id = uint8_t(ID);
    f.t[snap][(frame + 3) % 8].knob[0] = 3;
    f.t[snap][(frame + 3) % 8].knob[1] = 9;
    return f;
}
static Frame dropout(unsigned frame) {       // CF BURN on, off, on: state continuity
    Frame f = base(frame);
    if ((frame / 4) % 2)
        for (unsigned s = 0; s < 4; ++s) { f.t[s][7].id = uint8_t(ID); f.t[s][7].knob[0] = 10; f.t[s][7].knob[1] = 1; }
    return f;
}

int main(int argc, char** argv) {
    if (argc != 6) { std::fprintf(stderr, "cfburn_probe IMAGE STOCK ID STEP BODY\n"); return 2; }
    auto image = read(argv[1]), pristine = read(argv[2]);
    ID = std::strtoul(argv[3], nullptr, 0); STEP = std::strtoul(argv[4], nullptr, 0);
    BODY = std::strtoul(argv[5], nullptr, 0);
    if (image.size() != pristine.size()) { std::fprintf(stderr, "image and stock differ in size\n"); return 1; }

    auto fresh = [&](ot::Machine& img, ot::Machine& stock) { reset(img); reset(stock); };
    {
        ot::Machine img(image), stock(pristine);
        ot::Edma d1, d2; dma_model(img, d1); dma_model(stock, d2); fresh(img, stock);
        check("inert: 200 frames, no CF BURN track, live DELAY + six other ids: state = stock, cost = stock + 75",
              scenario(img, stock, "inert", 200, inert));
    }
    {
        ot::Machine img(image), stock(pristine);
        ot::Edma d1, d2; dma_model(img, d1); dma_model(stock, d2); fresh(img, stock);
        check("exact: 10 knob pairs x 8 tracks (BURN/FINE 0..127), live DELAY beside it: state = stock, cost = stock + 80 + 10*N",
              scenario(img, stock, "single", 8 * GRIDN, single));
    }
    {
        ot::Machine img(image), stock(pristine);
        ot::Edma d1, d2; dma_model(img, d1); dma_model(stock, d2); fresh(img, stock);
        check("sum: CF BURN on all eight tracks, up to 127/127 each (660,400 burn instructions): tracks add",
              scenario(img, stock, "all8", 12, all8));
    }
    {
        ot::Machine img(image), stock(pristine);
        ot::Edma d1, d2; dma_model(img, d1); dma_model(stock, d2); fresh(img, stock);
        check("snapshot: CF BURN 127/127 on every track of the three other snapshots is ignored",
              scenario(img, stock, "decoy", 40, decoy));
    }
    {
        ot::Machine img(image), stock(pristine);
        ot::Edma d1, d2; dma_model(img, d1); dma_model(stock, d2); fresh(img, stock);
        check("toggle: CF BURN switched on and off every four frames beside live DELAY",
              scenario(img, stock, "dropout", 64, dropout));
    }
    check("the comparison is live: DELAY tracks wrote nonzero ring words and changed their audio",
          liveRing > 1000 && liveWet > 1000);
    std::printf("  [LIVE] nonzero ring words %u, wet samples %u\n", liveRing, liveWet);
    // ---- the comparison can see ------------------------------------------
    {
        ot::Machine img(image), stock(pristine);
        ot::Edma d1, d2; dma_model(img, d1); dma_model(stock, d2); fresh(img, stock);
        scenario(img, stock, "warm", 8, inert);
        uint32_t pos[8]; for (unsigned t = 0; t < 8; ++t) pos[t] = stock.read32(0x80005f9c + 68 * t);
        std::string why;
        bool before = same(img, stock, pos, why);
        img.write8(0x80005f60 + 68 * 3 + 29, img.read8(0x80005f60 + 68 * 3 + 29) ^ 0x10);
        bool after = same(img, stock, pos, why);
        check("negative control: one flipped bit in a delay state record is reported", before && !after);
        // Stock against itself with the id: a stock image has no hook, so the
        // count formula must FAIL there -- the meter is not blind to the loop.
        ot::Machine s1(pristine), s2(pristine);
        ot::Edma d3, d4; dma_model(s1, d3); dma_model(s2, d4); fresh(s1, s2);
        check("negative control: stock vs stock does not satisfy the CF BURN count",
              !scenario(s1, s2, "stock-vs-stock", 1, single, true));
    }
    std::printf("  [METER] no CF BURN track: +75 instructions/frame; per CF BURN track: +5; "
                "per BURN step: %u; per FINE step: %u (instructions, not cycles)\n", STEP * BODY, BODY);
    return fails ? 1 : 0;
}
