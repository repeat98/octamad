; ---------------------------------------------------------------------------
; BusDelay: a two-line ping-pong delay with feedback tone-shaped by a one-pole
; low-pass inside the loop, and three engines on the same lines -- CLEAN,
; GRAIN (four unity-rate grain readers per line, one continuous pitch) and
; REVERSE (the two lines as one 32K mono ring, segments played backwards) --
; with tape wow and a sticky tempo snap on TIME.
; CYCLES_FORWARD_BRANCHES -- the REVERSE skips of the R line are forward
; branches the pricer admits.
;
; The LineL base is one hardcoded literal (Y:0x30000, the shared window)
; that build_bus.py rewrites per payload with a blanket text replace over the
; whole source, comments included, and censuses; shared-window addresses
; elsewhere in this file are offsets from a register-held base. The lines are
; plain circular buffers wrapped by hand (m1/m2 stay linear): the read
; address is base + ((wr - TIME) & mask) and the post-write pointer folds
; back the same way. THE GEOMETRY FOLLOWS THE PLACEMENT (tools/remix/geom.py:
; lines tagged `; @B` ship, `; @DEV` are the hatch's):
;   shipping (payload B, core 1), 741 ms of TIME:
;     LineL   base .. base+0x7fff          32768 words, the whole shared half
;     LineR   Y:0x4000 .. Y:0xbfff         32768 words, the core's private FX2
;             buffer region -- nothing else on core 1 writes it (measured
;             under the port on OCTABAM89 C02, 900 frames, 15 Sep 2026); on
;             core 0 it is the reverb's tank, which is why this is B-only
;   DEV hatch (payload A beside the reverb), 371 ms:
;     LineL   base .. base+0x3fff          16384 words
;     LineR   base+0x4000 .. base+0x7fff   16384 words
; A knob value means the same TIME in both (64 + value*256 samples, clamped
; to the line), so at any TIME the hatch can reach the two render
; bit-identically (verify_twocore). REVERSE's 32K mono ring is LineL's
; space in both.
;
; Input enters LineL, and LineR scaled by 1-PING; PING is a continuous 2x2
; crossfeed on the feedback path:
;        fbIntoL = fL*(1-PING) + fR*PING
;        fbIntoR = fR*(1-PING) + fL*PING
;        LineL[write] = x_in + fbIntoL*FDBK
;        LineR[write] = x_in*(1-PING) + fbIntoR*FDBK
; The loop gain per line is a convex combination of fL/fR scaled by FDBK, so
; stability does not depend on PING. (Summing the input into both lines
; unscaled makes the two state equations identical for a mono source, and
; PING does nothing.)
;
; Every proc() call runs the position-0 rotation-flip-and-clear housekeeping
; modules/send/send_client.asm describes (copied byte for byte: a divergent
; copy desyncs the bus silently), sums the shared DELAY accumulator into its
; input, multiplies by the auto-gain 1/sqrt(N) and writes its stage output
; (in + wet*WET, mono) to the chain buffer for the reverb. The host track
; prints wet*WET under its dry (20 Sep 2026: the wet leaves through the
; host and the chain and nowhere else; the published stereo stage output and
; the T8 return went); its own audio reaches the engine only through SEND.
;
; State in the per-instance r7 block. The numbers below are raw slots; the
; code from `bus_mine:` to `dry:` spells them rebased -- r7 is moved $49
; into the block there so every access is the one-word displaced move, and
; slot NN reads as x:(r7+(NN-$49)): $14 is x:(r7-$35), $88 is x:(r7+$3f).
;   r7+$14              call flag stash (proc entry accumulator)
;   r7+$15/$16/$17      per-sample scratch (age / phase then g^2 / t0 then
;                       tap); $15 doubles as the warm-up count stash
;   r7+$18              grain PRNG state, 23-bit xorshift (persistent, seeded
;                       nonzero at warm-up)
;   r7+$19..$1f         GRAIN per-sample parks: window, frac, t0, read phase,
;                       s, wet L, wet R
;   r7+$21..$23         per-sample scratch (PRNG candidate, parked age)
;   r7+$24/$25          shifted OUTPUT tap L / R (per sample; kept apart from
;                       the loop's taps so the shift never re-enters feedback)
;   r7+$26              TIME, Q8: the per-sample ramp value (last block's
;                       glide state at the block start, + the increment per
;                       sample); the glide state itself is the core-private
;                       TIME word below the RATE state block
;   r7+$27/$28          wow / flutter LFO phase (persistent, masked)
;   r7+$29              wow's offset park (per sample)
;   r7+$2b/$2c          this sample's loop lag: integer / Q23 fraction
;   r7+$2d/$2e          wow depth / flutter depth (per block)
;   r7+$2f/$30          per-sample scratch (the parked write value, clipped)
;   r7+$31              LineL base
;   r7+$32              GRAIN base age, Q11.12 (persistent, masked on load
;                       and save); each grain is a fixed quarter cycle off it
;   r7+$33              SHIFTED-OUTPUT flag (per block): the wet comes from
;                       $24/$25 (GRAIN)
;   r7+$34..$37         GRAIN latched scatter s0..s3 (persistent, latched at
;                       each grain's own wrap; cleared by the warm-up)
;   r7+$38/$39/$3a      GRAIN mask G-1, G/4 (grain-to-grain phase offset),
;                       window multiplier 2^(23-k) (per block, from SIZE)
;   r7+$3b              GRAIN read distance base lag + G + 1 (per block; lag
;                       capped so lag + scatter + G stays inside the line)
;   r7+$3c/$3d          GRAIN density and makeup coefficient (per block)
;   r7+$40..$4b         GRAIN line-L records: s, w, acc x 4 grains
;   r7+$4c..$57         GRAIN line-R records
;   r7+$58/$59          this sample's scatter / window-multiplier candidates
;   r7+$5d              GRAIN phase cursor
;   r7+$56..$5b         REVERSE per-sample scratch (mode-exclusive with GRAIN)
;   r7+$5e              REVERSE segment phase, 23-bit (persistent, masked on
;                       load and save); one phase for both lines and heads
;   r7+$5f              SIZE select index, raw 0..3 (per block)
;   r7+$60/$61          REVERSE segment length S / phase step 2^23/S
;   r7+$62              REVERSE lag floor (per block)
;   r7+$0c              last-seen rotation (the gated housekeeping block's)
;   r7+$20              this block's resolved write offset (0..112);
;                       every bus address derives from it (the ROTLATCH slot)
;   r7+$2a              REVERSE lag cap 32704 - 2S (per block; the loop's RLAG0 source)
;   r7+$6d              WET coefficient, glided (per block)
;   r7+$83              this call's CHAIN write address ($9d8 + rotation +
;                       frame offset; advances per sample; DRIVE's slot until
;                       21 Sep 2026, dead since the cubic went)
;   r7+$63/$64          this call's DELAY ACC read address / the TIME ramp's per-sample increment (Q8)
;   r7+$67              this call's frame offset, from r0 (shared mechanism;
;                       $65/$66 free since 21 Sep 2026)
;   r7+$68              LineR base: Y:0x4000 (the hatch: LineL + 0x4000) (per block)
;   r7+$69              MODE, MSB-aligned select (per block; 0 = CLEAN,
;                       1 = GRAIN, 2 = REVERSE; anything else = CLEAN)
;   r7+$6a              this block's MIDI note for GRAIN (0 = none)
;   r7+$6b              the L ring's mask: $7fff (the hatch: $3fff, or
;                       $7fff in REVERSE)
;   r7+$6c              skipR: 1 in REVERSE (the R line's read and write are
;                       skipped per sample; the output is mono to both)
;   r7+$6e/$6f          scratch: x_in (the passthrough term), stage output L (per sample)
;   r7+$70/$71          LineL/LineR write-pointer phase (persistent, masked
;                       on load and save: garbage with bit 23 set saturates
;                       the AGU and hangs the bus)
;   r7+$72/$73/$74/$75  TONE coefficient, FDBK coefficient, PING, TIME (per block)
;   r7+$76              IN, pinned to 0 (its arithmetic stays in the loop)
;   r7+$77/$78          TONE filter state, line L / R (persistent)
;   r7+$79/$7a          scratch: dL/dR, raw taps (per sample)
;   r7+$7b/$7c          scratch: fL/fR, damped taps == this sample's wet
;   r7+$7d              scratch: x_in, own dry mono + bus (per sample)
;   r7+$7e/$81          scratch: fbIntoL/fbIntoR (per sample)
;   r7+$7f              bus auto-gain 1/sqrt(N) (per block; read per sample)
;   r7+$80              1 - PING (per block)
;   r7+$82              warm-up tagged counter
;   $84..$8a            NEVER WRITTEN (21 Sep 2026). Until then the chain write
;                       address, the WET glide state, the write offset, the
;                       REVERSE cap and the last-seen rotation sat at $84..$88:
;                       on a host track with a sample playing, the unit's own
;                       per-track state lives there between our calls, and the
;                       delay printed a white-noise wash that survived STOP
;                       (docs/remixer/FAILURE_MODES.md). DSP.md had recorded
;                       $84..$8a as not persisting since 10 Aug 2026.
;
; Parameters (a knob arrives as value<<16, value 0..127):
;   p0 AUX   -> this host's own dry send into the aux (headroomed, summed
;               before the auto-gain, counted as a client while nonzero)
;   p1 TIME  -> delay length, 64 .. 32576 samples (~1.5 .. 739 ms; the hatch
;               clamps at 16320), a free
;               dial that sticky-snaps to a tempo division (1/32T .. 1/4. of
;               stock's tempo24 at r6+$13, ticks derived per block), holds it
;               through tempo changes and lets go when the knob moves; the
;               STICKY SNAP block in proc
;   p2 FDBK  -> feedback gain, 0 .. ~0.87 (FDBK=0 is a single echo)
;   p3 TONE  -> one-pole coefficient, 0.125 (dark) .. 0.99 (bright)
;   p4 PING  -> crossfeed, 0 (centred) .. ~0.99 (full ping-pong), Q1.23
;   p5 MIX   -> the stage crossfade
;   p6 MODE  -> page-2 slot 6 KNOB field (r6+$c bits 16-23)
;   p7 MDEP  -> wow depth (GRAIN: scatter), slot 7 companion (r6+$c bits 8-15)
;   p8 MRAT  -> wow rate, 64 = 1x (GRAIN: density)
;   p9 SIZE  -> slot 9 companion (r6+$d low bits): GRAIN grain length and
;               REVERSE segment, one select for both
;   p10 PTCH -> slot 10 KNOB field (r6+$e bits 16-23): GRAIN pitch, +-2 oct;
;               a held MIDI note (r6+$1 bits 8-15, latched) overrides
;   p11 WOW  -> slot 11 companion (r6+$e bits 8-15): tape wobble depth,
;               0 .. +-254 samples (wow 0.8 Hz + flutter 7.3 Hz at an
;               eighth; ~47 + ~54 cents peak at 127, computed), on the
;               loop tap in every mode
; ---------------------------------------------------------------------------

init:
; Hardcoded base, no per-instance stash needed -- literal is identical for
; every instance, same reasoning as modules/busverb/reverb_server.asm's init.
; ---- seed the tracked rotation, so a cold boot cannot start out of step ---
; ⚠️ THE TRACKING CANNOT SELF-CORRECT A BAD START, and the commit that added it
; claimed otherwise. "This client legitimately read PRE-FLIP" and "this client
; is stuck one step AHEAD" give an identical comparison result, every block,
; forever -- no observation separates them, so a client that boots one step
; ahead stays there. Harmless when written; NOT harmless once the clear moved
; one block ahead, because a client stuck one step ahead then writes precisely
; the buffer core 0 is clearing, and every core-1 sender is wiped. That was the
; metallic on every power cycle of R25, and why re-selecting the effect cured
; it: the instance misses blocks during the switch, falls BEHIND, and snaps.
; If it cannot self-correct it must begin correct. init runs on instantiation
; -- exactly what re-selecting does -- so seeding here makes a cold boot
; deterministic. The shared word may advance one step before the first proc;
; that direction DOES snap, so it is safe.
; build_bus.py emits a body here for PAYLOAD B ONLY -- payload A recomputes the
; offset from the shared word every block and has nothing to seed.
; INIT WRITES NOTHING BUT THE ROTATION SEED (21 Sep 2026). Four stores here
; zeroing the glided coefficients (raw $72/$73/$74/$6d, images 39-41) put a
; white-noise wash on any host past dispatch position 0 that had trigs on
; it (T2 THRU or T3 STATIC with a trig every step; T1 never), bisected on
; the unit: image 38 without them clean, 39/40/41 wash, 42 = 41 minus the
; four stores clean. The port never showed it. Mechanism open
; (docs/remixer/FAILURE_MODES.md); the coefficients glide in from whatever
; the slot held for ~20 ms after a select, as before.
; ROTINIT
        rts

proc:
; ---- BOTH calls are audio -------------------------------------------------
; Same dispatcher shape as every other effect in this project -- see
; dsp/reverb89.asm's proc: comment for the full mechanism. Everything below
; re-derives from r7 state per call, so the two sub-calls of a split block
; are sample-continuous by construction.
        move    a,x:(r7+$14)            ; the dispatcher's call flag, stashed
                                        ; (0 = the a=0 sub-block, $010000 = a=1)
; ---- this call's frame offset, from r0 (21 Sep 2026) --------------------
; The dispatcher passes r0 = 0 on a block's first call and r0 = 2 x split on
; the a=1 call of a split block (measured under the port: r0 = $e for a trig
; at frame 7). Until 21 Sep 2026 the offset was reconstructed from a flag
; and a split the a=0 call stashed in $65/$66 for the matching a=1 call; on
; the unit a host with a trig on every step (T2 THRU, T3 STATIC) washed with
; white noise while the port stayed clean, the shape of a stash that does
; not survive between the two calls: a second call taken for a first one
; advances position 0's rotation tracker twice in a frame, and the tracker
; keeps a lead of one for ever (the R25 "metallic" mode). r0 needs no state.
        move    r0,a
        asr     #$1,a,a                 ; words -> frames
        and     #>$f,a                  ; 0..15 by construction; garbage masked
        move    a1,x0
        move    x0,a                    ; A2-clean
        move    a,x:(r7+$67)            ; this call's frame offset
bus_off_done:

; ---- position-0 housekeeping: flip the shared bus rotation, clear the new
; write-target ACC buffers. Gated on r7==0x6200 AND offset==0 -- copied from
; modules/send/send_client.asm / modules/busverb/reverb_server.asm, must stay identical.
; Housekeeping is normally done by position 0 (r7 == 0x6200, the bank's first
; FX2 call). That alone breaks the moment the first track's FX2 is NONE: our
; code never runs there, so nobody flips the rotation or clears the
; accumulators, and the bus saturates. NONE became selectable with the task-11
; menu, so this is reachable in ordinary use.
;
; Self-healing election instead. Position 0 still housekeeps whenever it runs.
; Any other instance takes over if it sees that the rotation has NOT changed
; since the last time it ran -- which can only mean nobody housekept in
; between. Costs one r7 word (the rotation this instance last saw) and no new
; global signal, so it needs nothing the bus does not already have.
;
; Gated on the split offset FIRST: only a block's first call may housekeep, so
; a split block's second call can never flip a second time -- the same trap
; the original position-0 code was written around.
; XBUS_GATE -- build_bus.py substitutes a payload gate here when XBUS=1.
; A shared-memory bus is housekept by ONE core only: both cores number their
; own instances from zero, so each core's position 0 believes it is the
; housekeeper and they would flip the shared rotation TWICE a block, cancelling
; out and silently desyncing the bus -- the same trap the split-call gate
; below was written around, one level up. Payload B is sent straight to
; bus_notfirst, so it still finds this block's write targets but never elects.
; Inert in a normal build: it is a comment.
        move    x:(r7+$67),a
        tst     a
        bne     bus_notfirst                ; not this block's first call
        move    r7,a
        move    #>$6200,x0
        cmp     x0,a
        beq     bus_dohk                ; position 0: always the housekeeper
        move    y:>$900,a
        and     #>$70,a
        move    a1,x0
        move    x0,a                    ; offset now, A2-clean
        move    x:(r7+$0c),x0
        cmp     x0,a
        bne     bus_seen                ; it moved: someone else housekept
bus_dohk:                               ; nobody did -- take over this block

; y:>$900 holds the WRITE OFFSET (0..112), not the bare buffer index --
; see the layout comment in modules/send/send_client.asm. EIGHT buffers, so the rotation
; is +16 mod 8 and the mask that does the modulo sanitises boot garbage too.
; No `asl #$4` follows: the value is already scaled.
        move    y:>$900,a
        add     #>$10,a
        and     #>$70,a
        move    a,y:>$900               ; the new CURRENT rotation
; ⚠️ CLEAR THE BUFFER WRITTEN **NEXT** BLOCK, NOT THIS ONE.
; Clearing the buffer we are about to write races the OTHER core's writers:
; core 0 clears at the start of its block and everyone fills it during that
; block, so a core-1 writer that gets there BEFORE core 0's housekeeper has
; its contribution written and then wiped. Straddle that boundary and the
; sender drops out on some blocks and not others -- intermittent dropout,
; which is broadband hash exactly like the two defects before it.
; The four-buffer rotation fixed clear-vs-READ and the per-core tracking fixed
; which-buffer; NEITHER touches clear-vs-WRITE. This does, and it is free:
; with four buffers there is an idle slot. The buffer written next block was
; last READ a full block ago and will not be WRITTEN for another full block,
; so clearing it now has a block of margin on both sides.
        add     #>$20,a                 ; two on: written two blocks from now,
        and     #>$70,a                 ; last read three blocks ago
        move    a,x0                    ; bases for the clear AND the count

        move    #>$901,b                ; ONE BUS (6 Sep 2026): the AUX
        add     x0,b                    ; accumulator, the only one left
        move    b,r2                    ; r2 = AUX ACC[new] base
        move    #>$ffffff,m2
        clr     a
        move    #>16,y0
        do      y0,>bus_zclr
        move    a,y:(r2)+
bus_zclr:
        nop
; ---- release both server-role locks for this block (BUS.md hardware test 3)
; a is still 0 from the clear loop above. Whichever of the three effects is
; position 0 does this, so the locks are freed exactly once per block and
; re-claimed below in dispatch order.
        move    a,y:>$9c1               ; DELAY SERVER role owner
        move    a,y:>$9c2               ; REVERB SERVER role owner
; ---- reset the new write buffer's SEND COUNTs, alongside its accumulators --
        move    x0,a                    ; the SAME buffer the clear loop just
        asr     #$4,a,a                 ; zeroed: count and accumulator move
        move    #>$9c7,x0               ; together (0..3); the AUX count
        add     x0,a
        move    a,r3
        move    #>$ffffff,m3
        clr     a
        move    a,y:(r3)                ; AUX count = 0
bus_seen:
        move    y:>$900,a               ; remember this block's offset so next
        and     #>$70,a                 ; block we can tell whether anybody
                                        ; else housekept in between
        move    a1,x0
        move    x0,a
        move    a,x:(r7+$0c)
bus_notfirst:
; ---- resolve THIS BLOCK'S WRITE OFFSET, ONCE, into r7+$86 ---------------
; See the long note in modules/send/send_client.asm: every client used to read y:>$900
; at its own dispatch time, which is not a stable value on payload B because
; core 0 owns the flip. This server is on payload B, so it is exposed.
; build_bus.py substitutes a per-payload body here; both leave the offset in
; r7+$86, and every site downstream reads that instead of the shared word.
; ROTLATCH

; ---- server-role lock: only ONE DELAY SERVER may run per bank -----------------
; Both servers use a FIXED, hardcoded Y base identical for every instance, so
; two of the same role would share one set of buffers and drive each other's
; feedback path -- measured on hardware as a solid, unchanging tone (BUS.md's
; hardware test 3). The lock is released once per block by whichever effect is
; position 0 (above) and claimed here in dispatch order: the first instance to
; arrive owns the role for that block, any duplicate rts's without touching
; the audio buffer at all, which is an exact dry passthrough.
;
; Keyed on r7 (this instance's own state block), so a split block's two calls
; both match the same owner and the second is not mistaken for a duplicate.
        move    y:>$9c1,a
        move    a1,x0
        move    x0,a                    ; A2-clean before the compare
        tst     a
        beq     bus_claim               ; free: take it
        move    r7,x0
        cmp     x0,a
        beq     bus_mine                ; already ours (split block's 2nd call)
        rts                             ; a duplicate: pass audio through
bus_claim:
        move    r7,a
        move    a,y:>$9c1
bus_mine:
; ---- r7 REBASE (14 Sep 2026): from here to `dry:` r7 points $49 INTO the
; state block. The one-word displaced move reaches -64..63 and the block
; spans $14..$88, so with the raw r7 every slot from $40 up cost two words
; (222 sites, most of them per sample). Slot NN is written x:(r7+(NN-$49))
; from here on -- x:(r7-$35) is $14, x:(r7+$3f) is $88 -- and the header
; map and every comment keep the RAW numbers. Everything that compares or
; stores r7 ITSELF (the position-0 test, the role lock, the ROTLATCH /
; ROTINIT / HOSTGUARD bodies the build substitutes) runs ABOVE this point
; on the raw value; the duplicate-server rts above never reaches it; the
; GRAIN record bases below derive from the rebased value; `dry:` puts the
; raw block back before the rts. Costs 8 words a call, pays ~190.
        move    r7,a
        add     #>$49,a
        move    a,r7                    ; r7 = state block + $49
; ---- the P table: five SIZE rows, the snap divisions and the
; reciprocals live in a table the manifest declares (schema.DspSection.ptable)
; and the build parks in the stock curve bank (X:0x4840, `p:(` reads become
; `x:(`), or leaves in P in front of the code. Its base is held in n4 for the
; whole block: r7 has no spare word and r4 walks GRAIN's records with no
; stride, so n4 is free from here to `dry:`. The literal below is the one the
; build rewrites; it may appear nowhere else in this file.
        move    #>$fab1e0,n4            ; the P table -- rewritten by build_bus.py

; ---- this call's DELAY ACC read address ----------------------------------
; READ is the OTHER buffer from the current write rotation -- the one every
; SEND client (and our own dry sum, below) finished filling last block.
; WRITE uses the SAME rotation clients currently write into, for a future
; cross-bus reader (task 10), not consumed by anything yet.
; ⚠️ THE OFFSET COMES FROM r7+$86, NOT y:>$900. This server lives on payload B
; and cannot read the shared rotation at its own dispatch time -- core 0 flips
; it asynchronously, so a core-1 client whose window straddles the flip sees a
; different value on different blocks. The resolve block at bus_notfirst
; tracks a stable rotation for this core; see the long note there and
; docs/effects/XBUS.md step 3.
; The offset is already scaled by the 16-word buffer stride, so the write
; addresses need no shift at all. THE READ TARGET IS TWO BUFFERS
; BACK, `write + 32 & $30`. THIS IS THE LINE THE WHOLE RACE FIX IS FOR: with
; four buffers there is an idle block on each side of this read, so core 0's
; housekeeper can lead or lag core 1 by up to a full block and still never
; clear or write the words being read here. Two buffers had no such margin at
; any clear time, which is why the delay stuttered on track 1 and not track 4
; (hardware, 17 Aug 2026 -- dispatch position moved the read relative to the
; other core's flip).
        move    x:(r7-$29),a
        move    a,x1                    ; x1 = write offset (0..112)
        add     #>$50,a                 ; five buffers on == three buffers back
        and     #>$70,a                 ; mod 8
        move    a,x0                    ; x0 = the read offset
        move    #>$901,a
        add     x0,a
        move    x:(r7+$1e),b            ; this call's split-aware frame offset
        add     b,a
        move    a,x:(r7+$1a)            ; this call's DELAY ACC read address
        move    x1,x0                   ; the full write offset, 0..112
        move    #>$9d8,a                ; the CHAIN buffer (one-aux rig, 7 Sep
        add     x0,a                    ; 2026): 8 x 16 mono words since 22 Sep
        add     b,a                     ; 2026 (the map in send_client.asm)
        move    a,x:(r7+$3a)            ; this call's CHAIN write address

; ---- bus auto-gain: resolve 1/sqrt(N) for this block's READ buffer --------
; The DELAY-bus mirror of the reverb's v121 fix (XBUS.md "Gain staging"):
; N clients summing into one accumulator word drive the delay N x as hard as
; one, and the shared word clamps at 1.0. Every DELAY-bus writer (SEND's
; ->DELAY tap, the reverb's ->DEL send) now registers once per block in a
; per-buffer DELAY count and writes with 3 bits of headroom
; (asr #3); this block divides by the count and the per-sample read shifts
; back up by 3, so the send knob sets a track's SHARE of the delay rather
; than how hard the line is hit.
; ⚠️ THE LAW IS 1/sqrt(N), NOT 1/N -- see the long note at the
; reverb's copy of this table. N sources sum as N only when CORRELATED;
; uncorrelated ones (actual different tracks) sum as sqrt(N), so dividing by N
; over-corrects real material by 3 dB per doubling, 9 dB at eight senders.
; The original verification was blind to it: send_probe feeds the SAME tone to
; every sender, which is exactly the correlated case 1/N gets right.
; Same table order as the reverb's: count is masked to 0..7, so 8 writers wrap
; to index 0, which therefore holds 1/sqrt(8). A count of 0 (nobody wrote)
; lands there too -- harmless, the accumulator is zero then anyway.
;
; The eight reciprocals are the manifest's RECIP, in the P table at offset
; 50. Until then they were rebuilt into the shared bus scratch
; every block, 27 words a call, because this server has no free ground of
; its own; those eight bus-scratch words are free now. x1 (write_rotation)
; is still valid from the address block above.
        move    #>$ffffff,m5            ; r5 linear for the block (the

        move    x1,a                    ; the count belongs to the buffer this
        add     #>$50,a                 ; block READS, which is three buffers back
        and     #>$70,a                 ; mod 8
        asr     #$4,a,a                 ; scaled back down -- the counts are one
        move    #>$9c7,x0               ; word per buffer, not sixteen
        add     x0,a
        move    a,r5
        move    #>$1,x0                 ; the "one more client" increment
        clr     b                       ; b = 0 -- BEFORE the tst below
        move    x:(r6),a                ; AUX (slot 0): the host's own send
        and     #>$7f0000,a             ; knob field only
        tst     a
        tne     x0,b                    ; sending -> b = 1: we count ourselves
; ->DEL from the REVERB host (v8, 5 Sep 2026): BusVerb writes its ->DEL knob
; field to y:$981 every block -- a single-writer word, not a count RMW -- and
; it is one more client while nonzero. x0 is still the increment; the Tcc
; reads the tst with nothing between; a zero word leaves a = 0, which IS the
; right count. The warm-up below zeroes the word, so a rig with no reverb
; never counts boot garbage (and one block of it before the first warm-up
; is masked to 0..7 like everything else here).
        move    y:>$981,a
        tst     a
        tne     x0,a                    ; a = 1 if the reverb host is sending
        add     a,b                     ; ... one more client
        move    y:(r5),a                ; clients that wrote the buffer we read
        add     b,a                     ; ... plus ourselves, if sending
        and     #>$7,a                  ; masked: boot garbage cannot index wild
        add     #>$34,a                 ; + 52, the reciprocals' offset in the
        move    a1,n5                   ; P table -- a1 straight into n5, so
        move    n4,r5                   ; there is no store and no A2 to clean
        move    p:(r5+n5),a             ; 1/sqrt(N)
        move    a,x:(r7+$36)            ; this block's bus gain, used per sample

; ---- (the REVERB-client registration lived here until the one-aux rig,
; 7 Sep 2026: the delay is chain stage 1, its output reaches the reverb
; through the CHAIN buffer at unity, and it is not a client of anything.
; $9c3 is its liveness stamp now -- see dwarmdone.)

        move    #>$ffffff,m0            ; audio is read and written via r0
        move    #>$ffffff,m4            ; GRAIN walks its table with r4 -- the
                                        ; one free AGU pointer, held at the
                                        ; global linear invariant like the rest
        move    #>$30000,x0
        move    x0,x:(r7-$18)

; ---- warm-up: zero both lines and persistent state before running --------
; Same tagged-counter idiom as dsp/reverb89.asm/modules/busverb/reverb_server.asm, but a
; DIFFERENT TAG -- $2e0000, where reverb_server uses $2c0000. Both effects
; keep their counter in the same r7+$82 slot and the dispatcher does NOT clear
; the state block when a track's effect changes, so with a shared tag the
; incoming effect read the outgoing one's counter, saw a valid tag at full
; count, skipped warm-up entirely and ran on the other algorithm's leftover
; buffers. Measured on hardware as "the track will not switch between DELAY
; and REVERB SERVER" (BUS.md's hardware test 3). A distinct tag makes the
; other effect's counter fail the tag compare, restarting warm-up exactly as
; a cold start does. ($82 = $2e0000 | count.) Necessary here too: LineL and
; LineR hold boot garbage on
; first use, and this engine has real feedback, so uncleared garbage would
; recirculate rather than just play once and vanish. Sized for this file's
; 32768-word allocation: 128 words/block * 256 blocks = 32768 exactly.
        move    x:(r7+$39),a
        and     #>$fffe00,a             ; tag field -- AND cleans A1 only
        move    a1,x0
        move    x0,a                    ; A2-clean before the compare
        move    #$2e,x0  
        cmp     x0,a
        beq     dwarmtag
        clr     a                       ; garbage tag: warm-up starts at 0
        bra     dwarmrun
dwarmtag:
        move    x:(r7+$39),a
        and     #>$1ff,a
        move    a1,x0
        move    x0,a                    ; the count, A2-clean
        move    #>$100,x0
        cmp     x0,a
        bge     dwarmdone               ; warmed: run the delay
dwarmrun:
        move    a,x:(r7-$34)            ; count, for the save below
        asl     #$7,a,a                 ; count*128
        move    x:(r7-$18),x0
        add     x0,a
        move    a,r5                    ; base + count*128
        clr     b                       ; the zero source ...
        move    x:(r7-$18),x0           ; ... and both fill the AGU slot
        do      #128,>dwarmz
        move    b,y:(r5)+
dwarmz:
; shipping: LineR is its own 32K in the private region -- 128 more words a
; block, so 256 blocks clear both lines. (The hatch's lines are contiguous
; and the loop above already walks both.)
        move    x:(r7-$34),a            ; count                            ; @B
        asl     #$7,a,a                 ; count*128                        ; @B
        add     #>$4000,a               ; LineR base + count*128           ; @B
        move    a,r5                                                       ; @B
        do      #128,>dwarmq                                               ; @B
        move    b,y:(r5)+                                                  ; @B
dwarmq:                                                                    ; @B
        move    b,x:(r7+$27)
        move    b,x:(r7+$28)
        move    b,x:(r7+$2e)
        move    b,x:(r7+$2f)
        move    b,y:>$981               ; the REVERB host's ->DEL flag (v8):
                                        ; zeroed once here, so a rig without
                                        ; a reverb never counts garbage in it
; (14 Sep 2026: thirteen clears left with the dead code they served. $19-$1f
; are GRAIN v5's per-sample parks and $1e/$1f its wet sums, every one written
; before it is read in the same sample; $20/$21 have had no reader since the
; PITCH jitter retired; $24/$25 are only ever LOADED into a Tcc source that
; does not fire outside GRAIN/REVERSE, which write them first; $6c is skipR,
; decoded every block before the loop; $6d had no reader at all.)
; ---- ONE LOOP CLEARS RAW $27..$5e: the TAPE LFO phases, GRAIN's
        move    r7,a
        sub     #>$22,a                 ; raw $27 (r7 is rebased by $49)
        move    a,r5
        do      #56,>dwarmc
        move    b,x:(r5)+
dwarmc:
; ---- THE GRAIN COUNT IS A BUILD-TIME LEVER (4 Sep 2026) -------------------
; Four grains per line is what this source assembles to. A remix that
; declares `grains=2` (schema.Remix) has build_bus.py substitute three
; things at the markers below, and nothing else changes:
;
;   ; GRAINCNT  the two rolled loops count 2 instead of 4
;   ; GRAINOFF  the grain-to-grain phase offset doubles, G/4 -> G/2, so two
;              grains still tile the cycle
;   ; GRAINMK   the makeup doubles, because FOUR triangle windows at quarter
;              offsets sum to exactly 2 while TWO at half offsets sum to
;              exactly 1 -- so the same coefficient would land 6 dB down
;
; WHY: cycles, not sound. The delay's core cannot carry four active stations
; beside a four-grain GRAIN (3,294 of 3,120 by the pricer); at two grains it
; fits. The cost is half the simultaneous grain voices, which is an ear
; decision, not a correctness one.
;
; ⚠️ THE HALF-OFFSET CASE HAS AN EXACT TEST and the quarter-offset one does
; not: two triangle windows a half period apart sum to exactly 1, so DC in
; must come back flat. That is the gate that caught Nimbus's double-rate
; window (CLAUDE.md, the a0 trap), and it is why the two-grain build is the
; better-checked of the two.
;
; GRAIN v5's PERSISTENT latches: eight scatters, eight window multipliers
; and eight read advances, each re-latched at its own grain's wrap. A garbage scatter subtracts
; straight into a read address and a garbage multiplier is a garbage window
; for one grain-life, so both start at 0 like the PITCH offsets do.
        move    b,y:>$090a              ; the latched MIDI note starts at NONE.
        move    #>$123456,a             ; PRNG seed: any nonzero word (xorshift
        move    a,x:(r7-$31)            ; is dead at 0), fixed for determinism
        move    x:(r7-$34),a            ; reload count
        add     #>$1,a
        add     #>$2e0000,a             ; tag | count+1
        move    a,x:(r7+$39)
        bra     dry                     ; output stays dry until warm
dwarmdone:
; ---- DELAY LIVE (one-aux rig, 7 Sep 2026): stamp y:$9c3 (the reverb's
; chain-live word) every block this engine really processes; clear-on-read
; by the reverb. Not written during the warm-up above, so a warming delay is
; not live: the reverb reads the aux accumulator.
        move    #>$1,x0
        move    x0,y:>$9c3
        move    x:(r7-$18),x0           ; LineL base

; ---- per-block: TIME, FDBK, TONE, PING, -VRB, IN, ... ---------------------
        move    x:(r6+$1),a             ; TIME: slot 1 (one-aux re-slot, 7 Sep 2026)
        and     #>$7f0000,a             ; knob field only
        asr     #$8,a,a                 ; value*256 (0..32512)
        move    #>64,x0
        add     x0,a                    ; floor 64 samples (~1.45 ms)
        move    a,x:(r7+$2c)            ; TIME, 64..32576 samples (the hatch clamps at 16320 below)
        move    #>16320,x0                                                 ; @DEV
        cmp     x0,a                                                       ; @DEV
        tgt     x0,a                                                       ; @DEV
        move    a,x:(r7+$2c)                                               ; @DEV

; ---- samples per MIDI clock, from stock's tempo24 (15 Sep 2026) ----------
; The frame builder stores tempo24 (BPM*24, 720..7200) into halfword 31 of
; every track's record every frame (0x40004d6a), which an FX2 instance reads
; at r6+$13. ticks Q12.4 = 42,336,000 / tempo24 -- the word the ColdFire
; cave used to publish at r6+$7, and it clobbered the FX1 station's page 2
; there (docs/remixer/FAILURE_MODES.md). 48/24 division, 24 `div` steps:
; `div` is fractional, so a0 comes out as N/(2D) for a dividend N loaded as
; an integer -- the dividend is loaded DOUBLED (84,672,000 = $050bfe00) and
; a0 is the integer quotient. Measured under the port (tempo24 2901: 7296
; from the plain constant, 14593 doubled); a halved period snaps every
; division M <= 12 to the same TIME through 2M, so only the 1/4 case in
; tools/verify/verify_tempo.py can see it. 0 when tempo24 reads 0 (no
; frame yet): free-running TIME.
        move    x:(r6+$13),a
        and     #>$ffff00,a
        asr     #$8,a,a                 ; tempo24, integer
        move    a1,x0
        clr     b
        tst     a
        beq     tickz                   ; 0 -> ticks 0
        move    #>$0bfe00,x1
        move    #>$5,a                  ; a1:a0 = 84,672,000 = $050bfe00
        move    x1,a0
        andi    #$fe,ccr
        rep     #$18
        div     x0,a
        move    a0,b                    ; quotient, <= 58,800 (B2 clean: a0 < 2^23)
        asl     #$8,b,b                 ; << 8, as every published word
tickz:
        move    b,y:>$090d

; ---- TIME: STICKY SNAP to a tempo division --
        move    x:(r7+$2c),a            ; free-running TIME, from the knob
        move    a,y1
        asr     #$4,a,a
        move    a,x1                    ; tolerance = free/16
        move    y:>$090d,x0             ; ticks Q12.4 << 8 (0 = not published)
        clr     b                       ; candidate: 0 = nothing near
; THE TWELVE DIVISIONS ARE A TABLE: M << 11 for M in {2, 3, 4,
; 6, 8, 9, 12, 16, 18, 24, 32, 36}, the manifest's SNAP_DIVS, appended to the
; P table after the SIZE rows. One `do` over them; the table read leads the
; body so each trip's cmp and tlt stay adjacent (the shared-flag idiom), and
; nothing in the body but the read changes between trips. 70 words -> 12.
        move    n4,r5                   ; the P table (block preamble)
        move    #$28,n5                 ; + 40: the divisions
        move    (r5)+n5
        do      #12,>snapz
        move    p:(r5)+,y0              ; M << 11, smallest first
        mpy     y0,x0,a                 ; ticks*M
        sub     y1,a
        abs     a                       ; |d - free|
        cmp     x1,a
        tlt     y0,b                    ; within tolerance -> candidate
snapz:
; ---- knob moved? then held = candidate, else keep ---------------------------
        move    b,x1                    ; candidate (B2 clean: clr/Tcc only)
        move    x:(r6+$1),a             ; TIME (slot 1)
        and     #>$7f0000,a
        asr     #$10,a,a                ; knob, 0..127
        move    a,y0
        move    y:>$0908,x0             ; last knob
        move    y0,y:>$0908
        move    y:>$0909,b              ; held M<<11 (0 = free)
        cmp     x0,a                    ; knob - last
        tne     x1,b                    ; moved -> re-evaluated
        move    b,y:>$0909
; ---- TIME = held ? ticks*held : free ---------------------------------------
        move    b,y0
        move    y:>$090d,x0
        mpy     y0,x0,a                 ; 0 when free or unpublished
        move    #>32704,x1                                                 ; @B
        move    #>16320,x1                                                 ; @DEV
        cmp     x1,a
        tgt     x1,a                    ; clamp to the line
        move    x:(r7+$2c),x1
        tst     a
        teq     x1,a                    ; free
        move    a,x:(r7+$2c)

; ---- TIME SLEW: glide, don't jump ---------------------------
; ONCE PER BLOCK (21 Sep 2026): the dispatcher calls twice on a trig split
; (a=0 for the frames before the trig, a=1 for the rest) and the glide,
; the ramp base and the coefficient glides below ran on both calls -- the
; ramp restarted from last block's state at the trig, a jump of up to a
; quarter or three-quarters of the glide step (up to ~30 samples on a big
; TIME move): a click at every trig while the knob moved. They run on the
; first call of a block only (frame offset 0); the second sub-call keeps
; the ramp's running value and its increment, and every coefficient slot
; already holds this block's value.
        move    x:(r7+$1e),a            ; this call's frame offset
        tst     a
        bne     slew2                   ; second sub-call: everything stands
        move    x:(r7+$2c),a            ; target, integer samples
        asl     #$8,a,a                 ; Q8
        move    a,x0
        move    y:>$0907,b              ; slewed TIME, Q8 (0 at boot)
        tst     b
        teq     x0,b                    ; boot: start AT the target
        tmi     x0,b                    ; boot garbage, negative: the target
        move    #>$7fc000,y0            ; 32752 samples in Q8, past any line
        cmp     y0,b
        tgt     x0,b                    ; boot garbage past the line: the target
        move    b,y0                    ; the state
        move    x0,a
        sub     y0,a                    ; d = target - state
        move    a,y1
        asr     #$a,a,a                 ; /1024 per block
        move    a,b                     ; the exponential step
; MINIMUM STEP (21 Sep 2026): /1024 rounds to zero inside 4 samples of the
; target, and a standing fraction is a 2-sample average on every pass round
; the loop, which dulls the repeats; image 33's snap landed ON the target
; from 4 samples out, a quarter-sample-per-sample ramp for one block. The
; step is now never smaller than 1/16 sample per block toward the target
; and never past it: the last 4 samples take 64 blocks (23 ms) at a slope
; of 1/256, and the state lands exactly, so the fraction is 0 at rest.
        move    y1,a
        abs     a                       ; |d|
        cmp     #>$10,a
        bgt     stpbig
        move    y1,b                    ; within 1/16 sample: land on it
        bra     stpdn
stpbig:
        move    b,a
        abs     a                       ; |step|
        cmp     #>$10,a
        bge     stpdn                   ; the exponential step is big enough
        move    #>$10,x1
        move    y1,a
        tst     a                       ; the sign of d
        tpl     x1,b                    ; +1/16 sample
        move    #>$fffff0,x1
        tmi     x1,b                    ; -1/16 sample
stpdn:
        move    y0,a
        add     b,a                     ; state += step
        move    a,y:>$0907
        move    a,b                     ; the Q8 state
        asr     #$8,a,a                 ; back to integer samples
        move    a,x:(r7+$2c)            ; TIME, as every consumer below sees it
; THE RAMP (20 Sep 2026, the second crackle): the loop's tap does not sit
; at this block's state, it walks from LAST block's state to this one's a
; sixteenth of the step per sample -- a step applied whole at the block
; edge was a read that jumped up to 17 samples every 16, a click per block
; for the ~1 s a big TIME move glides (measured under dsp_host and the
; port, image 38: 24 second-difference spikes per 1,000 samples for the
; whole glide, 0 at rest). Each sample adds the wobble to the ramped Q8
; value and splits the sum into the lag and a fraction; modtap reads
; BETWEEN samples at that fraction. Raw $26 holds the running value (r7
; is rebased by $49 here and in the loop), raw $64 the per-sample increment.
; A split block's two calls walk the same ramp end to end (the a=1 call
; skips to slew2 above); the harness's 15-frame blocks land a sixteenth of
; a step short and re-base, under two samples at the fastest glide.
        move    y0,x1                   ; last block's state
        move    x1,x:(r7-$23)           ; the ramp starts there
        sub     x1,b                    ; this block's step, Q8
        asr     #$4,b,b                 ; per sample, over 16
        move    b,x:(r7+$1b)            ; the increment

; FDBK, TONE, PING and WET glide too (20 Sep 2026): each coefficient
; moves an eighth of the way to its knob per block (~130 samples to settle)
; instead of stepping -- a step on the recirculating signal was a click a
; block while a knob turned. The state is the slot itself.
        move    x:(r6+$2),x0            ; FDBK: slot 2 (one-aux re-slot)
        move    #$70,y1  
        mpy     x0,y1,a                 ; target, 0 .. ~0.87
        move    x:(r7+$2a),b            ; last block's coefficient
        sub     b,a
        asr     #$3,a,a
        add     b,a
        move    a,x:(r7+$2a)            ; FDBK, glided

        move    x:(r6+$3),x0            ; TONE: slot 3 (one-aux re-slot)
        move    #$70,y1  
        mpy     x0,y1,a
        add     #>$100000,a             ; target, 0.125 (dark) .. 0.99 (bright)
        move    x:(r7+$29),b
        sub     b,a
        asr     #$3,a,a
        add     b,a
        move    a,x:(r7+$29)            ; TONE, glided

        move    x:(r6+$4),x0            ; PING: slot 4 (one-aux re-slot)
        move    x0,a                    ; target, 0 .. ~0.99
        move    x:(r7+$2b),b
        sub     b,a
        asr     #$3,a,a
        add     b,a
        move    a,x:(r7+$2b)            ; PING, glided
        move    a,x0
        move    #>$7fffff,a
        sub     x0,a
        move    a,x:(r7+$37)            ; 1 - PING

        move    x:(r6+$5),x0            ; WET, slot 5
        move    x0,a                    ; target
        move    x:(r7+$24),b
        sub     b,a
        asr     #$3,a,a
        add     b,a
        move    a,x:(r7+$24)            ; WET, glided (raw $6d since 21 Sep
                                        ; 2026: raw $85 was in the $84..$8a
                                        ; range that hardware does not keep)
        bra     slewdn
slew2:
        move    x:(r7-$23),a            ; the ramp's running value, Q8
        asr     #$8,a,a
        move    a,x:(r7+$2c)            ; TIME for the per-block consumers below
slewdn:

; ---- IN: this track's OWN send level into the delay (v3 stage 1) ---------
        move    x:(r6),a                ; AUX, slot 0 (one-aux rig, 7 Sep 2026:
                                        ; every track's one send, this host's
                                        ; included; was ->DEL on p10)
        and     #>$7f0000,a
        move    a,x:(r7+$2d)            ; AUX, this block

; ---- MODE: engine select, page-2 slot 7 ($c bits 8-15) -- v2 spine --------
; Same field, same extract, same MSB-aligned convention as BusVerb's MODE
; (modules/busverb/reverb_server.asm). STAGE 1: CLEAN is the only engine, so every value
; -- including whatever an undefined descriptor slot leaves in this word on
; hardware -- runs CLEAN. When PITCH lands, the dispatch compares MSB-aligned
; short immediates on $69, and unknown values must keep falling through to
; CLEAN: a wrong select degrades to the trad delay, never to silence. The
; descriptor's MODE select (RENAMES/DEFAULTS/PAGE2_COUNTS in build_bus.py)
; lands with the second mode. DMODE=n (build_bus.py) substitutes a literal
; at the marker below (dsp_host can also drive companions via -params 7/9/11;
; the override forces the decoded VALUE).
        move    x:(r6+$c),a
        and     #>$ff0000,a             ; slot 6's KNOB field (v6, 4 Sep 2026;
                                        ; slot 7's companion byte before --
                                        ; moved so the panel's page-2 knob
                                        ; editor can set MODE from a screen)
        move    a1,x0
        move    x0,a                    ; A2-clean (AND cleans A1 only); the
                                        ; knob field is already MSB-aligned
                                        ; ($010000 per step), so no shift
; DMODE_OVERRIDE
        move    a,x:(r7+$20)            ; MODE, this block (0 = CLEAN)

; ---- SHIFTED-OUTPUT flag: which modes replace the wet with $24/$25 --------
; GRAIN and REVERSE both leave their result in the shifted-output taps
; are substituted into the wet AFTER the lines are written (stage 2c, so
; nothing shifted can re-enter the feedback). Resolving "is this such a mode"
; ONCE PER BLOCK instead of at the substitution point makes that per-sample
; test a `tst` -- it costs two words fewer than
; the single compare it replaces and does not grow when a fourth mode wants
; the same treatment. Branchless: cmp sets Z, the intervening moves do not
; disturb it, and teq moves a CLEAN register in (never a hand-rolled mask).
        clr     a
        move    x:(r7+$20),b            ; MODE
        move    #$1,x0               ; 1 << 16 = GRAIN
        cmp     x0,b
        move    #>$1,x0
        teq     x0,a
        move    #$2,x0               ; 2 << 16 = REVERSE
        cmp     x0,b
        move    #>$1,x0
        teq     x0,a
        move    a,x:(r7-$16)            ; nonzero = the wet comes from $24/$25
; REVERSE-32K: in REVERSE the two 16K lines are ONE 32K MONO
; ring, so a segment can be 371 ms (2S = 32768 fits, the read preceding the
; write each sample). The L ring's mask goes $7fff, the R line's read and
; write are skipped per sample (they would land in the upper half), PING is
; forced off (R's stale tap would otherwise cross-feed), and the reverse
; output is mono to both channels. CLEAN and GRAIN see the line's own mask
; ($7fff shipping, $3fff in the hatch) and skipR 0.
        clr     a
        move    #$2,x0               ; 2 << 16 = REVERSE
        cmp     x0,b                    ; b = MODE, still
        move    #>$1,x0
        teq     x0,a
        move    a,x:(r7+$23)            ; skipR
        move    #>$7fff,a                                                  ; @B
        move    #>$3fff,a                                                  ; @DEV
        move    #>$7fff,x0
        teq     x0,a                    ; the flag survives the moves
        move    a,x:(r7+$22)            ; the L ring's mask
        move    x:(r7+$2b),a
        move    #$0,x0 
        teq     x0,a
        move    a,x:(r7+$2b)            ; PING 0 in REVERSE
        move    x:(r7+$37),a
        move    #>$7fffff,x0
        teq     x0,a
        move    a,x:(r7+$37)            ; 1 - PING = 1 in REVERSE

; ---- SIZE select (the PTCH slot until v5): the raw index for GRAIN and ----
; REVERSE, both of which read it as a SIZE. Page-2 slot 9's companion field,
; r6+$d LOW bits (bits 8-15). Decoded every block regardless of MODE.
        move    x:(r6+$d),a
        and     #>$7f00,a               ; slot 9's companion field: BITS 8-15
        asr     #$8,a,a
; DINT_OVERRIDE
        move    a1,x0
        move    x0,a                    ; A2-clean
        move    a,x:(r7+$16)            ; the RAW index, 0..3

; ---- MIDI note -> latched note (branch midi, 24 Aug 2026; v5: GRAIN pitch) -
; The ColdFire cave (modules/tempo-sync/tempo_cave.s) stores the host track's
; held MIDI note into the low byte of record halfword 13 every frame: bits
; 8-15 of r6+$1, under TIME's knob field (since 15 Sep 2026; r6+$9 before,
; which was the AMP page 2's first word). 0 = released or no cave. HOLD
; semantics: the last note LATCHES in a core-private Y slot for as long as
; any note has ever arrived -- a track that never sees MIDI behaves exactly
; as before. Since v5 the latched note drives GRAIN's continuous pitch
; (2^((note-84)/12), the OT's 84 = unison) in place of the RATE knob; the
; interval ladder it used to select died with PITCH mode.
        move    x:(r6+$1),a
        and     #>$7f00,a               ; the note, bits 8-15
        asr     #$8,a,a
; DNOTE_OVERRIDE
        move    a1,x0
        move    x0,a                    ; A2-clean
        tst     a
        move    y:>$090a,b              ; latched note (0 = never)
        tne     x0,b                    ; a new note replaces it; a release
                                        ; (0) leaves it -- the moves between
                                        ; tst and tne do not touch the flags
        move    b,y:>$090a
        move    b,x:(r7+$21)            ; this block's note for GRAIN (0 = none)

; (the tape wow -- WOW depth, flutter, the RATE increments at 0901h/0902h --
; went 15 Sep 2026, Sam: the modulation is the LFOs' and the Modulation
; station's, and the crackle gathered around these knobs. Slots 7 and 8
; are GRAIN's SCAT and DENS now, inert in CLEAN and REVERSE.)

; ---- WOW: tape wobble depth, page-2 slot 11 (r6+$e bits 8-15) -----------
; knob<<13 is the depth in Q11.12: two samples per knob step, +-254 at 127.
; Flutter rides at an eighth of it. Peak pitch deviation at 127, from the
; smoothstepped triangle's slope (3*depth*inc/2^22 per sample): ~47 cents
; wow + ~54 cents flutter (computed, not measured; the old '~17 cents'
; figure was the slope without the x3 smoothstep factor). The per-sample
; lag clamp below keeps TIME + wobble inside the line, so no depth is unsafe.
; (Back 20 Sep 2026 in freeze's slot -- Sam: "wow back freeze gone". The
; 15 Sep removal was for the crackle, whose cause was the TIME jump, since
; glided; the wobble rides the same between-samples read.)
        move    x:(r6+$e),a
        and     #>$7f00,a               ; slot 11's companion field: knob<<8
        asl     #$5,a,a                 ; knob<<13
        move    a1,x0
        move    x0,a                    ; A2-clean
        move    a,x:(r7-$1c)            ; WOWD
        asr     #$3,a,a
        move    a1,x0
        move    x0,a
        move    a,x:(r7-$1b)            ; FLTD = WOWD/8

; ---- SPRAY: GRAIN scatter depth (v2 stage 5; on MDEP since v5.1) ----------
; Page-2 slot 7's COMPANION field (r6+$c bits 8-15, the word MODE's knob
; field shares; slot 6 / the knob field until v6). Shifted up
; to knob<<16, which already IS value/128 in Q1.23, so it is used directly
; as a multiplier with no mpy to build it (the MIX/PING trick).
; SPRAY=0 puts every grain on the same read position -- four heads in a
; cluster, the most coherent and least granular end -- and 127 gives the
; full 0..1015-sample scatter. Decoded every block regardless of MODE, like
; PTCH; harmless in the modes that never read it.
        move    x:(r6+$c),a             ; MDEP's companion field: SCATTER in
        and     #>$7f00,a               ; GRAIN (v5.1 -- the mod depth is fixed there)
        move    a1,x0
        move    x0,a                    ; A2-clean (AND cleans A1 only)
        asl     #$8,a,a                 ; -> knob<<16
        move    a,x:(r7+$13)            ; SPRAY, 0 .. ~0.992 as Q23

; ---- REVERSE: segment size, phase step, and the lag floor (v2 stage 6) ----
        move    x:(r7+$16),a            ; select index, 0..127
        move    #>$4,x0
        cmp     x0,a
        tgt     x0,a                    ; 4 and up: the garbage row
        asl     #$3,a,a                 ; row stride 8
        move    n4,x0                   ; the table base (see the block preamble)
        add     x0,a
        move    a,r5
        move    p:(r5)+,a               ; S
        move    a,x:(r7+$17)            ; REVERSE segment length
        move    p:(r5)+,a               ; 2^23 / S
        move    a,x:(r7+$18)            ; REVERSE phase step
        move    p:(r5)+,a               ; 32704 - 2S
        move    a,x:(r7+$d)             ; the cap for this size
        move    a,x:(r7-$1f)            ; ... kept for the loop ($d is its
                                        ; lag0 scratch): REVERSE re-derives
                                        ; RLAG0 per sample from the TIME ramp
        move    p:(r5)+,a               ; G - 1
        move    a,x:(r7-$11)            ; GRAIN mask
        move    p:(r5)+,a               ; G/4
; GRAINOFF
        move    a,x:(r7-$10)            ; G/4, the grain-to-grain offset
        move    p:(r5)+,a               ; 2^(23-k)
        move    a,x:(r7-$f)             ; GRAIN window multiplier
        move    p:(r5),a                ; 2^(32-k)
        move    a,x:(r7-$a)             ; GRAIN pitch-ceiling multiplier
        move    x:(r7+$2c),a            ; TIME
        move    x:(r7+$d),x0
        sub     x0,a                    ; sub/branch, not cmp (the
        tst     a                       ; cmp-encodes-as-max trap family)
        ble     rlagok
        clr     a                       ; over the cap: excess -> 0
rlagok:
        add     x0,a                    ; min(TIME, cap)
        move    a,x:(r7+$19)            ; RLAG0, the reversed chunk's lag floor

; ---- GRAIN v5 per-block decode (BusDelay v5) ----------------
; Nimbus's grain family from the SIZE select ($5f), in REVERSE's index order
; so one select reads the same way in both modes: 0 = 46 ms (G 2048),
; 1 = 93 ms (4096, the default), 2 = 23 ms (1024), 3 = 186 ms (8192). Per
; size: the mask G-1, G/4 (grain-to-grain offset), the one-multiply window's
; multiplier 2^(23-k) (modules/nimbus/nimbus_grain.asm: 2^(23-k), NOT
; 2^(24-k) -- the a0 trap) and 2^(32-k), which turns the lag into the pitch
; ceiling below with one mpy. Per block, so the loop pays nothing. All four
; come from the table read above (the right half of the SIZE row).
; the read distance base: lag + G + 2, with lag = min(TIME, 12286 - mask).
; A grain at unity reads W - (lag + s + G + 2 - phase): at least lag + s + 2
; behind the write head and at most lag + s + G + 1 behind it; s tops out at
; 4095, so lag + 4095 + G + 1 must stay inside the 16,384-word line. ⚠️ THAT
; BOUND IS LOAD-BEARING: past it a head reads across the write pointer, a
; full-scale discontinuity once per grain. sub/tst, not cmp (the
; cmp-encodes-as-max trap family).
        move    x:(r7-$11),b            ; mask = G - 1
        move    #>28670,a               ; 32767 - 4096 - 1                 ; @B
        move    #>12286,a               ; 16383 - 4096 - 1                 ; @DEV
        sub     b,a                     ; the lag cap for this G
        move    a,x:(r7-$e)            ; park the cap
        move    x:(r7+$2c),a            ; TIME
        move    x:(r7-$e),x0
        sub     x0,a
        tst     a
        ble     gvlag                   ; TIME <= cap: keep it
        clr     a                       ; over: excess -> 0, i.e. clamp
gvlag:
        add     x0,a                    ; min(TIME, cap) = lag
        move    a,x:(r7-$d)            ; park lag for the pitch ceiling
        move    x:(r7-$11),x0
        add     x0,a                    ; + G - 1
        add     #>$3,a                  ; + 3 = lag + G + 2
        move    a,x:(r7-$e)            ; the read distance base
; ---- GRAIN PITCH (v5): rstep, the grain's read advance per sample, Q9 ----
; 512 = unity. From the RATE knob, +-2 octaves: r = 2^((RATE-64)/32), 64 =
; unison, 96 = +12, 32 = -12. From a latched MIDI note when one has ever
; arrived ($6a, the cave's r6+$1 low byte): r = 2^((note-84)/12), clamped to
; +-24 semitones -- the same law the retired PITCH mode drove from the note.
; 2^f for f in [0,1) is a cubic, 1 + f(0.6931 + f(0.2402 + 0.0558 f)), error
; < 0.2 cent; the octave part is a shift. Both paths meet at gvoct with
; oct in a (-2..2, sign-extended) and f in x:(r7+$3d) (Q23).
        move    x:(r7+$21),a
        tst     a
        beq     gvknob
; note path: st = note - 84 clamped to +-24; oct' = (st + 24) / 12 by ladder
        move    #>84,x0
        sub     x0,a                    ; st
        move    #>$ffffe8,x0            ; -24
        cmp     x0,a
        tlt     x0,a
        move    #>24,x0
        cmp     x0,a
        tgt     x0,a
        add     x0,a                    ; st + 24, 0..48
        move    a,x:(r7-$c)            ; park (integer)
        move    #$0,b                    ; oct'
        move    #>12,x0
        cmp     x0,a                    ; the ladder: subtract 12 while >= 12
        blt     gvn0
        sub     x0,a
        move    #>1,b
        cmp     x0,a
        blt     gvn0
        sub     x0,a
        move    #>2,b
        cmp     x0,a
        blt     gvn0
        sub     x0,a
        move    #>3,b
        cmp     x0,a
        blt     gvn0
        sub     x0,a
        move    #>4,b
gvn0:
        asl     #$13,a,a                ; rem << 19 = rem/16 in Q23 (<= 0.69)
        move    a1,x0
        move    #>$555555,y1            ; 2/3
        mpy     x0,y1,a                 ; rem/24
        asl     #$1,a,a                 ; rem/12 = f, Q23
        move    a1,x0
        move    x0,a
        move    a,x:(r7-$c)            ; f, Q23
        move    b,a
        move    #>2,x0
        sub     x0,a                    ; oct = oct' - 2
        bra     gvoct
gvknob:
; knob path: e = RATE - 64 (-64..63); oct = e >> 5; f = (e & 31) << 18
        move    x:(r6+$e),a             ; PTCH: page-2 slot 10's KNOB field
                                        ; (one-aux re-slot; was
                                        ; page-1 slot 5, which is MIX now),
        and     #>$7f0000,a             ; a plain knob, val << 16
        move    a1,x0
        move    x0,a
        asr     #$10,a,a                ; the integer knob 0..127
        move    #>64,x0
        sub     x0,a                    ; e
        move    a,x:(r7-$c)            ; park e
        and     #>$1f,a
        asl     #$12,a,a                ; (e & 31) << 18 = f in Q23
        move    a1,x0
        move    x0,a
        move    a,x:(r7+$0)            ; f, Q23 (park)
        move    x:(r7-$c),a
        asr     #$5,a,a                 ; oct = e >> 5, -2..1 (arithmetic)
        move    a1,x0
        move    x0,a
        move    x:(r7+$0),x0
        move    x0,x:(r7-$c)           ; f into its slot
gvoct:
        move    a,x:(r7+$0)            ; park oct
; 2^f - 1 = f * (c1 + f * (c2 + c3 * f))
        move    x:(r7-$c),x0           ; f
        move    #>$072470,y1            ; c3 = 0.0558
        mpy     x0,y1,a
        add     #>$1ebfce,a             ; + c2 = 0.2402
        move    a,y1
        mpy     x0,y1,a                 ; f * (c2 + c3 f)
        add     #>$58b90c,a             ; + c1 = 0.6931
        move    a,y1
        mpy     x0,y1,a                 ; 2^f - 1, Q23, 0 .. 0.99
        asr     #$e,a,a                 ; * 512 -> Q9 integer 0..511
        move    a1,x0
        move    x0,a
        add     #>512,a                 ; rstep at oct 0: 512 .. 1023
; the octave: shift by oct
        move    a,x:(r7-$b)
        move    x:(r7+$0),a
        tst     a
        beq     gvrdone
        move    #>1,x0
        cmp     x0,a
        beq     gvr1
        move    #>2,x0
        cmp     x0,a
        beq     gvr2
        move    #>$ffffff,x0            ; -1
        cmp     x0,a
        beq     gvrm1
        move    x:(r7-$b),a            ; -2
        asr     #$2,a,a
        bra     gvrst
gvrm1:
        move    x:(r7-$b),a
        asr     #$1,a,a
        bra     gvrst
gvr1:
        move    x:(r7-$b),a
        asl     #$1,a,a
        bra     gvrst
gvr2:
        move    x:(r7-$b),a
        asl     #$2,a,a
gvrst:
        move    a1,x0
        move    x0,a
        move    a,x:(r7-$b)
gvrdone:
; ---- the pitch CEILING: a grain running faster than the write head needs
; room in front of it. Its read starts lag + s + G + 2 behind the head and
; closes on it by G*(r-1) over its life, so r - 1 <= 1 + lag/G keeps it
; behind. rmax = 1024 + lag * 2^(9-k) via the per-size 2^(32-k) constant,
; one mpy; rstep is clamped to it, so a short TIME on a long grain quietly
; limits how far UP the pitch reaches (+12 always fits). The per-sample
; distance clamps in the reader are the belt to this brace.
        move    x:(r7-$d),x0           ; lag (integer, 0..12285)
        move    x:(r7-$a),y1           ; 2^(32-k)
        mpy     x0,y1,a                 ; a1 = lag * 2^(9-k)
        move    a1,x0
        move    x0,a
        add     #>1024,a                ; rmax
        move    a,x0
        move    x:(r7-$b),a
        cmp     x0,a
        tgt     x0,a                    ; rstep = min(rstep, rmax)
        move    a,x:(r7-$b)
        move    x:(r6+$d),a             ; MRAT's knob field: DENSITY in GRAIN
        and     #>$7f0000,a             ; (v5.1 -- the mod rate is fixed there)
        asr     #$14,a,a                ; knob >> 4 = dens3, 0..7
        move    a1,x0
        move    x0,a
        move    a,x:(r7-$d)            ; dens3 (lag's park is consumed)
        move    #>7,b
        sub     a,b                     ; 7 - dens3
        move    b1,x0
        move    x0,b
        asl     #$14,b,b                ; (7-dens3) << 20 = n/8 in Q23
        move    b1,x0
        move    #>$492492,y1            ; 8/14 in Q23
        mpy     x0,y1,b                 ; n/14 (x0,y1 -- a SIGNED encode)
        move    #$40,x0  
        add     x0,b                    ; + 1/2
        move    b1,x0
        move    x0,b
        move    b,x:(r7-$c)            ; GRAIN makeup coeff, this block

; ---- rebuild both line pointers from saved phase --------------------------
; Same A2-clean discipline as dsp/reverb89.asm's phase reload: garbage with
; bit 23 set would sign-extend and saturate the following move a,rN to
; $800000, which hangs the bus forever (the two-track-freeze mechanism).
; THE LINE BASES LIVE IN n1 / n2 FOR THE BLOCK: a base add is
; `move a1,rN / move (rN)+nN` (a1 straight into the pointer: no limiter, so
; no A2 to clean), a line read is `move a1,r5 / move y:(r5+n5),a` with n5
; staged from n1 or n2 at the site. The $68 stash and modtap's $30 staging
; slot went with their readers. n1/n2 were unused; the reverb writes n1 too.
        move    x:(r7+$27),a            ; LineL phase
        move    x:(r7+$22),x0           ; the L ring's mask ($7fff in REVERSE)
        and     x0,a
        move    x:(r7-$18),x0           ; LineL base
        move    x0,n1                   ; ... for the block
        move    a1,r1
        move    (r1)+n1                 ; LineL write pointer = base + phase

        move    #>$4000,a               ; LineR base: the private region   ; @B
        move    x:(r7-$18),a            ; LineR base = LineL base + 0x4000 ; @DEV
        move    #>$4000,x0                                                 ; @DEV
        add     x0,a                                                       ; @DEV
        move    a,n2                    ; ... for the block

        move    x:(r7+$28),a            ; LineR phase
        move    #>$7fff,x0                                                 ; @B
        move    #>$3fff,x0                                                 ; @DEV
        and     x0,a
        move    a1,r2                   ; LineR write PHASE -- r2 stays
                                        ; base-relative: the private base is
                                        ; only 16K-aligned, so the absolute
                                        ; pointer cannot be masked (the L
                                        ; base is 32K-aligned and r1 can);
                                        ; n2 supplies the base at the write

; v2 SPINE: NO AGU MODULO. m1/m2 stay at the linear invariant ($ffffff);
; the TIME-behind read address is computed per sample and the write
; pointers are wrapped by hand below. n1/n2 are unused.

        move    #$1,n0                  ; the frame stride (a byte lands
        do      n7,>dlyend              ; LOW in an address register)

; ---- input: own dry mono sum + shared DELAY bus accumulator --------------
        move    x:(r0),a
        move    x:(r0+n0),x0
        add     x0,a
        asr     #$1,a,a
; ---- v3 stage 1: OUR OWN DRY IS JUST ANOTHER CLIENT ----------------------
        move    a,x0                    ; own dry mono
        move    x:(r7+$2d),y1           ; IN, this track's send level
        mpy     x0,y1,a                 ; our contribution to the bus
        asr     #$3,a,a                 ; the 3 bits of headroom EVERY writer
                                        ; applies, so N of them cannot rail
                                        ; the sum before it is divided
        move    a,x:(r7+$34)            ; park our share
        move    x:(r7+$1a),a            ; this sample's ACC read address
        move    a,r5
        move    y:(r5),x0               ; last block's fully-summed sends
        move    x:(r7+$34),a
        add     x0,a                    ; the full sum, our own share included
        move    a,x0
        move    x:(r7+$36),y1           ; this block's bus gain 1/sqrt(N); N
                                        ; COUNTS US (see the resolve block)
        mpy     x0,y1,a                 ; hold total drive constant vs N --
                                        ; signed (2000c0): x0 is a bus sample
                                        ; and can be negative, y1 (the gain) never
        asl     #$3,a,a                 ; undo the writers' 3-bit headroom
        move    a,x:(r7+$34)            ; x_in = the averaged bus, us included
        move    x:(r7+$1a),a
        add     #>$1,a
        move    a,x:(r7+$1a)            ; advance ACC read pointer

; ---- the FEEDBACK LOOP's taps: ALWAYS the unshifted read (v2 stage 2c) ----
; NON-CASCADING PITCH. Until stage 2c the shifted taps WERE the loop's taps,
; so every repeat was shifted again: repeat n had been through the shifter n
; times and carried n generations of splice artifact. That compounding, not
; the splice itself, is most of what an ear calls "machine" -- and BusVerb
; hit exactly this and fixed it the same way (its shimmer deliberately cut
; its own cascade; see modules/busverb/reverb_server.asm's SHIMMER block).
;
; Now the loop recirculates the CLEAN tap and the shifter sits on the OUTPUT
; only, so every repeat is shifted exactly ONCE: a fixed-interval harmoniser
; on the delay's output rather than a climbing ladder. TONE, PING, FDBK and
; the write-back are all mode-blind and bit-identical to CLEAN's; the
; substitution happens after the lines are written (below), so nothing
; shifted ever re-enters the loop.
;
; ⚠️ The climb is GONE by construction -- +12 no longer walks up in octaves.
; That was the Crystal behaviour stage 2 chose on purpose; it is exactly
; what compounds the artifact, and the ear rejected it (12 Aug). If a climb
; is ever wanted back it belongs on a select, not as the only topology.
;
; ---- LOOP taps: the read at lag TIME + wobble, EVERY mode -----------------
; The loop's recirculating tap is the same in every mode since stage 2c, so
; the wobble belongs to the INSTRUMENT, not to a mode. Two LFOs at a fixed
; non-integer ratio (wow $98/sample = 0.8 Hz, flutter $56d = 7.3 Hz) never
; lock; WOW 0 gives a wobble of exactly 0, so the lag is the glide's state
; and the read is the glide's own, bit for bit.
        move    x:(r7-$22),a            ; wow phase
        add     #>$98,a
        and     #>$7fffff,a
        move    a1,x0
        move    x0,a                    ; A2-clean; boot garbage dies here
        move    a,x:(r7-$22)
        bsr     smoothw                 ; s = g^2*(3-2g), 0..1
        move    a1,x0
        move    x:(r7-$1c),y1           ; WOWD
        mpy     x0,y1,a                 ; s*depth
        asl     #$1,a,a
        move    x:(r7-$1c),x0
        sub     x0,a                    ; depth*(2s-1): centred, +-depth
        move    a,x:(r7-$20)            ; park the wow

        move    x:(r7-$21),a            ; flutter phase
        add     #>$56d,a
        and     #>$7fffff,a
        move    a1,x0
        move    x0,a
        move    a,x:(r7-$21)
        bsr     smoothw
        move    a1,x0
        move    x:(r7-$1b),y1           ; FLTD
        mpy     x0,y1,a
        asl     #$1,a,a
        move    x:(r7-$1b),x0
        sub     x0,a
        move    x:(r7-$20),x0
        add     x0,a                    ; wobble = wow + flutter, Q11.12 signed
; ---- this sample's lag: the glided TIME plus the wobble, Q8, kept inside
; the line: never nearer the write head than 8, never past the ring's oldest
; valid sample (32760; the hatch's 16376). Pinning at an extreme is a flat
; spot in the wobble; a wrap would be a full-lap discontinuity.
        asr     #$4,a,a                 ; Q11.12 -> Q8
        move    x:(r7-$23),b            ; the ramped TIME, Q8
        move    x:(r7+$1b),x0           ; this block's per-sample increment
        add     x0,b
        move    b,x:(r7-$23)            ; ... advanced for the next sample
        add     b,a                     ; + the wobble
        move    #>$800,x0               ; 8 samples
        cmp     x0,a
        tlt     x0,a
        move    #>$7ff800,x0            ; 32760 samples                     ; @B
        move    #>$3ff800,x0            ; 16376 samples                     ; @DEV
        cmp     x0,a
        tgt     x0,a
        move    a,b
        asr     #$8,a,a
        move    a,x:(r7-$1e)            ; lag, integer samples
        move    b,a
        and     #>$ff,a                 ; the low 8 bits (a is positive: a2 stays clean)
        asl     #$f,a,a                 ; -> Q23, 0 .. 255/256
        move    a,x:(r7-$1d)            ; fraction
; ---- Line L: the read at the lag --------------------------------------
        move    r1,a
; lerp read rolled into modtap: line base staged in n5, the
; pointer arrives in a, the tap returns in a. Same word-saving move as satdrv.
        move    n1,n5
        bsr     modtap
        move    a,x:(r7+$30)          ; dL -- the LOOP's own tap

; ---- Line R: the read at lag TIME --------------------------------------
        move    x:(r7+$23),a            ; skipR (REVERSE-32K): R's read would
        tst     a                       ; land in the mono ring's upper half
        bne     rskipr
        move    r2,a
        move    n2,n5
        bsr     modtap
        move    a,x:(r7+$31)          ; dR
rskipr:
; ---- MODE dispatch: PITCH additionally computes the SHIFTED OUTPUT taps ---
; 0 and every unknown value run the loop's clean taps alone -- a wrong select
; degrades to the trad delay, never to silence (the stage-1 rule). The
; compare is the safe `cmp x0,a` form.
; MODEFORK_BEGIN -- cycle_count.py: BEGIN..first MID is the dispatch and
; always runs; each MID..next is one mutually exclusive alternative, and the
; tool charges dispatch + the WORST alternative, never every engine summed.
        move    x:(r7+$20),a
        move    #$1,x0               ; 1 << 16 = GRAIN (v5 numbering)
        cmp     x0,a
        beq     gmode
        move    #$2,x0               ; 2 << 16 = REVERSE
        cmp     x0,a
        beq     rmode
        bra     pdone                   ; CLEAN, and every unknown value
; MODEFORK_MID -- alternative 1: GRAIN

gmode:
; the read distance base per sample from the TIME ramp (20 Sep 2026): the
; per-block base stepped every reader by the whole glide step at each block
; edge -- the click per block the loop's tap had. Same recipe as the block's:
; min(TIME, 28670 - mask) + G + 2, on this sample's ramped TIME. The block's
; own write of $-e is the first sample's starting point and is overwritten.
        move    x:(r7-$23),a            ; the ramped TIME, Q8 (this sample's)
        asr     #$8,a,a
        move    #>28670,b               ; 32767 - 4096 - 1                 ; @B
        move    #>12286,b               ; 16383 - 4096 - 1                 ; @DEV
        move    x:(r7-$11),x0           ; mask = G - 1
        sub     x0,b                    ; the lag cap for this G
        move    b,x0
        cmp     x0,a
        tgt     x0,a                    ; min(TIME, cap) = lag
        move    x:(r7-$11),x0
        add     x0,a                    ; + G - 1
        add     #>$3,a                  ; + 3 = lag + G + 2
        move    a,x:(r7-$e)            ; the read distance base
; ---- PRNG advance: BusDelay's 23-bit xorshift 15/15/8 -------------------
        move    x:(r7-$31),a            ; state
        move    a1,x0
        asl     #$f,a,a
        and     #>$7fffff,a
        eor     x0,a                    ; x ^= (x << 15)
        move    a1,x0
        move    x0,a
        asr     #$f,a,a                 ; state is always positive, so the
        eor     x0,a                    ; arithmetic shift IS a logical one
        move    a1,x0
        move    x0,a
        asl     #$8,a,a
        and     #>$7fffff,a
        eor     x0,a                    ; x ^= (x << 8)
        move    a1,x0
        move    x0,a                    ; A2 clean before the store
        move    a,x:(r7-$31)
; ---- this sample's scatter candidate: prng * SPRAY -> 0..4095 samples ----
        move    a,x0                    ; state, 0 .. ~1.0 (always positive)
        move    x:(r7+$13),y1           ; SPRAY, Q23
        mpy     x0,y1,a                 ; both operands non-negative
        asr     #$b,a,a                 ; fraction -> integer samples
        and     #>$fff,a                ; belt and braces: it IS 0..4095
        move    a1,x0
        move    x0,a
        move    a,x:(r7+$f)
; ---- this sample's window-multiplier candidate: 2^(23-k), or 0 if muted --
        move    x:(r7-$31),b
        asr     #$5,b,b
        and     #>$7,b
        move    b1,x1                   ; bits, 0..7 (x1 is free in this mode)
        clr     b                       ; the muted form, BEFORE the compare
        move    x:(r7-$d),a            ; dens3
        sub     x1,a                    ; N SET == muted
        move    x:(r7-$f),x0           ; the live multiplier
        tpl     x0,b                    ; not muted -> take it
        move    b,x:(r7+$10)
; ---- age advance, masked by G-1 (also swallows size changes) -------------
        move    x:(r7-$17),a
        add     #>$1,a
        move    x:(r7-$11),x0
        and     x0,a
        move    a1,x0
        move    x0,a
        move    a,x:(r7-$17)
        clr     b                       ; wet L accumulates in b
; ---- READER, line L: four grains, ROLLED (v5) ----------------------------
; Records of THREE words at r7+$40: s (latched scatter), w (window
; multiplier, 0 = muted), acc (read advance, Q14.9). Every latch is a Tcc
; reading the ONE `tst` of this grain's phase, with nothing but moves between
; them (the GRAIN 5d trap); the `add` that advances acc comes AFTER the last
; of them. Phase walks $5d by G/4 per trip; the wet sum lives in x:(r7+$1e)
; because b is the latch register inside the body.
        move    r7,a                    ; records at raw $40 = r7 - 9
        sub     #>$9,a                  ; (r7 is rebased by $49 here)
        move    a,r4                    ; (m4 is linear from the block preamble)
        move    x:(r7-$17),x0
        move    x0,x:(r7+$14)           ; cursor = age (grain 0's phase)
        move    n1,n5                   ; this line's base for the reads
        clr     a
        move    a,x:(r7-$2b)
; GRAINCNT
        do      #4,>gvlz
        move    x:(r7+$14),a            ; this grain's phase
        tst     a                       ; Z SET == its wrap
        move    a,x1                    ; phase, kept for the distance
        move    x:(r7+$f),x0           ; candidate scatter
        move    x:(r4),b
        teq     x0,b
        move    b,x:(r4)+               ; s
        move    b,x:(r7-$2c)            ; park s
        move    x:(r7+$10),x0           ; candidate multiplier (0 = muted)
        move    x:(r4),b
        teq     x0,b
        move    b,x:(r4)+               ; w
        move    b,y1                    ; w, the window multiplier
        move    #$0,x0 
        move    x:(r4),b
        teq     x0,b                    ; acc restarts at the wrap
        move    x:(r7-$b),x0           ; rstep
        add     x0,b                    ; acc += rstep
        move    b,x:(r4)+               ; -> the next record
        move    a,x0                    ; phase
        mpy     x0,y1,a                 ; a0 = wrap(2*phase/G), signed Q23
        move    a0,x0
        move    x0,a                    ; reloaded clean: A2 consistent
        abs     a
        move    a,x:(r7-$30)            ; park the window gain
        move    b,a                     ; acc
        and     #>$1ff,a                ; the fraction
        asl     #$e,a,a                 ; -> Q23
        move    a1,x0
        move    x0,a
        move    a,x:(r7-$2f)            ; park frac
        move    b,a
        asr     #$9,a,a                 ; integer samples advanced
        move    a1,x0
        move    x:(r7-$e),a            ; lag + G + 2
        sub     x0,a                    ; - advance
        move    x:(r7-$2c),x0
        add     x0,a                    ; + s
        add     x1,a                    ; + phase = dist. ⚠️ THE PHASE TERM IS
                                        ; WHAT MAKES UNITY A FIXED TAP: W moves
                                        ; one sample per sample, so a distance
                                        ; that does not grow with the phase
                                        ; reads at 1 + r, an octave up at
                                        ; "unity" (measured: 955 Hz
                                        ; for 438 in). Nimbus's geometry has the
                                        ; same term missing -- see its README.
        move    #>$2,x0
        cmp     x0,a                    ; never the head's own slot ...
        tlt     x0,a
        move    #>$7fff,x0                                                 ; @B
        move    #>$3fff,x0                                                 ; @DEV
        cmp     x0,a                    ; ... and never past the line's end
        tgt     x0,a                    ; (a low pitch on a long grain pins
                                        ; at the oldest sample: a flat spot,
                                        ; not a wrap)
        move    a,x0
        move    r1,a                ; line L write pointer
        sub     x0,a                    ; W - dist
        and     #>$7fff,a                                                  ; @B
        and     #>$3fff,a                                                  ; @DEV
        move    a1,x0
        move    x0,a
        move    a,x:(r7-$2d)            ; park the read phase
        move    a,r5
        move    y:(r5+n5),a             ; t0 (line L base in n5)
        move    a,x:(r7-$2e)
        move    x:(r7-$2d),a
        add     #>$1,a                  ; one sample NEWER
        and     #>$7fff,a                                                  ; @B
        and     #>$3fff,a                                                  ; @DEV
        move    a1,r5
        move    y:(r5+n5),a             ; t1
        move    x:(r7-$2e),x0
        sub     x0,a                    ; t1 - t0, signed
        move    a1,x0                   ; -> FIRST mpy operand
        move    x:(r7-$2f),y1           ; frac
        mpy     x0,y1,a
        move    x:(r7-$2e),x0
        add     x0,a                    ; tap = t0 + frac*(t1-t0)
        move    a,x0                    ; LIMITING move
        move    x:(r7-$30),y1           ; window gain
        mpy     x0,y1,a
        move    x:(r7-$2b),b
        add     b,a
        move    a,x:(r7-$2b)       ; wet L +=
        move    x:(r7+$14),a            ; next grain: a quarter further round
        move    x:(r7-$10),x0
        add     x0,a
        move    x:(r7-$11),x0
        and     x0,a
        move    a1,x0
        move    x0,a
        move    a,x:(r7+$14)
gvlz:
; ---- wet L = sum of four * makeup --------------------------------------
; four windows at quarter offsets sum to exactly 2, so the makeup coeff's
; 1/2 at full density is unity and its 1.0 top is +6 dB for the sparsest
; gate -- the v2 arithmetic, kept.
        move    x:(r7-$2b),x0
        move    x:(r7-$c),y1           ; makeup coeff
        mpy     x0,y1,b                 ; (a +6 dB asl sat here for a day, 12 Sep
                                        ; 2026, sized on the clobbered reader:
                                        ; whole, GRAIN is +2.1 dB RMS / +6.6 dB
                                        ; peak over CLEAN with it, peaks level
                                        ; without -- the level a return wants)
; GRAINMK
        move    b,x:(r7-$25)            ; shifted OUTPUT tap L
; ---- READER, line R: four grains, ROLLED (v5) ----------------------------
; Records of THREE words at r7+$4c: s (latched scatter), w (window
; multiplier, 0 = muted), acc (read advance, Q14.9). Every latch is a Tcc
; reading the ONE `tst` of this grain's phase, with nothing but moves between
; them (the GRAIN 5d trap); the `add` that advances acc comes AFTER the last
; of them. Phase walks $5d by G/4 per trip; the wet sum lives in x:(r7+$1f)
; because b is the latch register inside the body.
        move    r7,a                    ; records at raw $4c = r7 + 3
        add     #>$3,a                  ; (r7 is rebased by $49 here)
        move    a,r4
        move    x:(r7-$17),x0
        move    x0,x:(r7+$14)           ; cursor = age (grain 0's phase)
        move    n2,n5                   ; this line's base for the reads
        clr     a
        move    a,x:(r7-$2a)
; GRAINCNT
        do      #4,>gvrz
        move    x:(r7+$14),a            ; this grain's phase
        tst     a                       ; Z SET == its wrap
        move    a,x1                    ; phase, kept for the distance
        move    x:(r7+$f),x0           ; candidate scatter
        move    x:(r4),b
        teq     x0,b
        move    b,x:(r4)+               ; s
        move    b,x:(r7-$2c)            ; park s
        move    x:(r7+$10),x0           ; candidate multiplier (0 = muted)
        move    x:(r4),b
        teq     x0,b
        move    b,x:(r4)+               ; w
        move    b,y1                    ; w, the window multiplier
        move    #$0,x0 
        move    x:(r4),b
        teq     x0,b                    ; acc restarts at the wrap
        move    x:(r7-$b),x0           ; rstep
        add     x0,b                    ; acc += rstep
        move    b,x:(r4)+               ; -> the next record
        move    a,x0                    ; phase
        mpy     x0,y1,a                 ; a0 = wrap(2*phase/G), signed Q23
        move    a0,x0
        move    x0,a                    ; reloaded clean: A2 consistent
        abs     a
        move    a,x:(r7-$30)            ; park the window gain
        move    b,a                     ; acc
        and     #>$1ff,a                ; the fraction
        asl     #$e,a,a                 ; -> Q23
        move    a1,x0
        move    x0,a
        move    a,x:(r7-$2f)            ; park frac
        move    b,a
        asr     #$9,a,a                 ; integer samples advanced
        move    a1,x0
        move    x:(r7-$e),a            ; lag + G + 2
        sub     x0,a                    ; - advance
        move    x:(r7-$2c),x0
        add     x0,a                    ; + s
        add     x1,a                    ; + phase = dist. ⚠️ THE PHASE TERM IS
                                        ; WHAT MAKES UNITY A FIXED TAP: W moves
                                        ; one sample per sample, so a distance
                                        ; that does not grow with the phase
                                        ; reads at 1 + r, an octave up at
                                        ; "unity" (measured: 955 Hz
                                        ; for 438 in). Nimbus's geometry has the
                                        ; same term missing -- see its README.
        move    #>$2,x0
        cmp     x0,a                    ; never the head's own slot ...
        tlt     x0,a
        move    #>$7fff,x0                                                 ; @B
        move    #>$3fff,x0                                                 ; @DEV
        cmp     x0,a                    ; ... and never past the line's end
        tgt     x0,a                    ; (a low pitch on a long grain pins
                                        ; at the oldest sample: a flat spot,
                                        ; not a wrap)
        move    a,x0
        move    r2,a                ; line R write pointer
        sub     x0,a                    ; W - dist
        and     #>$7fff,a                                                  ; @B
        and     #>$3fff,a                                                  ; @DEV
        move    a1,x0
        move    x0,a
        move    a,x:(r7-$2d)            ; park the read phase
        move    a,r5
        move    y:(r5+n5),a             ; t0 (line R base in n5)
        move    a,x:(r7-$2e)
        move    x:(r7-$2d),a
        add     #>$1,a                  ; one sample NEWER
        and     #>$7fff,a                                                  ; @B
        and     #>$3fff,a                                                  ; @DEV
        move    a1,r5
        move    y:(r5+n5),a             ; t1
        move    x:(r7-$2e),x0
        sub     x0,a                    ; t1 - t0, signed
        move    a1,x0                   ; -> FIRST mpy operand
        move    x:(r7-$2f),y1           ; frac
        mpy     x0,y1,a
        move    x:(r7-$2e),x0
        add     x0,a                    ; tap = t0 + frac*(t1-t0)
        move    a,x0                    ; LIMITING move
        move    x:(r7-$30),y1           ; window gain
        mpy     x0,y1,a
        move    x:(r7-$2a),b
        add     b,a
        move    a,x:(r7-$2a)       ; wet R +=
        move    x:(r7+$14),a            ; next grain: a quarter further round
        move    x:(r7-$10),x0
        add     x0,a
        move    x:(r7-$11),x0
        and     x0,a
        move    a1,x0
        move    x0,a
        move    a,x:(r7+$14)
gvrz:
; ---- wet R -------------------------------------------------------------
        move    x:(r7-$2a),x0
        move    x:(r7-$c),y1
        mpy     x0,y1,b                 ; (a +6 dB asl sat here for a day, 12 Sep
                                        ; 2026, sized on the clobbered reader:
                                        ; whole, GRAIN is +2.1 dB RMS / +6.6 dB
                                        ; peak over CLEAN with it, peaks level
                                        ; without -- the level a return wants)
; GRAINMK
        move    b,x:(r7-$24)            ; shifted OUTPUT tap R
        bra     pdone
; MODEFORK_MID -- alternative 2: REVERSE

; ---- REVERSE: windowed backward reads (v2 stage 6) -----------------------
; The cheapest mode left, and cheap only BECAUSE the crossfade machinery
; already exists -- it is the same two complementary heads PITCH uses, with
; the head walking BACKWARDS through the line instead of drifting.
;
; THE MECHANISM, and why it needs no lerp. A phase runs 0..2^23 and the
; segment-local sample index is p = phase*S/2^23, which is EXACTLY what a
; fractional mpy of the phase by S computes -- so p advances by exactly 1
; per sample and the read lands on a whole sample every time. Contrast
; PITCH and TAPE, where the read sits between samples and the lerp is
; mandatory (the truncation floor that cost the first shimmer). Reverse at
; unity rate is the one moving read in this file that is exact.
;
;   read = wr - (LAG0 + 2p)
;
; and since wr advances by 1 per sample while p does too, the read address
; DECREASES by exactly 1 per sample: backwards, at unity speed. The 2 is
; not a fudge -- it is the write pointer running away from the read.
;
; Two heads half a segment apart, complementary-triangle windowed on the
; phase and smoothstepped, so g0 + g1 == 1 EXACTLY at every phase and the
; splice at each segment restart happens where that head's gain is 0. Both
; heads and BOTH LINES share one phase: each line reads its own buffer at
; the same lag, and the lines already hold different material (the input
; enters L only and crosses over through PING), so nothing is gained by
; giving them separate phases and one r7 slot is saved.
;
; OUTPUT ONLY, never in the loop -- stage 2c. A reverse read HAS a splice,
; so recirculating it would compound one per repeat, which is exactly the
; mechanism the PITCH ear pass rejected.
;
; mpy orientation: the possibly-negative operand (the tap) is always x0, the
; audited-signed `mpy x0,y1` form; y1 carries S or a window gain, both
; non-negative.
rmode:
; RLAG0 per sample from the TIME ramp (20 Sep 2026): the per-block value
; below stepped the heads by the whole glide step at every block edge --
; the same click per block the loop's tap had; min(TIME, cap), the
; per-block recipe, on this sample's ramped TIME.
        move    x:(r7-$23),a            ; the ramped TIME, Q8 (this sample's)
        asr     #$8,a,a
        move    x:(r7-$1f),x0           ; the cap, 32704 - 2S
        cmp     x0,a
        tgt     x0,a                    ; min(TIME, cap)
        move    a,x:(r7+$19)            ; RLAG0 for this sample
        move    x:(r7+$15),a            ; segment phase
        move    x:(r7+$18),x0           ; step = 2^23 / S
        add     x0,a
        and     #>$7fffff,a             ; wrap: one segment
        move    a1,x0
        move    x0,a                    ; A2-clean; boot garbage dies here
        move    a,x:(r7+$15)
; ---- head 0: lag and window from the phase -------------------------------
        move    a1,x0                   ; phase
        move    x:(r7+$17),y1           ; S, non-negative
        mpy     x0,y1,a                 ; p = phase*S/2^23, EXACT (the
                                        ; product is a whole multiple of
                                        ; 2^23, so nothing is rounded)
        asl     #$1,a,a                 ; 2p -- the write pointer's run-away
        move    a1,x0
        move    x:(r7+$19),a            ; RLAG0
        add     x0,a
        move    a,x:(r7+$d)            ; lag0, shared by both lines
        move    x:(r7+$15),a            ; phase again
        bsr     smoothw                 ; s = g^2*(3-2g) (v6 roll)
        move    a1,x0
        move    x0,a
        move    a,x:(r7+$e)            ; g0
; ---- head 1: half a segment further on, same machinery -------------------
        move    x:(r7+$15),a
        move    #$40,x0  
        add     x0,a
        and     #>$7fffff,a
        move    a1,x0
        move    x0,a
        move    a,x:(r7+$12)            ; park phase1
        move    a1,x0
        move    x:(r7+$17),y1
        mpy     x0,y1,a
        asl     #$1,a,a
        move    a1,x0
        move    x:(r7+$19),a
        add     x0,a
        move    a,x:(r7+$f)            ; lag1
        move    x:(r7+$12),a
        bsr     smoothw                 ; (v6 roll)
        move    a1,x0
        move    x0,a
        move    a,x:(r7+$10)            ; g1, and g0+g1 == 1 exactly
; ---- Line L: both heads, windowed and summed -----------------------------
        move    n1,n5                   ; the L base (the ring's, in REVERSE)
        move    r1,a                    ; LineL write pointer
        move    x:(r7+$d),x0           ; lag0
        sub     x0,a
        and     #>$7fff,a               ; read phase in the 32K MONO ring
        move    a1,r5                   ; (REVERSE-32K, 13 Sep 2026; the base
        move    y:(r5+n5),a             ; is 0x8000-aligned too) tap, head 0
        move    a,x0                    ; possibly negative -> FIRST operand
        move    x:(r7+$e),y1           ; g0
        mpy     x0,y1,a
        move    a,b
        move    r1,a
        move    x:(r7+$f),x0           ; lag1
        sub     x0,a
        and     #>$7fff,a
        move    a1,r5
        move    y:(r5+n5),a             ; tap, head 1
        move    a,x0
        move    x:(r7+$10),y1           ; g1
        mpy     x0,y1,a
        add     b,a
        move    a,x:(r7-$25)            ; shifted OUTPUT tap L -- NOT $79
        move    a,x:(r7-$24)            ; ... and R: the reverse is MONO
                                        ; (REVERSE-32K; the R line is not
                                        ; written in this mode)
; MODEFORK_END
pdone:

; ---- one-pole damping in the feedback path: s += c*(d-s) ------------------
        move    x:(r7+$2e),b            ; state L
        move    x:(r7+$30),a            ; dL
        sub     b,a
        move    a,x0
        move    x:(r7+$29),y1           ; TONE coefficient
        mpy     x0,y1,a
        add     b,a
        move    a,x:(r7+$2e)            ; new state L
        move    a,x:(r7+$32)            ; fL == this sample's wet L

        move    x:(r7+$2f),b            ; state R
        move    x:(r7+$31),a            ; dR
        sub     b,a
        move    a,x0
        move    x:(r7+$29),y1
        mpy     x0,y1,a
        add     b,a
        move    a,x:(r7+$2f)            ; new state R
        move    a,x:(r7+$33)            ; fR == this sample's wet R

; ---- ping-pong crossfeed matrix, feedback path only -----------------------
        move    x:(r7+$32),x0           ; fL
        move    x:(r7+$37),y1           ; 1-PING
        mpy     x0,y1,a
        move    x:(r7+$33),x0           ; fR
        move    x:(r7+$2b),y1           ; PING
        mpy     x0,y1,b
        add     b,a                     ; fbIntoL
        move    a,x:(r7+$35)

        move    x:(r7+$33),x0           ; fR
        move    x:(r7+$37),y1
        mpy     x0,y1,a
        move    x:(r7+$32),x0           ; fL
        move    x:(r7+$2b),y1
        mpy     x0,y1,b
        add     b,a                     ; fbIntoR
        move    a,x:(r7+$38)

; ---- write both lines: LineL receives x_in in full, LineR receives it
; scaled by 1-PING (v3 stage 2 -- was "LineR only ever hears whatever
; crosses over", which left PING=0 with no path into R at all) ------------
        move    x:(r7+$35),x0           ; fbIntoL
        move    x:(r7+$2a),y1           ; FDBK
        mpy     x0,y1,a
        move    x:(r7+$34),x0           ; x_in
        add     x0,a
; ---- the line write: a limiting store ------------------------------------
; What each line is ABOUT TO BE WRITTEN (input + feedback for LineL,
; crossfed feedback for LineR) goes through satdrv, which since 15 Sep 2026
; is a plain limiting store: the sum can exceed full scale and a raw a1
; would wrap where this saturates. The cubic y = w - w^3/3 that lived here
; (v2 stage 4b; -0.03 dB at 0.1 FS, -0.76 at 0.5, -3.52 at full scale) went
; with the wow's depth gate. The store adds no loop gain (|y| <= |w|), so
; no FDBK setting can self-oscillate.
;
; TAPE ONLY, via the same Tcc substitution as the PITCH wet: cmp sets Z,
; moves do not disturb it, teq moves a CLEAN register in. CLEAN and PITCH
; are untouched, which is what keeps verify-delay's bit-identity gate green.
; sat + drive, SHARED: the transform is identical for both lines, so it is a
; bsr subroutine (satdrv, end of file) -- the roll that paid for DRIVE's
; words. In: a = the value about to be written. Out: a. Clobbers $2f.
        bsr     satdrv
        move    a,y:(r1)+                ; LineL write, advance

        move    x:(r7+$23),a            ; skipR (REVERSE-32K): no R write, it
        tst     a                       ; would land in the mono ring's upper half
        bne     rskipw
        move    x:(r7+$38),x0           ; fbIntoR
        move    x:(r7+$2a),y1
        mpy     x0,y1,a
; ---- LineR ALSO takes the input now, scaled by 1-PING (v3 stage 2) -------
        move    x:(r7+$34),x0           ; x_in
        move    x:(r7+$37),y1           ; 1 - PING
        mac     x0,y1,a                 ; + the direct input's share
; sat + drive, SHARED: the transform is identical for both lines, so it is a
; bsr subroutine (satdrv, end of file) -- the roll that paid for DRIVE's
; words. In: a = the value about to be written. Out: a. Clobbers $2f.
        bsr     satdrv
        move    a,y:(r2+n2)             ; LineR write (phase + base) -- no x_in term
        move    (r2)+                   ; advance the phase
rskipw:

        move    r1,a
        move    x:(r7+$22),x0
        and     x0,a
        move    a1,r1                   ; the masked phase (a1 needs no A2-clean)
        move    (r1)+n1                 ; + LineL base
        move    r2,a
        and     #>$7fff,a                                                  ; @B
        and     #>$3fff,a                                                  ; @DEV
        move    a1,r2                   ; the wrapped phase (base-relative)

; ---- PITCH / GRAIN: the wet becomes the SHIFTED tap (v2 stage 2c) --------
; Placed HERE deliberately: both lines have already been written above from
; the clean tap, so the shift can never re-enter the feedback loop. From
; this point on the wet -- own-track MIX, the shared DELAY WET buffer and
; the ->VERB send -- carries the shifted signal, and everything downstream
; stays mode-blind.
;
; Branchless via Tcc: tst sets Z, the intervening moves do not disturb it,
; and tne moves a CLEAN register into the accumulator (never a hand-rolled
; mask -- the A2-staleness store trap). In CLEAN and TAPE the flag is 0, tne
; does not fire and the wet is bit-identical to v1's.
;
; The mode test itself moved OUT of the sample loop in stage 5 ($33, resolved
; once per block): PITCH and GRAIN both land here, and an in-loop compare
; would have had to grow a second one to say so.
        move    x:(r7-$16),a            ; SHIFTED flag: PITCH or GRAIN
        tst     a
        move    x:(r7-$25),x0           ; shifted L
        move    x:(r7+$32),b            ; loop's wet L
        tne     x0,b
        move    b,x:(r7+$32)
        move    x:(r7-$24),x0           ; shifted R
        move    x:(r7+$33),b
        tne     x0,b
        move    b,x:(r7+$33)

; ---- own track: DRY AT UNITY + WET ----------------------
; ---- DRIVE MAKEUP: out = wet * (1 + d/2), OUTPUT STAGE ONLY --
; ---- OUTPUT STAGE (one-aux rig, 7 Sep 2026; add-only 15 Sep 2026) ----------
; The stage output is out = in + wet*WET per channel, where `in` is this
; sample's chain input x_in ($7d: the auto-gained aux, this host's SEND
; included) and wet is the final (drive, x1.5, ping-shelved) tap: a pedal on
; the send, the send passing through it at unity and WET adding the repeats
; (until 15 Sep 2026 it crossfaded, in*(1-MIX) + wet*MIX, and the reverb's
; MIX then faded the delay out). Its MONO average goes to the CHAIN buffer
; at $901 at unity -- the reverb's input while this stage is live. The host
; prints wet*WET under its own dry (until 20 Sep 2026 the stage output was
; also published stereo for the T8 return, and the print gated off while
; that return was live). Every mpy is an audited-signed order: y0,x0 or
; x0,y1.
        move    x:(r7+$34),b            ; x_in, this sample's chain input
        move    b,x:(r7+$25)            ; the passthrough term, both channels, at unity
        move    x:(r7+$32),x0           ; wet L = fL
        move    x0,a                    ; (was wet * (1 + d/2) with d = 0)
        move    x0,b
        asr     #$1,b,b                 ; wet/2 -> x1.5 both channels (R58)
        add     b,a
        move    a,x0                    ; wet L, final
        move    x:(r7+$24),y1           ; WET
        mpy     x0,y1,a                 ; wet * WET
        move    a,x0                    ; x0 = wet*WET: what the host prints
        move    x:(r7+$25),b
        add     x0,b                    ; b = stage output L
        move    b,x:(r7+$26)            ; parked for the chain's mono average
        move    x:(r0),b                ; dry L, still in place
        add     x0,b                    ; + dry at unity (v5)
        move    b,x:(r0)                ; L in place -- dry + wet*WET
        move    x:(r7+$33),x0           ; wet R = fR
        move    x0,a
        move    x0,b
        asr     #$1,b,b                 ; wet/2 -> x1.5, matching L
        add     b,a
        move    x:(r7+$2b),y1           ; PING
        mpy     x0,y1,b                 ; wet*PING (signed order)
        asr     #$1,b,b
        add     b,a                     ; + wet*PING/2
        asr     #$1,b,b
        add     b,a                     ; + wet*PING/4 -> R shelf 0.75*PING
        move    a,x0                    ; wet R, final
        move    x:(r7+$24),y1           ; WET
        mpy     x0,y1,a                 ; wet * WET
        move    a,x0                    ; x0 = wet*WET
        move    x:(r7+$25),b
        add     x0,b                    ; b = stage output R
        move    x:(r0+n0),a             ; dry R
        add     x0,a                    ; + dry at unity
        move    a,x:(r0+n0)             ; R in place -- dry + wet*WET
; ---- the CHAIN buffer: mono average of the stage output, at unity --------
        move    x:(r7+$26),a            ; out L
        add     b,a                     ; + out R (b still holds it)
        asr     #$1,a,a                 ; mono
        move    x:(r7+$3a),b            ; this call's CHAIN write address
        move    b,r5
        move    a,y:(r5)                ; CHAIN[write][i] = the stage output --
                                        ; a STORE, not an accumulate: one
                                        ; writer, and nobody clears this buffer
        move    x:(r7+$3a),a
        move    #>$1,x0
        add     x0,a
        move    a,x:(r7+$3a)            ; advance the CHAIN write pointer

        move    (r0)+n0                 ; advance one stereo frame: two
        move    (r0)+n0                 ; steps, n0 stays 1 (14 Sep 2026)
dlyend:

; ---- save both phases, restore the M registers ----------------------------
        move    r1,a
        move    x:(r7+$22),x0           ; the L ring's mask ($7fff in REVERSE)
        and     x0,a
        move    a,x:(r7+$27)
        move    r2,a
        move    #>$7fff,x0                                                 ; @B
        move    #>$3fff,x0                                                 ; @DEV
        and     x0,a
        move    a,x:(r7+$28)
dry:
        move    r7,a                    ; the r7 REBASE undone: the raw
        sub     #>$49,a                 ; state block goes back to the
        move    a,r7                    ; dispatcher exactly as it came
        move    #>$ffffff,m1            ; the global linear invariant for the
        move    #>$ffffff,m2            ; two pointers this file never sets
                                        ; (m0/m4/m5 are set linear every block
                                        ; above and never changed: their
                                        ; restores here were no-ops)
        rts

; ---- modtap: the line read at this sample's lag, shared by both lines -----
; In: a = line write pointer (LineR's is base-relative), n5 = the line's
; base. Out: a = the sample at the lag: t0 at the integer lag, t1 one
; sample older, lerped by the fraction (the glide's plus the wobble's, split
; in the loop above). Clobbers b, x0, y1, r5.
modtap:
        move    x:(r7-$1e),x0           ; the lag, integer
        sub     x0,a
        move    x:(r7+$22),x0           ; the ring's mask
        and     x0,a
        move    a1,r5
        move    y:(r5+n5),b             ; t0 (n5 = the line base, from the caller)
        sub     #>1,a                   ; lag + 1: one sample older
        and     x0,a
        move    a1,r5
        move    y:(r5+n5),a             ; t1
        sub     b,a                     ; t1 - t0
        move    a,x0
        move    x:(r7-$1d),y1           ; the fraction, Q23
        mpy     x0,y1,a                 ; (signed x0,y1) frac * (t1 - t0)
        add     b,a                     ; t0 + frac * (t1 - t0)
        rts

; ---- satdrv: the limiting store, shared by both line writes ---------------
; (18 Aug 2026 -- rolled when DRIVE landed; the freeze hold lived in its
; tail until 20 Sep 2026.) In: a = the value about to be written. Out: a,
; clamped to full scale. bsr, not jsr: dsp_asm implements only the RELATIVE
; b-forms.
satdrv:
        move    a,x:(r7-$1a)            ; park w. A LIMITING store: the sum
                                        ; can exceed full scale and a raw a1
                                        ; would WRAP where this saturates
        move    x:(r7-$1a),a            ; w, saturated (the tape's w - w^3/3
                                        ; was gated on the wow depth until
                                        ; 15 Sep 2026: this is the depth-0
                                        ; path, bit for bit)
        rts

; ---- smoothw: smoothstepped triangle window from a phase (v6 roll) --------
; In: a = phase, 0..$7fffff. Out: a = s = g^2*(3-2g), Q23, where g is the
; triangle fold of the phase (t/2^22; the LIMITING move clips the single
; peak value, exactly as every site this replaces did). Clobbers x0/y1 and
; the $5a park; y0/x1/b are untouched -- GRAIN's builder parks its wrap flag
; in y0 across its call.
;
; THE ROLL (v6): this exact 17-instruction
; sequence appeared FIVE times (wow LFO, flutter LFO, GRAIN's builder,
; REVERSE head 0, REVERSE head 1), 21 words each -- found mechanically by
; scanning the built module for repeated instruction runs. 105 inline words
; became 22 + five 1-word bsr's. The wow/flutter copies parked g^2 in $2a
; and the others in $5a; both parks are transient, so the roll unifies on
; $5a ($2a stays the LFO block's own "park mod" scratch, untouched here).
; Bit-identity across all modes is the gate this shipped under, same as the
; modtap/satdrv rolls before it.
smoothw:
        move    #$40,x0  
        sub     x0,a
        abs     a
        neg     a
        add     x0,a                    ; triangle, 0..$400000
        asl     #$1,a,a                 ; g, 0..1 (limiting move clamps the peak)
        move    a,x0
        move    a,y1
        mpy     x0,y1,a                 ; g^2
        move    a,x:(r7+$11)
        move    #>$7fffff,a
        sub     x0,a
        move    a,y1                    ; 1-g
        move    x:(r7+$11),x0
        mpy     x0,y1,a
        asl     #$1,a,a
        add     x0,a                    ; s = g^2*(3-2g)
        rts

