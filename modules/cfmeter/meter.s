| CF METER -- the frame interrupt's duration and the ColdFire's idle time,
| timed on DMA timer 3 and published to track 8's FX2 page-2 lane.
|
| DTIM3 (`DTMR3 = 0x000b` at 0x400209c0: enabled, internal bus clock,
| prescaler 1, reference 0xffffffff) is a free-running counter the firmware
| itself timestamps with (0x4000169a); at the 132 MHz bus clock one count
| is 7.58 ns. Slot 5 below prints the frame period in its counts, which
| checks the rate against the 16-sample frame.
|
| m_isr    vector 0x41 (main installs it: the `pea` of the stock handler at
|          0x4001fbf8 names m_isr): stamps the entry, burns BURN x 2 us
|          (T8's FX2 page-1 slot 0 in the live lane) while T8's live FX2
|          is CF METER, enters the stock handler.
| m_tail   replaces the handler's epilogue (0x4000d9a6, every exit path):
|          duration = now - entry stamp, into sum / count / max; every
|          125 ms (16,500,000 counts) closes a segment; while T8's live
|          FX2 is CF METER, writes the lane every frame (the lane is
|          refreshed from the Part).
| m_iacc   idle counts, added by CF METER IDLE's loop (idle.s); 0 without it.
|
| The lane's FX2 page-2 words carry N (slots 6/7 = word $c, big-endian)
| and the reference 8192 (slots 8/9 = word $d); the CF METER insert prints
| them as a square wave, so N = 8192 x rms(L) / rms(R)
| (tools/harness/cfmeter.py). The displayed slot k advances per segment:
|
|   k  N
|   0  0 (sync)
|   1  8192 (the reference itself: L/R = 1)
|   2  idle time / segment x 16384
|   3  frame interrupt, mean duration, counts / 4
|   4  frame interrupt, longest in the segment, counts / 4
|   5  frame period (segment / interrupts), counts / 4
|   6  the idle loop's shortest step, counts
|   7  BURN, counts / 4

        .equ    DTCN3,      0xfc07c00c
        .equ    LANE8,      0x80000a08          | 0x80000810 + 7 * 72
        .equ    BURN,       LANE8 + 24          | FX2 page 1 slot 0
        .equ    P2VAL,      LANE8 + 0x38        | FX2 page 2 slots 6/7
        .equ    FX2ID8,     0x80000ed3          | T8's live FX2 id (0x80000ecc + 7)
        .equ    METER_ID,   0x0e
        .equ    STOCK_ISR,  0x4000aad0
        .equ    SEG,        16500000            | 125 ms at 132 MHz
        .equ    REF,        8192

        .text
        .globl  m_isr, m_tail, m_iacc, m_istep

| Vector 0x41. The stock handler saves everything itself; d0/d1 are kept.
m_isr:
        move.l  %d0,-(%sp)
        move.l  %d1,-(%sp)
        move.l  DTCN3,%d0
        move.l  %d0,m_t0
        moveq   #0,%d1
        move.b  FX2ID8,%d1
        cmpi.l  #METER_ID,%d1
        bne.s   2f                              | T8's FX2 is not CF METER: no burn
        move.b  BURN,%d1
        beq.s   2f
        mulu.w  #264,%d1                        | 2 us per step
        add.l   %d0,%d1                         | deadline
1:      move.l  DTCN3,%d0
        sub.l   %d1,%d0
        bmi.s   1b
2:      move.l  (%sp)+,%d1
        move.l  (%sp)+,%d0
        jmp     STOCK_ISR

| The stock epilogue's place: d0-a6 are saved at (sp) and restored below,
| so every register is free here.
m_tail:
        move.l  DTCN3,%d2                       | d2 = now
        move.l  %d2,%d0
        sub.l   m_t0,%d0                        | this interrupt's duration
        add.l   %d0,m_isum
        addq.l  #1,m_icnt
        cmp.l   m_imax,%d0
        bls.s   1f
        move.l  %d0,m_imax
1:      move.l  %d2,%d1
        sub.l   m_seg0,%d1                      | d1 = segment so far
        cmp.l   #SEG,%d1
        bcs.s   2f
        move.l  %d2,m_seg0
        bsr.w   m_close
2:      moveq   #0,%d0
        move.b  FX2ID8,%d0
        cmpi.l  #METER_ID,%d0
        bne.s   3f                              | another effect's page 2: untouched
        lea     P2VAL,%a0
        move.w  m_out,(%a0)+
        move.w  #REF,(%a0)
3:
        movem.l (%sp),%d0-%d7/%a0-%a6           | displaced: moveml %sp@,%d0-%fp
        lea     252(%sp),%sp                    | displaced
        rte                                     | displaced

| d1 = segment length. Interrupts are masked (level 5).
m_close:
        lea     m_val,%a0
        move.l  m_imax,%d0
        lsr.l   #2,%d0
        bsr.w   m_clamp
        move.l  %d0,16(%a0)                     | 4: longest
        move.l  m_icnt,%d4
        clr.l   12(%a0)
        clr.l   20(%a0)
        tst.l   %d4
        beq.s   3f
        move.l  m_isum,%d0
        divu.l  %d4,%d0
        lsr.l   #2,%d0
        bsr.w   m_clamp
        move.l  %d0,12(%a0)                     | 3: mean
        move.l  %d1,%d0
        divu.l  %d4,%d0
        lsr.l   #2,%d0
        bsr.w   m_clamp
        move.l  %d0,20(%a0)                     | 5: period
3:      clr.l   m_isum
        clr.l   m_icnt
        clr.l   m_imax
        moveq   #14,%d0
        lsr.l   %d0,%d1                         | segment / 16384
        move.l  m_iacc,%d0
        clr.l   m_iacc
        divu.l  %d1,%d0                         | idle x 16384 / segment
        bsr.w   m_clamp
        move.l  %d0,8(%a0)                      | 2: idle
        move.l  m_istep,%d0
        bsr.w   m_clamp
        move.l  %d0,24(%a0)                     | 6: shortest step
        moveq   #0,%d0
        move.b  BURN,%d0
        mulu.w  #66,%d0                         | x 2 us = x 264 counts, / 4
        bsr.w   m_clamp
        move.l  %d0,28(%a0)                     | 7: BURN
        clr.l   (%a0)                           | 0: sync
        move.l  #REF,%d0
        move.l  %d0,4(%a0)                      | 1: reference
        move.l  m_k,%d3
        addq.l  #1,%d3
        moveq   #7,%d0
        and.l   %d0,%d3
        move.l  %d3,m_k
        move.l  (%a0,%d3.l*4),%d0
        move.w  %d0,m_out
        rts

m_clamp:
        cmp.l   #32767,%d0
        bls.s   1f
        move.l  #32767,%d0
1:      rts

        .balign 4
m_t0:   .long   0
m_seg0: .long   0
m_isum: .long   0
m_icnt: .long   0
m_imax: .long   0
m_iacc: .long   0
m_istep: .long  0
m_k:    .long   0
m_val:  .zero   32
m_out:  .word   0
        .balign 4
