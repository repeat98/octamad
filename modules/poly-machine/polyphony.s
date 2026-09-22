| POLY MACHINE -- four independent untimestretched playback positions per
| audio track.  The stock voice is always the newest voice.  Immediately
| before stock retriggers it, the active old state is copied into one of
| three rotating extension records.  The stock renderer then renders the
| primary and extension records into one track buffer, before the normal
| per-track FX chain.
|
| Pitch, RATE, sample selection and p-locks remain track-wide in this first
| hardware prototype.  In particular, stock MIDI chromatic play still writes
| one shared PTCH lock.  Independent MIDI pitch needs independent resampling;
| cloning only the 168-byte renderer state is not sufficient.
        .text
        .global polyphony_call
        .global poly_config_type
        .global poly_live_type
        .global poly_stop_voice
        .global poly_voice_trigger
        .global poly_machine_name
        .global voice_pointer
        .global poly_voice_selector
        .global poly_extra_voices
        .global poly_scratch
        .global poly_next

        .equ    VOICES, 0x800049d8
        .equ    STATES, 0x80004898
        .equ    LANES,  0x80000510
        .equ    BANK_PTR, 0x46c82456
        .equ    PART_INDEX, 0x100b14cf
        .equ    PART_STRIDE, 6322
        .equ    PART_MACHINE_OFF, 0x8eda2
        .equ    POLY_TYPE, 5
        .equ    RENDER, 0x40007960
        .equ    CONTINUE_CALLER, 0x400041cc
        .equ    CONTINUE_CONFIG_TYPE, 0x4000c0de
        .equ    CONTINUE_STOP, 0x40006828
        .equ    CONTINUE_POINTER, 0x4000798a
        .equ    CONTINUE_TRIGGER, 0x4000f458
        .equ    CONTINUE_LIVE_TYPE, 0x4000bff0
        .equ    CONTINUE_NAME, 0x400334de
        .equ    VOICE_SIZE, 168
        .equ    EXTRA_PER_TRACK, 3
        .equ    EXTRA_TRACK_SIZE, 504
        .equ    STATE_SIZE, 40
        .equ    MAX_SOURCE_FRAMES, 64

| d0 = track -> d0 = 1 when the current Part stores raw machine type 5.
| d1/a0 are scratch; all other registers are preserved.
poly_is_track:
        cmpi.l  #7,%d0
        bhi.s   .pit_no
        move.l  %d0,%d1
        movea.l (BANK_PTR).l,%a0
        moveq   #0,%d0
        move.b  (PART_INDEX).l,%d0
        move.l  %d2,-(%sp)
        move.l  #PART_STRIDE,%d2
        mulu.l  %d2,%d0
        move.l  (%sp)+,%d2
        adda.l  %d0,%a0
        adda.l  %d1,%a0
        adda.l  #PART_MACHINE_OFF,%a0
        moveq   #POLY_TYPE,%d0
        cmp.b   (%a0),%d0
        seq     %d0
        andi.l  #1,%d0
        rts
.pit_no:
        moveq   #0,%d0
        rts

| Detour at 0x4000bfe8, immediately after stock publishes the stored machine
| byte to its per-ping operational mirror.  Preserve raw type 5 in the Part
| for UI/persistence, but expose FLEX (1) to the stock builder and common
| voice initializer.  Those paths otherwise reject type 5 and clear playback.
poly_live_type:
        .word   0x7332,0x2800             | displaced mvs.b (a2,d2.l),d1
        cmpi.l  #POLY_TYPE,%d1
        bne.s   .plt_done
        moveq   #1,%d1
        move.b  %d1,(%a2,%d2.l)
.plt_done:
        moveq   #7,%d0                    | displaced instruction
        and.l   %d1,%d0                   | stock builder-table index mask
        jmp     (CONTINUE_LIVE_TYPE).l

| The Part retains raw type 5, but this routine walks machine-specific
| configuration arrays (sample-slot assignment, SRC setup, and attributes).
| Normalize its local machine index to FLEX so POLY consumes the same layout.
| Without this, type 5 indexes past the five stock rows and turns track N into
| sample slot N+1 after a project load.
poly_config_type:
        .word   0x7130,0x0800             | displaced mvs.b (a0,d0.l),d0
        cmpi.l  #POLY_TYPE,%d0
        bne.s   .pct_done
        moveq   #1,%d0
.pct_done:
        movea.l %d0,%a5                   | displaced instructions
        add.l   %d0,%d0
        jmp     (CONTINUE_CONFIG_TYPE).l

| Stock's stop helper addresses only the primary voice by track. During an
| extension render, redirect that operation to the selected extension and do
| not clear the track's shared increment state. Selector zero is exactly stock.
poly_stop_voice:
        move.l  poly_voice_selector(%pc),%d0
        beq.s   .psv_stock
        move.l  4(%sp),%d1
        cmpi.l  #7,%d1
        bhi.s   .psv_stock
        subq.l  #1,%d0
        move.l  %d1,%a0
        add.l   %d1,%d1
        add.l   %a0,%d1                   | track * 3
        add.l   %d0,%d1                   | plus extension slot
        move.l  #VOICE_SIZE,%d0
        mulu.l  %d0,%d1
        lea     poly_extra_voices(%pc),%a0
        clr.b   (%a0,%d1.l)
        rts
.psv_stock:
        move.l  %a2,-(%sp)                | displaced prologue
        move.l  %d2,-(%sp)
        move.l  12(%sp),%d1
        jmp     (CONTINUE_STOP).l

| Detour at 0x4000f450, the shared sample-machine voice initializer.  Its
| first argument is the track at 4(sp).  Preserve the active primary before
| stock overwrites it, rotating through the three extension records.  This
| catches sequencer, manual and MIDI triggers at the common boundary.
poly_voice_trigger:
        lea     -24(%sp),%sp
        movem.l %d0-%d2/%a0-%a2,(%sp)
        move.l  28(%sp),%d2
        move.l  %d2,%d0
        bsr.w   poly_is_track
        tst.l   %d0
        beq.w   .pvt_done

        move.l  %d2,%d0
        move.l  #VOICE_SIZE,%d1
        mulu.l  %d1,%d0
        lea     (VOICES).l,%a0
        adda.l  %d0,%a0
        tst.b   (%a0)
        beq.w   .pvt_done

        lea     poly_next(%pc),%a1
        moveq   #0,%d0
        move.b  (%a1,%d2.l),%d0          | extension slot 0..2
        move.l  %d2,%d1
        add.l   %d2,%d1
        add.l   %d2,%d1
        add.l   %d0,%d1                  | flat extension index

        addq.l  #1,%d0
        cmpi.l  #EXTRA_PER_TRACK,%d0
        bcs.s   .pvt_store_next
        moveq   #0,%d0
.pvt_store_next:
        move.b  %d0,(%a1,%d2.l)

| Retain the old track increment as evidence/state for the next pitch stage.
| The first hardware prototype still renders all voices through the track's
| shared resampler and therefore does not consume this array yet.
        move.l  %d2,%d0
        lsl.l   #2,%d0
        add.l   %d2,%d0
        lsl.l   #3,%d0                  | track * 40
        lea     (STATES).l,%a2
        move.l  36(%a2,%d0.l),%d0
        lea     poly_extra_increment(%pc),%a2
        move.l  %d0,(%a2,%d1.l*4)

        move.l  %d1,%d0
        move.l  #VOICE_SIZE,%d2
        mulu.l  %d2,%d0
        lea     poly_extra_voices(%pc),%a1
        adda.l  %d0,%a1
        moveq   #41,%d0                   | 42 longs = 168 bytes
.pvt_copy:
        move.l  (%a0)+,(%a1)+
        subq.l  #1,%d0
        bpl.s   .pvt_copy

.pvt_done:
        movem.l (%sp),%d0-%d2/%a0-%a2
        lea     24(%sp),%sp
        lea     -60(%sp),%sp              | displaced initializer prologue
        movem.l %d2-%d7/%a2-%fp,(%sp)
        jmp     (CONTINUE_TRIGGER).l

| Detour at 0x400041c4.  The stock caller has already pushed six arguments:
| output, renderer arg2, track, source frames, output samples, and flags.
| There is no JSR return address because the detour jumps here.  The wrapper
| replays the displaced call cleanup itself.
polyphony_call:
        lea     -40(%sp),%sp
        movem.l %d2-%d7/%a2-%a5,(%sp)
        movea.l %sp,%a5                   | fixed frame; original args at +40
        move.l  48(%a5),%d2               | track
        cmpi.l  #7,%d2
        bhi.w   .mono
        move.l  %d2,%d0
        bsr.w   poly_is_track
        tst.l   %d0
        beq.w   .reset_mono

        move.l  %d2,%d0
        moveq   #48,%d1
        mulu.l  %d1,%d0
        lea     (LANES).l,%a0
        tst.b   28(%a0,%d0.l)             | POLY is TSTR OFF only
        bne.w   .reset_mono
        move.l  52(%a5),%d5               | rendered source frames, stereo
        beq.w   .mono
        cmpi.l  #MAX_SOURCE_FRAMES,%d5
        bhi.w   .reset_mono

        move.l  %d2,%d0
        move.l  #VOICE_SIZE,%d1
        mulu.l  %d1,%d0
        lea     (VOICES).l,%a3
        adda.l  %d0,%a3                   | stock primary voice
        move.l  %d2,%d0
        move.l  #EXTRA_TRACK_SIZE,%d1
        mulu.l  %d1,%d0
        lea     poly_extra_voices(%pc),%a2
        adda.l  %d0,%a2                   | first extension for this track

        moveq   #0,%d4                    | active count before this chunk
        tst.b   (%a3)
        beq.s   .count_e0
        addq.l  #1,%d4
.count_e0:
        tst.b   (%a2)
        beq.s   .count_e1
        addq.l  #1,%d4
.count_e1:
        tst.b   VOICE_SIZE(%a2)
        beq.s   .count_e2
        addq.l  #1,%d4
.count_e2:
        tst.b   VOICE_SIZE*2(%a2)
        beq.s   .count_done
        addq.l  #1,%d4
.count_done:
        tst.l   %d4
        beq.w   .mono                     | stock call clears the destination

        clr.l   poly_voice_selector
        movea.l 40(%a5),%a4
        bsr.w   .render

        moveq   #1,%d0
        move.l  %d0,poly_voice_selector
        lea     poly_scratch(%pc),%a4
        bsr.w   .render

        moveq   #2,%d0
        move.l  %d0,poly_voice_selector
        lea     poly_scratch+512(%pc),%a4
        bsr.w   .render

        moveq   #3,%d0
        move.l  %d0,poly_voice_selector
        lea     poly_scratch+1024(%pc),%a4
        bsr.w   .render
        clr.l   poly_voice_selector

| Normalize according to voices that contributed to the chunk: unity for
| one, /2 for two, and /4 for three or four.  The three-voice case keeps 6 dB
| of safety rather than adding a slow divide in the audio task.
        moveq   #0,%d6
        moveq   #1,%d0
        cmp.l   %d0,%d4
        beq.s   .mix_setup
        moveq   #1,%d6
        moveq   #2,%d0
        cmp.l   %d0,%d4
        beq.s   .mix_setup
        moveq   #2,%d6
.mix_setup:
        movea.l 40(%a5),%a0
        lea     poly_scratch(%pc),%a1
        lea     poly_scratch+512(%pc),%a2
        lea     poly_scratch+1024(%pc),%a3
        move.l  %d5,%d4
        lsl.l   #1,%d4
        subq.l  #1,%d4
.mix:
        move.l  (%a0),%d0
        asr.l   %d6,%d0
        move.l  (%a1)+,%d1
        asr.l   %d6,%d1
        add.l   %d1,%d0
        move.l  (%a2)+,%d1
        asr.l   %d6,%d1
        add.l   %d1,%d0
        move.l  (%a3)+,%d1
        asr.l   %d6,%d1
        add.l   %d1,%d0
        move.l  %d0,(%a0)+
        subq.l  #1,%d4
        bpl.s   .mix
        bra.s   .done

.reset_mono:
        move.l  %d2,%d0
        move.l  #EXTRA_TRACK_SIZE,%d1
        mulu.l  %d1,%d0
        lea     poly_extra_voices(%pc),%a0
        adda.l  %d0,%a0
        clr.b   (%a0)
        clr.b   VOICE_SIZE(%a0)
        clr.b   VOICE_SIZE*2(%a0)
        lea     poly_next(%pc),%a0
        clr.b   (%a0,%d2.l)
.mono:
        clr.l   poly_voice_selector
        movea.l 40(%a5),%a4
        bsr.s   .render
.done:
        clr.l   poly_voice_selector
        movem.l (%sp),%d2-%d7/%a2-%a5
        lea     40(%sp),%sp
        lea     24(%sp),%sp               | displaced caller cleanup
        jmp     (CONTINUE_CALLER).l

| Call the stock renderer with a fresh copy of the caller's six arguments.
| a5 remains the fixed wrapper frame and a4 selects the output buffer.
.render:
        move.l  60(%a5),-(%sp)
        move.l  56(%a5),-(%sp)
        move.l  52(%a5),-(%sp)
        move.l  48(%a5),-(%sp)
        move.l  44(%a5),-(%sp)
        move.l  %a4,-(%sp)
        jsr     (RENDER).l
        lea     24(%sp),%sp
        rts

| Detour at 0x40007978. d0 contains the track number. Selector zero rebuilds
| the exact stock pointer; 1..3 select that track's extension record.
voice_pointer:
        move.l  poly_voice_selector(%pc),%d1
        tst.l   %d1
        beq.s   .stock_pointer
        subq.l  #1,%d1
        move.l  %d1,%a2                   | selector - 1
        move.l  %d0,%d1
        add.l   %d0,%d0
        add.l   %d1,%d0                   | track * 3
        move.l  %a2,%d1
        add.l   %d1,%d0
        move.l  #VOICE_SIZE,%d1
        mulu.l  %d1,%d0
        lea     poly_extra_voices(%pc),%a2
        adda.l  %d0,%a2
        jmp     (CONTINUE_POINTER).l
.stock_pointer:
        move.l  #VOICE_SIZE,%d1            | displaced instruction
        mulu.l  %d1,%d0
        movea.l %d0,%a2
        adda.l  #VOICES,%a2
        jmp     (CONTINUE_POINTER).l

| Detour at 0x400334d8.  Stock's formatter table ends at PICKUP; return the
| runtime string for raw type 5 and replay stock's six displaced bytes for
| every existing value.
poly_machine_name:
        move.l  4(%sp),%d0
        cmpi.l  #POLY_TYPE,%d0
        bne.s   .pmn_stock
        lea     .poly_name(%pc),%a0
        move.l  %a0,%d0
        rts
.pmn_stock:
        move.l  %d2,-(%sp)
        move.l  8(%sp),%d1
        jmp     (CONTINUE_NAME).l
.poly_name:
        .asciz  "POLY"
        .balign 2

| Explicit initialization is intentional: this runtime is copied from the
| loader image and is not a zeroed BSS.
        .balign 4
poly_voice_selector:
        .long   0
poly_next:
        .zero   8
        .balign 4
poly_extra_increment:
        .zero   96                          | 24 saved Q26 increments
poly_extra_voices:
        .zero   4032                        | 8 tracks * 3 * 168 bytes
poly_scratch:
        .zero   1536                        | 3 * (64 frames * 2 * 4 bytes)
| objcopy omits trailing all-zero bytes. Keep all state inside the image.
poly_runtime_end_marker:
        .long   0x504f4c59                  | "POLY"
