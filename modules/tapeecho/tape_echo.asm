; ---------------------------------------------------------------------------
; HISTORICAL DSP IMPLEMENTATION. Not selected by manifest.py since the CPU
; migration. See cpu.c / cpu_hooks.s for the active implementation.
; Tape Echo -- lean three-head Space-Echo-style insert, replacing SPRING REV.
;
; This is the load-conscious DSP56300 port of the useful core of DJ-Mixer's
; TapeEchoBlock: one mono tape ring, three uneven playback heads, saturated
; feedback, tape-speed wobble, a monotonic FREE motor and quantised BEAT taps.
; The full desktop
; transport model, two flutter LFOs, biquads, dropouts and separate
; tone controls are deliberately absent: four copies may share one OT core.
;
; ---- signal path -----------------------------------------------------------
; stereo dry -> mono record -> [per-track, manually wrapped 16K tape ring]
;                  TIME/SYNC -> FREE motor / BEAT quantised head position
;                           -> heads at T, 1.96875T, 2.9609375T (+/- wow)
;                           -> normalised sum -> fixed tape LP -> wet output
; record <- dry mono + FDBK * fixed-LP(head sum), limiting store -> tape
;
; The head ratios reproduce the C++ source's 1.0/1.97/2.96 spacing with
; shifts only. Init reads this FX2 instance's 16K base from the stock allocator;
; every tape address is explicitly masked to 14 bits before adding that base.
; Multiple instances therefore use different tape loops. The later heads may
; circle past the record head at long TIME settings, as physical heads placed
; around one continuous loop would, without touching another track's audio.
;
; ---- controls --------------------------------------------------------------
; p0 TIME  FREE = 2048 + 64*value samples (46..231 ms).  In BEAT, TIME's
;          eight bands select 1/64, 1/32T, 1/32, 1/16T, 1/16, 1/8T, 1/16., 1/8.
; p1 FDBK  0..1.054; DRIVE softens self-oscillation before the limiting rail.
; p2 WOW   slow common transport wobble, +/-8 samples at 127, ~1.35 Hz.
; p3 HEADS seven normalised masks.
; p4 SYNC  FREE/BEAT; tempo24 is stock r6+$13.
; p5 MIX   dry + MIX*(wet-dry); 0 is exact passthrough after warm-up.
; p6 DRIVE cubic record-curve depth (r6+$c knob field).
; p7 AGE   repeat low-pass loss (r6+$c companion field).
;
; ---- fixed buffer / state --------------------------------------------------
; r7+$1f allocator-provided 16K tape base (P)
; r7+$20 MIX  $21/$22/$23 Q15.8 head distances  $24/$25/$26 head gains
; r7+$27 wow Q15.8 offset (scratch)  $28 write head (P)
; r7+$29 wow phase (P)  $2a feedback LP state (P)  $2b wet (scratch)
; r7+$2c feedback coefficient  $2d limiting write park (scratch)
; r7+$2f warm tag|count (P)  $30 warm count stash
; r7+$31 DRIVE cubic coefficient  $32 AGE low-pass coefficient
; r7+$33 motor target delay (integer)  $34 motor-ready flag
; r7+$35 Q15.8 per-sample master velocity ($36/$37 unused)
; r7+$38/$39/$3a Q15.8 head targets
; r7+$3b last valid BEAT target (integer, 0 until tempo is published)
; r7+$3c BEAT transition gain Q23  $3e signed gain step
; r7+$3d tape-noise PRNG state (P)
;
; ---- arithmetic discipline -------------------------------------------------
; Every multiply uses the toolchain's known signed x0,y1 order.  Every AND
; follows the A2-clean dance before its result is stored or compared.  The
; sample body has no control flow: CYCLES_FORWARD_BRANCHES only covers the
; per-block selector and tempo paths, not a data-dependent audio branch.
; ---------------------------------------------------------------------------

init:
; X:$213 points at this instance's allocator-table entry during init. FX2
; entries are one 16K line per track: $4000, $8000, or a shared-window base.
        move    x:>$213,r4
        move    #>$ffffff,m4
        move    x:(r4),a
        move    a,x:(r7+$1f)
        clr     a
        move    a,x:(r7+$2f)            ; reselect/reload always clears this tape
        rts

proc:
        move    #>$ffffff,m1

; ---- warm-up: clear 128 x 128 = this instance's whole 16K line -----------
        move    x:(r7+$2f),a
        move    #>$fffe00,x0
        and     x0,a
        move    a1,x0
        move    x0,a                    ; A2-clean before compare
        move    #>$540000,x0
        cmp     x0,a
        beq     te_wtag
        clr     a
        bra     te_wrun
te_wtag:
        move    x:(r7+$2f),a
        move    #>$1ff,x0
        and     x0,a
        move    a1,x0
        move    #>$80,x0
        cmp     x0,a
        bge     te_wdone
te_wrun:
        move    a,x:(r7+$30)
        asl     #$7,a,a                 ; count * 128
        move    x:(r7+$1f),x0
        add     x0,a
        move    a,r1
        clr     b
        do      #128,>te_wz
        move    b,y:(r1)+
te_wz:
        nop
        clr     a
        move    a,x:(r7+$28)           ; write-head phase, 0..0x3fff
        move    a,x:(r7+$29)
        move    a,x:(r7+$2a)
        move    a,x:(r7+$34)           ; first live block seeds motor exactly
        move    a,x:(r7+$3b)           ; no valid BEAT target yet
        move    a,x:(r7+$3e)           ; no BEAT fade step active
        move    #>$7fffff,a
        move    a,x:(r7+$3c)           ; BEAT transition gain = unity
        move    #>$345678,a             ; deterministic nonzero tape-noise seed
        move    a,x:(r7+$3d)
        move    x:(r7+$30),a
        add     #>$1,a
        add     #>$540000,a
        move    a,x:(r7+$2f)
        rts                             ; preserve dry frames while warming
te_wdone:

; ---- per-block: mix and safely bounded feedback --------------------------
        move    x:(r6+$5),x0
        move    x0,x:(r7+$20)
        move    x:(r6+$1),a             ; raw 0..0.992; the loop adds 1/16
        move    a,x:(r7+$2c)            ; in the sample body -> max 1.054
; ---- detail controls: DRIVE curve and AGE bandwidth -----------------------
; p6 is the detail-page knob field.  0..127 -> cubic x^3 coefficient
; 0..~1/4; default 64 is exactly the previously validated fixed 1/8 shave.
        move    x:(r6+$c),a
        move    #>$ff0000,x0
        and     x0,a
        move    a1,x0
        move    x0,a                    ; A2-clean
        asr     #$2,a,a
        move    a,x:(r7+$31)
; p7 is its companion field.  AGE maps the one-pole coefficient from
; 3/8 (fresh) through default 1/4 to ~1/8 (worn).
        move    x:(r6+$c),a
        move    #>$00ff00,x0
        and     x0,a
        move    a1,x0
        move    x0,a                    ; A2-clean
        asl     #$8,a,a
        move    a,x0
        move    #>$200000,y1
        mpy     x0,y1,a
        move    #>$300000,b
        sub     a,b
        move    b,x:(r7+$32)


; ---- free TIME: 2048 + 64*knob samples -----------------------------------
        move    x:(r6+$0),a
        asr     #$10,a,a                ; 0..127
        asl     #$6,a,a
        add     #>$800,a
        move    a,x:(r7+$33)

; ---- BEAT TIME: stock tempo24 -> MIDI clock period, then one of 8 divs ---
        move    x:(r6+$4),a             ; page-1 SYNC, slot 4
        and     #>$ff0000,a
        move    a1,x0
        tst     a
        beq     te_tdone                ; FREE
        move    x:(r6+$13),a
        and     #>$ffff00,a
        asr     #$8,a,a                 ; tempo24 (BPM*24)
        move    a1,x0                    ; integer tempo24 is the divisor
        clr     b
        tst     a
        bne     te_thavetempo
; A frame with no published tempo must not kick a running synced motor back
; to FREE.  Retain the last valid beat target; only a never-synchronised
; instance falls back to the FREE target calculated above.
        move    x:(r7+$3b),a
        tst     a
        beq     te_tdone
        bra     te_anchor_note
te_thavetempo:
        move    #>$0bfe00,x1
        move    #>$5,a                  ; a1:a0 = 84,672,000 = 2*42,336,000
        move    x1,a0
        andi    #$fe,ccr
        rep     #$18
        div     x0,a
        move    a0,x0
        move    x0,a
        asl     #$7,a,a
        move    a,x0                    ; ticks Q12.4 << 7; fits down to 30 BPM

; TIME's upper three bits select the beat division. Values are M<<12,
; paired with the ticks' <<7 above (<<8 saturated below about 54 BPM).
; M MIDI clocks make the division; 24 is a quarter note.
        move    x:(r6+$0),a
        asr     #$14,a,a                ; 0..7
        move    a1,y0
        move    y0,a                    ; discard A0: cmp tests all 56 bits
        cmp     #>$1,a
        beq     te_div1
        cmp     #>$2,a
        beq     te_div2
        cmp     #>$3,a
        beq     te_div3
        cmp     #>$4,a
        beq     te_div4
        cmp     #>$5,a
        beq     te_div5
        cmp     #>$6,a
        beq     te_div6
        cmp     #>$7,a
        beq     te_div7
        move    #>$1800,y0              ; 1/64
        bra     te_divgo
te_div1:
        move    #>$2000,y0              ; 1/32 triplet
        bra     te_divgo
te_div2:
        move    #>$3000,y0              ; 1/32
        bra     te_divgo
te_div3:
        move    #>$4000,y0              ; 1/16 triplet
        bra     te_divgo
te_div4:
        move    #>$6000,y0              ; 1/16
        bra     te_divgo
te_div5:
        move    #>$8000,y0              ; 1/8 triplet
        bra     te_divgo
te_div6:
        move    #>$9000,y0              ; dotted 1/16
        bra     te_divgo
te_div7:
        move    #>$c000,y0              ; 1/8
te_divgo:
        mpy     y0,x0,a
        move    #>11000,x0
        cmp     x0,a
        tgt     x0,a                    ; keep head 3's Q15.8 state positive
        move    a,x:(r7+$3b)            ; selected note, before head compensation
te_anchor_note:
; Like fx-dsp TapeEchoBlock::targets, put the FIRST ENABLED head on the
; note. Keep this port's established 1 : 63/32 : 379/128 head geometry.
; Masks 2 and 2+3 start at head 2; mask 3 starts at head 3. All others
; (including an out-of-range mask, decoded as all three) start at head 1.
        move    a,y1
        move    x:(r6+$3),a
        asr     #$10,a,a
        move    a1,x0
        move    x0,a
        cmp     #>1,a
        beq     te_anchor_second
        cmp     #>4,a
        beq     te_anchor_second
        cmp     #>2,a
        beq     te_anchor_third
        move    y1,a
        bra     te_anchor_store
te_anchor_second:
        move    #>$410410,x0            ; round(2^23 * 32/63)
        mpy     x0,y1,a
        rnd     a
        bra     te_anchor_store
te_anchor_third:
        move    #>$2b3ac4,x0            ; round(2^23 * 128/379)
        mpy     x0,y1,a
        rnd     a
te_anchor_store:
        move    a,x:(r7+$33)
te_tdone:
; Only 16K samples of history exist. Reserve ten samples for WOW and the
; older interpolation neighbour; constrain the base by the LAST active head.
; A distance beyond one ring does not make a longer echo: it aliases to recent
; audio, and gliding across the seam produces a discontinuity.
        move    x:(r6+$3),a
        asr     #$10,a,a
        move    a1,x0
        move    x0,a
        cmp     #>0,a
        beq     te_limit_one
        cmp     #>1,a
        beq     te_limit_two
        cmp     #>3,a
        beq     te_limit_two
        move    #>5529,x0              ; floor(16374 * 128/379)
        bra     te_limit_apply
te_limit_one:
        move    #>11000,x0
        bra     te_limit_apply
te_limit_two:
        move    #>8316,x0              ; floor(16374 * 32/63)
te_limit_apply:
        move    x:(r7+$33),a
        cmp     x0,a
        tgt     x0,a
        move    a,x:(r7+$33)

; ---- three Q15.8 targets retain the original uneven head geometry --------
        move    x:(r7+$33),a
        asl     #$8,a,a
        move    a,x:(r7+$38)
        asl     #$1,a,a
        move    x:(r7+$38),b
        asr     #$5,b,b
        sub     b,a
        move    a,x:(r7+$39)
        move    x:(r7+$38),b
        asr     #$7,b,b
        move    x:(r7+$39),a
        move    x:(r7+$38),x0
        add     x0,a
        sub     b,a
        move    a,x:(r7+$3a)

; ---- BEAT mute-switches; FREE has one coherent tape transport ------------
; BEAT never reads two delay times together. A signed gain step fades the wet
; path to zero, all three heads switch to the latest quantised target, then
; the wet path fades back up. New targets during either phase are queued until
; the complete down/up envelope finishes. The feedback receives the same gain.
; Seed every head and the velocity before EITHER mode can read them. A saved
; BEAT selection used to enter the fade with the previous effect's RAM here.
        move    x:(r7+$34),a
        tst     a
        bne     te_transport_live
        move    x:(r7+$38),a
        move    a,x:(r7+$21)
        move    x:(r7+$39),a
        move    a,x:(r7+$22)
        move    x:(r7+$3a),a
        move    a,x:(r7+$23)
        clr     a
        move    a,x:(r7+$35)
        move    #>$1,a
        move    a,x:(r7+$34)
        bra     te_motor_done
te_transport_live:
        move    x:(r6+$4),a
        and     #>$ff0000,a
        tst     a
        beq     te_motor_free
; A FREE glide may still be in flight when BEAT is engaged. Keep the old
; tap stationary during fade-out, even when it already equals the new target.
        clr     a
        move    a,x:(r7+$35)

; Complete a fade boundary at block granularity. +/-32767 over 256 samples
; lands within 255 Q23 units of the rail; the explicit rail removes drift.
        move    x:(r7+$3e),a
        tst     a
        beq     te_beat_compare
        bgt     te_beat_fadein
        move    x:(r7+$3c),a
        move    #>$200,x0
        cmp     x0,a
        bgt     te_beat_compare
        move    x:(r7+$38),a
        move    a,x:(r7+$21)
        move    x:(r7+$39),a
        move    a,x:(r7+$22)
        move    x:(r7+$3a),a
        move    a,x:(r7+$23)
        clr     a
        move    a,x:(r7+$3c)
        move    #>$007fff,a
        move    a,x:(r7+$3e)            ; switch complete: fade in
        bra     te_motor_done
te_beat_fadein:
        move    x:(r7+$3c),a
        move    #>$7fff00,x0
        cmp     x0,a
        blt     te_beat_compare
        move    #>$7fffff,a
        move    a,x:(r7+$3c)
        clr     a
        move    a,x:(r7+$3e)            ; fade-in complete
        bra     te_motor_done            ; one full block at unity before a queued change
te_beat_compare:
        move    x:(r7+$38),a
        move    x:(r7+$21),b
        sub     b,a
        beq     te_motor_done
        move    x:(r7+$3e),a
        tst     a
        bne     te_motor_done            ; finish this transition; target stays queued
        move    #>$ff8001,a
        move    a,x:(r7+$3e)            ; start a new fade out
        clr     a
        move    a,x:(r7+$35)
        move    a,x:(r7+$36)
        move    a,x:(r7+$37)
        move    #>$1,a
        move    a,x:(r7+$34)
        bra     te_motor_done

; FREE reverses an unfinished BEAT fade from its CURRENT gain. Resetting gain
; to unity here makes a full-level step when SYNC changes during fade-out.
; Derive ONE master velocity from head 1.
; Heads 2 and 3 are reconstructed from that base position on every sample,
; so there is one tape-speed ramp, not three independent Doppler ramps.
te_motor_free:
        move    x:(r7+$3c),a
        move    #>$7fffff,x0
        cmp     x0,a
        beq     te_free_unity
        move    #>$007fff,a
        move    a,x:(r7+$3e)
        bra     te_motor_slew
te_free_unity:
        clr     a
        move    a,x:(r7+$3e)
te_motor_slew:
        move    x:(r7+$38),a
        move    x:(r7+$21),x0
        sub     x0,a                    ; master target - current
        tst     a
        beq     te_motor_v1_zero
        move    a,b
        abs     a
        move    #>$10,x0
        cmp     x0,a
        bgt     te_motor_v1_calc
        move    x:(r7+$38),a
        move    a,x:(r7+$21)
        bra     te_motor_v1_zero
te_motor_v1_calc:
        move    b,a
        asr     #$e,a,a
        move    a1,x0
        move    x0,a
        move    #>$20,x0
        cmp     x0,a
        tgt     x0,a
        move    #>$ffffe0,x0
        cmp     x0,a
        tlt     x0,a
        tst     a
        bne     te_motor_v1_store
        move    #>$1,a
        bra     te_motor_v1_store       ; keep the final positive fraction moving
te_motor_v1_zero:
        clr     a
te_motor_v1_store:
        move    a,x:(r7+$35)
te_motor_done:

; ---- HEADS -> three gains: 1, 1/sqrt(2), or 1/sqrt(3) --------------------
        move    x:(r6+$3),a             ; page-1 HEADS, slot 3
        asr     #$10,a,a                ; 0..6 under the descriptor
        move    a1,x0
        move    x0,a                    ; no fractional residue in the selector
        cmp     #>$0,a
        beq     te_select_solo1
        cmp     #>$1,a
        beq     te_select_solo2
        cmp     #>$2,a
        beq     te_select_solo3
        cmp     #>$3,a
        beq     te_select_pair12
        cmp     #>$4,a
        beq     te_select_pair23
        cmp     #>$5,a
        beq     te_select_pair13
; 6 and a stale out-of-range value: all three heads, never silence
        move    #>$49e69d,x0            ; 1/sqrt(3)
        move    x0,x:(r7+$24)
        move    x0,x:(r7+$25)
        move    x0,x:(r7+$26)
        bra     te_select_done
te_select_solo1:
        move    #>$7fffff,x0
        move    x0,x:(r7+$24)
        clr     a
        move    a,x:(r7+$25)
        move    a,x:(r7+$26)
        bra     te_select_done
te_select_solo2:
        clr     a
        move    a,x:(r7+$24)
        move    #>$7fffff,x0
        move    x0,x:(r7+$25)
        move    a,x:(r7+$26)
        bra     te_select_done
te_select_solo3:
        clr     a
        move    a,x:(r7+$24)
        move    a,x:(r7+$25)
        move    #>$7fffff,x0
        move    x0,x:(r7+$26)
        bra     te_select_done
te_select_pair12:
        move    #>$5a8279,x0            ; 1/sqrt(2)
        move    x0,x:(r7+$24)
        move    x0,x:(r7+$25)
        clr     a
        move    a,x:(r7+$26)
        bra     te_select_done
te_select_pair23:
        clr     a
        move    a,x:(r7+$24)
        move    #>$5a8279,x0
        move    x0,x:(r7+$25)
        move    x0,x:(r7+$26)
        bra     te_select_done
te_select_pair13:
        move    #>$5a8279,x0
        move    x0,x:(r7+$24)
        clr     a
        move    a,x:(r7+$25)
        move    x0,x:(r7+$26)
te_select_done:

; ---- counters: tape head and one slow 32K-sample wow triangle -----------
        move    #>$ffffff,m5            ; r5 is linear; tape wrap is explicit
        move    #>$7fff,m1
        move    #>$1,n1
        move    x:(r7+$1f),n5           ; this track's tape base
        move    x:(r7+$29),a
        move    a,r1

; ---- per-sample body: straight-line by design ----------------------------
        move    #>$1,n0
        do      n7,>te_end
; Wow triangle: centre it, multiply depth, retain eight fractional bits.
; Add the modulation BEFORE splitting each tap into integer/fractional parts.
; Rounding wow to whole samples makes discontinuous read jumps every cycle.
        move    (r1)+n1
        move    r1,a
        move    #>$4000,x0
        sub     x0,a
        abs     a
        move    a,b
        move    #>$4000,a
        sub     b,a                    ; 0..16384
        asl     #$8,a,a                ; 0..0.5 Q23, exact safe peak
        sub     #>$200000,a            ; -0.25..+0.25, centred
        move    a,x0
        move    x:(r6+$2),y1
        mpy     x0,y1,a
        asr     #$a,a,a                ; +/-2048 Q15.8 units = +/-8 samples
        move    a,x:(r7+$27)

; Advance the ONE master motor, then derive the two physical head spacings.
; This keeps all heads on one coherent tape-speed ramp.
        move    x:(r7+$21),a
        move    x:(r7+$35),x0
        add     x0,a
        move    a,x:(r7+$21)
        asl     #$1,a,a
        move    x:(r7+$21),b
        asr     #$5,b,b
        sub     b,a
        move    a,x:(r7+$22)
        move    x:(r7+$21),b
        asr     #$7,b,b
        move    x:(r7+$22),a
        move    x:(r7+$21),x0
        add     x0,a
        sub     b,a
        move    a,x:(r7+$23)

; head 1: t0 + frac*(t1-t0), with t1 the OLDER neighbour
        move    x:(r7+$21),a
        move    x:(r7+$27),x0
        add     x0,a
; Bound actual taps too: a newly enabled head can exceed history while the
; common FREE motor is still returning from a longer solo-head setting.
        move    #>$100,x0
        cmp     x0,a
        tlt     x0,a
        move    #>$3ffe00,x0
        cmp     x0,a
        tgt     x0,a
        move    a,x1                    ; combined fractional motor + wow
        and     #>$ff,a
        move    a1,x0
        move    x0,a
        asl     #$f,a,a
        move    a1,y0                   ; Q23 interpolation fraction
        move    x1,a
        asr     #$8,a,a
        move    a,x0                    ; positive integer delay
        move    x:(r7+$28),a            ; 14-bit write-head phase
        sub     x0,a
        and     #>$3fff,a
        move    a1,r5
        move    y:(r5+n5),x1            ; t0 at integer delay
        sub     #>$1,a
        and     #>$3fff,a
        move    a1,r5
        move    y:(r5+n5),a             ; t1 one sample older
        sub     x1,a
        move    a,x0
        mpy     x0,y0,a
        add     x1,a
        move    a,x0
        move    x:(r7+$24),y1
        mpy     x0,y1,b
; head 2
        move    x:(r7+$22),a
        move    x:(r7+$27),x0
        add     x0,a
        move    #>$100,x0
        cmp     x0,a
        tlt     x0,a
        move    #>$3ffe00,x0
        cmp     x0,a
        tgt     x0,a
        move    a,x1
        and     #>$ff,a
        move    a1,x0
        move    x0,a
        asl     #$f,a,a
        move    a1,y0
        move    x1,a
        asr     #$8,a,a
        move    a,x0
        move    x:(r7+$28),a
        sub     x0,a
        and     #>$3fff,a
        move    a1,r5
        move    y:(r5+n5),x1
        sub     #>$1,a
        and     #>$3fff,a
        move    a1,r5
        move    y:(r5+n5),a
        sub     x1,a
        move    a,x0
        mpy     x0,y0,a
        add     x1,a
        move    a,x0
        move    x:(r7+$25),y1
        mpy     x0,y1,a
        add     b,a
        move    a,b
; head 3
        move    x:(r7+$23),a
        move    x:(r7+$27),x0
        add     x0,a
        move    #>$100,x0
        cmp     x0,a
        tlt     x0,a
        move    #>$3ffe00,x0
        cmp     x0,a
        tgt     x0,a
        move    a,x1
        and     #>$ff,a
        move    a1,x0
        move    x0,a
        asl     #$f,a,a
        move    a1,y0
        move    x1,a
        asr     #$8,a,a
        move    a,x0
        move    x:(r7+$28),a
        sub     x0,a
        and     #>$3fff,a
        move    a1,r5
        move    y:(r5+n5),x1
        sub     #>$1,a
        and     #>$3fff,a
        move    a1,r5
        move    y:(r5+n5),a
        sub     x1,a
        move    a,x0
        mpy     x0,y0,a
        add     x1,a
        move    a,x0
        move    x:(r7+$26),y1
        mpy     x0,y1,a
        add     b,a                    ; selected, normalised head sum

; AGE-controlled tape low-pass.  The coefficient is 3/8 at 0, 1/4 at
; the default 64, and ~1/8 at 127; each feedback pass loses more top end.
        move    x:(r7+$2a),b
        sub     b,a
        move    a,x0
        move    x:(r7+$32),y1
        mpy     x0,y1,a
        add     b,a
        move    a,x:(r7+$2a)
; Apply the BEAT mute-switch envelope to BOTH output and feedback. FREE keeps
; gain at unity and step at zero. The switch itself occurs near digital zero.
        move    a,x0
        move    x:(r7+$3c),y1
        mpy     x0,y1,a
        move    a,x:(r7+$2b)           ; wet before the record calculation
        move    x:(r7+$3c),a
        move    x:(r7+$3e),x0
        add     x0,a
; Calls may contain 1..16 samples after a trig. Clamp EVERY sample: checking
; only at call boundaries can overshoot zero and invert the wet/feedback path.
        move    #>0,x0
        cmp     x0,a
        tlt     x0,a
        move    #>$7fffff,x0
        cmp     x0,a
        tgt     x0,a
        move    a,x:(r7+$3c)

; Advance a deterministic xorshift source and centre it around zero.  At
; roughly -78 dBFS it behaves like tape electronics: effectively absent at
; normal settings, but enough to let an above-unity loop bloom from silence.
        move    x:(r7+$3d),a
        move    a1,x0
        asl     #$f,a,a
        and     #>$7fffff,a
        eor     x0,a
        move    a1,x0
        move    x0,a
        asr     #$f,a,a
        eor     x0,a
        move    a1,x0
        move    x0,a
        asl     #$8,a,a
        and     #>$7fffff,a
        eor     x0,a
        move    a1,x0
        move    x0,a
        move    a,x:(r7+$3d)
        sub     #>$400000,a
        asr     #$c,a,a
        move    a,x:(r7+$2d)           ; centred tape-noise seed

; record = mono dry + FDBK*wet + tape noise.  Clamp BEFORE evaluating the
; cubic curve as well as after it. This prevents an above-unity loop plus a
; hot input from feeding an out-of-range accumulator into x-x^3.
        move    x:(r7+$2b),a
        move    a,x0
        move    x:(r7+$2c),y1
        mpy     x0,y1,a
        move    a,b
        asr     #$4,b,b                 ; +1/16: crosses unity near 121
        add     b,a                     ; and reaches ~1.054 at the top
        move    x:(r0),b
        move    x:(r0+n0),x0
        add     x0,b
        asr     #$1,b,b
        add     b,a
        move    x:(r7+$2d),x0
        add     x0,a
        move    a,x:(r7+$2d)           ; pre-curve limiting store
        move    x:(r7+$2d),a
; DRIVE-scaled cubic tape shave: x - DRIVE*x^3; the following store remains
; the final hard safety rail if a self-oscillating loop reaches full scale.
        move    a,x0
        move    a,y1
        mpy     x0,y1,b
        move    b,y1
        mpy     x0,y1,b
        move    b,x0
        move    x:(r7+$31),y1
        mpy     x0,y1,b
        sub     b,a
        move    a,x:(r7+$2d)
; Write at Y:(base + phase), then wrap the phase explicitly. The allocator's
; four bases are not all suitable for one fixed AGU modulo setup, so keeping
; the phase base-relative makes the same code safe on every track.
        move    x:(r7+$28),a
        move    a1,r5
        move    x:(r7+$2d),a
        move    a,y:(r5+n5)
        move    r5,a
        add     #>$1,a
        and     #>$3fff,a
        move    a1,x0
        move    x0,a                    ; A2-clean before the state store
        move    a,x:(r7+$28)

; stereo dry/wet crossfade.  MIX=0 reaches these macs with y1=0, preserving
; each dry word exactly; warm-up returned before this loop.
        move    x:(r7+$2b),a
        move    x:(r0),b
        sub     b,a
        move    a,x0
        move    b,a
        move    x:(r7+$20),y1
        mac     x0,y1,a
        move    a,x:(r0)
        move    x:(r7+$2b),a
        move    x:(r0+n0),b
        sub     b,a
        move    a,x0
        move    b,a
        mac     x0,y1,a
        move    a,x:(r0+n0)
        move    #>$2,n0
        move    (r0)+n0
        move    #>$1,n0
te_end:
        nop

; ---- persistent counters return to the instance block --------------------
        move    r1,a
        move    a,x:(r7+$29)
        move    #>$ffffff,m1
        rts
