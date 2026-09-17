; ---------------------------------------------------------------------------
; Vintage Verb -- a Dattorro plate running at HALF the audio rate.
;
; v3, 17 Sep 2026. v2's structure was right (see the README for why v1's
; Freeverb was scrapped) but it was 1.6x stock DARK REV's instruction count
; and its room was small: 16,384 words of delay at 44.1 kHz is a 0.30 s
; figure-8, where Dattorro's own tuning is 0.717 s.
;
; BOTH of those are the same problem, and running the tank at 22.05 kHz
; fixes both at once:
;   * the tank executes on every OTHER sample, so its ~300 cycles are paid
;     half as often;
;   * the same 16,384 words now hold TWICE the time -- the figure-8 loop
;     becomes 0.607 s, 85% of Dattorro's own, with no extra memory;
;   * and 22 kHz is what the machines this is named after actually ran at
;     (Lexicon 224: 31.25 kHz; AMS RMX16: 32 kHz). An 11 kHz reverb
;     bandwidth is the period-correct sound, not a compromise.
;
; The input is decimated by a two-sample average, whose null sits exactly on
; the new Nyquist (11.025 kHz), so it IS the anti-alias filter. The output is
; linearly interpolated back up: the tank's last two outputs are kept, a tank
; sample emits the older one and an off sample emits their mean, so every
; sample carries the same two-sample latency and there is no zero-order-hold
; step. `; CYCLES_FORWARD_BRANCHES` -- the half-rate gate is a forward skip,
; so tools/build/cycle_count.py prices the tank path and calls the result a
; CEILING; the dynamic figure (dsp_host's meter) is the one that reflects the
; every-other-sample reality.
;
; ---- signal path -----------------------------------------------------------
;   in -> mono/4 -> 2-sample average -> [half rate:] PRE -> DC block -> input
;   LP -> 3 series allpass diffusers (105/79/281, g .75/.75/.625) ->
;   figure-8 tank:
;
;     branch 1:  x + DECAY*b2 -> AP 417(+mod, g.7) -> delay 2761 -> damp LP
;                -> *DECAY -> AP 1116 (g.5) -> delay 2306 -> b1
;     branch 2:  x + DECAY*b1 -> AP 563(+mod, g.7) -> delay 2615 -> damp LP
;                -> *DECAY -> AP 1647 (g.5) -> delay 1961 -> b2
;
;   wet L = b1 + TD1[266] - TD3[1868],  wet R = b2 + TD3[162] - TD1[2350]
;   - TD2[154]  -- the two channels are built from different points in the
;   tank, so they decorrelate for free. Then [full rate:] interpolate,
;   WIDTH, MIX.
;
;   Round-trip gain is DECAY^4 per figure-8, loop 0.607 s, so DECAY
;   0.28..0.82 spans RT60 ~0.8 s .. ~5.3 s.
;
; ---- ONE circular buffer, every line a window on one head ------------------
; Y:0x4000..0x7FFF, 16,384 words, m5 = $3FFF, r5 = the head. Line i writes at
; (head - W_i) and reads at (head - W_i - D_i), so its data occupies the
; fixed relative window [W_i, W_i+D_i] and the AGU's modulo does every wrap
; for free -- no per-line pointer, no compare, no mask. The head is now kept
; IN r5 across the whole block and advanced with `move (r5)+` (one cycle,
; wrapped by the AGU) instead of being rebuilt from an r7 word every sample.
; 0x4000 is 16,384-aligned, which is what the modulo mode requires.
;
;   PRE   W=0      D=2047     AP1  W=2048  D=105    AP2  W=2154  D=79
;   AP3   W=2234   D=281      MAP1 W=2516  D=417 (+40 slack for the mod)
;   TD1   W=2974   D=2761     AP5  W=5736  D=1116   TD2  W=6853  D=2306
;   MAP2  W=9160   D=563      TD3  W=9764  D=2615   AP6  W=12380 D=1647
;   TD4   W=14028  D=1961                  15,990 of 16,384 words used.
;
; r1 (m1 = $7FFF) is the LFO phase and r2 (m2 = $0001) the half-rate toggle:
; both are counters the AGU wraps, never dereferenced.
;
; ---- r7 slots ---------------------------------------------------------------
;   $20 DECAY  $21 damp coeff  $22 WARP  $23 -(predelay)  $24 MIX  $25 WIDTH
;   $26 head address (PERSISTENT)   $28 toggle (P)   $29 previous input (P)
;   $2c wetL now / tap acc   $2d wetR now / tap acc
;   $2e wetL previous (P)    $33 wetR previous (P)
;   $2f allpass park         $30 diffused input     $34/$35 this sample's out
;   $31 warm tag|count (P)   $32 warm count stash
;   $36 LFO phase (P)  $37 wobble int  $38 wobble frac
;   $39 DC state (P)  $3a input LP state (P)  $3b input LP coeff
;   $3c b2 (P)  $3d branch-1 damp state (P)  $3e b1  $3f branch-2 damp state (P)
;
; ---- traps this code is written to avoid (CLAUDE.md) ------------------------
; Every `mpy`/`mac` is `x0,y1` or `y0,x0` -- the unconditionally signed
; encodings ($2000c0/$2000c2/$2000c6/$2000d0, the MPY/MAC opcode, never
; mpysu). Every `and` is followed by the A2-clean dance before the value is
; stored or used as an address; `asr`/`asl`/`abs`/`neg` are arithmetic and get
; none. No Tcc anywhere: the modulo AGU does the wrapping, so the
; shared-compare trap has no surface. No a0 read anywhere (the LFO is integer
; sub/abs/sub/shift). The LFO triangle is shifted left by 8, not 9: 16384<<9
; is exactly $800000, which as a 24-bit signed word is -1.0, not +1.0. The
; one branch in the sample body is a forward skip that lands inside the `do`
; loop, never out of it.
; ---------------------------------------------------------------------------

init:
        rts

proc:
        move    #>$ffffff,m1
        move    #>$ffffff,m2

; ---- warm-up: the tagged-counter idiom, 128 blocks x 128 words = 16,384 ----
        move    x:(r7+$31),a
        move    #>$fffe00,x0
        and     x0,a
        move    a1,x0
        move    x0,a
        move    #>$320000,x0
        cmp     x0,a
        beq     vv_wtag
        clr     a
        bra     vv_wrun
vv_wtag:
        move    x:(r7+$31),a
        move    #>$1ff,x0
        and     x0,a
        move    a1,x0
        move    x0,a
        move    #>$80,x0                ; 128 blocks
        cmp     x0,a
        bge     vv_wdone
vv_wrun:
        move    a,x:(r7+$32)
        asl     #$7,a,a                 ; count*128
        add     #>$4000,a
        move    a,r1
        clr     b
        do      #128,>vv_wz
        move    b,y:(r1)+
vv_wz:
        nop
        move    b,x:(r7+$28)            ; toggle
        move    b,x:(r7+$29)            ; previous input
        move    b,x:(r7+$2e)            ; wetL previous
        move    b,x:(r7+$33)            ; wetR previous
        move    b,x:(r7+$36)            ; LFO phase
        move    b,x:(r7+$39)            ; DC state
        move    b,x:(r7+$3a)            ; input LP state
        move    b,x:(r7+$3c)            ; b2
        move    b,x:(r7+$3d)            ; branch-1 damp state
        move    b,x:(r7+$3e)            ; b1
        move    b,x:(r7+$3f)            ; branch-2 damp state
        move    #>$4000,a               ; the head, as an absolute address
        move    a,x:(r7+$26)
        move    x:(r7+$32),a
        add     #>$1,a
        add     #>$320000,a
        move    a,x:(r7+$31)
        rts                             ; frames untouched: pure dry out
vv_wdone:

; ---- per-block knob decode --------------------------------------------------
; DECAY -> 0.28 + 0.54*(knob/128) = 0.28..0.816. The tank applies it twice
; per branch, so a figure-8 round trip is this to the fourth, over 0.607 s.
        move    x:(r6+$0),x0
        move    #>$451eb8,y1            ; 0.54
        mpy     x0,y1,a
        move    #>$23d70a,x0            ; 0.28
        add     x0,a
        move    a,x:(r7+$20)
; DAMP -> 0.30 + 0.69*(knob/128): the in-loop one-pole's coefficient. At the
; tank's 22.05 kHz a given coefficient is half the corner frequency it would
; be at 44.1, which is why this range sits higher than v2's.
        move    x:(r6+$1),x0
        move    #>$584fdf,y1            ; 0.69
        mpy     x0,y1,a
        move    #>$266666,x0            ; 0.30
        add     x0,a
        move    a,x:(r7+$21)
        move    x:(r6+$2),x0            ; WARP depth, straight Q23
        move    x0,x:(r7+$22)
; PRE -> -(PRE_int * 16) TANK samples, i.e. 0..92 ms at the half rate.
        move    x:(r6+$3),a
        asr     #$10,a,a
        asl     #$4,a,a                 ; 0..2032 tank samples
        neg     a
        move    a,x:(r7+$23)
        move    x:(r6+$4),x0            ; MIX, straight Q23
        move    x0,x:(r7+$24)
; WIDTH: page 2 slot 6, $c's knob field (bits 16-23)
        move    x:(r6+$c),a
        and     #>$7f0000,a
        move    a1,x0
        move    x0,a
        move    a,x:(r7+$25)
        move    #>$6ccccc,x0            ; input bandwidth, fixed 0.85
        move    x0,x:(r7+$3b)

; ---- the three AGU counters, held in registers across the whole block ------
        move    #>$3fff,m5              ; the one circular buffer
        move    #>$7fff,m1              ; the LFO phase
        move    #>$1,m2                 ; the half-rate toggle, modulo 2
        move    #>$2,n1                 ; LFO step -> ~1.35 Hz
        move    x:(r7+$26),a
        move    a,r5                    ; the delay head
        move    x:(r7+$36),a
        move    a,r1                    ; the LFO phase
        move    x:(r7+$28),a
        move    a,r2                    ; the toggle

; ---- per-sample loop --------------------------------------------------------
        move    #>$1,n0
        do      n7,>vv_end

; mono in, /4 for headroom, then the two-sample average that decimates to
; the tank's rate (its null is exactly on the new Nyquist)
        move    x:(r0),a
        move    x:(r0+n0),x0
        add     x0,a
        asr     #$2,a,a
        move    a,b
        move    x:(r7+$29),x0           ; the previous input sample
        move    b,x:(r7+$29)
        move    x0,a
        add     b,a
        asr     #$1,a,a
        move    a,x1                    ; the tank's input

; ---- this sample's output, assuming it is an OFF sample: the mean of the
; ---- last two tank outputs. A tank sample overwrites it below.
        move    x:(r7+$2e),a
        move    x:(r7+$2c),x0
        add     x0,a
        asr     #$1,a,a
        move    a,x:(r7+$34)
        move    x:(r7+$33),a
        move    x:(r7+$2d),x0
        add     x0,a
        asr     #$1,a,a
        move    a,x:(r7+$35)

; ---- the half-rate gate: a FORWARD skip over the tank, nothing else --------
        move    (r2)+
        move    r2,a
        tst     a
        beq     vv_off

; ---- a tank sample ---------------------------------------------------------
        move    (r5)+                   ; the head advances, AGU-wrapped
        move    x:(r7+$2c),a            ; this sample's wet becomes the previous
        move    a,x:(r7+$2e)
        move    x:(r7+$2d),a
        move    a,x:(r7+$33)

; LFO: an integer triangle, split into whole samples and a fraction
        move    (r1)+n1
        move    r1,a
        move    #>$4000,x0
        sub     x0,a
        abs     a
        move    a,b
        move    #>$4000,a
        sub     b,a                     ; 16384 - |ph-16384|
        asl     #$8,a,a                 ; -> Q23 0..0.5 (NOT 9: see the header)
        move    a,x0
        move    x:(r7+$22),y1           ; WARP depth
        mpy     x0,y1,a
        asr     #$e,a,a                 ; -> 0..254, sixteenths of a sample
        move    a,b
        asr     #$4,a,a                 ; whole samples, 0..15
        move    a,x:(r7+$37)
        move    b,a
        and     #>$f,a
        move    a1,x0
        move    x0,a
        asl     #$13,a,a                ; the sixteenths, as a Q23 fraction
        move    a,x:(r7+$38)

; ==== the chain: x1 carries the running signal, y0 holds DECAY ====
        move    x:(r7+$20),y0           ; DECAY, held through the tank

; -- predelay: write the head, read PRE samples back --
        move    #>$000000,n5
        move    x1,x0
        move    x0,y:(r5+n5)            ; write
        move    x:(r7+$23),n5           ; -(W + PRE), decoded per block
        move    y:(r5+n5),x1            ; the pre-delayed signal

; -- DC blocker, one-pole high-pass (no DC into the tank: the v1 comb bank let 0 Hz dominate) --
        move    #>$008000,y1            ; ~1/1024 -> corner ~7 Hz
        move    x:(r7+$39),b
        move    x1,a
        sub     b,a
        move    a,x0
        mpy     x0,y1,a
        add     b,a
        move    a,x:(r7+$39)
        move    a,x0
        move    x1,a
        sub     x0,a                    ; x - lp = the high-passed part
        move    a,x1

; -- one-pole low-pass (input bandwidth) --
        move    x:(r7+$3b),y1
        move    x:(r7+$3a),b
        move    x1,a
        sub     b,a
        move    a,x0
        mpy     x0,y1,a
        add     b,a
        move    a,x:(r7+$3a)
        move    a,x1

; -- allpass AP1: delay 105, g 0.75 (input diffusion 1) --
        move    #>$fff797,n5
        move    y:(r5+n5),b             ; v[n-N]
        move    #>$600000,y1    ; g
        move    x1,a                    ; x
        move    b,x0
        mac     -x0,y1,a                ; v = x - g*v[n-N]
        move    #>$fff800,n5
        move    a,y:(r5+n5)             ; store v at the head
        move    a,x0
        move    b,a                     ; v[n-N]
        mac     x0,y1,a                 ; y = v[n-N] + g*v
        move    a,x1                    ; running := y

; -- allpass AP2: delay 79, g 0.75 (input diffusion 2) --
        move    #>$fff747,n5
        move    y:(r5+n5),b             ; v[n-N]
        move    #>$600000,y1    ; g
        move    x1,a                    ; x
        move    b,x0
        mac     -x0,y1,a                ; v = x - g*v[n-N]
        move    #>$fff796,n5
        move    a,y:(r5+n5)             ; store v at the head
        move    a,x0
        move    b,a                     ; v[n-N]
        mac     x0,y1,a                 ; y = v[n-N] + g*v
        move    a,x1                    ; running := y

; -- allpass AP3: delay 281, g 0.625 (input diffusion 3) --
        move    #>$fff62d,n5
        move    y:(r5+n5),b             ; v[n-N]
        move    #>$500000,y1    ; g
        move    x1,a                    ; x
        move    b,x0
        mac     -x0,y1,a                ; v = x - g*v[n-N]
        move    #>$fff746,n5
        move    a,y:(r5+n5)             ; store v at the head
        move    a,x0
        move    b,a                     ; v[n-N]
        mac     x0,y1,a                 ; y = v[n-N] + g*v
        move    a,x1                    ; running := y

        move    x1,x:(r7+$30)           ; the diffused input, feeding both branches
        clr     a
        move    a,x:(r7+$2c)            ; wetL accumulator
        move    a,x:(r7+$2d)            ; wetR accumulator

; ==== tank branch 1 ====
        move    x:(r7+$3c),x0           ; b2, last sample's branch-2 output
        mpy     y0,x0,a                 ; * DECAY
        move    x:(r7+$30),b            ; + the diffused input
        add     b,a
        move    a,x1

; -- modulated allpass MAP1: delay 417+wob, g 0.7 (branch 1, modulated) --
        move    x:(r7+$37),x0           ; wobble, whole samples
        move    #>$000b75,a
        add     x0,a
        neg     a                       ; -(W+D+wob)
        move    a,n5
        move    y:(r5+n5),b             ; v0
        sub     #>$1,a                   ; one sample deeper
        move    a,n5
        move    y:(r5+n5),a             ; v1
        move    b,x0
        sub     x0,a                    ; v1 - v0
        move    a,x0
        move    x:(r7+$38),y1           ; wobble fraction
        mac     x0,y1,b                 ; v[n-N] = v0 + f*(v1-v0)
        move    #>$59999a,y1    ; g
        move    x1,a                    ; x
        move    b,x0
        mac     -x0,y1,a                ; v = x - g*v[n-N]
        move    #>$fff62c,n5
        move    a,y:(r5+n5)             ; store v at the head
        move    a,x0
        move    b,a
        mac     x0,y1,a                 ; y = v[n-N] + g*v
        move    a,x1

; -- delay TD1: 2761 samples (branch 1, first delay) --
        move    #>$ffe999,n5
        move    y:(r5+n5),b             ; delayed out
        move    #>$fff462,n5
        move    x1,x0
        move    x0,y:(r5+n5)            ; write head
        move    b,x1                    ; running := delayed

; -- output tap from TD1 at 266 -> wet L --
        move    #>$fff358,n5
        move    y:(r5+n5),b
        move    x:(r7+$2c),a
        add     b,a
        move    a,x:(r7+$2c)

; -- output tap from TD1 at 2350 -> wet R --
        move    #>$ffeb34,n5
        move    y:(r5+n5),b
        move    x:(r7+$2d),a
        sub     b,a
        move    a,x:(r7+$2d)

; -- one-pole low-pass (branch 1 damping) --
        move    x:(r7+$21),y1
        move    x:(r7+$3d),b
        move    x1,a
        sub     b,a
        move    a,x0
        mpy     x0,y1,a
        add     b,a
        move    a,x:(r7+$3d)
        move    a,x1

; -- x decay (branch 1) --
        move    x1,x0
        mpy     y0,x0,a                 ; y0 = DECAY, held
        move    a,x1

; -- allpass AP5: delay 1116, g 0.5 (branch 1, late diffusion) --
        move    #>$ffe53c,n5
        move    y:(r5+n5),b             ; v[n-N]
        move    #>$400000,y1    ; g
        move    x1,a                    ; x
        move    b,x0
        mac     -x0,y1,a                ; v = x - g*v[n-N]
        move    #>$ffe998,n5
        move    a,y:(r5+n5)             ; store v at the head
        move    a,x0
        move    b,a                     ; v[n-N]
        mac     x0,y1,a                 ; y = v[n-N] + g*v
        move    a,x1                    ; running := y

; -- delay TD2: 2306 samples (branch 1, second delay -> b1) --
        move    #>$ffdc39,n5
        move    y:(r5+n5),b             ; delayed out
        move    #>$ffe53b,n5
        move    x1,x0
        move    x0,y:(r5+n5)            ; write head
        move    b,x1                    ; running := delayed

        move    x1,x:(r7+$3e)           ; b1, for branch 2's cross-feed
        move    x:(r7+$2c),a
        add     x1,a
        move    a,x:(r7+$2c)            ; wet L += b1

; -- output tap from TD2 at 154 -> wet R --
        move    #>$ffe4a1,n5
        move    y:(r5+n5),b
        move    x:(r7+$2d),a
        sub     b,a
        move    a,x:(r7+$2d)

; ==== tank branch 2 ====
        move    x:(r7+$3e),x0           ; b1, this sample's branch-1 output
        mpy     y0,x0,a                 ; * DECAY
        move    x:(r7+$30),b            ; + the diffused input
        add     b,a
        move    a,x1

; -- modulated allpass MAP2: delay 563+wob, g 0.7 (branch 2, modulated) --
        move    x:(r7+$37),x0           ; wobble, whole samples
        move    #>$0025fb,a
        add     x0,a
        neg     a                       ; -(W+D+wob)
        move    a,n5
        move    y:(r5+n5),b             ; v0
        sub     #>$1,a                   ; one sample deeper
        move    a,n5
        move    y:(r5+n5),a             ; v1
        move    b,x0
        sub     x0,a                    ; v1 - v0
        move    a,x0
        move    x:(r7+$38),y1           ; wobble fraction
        mac     x0,y1,b                 ; v[n-N] = v0 + f*(v1-v0)
        move    #>$59999a,y1    ; g
        move    x1,a                    ; x
        move    b,x0
        mac     -x0,y1,a                ; v = x - g*v[n-N]
        move    #>$ffdc38,n5
        move    a,y:(r5+n5)             ; store v at the head
        move    a,x0
        move    b,a
        mac     x0,y1,a                 ; y = v[n-N] + g*v
        move    a,x1

; -- delay TD3: 2615 samples (branch 2, first delay) --
        move    #>$ffcfa5,n5
        move    y:(r5+n5),b             ; delayed out
        move    #>$ffd9dc,n5
        move    x1,x0
        move    x0,y:(r5+n5)            ; write head
        move    b,x1                    ; running := delayed

; -- output tap from TD3 at 162 -> wet R --
        move    #>$ffd93a,n5
        move    y:(r5+n5),b
        move    x:(r7+$2d),a
        add     b,a
        move    a,x:(r7+$2d)

; -- output tap from TD3 at 1868 -> wet L --
        move    #>$ffd290,n5
        move    y:(r5+n5),b
        move    x:(r7+$2c),a
        sub     b,a
        move    a,x:(r7+$2c)

; -- one-pole low-pass (branch 2 damping) --
        move    x:(r7+$21),y1
        move    x:(r7+$3f),b
        move    x1,a
        sub     b,a
        move    a,x0
        mpy     x0,y1,a
        add     b,a
        move    a,x:(r7+$3f)
        move    a,x1

; -- x decay (branch 2) --
        move    x1,x0
        mpy     y0,x0,a                 ; y0 = DECAY, held
        move    a,x1

; -- allpass AP6: delay 1647, g 0.5 (branch 2, late diffusion) --
        move    #>$ffc935,n5
        move    y:(r5+n5),b             ; v[n-N]
        move    #>$400000,y1    ; g
        move    x1,a                    ; x
        move    b,x0
        mac     -x0,y1,a                ; v = x - g*v[n-N]
        move    #>$ffcfa4,n5
        move    a,y:(r5+n5)             ; store v at the head
        move    a,x0
        move    b,a                     ; v[n-N]
        mac     x0,y1,a                 ; y = v[n-N] + g*v
        move    a,x1                    ; running := y

; -- delay TD4: 1961 samples (branch 2, second delay -> b2) --
        move    #>$ffc18b,n5
        move    y:(r5+n5),b             ; delayed out
        move    #>$ffc934,n5
        move    x1,x0
        move    x0,y:(r5+n5)            ; write head
        move    b,x1                    ; running := delayed

        move    x1,x:(r7+$3c)           ; b2, for the next sample's cross-feed
        move    x:(r7+$2d),a
        add     x1,a
        move    a,x:(r7+$2d)            ; wet R += b2

; a tank sample emits the OLDER of the two tank outputs, overwriting the
; interpolated value computed above: every sample then carries the same
; two-sample latency, and the off sample in between is their exact mean.
        move    x:(r7+$2e),a
        move    a,x:(r7+$34)
        move    x:(r7+$33),a
        move    a,x:(r7+$35)

; ---- makeup, WIDTH, MIX -----------------------------------------------------
vv_off:
        move    x:(r7+$34),a
        asl     #$2,a,a                 ; makeup for the /4 at the input
        move    a,x:(r7+$34)
        move    x:(r7+$35),a
        asl     #$2,a,a
        move    a,x:(r7+$35)
        move    x:(r7+$34),a
        move    x:(r7+$35),b
        move    a,x0
        add     b,a
        asr     #$1,a,a                 ; the mono fold
        move    a,x1
        move    x0,a
        sub     x1,a                    ; L - mono
        move    a,x0
        move    x1,a
        move    x:(r7+$25),y1           ; WIDTH
        mac     x0,y1,a                 ; mono + w*(L - mono)
        move    a,x:(r7+$34)
        move    b,a
        sub     x1,a                    ; R - mono
        move    a,x0
        move    x1,a
        mac     x0,y1,a
        move    a,x:(r7+$35)
        move    x:(r7+$34),a            ; MIX: out = dry + m*(wet-dry)
        move    x:(r0),b
        sub     b,a
        move    a,x0
        move    b,a
        move    x:(r7+$24),y1
        mac     x0,y1,a
        move    a,x:(r0)
        move    x:(r7+$35),a
        move    x:(r0+n0),b
        sub     b,a
        move    a,x0
        move    b,a
        mac     x0,y1,a
        move    a,x:(r0+n0)
        move    #>$2,n0
        move    (r0)+n0
        move    #>$1,n0
vv_end:
        nop

; ---- the counters go back to the instance block ----------------------------
        move    r5,a
        move    a,x:(r7+$26)
        move    r1,a
        move    a,x:(r7+$36)
        move    r2,a
        move    a,x:(r7+$28)
        rts
