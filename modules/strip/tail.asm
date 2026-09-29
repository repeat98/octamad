; ---------------------------------------------------------------------------
; MASTER STRIP -- tail: MAIN's samples 1..15, after stock's tail.
;
; Reached by `jsr` over P:0x35d's two-word `move x:>$207,r0`, after the cue
; mix: stock has packed MAIN for the recorder and USB audio (P:0x2df), added
; the metronome click into CUE and MAIN (P:0x2ec..) and mixed the phones
; (P:0x33f..), all from a MAIN whose sample 0 the head (head.asm) already
; ran through the insert and whose samples 1..15 are dry. The output DMA
; reads sample j about 2,000 + 4,160 j cycles after the mixdown (MIXER.md
; section 3), so samples 1..15 still have thousands of cycles to spare; each
; is finished here, in order, before the next is started.
;
; For each sample j = 1..15:
;   click   C_j = ring MAIN_j - D_j: what the click added (D holds the dry
;           pair the head gathered; the click is a plain add, so this is it
;           exactly unless MAIN + click clipped, where stock clips too)
;   insert  the insert on D_j, in place: P_j
;   MAIN    ring MAIN_j = P_j + C_j, stored limited, as the click's store is
;   phones  ring phones_j = g_cue CUE_j + g_main MAIN_j, the cue mix's own
;           arithmetic on its own gains (Y:0x40 + 2j, which the ramp at
;           P:0x30a wrote this frame), stored limited, L/R crossed when bit 0
;           of the record word the cue mix tests (x:$205 + $2b) is set
; then the MAIN pack again, from D (P_0..P_15, before the click, as stock
; packs it), through the stock routine at its stock destination.
;
; Register discipline is the head's: everything stock might read after the
; return is saved and put back, and nothing is kept in a register across the
; insert (the loop's pointers live at $3b..$3d of the strip's block).
; ---------------------------------------------------------------------------
entry:
        move    r7,x:>$7c3f             ; the caller's r7
        move    #>$7c00,r7              ; -> the strip's block (boot.asm's map)
        move    r1,x:(r7+$30)
        move    r2,x:(r7+$31)
        move    r3,x:(r7+$32)
        move    r4,x:(r7+$33)
        move    r5,x:(r7+$34)
        move    r6,x:(r7+$35)
        move    n0,x0
        move    x0,x:(r7+$36)
        move    n1,x0
        move    x0,x:(r7+$37)
        move    n2,x0
        move    x0,x:(r7+$38)
        move    n3,x0
        move    x0,x:(r7+$39)
        move    n7,x0
        move    x0,x:(r7+$3a)
; ---- the click, 1..15: C = ring MAIN - D ------------------------------------
        move    x:>$203,r1
        lua     (r1+$a),r1              ; sample 1's MAIN L
        move    #$7,n1
        move    #>$7c42,r0              ; D's sample 1
        move    #>$7c62,r2              ; C's sample 1
        do      #$f,tclick
        move    x:(r1)+,a
        move    x:(r0)+,x0
        sub     x0,a            x:(r1)+n1,b
        move    x:(r0)+,x0
        sub     x0,b            a,x:(r2)+
        move    b,x:(r2)+
tclick:
; ---- the cue mix's L/R order, and the loop's pointers ------------------------
        move    x:>$205,r0
        move    x:>$203,r1
        move    x:(r0+$2b),a            ; the word the cue mix tests (bit 0)
        and     #>$1,a
        move    a1,x:(r7+$3e)           ; a1, not a: the and left a2 as it was
        lua     (r1+$8),r1
        move    r1,x:(r7+$3b)           ; ring, sample 1
        move    #>$7c42,r1
        move    r1,x:(r7+$3c)           ; D, sample 1
        move    #$42,r1
        move    r1,x:(r7+$3d)           ; the cue mix's gains, sample 1
        do      #$f,tloop
; ---- the insert on D_j -------------------------------------------------------
        move    x:(r7+$3c),r0
        move    #>$7c80,r6              ; the strip's parameter record
        move    #$1,n7                  ; one frame
        move    x:>$254,r2              ; PROC_TABLE[0x1f]: OXIDE's proc
        jsr     (r2)
; ---- MAIN_j = P_j + C_j --------------------------------------------------------
        move    x:(r7+$3c),r0           ; P_j
        move    x:(r7+$3b),r3           ; the ring's sample j
        lua     (r0+$20),r1             ; C_j
        lua     (r3+$2),r2              ; its MAIN L
        move    x:(r0)+,a
        move    x:(r1)+,x0
        add     x0,a            x:(r0)+,b
        move    x:(r1)+,x0
        add     x0,b            a,x:(r2)+
        move    b,x:(r2)+
        move    r0,x:(r7+$3c)           ; D, the next sample
; ---- the phones: the cue mix on the new MAIN ----------------------------------
        move    x:(r7+$3d),r4
        move    x:(r3)+,x0      y:(r4)+,y0      ; CUE L, g_cue
        mpy     y0,x0,a         x:(r3)+,x0              ; CUE R
        mpy     y0,x0,b         x:(r3)+,x0              ; MAIN L
        move    y:(r4)+,y0              ; g_main (dsp_asm encodes this XY move with an
                                        ; mpy as a bare mpysu, so it stands alone)
        mac     y0,x0,a         x:(r3)+,x0              ; MAIN R
        mac     y0,x0,b
        move    r4,x:(r7+$3d)           ; the gains, the next sample
        move    x:(r7+$3e),n3           ; 0, or 1 when crossed
        move    x:(r7+$3e),n1
        lua     (r3+$1),r1              ; r3 is at the phones L word; r1 at R
        lua     (r3)+n3,r2              ; the L mix's word: L, or R when crossed
        move    (r1)-n1                 ; the R mix's word: R, or L when crossed
        move    a,x:(r2)
        move    b,x:(r1)
        lua     (r3+$4),r3              ; past the unused pair: the next sample
        move    r3,x:(r7+$3b)
tloop:
; ---- the MAIN pack again, from D ---------------------------------------------
        move    x:>$206,r0              ; stock's destination: x:$206 + $100
        move    #>$100,n0
        move    #>$7c40,r1              ; P_0..P_15, L/R adjacent
        move    #$1,n1
        move    (r0)+n0
        jsr     $55a                    ; stock's pack (func_00055a), stock's own short form
; ---- back as stock left them -------------------------------------------------
        move    x:(r7+$3a),n7
        move    x:(r7+$39),n3
        move    x:(r7+$38),n2
        move    x:(r7+$37),n1
        move    x:(r7+$36),n0
        move    x:(r7+$35),r6
        move    x:(r7+$34),r5
        move    x:(r7+$33),r4
        move    x:(r7+$32),r3
        move    x:(r7+$31),r2
        move    x:(r7+$30),r1
        move    x:>$7c3f,r7
        move    x:>$207,r0              ; the displaced instruction, as stock has it
        rts
