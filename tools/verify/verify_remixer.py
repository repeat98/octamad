#!/usr/bin/env python3
"""The remixer (`make remix`) opens and draws, headless.

    .venv/bin/python3 tools/verify/verify_remixer.py

Textual's test pilot runs tools/remix/app.py with the background rebuild
switched off. For stock and every remix it loads the selection and draws the
three panes with the cursor in each; then it presses `k` (cursor up) in
AVAILABLE and `K` (reset to stock). Two defects this covers:
- 27 Sep 2026 (86483481) the AVAILABLE pane read a variable the regroup
  had removed, and `make remix` raised NameError on its first draw;
- `k` was bound both to cursor-up and to reset-to-stock, so moving up
  threw the selection away (measured 30 Sep 2026: ok-ms -> stock).
[SKIP] without textual (`make emu-setup`).
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401

try:
    import textual  # noqa: F401
except ImportError:
    print("  [SKIP] verify_remixer: textual is not installed (make emu-setup)")
    sys.exit(0)

from remix import app as A, registry  # noqa: E402

A.RemixerScreen.ensure_sync = lambda self, probs=None: None     # no image builds


async def run():
    fails = []
    names = ["stock"] + [n for n in registry.remix_names() if not n.startswith("_")]
    app = A.Remixer()
    async with app.run_test(size=(160, 50)) as pilot:
        await pilot.pause()
        scr = app.screen
        for name in names:
            try:
                app.state.load_stock() if name == "stock" else app.state.load(name)
                for pane in (A.AVAILABLE, A.LOADED, A.UNIT):
                    scr.pane, scr.cur = pane, [0, 0, 0]
                    scr.rerender()
                    await pilot.pause()
            except Exception as e:                      # noqa: BLE001
                fails.append(f"{name}: drawing raised {type(e).__name__}: {e}")
        app.state.load("ok-ms")
        scr.pane, scr.cur = A.AVAILABLE, [3, 0, 0]
        await pilot.press("k")
        await pilot.pause()
        if app.state.loaded_name != "ok-ms" or scr.cur[A.AVAILABLE] != 2:
            fails.append(f"`k` in AVAILABLE: selection {app.state.loaded_name!r}, "
                         f"cursor {scr.cur[A.AVAILABLE]} (want 'ok-ms', 2)")
        await pilot.press("K")
        await pilot.pause()
        if app.state.loaded_name != "stock":
            fails.append(f"`K`: selection {app.state.loaded_name!r} (want 'stock')")
    return names, fails


def main():
    names, fails = asyncio.run(run())
    for f in fails:
        print("  [FAIL]", f)
    if not fails:
        print(f"  [PASS] verify_remixer: {len(names)} selections drawn in all three panes; "
              f"`k` moves the cursor, `K` resets to stock")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
