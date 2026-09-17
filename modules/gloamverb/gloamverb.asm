; ---------------------------------------------------------------------------
; Gloam -- a small four-line Hadamard-mixed FDN insert, DARK REV's replacement.
;
; No LFO, no interpolation, no input diffuser: four FIXED-TAP 4096-word lines
; (compile-time offsets, chosen with no simple common ratio so the
; un-modulated tank does not ring on one pitch), one-pole damping inside the
; feedback path, a 4x4 Hadamard butterfly (two sum/difference stages,
; normalised by one right shift so the matrix itself adds no gain), a short
; pre-delay ahead of the tank, WIDTH and MIX at the end. Closer in spirit to
; Airwindows' VerbTiny (small, cheap, Hadamard-butterflied, no modulation)
; than to this repo's own BusVerb (eight modulated lines, input diffuser,
; shimmer) -- deliberately smaller, since this stands in for a per-track
; stock effect four tracks on a core can select at once.
;
; ---- buffer (Y, fixed literals -- core-private, one Gloam per core) -------
;   line 0   Y:0x4000..0x4FFF   4096 words, tap  1327 (comp 0xAD1)
;   line 1   Y:0x5000..0x5FFF   4096 words, tap  1979 (comp 0x845)
;   line 2   Y:0x6000..0x6FFF   4096 words, tap  2663 (comp 0x599)
;   line 3   Y:0x7000..0x7FFF   4096 words, tap  3541 (comp 0x22B)
;   pre      Y:0x8000..0x87FF   2048 words, tap from the PRE knob
; 18,432 of the 32,768-word per-core FX2-instance region; the same ground
; BusVerb's tank and Nimbus's line use -- one buffered module per core.
;
; ---- the per-sample shape ---------------------------------------------------
; All four lines share ONE write pointer W (same size, so one shared phase):
;   raw_i  = line_i[(W + comp_i) & 0xFFF]         -- comp_i = 4096 - tap_i
;   damp_i = damp_i + DAMP*(raw_i - damp_i)         [persistent one-pole]
;   proc_i = damp_i * DECAY                         [this feeds the matrix]
;   v = H4 * proc, two sum/difference stages, each v_i >>= 1 (normalise)
;   v_i += (+/-)0.5*preOut                          [alternating sign inject]
;   line_i[W & 0xFFF] = v_i
;   wetL = v1, wetR = v2                            -- two orthogonal H4 rows,
;                                                       decorrelated for free
; W advances by one, masked, after all four lines. The pre-delay line (its
; own write pointer Wp, own mask 0x7FF) is written with mono_in and read
; PRE samples behind every sample, feeding proc's injection above.
;
; ---- r7 slots ---------------------------------------------------------------
;   $20 DECAY (Q23, per block)      $21 DAMP (Q23, per block)
;   $22 PRE complement 0..2047 (per block)   $23 MIX (Q23, per block)
;   $24 WIDTH (Q23, per block)
;   $25..$28 damp state, lines 0..3 (PERSISTENT)
;   $29 W, tank write pointer (PERSISTENT, masked on load and save)
;   $2a Wp, pre-delay write pointer (PERSISTENT, masked on load and save)
;   $2b warm tag|count (PERSISTENT)     $2c mono_in (per sample)
;   $2d preOut (per sample)             $2e..$31 u0..u3 / v0..v3 (per sample)
;   $32 wetL   $33 wetR (per sample)    $34 warm count stash (per call)
;
; ---- traps this code is written to avoid (CLAUDE.md) ------------------------
; Every `mpy` here is `mpy x0,y1` (known-signed encoding; DAMP/DECAY/WIDTH/MIX
; and the injection gain are all knob-derived or a positive constant, so the
; sign risk `mpysu` -- x0,y0 or x1,x0 -- would carry is moot, but the operand
; order is still always the audited-signed one). Every `and` (the W/Wp masks,
; the page-2 field mask) is followed by the A2-clean dance (`move a1,x0 /
; move x0,a`) before the value is stored or added to a base literal; `asr`
; (arithmetic, not a hand-rolled mask) needs no such dance and gets none,
; matching Nimbus's mono-sum and BusVerb's Hadamard normalisation. The tank
; is fully unrolled (four straight-line blocks, no `do` loop over lines) so
; no Tcc pair shares a compare across code that might grow between them, and
; no address register's m/n modulo state is load-bearing anywhere in this
; file -- every buffer address is computed as a full literal + masked offset,
; the same manual-wrap idiom Nimbus's single buffer uses, chosen over
; BusVerb's hardware-AGU-modulo tank addressing specifically to avoid the
; alignment precondition that mode depends on.
; ---------------------------------------------------------------------------

init:
        rts

proc:
        move    #>$ffffff,m1
        move    #>$ffffff,m2

; ---- warm-up: the tagged-counter idiom, sized to this buffer -------------
; 144 blocks x 128 words = 18,432 = the whole allocation (0x4000..0x87FF).
        move    x:(r7+$2b),a
        move    #>$fffe00,x0
        and     x0,a
        move    a1,x0
        move    x0,a
        move    #>$2e0000,x0
        cmp     x0,a
        beq     gv_wtag
        clr     a
        bra     gv_wrun
gv_wtag:
        move    x:(r7+$2b),a
        move    #>$1ff,x0
        and     x0,a
        move    a1,x0
        move    x0,a
        move    #>$90,x0                ; 144
        cmp     x0,a
        bge     gv_wdone
gv_wrun:
        move    a,x:(r7+$34)
        asl     #$7,a,a                 ; count*128
        add     #>$4000,a
        move    a,r1
        clr     b
        do      #128,>gv_wz
        move    b,y:(r1)+
gv_wz:
        nop
        move    b,x:(r7+$29)            ; W = 0
        move    b,x:(r7+$2a)            ; Wp = 0
        move    b,x:(r7+$25)            ; damp states = 0
        move    b,x:(r7+$26)
        move    b,x:(r7+$27)
        move    b,x:(r7+$28)
        move    x:(r7+$34),a
        add     #>$1,a
        add     #>$2e0000,a
        move    a,x:(r7+$2b)
        rts                             ; frames untouched: pure dry out
gv_wdone:

; ---- per-block knob decode --------------------------------------------------
        move    x:(r6+$0),x0            ; DECAY, straight Q23 (val/128)
        move    x0,x:(r7+$20)
        move    x:(r6+$1),x0            ; DAMP, straight Q23
        move    x0,x:(r7+$21)
        move    x:(r6+$3),x0            ; MIX, straight Q23
        move    x0,x:(r7+$23)
; WIDTH: page 2 slot 6, $c's knob field (bits 16-23)
        move    x:(r6+$c),a
        and     #>$7f0000,a
        move    a1,x0
        move    x0,a
        move    a,x:(r7+$24)
; PRE -> pre-delay complement: samples = PRE_int * 16 (0..2032), comp = 2048 - samples
        move    x:(r6+$2),a
        asr     #$10,a,a                ; integer knob 0..127
        asl     #$4,a,a                 ; *16 -> 0..2032 samples
        move    a,x0
        move    #>$800,a                ; 2048
        sub     x0,a
        and     #>$7ff,a
        move    a1,x0
        move    x0,a
        move    a,x:(r7+$22)

; ---- per-sample loop --------------------------------------------------------
        move    #>$1,n0
        do      n7,>gv_end

; mono in, and the pre-delay line
        move    x:(r0),a
        move    x:(r0+n0),x0
        add     x0,a
        asr     #$1,a,a
        move    a,x:(r7+$2c)
        move    x:(r7+$2a),a            ; Wp
        and     #>$7ff,a
        move    a1,x0
        move    x0,a
        add     #>$8000,a
        move    a,r1
        move    x:(r7+$2c),x0
        move    x0,y:(r1)               ; pre[Wp] = mono_in
        move    x:(r7+$22),x0           ; PRE complement
        move    x:(r7+$2a),a
        add     x0,a
        and     #>$7ff,a
        move    a1,x0
        move    x0,a
        add     #>$8000,a
        move    a,r1
        move    y:(r1),a
        move    a,x:(r7+$2d)            ; preOut
        move    x:(r7+$2a),a
        add     #>$1,a
        and     #>$7ff,a
        move    a1,x0
        move    x0,a
        move    a,x:(r7+$2a)            ; Wp advances

; ---- line 0: tap 1327, comp 0xAD1 -------------------------------------------
        move    #>$ad1,x0
        move    x:(r7+$29),a
        add     x0,a
        and     #>$fff,a
        move    a1,x0
        move    x0,a
        add     #>$4000,a
        move    a,r1
        move    y:(r1),a                ; raw_0
        move    x:(r7+$25),b            ; damp_0
        sub     b,a
        move    a,x0
        move    x:(r7+$21),y1           ; DAMP
        mpy     x0,y1,a
        add     b,a
        move    a,x:(r7+$25)            ; damp_0 updated
        move    a,x0
        move    x:(r7+$20),y1           ; DECAY
        mpy     x0,y1,a
        move    a,x:(r7+$2e)            ; u0 = proc_0

; ---- line 1: tap 1979, comp 0x845 -------------------------------------------
        move    #>$845,x0
        move    x:(r7+$29),a
        add     x0,a
        and     #>$fff,a
        move    a1,x0
        move    x0,a
        add     #>$5000,a
        move    a,r1
        move    y:(r1),a
        move    x:(r7+$26),b
        sub     b,a
        move    a,x0
        move    x:(r7+$21),y1
        mpy     x0,y1,a
        add     b,a
        move    a,x:(r7+$26)
        move    a,x0
        move    x:(r7+$20),y1
        mpy     x0,y1,a
        move    a,x:(r7+$2f)            ; u1 = proc_1

; ---- line 2: tap 2663, comp 0x599 -------------------------------------------
        move    #>$599,x0
        move    x:(r7+$29),a
        add     x0,a
        and     #>$fff,a
        move    a1,x0
        move    x0,a
        add     #>$6000,a
        move    a,r1
        move    y:(r1),a
        move    x:(r7+$27),b
        sub     b,a
        move    a,x0
        move    x:(r7+$21),y1
        mpy     x0,y1,a
        add     b,a
        move    a,x:(r7+$27)
        move    a,x0
        move    x:(r7+$20),y1
        mpy     x0,y1,a
        move    a,x:(r7+$30)            ; u2 = proc_2

; ---- line 3: tap 3541, comp 0x22B -------------------------------------------
        move    #>$22b,x0
        move    x:(r7+$29),a
        add     x0,a
        and     #>$fff,a
        move    a1,x0
        move    x0,a
        add     #>$7000,a
        move    a,r1
        move    y:(r1),a
        move    x:(r7+$28),b
        sub     b,a
        move    a,x0
        move    x:(r7+$21),y1
        mpy     x0,y1,a
        add     b,a
        move    a,x:(r7+$28)
        move    a,x0
        move    x:(r7+$20),y1
        mpy     x0,y1,a
        move    a,x:(r7+$31)            ; u3 = proc_3

; ---- 4x4 Hadamard: two sum/difference stages --------------------------------
; stage 1: (u0,u1) and (u2,u3)
        move    x:(r7+$2e),a
        move    x:(r7+$2f),x0
        move    a,b
        add     x0,a
        sub     x0,b
        move    a,x:(r7+$2e)            ; u0' = u0+u1
        move    b,x:(r7+$2f)            ; u1' = u0-u1
        move    x:(r7+$30),a
        move    x:(r7+$31),x0
        move    a,b
        add     x0,a
        sub     x0,b
        move    a,x:(r7+$30)            ; u2' = u2+u3
        move    b,x:(r7+$31)            ; u3' = u2-u3
; stage 2: (u0',u2') and (u1',u3')
        move    x:(r7+$2e),a
        move    x:(r7+$30),x0
        move    a,b
        add     x0,a
        sub     x0,b
        asr     #$1,a,a                 ; v0, normalised
        asr     #$1,b,b                 ; v2, normalised
        move    a,x:(r7+$2e)
        move    b,x:(r7+$30)
        move    x:(r7+$2f),a
        move    x:(r7+$31),x0
        move    a,b
        add     x0,a
        sub     x0,b
        asr     #$1,a,a                 ; v1, normalised
        asr     #$1,b,b                 ; v3, normalised
        move    a,x:(r7+$2f)
        move    b,x:(r7+$31)

; ---- wet taps: two orthogonal rows, decorrelated for free -------------------
        move    x:(r7+$2f),a            ; v1
        move    a,x:(r7+$32)            ; wetL
        move    x:(r7+$30),a            ; v2
        move    a,x:(r7+$33)            ; wetR

; ---- injection: alternating-sign half of the pre-delayed input -------------
        move    x:(r7+$2d),x0           ; preOut
        move    #>$400000,y1            ; 0.5
        mpy     x0,y1,a                 ; halfPre
        move    a,x1                    ; parked across the four adds below
        move    x:(r7+$2e),a
        add     x1,a
        move    a,x:(r7+$2e)            ; v0 +
        move    x:(r7+$2f),a
        sub     x1,a
        move    a,x:(r7+$2f)            ; v1 -
        move    x:(r7+$30),a
        add     x1,a
        move    a,x:(r7+$30)            ; v2 +
        move    x:(r7+$31),a
        sub     x1,a
        move    a,x:(r7+$31)            ; v3 -

; ---- write back: v_i -> line_i[W & 0xfff] -----------------------------------
        move    x:(r7+$29),a
        and     #>$fff,a
        move    a1,x0
        move    x0,a
        move    a,x1                    ; masked W, parked across four writes
        move    x1,a
        add     #>$4000,a
        move    a,r1
        move    x:(r7+$2e),x0
        move    x0,y:(r1)
        move    x1,a
        add     #>$5000,a
        move    a,r1
        move    x:(r7+$2f),x0
        move    x0,y:(r1)
        move    x1,a
        add     #>$6000,a
        move    a,r1
        move    x:(r7+$30),x0
        move    x0,y:(r1)
        move    x1,a
        add     #>$7000,a
        move    a,r1
        move    x:(r7+$31),x0
        move    x0,y:(r1)
        move    x:(r7+$29),a
        add     #>$1,a
        and     #>$fff,a
        move    a1,x0
        move    x0,a
        move    a,x:(r7+$29)            ; W advances

; ---- WIDTH: blend wet L/R toward their mono sum -----------------------------
        move    x:(r7+$32),a            ; wetL
        move    x:(r7+$33),b            ; wetR
        move    a,x0
        add     b,a
        asr     #$1,a,a                 ; monoW
        move    a,x1                    ; parked
        move    x0,a                    ; wetL
        sub     x1,a                    ; wetL - monoW
        asr     #$1,a,a
        move    a,x0
        move    x:(r7+$24),y1           ; WIDTH
        mpy     x0,y1,a
        asl     #$1,a,a
        add     x1,a
        move    a,x:(r7+$32)            ; wetL, widthed
        move    b,a                     ; wetR
        sub     x1,a                    ; wetR - monoW
        asr     #$1,a,a
        move    a,x0
        mpy     x0,y1,a
        asl     #$1,a,a
        add     x1,a
        move    a,x:(r7+$33)            ; wetR, widthed

; ---- MIX: out = dry + m*(wet-dry) -------------------------------------------
        move    x:(r7+$32),a            ; wetL
        move    x:(r0),b
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        move    x:(r7+$23),y1           ; MIX
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    a,x:(r0)
        move    x:(r7+$33),a            ; wetR
        move    x:(r0+n0),b
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    a,x:(r0+n0)
        move    #>$2,n0
        move    (r0)+n0
        move    #>$1,n0
gv_end:
        nop
        rts
