# WP-A4 Boot-time init on the OT: report

- **Status:** review
- **Branch and commit:** `machinedrum` @ `cab97a3`
- **Date:** 24 September 2026
- **Agent:** overnight Machinedrum handover

## What was done

The relocator now follows the boot-time init descent from `P:0x100057` and
patches the voice-record, P-I base/count, and sine-table immediates. The
replay harness accepts `--init`, clears the proposed destinations, runs the
relocated sequence, and checks the initialized spans without requiring a
hardware image.

## Acceptance check

```text
$ out/md_reference/md_replay out/md_profile/cap4/c10 --reloc --init
relocated 29 regions, 3130 patched words; old regions wiped
init: sine 32768/32768 pi 9216/9216 voice-X 1024/1024 voice-Y 1024/1024

$ out/md_reference/md_replay out/md_profile/cap4/c37_16 --reloc --init
relocated 29 regions, 3130 patched words; old regions wiped
init: sine 32768/32768 pi 9216/9216 voice-X 1024/1024 voice-Y 1024/1024
```

## Measured

- ✅ The relocated init writes all 32,768 sine words, 9,216 P-I words, and
  1,024 words in each X/Y voice span checked by the harness.
- ✅ The six-voice P-I span is `0x2400` words. The original stock init count
  was `0x6000`; the proposed map deliberately patches it to `0x2400`.
- ✅ The relocator reports 29 moved regions and 3,130 patched words on both
  acceptance captures. The code and measurements are recorded in section 12
  of `MACHINEDRUM_MACHINE.md`.
- *inferred* Passing this check shows that the relocated boot sequence can
  initialize the proposed spans in replay; it does not prove that the stock
  nine/16-voice P-I buffers fit the proposed shared window.
- All results are **pending the user’s sign-off** on the A2 address map.

## Retracted

None.

## Open and handover

- The user must choose the A2 voice-home and shared-window policy. WP-A3 is
  blocked until that choice is made; rerun the init check if the selected
  policy changes these destinations.
- The six-voice cap is a layout proposal, not a decision to silently drop
  stock voices. No hardware or flash image qualification was attempted.
