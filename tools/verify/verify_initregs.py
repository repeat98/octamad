#!/usr/bin/env python3
"""No module's init may write r1 (or n1/m1): the stock FX1 dispatcher keeps
the effect id in r1 across `jsr init` and indexes PROC_TABLE with it
afterwards (P:0x4c8..0x4d7 on payload A), so an init that leaves r1 elsewhere
sends the proc call to P:0 = the reset vector. Image 99 hung
every core that loaded a Spectrum on FX1 at project load, found under the
ColdFire port; dsp_host cannot see it because it calls init and proc itself.

    python3 tools/verify/verify_initregs.py [remix]      

A static scan of each DSP module's source from `init:` to the first `rts`
for a write to r1 / n1 / m1 (a `move ...,r1`, `,n1`, `,m1`, a `(r1)+` style
update, `lua`, or a `do`/`rep` count register). Stock code and servers are
scanned too: r1 is the dispatcher's on both slots.
"""
import os, pathlib, re, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
from remix import registry

def init_block(src: str) -> str:
    m = re.search(r"^init:\s*$(.*?)^\s+rts\b", src, re.S | re.M)
    return m.group(1) if m else ""

WRITE = re.compile(r"^\s*(move|movem|lua|tfr)\b[^;]*,\s*(r1|n1|m1)\s*(;.*)?$|^\s*[a-z]+[^;]*\((r1)\)[+-]|^\s*(do|rep)\s+(r1|n1|m1)\b", re.M)

def main():
    name = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("REMIX")
    remix = registry.remix(name); mods = registry.modules()
    fails = 0; checked = 0
    for key in remix.modules:
        mod = mods.get(key)
        dsp = getattr(mod, "dsp", None)
        asm = getattr(dsp, "asm", None) if dsp else None
        if not asm or not pathlib.Path(asm).is_file():
            continue
        block = init_block(pathlib.Path(asm).read_text())
        if not block:
            continue
        checked += 1
        hits = [l.strip() for l in block.splitlines() if WRITE.search(l)]
        if hits:
            fails += 1
            print(f"  [FAIL] {key}: init writes r1/n1/m1: " + " | ".join(hits[:3]))
        else:
            print(f"  [PASS] {key}: init preserves r1")
    print(f"init-registers: {checked} module inits scanned, {fails} failure(s)")
    sys.exit(1 if fails else 0)

if __name__ == "__main__":
    main()
