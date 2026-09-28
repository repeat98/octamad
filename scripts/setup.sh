#!/usr/bin/env bash
# Install the toolchain this repo builds against. Idempotent -- safe to re-run.
#
# The thing that actually matters here is step 4: the DSP56300 assembler
# (dsp_asm) and emulator harness (dsp_host). Those are what let effects be
# assembled and auditioned locally instead of by flashing hardware.
set -euo pipefail

# Pins, patches and the fetch/patch helpers: scripts/vendor.sh.
source "$(dirname "$0")/vendor.sh"

cd "$(dirname "$0")/.."

echo "== 1) System tools (via Homebrew) =="
need_brew=()
command -v binwalk  >/dev/null 2>&1 || need_brew+=(binwalk)
command -v radare2  >/dev/null 2>&1 || need_brew+=(radare2)
# The m68k/ColdFire cross-toolchain (bottled): DRAM runtimes and units are
# compiled from source at build time, and every pinned ColdFire cave with a
# `.s` source is re-assembled and compared against its bytes.
command -v m68k-elf-gcc >/dev/null 2>&1 || need_brew+=(m68k-elf-gcc)
if [ "${#need_brew[@]}" -gt 0 ]; then
  echo "   installing: ${need_brew[*]}"
  brew install "${need_brew[@]}"
else
  echo "   binwalk and radare2 already present."
fi

echo
echo "== 1b) mc68k (ColdFire core for the headless machine) =="
vendor_mc68k

echo
echo "== 2) elektron-firmware-tool (mischa85) =="
vendor_eft

echo "   building ..."
if [ -f vendor/elektron-firmware-tool/Makefile ]; then
  make -C vendor/elektron-firmware-tool || { echo "   [!] elektron-firmware-tool build FAILED -- make image needs it"; exit 1; }
  # The binary must carry the container dump, or make image has nothing to
  # wrap.
  grep -a -q EFT_EMIT_CONTAINER vendor/elektron-firmware-tool/elektron-firmware-tool \
    || { echo "   [!] elektron-firmware-tool was built WITHOUT the local patch (no EFT_EMIT_CONTAINER)."; \
         echo "       Fix: rm -rf vendor/elektron-firmware-tool; make setup"; exit 1; }
else
  src=$(find vendor/elektron-firmware-tool -maxdepth 2 -name '*.c' | tr '\n' ' ')
  if [ -n "$src" ]; then
    echo "   no Makefile; compiling sources: $src"
    cc -O2 -o vendor/elektron-firmware-tool/elektron-firmware-tool $src || \
      echo "   [!] direct compile failed — inspect the repo manually"
  else
    echo "   [!] no C sources or Makefile found — check the repo"
  fi
fi

echo
echo "== 3) Ghidra (optional, manual) =="
if [ ! -d "/Applications/ghidra" ] && ! command -v ghidra >/dev/null 2>&1; then
  cat <<'EOF'
   Ghidra not detected. For ColdFire disassembly:
     brew install --cask ghidra      # needs JDK 17+ (brew install temurin)
   Ghidra has no perfect native ColdFire processor; the m68k module covers
   most of the ISA. Alternative: radare2/rizin with -a m68k.
   Only needed for OS archaeology, not for building effects.
EOF
fi

echo
echo "== 4) dsp56300 -- assembler, disassembler and emulator for the audio DSP =="
# The effects and timestretch run on a DSP56300, not the ColdFire. Neither
# Ghidra nor radare2 targets it; we use the Access Virus emulator's toolchain.
# See docs/firmware/DSP.md and tools/build/dsp_modmap.py.
DIS=vendor/dsp56300/build/source/disassemble/dsp56kDisassemble
ASM=vendor/dsp56300/build/source/dsp_host/dsp_asm
HOST=vendor/dsp56300/build/source/dsp_host/dsp_host
# All three: a build that got the disassembler and failed on dsp_host must
# not read as "already built".
if [ ! -x "$DIS" ] || [ ! -x "$ASM" ] || [ ! -x "$HOST" ]; then
  if ! command -v cmake >/dev/null 2>&1; then
    echo "   [!] cmake not found — brew install cmake — then re-run make setup (make check needs dsp_asm and dsp_host)"
    exit 1
  else
    vendor_dsp56300
    cmake -S vendor/dsp56300 -B vendor/dsp56300/build -DCMAKE_BUILD_TYPE=Release -DCMAKE_OSX_ARCHITECTURES="$(uname -m)" \
      && cmake --build vendor/dsp56300/build \
           --target dsp56kDisassemble dsp_asm dsp_host -j8 \
      || { echo "   [!] dsp56300 build FAILED -- make check cannot run without dsp_asm and dsp_host."; \
           echo "       Fix what cmake printed above, then: rm -rf vendor/dsp56300/build; make setup"; exit 1; }
  fi
else
  echo "   already built: $DIS, $ASM, $HOST"
  # Stage the tree's dsp_host/dsp_asm sources AND rebuild them: until 27 Sep
  # 2026 this path only copied, so a binary built before a harness change
  # kept running with the old options (PR #356 was reviewed twice on a
  # dsp_host that ignored -paramfile, and verify_miniverb read MOD as inert
  # for the same reason). cmake is incremental: nothing to do costs seconds.
  stage_dsp_host
  cmake --build vendor/dsp56300/build --target dsp_asm dsp_host -j8 \
    || { echo "   [!] dsp_host/dsp_asm rebuild FAILED"; exit 1; }
fi

echo
echo "== setup complete. Next:  make os  then  make bus =="
