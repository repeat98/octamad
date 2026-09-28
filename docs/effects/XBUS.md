# The cross-core bus: one aux, delay into reverb, each wet on its host

The architecture record for the bus. The development logs, `XBUS_LOG.md`
(the cross-core race) and `BUS.md` (the per-bank two-bus design this
replaced, and the one-aux build of 7 Sep 2026), are in git history under
`docs/history/` (`git show 3ceba41:docs/history/<name>`). ✅ measured on the unit, 🟡 measured under the port or the harness,
❓ inferred.

## The shape

```
every track ──SEND──▶ [aux accumulator] ──▶ BusDelay (T1 FX2) ──chain──▶ BusVerb (T5 FX2)
  (SEND's one knob; the hosts' too)         stage 1: T1 prints           stage 2: T5 prints
                                            dry + wet × WET              dry + wet × WET

CORE 0 (payload A)  tracks 5–8   BusVerb   Y:0x4000–0xBFFF (private) + Y:0x30000–0x37FFF (shared lo) = 65,536 words = 1.49 s
CORE 1 (payload B)  tracks 1–4   BusDelay  Y:0x4000–0xBFFF (private) + Y:0x38000–0x3FFFF (shared hi) = 65,536 words = 1.49 s
```

- ✅ Payload A / core 0 serves tracks 5–8, payload B / core 1 tracks 1–4
  (marker flash, 10 Aug 2026). Since 22 Sep 2026 (`Remix.locked`, image
  51) each engine runs on its core's position 0 only — the reverb on T5,
  the delay on T1 — and is an exact dry pass on any other track (the
  HOSTGUARD body at proc entry: `r7 == 0x6200`); `stamp-defaults` warns
  about an engine anywhere else. Image 52 takes both engines out of the
  FX2 chooser (SEND is its only row) and RIG HOSTS gives every new
  project T1 = BusDelay, T5 = BusVerb from the part-defaults initialiser.
  Until 22 Sep 2026 the reverb ran on any of T5–8 and the delay on any
  of T1–4.
- Under `SPEC=1` each server exists in one payload and can only be hosted
  on its own core's bank; any track can send into it. The absent server's
  dispatch id is aliased to the SEND client on the other payload, so a
  wrong menu pick runs a send.
- A server's memory is its core's two private FX2 slots plus half of the
  64K shared window `0x30000–0x3FFFF`, where P, X and Y alias ✅. The
  stock allocator's slot table (`X:0x255`, both payloads of the raw image)
  already hands the low half to core 0 and the high half to core 1
  (`docs/firmware/DSP.md` §7).
- Total bus latency is 3 blocks since 22 Sep 2026: 48 samples on hardware,
  45 in the harness's 15-frame blocks (2 blocks from 17 Aug to 21 Sep;
  `docs/history/TESTPASS.md`).

## The two sends (25 Sep 2026; one aux bus 7–25 Sep, ✅ flash 7)

- `SEND` has two knobs: `DEL` (slot 0) into the aux accumulator
  `Y:0x901..0x980`, the delay's only input, and `REV` (slot 1) into the REV
  accumulator `Y:0xa58..0xad7` (spelled `$9d8 + $80`), the reverb's. Each
  registers in its own per-buffer count (`0x9c7..0x9ce` aux,
  `0x983..0x98a` REV) only while its knob is nonzero; same 3-bit headroom
  and 1/√N auto-gain on both. The housekeeper clears both accumulators and
  both counts together. Each engine carries `SEND` at slot 0: T1's goes
  into the delay, T5's into the reverb (flagged at `0x981`, counted on the
  REV bus). Stations carry no sends.
- The chain: the delay stamps `Y:0x9c3` every block it runs (after its
  warm-up); the reverb reads it, clear-on-read, one writer one reader,
  three blocks of grace. The delay writes `wet × DLY`, mono, into the chain
  buffer `Y:0x9d8..0xa57` (eight rotations × 16 words, stored, never
  cleared). The reverb's input is the REV accumulator × 1/√N plus the chain
  × 1/8 (the loop's `asl #3` lands the chain word untouched) while the
  delay is live, × 0 otherwise. DLY is the reverb's page-2 slot 10; the
  reverb publishes its knob field to `Y:0x982` every block (one writer,
  like `0x981`) and the delay glides it as it glides WET.
- So: a DEL-only send reaches the reverb only as repeats × DLY; a REV-only
  send never reaches the delay; DLY 0 = the two engines in parallel
  (`verify_onebus` measures each, bit for bit where it can). Until 25 Sep
  2026 the chain carried `in + wet × DLY` (the send passing through the
  delay at unity) and the reverb read the chain or, with no delay, the aux.
- WET on each engine (slot 5): each host prints `wet × WET` under its own
  dry: T1 (the delay host) the repeats, T5 (the reverb host) the tail.
  Until 15 Sep 2026 each stage crossfaded (`in × (1 − MIX) + wet × MIX`),
  so the reverb's MIX faded the delay out.
- Where the wet comes out, 20 Sep 2026: on the hosts, and nowhere else.
  From 7 to 20 Sep 2026 each stage also published its output stereo, four
  deep (`0x9da` reverb, `0xa5a` delay), Character's `RET` on track 8 (by
  dispatch position, payload A position 3, `r7 $6a00`) returned the last
  live stage's output and stamped both hosts quiet (`0x9d8/0x9d9`). ✅
  Flash 7 (OCTABAM21) measured all of that on the unit; on image 35 the
  return was "less rich / bit-crushed" on the unit and clean under the port
  (`FAILURE_MODES.md`), and the mechanism went. The hosts add the wet in
  place after their own send tap, so a host never sends its own wet.
- The send is refused on track 8: `SEND` at core 0's position 3 (`r7
  $6b00` on payload A) contributes and registers nothing. T8 is the
  master: with MASTER TRACK on its input is the mix, the hosts' wet
  included, and a send from it would put that wet back into the bus (the
  master loop that silenced the unit on 6 Sep 2026, `FAILURE_MODES.md`).
  Payload B's position 3 (T4) sends normally; the payload is told apart by
  SEND's `$30000` base literal, rewritten to `$38000` on B (`YBase.XBUS`).
- Return balance on material (7 Sep, `out/rig/oneaux/`, the MIX-crossfade
  stage of the time; WET adds since 15 Sep 2026 and the wet is ×2 since 16
  Sep): drum loop −25.1 dB rms with the reverb at MIX 0 and −26.8 at MIX
  127; pad −31.4 / −32.8; no makeup. (The "wet ~25 dB under the repeats" reading from the 438 Hz gate
  tone was retracted the same day.)

Slots (stamp every project before play, `tools/hw/ot_project.py
stamp-defaults <project> <remix> --all`; without `--all` the stamper
touches only the ids a station replaced):

| | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| SEND | DEL | REV | | | | | | | | | | |
| BusVerb | DEL | REV | SIZE | SHMR | SHFT | WET | MODE | TONE | DIFF | GATE | DLY | TIME |
| BusDelay | DEL | REV | FDBK | TONE | PING | WET | MODE | SCTR | DENS | SIZE | PTCH | TIME |

Since 26 Sep 2026 the hosts carry SEND's two knobs on slots 0/1 and draw
nothing else on their pages (the remix's `host_slots`); every other engine
knob is on the TEMPO window. T1's DEL feeds the delay (its old SEND) and its
REV the reverb's REV accumulator; T5's DEL feeds the delay's aux and its
REV the reverb (its old SEND, slot 0 until then). TIME moved to page-2
slot 11 (`$e` bits 8-15) on both; WOW left BusDelay. A part saved before
reads its old TIME byte as REV and its old slot-11 byte (WOW, or 0) as
TIME: stamp before play (`stamp-defaults <project> bamsep26 --all
--keep-mode`). Each host's send is tapped from its dry before the engine,
so neither reaches its own wet (`verify_onebus`: T5's DEL and T1's REV
land bit-identically to a SEND track's on the same core).
| Character | DRV | FOLD | WDTH | COMP | TONE | MIX | SAT | — | — | — | — | — |

## What a send is

A block with a trig on the track is dispatched as two calls: a=0 for the
frames before the trig (`r0 = 0`, `n7 = split`) and a=1 for the rest
(`r0 = 2 x split`, `n7 = 16 - split`); an unsplit block is one a=1 call
at `r0 = 0`. Every bus participant takes its frame offset from `r0`
(21 Sep 2026); until then the first call stashed a flag and the split in
its block for the second, which is the suspected cause of the trig-host
wash (`docs/remixer/FAILURE_MODES.md`).

A track on SEND runs a client that, each block, adds its level-scaled
audio into the current write accumulator and registers in the client
count. Servers consume the summed previous block. Under the two-bus layout
(until 7 Sep 2026) the client had two knobs, `x:(r6+0)` →DELAY and
`x:(r6+1)` →REVERB; driving the wrong one renders silence.

## The accumulators: eight rotating buffers (22 Sep 2026; four from 17 Aug)

The bus keeps eight accumulator buffers and eight chain buffers, rotated
once per block; a server reads three buffers back from the write, and the
housekeeper clears the buffer two on from the one it flips to:

- A buffer is written at block n, read at n+3, cleared at n+6. A client
  whose label is one off in either direction writes n±1: never the buffer
  being cleared (n+2), never one being read (n−3..n−1); a reader one off
  reads n−4..n−2, never one being written. The margin is a whole block on
  each side, so no cross-core phase can tear a buffer.
- Eight because the count is a power of two: rotation `+16 & $70`, read
  offset `+80 & $70` (five on == three back), clear target `+32 & $70`; the
  mask sanitises boot garbage.
- Read-three-back costs a third block of latency (48 samples, 1.1 ms;
  the chain adds three more through a live delay).
- Both directions ride the same rotation (core 1 reading core 0's clears;
  core 1 writing into core 0's accumulator).

Bus scratch, `Y:0x900..` in core 0's half of the shared window
(`modules/send/send_client.asm` is the map): `0x900` rotation,
`0x901..0x980` aux accumulator, `0x981` BusVerb host's SEND field,
`0x9c1/0x9c2` role locks, `0x9c3` the delay's liveness stamp,
`0x9c7..0x9ce` aux send count per buffer, `0x9d8..0xa57`
the chain buffer. Role locks make the first instance of a server the only
one: a second instance returns as a passthrough, so a server's cycle cost
is charged once per bank.

## Housekeeping and the rotation

Housekeeping (flip the rotation, clear buffers) is gated to payload A;
every bus participant carries the block, and an election makes the
first-dispatched core-0 instance (position 0 = track 5) run it.

- Core 0's clients read the rotation after their own housekeeper flipped
  it. Core 1's clients never label a block from it: each counts its own
  blocks from a seed read at init and, once a block, checks the count
  against the rotation R (`build_bus.py` ROTLATCH, 22 Sep 2026). A
  difference of one either way is kept (the seed was read before or after
  a flip); two or more means lost blocks or boot garbage, and the count
  snaps to R. A count cannot flap with the flip's phase, and a label one
  off in either direction is inside the eight buffers' margin. 9 Sep to
  21 Sep 2026 one tracker per core followed R, advancing at position 0
  and keeping `T == R + 1` as the pre-flip phase, which could not tell a
  genuine lead of one from it; images 40–47's washes were that lead. A
  label from two shared words (the rotation and a word every core-0
  client stores at the end of its proc) was tried first on 22 Sep 2026:
  the pair reads the same before a block's flip and after its last
  client, so a late reader labels one ahead; the port's two-core gate
  showed it (four layouts differing from the one-core control).
- The housekeeper clears the buffer two on from the one it flips to.

## An FX1 slot is not a client (21 Sep 2026)

Id 0 is aliased to SEND and the FX1 chooser's NONE is id 0, so SEND's proc
runs on every FX1 slot with no effect, at that slot's r7. ✅ Measured under
the port on Sam's project (bank 1, T1/T5/T6/T8 FX1 = NONE; `--dsp-pcwatch`
on the tracker's store): core 1 ran the SEND client eight times a frame,
at 0x6100 0x6200 0x6400 0x6500 0x6700 0x6800 0x6a00 0x6b00 in that order
— the FX1 slots are 0x6100/0x6400/0x6700/0x6a00, the FX2 slots
0x6200/0x6500/0x6800/0x6b00 (three r7 bumps per track). Two consequences,
both on images up to 47:

- The FX1 call registered and sent from whatever byte its page held: the
  bleed into the bus with every SEND at 0 (image 46, on the unit). The
  stamper had been zeroing id-0 slots to hide it since 16 Sep 2026.
- On core 1 the 0x6100 call ran the tracker's compare BEFORE position 0's
  advance. With the flip landing before that call, it snapped T to R, the
  0x6200 call then advanced to R + 1, and every later check read
  `T == R + 1` as the legitimate pre-flip phase: one step ahead for good,
  which is the buffer core 0 clears. The port never shows it: its flip
  lands late in core 1's frame (between 0x6800 and 0x6a00 in every frame
  watched), so 0x6100 always compared equal. On the unit the stamp probe
  (image 47, a marker tone whenever a client's last stamp was gone) sounded
  on every block of plain play: 🟡 the lead of one is measured; that the
  0x6100 call is its cause is inferred from the order above and the flip
  phase, which nothing local can see. What would falsify it: image 48 (the
  gate below) still washing on a THRU host past position 0 with a trig on
  every step, or still bleeding with every SEND at 0.

Since image 48 SEND returns at once on an FX1 r7 (four compares at proc
entry, before any state is touched): no registration, no write, no
tracker call. Image 48 still needed position 0's FX2 to be a client for
the core's advance; image 49's per-client count (above) needs no
advance and no position, so T1's FX2 may be anything.

Images 44–46 carried a self-check instead (a stamp per client per buffer,
a hold flag, position 0 skipping one advance): 44 and 45 wedged on the
first play (a never-run displaced Y store, then an unmasked slot read into
a wild Y address), 46 played with static and the wash. With the lead
permanent, the hold fired every frame and fought the snap. Removed in 48;
the tracker body is image 43's.

## Auto-gain

Every writer contributes with 3 bits of headroom (`asr #3`; eight
full-scale clients sum to 1.0) and registers in the per-block count; the
server multiplies the sum by 1/√N from a reciprocal table and shifts back.
The law was 1/N until 17 Aug 2026 (R27): uncorrelated tracks sum as √N,
so 1/N over-corrected by 3 dB per doubling (`modules/busverb/
reverb_server.asm` "THE LAW IS 1/sqrt(N)"; `docs/history/CAPTURE_18AUG.md`
capture E: three senders, two 10–15 dB quieter, dropped the wet 4.8 dB
against 1/N's predicted −9.5). The "1 through 7 senders render identically"
measurement fed the same tone to every sender, the one case where 1/N and
1/√N agree. Registration is gated on the send knob: a client that
registers and contributes nothing dilutes every real sender by
√(N/(N+1)): −3.0 dB with one sender (the −6.02 dB measured on 17 Aug 2026
was under 1/N). Every writer registers, the cross-core one
included.

## The three cross-core defects

Each found on hardware, each visible only once the previous one was fixed;
all three closed on the unit (sweep of core-1 tracks × delay modes):

| # | defect | fix |
|---|---|---|
| 1 | clear-vs-read: core 0 zeroing a buffer core 1 was still reading; +18 to +31 dB of broadband hash on the bus path | four buffers, read two back |
| 2 | the rotation read: each client read the shared rotation at its own dispatch time; block-rate amplitude jitter | per-core rotation tracking |
| 3 | clear-vs-write: core 0's clear racing core 1's writers | clear the next-block buffer |

Plus the unseeded rotation tracking above. The diagnostic that isolated
them: change what runs on track 5 (the housekeeper), which moves the flip
in time and nothing else.

## Standing caveats

- 🟡 The fix assumes the cores are rate-locked (same sample clock, constant
  phase offset); drift would show as a slow return of the artifact over
  minutes.
- The artifacts relocate: one (core-1 track, delay mode) pairing is bad at
  a time and moves with the mode or core 0's load; any "fixed" claim needs
  a track × mode sweep.
- `dsp_host` runs both cores since 7 Sep 2026, lock-step or under `-skew`;
  a mismatch under skew is a defect, identity is not evidence
  (`docs/remixer/HARNESS.md`). The decisive configuration is BusDelay on
  track 1, fed over the bus.
- Residual at 6–7 senders: 2 samples in 16,305 differ by ≤ 33 LSB
  (−105 dB) from the lag-0 control; does not scale with amplitude; filed as
  rounding under the added latency.

## Verification

`make verify-bus`: 19 layouts (17 until 18 Aug 2026; the two `IN` cases
were added after the delay's IN decode was deleted by a splice with 17/17
still passing), the three carriers of the housekeeping block, the election,
1–7 senders per bus, both cross-sends, split blocks, compared bit-for-bit
against a stamp (`SAVE=1` first). `tools/verify/verify_onebus.py` (in `make
check`) runs the chain on both cores: T5 prints the reverb (stereo) and T1
the delay; the reverb hears the delay; delay WET 0 == no delay three blocks
later, sample-exact; a host at WET 0 prints only its dry; T1's print is
bit-identical with the reverb at WET 0, WET 127 or absent; a SEND at
core-0 position 3 (T8) at SEND 127 changes neither host and the mirror
position on core 1 does; a Character with slot 4 stored 127 (RET in a
pre-20-Sep part) prints nothing and changes neither host; a station with
stored send bytes contributes nothing; the chain is identical under four
instruction-level skews. `make verify-twocore`: SEND, delay and series hops
on their real cores == the DEV hatch.

## The shared window

| range | what | notes |
|---|---|---|
| `0x30000–0x30047` | stock's per-frame parameter staging ✅ | rewritten every frame |
| `0x30000–0x37FFF` | core 0's half: BusVerb's relocated buffers (`0x30000`, `0x34000`), shimmer line, tank state | fully owned |
| `0x31000` / `0x32000` | stock bootstraps A and B ✅ | dead after boot |
| `0x36000+` | bus scratch (`docs/firmware/CHIP.md` for the extent) | both cores touch it |
| `0x38000–0x3FFFF` | core 1's half: BusDelay's LineL, 32,768 words (LineR is core 1's private `Y:0x4000–0xBFFF`, 15 Sep 2026) | 741 ms per line |

AGU modulo addressing needs power-of-2 alignment (big buffers at
`0x30000`/`0x34000`/`0x38000`/`0x3C000`); `0xC000–0x2FFFF` is absent, so no
single 128K buffer; the DSP56720 manual guarantees no bus contention while
the cores touch different 8K blocks ✅. A delay line based in core 0's half
sweeps the rotation word, the accumulators and the role locks every 16,384
samples (12 Aug 2026).

## Program space

`SPEC=1`: each payload carries SEND plus its own server, so the donor region
(2,724 words per core for the DEFAULT harvest, the three stock FX2 reverb
slots; since 3 Sep 2026 any of the thirteen, up to 6,158) is spent once per
effect. `SPEC=1` requires `XBUS=1`: without the bus each half of the tracks
reaches only its own core's server, and the build still makes sound, so the
build guards the combination. The build report is the free-word ledger
(`make bus`).
