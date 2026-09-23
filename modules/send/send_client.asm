; ---------------------------------------------------------------------------
; SEND: the bus client. One knob, page 1: x:(r6+0) = SEND, this track's send
; into the one aux bus (delay, then reverb; each engine prints its wet on the
; track that hosts it). A parallel tap: SEND never writes its own audio
; buffer.
;
; ---- the shared absolute-Y bus scratch. This layout is shared with REVERB
; SERVER and DELAY SERVER and must stay identical across the three sources.
; It lives at Y:0x900..0x9d2 and under XBUS relocates whole to
; 0x36000.. (base + (old - 0x900)): build_bus.py rewrites `$9xx`
; literals only, so a buffer past the 0x900 page is spelled as `$9xx + n`,
; never fused into an `$axx` literal that would stay core-private.
;
;   Y:0x900            this block's WRITE OFFSET into the accumulators, the
;                       buffer index already scaled by the 16-word stride:
;                       0, 16, .. 112; masked on load and save (it may start
;                       as boot garbage). EIGHT buffers since 22 Sep 2026
;                       (four from 17 Aug to then): a buffer is written at
;                       block n, read at n+3 and cleared at n+6 (the
;                       housekeeper clears the buffer two on from the one it
;                       flips to), so a client whose label is off by one in
;                       either direction never writes a buffer being cleared
;                       or read, and never reads one being written. The
;                       rotation is `+16 & $70`, the read offset `+80 & $70`
;                       (three back == five on), no compare and no clamp.
;   Y:0x901..0x980      THE AUX accumulator, eight buffers of 16 words: every
;                       track's one send (SEND's AUX, the hosts' AUX)
;   Y:0x981             BusVerb host's AUX knob field: the reverb writes it
;                        every block; the delay's auto-gain and the reverb's
;                        own count it as one more client while nonzero; the
;                        delay's warm-up zeroes it. A single-writer word in
;                        place of a cross-core count RMW.
;   Y:0x982..0x9c0      free
;   Y:0x9c1             DELAY SERVER role owner (lock)
;   Y:0x9c2             REVERB SERVER role owner (lock)
;   Y:0x9c3             DELAY LIVE stamp for the REVERB (clear-on-read): the
;                       delay writes 1 every block it processes; the reverb
;                       reads it, clears it, keeps 3 blocks of grace and takes
;                       its input from the CHAIN buffer while live
;   Y:0x9c4..0x9c6      free
;   Y:0x9c7..0x9ce      AUX send COUNT, one per accumulator buffer: how many
;                        clients wrote that buffer this block, indexed by the
;                        same rotation (a server reads the buffer three back
;                        and needs that buffer's count). SEND and BusDelay's
;                        AUX register here, gated on their knobs (an idle
;                        client that registers dilutes the real ones);
;                        BusVerb's AUX is counted through Y:0x981. One word
;                        per buffer, so these are the only sites that scale
;                        the offset back to a bare index (`asr #$4`).
;   Y:0x9cf..0x9d2      free
;   Y:0x9d3..0x9d7      unused, deliberately: under XBUS these are
;                       0x360d3-5, where per-block state was dead on hardware
;                       (writes and in-loop reads never met; mechanism unknown)
;   Y:0x9d8..0xa57      THE CHAIN BUFFER: the delay's stage output, mono, at
;                       unity, eight buffers of 16 words at +0/+16/../+112,
;                       stored (not accumulated, never cleared) by the delay
;                       every block it runs, read three back by the reverb
;                       while the delay is live. Spelled `$9d8 + n` (the
;                       XBUS rewrite moves `$9xx` literals only); the range
;                       carried the T8 return's stage buffers until 20 Sep
;                       2026.
;   Y:0xa58..0xad9      free
;
; Latency: every block, whichever track is position 0 (r7 == 0x6200, the
; first FX2 dispatched in this bank, whatever module it runs) advances the
; rotation and clears the buffer two on before anyone accumulates into it;
; core 0's other tracks read the rotation that leaves, core 1's count their
; own blocks from a seed (ROTINIT, ROTLATCH). So every track's send lands in
; the same buffer every block and a server reads a fully-summed buffer back
; regardless of dispatch order. The read target is three buffers behind the
; write target: three blocks of bus latency, 48 samples (two until 22 Sep
; 2026).
;
; r7 slots used here: $14 (call flag), $67 (this call's frame offset; $65/$66
; free since 21 Sep 2026), $68
; (the housekeeping election's last-seen rotation, payload A only: the XBUS
; gate excises the block on payload B), $69 (this block's resolved write
; offset).
;
; No read of x:>$213: SEND never uses its per-instance table entry.
; ---------------------------------------------------------------------------

init:
; ---- seed this client's block label (payload B) ---------------------------
; A core-1 client counts its own blocks from the seed read here and checks
; the count against the shared rotation once a block, keeping a difference
; of one either way and snapping beyond that (build_bus.py ROTLATCH). The
; seed is the rotation as read, before or after a flip, so the label runs
; exact or one behind for the life of the instance; both are inside the
; eight buffers' margin (docs/effects/XBUS.md).
; ROTINIT
        rts

proc:
; A track's proc() runs TWICE in a block with a nonzero split: a=0 for
; frames [0,split), then a=1 for [split,16). x:(r7+$67) ends this section
; holding this call's frame offset; the housekeeping and the count are
; gated on it being 0, the per-sample ACC writes start at it.
        move    a,x:(r7+$14)            ; the dispatcher's call flag, stashed
                                        ; (0 = the a=0 sub-block, $010000 = a=1)
; ---- an FX1 slot has no bus role ------------------------------------------
; Id 0 is aliased to SEND and the FX1 chooser's NONE is id 0, so this proc
; runs on every empty FX1 slot at the slot's own r7: 0x6100, 0x6400,
; 0x6700, 0x6a00 on each core (measured under the port, `--dsp-pcwatch`;
; the FX2 slots are 0x6200, 0x6500, 0x6800, 0x6b00). Such a call must
; neither register, send, nor run the rotation tracker (images 46-48,
; docs/effects/XBUS.md). X:$213 cannot gate this: it is the last init's
; pointer at proc time. The refusal returns before any state is touched.
        move    r7,a
        move    #>$6100,x0
        cmp     x0,a
        beq     fx1out
        move    #>$6400,x0
        cmp     x0,a
        beq     fx1out
        move    #>$6700,x0
        cmp     x0,a
        beq     fx1out
        move    #>$6a00,x0
        cmp     x0,a
        beq     fx1out
; ---- this call's frame offset, from r0 --------------------------------------
; The dispatcher passes r0 = 0 on a block's first call and r0 = 2 x split on
; the a=1 call of a split block (measured under the port: r0 = $e for a trig
; at frame 7). Nothing is stashed between the two calls: a stash did not
; survive them on the unit (images 40-47, docs/effects/XBUS.md).
        move    r0,a
        asr     #$1,a,a                 ; words -> frames
        and     #>$f,a                  ; 0..15 by construction; garbage masked
        move    a1,x0
        move    x0,a                    ; A2-clean
        move    a,x:(r7+$67)            ; this call's frame offset
bus_off_done:

; ---- position-0 housekeeping: flip rotation, clear the new write targets ---
; Only a block's first call may housekeep (offset == 0), so a split block
; flips exactly once. Position 0 (r7 == 0x6200, the bank's first FX2 call)
; housekeeps whenever it runs; any other instance takes over when the
; rotation has not changed since it last ran, which means nobody housekept
; in between (position 0's FX2 may be NONE). One r7 word: the rotation this
; instance last saw.
; XBUS_GATE -- build_bus.py substitutes a payload gate here when XBUS=1:
; one core housekeeps the shared bus; payload B is sent straight to
; notfirst, finds this block's write targets and never elects.
        move    x:(r7+$67),a
        tst     a
        bne     notfirst                ; not this block's first call
        move    r7,a
        move    #>$6200,x0
        cmp     x0,a
        beq     bus_dohk                ; position 0: always the housekeeper
        move    y:>$900,a
        and     #>$70,a
        move    a1,x0
        move    x0,a                    ; offset now, A2-clean
        move    x:(r7+$68),x0
        cmp     x0,a
        bne     bus_seen                ; it moved: someone else housekept
bus_dohk:                               ; nobody did -- take over this block

        move    y:>$900,a
        add     #>$10,a                 ; advance one buffer
        and     #>$70,a                 ; mod 8; the mask sanitises boot garbage
        move    a1,x0                   ; A2-clean: a boot word with bit 23 set
        move    x0,a                    ; would saturate the store
        move    a,y:>$900               ; the new CURRENT rotation
; The buffer cleared is the one written TWO blocks from now: clearing the
; buffer about to be written races the other core's writers (a core-1
; contribution landing before this clear is wiped: intermittent dropout,
; broadband hash), and the one two on was last read three blocks ago.
        add     #>$20,a                 ; two on
        and     #>$70,a
        move    a,x0                    ; bases for the clear AND the count

        move    #>$901,b                ; the AUX accumulator
        add     x0,b
        move    b,r2                    ; r2 = AUX ACC[new] base
        move    #>$ffffff,m2
        clr     a
        do      #16,>zclr
        move    a,y:(r2)+
zclr:
        nop
; ---- reset that buffer's SEND COUNT alongside its accumulator ------------
; The counts are one word per buffer where the accumulators are sixteen, so
; the offset is scaled back down to a bare index (0..7). A2-cleaned before it
; becomes an address.
        move    x0,a                    ; the buffer the clear loop zeroed
        asr     #$4,a,a
        move    a1,x0
        move    x0,a
        move    #>$9c7,x0               ; the AUX count region
        add     x0,a
        move    a,r3
        move    #>$ffffff,m3
        clr     a
        move    a,y:(r3)                ; AUX count = 0; a stays 0 for the
                                        ; locks below
; ---- release both server-role locks for this block ---------------------
; a is still 0. The housekeeper frees them once per block; the servers
; re-claim them in dispatch order.
        move    a,y:>$9c1               ; DELAY SERVER role owner
        move    a,y:>$9c2               ; REVERB SERVER role owner

bus_seen:
        move    y:>$900,a               ; this block's rotation, for next
        and     #>$70,a                 ; block's election test
        move    a1,x0
        move    x0,a
        move    a,x:(r7+$68)
notfirst:
; ---- everyone: resolve THIS BLOCK'S WRITE OFFSET, ONCE, into r7+$69 ------
; Core 1 reads the shared rotation asynchronously to core 0's flip, so a
; client that read y:>$900 at its own dispatch time landed in an already
; consumed buffer on some blocks (hardware, 17 Aug 2026, docs/effects/XBUS.md
; step 3). build_bus.py substitutes a per-payload body at the marker: payload
; A reads the shared word, payload B tracks its own count. Both leave this
; block's offset in `a` and in r7+$69, which every site below reads.
; ROTLATCH
        move    a,x0
        move    #>$901,a
        add     x0,a
        move    x:(r7+$67),b            ; this call's frame offset
        add     b,a
        move    a,r2                    ; r2 = AUX ACC[write] base + offset
        move    #>$ffffff,m2

; ---- register as a bus client, once per block, only if sending ------------
; Track 8 is refused: with MASTER TRACK on its chain input is the mix of
; the other tracks, hosts' wet included, so its send would feed the bus's
; wet back into the bus (FAILURE_MODES, 6 Sep 2026). On payload A, position
; 3 (r7 == $6b00, track 8's FX2 slot) neither contributes nor registers;
; payload B's position 3 is track 4 and sends. The payload is told apart by
; its Y base literal, which build_bus.py rewrites to $38000 for B; the
; literal is never used as an address here.
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
        move    x:(r7+$69),a            ; the WRITE buffer's count (r7+$69,
        asr     #$4,a,a                 ; never y:>$900), as a bare index
        move    a1,x0
        move    x0,a
        move    #>$9c7,x0               ; the AUX count region
        add     x0,a
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
        move    a,x0

        mpy     x0,y1,a                  ; a = mono * AUX level
        asr     #$3,a,a                  ; 3 bits of bus headroom: eight clients
        move    y:(r2),b
        add     b,a
        move    a,y:(r2)+                ; AUX ACC[write][i] += contribution

send_end:
        nop
send_refused:
        rts
fx1out:                                 ; an FX1 slot: nothing above ran
        rts
