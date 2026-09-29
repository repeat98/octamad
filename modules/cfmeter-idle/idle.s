| CF METER IDLE -- main's idle loop, timed.
|
| Replaces main's last init call (0x4001fc96) and the `bras .` after it:
| makes the call, then spins reading DMA timer 3. A step shorter than twice
| the shortest step seen, + 8 counts, is idle time and is added to CF
| METER's m_iacc; a longer one was taken by an interrupt or a task. The
| shortest step goes to m_istep.
|
| The ColdFire port reads the `jmp` this detour leaves at 0x4001fc96 and
| counts PCs in the loop as main's park (rtos.cpp, Rtos::atSpin, since 28
| Sep 2026); a borrowed call returns to the stock `bras .` behind it and
| main parks there, so the accounting stops at the first --call.

        .equ    DTCN3,      0xfc07c00c

        .text
        .globl  m_idle

m_idle:
        jsr     0x40098a2c                      | displaced: main's last init call
        lea     m_iacc,%a2
        move.l  DTCN3,%d2                       | d2 = previous reading
        move.l  #0x7fffffff,%d5                 | d5 = shortest step
        move.l  %d5,%d6                         | d6 = idle threshold
1:      move.l  DTCN3,%d0
        move.l  %d0,%d1
        sub.l   %d2,%d1                         | step
        move.l  %d0,%d2
        cmp.l   %d5,%d1
        bcc.s   2f
        move.l  %d1,%d5                         | new shortest step
        move.l  %d5,m_istep
        move.l  %d5,%d6
        add.l   %d6,%d6
        addq.l  #8,%d6                          | threshold = 2 x shortest + 8
2:      cmp.l   %d6,%d1
        bcc.s   1b
        add.l   %d1,(%a2)                       | idle (one instruction: the
        bra.s   1b                              | interrupt's clear cannot split it)
