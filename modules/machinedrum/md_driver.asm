; ---------------------------------------------------------------------------
; md_driver -- the OT-side replacement for the Machinedrum voice DSP's loop.
;
; Step 1 (23 Sep 2026): the MD loop's logic (P:64-e7 of the MD's voice DSP,
; read from the disassembly) without its I/O, at the MD's own data addresses.
; For each of the 16 slots it calls the engine's init when the slot's engine
; changed, its trigger when the record's word 0 is set, and its render every
; period. Left out: the slot report to the host every fourth slot (P:73),
; slot 0's frame-sync wait and DMA2 re-arm (P:b9-cb), and the output DMA to
; the mixer (P:cf-d3). md_replay --driver runs it in place of the loop and
; compares every rendered block with the reference.
;
; Step 2a: each slot renders into its own 32 words at $c00 + $20*slot (the
; MD alternates two buffers at $100/$120 and DMAs each block out at once; the
; OT mixes later, so all 16 blocks must survive the batch).
;
; Data the loop keeps (MD addresses, moved in a later step):
;   y:$140  the slot's render buffer (m7 = $1f, so 32-aligned)
;   y:$141  the slot's record base, $800 + $40*slot
;   y:$142  the slot index
;   y:$153+slot  the engine the slot was last initialised for
; Routine tables (193 entries each), patched per layout by md_driver.py:
;   init $145af5, trigger $145bb6, render $145c77
;
; Registers at each call are the loop's, including the ones that look
; incidental (b from the slot arithmetic, x0/x1 from the buffer toggle): an
; engine may read them, and step 1 keeps them until a replay shows it does
; not. The loop's "move m0,mN" is written as an immediate load, and its two
; backward branches as a jump through r0 (free there: every path reloads it
; before use). dsp_asm encodes neither the register form nor a backward bcc,
; and its jmp/jcc only in the short form, which cannot reach above $fff.
; The loop's "cmp a,b" goes through x0 ("move b,x0 / cmp x0,a"): the dsp_asm
; this was built with (pin c051afad) emits accumulator-to-accumulator cmp as
; max, which leaves Z stale. So x0 holds the slot's engine at an init call
; where the loop's x0 was left over from the previous slot. Labels: md_slot is the loop's P:6b (a slot
; starts), md_done its P:b5 (the render returned); md_replay stops at both.
; ---------------------------------------------------------------------------

md_period:
        move    #>$800,x0
        move    x0,y:>$141
        move    #$0,x0
        move    x0,y:>$142
        bra     md_slot                 ; ends a block, so md_slot starts one
md_slot:
        move    y:>$142,b
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
        move    y:>$141,r6
        move    y:>$142,r1
        move    y:(r6),a
        tst     a
        beq     md_render
        move    y:(r1+$153),b
        move    b,x0
        cmp     x0,a
        beq     md_trig
        move    a,r0
        move    y:(r0+$145af5),r2
        move    a,y:(r1+$153)
        jsr     (r2)
md_trig:
        move    y:>$142,r1
        move    y:>$141,r6
        move    y:(r1+$153),r0
        move    y:(r0+$145bb6),r1
        move    #$0,x0
        move    x0,y:(r6)
        jsr     (r1)
md_render:
        move    y:>$142,r1
        move    y:>$142,a               ; each slot renders into its own
        asl     #5,a,a                  ; 32 words, $c00 + $20*slot, kept
        add     #>$c00,a                ; for the mix
        move    #>$100,x1               ; x0/x1 as the loop's buffer
        move    #>$20,x0                ; toggle left them
        move    y:(r1+$153),r0
        move    a,y:>$140
        move    a,r7
        move    y:(r0+$145c77),r1
        move    y:>$141,r6
        move    #>$ffffff,m0
        move    #>$ffffff,m1
        move    #>$ffffff,m2
        move    #>$ffffff,m3
        move    #>$ffffff,m4
        move    #>$ffffff,m5
        move    #$1f,m7
        jsr     (r1)
md_done:
        move    y:>$142,b
        add     #<$1,b
        move    y:>$141,a
        move    b,y:>$142
        add     #>$40,a
        cmp     #<$10,b
        move    a,y:>$141
        beq     md_wrap
        move    #>md_slot,r0
        jmp     (r0)
md_wrap:
        movep   x:<<$ffffea,a
        and     #>$ffffc0,a
        move    a,x:>$256
        move    #>md_period,r0
        jmp     (r0)
