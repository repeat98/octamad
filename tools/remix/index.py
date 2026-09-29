#!/usr/bin/env python3
"""Print the module index and the available remixes.

    python3 tools/remix/index.py

The authoritative list; a README's table is a copy.
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401  (every tools/ dir on sys.path)

from remix import registry  # noqa: E402
from remix.schema import Kind  # noqa: E402


from remix.rig import touches_coldfire  # noqa: E402


def matrix(mods):
    """The compatibility matrix: every pair of ColdFire-side modules through
    the ledger -- the same call the build makes, so a cell here IS what
    `make bus` would say. Printed rather than written down because a table
    in a README is a copy, and this one changes every time a module lands.
    """
    from remix import ledger
    cf = sorted((m for m in mods.values() if not m.is_stock and touches_coldfire(m)),
                key=lambda m: m.name)
    if len(cf) < 2:
        return
    # A BRIDGE (schema.Override) exists to let two other modules share a
    # site, and is refused unless both are in the remix. So a bridge's cell
    # is checked with its parties present, and a pair that a bridge joins is
    # marked ✓* -- refused alone, clean with the bridge.
    parties = {m.key: [mods[o.module] for o in (m.overrides or ())
                       if o.module in mods] for m in cf}
    bridges = [m for m in cf if parties[m.key]]
    print("COMPATIBILITY  (the ledger, pairwise: which ColdFire-side modules "
          "can share an image)\n")
    short = [m.name[:9] for m in cf]
    w = max(len(s) for s in short)
    print("  " + " " * (w + 2) + " ".join(f"{s[:3]:>3}" for s in short))
    reasons, joined = {}, {}
    for a in cf:
        row = []
        for b in cf:
            if a is b:
                row.append("  ·")
                continue
            sel = {m.key: m for m in [a, b] + parties[a.key] + parties[b.key]}
            probs = ledger.check(list(sel.values()))
            key = tuple(sorted((a.name, b.name)))
            if probs:
                fix = next((br for br in bridges if br not in (a, b)
                            and not ledger.check(list({**sel, br.key: br}.values()))),
                           None)
                if fix is not None:
                    row.append(" ✓*")
                    joined.setdefault(key, fix.name)
                else:
                    row.append("  x")
                    reasons.setdefault(key, probs[0])
            else:
                row.append("  ✓")
        print(f"  {a.name[:9]:<{w + 2}}" + " ".join(row))
    print()
    for (a, b), why in sorted(reasons.items()):
        print(f"  x {a} + {b}: {why}")
    for (a, b), br in sorted(joined.items()):
        print(f"  ✓* {a} + {b}: with {br}")
    if reasons or joined:
        print()
    print("  (a x is refused at build time, by name; ✓* needs the named bridge; "
          "a bridge's own row is\n   checked with the modules it bridges present. "
          "Anything not listed here is a DSP effect,\n   which the ledger checks "
          "by FX2 id, buffer region and private Y instead)\n")


def main():
    mods = registry.modules()
    print("MODULES  (modules/<name>/manifest.py)\n")
    for key in sorted(mods):
        m = mods[key]
        if m.is_stock:
            continue
        bits = []
        if m.menu is not None:
            bits.append(f"FX2 id 0x{m.menu.fx2_id:02x}")
            bits.append(f"{len(m.active_params)} knobs")
        if m.dsp is not None:
            bits.append(f"asm {m.dsp.asm}")
        for d in m.dsp_sites:
            bits.append(f"DSP site P:0x{d.site:05x}+{d.words} ({d.kind}, "
                        f"payload {'/'.join(sorted(d.payloads))}, "
                        f"{'copy of P:0x%05x..0x%05x' % d.copy if d.copy else 'asm ' + d.asm})")
        if m.cf_patches:
            bits.append(f"{len(m.cf_patches)} ColdFire cave"
                        f"{'s' if len(m.cf_patches) > 1 else ''}")
        print(f"  {m.name:<12} {m.kind.value:<10} [{m.key}]")
        print(f"      {m.doc}")
        print(f"      {' | '.join(bits)}")
        if m.menu is not None:
            knobs = ", ".join(f"{n}@{i}" for n, i in sorted(
                m.knob_map().items(), key=lambda kv: kv[1]))
            print(f"      knobs: {knobs}")
        print()

    from remix import stock
    print("STOCK FX2 EFFECTS  (tools/remix/stock.py -- already in every image;\n"
          "list one in a remix to KEEP its chooser row, by key)\n")
    for m in stock.MODULES:
        buf = "  [instance buffer -- not beside BusVerb/Nimbus/BusDelay]" \
            if m.claims is not None and m.claims.stock_instance_buffer else ""
        print(f"  {m.key:<12} FX2 id 0x{m.menu.fx2_id:02x}  {m.doc}{buf}")
        if m.params:
            knobs = ", ".join(f"{n}@{i}" for n, i in sorted(
                m.knob_map().items(), key=lambda kv: kv[1]))
            print(f"      knobs: {knobs}")
    # ⚠️ NOT "every remix" any more: what a remix gives up is DERIVED from
    # its two choosers -- an effect on neither is one it does not want -- and
    # each remix's is printed with it below when it differs from these.
    print(f"\n  given up by most remixes (on neither chooser): "
          f"{', '.join(stock.CONSUMED)}\n")

    matrix(mods)

    print("REMIXES  (remixes/<name>.py)\n")
    for name in registry.remix_names():
        r = registry.remix(name)
        default = "  <- default" if name == registry.DEFAULT_REMIX else ""
        print(f"  {r.name:<12} {r.doc}{default}")
        print(f"      modules: {', '.join(r.modules)}")
        if r.fx1:
            print(f"      also on the FX1 chooser: {', '.join(r.fx1)}")
        _hv = stock.region_of(stock.harvested(
            set(r.modules) | set(r.fx1 or [
                k for k in stock.p_spans("A")
                if registry.modules()[k].menu.fx2_id in stock.fx1_ids()])))
        if tuple(_hv) != stock.CONSUMED:
            print(f"      gives up (on neither chooser): "
                  f"{', '.join(_hv) or 'nothing'}")
        print(f"      unimplemented ids fall back to: {r.fallback}")
        print()
    print("Build one with:  make bus REMIX=<name>")


if __name__ == "__main__":
    main()
