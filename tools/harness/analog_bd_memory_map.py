#!/usr/bin/env python3
"""Draw the built Analog BD remix's DSP allocation, without firmware bytes."""
import html
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/build'))
import ab_records

OUT = ROOT / 'out/analog-bassdrum/dynamic'
IMG = ROOT / 'out/analog-bassdrum/image'
COLORS = dict(stock='#435b73', resident='#eb9854', engine808='#ffd369',
              engine909='#dd755f', common='#7abfa9', state='#79a9dc',
              allocated='#7d8ea0', spare='#dce5ee', unknown='#eef1f4',
              shared0='#7a95c5', shared1='#a688c8')
parts = []


def rect(x, y, w, h, color, stroke='none'):
    parts.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" '
                 f'height="{h:.2f}" fill="{color}" stroke="{stroke}"/>')


def label(x, y, value, size=14, color='#193047', weight='normal', anchor='start'):
    parts.append(f'<text x="{x:.2f}" y="{y:.2f}" font-size="{size}" '
                 f'fill="{color}" font-weight="{weight}" text-anchor="{anchor}">'
                 f'{html.escape(str(value))}</text>')


def bar(y, title, total, segments, subtitle, axis_base=0):
    x0, width = 265, 1065
    label(45, y + 23, title, 18, weight='bold')
    rect(x0, y, width, 30, COLORS['unknown'], '#9aaab8')
    for start, end, color in segments:
        assert 0 <= start <= end <= total, (title, start, end, total)
        rect(x0 + width * start / total, y, width * (end - start) / total,
             30, COLORS[color])
    for fraction in (0, .25, .5, .75, 1):
        x = x0 + width * fraction
        parts.append(f'<line x1="{x:.2f}" y1="{y+30}" x2="{x:.2f}" '
                     f'y2="{y+38}" stroke="#647789"/>')
        label(x, y + 54, f'{axis_base+round(total*fraction):05X}',
              11, anchor='middle')
    label(x0, y + 76, subtitle, 13)


def counts(tag):
    blob = (IMG / f'upload_{tag}.bin').read_bytes()
    records, _ = ab_records.records(blob, ab_records.BASE, len(blob))
    return {name: (sum(n for sp, _, n, _ in records if sp == i),
                   max(a+n for sp, a, n, _ in records if sp == i))
            for i, name in enumerate('PXY')}


def core(tag, y, kernel, packages):
    data = counts(tag)
    base, end = kernel['base'], kernel['end']
    spring = base - 385
    p808 = packages[0]['program_words']
    p909 = packages[1]['program_words']
    label(45, y, f'CORE {0 if tag == "A" else 1} · payload {tag} · '
          f'tracks {"5–8" if tag == "A" else "1–4"}', 25, weight='bold')
    label(45, y + 27,
          f'Boot upload: P {data["P"][0]:,} words (includes shared boot code); '
          f'X {data["X"][0]:,}; Y {data["Y"][0]:,}', 14)
    ptop = max((a+n for sp, a, n, _ in
                ab_records.records((IMG / f'upload_{tag}.bin').read_bytes(),
                                   ab_records.BASE,
                                   (IMG / f'upload_{tag}.bin').stat().st_size)[0]
                if sp == 0 and a < 0x2000), default=0)
    bar(y + 53, 'Program P', 0x2000, [
        (0, spring, 'stock'), (spring, base, 'resident'),
        (base, base+p808, 'engine808'),
        (base+p808, base+p808+p909, 'engine909'),
        (base+p808+p909, end, 'spare'),
        (end, spring+1063, 'stock'),
        (spring+1063, ptop, 'stock')
    ], f'SPRING donor P:{spring:04X}–{spring+1063-1:04X}: '
       f'385 resident + 246 (808) + 377 (909) + 20 spare + 35 helper. '
       f'Mixed set shown; inactive code is loaded on demand.')
    bar(y + 153, 'Private X', 0x9000, [
        (0, 0x2840, 'allocated'), (0x2840, 0x2b40, 'common'),
        (0x2b40, 0x2f40, 'engine808'),
        (0x2f40, 0x2f40+1425, 'engine909'),
        (0x2f40+1425, 0x3700, 'spare'),
        (0x3700, 0x3808, 'state'),
        (0x3808, 0x9000, 'allocated')
    ], 'X:2840–2B3F common; 2B40–36FF engine tables (559 spare mixed); '
       '3700–3807 voice state + loader status. Gray also includes runtime FX use.')
    system = 0x795 if tag == 'A' else 0x7a5
    bar(y + 253, 'Private Y', 0xc000, [
        (0, system, 'stock'), (system, 0x1000, 'spare'),
        (0x1000, 0x4000, 'allocated'), (0x4000, 0xc000, 'allocated')
    ], 'Y:1000–3FFF four FX1 slots; 4000–BFFF two FX2 slots. '
       f'System boot data ends at {system-1:04X}; unallocated lower gap is measured.')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    meta = json.loads((IMG / 'dynamic.json').read_text())
    parts.append('<svg xmlns="http://www.w3.org/2000/svg" '
                 'viewBox="0 0 1400 1120" width="1400" height="1120">')
    rect(0, 0, 1400, 1140, '#f9fbfd')
    label(45, 55, 'Octatrack DSP memory · Analog BD remix', 33, weight='bold')
    label(45, 85, 'Built image, both cores · address values are 24-bit DSP words · '
          'mixed 808 + 909 Part illustrated', 16)
    core('A', 135, meta['kernels'][0], meta['packages'])
    core('B', 535, meta['kernels'][1], meta['packages'])
    label(45, 945, 'Shared on-chip window · P/X/Y alias · 64K words', 22, weight='bold')
    bar(961, 'Both cores', 0x10000, [
        (0, 0x8000, 'shared0'), (0x8000, 0x10000, 'shared1')
    ], 'DSP:30000–37FFF serves core 0 FX2 slots; 38000–3FFFF serves '
       'core 1 FX2 slots. Stock staging and boot code also touch this window.',
       axis_base=0x30000)
    legend = [('stock', 'stock code/data'), ('resident', 'loader + desk'),
              ('engine808', '808'), ('engine909', '909'),
              ('common', 'common tables'), ('state', 'state/status'),
              ('allocated', 'FX allocation / other X'),
              ('spare', 'unassigned or active-pool slack')]
    for i, (key, title) in enumerate(legend):
        x, y = 45 + (i % 4) * 337, 1085 + (i // 4) * 23
        rect(x, y-13, 16, 16, COLORS[key])
        label(x+23, y, title, 12)
    parts.append('</svg>')
    # Legend's second row extends beyond the original viewBox.
    svg = ''.join(parts).replace('viewBox="0 0 1400 1120"',
                                 'viewBox="0 0 1400 1140"').replace(
                                 'height="1120"', 'height="1140"')
    output = ROOT / 'modules/analog-bassdrum/memory-map.svg'
    output.write_text(svg)
    (OUT / 'memory-map.svg').write_text(svg)
    print(output)
    for tag in 'AB':
        print(tag, counts(tag))


if __name__ == '__main__':
    main()
