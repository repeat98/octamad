"""Build a local source-audio probe against this worktree's port libraries.

The stock --dsp-pcwatch switch enables the instrumentation path. The local
copy additionally records X memory at that PC; no shipping port API changes.
"""
import pathlib
import re
import shlex
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]


def build(out, core, pc, knobs):
    out.mkdir(parents=True, exist_ok=True)
    source = (ROOT / 'tools/emu/ot_emu/dsp.cpp').read_text()
    marker = 'void DspPair::instrumentBefore(Core& c, const int i, const uint32_t pc)\n\t{'
    assert source.count(marker) == 1
    probe = '''
        if(i == CORE && pc == PC) {
            static FILE* output = std::fopen(std::getenv("AB_SOURCE_TRACE"), "w");
            static unsigned lines = 0;
            if(!output) std::abort();
            if(lines++ < 20000) {
                std::fprintf(output, "%llu", static_cast<unsigned long long>(c.executed));
                const unsigned bases[] = {0x418, 0, KNOBS, 0x3800};
                const unsigned sizes[] = {1, 32, 13, 8};
                for(unsigned span = 0; span < 4; ++span) {
                    std::fprintf(output, " |");
                    for(unsigned k = 0; k < sizes[span]; ++k)
                        std::fprintf(output, " %06x", c.mem->get(dsp56k::MemArea_X, bases[span]+k) & 0xffffff);
                }
                std::fputc('\\n', output);
            }
        }
'''.replace('CORE', str(core)).replace('PC', hex(pc)).replace('KNOBS', hex(knobs))
    src = out / 'dsp.cpp'
    src.write_text('#include <cstdlib>\n' + source.replace(marker, marker + probe))
    builddir = ROOT / 'out/emu'
    flags = (builddir / 'CMakeFiles/ot_emu.dir/flags.make').read_text()
    args = []
    for name in ('CXX_DEFINES', 'CXX_INCLUDES', 'CXX_FLAGS'):
        args += shlex.split(re.search(r'^' + name + r' = (.*)$', flags, re.M)[1])
    link = shlex.split((builddir / 'CMakeFiles/ot_emu.dir/link.txt').read_text())
    tail = link[link.index('CMakeFiles/ot_emu.dir/main.cpp.o'):]
    exe = out / 'ot_emu'
    tail[tail.index('-o') + 1] = str(exe)
    subprocess.run([link[0], *args, str(src), *tail], cwd=builddir,
                   check=True, capture_output=True)
    return exe
