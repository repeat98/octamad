# Hardware failure modes: the register

Symptom → cause (measured, inferred or open) → fix. Add an entry the moment
a mode is seen on hardware.

## A white-noise wash from a sample host with trigs on it ✅ measured on the unit, fixed (image 43)

**Symptom.** BusDelay on a track with its own trigs: T3 STATIC with a trig
on every step washes from the second pass of the pattern on, T2 THRU with a
trig on every step at once (the THRU's re-open clicks ride on top). A
steady white-noise wash out of the host track: its LEVEL 0 silences it,
FDBK moves the repeats underneath and leaves it, WET scales it without
removing it, STOP does not end it, a double STOP thins it, PLAY or a
project reload clears it -- and it comes back after the next full loop.
T1 as host (position 0) with the same trigs: clicks, no wash, in the one
test made. Trigs on a sender only: nothing. The bus input is irrelevant
(every SEND at 0: the same). Sam's MKII, 21 Sep 2026.

**Images.** 38: one test clean. 39, 40, 41: wash. 42 (= 41 minus PR
#344's four init stores): one test clean, then the wash after a reload and
a loop. So the mode is state-dependent and single runs do not bisect it;
the init stores were not the cause (their removal stays, harmless). The
`$84..$88` relocation (PR #346) and the once-per-block glides (PR #345)
were not it either and stay.

**What the port sees.** Nothing, in every form: the host's sample staged
and playing, a THRU host, a trig every step, two loops, garbage RAM, on
38, 39, 40, 41. A PC watch on the delay's proc entry shows both calls of a
split block with the same `r7`; on its init entry, one call at load across
two loops. The port's cores are lock-step: a race between core 0's flip and
a core-1 client is structurally invisible to it.

**Cause and fix (image 43, 21 Sep 2026: T3 STATIC with a trig every step clean through eight loops and a project reload, where 42 washed after one; the FX2 change on T1 clean too).** Each bus participant's
proc reconstructed the second call's frame offset from a flag and a split
the FIRST call stashed in its block (`$65/$66`), consumed by the matching
a=1 call. If that stash does not survive between the two calls when a trig
lands there (nothing measured; the stash was written in July on the
harness), the second call runs as a first call: at position 0 the rotation
tracker advances twice in a frame and keeps a lead of one for ever (the
R25 "metallic on every power cycle" mode: only a re-select or a transport
start, which makes the instance miss blocks, fall behind and snap, cures
it -- exactly what PLAY and a reload do here); elsewhere the call writes
its block from frame 0. Since 21 Sep 2026 the offset comes from `r0`,
which the dispatcher passes as 0 on a first call and 2 x split on the
second (the port: `r0 = $e` for a trig at frame 7): no state between the
calls. Same code in SEND, BusDelay and BusVerb. The stash itself was never measured on the unit; the fix's
effect was.

## Sequencer stuck on step 1 at the first play: images 44 and 45 🟡 two causes inferred, fix built (image 46)

**Symptom.** Image 44 (21 Sep 2026): flash, load, play -- stuck on step 1,
the standard wedge; power-cycle and reload recover. **Cause, inferred.**
The one change on core 0's first block was the housekeeper's new stamp
clear, written as four one-word displaced Y stores (`move a,y:(r3+$1)`,
`+$2`, `+$3`): no module and no stock code in either payload uses that
form, the assembler's one-word displaced move was patched in on 14 Sep
2026 and proven on the X form (`move x:(r7+$15),a` = `0257de`, 533 stock
sites), and the port runs whatever the assembler encodes, so a chip that
decodes that word differently is invisible locally. **Image 45** clears the stamps with `move a,y:(r3)+` after `m3 = $ffffff`
and wedged the same way, so the form was not (or not only) it; the rule
stands regardless: a DSP instruction form with no stock precedent in the
payload disassembly (`tools/build/dsp_disasm_all.py`) does not ship without
a hardware probe. **The second cause, inferred.** The tracker's new check
reads the client's last write offset from its own slot and turns it into
the stamp address. An FX1 slot with no effect runs SEND (id 0 aliases to
SEND) at an r7 below `$6200`, which ROTINIT deliberately never seeds, so
on the unit that slot is boot garbage until the first `rotuse` store, and
the read went to a wild Y address -- the peripheral registers live in Y,
and a stray read of a host-port or ESAI register stalls the handshake at
the first block. The port zeroes RAM: the slot reads 0 there. **Image
46** masks the value (`and #>$30`) before it becomes an address, as every
other tracker address is built; the gate chain now runs the port with
`--dsp-dirty` on the trig-host fixtures as well. Rule: no address from a
word that init did not seed, unmasked.

## A white-noise wash from a THRU host past position 0 with a trig on every step; bleed into the bus with every SEND at 0 🟡 the core-1 lead of one measured (image 47), its cause inferred, fix built (image 48)

**Symptom.** BusDelay on T2 (a THRU machine) with a trig on every step of
T2: a white-noise wash at once, on images 40 through 43 alike (43 fixed the
sample-host wash above; this one is untouched by the r0 offsets). T1 as
host, a THRU with the same trigs: the THRU's re-open clicks, no wash. A
THRU host with its ordinary one trig per bar: nothing, on every image
since the one-aux rig. On image 46 a silent run on T1 was clean, the same
on T2 gave static and the wash, and with every SEND at 0 audio still
reached the bus.

**What the port sees.** Nothing: a THRU host with a trig every step under
`verify_set` (`out/OCTABAM89_t2thru`, tones at the inputs) prints flat;
a THRU host and a sample host are dispatched identically (a=0 at `r0 =
0`, `n7 = split`; a=1 at `r0 = 2 x split`, `n7 = 16 - split`).

**Images 44–47.** 44 and 45 (the tracker's self-check: stamps, a hold
flag) wedged on the first play, the entry above; 46 played with static
and the wash. 47, a probe: the delay printed a marker tone on every block
whose flag said a client's stamp was gone — a permanent tone on plain
play, so the core-1 tracker sits one step ahead all the time on the unit
(✅ measured; the port never shows it).

**Cause (inferred from two port measurements, `XBUS.md` "An FX1 slot is
not a client").** Id 0 is SEND and FX1 NONE is id 0, so SEND ran on every
FX1 slot with no effect, at r7 0x6100/0x6400/0x6700/0x6a00 (measured, PC
watch on Sam's project). The 0x6100 call registered and sent from an
unseen page byte (the bleed), and on core 1 it ran the tracker's compare
before position 0's advance: a flip landing before it snaps T to R, the
advance then leads by one, and `T == R + 1` is kept for ever. Under the
port the flip lands late in core 1's frame in every frame watched, which
is why every local run was clean.

**Fix (image 48).** SEND returns at proc entry on an FX1 r7: no
registration, no write, no tracker call. The self-check is removed; the
tracker body is image 43's. Falsified by: 48 still washing on T2 THRU with
a trig every step, or still bleeding with every SEND at 0.

**Structural fix (image 49, built before 48 was heard).** The phase
agreement itself is gone: eight accumulator and chain buffers, a server
reads three back, the housekeeper clears two on, and a core-1 client
counts its own blocks from a seed read at init, checked against the
rotation once a block with a tolerance of one (`XBUS.md` "The
accumulators", "Housekeeping and the rotation"). A label one off in either
direction touches no buffer being cleared or read, and a count cannot
flap with the flip's phase. Costs one more block of latency (48 samples).
The port's two-core gate is bit-identical to the one-core control under
every skew, which under the old tracker was only true of the skews that
left the flip on one side of every read. Falsified by: any wash or static
on 49 that a host position, a trig pattern or a load changes.

## Audio engine wedged, sequencer alive: the master loop ✅ measured

**Symptom.** The sequencer runs but no audio plays, sample preview is
silent, the record meters for B/C/D sit lit. Distinct from the DSP hang
(there the sequencer freezes).

**Cause (measured 6 Sep 2026).** The master's station (T8, Character in
the return role) was sending into the reverb bus it returns: T8 FX1 -VRB
at 71 in bank02's parts; turning it to 0 brought the audio back live. Why
the loop reads as silence rather than a squeal is not established. On the
tag-93 rig (5 Sep) one instance cleared with a power-cycle; the 6 Sep
instances did not.

**Fix.** By construction: the stations have no sends, and the SEND is
refused at track 8's dispatch position on payload A whatever its knob says
(`tools/verify/verify_onebus.py`). The refusal outlived the T8 return (20
Sep 2026): with MASTER TRACK on, T8's input is the mix, the hosts' wet
included, so a send from T8 would put the bus's wet back into the bus.

## The audio engine wedges with only BusVerb + the return 🔴 cause open (the return itself removed 20 Sep 2026)

**Symptom.** Playing, the output drops to the noise floor and never comes
back while the transport keeps running.

**Measured (13 Sep 2026, image 94, `tools/hw/ot_soak.py`)**, T5 FX2 =
BusVerb, T8 FX1 = Character as the return, every other slot stock:

| configuration | return level | 3 min soak |
|---|---|---|
| return alone, no engines | 127 | clean |
| BusVerb, return at 0 | 0 | clean (twice) |
| BusVerb + return | 127 | silent at 131.5 s, never recovered |
| the same, repeated | 127 | clean |
| the same, 9 min | 127 | clean |

Not the cycle wall (this layout is nowhere near it). Rate ~one freeze in
15 minutes, so a 3-minute pass cannot clear a configuration. Recovery: a
transport restart.

**Cause.** Open. The only configuration that wedged is the one where the
reverb's output reaches the mix. Next: soak `BusVerb + return` against
`BusDelay + return` for tens of minutes each.

## BusDelay silent with its knobs locked: the MODE formatter wrote over the minimum table ✅ measured

**Symptom.** No delay audible; BusDelay's TONE, PING and MIX pinned and the
encoders would not move them; cleared by a reboot, returned when the
delay's page 2 was drawn.

**Cause (measured under the emulator with a write watch, 13 Sep 2026).**
`tools/build/mode_names.py` was handed the clone's page descriptor `P` and
wrote the rename bytes at `P + 0x4e + 6·slot`; the names live at `E + 0x4e`
and `P = E + 0x38`, so every rename landed 0x38 too high, in the
minimum-value table (`P + 0x6a + 4·slot`). BusDelay's GRAIN names hit
`min[3..5]` (TONE, PING, MIX) with 0x4d444550 / 0x4d524154: a knob whose
minimum is 1.3 billion cannot be turned. `verify_modenames` read the names
back from the same wrong offset and passed. Character's SAT view and
Modulation's COMB view had the same fault with a smaller blast radius.

**Fix.** `NAMES_AT = 0x16` (P-relative); the verifier reads there.

The stored values themselves (TONE 68, FDBK 85, AUX 90 in OCTABAM86's
parts, every other track's AUX at 110-127) were the part's own bytes;
re-stamped from the manifests (OCTABAM87) the rig measured clean on the
ladder at every rung. An autocorrelation of the whole mix that "measured
TIME inert" was reading the material's own eighth and quarter at 121 BPM
(248 / 496 ms) and is retracted; measure a delay time from the spacing of
the decaying repeats after the source stops.

## CC PAGE 2 did not write on hardware ✅ fixed (image 96)

**Symptom.** CC 62-67 changed nothing on the panel, transport stopped or
running, on an image whose dispatch vector held the cave's address.

**Cause.** The cave used the PLAYBACK page-2 editor's three stores
(`0x4003a474`), so every CC corrupted the track's PLAYBACK page-2 byte and
never touched FX2's. The FX2 editor's stores are Part `+0x8f084`, shadow
`0x100a51d2`, lane +0x38.

**Fix.** The cave uses those; `verify_ccpage2` proves the write against the
FX2 editor; CC 63 on channel 5 moved SHMR on the panel and raised the
tail's 2-8 kHz bands 5-8 dB (image 96). Every page-2 sweep taken over the
old cave is void.

## BusDelay's SEND knob drew TIME's division labels ✅ measured

**Symptom (15 Sep 2026, on the unit).** BusDelay's first knob printed
`1/8`-style labels at some settings.

**Cause.** `modules/tempo-sync` registered the TIME formatter on DELAY
SERVER slot 0; TIME has been slot 1 since the one-aux re-slot (7 Sep
2026), so the label cave drew the SEND knob (then named AUX) and TIME drew
plain numbers. The value published was the knob's (the port: CC 40 on a
host moves record halfword 12 and the host's own send registers).

**Fix.** Registered on slot 1. The knob is `SEND` on every track since the
same day (it was `AUX` on SEND, BusDelay and BusVerb alike), and the
engines' `MIX` is `WET` and add-only: the send passes each stage at unity
and WET adds the effect. As a crossfade the reverb's MIX faded the delay
out and both at 0 returned the dry send alone (measured on an impulse,
15 Sep 2026: the four corners of the two knobs gave tail-only / tail
without the repeat delay / repeats only / the dry once).

## A generated project shows as modified and RELOAD refuses ✅ measured

**Symptom.** A project written by `tools/hw` loads, shows the modified
marker at once, and RELOAD PROJECT does nothing.

**Cause.** The unit's saved state is the `.strd` twin of every `.work`
file (byte-identical in a unit-saved project); the tools wrote `.work`
only, so there was no stored state to reload.

**Fix.** `ot_project.py stored <project>` writes the twins; `rigproj` and
`delaytest` write them. A SAVE PROJECT on the unit does the same.

## Re-selecting an effect zeroes the bus ⚠️

**Symptom.** A rig that measures dead after ordinary panel work: no wet,
soak after soak passing because nothing is connected.

**Cause (measured).** A re-select loads the manifest defaults, and the two
knobs that connect the bus both default to 0: BusVerb's SEND (0 is
load-bearing: a non-zero default registers every idle host as a client)
and Character's RET.

**Fix.** Assert the connections over MIDI immediately before every
measurement: SEND `CC 40` per track (and, until 20 Sep 2026, RET `CC 38`
on the master's channel).

## A station "at its defaults" was running its default mode's view ✅ measured

**Symptom.** A station that documents a bit-exact passthrough at its
defaults changes the track's level (T5 −2.5 dB on the ladder).

**Cause.** `ot_project.module_defaults` applied the ModeView of the MODE
the manifest defaults select (Modulation's CHOR: MIX 64, RATE 30), so
`rigproj` and `stamp-defaults` wrote a chorus at half mix into every T5.

**Fix.** A view applies only when the MODE is explicitly given; the
manifest defaults are the stamped default. Re-stamp.

## PARSE ERROR loading a generated project ✅ measured

**Symptom.** LOAD PROJECT on a project written by our tooling stops with
"PARSE ERROR", reliably.

**Cause.** Every PART record in a bank file carries its own index in byte
8 (parts 1-4 hold 0-3, the saved mirrors 5-8 repeat 0-3). A whole-record
copy keeps the donor's index.

**Fix.** Write `p % 4` into byte 8 after any whole-record copy
(`ot_ladder.PART_INDEX_OFF`); the generator's read-back checks every
record. The other known parse error: `project.work` edited in text mode
loses its CRLF. Under the port the load completes and the firmware logs
`Couldn't read bank file '...bank01.work' ('PARSE ERROR')` to the card's
`LOG 000000.txt` (`verify_set`, `ot_emu --card-out`): a generated project
is checked before it goes near the card.

## The set went silent after a test flash: the firmware reset the project 🟡

**Symptom.** After flashing a test image whose remix omitted Character,
the set printed nothing under it and stayed silent back on the rig image.

**Measured.** The card's bank records had every part reset: FX1 id 4 with
FILTER's page-2 bytes, FX2 = the stock delay, T1/T2 no longer THRU, T8 =
FX1 NONE / FX2 COMPRESSOR (0x18, a harvested donor id on the rig → the
null stub on the master).

**Inferred.** The firmware sanitises part records whose FX ids are not in
the running image's tables and writes the .work files back. Never load
the set under a test image. Not reproduced by LOAD PROJECT under the port
(15 Sep 2026: OCTABAM88 bank B under the `bus` image, which carries none
of the station ids, kept the ids live and rewrote no file; `verify_set`
reads the card back), so the rewrite happens on another action.

**Recovery.** Regenerate from the material (`ot_project.py rigproj … +
lfo-clear … all`), copy the banks over the card's project in place, keep
the project's own `project.work` (a foreign `OS_VERSION` tag gave PARSE
ERROR, inferred from the diff). Save a copy of the card's project first.

## The master compressor collapses one channel above COMP ~40 ✅ measured

**Symptom.** Character on T8 with COMP above ~40: the right channel drops
40+ dB, L holds; scales with WDTH; only with the stations loaded.

**Cause (measured 14 Sep 2026).** Character's compressor was innocent.
Track LEVEL 0 on T4 cleared it and T4's AMP VOL 0 did not: T4's Spectrum
generated a near-full-scale DC from its state. Reproduced under `dsp_host`:
Spectrum with its instance block pre-filled with 0x400000 outputs −0.5 FS
on silence forever; filter B's two HP poles at cHP = 0 were frozen and
`hp2 = yB − h2` subtracted the stale h2 every sample. Init cleared
`$00..$17` only. The makeup then clipped DC + audio to a constant on the
channel whose offset was larger; an AC-coupled capture cannot see the DC.

**Fix.** Every persistent slot zeroed at init (Spectrum `$00..$3f`,
Modulation's LFO values, Character's counters, phase and grace);
`tools/verify/verify_dirtystate.py` (in `make verify`) renders every module
from a garbage block on silence and refuses any output above −100 dBFS.
Confirmed on the unit (image 8): bank G's master at COMP 40 / 80 / 127
reads R−L −0.4 / −0.1 / −0.6 dB (was −44 at COMP 80).

## A diagnostic image silenced every bank with stations; the port played them 🔴 open

**Symptom.** OCTABAM5 (Character 189 words shorter) played banks A, B, E
and was silent on F and G (the station layouts), DSP not hung. Image 4 and
the shipping image play G.

**Measured.** Under the port image 5 plays F and G; the stopwatch reads
its Character cheaper; no instruction runs in image 5 that image 4 did
not. The differences left are placement: Modulation moved down on both
payloads (A 0x1c1b, B 0x193c) and the build kept the stock COMB code and
dispatch on payload B (never executed under the port). Image 6 = image
5's Character plus 189 nop words (image 4's placement) plays F and G.

**Cause.** Open: something at that placement the port does not model
(the kept stock COMB on payload B, or Modulation's address). Not bisected.

**Workaround.** Pad a diagnostic module to a placement known to play.

## Sequencer stuck on step 1 at project load: an init that moved r1 ✅ measured

**Symptom.** Play sticks on step 1 on every project that loads a Spectrum
on FX1 (image 99).

**Cause (the port's last-PC ring).** The stock FX1 dispatcher keeps the
effect id in r1 across `jsr init` and indexes the proc table with it
(`P:0x4c8..0x4d7`). Spectrum's init zeroed its state through r1 and
returned with r1 = r7+24; the proc lookup read garbage and `jsr (r2)`
landed on P:0. `dsp_host` cannot see it: it calls init and proc itself.

**Fix.** Zero through r5; `tools/verify/verify_initregs.py` (in `make
check`) refuses an init that writes r1/n1/m1. Recovery: a power-cycle and
a project without the module.

## Sequencer stuck on step 1: cycle overrun or a wild value

**Symptom.** Step 1 solid and never advances, no audio.

**Cause (measured).** A core cannot finish a block: a cycle overrun (three
heavy stations beside an engine at a static 3,106 of 3,120; the counter
is a floor, the wall a cliff), or a wild stored value feeding an engine
on frame one (an old part's crossed-slot byte after a layout change).

**Fix.** Fit the layout (≤ two heavy stations per core) and stamp the
project for the current remix before playing.

## The bus return is "less rich / bit-crushed" on the unit, clean under the port — ✅ gone with the return (20 Sep 2026, images 35 → 38)

**Symptom.** With one track sending, WET 0 on both engines and RET 127 on
T8, the return is duller and grainier than the dry from a fresh start;
knob presses make it worse and it stays; STOP then PLAY resets it; RET 0
silences it. The same with every sender on either core, at any send
level. Reverb-only on one core (BusDelay off, T6/T7 sending): still
degraded. The return alone (the sender muted post-FX): still degraded, so
it is not the dry + 60-sample-late return combing at the main out. T8's
Character reads DRV/FOLD/TXTR 0. Both engines' wets sound grainy too.

**Measured elsewhere.** Under the port the same path (one sender, WET 0,
RET 127) is the aux itself at −109 dB residual, lag 60 samples
(`verify_set`). A four-minute `rig_render` with seven hot senders shows no
growth over time.

**Lead (unverified).** Every word on that path is in the shared window
and read per sample; R36's per-block writes / in-loop reads there were
dead on silicon with the emulator passing (BusDelay's RATE/DRV words).
The engines' outputs cross the same reads.

**Outcome (20 Sep 2026).** The return went: Character has no RET, the
engines publish no stage output, the hosts' print is ungated, the SEND is
allowed on T8. Each engine's wet now leaves through its host only (T1 the
repeats, T5 the tail). ✅ Image 38 on the unit: the reverb on T5 is clean
(Sam, 20 Sep 2026). The degradation was in the return path, not the
engine; which part of it (the shared-window per-sample reads, the
rotation, the station's add) was not bisected and the code is gone.

## A TIME turn on BusDelay crackles for about a second, in both directions ✅ measured, fixed (unflashed)

**Symptom (Sam, 20 Sep 2026, image 38).** TIME or FDBK moves crackle;
putting the knobs back does not clear it; re-selecting the effect does.

**Cause (measured under `dsp_host` and the port).** The glide (image 33)
stepped its Q8 state once per block, up to ~17 samples a step, and the
loop's tap, REVERSE's lag floor and GRAIN's read base were computed from
that per-block value: the read jumped by the step at every block edge, a
click every 16 samples while the step exceeded a sample (~1 s after a big
move), then a sub-sample tail for ~3 s. A revert is another glide, hence
"doesn't fix"; init starts the state at the target, hence "re-select
fixes". The FDBK crackle was the TIME glide's tail; FDBK's own glide and
PTCH moves measured clean. `tools/harness/glide_census.py` /
`port_click_census.py`.

**Fix.** The Q8 TIME ramps within the block, a sixteenth of the step per
sample; REVERSE and GRAIN re-derive their per-sample lag from it. Spikes
per mode 5,228 / 2,676 / 4,483 -> 0 / 73 / 896 (the remainder REVERSE's
uninterpolated heads repeating a sample as the ramp passes an integer, at
the level of its own segment splices).

## The RET/CRSH trap ✅ removed by design

**Symptom.** With T8's Character in the old BUS mode and knob 3 at 127,
turning SAT to TAPE made the whole mix a 4-bit crush at full scale: the
same knob was RET in BUS and CRSH elsewhere.

**Fix.** No BUS mode. From 13 to 20 Sep 2026 slot 4 was RET on every
track, live by dispatch position on the master and inert elsewhere; since
20 Sep 2026 slot 4 is empty (`---`) and the return is gone. DRV 0 skips
the saturator (bit-exact).

## An FX1 station's page 2 does not reach the DSP on a bus host ✅ fixed (image 24)

**Symptom.** Character on T1 (a THRU, FX1) made a quiet tone at idle; knob
3 at 127 gave −47 dBFS of broadband hash with the panel's SAT at BUS or
TAPE alike: the DSP on T1 was in TAPE whatever the panel said (the old bit
crusher on the input floor). T3 (STATIC) and T8 (FLEX) took a panel page-2
edit; T1 did not.

**Cause (measured 15 Sep 2026, `ot_emu --watch-mem` on T1's DSP record).**
The tempo cave (`modules/tempo-sync`, hooked in the voice-record writer
for FX2 ids 6/7) stored tempo24, the clock period, fader+1 and the note
into record halfwords 18-21 (`+0x24..+0x2a`) every frame, after the copier
had put the FX1 page-2 bytes in 18-20 and the AMP page-2 bytes in 21-23:
`0x400d7550` wrote `0x0b55` (TEMPOx24 2901) over MIX/SAT, `0x400d755e` the
period over WDTH, `0x400d7522` the fader over AMP p2's first word, 59
frames of 60. Halfwords 18-20 are `r6_FX2+$6..$8`, believed unread since
24 Aug 2026 (true of FX2 effects) — and `r6_FX1+$c..$e`, the FX1
instance's page 2. The discriminator was the host, not the machine: T2
(THRU, FX2 = SEND) kept its page 2, T1 (THRU, FX2 = BusDelay) lost it.
Every FX1 effect on a delay or reverb host, stock ones included, has run
page 2 on the tempo bytes since 24 Aug 2026.

**Fix.** The cave publishes the note only, into the low byte of BusDelay's
TIME halfword (`+0x1b`, `r6+$1` bits 8-15, masked out of the knob decode);
BusDelay reads tempo24 from stock's own record word (halfword 31, `r6+$13`,
`0x40004d6a`) and derives the period on the DSP. Under the port with the
fix, a live SAT edit on T1 (`--call 0x4003abe4,1,1 --call-at 20`) lands in
the record (`0x7f01`) and only the copier writes halfwords 18-20; 120 BPM
snaps TIME to exactly 11,025 samples (1/8) in `rig_render`. Image 24
(15 Sep 2026): the sends into the delay work on the unit.

## Static that stays after knob moves with both engines live 🔴 cause open

**Symptom (15 Sep 2026, image 26, OCTABAM89 C02).** Turning knobs on
BusDelay or BusVerb -- "ones that would tax it, like changing times" --
sometimes brings in static and crackle that stays. Triggered "pretty
reliably" with the reverb host's SEND up and both WETs up; a transport
restart clears it, after which it takes a few knob moves on either engine
to bring back. Not reproducible on demand afterwards. One
10 s capture while it was audible (`out/hw/voicing25/noise_now.wav`):
HF above 8 kHz −77 dB against −85..−91 dB after CC toggles of the delay's
WET, with no clean A/B on the same material.

**Measured under the port (ONEAUX fixture, engines warm, CC at frame
700).** A knob turn costs no block extra: the CC lands through the page-1
slew and the FX2 call is the same on the change frame (delay 3,754 →
3,754, MODE → REVRS 3,914; reverb 16,710 ± 14) for TIME / SIZE / MODE /
FRZE. The reverb host sending itself is not a loop: T5 SEND 127, both
WETs 127, T3 sending -- +0.8 dB on T5's chain output, no growth over 2,000
frames; the ColdFire delivers every track's audio block every frame.

**The same project under the port (OCTABAM89 C02, 2,400 frames, T2+T3
sending 127, T5's own SEND 127, both WETs 127, then TIME 0 → 127 on the
delay, SIZE 0 → 127 and TIME 0 → 127 on the reverb, MODE → REVRS → CLEAN
over MIDI):** every track's chain output stays off the rail with no
sample-to-sample jump above 0.25 FS; T5's print settles at −27..−30 dBFS,
T1's at −22. No reproduction (`out/crackle/c02_recipe.midi`).

**Open.** The port models no stall, so it cannot see the cycle wall,
which fits the shape: C02's layout prices ~2,950 (core 1) and ~2,994
(core 0) instructions/sample against 3,120 usable with a counter ~270 low
on the reverb, and an overrun that desynchronises the frame handshake
persists until a restart. Same family as the tick and the freeze above.
To decide: with the static going, take one station off the core (T2's
FX1 to NONE); or the burn image (`make burn`) on C02, stepping the burn
until it appears.

## A DC thump every 10.59 s at idle, from track 6 ✅ source measured

**Symptom.** Transport stopped: a thump every 10.59 s, ringing 2 s through
the return. A DC step, +0.23 FS on L, +0.46 on R, rising in two samples,
bled away by the output DC blocker over ~35 ms. On every ladder rung
including the one with no module of ours. Track LEVEL 0 on T6 removes it;
AMP VOL 0 does not.

**Source.** T6 LFO 2: destination 16 (AMP BAL), triangle, speed 18, depth
21, FREE (`ot_project.py lfo`). Zeroing the three LFO depths over CC
29/31/33 removes it; depth 64 on LFO 2 alone brings it back at −21 dBFS;
the period is 64 steps at 121 BPM with a 3/4X scale; the pulse rate
follows the LFO speed. A plain BAL move over CC 8 never pulses.

**Fix.** Every LFO depth cleared in OCTABAM87 and the ladder (`lfo-clear
all`). Open: whether a balance LFO pulses on stock 1.40C too (the pan
stage is stock; its table may sit in harvested memory); the port with a
fast LFO fixture decides it. A separate 593.5 Hz tone at −75 dBFS after
STOP on OCTABAM87 only: cause open.

## Spectrum VOWL went silent with RES up 🟡 seen once

**Measured (image 96, T3 soloed, FREQ/RES over CC, MODE set at the
panel).** VOWL at RES 100 with FREQ ≤ 96, and RES 127 at FREQ 64, output
−102 dBFS; LP/BP/HP/NTCH bounded at RES 127. `dsp_host` does not reproduce
it, and on image 97 with MODE set over CC 69 the same sweep in both knob
orders never went silent. The one difference: T3's FX1 page 2 was on
screen while the page-1 CCs were sent, MODE set at the panel (the editor's
refresher `0x40027e00` runs there and not on the CC path). A CC 35 = 100
with page 2 on screen landed on RES, not MODE (falsifying the
routed-by-displayed-page hypothesis). The two-peak VOWL it happened on is
gone (image 98: a three-formant resonator bank, bounded at RES 127). If
it recurs at the panel, capture before touching anything.

## A one-sample tick on an exact 2048-sample grid at idle 🔴 cause open

**Symptom.** Sequencer stopped, nothing playing: a one-sample downward
spike, common-mode on L and R, −45 dBFS peak, at irregular intervals of a
few hundred ms; occasionally its reverb tail lifts the floor to ~−90 dB
for a second. Present with the reverb's track muted.

**Measured (image 93, two 30 s captures).** 23 / 24 ticks in 30 s on a
grid of 2048.050 / 2048.049 samples (fit residual 0.29 / 0.25 samples
over 631 periods). The +24 ppm offset says the unit generates it (a
capture dropout lands on exactly 2048.000). Not an overrun (locked to a
buffer boundary to a third of a sample). Intermittent at the boundary:
96 % of wraps clean, 4 % spike, gaps 8, 10, 18, 21, 29, 31, 47 wraps.

**Ruled out.** The capture rig; Character (removing it removed the whole
wet bus's path to the outputs, not a source); the stored project (a
reload measured −104.6 dBFS with zero ticks against −73.9 and 23 before:
the tick needs a live edit the card does not hold); the input path;
BusVerb page 1 (every knob to extremes over verified CCs: zero ticks).
Page 2 was untested (the CC PAGE 2 fault) and is not cleared.

**Candidates for 2048.** BusVerb's diffusers, allpasses, shimmer and
pre-delay are 2048-word modulo buffers (`m5 = $7ff`); Modulation's
`buffer_words=2048`; the firmware's PCM-pool block (`0x800` in the
recorder's block table at `0x80003c20`). The live state that produced it
is lost. When bisecting by hand, take slots to a stock effect, not NONE
(id 0 is SEND). `tools/rec` (built from `tools/hw/rec.swift`) must be the HAL recorder.

## Sequencer stuck on step 1 with every effect turned off: id 0 is SEND

**Symptom (image 85B, the first rig-burn image).** Step 1 solid with every
FX1 set to NONE and every FX2 set to SEND; the plain image played.

**Cause.** Id 0 is aliased to SEND and the FX1 chooser's NONE is id 0, so
SEND's proc runs on every FX1 slot set to NONE with r6 on that slot's
page, whose bytes are whatever the last effect left. The burn knob read a
stale slot-1 byte on four extra slots per core. The emulator never
instantiates an FX1-NONE slot.

**Fix.** Anything in SEND that reads a knob and can cost cycles or write
the bus gates on the slot being FX2 (`X:$213` base ≥ 0x4000, tested per
call); the burn does (`dsp/burn_send.inc`, `verify_burn.py` check 5).
SEND's SEND-knob read had no such gate until image 48: an FX1-NONE slot
with a stale SEND byte did register and send on the unit (image 46: audio
in the bus with every SEND at 0). X:$213 is the last init's pointer at
proc time (`dsp_host -allocproc`), so since image 48 SEND keys the refusal
on r7 instead (0x6100/0x6400/0x6700/0x6a00 are the FX1 slots, measured
under the port) and returns before touching any state; the entry on the
THRU-host wash has the rest.

**Second instance (image 32B, 16 Sep 2026): step 1 forever on two projects
with every stored page byte zero.** Under the port (`--dsp-pcwatch` on the
burn's `do`, core 0) the word the burn read at `x:(r6+$1)` was `0x378f00`
with every byte 0 and `0x69f400` with one track's byte at 100 — the same
word on every SEND track, and the same with SEND cloned from DARK REV
instead of FILTER. ❌ "the firmware computes page-1 slot 1's word for this
effect" (16 Sep 2026): a port page dump on 22 Sep 2026 (`--dsp-peek
core:X:0x2c0,384` with every page-1 byte of Spectrum, Character and
Modulation stamped distinct) shows every slot raw, knob << 16 with the
companion in bits 8–15; a PC watch on a displaced load samples `a` before
the load lands, so `0x378f00` was the previous instruction's `a`, not the
word. 7,111 loop iterations at "0" and the frame never finished; the
loop count's cause is open. The
burn now reads page-2 slot 6 (`$c`'s knob field, CC 62), the delivery
`verify_set` proves raw for every track on a real project; unflashed. The
stamper writes SEND's defaults into every id-0 slot (both FX1 and FX2)
since the same day, which also closes the phantom-sender claim above for a
stamped project.

## Line-F exception on [PROJ]: a cave pinned in OS .bss

**Symptom.** PROJECT throws an exception and wedges.

**Cause (measured, tag 91).** A cave pinned at `0x40108800`, inside the OS
image's last ~30 KB: a zero run at rest that is the PROJECT subsystem's
RAM.

**Fix.** `build_bus.SAFE_CAVE_CEIL` (0x400d8000) refuses any cave above
the decoded free region.

## Garbled audio straight after an OS upgrade: the warm-up tag

**Symptom.** Right after OS UPGRADE, audio is garbled (worse for the
delay). Not present after a reboot.

**Cause (inferred).** An OS upgrade rewrites program memory but does not
clear DSP state RAM; an engine skips warm-up when its tagged counter holds
a valid tag at full count (BusVerb `$2c0000` at `r7+$82`, BusDelay
`$2e0000`, Nimbus `$2d0000`).

**Fix.** Power-cycle after every upgrade before judging anything.

## A module mistuned on tracks 1-4 only: an absolute stock-table address ✅ measured

**Symptom.** An effect behaves differently on tracks 1-4 than on 5-8
(Bryan T's LOFI2 low-pass three times too bright on 1-4).

**Cause.** The two payloads are linked separately: the 6,305-word curve
bank is `X:0x438` in A and `X:0x42b` in B; the Y tables shift by 16. A
module is one source assembled into both, so an absolute stock-table
address is right on A (tracks 5-8) and 13 words off on B. The
single-payload audition render dumps payload A.

**Fix.** Never write a stock X or Y table address as a bare literal;
declare it so the build rewrites it per payload, or read through a
build-supplied base. Audit any stock-table read on both payloads with
`rig_render.py`.

## Self-oscillating squeal: a page-2 value out of range, or deep overrun

**Cause.** (1) A wild page-2 value (BusVerb DIFF stamped to 127
self-oscillates the tank: the +0x325/+0x331 stamp-offset bug, which is
also what flash 4's "the stock DELAY wedges the unit on part load" was;
T4's DELAY row landed on T5's BusVerb). (2) Deep cycle overrun (the
high-pitch squeal signature, `docs/firmware/CHIP.md`).

**Fix.** Re-stamp the project (1); fit the layout (2).

## "Z" screen / won't boot: corrupt OS

**Fix.** Startup Menu recovery: power off; hold [FUNC], power on; [TRIG 3]
MIDI UPGRADE; send a good `.syx` (`make midi-flash PORT=A SYX=…`, or a
SysEx app). `docs/remixer/FLASHING.md` §1.

## Cross-core bus glitch: the accumulators' race ✅ mechanism measured, fixed

**Symptom.** A tear, stutter or hash on wet audio that crosses cores,
often smeared into a reverb tail.

**Cause.** Core 0's housekeeping flips the rotation word in the middle of
core 1's frame and every client read the word directly, so a frame's
sends split across two buffers (measured under the port,
`docs/history/COLDFIRE_PORT.md` O12; `docs/effects/XBUS.md`).

**Fix.** Four ACC buffers; one rotation tracker per core (`build_bus.py`
ROTLATCH, payload B). No local test is evidence here: `dsp_host` runs the
cores lock-step or under a guessed interleave.

## CONTROL menu shows its stock six rows though the image carries eight 🔴

**Seen (tag 16).** The rows a module appended (the bus screen) were not
there; the image held row count 8 at 0x400cbd54 and the repointed row
pointer.

**Cause.** Unknown; the CONTROL rows are read from somewhere the patch
does not reach. The module is out of the tree; navigate to CONTROL in the
ColdFire emulator's own menu before any flash that appends rows again.

## The one-aux return never reached T8 ✅ measured under the port

**Symptom (flash 6).** Sending (the AUX knob then) produced wet out of T1 and T5, the
engines' own hosts; nothing arrived at T8.

**Cause.** The station pinned the return to track 8 by testing `r7 &
0xff00` against `$6700/$6800`, the harness's two-per-track model. The
stock dispatcher bumps r7 three times per track (FX1, FX2, an
unconditional third at P:0x51e), so track 8's FX1 runs with r7 = `$6a00`;
the pin never matched, the RET level was cleared, the station stamped
nothing. `verify_onebus` was green on exactly this property.

**Fix.** Pin `$6a00/$6b00`; the harness's r7 model corrected. Confirmed on
flash 7.

## The port reports a wrong bank/pattern for an image that detours `0x40087d44`: the instrument

**Symptom.** Under `ot_emu --sequencer`, an image hooking the engine's
BANK= store at `0x40087d44` plays bank 0 pattern 0 after LOAD PROJECT
(`saved_bank: -1`).

**Cause.** `rtos.cpp` learns the saved bank from a write watch on
`BANK_PTR` (`0x46c82456`) that accepted only writes whose PC is the stock
store; a detour makes the store from a cave's PC, the watch never fires,
and the port's transport-start re-select picks bank 0. A 38-site bisect,
a "narrowed to `unpack`" reading and a PR to midisc's author (withdrawn)
were built on it.

**Fix.** The watch follows a `jsr (abs).l` at the site and accepts the
store from the detour's own code; `--bank N` overrides. A port watch keyed
on a stock PC is blind to any module that detours that PC.

## A send that ignores its knob, a track loud into the bus at SEND 0, different per track 🟡 two causes, both project data

**Symptom (16 Sep 2026, image 32, OCTABAM89 and its no-effects copy).**
T5 and T7 loud through BusDelay with SEND 0 and no effects; T3 through it
quietly; T2 leaking with a dead knob; T4/T6 as designed. CLEAR PATTERN on
the unit made it behave.

**Cause 1: stale parameter locks.** A pattern's trigs carry one lock byte
per parameter slot (`tools/hw/ot_bank.py`: 64 steps × 32 slots per track
record; FX1 = slots 18–23, FX2 = 24–29; `0xff` = none). Every slot move
since 7 Sep left locks pointing at whatever knob now sits there; a lock
overrides the knob on its trig. OCTABAM89 carried 962 FX1 and 6 FX2 lock
bytes, mostly a knob-C sweep on T3/T4 driving Spectrum's ENV, and one on
T5's FX2 knob A (the send). `ot_bank.py strip` clears a page's locks in
every pattern; the stamper never touched patterns.

**Cause 2 (🟡 inferred from the symptom set): an FX2 stored as id 0.** A
fresh or cleared FX2 slot is id 0, which the image aliases to SEND; the
firmware delivers no page for an effect it does not know, so SEND reads
whatever the DSP page word holds — a level the knob cannot reach, and
different on each track. `stamp-defaults` and `clean` now store SEND (id
9) with a zero page in every empty FX2 slot; a project of ours has no id-0
FX2 slot left. Not measured under the port (its fixture had no audio on
those tracks); the falsifier is a stamped project that still leaks.


## Freeze without an exception screen as ColdFire delay-routine work grows 🟡 his unit, open

**Symptom.** Tape Echo (PR #357, Jannik Aßfalg / repeat98: the effect runs
on the ColdFire inside the stock delay's frame routine, `COLDFIRE_DELAY.md`)
freezes his unit as instances are added, always during control edits, with
no exception screen: OCTACLID3 on a TIME edit with three instances,
OCTACLID4 while editing the sixth, the PR's candidate at seven. Earlier
images froze on a second instance's TIME change and on loading three.

**What the counts say.** Per eight-track 16-sample frame under the port's
instruction meter: stock DELAY 7,628; eight tape instances settled ~23,000;
all controls moving up to 32,355. Per instance that is ~1,900 settled and
~3,100 moving. The frame period is 363 µs, ~95,800 CPU cycles at 264 MHz,
shared with everything else the ColdFire runs. The meter prices an
uncached SDRAM ring access at one cycle.

**Cause (🟡 inferred).** The routine's per-frame deadline, not memory: the
state is a fixed 1,600 B, the rings exist for all eight tracks whatever
FX2 holds, nothing is allocated. Stock spins at `0x40003780` on the DMA
status word `0xfc0450be` before the commit, which is a silent hang when a
frame overruns, where a bad pointer on this chip throws a vector screen.
What would falsify it: a freeze at the same instance count with the
per-frame work halved, or a freeze with settled controls.

**Fix.** Open. The ColdFire's per-frame budget for this routine is not
measured; his freezes bracket it. Any reverb or granular on the ColdFire
prices above the seven-instance point (BusVerb ~18,000 DSP cycles per
frame, four-grain GRAIN ~28,400, each in the cheaper unit).

## Bursts of garbage on the reverb host's frame while the delay runs on core 1 🔴 cause open

**Symptom (Sam, 23 Sep 2026, image 58 onward; heard as "intermittent
clicks" since image 26).** With the rig hosted (BusDelay on T1, BusVerb on
T5), a sample playing on T1 and nothing sent, T5's print carries 24-40
samples of near-full-scale garbage, 4-16 times in two minutes, on an
otherwise digitally silent frame. `tools/rec` on the MicroBook with T1 BAL
hard left and T5 hard right, and a second-difference census of the capture
(`tools/harness/burst_census.py`, events absent one pattern period either
side; it reads input 3 as R and input 4 as L), is the instrument; the ear correlated them with knob moves, which
was wrong.

**Measured, one image per row, same setup, two minutes each:**

| image | what | bursts on T5 |
|---|---|---|
| stock 1.40C | | 0 |
| 69 | SEND + the stations, no engines, no caves | 0 |
| 78 | + BusVerb present, unhosted | 0 |
| 84 | the rig, the delay returning at its first instruction | 0 |
| 86 (WOW 20) | the rig, the delay in full but never reading the aux or writing the chain | 0 |
| 89 | only the chain write removed / only the aux read removed | 4 / 1 |
| 85 | both delay lines in core 1's private memory | 8 |
| 87 | the chain moved from Y:$9d8 to $a58 | 6 |
| 90 | the aux read and the chain write as two 16-word bursts per block through stock's X scratch | 3 |
| 58-83 | the rig; the reverb stubbed, on id 0x1e, cloned from SPRING REV, its private Y words in r7, its m0..m6 preserved, the live stamp a counter, the rotation read twice, the levels ramped | 4-16 |

**What those rows said (retracted by image 91 below).** The delay's accesses from core 1 into core 0's half of
the shared RAM (the aux read at 0x36901.., the chain write at 0x360d8..)
put the garbage into T5's frame; nothing the reverb does, and nothing on
the ColdFire side, changes it. The SEND clients make the same per-sample
read and write into the same aux buffers and are clean (69, 78). Position
within the block (per sample or one burst), the address, and the delay's
own line traffic in its own half (85, 86) do not matter. The port never
reproduces any of it: it runs the cores in lock step over one shared array.

**Every zero in that table is a two-minute take.** At the rate image 91
measured (about one burst per two minutes), a two-minute take reads 0 by
chance about 37% of the time, stock 1.40C included. None of the zeros
above separates a cause.

**Image 91 (23 Sep 2026, branch `diag91`, a new project, 120 BPM, 16
steps, T1 trigs on 1/5/9/13, six minutes each).** WOW/16 selected a
variant of the delay's two per-sample shared accesses:

| take | the delay's aux read / chain write | bursts on T5 |
|---|---|---|
| 1 | as shipped | 3 |
| 2 | read from the write buffer / written where the reverb never reads | 0 |
| 2b | the same as take 2 | 2 |
| 5 | both to core-private Y:$a60.., bus gain 0: no per-sample shared access | 4 |
| 7 | as shipped, T1's trigs on 2/6/10/14 | 3 |

Take 5 retracts the location above: with no per-sample shared access from
the delay, the bursts continue at the same rate. 9 of 12 bursts start 14-18 ms
after the loud transient in T1's sample (repeating every 500 ms), 2 at
-0.8 ms, 1 at +186 ms; with T1's trigs moved 125 ms against the
beat (take 7) they stayed at that phase against T1's audio, so they follow
T1's trigs or T1's audio, not the beat. Where that transient sits against
the trig is not known (it depends on the sample). Bursts are 23-53 samples.

**24 Sep 2026: bisected on the unit** (a new project per image, the same
setup; T1 on input 3 and T5 on input 4 this time; 6-minute takes unless
marked, 12-minute takes marked 12). Sam: stock 1.40C does not burst.

| image / take | what | bursts on T5 |
|---|---|---|
| 91 take 8 | T1 AMP VOL 0, trigs running | 0 |
| 69 | SEND + stations, no engines (FX1 NONE, T1-7 SEND, T8 DELAY) | 0 |
| 91 take 10 | T5 = SEND: the delay on T1, no reverb | 3 |
| 91 take 11 | T1 = SEND: the reverb on T5, no delay | 0 |
| 91 take 14 | no delay; SEND on T2-4 burning ~300 cycles/sample each | 0 |
| 92 | the delay's write-back of T1's frame moved to X:$20.. | 4 |
| 93 (WOW cut 3) | the delay stops after its warm-up and live stamp | 1 |
| 93 (WOW cut 1) | the delay stops after its preamble and role lock | 5 |
| 94 | no role lock, the delay in full | 7 (12) |
| 95 | the delay's DSP proc returns at its first instruction; ColdFire side of id 6 unchanged | 0 (12) |
| 96 (WOW stop 3) | the delay stops after its preamble (host check, frame offset, rotation tracker); no shared write | 0 (12) |
| 97 | 94 with no absolute-address store from core 1 into the shared window | 4 (12) |
| 98 | 97 with no live stamp and no warm-up `y:$981` store: no word written by both cores | 2 (8.4, capture dropped) |
| 99 | every bus word in core 1's half (`XBUS_BASE` 3c000), both delay lines private 16K: core 1 never writes core 0's half | 1 (12) |

At the bursting rate (about 3.5 per six minutes) a six-minute 0 occurs by
chance 5-9% of the time and a twelve-minute 0 about 0.1%. Take 8 is read
as one of the chance zeros: nothing the delay runs before its sample loop
touches T1's audio, and 93/94 burst without it.

**What that leaves.** The bursts need the delay's DSP code running on T1
past its preamble (95 and 96 against every other delay image). Ruled out
on the unit: the ColdFire side of id 6 (descriptor, page-2 delivery, CC
PAGE 2, MODE DEFAULTS, RIG HOSTS; TEMPO SYNC by image 70's two-minute
capture, 10 bursts), CPU load on core 1, the reverb, the frame write-back,
the role lock alone, absolute-address stores, a word written by both
cores, and which half of the shared window the bus scratch sits in.

**Burst content.** 38 bursts from ten takes: two waveforms repeat with
|corr| > 0.97 across images 91-94 and both days (7 and 6 copies), plus
pairs, so the garbage comes from a fixed source. They do not match T1's
recorded audio, T1's sample file (`Acdrum.wav`, both channels,
interleaved, every second sample) or any window of the DSP payloads' P/X/Y
data (best |corr| 0.70 each, not a match). The codec's filtering smears a
broadband burst, so a raw-data search is weak evidence either way.

**Open.** Which part of the delay's per-block decodes or sample loop
(the aux read, the chain write, the per-block bus reads, the line work)
the bursts need. Branches: `diag91`..`diag98`, `core1scratch99`,
`nolock94`, `fix97`; captures in `out/hw/v9*.wav` (machine-local). The
record's "dead words at 0x360d3-5" (send_client.asm) are unexplained.

**24 Sep 2026, the takes re-read and three zero-flash takes (image 99 on
the card, census with the aligned-copy check, `tools/harness/burst_census.py`).**
The event detector had only looked at the channel that crossed 0.35 FS.
Aligning the OTHER channel against its own copy one or two trigs earlier
(the audio repeats every trig; corr 0.99-1.00) shows T1's print deviating
in the SAME 16-sample block in 29 of 32 bursts across images 91-99, by
0.03-0.35 FS, below the threshold. The burst on the other side is one
block of broadband words that clip (-1.00 twice in one burst), near full
scale, while that channel is otherwise at -64 dBFS rms. The same T1 audio
instant gives the same burst waveform every time (12 copies of one
cluster across 91, 92, 93, 94, 99), so the content is a function of T1's
audio. Two earlier readings did not survive: "the T1 block is
sign-flipped" (the swap take put deviations of the same sign as T1's
audio) and "T1's gain/pan are torn in the 64-word block core 0 hands core 1
at X:0x30004" (under the port that block is input audio A-D x 16 samples
for THRU machines; a STATIC T1 does not pass through it). The AMP VOL 0
zero of take 8 was a true zero, not a chance one.

| take (12 min each) | change | bursts | T1's side deviates |
|---|---|---|---|
| v99_23_swap | T1 BAL hard right, T5 hard left | 4, on the side opposite T1 | 3 of 4 (one alignment poor) |
| v99_24_t5lvl0 | + T5 LEVEL 0 | 6, same side | 5 of 6 |
| v99_25_cue | CUE L/R recorded instead of MAIN, T1 cued | 5, same side | 4 of 5 |

So: the junk is in T1's stereo block, on both channels of it, full scale
on the side T1 is panned away from; it is there before the main mix (the
CUE mix shows it) and it is not T5's block (LEVEL 0 changes nothing).
With the 23 Sep bisect (the lock-only delay that writes no audio bursts,
the preamble-only delay does not) it is not the delay's audio output
either. The dispatcher re-sets r0, r1, n1, r3, x1 and y1 before the
read-back packer (`P:0x303-0x35e` on B), so a data-register left by proc
is not a path; m0-m6 were saved on image 83 and it still burst. Where
between T1's audio block after proc and the read-back words at
`X:0x2600` the junk appears is the open question. The pan swap does NOT
discriminate T1's block from T5's (both put the burst opposite T1); T5
LEVEL 0 does. The CUE outs carry nothing until the track is cued.
`tools/rec` needs the device name as its third argument (without it it
looks for EVO4 and exits at once).
