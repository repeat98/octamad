# OCTACLIDEAN6 — Mini Verb

Remix: `octaclidean-miniverb`. Build: **87**. Device version: **OCTACL6R4**.
The card/MIDI artifacts use the longer filename **OCTACLIDEAN6**.

This is the OCTACLIDEAN5 selection with the listening-approved Mini Verb v4
replacing Dark Reverb at FX2 id `0x16`. Octapitch2, preview volume, filename
BPM, Euclid, CPU Tape Echo and every other selected stock effect carry over.
The FX1 chooser is unchanged. DJ EQ, stock spring and stock plate remain
omitted, as in version 5; Tape Echo occupies stock spring's slot.

Before composing this image, rebuilding `octaclidean` with BUILD=82 matched
the saved OCTACLIDEAN5 MAIN OS section byte-for-byte:
`ec0f3e664b6e112d6f1eda222e8f90f7eb061877d7d10f8354bb3df086d65359`.
The original `octaclidean` remix and packaged version 5 are retained.

Mini Verb controls: **DECAY / DAMP / MIX / MOD / RATE**, with defaults
**104 / 70 / 40 / 80 / 2**. RATE has eight positions. The accepted DSP source
is unchanged by image composition. See [Mini Verb](../../modules/miniverb/README.md)
for its algorithm, eight-instance tests and instruction measurements.

Euclid now offers **LP / BP / HP / AMP / NOTCH** while preserving AMP's saved
value. Filter types show **FREQ / RES / DEPTH**; AMP shows
**LEVEL / -- / AMT**. AMP bypasses the filter coefficient and SVF work while
remaining bit-identical to the old AMP output. NOTCH combines the LP and HP
taps. The control engine also skips timing calculations unused by the active
mode.

## Build

```sh
make check REMIX=octaclidean-miniverb BUILD=87
make image REMIX=octaclidean-miniverb BUILD=87 VERSION=OCTACL6R4
```

The normal image target names its files `OCTATRACK_OCTACL6R4.bin` and
`OCTATRACK_OS1.40C_OCTACL6R4.syx`. The release also provides byte-identical
copies named `OCTATRACK_OCTACLIDEAN6.bin` and
`OCTATRACK_OS1.40C_OCTACLIDEAN6.syx` for consistency with the previous images.
Do not change the short device version to the longer filename label: the
firmware version field is limited to ten characters.

`out/octaclidean6/` retains the base identity proof, check/build/package
logs, verified MAIN OS and packaging checks. `out/OCTACLIDEAN6-NOTES.md`
records the final artifact hashes. Generated images contain the user's
Elektron firmware and remain local; they are not source-controlled.

## Existing projects

A saved Dark Reverb instance now selects Mini Verb, but its old parameter
bytes and locks still describe Dark Reverb. In particular, Dark's LP knob
occupies Mini Verb's eight-position RATE slot. Use a fresh test project, or
reset the former Dark Reverb slots and remove/remap their old parameter
locks before playback. Tape Echo's detail page is disabled again; its old
page-2 bytes are ignored. No projects are modified by building or checking
the image.

This revision restores the optimized one-page Tape Echo and retains the new
parameter-tweaking peak gate. The prior BUILD=83 artifacts are backed up under
`out/octaclidean6/revision-83-backup/`.

The image is locally verified and unflashed. Project-backed playback checks
require an OT_PROJECT, and physical CPU/cache/DMA headroom remains unmeasured.
The version-5 Tape Echo hardware acceptance limitations still apply; see
its retained local release notes. [Flashing instructions](../remixer/FLASHING.md)
describe the existing card and MIDI procedures.
