; ---------------------------------------------------------------------------
; CHARACTER -- fold, texture (Pockey), saturate, tilt, compress, width.
;
; Insert contract (modules/ripple/ripple_svf.asm): frames in place at
; x:(r0)/x:(r0+n0), knobs from r6, state in this instance's r7 block. The
; station never touches the bus (the return it carried on T8 went 20 Sep
; 2026: each engine prints its wet on its own host).
;
; ---- the chain, fixed order ----------------------------------------------
;   f     = fold(x * gain) / gain                       FOLD (held level)
;   p     = pockey(f; TXTR)                              TXTR (0 = skip)
;   s     = TAPE: TapeHead(f; DRV) | TUBE | INFL          DRV, SAT (held level)
;   t     = tilt(s; TONE)                                TONE (64 = flat)
;   c     = t * gain(env)                                COMP (GLUE on the master)
;   w     = width(c)                                     WDTH
;   out   = x + MIX*(w - x)                              MIX
; Distortion BEFORE dynamics: a compressor after the dirt is a tool, before
; it is a fader for the dirt.
;
; ---- the compressor (JClones AC1, MIT) -------------------------------------
; AC1's console channel law for both flavours: |key| smoothed by attack /
; release, Lv = K * level_s, gr = (Lv^2/2 - 1)^2 + a*Lv clamped at 1 -- a
; dip around Lv = 1 whose depth is a = 0.75 - 0.675*COMP/128 -- and a
; makeup 1/(1 - 0.3375*COMP/128). GLUE: 0.5 / 500 ms, K = 3. COMP: 0.5 /
; 63 ms, K = 4 (release coefficient $bd0 = 3024/2^23 per sample, tau = 62.9
; ms; written as 50 ms until 21 Sep 2026). COMP 0 skips the stage, bit-exact.
; The detector reads x:(r7+$32), the KEY; the station writes its own input
; there.
;
; ---- r7 slots -------------------------------------------------------------
;   $15/$16 L y1/y2, $17/$18 R y1/y2: TapeHead's SVF states (PERSISTENT, /4)
;   $29 sat mode (0 TAPE = TapeHead, 1 TUBE = DaTube, 2 INFL = OInflator)  $30 k2  $31 k3mag  $48 d/8 (per block)
;   per block:
;   $20 m (MIX)   $21 fold gain/64  $22 K/4 (the detector's)  $2a TAPE trim (1/11)/d8 + 0.023
;   $1d fold trim/2 (1/128)/gq   $24 tilt t/2   $26 comp amount    $27 makeup/4
;   $28 the dip's a   $29 sat mode   $2b width side gain
;   $2c width mid gain  $2d attack coeff   $2e release coeff
;   $40 FX2-slot flag (set at init: 1 = this instance is on FX2, dry; per block)
;   $41/$42 DC block L x1/y1, $43/$44 R x1/y1 (TUBE; PERSISTENT, zeroed at init; long-form slots)
;   $37 d/2  $38 d  $4c (0.5+d)/2  $39 comp/4 (TUBE, per block)   $3a e/2  $3b 1-e (INFL, per block)
;   $49 chtube's u/2 park (per sample)
;   $4d DRV==0: skip the saturator (per block)
;   per sample / persistent (all below $40: an r7 displacement past 63
;   assembles to the two-word long form):
;   $3f tilt lp L (PERSISTENT)   $23 tilt lp R (PERSISTENT)
;   TXTR (Pockey): $19/$1a held L/R, $1b/$1c last L/R, $25 pos/2, $46/$47
;   soften L/R (all PERSISTENT); per block $4e skip, $50 freq/2, $51 rez,
;   $52 4 rez, $53 1 - rez, $54 q4096, $55..$58 table bases; per sample
;   $4f wrap, $59 dry park, $5a 1 - pos, $5b pos, $5c d/2
;   $1e level_s (PERSISTENT)   $45 master flag (1 = position 3 on A: GLUE)
;   $1f gr (per sample)
;   $32 key    $33 dry L park   $34 dry R park
;   $35 scratch (wet L)          $36 scratch (wet R)
;
; ---- the master, by position ---------------------------------------------
; On the master (dispatch position 3 on payload A, track 8) COMP runs the
; GLUE law; everywhere else the channel law. Slot 4 is unused (the return
; level until 20 Sep 2026; a stored byte there is never read). SAT is TAPE /
; TUBE / INFL on every track; no knob changes meaning by mode.
;
; CYCLES_FORWARD_BRANCHES -- the branches in the sample loop are forward and
; skip work, so the word span is the worst-case cycle count
; (tools/build/cycle_count.py). The
; saturation character and the compressor mode are per-block COEFFICIENTS
; for exactly this reason: a dispatch inside the loop cannot be priced.
;
; Every mpy is `mpy x0,y1` (the audited-signed encoding) except the three
; in the callees whose second operand is a non-negative coefficient, each
; commented at its site. Every Tcc reads the ONE compare above it with nothing but moves
; between (the flag-clobber trap).
; ---------------------------------------------------------------------------

init:
; ROTINIT
; ---- FX1 ONLY: the allocator base decides, at init --------
; Modulation's idiom (modules/modulation/modulation.asm): X:0x213 points at
; this instance's entry in the base table, valid HERE and nowhere else. FX1
; slots are below 0x4000, FX2 slots at or above it. An FX2 instance runs as
; a dry pass -- proc returns before it touches a frame or the bus -- so a
; part that names this id on FX2 (the stock id both menus share) costs its
; core nothing: the rig's cycle envelope is priced with the stations on FX1
; only (tools/harness/pressure.py), and the FX2 chooser hides them.
; sub/tst rather than cmp: the cmp-encodes-as-max family (CLAUDE.md).
        move    x:>$213,r4
        move    #>$ffffff,m4
        move    x:(r4),x0
        move    x0,a
        move    #>$4000,x0
        sub     x0,a                    ; base - 0x4000
        clr     b                       ; b = 0 BEFORE the tst (the flag trap)
        move    #>$1,x0
        tst     a
        tpl     x0,b                    ; base >= 0x4000: an FX2 slot
        move    b,x:(r7+$40)          ; 1 = dry pass
        clr     a
        move    a,x:(r7+$41)            ; the DC blocker's state, both channels
        move    a,x:(r7+$42)
        move    a,x:(r7+$43)
        move    a,x:(r7+$44)
        move    a,x:(r7+$15)            ; TapeHead's SVF states, both channels
        move    a,x:(r7+$16)
        move    a,x:(r7+$17)
        move    a,x:(r7+$18)
        move    a,x:(r7+$1e)            ; the compressor's state: AC1 level_s
        move    a,x:(r7+$3f)            ; the tilt's two low-pass states, the
        move    a,x:(r7+$23)            ; master flag: every slot read before
        move    a,x:(r7+$45)            ; written (14 Sep 2026, verify_dirtystate)
        move    a,x:(r7+$19)            ; TXTR's states: held L/R, last L/R,
        move    a,x:(r7+$1a)            ; the hold position, soften L/R
        move    a,x:(r7+$1b)
        move    a,x:(r7+$1c)
        move    a,x:(r7+$25)
        move    a,x:(r7+$46)
        move    a,x:(r7+$47)
        move    #>$7fffff,x0
        move    x0,x:(r7+$1f)           ; gr = unity
        rts

proc:
        move    x:(r7+$40),a           ; an FX2 slot: dry, nothing written
        tst     a
        bne     ch_end
; ===========================================================================
; PER-BLOCK KNOB DECODE
; ===========================================================================
; MIX: page-1 slot 5 since 16 Sep 2026; TONE page-1 slot 4 since 20 Sep
        move    x:(r6+$5),a             ; a knob word: bit 23 clear, a2 = 0
        move    a1,x:(r7+$20)           ; m (a1 straight to memory)
        move    x:(r6+$1),x0            ; the knob word IS FOLD/128 in Q23
        move    #$5e,y1                 ; 47/64 (short immediate: bits 23-16)
        mpy     x0,y1,a                 ; (47/64)*(FOLD/128)
        add     #>$020000,a             ; + 1/64 -> gain/64, 0.016 .. 0.75
        move    a,x:(r7+$21)            ; gq
        move    a,x0                    ; gq = the denominator, >= 1/64
        move    #>$010000,a             ; 1/128 (a clean load: a0 = 0)
        andi    #$fe,ccr
        rep     #$18
        div     x0,a
        move    a0,x0
        move    x0,x:(r7+$1d)           ; fold trim/2
; DRV 0 = NO saturation stage at all (13 Sep 2026): every mode's curve is
; unity only for small signals. A per-block flag ($4d) skips the stage per
; sample -- a forward skip, the class CYCLES_FORWARD_BRANCHES admits -- so
; DRV 0 is bit-exact in
; every mode on every track. (The DC blocker / low-pass state is NOT cleared
; while skipped -- 9 words the BURN build on payload A did not have; a later
; DRV resumes from stale filter history, one small step at most.)
        move    x:(r6+$0),a             ; DRV
        clr     b                       ; b = 0 BEFORE the tst (the flag trap)
        move    #>$1,x0
        tst     a
        teq     x0,b                    ; DRV == 0 -> skip flag 1
        move    b,x:(r7+$4d)
        move    x:(r6+$4),a             ; TONE: page-1 slot 4 since 20 Sep 2026
        and     #>$7f0000,a             ; (the return's slot); a knob word, TONE << 16
        sub     #>$400000,a
        move    a,x:(r7+$24)            ; t/2, -0.5 .. +0.49
; COMP amount, straight from the knob
        move    x:(r6+$3),x0
        move    x0,x:(r7+$26)
        move    x:(r7+$45),a
        tst     a
        bne     ch_cglue
        move    #>$7fffff,x0            ; COMP: K/4 = 1.0 (4x), release 63 ms
        move    x0,x:(r7+$22)
        move    #>$000bd0,x0
        move    x0,x:(r7+$2e)
        bra     ch_cset
ch_cglue:
        move    #$60,x0                 ; GLUE: K/4 = 0.75 (3x), release 500 ms
        move    x0,x:(r7+$22)
        move    #>$00017c,x0
        move    x0,x:(r7+$2e)
ch_cset:
        move    #>$05ce1b,x0            ; attack 0.5 ms: 1/(fs*t), both
        move    x0,x:(r7+$2d)
        move    x:(r7+$26),x0           ; COMP/128
        move    #>$566666,y1            ; 0.675
        mpy     x0,y1,a
        neg     a
        add     #>$600000,a             ; a = 0.75 - 0.675*COMP/128
        move    a,x:(r7+$28)
        move    #>$2b3333,y1            ; 0.3375
        mpy     x0,y1,a
        neg     a
        add     #>$7fffff,a             ; den = 1 - 0.3375*COMP/128 (0.66..1)
        move    a,x0
        move    #$20,a                  ; num = 0.25 (a1), a2 = a0 = 0 (short: bits 23-16)
        andi    #$fe,ccr
        rep     #$18
        div     x0,a
        move    a0,x0
        move    x0,x:(r7+$27)           ; m/4 = 0.25/den: makeup/4
ch_cdone:
; SAT character (slot 6 select of r6+$c, the knob field) -> a MODE FLAG and per-mode words,
; so the sample loop's SAT stage is a MODEFORK: TAPE (0) = TapeHead, TUBE (1)
; = DaTube, INFL (2) = OInflator (all JClones, MIT;). The tanh
; curve, its P table, FUZZ and the drive-keyed low-pass are gone. A stored 3
; (the old BUS) lands on TAPE. Per-mode words, all from DRV = d (0..0.992):
;   TUBE  $37 = d/2 (the positive half's scale)  $38 = d (the negative half's)
;         ($4c = (0.5 + d)/2 input gain and $39 = comp/2 below, every mode)
;         (the DC blocker's k = 1, R = 0.999 are chtube's own immediates)
;   INFL  $3a = e/2 with e = d            $3b = 1 - e
        clr     a
        move    a,x:(r7+$29)            ; sat mode: 0 = TAPE
        move    x:(r6+$c),a             ; SAT, slot 6 = $c's knob field
        and     #>$ff0000,a
        cmp     #>$10000,a
        beq     ch_stube
        cmp     #>$20000,a
        beq     ch_sinfd
        bra     ch_sdone                ; TAPE (a stored 3, the old BUS, too)
ch_stube:
        move    #>$1,x0
        move    x0,x:(r7+$29)           ; sat mode 1: TUBE
        move    x:(r6+$0),a             ; d = DRV/128
        move    a,x:(r7+$38)            ; the negative half: d
        asr     #$1,a,a
        move    a,x:(r7+$37)            ; the positive half: d/2
                                        ; (the DC blocker -- TUBE's asymmetry
                                        ; leaves DC; JClones' own 3 Hz remover,
                                        ; ours R = 0.999, ~7 Hz -- is chtube's,
                                        ; its k and R immediates there)
        bra     ch_sdone
ch_sinfd:
        move    #>$2,x0
        move    x0,x:(r7+$29)           ; sat mode 2: INFL
        move    x:(r6+$0),a             ; e = DRV/128
        move    a,x0
        asr     #$1,a,a
        move    a,x:(r7+$3a)            ; e/2
        move    #>$7fffff,a
        sub     x0,a
        move    a,x:(r7+$3b)            ; 1 - e (DRV 0 never gets here: the skip)
ch_sdone:
; ---- the master flag, BY POSITION ($45: GLUE) ---------------------------
; Track 8 is dispatch position 3 on PAYLOAD A; the mirror position on core 1
; is track 4. An insert carries no per-payload literal (an FX1 module may own
; no buffers, so the build refuses it a base), so the core is read off the
; DISPATCH TABLE: in the specialized image BusVerb (id 0x07) is real on
; payload A and ALIASED TO SEND (id 0x09) on payload B -- X:$215+7 ==
; X:$215+9 there. Under the DEV hatch everything is payload A and the test
; allows. A remix WITHOUT BusVerb has no master anywhere (its id aliases on
; both cores).
        move    x:>$21c,a               ; INIT_TABLE[REVERB SERVER]
        move    x:>$21e,x0              ; INIT_TABLE[SEND]
        cmp     x0,a
        beq     ch_nopos                ; the alias: payload B
        move    r7,a
        and     #>$ff00,a
        move    #>$6a00,x0
        cmp     x0,a
        beq     ch_master
ch_nopos:
        clr     a
        move    a,x:(r7+$45)            ; not track 8: the channel law
        bra     ch_pos3
ch_master:
        move    #>$1,x0
        move    x0,x:(r7+$45)           ; the master: GLUE
ch_pos3:
        move    x:(r6+$0),a             ; d = DRV/128
        move    a,x1                    ; (x1 = DRV/128 for TapeHead's words below)
        move    a,x0
        move    #>$37445f,y1            ; 0.43175 = 1.727/4
        mpy     x0,y1,a
        add     #>$200000,a             ; (1 + 1.727 d)/4
        move    a,x0
        move    x1,a
        asr     #$1,a,a
        add     #>$200000,a             ; (0.5 + d)/2
        move    a,x:(r7+$4c)            ; TUBE's input gain, halved
        move    a,y1
        mpy     x0,y1,a                 ; D8
        move    a,x0                    ; den
        move    #$08,y1                 ; 1/16
        move    y1,a                    ; a clean load: a0 = 0 for the divide
        andi    #$fe,ccr                ; carry clear
        rep     #$18
        div     x0,a                    ; 24 quotient bits land in a0
        move    a0,x0
        move    x0,x:(r7+$39)           ; comp/2
; the P table: TUBE_UP (17 pairs, DaTube's curve) then TAPE_D8 (9 words).
        move    #>$fab1e0,r1            ; TUBE_UP -- rewritten by build_bus.py
        move    #>$ffffff,m1
        move    r1,r2
        move    (r2)+                   ; r2 = its slopes
; ---- TapeHead's per-block words (TAPE only reads them; computed always) --
; d8 = d/8 from TAPE_D8 (the 17 words after TUBE_UP's 34), interpolated over
; DRV/128 (idx = DRV >> 19, frac = the 19 bits under it); k2 linear in
; TONE/128 (2.1 -> 5 kHz);
; k3mag = 1.4*k2 = (0.7*k2)*2. The table sits in the manifest after DaTube's
; curve, so the one P-table literal above still finds everything.
        move    r1,r3
        move    #$22,n3                 ; 34 (short immediate: an integer)
        move    #>$ffffff,m3
        move    x1,a                    ; DRV/128
        asr     #$13,a,a
        move    (r3)+n3                 ; r3 = TAPE_D8
        move    a1,n3
        move    x1,a
        and     #>$7ffff,a
        asl     #$4,a,a
        move    a,x0                    ; frac
        move    (r3)+n3
        move    p:(r3)+,y0              ; D8[idx]
        move    p:(r3),b                ; D8[idx+1]
        move    y0,a
        sub     a,b                     ; diff (> 0: the table rises)
        move    b,y1
        mpy     x0,y1,a
        add     y0,a
        move    a,x:(r7+$48)            ; d8 = d/8, 0.1 .. 0.98
        move    a,x0                    ; d8 = the denominator
        move    #>$0ba2e9,a             ; 1/11 (a clean load: a0 = 0)
        andi    #$fe,ccr                ; carry clear
        rep     #$18
        div     x0,a                    ; 24 quotient bits land in a0
        move    a0,x0                   ; (1/11)/d8, flat unity
        move    x0,a
        add     #>$02fb7f,a             ; 0.0233
        move    a,x:(r7+$2a)            ; TAPE trim
        move    #>$3fb89c,a             ; k2 = 0.4978: the split at its middle
        move    a,x:(r7+$30)            ; (3.7 kHz; TONE is the tilt since 14 Sep 2026)
        move    a,x0
        move    #>$59999a,y1            ; 0.7: k3mag = 1.4 * k2, halved
        mpy     x0,y1,a
        asl     #$1,a,a
        move    a,x:(r7+$31)            ; k3mag (< 0.98)
; ---- TXTR: Airwindows Pockey (Chris Johnson, MIT, 2022) -------
        move    x:(r6+$2),a             ; t
        clr     b                       ; b = 0 BEFORE the tst (the flag trap)
        move    #>$1,x0
        tst     a
        teq     x0,b
        move    b,x:(r7+$4e)            ; 1 = TXTR 0: skip
        move    a,x1                    ; t
        move    #>$7fffff,a
        sub     x1,a                    ; 1 - t
        move    a,x0
        move    a,y1
        mpy     x0,y1,a                 ; (1-t)^2
        move    a,y1
        mpy     x0,y1,a                 ; (1-t)^3
        move    a,x0
        move    #>$226f31,y1            ; (0.618 - 0.08)/2
        mpy     x0,y1,a
        add     #>$051eb8,a             ; + 0.08/2
        move    a,x:(r7+$50)            ; freq/2
        move    x1,x0
        move    #>$4f1bbd,y1            ; 0.618
        mpy     x0,y1,a                 ; 0.618 t
        move    a,x0
        move    a,y1
        mpy     x0,y1,a
        move    a,y1
        mpy     x0,y1,a                 ; (0.618 t)^3
        add     #>$000800,a             ; + 2^-12
        move    a,x:(r7+$51)            ; rez, 2^-12 .. 0.2364
        move    a,x0
        asl     #$2,a,a
        move    a,x:(r7+$52)            ; 4 rez (< 0.95)
        move    #>$7fffff,a
        sub     x0,a
        move    a,x:(r7+$53)            ; 1 - rez
        move    #>$000800,a             ; 2^-12 (a clean load: a0 = 0)
        andi    #$fe,ccr
        rep     #$18
        div     x0,a                    ; 2^-12 / rez, <= 1 (= 1 only at t = 0, skipped)
        move    a0,x0
        move    x0,x:(r7+$54)           ; q4096
        move    #>51,n1
        lua     (r1)+n1,r3              ; ENC (r1/r2 are TUBE's own table
        move    r3,x:(r7+$57)           ; registers in the loop: hands off)
        move    #>257,n3
        lua     (r3)+n3,r5              ; DEC
        move    r5,x:(r7+$55)
; WDTH -> mid and side gains. 64 = (1, 1); 0 = (1, 0) mono; 127 = (1, ~2).
; side gain = WDTH/64, mid stays 1 -- widening only touches the difference,
; so a mono source is untouched at every setting.
        move    x:(r6+$c),a             ; WDTH: page-2 slot 7 since 20 Sep 2026,
        and     #>$7f00,a               ; $c's companion field (bits 8-15; SAT's
        asl     #$8,a,a                 ; select is the knob field) -> WDTH << 16
; ⚠️ STORED HALVED. A y1 operand is a FRACTION, and a side gain of WDTH/64
; tops out near 2.0, which would wrap the word. The knob's own value IS
; WDTH/128, so it is stored as-is and the product is doubled back in the
; accumulator's guard bits. 64 -> 0.5 -> x2 = exactly 1.0, i.e. untouched.
        move    a1,x:(r7+$2b)           ; side gain / 2 (a1 straight to memory)
; ---- BYPASS: the defaults are a bit-exact passthrough ---------------------
; DRV 0, FOLD 0, TXTR 0, TONE 64, COMP 0, MIX 127, WDTH 64. Every part that
; ever chose LO-FI runs this after the flash, so the neutral block does
; nothing at all.
        move    x:(r6+$0),a             ; DRV
        tst     a
        bne     ch_live
        move    x:(r6+$1),a             ; FOLD
        tst     a
        bne     ch_live
        move    x:(r6+$2),a             ; TXTR
        tst     a
        bne     ch_live
        move    x:(r7+$24),a            ; the tilt's t/2 (TONE 64 = 0)
        tst     a
        bne     ch_live
        move    x:(r6+$3),a             ; COMP
        tst     a
        bne     ch_live
        move    x:(r7+$2b),a            ; side gain/2: 64 -> exactly 0.5
        move    #$40,x0
        cmp     x0,a
        beq     ch_bypass
ch_live:

; ===========================================================================
; THE SAMPLE LOOP
; ===========================================================================
        move    #$1,n0                  ; (short immediate, stock's own form)
        move    x:(r7+$55),r5           ; TXTR's DEC table (r5 is free in the
        move    #>$ffffff,m5            ; loop); ENC goes into r3 per sample,
        move    #>$ffffff,m3            ; the SAT callees own r3 after that
        do      n7,>ch_end
; ---- park the dry, and take the key (the mono sum) ------------------------
        move    x:(r0),a
        move    a,x:(r7+$33)
        move    x:(r0+n0),x0
        move    x0,x:(r7+$34)
        add     x0,a
        asr     #$1,a,a
        move    a,x:(r7+$32)            ; key = mono in (the ->KEY hook)
; ---- FOLD: WarpFold's wrap-and-reflect, both channels --------------------
        move    x:(r7+$33),x0
        move    x:(r7+$21),y1           ; gq = gain/64
        mpy     x0,y1,a                 ; v/64
        asl     #$5,a,a                 ; v/2
        move    #$40,x1                 ; 0.5 (short immediate: bits 23-16)
        add     x1,a                    ; (v+1)/2
        move    a1,x1                   ; s = wrap(...), raw A1: the fold
        move    x1,a                    ; clean re-load, A2 consistent
        abs     a
        move    #$40,b                  ; 0.5, b2 = b0 = 0
        sub     b,a                     ; |s| - 0.5
        asl     #$1,a,a                 ; fold in [-1,1)
        move    a,x0
        move    x:(r7+$1d),y1           ; trim/2
        mpy     x0,y1,a
        asl     #$1,a,a                 ; the fold at a held level
        move    a,x:(r7+$35)            ; wet L
        move    x:(r7+$34),x0
        move    x:(r7+$21),y1
        mpy     x0,y1,a
        asl     #$5,a,a
        move    #$40,x1
        add     x1,a
        move    a1,x1
        move    x1,a
        abs     a
        move    #$40,b
        sub     b,a
        asl     #$1,a,a
        move    a,x0
        move    x:(r7+$1d),y1
        mpy     x0,y1,a
        asl     #$1,a,a
        move    a,x:(r7+$36)            ; wet R
; ---- TXTR: Airwindows Pockey (MIT, 2022), both channels -------------------
; mu-law encode -> quantise to rez -> x (1 - rez) -> decode (chtxc, on the
; magnitude; the sign comes back by Tcc), then the hold (a crossfade of the
; previous DRY sample and this coded one at the fractional hold instant,
; shared position) and the slew smoother (strength = jump x rate, <= 0.5).
        move    x:(r7+$4e),a
        tst     a
        bne     ch_notx
        move    x:(r7+$57),r3           ; ENC
        move    x:(r7+$25),a            ; pos/2
        move    x:(r7+$50),x0           ; freq/2
        add     x0,a
        move    a,y0                    ; the unwrapped position (< 1)
        clr     b                       ; wrap flag 0 BEFORE the sub (the flag trap)
        move    #>$1,x1
        move    #>$400000,x0            ; 0.5 (= a position of 1)
        sub     x0,a                    ; a = pos - 1 ...
        tlt     y0,a                    ; ... unless that is negative: no wrap
        tge     x1,b                    ; wrapped -> flag 1 (the same sub's flags)
        move    a,x:(r7+$25)
        move    b,x:(r7+$4f)
        asl     #$1,a,a                 ; pos (< 0.62)
        move    a,x:(r7+$5b)
        neg     a
        add     #>$7fffff,a
        move    a,x:(r7+$5a)            ; 1 - pos
; --- L ---
        move    x:(r7+$35),a
        move    a,x:(r7+$59)            ; the dry (Pockey's input)
        abs     a
        bsr     chtxc                   ; a = dec(quant(enc(|x|)))
        move    a,x0
        neg     a
        move    x:(r7+$59),b
        tst     b
        tpl     x0,a                    ; the sign back
; the hold, branch-free (cycle_count.py wants a straight loop): the wrap
; path is computed every sample and selected by the flag with Tcc.
        move    a,x0                    ; coded
        move    x:(r7+$5a),y1           ; 1 - pos
        mpy     x0,y1,a
        move    x:(r7+$1b),x0           ; last L (the previous dry)
        move    x:(r7+$5b),y1           ; pos
        mpy     x0,y1,b
        add     b,a                     ; heldN = last pos + coded (1 - pos)
        move    a,x1
        move    x:(r7+$19),x0           ; held
        mpy     x0,y1,b                 ; held pos
        move    x1,x0
        move    x:(r7+$5a),y1
        mpy     x0,y1,a                 ; heldN (1 - pos)
        add     b,a                     ; outW (if wrapped)
        move    a,y0                    ; outW
        move    x:(r7+$19),x0           ; held (old)
        move    x:(r7+$4f),a
        tst     a                       ; the wrap flag; two Tcc read it
        move    x0,b                    ; held' = held ...
        tne     x1,b                    ; ... or heldN when wrapped
        move    b,x:(r7+$19)
        move    x0,a                    ; out = held ...
        tne     y0,a                    ; ... or outW when wrapped
        move    a,x1                    ; out, for soften
        move    x:(r7+$46),b            ; soften L
        sub     b,a                     ; d = out - soften
        asr     #$1,a,a
        move    a,x:(r7+$5c)            ; d/2 (|d| <= 2)
        abs     a
        move    a,x0                    ; |d|/2
        move    x:(r7+$50),y1           ; freq/2
        mpy     x0,y1,a
        asl     #$2,a,a                 ; |d| freq
        move    #>$400000,x0
        cmp     x0,a
        tgt     x0,a                    ; s = min(0.5, |d| freq)
        move    a,y1
        move    x:(r7+$5c),x0
        mpy     x0,y1,a                 ; s d/2
        asl     #$1,a,a
        add     b,a                     ; y = soften + s d
        move    a,x:(r7+$35)
        move    x1,x:(r7+$46)           ; soften = out
        move    x:(r7+$59),x0
        move    x0,x:(r7+$1b)           ; last = the dry
; --- R ---
        move    x:(r7+$36),a
        move    a,x:(r7+$59)
        abs     a
        bsr     chtxc
        move    a,x0
        neg     a
        move    x:(r7+$59),b
        tst     b
        tpl     x0,a
        move    a,x0
        move    x:(r7+$5a),y1
        mpy     x0,y1,a
        move    x:(r7+$1c),x0           ; last R
        move    x:(r7+$5b),y1
        mpy     x0,y1,b
        add     b,a
        move    a,x1
        move    x:(r7+$1a),x0           ; held R
        mpy     x0,y1,b
        move    x1,x0
        move    x:(r7+$5a),y1
        mpy     x0,y1,a
        add     b,a
        move    a,y0
        move    x:(r7+$1a),x0
        move    x:(r7+$4f),a
        tst     a
        move    x0,b
        tne     x1,b
        move    b,x:(r7+$1a)
        move    x0,a
        tne     y0,a
        move    a,x1
        move    x:(r7+$47),b            ; soften R
        sub     b,a
        asr     #$1,a,a
        move    a,x:(r7+$5c)
        abs     a
        move    a,x0
        move    x:(r7+$50),y1
        mpy     x0,y1,a
        asl     #$2,a,a
        move    #>$400000,x0
        cmp     x0,a
        tgt     x0,a
        move    a,y1
        move    x:(r7+$5c),x0
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    a,x:(r7+$36)
        move    x1,x:(r7+$47)
        move    x:(r7+$59),x0
        move    x0,x:(r7+$1c)
ch_notx:
; ---- SATURATE: the character. TAPE is
; TapeHead, TUBE is DaTube, INFL is OInflator: one straight-line callee per
; mode per channel (a = the sample in, b = out; the caller's store is the
; hard clip). Skipped whole when DRV is 0 ($4d, per block). The three
; alternatives are a MODEFORK so the pricer charges the worst, not all.
        move    x:(r7+$4d),a
        tst     a
        bne     ch_nosat
; MODEFORK_BEGIN -- cycle_count.py: the dispatch, one flag test
        move    x:(r7+$29),a
        tst     a
        bne     ch_s12
; MODEFORK_MID -- alternative 1: TAPE = TapeHead
; r3 -> the channel's y1/y2 pair (the SVF state).
        move    #$15,n3
        move    r7,r3
        move    x:(r7+$35),a            ; L in (post fold/ring)
        move    (r3)+n3                 ; r3 = r7+$15: L y1, y2
        bsr     chtape
        move    b,x:(r7+$35)            ; LIMITING store: the hard clip
        move    #$17,n3
        move    r7,r3
        move    x:(r7+$36),a            ; R in
        move    (r3)+n3                 ; r3 = r7+$17: R y1, y2
        bsr     chtape
        move    b,x:(r7+$36)
        bra     ch_nosat
; MODEFORK_MID -- alternative 2: TUBE = DaTube (one compare more: 1 or 2)
ch_s12:
        move    #>$1,x0
        cmp     x0,a
        bne     ch_sinfl
; r3 -> the channel's DC-blocker pair (x1, y1).
        move    #$41,n3
        move    r7,r3
        move    x:(r7+$35),a            ; L in
        move    (r3)+n3                 ; r3 = r7+$41: L x1, y1
        bsr     chtube
        move    b,x:(r7+$35)            ; LIMITING store: the clip
        move    #$43,n3
        move    r7,r3
        move    x:(r7+$36),a            ; R in
        move    (r3)+n3                 ; r3 = r7+$43: R x1, y1
        bsr     chtube
        move    b,x:(r7+$36)
        bra     ch_nosat
; MODEFORK_MID -- alternative 3: INFL = OInflator (stateless)
ch_sinfl:
        move    x:(r7+$35),a            ; L in
        bsr     chinfl
        move    b,x:(r7+$35)            ; LIMITING store: the clip (|out| <= 1)
        move    x:(r7+$36),a            ; R in
        bsr     chinfl
        move    b,x:(r7+$36)
; MODEFORK_END
ch_nosat:
; ---- TONE: a tilt after the saturator, every mode ----------
; One-pole low-pass at 1.2 kHz per channel (k = 0.157), y = x + (t/2)(x - 2lp):
; TONE 127 = +3.5 dB above / -6 dB below, 0 the mirror, 64 bit-exact.
        move    x:(r7+$35),a            ; L
        move    x:(r7+$3f),x0           ; lp
        sub     x0,a
        move    a,x0                    ; x - lp
        move    #>$141893,y1            ; k
        mpy     x0,y1,a
        move    x:(r7+$3f),b
        add     b,a                     ; lp' = lp + k (x - lp)
        move    a,x:(r7+$3f)
        move    a,x0
        move    x:(r7+$35),a
        sub     x0,a
        sub     x0,a                    ; x - 2 lp'
        move    a,x0
        move    x:(r7+$24),y1           ; t/2
        mpy     x0,y1,a
        move    x:(r7+$35),b
        add     b,a
        move    a,x:(r7+$35)
        move    x:(r7+$36),a            ; R
        move    x:(r7+$23),x0
        sub     x0,a
        move    a,x0
        move    #>$141893,y1
        mpy     x0,y1,a
        move    x:(r7+$23),b
        add     b,a
        move    a,x:(r7+$23)
        move    a,x0
        move    x:(r7+$36),a
        sub     x0,a
        sub     x0,a
        move    a,x0
        move    x:(r7+$24),y1
        mpy     x0,y1,a
        move    x:(r7+$36),b
        add     b,a
        move    a,x:(r7+$36)
; ---- COMPRESS: COMP 0 skips the stage
; (bit-exact); else |key| smoothed by the flavour's attack / release, Lv =
; K * level_s, gr = (Lv^2/2 - 1)^2 + a*Lv, <= 1 by the limiting store --
; a dip around Lv = 1 -- then x *= gr * makeup on both channels. Lv is
; carried halved (Lv/2, so Lv up to 2 fits a word; the dip is over by 1.5).
        move    x:(r7+$26),a            ; COMP
        tst     a
        beq     ch_capd                 ; COMP 0: the stage is skipped
        move    x:(r7+$32),a            ; key
        abs     a
        move    a,x0                    ; level
        move    x:(r7+$1e),b            ; level_s
        move    x0,a
        sub     b,a                     ; d = level - level_s
        move    x:(r7+$2d),x1           ; attack
        move    x:(r7+$2e),b            ; release
        tst     a                       ; nothing between this and the Tcc
        tpl     x1,b                    ; rising: attack
        move    b,y1
        move    a,x0
        mpy     x0,y1,a                 ; k*d
        move    x:(r7+$1e),b
        add     b,a
        move    a,x:(r7+$1e)            ; level_s
        move    a,x0
        move    x:(r7+$22),y1           ; K/4
        mpy     x0,y1,a
        asl     #$1,a,a
        move    a,x0                    ; Lv/2 (the limiting store: Lv <= 2)
        move    x0,y1
        mpy     x0,y1,a                 ; (Lv/2)^2
        asl     #$1,a,a                 ; Lv^2/2
        add     #>$800000,a             ; t = Lv^2/2 - 1  (-1 .. 1)
        move    a,x1                    ; t (clean)
        move    x:(r7+$28),y1           ; a
        mpy     x0,y1,b                 ; a*Lv/2  (x0 = Lv/2 >= 0)
        asl     #$1,b,b                 ; a*Lv
        move    x1,x0                   ; t goes negative below the dip: the
        move    x1,y1                   ; square must be the audited x0,y1
        mpy     x0,y1,a                 ; t^2   (mpy x1,y1 encodes as mpysu)
        add     b,a                     ; gr = t^2 + a*Lv
        move    a,x:(r7+$1f)            ; gr (the limiting store: <= 1)
ch_capp:
        move    x:(r7+$1f),x0           ; gr
        move    x:(r7+$27),y1           ; makeup/4
        mpy     x0,y1,a
        move    a,y1                    ; gr*makeup/4
        move    x:(r7+$35),x0
        mpy     x0,y1,a
        asl     #$2,a,a
        move    a,x:(r7+$35)
        move    x:(r7+$36),x0
        mpy     x0,y1,a
        asl     #$2,a,a
        move    a,x:(r7+$36)
ch_capd:
; ---- WIDTH: mid stays, side scales ---------------------------------------
        move    x:(r7+$35),a            ; L
        move    x:(r7+$36),x0           ; R
        add     x0,a
        asr     #$1,a,a
        move    a,x1                    ; mid
        move    x:(r7+$35),a
        sub     x0,a
        asr     #$1,a,a
        move    a,x0                    ; side
        move    x:(r7+$2b),y1           ; side gain / 2
        mpy     x0,y1,a
        asl     #$1,a,a                 ; the halving undone in the guard bits
        move    a,y0                    ; scaled side
        move    x1,a
        add     y0,a                    ; mid + side
        move    a,x:(r7+$35)
        move    x1,a
        sub     y0,a                    ; mid - side
        move    a,x:(r7+$36)
; ---- MIX and write back --------------------------------------------------
        move    x:(r7+$35),a
        move    x:(r0),b
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        move    x:(r7+$20),y1           ; m
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    a,x:(r0)
        move    x:(r7+$36),a
        move    x:(r0+n0),b
        sub     b,a
        asr     #$1,a,a
        move    a,x0
        move    x:(r7+$20),y1
        mpy     x0,y1,a
        asl     #$1,a,a
        add     b,a
        move    a,x:(r0+n0)
        move    (r0)+n0                 ; the frame advance: n0 is 1 for the
        move    (r0)+n0                 ; whole loop, so two steps, no reload
ch_end:
        nop
        rts

; ===========================================================================
; BYPASS: frames untouched -- nothing to do at all (Spectrum's shape)
; ===========================================================================
ch_bypass:
        rts

; ---------------------------------------------------------------------------
; chtube -- DaTube per channel (JClones_DaTube.jsfx, MIT;).
; In: a = x, r3 -> the DC blocker's x1 (x:(r3)) and y1 (x:(r3+$1)). Out: b.
;   xin = x*(0.5 + d)                           ($4c = (0.5+d)/2, halved)
;   u   = 1 - |xin|      (may go negative: the JSFX's linear extension past
;                         +-1 is exactly the curve with u^P dropped, so the
;                         table lookup clamps u to 0 and the rest is linear)
;   T   = u - u^P, P = ln(10) + 1 = 3.3026     (TUBE_UP: 17 pairs of u^P/2)
;   y   = xin + (d/2)*T for xin > 0, xin - d*T for xin < 0   (asymmetric: the
;                         negative half is driven twice as hard -- the tube)
;   out = 2 * y * comp(d), then the DC blocker (k 1, R 0.999).
; Everything runs HALVED (xin/2 <= 0.75, u/2, T/2, y/2) and the post gain is
; comp/4 doubled back twice. STRAIGHT-LINE: no branch. Every mpy x0,y1 (the
; audited-signed order; the one Tcc reads the tst right before it). Clobbers
; x0, x1, y0, y1, a, b, n1, n2; $49 parks u/2.
chtube:
        move    a,x0                    ; x
        move    x:(r7+$4c),y1           ; (0.5 + d)/2
        mpy     x0,y1,a
        move    a,x1                    ; xin/2  (|.| <= 0.75)
        abs     a
        neg     a
        add     #>$400000,a             ; u/2 = 0.5 - |xin/2|, in [-0.25, 0.5]
        move    a,x:(r7+$49)            ; park u/2
        move    #$0,x0                  ; (a move does not disturb the flags)
        tst     a
        tmi     x0,a                    ; the lookup's argument: max(u, 0)/2
        move    a,b
        asr     #$11,b,b                ; u/2 >> 17 = 2*idx + bit 17 ...
        and     #>$fffffe,b             ; ... masked to 2*idx (17 pairs, 1/32 steps)
        move    b1,n1
        move    b1,n2
        move    a,b
        and     #>$3ffff,b              ; the 18 bits under the step (b2 = 0)
        asl     #$5,b,b                 ; frac, Q23
        move    b,x0                    ; AGU settle: n1 written 4 back
        move    p:(r1+n1),y0            ; P2[idx] = u^P / 2
        move    p:(r2+n2),y1            ; P2[idx+1] - P2[idx]  (>= 0)
        mpy     x0,y1,a                 ; frac * slope
        add     y0,a                    ; u^P / 2
        move    x:(r7+$49),b            ; u/2
        sub     a,b                     ; T/2 = (u - u^P)/2
        move    b,x0                    ; T/2
        move    x:(r7+$38),y1           ; d
        mpy     x0,y1,a                 ; d * T/2
        neg     a
        move    a,y0                    ; the negative half's term, parked
        move    x:(r7+$37),y1           ; d/2
        mpy     x0,y1,a                 ; the positive half's term
        move    x1,b                    ; xin/2
        tst     b                       ; its sign -- nothing between this
        tmi     y0,a                    ; and the Tcc (the flag trap)
        add     x1,a                    ; y/2 = xin/2 + term
        move    a,x0
        move    x:(r7+$39),y1           ; comp/2
        mpy     x0,y1,a                 ; (y/2)(comp/2) = y*comp/4
        asl     #$2,a,a                 ; *4 -> y*comp: the JSFX's -6 dB default
        move    a,x0                    ; x, the DC blocker's input (LIMITING)
        move    x:(r3),x1               ; x1
        move    x0,x:(r3)               ; x1 <- x
        move    #>$7fffff,y1            ; k = 1.0 (an immediate: chtube is TUBE's)
        mpy     x1,y1,b                 ; k*x1 (mpysu: y1 is positive)
        move    x0,a
        sub     b,a                     ; x - x1
        move    x:(r3+$1),x0            ; y1
        move    #>$7fdf3b,y1            ; R = 0.999
        mac     x0,y1,a                 ; + R*y1
        move    a,x:(r3+$1)             ; y1 <- y
        move    a,b
        rts

; ---------------------------------------------------------------------------
; chinfl -- OInflator per channel (JClones_OInflator.jsfx, MIT;),
; single band, Curve at the JSFX default 0 (c = 0.25), Clip on (the +-0.5
; threshold on the halved signal IS the input's full scale). In: a = x. Out: b.
;   x2 = x/2                      (the JSFX's 0.5 input headroom)
;   g  = 0.75 + 0.5*|x2|          (2c|x2| + (1 - c), in [0.75, 1])
;   gx = g*x2                     (|gx| <= 0.5)
;   y  = 2e*gx*(1 - |gx|) + (1 - e)*x2
;   out = 2*y                     (the JSFX's x2 output gain; |out| <= 1)
; e = DRV/128 ($3a = e/2, $3b = 1 - e). g and t = 1 - |gx| live halved.
; STRAIGHT-LINE, stateless; every mpy/mac x0,y1. Clobbers x0, x1, y1, a, b.
chinfl:
        asr     #$1,a,a                 ; x2
        move    a,x1
        abs     a
        move    a,x0                    ; |x2|
        move    #$20,y1                 ; 0.25
        mpy     x0,y1,a
        add     #>$300000,a             ; g/2 = 0.375 + 0.25*|x2|
        move    a,y1
        move    x1,x0                   ; x2
        mpy     x0,y1,a
        asl     #$1,a,a                 ; gx = g*x2
        move    a,x0                    ; gx
        abs     a
        asr     #$1,a,a
        neg     a
        add     #>$400000,a             ; t/2 = 0.5 - |gx|/2, in [0.25, 0.5]
        move    a,y1
        mpy     x0,y1,a                 ; gx * t/2
        move    a,x0
        move    x:(r7+$3a),y1           ; e/2
        mpy     x0,y1,a                 ; gx * t/2 * e/2
        asl     #$3,a,a                 ; 2e * gx * t
        move    x1,x0                   ; x2
        move    x:(r7+$3b),y1           ; 1 - e
        mac     x0,y1,a                 ; + (1 - e)*x2 = y
        asl     #$1,a,a                 ; out = 2y
        move    a,b
        rts

; ---------------------------------------------------------------------------
; chtxc -- Pockey's codec on a MAGNITUDE: a = |x| in, a = out.
; mu-law encode by the 257-point ENC table (r3 = t, idx = the top 8 bits,
; frac = the 15 under them, the second point through (r3)+ and back),
; quantise to rez in that domain -- the reference rounds UP: ceil(y/rez) rez
; = floor(y q4096 + 2^-12 - lsb) on the 2^-12 grid, back by 4 rez x 1024,
; exact multiples and zero unchanged -- scale by 1 - rez, decode by the DEC
; table (r5). STRAIGHT-LINE. Clobbers x0, x1, y0, y1, b, n3, n5.
chtxc:
        move    a,x1                    ; u
        asr     #$f,a,a                 ; idx = u >> 15  (0..255)
        move    a1,n3
        move    x1,a
        and     #>$7fff,a               ; (a2 = 0: u >= 0)
        asl     #$8,a,a                 ; frac
        move    a,x0
        move    p:(r3+n3),y0            ; t[i]
        move    (r3)+
        move    p:(r3+n3),b             ; t[i+1]
        move    (r3)-
        move    y0,a
        sub     a,b
        move    b,y1
        mpy     x0,y1,a
        add     y0,a                    ; y = enc(u)
        move    a,x0
        move    x:(r7+$54),y1           ; q4096
        mpy     x0,y1,a
        add     #>$0007ff,a             ; ceil on the grid (a multiple stays)
        and     #>$fff800,a
        move    a,x0
        move    x:(r7+$52),y1           ; 4 rez
        mpy     x0,y1,a
        asl     #$a,a,a                 ; n rez
        move    a,x0
        move    x:(r7+$53),y1           ; 1 - rez
        mpy     x0,y1,a
        move    a,x1
        asr     #$f,a,a
        move    a1,n5
        move    x1,a
        and     #>$7fff,a
        asl     #$8,a,a
        move    a,x0
        move    p:(r5+n5),y0
        move    (r5)+
        move    p:(r5+n5),b
        move    (r5)-
        move    y0,a
        sub     a,b
        move    b,y1
        mpy     x0,y1,a
        add     y0,a                    ; dec(...)
        rts

; chtape -- TapeHead per channel (JClones_TapeHead.jsfx, MIT;).
; In: a = x, r3 -> y1 (x:(r3)) and y2 (x:(r3+$1)), both kept at /4 (the
; port's headroom: |y1| <= 1.46, |y2| <= 1.95 true). Out: b = (g3*clip(y3)
; + ss(d*y1) + ss(d*y2)) * trim, up to 2.2, CLIPPED (the JSFX's own output
; clip) and then scaled by the block's unity trim x:(r7+$22) = (1/11)/d8. STRAIGHT-LINE: no branch of any kind
; (cycle_count.py charges the span at each call). Every mpy is x0,y1 (the
; audited-signed order); every clip is a LIMITING move into x0. Clobbers
; x0, x1, y1, a, b.
;   y1 += k2*y2 ; y3 = k1*y1 + y2 - x ; y2 -= k3mag*y3      (k3 = -1.4 k2)
;   ss(v) = 1.5v - 0.5v^3 on v = clip(d*y1), clip(d*y2)      (v = 32*(y1/4*d/8))
chtape:
        asr     #$2,a,a                 ; Xs = x/4
        move    a,x1
        move    x:(r3+$1),x0            ; y2
        move    x:(r7+$30),y1           ; k2
        mpy     x0,y1,a
        move    x:(r3),b
        add     b,a                     ; y1n = y1 + k2*y2
        move    a,x0
        move    x0,x:(r3)
        move    #>$5b6db7,y1            ; k1 = 5/7
        mpy     x0,y1,a
        move    x:(r3+$1),b
        add     b,a
        sub     x1,a                    ; y3 = k1*y1n + y2 - Xs
        move    a,x0
        move    x:(r7+$31),y1           ; k3mag
        mpy     x0,y1,a
        move    x:(r3+$1),b
        sub     a,b                     ; y2n = y2 - k3mag*y3
        move    b,x:(r3+$1)
        move    x0,a
        asl     #$2,a,a                 ; 4*y3
        move    a,x0                    ; LIMITING move: clip(y3)
        move    #>$33e5de,y1            ; |g3|*trim/2
        mpy     x0,y1,b
        asl     #$1,b,b
        neg     b                       ; b = g3*trim*clip(y3)   (g3 < 0)
        move    x:(r3),x0               ; y1n/4
        move    x:(r7+$48),y1           ; d/8
        mpy     x0,y1,a
        asl     #$5,a,a                 ; v = d*y1n
        move    a,x0                    ; LIMITING move: clip(v)
        move    x0,y1
        mpy     x0,y1,a                 ; v^2
        move    a,y1
        mpy     x0,y1,a                 ; v^3
        neg     a
        add     x0,a                    ; v - v^3
        asr     #$1,a,a
        add     x0,a                    ; ss(v) = 1.5v - 0.5v^3
        move    a,x0
        move    #>$59999a,y1            ; trim 0.7
        mpy     x0,y1,a
        add     a,b
        move    x:(r3+$1),x0            ; y2n/4
        move    x:(r7+$48),y1
        mpy     x0,y1,a
        asl     #$5,a,a
        move    a,x0
        move    x0,y1
        mpy     x0,y1,a
        move    a,y1
        mpy     x0,y1,a
        neg     a
        add     x0,a
        asr     #$1,a,a
        add     x0,a
        move    a,x0
        move    #>$59999a,y1
        mpy     x0,y1,a
        add     a,b
        move    b,x0                    ; LIMITING move: the JSFX's output clip
        move    x:(r7+$2a),y1           ; then the trim (1/11)/d8 + 0.023
        mpy     x0,y1,b
        rts
