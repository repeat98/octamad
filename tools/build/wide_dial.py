"""Generate the shared ColdFire hook for labelled controls wider than 5 values."""


SITE = 0x40047A3C
STOCK = bytes.fromhex("7c02cc856748")


def source(rows):
    """Return assembler for ``(formatter_address, maximum)`` rows."""
    table = "\n".join(f"        .long   0x{address:08x}, {maximum}"
                      for address, maximum in rows)
    return f"""        .text
        .balign 4
        .global wide_dial_hook
wide_dial_hook:
        lea     -16(%sp),%sp
        movem.l %d0-%d1/%a0-%a1,(%sp)
        lea     wide_dial_table(%pc),%a0
wide_dial_next:
        move.l  (%a0)+,%a1
        tst.l   %a1
        beq.s   wide_dial_done
        cmpa.l  %a2,%a1
        beq.s   wide_dial_scale
        addq.l  #4,%a0
        bra.s   wide_dial_next
wide_dial_scale:
        move.l  (%a0),%d1
        move.l  %d2,%d0
        cmp.l   %d1,%d0
        bls.s   wide_dial_bound
        move.l  %d1,%d0
wide_dial_bound:
        move.l  %d1,%a1
        moveq   #127,%d1
        mulu.l  %d1,%d0
        move.l  %a1,%d1
        lsr.l   #1,%d1
        add.l   %d1,%d0
        move.l  %a1,%d1
        divu.l  %d1,%d0
        move.l  %d0,%d2
wide_dial_done:
        movem.l (%sp),%d0-%d1/%a0-%a1
        lea     16(%sp),%sp
        moveq   #2,%d6
        and.l   %d5,%d6
        beq.s   wide_dial_normal
        jmp     0x40047a42
wide_dial_normal:
        jmp     0x40047a8a
        .balign 4
wide_dial_table:
{table}
        .long   0, 0
"""
