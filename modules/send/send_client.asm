; ---------------------------------------------------------------------------
; SEND: the bus client. One knob, page 1: x:(r6+0) = SEND, this track's send
; into the one aux bus (delay, then reverb; each engine prints its wet on the
; track that hosts it). A dry,
; parallel tap: SEND never writes its own audio buffer, which is why a
; hardcoded-base server may encroach on the per-instance slot SEND owns.
;
; ---- the shared absolute-Y bus scratch. This layout is shared with REVERB
; SERVER and DELAY SERVER and must stay identical across the three sources.
; It lives at Y:0x900..0x9d2 and under XBUS relocates whole to
; 0x36000.. (base + (old - 0x900)): build_bus.py rewrites `$9xx`
; literals only, so a buffer past the 0x900 page is spelled as `$9xx + n`,
; never fused into an `$axx` literal that would stay core-private.
;
;   Y:0x900            this block's WRITE OFFSET into the accumulators: 0, 16,
;                       32 or 48, the buffer index already scaled by the
;                       16-word stride; masked on load and save (it may start
;                       as boot garbage). Four buffers, not two: at every
;                       instant one buffer is the write target and one the
;                       read target, so with two the only buffer that can be
;                       cleared is the one a skewed reader on the other core
;                       may still be inside. With four a buffer is written at
;                       block n, rests at n+1, read at n+2, rests at n+3 and
;                       is cleared again at n+4, so either core may lead by
;                       up to a block. Four rather than three because the
;                       rotation is `+16 & $30` and the read offset `+32 &
;                       $30`, no compare and no clamp.
;   Y:0x901..0x940      THE CHAIN BUFFER: the delay's stage output, mono, at
;                       unity, four buffers of 16 words at +0/+16/+32/+48,
;                       stored (not accumulated, never cleared) by the delay
;                       every block it runs, read two back by the reverb
;                       while the delay is live.
;   Y:0x941             BusVerb host's AUX knob field: the reverb writes it
;                        every block; the delay's auto-gain and the reverb's
;                        own count it as one more client while nonzero; the
;                        delay's warm-up zeroes it. A single-writer word in
;                        place of a cross-core count RMW.
;   Y:0x942..0x960      dead (kept so nothing below moves)
;   Y:0x961..0x9a0      THE AUX accumulator, four buffers of 16 words: every
;                       track's one send (SEND's AUX, the hosts' AUX)
;   Y:0x9a1..0x9c0      dead
;   Y:0x9c1             DELAY SERVER role owner (lock)
;   Y:0x9c2             REVERB SERVER role owner (lock)
;   Y:0x9c3             DELAY LIVE stamp for the REVERB (clear-on-read): the
;                       delay writes 1 every block it processes; the reverb
;                       reads it, clears it, keeps 3 blocks of grace and takes
;                       its input from the CHAIN buffer while live
;   Y:0x9c4..0x9c6      free (0x9c4/0x9c5 were the T8 return's liveness
;                       stamps until 20 Sep 2026)
;   Y:0x9c7..0x9ca      AUX send COUNT, one per accumulator buffer: how many
;                        clients wrote that buffer this block, indexed by the
;                        same rotation (a server reads last block's sum and
;                        needs last block's count). SEND and BusDelay's AUX
;                        register here, gated on their knobs (an idle client
;                        that registers dilutes the real ones); BusVerb's AUX
;                        is counted through Y:0x941. One word per buffer, so
;                        these are the only sites that scale the offset back
;                        to a bare index (`asr #$4`).
;   Y:0x9cb..0x9d2      free
;   Y:0x9d3..0x9d7      unused, deliberately: under XBUS these are
;                       0x360d3-5, where per-block state was dead on hardware
;                       (writes and in-loop reads never met; mechanism unknown)
;   Y:0x9d8..0xad9      free since 20 Sep 2026 (the T8 return's RETV/RETD
;                       stamps and the two stereo four-deep stage-output
;                       buffers)
;
; Latency: every block, whichever track is position 0 (r7 == 0x6200, the
; first FX2 dispatched in this bank, whatever module it runs) advances the
; rotation and clears the new write-target buffers before anyone accumulates
; into them; every other track reads whatever rotation that leaves. So every
; track's send lands in the same buffer every block and reads a
; fully-summed, one-block-old buffer back regardless of dispatch order. The
; read target is two buffers behind the write target (the idle block on each
; side of the reader): one extra block of bus latency, 16 samples.
;
; r7 slots used here: $14 (call flag), $65/$66/$67 (split bookkeeping), $68
; (the housekeeping election's last-seen rotation, payload A only: the XBUS
; gate excises the block on payload B), $69 (this block's resolved write
; offset).
;
; No read of x:>$213: SEND never uses its per-instance table entry.
; ---------------------------------------------------------------------------

init:
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
; ROTINIT
        rts

proc:
; ---- split-aware frame offset (BUS.md fix, found while wiring the REVERB
; SERVER): a track's proc() runs TWICE in a block that has a nonzero split
; (dsp/reverb89.asm's dispatcher note, reproduced here since this file has
; no other comment on it) -- a=0 first for frames [0,split), then always
; a=1 for [split,16). Naively gating position-0's flip on "r7==0x6200"
; alone flips the shared rotation ONCE PER CALL, i.e. TWICE in a split block,
; which cancels itself out and silently desyncs the bus. And without an
; offset, every call's per-sample ACC/WET writes start back at index 0,
; so a split a=1 call stomps the START of the block instead of continuing
; from where a=0 left off.
;
; x:(r7+$67) ends this section holding the correct write offset for THIS
; call (0 if it is the first dispatch of the block -- either the a=0 call,
; or the a=1 call when there was no a=0 this block -- else the stashed
; split point). x:(r7+$65)/(r7+$66) are private bookkeeping, consumed by
; the a=1 call that matches an a=0.
        move    a,x:(r7+$14)             ; stash the dispatcher's incoming call
                                          ; flag before it's clobbered: 0 for
                                          ; a=0 (first sub-block), left-aligned
                                          ; $010000 for a=1 (reverb89.asm's
                                          ; same idiom, r7+$14)
        clr     a
        move    a,x:(r7+$67)             ; default: offset 0 (first call)
        move    x:(r7+$14),a
        tst     a
        bne     bus_a1
        move    #>$1,a
        move    a,x:(r7+$65)             ; "a=0 ran this block"
        move    n7,a
        and     #>$f,a                   ; same mask on the way in
        move    a1,x0
        move    x0,a
        move    a,x:(r7+$66)             ; stash split for the matching a=1
        bra     bus_off_done
bus_a1:
; COLD-BOOT SAFETY. These three slots hold boot garbage the first time an
; instance runs, and x:(r7+$67) feeds straight into r1/r2 as a Y pointer
; below -- an unmasked garbage value there makes the per-sample loop write
; through a wild address, which hangs the DSP. Reproduced on hardware:
; selecting SEND on any track from a clean boot froze the unit. Same class
; as DSP.md's masked-garbage AGU saturation, so the same discipline applies
; -- mask AND A2-clean every one of them before use.
        move    x:(r7+$65),a
        and     #>$ff,a                  ; flag field only
        move    a1,x0
        move    x0,a                     ; A2-clean before the compare
        move    #>$1,x0
        cmp     x0,a                     ; EXACTLY 1, not merely nonzero:
        bne     bus_off_done             ; garbage is unlikely to be 1, where
                                         ; "nonzero" accepts almost any garbage
        clr     a
        move    a,x:(r7+$65)             ; consume the flag
        move    x:(r7+$66),a
        and     #>$f,a                   ; a split point is 0..15 by
        move    a1,x0                    ; construction, so this cannot narrow
        move    x0,a                     ; a legitimate value -- it only makes
        move    a,x:(r7+$67)             ; garbage harmless
bus_off_done:

; ---- position-0 housekeeping: flip rotation, clear the new write targets ---
; Gated on offset==0 too (not just r7==0x6200): only the FIRST dispatch of
; position-0's block may flip, so a split block flips exactly once, on
; whichever call that is.
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
; notfirst, so it still finds this block's write targets but never elects.
; Inert in a normal build: it is a comment.
        move    x:(r7+$67),a
        tst     a
        bne     notfirst                ; not this block's first call
        move    r7,a
        move    #>$6200,x0
        cmp     x0,a
        beq     bus_dohk                ; position 0: always the housekeeper
        move    y:>$900,a
        and     #>$30,a
        move    a1,x0
        move    x0,a                    ; offset now, A2-clean
        move    x:(r7+$68),x0
        cmp     x0,a
        bne     bus_seen                ; it moved: someone else housekept
bus_dohk:                               ; nobody did -- take over this block

        move    y:>$900,a
        add     #>$10,a                     ; advance one buffer
        and     #>$30,a                     ; mod 4 -- and the SAME mask sanitises
                                          ; boot garbage, which is why four
                                          ; buffers cost less than three
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
        add     #>$10,a                 ; one further on: the NEXT block's
        and     #>$30,a                 ; write target, idle right now
        move    a,x0                    ; bases for the clear AND the count

        move    #>$961,b                 ; ONE BUS (6 Sep 2026): the AUX
        add     x0,b                     ; accumulator is the only one left.
        move    b,r2                     ; r2 = AUX ACC[new] base
        move    #>$ffffff,m2
        clr     a
        do      #16,>zclr
        move    a,y:(r2)+
zclr:
        nop
; ---- reset the new write buffer's SEND COUNT, alongside its accumulators ----
; y:>$900 already holds the NEW offset (written just above), so this indexes the
; same buffer the loop just cleared. A2-cleaned before it becomes an address,
; per the standing rule -- a garbage value here is a wild Y write.
; The counts are ONE word per buffer where the accumulators are sixteen, so
; this is the one consumer that wants the bare index and has to scale the
; offset back DOWN. x1 holds the NEW offset from the rotation above, so this
; no longer re-reads y:>$900.
        move    x0,a                    ; the SAME buffer the clear loop just
        asr     #$4,a,a                 ; zeroed -- count and accumulator must
                                        ; always move together (0..3)
        move    a1,x0
        move    x0,a
        move    #>$9c7,x0               ; the AUX count region
        add     x0,a
        move    a,r3
        move    #>$ffffff,m3
        clr     a
        move    a,y:(r3)                ; AUX count = 0; a stays 0 for the
                                        ; locks below
; ---- release both server-role locks for this block (BUS.md hardware test 3)
; a is still 0 from the clear loop above. Whichever of the three effects is
; position 0 does this, so the locks are freed exactly once per block and
; re-claimed below in dispatch order.
        move    a,y:>$9c1               ; DELAY SERVER role owner
        move    a,y:>$9c2               ; REVERB SERVER role owner

bus_seen:
        move    y:>$900,a               ; remember this block's offset so next
        and     #>$30,a                 ; block we can tell whether anybody
                                        ; else housekept in between
        move    a1,x0
        move    x0,a
        move    a,x:(r7+$68)
notfirst:
; ---- everyone: resolve THIS BLOCK'S WRITE OFFSET, ONCE, into r7+$69 ------
; ⚠️ THE POINT OF THE INDIRECTION: every client used to read y:>$900 at its own
; dispatch time, and on PAYLOAD B that is not a stable value. Core 0 owns the
; rotation and flips it once per block; core 0's own clients are dispatched
; right after the housekeeper and always see the post-flip value, but core 1's
; clients read it asynchronously. The core-1 client whose execution window
; STRADDLES the flip reads the old rotation on some blocks and the new one on
; others, so its contribution lands in an already-consumed buffer half the
; time -- block-rate amplitude jitter, i.e. broadband hash that scales linearly
; with the send and never changes character.
;
; CONFIRMED ON HARDWARE 17 Aug 2026: changing track 5 -- core 0's POSITION 0,
; the housekeeper -- from BusVerb to Send cured static on a core-1 signal
; path, with nothing on core 1 touched. Only the flip's timing changed.
; Full evidence table in docs/effects/XBUS.md step 3.
;
; ⚠️ IT RELOCATES: exactly one (core-1 track, delay mode) combination is bad at
; a time, and it moves when the mode or core 0's load changes. A single clean
; configuration therefore proves nothing -- test a sweep.
;
; build_bus.py substitutes a per-payload body at the marker below. Payload A
; reads the shared word directly (it is in lockstep and needs nothing);
; payload B tracks its own rotation. Both leave this block's offset in `a` AND
; in r7+$69, which every site downstream now reads instead of y:>$900.
; ROTLATCH
        move    a,x0
        move    #>$961,a
        add     x0,a
        move    x:(r7+$67),b             ; this call's split-aware frame offset
        add     b,a
        move    a,r2                     ; r2 = AUX ACC[write] base + offset.
                                         ; ONE BUS: this is the
                                         ; old DELAY accumulator, kept because
                                         ; the delay -- chain stage 1 -- already
                                         ; reads it, so its input never changed.
                                         ; 0x901-0x940 and 0x9c3-0x9c6 (the old
                                         ; REVERB accumulator and its counts) are
                                         ; FREE and nothing writes them.
        move    #>$ffffff,m2

; ---- register as a bus client, once per block, PER BUS, ONLY IF SENDING ---
; ---- THE SEND IS REFUSED ON TRACK 8 (the one-aux rig, 7 Sep 2026) --------
; Track 8 is the master: with MASTER TRACK on, its chain input is the mix
; of the other tracks, the hosts' wet included, so a send from it would put
; the bus's wet back into the bus -- the master loop that silenced the unit
; on 6 Sep 2026 (FAILURE_MODES). Refused by construction, not by
; discipline: on PAYLOAD A, core 0's position 3 (r7 == $6b00, the FX2 slot
; of track 8) contributes nothing and registers nothing, whatever its knob
; says. Payload B's position 3 is track 4 and sends normally. The payload
; is told apart by its Y base literal, which build_bus.py rewrites to
; $38000 for payload B and leaves at $30000 for A (the same discriminator
; the HKB diagnostic used); the literal is never used as an address here.
; (Sam, 20 Sep 2026, after the return left T8: "we still dont want send on
; t8".)
        move    #>$30000,a              ; this payload's base ($38000 on B)
        move    #>$38000,x0
        cmp     x0,a
        beq     send_ok                 ; payload B: every position sends
        move    r7,a
        move    #>$6b00,x0
        cmp     x0,a
        beq     send_refused            ; payload A position 3 = track 8
send_ok:
        move    x:(r7+$67),a
        tst     a
        bne     cnt_done                ; not this block's first call
        move    x:(r7+$69),a            ; WRITE offset: count the buffer we are
        asr     #$4,a,a                 ; about to add into, not the one being
        move    a1,x0                   ; read. Scaled back down to a bare index
        move    x0,a                    ; because the counts are one word each.
                                        ; r7+$69, NOT y:>$900 -- re-reading the
                                        ; shared word here would reintroduce
                                        ; exactly the disagreement the resolve
                                        ; block above exists to remove.
        move    #>$9c7,x0               ; THE AUX count (the old DELAY count
        add     x0,a                    ; region; 0x9c3-0x9c6 is now free)
        move    a,r3
        move    #>$ffffff,m3
        move    #>$1,x0                 ; the increment
        clr     b                       ; b = 0 -- BEFORE the tst below
        move    x:(r6),a                ; AUX level, the one knob
        tst     a                       ; Z set == silent == not a client
        tne     x0,b                    ; sending -> b = 1
        move    y:(r3),a
        add     b,a
        move    a,y:(r3)                ; AUX count += 1 ONLY if sending
cnt_done:

; ---- per-sample: mono dry sum, scaled into the ONE accumulator -----------
        move    x:(r6),y1                ; AUX level, the one knob
        do      n7,>send_end
        move    x:(r0)+,a                ; L
        move    x:(r0)+,x0               ; R, and r0 on to the next frame
        add     x0,a
        asr     #$1,a,a                  ; a = mono
        move    a,x1                     ; x1 = mono, the mpy operand

        mpy     x1,y1,a                  ; a = mono * AUX level
        asr     #$3,a,a                  ; 3 BITS OF BUS HEADROOM. Eight clients
        move    y:(r2),b
        add     b,a
        move    a,y:(r2)+                ; AUX ACC[write][i] += contribution

send_end:
        nop
send_refused:
        rts
