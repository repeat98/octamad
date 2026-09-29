| CC FEEDBACK -- the OT transmits a CC for every live knob byte that changed,
| whatever changed it: a pattern or part change, a project load, MODE
| DEFAULTS, a CC in, a page-2 knob turn. A controller with LED-ring or
| motorised encoders (a BCR2000) follows the unit. Stock transmits panel
| turns of page-1 knobs only (0x400552f0: current track, CC 10 + 6*page +
| slot) and nothing on a state change.
|
| Mechanism (0x40033e3c, disassembled): the stock emitter
| EMIT(track, cc, value) keeps the last value it queued per channel
| (CACHE + channel*128 + cc), sets the CC's bit in a per-channel dirty
| bitmap (0x46c7d7d8 + channel*16), the channel's bit in 0x46c7e0de, and
| forces interrupt source 34 (INTFRCH bit 2, the soft-timer dispatcher
| 0x400409f4) when 0x46c7ca34 is 0; the dispatcher drains the bitmap to
| UART0. It returns without queueing unless AUDIO CC OUT (CCOUT) bit 1 is
| set, the track's trig channel (TRIGCH + track) is >= 0, and no MIDI
| track uses that channel. Repeats coalesce in the bitmap.
|
| One track per UI tick (the keyrepeat task's loop 0x4005595c, one pass per
| DTIM1 tick: 120 Hz, handler 0x40055cb8 signals EVENT), the track's live
| lane LIVEB + track*72 is compared with the channel's cache: page 1 (bytes
| 0..29 -> CC 16..45), FX1 page 2 (+0x32..0x37 -> CC 68..73) and FX2 page 2
| (+0x38..0x3d -> CC 62..67), CC MAP's numbering. A byte that differs is
| queued through EMIT, which updates the cache itself; stock's own knob
| echo goes through the same cache, so a panel turn is sent once. A track
| whose channel is off is skipped here; one that shares a channel with a
| MIDI track is refused by EMIT on every call (42 refused calls per sweep).
|
| The sweep waits while the engine task runs a command (a project load, a
| bank or part change): ENGQ+0xc is the TCB the kernel's event wait
| (0x40000818) parks there while the engine is blocked on its queue, and
| the post (0x40000c3c) clears it. Stock transmits nothing during a load;
| under the port, 272 UART interrupts inside LOAD PROJECT re-ordered sys
| against the engine and tripped Octakit's part-byte lifecycle check
| (docs/remixer/EMU.md, the ATA-latency note) -- measured 28 Sep 2026.
        .set    CCOUT,   0x8000004a    | AUDIO CC OUT: bit 0 INT, bit 1 EXT (0x40033e52)
        .set    TRIGCH,  0x8000003f    | +track: trig channel, -1 = off
        .set    LIVEB,   0x80000810    | +track*72: the live knob block
        .set    CACHE,   0x46c7bf2c    | +channel*128 + cc: last value queued (0x40033ee6)
        .set    EMIT,    0x40033e3c    | (track, cc, value) on the stack
        .set    EVENT,   0x46c7e0e2    | the UI tick event the loop pends on
        .set    RESUME,  0x40055962    | the instruction after the displaced pea
        .set    ENGQ,    0x460d17ce    | the engine's command queue: +4 count, +8 event flag, +0xc waiting TCB

        .text
        .globl  cf_tick, cf_sweep, cf_track, cf_map

| jmp detour at 0x4005595c: replays the displaced `pea EVENT`. a2/a3 are
| the loop's function pointers; the sweep preserves them.
cf_tick:
        bsr.w   cf_sweep
        pea     EVENT
        jmp     RESUME

| cf_sweep(): track cf_track (advanced each call), the 42 mapped CCs.
| Preserves every register but d0/d1/a0/a1.
cf_sweep:
        lea     %sp@(-28),%sp
        movem.l %d2-%d5/%a2-%a4,%sp@
        moveq   #0,%d0
        move.b  CCOUT,%d0
        btst    #1,%d0
        beq.s   9f                      | EXT off: EMIT would refuse every call
        tst.l   ENGQ+12
        beq.s   9f                      | the engine is running a command: wait
        moveq   #0,%d2
        move.b  cf_track,%d2            | d2 = track
        move.l  %d2,%d0
        addq.l  #1,%d0
        moveq   #7,%d1
        and.l   %d1,%d0
        move.b  %d0,cf_track            | the next call takes the next track
        lea     TRIGCH,%a0
        move.b  %a0@(0,%d2:l),%d3
        extb.l  %d3                     | d3 = channel
        blt.s   9f                      | off
        move.l  %d2,%d0
        moveq   #72,%d1
        mulu.l  %d1,%d0
        lea     LIVEB,%a2
        adda.l  %d0,%a2                 | a2 = the track's live block
        move.l  %d3,%d0
        lsl.l   #7,%d0
        lea     CACHE,%a3
        adda.l  %d0,%a3                 | a3 = the channel's cache
        lea     cf_map,%a4
1:      moveq   #0,%d4
        move.b  %a4@+,%d4               | lane offset
        moveq   #0,%d5
        move.b  %a4@+,%d5               | CC number; 0 ends the table
        beq.s   9f
        moveq   #0,%d0
        move.b  %a2@(0,%d4:l),%d0       | the live value
        moveq   #0,%d1
        move.b  %a3@(0,%d5:l),%d1       | the last value queued for this CC
        cmp.l   %d0,%d1
        beq.s   1b
        move.l  %d0,%sp@-               | value
        move.l  %d5,%sp@-               | cc
        move.l  %d2,%sp@-               | track
        jsr     EMIT
        lea     %sp@(12),%sp
        bra.s   1b
9:      movem.l %sp@,%d2-%d5/%a2-%a4
        lea     %sp@(28),%sp
        rts

cf_track:
        .byte   0                       | the track the next sweep takes
        .balign 2
| (lane offset, CC) pairs, 0 ends. Page 1 flat 0..29 -> CC 16..45 (PLAYBACK
| 16-21, AMP 22-27, LFO 28-33, FX1 34-39, FX2 40-45); FX1 page 2 lane +0x32
| -> CC 68..73; FX2 page 2 lane +0x38 -> CC 62..67 (modules/cc-map).
cf_map:
        .byte   0x00,16, 0x01,17, 0x02,18, 0x03,19, 0x04,20, 0x05,21
        .byte   0x06,22, 0x07,23, 0x08,24, 0x09,25, 0x0a,26, 0x0b,27
        .byte   0x0c,28, 0x0d,29, 0x0e,30, 0x0f,31, 0x10,32, 0x11,33
        .byte   0x12,34, 0x13,35, 0x14,36, 0x15,37, 0x16,38, 0x17,39
        .byte   0x18,40, 0x19,41, 0x1a,42, 0x1b,43, 0x1c,44, 0x1d,45
        .byte   0x32,68, 0x33,69, 0x34,70, 0x35,71, 0x36,72, 0x37,73
        .byte   0x38,62, 0x39,63, 0x3a,64, 0x3b,65, 0x3c,66, 0x3d,67
        .byte   0,0
