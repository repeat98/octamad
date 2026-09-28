#!/usr/bin/env python3
"""The two Markdown copies of the registry are current, and every remix has
its README.

    python3 tools/verify/verify_docs.py

README.md's module table and docs/remixes/README.md are rendered from the
manifests and the selections by `make docs` (tools/remix/index.py --write);
this refuses a stale copy. It also refuses a remix directory without a
README.md. Eight merged modules and four remixes had no row or page on
27 Sep 2026, when the README was a hand copy nothing compared.
"""
import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
from remix import index, registry

ROOT = pathlib.Path(__file__).resolve().parents[2]


def main():
    fails = [f"{p.relative_to(ROOT)} is stale: make docs" for p in index.stale()]
    for name in registry.remix_names():
        d = registry.remix_dir(name)
        if d is None:
            fails.append(f"remixes/{name}.py: a remix is a directory, remixes/{name}/remix.py "
                         f"(or remixes/test/{name}/remix.py) + README.md")
        elif not (d / "README.md").exists():
            fails.append(f"{d.relative_to(ROOT)}/README.md: missing")
    for f in fails:
        print("  [FAIL]", f)
    n = len([m for m in registry.modules().values() if not m.is_stock])
    print(f"verify_docs: {n} modules, {len(registry.remix_names())} remixes, "
          f"{len(fails)} problem{'s' if len(fails) != 1 else ''}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
