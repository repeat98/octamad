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

        .global dl_chain_stop
| STOP on a playing chain (0x400a11ba, the chain branch) stores chain[0] as
| the running pattern before requesting it. Admit the restart first. Refused
| or deferred: stop on the current pattern through stock's own publish tail
| (0x400a1274, which leaves d3 = 0 exactly as the chain branch does).
dl_chain_stop:
        lea -60(%sp),%sp
        movem.l %d0-%d7/%a0-%a6,(%sp)
        jsr dl_chain_stop_guard
        tst.l %d0
        beq dl_chain_stop_held
        movem.l (%sp),%d0-%d7/%a0-%a6
        lea 60(%sp),%sp
        clr.l 0x8000654a
        jmp 0x400a11c0
dl_chain_stop_held:
        movem.l (%sp),%d0-%d7/%a0-%a6
        lea 60(%sp),%sp
        jmp 0x400a1274

        .global dl_paste_guard,dl_reload_guard,dl_reset_guard
| PASTE (0x40029a4c), RELOAD (0x4004aab4) and RESET (0x4004a9d0) rewrite a
| Part and apply it when it is the active one. The guard answers 1 = run the
| stock routine now, 2 = deferred (the UI task replays it once prepared),
| 0 = refused. A deferred RELOAD reports success, as the replay performs it.
dl_paste_guard:
        move.l 4(%sp),-(%sp)            | source
        move.l 12(%sp),-(%sp)           | Part
        pea 3
        jsr dl_selection_part_edit_guard
        lea 12(%sp),%sp
        cmpi.l #1,%d0
        bne dl_edit_return
        move.l 8(%sp),-(%sp)
        move.l 8(%sp),-(%sp)
        jsr dl_paste_body
        addq.l #8,%sp
        jsr dl_selection_applied
        rts
dl_paste_body:
        lea -20(%sp),%sp
        movem.l %d2-%d5/%a2,(%sp)
        jmp 0x40029a54
dl_reload_guard:
        pea 0
        move.l 8(%sp),-(%sp)            | Part
        pea 4
        jsr dl_selection_part_edit_guard
        lea 12(%sp),%sp
        cmpi.l #1,%d0
        bne dl_edit_return
        move.l 4(%sp),-(%sp)
        jsr dl_reload_body
        addq.l #4,%sp
        move.l %d0,-(%sp)
        jsr dl_selection_applied
        move.l (%sp)+,%d0
        rts
dl_reload_body:
        lea -32(%sp),%sp
        movem.l %d2-%d5/%a2-%a3,(%sp)
        jmp 0x4004aabc
dl_reset_guard:
        pea 0
        move.l 8(%sp),-(%sp)            | Part
        pea 5
        jsr dl_selection_part_edit_guard
        lea 12(%sp),%sp
        cmpi.l #1,%d0
        bne dl_edit_return
        move.l 4(%sp),-(%sp)
        jsr dl_reset_body
        addq.l #4,%sp
        jsr dl_selection_applied
        rts
dl_reset_body:
        lea -16(%sp),%sp
        movem.l %d2-%d3/%a2-%a3,(%sp)
        jmp 0x4004a9d8
dl_edit_return:
        tst.l %d0
        beq dl_edit_refused
        moveq #1,%d0
dl_edit_refused:
        rts
