# DSP memory inventory for the dynamic Analog BD prototype

The accompanying graphic is generated from this branch's built DSP uploads and
engine metadata:

```sh
python3 tools/harness/analog_bd_memory_map.py
```

It writes [memory-map.svg](memory-map.svg) and a copy in
`out/analog-bassdrum/dynamic/`. The bars show the
default memory map and a **mixed 808 + 909 Part on both cores**. Each address
and size is in 24-bit DSP words. Gray X covers stock data and areas whose
runtime safety is not established; a blank upload address is not free RAM.
The diagram is an allocation inventory, not a live dump of every effect's
delay line.

| Resource | Core 0, payload A, tracks 5–8 | Core 1, payload B, tracks 1–4 |
|---|---:|---:|
| Stock mapped private P window shown | `0000–1FFF`, 8,192 words | same |
| P words in the DSP boot upload, below `2000` | 8,159 | 7,583 |
| Stock P upper loaded address | `1FDF` | `1D9E` |
| SPRING donor repurposed for Analog BD | `1252–1678`, 1,063 | `1012–1438`, 1,063 |
| Resident loader + common desk | 385 | 385 |
| Active engine P pool | 643 | 643 |
| 808 + 909 in that pool | 246 + 377 = 623 | same |
| Pool slack with both present | 20 | 20 |
| Preserved stock reverb helper | 35 | 35 |
| P gap after highest stock upload, within first 8K | 32 | 609 |
| X words written at boot | 20,591 | 20,528 |
| Y words written at boot | 1,321 | 1,337 |

The core 0 P upload also writes 190 words of boot/shared-window code at high
P addresses; that is why its total P upload count is 8,349 rather than 8,159.
These counts describe the built image, not free memory. The stock firmware
and effects write additional X/Y state at runtime.

The Analog BD private X allocation is the same on both cores:

| X range | Words | Use |
|---|---:|---|
| `2840–2B3F` | 768 | Common coefficients/tables |
| `2B40–36FF` | 3,008 | Relocatable engine tables; 808 1,024 + 909 1,425 leaves 559 |
| `3700–37FF` | 256 | Four 64-word voice blocks |
| `3800–3807` | 8 | Dispatch entries and loader status |

Private Y has system data through `0794` on A / `07A4` on B; the remaining
lower region before `1000` was measured free. Stock assigns `1000–3FFF`
to four FX1 instances and `4000–BFFF` to two FX2 instances per core. The
shared on-chip `30000–3FFFF` is visible through P, X and Y aliases, but the
stock allocator assigns its four 16K-word quarters to further FX2 slots:
the low half to core 0, the high half to core 1. Stock parameter staging also
uses its first 72 words. Reserving part of it for engine code would require
changing the FX2 memory plan and checking every compatible effect.

The ColdFire's SDRAM library is a separate resource: 15,544 bytes of engine
packages currently live in a declared platform reserve, with about 7.58 MiB
above the highest current allocation. The DSP56721 has no external memory
controller, so the DSP cannot execute directly from that SDRAM.

The DSP's OMR can trade Y capacity for more P capacity, but stock uses Y
through `BFFF`; a map with 16K P leaves only 40K Y. That is a redesign of
stock FX allocation, not a free 8K program expansion. `P:2000` has run code
on hardware in an earlier probe, but its upper usable limit is unmeasured;
the diagram stops at the first 8K for this reason.

## Switching result and next memory choice

`python3 tools/harness/verify_analog_bd_switch.py` sent real ColdFire packet
streams through the resident DSP loader, first with four 808 tracks and then
four 909 tracks. Each core produced **132 muted source calls**, equal to 33
16-sample frames or **528 samples / 11.97 ms** at 44.1 kHz. A sounding 808
voice was cut to exact zero at BEGIN, and the queued 909 trigger sounded at
COMMIT. This is a measurable source dropout and an abrupt waveform edge;
stock FX tails may mask it at MAIN, but the dry transition is not seamless.
With one selected synth track, the protocol's 133-packet 909 load takes about
48 ms in frame terms. Hardware timing has not been measured.

For 808/909, the first memory optimization is to retain both packages once
loaded and retarget only the affected track when a Part changes. They already
fit together, so repeated switches should not need a code transfer. A short
fade at the retarget boundary can remove the hard edge. Preserving the old
voice tail would require overlap of old and new voice state and execution,
with an additional X and cycle budget. For future engines, the catalogue can
be large in SDRAM, while each Part's **distinct active engines per core** must
still fit the measured 643-word P and 3,008-word X pools. More simultaneous
program space requires proving a larger safe P range, sharing/reducing engine
code, or changing the stock FX memory allocation.

Sources: `out/analog-bassdrum/image/upload_A.bin` and `upload_B.bin` parsed
as DSP boot records, `out/analog-bassdrum/image/dynamic.json`, this branch's
`make bus REMIX=analog-bassdrum` report, `docs/firmware/CHIP.md` §§0/3–4,
`docs/firmware/DSP.md` §§3/7, and the switch capture produced by the command
above. No firmware bytes are embedded in the diagram.
