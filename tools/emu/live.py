#!/usr/bin/env python3
"""The remix on the port with its screen and panel: play with it.

    make emu-live REMIX=bottleservice                  # OT_PROJECT or ~/.octabam_project
    python3 tools/emu/live.py bottleservice --project ~/octa/projects/RIG [--bank 2]

Builds the remix (unless --image), stages the project onto a scratch card
the way tools/verify/verify_set.py does, boots `ot_emu --live <fifo> --lcd
<file>` and opens tools/emu/lcd_view.py's window on the same FIFO: the
screen (page plus popups, composited) with the keys and encoders under it.
Closing the window quits the port. The boot's date prompt is up first:
[NO] (Escape) clears it. The port boots as an MKII (`--mkii`,
docs/firmware/PANEL.md), so the window's PROJ/PART/AED/ARR/REC3 keys work;
--mki boots it as an MKI, where those keys do nothing.
"""
import argparse, os, pathlib, re, shutil, signal, subprocess, sys, tempfile, time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
import ot_project as otp  # noqa: E402
import verify_set as vs  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
EMU = ROOT / "out/emu/ot_emu"
PY = ROOT / ".venv/bin/python3"
OUT = ROOT / "out/live"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("remix", nargs="?", default=os.environ.get("REMIX"))
    ap.add_argument("--project", default=os.environ.get("OT_PROJECT", ""))
    ap.add_argument("--bank", type=int, default=int(os.environ.get("OT_BANK", "0") or 0))
    ap.add_argument("--image", default="", help="a built image instead of building the remix")
    ap.add_argument("--set-name", default="OCTABAM")
    ap.add_argument("--name", default="RIG")
    ap.add_argument("--scale", type=int, default=4)
    ap.add_argument("--shot", type=float, default=0,
                    help="no window: wait this many seconds after the boot, write out/live/screen.png, quit")
    ap.add_argument("--mki", action="store_true", help="boot the port as an MKI (default: --mkii)")
    a = ap.parse_args()

    if not a.project:
        p = pathlib.Path.home() / ".octabam_project"
        a.project = p.read_text().strip() if p.is_file() else ""
    if not a.project:
        sys.exit("emu-live: no project (OT_PROJECT=<dir>, --project, or ~/.octabam_project)")
    if not EMU.exists():
        sys.exit("emu-live: the port is not built -- make emu-cf")
    pdir = pathlib.Path(a.project).expanduser()

    OUT.mkdir(parents=True, exist_ok=True)
    image = OUT / "image.bin"
    if a.image:
        shutil.copy2(a.image, image)
    else:
        env = dict(os.environ, REMIX=a.remix, XBUS="1", SPEC="1"); env.setdefault("BUILD", "0")
        r = subprocess.run([sys.executable, str(ROOT / "tools/build/build_bus.py")], env=env,
                           capture_output=True, text=True, cwd=ROOT)
        if r.returncode:
            sys.exit(f"emu-live: building {a.remix} failed:\n{(r.stdout + r.stderr)[-1500:]}")
        shutil.copy2(ROOT / "out/mainos_bus.bin", image)

    raw = (pdir / "project.work").read_bytes()
    m = re.search(rb"\r\nBANK=(\d+)\r\n", raw)
    bank = a.bank or (int(m.group(1)) + 1 if m else 1)
    pat_part, _ = otp.bank_info(pdir, bank)
    part = vs.part_of(pdir, bank, pat_part[0] + 1)
    card = OUT / "card.img"
    audio, mb = vs.stage(pdir, part, a.set_name, a.name, OUT / "tree", 64, bank, card)
    print(f"emu-live: {a.remix} on {pdir.name} bank {bank}, card {mb} MB, {len(audio)} sample file(s)")

    work = pathlib.Path(tempfile.mkdtemp(prefix="emulive."))
    fifo, lcd, log = work / "panel", OUT / "lcd.bin", OUT / "port.txt"
    os.mkfifo(fifo)
    cmd = [str(EMU), "--image", str(image), "--card", str(card), "--set", a.set_name,
           "--project", a.name, "--load-ms", "90000", "--live", str(fifo), "--lcd", str(lcd)]
    if not a.mki:
        cmd.append("--mkii")
    print("emu-live: booting (the screen appears once the project has loaded; ~30 s)")
    with open(log, "w") as lf:
        port = subprocess.Popen(cmd, cwd=ROOT, stdout=lf, stderr=subprocess.STDOUT)
        keep = os.open(fifo, os.O_RDWR)              # holds the FIFO open for the port
        while port.poll() is None and "live       : reading panel" not in log.read_text():
            time.sleep(0.2)
        if port.poll() is not None:
            sys.exit(f"emu-live: the port stopped during boot -- {log}")
        viewer = [str(PY if PY.exists() else sys.executable), str(ROOT / "tools/emu/lcd_view.py"), str(lcd)]
        rc = 0
        try:
            if a.shot:
                time.sleep(a.shot)
                rc = subprocess.run(viewer + ["--png", str(OUT / "screen.png"), "--scale", str(a.scale)],
                                    cwd=ROOT).returncode
            else:
                rc = subprocess.run(viewer + ["--panel", str(fifo), "--scale", str(a.scale)], cwd=ROOT).returncode
        except KeyboardInterrupt:          # Ctrl-C in the terminal: stop both, quietly
            print("\nemu-live: stopped")
        finally:
            try:
                os.write(keep, b"quit\n")
                port.wait(timeout=20)
            except (subprocess.TimeoutExpired, KeyboardInterrupt, OSError):
                port.send_signal(signal.SIGTERM)
            os.close(keep)
    print(f"emu-live: port log {log}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
