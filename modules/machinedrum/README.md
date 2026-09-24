# Machinedrum module

The core-1 layout, relocator, and driver match the plain replay baseline on
all twelve captured kits (`md_gate.sh`, `md_init_gate.py`).
`tools/build/md_payload.py` builds a verified payload-B load-record artifact
from the user's pinned MD OS 1.63 update, under ignored
`out/machinedrum/build/`.
The payload also needs the generated `out/machinedrum/plan.json` and capture
relocation plans. Rebuild the access traces with `md_reads.sh`, run
`md_flip.py <access files> --init <init access> --plan out/machinedrum/plan.json`,
then run `md_gate.sh` with the `MD_REPLAY_FETCH=2` profiles in `out/md_fetch/`
to regenerate the twelve relocation plans before
`md_payload.py`. The relocator fills private P with whole unobserved code
units after the measured hot units; this keeps the shared-window code inside
its allocation when profiles omit reachable boot or rare-engine code.

`make bus REMIX=machinedrum` loads that artifact into core 1 at boot
(`tools/build/md_image.py`: a pre-boot payload of octabam's loader, uploaded
by the stock DSP boot). The SRC SETUP machine chooser carries MACHINEDRUM as
serialized type 6; type 5 remains reserved for POLY. The remix hides internal
DSP id `0x1e` from FX2. The frame builder selects it only for an MD machine
on T1–T4, without changing the Part's FX2 setting. Both chooser commit paths
refuse a second MD within the active Part or assignment on T5–T8. On core 1
it runs `md_glue.asm`, which does three things:

- it applies the ColdFire record packets, including word-0 triggers;
  until a voice-record packet arrives, the track's trig fires a fixed TRX-BD record;
- it runs the relocated voice DSP through `md_driver.asm`;
- it mixes the sixteen slots into stereo with separate per-part left/right
  gain tables (both default to 1/4) at the fixed proof output gain (100/128).
  Mailbox destinations `0xc00–0xc1f` update those tables through the
  ColdFire host-transfer chain; `verify_md_image.py --gain-probe` checks a
  right-channel mute under Octemu. `md_gain_set` stages a left/right Q23 pair
  for one internal part; the transport sends one pending pair per frame.
  `verify_md_image.py --gain-queue-probe` checks that queue under Octemu.

On T5–T8 the id is a passthrough (`md_stub.asm`). `make verify-md`
(OT_PROJECT with a sample on T1) checks the whole path under the port.
Slot 0 is bit-identical to the MD reference until the OT's next trig,
with a port built from the repo's dsp56300 pin.

`make verify-md-transport` (same OT_PROJECT/MD_EMU inputs) feeds the full
c01_16 host stream through `md_xport.s` and the DSP mailbox. All 33,503
captured voice blocks match the reference interpreter, including 20,544
non-silent blocks. That gate's producer is a test stream loaded by the port's
`--load-file` option; the live producer is the control engine below.
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

## The control engine (WP-C4, WP-D3)

`md_ctl.c` is C compiled to the checked-in `md_ctl.s` by `generate_ctl.py`
(`--check` reports drift). It holds the kit (16 parts: engine, VOL, PAN,
mute, SYN 1–8) and one MD pattern per OT pattern (16 lanes of 64 steps and
64 locks each). It plays the lanes on the parent track's step grid, and
runs the MD's own handlers to produce the records. Once a frame,
`md_xport.s` asks it for a chunk:

- the frame builder's MD hook tells it which of T1–T4 is the MACHINEDRUM
  track;
- on the first frame with an MD track it loads the default kit: eight TRX
  voices and eight empty parts;
- the lanes follow the parent track's length, scale and swing, on the clock
  the stock PLAY paths anchor (the same two sites as Euclid, so the two
  modules never share a remix);
- a step's trigs are sent one frame ahead. Its locks (SYN 1–8, VOL, PAN)
  hold for that trig;
- VOL and PAN become the glue's gain pair (the MD's VOL² law, constant-power
  PAN);
- each frame one idle part's words and gains are sent again.

The MD's send path this reproduces is in `MACHINEDRUM_MACHINE.md` section
12, "How the MD sends a record". Gates, under the port:

- `make verify-md-kit [CASES=all]`: the captured cases of every engine
  (450 with `all`) reach core 1 as the MD's own trig records, and the gains
  are right;
- `make verify-md-seq`: T1 as MACHINEDRUM plays a poked pattern on the
  grid, with locks, and T1's output carries the mix.

The registration proof was walked in headless Octemu with FX2 at NONE:
MACHINEDRUM appeared in SRC SETUP and on the main track view, TRX-BD played
on T1, and T2/T5 assignment attempts left STATIC selected. The normal FX2
list no longer shows MACHINEDRUM. This still runs at the FX2 DSP dispatch
stage internally. T1–T4's stock FX code is displaced by the MD payload, so
the visible FX choices on those tracks are not functional yet.

The user excluded the eight original MD TRACK EFFECTS controls (amplitude
modulation, EQ, filter and sample-rate reduction) on 24 September 2026.
The current payload already loads only the MD voice DSP (`section_1_DSP`),
not its mixer DSP (`section_2_DSP`), so this decision does not reduce the
current image's DSP footprint. The planned interface now has SYN 1/2 and
per-part VOL/PAN; it has no MD FX pages. The original MD distortion and
master effects are also absent. OT FX on T1–T4 still need a separate code
restoration before they can process the MD mix.

Not yet done:

- the editor: part selection, the grid view of a part's lane, the SYN
  pages (WP-D4, WP-D5, WP-D6); lanes are poked in the gates only;
- persistence of kits and patterns (WP-E1), MIDI (WP-E2);
- E12 samples (E12 parts play as GND---);
- the full-kit cycle budget on the unit;
- any hardware run.

No flash image, sample, `.syx`, or extracted firmware blob belongs in Git.
See `docs/proposals/MACHINEDRUM_MACHINE.md` §12 and
`docs/proposals/machinedrum_reports/WP-B3-B4.md`.
