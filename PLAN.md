# The plan

octabam is a remixer for the Octatrack's OS: a mod is a module, a remix is
a selection of modules, and the build turns a remix and the user's own
1.40C into one image. `docs/remixer/PLACEMENT.md` is the architecture
record for where code goes; `docs/remixes/` describes each remix;
`CHANGELOG.md` records each flashed image.

## Where it stands (21 Sep 2026)

- **On hardware.** The rig (`bamsep26`) on Sam's MKII, image 43
  (`OCTABAM43`, 21 Sep 2026: the split block's frame offset from r0; a
  sample host with a trig every step clean; the rest of the changes since
  38 not yet heard). Images 44–47 and 50 were probes; 50 is on the unit
  and on a fresh project every configuration tested clean. Image 51
  built: the engines locked to T1 and T5 (`Remix.locked`) and out of
  the chooser, a new project born hosted (RIG HOSTS), the stock DELAY
  row out, Character's TXTR removed with WDTH in its slot; image
  49's bus needs no cross-core phase (eight buffers, read three back, a
  per-client block count; `docs/effects/XBUS.md`), bus latency 48
  samples. Sam's road test on a fresh project is next. `ok-ms` (Octakit + MIDI SCENES on the stock effects) on
  midisc's author's unit as OKMS2. octalab (nordseele) is a DRAM module of
  this remixer and has run on an MKI since 11 Sep 2026.
- **Built and gated, unflashed:** every other remix; main is image 43.
- **The platform** (`tools/remix/`): linked GNU-as units, detours, pokes
  and table growth wired by symbol and asserted against stock; recipe-built
  DRAM runtimes; the loader (derived from Octakit's, N payloads,
  hash-gated); the arena reserve (10 MiB off the bottom of the 85.5 MB
  sample pool); the ledger and compatibility matrix; the ColdFire port
  (`tools/emu/ot_emu`) that boots every remix and, with a project
  (`OT_PROJECT` or `~/.octabam_project`), plays it and reads every window
  back (`verify_set`, `verify_modedefaults`).

## The ground

Measured under the port unless marked (`docs/remixer/PLACEMENT.md`).

| where | how much | status |
|---|---|---|
| ROM: the OS image's free zero runs | ~8.4 KB, shared by every ROM cave and the chooser clones | measured |
| RAM | 128 MB at `0x40000000`; `0x48000000..` is the same memory uncached | boot code + hardware |
| the audio page arena `0x40a955e0..0x46025de0` | 85.56 MiB; Octakit the top 528 pages, octamax the bottom 64, the platform reserve the bottom 1,707 | measured |
| the top window `0x47fc7410..0x47fe0000` | 101,360 B; Octakit's boot-time stage; the engine task's sector bounce buffers land at `0x47fc8fe4..` at project load | port (PIO path); DMA-card path unexercised |
| the delay rings `0x47502c10..0x47fc7410` | 10.8 MB, cleared at boot through the alias; not free | static + port + hardware |
| `0x46025de0..0x4763d580` | stock's globals and object pool; not free | static |

## Release (stage D, then E's tail)

1. **The hardware pass** on image 38 (on the unit; the reverb on T5
   clean): the station banks under the new placement; Modulation's five
   modes + LOFI on the panel; the MIDI voice pass; the set. Two voicing
   items from Sam, 20 Sep 2026: Character's DRV is faint (TAPE THD at DRV
   64 is −36 dB on a tone, measured) and BusVerb's WET is hot (WET 127 =
   wet ×2 since 16 Sep) — a live round each.
2. Tag the next flashed build, `CHANGELOG.md`, `v0.1.0`.
3. The remixer TUI shows ColdFire modules as rows with the matrix's verdicts
   (`tools/remix/rig.py` `category()`, `app.py` prints only the first clash).

## Open, not scheduled

- The Kit write protocol: midisc's Part save/reload hooks against Octakit's
  LOAD/SAVE KIT menus are unmeasured (`modules/octakit/README.md`).
- Tell Em what the port saw at `0x47fc8fe4`.
- Upstream: an optional tidy PR to Em splitting her loader infrastructure.
- Measure `0x46000000..0x47502c10` with samples loaded and the recorder
  running before anyone places there.
- octamax (mxldyn): ported on branch `octamax-deferred` (`d952976`), parked
  pending a conversation with the author.
- Under the port the transport start re-applies the saved bank's FX ids for
  T1-T3, T7 and T8 only; `verify_set` stages the tested bank as bank A.
  Cause open.
- Each module's README, `## Open`.
- PR #257 (yvesrosius, STEM REC: record T1 to the card), draft.

## Gates and rules

- `make check REMIX=<name>` is the floor for every remix touched.
- A change to the build proves it changed nothing: `scripts/refhash.sh save`
  on a tree you trust, then `scripts/refhash.sh check`.
- The author's build is the oracle: `pinned`, `reference(addr)`,
  `Linked.reference` and a `Runtime` recipe's identities are four forms of
  one rule.
- Measured beats inferred, and says which it is (markers as in
  `docs/firmware/CHIP.md`; a retraction propagates to every document that
  repeated the number).
- Never an Elektron byte in the repo (`CONTRIBUTING.md` for what that
  covers); `.incbin` from the user's stock image at build time.

```sh
make modules                     # the index, the compatibility matrix, the remixes
make image REMIX=bamsep26 BUILD=29   # a card-flashable image, version-stamped
make check REMIX=bamsep26        # everything that can be checked without hardware
make remix                       # the TUI remixer
scripts/refhash.sh check         # after a change to the build itself
```
