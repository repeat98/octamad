#!/usr/bin/env python3
# ###
# IP: GHIDRA
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
##
"""Expand dsp56300.sinc.in into dsp56300.sinc.

The DSP56300 encodings in the Family Manual are written as 24-character bit
strings ("0000101001MMMRRR0S0bbbbb").  The template lets constructors use
those strings directly:

  {0000101001MMMRRR0S0bbbbb}   -> k23_14=0x29 & k7_7=0 & k5_5=0
                                  (runs of 0/1 become constraints on generated
                                  fields; letters, '?' and 'o' are free bits)

  kHI_LO / sHI_LO anywhere      -> an unsigned / signed field over bits HI..LO
                                  of the instruction word is generated

  @regtable NAME r|w BITS SET [TEMP]
                                -> a subtable decoding a register code held in
                                  BITS ("20-16" or "21-20,18-16"); 'r' tables
                                  export the (limited) 24-bit source value, 'w'
                                  tables store TEMP into the destination with the
                                  DSP56300's width rules.

Usage: gen_sinc.py dsp56300.sinc.in dsp56300_np.sinc.in dsp56300.sinc
"""
import re
import sys

REGS6 = {
    0x04: 'x0', 0x05: 'x1', 0x06: 'y0', 0x07: 'y1',
    0x08: 'a0', 0x09: 'b0', 0x0a: 'a2', 0x0b: 'b2',
    0x0c: 'a1', 0x0d: 'b1', 0x0e: 'a', 0x0f: 'b',
    0x2a: 'ep', 0x30: 'vba', 0x31: 'sc',
    0x38: 'sz', 0x39: 'sr', 0x3a: 'omr', 0x3b: 'sp',
    0x3c: 'ssh', 0x3d: 'ssl', 0x3e: 'la', 0x3f: 'lc',
}
for i in range(8):
    REGS6[0x10 + i] = 'r%d' % i
    REGS6[0x18 + i] = 'n%d' % i
    REGS6[0x20 + i] = 'm%d' % i

SETS = {
    # name: (list of 6-bit codes, value-in-field function)
    'r5': ([c for c in REGS6 if 4 <= c < 0x20], lambda c: c),
    'r6': (sorted(REGS6), lambda c: c),
    'r6nos': ([c for c in sorted(REGS6) if c != 0x3c], lambda c: c),
    'ctl5': ([c for c in sorted(REGS6) if c >= 0x20], lambda c: c - 0x20),
    'dalu4': ([c for c in sorted(REGS6) if 4 <= c < 0x10], lambda c: c),
}

fields = {}


def field(kind, hi, lo):
    name = '%s%d_%d' % (kind, hi, lo)
    fields[name] = (lo, hi, kind == 's')
    return name


def pattern(bits):
    bits = re.sub(r'[\s_]', '', bits)
    if len(bits) != 24:
        raise ValueError('pattern not 24 bits: %r' % bits)
    cons = []
    i = 0
    while i < 24:
        if bits[i] in '01':
            j = i
            while j < 24 and bits[j] in '01':
                j += 1
            hi, lo = 23 - i, 23 - (j - 1)
            cons.append('%s=0x%x' % (field('k', hi, lo), int(bits[i:j], 2)))
            i = j
        else:
            i += 1
    if not cons:
        raise ValueError('pattern with no constant bits: %r' % bits)
    return ' & '.join(cons)


def segs(spec):
    out = []
    for part in spec.split(','):
        hi, lo = (int(x) for x in part.split('-'))
        out.append((hi, lo))
    return out


def code_constraint(segments, value):
    width = sum(hi - lo + 1 for hi, lo in segments)
    cons = []
    shift = width
    for hi, lo in segments:
        w = hi - lo + 1
        shift -= w
        cons.append('%s=0x%x' % (field('k', hi, lo), (value >> shift) & ((1 << w) - 1)))
    return ' & '.join(cons)


def reg_read(r):
    if r in ('a', 'b'):
        return '{ local v:3 = sat24(%s); export v; }' % r
    if r in ('a2', 'b2'):
        return '{ local v:3 = sext(%s); export v; }' % r
    if r == 'sr':
        return '{ local v:3 = 0; packSR(v); export v; }'
    if r == 'sp':
        return '{ local v:3 = zext(ssp / 6); export v; }'
    if r == 'ssh':
        return '{ local v:3 = *[SS]:3 (ssp + 3); ssp = ssp - 6; export v; }'
    if r == 'ssl':
        return '{ local v:3 = *[SS]:3 ssp; export v; }'
    return '{ export %s; }' % r


def reg_write(r, t):
    if r in ('a', 'b'):
        return '{ local v:7 = sext(%s); %s = v << 24; }' % (t, r)
    if r in ('a2', 'b2'):
        return '{ %s = %s:1; }' % (r, t)
    if r == 'sr':
        return '{ unpackSR(%s); }' % t
    if r == 'sp':
        return '{ ssp = %s:2 * 6; }' % t
    if r == 'ssh':
        return '{ ssp = ssp + 6; *[SS]:3 (ssp + 3) = %s; }' % t
    if r == 'ssl':
        return '{ *[SS]:3 ssp = %s; }' % t
    return '{ %s = %s; }' % (r, t)


def regtable(m):
    name, mode, bits, setname = m.group(1), m.group(2), m.group(3), m.group(4)
    temp = m.group(5)
    codes, conv = SETS[setname]
    sg = segs(bits)
    lines = []
    for c in codes:
        r = REGS6[c]
        cons = code_constraint(sg, conv(c))
        body = reg_read(r) if mode == 'r' else reg_write(r, temp)
        lines.append('%s: "%s" is %s %s' % (name, r, cons, body))
    return '\n'.join(lines)


CONDS = [
    ('cc', '!C'), ('ge', 'N == V'), ('ne', '!Z'), ('pl', '!N'),
    ('nn', 'Z || (!U && !E)'), ('ec', '!E'), ('lc', '!L'), ('gt', '!Z && (N == V)'),
    ('cs', 'C'), ('lt', 'N != V'), ('eq', 'Z'), ('mi', 'N'),
    ('nr', '!Z && (U || E)'), ('es', 'E'), ('ls', 'L'), ('le', 'Z || (N != V)'),
]


def cctable(m):
    name, bits = m.group(1), m.group(2)
    sg = segs(bits)
    return '\n'.join('%s: "%s" is %s { local c:1 = %s; export c; }'
                     % (name, mn, code_constraint(sg, i), expr)
                     for i, (mn, expr) in enumerate(CONDS))


def alutable(m):
    """@alu PATTERN8 @| mnemonic @| operands @| extra constraints @| semantics"""
    parts = [p.strip() for p in m.group(1).split('@|')]
    pat8, mnem, opnds, extra, sem = parts
    pat = '{????????????????%s}' % pat8.replace(' ', '')
    cons = pat + (' & ' + extra if extra else '')
    return ('ALUm: "%s" is %s { }\nALU: %s is %s { %s }'
            % (mnem, pat, opnds, cons, sem))


def main(inputs, outp):
    text = ''.join(open(i).read() for i in inputs)
    text = re.sub(r'^@regtable\s+(\w+)\s+([rw])\s+([\d,\-]+)\s+(\w+)(?:\s+(\w+))?\s*$',
                  regtable, text, flags=re.M)
    text = re.sub(r'^@cctable\s+(\w+)\s+([\d,\-]+)\s*$', cctable, text, flags=re.M)
    text = re.sub(r'^@alu\s+(.*)$', alutable, text, flags=re.M)
    text = re.sub(r'\{([01A-Za-z?\s_]{16,40})\}', lambda m: pattern(m.group(1)), text)
    for m in re.finditer(r'\b([ks])(\d+)_(\d+)\b', text):
        field(m.group(1), int(m.group(2)), int(m.group(3)))
    decl = []
    for name in sorted(fields, key=lambda n: (fields[n][1], fields[n][0], n)):
        lo, hi, signed = fields[name]
        decl.append('  %-8s = (%d,%d)%s' % (name, lo, hi, ' signed' if signed else ''))
    text = text.replace('@@FIELDS@@', '\n'.join(decl))
    header = ('# GENERATED by tools/gen_sinc.py from %s -- edit the templates, '
              'not this file.\n' % ', '.join(i.split('/')[-1] for i in inputs))
    open(outp, 'w').write(header + text)


if __name__ == '__main__':
    main(sys.argv[1:-1], sys.argv[-1])
