| strip_xport -- the master strip's slot record, ColdFire -> core 0, every frame.
|
| The host-transfer chain (0x40004840, docs/firmware/DSP.md section 6c) sends
| each DSP its per-frame blocks, one eDMA channel-0 burst per state, the next
| state entered from the burst's completion interrupt through the table at
| 0x400ab61a. This unit takes state 3's entry (0x400049ca, core 0's 64-word
| block to X:0x6800, which sets its own NBYTES): the first visit packs
| strip_model into strip_tx and sends it to core 0; the completion re-enters
| with the state still 3, and it hands over to stock. One more burst a frame,
| every frame. State 5 is the Machinedrum's (origin/machinedrum md_xport.s,
| which this unit follows step for step); state 3 keeps the two combinable.
|
| The block goes to X:0x7c80. Payload A's host-command handler (P:0x588)
| masks every destination with 0x3fff or 0x5fff, alternately per frame (the
| DSP patches the mask at P:0x58c), so it lands at X:0x3c80 or X:0x5c80: the
| bank the DSP works in the next frame, x:$205 + $1480 there, as every stock
| block does. Neither is written by anything else under the port on the
| user's project (`ot_emu --dsp-writes`, 300 frames, 29 Sep 2026).
|
| One DSP word per 16-bit bus cycle (the host port's mover), the halfword in
| bits 15..0 and the top byte not zero. Thirty-two halfwords, one 64-byte
| burst (4 minor loops of 16-byte beats, as every stock block):
|   [0]       0x5354, the magic
|   [1]       slot 1's effect id (the stock dispatch id; 0 = none)
|   [2..7]    its page-1 values 0..5, each v << 8
|   [8..10]   its page-2 values in pairs, (v6 << 8) | v7, (v8 << 8) | v9,
|             (v10 << 8) | v11
|   [11..20]  slot 2, the same
|   [21..30]  zero
|   [31]      the checksum: the 32 halfwords sum to 0 mod 2^16
| so every halfword h is the r6 record word (h << 8): page 1 at r6 + 0..5,
| page 2 at r6 + $c..$e, as the stock dispatcher hands a track's knobs to its
| effect. The DSP side (tail.asm) takes the record only when the magic and
| the checksum hold, masks every value to 0..127, and runs an id only from
| its own list.
|
| strip_model is what the MIXER page edits (and a Part will store): two
| slots of 16 bytes, the id at +0, the twelve values at +4..+15. It starts
| as the strip ran before it had a record: OXIDE (0x1f) at IN 48 / OUT 80 on
| slot 1, slot 2 empty; boot.asm starts the DSP at the same state, so the
| first frames before a record arrives run what the record then says.
|
| ISR context: the chain's prologue saved d0-d1/a0-a1 only.

        .equ    STOCK3,    0x400049ca   | stock state 3: core 0's 64-word block
        .equ    ISR_OUT,   0x40004bc8   | the chain's exit: movem d0-d1/a0-a1, rte
        .equ    UNCACHED,  0x08000000   | the DMA reads SDRAM; write past the cache
        .equ    MBOX_DEST, 0x7c80
        .equ    TX_HW,     32
        .equ    MAGIC,     0x5354
        .equ    SLOTS,     2
        .equ    SLOT_HW,   10           | halfwords a slot: id, 6 page 1, 3 page 2

        .text
        .global strip_xport, strip_model, strip_sent, strip_frames, strip_tx

strip_xport:
        tst.b   strip_sent
        bne.w   sx_after                | our burst just completed: stock's turn
        lea     -12(%sp),%sp
        movem.l %d2-%d4,(%sp)
        lea     strip_model,%a0
        move.l  #strip_tx+UNCACHED,%a1
        move.l  #MAGIC,%d2              | d2: the halfwords' running sum
        move.w  %d2,(%a1)+
        moveq   #SLOTS-1,%d4
1:      mvz.b   (%a0),%d0               | the slot's effect id
        addq.l  #4,%a0                  | its values
        add.l   %d0,%d2
        move.w  %d0,(%a1)+
        moveq   #6-1,%d3                | page 1: v << 8
2:      mvz.b   (%a0)+,%d0
        lsl.l   #8,%d0
        add.l   %d0,%d2
        move.w  %d0,(%a1)+
        subq.l  #1,%d3
        bpl.s   2b
        moveq   #3-1,%d3                | page 2: two values a halfword
3:      mvz.b   (%a0)+,%d0
        lsl.l   #8,%d0
        mvz.b   (%a0)+,%d1
        or.l    %d1,%d0
        add.l   %d0,%d2
        move.w  %d0,(%a1)+
        subq.l  #1,%d3
        bpl.s   3b
        subq.l  #1,%d4
        bpl.s   1b
        moveq   #TX_HW-2-SLOTS*SLOT_HW-1,%d3
4:      clr.w   (%a1)+
        subq.l  #1,%d3
        bpl.s   4b
        neg.l   %d2
        move.w  %d2,(%a1)               | the checksum
| the burst, as stock state 1 sends core 0's per-track records
        clr.b   0xfc0a400c              | core 0's host port
        moveq   #TX_HW/2,%d0            | NBYTES: 64 bytes over 4 minor loops
        move.l  %d0,0xfc045008
        move.l  #strip_tx,%d0
        move.l  %d0,0xfc045000          | SADDR
        move.w  #0x81,%d0
        move.w  %d0,0x20000000
        move.w  #MBOX_DEST,%d0
        move.w  %d0,0x2000001c          | the DSP destination
        moveq   #TX_HW-1,%d0
        move.w  %d0,0x2000001c          | its count - 1
        move.w  #0x88,%d0
        move.w  %d0,0x20000004          | host command 0x10: DMA0 in
        move.w  #0x8004,%d0
        move.w  %d0,0xfc045014          | CITER 4, linked to itself
        move.w  %d0,0xfc04501c          | BITER
        clr.b   0xfc04401e              | SSRT: start channel 0
        moveq   #1,%d0
        move.b  %d0,strip_sent
        addq.l  #1,strip_frames
        movem.l (%sp),%d2-%d4
        lea     12(%sp),%sp
        jmp     ISR_OUT

| Stock state 3 writes its own NBYTES, chip select and SADDR: nothing of
| ours carries over.
sx_after:
        clr.b   strip_sent
        jmp     STOCK3

        .balign 4
strip_frames:   .long   0               | records sent
strip_sent:     .byte   0               | our burst is in flight
        .balign 4
strip_model:                            | two slots: id, 3 spare, 12 values
        .byte   0x1f, 0, 0, 0           | slot 1: OXIDE
        .byte   48, 80, 0, 0, 0, 0      |   IN 48, OUT 80 (0 dB)
        .byte   0, 0, 0, 0, 0, 0
        .byte   0, 0, 0, 0              | slot 2: none
        .byte   0, 0, 0, 0, 0, 0
        .byte   0, 0, 0, 0, 0, 0
        .balign 16
strip_tx:       .space  TX_HW*2         | the block (the DMA's SADDR; 16-byte beats)
