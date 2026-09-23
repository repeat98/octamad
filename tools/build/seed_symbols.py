#!/usr/bin/env python3
"""One-off (re-runnable) seed of firmware/symbols.toml from the addresses
already sitting in this repo's prose -- CLAUDE.md, docs/**/*.md, and any
modules/*/STATUS.md or README.md. It does not touch source code (.py/.s):
those addresses already sit next to a Python name, so indexing them again
would just duplicate the source, not add information.

For each ColdFire address (0x40xxxxxx / 0x48xxxxxx / 0x4fxxxxxx, 8 hex
digits) it finds, the note is the whole paragraph the address appears in --
that's usually the one sentence that says what the address IS. Re-running
this is safe: `symtable.add_note` skips a (text, source) pair already on
file, so editing a doc and re-seeding only adds what changed.

    python3 tools/build/seed_symbols.py [--dry-run]
"""
import pathlib, re, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import symtable  # noqa: E402

ADDR_RE = re.compile(r"\b0x4[089f][0-9a-f]{6}\b")
ROOT = pathlib.Path(__file__).resolve().parents[2]

FILES = (
    [ROOT / "CLAUDE.md", ROOT / "README.md"]
    + sorted((ROOT / "docs").rglob("*.md"))
    + sorted((ROOT / "modules").rglob("STATUS.md"))
    + sorted((ROOT / "modules").rglob("README.md"))
)


def paragraphs(text: str):
    """(start_line, paragraph_text) for each blank-line-delimited block."""
    lines = text.splitlines()
    buf, start = [], 1
    for i, line in enumerate(lines, 1):
        if line.strip():
            if not buf:
                start = i
            buf.append(line)
        elif buf:
            yield start, "\n".join(buf)
            buf = []
    if buf:
        yield start, "\n".join(buf)


def main():
    dry = "--dry-run" in sys.argv
    # Batched in memory (one load, one save) rather than tools/build/symtable
    # .add_note()'s per-call round trip -- that's the right shape for one
    # interactive learn, not for ~1,300 seed notes.
    entries = {} if dry else symtable.load()
    added = seen_files = 0
    today = __import__("datetime").date.today().isoformat()
    for f in FILES:
        if not f.is_file():
            continue
        seen_files += 1
        rel = f.relative_to(ROOT)
        for start, para in paragraphs(f.read_text(errors="replace")):
            addrs = sorted(set(ADDR_RE.findall(para)))
            if not addrs:
                continue
            note = " ".join(para.split())
            if len(note) > 500:
                note = note[:497] + "..."
            for a in addrs:
                addr, source = symtable.norm(a), f"{rel}:{start}"
                if dry:
                    print(f"{addr}  {source}")
                    continue
                e = entries.setdefault(addr, {"name": "", "kind": "unknown",
                                              "confidence": "doc", "notes": []})
                if any(n["text"] == note and n["source"] == source
                       for n in e["notes"]):
                    continue
                e["notes"].append({"text": note, "source": source, "date": today})
                added += 1
    if dry:
        return
    symtable.save(entries)
    print(f"seed_symbols: scanned {seen_files} files, added {added} notes "
         f"-> {symtable.PATH} ({len(entries)} addresses total)")


if __name__ == "__main__":
    main()
