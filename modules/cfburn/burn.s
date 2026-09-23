| CF BURN: a knob-set, register-only spin at the end of the stock
| eight-track delay routine. Entered from 0x40003826 (displaced:
| `lea 116(%sp),%a2` / `moveq #3,%d1`), after the track loop and before the
| routine's epilogue. That epilogue reloads d0-d5/a0-a1 from sp+116 and
| d2-d7/a2-fp from sp+0, so every register is dead here and the routine
| returns exactly what stock returns. Nothing below writes memory or EMAC.
|
| The knobs are this frame's staged FX2 page-1 controls, read the way the
| routine reads them (COLDFIRE_DELAY.md 2): snapshot s = [0x80004804]
| (advanced only after this site), FX2 id = byte 0x80001b87 + 64*s + 8*t,
| controls = halfwords at 0x80001a00 + 96*s + 12*t, each knob its high byte.
        .text
        .balign 2
        .global cfburn_hook
        .equ    CFBURN_ID, 0x1f         | manifest.py ID
cfburn_hook:
        move.l  0x80004804,%d0          | this frame's control snapshot
        move.l  %d0,%d1
        lsl.l   #6,%d1                  | 64 * s
        movea.l %d1,%a0
        adda.l  #0x80001b87,%a0         | track 1's FX2 id
        move.l  %d0,%d1
        lsl.l   #5,%d1                  | 32 * s
        move.l  %d1,%d2
        add.l   %d1,%d1
        add.l   %d2,%d1                 | 96 * s
        movea.l %d1,%a1
        adda.l  #0x80001a00,%a1         | track 1's page-1 controls
        moveq   #0,%d2                  | iterations
        moveq   #8,%d3                  | tracks
        moveq   #CFBURN_ID,%d4
1:      mvz.b   (%a0),%d0
        cmp.l   %d4,%d0
        bne.s   2f
        mvz.b   (%a1),%d0               | BURN: slot 0's high byte
        lsl.l   #6,%d0                  | 64 iterations per step
        add.l   %d0,%d2
        mvz.b   2(%a1),%d0              | FINE: slot 1's high byte
        add.l   %d0,%d2
2:      addq.l  #8,%a0
        lea     12(%a1),%a1
        subq.l  #1,%d3
        bne.s   1b
        tst.l   %d2
        beq.s   4f                      | zero: no spin (a zero count would wrap)
3:      .rept   2
        add.l   %d1,%d3
        add.l   %d1,%d4
        add.l   %d1,%d5
        add.l   %d1,%d6
        .endr
        subq.l  #1,%d2
        bne.s   3b
4:      lea     116(%sp),%a2            | the displaced pair, replayed
        moveq   #3,%d1
        jmp     0x4000382c
