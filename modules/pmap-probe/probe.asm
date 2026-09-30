; ---------------------------------------------------------------------------
; PMAP PROBE -- one source for both payloads (modules/pmap-probe/manifest.py):
; payload A hooks `boot` (P:0x40) and `tone` (P:0x2d5), payload B `boot` and
; `report` (P:0x333); the entry a payload does not hook is placed and unused.
; Instruction forms: every one has a site in a stock payload or in a module
; that runs on units (P reads as BusVerb's and Spectrum's), except the three
; OMR moves, which are the question.
; ---------------------------------------------------------------------------
; ---------------------------------------------------------------------------
; PMAP PROBE -- boot: switch this core to the 16K program map, then test it.
;
; Reached by `jsr` (schema.DspHook) over P:0x40's `move #>$8000,b`, the first instruction of
; each payload after the upload, before anything has touched Y (the loop that
; follows zeroes Y:0x4000.. and this core's half of the shared window). The
; DSP56720's memory switch (RM ch. 3, CHIP.md section 3): OMR MS (bit 7) with
; MSW1:MSW0 (bits 22:21) = 11 gives 16K P, 36K X, 40K Y -- P gains
; 0x2000..0x3FFF, Y loses 0xA000..0xBFFF. Stock never writes OMR. MSW is set
; first with MS still 0, then MS; then a pipeline's worth of nops.
;
; The test, all of it before the first frame:
;   1. P:0x2000..0x3FFF written with (a xor 0x5A5A5A) and read back, then
;      with its complement and read back: X:0x7f01 counts the words that
;      did not hold (0 = the 8K is there and holds both patterns)
;   2. the five words at `exec` copied to P:0x3F00 and called there: they
;      write 0xC0DE to X:0x7f02 (0xC0DE = code runs from the new P)
;   3. X:0x7f00 = 0x50A55 when both held, else 0xFA1100 + min(errors, 255)
; The result is heard: tone.asm (core 0, MAIN L = this core) and report.asm
; (core 1, forwarded to core 0 for MAIN R).
;
; The displaced instruction is replayed as `move #>$6000,b`, not $8000: the
; loop after it zeroes b words from Y:0x4000, which under the new map would run
; into the Y that is gone. It now stops at 0x9FFF (and, in the same loop, 24K of
; this core's shared half instead of 32K).
;
; X:0x7f00..0x7f0f is the probe's: above every X module of both payloads (the
; curve bank ends at 0x7a91, the next X module starts at 0x8040 / 0x8580).
; ---------------------------------------------------------------------------
boot:
        move    #>$7f00,r0              ; the probe's words, from nothing: the unit
        clr     a                       ; does not zero X (tone.asm's phases)
        do      #$10,pzero
        move    a,x:(r0)+
pzero:
        move    omr,x0                  ; MSW1:MSW0 = 11 with MS still 0
        move    x0,a
        or      #>$600000,a
        move    a1,x0
        move    x0,omr
        nop
        nop
        ori     #$80,omr                ; MS: the 16K map
        nop
        nop
        nop
        nop
; ---- 1. the new P, two patterns ------------------------------------------
        clr     a
        clr     b                       ; b: errors, over both passes
        move    a,x:>$7f02              ; the exec flag
        move    #>$1,y1
        move    #>$2000,n1              ; 8K words: past a do immediate's 12 bits
        move    #>$2000,r0
        move    #>$5a5a5a,x1
        do      n1,pw1
        move    r0,a
        eor     x1,a
        move    a1,x0
        move    x0,p:(r0)+
pw1:
        move    #>$2000,r0
        do      n1,pr1
        move    r0,a
        eor     x1,a
        move    a1,x0
        move    p:(r0)+,a
        and     #>$ffffff,a
        eor     x0,a                    ; Z: the word held
        add     y1,b    ifne            ; else one more error (b), branch-free
pr1:
        move    #>$2000,r0
        move    #>$a5a5a5,x1
        do      n1,pw2
        move    r0,a
        eor     x1,a
        move    a1,x0
        move    x0,p:(r0)+
pw2:
        move    #>$2000,r0
        do      n1,pr2
        move    r0,a
        eor     x1,a
        move    a1,x0
        move    p:(r0)+,a
        and     #>$ffffff,a
        eor     x0,a                    ; Z: the word held
        add     y1,b    ifne            ; else one more error (b), branch-free
pr2:
        move    b1,x:>$7f01
; ---- 2. code runs from the new P ---------------------------------------------
        move    #>exec,r0
        move    #>$3f00,r1
        do      #$5,pcopy
        move    p:(r0)+,x0
        move    x0,p:(r1)+
pcopy:
        nop
        move    #>$3f00,r2
        jsr     (r2)
; ---- 3. the verdict ----------------------------------------------------------
        move    x:>$7f01,a
        tst     a
        bne     pfail
        move    x:>$7f02,a
        move    #>$c0de,x0
        sub     x0,a                    ; sub, not cmp (the cmp-as-max family)
        bne     pfail
        move    #>$50a55,x0
        move    x0,x:>$7f00
        bra     pdone
pfail:
        move    x:>$7f01,a
        move    #>$ff,x0
        sub     x0,a
        move    x:>$7f01,a
        blt     pclamp                  ; errors < 255: as counted
        move    x0,a
pclamp:
        add     #>$fa1100,a
        move    a1,x:>$7f00
pdone:
        move    #>$6000,b               ; the displaced move #>$8000,b, shortened
        rts

; copied to P:0x3F00 and called there: two-word absolute forms only (they must
; not depend on where they run)
exec:
        move    #>$c0de,x0
        move    x0,x:>$7f02
        rts

; ---------------------------------------------------------------------------
; PMAP PROBE -- the verdicts, heard: a square wave on MAIN per core.
;
; Reached by `jsr` over payload A's P:0x2d5 `move x:>$206,r0`, where both
; mixdown paths have written this frame's 16 samples into the TX ring (x:$203,
; eight words a sample, MAIN L/R at +2/+3) and nothing has read them yet.
;   MAIN L: core 0's verdict (X:0x7f00), MAIN R: core 1's (X:0x3fff0)
;   pass (0x50A55): 882 Hz (a 50-sample period)
;   fail (0xFA11xx): 110 Hz (400)
;   anything else (no report): no tone on that side
; at +/- 0x080000 (-24 dBFS) added to MAIN. Phases at X:0x7f08 (L), 0x7f09 (R).
; Every register it writes that stock reads after the return is saved.
; ---------------------------------------------------------------------------
tone:
        move    r1,x:>$7f0a
        move    r2,x:>$7f0b
        move    n1,x0
        move    x0,x:>$7f0c
        move    x:>$203,r1
        lua     (r1+$2),r1              ; sample 0's MAIN L
        move    #>$7f08,r2              ; its phase
        move    x:>$7f00,a
        bsr     side
        move    x:>$203,r1
        lua     (r1+$3),r1              ; MAIN R
        move    #>$7f09,r2
        move    x:>$3fff0,a
        bsr     side
        move    x:>$7f0c,n1
        move    x:>$7f0b,r2
        move    x:>$7f0a,r1
        move    x:>$206,r0              ; the displaced instruction, as stock has it
        rts

; a = the verdict, r1 = the channel's word of sample 0, r2 = its phase word.
; Branch-free per sample: the phase wraps with tlt, and one compare (phase -
; half the period) drives both conditional adds, with only moves between them
; (IFcc does not touch the condition codes).
side:
        move    #>$32,x1                ; the period: 50 on pass
        move    #>$50a55,x0
        sub     x0,a
        beq     sgo
        add     x0,a                    ; the verdict back
        and     #>$ffff00,a
        move    #>$fa1100,x0
        eor     x0,a
        bne     snone                   ; neither: silent
        move    #>$190,x1               ; 400 on fail
sgo:
        move    x1,b
        asr     b
        move    b1,x:>$7f0d             ; half the period
        move    #>$080000,y0            ; the amplitude, -24 dBFS
        move    #>$1,y1
        move    #>$8,n1                 ; eight words a sample
        do      #$10,sloop
        move    x:(r2),a                ; phase
        add     y1,a                    ; + 1
        move    a1,x0
        sub     x1,a                    ; past the period: wrap to 0
        tlt     x0,a                    ; else phase + 1
        move    a1,x:(r2)
        move    x:>$7f0d,x0
        sub     x0,a                    ; N: the first half of the period
        move    x:(r1),b                ; MAIN
        add     y0,b    iflt            ; the forms stock has (P:0x24b's iflt,
        sub     y0,b    ifge            ; its ifge subs)
        move    b,x:(r1)+n1             ; stored limited
sloop:
snone:
        rts

; ---------------------------------------------------------------------------
; PMAP PROBE -- core 1's verdict, forwarded to core 0 every frame.
;
; Reached by `jsr` over payload B's P:0x333 `move x:>$415,a` (the frame's end,
; after the last track's effects; the same site MASTER STRIP's RET A uses, and
; the ledger keeps the two apart). Copies core 1's X:0x7f00 (boot.asm's
; verdict) to X:0x3fff0, the top of this core's half of the shared window:
; above every stock effect's reach in a slot based at 0x3c000 (the reverbs
; are harvested in this probe's remix; the others reach 0x3cc00 at most) and
; written every frame, so the boot's zeroing of the shared half cannot lose it.
; ---------------------------------------------------------------------------
report:
        move    x:>$7f00,x0
        move    x0,x:>$3fff0
        move    x:>$415,a               ; the displaced instruction, as stock has it
        rts
