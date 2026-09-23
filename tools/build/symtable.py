#!/usr/bin/env python3
"""Read/write firmware/symbols.toml -- the project's own memory of what a
ColdFire address means, keyed by address, additive across sessions.

The problem this exists for: `CLAUDE.md` and `docs/` carry ~1,600 addresses
in prose (hook sites, tables, caves, pokes), and every session that needs to
know "what already happened at 0x4000abcd" re-greps for it, or worse,
re-disassembles and re-derives it from scratch. This file is the same facts,
indexed by address instead of buried in paragraphs, so `tools/build/where.py`
can answer in one lookup -- and so a session that LEARNS something new about
an address can record it in one line instead of a paragraph.

Schema (one entry per address, notes are additive -- never overwritten):

    [[sym]]
    addr = "0x400d5fdc"
    name = "FX2_IDS"            # "" if nobody has named it yet
    kind = "table"               # function | table | hook-site | cave |
                                  # poke | detour | global | unknown
    confidence = "doc"           # doc (prose only) | measured (port/hw)

      [[sym.notes]]
      text = "id-indexed FX2 dispatch table, 32 slots"
      source = "CLAUDE.md"
      date = "2026-09-22"

Only addresses and OUR OWN names/notes are stored -- no Elektron bytes, same
rule as everything else in this repo.
"""
import datetime, pathlib, re, sys

PATH = pathlib.Path("firmware/symbols.toml")
ADDR_RE = re.compile(r"^0x[0-9a-f]{6,8}$")


def norm(addr) -> str:
    """'400d5fdc', '0x400D5FDC', 0x400d5fdc -> '0x400d5fdc'."""
    if isinstance(addr, int):
        return f"0x{addr:08x}"
    s = addr.strip().lower()
    if not s.startswith("0x"):
        s = "0x" + s
    if not ADDR_RE.match(s):
        sys.exit(f"symtable: {addr!r} is not a hex address")
    return "0x" + s[2:].rjust(8, "0")


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def load() -> dict:
    """addr -> entry dict. Missing file -> {}."""
    if not PATH.is_file():
        return {}
    import tomllib
    doc = tomllib.loads(PATH.read_text())
    return {e["addr"]: e for e in doc.get("sym", [])}


def save(entries: dict) -> None:
    """entries: addr -> {name, kind, confidence, notes: [...]}. Deterministic
    output (sorted by address) so the file diffs cleanly in git."""
    PATH.parent.mkdir(parents=True, exist_ok=True)
    out = []
    for addr in sorted(entries):
        e = entries[addr]
        out.append("[[sym]]")
        out.append(f'addr = "{addr}"')
        out.append(f'name = "{_esc(e.get("name", ""))}"')
        out.append(f'kind = "{_esc(e.get("kind", "unknown"))}"')
        out.append(f'confidence = "{_esc(e.get("confidence", "doc"))}"')
        for n in e.get("notes", []):
            out.append("")
            out.append("  [[sym.notes]]")
            out.append(f'  text = "{_esc(n["text"])}"')
            out.append(f'  source = "{_esc(n["source"])}"')
            out.append(f'  date = "{_esc(n["date"])}"')
        out.append("")
    PATH.write_text("\n".join(out).rstrip() + "\n")


def add_note(addr, text, source, name=None, kind=None, confidence=None,
             date=None) -> bool:
    """Append one note to an address's entry (creating it if new). Returns
    False (no write) if this exact text+source is already recorded for this
    address -- re-running a seeder or re-learning the same fact is a no-op."""
    addr = norm(addr)
    entries = load()
    e = entries.setdefault(addr, {"name": "", "kind": "unknown",
                                  "confidence": "doc", "notes": []})
    if any(n["text"] == text and n["source"] == source for n in e["notes"]):
        return False
    if name:
        e["name"] = name
    if kind:
        e["kind"] = kind
    if confidence:
        e["confidence"] = confidence
    e["notes"].append({"text": text, "source": source,
                       "date": date or datetime.date.today().isoformat()})
    save(entries)
    return True


if __name__ == "__main__":
    n = len(load())
    print(f"{PATH}: {n} addresses" if n else f"{PATH}: none yet")
