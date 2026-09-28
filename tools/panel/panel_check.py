#!/usr/bin/env python3
"""Drive a running panel server over HTTP and check it end to end.

    tools/panel/panel_check.py --url http://localhost:8563 --out out/panel_check [--phase all|save|persist]

Phases (default `all` = boot, key, knob, save): the screen decodes to a
128x64 PNG; a page key changes the screen; a knob turn changes the
parameter's value (read from the firmware's memory through /peek); the
unit's own SAVE PROJECT (FUNC+MIXER on an MKI, PROJ on an MKII; RIGHT, DOWN
to SAVE, YES, YES) writes
sectors into the persistent card. `persist` runs against a server
restarted on the same card and checks the value saved in `save` is there.
The value and its address are kept in <out>/saved.json between the two.
"""
import argparse
import json
import pathlib
import sys
import time
import urllib.request


def get(url, timeout=120):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        body = r.read()
    try:
        return json.loads(body)
    except ValueError:
        return body


class Panel:
    def __init__(self, url, out):
        self.url = url.rstrip("/")
        self.out = out
        m = get(self.url + "/map")
        self.keys = m["keys"]
        self.model = m.get("model", "mki")

    def status(self):
        return get(self.url + "/status")

    def wait_booted(self, limit=300):
        t0 = time.time()
        while time.time() - t0 < limit:
            try:
                s = self.status()
                if s.get("booted") and s.get("phase") == "ready":
                    return s
            except OSError:
                pass
            time.sleep(1)
        raise SystemExit("panel_check: the server did not come ready")

    def screen(self, name):
        png = get(self.url + "/screen.png")
        (self.out / f"{name}.png").write_bytes(png)
        txt = get(self.url + "/screen.txt")
        txt = txt.decode() if isinstance(txt, bytes) else str(txt)
        (self.out / f"{name}.txt").write_text(txt)
        return png, txt

    def press(self, key, hold=0.08, settle=0.4):
        row, bit = self.keys[key]
        get(f"{self.url}/key?row={row:#x}&bit={bit}&down=1")
        time.sleep(hold)
        get(f"{self.url}/key?row={row:#x}&bit={bit}&down=0")
        time.sleep(settle)

    def chord(self, hold_key, key, settle=0.6):
        hr, hb = self.keys[hold_key]
        get(f"{self.url}/key?row={hr:#x}&bit={hb}&down=1")
        time.sleep(0.1)
        self.press(key, settle=0.1)
        get(f"{self.url}/key?row={hr:#x}&bit={hb}&down=0")
        time.sleep(settle)

    def peek(self, addr, n=1):
        r = get(f"{self.url}/peek?addr={addr:#x}&len={n}")
        return r


def check(ok, what, detail=""):
    print(f"  [{'ok' if ok else 'FAIL'}] {what}" + (f"  {detail}" if detail else ""))
    return ok


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--url", default="http://localhost:8563")
    ap.add_argument("--out", default="out/panel_check")
    ap.add_argument("--phase", choices=("all", "persist"), default="all")
    a = ap.parse_args()
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    p = Panel(a.url, out)
    s = p.wait_booted()
    fails = 0
    print(f"panel_check: {a.url} booted, backend {s.get('backend')}, card {s.get('card')} ({s.get('card_mode')}), "
          f"project {s.get('project')}")
    saved_file = out / "saved.json"

    if a.phase == "persist":
        saved = json.loads(saved_file.read_text())
        p.press("t1")
        p.press("pg_amp")
        v = p.peek(int(saved["addr"], 16))
        got = int(v["hex"][:2], 16) if isinstance(v, dict) and v.get("hex") else None
        fails += not check(got == saved["value"], "the saved value survived the restart",
                           f"{saved['name']} at {saved['addr']}: {got} (saved {saved['value']})")
        p.screen("persist")
        print(f"panel_check persist: {fails} failure(s)")
        return 1 if fails else 0

    png, boot = p.screen("boot")
    fails += not check(png[:8] == b"\x89PNG\r\n\x1a\n" and len(boot.splitlines()) == 64
                       and any("#" in ln for ln in boot.splitlines()),
                       "the screen decodes", f"{len(png)} B PNG, {sum(ln.count('#') for ln in boot.splitlines())} dark pixels")

    # a key: T1, then the AMP page
    p.press("t1")
    _, t1 = p.screen("t1")
    p.press("pg_amp", settle=0.8)
    _, amp = p.screen("amp")
    fails += not check(amp != t1, "a key press changes the screen (T1 -> AMP page)",
                       f"{sum(x != y for x, y in zip(amp, t1))} characters differ")

    # a knob: A on the AMP page, read through the firmware's memory
    r = get(f"{p.url}/knob/reset?row=0x30")
    addr = r.get("addr")
    if not check(bool(addr), "knob A on the AMP page resolves its parameter", json.dumps(r)[:200]):
        return 1
    before = r.get("after")
    get(f"{p.url}/knob?row=0x30&delta=5")
    time.sleep(0.6)
    v = p.peek(int(addr, 16))
    after = int(v["hex"][:2], 16) if isinstance(v, dict) and v.get("hex") else None
    _, knob = p.screen("knob")
    fails += not check(after is not None and after != before, "a knob turn changes the value",
                       f"{r.get('name')} at {addr}: {before} -> {after}; screen "
                       f"{'changed' if knob != amp else 'UNCHANGED'}")

    # the unit's SAVE PROJECT onto the persistent card
    st0 = get(p.url + "/card")
    # the PROJECT menu: FUNC+MIXER on an MKI, the PROJ key on an MKII (FUNC+MIXER
    # does not open it there, measured 25 Sep 2026)
    if p.model == "mkii":
        p.press("proj", settle=1.0)
    else:
        p.chord("func", "mixer", settle=1.0)
    p.screen("save_menu")
    p.press("right", settle=0.6)
    p.screen("save_list")
    # SAVE is one below the list's top (CHANGE, SAVE, ...)
    p.press("down", settle=0.4)
    p.screen("save_pick")
    p.press("yes", settle=1.0)
    p.screen("save_confirm")
    p.press("yes", settle=6.0)
    p.screen("save_done")
    st1 = get(p.url + "/card")

    def through(st):        # the child's `card flush` line: sectors written through to the file
        f = st.get("flush") or ""
        return int(f.split("through=")[1].split()[0]) if "through=" in f else 0
    fails += not check(through(st1) > through(st0), "SAVE PROJECT wrote sectors through to the card file",
                       f"{through(st0)} -> {through(st1)} sectors")
    saved_file.write_text(json.dumps({"addr": addr, "value": after, "name": r.get("name")}))
    print(f"panel_check: {fails} failure(s); screens in {out}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
