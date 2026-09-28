#!/usr/bin/env python3
"""Which remixes' images a change moved: every remix built from the base and
from this tree, artifact and report compared byte for byte.

    python3 tools/verify/image_identity.py [--base origin/main] [--remixes a b ...]
    make identity [BASE=origin/main]

A build change reaches every remix in principle; in practice most of the
27 images do not change, and a gate that only reads the image has nothing
new to say about an image that is bit-identical to the one it already
passed on. `scripts/refhash.sh` pins 24 build-FLAG configurations of one
layout (bus, plain, DEV, the probes, the overrides); this pins the 27
remixes. `reach` runs it for a change to the build and then checks only
the remixes it names.

The base is built in a detached worktree of the merge-base under
out/identity/base (kept between runs, moved to the new merge-base when it
changes) with the shared vendor/ and .venv/ links, the stock slice, its
submodules and this tree's build memo. Both trees build with
`REMIX=<r> BUILD=0 XBUS=1 SPEC=1` (the shipping flags; `make bus`). A
remix that builds in neither tree is unchanged; one that builds in only
one is changed.

Output: one line per remix, `out/identity/changed.json` (the changed
remixes, for `reach --run`), exit 0 whether or not anything changed. Exit
1 only when the tool itself could not run (no stock slice, no merge-base).
"""
import argparse
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
from remix import registry  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "out/identity"
BASE_TREE = OUT / "base"
FLAGS = {"BUILD": "0", "XBUS": "1", "SPEC": "1"}
TRACEBACK_LINE = re.compile(r'File "[^"]*", line \d+')


def git(*args, cwd=ROOT, check=True):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=check)


def base_tree(merge_base):
    """A worktree of `merge_base` at out/identity/base, reused when it is
    already there at that commit."""
    marker = BASE_TREE / ".identity-sha"
    if BASE_TREE.is_dir() and marker.is_file() and marker.read_text().strip() == merge_base:
        return BASE_TREE
    if BASE_TREE.exists():
        git("worktree", "remove", "--force", str(BASE_TREE), check=False)
        shutil.rmtree(BASE_TREE, ignore_errors=True)
    git("worktree", "prune", check=False)
    git("worktree", "add", "--detach", str(BASE_TREE), merge_base)
    for name in ("vendor", ".venv"):
        if (ROOT / name).exists():
            os.symlink(os.path.realpath(ROOT / name), BASE_TREE / name)
    (BASE_TREE / "out/raw").mkdir(parents=True)
    shutil.copy2(ROOT / "out/raw/section_3_MAIN_OS.bin", BASE_TREE / "out/raw/section_3_MAIN_OS.bin")
    subprocess.run(["git", "submodule", "update", "--init"], cwd=BASE_TREE, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    marker.write_text(merge_base + "\n")
    return BASE_TREE


def build(tree, remix):
    """(rc, sha256 of the image or None, sha256 of the normalised report)."""
    env = dict(os.environ)
    for var in ("MAKEFLAGS", "MFLAGS", "MAKEOVERRIDES"):
        env.pop(var, None)
    env.update(FLAGS)
    env["REMIX"] = remix
    env.setdefault("OCTABAM_CACHE", str(ROOT / "out/cache"))
    image = tree / "out/mainos_bus.bin"
    if image.exists():
        image.unlink()
    r = subprocess.run([sys.executable, "tools/build/build_bus.py"], cwd=tree, env=env,
                       capture_output=True, text=True)
    report = TRACEBACK_LINE.sub('File "<src>", line <n>', r.stdout + r.stderr)
    report = report.replace(str(tree), "<tree>")
    img = hashlib.sha256(image.read_bytes()).hexdigest() if image.exists() else None
    return r.returncode, img, hashlib.sha256(report.encode()).hexdigest(), report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default="origin/main")
    ap.add_argument("--remixes", nargs="*", help="only these (default: every remix)")
    ap.add_argument("--reports", action="store_true", help="keep both reports per changed remix under out/identity/")
    a = ap.parse_args(argv)
    if not (ROOT / "out/raw/section_3_MAIN_OS.bin").is_file():
        sys.exit("image_identity: out/raw/section_3_MAIN_OS.bin is missing (make os && make recon)")
    mb = git("merge-base", a.base, "HEAD", check=False)
    if mb.returncode:
        sys.exit(f"image_identity: no merge-base with {a.base}: {mb.stderr.strip()}")
    merge_base = mb.stdout.strip()
    OUT.mkdir(parents=True, exist_ok=True)
    base = base_tree(merge_base)
    remixes = a.remixes or registry.remix_names()
    print(f"image_identity: {len(remixes)} remixes, base {merge_base[:10]} ({a.base}) vs this tree", flush=True)
    changed, rows = [], []
    for name in remixes:
        rc_b, img_b, rep_b, text_b = build(base, name)
        rc_h, img_h, rep_h, text_h = build(ROOT, name)
        if rc_b and rc_h:
            status = "unbuilt"            # fails on both sides: nothing moved
        elif (rc_b, img_b, rep_b) == (rc_h, img_h, rep_h):
            status = "identical"
        elif img_b == img_h and img_b is not None:
            status = "report"             # same bytes, different report
        else:
            status = "CHANGED"
        if status in ("CHANGED", "report"):
            changed.append(name)
            if a.reports:
                (OUT / f"{name}.base.txt").write_text(text_b)
                (OUT / f"{name}.head.txt").write_text(text_h)
        rows.append((name, status, img_h[:12] if img_h else "-"))
        print(f"  {status:10} {name:18} {rows[-1][2]}", flush=True)
    # the shipping image back at out/mainos_bus.bin, as make check leaves it
    (OUT / "changed.json").write_text(json.dumps(changed) + "\n")
    n = sum(1 for _, s, _ in rows if s == "identical")
    print(f"\nimage_identity: {n} identical, {len(changed)} changed"
          + (": " + ", ".join(changed) if changed else "") + f"  -> {OUT.relative_to(ROOT)}/changed.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
