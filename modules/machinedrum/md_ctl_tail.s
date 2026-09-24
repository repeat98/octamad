| Appended to the generated md_ctl.s (generate_ctl.py).
|
| The PLAY hooks. Both stock PLAY paths store PLAYING (0x800065b8) and then
| anchor the sequencer's step clock (0x4610757c); the lanes restart there,
| on the same anchor as the OT tracks. Euclid (modules/euclid/hooks.s) takes
| the same two sites for its own clock, so the two modules do not share a
| remix. The displaced store sets the condition codes the stock code after
| it tests: keep them across the call.
        .text
        .balign 4
        .global md_start_hook, md_resume_hook
md_start_hook:
        move.l  %d0,0x800065b8     | displaced: PLAYING
        bsr.s   md_reset_clock
        jmp     0x4009c3da

md_resume_hook:
        move.l  %d0,0x800065b8
        bsr.s   md_reset_clock
        jmp     0x4009c4da

md_reset_clock:
        lea     -28(%sp),%sp
        movem.l %d0-%d1/%a0-%a1,%sp@(12)
        move.w  %ccr,%d1
        move.w  %d1,%sp@(8)
        move.l  #md_clock,(%sp)
        move.l  0x4610757c,%d0
        move.l  %d0,4(%sp)
        jsr     md_clock_start
        move.w  %sp@(8),%d1
        move.w  %d1,%ccr
        movem.l %sp@(12),%d0-%d1/%a0-%a1
        lea     28(%sp),%sp
        rts

| The platform runtime is an objcopy'd image with no .bss, so the control
| engine's mutable state is explicit zeroed storage here. md_ctl.c's static
| assertions pin the sizes against md_ctl.h.
        .data
        .balign 4
        .global md_kit, md_run, md_trig_request, md_kit_active
        .global md_clock, md_lanes, md_patterns, md_parent_track
md_kit:
        .zero   192
md_run:
        .zero   2476
md_clock:
        .zero   20
md_lanes:
        .zero   212
md_trig_request:
        .long   0
md_kit_active:
        .long   0
md_parent_track:
        .long   0
md_patterns:                       | 256 x 384: one MD pattern per OT pattern
        .zero   98304
        .text
