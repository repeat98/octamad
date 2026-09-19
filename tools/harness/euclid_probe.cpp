// Execute the actual ColdFire hooks; publish a cutoff trace for DSP audition.
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iterator>
#include <string>
#include <vector>
#include "machine.h"
#include "mc68k/Musashi/m68k.h"
#include "mc68k/cpuState.h"

static std::vector<uint8_t> read(const char* path) {
    std::ifstream f(path, std::ios::binary);
    return {std::istreambuf_iterator<char>(f), std::istreambuf_iterator<char>()};
}

int main(int argc, char** argv) {
    if (argc != 8) {
        std::fprintf(stderr, "euclid_probe image runtime base state trace mode frames\n");
        return 2;
    }
    auto image = read(argv[1]), runtime = read(argv[2]);
    uint32_t base = std::strtoul(argv[3], nullptr, 16);
    uint32_t state = std::strtoul(argv[4], nullptr, 16);
    unsigned mode = std::strtoul(argv[6], nullptr, 10);
    unsigned frames = std::strtoul(argv[7], nullptr, 10);
    ot::Machine m(image);
    for (unsigned i = 0; i < runtime.size(); ++i) m.write8(base + i, runtime[i]);
    auto* cpu = m.getCpuState();
    constexpr uint32_t stack = 0x47100000, anchor = 0xffff0000;
    for (unsigned i = 0; i < 1024; ++i) m.write8(0x80000110 + i, 0);
    uint32_t rec = 0x80000110;
    unsigned peakInstructions = 0;
    auto run = [&](uint32_t pc, uint32_t until) {
        m68k_set_reg(cpu, M68K_REG_PC, pc);
        unsigned n = 0;
        while (m.pc() != until && n++ < 100000) if (!m.step()) break;
        if (m.pc() != until) {
            std::fprintf(stderr, "hook failed at %08x after %u instructions (wanted %08x)\n", m.pc(), n, until);
            return false;
        }
        if (n > peakInstructions) peakInstructions = n;
        return true;
    };
    m68k_set_reg(cpu, M68K_REG_SP, stack);
    m68k_set_reg(cpu, M68K_REG_SR, 0x2700);
    m68k_set_reg(cpu, M68K_REG_D0, 1);
    m.write32(0x4610757c, anchor);
    if (!run(0x4009c3d4, 0x4009c3da)) return 1;
    m.write8(0x800065bd, 0); m.write8(0x800065be, 0);
    m.write8(0x400e21e0 + 0x8e55, 1);   // per-track scale
    for (unsigned track = 0; track < 8; ++track) {
        auto tr = 0x400e21e0 + track * 2330;
        m.write8(tr + 0x50, 16);
        m.write8(tr + 0x51, 2);    // 1x
        m.write8(tr + 0x52, 16);   // swing 66%
        m.write32(tr + 0x40, 0xaaaaaaaa);
        m.write32(tr + 0x44, 0xaaaaaaaa);
    }
    m.write32(0x8000181c, 2880);
    std::ofstream trace(argv[5]);
    for (unsigned frame = 0; frame < frames; ++frame) {
        m.write32(0x800000e0, frame & 1);
        rec = 0x80000110 + (frame & 1) * 512;
        for (unsigned i = 0; i < 256; ++i) m.write16(rec + 2*i, 0x1200 + i);
        // All sixteen instances, alternating between both outgoing buffers.
        for (unsigned track = 0; track < 8; ++track) {
            for (unsigned fx = 0; fx < 2; ++fx) {
                unsigned h = 32 * track + 6 + 6 * fx, b = 64 * track + 36 + 12 * fx;
                // Sparse ENV pulses leave room for the full eight-step tail.
                const unsigned params[] = {40, 48, 100, mode == 0 ? 127u : 48u,
                                           mode == 0 ? 15u : 7u, mode == 0 ? 1u : 3u};
                for (unsigned i = 0; i < 6; ++i) m.write16(rec + 2*(h+i), params[i] << 8);
                m.write8(rec + b, 0); m.write8(rec + b + 1, 1);
                m.write8(rec + b + 2, 0); m.write8(rec + b + 3, 0);
                m.write8(rec + b + 4, mode); m.write8(rec + b + 5, 127);
                m.write16(rec + 64*track + 2*(27+fx), 0x1d);
            }
        }
        std::vector<uint16_t> before;
        for (unsigned i = 0; i < 256; ++i) before.push_back(m.read16(rec + 2*i));
        m.write32(0x46104cf0, anchor + frame * 16u * 2880u);
        // Lock the already heard random values after one complete cycle.
        unsigned output = mode;
        if (mode == 2 && frame >= 3000) output = 3;
        for (unsigned track = 0; track < 8; ++track) {
            m.write8(rec + 64*track + 40, output); m.write8(rec + 64*track + 52, output);
            before[32*track+20] = (output << 8) | 127;
            before[32*track+26] = before[32*track+20];
        }
        uint32_t regs[16];
        for (unsigned i = 0; i < 16; ++i) {
            regs[i] = 0x15000000 + 4*i;
            if (i == 4) regs[i] = 0;
            if (i == 8) regs[i] = 2880;
            if (i == 10) regs[i] = rec;
            if (i == 15) regs[i] = stack;
            m68k_set_reg(cpu, m68k_register_t(M68K_REG_D0 + i), regs[i]);
        }
        if (!run(0x4000d562, 0x4000d568)) return 1;
        for (unsigned i = 0; i < 16; ++i) {
            auto got = m68k_get_reg(cpu, m68k_register_t(M68K_REG_D0 + i));
            if (got != (i == 9 ? 0x800000f0 : regs[i])) {
                std::fprintf(stderr, "register %u clobbered: %08x -> %08x\n", i, regs[i], got); return 1;
            }
        }
        for (unsigned i = 0; i < 256; ++i) {
            if (i % 32 == 6 || i % 32 == 12) continue;
            if (m.read16(rec + 2*i) != before[i]) {
                std::fprintf(stderr, "record halfword %u corrupted\n", i); return 1;
            }
        }
        trace << frame << ',' << m.read16(rec + 12) << ',' << m.read16(rec + 24)
              << ',' << m.read32(state + 20) << ',' << m.read32(state + 164 + 20)
              << ',' << m.read16(rec + 7*64 + 12) << ',' << m.read16(rec + 7*64 + 24)
              << ',' << m.read32(state + 14*164 + 20) << ',' << m.read32(state + 15*164 + 20) << '\n';
    }
    // An unrelated effect must be a byte-for-byte replay of the stock write.
    m.write16(rec + 54, 4); m.write16(rec + 56, 8);
    m.write16(rec + 12, 0x1234); m.write16(rec + 24, 0x5678);
    m68k_set_reg(cpu, M68K_REG_D4, 0);
    if (!run(0x4000d562, 0x4000d568)) return 1;
    if (m.read16(rec + 12) != 0x1234 || m.read16(rec + 24) != 0x5678) return 1;
    // The resume PLAY hook must reset phase too, without losing a captured loop.
    std::vector<uint16_t> captured;
    for (unsigned i = 0; i < 64; ++i) captured.push_back(m.read16(state + 2*164 + 24 + 2*i));
    const auto epoch = m.read32(state);
    m68k_set_reg(cpu, M68K_REG_D0, 1);
    m.write32(0x4610757c, anchor);
    if (!run(0x4009c4d4, 0x4009c4da)) return 1;
    m.write32(0x46104cf0, anchor);
    m.write16(rec + 54, 0x1d); m.write8(rec + 40, 3);
    m.write8(rec + 64 + 40, 3);
    if (!run(0x4000d562, 0x4000d568)) return 1;
    // Track 1 was removed above; check a continuously active track's capture.
    if (m.read32(state + 2*164) != epoch + 1 || m.read32(state + 2*164 + 4) != 12) return 1;
    for (unsigned i = 0; i < 64; ++i)
        if (captured[i] != m.read16(state + 2*164 + 24 + 2*i)) return 1;

    // Execute the real knob renderer, including its label formatter and
    // Euclid's display hook. Capture its bitmap/text draw calls without
    // needing a screen. Stored values and labels must remain unscaled.
    const auto desc = m.read32(0x400d6050);
    auto dial = [&](unsigned slot, unsigned value, unsigned flags, unsigned maximum) {
        constexpr uint32_t done = 0x47f00000;
        const auto formatter = slot < 12 ? m.read32(desc + 0xca + 4*slot) : 0;
        const uint32_t args[] = {20, 20, slot % 6, value, flags, formatter, 0x47020000};
        m68k_set_reg(cpu, M68K_REG_SP, stack);
        m.write32(stack, done);
        for (unsigned i = 0; i < 7; ++i) m.write32(stack + 4 + 4*i, args[i]);
        m68k_set_reg(cpu, M68K_REG_PC, 0x400479b4);
        std::vector<uint32_t> sprites;
        std::string label;
        unsigned instructions = 0;
        while (m.pc() != done && instructions++ < 10000) {
            auto pc = m.pc();
            if (pc == 0x400128a8 || pc == 0x40012bd8 || pc == 0x40012f30
                    || pc == 0x40012254 || pc == 0x40011830) {
                auto sp = m68k_get_reg(cpu, M68K_REG_SP);
                if (pc == 0x400128a8) sprites.push_back(m.read32(sp + 4));
                if (pc == 0x40012bd8) {
                    auto text = m.read32(sp + 24);
                    for (unsigned j = 0; j < 12 && m.read8(text+j); ++j)
                        label += char(m.read8(text+j));
                }
                m68k_set_reg(cpu, M68K_REG_D0, pc == 0x40012f30 ? 12 : 0);
                m68k_set_reg(cpu, M68K_REG_PC, m.read32(sp));
                m68k_set_reg(cpu, M68K_REG_SP, sp + 4);
            } else if (!m.step()) break;
        }
        unsigned position = maximum == 127 ? value : (value * 127 + maximum/2) / maximum;
        const auto text = std::to_string(value + (slot == 4 ? 1 : 0));
        bool graphic = (flags & 2) ? sprites.empty()
            : sprites.size() == 2 && sprites.back() == m.read32(0x400bdb6e + 4*position);
        if (m.pc() != done || label != text || !graphic || m.read32(stack + 16) != value) {
            std::fprintf(stderr, "dial slot %u value %u flags %u: pc=%08x label=%s want=%s sprites=%zu position=%u\n",
                         slot, value, flags, m.pc(), label.c_str(), text.c_str(), sprites.size(), position);
            return false;
        }
        return true;
    };
    for (unsigned slot : {4u, 5u, 6u, 12u}) {
        unsigned maximum = slot == 5 ? 64 : slot == 12 ? 127 : 63;
        for (unsigned value = 0; value <= maximum; ++value)
            for (unsigned flags : {1u, 3u})
                if (!dial(slot, value, flags, maximum)) return 1;
    }
    std::printf("PASS: actual dial renderer uses the full arc at 64 steps/pulses; labels, storage and other dials unchanged\n");
    std::printf("PASS: %u frames, 16 instances, both buffers, both PLAY paths; peak %u CF instructions per frame\n", frames, peakInstructions);
    return 0;
}
