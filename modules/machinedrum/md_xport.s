| md_xport -- the Machinedrum's record transport, ColdFire side (WP-C1).
|
| The host-transfer chain (0x40004840, DSP.md section 6c) sends each DSP
| its per-frame blocks, one eDMA channel-0 burst per state, the next state
| entered from the burst's completion interrupt through the table at
| 0x400ab61a. This unit takes state 5's entry (core 0's per-voice block,
| 0x40004aaa, which follows core 1's at state 4): when a block is waiting it
| sends it to core 1 first and returns; the completion re-enters with the
| state still 5, and it hands over to stock. With nothing to send, stock
| runs at once. So the chain gains one burst on frames that carry records
| and none on the others.
|
| The block goes to X:0x7d40. Payload B's host-command handler (P:0x36d)
| masks every destination with 0x3fff or 0x5fff, alternately per frame, so
| it lands at X:0x3d40 or X:0x5d40 -- the bank the DSP reads the next frame,
| as every stock block does. md_glue.asm (gfxproc) reads it:
|   seq, flags, npkt, then npkt x [dest] [count] [hi lo] x count
| Dest $800-$bff addresses Y voice records; $c00-$c1f addresses the
| thirty-two X gain words (sixteen left, sixteen right). The test stream
| may carry either kind. The future kit producer owns live gain updates.
| One DSP word per 16-bit bus cycle (rtos.cpp's host-port mover), so a
| 24-bit record word travels as two. The burst is whole 64-byte multiples
| (4 minor loops of 16-byte beats, as every stock block), at most 448
| halfwords (layout.py mbox_a).
|
| THE PRODUCER. A test feed (tools/verify/verify_md_transport.py):
| md_feed points at a stream of chunks, each
|   flags, npkt, nhw, then nhw halfwords of packets
| and 0xffff in npkt ends it. Without a feed, md_gain_set's dirty part pairs
| are sent one per frame via the same md_tx DMA path. The Machinedrum's own
| voice update (WP-C4) still needs to supply live record packets.
|
| ISR context: the chain's prologue saved d0-d1/a0-a1 only.
|
| STOCK STATE 5 DOES NOT WRITE NBYTES: it sends core 0's per-voice block
| with the 64 that state 4 left for core 1's. The burst here saves the TCD's
| NBYTES and puts it back before stock runs. Without that, core 0's block
| went out a quarter short, core 0's DMA0 waited for the rest and the chain
| never reached the state that unmasks the frame interrupt (the port, 24 Sep
| 2026: one frame, then none).

        .equ    STOCK5,    0x40004aaa   | stock state 5: core 0's per-voice block
        .equ    ISR_OUT,   0x40004bc8   | the chain's exit: movem d0-d1/a0-a1, rte
        .equ    UNCACHED,  0x08000000   | the DMA reads SDRAM; write past the cache
        .equ    MBOX_DEST, 0x7d40
        .equ    MBOX_HW,   448
        .equ    FEED_END,  0xffff

        .text
        .global md_xport, md_feed, md_seq, md_sent, md_blocks, md_over, md_tx
        .global md_gain_set, md_gain_dirty, md_gain_values

md_xport:
        tst.b   md_sent
        bne.w   md_after                | our burst just completed: stock's turn
        lea     -8(%sp),%sp
        movem.l %d2-%d3,(%sp)
        move.l  md_feed,%d0
        beq.w   md_gain_prepare
md_have:
        move.l  %d0,%a0
        mvz.w   2(%a0),%d1              | npkt
        cmp.l   #FEED_END,%d1
        bne.s   1f
        clr.l   md_feed                 | the stream is over
        bra.w   md_gain_prepare
1:      mvz.w   4(%a0),%d2              | halfwords of packets
        move.l  %d2,%d3
        add.l   #3+31,%d3               | + seq, flags, npkt, rounded up to
        and.l   #-32,%d3                | whole 64-byte bursts
        cmp.l   #MBOX_HW,%d3
        bls.s   2f
        addq.l  #1,md_over              | does not fit the mailbox: dropped
        lea     6(%a0,%d2.l*2),%a0
        move.l  %a0,md_feed
        bra.w   md_idle
2:      move.l  #md_tx+UNCACHED,%a1
        move.l  md_seq,%d0
        addq.l  #1,%d0
        and.l   #0xffff,%d0
        bne.s   3f
        moveq   #1,%d0                  | seq skips 0, the glue's "nothing yet"
3:      move.l  %d0,md_seq
        move.w  %d0,(%a1)+
        move.w  (%a0),(%a1)+            | flags
        move.w  %d1,(%a1)+              | npkt
        addq.l  #6,%a0
        move.l  %d2,%d0
        bra.s   5f
4:      move.w  (%a0)+,(%a1)+
5:      subq.l  #1,%d0
        bpl.s   4b
        move.l  %a0,md_feed             | the next chunk
| the burst, as stock state 4 sends core 1's per-voice block
        moveq   #1,%d0
        move.b  %d0,0xfc0a400c          | core 1's host port
        move.l  0xfc045008,%d0
        move.l  %d0,md_nbytes           | stock state 5 reuses it
        move.l  %d3,%d0
        lsr.l   #1,%d0                  | NBYTES: the block's bytes over 4 minor loops
        move.l  %d0,0xfc045008
        move.l  #md_tx,%d0
        move.l  %d0,0xfc045000          | SADDR
        move.w  #0x81,%d0
        move.w  %d0,0x20000000
        move.w  #MBOX_DEST,%d0
        move.w  %d0,0x2000001c          | the DSP destination
        move.l  %d3,%d0
        subq.l  #1,%d0
        move.w  %d0,0x2000001c          | its count - 1
        move.w  #0x88,%d0
        move.w  %d0,0x20000004          | host command 0x10: DMA0 in
        move.w  #0x8004,%d0
        move.w  %d0,0xfc045014          | CITER 4, linked to itself
        move.w  %d0,0xfc04501c          | BITER
        clr.b   0xfc04401e              | SSRT: start channel 0
        moveq   #1,%d0
        move.b  %d0,md_sent
        addq.l  #1,md_blocks
        movem.l (%sp),%d2-%d3
        lea     8(%sp),%sp
        jmp     ISR_OUT

md_idle:
        movem.l (%sp),%d2-%d3
        lea     8(%sp),%sp
        jmp     STOCK5

| One dirty part becomes two one-word gain packets. The caller and ISR share
| one ColdFire core, so md_gain_set clears the dirty bit before replacing
| the pair and sets it only after both words are ready. The newest value wins.
md_gain_prepare:
        move.l  md_gain_dirty,%d0
        beq.w   md_idle
        moveq   #0,%d2
        moveq   #1,%d3
md_gain_scan:
        move.l  %d0,%d1
        and.l   %d3,%d1
        bne.s   md_gain_found
        addq.l  #1,%d2
        lsl.l   #1,%d3
        cmpi.l  #16,%d2
        bne.s   md_gain_scan
        bra.w   md_idle
md_gain_found:
        move.l  %d3,%d1
        not.l   %d1
        and.l   %d1,md_gain_dirty
        move.l  %d2,%d0
        lsl.l   #3,%d0
        lea     md_gain_values,%a0
        adda.l  %d0,%a0
        lea     md_live_chunk,%a1
        clr.w   (%a1)+                  | flags: no half sync
        move.w  #2,(%a1)+               | two gain packets
        move.w  #8,(%a1)+               | eight packet halfwords
        move.l  %d2,%d0
        add.l   #0xc00,%d0
        move.w  %d0,(%a1)+              | left destination
        move.w  #1,(%a1)+
        move.l  (%a0)+,%d1
        move.l  %d1,%d0
        swap    %d0
        move.w  %d0,(%a1)+
        move.w  %d1,(%a1)+
        move.l  %d2,%d0
        add.l   #0xc10,%d0
        move.w  %d0,(%a1)+              | right destination
        move.w  #1,(%a1)+
        move.l  (%a0),%d1
        move.l  %d1,%d0
        swap    %d0
        move.w  %d0,(%a1)+
        move.w  %d1,(%a1)+
        clr.w   (%a1)+                  | terminator for md_feed
        move.w  #FEED_END,(%a1)+
        clr.w   (%a1)+
        move.l  #md_live_chunk,%d0
        move.l  %d0,md_feed
        move.l  md_feed,%d0
        bra.w   md_have

md_after:
        clr.b   md_sent
        move.l  md_nbytes,%d0
        move.l  %d0,0xfc045008
        jmp     STOCK5

| md_gain_set(d0=part 0..15, d1=left Q23, d2=right Q23). Returns d0=0 on
| success or 1 for an invalid part/value. The UI/kit producer calls this
| after translating VOL/PAN. d2 is read, not clobbered (callee-saved ABI).
md_gain_set:
        cmpi.l  #16,%d0
        bcc.s   md_gain_reject
        cmpi.l  #0x7fffff,%d1
        bhi.s   md_gain_reject
        cmpi.l  #0x7fffff,%d2
        bhi.s   md_gain_reject
        move.l  %d3,-(%sp)
        moveq   #1,%d3
        lsl.l   %d0,%d3
        move.l  %d3,%a0
        not.l   %d3
        and.l   %d3,md_gain_dirty       | old pending pair is superseded
        lsl.l   #3,%d0
        lea     md_gain_values,%a1
        adda.l  %d0,%a1
        move.l  %d1,(%a1)+
        move.l  %d2,(%a1)
        move.l  %a0,%d3
        or.l    %d3,md_gain_dirty       | publish after both writes
        move.l  (%sp)+,%d3
        moveq   #0,%d0
        rts
md_gain_reject:
        moveq   #1,%d0
        rts

        .balign 4
md_feed:    .long   0                   | the test stream's next chunk (0: none)
md_seq:     .long   0                   | the last block's sequence number
md_blocks:  .long   0                   | blocks sent
md_over:    .long   0                   | chunks dropped: larger than the mailbox
md_nbytes:  .long   0                   | the TCD's NBYTES across our burst
md_sent:    .byte   0                   | our burst is in flight
        .balign 4
md_gain_dirty:  .long 0                | one bit per pending part
md_gain_values: .space 16*8             | left/right Q23 longs, part-major
md_live_chunk:  .space 28               | 3 + 8 + 3 halfwords
        .balign 16
md_tx:      .space  MBOX_HW*2           | the block (the DMA's SADDR; 16-byte beats)
