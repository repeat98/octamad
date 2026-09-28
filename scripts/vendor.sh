#!/usr/bin/env bash
# The vendored sources this repo builds against: their pins, the local
# patches on them and the helpers that fetch and patch them. One place for
# both consumers -- scripts/setup.sh (the operator's Mac, which also builds)
# and CI (.github/workflows/ci.yml).
#
#   source scripts/vendor.sh          # pins + helpers
#   scripts/vendor.sh mc68k dsp56300  # fetch + patch those trees (no build)

# Copy our sources into the vendor tree. Always overwrite: tools/harness/dsp_host/ is
# the source of truth. Two diverging copies means an edit that never reaches
# the binary, which produces confidently wrong measurements.
stage_dsp_host() {
  mkdir -p vendor/dsp56300/source/dsp_host
  cp tools/harness/dsp_host/dsp_asm.cpp tools/harness/dsp_host/dsp_host.cpp \
     tools/harness/dsp_host/CMakeLists.txt vendor/dsp56300/source/dsp_host/ 2>/dev/null || true
  grep -q dsp_host vendor/dsp56300/source/CMakeLists.txt 2>/dev/null \
    || echo 'add_subdirectory(dsp_host)' >> vendor/dsp56300/source/CMakeLists.txt
}

# Musashi plus ColdFire mode, an HI08 host-port register file and the on-chip
# peripheral scaffolding -- the CPU half of tools/emu/ot_emu. Vendored, GPLv3, the
# same posture as vendor/dsp56300: tooling and patches are shared, built
# binaries never are. `docs/history/COLDFIRE_PORT.md`.
# Pinned: the port was measured against this commit
# (docs/history/COLDFIRE_PORT.md).
MC68K_PIN=4a6d0d17a1f2b30077ab726c27fe9bb770fa0456

# elektron-firmware-tool (mischa85): unpacks and repacks the OS container.
EFT_PIN=065d18f4195793e61891e387813488ee59f6d1ca

# Pinned: tools/patches/dsp56300.patch is against this commit and does not apply to
# upstream's later HEAD. Moving the pin means re-basing the patch and
# re-running make check's bit-identity gates.
#
# Re-pinned 22 Sep 2026 from c051afad (28 Jul) to 8ccdd843 (21 Sep, 144
# commits later). Upstream absorbed several of our own fixes in that
# span -- MPYRI and MACRI, the DCOL 12-bit width, "serve a DMA request
# raised before the channel was enabled", 2D/no-update DMA address
# modes, the assembler's TFR/CMP/CMPM/Tcc JJJ=000 encoding, JIT MPYI
# sign-extension, CCR overflow flags -- so this patch dropped those
# hunks; see the PR that did the re-pin for what was checked absorbed
# vs. still needed. NOT absorbed, still ours: the AGU pre-decrement fix
# (upstream PR #13 from us, open since 8 Sep), the one-word displaced
# move, the DMA dual-counter reload at end of block, the host-stepped
# mode, the shared window, the unmapped-register hooks.
DSP56300_PIN=8ccdd843adda9c18fc232a2ca50d6caccbf3cb1e

pin_checkout() {  # dir url sha
  [ -d "$1" ] || git clone --no-checkout "$2" "$1"
  if [ "$(git -C "$1" rev-parse HEAD 2>/dev/null)" != "$3" ]; then
    git -C "$1" fetch -q origin "$3"
    git -C "$1" checkout -q "$3"
  fi
  echo "   $1 at $(git -C "$1" rev-parse --short HEAD) (pinned)"
}
# apply_patch dir patch: apply, or accept already-applied, or fail loudly
# (a rejected patch reads as "already applied" otherwise).
apply_patch() {
  if git -C "$1" apply --check "$2" 2>/dev/null; then
    git -C "$1" apply "$2" && echo "   local patch applied: $(basename "$2")"
  elif git -C "$1" apply --check --reverse "$2" 2>/dev/null; then
    echo "   local patch already applied: $(basename "$2")"
  else
    echo "   [!] $(basename "$2") does NOT apply to $1 at $(git -C "$1" rev-parse --short HEAD)"
    echo "       and is not already applied either. Fix: rm -rf $1; make setup"
    echo "       (vendor/dsp56300 with an older version of the patch: make dsp-repatch)"
    exit 1
  fi
}

vendor_mc68k() {
  pin_checkout vendor/mc68k https://github.com/joelanders/mc68k-md-mm "$MC68K_PIN"
}

# Two local changes are needed to reproduce this build:
#   - set_version() writes the full 10-char ELEK version field from 0x08;
#     upstream only writes from 0x0D, where 5 fit.
#   - EFT_EMIT_CONTAINER dumps the rebuilt container, which tools/build/make_bin.py
#     wraps to produce the CF card .bin.
vendor_eft() {
  pin_checkout vendor/elektron-firmware-tool https://github.com/mischa85/elektron-firmware-tool "$EFT_PIN"
  apply_patch vendor/elektron-firmware-tool "$(pwd)/tools/patches/elektron-firmware-tool.patch"
}

# The patch carries: the one-word displaced move; the AGU pre-decrement
# fix; the DMA dual-counter reload at end of block; a same-value DCR
# rewrite while a self-clearing window is open renews instead of being
# dropped (measured 1199/1200 frames on DCR2, the ESAI feed -- bit-
# identical with or without it on that project, ported defensively);
# the shared window, two-way for dsp_host (X with X, Y with Y) and
# three-way for the ColdFire port's DSP pair (P, X and Y one memory,
# as the chip has it); and the host-stepped mode the port drives the
# cores in (DO loops stepped, interrupts interpreted, peripherals
# serviced under a masked interrupt, an idle step) plus hooks for
# Y-side registers it does not map. From Tim Hastie's octa-panel
# (be68244, the port's --dsp-rt mode, O17-O22), rebased onto this pin
# 25 Sep 2026: the JIT cores on worker threads -- a transmit FIFO and
# lock-free rings on the HDI08, burst DMA to and from the host port,
# the writing instruction's PC on a JIT peripheral write, volatile P
# addresses declared up front, the masked-interrupt peripheral service
# for a threaded core, a DMA request-source bounds check -- and the
# JIT's M-register bit op (`bset #$f,m4` kept stale modulo words). His
# hunks upstream now carries (MPYI sign, the dynamic fast-interrupt
# return PC, a request pending at arm) are not in it. A tree with an
# older version of this patch applied: `make dsp-repatch`.
vendor_dsp56300() {
  pin_checkout vendor/dsp56300 https://github.com/dsp56300/dsp56300.git "$DSP56300_PIN"
  git -C vendor/dsp56300 submodule update --init --depth 1 --recursive
  apply_patch vendor/dsp56300 "$(pwd)/tools/patches/dsp56300.patch"
  stage_dsp_host
}

if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  set -euo pipefail
  cd "$(dirname "$0")/.."
  [ "$#" -gt 0 ] || { echo "usage: scripts/vendor.sh mc68k|eft|dsp56300 ..."; exit 2; }
  for t in "$@"; do "vendor_$t"; done
fi
