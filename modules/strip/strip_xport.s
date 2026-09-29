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
|   [21..30]  the AUX sends, two 7-bit gains a halfword, (g0 << 8) | g1 in
|             aux_model's order: AUX A's ten sources (T1..T8, IN AB, IN CD),
|             then AUX B's (docs/proposals/MIXER.md section 18)
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
| The Part keeps it. Each Part window (0x18b2 bytes a part, docs/firmware/
| STORAGE.md section 3) carries the two slots at bank + 0x904e2: 32 bytes, the
| audio LFO designer's shapes T7 and T8 (stock copies 16 bytes from
| bank + 0x90482 + 16 n into the LFO when a WAVE of 11 + n is chosen: n = 0..7,
| so T7 and T8 are 0x904e2 and 0x904f2; the audio census in docs/proposals/
| MIXER.md section 15). A slot is stored as it is modelled but for its spare
| bytes, which hold a tag (0x53), the checksum byte that makes the sixteen sum
| to 0 mod 256, and the version (1). The Part is the truth and strip_model its
| cache: strip_sync, once a frame before the record is packed, reads the window
| of the part the panel edits (0x100b14cf) in the resident bank (0x46c82456)
| and, when it has held one new value for two frames running, adopts it: both
| slots valid, the model is the Part's; otherwise (a Part nobody has written,
| a designer shape drawn over it) the boot default. Part Save, Part Reload,
| a project load, a bank change and a part change are all this one look.
| strip_store, the MIXER page's edits, writes the model to the window, to the
| part's SRAM twin (0x100a4ece + part * 0x18b2, the copy that survives a power
| cycle) and sets the stock editors' dirty marks (as the FX2 page-2 editor's
| store does, 0x4003aab6..0x4003aaea), with the ISR's look held off meanwhile.
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
        .equ    AUX_HW,    TX_HW-2-SLOTS*SLOT_HW    | the sends: 10 halfwords, 20 gains
        .equ    DBPTR,     0x46c82456   | long: the resident bank's DB (stock's UI code)
        .equ    PARTSEL,   0x100b14cf   | byte: the part the panel edits
        .equ    SRAM_PART, 0x100a4ece   | + part * PSTRIDE: the working parts' twin
        .equ    DIRTY,     0x40027e00   | what stock's editors call after their stores
        .equ    PSTRIDE,   0x18b2
        .equ    PARTS,     4            | stock's; a kit's window (Octakit) is not ours
        .equ    WOFF,      0x904e2      | in the bank: part 0's slot 1 (0x8ed80 + 0x1762)
        .equ    TWOFF,     0x1762       | the same in a part
        .equ    TAG,       0x53
        .equ    VERSION,   1

        .text
        .global strip_xport, strip_model, aux_model, strip_sent, strip_frames, strip_tx
        .global strip_store, strip_default, strip_seen, strip_cand, strip_lock

strip_xport:
        tst.b   strip_sent
        bne.w   sx_after                | our burst just completed: stock's turn
        lea     -12(%sp),%sp
        movem.l %d2-%d4,(%sp)
        bsr.w   strip_sync              | the Part's copy, adopted when it changed
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
        lea     aux_model,%a0           | the sends: two 7-bit gains a halfword
        moveq   #AUX_HW-1,%d3
4:      mvz.b   (%a0)+,%d0
        lsl.l   #8,%d0
        mvz.b   (%a0)+,%d1
        or.l    %d1,%d0
        and.l   #0x7f7f,%d0             | the DSP masks again; a clean sum here
        add.l   %d0,%d2
        move.w  %d0,(%a1)+
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

| ---------------------------------------------------------- the Part's copy --
| swin: d0 = the part the panel edits (0..3), a0 = its window's slot 1; d0 = -1
| when there is no bank yet or the part is not one of stock's four (clobbers
| d1)
swin:   move.l  DBPTR,%a0
        move.l  %a0,%d0
        beq.s   1f
        mvz.b   PARTSEL,%d1
        moveq   #PARTS,%d0
        cmp.l   %d0,%d1
        bhs.s   1f
        move.l  #PSTRIDE,%d0
        mulu.l  %d1,%d0
        add.l   %a0,%d0
        add.l   #WOFF,%d0
        move.l  %d0,%a0
        move.l  %d1,%d0
        rts
1:      moveq   #-1,%d0
        rts

| same32: Z set when the 32 bytes at a0 and at a1 are equal (clobbers d0-d2,
| a0, a1)
same32: moveq   #16-1,%d1
1:      mvz.w   (%a0)+,%d0
        mvz.w   (%a1)+,%d2
        cmp.l   %d2,%d0
        bne.s   2f
        subq.l  #1,%d1
        bpl.s   1b
        moveq   #0,%d0
2:      rts

| copy32: the 32 bytes at a0 to a1, a halfword at a time (a window is 2 mod 4
| from the second part on); clobbers a0, a1
copy32: .rept   16
        move.w  (%a0)+,(%a1)+
        .endr
        rts

| ok16: Z set when the sixteen bytes at a0 are a stored slot: the tag, the
| version, a sum of 0 mod 256, an effect id on the strip's list (SU_IDS, ended
| by 0xff). Clobbers d0-d2, a1
ok16:   mvz.b   1(%a0),%d0
        moveq   #TAG,%d1
        cmp.l   %d1,%d0
        bne.s   9f
        mvz.b   3(%a0),%d0
        moveq   #VERSION,%d1
        cmp.l   %d1,%d0
        bne.s   9f
        moveq   #0,%d0
        moveq   #16-1,%d1
        move.l  %a0,%a1
1:      mvz.b   (%a1)+,%d2
        add.l   %d2,%d0
        subq.l  #1,%d1
        bpl.s   1b
        and.l   #0xff,%d0
        bne.s   9f
        mvz.b   (%a0),%d0
        lea     SU_IDS,%a1
2:      mvz.b   (%a1)+,%d1
        cmp.l   #0xff,%d1
        beq.s   9f
        cmp.l   %d1,%d0
        bne.s   2b
        moveq   #0,%d0                  | on the list
        rts
9:      moveq   #1,%d0
        rts

| strip_sync: the ISR's look at the shown Part. A window that is not the one
| adopted (strip_seen) is noted (strip_cand); the same window a frame later is
| adopted: a Part being copied whole by stock is not read half written.
strip_sync:
        lea     -12(%sp),%sp
        movem.l %d3/%a2-%a3,(%sp)
        tst.b   strip_lock
        bne.w   sydone
        bsr.w   swin
        tst.l   %d0
        bmi.w   sydone
        move.l  %a0,%a2                 | a2 = the window
        lea     strip_seen,%a1
        bsr.w   same32
        beq.w   sydone                  | nothing new
        move.l  %a2,%a0
        lea     strip_cand,%a3
        move.l  %a3,%a1
        bsr.w   same32
        beq.s   1f
        move.l  %a2,%a0                 | changed since the last frame too: wait
        move.l  %a3,%a1
        bsr.w   copy32
        bra.s   sydone
1:      move.l  %a2,%a0                 | held: adopt it
        lea     strip_seen,%a1
        bsr.w   copy32
        move.l  %a2,%a0
        bsr.w   ok16
        bne.s   dflt
        lea     16(%a2),%a0
        bsr.w   ok16
        bne.s   dflt
        lea     strip_model,%a1         | the Part's, spare bytes back to 0
        move.l  %a2,%a0
        moveq   #32-1,%d3
2:      move.b  (%a0)+,(%a1)+
        subq.l  #1,%d3
        bpl.s   2b
        lea     strip_model,%a1
        clr.b   1(%a1)
        clr.b   2(%a1)
        clr.b   3(%a1)
        clr.b   17(%a1)
        clr.b   18(%a1)
        clr.b   19(%a1)
        bra.s   sydone
dflt:   lea     strip_default,%a0       | nobody's: the boot's
        lea     strip_model,%a1
        moveq   #8-1,%d3
3:      move.l  (%a0)+,(%a1)+
        subq.l  #1,%d3
        bpl.s   3b
sydone: movem.l (%sp),%d3/%a2-%a3
        lea     12(%sp),%sp
        rts

| strip_store: the model is what the Part keeps now. From the MIXER page's
| edits (main context, every register but d0/d1/a0/a1 kept): the two slots
| into strip_seen in their stored form, from there to the window and to the
| part's SRAM twin, then the stock editors' dirty marks. A part that is not
| stock's four keeps the model to itself.
strip_store:
        lea     -20(%sp),%sp
        movem.l %d2-%d4/%a2-%a3,(%sp)
        moveq   #1,%d0
        move.b  %d0,strip_lock          | the ISR's look waits
        bsr.w   swin
        tst.l   %d0
        bmi.w   ssdone
        move.l  %d0,%d4                 | d4 = the part
        move.l  %a0,%a2                 | a2 = its window
        lea     strip_seen,%a3
        lea     strip_model,%a0
        move.l  %a3,%a1
        moveq   #2-1,%d3
1:      mvz.b   (%a0),%d0               | the id
        move.b  %d0,(%a1)
        moveq   #TAG,%d1
        move.b  %d1,1(%a1)
        add.l   %d1,%d0
        moveq   #VERSION,%d1
        move.b  %d1,3(%a1)
        add.l   %d1,%d0
        lea     4(%a0),%a0
        lea     4(%a1),%a1
        moveq   #12-1,%d2
2:      mvz.b   (%a0)+,%d1
        move.b  %d1,(%a1)+
        add.l   %d1,%d0
        subq.l  #1,%d2
        bpl.s   2b
        neg.l   %d0
        move.b  %d0,-14(%a1)            | the checksum, byte 2 of the slot
        subq.l  #1,%d3
        bpl.s   1b
        move.l  %a3,%a0
        move.l  %a2,%a1
        bsr.w   copy32                  | the working window
        move.l  #PSTRIDE,%d0
        mulu.l  %d4,%d0
        add.l   #SRAM_PART+TWOFF,%d0
        move.l  %d0,%a1
        move.l  %a3,%a0
        bsr.w   copy32                  | its twin
        move.l  %a3,%a0
        lea     strip_cand,%a1
        bsr.w   copy32                  | the ISR's look finds nothing new
        move.l  DBPTR,%a0               | the stock editors' marks (0x4003aac6..0x4003aae4)
        moveq   #1,%d1
        lsl.l   %d4,%d1
        move.l  %a0,%d0
        add.l   #0x95048,%d0
        move.l  %d0,%a1
        mvz.b   (%a1),%d0
        or.l    %d1,%d0
        move.b  %d0,(%a1)               | the part's dirty bit in the bank
        mvz.b   0x100b145e,%d0
        or.l    %d1,%d0
        move.b  %d0,0x100b145e
        move.l  %a0,%d0
        add.l   #0x9b332,%d0
        move.l  %d0,%a1
        moveq   #1,%d0
        move.l  %d0,(%a1)
        move.l  %d0,0x100f8598
        jsr     DIRTY
ssdone: clr.b   strip_lock
        movem.l (%sp),%d2-%d4/%a2-%a3
        lea     20(%sp),%sp
        rts

        .balign 4
strip_frames:   .long   0               | records sent
strip_sent:     .byte   0               | our burst is in flight
        .balign 4
        .macro  BOOT_MODEL
        .byte   0x1f, 0, 0, 0           | slot 1: OXIDE
        .byte   48, 80, 0, 0, 0, 0      |   IN 48, OUT 80 (0 dB)
        .byte   0, 0, 0, 0, 0, 0
        .byte   0, 0, 0, 0              | slot 2: none
        .byte   0, 0, 0, 0, 0, 0
        .byte   0, 0, 0, 0, 0, 0
        .endm
strip_model:                            | two slots: id, 3 spare, 12 values
        BOOT_MODEL
strip_default:                          | what a Part nobody has written gives
        BOOT_MODEL
aux_model:      .space  AUX_HW*2        | the sends: AUX A's ten gains, AUX B's ten, 0..127
                                        | (0 = off; zero at boot, so an image with sends
                                        | at rest is stock's mix)
strip_seen:     .space  32              | the window as adopted (stored form)
strip_cand:     .space  32              | the window as last looked at
strip_lock:     .byte   0               | strip_store is writing: the ISR keeps out
        .balign 16
strip_tx:       .space  TX_HW*2         | the block (the DMA's SADDR; 16-byte beats)
