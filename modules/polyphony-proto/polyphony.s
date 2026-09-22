| Four-voice render-path prototype for untimestretched audio tracks.
|
| The stock renderer owns one 168-byte voice record per track. We retain it
| as voice 0 and reserve three more records for each of the eight tracks in
| loader-owned DRAM. On the first active OFF-mode chunk, the stock record is
| copied into those records. The stock renderer is then called four times,
| selecting a different record at its pointer-calculation site. The three
| extra results land in scratch buffers; all four signed 32-bit stereo streams
| are divided by four and summed into the stock destination.
|
| This deliberately proves the expensive part first: independent renderer
| state and its CPU cost. It does not yet allocate a voice on a new trig or
| transpose voices independently. The three clones are re-primed only after
| the primary record becomes inactive. Any TSTR mode other than OFF follows
| the untouched mono path.
        .text
        .global polyphony_call
        .global voice_pointer
        .global poly_voice_selector
        .global poly_extra_voices
        .global poly_scratch
        .global poly_primed

        .equ    VOICES, 0x800049d8
        .equ    LANES,  0x80000510
        .equ    RENDER, 0x40007960
        .equ    CONTINUE_CALLER, 0x400041cc
        .equ    CONTINUE_POINTER, 0x4000798a
        .equ    VOICE_SIZE, 168
        .equ    EXTRA_PER_TRACK, 3
        .equ    EXTRA_TRACK_SIZE, 504
        .equ    MAX_SOURCE_FRAMES, 64

| Detour at 0x400041c4. The stock caller has already pushed six arguments:
| output, renderer arg2, track, source frames, output samples, and flags.
| The displaced JSR and 24-byte stack cleanup are both replayed here.
polyphony_call:
        lea     -32(%sp),%sp
        movem.l %d2-%d5/%a2-%a5,(%sp)
        movea.l %sp,%a5                   | fixed frame; original args at +32
        move.l  40(%a5),%d2               | track
        cmpi.l  #7,%d2
        bhi.w   .mono

        move.l  %d2,%d0
        move.l  #VOICE_SIZE,%d1
        mulu.l  %d1,%d0
        lea     (VOICES).l,%a3
        adda.l  %d0,%a3                   | stock primary voice
        tst.b   (%a3)
        beq.w   .inactive

        move.l  %d2,%d0
        moveq   #48,%d1
        mulu.l  %d1,%d0
        lea     (LANES).l,%a0
        tst.b   28(%a0,%d0.l)             | prototype is TSTR OFF only
        bne.w   .reset_mono
        move.l  44(%a5),%d5               | source frames; output is 8 B each
        beq.w   .mono
        cmpi.l  #MAX_SOURCE_FRAMES,%d5
        bhi.w   .reset_mono

        move.l  %d2,%d0
        move.l  #EXTRA_TRACK_SIZE,%d1
        mulu.l  %d1,%d0
        lea     poly_extra_voices(%pc),%a2
        adda.l  %d0,%a2                   | first extra record for this track
        lea     poly_primed(%pc),%a0
        tst.b   (%a0,%d2.l)
        bne.s   .render_four

| Prime all three extra records from the same pre-render primary state.
        movea.l %a2,%a1
        moveq   #2,%d4
.clone_voice:
        movea.l %a3,%a0
        moveq   #41,%d0                   | 42 longwords = 168 bytes
.clone_long:
        move.l  (%a0)+,(%a1)+
        subq.l  #1,%d0
        bpl.s   .clone_long
        subq.l  #1,%d4
        bpl.s   .clone_voice
        lea     poly_primed(%pc),%a0
        moveq   #1,%d0
        move.b  %d0,(%a0,%d2.l)

.render_four:
        clr.l   poly_voice_selector
        movea.l 32(%a5),%a4
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

| Average the four signed 32-bit words independently. There are two words
| per source frame. Quartering before addition makes overflow impossible.
        movea.l 32(%a5),%a0
        lea     poly_scratch(%pc),%a1
        lea     poly_scratch+512(%pc),%a2
        lea     poly_scratch+1024(%pc),%a3
        move.l  %d5,%d4
        lsl.l   #1,%d4
        subq.l  #1,%d4
.mix:
        move.l  (%a0),%d0
        asr.l   #2,%d0
        move.l  (%a1)+,%d1
        asr.l   #2,%d1
        add.l   %d1,%d0
        move.l  (%a2)+,%d1
        asr.l   #2,%d1
        add.l   %d1,%d0
        move.l  (%a3)+,%d1
        asr.l   #2,%d1
        add.l   %d1,%d0
        move.l  %d0,(%a0)+
        subq.l  #1,%d4
        bpl.s   .mix
        bra.s   .done

.inactive:
.reset_mono:
        lea     poly_primed(%pc),%a0
        clr.b   (%a0,%d2.l)
.mono:
        clr.l   poly_voice_selector
        movea.l 32(%a5),%a4
        bsr.s   .render
.done:
        clr.l   poly_voice_selector
        movem.l (%sp),%d2-%d5/%a2-%a5
        lea     32(%sp),%sp
        lea     24(%sp),%sp               | displaced caller cleanup
        jmp     (CONTINUE_CALLER).l

| Call the stock renderer with a fresh copy of the caller's six arguments.
| a5 remains the fixed wrapper frame and a4 selects the output buffer.
.render:
        move.l  52(%a5),-(%sp)
        move.l  48(%a5),-(%sp)
        move.l  44(%a5),-(%sp)
        move.l  40(%a5),-(%sp)
        move.l  36(%a5),-(%sp)
        move.l  %a4,-(%sp)
        jsr     (RENDER).l
        lea     24(%sp),%sp
        rts

| Detour at 0x40007978. d0 contains the track number. Selector zero rebuilds
| the exact stock pointer; 1..3 select that track's extra DRAM records.
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

| Explicit initialization is intentional: this runtime is copied from the
| loader image and is not a zeroed BSS.
        .balign 4
poly_voice_selector:
        .long   0
poly_primed:
        .zero   8
        .balign 4
poly_extra_voices:
        .zero   4032                       | 8 tracks * 3 * 168 bytes
poly_scratch:
        .zero   1536                       | 3 * (64 frames * 2 * 4 bytes)
| objcopy omits trailing all-zero bytes. Keep the explicit state and scratch
| region inside the loader image with a nonzero end marker.
poly_runtime_end_marker:
        .long   0x504f4c59                 | "POLY"
