; ---------------------------------------------------------------------------
; md_driver -- the OT-side replacement for the Machinedrum voice DSP's loop.
;
; One call per OT frame (16 samples) renders HALF of the 16 slots, 32
; samples each, alternating halves. So a 32-sample MD period takes two
; frames and the per-frame load stays even. For each slot it calls the
; engine's init when the slot's engine changed, its trigger when the
; record's word 0 is set, and its render every period, as the MD loop does
; (P:64-e7 of the MD's voice DSP, read from the disassembly). The loop's
; I/O is left out: the slot report to the host (P:73), slot 0's frame-sync
; wait and DMA2 re-arm (P:b9-cb), the output DMA (P:cf-d3), and the DMA1
; position (P:e2-e7). The only engines that read the last one are the input
; and control machines, which are not ported.
;
; Around the batch it swaps low memory. The OT's X:0-$ff and Y:0-$13f are
; saved to @STASH@ and put back afterwards. Only the MD's own 36 words that
; outlive a period (X:$a0-$bf, Y:$1e-$21, measured with md_replay's poison
; runs) are kept, at @MDSAVE@; the rest of that range is MD scratch.
; Known deviation: TRX-S2's first block after a trigger reads scratch it
; never wrote, so on the MD it depends on other voices' leftovers. With 36
; words kept, 1-2 such blocks in ~33,500 differ on 2 of 12 kits. Carrying
; the whole low image (576 words each way) fixed one kit, and costs ~70
; cycles/sample more (estimated).
;
; Addresses are placeholders between at-signs that md_driver.py fills per
; layout:
;   @LV140@ @LV141@ @LV142@  the slot's render buffer, record base, index
;   @ENG@     each slot's current engine, @ENG@+slot
;   @HALF@    0 or 8, the first slot of the next call
;   @TMP@     one word, b parked across the empty-slot check
;   @OUTBUF@  16 x 32 words, slot k's block at @OUTBUF@ + $20*k (m7 = $1f,
;             so 32-aligned); the mix reads them
;   @INIT@ @TRIG@ @RENDER@   the routine tables (193 entries each)
;   @EMPTY@   the empty slot's render (32 zeros and a busy-wait: the MD's
;             pacing); the driver writes the zeros itself instead
;
; Registers at each call are the loop's where the loop set them: r6, r0/r1/
; r2, r7, m0-m7, and x0/x1 before a render. Others differ from the MD's; the
; replays show no engine reads them.
;
; dsp_asm (the shared build, pin c051afad) does not take the loop verbatim.
; "move m0,mN" is written as immediate loads. Backward branches go through
; r0 ("move #>label,r0 / jmp (r0)"): there is no backward bcc, and jmp/jcc
; exist only in the short form, which cannot reach above $fff. The loop's
; "cmp a,b" goes through x0, because it assembles as max, which leaves Z
; stale. No label is a prefix of another (labels resolve by prefix;
; md_driver.py checks).
;
; md_replay stops at md_slot (the loop's P:6b: a slot starts), md_done (its
; P:b5: the render returned) and md_idle (the frame is done; on the OT the
; rts back to the dispatcher).
; ---------------------------------------------------------------------------

md_enter:
; ---- swap in: the OT's low memory out, the MD's 36 words in
        move    #$0,r0
        move    #>@STASH@,r4
        do      #256,md_a1
        move    x:(r0)+,x0
        move    x0,y:(r4)+
md_a1:
        move    #$0,r0
        do      #320,md_a2
        move    y:(r0)+,x0
        move    x0,y:(r4)+
md_a2:
        move    #>$a0,r0
        move    #>@MDSAVE@,r4
        do      #32,md_a3
        move    y:(r4)+,x0
        move    x0,x:(r0)+
md_a3:
        move    #>$1e,r0
        do      #4,md_a4
        move    y:(r4)+,x0
        move    x0,y:(r0)+
md_a4:
; ---- this call's slots
        move    y:>@HALF@,a
        move    a,y:>@LV142@
        asl     #6,a,a
        add     #>@VOICE@,a
        move    a,y:>@LV141@
        bra     md_slot                 ; ends a block, so md_slot starts one
md_slot:
        move    y:>@LV142@,b
        asr     #$2,b,a
        and     #<$3,b
        move    #>$ffffff,m0
        move    #>$ffffff,m1
        move    #>$ffffff,m2
        move    #>$ffffff,m3
        move    #>$ffffff,m4
        move    #>$ffffff,m5
        move    #>$ffffff,m6
        move    #>$ffffff,m7
        move    y:>@LV141@,r6
        move    y:>@LV142@,r1
        move    y:(r6),a
        tst     a
        beq     md_render
        move    y:(r1+@ENG@),b
        move    b,x0
        cmp     x0,a
        beq     md_trig
        move    a,r0
        move    y:(r0+@INIT@),r2
        move    a,y:(r1+@ENG@)
        jsr     (r2)
md_trig:
        move    y:>@LV142@,r1
        move    y:>@LV141@,r6
        move    y:(r1+@ENG@),r0
        move    y:(r0+@TRIG@),r1
        move    #$0,x0
        move    x0,y:(r6)
        jsr     (r1)
md_render:
        move    y:>@LV142@,r1
        move    y:>@LV142@,a
        asl     #5,a,a
        add     #>@OUTBUF@,a
        move    #>$100,x1
        move    #>$20,x0
        move    y:(r1+@ENG@),r0
        move    a,y:>@LV140@
        move    a,r7
        move    y:(r0+@RENDER@),r1
        move    y:>@LV141@,r6
        move    #>$ffffff,m0
        move    #>$ffffff,m1
        move    #>$ffffff,m2
        move    #>$ffffff,m3
        move    #>$ffffff,m4
        move    #>$ffffff,m5
        move    #$1f,m7
        move    b,y:>@TMP@              ; b as the loop left it: an engine
        move    r1,b                    ; may read it (TRX-S2's first block
        cmp     #>@EMPTY@,b             ; after a trigger does)
        beq     md_empty
        move    y:>@TMP@,b
        jsr     (r1)
        bra     md_done
md_empty:
        clr     b
        rep     #32
        move    b,y:(r7)+
        bra     md_done                 ; ends a block, so md_done starts one
md_done:
        move    y:>@LV142@,b
        add     #<$1,b
        move    y:>@LV141@,a
        move    b,y:>@LV142@
        add     #>$40,a
        move    a,y:>@LV141@
        move    b,a
        and     #<$7,a
        beq     md_leave
        move    #>md_slot,r0
        jmp     (r0)
md_leave:
; ---- swap out: the MD's 36 words kept, the OT's low memory back
        move    #>$a0,r0
        move    #>@MDSAVE@,r4
        do      #32,md_a5
        move    x:(r0)+,x0
        move    x0,y:(r4)+
md_a5:
        move    #>$1e,r0
        do      #4,md_a6
        move    y:(r0)+,x0
        move    x0,y:(r4)+
md_a6:
        move    #$0,r0
        move    #>@STASH@,r4
        do      #256,md_a7
        move    y:(r4)+,x0
        move    x0,x:(r0)+
md_a7:
        move    #$0,r0
        do      #320,md_a8
        move    y:(r4)+,x0
        move    x0,y:(r0)+
md_a8:
        move    y:>@HALF@,a
        move    #>$8,x0
        eor     x0,a
        move    a,y:>@HALF@
        bra     md_idle                 ; ends a block, so md_idle starts one
md_idle:
        rts
