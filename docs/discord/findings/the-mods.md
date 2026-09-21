# the-mods — Discord catalog

Source: `docs/discord/Octahackers - the-mods [1546462410833928282].txt` (Octahackers guild,
channel `the-mods`, topic: "Listing firmware modifications, tooling, creators/modders, and
other resources."). Exported 8 messages total; this channel is a curated reference index, not
a discussion thread — every substantive message is a catalog entry posted by one indexer
(`zackyoti_98392`) on behalf of the listed authors. Full text below is transcribed verbatim
from the export (including author handles as given).

---

## Channel intro

**Posted:** 07.09.2026 20:55, by `yldopactyly`

> Hello. This is the channel which will list and provide links and basic info for the firmware
> modifications, creators/hackers, their tooling, and the other resources associated with this
> server.

No catalog content itself — states the channel's purpose.

---

## Elektron Firmware Tool

- **Posted:** 13.09.2026 01:19, by `zackyoti_98392`
- **Author:** `@mischa85`
- **Category:** Tools
- **Instruments:** Elektron instruments utilizing container formats **ELE3, ELE2, ELEK, AD**,
  and the older **Pre-ELE** (Machinedrum/Monomachine)
- **Description:** An unofficial C tool to inspect and modify Elektron instrument OS files
  (`.syx`). Not affiliated with or endorsed by Elektron.
- **Link:** https://github.com/mischa85/elektron-firmware-tool

**File-format note (directly relevant to octamad):** this is the one entry in the channel that
names the Elektron OS container formats explicitly: **ELE3**, **ELE2**, **ELEK**, **AD**, and
**Pre-ELE** (used by the Machinedrum/Monomachine, i.e. older than the ELE-prefixed formats).
The channel gives no further detail (no version-to-format mapping, no byte layout) — just the
list of container-format names and that this tool inspects/modifies `.syx` OS files carrying
them.

**Potentially useful reference tool.** A general-purpose C tool for inspecting/modifying
Elektron `.syx` OS containers across the ELE3/ELE2/ELEK/AD/Pre-ELE format family is directly
adjacent to octamad's own build/verify tooling (`tools/build/build_bus.py`,
`tools/verify/*`), which composes and patches Octatrack OS images. Worth checking whether it
documents the container/header format in enough detail to cross-check or simplify anything in
this project's own image-inspection code — while remembering the repo rule that no Elektron
byte itself may ever be vendored in.

---

## Octamax

- **Posted:** 13.09.2026 01:21, by `zackyoti_98392`
- **Author:** `@maxolydian`
- **Category:** Modifications, Tools
- **Instrument:** Octatrack MK1/MK2
- **Description:** An educational toolkit for understanding how the firmware of the Elektron
  Octatrack works. A reverse engineering project.
- **Link:** https://github.com/mxldyn/octamax
- **Embed subtitle (from Discord's GitHub preview):** "Educational reverse engineering of the
  Elektron Octatrack MKII firmware (OS 1.40C, ColdFire + DSP56xxx) — tooling, notes and
  behavior patches"

**Potentially useful reference tool.** Explicitly targets OS 1.40C on the same
ColdFire + DSP56xxx architecture octamad builds against; likely a source of independent
reverse-engineering notes/tooling worth cross-referencing against this project's own
`docs/firmware/` findings.

---

## Octabam

- **Posted:** 13.09.2026 01:22, by `zackyoti_98392`
- **Author:** `@bamshanks`
- **Category:** Modifications, Tools
- **Instrument:** Octatrack MK1/MK2
- **Description:** Custom DSP effects and firmware patches for the Elektron Octatrack
  MKI/MKII.
- **Link:** https://github.com/sambanks/octabam
- **Embed subtitle:** "Custom DSP effects for the Elektron Octatrack MKII — original DSP56300
  algorithms (ChonVerb reverb, BongDelay) on a cross-core send bus, delivered by patching the
  stock OS image"

**Note:** this is the upstream project octamad forks/remixes from (author handle `sambanks`
matches the `upstream/main` remote and `sambanks`-authored PRs seen in this repo's git log,
e.g. `lock-slots`, `jit-parked`). Not a third-party reference — this is the parent repo.

---

## Octakit

- **Posted:** 13.09.2026 01:23, by `zackyoti_98392`
- **Author:** `@em`
- **Category:** Modifications
- **Instrument:** Octatrack MK1/MK2
- **Description:** Firmware mod providing 256 Kits per Project, replacing the native Parts per
  Bank system.
- **Links:**
  - https://www.junes.website/goodies/octakit
  - https://github.com/emuyia/ems-octakit
- **Embed subtitle:** "Custom firmware mod for the Elektron Octatrack. Replaces 4 Parts per
  Bank with 256 Kits per Project."

Note: there is an existing `Octahackers - OCTATRACK - octakit` Discord export file in this
same `docs/discord/` directory, suggesting a dedicated channel with more detail on this mod.

---

## MIDI scenes

- **Posted:** 13.09.2026 01:23, by `zackyoti_98392`
- **Author:** `@BUKKAKEBOREALIS`
- **Category:** Modifications
- **Instrument:** Octatrack MK1/MK2
- **Description:** MIDI scenes usable with the crossfader.
- **Link:** https://github.com/bkkbrls-del/midisc
- **Embed subtitle:** "Octatrack 1.40C MIDI scene locks (1.40MSCN6) — rebuild from your own
  stock OS"

**Note:** "rebuild from your own stock OS" mirrors octamad's own no-vendored-bytes /
build-from-user's-1.40C pattern (`.incbin` from the user's stock image at build time). There is
also a dedicated `Octahackers - OCTATRACK - midi-scenes` Discord export in this directory with
presumably deeper technical detail.

---

## octalab-notes

- **Posted:** 13.09.2026 01:24, by `zackyoti_98392`
- **Author:** `@BuMa`
- **Category:** Modifications, Tools
- **Instrument:** Octatrack MK1/MK2? (question mark is in the original post, indicating the
  indexer was unsure which hardware revision)
- **Description:** Reverse-engineering notes on the Elektron Octatrack MKI, OS 1.40C.
- **Link:** https://github.com/nordseele/octalab-notes

**Potentially useful reference tool.** Another independent OS-1.40C reverse-engineering notes
repo (this one MKI-focused per the description, despite the "MK1/MK2?" category tag) — worth
diffing against octamad's own `docs/firmware/` for MKI-specific findings, since most of this
project's own measurements (per CLAUDE.md) are MKII-derived.

---

## octa-bt-pt

- **Posted:** 13.09.2026 01:24, by `zackyoti_98392`
- **Author:** `@Bryan T (ukulele owner)`
- **Category:** Modifications
- **Instrument:** Octatrack MK1/MK2
- **Description:** A parameter default patch tool for the Elektron Octatrack (OS 1.40C).
- **Link:** https://github.com/bryantysinger/octa-bt-pt
- **Embed subtitle:** "Tool for patching Octatrack firmware, focused on default values when a
  new project is created"

**Note:** "Bryan T" matches the "Bryan T" cited multiple times in this project's own
CLAUDE.md traps (LOFI2 stock-table-address bug, `modules/hello/` overlong-abbr crash) — same
contributor as a named module author elsewhere in octamad's history. This tool's focus on
default parameter values on project creation is directly relevant to the CLAUDE.md trap about
stored parts carrying stale bytes across a slot-layout change (`stamp-defaults`).

---

## Summary table

| Name | Category | Author | Instrument | Link |
|---|---|---|---|---|
| Elektron Firmware Tool | Tools | mischa85 | ELE3/ELE2/ELEK/AD/Pre-ELE instruments | github.com/mischa85/elektron-firmware-tool |
| Octamax | Modifications, Tools | maxolydian | Octatrack MK1/MK2 | github.com/mxldyn/octamax |
| Octabam | Modifications, Tools | bamshanks | Octatrack MK1/MK2 | github.com/sambanks/octabam |
| Octakit | Modifications | em | Octatrack MK1/MK2 | github.com/emuyia/ems-octakit, junes.website/goodies/octakit |
| MIDI scenes | Modifications | BUKKAKEBOREALIS | Octatrack MK1/MK2 | github.com/bkkbrls-del/midisc |
| octalab-notes | Modifications, Tools | BuMa | Octatrack MK1/MK2? | github.com/nordseele/octalab-notes |
| octa-bt-pt | Modifications | Bryan T | Octatrack MK1/MK2 | github.com/bryantysinger/octa-bt-pt |

## File-format notes relevant to octamad

The only explicit mention of Elektron OS container formats in this channel is in the
**Elektron Firmware Tool** entry: **ELE3, ELE2, ELEK, AD**, and **Pre-ELE** (the last used by
the Machinedrum/Monomachine, predating the ELE-prefixed formats). No byte-level structure,
version mapping, or header layout is given in this channel — only the format-name list and
that the tool works on `.syx` files carrying them. This is a lead worth following into the
`elektron-firmware-tool` repo itself if octamad's own image-parsing code ever needs a
cross-check, but nothing here can be copied in directly per the repo's "never an Elektron byte
in the repo" rule.

## Tools flagged as potentially useful reference for octamad's own build/verify tooling

1. **Elektron Firmware Tool** (mischa85) — general `.syx` OS-container inspector/modifier
   across the whole ELE3/ELE2/ELEK/AD/Pre-ELE family.
2. **Octamax** (maxolydian) — OS 1.40C, ColdFire + DSP56xxx reverse-engineering toolkit and
   notes, same architecture and OS version octamad targets.
3. **octalab-notes** (BuMa) — independent OS 1.40C reverse-engineering notes, MKI-focused.
