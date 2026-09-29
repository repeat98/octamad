        .text
        .global dl_boundary_a,dl_boundary_b
| Both seams precede the sequencer's current-bank/current-pattern writes.
| The callback restores a rejected next pair to the current pair; replay the
| original stock instructions so timing/loop housekeeping still runs.
dl_boundary_a:
        lea -60(%sp),%sp
        movem.l %d0-%d7/%a0-%a6,(%sp)
        jsr dl_pattern_boundary
        movem.l (%sp),%d0-%d7/%a0-%a6
        lea 60(%sp),%sp
        lea 0x800065be,%a0
        jmp 0x400a4074
dl_boundary_b:
        lea -60(%sp),%sp
        movem.l %d0-%d7/%a0-%a6,(%sp)
        jsr dl_pattern_boundary
        movem.l (%sp),%d0-%d7/%a0-%a6
        lea 60(%sp),%sp
        lea 0x800065be,%a0
        jmp 0x400a44a6

        .global dl_project_post,dl_project_post_body,dl_project_engine,dl_project_end
dl_project_post:
        move.l 4(%sp),-(%sp)
        jsr dl_project_guard
        addq.l #4,%sp
        rts
dl_project_post_body:
        move.l %d2,-(%sp)
        move.l 8(%sp),%d2
        jmp 0x40023c82
| Refusal uses the stock command-completion tail, before load side effects.
dl_project_engine:
        lea -60(%sp),%sp
        movem.l %d0-%d7/%a0-%a6,(%sp)
        move.l %a2,-(%sp)
        jsr dl_project_engine_guard
        addq.l #4,%sp
        tst.l %d0
        beq dl_project_rejected
        movem.l (%sp),%d0-%d7/%a0-%a6
        lea 60(%sp),%sp
        move.l %a2,-566(%a6)
        move.l 264(%a2),-(%sp)
        jmp 0x4008533e
dl_project_rejected:
        movem.l (%sp),%d0-%d7/%a0-%a6
        lea 60(%sp),%sp
        moveq #-1,%d0
        move.l %d0,-(%sp)
        move.l %a2,%a0
        jmp 0x400850f4
dl_project_end:
        lea -60(%sp),%sp
        movem.l %d0-%d7/%a0-%a6,(%sp)
        move.l %d2,-(%sp)
        jsr dl_project_finished
        addq.l #4,%sp
        movem.l (%sp),%d0-%d7/%a0-%a6
        lea 60(%sp),%sp
        move.l %d2,-(%sp)
        move.l -566(%a6),%a0
        jmp 0x40085414

        .global dl_pattern_post,dl_pattern_post_body
dl_pattern_post:
        lea 4(%sp),%a0
        move.l %a0,-(%sp)
        jsr dl_pattern_request_guard
        addq.l #4,%sp
        tst.l %d0
        bne dl_pattern_post_body
        rts
dl_pattern_post_body:
        lea -20(%sp),%sp
        movem.l %d2-%d6,(%sp)
        jmp 0x400a0578
