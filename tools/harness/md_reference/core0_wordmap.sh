#!/bin/sh
# WP-A1: build the ColdFire port with a per-word read/write map, in an
# ISOLATED tree (never in the shared vendor/ or out/emu), and run it on a
# project for N frames.
#
#   tools/harness/md_reference/core0_wordmap.sh <scratch dir> <project dir> <tag> [frames]
#
# Then: python3 tools/harness/md_reference/core0_ledger.py <scratch>/<tag>/wordmap.bin
#
# The copy: vendor/dsp56300/source/dsp56kEmu and tools/emu/ot_emu are
# copied into <scratch>, core0_wordmap.patch is applied there (a read hook in
# Memory::get, the --dsp-wordmap option, the test targets cut from the
# CMakeLists), and every other vendored directory is a symlink.
set -e
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
S=$1; PROJ=$2; TAG=$3; FRAMES=${4:-1000}
[ -n "$S" ] && [ -n "$PROJ" ] && [ -n "$TAG" ] || { echo "usage: $0 <scratch> <project> <tag> [frames]"; exit 2; }
if [ ! -x "$S/build/ot_emu" ]; then
	mkdir -p "$S/vendor/dsp56300/source"
	ln -sfn "$ROOT/vendor/mc68k" "$S/vendor/mc68k"
	for d in asmjit dsp56kBase dsp56kTestRunner disassemble vtuneSdk HxDplugin dsp56kDebugger dsp_host; do
		ln -sfn "$ROOT/vendor/dsp56300/source/$d" "$S/vendor/dsp56300/source/$d"
	done
	cp "$ROOT/vendor/dsp56300/source/CMakeLists.txt" "$ROOT/vendor/dsp56300/source/base.cmake" "$S/vendor/dsp56300/source/"
	rm -rf "$S/vendor/dsp56300/source/dsp56kEmu" "$S/tools/emu/ot_emu"
	cp -R "$ROOT/vendor/dsp56300/source/dsp56kEmu" "$S/vendor/dsp56300/source/"
	mkdir -p "$S/tools/emu" && cp -R "$ROOT/tools/emu/ot_emu" "$S/tools/emu/"
	(cd "$S" && patch -p1 < "$ROOT/tools/harness/md_reference/core0_wordmap.patch")
	cmake -S "$S/tools/emu/ot_emu" -B "$S/build" -DOT_VENDOR="$S/vendor" -DCMAKE_OSX_ARCHITECTURES="$(uname -m)" -DCMAKE_BUILD_TYPE=Release >/dev/null
	cmake --build "$S/build" --target ot_emu -j8 >/dev/null
fi
cat > "$S/run.py" <<'EOF'
import sys, pathlib, subprocess
ROOT = pathlib.Path(sys.argv[5])
sys.path.insert(0, str(ROOT / "tools/verify"))
import verify_set as vs
import ot_project as otp
S = pathlib.Path(sys.argv[1]); proj = pathlib.Path(sys.argv[2]); tag = sys.argv[3]; frames = sys.argv[4]
out = S / tag; out.mkdir(exist_ok=True)
pat_part, _ = otp.bank_info(proj, 1)
part = vs.part_of(proj, 1, pat_part[0] + 1)
card = out / "card.img"
vs.stage(proj, part, "OCTABAM", "RIG", out / "tree", 64, 1, card)
cmd = [str(S / "build/ot_emu"), "--image", str(ROOT / "out/raw/section_3_MAIN_OS.bin"), "--card", str(card),
       "--set", "OCTABAM", "--project", "RIG", "--sequencer", "--internal-clock", "--frames", frames,
       "--load-ms", "20000", "--dsp", "--main-level", "64", "--audio-in", "tones", "--poke-trig", "2",
       "--dsp-dirty", "--dsp-wordmap", str(out / "wordmap.bin")]
with open(out / "port.txt", "w") as f:
    f.write(" ".join(cmd) + "\n"); f.flush()
    r = subprocess.run(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT)
print(tag, "exit", r.returncode)
EOF
"$ROOT/.venv/bin/python" "$S/run.py" "$S" "$PROJ" "$TAG" "$FRAMES" "$ROOT"
