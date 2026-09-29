"""Build relocation candidates from unchanged Spectrum/Character sources.

Run: python3 -m tools.experimental.dsp_part_loader.build_candidates
This is relocation evidence, NOT admission or hardware qualification. Processing
bounds are deliberately unknown, so the planner refuses these candidates until
separate worst-case measurements are supplied. No shipping build is modified.
"""
import hashlib
import json
import os
from pathlib import Path
import sys

from .package import Package, Relocation, Section

ROOT = Path(__file__).resolve().parents[3]


def build(name):
    sys.path.insert(0, str(ROOT / 'tools'))
    import toolpath  # noqa: F401
    os.environ.setdefault('REMIX', 'analog-bassdrum')
    import build_bus
    from remix import registry

    if name not in ('spectrum', 'character'):
        raise ValueError('only the two reviewed private-state inserts are candidates')
    if not build_bus.DISASM.exists() or os.environ.get('NOROUNDTRIP') == '1':
        raise ValueError('assembler round-trip audit required')
    mod = registry.by_name(name)
    source = (ROOT / mod.dsp.asm).read_text()
    table = tuple(mod.dsp.ptable)
    if source.count('$fab1e0') != 1 or not table:
        raise ValueError('expected one manifest table base')

    def oracle(base):
        # Same supported P-table placement as the ordinary build; no DSP rewrite.
        words, symbols = build_bus.assemble_syms(
            source.replace('$fab1e0', f'${base:x}'), base + len(table), mod.key)
        return table + tuple(words), symbols

    origin = 0x1000
    baseline, symbols = oracle(origin)
    normalized = list(baseline)
    relocations = []
    moved, _ = oracle(0x1400)
    if len(moved) != len(baseline):
        raise ValueError('instruction widths change with placement')
    for offset, (old, new) in enumerate(zip(baseline, moved)):
        if old == new:
            continue
        if new - old != 0x400 or not origin <= old < origin + len(baseline):
            raise ValueError(f'{name}: unsupported relocation at word {offset}')
        normalized[offset] = old - origin
        relocations.append(Relocation('P', offset, 'P', old - origin))
    source_hash = hashlib.sha256((source + json.dumps(table)).encode()).hexdigest()
    package = Package(name, (Section('P', tuple(normalized)),), tuple(relocations),
                      symbols['init'] - origin, symbols['proc'] - origin,
                      0x84, None, '', source_hash, slots=('fx1',))
    # Independent placements: crossing address bits, including non-round bases.
    for base in (0x1000, 0x1400, 0x1801, 0x2407):
        expected, syms = oracle(base)
        if package.relocate({'P': base})['P'] != expected:
            raise ValueError(f'{name}: relocation disagrees with assembly at {base:x}')
        if (base + package.init, base + package.proc) != (syms['init'], syms['proc']):
            raise ValueError('entry point relocation mismatch')
    return package


def main():
    out = ROOT / 'out/dsp-part-loader'
    out.mkdir(parents=True, exist_ok=True)
    for name in ('spectrum', 'character'):
        package = build(name)
        (out / f'{name}.json').write_text(package.to_json() + '\n')
        print(f'{name}: {len(package.sections[0].words)} P words, '
              f'{len(package.relocations)} relocations; four placements byte-identical; '
              'processing admission pending')


if __name__ == '__main__':
    main()
