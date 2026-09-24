# WP-C2: ColdFire parameter handlers

- **Status:** done (emulator acceptance); unflashed.
- **Branch and commit:** machinedrum @ this commit.
- **Date:** 24 September 2026.
- **Agent:** Codex, main checkout, WSL.

## What was done

The build extracts 44 distinct non-empty descriptor handlers for all 50
playable engines from the user's pinned MD OS 1.63. GNU as copies the
original 12,808-byte code slice and two lookup-table spans into a
ColdFire DRAM unit. The linker changes only 148 absolute operands:
128 table references and 20 E12 reads of the MD's internal-SRAM word
at 0x0100150c. The latter now names the writable symbol
md_handler_sram_word, which the future live producer must supply.
No extracted firmware bytes are committed.

The reference md_profile map= path captures each handler's exact
parameters, SRAM word, and 84-byte record before and after a call.
A firmware-free ColdFire gate runs both original and build-linked
handlers against the same input. TRX-S2's live map= assignment stays
on the empty handler, so its descriptor is separately compared source
versus port on the nine captured parameter vectors; that comparison
has no live record oracle. GND-NS sends no trigger record but does
invoke its descriptor, which is compared normally. (❌ 24 Sep 2026, WP-C4:
both send a two-word trig record that the map hook's four-word filter
dropped. TRX-S2 stays on the empty handler because MD OS 1.63's live
handler table points it there; see MACHINEDRUM_MACHINE.md section 12, "How
the MD sends a record".)

## Acceptance check

The 50 map scenarios were captured in one reference run. The E12
scenarios were repeated with the newly identified SRAM input captured;
their cases and corresponding map lines replaced the first run's E12
cases. Then:

    $ make bus REMIX=machinedrum
    MD handlers: 50 engines, 44 code entries, 148 relocated table operands

    $ python3 tools/harness/md_reference/md_handler_cases.py --verify-only
    PASS: full handler code and both table spans match the pinned OS apart from 148 relocated operands
    PASS: 450 handler cases, 50 engines, 84 record bytes per case match source and port; 9 additional TRX-S2 descriptor comparisons

    $ MD_EMU=out/mdverify/isolated/emu/ot_emu OT_PROJECT=out/stress-project make verify-md-transport
    [ok] voices: core 1's blocks equal the replay's  33503 of 33503 blocks bit-identical (20544 non-silent), 2094 of 2094 periods
    verify_md_transport: PASS

    $ bash scripts/refhash.sh check
    ALL 24 CASES BIT-IDENTICAL

make check REMIX=machinedrum reached the repository-wide verification
matrix. Six Octakit remixes still fail to assemble the pre-existing dirty
modules/octakit/upstream at runtime.S:438; Machinedrum was not among those
failures. The same six failures were present before WP-C2.

## Measured

✅ The source identity and 450 case results above are recorded in
MACHINEDRUM_MACHINE.md section 12, “WP-C2 ColdFire parameter handlers.”
The source check covers every byte of the linked code and both table
spans; the execution check covers all 84 output bytes for each case.

## Retracted

❌ The earlier claim that every descriptor handler is a pure
f(record*, params*) is wrong for E12: ten distinct E12 handlers read the
MD SRAM word at 0x0100150c through 20 operands. The captured map
scenarios observed 0x00000bb8. The proposal now carries the correction.

## Open and handover

WP-C4 must call the linked handler selected by engine, set
md_handler_sram_word from live control state, and send the resulting
record through WP-C1. This packet links and verifies handlers; it
does not add the live producer or qualify hardware timing.
