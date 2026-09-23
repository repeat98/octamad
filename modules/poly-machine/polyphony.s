| POLY MACHINE -- four independent untimestretched playback positions per
| audio track.  The stock voice is always the newest voice.  Immediately
| before stock retriggers it, the active old state is copied into one of
| three rotating extension records.  The stock renderer then renders the
| primary and extension records into one track buffer, before the normal
| per-track FX chain.
|
| Each voice keeps the pitch it was triggered with: the stock renderer only
| fetches raw source frames and the DSP resamples the track by the primary's
| increment, so extensions are resampled here to the primary's source rate
| (.render_ext).  Panel chromatic presses are queued so a chord is not
| collapsed into stock's one-command mailbox, and releases address the voice
| that owns the key.  RATE, sample selection and p-locks remain track-wide.
        .text
        .global polyphony_call
        .global poly_config_type
        .global poly_live_type
        .global poly_stop_voice
        .global poly_voice_trigger
        .global poly_machine_name
        .global poly_src_names
        .global poly_octave_button
        .global poly_sample_ui_init
        .global poly_sample_ui_left
        .global poly_sample_ui_right
        .global poly_src_cursor_scroll
        .global poly_src_cursor_draw
        .global poly_src_cursor_record
        .global poly_src_cursor_updown_old
        .global poly_src_cursor_updown_new
        .global poly_src_cursor_right
        .global poly_src_cursor_commit_list
        .global poly_src_cursor_slot_yes
        .global poly_src_cursor_slot_lookup
        .global poly_config_tstr
        .global poly_increment_shift
        .global poly_chromatic_key
        .global poly_chord_dequeue
        .global poly_release_note
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
        .equ    STOCK_STOP, 0x40006820
        .equ    CONTINUE_POINTER, 0x4000798a
        .equ    CONTINUE_TRIGGER, 0x4000f458
        .equ    CONTINUE_LIVE_TYPE, 0x4000bff0
        .equ    CONTINUE_NAME, 0x400334de
        .equ    CONTINUE_SRC_MACHINE_NAME, 0x4003c95a
        .equ    CONTINUE_OCTAVE_BUTTON, 0x40045920
        .equ    CONTINUE_SAMPLE_UI_INIT, 0x400788d6
        .equ    CONTINUE_SAMPLE_UI_LEFT, 0x40078956
        .equ    CONTINUE_SAMPLE_UI_RIGHT, 0x4007910a
        .equ    SAMPLE_UI_MACHINE, 0x460e738e
        .equ    SAMPLE_UI_PANE, 0x460e739a
        .equ    SRC_CURSOR, 0x460d5c30
        .equ    CONTINUE_CHROMATIC_KEY, 0x4004fb9c
        .equ    CONTINUE_CHORD_DEQUEUE, 0x4000b7c6
        .equ    PENDING_COMMANDS, 0x46c80354
        .equ    LIVE_LOCKS, 0x46c7dfda
        .equ    VOICE_SIZE, 168
        .equ    EXTRA_PER_TRACK, 3
        .equ    EXTRA_TRACK_SIZE, 504
        .equ    STATE_SIZE, 40
        .equ    MAX_SOURCE_FRAMES, 64
        .equ    FETCH_FRAMES, 96            | >= 16 * 4.0 + a ratio's slack

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

| Detour at 0x4000c140, right after the config walk copied the six SRC SETUP
| bytes (LOOP SLIC LEN RATE TSTR TSNS) to 0x80000830 + 72*track, from where
| every ping copies them to lane bytes 24..29.  POLY renders its extension
| voices untimestretched only, and the render hook fell back to one voice
| whenever lane TSTR (byte 28) was non-zero -- which the stock default AUTO
| is, so a new POLY track played mono.  Force the live TSTR to OFF for POLY;
| the Part keeps whatever the user set.
poly_config_tstr:
        move.l  114(%sp),%d2              | displaced: track
        move.l  %d2,%d0
        bsr.w   poly_is_track             | d1/a0 scratch, a0 reloaded below
        tst.l   %d0
        beq.s   .pcts_done
        move.l  %d2,%d0
        moveq   #72,%d1
        mulu.l  %d1,%d0
        lea     (0x80000834).l,%a0
        clr.b   (%a0,%d0.l)               | TSTR OFF in the live config
.pcts_done:
        lsl.l   #3,%d2                    | displaced
        jmp     (0x4000c146).l

| Detour at 0x40004100, where the increment builder recomputes a track's
| increment (only on a retrigger or a pitch change; otherwise it reuses
| STATES+36).  This is the ratio the DSP resamples the track with and the
| rate its source frames are fetched at, so a POLY key's octave shift must
| land HERE; applied anywhere later it reaches neither.  Capped below 4.0:
| the caller masks a chunk's source frames with 63, so 16 samples at 4.0
| would wrap to zero -- octaves beyond the cap are dropped.
        .equ    INCREMENT_CAP, 0x0fc00000
poly_increment_shift:
        .word   0xa1c0                    | displaced movclr.l %acc0,%d0
        asr.l   %d6,%d0                   | displaced
        lea     -12(%sp),%sp
        movem.l %d0-%d1/%a0,(%sp)
        move.l  64(%sp),%d0               | track (builder arg at 52)
        bsr.w   poly_is_track
        tst.l   %d0
        beq.s   .pis_done
        move.l  64(%sp),%d1
        lea     poly_primary_shift(%pc),%a0
        mvs.b   (%a0,%d1.l),%d1
        move.l  (%sp),%d0
        tst.l   %d1
        beq.s   .pis_cap
        bmi.s   .pis_down
.pis_up:
        cmpi.l  #INCREMENT_CAP/2,%d0
        bcc.s   .pis_cap
        add.l   %d0,%d0
        subq.l  #1,%d1
        bne.s   .pis_up
        bra.s   .pis_cap
.pis_down:
        lsr.l   #1,%d0
        addq.l  #1,%d1
        bne.s   .pis_down
.pis_cap:
        cmpi.l  #INCREMENT_CAP,%d0
        bcs.s   .pis_store
        lsr.l   #1,%d0
        bra.s   .pis_cap
.pis_store:
        move.l  %d0,(%sp)
.pis_done:
        movem.l (%sp),%d0-%d1/%a0
        lea     12(%sp),%sp
        move.l  %d0,36(%a3)               | displaced
        jmp     (0x40004108).l

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
        bne.s   .pvt_active
        bsr.w   .pvt_set_primary_note
        bsr.w   .pvt_set_primary_shift
        bra.w   .pvt_done
.pvt_active:

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

| Associate the voice slot with its chromatic pitch so each held panel key
| can release its own voice instead of the stock "last key only" behavior.
        lea     poly_primary_note(%pc),%a2
        move.b  (%a2,%d2.l),%d0
        lea     poly_extra_note(%pc),%a2
        move.b  %d0,(%a2,%d1.l)
        bsr.w   .pvt_set_primary_note

        lea     poly_primary_shift(%pc),%a2
        move.b  (%a2,%d2.l),%d0
        lea     poly_extra_shift(%pc),%a2
        move.b  %d0,(%a2,%d1.l)
        bsr.w   .pvt_set_primary_shift

| The extension keeps the old primary's own increment, which the render
| publishes for that voice alone.  Measured order within a frame (octemu,
| 22 Sep 2026): consumer -> this initializer -> increment recompute ->
| render, so STATES+36 here still holds the OLD note's increment.  (Image 92
| took it from the last render instead; with keys pressed together the queue
| triggers the next note before the previous one has been rendered, the saved
| increment was 0, and that voice played DC and never ended.)
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
        lea     poly_ext_phase(%pc),%a1   | its resampler starts fresh
        clr.l   (%a1,%d1.l*4)
        lea     poly_ext_carry(%pc),%a1
        clr.l   (%a1,%d1.l*4)
        bra.s   .pvt_done

| A chromatic press leaves its key and octave shift pending; the trigger it
| causes consumes them.  Any other trigger (sequencer, MIDI, a trig key in
| another mode) finds none: no owning key, and no octave shift.
.pvt_set_primary_note:
        lea     poly_pending_key(%pc),%a2
        move.b  (%a2,%d2.l),%d0
        lea     poly_primary_note(%pc),%a2
        move.b  %d0,(%a2,%d2.l)
        moveq   #-1,%d0                   | consumed: 0xff = no key
        lea     poly_pending_key(%pc),%a2
        move.b  %d0,(%a2,%d2.l)
        rts

.pvt_set_primary_shift:
        lea     poly_pending_shift(%pc),%a2
        move.b  (%a2,%d2.l),%d0
        clr.b   (%a2,%d2.l)               | consumed
        lea     poly_primary_shift(%pc),%a2
        move.b  %d0,(%a2,%d2.l)
        rts

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

        move.l  %d2,%d0
        move.l  %d0,%d1
        lsl.l   #2,%d0
        add.l   %d1,%d0
        lsl.l   #3,%d0                    | track * 40
        lea     (STATES).l,%a0
        move.l  36(%a0,%d0.l),%d7         | primary increment (octave applied)

| The renderer does not resample: it fetches RAW source frames (d5 of them,
| the count the caller derived from the primary's increment) and the DSP
| resamples the whole track by that one increment.  So the primary renders
| as stock does, and each extension fetches its own frame count and is
| resampled here to the primary's source rate before the mix (.render_ext).
        clr.l   poly_voice_selector
        movea.l 40(%a5),%a4
        bsr.w   .render

        moveq   #1,%d3
.ext_loop:
        move.l  %d3,poly_voice_selector
        bsr.w   .render_ext
        addq.l  #1,%d3
        cmpi.l  #EXTRA_PER_TRACK+1,%d3
        bcs.s   .ext_loop
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

| .render with the fetch count in d0 and the destination in a4.
.render_count:
        move.l  60(%a5),-(%sp)
        move.l  56(%a5),-(%sp)
        move.l  %d0,-(%sp)
        move.l  48(%a5),-(%sp)
        move.l  44(%a5),-(%sp)
        move.l  %a4,-(%sp)
        jsr     (RENDER).l
        lea     24(%sp),%sp
        rts

| Render extension d3 (1..3) of track d2 into poly_scratch + (d3-1)*512 as
| d5 stereo frames at the PRIMARY's source rate (d7 = primary increment).
|
| r = inc_ext / inc_primary (Q16).  Output frame j sits at p + j*r in the
| fetch buffer, linearly interpolated.  The renderer advances the voice by
| every frame it fetches, so nothing fetched may be dropped: the frames from
| the next start's floor onward (one or two) are carried to the next chunk,
| and p stays in [0,1) relative to the first carried frame.  A voice fresh
| from poly_voice_trigger has no carried frames and p = 0.
.render_ext:
        lea     -36(%sp),%sp
        movem.l %d2-%d7/%a2-%a4,(%sp)
        move.l  %d2,%d4
        add.l   %d2,%d4
        add.l   %d2,%d4
        add.l   %d3,%d4
        subq.l  #1,%d4                    | d4 = flat extension index
        move.l  %d3,%d1
        subq.l  #1,%d1
        moveq   #9,%d0
        lsl.l   %d0,%d1
        lea     poly_scratch(%pc),%a3
        adda.l  %d1,%a3                   | a3 = output
        move.l  %d4,%d0
        move.l  #VOICE_SIZE,%d1
        mulu.l  %d1,%d0
        lea     poly_extra_voices(%pc),%a0
        tst.b   (%a0,%d0.l)
        bne.s   .re_active
        move.l  %d5,%d0                   | idle voice: silence
        bra.s   .re_zero_next
.re_zero:
        clr.l   (%a3)+
        clr.l   (%a3)+
.re_zero_next:
        subq.l  #1,%d0
        bpl.s   .re_zero
        bra.w   .re_out

.re_active:
| r16 = inc_ext * 65536 / inc_primary, with 32-bit divides: both >> 8, then
| the integer part and two 8-bit fraction digits.
        lea     poly_extra_increment(%pc),%a0
        move.l  (%a0,%d4.l*4),%d0
        lsr.l   #8,%d0                    | a
        move.l  %d7,%d1
        lsr.l   #8,%d1                    | b
        bne.s   .re_div
        move.l  #0x10000,%d6
        bra.s   .re_ratio_done
.re_div:
        move.l  %d0,%d3
        divu.l  %d1,%d3                   | q
        move.l  %d3,%d6
        swap    %d6
        clr.w   %d6                       | q << 16
        mulu.l  %d1,%d3
        sub.l   %d3,%d0                   | rem
        lsl.l   #8,%d0
        move.l  %d0,%d3
        divu.l  %d1,%d3                   | first fraction digit
        move.l  %d3,%d2
        lsl.l   #8,%d2
        add.l   %d2,%d6
        mulu.l  %d1,%d3
        sub.l   %d3,%d0
        lsl.l   #8,%d0
        divu.l  %d1,%d0                   | second fraction digit
        add.l   %d0,%d6                   | d6 = r
.re_ratio_done:
        tst.l   %d5
        beq.w   .re_out                   | nothing to produce this chunk

| Carried frames go to the front of the fetch buffer.
        lea     poly_fetch(%pc),%a4
        lea     poly_ext_carry(%pc),%a0
        move.l  (%a0,%d4.l*4),%d2         | carried frames c (0..2)
        move.l  %d4,%d0
        lsl.l   #4,%d0                    | 16 bytes of history per voice
        lea     poly_ext_hist(%pc),%a0
        adda.l  %d0,%a0
        move.l  (%a0)+,(%a4)
        move.l  (%a0)+,4(%a4)
        move.l  (%a0)+,8(%a4)
        move.l  (%a0),12(%a4)

| last = max(floor(p+(N-1)r)+1, floor(p+N*r)); frames needed = last+1.
        lea     poly_ext_phase(%pc),%a0
        move.l  (%a0,%d4.l*4),%d3         | p
        move.l  %d5,%d0
        subq.l  #1,%d0
        mulu.l  %d6,%d0
        add.l   %d3,%d0
        clr.w   %d0
        swap    %d0
        addq.l  #1,%d0                    | m
        move.l  %d5,%d1
        mulu.l  %d6,%d1
        add.l   %d3,%d1
        clr.w   %d1
        swap    %d1                       | k
        cmp.l   %d1,%d0
        bcc.s   .re_last
        move.l  %d1,%d0
.re_last:
        addq.l  #1,%d0                    | total frames in the buffer
        cmpi.l  #FETCH_FRAMES,%d0
        bls.s   .re_total_ok
        move.l  #FETCH_FRAMES,%d0         | out of range: cap, never overrun
.re_total_ok:
        movea.l %d0,%a2                   | a2 = total
        sub.l   %d2,%d0                   | frames to fetch
        ble.s   .re_fetched
        move.l  %d2,%d1
        lsl.l   #3,%d1
        adda.l  %d1,%a4                   | fetch after the carried frames
.re_fetch:
        move.l  %d0,%d1
        cmpi.l  #63,%d1
        bls.s   .re_fetch_n
        moveq   #63,%d1
.re_fetch_n:
        sub.l   %d1,%d0
        move.l  %d0,-(%sp)
        move.l  %d1,-(%sp)
        move.l  %d1,%d0
        bsr.w   .render_count
        move.l  (%sp)+,%d1
        move.l  (%sp)+,%d0
        lsl.l   #3,%d1
        adda.l  %d1,%a4
        tst.l   %d0
        bgt.s   .re_fetch
.re_fetched:

| Interpolate d5 output frames.  Sample words are 16-bit PCM << 16, so the
| difference is taken on the top halves and scaled by a 13-bit fraction.
        lea     poly_fetch(%pc),%a4
        move.l  %d3,%d2                   | pos = p
        move.l  %d5,%d7
        subq.l  #1,%d7
.re_interp:
        move.l  %d2,%d0
        clr.w   %d0
        swap    %d0
        lsl.l   #3,%d0
        lea     (%a4,%d0.l),%a0           | &buf[floor(pos)]
        move.l  %d2,%d1
        andi.l  #0xffff,%d1
        lsr.l   #3,%d1                    | 13-bit fraction
        move.l  (%a0),%d3                 | left a
        move.l  8(%a0),%d0                | left b
        swap    %d0
        ext.l   %d0
        move.l  %d3,%d5
        swap    %d5
        ext.l   %d5
        sub.l   %d5,%d0
        muls.l  %d1,%d0
        asl.l   #3,%d0
        add.l   %d3,%d0
        move.l  %d0,(%a3)+
        move.l  4(%a0),%d3                | right a
        move.l  12(%a0),%d0               | right b
        swap    %d0
        ext.l   %d0
        move.l  %d3,%d5
        swap    %d5
        ext.l   %d5
        sub.l   %d5,%d0
        muls.l  %d1,%d0
        asl.l   #3,%d0
        add.l   %d3,%d0
        move.l  %d0,(%a3)+
        add.l   %d6,%d2
        subq.l  #1,%d7
        bpl.s   .re_interp

| Carry buf[k..total-1] and keep p in [0,1) relative to buf[k].
        move.l  %d2,%d0
        clr.w   %d0
        swap    %d0                       | k
        move.l  %a2,%d1
        subq.l  #1,%d1
        cmp.l   %d1,%d0
        bls.s   .re_k_ok
        move.l  %d1,%d0                   | capped fetch: hold at the end
.re_k_ok:
        andi.l  #0xffff,%d2
        lea     poly_ext_phase(%pc),%a0
        move.l  %d2,(%a0,%d4.l*4)
        move.l  %a2,%d1
        sub.l   %d0,%d1                   | frames carried (1 or 2)
        cmpi.l  #2,%d1
        bls.s   .re_carry_n
        moveq   #2,%d1
.re_carry_n:
        lea     poly_ext_carry(%pc),%a0
        move.l  %d1,(%a0,%d4.l*4)
        lsl.l   #3,%d0
        lea     (%a4,%d0.l),%a1           | &buf[k]
        move.l  %d4,%d0
        lsl.l   #4,%d0
        lea     poly_ext_hist(%pc),%a0
        adda.l  %d0,%a0
        move.l  (%a1)+,(%a0)+
        move.l  (%a1)+,(%a0)+
        move.l  (%a1)+,(%a0)+
        move.l  (%a1),(%a0)
.re_out:
        movem.l (%sp),%d2-%d7/%a2-%a4
        lea     36(%sp),%sp
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
        beq.s   .pmn_poly
        cmpi.l  #1,%d0
        bne.s   .pmn_stock
        move.l  poly_ui_machine(%pc),%d0
        cmpi.l  #POLY_TYPE,%d0
        bne.s   .pmn_stock
.pmn_poly:
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

| SRC SETUP normally points a5 at a stock five-entry table.  Repoint that LEA
| to this six-entry clone and widen the inline upper bound from 4 to 5.  This
| avoids running custom code inside the selector's fragile redraw loop.
        .balign 4
poly_src_names:
        .long   0x400b3eac
        .long   0x400b3e98
        .long   0x400b7c67
        .long   0x400b5413
        .long   0x400b7a63
        .long   .poly_name

| Stock audio chromatic mode toggles only octave 0/1.  For POLY the same
| buttons walk 0..POLY_OCTAVE_MAX.  Not further: the chromatic LED routine
| writes two 8-entry stack arrays at 2*octave and 2*octave+1 (0x4004d47e),
| so octave 4 smashed its stack and hung the UI (measured under octemu,
| 22 Sep 2026, images <= 92 walked 0..10); and above octave 2 the keys pass
| the +24-semitone fetch cap and only repeat the top octave.  Other machine
| types retain the exact stock XOR toggle.
        .equ    POLY_OCTAVE_MAX, 2
poly_octave_button:
        move.l  %d0,-(%sp)
        mvz.b   (0x100b14cc).l,%d0
        bsr.w   poly_is_track
        tst.l   %d0
        beq.s   .pob_stock
        move.l  (0x460d16fc).l,%d0
        cmpi.l  #52,%d2                  | down button
        bne.s   .pob_up
        subq.l  #1,%d0
        bpl.s   .pob_store
        moveq   #POLY_OCTAVE_MAX,%d0
        bra.s   .pob_store
.pob_up:
        addq.l  #1,%d0
        cmpi.l  #POLY_OCTAVE_MAX,%d0
        bls.s   .pob_store
        moveq   #0,%d0
.pob_store:
        move.l  %d0,(0x460d16fc).l
        move.l  (%sp)+,%d0
        jmp     (CONTINUE_OCTAVE_BUTTON).l
.pob_stock:
        move.l  (%sp)+,%d0
        moveq   #1,%d2
        eor.l   %d2,(0x460d16fc).l
        jmp     (CONTINUE_OCTAVE_BUTTON).l

| The stock sample chooser uses the machine-selector value itself as its
| STATIC/FLEX discriminator.  Raw POLY (5) therefore falls through to the
| invalid-machine path and draws "Error".  Keep type 5 in the Part, but use
| FLEX (1) in this transient selector only while the sample pane is active.
| poly_ui_machine remembers which machine value LEFT must restore.
poly_sample_ui_init:
        .word   0x7190                    | displaced mvz.b (a0),d0
        clr.l   poly_ui_machine
        cmpi.l  #POLY_TYPE,%d0
        bne.s   .psui_pane
        move.l  %d0,poly_ui_machine
        moveq   #1,%d0
        move.l  %d0,(SAMPLE_UI_MACHINE).l
.psui_pane:
        moveq   #1,%d2
        cmp.l   %d0,%d2
        scs     %d0
        mvs.b   %d0,%d0
        addq.l  #1,%d0
        move.l  %d0,(SAMPLE_UI_PANE).l
        jmp     (CONTINUE_SAMPLE_UI_INIT).l

poly_sample_ui_left:
        move.l  %d0,-(%sp)
        move.l  poly_ui_machine(%pc),%d0
        beq.s   .psul_clear
        move.l  %d0,(SAMPLE_UI_MACHINE).l
        clr.l   poly_ui_machine
.psul_clear:
        move.l  (%sp)+,%d0
        clr.l   (SAMPLE_UI_PANE).l
        jmp     (CONTINUE_SAMPLE_UI_LEFT).l

poly_sample_ui_right:
        move.l  (SAMPLE_UI_MACHINE).l,%d0
        moveq   #1,%d3
        clr.l   poly_ui_machine
        cmpi.l  #POLY_TYPE,%d0
        bne.s   .psur_done
        move.l  %d0,poly_ui_machine
        move.l  %d3,%d0
        move.l  %d0,(SAMPLE_UI_MACHINE).l
.psur_done:
        jmp     (CONTINUE_SAMPLE_UI_RIGHT).l

| SRC SETUP (double-click SRC, FUNC+SRC) is a second copy of the machine/slot
| chooser, with its own state: the machine list object at 0x460d5c28 whose
| cursor is SRC_CURSOR, the pane flag at 0x460d1a48, and the STATIC/FLEX slot
| lists at 0x460d5c3c/0x460d5c50.  Every read of the cursor that picks the
| STATIC or FLEX behaviour tests 0 and 1 only, so on raw POLY (5) RIGHT did
| nothing, the redraw closed the slot pane (cursor > 2), the Part's slot byte
| was indexed at track*5+5 (the next track's STATIC slot), and the slot lookup
| 0x40031d18 returned NULL.  These reads see FLEX instead.  The cursor itself
| stays 5, so the two commit sites (0x4005a616 machine pane YES, 0x4005a850
| slot pane YES) still write POLY into the Part.  Each stub replaces one
| six-byte `move.l SRC_CURSOR,Dn` and ends with `tst.l Dn`, so the flags the
| stock code branches on are those of the value it now holds.
        .macro  SRC_CURSOR_AS_FLEX reg, cont
        move.l  (SRC_CURSOR).l,\reg
        cmpi.l  #POLY_TYPE,\reg
        bne.s   1f
        moveq   #1,\reg
1:      tst.l   \reg
        jmp     (\cont).l
        .endm

poly_src_cursor_scroll:                     | 0x4003a4b4: which slot list turns
        SRC_CURSOR_AS_FLEX %d2, 0x4003a4ba
poly_src_cursor_draw:                       | 0x4003c8c4: pane kept, list drawn
        SRC_CURSOR_AS_FLEX %d6, 0x4003c8ca
poly_src_cursor_record:                     | 0x4003d016: machine/slot load record
        SRC_CURSOR_AS_FLEX %d1, 0x4003d01c
poly_src_cursor_updown_old:                 | 0x4003d07c: slot list UP/DOWN moves
        SRC_CURSOR_AS_FLEX %d3, 0x4003d082
poly_src_cursor_updown_new:                 | 0x4003d0fa: Part slot byte index
        SRC_CURSOR_AS_FLEX %d1, 0x4003d100
poly_src_cursor_right:                      | 0x4003d1da: RIGHT opens the slot pane
        SRC_CURSOR_AS_FLEX %d1, 0x4003d1e0
poly_src_cursor_commit_list:                | 0x4005a67c: list shown after YES
        SRC_CURSOR_AS_FLEX %d0, 0x4005a682
poly_src_cursor_slot_yes:                   | 0x4005a766: slot pane YES
        SRC_CURSOR_AS_FLEX %d4, 0x4005a76c

| 0x4005a806 pushes the cursor as the machine argument of the slot lookup
| 0x40031d18, which answers only 0 (STATIC) and 1/4 (FLEX pool).
poly_src_cursor_slot_lookup:
        subq.l  #4,%sp
        move.l  %d0,-(%sp)
        move.l  (SRC_CURSOR).l,%d0
        cmpi.l  #POLY_TYPE,%d0
        bne.s   1f
        moveq   #1,%d0
1:      move.l  %d0,4(%sp)
        move.l  (%sp)+,%d0
        jmp     (0x4005a80c).l

| The stock chromatic handler owns one pending command per track.  If two
| trig-key press events are dispatched before the next audio frame, the last
| one overwrites the first.  POLY retains the first stock event and queues up
| to three more pitch bytes, matching its three extension voices.  STATIC and
| FLEX replay their exact displaced prologue.
poly_chromatic_key:
        lea     -16(%sp),%sp
        movem.l %d2-%d4/%a2,(%sp)
        move.l  24(%sp),%d1              | chromatic key 0..135
        cmpi.l  #135,%d1
        bhi.w   .pck_stock
        move.l  20(%sp),%d0              | track
        bsr.w   poly_is_track
        tst.l   %d0
        beq.w   .pck_stock

        move.l  28(%sp),%d0              | edge: 1 press, 0 release
        beq.w   .pck_release
        cmpi.l  #1,%d0
        bne.w   .pck_stock

        move.l  20(%sp),%d0
        lea     (PENDING_COMMANDS).l,%a0
        tst.l   (%a0,%d0.l*4)
        beq.s   .pck_direct
        lea     poly_chord_count(%pc),%a0
        mvz.b   (%a0,%d0.l),%d2
        cmpi.l  #3,%d2
        bcc.s   .pck_done

        move.l  %d0,%d1
        add.l   %d0,%d1
        add.l   %d0,%d1                  | track * 3
        add.l   %d2,%d1
        lea     poly_chord_notes(%pc),%a1
        move.l  24(%sp),%d3
        move.b  %d3,(%a1,%d1.l)
        addq.l  #1,%d2
        move.b  %d2,(%a0,%d0.l)
.pck_done:
        moveq   #0,%d0
        movem.l (%sp),%d2-%d4/%a2
        lea     16(%sp),%sp
        rts
.pck_direct:
        move.l  24(%sp),%d1
        move.l  %d1,%d4                  | raw key
        bsr.w   .pck_encode              | d3=pitch byte, d2=octave shift
        move.l  20(%sp),%d0
        move.l  %d0,%d1
        lsl.l   #5,%d1
        lea     (LIVE_LOCKS).l,%a0
        move.b  %d3,(%a0,%d1.l)
        lea     (PENDING_COMMANDS).l,%a0
        moveq   #29,%d1
        move.l  %d1,(%a0,%d0.l*4)
        lea     poly_armed_shift(%pc),%a0
        move.b  %d2,(%a0,%d0.l)
        lea     poly_armed_key(%pc),%a0
        move.b  %d4,(%a0,%d0.l)
        bra.s   .pck_done
.pck_release:
        move.l  24(%sp),%d1              | raw extended key
        move.l  20(%sp),%d0
        bsr.w   poly_release_note
| The press's command (0x1d, no bit 8) set this track's bit in the frame
| consumer's live-played mask 0x46c7e9f8, which keeps the sequencer off the
| track; stock clears it by posting bit 6 on the release.  Post it once the
| track's last key is up -- without this a POLY track never triggered again
| after the first chromatic note (measured under octemu, 22 Sep 2026).
        move.l  20(%sp),%d0
        moveq   #-1,%d2                  | 0xff = no key
        lea     poly_primary_note(%pc),%a0
        cmp.b   (%a0,%d0.l),%d2
        bne.w   .pck_done
        move.l  %d0,%d1
        add.l   %d0,%d1
        add.l   %d0,%d1                  | track * 3
        lea     poly_extra_note(%pc),%a0
        adda.l  %d1,%a0
        cmp.b   (%a0)+,%d2
        bne.w   .pck_done
        cmp.b   (%a0)+,%d2
        bne.w   .pck_done
        cmp.b   (%a0),%d2
        bne.w   .pck_done
        lea     poly_chord_count(%pc),%a0
        tst.b   (%a0,%d0.l)
        bne.w   .pck_done
        lea     (PENDING_COMMANDS).l,%a0
        move.l  (%a0,%d0.l*4),%d1
        moveq   #0x40,%d2
        or.l    %d2,%d1
        move.l  %d1,(%a0,%d0.l*4)
        bra.w   .pck_done
.pck_stock:
        movem.l (%sp),%d2-%d4/%a2
        lea     16(%sp),%sp
        lea     -16(%sp),%sp              | replay displaced prologue
        movem.l %d2-%d4/%a2,(%sp)
        jmp     (CONTINUE_CHROMATIC_KEY).l

.pck_encode:
        move.l  %d1,%d0
        moveq   #-1,%d2
.pcke_octave:
        cmpi.l  #12,%d0
        bcs.s   .pcke_pitch
        subi.l  #12,%d0
        addq.l  #1,%d2
        bra.s   .pcke_octave
.pcke_pitch:
        addi.l  #12,%d0
        move.l  %d0,%d3
        lsl.l   #2,%d3
        add.l   %d0,%d3
        addq.l  #4,%d3
        rts

| d0=track, d1=stock chromatic pitch byte. Stop every matching primary or
| extension record. This replaces the stock single-held-note release only for
| POLY; the same pitch may legitimately exist in more than one stolen slot.
poly_release_note:
        lea     -20(%sp),%sp
        movem.l %d2-%d3/%a0-%a2,(%sp)
        move.l  %d0,%d2
        move.l  %d1,%d3

| The primary stops through stock's own stop routine: clearing only its
| active byte left STATES+4, the voice generation counter and 0x4000672c's
| bookkeeping behind, and the track never triggered again -- not from the
| sequencer, not from a grid-record preview (measured under octemu, 22 Sep
| 2026).  The UI task runs with the render idle, so the selector is 0 here
| and poly_stop_voice passes the call straight to stock.
        lea     poly_primary_note(%pc),%a0
        cmp.b   (%a0,%d2.l),%d3
        bne.s   .prn_extra
        move.l  %d2,-(%sp)
        jsr     (STOCK_STOP).l
        addq.l  #4,%sp
        lea     poly_primary_note(%pc),%a0
        st      %d0
        move.b  %d0,(%a0,%d2.l)          | the voice no longer owns the key
.prn_extra:
        move.l  %d2,%d0
        add.l   %d2,%d0
        add.l   %d2,%d0                  | first flat extension index
        lea     poly_extra_note(%pc),%a0
        lea     poly_extra_voices(%pc),%a1
        moveq   #0,%d2
.prn_loop:
        move.l  %d0,%a2
        add.l   %d2,%a2
        cmp.b   (%a0,%a2.l),%d3
        bne.s   .prn_next
        move.l  %a2,%d1
        move.l  #VOICE_SIZE,%d0
        mulu.l  %d0,%d1
        clr.b   (%a1,%d1.l)
        moveq   #-1,%d1
        move.b  %d1,(%a0,%a2.l)          | the voice no longer owns the key
        move.l  %a2,%d0
        sub.l   %d2,%d0
.prn_next:
        addq.l  #1,%d2
        cmpi.l  #EXTRA_PER_TRACK,%d2
        bcs.s   .prn_loop
        movem.l (%sp),%d2-%d3/%a0-%a2
        lea     20(%sp),%sp
        rts

| Called where the frame consumer has finished copying and clearing the live
| lock block.  Re-arm one queued pitch for the following frame, then replay
| the displaced clear/LEA sequence.  Spreading a chord over adjacent 16-sample
| frames prevents the stock one-command mailbox from collapsing its presses.
| A press (or the re-arm below) leaves its key and octave shift ARMED; the
| consumer taking that track's command promotes them to the pending pair
| the trigger consumes.  One stage was not enough: this hook runs between
| the consumer copying a command and the trigger it causes (measured order:
| here -> initializer -> recompute -> render), so re-arming the next queued
| key overwrote the key of the note about to start -- it played the right
| pitch under the wrong key and octave, and the chord's last voice owned no
| key and never released (octemu, 22 Sep 2026).
poly_chord_dequeue:
        lea     -24(%sp),%sp
        movem.l %d0-%d3/%a0-%a1,(%sp)
        move.l  (%a0,%d4.l*4),%d3         | the command being consumed
        clr.l   (%a0,%d4.l*4)             | displaced pending-command clear
        move.l  %d4,%d0
        bsr.w   poly_is_track
        tst.l   %d0
        beq.w   .pcd_done
        tst.l   %d3
        beq.s   .pcd_promoted
        lea     poly_armed_key(%pc),%a0
        move.b  (%a0,%d4.l),%d0
        moveq   #-1,%d1
        move.b  %d1,(%a0,%d4.l)
        lea     poly_pending_key(%pc),%a0
        move.b  %d0,(%a0,%d4.l)
        lea     poly_armed_shift(%pc),%a0
        move.b  (%a0,%d4.l),%d0
        clr.b   (%a0,%d4.l)
        lea     poly_pending_shift(%pc),%a0
        move.b  %d0,(%a0,%d4.l)
.pcd_promoted:
        lea     poly_chord_count(%pc),%a0
        mvz.b   (%a0,%d4.l),%d2
        beq.s   .pcd_done

        move.l  %d4,%d0
        move.l  %d0,%d1
        add.l   %d0,%d0
        add.l   %d1,%d0                  | track * 3
        lea     poly_chord_notes(%pc),%a1
        move.b  (%a1,%d0.l),%d3
        cmpi.l  #2,%d2
        bcs.s   .pcd_no_second
        move.b  1(%a1,%d0.l),%d1
        move.b  %d1,(%a1,%d0.l)
.pcd_no_second:
        cmpi.l  #3,%d2
        bcs.s   .pcd_store
        move.b  2(%a1,%d0.l),%d1
        move.b  %d1,1(%a1,%d0.l)
.pcd_store:
        subq.l  #1,%d2
        move.b  %d2,(%a0,%d4.l)
        lea     poly_armed_key(%pc),%a0
        move.b  %d3,(%a0,%d4.l)
        move.l  %d3,%d1
        bsr.w   .pck_encode              | d3=pitch byte, d2=octave shift
        lea     poly_armed_shift(%pc),%a0
        move.b  %d2,(%a0,%d4.l)
        move.l  %d4,%d0
        lsl.l   #5,%d0
        lea     (LIVE_LOCKS).l,%a1
        move.b  %d3,(%a1,%d0.l)
        lea     (PENDING_COMMANDS).l,%a1
        moveq   #29,%d0
        move.l  %d0,(%a1,%d4.l*4)
.pcd_done:
        movem.l (%sp),%d0-%d3/%a0-%a1
        lea     24(%sp),%sp
        lea     0x46c802a6.l,%a0          | displaced instruction
        jmp     (CONTINUE_CHORD_DEQUEUE).l

| Explicit initialization is intentional: this runtime is copied from the
| loader image and is not a zeroed BSS.
        .balign 4
poly_voice_selector:
        .long   0
poly_ui_machine:
        .long   0
poly_chord_count:
        .zero   8
poly_chord_notes:
        .zero   24
poly_pending_key:
        .fill   8,1,0xff                    | 0xff = no pending chromatic key
poly_pending_shift:
        .zero   8
poly_armed_key:
        .fill   8,1,0xff                    | set by a press, promoted by the consumer
poly_armed_shift:
        .zero   8
poly_primary_note:
        .fill   8,1,0xff
poly_extra_note:
        .fill   24,1,0xff
poly_primary_shift:
        .zero   8
poly_extra_shift:
        .zero   24
poly_next:
        .zero   8
        .balign 4
poly_extra_increment:
        .zero   96                          | 24 saved Q26 increments
poly_ext_phase:
        .zero   96                          | 24 resampler phases, Q16 in [0,1)
poly_ext_carry:
        .zero   96                          | 24 carried-frame counts (0..2)
poly_ext_hist:
        .zero   384                         | 24 * two carried stereo frames
poly_fetch:
        .zero   (FETCH_FRAMES+2)*8          | one extension's raw source frames
poly_extra_voices:
        .zero   4032                        | 8 tracks * 3 * 168 bytes
poly_scratch:
        .zero   1536                        | 3 * (64 frames * 2 * 4 bytes)
| objcopy omits trailing all-zero bytes. Keep all state inside the image.
poly_runtime_end_marker:
        .long   0x504f4c59                  | "POLY"
