| Generated control.s appends this adapter to the freestanding C engine.
| All stock scene/LFO writes have finished; publish into the outgoing frame.
        .text
        .balign 4
        .global eu_frame_hook, eu_start_hook, eu_resume_hook
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
        bsr.s   eu_reset_clock
        jmp     0x4009c3da

| The second PLAY path (resume) uses the same reset policy for the effect.
eu_resume_hook:
        move.l  %d0,0x800065b8
        bsr.s   eu_reset_clock
        jmp     0x4009c4da

| Preserve the CCR produced by the displaced PLAYING store. BSR, LEA and
| MOVEM do not alter it, so save it only after the call has pushed its return
| address; restore it after every instruction that can change the flags.
eu_reset_clock:
        lea     -28(%sp),%sp
        movem.l %d0-%d1/%a0-%a1,%sp@(12)
        move.w  %ccr,%d1
        move.w  %d1,%sp@(8)
        move.l  #eu_clock,(%sp)
        move.l  0x4610757c,%d0
        move.l  %d0,4(%sp)
        jsr     eu_clock_start
        move.w  %sp@(8),%d1
        move.w  %d1,%ccr
        movem.l %sp@(12),%d0-%d1/%a0-%a1
        lea     28(%sp),%sp
        rts

| Explicitly initialized, loader-owned DRAM, not uninitialized BSS. The
| C's static assertions check these sizes on both target and host compilers.
        .balign 4
        .global eu_clock, eu_states
eu_clock:
        .zero   20
eu_states:
        .zero   2624
