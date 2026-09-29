; ---------------------------------------------------------------------------
; MASTER STRIP -- tail: MAIN's samples 1..15 after stock's tail, then the
; next frame's slots from the ColdFire's record.
;
; Reached by `jsr` over P:0x35d's two-word `move x:>$207,r0`, after the cue
; mix: stock has packed MAIN for the recorder and USB audio (P:0x2df), added
; the metronome click into CUE and MAIN (P:0x2ec..) and mixed the phones
; (P:0x33f..), all from a MAIN whose sample 0 the head (head.asm) already
; ran through the slots and whose samples 1..15 are dry. The output DMA
; reads sample j about 2,000 + 4,160 j cycles after the mixdown (MIXER.md
; section 3), so samples 1..15 still have thousands of cycles to spare; each
; is finished here, in order, before the next is started.
;
; For each sample j = 1..15:
;   click   C_j = ring MAIN_j - D_j: what the click added (D holds the dry
;           pair the head gathered; the click is a plain add, so this is it
;           exactly unless MAIN + click clipped, where stock clips too)
;   slots   slot 1 then slot 2 on D_j, in place: P_j
;   MAIN    ring MAIN_j = P_j + C_j, stored limited, as the click's store is
;   phones  ring phones_j = g_cue CUE_j + g_main MAIN_j, the cue mix's own
;           arithmetic on its own gains (Y:0x40 + 2j, which the ramp at
;           P:0x30a wrote this frame), stored limited, L/R crossed when bit 0
;           of the record word the cue mix tests (x:$205 + $2b) is set
; then the MAIN pack again, from D (P_0..P_15, before the click, as stock
; packs it), through the stock routine at its stock destination.
;
; THE RECORD. Last, the slots the next frame runs: strip_xport.s sends the
; MIXER's model (strip_model) to core 0 every frame, and it lands in this
; frame's bank at x:$205 + $1480 (the host handler's mask folds its X:0x7c80
; there). Thirty-two words, the halfword in bits 15..0 of each (the top byte
; is not zero): the magic 0x5354, then per slot its id, six page-1 words
; (v << 8) and three page-2 words ((v << 8) | w), then zeros and a checksum
; that makes the 32 halfwords sum to 0 mod 2^16. A record whose magic or sum
; fails is not used (the bank holds what the RAM held until the ColdFire's
; first burst, and the unit's RAM is not zeroed); the slots run on as they
; were. Otherwise, per slot:
;   knobs   the page-1 words to r6 + 0..5 as v << 16 and the page-2 words to
;           r6 + $c..$e, each value masked to 0..127, every frame
;   id      when it differs from the id the slot runs: an id on the strip's
;           list gets its init (r1 the id, r6 the record, r7 the slot's
;           block, as the dispatcher calls it) and its proc; 0 and any id
;           off the list leave the slot dry. The list is OXIDE (0x1f): an
;           insert joins it once it is shown to run one frame at a time with
;           no dispatcher state (MIXER.md)
; The knobs reach the samples of the next frame: the record is a frame old
; when it lands and a frame older when it is heard.
;
; Register discipline is the head's: everything stock might read after the
; return is saved and put back, and nothing is kept in a register across a
; slot's call (the loop's pointers live at $0b..$0d of the strip's block).
; ---------------------------------------------------------------------------
entry:
        move    r7,x:>$7c0f             ; the caller's r7
        move    #>$7c00,r7              ; -> the strip's block (boot.asm's map)
        move    r1,x:(r7+$0)
        move    r2,x:(r7+$1)
        move    r3,x:(r7+$2)
        move    r4,x:(r7+$3)
        move    r5,x:(r7+$4)
        move    r6,x:(r7+$5)
        move    n0,x0
        move    x0,x:(r7+$6)
        move    n1,x0
        move    x0,x:(r7+$7)
        move    n2,x0
        move    x0,x:(r7+$8)
        move    n3,x0
        move    x0,x:(r7+$9)
        move    n7,x0
        move    x0,x:(r7+$a)
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
        move    a1,x:(r7+$e)            ; a1, not a: the and left a2 as it was
        lua     (r1+$8),r1
        move    r1,x:(r7+$b)            ; ring, sample 1
        move    #>$7c42,r1
        move    r1,x:(r7+$c)            ; D, sample 1
        move    #$42,r1
        move    r1,x:(r7+$d)            ; the cue mix's gains, sample 1
        do      #$f,tloop
; ---- the slots on D_j ----------------------------------------------------------
        move    x:(r7+$c),r0
        bsr     trun
; ---- MAIN_j = P_j + C_j --------------------------------------------------------
        move    x:(r7+$c),r0            ; P_j
        move    x:(r7+$b),r3            ; the ring's sample j
        lua     (r0+$20),r1             ; C_j
        lua     (r3+$2),r2              ; its MAIN L
        move    x:(r0)+,a
        move    x:(r1)+,x0
        add     x0,a            x:(r0)+,b
        move    x:(r1)+,x0
        add     x0,b            a,x:(r2)+
        move    b,x:(r2)+
        move    r0,x:(r7+$c)            ; D, the next sample
; ---- the phones: the cue mix on the new MAIN ----------------------------------
        move    x:(r7+$d),r4
        move    x:(r3)+,x0      y:(r4)+,y0      ; CUE L, g_cue
        mpy     y0,x0,a         x:(r3)+,x0              ; CUE R
        mpy     y0,x0,b         x:(r3)+,x0              ; MAIN L
        move    y:(r4)+,y0              ; g_main (dsp_asm encodes this XY move with an
                                        ; mpy as a bare mpysu, so it stands alone)
        mac     y0,x0,a         x:(r3)+,x0              ; MAIN R
        mac     y0,x0,b
        move    r4,x:(r7+$d)            ; the gains, the next sample
        move    x:(r7+$e),n3            ; 0, or 1 when crossed
        move    x:(r7+$e),n1
        lua     (r3+$1),r1              ; r3 is at the phones L word; r1 at R
        lua     (r3)+n3,r2              ; the L mix's word: L, or R when crossed
        move    (r1)-n1                 ; the R mix's word: R, or L when crossed
        move    a,x:(r2)
        move    b,x:(r1)
        lua     (r3+$4),r3              ; past the unused pair: the next sample
        move    r3,x:(r7+$b)
tloop:
; ---- the MAIN pack again, from D ---------------------------------------------
        move    x:>$206,r0              ; stock's destination: x:$206 + $100
        move    #>$100,n0
        move    #>$7c40,r1              ; P_0..P_15, L/R adjacent
        move    #$1,n1
        move    (r0)+n0
        jsr     $55a                    ; stock's pack (func_00055a), stock's own short form
; ---- the record: the next frame's slots -----------------------------------------
        move    x:>$205,r0
        move    #>$1480,n0
        move    (r0)+n0                 ; the record, in this frame's bank
        move    r0,x:(r7+$16)
        clr     b
        do      #$40,tsum
        move    x:(r0)+,a
        and     #>$ffff,a               ; the halfword (a1: the and leaves a2)
        move    a1,x0
        add     x0,b
tsum:
        and     #>$ffff,b               ; b is clean and positive: 0 when it sums
        bne     tdone
        move    x:(r7+$16),r0
        move    x:(r0)+,a
        and     #>$ffff,a
        move    a1,x0
        move    #>$5354,a               ; the magic
        sub     x0,a
        bne     tdone
        move    #>$7c10,r4              ; slot 1: its id and proc,
        move    #>$7c20,r6              ; its record,
        move    #>$7d00,r5              ; its instance block
        move    #>$fff,r3               ; the strip's list is OXIDE alone
        bsr     tslot
        move    #>$7c12,r4              ; slot 2
        move    #>$7c30,r6
        move    #>$7e00,r5
        move    #>$fff,r3
        bsr     tslot
        move    #>$7c80,r1              ; the AUX sends: 12 halfwords, 24 gains
        move    #$c,n0
        bsr     tgain
        move    #>$7ce0,r4              ; RET B's slot: id/proc at X:0x7ce0/1,
        move    #>$7cf0,r6              ; its record,
        move    #>$7f00,r5              ; its instance block (0x100 wide)
        move    #>$7,r3                 ; the return's list: OXIDE and the reverb server
        bsr     tslot
        lua     (r0+$a),r0              ; RET A's slot (stage 3): not taken
        move    #>$7c98,r1              ; the returns' levels: two halfwords
        move    #$2,n0
        bsr     tgain
        move    #>$4e2000,x0            ; the sends of a return's wet are capped at
        move    #>$7c8a,r0              ; send 100 = 0.61: RET A, RET B into AUX A,
        bsr     tcap                    ; then into AUX B
        move    #>$7c8b,r0
        bsr     tcap
        move    #>$7c96,r0
        bsr     tcap
        move    #>$7c97,r0
        bsr     tcap
tdone:
; ---- the AUX passes: this frame's sources, the record's sends ---------------
        bsr     auxrun
        bsr     retrun
; ---- back as stock left them -------------------------------------------------
        move    x:(r7+$a),n7
        move    x:(r7+$9),n3
        move    x:(r7+$8),n2
        move    x:(r7+$7),n1
        move    x:(r7+$6),n0
        move    x:(r7+$5),r6
        move    x:(r7+$4),r5
        move    x:(r7+$3),r4
        move    x:(r7+$2),r3
        move    x:(r7+$1),r2
        move    x:(r7+$0),r1
        move    x:>$7c0f,r7
        move    x:>$207,r0              ; the displaced instruction, as stock has it
        rts

; ---- the two slots on one pair at r0, in place; r7 the strip's block, and
; again on return. A slot whose proc word is 0 is dry.
trun:
        move    r0,x:(r7+$14)
        move    x:(r7+$11),a            ; slot 1's proc
        tst     a
        beq     tskp1
        move    x:(r7+$11),r2
        move    #>$7c20,r6              ; its record
        move    #>$7d00,r7              ; its instance block
        move    #$1,n7                  ; one frame
        move    #$1,n0                  ; R next to L (the contract's x:(r0+n0))
        jsr     (r2)
        move    #>$7c00,r7
        move    x:(r7+$14),r0
tskp1:
        move    x:(r7+$13),a            ; slot 2's proc
        tst     a
        beq     tskp2
        move    x:(r7+$13),r2
        move    #>$7c30,r6
        move    #>$7e00,r7
        move    #$1,n7
        move    #$1,n0
        jsr     (r2)
        move    #>$7c00,r7
tskp2:
        rts

; ---- one slot of the record: r0 at its id word, r4 its id/proc pair, r6 its
; record, r5 its instance block, r7 the strip's block. Returns r0 past the
; slot's ten words and r7 the strip's block; r1..r6 are the tail's to spend.
tslot:
        move    r3,x:(r7+$19)           ; the second id the list allows ($fff: none)
        move    x:(r0)+,a
        and     #>$ffff,a
        move    a1,x:(r7+$15)           ; the id the record asks for
        move    r6,r1
        do      #$6,tpgone
        move    x:(r0)+,a
        and     #>$7f00,a               ; v << 8, v 0..127
        asl     #$8,a,a                 ; v << 16 in a1 (a0 was 0; a2 is not read)
        move    a1,x:(r1)+
tpgone:
        lua     (r6+$c),r1
        do      #$3,tpgtwo
        move    x:(r0)+,a
        and     #>$7f7f,a               ; (v << 8) | w, both 0..127
        asl     #$8,a,a
        move    a1,x:(r1)+
tpgtwo:
        move    x:(r7+$15),a
        move    x:(r4),x0               ; the id the slot runs
        sub     x0,a
        beq     tsame
        move    x:(r7+$15),x0
        move    x0,x:(r4)               ; the slot runs what was asked, from here
        clr     a
        move    a,x:(r4+$1)             ; dry, unless the id is on the list
        move    x:(r7+$15),a
        move    #>$1f,x0                ; OXIDE
        sub     x0,a
        beq     tlist
        move    x:(r7+$15),a
        move    x:(r7+$19),x0           ; or the return's second id
        sub     x0,a
        bne     tsame
tlist:
        move    r0,x:(r7+$16)           ; park what init may take
        move    r4,x:(r7+$17)
        move    x:(r7+$15),r1           ; the id, where the dispatcher has it
        move    x:(r1+$215),r2          ; INIT_TABLE[id]
        move    r5,r7                   ; the slot's block
        jsr     (r2)
        move    #>$7c00,r7
        move    x:(r7+$15),r1
        move    x:(r1+$235),r2          ; PROC_TABLE[id]
        move    x:(r7+$17),r4
        move    r2,x:(r4+$1)            ; the slot runs it from the next frame
        move    x:(r7+$16),r0
tsame:
        rts

; ---- the AUX sends from the record: r0 at halfword 21, ten halfwords, two
; gains each, (a << 8) | b, each 0..127 and squared to the stock level law
; (v/128)^2 as a Q23 fraction, 0..127 -> 0..0x7e04 << 9. r1 the destination, n0 the
; halfword count.
; mpy x0,y1 is a signed form (CLAUDE.md); both operands are positive here.
tgain:
        do      n0,tgloop
        move    x:(r0),a
        and     #>$7f00,a               ; a << 8
        asl     #$8,a,a                 ; a << 16
        move    a1,x0
        move    a1,y1
        mpy     x0,y1,a
        move    a1,x:(r1)+
        move    x:(r0)+,a
        and     #>$7f,a
        asl     #$10,a,a                ; b << 16
        move    a1,x0
        move    a1,y1
        mpy     x0,y1,a
        move    a1,x:(r1)+
tgloop:
        rts

; ---- the AUX passes (MIXER.md sections 18, 19). Two more buses over the twelve
; sources: the eight tracks (x:$204's block, 32 words each, L/R interleaved, L at
; +2j), the two input pairs the mixdown chose (four words a sample), and the two
; returns' wet of the last frame (RET A at X:0x7de0, RET B at X:0x7dc0, sixteen L/R
; pairs each): g_k * source_k summed in 56 bits, stored limited. r7 is the strip's
; block on entry and again on return (the pass borrows it for RET B's block).
auxrun:
        move    x:>$202,b               ; the input ring, as the mixdown chooses it
        move    #>$140,x1               ; (P:0x23f..0x24e)
        move    #>$240,x0
        move    x:>$437,a
        tst     a
        beq     auxr1
        sub     x1,b
auxr1:
        cmp     #>$8100,b
        bge     auxr2
        add     x0,b
auxr2:
        move    b,x:>$7c18              ; its start
        move    #>$1f,n0                ; R, then the next track's L
        move    #>$7c80,r5              ; AUX A's sends
        move    #>$7ca0,r3              ; AUX A
        move    x:>$204,r1              ; the tracks' block
        move    x:>$7c18,r2
        move    #>$7de0,r4
        move    #>$7dc0,r7
        bsr     auxbus
        move    #>$7c8c,r5              ; AUX B's sends
        move    #>$7cc0,r3
        move    x:>$204,r1
        move    x:>$7c18,r2
        move    #>$7de0,r4
        move    #>$7dc0,r7
        bsr     auxbus
        move    #>$7c00,r7
        rts

; r1 the tracks' block, r2 the input ring, r3 the output, r4 RET A's wet, r7 RET B's,
; r5 the twelve sends.
auxbus:
        do      #$10,auxlp
        move    r1,r0
        move    r5,r6
        move    x:(r0)+,x0              ; T1 L
        move    x:(r6)+,y0
        mpy     y0,x0,a         x:(r0)+n0,x0
        mpy     y0,x0,b         x:(r0)+,x0
        move    x:(r6)+,y0              ; T2
        mac     y0,x0,a         x:(r0)+n0,x0
        mac     y0,x0,b         x:(r0)+,x0
        move    x:(r6)+,y0              ; T3
        mac     y0,x0,a         x:(r0)+n0,x0
        mac     y0,x0,b         x:(r0)+,x0
        move    x:(r6)+,y0              ; T4
        mac     y0,x0,a         x:(r0)+n0,x0
        mac     y0,x0,b         x:(r0)+,x0
        move    x:(r6)+,y0              ; T5
        mac     y0,x0,a         x:(r0)+n0,x0
        mac     y0,x0,b         x:(r0)+,x0
        move    x:(r6)+,y0              ; T6
        mac     y0,x0,a         x:(r0)+n0,x0
        mac     y0,x0,b         x:(r0)+,x0
        move    x:(r6)+,y0              ; T7
        mac     y0,x0,a         x:(r0)+n0,x0
        mac     y0,x0,b         x:(r0)+,x0
        move    x:(r6)+,y0              ; T8, then the input ring
        mac     y0,x0,a         x:(r0)+n0,x0
        mac     y0,x0,b         x:(r2)+,x0
        move    x:(r6)+,y0              ; IN AB
        mac     y0,x0,a         x:(r2)+,x0
        mac     y0,x0,b         x:(r2)+,x0
        move    x:(r6)+,y0              ; IN CD
        mac     y0,x0,a         x:(r2)+,x0
        mac     y0,x0,b         x:(r4)+,x0
        move    x:(r6)+,y0              ; RET A's wet
        mac     y0,x0,a         x:(r4)+,x0
        mac     y0,x0,b         x:(r7)+,x0
        move    x:(r6)+,y0              ; RET B's wet
        mac     y0,x0,a         x:(r7)+,x0
        mac     y0,x0,b
        lua     (r1+$2),r1              ; the next sample
        move    a,x:(r3)+
        move    b,x:(r3)+
auxlp:
        rts

; ---- the return B slot (MIXER.md section 19): AUX B through the effect the
; record chose, in place; the wet of this frame is what the AUX passes and the
; next frame's head hear. A slot whose proc is 0 is dry: the wet blocks are zero.
; An effect that returns dry + wet (the reverb server, id 7) has the dry taken back.
retrun:
        move    x:>$7ce1,a              ; RET B's proc
        tst     a
        bne     retgo
        move    #>$7dc0,r0              ; dry: RET B's wet is zero
        clr     a
        do      #$20,retz
        move    a,x:(r0)+
retz:
        bra     retmix
retgo:
        move    #>$7cc0,r0              ; AUX B into the block the effect works on
        move    #>$7dc0,r1
        do      #$20,retc
        move    x:(r0)+,x0
        move    x0,x:(r1)+
retc:
        move    #>$7dc0,r0              ; r0 = 0 mod 32: the server's frame offset is 0
        move    #>$7cf0,r6
        move    x:>$7ce0,r1             ; the id, where the dispatcher has it
        move    x:>$7ce1,r2
        move    #>$7f00,r7              ; its instance block
        move    #$10,n7                 ; sixteen frames
        move    #$1,n0
        move    #$1,a                   ; the dispatcher's call flag
        clr     b
        jsr     (r2)
        move    #>$7c00,r7
        move    x:>$7ce0,a
        move    #>$7,x0
        cmp     x0,a
        bne     retmix                  ; a replacing effect: the block is the wet
        move    #>$7dc0,r0              ; dry + wet: the dry (AUX B, unchanged) out
        move    #>$7cc0,r1
        do      #$20,rets
        move    x:(r0),a
        move    x:(r1)+,x0
        sub     x0,a
        move    a,x:(r0)+
rets:
; the head's blocks: MAIN's add M and CUE's add Cc, 16 L/R pairs each, from the
; two returns' wet at their levels and CUE sends (X:0x7c98..0x7c9b: RET B level,
; CUE send, RET A level, CUE send)
retmix:
        move    #>$7e90,r2
        move    x:>$7c98,y0
        move    #>$7dc0,r0
        do      #$20,retm1
        move    x:(r0)+,x0
        mpy     y0,x0,a
        move    a,x:(r2)+
retm1:
        move    #>$7e90,r2
        move    x:>$7c9a,y0
        move    #>$7de0,r0
        do      #$20,retm2
        move    x:(r2),a
        move    x:(r0)+,x0
        mac     y0,x0,a
        move    a,x:(r2)+
retm2:
        move    #>$7eb0,r2
        move    x:>$7c99,y0
        move    #>$7dc0,r0
        do      #$20,retm3
        move    x:(r0)+,x0
        mpy     y0,x0,a
        move    a,x:(r2)+
retm3:
        move    #>$7eb0,r2
        move    x:>$7c9b,y0
        move    #>$7de0,r0
        do      #$20,retm4
        move    x:(r2),a
        move    x:(r0)+,x0
        mac     y0,x0,a
        move    a,x:(r2)+
retm4:
        rts

; ---- cap the gain at r0 to x0 (a return's wet into an AUX bus)
tcap:
        move    x:(r0),a
        cmp     x0,a
        bmi     tkeep
        beq     tkeep
        move    x0,x:(r0)
tkeep:
        rts
