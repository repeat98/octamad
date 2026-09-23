        .section .runtime,"ax"
        .space 0x430
        .global gk_copy_payload_interruptible
        .type   gk_copy_payload_interruptible,@function
gk_copy_payload_interruptible:
        move.l  #1580,%d0
        .global gk_copy_payload_long_loop
gk_copy_payload_long_loop:
        move.l  (%a0)+,(%a1)+
        subq.l  #1,%d0
        bne.s   gk_copy_payload_long_loop
        .global gk_copy_payload_tail
gk_copy_payload_tail:
        move.w  (%a0)+,(%a1)+
        rts
        .size   gk_copy_payload_interruptible,.-gk_copy_payload_interruptible
