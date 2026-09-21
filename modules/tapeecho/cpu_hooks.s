| Enter after the stock DMA read wait and next-track prefetch, before its
| filter/mix. sp is still the stock routine's 148-byte frame. Stock's own
| EMAC save/restore and ring DMA commit surround this adapter.
        .text
        .balign 4
        .global te_cpu_hook, te_cpu_reset, te_states
te_cpu_reset:
        lea     -12(%sp),%sp
        movem.l %d0-%d1/%a0,(%sp)
        lea     te_states,%a0
        move.l  #399,%d1
        moveq   #0,%d0
te_clear_loop:
        move.l  %d0,(%a0)+
        subq.l  #1,%d1
        bpl.s   te_clear_loop
        movem.l (%sp),%d0-%d1/%a0
        lea     12(%sp),%sp
        lea     -16(%sp),%sp
        movem.l %d2-%d5,(%sp)
        jmp     0x40002f4c
te_cpu_hook:
        lea     -20(%sp),%sp
        movem.l %d0-%d1/%a0-%a1,4(%sp)
        lea     20(%sp),%a0
        move.l  %a0,(%sp)
        jsr     te_cpu_frame
        tst.l   %d0
        beq.s   te_stock_path
        movem.l 4(%sp),%d0-%d1/%a0-%a1
        lea     20(%sp),%sp
        jmp     0x4000377a
te_stock_path:
        movem.l 4(%sp),%d0-%d1/%a0-%a1
        lea     20(%sp),%sp
        move.l  92(%sp),%a5
        move.l  0x800000e8,%d0
        jmp     0x40003624
        .balign 4
te_states:
        .zero   1600
