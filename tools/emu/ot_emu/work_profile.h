// Explicit frame-scoped firmware work profile. No guest writes or timing changes.
#pragma once
#include <array>
#include <fstream>
#include <map>
#include <stdexcept>
#include <string>
#include <vector>
#include "dsp.h"

namespace ot
{
class WorkProfile
{
    struct Frame { uint64_t id, cpu; std::array<uint64_t, 2> dsp, skipped; bool complete; };
    DspPair& m_dsp;
    uint64_t m_frame, m_cpu = 0, m_first;
    std::array<uint64_t, 2> m_prevDsp{}, m_prevSkip{};
    std::map<uint32_t, uint64_t> m_pcs;
    std::vector<Frame> m_frames;

    void flush(bool complete)
    {
        Frame row{m_frame - m_first, m_cpu, {}, {}, complete};
        for(int c = 0; c < 2; ++c)
        {
            const auto work = m_dsp.profileWork(c), skip = m_dsp.profileSkipped(c);
            row.dsp[c] = work - m_prevDsp[c]; row.skipped[c] = skip - m_prevSkip[c];
            m_prevDsp[c] = work; m_prevSkip[c] = skip;
        }
        m_frames.push_back(row); m_cpu = 0;
    }
    static std::ofstream file(const std::string& path)
    {
        std::ofstream out(path);
        out.exceptions(std::ios::failbit | std::ios::badbit);
        return out;
    }
public:
    WorkProfile(DspPair& dsp, uint64_t frame) : m_dsp(dsp), m_frame(frame), m_first(frame)
    { m_dsp.beginWorkProfile(); }
    void note(uint32_t pc, uint64_t frame)
    {
        if(frame != m_frame)
        {
            flush(m_frame != m_first && frame == m_frame + 1);
            m_frame = frame;
        }
        ++m_pcs[pc]; ++m_cpu;
    }
    void finish(const std::string& prefix)
    {
        flush(false); // first and final buckets are partial, excluded from percentiles
        m_dsp.endWorkProfile();
        auto cpu = file(prefix + ".cpu.tsv");
        for(const auto& [pc,n] : m_pcs) cpu << std::hex << pc << ' ' << std::dec << n << '\n';
        for(int c = 0; c < 2; ++c)
        {
            auto dsp = file(prefix + ".dsp" + std::to_string(c) + ".tsv");
            for(const auto& [pc,n] : m_dsp.profilePcs(c)) dsp << std::hex << pc << ' ' << std::dec << n << '\n';
        }
        auto frames = file(prefix + ".frames.tsv");
        frames << "frame cpu dsp0 dsp1 skipped0 skipped1 complete\n";
        for(const auto& f : m_frames)
            frames << f.id << ' ' << f.cpu << ' ' << f.dsp[0] << ' ' << f.dsp[1]
                   << ' ' << f.skipped[0] << ' ' << f.skipped[1] << ' ' << f.complete << '\n';
    }
};
}
