; ---------------------------------------------------------------------------
; Tape Echo -- lean three-head Space-Echo-style insert, replacing SPRING REV.
;
; This is the load-conscious DSP56300 port of the useful core of DJ-Mixer's
; TapeEchoBlock: one mono tape ring, three uneven playback heads, saturated
; feedback, tape-speed wobble and shared motor inertia.  The full desktop
; transport model, two flutter LFOs, biquads, noise/dropouts and separate
; tone controls are deliberately absent: four copies may share one OT core.
;
; ---- signal path -----------------------------------------------------------
; stereo dry -> mono record -> [32K tape ring]
;                  TIME/SYNC -> slewed motor target
;                           -> heads at T, 1.96875T, 2.9609375T (+/- wow)
;                           -> normalised sum -> fixed tape LP -> wet output
; record <- dry mono + FDBK * fixed-LP(head sum), limiting store -> tape
;
; The head ratios reproduce the C++ source's 1.0/1.97/2.96 spacing with
; shifts only.  A 32K buffer permits first-head time <= 11,000 samples:
; 11000*2.9609375 + 8 = 32,579, safely within 32,768 words.
;
; ---- controls --------------------------------------------------------------
; p0 TIME  FREE = 2048 + 64*value samples (46..231 ms).  In BEAT, TIME's
;          eight bands select 1/64, 1/32T, 1/32, 1/16T, 1/16, 1/8T, 1/16., 1/8.
; p1 FDBK  0..0.875; DRIVE softens the record before the final limiting rail.
; p2 WOW   slow common transport wobble, +/-8 samples at 127, ~1.35 Hz.
; p3 HEADS seven normalised masks.
; p4 SYNC  FREE/BEAT; tempo24 is stock r6+$13.
; p5 MIX   dry + MIX*(wet-dry); 0 is exact passthrough after warm-up.
; p6 DRIVE cubic record-curve depth (r6+$c knob field).
; p7 AGE   repeat low-pass loss (r6+$c companion field).
;
; ---- fixed buffer / state --------------------------------------------------
; r7+$20 MIX  $21/$22/$23 Q15.8 head distances  $24/$25/$26 head gains
; r7+$27 wow whole-sample offset (scratch)  $28 write head (P)
; r7+$29 wow phase (P)  $2a feedback LP state (P)  $2b wet (scratch)
; r7+$2c feedback coefficient  $2d limiting write park (scratch)
; r7+$2f warm tag|count (P)  $30 warm count stash
; r7+$31 DRIVE cubic coefficient  $32 AGE low-pass coefficient
; r7+$33 motor target delay (integer)  $34 motor-ready flag
; r7+$35/$36/$37 Q15.8 per-sample head velocities
; r7+$38/$39/$3a Q15.8 head targets
;
; ---- arithmetic discipline -------------------------------------------------
; Every multiply uses the toolchain's known signed x0,y1 order.  Every AND
; follows the A2-clean dance before its result is stored or compared.  The
; sample body has no control flow: CYCLES_FORWARD_BRANCHES only covers the
; per-block selector and tempo paths, not a data-dependent audio branch.
; ---------------------------------------------------------------------------

init:
        rts

proc:
        move    #>$ffffff,m1

; ---- warm-up: clear 256 x 128 = the whole 32K line -----------------------
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
        move    #>$100,x0
        cmp     x0,a
        bge     te_wdone
te_wrun:
        move    a,x:(r7+$30)
        asl     #$7,a,a                 ; count * 128
        add     #>$4000,a
        move    a,r1
        clr     b
        do      #128,>te_wz
        move    b,y:(r1)+
te_wz:
        nop
        move    #>$4000,a
        move    a,x:(r7+$28)
        clr     a
        move    a,x:(r7+$29)
        move    a,x:(r7+$2a)
        move    a,x:(r7+$34)           ; first live block seeds motor exactly
        move    x:(r7+$30),a
        add     #>$1,a
        add     #>$540000,a
        move    a,x:(r7+$2f)
        rts                             ; preserve dry frames while warming
te_wdone:

; ---- per-block: mix and safely bounded feedback --------------------------
        move    x:(r6+$5),x0
        move    x0,x:(r7+$20)
        move    x:(r6+$1),x0
        move    #>$700000,y1            ; raw * 0.875 -> stable loop gain
        mpy     x0,y1,a
        move    a,x:(r7+$2c)
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
        beq     te_tdone                ; no published tempo: retain FREE
        move    #>$0bfe00,x1
        move    #>$5,a                  ; a1:a0 = 84,672,000 = 2*42,336,000
        move    x1,a0
        andi    #$fe,ccr
        rep     #$18
        div     x0,a
        move    a0,x0
        move    x0,a
        asl     #$8,a,a
        move    a,x0                    ; samples/MIDI-clock in Q form

; TIME's upper three bits select the beat division.  Values are M<<11,
; where M MIDI clocks make the division (24 is a quarter note).
        move    x:(r6+$0),a
        asr     #$14,a,a                ; 0..7
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
        move    #>$0c00,y0              ; 1/64
        bra     te_divgo
te_div1:
        move    #>$1000,y0              ; 1/32 triplet
        bra     te_divgo
te_div2:
        move    #>$1800,y0              ; 1/32
        bra     te_divgo
te_div3:
        move    #>$2000,y0              ; 1/16 triplet
        bra     te_divgo
te_div4:
        move    #>$3000,y0              ; 1/16
        bra     te_divgo
te_div5:
        move    #>$4000,y0              ; 1/8 triplet
        bra     te_divgo
te_div6:
        move    #>$4800,y0              ; dotted 1/16
        bra     te_divgo
te_div7:
        move    #>$6000,y0              ; 1/8
te_divgo:
        mpy     y0,x0,a
        move    #>11000,x0
        cmp     x0,a
        tgt     x0,a                    ; preserve all three heads in 32K
        move    a,x:(r7+$33)
te_tdone:

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

; ---- tape motor: shared FREE/BEAT inertia, ramped at audio rate ----------
; Per block, derive a Q15.8 velocity of error/65536 for each head.  The
; per-sample loop applies it fifteen times, giving a ~1.5-second motor time
; constant.  A one-LSB minimum closes the final fraction without a dead band.
; Fractional playback below linearly interpolates the moving taps; this is
; what prevents the old block jumps and integer-step whistle.
        move    x:(r7+$34),a
        tst     a
        bne     te_motor_slew
        move    x:(r7+$38),a
        move    a,x:(r7+$21)
        move    x:(r7+$39),a
        move    a,x:(r7+$22)
        move    x:(r7+$3a),a
        move    a,x:(r7+$23)
        clr     a
        move    a,x:(r7+$35)
        move    a,x:(r7+$36)
        move    a,x:(r7+$37)
        move    #>$1,a
        move    a,x:(r7+$34)
        bra     te_motor_done
te_motor_slew:
; head 1 velocity
        move    x:(r7+$38),a
        move    x:(r7+$21),x0
        sub     x0,a                    ; target - current
        tst     a
        beq     te_motor_v1_zero
        asr     #$10,a,a
        tst     a
        bne     te_motor_v1_store
        move    #>$1,a
        bra     te_motor_v1_store
te_motor_v1_zero:
        clr     a
te_motor_v1_store:
        move    a,x:(r7+$35)
; head 2 velocity
        move    x:(r7+$39),a
        move    x:(r7+$22),x0
        sub     x0,a
        tst     a
        beq     te_motor_v2_zero
        asr     #$10,a,a
        tst     a
        bne     te_motor_v2_store
        move    #>$1,a
        bra     te_motor_v2_store
te_motor_v2_zero:
        clr     a
te_motor_v2_store:
        move    a,x:(r7+$36)
; head 3 velocity
        move    x:(r7+$3a),a
        move    x:(r7+$23),x0
        sub     x0,a
        tst     a
        beq     te_motor_v3_zero
        asr     #$10,a,a
        tst     a
        bne     te_motor_v3_store
        move    #>$1,a
        bra     te_motor_v3_store
te_motor_v3_zero:
        clr     a
te_motor_v3_store:
        move    a,x:(r7+$37)
te_motor_done:

; ---- HEADS -> three gains: 1, 1/sqrt(2), or 1/sqrt(3) --------------------
        move    x:(r6+$3),a             ; page-1 HEADS, slot 3
        asr     #$10,a,a                ; 0..6 under the descriptor
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
        move    #>$7fff,m5
        move    #>$7fff,m1
        move    #>$1,n1
        move    x:(r7+$28),a
        move    a,r5
        move    x:(r7+$29),a
        move    a,r1

; ---- per-sample body: straight-line by design ----------------------------
        move    #>$1,n0
        do      n7,>te_end
; wow triangle: 0..0.5, centre it, multiply depth, retain whole samples.
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
        asr     #$e,a,a                ; +/-128 sixteenths of a sample
        asr     #$4,a,a                ; +/-8 whole samples
        move    a,x:(r7+$27)

; Advance every playback head fractionally on every audio sample.
        move    x:(r7+$21),a
        move    x:(r7+$35),x0
        add     x0,a
        move    a,x:(r7+$21)
        move    x:(r7+$22),a
        move    x:(r7+$36),x0
        add     x0,a
        move    a,x:(r7+$22)
        move    x:(r7+$23),a
        move    x:(r7+$37),x0
        add     x0,a
        move    a,x:(r7+$23)

; head 1: t0 + frac*(t1-t0), with t1 the OLDER neighbour
        move    x:(r7+$21),a
        and     #>$ff,a
        move    a1,x0
        move    x0,a
        asl     #$f,a,a
        move    a1,y0                   ; Q23 interpolation fraction
        move    x:(r7+$21),a
        asr     #$8,a,a
        move    x:(r7+$27),x0
        add     x0,a
        neg     a
        move    a,n5
        move    y:(r5+n5),x1            ; t0 at integer delay
        sub     #>$1,a
        move    a,n5
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
        and     #>$ff,a
        move    a1,x0
        move    x0,a
        asl     #$f,a,a
        move    a1,y0
        move    x:(r7+$22),a
        asr     #$8,a,a
        move    x:(r7+$27),x0
        add     x0,a
        neg     a
        move    a,n5
        move    y:(r5+n5),x1
        sub     #>$1,a
        move    a,n5
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
        and     #>$ff,a
        move    a1,x0
        move    x0,a
        asl     #$f,a,a
        move    a1,y0
        move    x:(r7+$23),a
        asr     #$8,a,a
        move    x:(r7+$27),x0
        add     x0,a
        neg     a
        move    a,n5
        move    y:(r5+n5),x1
        sub     #>$1,a
        move    a,n5
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
        move    a,x:(r7+$2b)           ; wet before the record calculation

; record = mono dry + FDBK*wet.  The X-memory round-trip is a LIMITING
; store, deliberately acting as the final safety rail at high feedback.
        move    a,x0
        move    x:(r7+$2c),y1
        mpy     x0,y1,a
        move    x:(r0),b
        move    x:(r0+n0),x0
        add     x0,b
        asr     #$1,b,b
        add     b,a
; DRIVE-scaled cubic tape shave: x - DRIVE*x^3; the following X store
; remains the hard safety rail if a self-oscillating loop reaches full scale.
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
        move    x:(r7+$2d),a
        move    a,y:(r5)
        move    (r5)+

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
        move    r5,a
        move    a,x:(r7+$28)
        move    r1,a
        move    a,x:(r7+$29)
        move    #>$ffffff,m1
        rts
