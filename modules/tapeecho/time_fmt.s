| TIME uses twelve quantized bands in BEAT, milliseconds in FREE.
| Read the selected track/Part's stored SYNC, not another instance's state.
| Position-independent; only caller-saved registers; fmt(buf, value).
        .text
        moveq   #0,%d0
        move.b  0x80000003,%d0
        and.l   #3,%d0
        move.l  #6322,%d1
        mulu.l  %d1,%d0
        movea.l 0x46c82456,%a0
        move.l  %a0,%d1
        beq.s   free
        adda.l  %d0,%a0
        moveq   #0,%d0
        move.b  0x80000000,%d0
        and.l   #7,%d0
        moveq   #24,%d1
        mulu.l  %d1,%d0
        adda.l  %d0,%a0
        adda.l  #0x8eeb0,%a0
        tst.b   (%a0)
        beq.s   free
        move.l  8(%sp),%d0
        and.l   #127,%d0
        moveq   #12,%d1
        mulu.l  %d1,%d0
        lsr.l   #7,%d0
        lea     offsets(%pc),%a0
        moveq   #0,%d1
        move.b  (%a0,%d0.l),%d1
        adda.l  %d1,%a0
        move.l  %a0,8(%sp)
        jmp     0x40013a08
free:
        move.l  8(%sp),%d0
        and.l   #127,%d0
        lsl.l   #6,%d0
        add.l   #2048,%d0
        moveq   #10,%d1
        mulu.l  %d1,%d0
        move.l  #441,%d1
        divu.l  %d1,%d0
        move.l  %d0,8(%sp)
        move.l  %d0,-(%sp)
        pea     ms(%pc)
        move.l  12(%sp),-(%sp)
        jsr     0x40013a08
        lea     12(%sp),%sp
        rts
offsets:
        .byte n0-offsets,n1-offsets,n2-offsets,n3-offsets
        .byte n4-offsets,n5-offsets,n6-offsets,n7-offsets
        .byte n8-offsets,n9-offsets,n10-offsets,n11-offsets
n0:     .asciz "1/64"
n1:     .asciz "1/32T"
n2:     .asciz "1/32"
n3:     .asciz "1/16T"
n4:     .asciz "1/16"
n5:     .asciz "1/8T"
n6:     .asciz "1/16."
n7:     .asciz "1/8"
n8:     .asciz "1/4T"
n9:     .asciz "1/8."
n10:    .asciz "1/4"
n11:    .asciz "1/4."
ms:     .asciz "%d"
        .balign 2
