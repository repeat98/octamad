; ---------------------------------------------------------------------------
; bd909 -- the Analog Bassdrum's TR-909 voice on the DSP (one voice per call).
;
; A circuit-stage model fitted to the user's Drumazon 2 (modules/analog-
; bassdrum/DSP909.md; the fits and every table: dsp909.py):
;   ENV5  pitch envelope ep, set at the trig, decays with TUNE
;   VCO   linear triangle, f = fb(PITCH) + A(PITCH,TUNE,TDEP) * ep, held while
;         the trig resets C14 and released rising ~2.48 ms after it
;   SHAPE static asymmetric shaper on the triangle (degree-11 polynomial)
;   VCA   ~60 ms hold with a slow droop, then the DECAY release (48-bit)
;   THUMP the VCA's control feedthrough: a slow negative DC (48-bit)
;   PULSE the trigger pulse ends the first time the triangle reaches THETA;
;         the edge rings through a HP and the 5.8 kHz resonant low-pass
;   NOISE free-running LCG, HP 230 Hz and two LP 2.37 kHz, gated by ENV2
;   LPF   the service notes' output network (knob 8; 0 passes through)
;   DESK  SAT (knob 5), LOW (9), HIGH (10): a Mackie-desk stage after it,
;         airwindows MackEQ as the reference
;
; Placeholders between at-signs are filled by dsp909.py: state offsets,
; table and constant addresses and the fixed coefficients. Labels are zqNN,
; all one length, because dsp_asm substitutes labels by textual prefix.
;
; zq01, one block:
;   r0  audio block: n7 frames written as interleaved L,R (the same value)
;   r5  this voice's state block, X words 0..@SWORDS@-1 (X only: the
;       48-bit states are hi/lo word pairs, so the block can sit where
;       only X is free)
;   r6  knob block: x:(r6+k) = knob k, 0..127, k = 0..11; x:(r6+$c) = the
;       trig's frame offset, or negative for none
;   knobs: 0 PITCH  1 DECAY  2 TUNE  3 ATK  4 TDEP  5 SAT  7 ACCNT  8 LPF
;          9 LOW  10 HIGH
; zq02, init: clears the state block at r5 and seeds the noise.
; m0, m1 and m4 are left linear; r5, r6 and n7 are preserved.
;
; Multiplies use only signed operand orders (AGENTS.md: dsp_asm turns an
; unknown order into mpysu), and no accumulator-to-accumulator ALU form;
; dsp909.py disassembles the build and refuses su/uu/max/rnd forms.
; ---------------------------------------------------------------------------

zq01:
        move    #>$ffffff,m0
        move    #>$ffffff,m1
        move    #>$ffffff,m4
; ---- control, once per block ------------------------------------------------
        move    x:(r6+$0),a             ; PITCH
        move    a1,n1
        move    #>@T_INCB@,r1
        move    x:(r1+n1),x0
        move    x0,x:(r5+@INCB@)
        move    #>@T_AP@,r1
        move    x:(r1+n1),x0            ; ap(PITCH)
        move    x:(r6+$2),a             ; TUNE
        move    a1,n1
        move    #>@T_GT@,r1
        move    x:(r1+n1),y0            ; gt(TUNE)
        mpyr    y0,x0,a
        move    #>@T_DKP@,r1
        move    x:(r1+n1),y1
        move    y1,x:(r5+@DKP@)
        move    a,x0                    ; ap*gt
        move    x:(r6+$4),a             ; TDEP
        move    a1,n1
        move    #>@T_GD@,r1
        move    x:(r1+n1),y0            ; gd(TDEP)
        mpyr    y0,x0,a                 ; q = ap*gt*gd, 0..1
        move    a,x0
        move    #>@KA_INC@,y0
        mpyr    y0,x0,b                 ; inc_a = q * K_A
        move    b,x:(r5+@INCA@)
        asr     #$10,a,a                ; thump index, q * 128
        move    a1,n1
        move    #>@T_THS@,r1
        move    x:(r1+n1),x1            ; thump level for this sweep size
        move    x:(r6+$1),a             ; DECAY
        move    a1,n1
        move    #>@T_DKD@,r1
        move    x:(r1+n1),y1
        move    y1,x:(r5+@DKD@)
        move    x:(r6+$7),a             ; ACCNT
        move    a1,n1
        move    #>@T_VB@,r1
        move    x:(r1+n1),y0            ; body level, velocity law
        mpyr    x1,y0,a
        move    a,x:(r5+@GDC@)
        move    #>@K_BODY@,x0
        mpyr    y0,x0,a
        move    a,x:(r5+@GBODY@)
        move    #>@T_VA@,r1
        move    x:(r1+n1),y1            ; attack level, velocity law
        move    x:(r6+$3),a             ; ATK
        move    a1,n1
        move    #>@T_ATP@,r1
        move    x:(r1+n1),x0
        mpyr    x0,y1,a
        move    a,x:(r5+@GP@)
        move    #>@T_ATN@,r1
        move    x:(r1+n1),x0
        mpyr    x0,y1,a
        move    a,x:(r5+@GN@)
        move    x:(r6+$8),a             ; LPF
        move    a1,n1
        move    #>@T_LPF@,r1
        move    x:(r1+n1),x0
        move    x0,x:(r5+@KLPF@)
;<desk-decode>
        move    x:(r6+$5),a             ; SAT
        move    a1,n1
        move    #>@T_TIN@,r1
        move    x:(r1+n1),x0
        move    x0,x:(r5+@TIN@)
        move    #>@T_PAD@,r1
        move    x:(r1+n1),x0
        move    x0,x:(r5+@PAD@)
        move    #>@T_KHP@,r1
        move    x:(r1+n1),x0
        move    x0,x:(r5+@KHP@)
        move    x:(r6+$9),a             ; LOW
        move    a1,n1
        move    #>@T_GB@,r1
        move    x:(r1+n1),x0
        move    x0,x:(r5+@GB@)
        move    #>@T_OB@,r1
        move    x:(r1+n1),x0
        move    x0,x:(r5+@OB@)
        move    x:(r6+$a),a             ; HIGH
        move    a1,n1
        move    #>@T_GB@,r1
        move    x:(r1+n1),x0
        move    x0,x:(r5+@GH@)
        move    #>@T_OB@,r1
        move    x:(r1+n1),x0
        move    x0,x:(r5+@OH@)
;</desk-decode>
; ---- the block, in one or two segments around the trig --------------------
        move    x:(r6+$c),a
        tst     a
        blt     zq03                    ; no trig in this block
        move    a,x:(r5+@SEG@)
        bsr     zq04                    ; frames before the trig (may be none)
        bsr     zq06                    ; the trig
        move    n7,a
        move    x:(r5+@SEG@),x0
        sub     x0,a
        bsr     zq04                    ; the rest of the block
        rts
zq03:
        move    n7,a
        bsr     zq04
        rts

; ---- zq04: a1 samples. A DO with a count of 0 runs 65536 times: skip it ----
zq04:
        tst     a
        beq     zq05
        do      a1,zq07
; (1) inc = inc_b + inc_a*ep; ep -= ep*dkp, truncating, so it reaches 0
        move    x:(r5+@EP@),x0
        move    x:(r5+@INCA@),y0
        move    x:(r5+@INCB@),a
        mac     y0,x0,a
        move    x0,b
        move    x:(r5+@DKP@),y1
        mac     -x0,y1,b
        move    b,x:(r5+@EP@)
        move    a,x1                    ; x1 = inc
; (2) phase; held until the release count
        move    x:(r5+@U@),a
        move    a,y0
        add     x1,a
        move    x:(r5+@C@),b
        cmp     #>@NREL@,b
        tlt     y0,a                    ; before the release: u stays
        move    a1,x:(r5+@U@)           ; a1 is not limited: wraps mod 2
; (3) triangle x = 1 - 2|u|
        move    a1,x0
        move    x0,a
        abs     a                       #>$400000,y0
        sub     y0,a
        asl     a
        neg     a
        move    a,x0                    ; x0 = x (1.0 limits to $7fffff)
; (4) the trigger pulse ends the first time the triangle reaches THETA
        cmp     #>@THETA@,a
        move    x:(r5+@PULSE@),b
        move    #0,y1
        tge     y1,b
        move    b,x:(r5+@PULSE@)
; (5) S/16 = c0/16 + x*(c1/16 + x*( ... + x*c11/16)), Horner; the degree-11
;     partial sums need the 1/16 (dsp909.horner_ok), two asl give S/4
        move    #>@CPOLY@,r1
        move    x:(r1)+,y0
        move    x:(r1)+,a
        mac     y0,x0,a         x:(r1)+,b
        move    a,y0
        mac     y0,x0,b         x:(r1)+,a
        move    b,y0
        mac     y0,x0,a         x:(r1)+,b
        move    a,y0
        mac     y0,x0,b         x:(r1)+,a
        move    b,y0
        mac     y0,x0,a         x:(r1)+,b
        move    a,y0
        mac     y0,x0,b         x:(r1)+,a
        move    b,y0
        mac     y0,x0,a         x:(r1)+,b
        move    a,y0
        mac     y0,x0,b         x:(r1)+,a
        move    b,y0
        mac     y0,x0,a         x:(r1)+,b
        move    a,y0
        mac     y0,x0,b         x:(r1)+,a
        move    b,y0
        mac     y0,x0,a
        asl     a
        asl     a
        move    a,y1                    ; y1 = S/4
; (6) the VCA opens: o += ka*(1 - o)
        move    x:(r5+@O@),x0
        move    #>@KA@,y0
        move    x0,a
        add     y0,a
        mac     -y0,x0,a
        move    a,x:(r5+@O@)
; (7) the VCA holds (slow droop) until NHOLD, then DECAY: m -= m*coef, 48-bit
        move    x:(r5+@C@),b
        cmp     #>@NHOLD@,b
        move    x:(r5+@DKD@),b
        move    #>@DKDROOP@,x1
        tlt     x1,b
        move    b,y0
        move    x:(r5+@LMH@),b          ; m, 48-bit as two X words
        move    x:(r5+@LML@),b0
        move    b1,x1
        mac     -x1,y0,b
        move    b,x:(r5+@LMH@)
        move    b0,x:(r5+@LML@)
        move    b,x1
        move    a,x0
        mpy     x1,x0,b
        move    b,x1                    ; x1 = g = o*m
; (8) body = GBODY * g * S/4; thump th += kth*(g - th), 48-bit; minus GDC*th
        mpy     y1,x1,a
        move    a,x0
        move    x:(r5+@GBODY@),y0
        mpy     y0,x0,a
        move    x:(r5+@THH@),b          ; th, 48-bit as two X words
        move    x:(r5+@THL@),b0
        move    b1,x0
        move    #>@KTH@,y0
        mac     x1,y0,b
        mac     -y0,x0,b
        move    b,x:(r5+@THH@)
        move    b0,x:(r5+@THL@)
        move    b,x0
        move    x:(r5+@GDC@),y0
        mac     -y0,x0,a
        move    a,x:(r5+@ACC@)          ; the body
; (9) pulse at 8x: r8 += KR8 - KR*r8; up8 = -r8*PULSE
        move    x:(r5+@R8@),x0
        move    x0,b
        move    #>@KR8@,y1
        add     y1,b                    #>@KR@,y0
        mac     -y0,x0,b
        move    b,x:(r5+@R8@)
        move    b,x0
        move    x:(r5+@PULSE@),y0
        mpy     -y0,x0,b
        move    b,x1                    ; x1 = up8
        move    x:(r5+@LPU@),x0         ; lpu += ku*(up - lpu)
        move    x0,a
        move    #>@KU@,y0
        mac     x1,y0,a
        mac     -y0,x0,a
        move    a,x:(r5+@LPU@)
        move    x:(r5+@UPPREV@),x0      ; hp = ahp*hp + bhp*(up - prev)
        move    x1,x:(r5+@UPPREV@)
        move    #>@BHP@,y0
        mpy     x1,y0,b
        mac     -y0,x0,b
        move    x:(r5+@HP@),x0
        move    #>@AHP@,y0
        mac     y0,x0,b
        move    b,x:(r5+@HP@)
        move    b,x0                    ; x0 = hp, the biquad's input
        move    #>@CBIQ@,r1             ; b0 b1 b2 -a1/2 -a2
        move    x:(r1)+,y0
        mpy     y0,x0,b         x:(r1)+,y0
        move    x:(r5+@BX1@),x0
        mac     y0,x0,b         x:(r1)+,y0
        move    x:(r5+@BX2@),x0
        mac     y0,x0,b         x:(r1)+,y0
        move    x:(r5+@BY1@),x0
        mac     y0,x0,b
        mac     y0,x0,b         x:(r1)+,y0
        move    x:(r5+@BY2@),x0
        mac     y0,x0,b
        move    x:(r5+@BX1@),x0
        move    x0,x:(r5+@BX2@)
        move    x:(r5+@HP@),x0
        move    x0,x:(r5+@BX1@)
        move    x:(r5+@BY1@),x0
        move    x0,x:(r5+@BY2@)
        move    b,x:(r5+@BY1@)
        move    b,x0                    ; x0 = w8
        move    #>@KW16@,y1
        mpy     x0,y1,b                 ; pls/16 = kw16*w8 + ku16*lpu8
        move    x:(r5+@LPU@),y0
        move    #>@KU16@,x1
        mac     x1,y0,b
        move    b,x0
        move    x:(r5+@GP@),y0
        mpy     y0,x0,b
        move    b,x:(r5+@PT@)           ; the pulse term / 16
; (10) noise: 24-bit LCG, HP, two LP, times ENV2 = e2 - e3. The chain runs
;      at half scale (BNH carries the 1/2): the HP swings w - prev, up to 2
        move    x:(r5+@LCG@),x0
        move    #>@LCGK@,y0
        mpy     y0,x0,b                 #0,x1 ; b0 = x*(M-1) mod 2^24
        add     x,b                     #>@LCGC@,y0 ; + x, then load c
        move    #0,y1
        add     y,b                     ; + c
        move    b0,x0
        move    x0,x:(r5+@LCG@)         ; x0 = white
        move    x:(r5+@NPREV@),y1
        move    x0,x:(r5+@NPREV@)
        move    #>@BNH@,y0
        mpy     y0,x0,b
        mac     -y1,y0,b
        move    x:(r5+@NH@),x0
        move    #>@ANH@,y0
        mac     y0,x0,b
        move    b,x:(r5+@NH@)
        move    b,x1                    ; x1 = nh
        move    x:(r5+@N1@),x0          ; n1 += kl*(nh - n1)
        move    x0,b
        move    #>@KL1@,y0
        mac     x1,y0,b
        mac     -y0,x0,b
        move    b,x:(r5+@N1@)
        move    b,x1
        move    x:(r5+@N2@),x0
        move    x0,b
        move    #>@KL2@,y0
        mac     x1,y0,b
        mac     -y0,x0,b
        move    b,x:(r5+@N2@)
        move    b,y1                    ; y1 = n2
        move    x:(r5+@E2@),x0
        move    #>@K2@,y0
        mpy     y0,x0,a
        move    a,x:(r5+@E2@)
        move    x:(r5+@E3@),x0
        move    #>@K3@,y0
        mpy     y0,x0,b
        move    b,x:(r5+@E3@)
        move    b,x0
        sub     x0,a                    ; env2
        move    a,x0
        mpy     x0,y1,a
        move    a,x0
        move    x:(r5+@GN@),y0
        mpy     y0,x0,b                 ; the noise term / 16
        move    x:(r5+@PT@),x0
        add     x0,b
        asl     b                       ; x16: single-bit shifts only (the
        asl     b                       ; multi-bit asl has no stock site)
        asl     b
        asl     b
        move    x:(r5+@ACC@),x0
        add     x0,b                    ; y = body + pulse + noise
; (11) the output network: yl += klpf*(y - yl); klpf $7fffff passes y
        move    b,x0                    ; limits: the one clip point
        move    x:(r5+@YL@),y1
        move    y1,a
        move    x:(r5+@KLPF@),y0
        mac     y0,x0,a
        mac     -y1,y0,a
        move    a,x:(r5+@YL@)
; (12) the Mackie stage (airwindows MackEQ as the reference, dsp909.MK): SAT's
;      drive into the curve, a complementary bass / mid / high split, the bass
;      and high bands driven into the curve by LOW and HIGH, the output
;      stage's curve, the make-up. SAT 0 with LOW and HIGH at 64 is flat.
;<desk>
        move    a,x0                    ; the desk's input coupling, 48-bit (a
        move    x:(r5+@HPH@),b          ; 24-bit state stalls short of the input
        move    x:(r5+@HPL@),b0         ; and SAT's drive makes that a DC floor):
        move    b1,y1                   ; hps += khp*(y - hps), y -= hps
        move    x:(r5+@KHP@),y0         ; (khp is 0 at SAT 0: DC-coupled)
        mac     y0,x0,b
        mac     -y1,y0,b
        move    b,x:(r5+@HPH@)
        move    b0,x:(r5+@HPL@)
        move    b,y1
        sub     y1,a
        move    a,x0
        move    x:(r5+@TIN@),y0         ; drive / stage / 32
        mpy     y0,x0,a
        asl     a
        asl     a
        asl     a
        asl     a
        asl     a
        move    a,x0                    ; the clip at 1: the move limits
        mpy     x0,x0,a                 ; the curve: x - KSAT*x^5
        move    a,y0
        mpy     y0,y0,a
        move    a,y0
        mpy     y0,x0,a         #>@KSAT@,y0 ; parallel load reads the old y0
        tfr     x0,a            a,y1    ; save the old product while loading x
        mac     -y1,y0,a
        move    a,x1                    ; x1 = x
        move    x:(r5+@LB@),x0          ; lb += KB*(x - lb): the bass band
        move    x0,a
        move    #>@KB@,y0
        mac     x1,y0,a
        mac     -y0,x0,a
        move    a,x:(r5+@LB@)
        move    a,y1                    ; y1 = lb
        move    x1,b
        sub     y1,b
        asr     b
        move    b,x1                    ; x1 = rest/2
        move    x:(r5+@M2@),x0          ; m2 += KM*(rest/2 - m2): mid/2
        move    x0,a
        move    #>@KM@,y0
        mac     x1,y0,a
        mac     -y0,x0,a
        move    a,x:(r5+@M2@)
        move    a,x0
        move    x1,b
        sub     x0,b
        move    b,x1                    ; x1 = high/2
        move    x:(r5+@GB@),y0          ; LOW: curve(gb*lb) * ob
        mpy     y1,y0,a
        asl     a
        asl     a
        move    a,x0
        mpy     x0,x0,a                 ; the curve: x - KSAT*x^5
        move    a,y0
        mpy     y0,y0,a
        move    a,y0
        mpy     y0,x0,a         #>@KSAT@,y0 ; parallel load reads the old y0
        tfr     x0,a            a,y1    ; save the old product while loading x
        mac     -y1,y0,a
        move    a,x0
        move    x:(r5+@OB@),y0
        mpy     y0,x0,b                 ; b = the sum * stage/16
        move    x:(r5+@GH@),y0          ; HIGH: curve(gh*high) * oh
        mpy     x1,y0,a
        asl     a
        asl     a
        asl     a
        move    a,x0
        mpy     x0,x0,a                 ; the curve: x - KSAT*x^5
        move    a,y0
        mpy     y0,y0,a
        move    a,y0
        mpy     y0,x0,a         #>@KSAT@,y0 ; parallel load reads the old y0
        tfr     x0,a            a,y1    ; save the old product while loading x
        mac     -y1,y0,a
        move    a,x0
        move    x:(r5+@OH@),y0
        mac     y0,x0,b
        move    x:(r5+@M2@),x0          ; + mid
        move    #>@KMS@,y0
        mac     y0,x0,b
        asl     b
        asl     b
        asl     b
        asl     b
        move    b,x0                    ; the output stage's clip
        mpy     x0,x0,a                 ; the curve: x - KSAT*x^5
        move    a,y0
        mpy     y0,y0,a
        move    a,y0
        mpy     y0,x0,a         #>@KSAT@,y0 ; parallel load reads the old y0
        tfr     x0,a            a,y1    ; save the old product while loading x
        mac     -y1,y0,a
        move    a,x0
        move    x:(r5+@PAD@),y0         ; make-up / 2
        mpy     y0,x0,a
        asl     a
        move    a,x:(r0)+
        move    a,x:(r0)+
;</desk>
; (12) samples since the trig, saturating at $7fffff
        move    x:(r5+@C@),a
        add     #>$000001,a
        move    a,x:(r5+@C@)
zq07:
zq05:
        rts

; ---- zq06: the trig ---------------------------------------------------------
; ep, the pulse flag and ENV2 to full; the count to 0; the VCA to 1.0 (48-bit)
; and the ramp to 0. u starts where the triangle holds x_r, backed off by the
; release's fractional sample so the first released sample lands on time.
; The thump, the filters and the noise keep running (a retrig does not reset
; the output coupling or the noise circuit).
zq06:
        move    #>$7fffff,x0
        move    x0,x:(r5+@EP@)
        move    x0,x:(r5+@PULSE@)
        move    x0,x:(r5+@E2@)
        move    x0,x:(r5+@E3@)
        clr     a
        move    a,x:(r5+@C@)
        move    a,x:(r5+@R8@)
        move    #>$7fffff,x0            ; m = 1 (48-bit: $7fffff:$ffffff)
        move    x0,x:(r5+@LMH@)
        move    #>$ffffff,x0
        move    x0,x:(r5+@LML@)
        move    x:(r5+@INCB@),a
        move    x:(r5+@INCA@),x0
        add     x0,a
        move    a,x0
        move    #>@FRAC@,y0
        move    #>@U0@,a
        mac     -y0,x0,a
        move    a,x:(r5+@U@)
        rts

; ---- zq02: init --------------------------------------------------------------
zq02:
        clr     a
        move    r5,r1
        do      #@SWORDS@,zq08
        move    a,x:(r1)+
zq08:
        move    #>$7fffff,x0
        move    x0,x:(r5+@C@)
        move    x0,x:(r5+@KLPF@)
        move    #>@SEED@,x0
        move    x0,x:(r5+@LCG@)
        rts
