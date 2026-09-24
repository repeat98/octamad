# Machinedrum module

The core-1 layout, relocator, and driver match the plain replay baseline on
all twelve captured kits (`md_gate.sh`, `md_init_gate.py`).
`tools/build/md_payload.py` builds a verified payload-B load-record artifact
from the user's pinned MD OS 1.63 update, under ignored
`out/machinedrum/build/`.

`make bus REMIX=machinedrum` loads that artifact into core 1 at boot
(`tools/build/md_image.py`: a pre-boot payload of octabam's loader, uploaded
by the stock DSP boot). The FX2 chooser carries MACHINEDRUM (id 0x1e). On a
core-1 track (T1–T4) it runs `md_glue.asm`, which does three things:

- it applies the ColdFire record packets, including word-0 triggers;
  until a packet arrives, the track's trig fires a fixed TRX-BD record;
- it runs the relocated voice DSP through `md_driver.asm`;
- it mixes the sixteen slots at 1/4 each into the track, times p0 (VOL).

On T5–T8 the id is a passthrough (`md_stub.asm`). `make verify-md`
(OT_PROJECT with a sample on T1) checks the whole path under the port.
Slot 0 is bit-identical to the MD reference until the OT's next trig,
with a port built from the repo's dsp56300 pin.

`make verify-md-transport` (same OT_PROJECT/MD_EMU inputs) feeds the full
c01_16 host stream through `md_xport.s` and the DSP mailbox. All 33,503
captured voice blocks match the reference interpreter, including 20,544
non-silent blocks. The producer is currently a test stream loaded by the
port's `--load-file` option; live parameter production is WP-C4.
The reference uses `md_replay --interpreter`: a firmware-free arithmetic
probe reproduces a JIT loop defect in the capture emulator. Details and
reproduction commands: [WP-C1 report](../../docs/proposals/machinedrum_reports/WP-C1.md).

WP-C2 links all 44 distinct descriptor handlers as a second ColdFire DRAM
unit. `handler_build.py` reads the user's pinned MD OS at build time, copies
the original ISA_A code and lookup tables, and relocates 128 table operands
plus 20 reads of the MD's internal-SRAM word to a writable runtime symbol.
`md_handler_cases.py` captures the reference's 50 `map=` scenarios and
byte-compares 450 handler outputs against the linked unit. TRX-S2's live
map scenario stays on the empty handler; its descriptor is compared
separately on the nine captured parameter vectors. See the
[WP-C2 report](../../docs/proposals/machinedrum_reports/WP-C2.md).
The handler unit is present but no live OT control path calls it yet.

Not yet done:

- machine registration (the MD is an FX2 effect for now);
- the live record producer that calls the linked parameter handlers;
- the per-part mix (D1);
- the sequencer, persistence and MIDI;
- E12 samples;
- the full-kit cycle budget;
- any hardware run.

No flash image, sample, `.syx`, or extracted firmware blob belongs in Git.
See `docs/proposals/MACHINEDRUM_MACHINE.md` §12 and
`docs/proposals/machinedrum_reports/WP-B3-B4.md`.
