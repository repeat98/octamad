| Generated control.s appends this adapter to the freestanding C engine.
| All stock scene/LFO writes have finished; publish into the outgoing frame.
        .text
        .balign 4
        .global eu_frame_hook, eu_start_hook, eu_resume_hook, eu_dial_hook
eu_frame_hook:
        lea     -16(%sp),%sp
        movem.l %d0-%d1/%a0-%a1,(%sp)
        jsr     eu_publish_frame
        movem.l (%sp),%d0-%d1/%a0-%a1
        lea     16(%sp),%sp
        lea     0x800000f0,%a1     | displaced, next MOVE sets the flags
        jmp     0x4000d568

| A fresh PLAY resets all instances together at the same anchor the stock
| transport sets for its first tick.
eu_start_hook:
        move.l  %d0,0x800065b8     | displaced: PLAYING
        lea     -24(%sp),%sp
        movem.l %d0-%d1/%a0-%a1,%sp@(8)
        move.l  #eu_clock,(%sp)
        move.l  0x4610757c,%d0
        move.l  %d0,4(%sp)
        jsr     eu_clock_start
        movem.l %sp@(8),%d0-%d1/%a0-%a1
        lea     24(%sp),%sp
        jmp     0x4009c3da

| The second PLAY path (resume) uses the same reset policy for the effect.
eu_resume_hook:
        move.l  %d0,0x800065b8
        lea     -24(%sp),%sp
        movem.l %d0-%d1/%a0-%a1,%sp@(8)
        move.l  #eu_clock,(%sp)
        move.l  0x4610757c,%d0
        move.l  %d0,4(%sp)
        jsr     eu_clock_start
        movem.l %sp@(8),%d0-%d1/%a0-%a1
        lea     24(%sp),%sp
        jmp     0x4009c4da

| The plain dial always indexes its 128-position arc with the raw value.
| At this point its numeric label has already been formatted. Match only
| Euclid's formatter pointers, then scale the DRAWING value, leaving all
| parameter storage, encoder increments and displayed numbers unchanged.
eu_dial_hook:
        lea     -16(%sp),%sp
        movem.l %d0-%d1/%a0-%a1,(%sp)
        move.l  0x400d6050,%a0    | FX2 descriptor table[EU_ID]
        moveq   #63,%d1
        cmpa.l  0xda(%a0),%a2    | STEPS A formatter, slot 4
        beq.s   eu_arc_scale
        cmpa.l  0xe2(%a0),%a2    | ROT A formatter, slot 6
        beq.s   eu_arc_scale
        moveq   #64,%d1
        cmpa.l  0xde(%a0),%a2    | PULSE A formatter, slot 5
        bne.s   eu_arc_done
eu_arc_scale:
        move.l  %d2,%d0
        cmp.l   %d1,%d0
        bls.s   eu_arc_bound
        move.l  %d1,%d0
eu_arc_bound:
        move.l  %d1,%a1
        moveq   #127,%d1
        mulu.l  %d1,%d0
        move.l  %a1,%d1
        lsr.l   #1,%d1
        add.l   %d1,%d0
        move.l  %a1,%d1
        divu.l  %d1,%d0
        move.l  %d0,%d2
eu_arc_done:
        movem.l (%sp),%d0-%d1/%a0-%a1
        lea     16(%sp),%sp
        moveq   #2,%d6           | displaced widget-flags branch
        and.l   %d5,%d6
        beq.s   eu_arc_normal
        jmp     0x40047a42
eu_arc_normal:
        jmp     0x40047a8a

| Explicitly initialized, loader-owned DRAM, not uninitialized BSS. The
| C's static assertions check these sizes on both target and host compilers.
        .balign 4
        .global eu_clock, eu_states
eu_clock:
        .zero   20
eu_states:
        .zero   2624
