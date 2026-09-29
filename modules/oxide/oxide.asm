; ---------------------------------------------------------------------------
; OXIDE -- tape: the headroom, saturation and head bump of UADx Oxide Tape
; Recorder (15 IPS, NAB), modelled. modules/oxide/design.py is the model and
; the source of every coefficient below; the render gate
; (tools/verify/verify_oxide.py) holds this file to design.fixed(), its
; bit-level twin, at 0 LSB -- so the two change together or not at all.
;
; Insert contract: frames in place at x:(r0) (L) and x:(r0+n0) (R), knobs
; from r6, state in this instance's r7 block. No bus, no buffers, no Y.
;
; ---- the chain, per channel ----------------------------------------------
;   E1   hh = hpf1(x)/2                      5.32 Hz high-pass, halved
;        s  = shelf(hh)/8 = u/16             +20.3 dB low shelf (5.32 Hz / 55 Hz)
;   IN   t  = u*gin/2, clamped to [-1, 1)    the limiting move IS the clamp:
;                                            the curve is flat past |u| = 2
;   V    v  = V(2t)/4                        33-point curve, 32 segments of t,
;                                            linear between (P table: VT, ST)
;   E2   y  = lowshelf(v)                    TPT state-variable filter
;        z  = hshelf(y)/2                    first-order high shelf, halved
;        q  = allpass(z)                     first-order, 52.9 Hz
;   OUT  out = q * c_out * 64,               c_out = -gain*gout/8 (the model's
;                                            sign flip and +0.107 dB folded in)
; Every stage is first-order or a state-variable filter: the poles sit at 5,
; 13 and 53 Hz, where a 24-bit direct-form biquad cannot place them.
;
; ---- knobs (page 1) -------------------------------------------------------
;   p0 IN   0.3 dB a step, 48 = 0 dB: -14.4 .. +23.7 dB into the curve
;   p1 OUT  0.3 dB a step, 80 = 0 dB: -24 .. +14.1 dB
;   Both through a 17-point table (knob 0, 8 .. 128), interpolated per block.
;
; ---- r7 slots -------------------------------------------------------------
;   L at +$00, R at +$08 (r4 walks them), each PERSISTENT, zeroed at init:
;     +0 x1   +1 hh1   +2 s1   +3 svf s1   +4 svf s2   +5 y1   +6 z1   +7 q1
;   $10 gin/16   $11 c_out   (per block)
;
; ---- the traps this file is written around (CLAUDE.md, DSP.md 8) ----------
; * Every multiply uses an operand order dsp_asm encodes SIGNED: x0,y1 /
;   y1,x1 / x1,y0 (mpy x1,y1, mac x0,y0 and friends silently become mpysu /
;   macsu). The gate disassembles this module and refuses any `su` form.
; * No XY parallel moves: with an ALU op dsp_asm drops both moves and emits
;   the su form, even for the stock mixdown's own encoding (29 Sep 2026).
; * After the `and` the extension byte of b is stale: frac leaves as b1,
;   never through the limiter.
; * n1/n2 are written four instructions before the table reads use them.
; * Every recursive section ends in macr/mpyr (convergent, unbiased): with
;   the plain truncating move, the -1/2 LSB bias through the 5 Hz poles put a
;   -51 dB DC offset on the curve's input (even harmonics the tape does not
;   make) and -70 dBFS of DC on the output (29 Sep 2026, verify_oxide's
;   float-model residual).
; ---------------------------------------------------------------------------

init:
        move    #>$ffffff,m5
        move    r7,r5
        clr     a
        rep     #$12                    ; both channels' state + the two per-block words
        move    a,x:(r5)+
        rts

proc:
        move    #>$ffffff,m1
        move    #>$ffffff,m2
        move    #>$ffffff,m3
        move    #>$ffffff,m4
        move    #>$fab1e0,r1            ; the P table -- rewritten by build_bus.py
        move    #>$1,n0
; ---- per block: IN and OUT from their tables -----------------------------
        move    #$40,n3                 ; 64: IN follows VT (32) and ST (32)
        move    r1,r3
        move    x:(r6+$0),a             ; IN, val << 16
        move    (r3)+n3                 ; r3 = IN
        bsr     oxd_gain
        move    a,x:(r7+$10)            ; gin/16
        move    #$51,n3                 ; 81: OUT follows IN (17)
        move    r1,r3
        move    x:(r6+$1),a             ; OUT, val << 16
        move    (r3)+n3                 ; r3 = OUT
        bsr     oxd_gain
        move    a,x:(r7+$11)            ; c_out
        lua     (r1+$30),r2             ; ST + 16: the segment starting at t = 0
        lua     (r1+$10),r1             ; VT + 16
; ---- per frame ------------------------------------------------------------
        do      n7,oxd_end
        move    r7,r4                   ; L's state
        move    x:(r0),a                ; L
        bsr     oxd_ch
        move    a,x:(r0)                ; LIMITING store
        lua     (r7+$8),r4              ; R's state
        move    x:(r0+n0),a             ; R
        bsr     oxd_ch
        move    a,x:(r0+n0)
        move    (r0)+n0                 ; the frame advance: n0 is 1, two steps
        move    (r0)+n0
oxd_end:
        nop
        rts

; ---------------------------------------------------------------------------
; oxd_gain -- a knob through a 17-point table. In: a = the knob word
; (val << 16), r3 -> the table. Out: a. idx = val >> 3, frac = its low 3 bits.
oxd_gain:
        move    a,x1                    ; the knob word (positive: a2 = 0)
        asr     #$13,a,a
        move    a1,n3                   ; idx
        move    x1,a
        and     #>$7ffff,a
        asl     #$4,a,a
        move    a,x0                    ; frac, Q23
        move    (r3)+n3                 ; r3 = &T[idx]
        move    p:(r3)+,y0              ; T[idx]
        move    p:(r3),b                ; T[idx+1]
        move    y0,a
        sub     a,b
        move    b,y1                    ; T[idx+1] - T[idx]
        mpy     x0,y1,a
        add     y0,a
        rts

; ---------------------------------------------------------------------------
; oxd_ch -- one channel, one sample. In: a = x, r4 -> the channel's state.
; Out: a = the output (the caller's store limits). Straight-line.
oxd_ch:
; ---- E1a: the high-pass, halved: hh = (c/2) x - (c/2) x1 + p1 hh1 --------
        move    a,x0                    ; x
        move    x:(r4),x1               ; x1
        move    x0,x:(r4)
        move    #>$3ff9cb,y1            ; COEF C1H
        mpy     x0,y1,a
        mac     -y1,x1,a
        move    x:(r4+$1),x1            ; hh1
        move    #>$7fe72c,y0            ; COEF P1
        macr    x1,y0,a                 ; rounded: truncation's -1/2 LSB would
                                        ; come out x1300 at DC (the 5 Hz pole)
        move    a,x0                    ; hh
        move    a,x:(r4+$1)
; ---- E1b: the shelf into s = u/16 (x1 = hh1 still) -----------------------
        move    #>$100e8c,y1            ; COEF B0S
        mpy     x0,y1,a
        move    #>$f011a7,y0            ; COEF B1S
        mac     x1,y0,a
        move    x:(r4+$2),x1            ; s1
        move    #>$7fe72c,y0            ; COEF P2
        macr    x1,y0,a                 ; rounded (the same pole)
        move    a,x0                    ; s
        move    a,x:(r4+$2)
; ---- IN: t = s * (gin/16) * 128, clamped by the limiting move ------------
        move    x:(r7+$10),y1           ; gin/16
        mpy     x0,y1,a
        asl     #$7,a,a
        move    a,x0                    ; t (LIMITING)
; ---- the curve: v = VT[k] + frac * ST[k], k - 16 = t >> 19 ---------------
        move    x0,b
        asr     #$13,b,b
        move    b1,n1
        move    b1,n2
        move    x0,b
        and     #>$7ffff,b
        asl     #$4,b,b
        move    b1,x0                   ; frac (b1: b2 is stale after the and)
        move    p:(r1+n1),y0            ; VT[k]
        move    p:(r2+n2),y1            ; ST[k]
        mpy     x0,y1,a
        add     y0,a                    ; v = V/4
; ---- E2a: the low shelf, a TPT state-variable filter ---------------------
;   hp = D (v - s2 - (k+g) s1); v1 = g hp; bp = v1 + s1; s1 = bp + v1
;   v2 = g bp; lp = v2 + s2; s2 = lp + v2; y = hp + A k bp + A^2 lp
        move    x:(r4+$4),x0            ; s2
        sub     x0,a
        move    x:(r4+$3),x0            ; s1
        move    #>$597f37,y1            ; COEF KG2
        mac     -x0,y1,a
        macr    -x0,y1,a                ; v - s2 - (k+g) s1
        move    a,x0
        move    #>$7fafec,y1            ; COEF DD
        mpyr    x0,y1,a
        move    a,x0                    ; hp
        move    a,y0                    ; hp, kept for the mix
        move    #>$003968,y1            ; COEF GG
        mpyr    x0,y1,a                 ; v1
        move    x:(r4+$3),b
        add     a,b                     ; bp
        add     b,a
        move    a,x:(r4+$3)             ; s1
        move    b,x1                    ; bp
        mpyr    y1,x1,a                 ; v2
        move    x:(r4+$4),b
        add     a,b                     ; lp
        add     b,a
        move    a,x:(r4+$4)             ; s2
        move    b,x0                    ; lp
        move    #>$0afefd,y1            ; COEF A2
        mpy     x0,y1,b
        add     y0,b
        move    #>$3465a7,y1            ; COEF AK
        macr    y1,x1,b                 ; y
; ---- E2b: the high shelf, halved: z = hb0 y + hb1 y1 + hp z1 --------------
        move    b,x0                    ; y
        move    x:(r4+$5),x1            ; y1
        move    x0,x:(r4+$5)
        move    #>$495d96,y1            ; COEF HB0
        mpy     x0,y1,a
        move    #>$f3be7c,y0            ; COEF HB1
        mac     x1,y0,a
        move    x:(r4+$6),x1            ; z1
        move    #>$05c7dc,y0            ; COEF HP
        macr    x1,y0,a
        move    a,x0                    ; z
        move    a,x:(r4+$6)
; ---- E2c: the all-pass: q = K z + z1 - K q1 (x1 = z1 still) ---------------
        move    #>$80f5ea,y1            ; COEF KAP
        mpy     x0,y1,a
        add     x1,a
        move    x:(r4+$7),x1            ; q1
        macr    -y1,x1,a                ; rounded: the 53 Hz pole's DC gain is 133
        move    a,x0                    ; q
        move    a,x:(r4+$7)
; ---- OUT: q * c_out * 64 ---------------------------------------------------
        move    x:(r7+$11),y1           ; c_out
        mpy     x0,y1,a
        asl     #$6,a,a
        rts
