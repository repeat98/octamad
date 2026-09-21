# Findings — general-elektron-discussion, part 2 (lines 4300–8800, ~7–13 Sep 2026)

Most of this range is off-topic (gear chat, studio photos, Elektronauts moderation
drama, LLM/model preference chatter, "joined the server" noise). The items below are
the substantive technical exceptions.

## Spare/extra RAM discovery (Em / midi-scenes) — DRAM platform relevant

- **[bamshanks, 9 Sep 2026, secondhand from "Em" (bukkakeborealis?)]** Claimed
  discovery of unused RAM on the Octatrack beyond the ~8.4 KB budget modules had been
  fighting over: "looks like (at this stage) about 8.8MB ... vs the 8.4kb we were all
  fighting over." **Numbers were retracted within the hour**: "ok numbers were very
  wrong ... it still works but an order of magnitude less" — so treat the ~8.8 MB
  figure as debunked; only "still huge (relatively)" and "there's meaningfully more
  than 8.4 KB" survive as claims, unconfirmed magnitude. bamshanks noted the
  candidate region overlaps the delay rings area (bryant12345 suggested it's "the
  delay rings ... 8 tracks of 4 second stereo files") but bamshanks said "it's where
  they are, but it looks like there is more."
  - **May relate to existing project trap docs — cross-check**: this looks like the
    same territory as the CLAUDE.md DRAM-platform work (the write-watch/uncached-alias
    trap, the "8.8 MB free at 0x47700000" retracted claim already documented under
    "A WRITE-WATCH ON CACHED ADDRESSES IS BLIND TO A CLEAR THROUGH THE UNCACHED
    ALIAS"). The 8.8 MB number in that trap doc and the 8.8 MB number here are
    suspiciously identical — this Discord exchange may be the actual origin of that
    retracted number, or an independent repeat of the same mistake. Worth checking
    dates/authorship against `machine.h`/`RTOS_FORK` history.
  - bamshanks, same thread: "the os wipes [the region] and then she puts it back" —
    i.e. the OS clears this RAM region at some point (boot?) and the midi-scenes
    loader restores/repopulates it afterward. Firsthand, but not detailed (no address
    given here).
  - bamshanks: confirmed with Em that midi-scenes "stole a bit from the flex pool" —
    i.e. part of the new headroom for midi-scenes actually comes out of the FLEX
    sample-pool RAM allocation, not pure "free" RAM. bryant12345 noted this could be
    "problematic" for users who load large samples into FLEX (sound-on-sound users).
  - bamshanks: "Midi scenes uses the whole space budget using the gaps we were
    fitting stuff into. So the way most of us were doing it had hit the ceiling, but
    Em loads into spare ram, which gives us roughly 1000x the budget" — describes an
    architecturally different loading strategy (load into spare/reserved RAM) versus
    the older approach of patching into small gaps in existing firmware regions. This
    matches octamad's own "Runtime recipe... loads into DRAM" framing, worth
    cross-referencing against `docs/remixer/PLACEMENT.md`.
  - bamshanks: "the effects still have to be on dsp ... it kicks them onto the dsp at
    boot and then they operate separately" and "the word limits are still in place" —
    confirms that even with more general-purpose RAM available, DSP-side effect code
    is still bound by the existing DSP word/instruction budget; only non-DSP
    (ColdFire-side, e.g. kit/scene data) content benefits from the newfound RAM.

## CF card FAT / RAM reservation (emuyia) — firsthand-tested exploration, not shipped

- **[emuyia, 10 Sep 2026, firsthand/tested-in-progress]** Investigating a path to
  store kit data without using the FLEX pool, by repurposing part of the RAM reserved
  for the FAT (file allocation table):
  - "the FAT takes up 8 MB regardless of CF card size" — i.e. the Octatrack reserves
    a fixed 8 MB RAM buffer for FAT regardless of actual card size.
  - "64 GB partitions at 32 KiB cluster size take up almost all the 8 MB, so 64 GB
    cards can't work" (this explains a known constraint on max CF card size under
    stock FAT layout).
  - Speculative path: supporting 64 KiB cluster sizes would allow 64 GB cards, but
    is "very invasive" and would also require patching USB storage and on-device
    card formatting.
  - emuyia says they "did create a test build to see if the kit data was happy, and
    it seemed so in initial testing" — a firsthand but preliminary/unconfirmed
    result.
  - Separately, there's "an 8 MB buffer separate from FAT that remembers cluster
    chains of loaded static samples" — a second, distinct 8 MB region from the FAT
    buffer.
  - bryant12345 proposed partitioning a 64 GB card into two 32 GB regions to free up
    4 MB on each; emuyia responded this is a "creative idea" and floated (still
    speculative) using a custom reader tracking per-partition cluster chains to get
    playback access to both partitions without needing the full FAT — but browsing/
    loading/saving across partitions "would still need figuring out," and mounting
    two FAT volumes simultaneously would mean "untangling the filesystem's
    assumptions about having one mounted volume." FAT32 has no hard/soft link
    support (emuyia confirmed), ruling out that shortcut.
  - Conclusion at end of exchange: emuyia intends to look into 64 KiB cluster size
    support as the more promising path forward. No result confirmed by end of this
    chunk.
  - **May relate to existing project trap docs — cross-check**: this is CF-card/FAT
    territory, distinct from the DRAM/RAM platform traps already documented; if
    octamad ever touches storage/FAT handling this is relevant prior art (unshipped,
    exploratory).

## Build/tooling breakage report — directly matches an existing project trap category

- **[rbl0k_28323 → bamshanks, 10 Sep 2026, firsthand build failure on commit
  9a49f21]**: "Fresh build of 9a49f21: `make setup` currently breaks because
  dsp56300 is cloned unpinned at current HEAD (`e3b4860`), where
  `tools/patches/dsp56300.patch` no longer applies. Setup then stages `dsp_host`,
  which fails on missing `Memory::setSharedWindow`, but still reports 'setup
  complete'." rbl0k_28323's own diagnosis: "Looks like dsp56300 should be pinned and
  setup should fail hard on patch/build errors." devilfish707 confirmed hitting "same
  error." This is an external, independent report of exactly the failure class
  octamad's own CLAUDE.md calls out under "A port is a proof" / pinned-build
  discipline, and under the "THE BINARY IS NOT THE SOURCE" / vendored `assembler.cpp`
  patch trap — **may relate to existing project trap docs — cross-check** against
  whether `dsp56300` is now properly pinned (by commit hash) in `scripts/setup.sh`
  and whether it now fails hard rather than silently reporting success when the
  patch doesn't apply. If this repo is the octamad fork of sambanks/octabam, verify
  this specific failure mode (unpinned dsp56300 clone + silent setup "complete") is
  actually fixed here.

## Vendored dsp56300 tool wrapping — architecture confirmation (bamshanks, 13 Sep 2026)

- bamshanks, describing octabam's toolchain (firsthand, from the maintainer):
  "the repo bills itself as an emulator but it has an assembler and disassembler in
  the tree too. We wrapped its assembler as our build's assembler, use its
  disassembler on the stock payloads, and run the emulator under our test harness."
  Exact links given (pinned to commit `c051afad31612c2d2c7a81a7ab23e1c5ac9e61af` of
  `dsp56300/dsp56300`):
  - Assembler: `source/dsp56kEmu/assembler.cpp`
  - Disassembler core: `source/dsp56kEmu/disasm.cpp`
  - Disassembler CLI: `source/disassemble/disassemble.cpp`
  - octabam's assembler wrapper: `tools/harness/dsp_host/dsp_asm.cpp` — "It includes
    upstream's assembler.h and feeds it one instruction at a time, adding labels,
    org and the file handling upstream's class lacks."
  - Build call site: `tools/build/build_bus.py`
  - Stock-payload disassembly call site: `tools/build/dsp_disasm_all.py`
  This directly corroborates (and gives exact upstream file names/commit) the
  `assembler.cpp`-behind-`dsp56300.patch` trap already in CLAUDE.md
  ("`tools/patches/dsp56300.patch` adds the one-word form... the encoder lives in
  the vendored `assembler.cpp`").
- A second, unrelated DSP56300 tool was surfaced by robottosan_ same day:
  `https://github.com/mborgerson/dsp56300` (Rust-based assembler/disassembler/JIT
  emulator, distinct project from `dsp56300/dsp56300`). bamshanks checked
  licensing — the one octabam uses (`dsp56300/dsp56300`) is **not** GPL per its
  `LICENSE.md` (he expected GPL but apparently it isn't); no adoption decision was
  made, purely a "worth a look" mention. Not acted on in this range.
- robottosan_ (speculative, unconfirmed): believes Elektron itself may have used
  Motorola/NXP's original `asm56300` assembler (from what's now branded "NXP Symphony
  Studio" dev tools) to build the Machinedrum/Monomachine, describing it as "old,
  closed source and not maintained anymore." No evidence given, purely inference.

## Firmware security / packing — mischa85 (elektron-firmware-tool author), firsthand

- **[marcel_hackerman = mischa85, 8 Sep 2026, firsthand — author of
  elektron-firmware-tool]**:
  - "There are so many layers of handrolled algorithms involved in the packing and
    compression" in Elektron firmware images generally.
  - "They kept adding more layers all the way to Digitone II/Digitakt II" — i.e.
    firmware packing/obfuscation complexity increased with each generation.
  - "DT2/DN2 also have a HMAC but that one is readable in the fw itself" — the
    Digitakt 2 / Digitone 2 firmware contains an HMAC, but the verification/key
    material is present in the firmware itself (i.e. not a hardware secret) —
    contrasted explicitly with Tonverk.
  - Tonverk: "there's crypto involved, and the private key probably sits in the
    SoC" — inferred/uncertain ("probably"), not confirmed. Also: "That also makes
    it legally a bit different I think" (DMCA-type concerns raised later by
    j_blanco: circumventing a technical protection measure is a different legal
    category than reverse-engineering an unencrypted image).
  - "It all starts with reading what the CPU executes, which has to be readable" —
    general methodology point: no matter how packed/obfuscated, the raw
    instruction stream fed to the CPU has to be recoverable, which is the practical
    starting point for any of this reverse-engineering work.
  - robottosan_, firsthand: did similar packer reverse-engineering on the
    Machinedrum ("just had to reverse engineer one packer though" — described as
    comparatively easy, "that one was easy lol" per mischa85).

## Octamax module description (bryant12345 quoting maxolydian, 11 Sep 2026)

- From octamax's own description, quoted verbatim by bryant12345: "Arp key scales —
  the MIDI arpeggiator's key-scale (ARP SETUP, F knob) gains 10 qualities beyond the
  stock major/minor: the five Greek modes, blues, phrygian-dominant, melodic-minor,
  octatonic and hirajoshi — 12 qualities × 12 roots. OFF/maj/min stay
  byte-identical to stock, so the extra scales only appear if you scroll past them."
  This is a **firsthand claim from the module author** about maintaining
  byte-identical stock behavior for existing values while extending a param's range
  — same discipline pattern as octamad's own bit-identity gates. Not from this
  repo's own modules, but a cross-project data point on how another author does it.

## Miscellaneous firsthand mod/reverse-engineering claims

- **[kjnilsson, 9 Sep 2026, firsthand]**: added a MIDI arp mode reusing the existing
  arp-mode option slot: "WALK" mode — "instead of enabling the arp [it] walks each
  note in the chord in order one step per pattern iteration." Later (13 Sep) added a
  module that reads a literal "REM: FILL" text string written on an arranger row and
  auto-enables fill mode ("FILL OFF" to disable) — described as working "quite nicely
  with manual fill mode changes" and backward-compatible ("wont break"). Considered
  and rejected an alternative implementation (a new flag on the mute page) as
  "gnarly."
- **[gotem4life, 9 Sep 2026, firsthand, shared as informal notes attachment
  `OCTATRACK_INTERNALS.md` — not read here, only the chat summary]**: reports (1) an
  FX2 "synth" playing polyphonically with different chord sets on its own chromatic
  keyboard; (2) internal MIDI routing where setting a MIDI track's channel to 1–8
  triggers audio track 1–8 (only tested for single-note triggering, not confirmed
  polyphonic); (3) a "generative sequencer" that auto-places trigs, P-locks chord
  values, and changes them on loop (partial success, "kind of worked"); (4) getting
  two sequencer triggers running on one channel at different rates to produce a
  polyrhythm within a single track. All described as personal experiments, mixed
  confirmation level ("maybe this will help someone if not already discovered").
- **[bamshanks, 9 Sep 2026, firsthand, in-progress/uncertain]**: "I did a reverse
  [delay] in the DSP but I'm not sure I'll keep it" — an experimental DSP-side
  reverse-delay effect, status undecided.
- **[bamshanks, 9 Sep 2026, firsthand]**: "I had to do a bit of MIDI stuff on the
  coldfire side to allow effects page 2 params to be MIDI accessible" — i.e. FX
  page-2 parameters required ColdFire-side MIDI plumbing work to be reachable over
  MIDI CC, implying they are not MIDI-addressable by default/stock. Relevant to
  `docs/firmware/PARAM_PAGES.md`.
- **[robottosan_, 10 Sep 2026, methodology, firsthand]**: "I used Ghidra-MCP couple
  months ago, that gave the LLM some sort of methodology and structure to follow
  instead of just trying things at random. Now I'm trying to build a debugger/
  emulator harness to give the LLMs something to test against." Also: "I also
  manually opened up a lot of the code in Ghidra though and added function names
  based on the functionality." Workflow-level, not a specific firmware finding, but
  documents a reverse-engineering methodology in active use by a community member
  (Ghidra + Ghidra-MCP + hand-named functions, moving toward a custom debugger/
  emulator harness for LLM-assisted RE — conceptually parallel to octamad's own
  `dsp_host`/`ot_emu` harnesses).
- Referenced-but-unread documents shared as Discord attachments in this range (not
  fetchable from the transcript, but worth knowing they exist as provenance for
  memory addresses/architecture elsewhere in the community): `bryant12345`'s
  `octatrack-delay-architecture.md` (10 Sep, confirmed by bamshanks as already
  matching his own notes), `kjnilsson`'s `SEQUENCER_RE.md` and its
  `SEQUENCER_RE_reply.md` (9 Sep), `bamshanks`'s `octabam-notes-for-karl-johan.md`
  (9 Sep, shared with lyingdalai's Elektron colleague context), and
  `gotem4life`'s `OCTATRACK_INTERNALS.md` (9 Sep).

## Not technical / skipped

The large remainder of this range — Elektronauts thread takedowns and moderator
drama (avantronica/lyingdalai), general legal/EU-reverse-engineering-rights
discussion, gear-collection/GAS chat, studio photos, LLM model preference
comparisons (Fable 5.1 vs GPT-5.6-Sol vs Opus, etc.), and Discord-bot/summarization
tooling discussion — contains no firmware/DSP implementation substance and was
skipped per instructions.
