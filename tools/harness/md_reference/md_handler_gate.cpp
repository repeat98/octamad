#include "mc68k.h"
#include "cpuState.h"
#include "musashiEntry.h"

#include <array>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <iterator>
#include <sstream>
#include <string>
#include <vector>

namespace
{
constexpr uint32_t kOsBase = 0x200000, kCodeBase = 0x201128;
constexpr uint32_t kRecord = 0x10000, kParams = 0x10100;
constexpr uint32_t kStack = 0x18000, kReturn = 0x1000;

std::vector<uint8_t> readFile(const char* path)
{
    std::ifstream f(path, std::ios::binary);
    if(!f) { std::cerr << "cannot open " << path << "\n"; std::exit(2); }
    return {std::istreambuf_iterator<char>(f), std::istreambuf_iterator<char>()};
}

std::vector<uint8_t> hexBytes(const std::string& s, size_t expected)
{
    if(s.size() != 2 * expected) { std::cerr << "fixture byte count\n"; std::exit(2); }
    std::vector<uint8_t> out(expected);
    for(size_t i = 0; i < expected; ++i)
        out[i] = static_cast<uint8_t>(std::stoul(s.substr(2 * i, 2), nullptr, 16));
    return out;
}

class BareColdFire final : public mc68k::Mc68k
{
public:
    BareColdFire(const std::vector<uint8_t>& os, const std::vector<uint8_t>& runtime,
                 uint32_t runtimeBase, uint32_t handlerWord)
        : Mc68k(M68K_CPU_TYPE_MCF5206E), m_os(os), m_runtime(runtime),
          m_runtimeBase(runtimeBase), m_handlerWordAddress(handlerWord) {}

    uint8_t read8(uint32_t addr) override
    {
        if(addr < m_work.size()) return m_work[addr];
        if(addr >= 0x01000000 && addr - 0x01000000 < m_sram.size())
            return m_sram[addr - 0x01000000];
        if(addr >= m_handlerWordAddress && addr - m_handlerWordAddress < 4)
            return m_handlerWord[addr - m_handlerWordAddress];
        if(addr >= kOsBase && addr - kOsBase < m_os.size())
            return m_os[addr - kOsBase];
        if(addr >= m_runtimeBase && addr - m_runtimeBase < m_runtime.size())
            return m_runtime[addr - m_runtimeBase];
        if(++m_badReads <= 3)
            std::fprintf(stderr, "unmapped handler read %08x at pc %08x\n", addr, getPC());
        return 0;
    }

    uint16_t read16(uint32_t addr) override
    {
        return static_cast<uint16_t>(read8(addr) << 8 | read8(addr + 1));
    }

    uint16_t readImm16(uint32_t addr) override { return read16(addr); }

    void write8(uint32_t addr, uint8_t value) override
    {
        if(addr < m_work.size()) { m_work[addr] = value; return; }
        if(addr >= 0x01000000 && addr - 0x01000000 < m_sram.size())
        { m_sram[addr - 0x01000000] = value; return; }
        if(addr >= m_handlerWordAddress && addr - m_handlerWordAddress < 4)
        { m_handlerWord[addr - m_handlerWordAddress] = value; return; }
        std::fprintf(stderr, "unmapped handler write %08x at pc %08x\n", addr, getPC());
        std::exit(1);
    }

    void write16(uint32_t addr, uint16_t value) override
    {
        write8(addr, static_cast<uint8_t>(value >> 8));
        write8(addr + 1, static_cast<uint8_t>(value));
    }

    uint32_t onIllegalInstruction(uint32_t opcode) override
    {
        std::fprintf(stderr, "illegal handler opcode %04x at pc %08x\n", opcode, getPC());
        std::exit(1);
    }

    uint32_t getResetPC() override { return kReturn; }
    uint32_t getResetSP() override { return kStack; }

    std::array<uint8_t, 84> runHandler(uint32_t pc,
        const std::vector<uint8_t>& shared, const std::vector<uint8_t>& params,
        const std::vector<uint8_t>& before)
    {
        m_work.fill(0);
        m_sram.fill(0);
        m_badReads = 0;
        for(size_t i = 0; i < 4; ++i)
        {
            m_sram[0x150c + i] = shared[i];
            m_handlerWord[i] = shared[i];
        }
        reset();
        for(int i = 0; i < 8; ++i)
        {
            m68k_set_reg(getCpuState(), static_cast<m68k_register_t>(M68K_REG_D0 + i), 0);
            m68k_set_reg(getCpuState(), static_cast<m68k_register_t>(M68K_REG_A0 + i), 0);
        }
        m68k_set_reg(getCpuState(), M68K_REG_A7, kStack);
        m68k_set_reg(getCpuState(), M68K_REG_SR, 0x2700);
        for(size_t i = 0; i < params.size(); ++i) m_work[kParams + i] = params[i];
        for(size_t i = 0; i < before.size(); ++i) m_work[kRecord + i] = before[i];
        auto put32 = [&](uint32_t addr, uint32_t value)
        {
            write16(addr, static_cast<uint16_t>(value >> 16));
            write16(addr + 2, static_cast<uint16_t>(value));
        };
        put32(kStack, kReturn);
        put32(kStack + 4, kRecord);
        put32(kStack + 8, kParams);
        setPC(pc);
        for(int n = 0; n < 10000 && getPC() != kReturn; ++n)
            exec();
        if(getPC() != kReturn || m_badReads)
        {
            std::fprintf(stderr, "handler failed to return cleanly, pc %08x, reads %u\n",
                         getPC(), m_badReads);
            std::exit(1);
        }
        std::array<uint8_t, 84> out{};
        for(size_t i = 0; i < out.size(); ++i) out[i] = m_work[kRecord + i];
        return out;
    }

private:
    const std::vector<uint8_t>& m_os;
    const std::vector<uint8_t>& m_runtime;
    uint32_t m_runtimeBase, m_handlerWordAddress;
    uint32_t m_badReads = 0;
    std::array<uint8_t, 0x20000> m_work{};
    std::array<uint8_t, 0x2000> m_sram{};
    std::array<uint8_t, 4> m_handlerWord{};
};

bool same(const std::array<uint8_t, 84>& got, const std::vector<uint8_t>& want,
          int id, int encoder, const char* which)
{
    for(size_t i = 0; i < got.size(); ++i)
        if(got[i] != want[i])
        {
            std::fprintf(stderr,
                "engine %02x encoder %d %s record byte %zu: %02x != %02x\n",
                id, encoder, which, i, got[i], want[i]);
            return false;
        }
    return true;
}
}

int main(int argc, char** argv)
{
    if(argc != 7)
    {
        std::cerr << "usage: md_handler_gate <MAIN_OS.bin> <runtime.bin> "
                     "<runtime-base> <md_handler_empty> "
                     "<md_handler_sram_word> <cases.txt>\n";
        return 2;
    }
    const auto os = readFile(argv[1]);
    const auto runtime = readFile(argv[2]);
    const auto runtimeBase = static_cast<uint32_t>(std::stoul(argv[3], nullptr, 0));
    const auto handlerBase = static_cast<uint32_t>(std::stoul(argv[4], nullptr, 0));
    const auto handlerWord = static_cast<uint32_t>(std::stoul(argv[5], nullptr, 0));
    std::ifstream f(argv[6]);
    if(!f) { std::cerr << "cannot open cases\n"; return 2; }
    BareColdFire cpu(os, runtime, runtimeBase, handlerWord);
    std::string line;
    unsigned count = 0, synthetic = 0;
    std::array<bool, 256> engines{};
    while(std::getline(f, line))
    {
        std::istringstream in(line);
        std::string idStr, pcStr, sharedHex, paramsHex, beforeHex, afterHex;
        int encoder;
        if(!(in >> idStr >> encoder >> pcStr >> sharedHex >> paramsHex >> beforeHex >> afterHex))
        { std::cerr << "malformed case\n"; return 2; }
        const auto id = static_cast<unsigned>(std::stoul(idStr, nullptr, 16));
        const auto sourcePc = static_cast<uint32_t>(std::stoul(pcStr, nullptr, 16));
        const auto shared = hexBytes(sharedHex, 4);
        const auto params = hexBytes(paramsHex, 16);
        const auto before = hexBytes(beforeHex, 84);
        const auto after = hexBytes(afterHex, 84);
        if(sourcePc < kCodeBase || sourcePc >= 0x204330)
        { std::cerr << "case handler outside source slice\n"; return 2; }
        auto original = cpu.runHandler(sourcePc, shared, params, before);
        auto ported = cpu.runHandler(handlerBase + sourcePc - kCodeBase,
                                     shared, params, before);
        if(!same(original, after, id, encoder, "source") ||
           !same(ported, after, id, encoder, "ported"))
            return 1;
        // The firmware map= path leaves TRX-S2 on the empty handler.
        // Execute its descriptor handler offline on the same nine vectors,
        // comparing the author's bytes to the relocated unit.
        if(id == 0x1d)
        {
            constexpr uint32_t trxS2 = 0x201e46;
            auto sourceS2 = cpu.runHandler(trxS2, shared, params, before);
            auto portS2 = cpu.runHandler(handlerBase + trxS2 - kCodeBase,
                                         shared, params, before);
            if(sourceS2 != portS2)
            {
                std::fprintf(stderr, "TRX-S2 descriptor mismatch at encoder %d\n", encoder);
                return 1;
            }
            ++synthetic;
        }
        engines[id] = true;
        ++count;
    }
    unsigned engineCount = 0;
    for(bool v : engines) engineCount += v;
    std::cout << "PASS: " << count << " handler cases, " << engineCount
              << " engines, 84 record bytes per case match source and port; "
              << synthetic << " additional TRX-S2 descriptor comparisons\n";
    return 0;
}
