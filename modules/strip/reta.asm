; ---------------------------------------------------------------------------
; MASTER STRIP -- RET A, payload B (core 1): an effect chosen from the pool on
; AUX A, at the frame's end.
;
; Reached by `jsr` over P:0x333's two-word `move x:>$415,a`, after the last track's
; effects of this frame (the code below is payload A's P:0x53e, relocated: nothing
; branches into it and every register it reads it writes first, so all are free
; here). AUX A is core 0's: its tail publishes the summed block into the shared
; window (tail.asm's retpub), and this reads the last one published; the wet goes
; back the same way (retain). MIXER.md section 20 has the exchange's map.
;
; Core 1's block, X:0x7c00..0x7fff (X above the curve bank is free on this core; boot
; zeroes it, retab_boot.asm):
;   0x7ce0  the id the slot runs            0x7ce1  its proc (0: dry)
;   0x7cf0  its record (r6): the shared 0x37010..0x3701e each frame
;   0x7dc0  the block the effect works on (32-aligned: the servers take their frame
;           offset from r0)                 0x7de0  the dry, for an effect that
;           returns dry + wet
;   0x7f00  its instance block (0x100 wide)
; The list it may run is core 0's (tslot): the delay server (6) and OXIDE (0x1f), and
; an id that aliases SEND on this image (a remix without the delay server) is dry.
; ---------------------------------------------------------------------------
entry:
        move    x:>$3701f,a             ; the id core 0 parsed from the record
        and     #>$ffff,a
        move    a1,x:>$7c1b
        tst     a
        beq     radry
        move    x:>$7ce0,x0
        sub     x0,a
        beq     rasame
; ---- a new id: the slot runs it if the list allows and the image has it -------
        move    x:>$7c1b,x0
        move    x0,x:>$7ce0
        clr     a
        move    a,x:>$7ce1              ; dry unless it is on the list
        move    x:>$7c1b,a
        move    #>$1f,x0
        sub     x0,a
        beq     ralist
        move    x:>$7c1b,a
        move    #>$6,x0
        sub     x0,a
        bne     rasame
ralist:
        move    x:>$7c1b,r1
        move    x:(r1+$235),a
        move    x:>$23e,x0              ; SEND's proc: an id this image lacks
        cmp     x0,a
        beq     rasame
        move    #>$7cf0,r6
        move    #>$7f00,r7
        move    x:(r1+$215),r2          ; INIT_TABLE[id]
        jsr     (r2)
        move    x:>$7c1b,r1
        move    x:(r1+$235),a
        move    a1,x:>$7ce1             ; the slot runs it from here
rasame:
; ---- the record, every frame ---------------------------------------------------
        move    #>$37010,r0
        move    #>$7cf0,r1
        do      #$f,rarec
        move    x:(r0)+,x0
        move    x0,x:(r1)+
rarec:
        move    x:>$7ce1,a
        tst     a
        beq     radry
; ---- AUX A, the last published slot, into the block and the dry copy ---------------
        move    x:>$37000,a
        and     #>$3,a
        asl     #$5,a,a
        move    a1,x0
        move    #>$37020,a
        add     x0,a
        move    a1,r0
        move    #>$7dc0,r1
        move    #>$7de0,r2
        do      #$20,raauxc
        move    x:(r0)+,x0
        move    x0,x:(r1)+
        move    x0,x:(r2)+
raauxc:
        move    #>$7dc0,r0
        move    #>$7cf0,r6
        move    x:>$7ce0,r1
        move    x:>$7ce1,r2
        move    #>$7f00,r7
        move    #$10,n7
        move    #$1,n0
        move    #$1,a                   ; the dispatcher's call flag
        clr     b
        jsr     (r2)
        move    x:>$7ce0,a
        move    #>$6,x0
        sub     x0,a
        bne     rapub                   ; a replacing effect: the block is the wet
        move    #>$7dc0,r0              ; dry + wet: the dry out
        move    #>$7de0,r1
        do      #$20,rasub
        move    x:(r0),a
        move    x:(r1)+,x0
        sub     x0,a
        move    a,x:(r0)+
rasub:
        bra     rapub
radry:
        move    #>$7dc0,r0              ; dry: silence out
        clr     a
        do      #$20,razero
        move    a,x:(r0)+
razero:
; ---- the wet into the next slot, then published --------------------------------------
rapub:
        move    x:>$37001,a
        add     #>$1,a
        and     #>$ffff,a
        move    a1,x:>$7c1c
        and     #>$3,a
        asl     #$5,a,a
        move    a1,x0
        move    #>$370a0,a
        add     x0,a
        move    a1,r1
        move    #>$7dc0,r0
        do      #$20,rapc
        move    x:(r0)+,x0
        move    x0,x:(r1)+
rapc:
        move    x:>$7c1c,a
        move    a1,x:>$37001
        move    x:>$415,a               ; the displaced instruction, as stock has it
        rts
