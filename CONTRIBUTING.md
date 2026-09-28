# Contributing

The contract a module signs, the rule every port lives by, and the
etiquette for building from somebody else's repository.

## The one rule

**Never an Elektron byte.** Not an OS image, not a `.syx`, not a slice of
either, not in a commit and not attached to an issue or PR. Describe it,
hash it, or name the commit that built it. Anything a module needs from
the stock firmware is taken from the user's copy at build time (Octakit
`.incbin`s 411 stock routines that way). `.gitignore` refuses `*.bin`,
`*.syx`, `downloads/` and `out/`.

What the rule does not cover (decided 16 Sep 2026): the few displaced
instructions at a cave's hook site. A `CfPatch.hook_stock` is the six to
ten bytes the installer overwrites with its `jsr` and the cave replays; the
build refuses an image that does not hold them, which is the check that
keeps a cave off the wrong OS. Those opcodes (four sites, 30 bytes in all,
across `tempo-sync`, `recorder-spacing`, `flex-seekbind*`) are an
instruction, not a firmware, and every ColdFire module carries its own
the same way. Keep a hook to whole instructions and the minimum span; data
tables, routines and anything longer than the displaced instructions come
from the user's image at build time.

## Your first pull request

1. Fork `sambanks/octabam` on GitHub and clone your fork with its
   submodules:

   ```bash
   git clone --recurse-submodules https://github.com/<you>/octabam
   cd octabam
   git remote add upstream https://github.com/sambanks/octabam
   ```

2. `make setup` builds the toolchain: dsp56300 at its pin with our patch,
   the ColdFire core, `elektron-firmware-tool` (`scripts/vendor.sh` holds
   the pins). macOS with Homebrew; `docs/WSL.md` for Linux.
3. `make os && make recon` turns **your own** copy of OS 1.40C into
   `out/raw/section_3_MAIN_OS.bin`. Every build and most gates read it;
   it never leaves your machine.
4. Branch from `upstream/main`, write the module (next section), and run
   the gates in [Before you open a PR](#before-you-open-a-pr).
5. Open the PR against `sambanks/octabam:main`. The template asks for the
   gates you ran and what was measured. CI runs on it; GitHub holds a
   first-time contributor's first CI run until a maintainer approves it.

Issues are turned off (`README.md`): a question about your change goes in
its PR.

## A module

One directory, `modules/<name>/`:

```
manifest.py     declares the module -- exports MODULE (tools/remix/schema.py is the vocabulary)
README.md       what it is, what was MEASURED, what is INFERRED, what is open
<sources>       .s for the ColdFire, .asm for the DSP -- or `upstream/`, a submodule
```

plus a remix that carries it (`remixes/<name>/remix.py`, or
`remixes/test/<name>/remix.py` for a remix of that one module, and a
`README.md` beside it: what is in it, where it has run;
`docs/remixes/BUILDING.md` §8) and, for anything with behaviour worth pinning, a gate
(`tools/verify/verify_<name>.py`, named in the manifest's `gates`, run by
`make check` for every remix that carries the module). Nothing else
registers it: the registry discovers every `modules/*/manifest.py`, and
refuses two modules on one key or one FX2 id.

The manifest's `category`, `author`, `author_url`, `proof` and `proof_note`
are the README's module table (`make docs` renders it and the remix index
from the manifests and the selections; the selftest refuses a module
without them, `verify_docs` a stale copy). `proof` is one of `CHECK`,
`RENDER`, `PORT`, `HARDWARE`; the note names the unit, image and date, or
the gate. A remix declares `family` (`rig`, `effects`, `mods`,
`reference`, `probes`) and the same `proof` pair.

Settings a module keeps on the card (a checkbox, a profile) go in the
shared OTX store once it exists, not in a file of the module's own;
`docs/remixer/MODULES.md` "Settings on the card".

Two skeletons and two worked examples:

| you are writing | copy | then read |
|---|---|---|
| a ColdFire modification (parts, kits, menus, MIDI, fixes) | `modules/_template_cf/` | `modules/repitch/` (one linked DRAM unit, detours and pokes), then `modules/midi-scenes/` (built from its author's repo as a submodule) |
| a DSP effect | `modules/_template/` | `modules/character/` (an in-place insert, its own render gate `verify_character`) |

`docs/remixer/MODULES.md` is the full guide; `docs/remixer/PLACEMENT.md` says
where the bytes land and how much room there is.

**Declare what it is, not where it goes.** A ColdFire module is `Linked`
units (GNU-as, symbols, no absolute addresses of its own) reached by
`Detour`s that name those symbols, plus `Poke`s and `TableGrow`s for the
OS-image edits — each asserted against stock before anything is written.
`dram=True` is the default place for code: a 10 MB reserve carved off the
unit's sample/recorder pool, placed by the build, the way midisc and
Octakit live (`docs/remixer/PLACEMENT.md`). The ~8 KB of free ROM
inside the OS image is for what must be ROM-resident, and it is shared
with everyone. A module that keeps its own DRAM (a `Runtime`) declares
the pages it takes with `ArenaReserve`, and the build composes everyone's.

**`key` is API.** It appears in the build report, and tools parse the
report. Renaming a key, or rewording a report line, is a breaking change.

## The oracle rule

**A port is done when the author's build and this repo's build agree byte for byte.**
The form depends on the module:

| the module carries | the oracle |
|---|---|
| ratified hex (`CavePatch.pinned`) with a `.s` | the build assembles and links the source at its resolved address and refuses if the bytes differ |
| a floating source-linked cave | `reference(addr)` — the ratified bytes *at that address*, checked every build |
| `Linked` units | `reference=(addr, sha256)`: the unit re-linked at the author's own address, compared every build |
| a `Runtime` recipe | every identity the recipe pins — rebuilt runtime, packed runtime, append — re-derived and compared |

`tools/verify/verify_midiscenes.py` and `verify_octakit.py` are the two
standing proofs; write the equivalent for yours. When you port someone
else's mod, run their build against the shared stock image first and use
its output as the oracle.

## Building from an author's repository

The preferred shape for a module that has a repository of its own,
because the author keeps developing where they are:

- The repo is a git submodule at `modules/<name>/upstream`, **pinned to a
  commit**; a branch is named in `.gitmodules` when the port lives on one.
  `git submodule update --init` fetches it.
- **Nothing inside `upstream/` is edited here.** A change the port needs
  goes to the author as a PR (or, with their agreement, to a fork branch
  that will become one — midi-scenes's `octabam-gas` is the pattern). A
  bump is a commit here that moves the pin, with the oracle still holding.
- The author's repo stays under its own terms. Nothing from it is
  vendored or relicensed; octabam's MIT covers octabam.
- What makes a repo easy to build from: GNU-as sources (or a recipe the
  build can drive), symbols rather than absolute addresses for anything
  the build might place, an artifact of the author's own build to prove
  against, and no Elektron bytes.

## Gates

**`make check REMIX=<name>` is the floor**, for every remix the change
reaches. There is no default remix: every target that builds or checks an
image takes `REMIX=<name>` and refuses without it (`make modules` lists
them); a gate that needs a particular image asks the registry for the
smallest remix carrying what it needs (`registry.fixture`). It builds, prices cycles, runs the shared gates (the ledger
selftest, the menu, the dirty-state render, the docs, a project under the
ColdFire port) and then every gate the selected modules declare in their
manifests (`schema.Gate`, run by `tools/verify/module_gates.py`). A remix
without a module never runs that module's gates; a module without gates
has only the shared ones. Never claim something works because it
assembled.

**`make reach`** reads the branch's diff against `origin/main` and prints
the gates it reaches: a module's remixes from the selections, a
verifier's owners, refhash for the build, `make ci-dsp`/`ci-emu` for the
toolchains. `make reach RUN=1` runs them in order. It refuses a tree that
is not rebased onto the base. Two or more remixes are printed as one
`make check-shared REMIXES="..."` (the ledger selftest, the knob census
and the isolated module gates that build their own image, once) and a
`make check-remix REMIX=<r>` each (its build, cycles, dirty state, init
regs, DRAM boot, labels, its own module gates, menu, the set under the
port, USB); `make check` is the two halves for one remix.

For acceptance evidence, use `make accept REMIX=<name>` with
`STRESS_SOURCE=<a local project>` (the fixture is generated for the
remix) or `OT_PROJECT=<dir>` (a project you prepared). Unlike the
development check, this refuses missing evidence and writes a versioned
JSON report. The pressure stages run when every DSP module in the
selection declares its dearest settings (`schema.Module.dear`); a module
without them blocks the remix, by name, never a render at defaults. See
[the acceptance contract](docs/remixer/ACCEPTANCE.md) for the fixture,
report fields, coverage and hardware limitations.

**If you changed the build rather than a module, prove it changed
nothing**: `scripts/refhash.sh save` on a tree you trust, then
`scripts/refhash.sh check` — 24 configurations, artifacts *and* build
reports, bit-identical. Every step of the DRAM platform landed under it.

**Say what was measured and what was inferred**, in the README, with what
would falsify each claim; retract in every document that repeated a
number, not just the one you are editing.

**Flashing is the author's own step, on their own unit**, and it is
expensive: bump `BUILD` so the unit's version string maps to a commit,
stamp projects after any parameter-layout change (`tools/hw/ot_project.py
stamp-defaults`), read `docs/remixer/FLASHING.md` first, and record
anything that goes wrong in `docs/remixer/FAILURE_MODES.md` the moment it
is seen.

## Before you open a PR

Rebase onto current main, then run the gates on the rebased tree. Gates
run before the rebase are not a result: a branch that merges without a
conflict can still fail on main (PR #396's stress fixture named a knob
that #415 had renamed).

```bash
git fetch upstream && git rebase upstream/main
make reach BASE=upstream/main        # the gates this diff reaches, in order
STRESS_SOURCE=<a local project> make reach BASE=upstream/main RUN=1   # run them
STRESS_SOURCE=<a local project> make reach BASE=upstream/main RUN=1 KEEP=1 JOBS=4
#   KEEP=1: every gate, then one table (instead of stopping at the first failure)
#   JOBS=4: the check-remix lines over four worktrees at a time (make check-remixes)
```

What `make reach` lists, by what changed:

| changed | gates |
|---|---|
| `modules/<name>/` (a pin bump too) | `make accept` for every remix that carries the module (one `REMIXES="..."` line; it runs both halves of `make check` itself, the shared half once) |
| `remixes/<name>/remix.py`, `remixes/test/<name>/remix.py` | `make accept` for that remix |
| a file under `tools/` or `scripts/` | by dependency: the Python imports and the `tools/x/y.py` paths the code runs or reads form a graph, and a change reaches the gates that depend on it. The build (`build_bus.py`, `cycle_count.py`, `dsp/`) and what it imports: `scripts/refhash.sh check` (save the baseline on main first), `python3 tools/verify/image_identity.py` (every remix built from the base and from this tree; `RUN=1` then checks the remixes whose image moved), `make test-acceptance`, `make check-shared` once for the cover. A gate of the shared half (the selftest, slots, replaces, docs, label_fmt, the knob census, a manifest gate with `remix_arg=False`): `make check-shared` once (for the cover) or for the owners' remixes. A gate of the per-remix half (dirtystate, initregs, dram_boot, labels, modenames, hidden, menu, set, usb): `make check-remix` for the cover. A manifest gate with `remix_arg=True`: its owners' remixes. The acceptance runner, the stress generator, `pressure.py`: `make test-acceptance`, `make accept` on the cover. A file no gate depends on: nothing, and the listing says so |
| `tools/harness/dsp_host/`, `tools/patches/`, `scripts/setup.sh`, `scripts/vendor.sh` | `make ci-dsp`, then the cover (rebuild the toolchain first; a `dsp_host` change builds in an isolated tree, AGENTS.md; identity cannot see a toolchain change, both trees build with the same binary) |
| `tools/emu/ot_emu/` | `make ci-emu`, `make emu-cf`, the cover's per-remix half, with OT_PROJECT |
| `Makefile` | by target, against the base: a target of the check graph (`bus`, `cycles`, `verify*`, `check*`), a variable or a `define`: identity, the cover and `make ci`; `accept`, `reach`, `check-remixes`, `test-acceptance`: the runner tests; a ci target: `make ci`; any other target: nothing |
| `docs/`, `*.md` | `python3 tools/verify/verify_docs.py` |
| `.github/` | `make ci` |
| anything else | the cover, named as unclassified |

**The cover** is the fewest remixes that between them carry every module, computed from the registry each run (9 of 27 on 28 Sep 2026: `cfmeter`, `bottleservice`, `recfix`, `mods`, `euclid`, `miniverb`, `repitch`, `tapeecho`, `usb-full`), so every module's gates and every kind of per-remix gate run at least once. A remix outside it is a subset of one inside. `make reach REACHARGS=--all` makes the floor every remix. **Identity** (`tools/verify/image_identity.py`) builds every remix from the merge-base (a kept worktree under `out/identity/base`) and from this tree with the shipping flags and compares image and report byte for byte; a remix whose bytes did not move has nothing new for a gate that reads the image.

Without `STRESS_SOURCE` the accept line cannot run, so the list carries
the `make check` lines separately and names the accept line as blocked.
A remix with a DSP module that declares no `dear` makes `make accept`
report `blocked` with the module's name; say so in the PR. List each
command and its result in the PR body (`make reach`'s output is the list).

## What CI checks

`.github/workflows/ci.yml` runs on every PR, on `main` and by hand
(Actions → CI → Run workflow), on Ubuntu and macOS. It has no Elektron
bytes, so it checks only what needs none:

| job | make target | what it proves |
|---|---|---|
| gates the PR reaches | `make reach` | the diff classifies and the tree is rebased; the job log carries the gate list the PR body must answer (pull requests only) |
| acceptance runner tests | `make test-acceptance` | `make accept` refuses skipped, failed, incomplete and over-budget evidence; `make reach` classifies paths as documented |
| dsp56300 + our patch | `make ci-dsp` | the vendored DSP emulator at its pin takes `tools/patches/dsp56300.patch`, builds, passes upstream's own test runner, and `dsp_asm` emits the one-word displaced move (`make check-asm`) |
| ColdFire port unit tests | `make ci-emu` | `tools/emu/ot_emu` builds against the pinned cores and passes the EMAC, peripheral and mc68k unit tests |

The port's `rtos`, `dsp` and `repitch` tests read the stock OS and are
excluded from CI by name. **A green CI run says nothing about a
remix**: building, booting and playing one needs 1.40C, which is why the
gates above run on your machine. Actions are pinned to commit SHAs (the
repository requires it); a bump is a PR that changes the SHA and the
version comment beside it.

## Etiquette

- Read the traps in `AGENTS.md` before trusting an assembler, an
  emulator, or a null result.
- Collisions are refused by name; `make modules` prints the matrix. If
  your module cannot share an image with another, say so in its README
  and say why (a shared hook site, a shared data structure).
- Keep the report text stable, keep `priority` stable (it is
  byte-load-bearing), keep `key` stable.
- A PR that touches a submodule pin says which upstream commit and why.
