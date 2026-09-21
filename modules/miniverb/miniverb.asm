; Mini Verb v4: four branches, eight in-loop allpass diffusers, 44.1 kHz.
; Own 16K allocator buffer and r7+$20..$3f. No global writable state.
; Four input allpasses, two interpolated/modulated in-loop allpasses.
; Orthogonal Householder feedback. INIT resets all state, preserves r1/n1/m1.
; 20 base,21 head,22 clear;24..27 targets;28..2a smooth decay/damp/mix;
; 2b DC LP,2c diffused input,2d smoothed depth;30..33 damping state;
; 34 mean,35 feedback*mean,37 bounded phase;38..3b fully diffused branch taps.
; Ring segments: write..furthest read (including modulation neighbor):
; AP: 0..113
; AP: 114..287
; AP: 288..625
; AP: 626..1075
; delay: 1076..2053
; AP mod: 2054..2466
; AP: 2467..3150
; delay: 3151..4580
; AP: 4581..5012
; AP: 5013..5900
; delay: 5901..7732
; AP mod: 7733..8361
; AP: 8362..9453
; delay: 9454..11667
; AP: 11668..12387
; AP: 12388..13749

init:
        move    #>$ffffff,m4
        move    r7,r4
        move    #>$20,n4
        move    (r4)+n4
        clr     a
        do      #32,>mv_zero
        move    a,x:(r4)+
mv_zero:
        nop
        move    x:>$213,r4
        move    x:(r4),a
        move    a,x:(r7+$20)
        move    a,x:(r7+$21)
        move    #>$80,a
        move    a,x:(r7+$22)
        rts

proc:
; Bounded clearing: 128 words per call, dry until the entire ring is clean.
; Unconditional init resets every persistent scalar, even from dirty RAM.
        move    x:(r7+$22),a
        tst     a
        beq     mv_ready
        sub     #>$1,a
        move    a,x:(r7+$22)
        asl     #$7,a,a
        move    x:(r7+$20),x0
        add     x0,a
        move    a,r4
        move    #>$ffffff,m4
        clr     a
        do      #128,>mv_clear
        move    a,y:(r4)+
mv_clear:
        nop
        rts
mv_ready:
; feedback .65 + .32 * knob/128, bounded at .9675.
        move    x:(r6),x0
        move    #>$28f5c3,y1
        mpy     x0,y1,a
        move    #>$533333,x0
        add     x0,a
        move    a,x:(r7+$24)
; damping lowpass coefficient .90 - .80 * knob/128.
        move    x:(r6+$1),x0
        move    #>$666666,y1
        mpy     x0,y1,b
        move    #>$733333,a
        sub     b,a
        move    a,x:(r7+$25)
; Full-wet endpoint, all other values knob/128; mix zero is exact dry.
        move    x:(r6+$2),a
        move    #>$7f0000,x0
        cmp     x0,a
        bne     mv_mix
        move    #>$7fffff,a
mv_mix:
        move    a,x:(r7+$26)
        move    x:(r6+$3),a
        move    a,x:(r7+$27)
; RATE is an 8-way control: AGU step 1..8, 0.336..2.692 Hz.
        move    x:(r6+$4),a
        asr     #$10,a,a
        add     #>$1,a
        move    a,n2
        move    #>$ffffff,m2
        move    x:(r7+$37),r2
        move    #>$3fff,m4
        move    #>$3fff,m5
        move    x:(r7+$21),r5
        move    #>$1,n0
        do      n7,>mv_end
; Smooth target $24 into $28.
        move    x:(r7+$24),a
        move    x:(r7+$28),b
        sub     b,a
        asr     #$8,a,a
        add     b,a
        move    a,x:(r7+$28)
; Smooth target $25 into $29.
        move    x:(r7+$25),a
        move    x:(r7+$29),b
        sub     b,a
        asr     #$8,a,a
        add     b,a
        move    a,x:(r7+$29)
; Smooth target $26 into $2a.
        move    x:(r7+$26),a
        move    x:(r7+$2a),b
        sub     b,a
        asr     #$8,a,a
        add     b,a
        move    a,x:(r7+$2a)
        move    x:(r7+$27),a
        move    x:(r7+$2d),b
        sub     b,a
        asr     #$8,a,a
        add     b,a
        move    a,x:(r7+$2d)
; Mono input with headroom, DC highpass via a 0.001 lowpass subtraction.
        move    x:(r0),a
        move    x:(r0+n0),x0
        add     x0,a
        asr     #$3,a,a
        move    a,x1
        move    x:(r7+$2b),b
        sub     b,a
        move    a,x0
        move    #>$0020c5,y1
        mpy     x0,y1,a
        add     b,a
        move    a,x:(r7+$2b)
        move    x1,b
        sub     a,b
        move    b,a
; Input diffuser 113, g=0.75.
        move    #>$ffff8f,n5
        move    y:(r5+n5),b
        move    b,x0
        move    #>$600000,y1
        mac     -x0,y1,a
        move    #>$000000,n5
        move    a,y:(r5+n5)
        move    a,x0
        move    b,a
        mac     x0,y1,a
; Input diffuser 173, g=0.75.
        move    #>$fffee1,n5
        move    y:(r5+n5),b
        move    b,x0
        move    #>$600000,y1
        mac     -x0,y1,a
        move    #>$ffff8e,n5
        move    a,y:(r5+n5)
        move    a,x0
        move    b,a
        mac     x0,y1,a
; Input diffuser 337, g=0.625.
        move    #>$fffd8f,n5
        move    y:(r5+n5),b
        move    b,x0
        move    #>$500000,y1
        mac     -x0,y1,a
        move    #>$fffee0,n5
        move    a,y:(r5+n5)
        move    a,x0
        move    b,a
        mac     x0,y1,a
; Input diffuser 449, g=0.625.
        move    #>$fffbcd,n5
        move    y:(r5+n5),b
        move    b,x0
        move    #>$500000,y1
        mac     -x0,y1,a
        move    #>$fffd8e,n5
        move    a,y:(r5+n5)
        move    a,x0
        move    b,a
        mac     x0,y1,a
        move    a,x:(r7+$2c)
; One continuous per-sample triangle; split calls do not change its timebase.
; Triangle Q23 * smoothed DEPTH -> Q12 samples (0..64); x1=whole,
; y0=fraction. First allpasses in branches 1/3 move in opposite directions with adjacent taps.
        move    (r2)+n2
        move    r2,a
        and     #>$1ffff,a             ; M=0x1ffff selects LINEAR, not modulo
        move    a1,r2                 ; phase is nonnegative, extension stays zero
        sub     #>$10000,a
        abs     a
        asl     #$6,a,a
        move    a,x0
        move    x:(r7+$2d),y1
        mpy     x0,y1,a
        asr     #$4,a,a
        move    a,b
        asr     #$c,a,a
        move    a1,x1                  ; integer only; do not negate fractional A0
        and     #>$fff,b
; B2 stays zero: phase/product/fraction are nonnegative and bounded.
        asl     #$b,b,b
        move    b,y0
; Branch 1: delay 977, damping, AP 347, AP 683.
        move    #>$fff7fb,n5
        move    y:(r5+n5),a
        move    x:(r7+$29),y1
        move    x:(r7+$30),b
        sub     b,a
        move    a,x0
        mpy     x0,y1,a
        add     b,a
        move    a,x:(r7+$30)
        move    a,y1             ; park input while interpolating the AP read
        move    #>$fff69f,a
        sub     x1,a
        move    a,n5
        lua     (r5+n5),r4
        move    y:(r4)-,b
        move    y:(r4),a
        sub     b,a
        move    a,x0
        mpy     y0,x0,a
        add     b,a
        move    a,b
        move    y1,a
        move    b,x0
        move    #>$59999a,y1
        mac     -x0,y1,a
        move    #>$fff7fa,n5
        move    a,y:(r5+n5)
        move    a,x0
        move    b,a
        mac     x0,y1,a
        move    #>$fff3b2,n5
        move    y:(r5+n5),b
        move    b,x0
        move    #>$400000,y1
        mac     -x0,y1,a
        move    #>$fff65d,n5
        move    a,y:(r5+n5)
        move    a,x0
        move    b,a
        mac     x0,y1,a
        move    a,x:(r7+$38)
; Branch 2: delay 1429, damping, AP 431, AP 887.
        move    #>$ffee1c,n5
        move    y:(r5+n5),a
        move    x:(r7+$29),y1
        move    x:(r7+$31),b
        sub     b,a
        move    a,x0
        mpy     x0,y1,a
        add     b,a
        move    a,x:(r7+$31)
        move    #>$ffec6c,n5
        move    y:(r5+n5),b
        move    b,x0
        move    #>$59999a,y1
        mac     -x0,y1,a
        move    #>$ffee1b,n5
        move    a,y:(r5+n5)
        move    a,x0
        move    b,a
        mac     x0,y1,a
        move    #>$ffe8f4,n5
        move    y:(r5+n5),b
        move    b,x0
        move    #>$400000,y1
        mac     -x0,y1,a
        move    #>$ffec6b,n5
        move    a,y:(r5+n5)
        move    a,x0
        move    b,a
        mac     x0,y1,a
        move    a,x:(r7+$39)
; Branch 3: delay 1831, damping, AP 563, AP 1091.
        move    #>$ffe1cc,n5
        move    y:(r5+n5),a
        move    x:(r7+$29),y1
        move    x:(r7+$32),b
        sub     b,a
        move    a,x0
        mpy     x0,y1,a
        add     b,a
        move    a,x:(r7+$32)
        move    a,y1             ; park input while interpolating the AP read
        move    #>$ffdf58,a
        add     x1,a
        move    a,n5
        lua     (r5+n5),r4
        move    y:(r4)+,b
        move    y:(r4),a
        sub     b,a
        move    a,x0
        mpy     y0,x0,a
        add     b,a
        move    a,b
        move    y1,a
        move    b,x0
        move    #>$59999a,y1
        mac     -x0,y1,a
        move    #>$ffe1cb,n5
        move    a,y:(r5+n5)
        move    a,x0
        move    b,a
        mac     x0,y1,a
        move    #>$ffdb13,n5
        move    y:(r5+n5),b
        move    b,x0
        move    #>$400000,y1
        mac     -x0,y1,a
        move    #>$ffdf56,n5
        move    a,y:(r5+n5)
        move    a,x0
        move    b,a
        mac     x0,y1,a
        move    a,x:(r7+$3a)
; Branch 4: delay 2213, damping, AP 719, AP 1361.
        move    #>$ffd26d,n5
        move    y:(r5+n5),a
        move    x:(r7+$29),y1
        move    x:(r7+$33),b
        sub     b,a
        move    a,x0
        mpy     x0,y1,a
        add     b,a
        move    a,x:(r7+$33)
        move    #>$ffcf9d,n5
        move    y:(r5+n5),b
        move    b,x0
        move    #>$59999a,y1
        mac     -x0,y1,a
        move    #>$ffd26c,n5
        move    a,y:(r5+n5)
        move    a,x0
        move    b,a
        mac     x0,y1,a
        move    #>$ffca4b,n5
        move    y:(r5+n5),b
        move    b,x0
        move    #>$400000,y1
        mac     -x0,y1,a
        move    #>$ffcf9c,n5
        move    a,y:(r5+n5)
        move    a,x0
        move    b,a
        mac     x0,y1,a
        move    a,x:(r7+$3b)
; Store the MEAN, not half-sum: sum/2 can exceed Q23 and its saturation
; would break the intended matrix at large signal levels.
; Store mean and feedback*mean; reconstruct 2*g*mean - g*di in the wide
; accumulator using MAC, then add input and saturate only the final line.
        move    x:(r7+$38),a
        move    x:(r7+$39),x0
        add     x0,a
        move    x:(r7+$3a),x0
        add     x0,a
        move    x:(r7+$3b),x0
        add     x0,a
        asr     #$2,a,a
        move    a,x:(r7+$34)
        move    x:(r7+$28),y1
        move    a,x0
        mpy     x0,y1,a
        move    a,x:(r7+$35)
; line 1 = diffused input + feedback * (half-sum - di).
        move    x:(r7+$35),a
        asl     #$1,a,a
        move    x:(r7+$38),x0
        mac     -x0,y1,a
        move    x:(r7+$2c),x0
        add     x0,a
        move    #>$fffbcc,n5
        move    a,y:(r5+n5)
; line 2 = diffused input + feedback * (half-sum - di).
        move    x:(r7+$35),a
        asl     #$1,a,a
        move    x:(r7+$39),x0
        mac     -x0,y1,a
        move    x:(r7+$2c),x0
        add     x0,a
        move    #>$fff3b1,n5
        move    a,y:(r5+n5)
; line 3 = diffused input + feedback * (half-sum - di).
        move    x:(r7+$35),a
        asl     #$1,a,a
        move    x:(r7+$3a),x0
        mac     -x0,y1,a
        move    x:(r7+$2c),x0
        add     x0,a
        move    #>$ffe8f3,n5
        move    a,y:(r5+n5)
; line 4 = diffused input + feedback * (half-sum - di).
        move    x:(r7+$35),a
        asl     #$1,a,a
        move    x:(r7+$3b),x0
        mac     -x0,y1,a
        move    x:(r7+$2c),x0
        add     x0,a
        move    #>$ffdb12,n5
        move    a,y:(r5+n5)
; Stereo projections reconstruct the matrix half-sum from its mean. Mix directly into audio.
        move    x:(r7+$2a),y1
        move    x:(r7+$34),a
        asl     #$1,a,a
        move    x:(r7+$3a),x0
        sub     x0,a
        move    x:(r7+$3b),x0
        sub     x0,a
        asl     #$1,a,a                 ; recover wet level outside the tank
        move    x:(r0),b
        sub     b,a
        move    a,x0
        mpy     x0,y1,a
        add     b,a
        move    a,x:(r0)+
        move    x:(r7+$34),a
        asl     #$1,a,a
        move    x:(r7+$39),x0
        sub     x0,a
        move    x:(r7+$3b),x0
        sub     x0,a
        asl     #$1,a,a                 ; recover wet level outside the tank
        move    x:(r0),b
        sub     b,a
        move    a,x0
        mpy     x0,y1,a
        add     b,a
        move    a,x:(r0)+
        move    (r5)+
mv_end:
        nop
        move    r2,x:(r7+$37)
        move    #>$ffffff,m2
        move    #>$ffffff,m4
        move    r5,x:(r7+$21)
        move    #>$ffffff,m5
        rts
