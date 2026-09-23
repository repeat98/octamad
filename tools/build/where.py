#!/usr/bin/env python3
"""What do we already know about this ColdFire address, and what's actually
there? One command instead of re-grepping docs/ and re-typing an objdump
invocation:

    python3 tools/build/where.py 0x40004d40
    make where A=0x40004d40                  # same thing
    make where A=0x40004d40 N=128             # wider disassembly window
    make where A=0x40004d40 NOTE="confirmed under the port: ..."
                                               # record a NEW finding, in place

Prints, in order:
  1. every note firmware/symbols.toml already has for this exact address
     (seeded from docs/CLAUDE.md prose, or added by a previous `NOTE=`)
  2. the nearest OTHER recorded addresses, so you can tell whether you're
     inside a documented region even without an exact hit
  3. a live EMAC-correct disassembly window around the address, via
     scripts/disasm.sh emac -- the same tool `make disasm`'s docstring
     recommends, run for you instead of re-typed by hand

With NOTE=, appends that text to the address's entry (source recorded as
"session <today>") and saves -- so the next `where` on this address, in this
session or a future one, already has it.
"""
import argparse, pathlib, subprocess, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import symtable  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
NEARBY_WINDOW = 0x200
NEARBY_MAX = 6


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("addr")
    ap.add_argument("--bytes", "-n", type=lambda s: int(s, 0), default=64,
                    help="disassembly window size (default 64)")
    ap.add_argument("--note", default=None,
                    help="record a new finding for this address")
    ap.add_argument("--name", default=None, help="name this address (with --note)")
    ap.add_argument("--kind", default=None,
                    help="function|table|hook-site|cave|poke|detour|global (with --note)")
    ap.add_argument("--confidence", default=None, choices=["doc", "measured"],
                    help="with --note (default: doc)")
    args = ap.parse_args()
    addr = symtable.norm(args.addr)
    ival = int(addr, 16)

    if args.note:
        source = f"session {__import__('datetime').date.today().isoformat()}"
        added = symtable.add_note(addr, args.note, source, name=args.name,
                                  kind=args.kind, confidence=args.confidence)
        print(f"{'recorded' if added else 'already on file (unchanged)'}: "
             f"{addr} -- {args.note}")

    entries = symtable.load()
    e = entries.get(addr)
    print(f"\n=== {addr} ===")
    if e:
        if e.get("name"):
            print(f"  name: {e['name']}  ({e.get('kind', 'unknown')}, "
                 f"{e.get('confidence', 'doc')})")
        for n in e["notes"]:
            print(f"  [{n['date']}] ({n['source']}) {n['text']}")
    else:
        print("  no recorded notes -- nothing seeded or learned here yet")

    nearby = sorted(
        (abs(int(a, 16) - ival), a, en) for a, en in entries.items()
        if a != addr and abs(int(a, 16) - ival) <= NEARBY_WINDOW)[:NEARBY_MAX]
    if nearby:
        print(f"\n  nearby recorded addresses (within 0x{NEARBY_WINDOW:x}):")
        for dist, a, en in nearby:
            sign = "+" if int(a, 16) >= ival else "-"
            label = en.get("name") or (en["notes"][0]["text"][:70] + "..."
                                       if en["notes"] else "")
            print(f"    {a}  ({sign}0x{dist:x})  {label}")

    disasm = ROOT / "scripts" / "disasm.sh"
    raw = ROOT / "out" / "raw" / "section_3_MAIN_OS.bin"
    if disasm.is_file() and raw.is_file() and ival >= 0x40000400:
        print(f"\n  -- scripts/disasm.sh emac {addr} {args.bytes} --")
        r = subprocess.run(["bash", str(disasm), "emac", addr, str(args.bytes)],
                           cwd=ROOT, capture_output=True, text=True)
        print((r.stdout or r.stderr).rstrip())
    else:
        print("\n  (no out/raw/section_3_MAIN_OS.bin -- run 'make os' then "
             "'make recon' for a live disassembly window)")


if __name__ == "__main__":
    main()
