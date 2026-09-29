| POLY MACHINE -- four independent untimestretched playback positions per
| audio track.  The stock voice is always the newest voice.  Immediately
| before stock retriggers it, the sounding old voice is moved into one of
| three extension records.  The stock renderer then fetches every voice's
| raw frames, and each is resampled, enveloped and mixed here into the one
| track buffer, before the normal per-track FX chain.
|
| Each voice keeps its own pitch and its own AMP envelope.  The stock
| renderer only fetches raw source frames and the DSP resamples each track
| by one increment and applies one amp envelope; on a POLY track the DSP
| runs at unity with its envelope held open (poly_increment_shift,
| poly_amp_hook), and every voice is resampled (.render_voice) and enveloped
| (.env_track) on the ColdFire.  Chromatic presses -- panel keys and MIDI
| notes alike -- are queued so a chord is not collapsed into stock's
| one-command mailbox, and releases address the voices that own the key.
| RATE, sample selection, FX and p-locks remain track-wide.
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
        .global poly_midi_note_on
        .global poly_midi_note_off
        .global poly_release_held
        .global poly_kbd_fill
        .global poly_kbd_next
        .global poly_amp_hook
        .global poly_oct_number
        .global poly_oct_led
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
        .equ    MIDI_GATES, 0x46c7fb08
        .equ    CONTINUE_MIDI_ON, 0x4000e74e
        .equ    MIDI_ON_HELD, 0x4000e75a
        .equ    MIDI_OFF_MATCH, 0x4000dfdc
        .equ    MIDI_OFF_NEXT, 0x4000dff8
| A voice's owning key: a panel chromatic key 0..135, or MIDI_KEY + note for
| a MIDI note (72..96 reach the chromatic path, so 0xc8..0xe0); 0xff = none.
        .equ    MIDI_KEY, 0x80
        .equ    PANEL_KEYS, 136
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
| STATES+36).  STATES+36 is the ratio the DSP resamples the whole track by,
| and the caller fetches the chunk's source frames at it.  On a POLY track
| the DSP runs at unity instead: the builder's increment, with the key's
| octave shift, becomes the newest voice's own (poly_voice_inc), and every
| voice is resampled on the ColdFire (.render_voice).  While the DSP followed
| each newest note, every new key changed the rate under the voices still
| sounding and their waveforms stepped (octemu, 25 Sep 2026: about half of
| full scale at a pitch-changing press, five times a same-pitch press).
| Capped where a voice's fetch still fits poly_fetch: 16 frames at 5.75,
| 30 semitones up.  With TSTR on, POLY renders stock mono: stock's rate.
        .equ    INCREMENT_CAP, 0x17000000
        .equ    INCREMENT_UNITY, 0x04000000
poly_increment_shift:
        .word   0xa1c0                    | displaced movclr.l %acc0,%d0
        asr.l   %d6,%d0                   | displaced
        lea     -12(%sp),%sp
        movem.l %d0-%d1/%a0,(%sp)
        move.l  64(%sp),%d0               | track (builder arg at 52)
        bsr.w   poly_is_track
        tst.l   %d0
        beq.s   .pis_done
        move.l  64(%sp),%d0
        moveq   #48,%d1
        mulu.l  %d1,%d0
        lea     (LANES).l,%a0
        tst.b   28(%a0,%d0.l)             | TSTR on: stock mono, stock's rate
        bne.s   .pis_done
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
        move.l  64(%sp),%d1
        lsl.l   #4,%d1                    | the primary's voice index * 4
        lea     poly_voice_inc(%pc),%a0
        move.l  %d0,(%a0,%d1.l)
        move.l  #INCREMENT_UNITY,%d0
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
| first argument is the track at 4(sp).  Before stock overwrites a sounding
| primary, the primary -- voice record, owning key, octave shift, increment
| and envelope -- moves into an extension slot: a free one, else the quietest
| voice already in its release, else the next in rotation.  The new primary
| then starts its own envelope from zero.  This catches sequencer, manual and
| MIDI triggers at the common boundary.
poly_voice_trigger:
        lea     -40(%sp),%sp
        movem.l %d0-%d5/%a0-%a3,(%sp)
        move.l  44(%sp),%d2               | track
        move.l  %d2,%d0
        bsr.w   poly_is_track
        tst.l   %d0
        beq.w   .pvt_done

        move.l  %d2,%d0
        move.l  #VOICE_SIZE,%d4
        mulu.l  %d4,%d0
        lea     (VOICES).l,%a0
        adda.l  %d0,%a0                   | a0 = the primary's record
        tst.b   (%a0)
        beq.w   .pvt_fresh

        bsr.w   .pvt_pick_slot            | d0 = extension slot 0..2
        move.l  %d0,%d3
        move.l  %d2,%d1
        add.l   %d2,%d1
        add.l   %d2,%d1
        add.l   %d3,%d1                   | d1 = flat extension index

        lea     poly_primary_note(%pc),%a2
        move.b  (%a2,%d2.l),%d0
        lea     poly_extra_note(%pc),%a2
        move.b  %d0,(%a2,%d1.l)
        lea     poly_primary_shift(%pc),%a2
        move.b  (%a2,%d2.l),%d0
        lea     poly_extra_shift(%pc),%a2
        move.b  %d0,(%a2,%d1.l)

| Its envelope, its own increment (poly_increment_shift) and its resampler
| (phase, carried frames) move with it: a held note neither dips nor steps
| when the next one starts.
        move.l  %d2,%d4
        lsl.l   #2,%d4                    | the primary's voice index
        move.l  %d4,%d5
        add.l   %d3,%d5
        addq.l  #1,%d5                    | the extension's voice index
        lea     poly_env_level(%pc),%a2
        move.l  (%a2,%d4.l*4),%d0
        move.l  %d0,(%a2,%d5.l*4)
        lea     poly_env_timer(%pc),%a2
        move.l  (%a2,%d4.l*4),%d0
        move.l  %d0,(%a2,%d5.l*4)
        lea     poly_env_stage(%pc),%a2
        move.b  (%a2,%d4.l),%d0
        move.b  %d0,(%a2,%d5.l)
        lea     poly_env_gain(%pc),%a2
        move.w  (%a2,%d4.l*2),%d0
        move.w  %d0,(%a2,%d5.l*2)
        lea     poly_voice_inc(%pc),%a2
        move.l  (%a2,%d4.l*4),%d0
        move.l  %d0,(%a2,%d5.l*4)
        lea     poly_rs_phase(%pc),%a2
        move.l  (%a2,%d4.l*4),%d0
        move.l  %d0,(%a2,%d5.l*4)
        lea     poly_rs_carry(%pc),%a2
        move.l  (%a2,%d4.l*4),%d0
        move.l  %d0,(%a2,%d5.l*4)
        move.l  %d4,%d0
        lsl.l   #4,%d0
        lea     poly_rs_hist(%pc),%a2
        adda.l  %d0,%a2
        move.l  %d5,%d0
        lsl.l   #4,%d0
        lea     poly_rs_hist(%pc),%a3
        adda.l  %d0,%a3
        move.l  (%a2)+,(%a3)+
        move.l  (%a2)+,(%a3)+
        move.l  (%a2)+,(%a3)+
        move.l  (%a2),(%a3)

        move.l  %d1,%d0
        move.l  #VOICE_SIZE,%d4
        mulu.l  %d4,%d0
        lea     poly_extra_voices(%pc),%a1
        adda.l  %d0,%a1
        moveq   #41,%d0                   | 42 longs = 168 bytes
.pvt_copy:
        move.l  (%a0)+,(%a1)+
        subq.l  #1,%d0
        bpl.s   .pvt_copy

.pvt_fresh:
        bsr.w   .pvt_set_primary_note
        bsr.w   .pvt_set_primary_shift
        move.l  %d2,%d4
        lsl.l   #2,%d4                    | the new primary's envelope starts at 0
        lea     poly_env_level(%pc),%a2
        clr.l   (%a2,%d4.l*4)
        lea     poly_env_timer(%pc),%a2
        clr.l   (%a2,%d4.l*4)
        lea     poly_env_gain(%pc),%a2
        clr.w   (%a2,%d4.l*2)
        lea     poly_env_stage(%pc),%a2
        moveq   #ENV_ATTACK,%d0
        move.b  %d0,(%a2,%d4.l)
        lea     poly_rs_phase(%pc),%a2    | and its resampler starts fresh
        clr.l   (%a2,%d4.l*4)
        lea     poly_rs_carry(%pc),%a2
        clr.l   (%a2,%d4.l*4)
        bra.w   .pvt_done

| Track d2: the extension slot a moving primary takes, in d0 (0..2).  A free
| slot first; else the quietest voice already releasing; else the rotation.
| The rotation then continues after the slot taken.  Clobbers d1/d3-d5/a1.
.pvt_pick_slot:
        move.l  %d2,%d0
        move.l  #EXTRA_TRACK_SIZE,%d1
        mulu.l  %d1,%d0
        lea     poly_extra_voices(%pc),%a1
        adda.l  %d0,%a1
        moveq   #0,%d0
.pps_free:
        tst.b   (%a1)
        beq.s   .pps_take
        lea     VOICE_SIZE(%a1),%a1
        addq.l  #1,%d0
        cmpi.l  #EXTRA_PER_TRACK,%d0
        bcs.s   .pps_free
        moveq   #-1,%d0
        move.l  #0x7fffffff,%d5           | the quietest level so far
        move.l  %d2,%d4
        lsl.l   #2,%d4
        addq.l  #1,%d4                    | voice index of extension 0
        moveq   #0,%d1
.pps_release:
        lea     poly_env_stage(%pc),%a1
        mvz.b   (%a1,%d4.l),%d3
        cmpi.l  #ENV_RELEASE,%d3
        bne.s   .pps_next
        lea     poly_env_level(%pc),%a1
        move.l  (%a1,%d4.l*4),%d3
        cmp.l   %d5,%d3
        bcc.s   .pps_next
        move.l  %d3,%d5
        move.l  %d1,%d0
.pps_next:
        addq.l  #1,%d4
        addq.l  #1,%d1
        cmpi.l  #EXTRA_PER_TRACK,%d1
        bcs.s   .pps_release
        tst.l   %d0
        bpl.s   .pps_take
        lea     poly_next(%pc),%a1
        mvz.b   (%a1,%d2.l),%d0
.pps_take:
        move.l  %d0,%d1
        addq.l  #1,%d1
        cmpi.l  #EXTRA_PER_TRACK,%d1
        bcs.s   .pps_rot
        moveq   #0,%d1
.pps_rot:
        lea     poly_next(%pc),%a1
        move.b  %d1,(%a1,%d2.l)
        rts

| A chromatic press leaves its key and octave shift pending; the trigger it
| causes consumes them.  Any other trigger (sequencer, a trig key in another
| mode) finds none: no owning key, and no octave shift.
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
        movem.l (%sp),%d0-%d5/%a0-%a3
        lea     40(%sp),%sp
        lea     -60(%sp),%sp              | displaced initializer prologue
        movem.l %d2-%d7/%a2-%fp,(%sp)
        jmp     (CONTINUE_TRIGGER).l

| Detour at 0x400041c4.  The stock caller has already pushed six arguments:
| output, renderer arg2, track, source frames, output samples, and flags.
| There is no JSR return address because the detour jumps here.  The wrapper
| replays the displaced call cleanup itself.
|
| Each voice renders at unity, gets its own AMP envelope (.env_track) and
| is mixed at that gain (.mix); voices whose release has ended stop
| (.env_reap).  The DSP's one envelope per track is held open meanwhile
| (poly_amp_hook).
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

        bsr.w   .env_track                | d6 = mask of active voices
        tst.l   %d6
        beq.w   .mono                     | stock call clears the destination

        move.l  %d2,%d0
        move.l  %d0,%d1
        lsl.l   #2,%d0
        add.l   %d1,%d0
        lsl.l   #3,%d0                    | track * 40
        lea     (STATES).l,%a0
        move.l  36(%a0,%d0.l),%d7         | primary increment (octave applied)

| The renderer does not resample: it fetches RAW source frames, and the DSP
| resamples the whole track by STATES+36 -- unity on a POLY track
| (poly_increment_shift).  So each voice, the primary too, fetches its own
| frame count and is resampled here to d5 frames at d7 (.render_voice).
        moveq   #0,%d3
.voice_loop:
        btst    %d3,%d6
        beq.s   .voice_next
        move.l  %d3,poly_voice_selector
        bsr.w   .render_voice
.voice_next:
        addq.l  #1,%d3
        moveq   #4,%d0
        cmp.l   %d0,%d3
        bcs.s   .voice_loop
        clr.l   poly_voice_selector
        bsr.w   .mix
        bsr.w   .env_reap
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
        lea     poly_sounding(%pc),%a0
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

| Render voice d3 (0 = the primary, 1..3 = the extensions) of track d2 into
| poly_scratch + d3*512 as d5 stereo frames at d7 (STATES+36, unity on a
| POLY track).
|
| r = inc_voice / d7 (Q16).  Output frame j sits at p + j*r in the fetch
| buffer, linearly interpolated.  The renderer advances the voice by every
| frame it fetches, so nothing fetched may be dropped: the frames from the
| next start's floor onward (one or two) are carried to the next chunk, and
| p stays in [0,1) relative to the first carried frame.  A voice fresh from
| poly_voice_trigger has no carried frames and p = 0; a voice that moves
| slots takes its phase and carried frames along.
.render_voice:
        lea     -36(%sp),%sp
        movem.l %d2-%d7/%a2-%a4,(%sp)
        move.l  %d2,%d4
        lsl.l   #2,%d4
        add.l   %d3,%d4                   | d4 = voice index
        move.l  %d3,%d1
        moveq   #9,%d0
        lsl.l   %d0,%d1
        lea     poly_scratch(%pc),%a3
        adda.l  %d1,%a3                   | a3 = output
.re_active:
| r16 = inc_voice * 65536 / d7, with 32-bit divides: both >> 8, then the
| integer part and two 8-bit fraction digits.  No increment yet: r = 1.
        lea     poly_voice_inc(%pc),%a0
        move.l  (%a0,%d4.l*4),%d0
        bne.s   .re_inc
        move.l  %d7,%d0
.re_inc:
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
| At exactly the DSP's rate with nothing carried and no phase (a note at the
| sample's own pitch, from its start), the frames ARE the output: fetch them
| straight into place.
        cmpi.l  #0x10000,%d6
        bne.s   .re_resample
        cmpi.l  #63,%d5
        bhi.s   .re_resample
        lea     poly_rs_carry(%pc),%a0
        tst.l   (%a0,%d4.l*4)
        bne.s   .re_resample
        lea     poly_rs_phase(%pc),%a0
        tst.l   (%a0,%d4.l*4)
        bne.s   .re_resample
        movea.l %a3,%a4
        move.l  %d5,%d0
        bsr.w   .render_count
        bra.w   .re_out
.re_resample:

| Carried frames go to the front of the fetch buffer.
        lea     poly_fetch(%pc),%a4
        lea     poly_rs_carry(%pc),%a0
        move.l  (%a0,%d4.l*4),%d2         | carried frames c (0..2)
        move.l  %d4,%d0
        lsl.l   #4,%d0                    | 16 bytes of history per voice
        lea     poly_rs_hist(%pc),%a0
        adda.l  %d0,%a0
        move.l  (%a0)+,(%a4)
        move.l  (%a0)+,4(%a4)
        move.l  (%a0)+,8(%a4)
        move.l  (%a0),12(%a4)

| last = max(floor(p+(N-1)r)+1, floor(p+N*r)); frames needed = last+1.
        lea     poly_rs_phase(%pc),%a0
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
        lea     poly_rs_phase(%pc),%a0
        move.l  %d2,(%a0,%d4.l*4)
        move.l  %a2,%d1
        sub.l   %d0,%d1                   | frames carried (1 or 2)
        cmpi.l  #2,%d1
        bls.s   .re_carry_n
        moveq   #2,%d1
.re_carry_n:
        lea     poly_rs_carry(%pc),%a0
        move.l  %d1,(%a0,%d4.l*4)
        lsl.l   #3,%d0
        lea     (%a4,%d0.l),%a1           | &buf[k]
        move.l  %d4,%d0
        lsl.l   #4,%d0
        lea     poly_rs_hist(%pc),%a0
        adda.l  %d0,%a0
        move.l  (%a1)+,(%a0)+
        move.l  (%a1)+,(%a0)+
        move.l  (%a1)+,(%a0)+
        move.l  (%a1),(%a0)
.re_out:
        movem.l (%sp),%d2-%d7/%a2-%a4
        lea     36(%sp),%sp
        rts

| ---------------------------------------------------------------------------
| Per-voice AMP.  Stock runs ONE amp envelope per track, on the DSP, after
| the track's audio is summed: with POLY every new key restarted it (the
| held voices dipped to zero), a released key could only be cut, and REL
| applied only when the last key was up.  Each voice now carries its own
| envelope, applied in the mix; the laws were measured from stock FLEX under
| octemu (25 Sep 2026, STATUS.md): attack linear over 3.39 ms * 2^(ATK/8.39),
| release exponential with time constant 0.337 ms * 2^(REL/8.64), REL 127 =
| INF; hold for HOLD from stock's own table (0x400a9690, tempo-scaled when
| SYNC is on), HOLD 127 = INF; release at whichever comes first, the hold's
| end or the key coming up.  Levels are Q30 (ENV_FULL = unity), gains Q13.
        .equ    ENV_ATTACK, 1
        .equ    ENV_HOLD, 2
        .equ    ENV_RELEASE, 3
        .equ    ENV_FULL, 0x40000000
        .equ    ENV_FLOOR, 0x20000          | -78 dB: the release has ended
        .equ    ENV_UNITY, 8192
        .equ    LIM_UNITY, 0x10000
        .equ    LIM_FS, 0x10000000          | full scale of the Q28 sum
        .equ    TEMPO24, 0x8000181c
        .equ    HOLD_TABLE, 0x400a9690

| One 16-sample frame of the four envelopes of track d2 (slot 0 = the
| primary, 1..3 = the extensions).  Out: d6 = mask of active voices,
| poly_g0 / poly_g1 = each voice's gain at the chunk's start and end,
| poly_sounding[t].  Preserves d2/d5/a5; clobbers d0/d1/d3/d4/a0/a1/a3.
.env_track:
        moveq   #0,%d6
        move.l  %d2,%d0
        lsl.l   #2,%d0
        lea     poly_amp(%pc),%a3
        adda.l  %d0,%a3                   | ATK HOLD REL SYNC
        move.l  #2880,%d4                 | the hold timer's base (stock 0x40004c44)
        tst.b   3(%a3)
        beq.s   .et_base
        move.l  (TEMPO24).l,%d4
.et_base:
        lsl.l   #4,%d4                    | per 16-sample frame
        moveq   #0,%d3
.et_slot:
        tst.l   %d3
        bne.s   .et_ext
        move.l  %d2,%d0
        move.l  #VOICE_SIZE,%d1
        mulu.l  %d1,%d0
        lea     (VOICES).l,%a0
        adda.l  %d0,%a0
        bra.s   .et_record
.et_ext:
        move.l  %d2,%d0
        add.l   %d2,%d0
        add.l   %d2,%d0
        add.l   %d3,%d0
        subq.l  #1,%d0
        move.l  #VOICE_SIZE,%d1
        mulu.l  %d1,%d0
        lea     poly_extra_voices(%pc),%a0
        adda.l  %d0,%a0
.et_record:
        move.l  %d2,%d0
        lsl.l   #2,%d0
        add.l   %d3,%d0                   | voice index
        lea     poly_env_gain(%pc),%a1
        mvz.w   (%a1,%d0.l*2),%d1
        lea     poly_g0(%pc),%a1
        move.w  %d1,(%a1,%d3.l*2)
        moveq   #0,%d1
        tst.b   (%a0)
        beq.s   .et_idle
        bset    %d3,%d6
        bsr.w   .env_voice                | d1 = gain at the chunk's end
        bra.s   .et_gain
.et_idle:
        bsr.w   .env_clear
.et_gain:
        lea     poly_g1(%pc),%a1
        move.w  %d1,(%a1,%d3.l*2)
        addq.l  #1,%d3
        moveq   #4,%d0
        cmp.l   %d0,%d3
        bcs.s   .et_slot
        tst.l   %d6
        sne     %d0
        lea     poly_sounding(%pc),%a1
        move.b  %d0,(%a1,%d2.l)
        rts

| One frame of voice d0's envelope (active; a3 = the track's ATK HOLD REL
| SYNC, d4 = the hold timer's step).  Returns d1 = its gain at the chunk's
| end (Q13).  Preserves every other register.
.env_voice:
        lea     -24(%sp),%sp
        movem.l %d2-%d3/%d5-%d7/%a1,(%sp)
        lea     poly_env_level(%pc),%a1
        move.l  (%a1,%d0.l*4),%d2         | level
        lea     poly_env_stage(%pc),%a1
        mvz.b   (%a1,%d0.l),%d3           | stage
        bne.s   .ev_staged
        moveq   #ENV_ATTACK,%d3           | a voice with no envelope yet starts one
        moveq   #0,%d2
        lea     poly_env_timer(%pc),%a1
        clr.l   (%a1,%d0.l*4)
.ev_staged:
        cmpi.l  #ENV_RELEASE,%d3
        beq.s   .ev_release
        lea     poly_env_timer(%pc),%a1   | the hold runs from the trigger
        move.l  (%a1,%d0.l*4),%d5
        add.l   %d4,%d5
        move.l  %d5,(%a1,%d0.l*4)
        cmpi.l  #ENV_ATTACK,%d3
        bne.s   .ev_hold
        mvz.b   (%a3),%d6                 | ATK
        lea     poly_atk_step(%pc),%a1
        add.l   (%a1,%d6.l*4),%d2
        cmpi.l  #ENV_FULL,%d2
        bcs.s   .ev_hold
        move.l  #ENV_FULL,%d2
        moveq   #ENV_HOLD,%d3
.ev_hold:
        mvz.b   1(%a3),%d6                | HOLD; 127 = INF, until the key is up
        cmpi.l  #127,%d6
        bcc.s   .ev_store
        lea     (HOLD_TABLE).l,%a1
        cmp.l   (%a1,%d6.l*4),%d5
        bcs.s   .ev_store
        moveq   #ENV_RELEASE,%d3          | held for HOLD: release, key or not
        bra.s   .ev_store
.ev_release:
        mvz.b   2(%a3),%d6                | REL; 127 = INF, the level stays
        lea     poly_rel_fall(%pc),%a1
        move.l  (%a1,%d6.l*4),%d6         | the fall per frame, Q32
        beq.s   .ev_store
| level -= level * fall >> 32, in 16-bit products (level = lh*2^15 + ll,
| fall = fh*2^16 + fl): lh*fh/2 + lh*fl/2^17 + ll*fh/2^16.
        move.l  %d2,%d5
        lsr.l   #8,%d5
        lsr.l   #7,%d5                    | lh
        move.l  %d2,%d7
        andi.l  #0x7fff,%d7               | ll
        move.l  %d6,%d1
        swap    %d1                       | fh
        andi.l  #0xffff,%d6               | fl
        mulu.w  %d5,%d6
        lsr.l   #8,%d6
        lsr.l   #8,%d6
        lsr.l   #1,%d6
        mulu.w  %d1,%d7
        clr.w   %d7
        swap    %d7
        mulu.w  %d1,%d5
        lsr.l   #1,%d5
        add.l   %d6,%d5
        add.l   %d7,%d5
        sub.l   %d5,%d2
        cmpi.l  #ENV_FLOOR,%d2
        bcc.s   .ev_store
        moveq   #0,%d2                    | ended: .env_reap stops the voice
.ev_store:
        lea     poly_env_level(%pc),%a1
        move.l  %d2,(%a1,%d0.l*4)
        lea     poly_env_stage(%pc),%a1
        move.b  %d3,(%a1,%d0.l)
        move.l  %d2,%d1
        moveq   #17,%d2
        lsr.l   %d2,%d1                   | Q30 -> Q13
        lea     poly_env_gain(%pc),%a1
        move.w  %d1,(%a1,%d0.l*2)
        movem.l (%sp),%d2-%d3/%d5-%d7/%a1
        lea     24(%sp),%sp
        rts

| Voice d0 has no envelope.  Clobbers a1.
.env_clear:
        lea     poly_env_level(%pc),%a1
        clr.l   (%a1,%d0.l*4)
        lea     poly_env_timer(%pc),%a1
        clr.l   (%a1,%d0.l*4)
        lea     poly_env_gain(%pc),%a1
        clr.w   (%a1,%d0.l*2)
        lea     poly_env_stage(%pc),%a1
        clr.b   (%a1,%d0.l)
        rts

| Voice d0's key is up: its envelope releases from where it is.  Called with
| interrupts masked.  Clobbers d1/a1.
.env_release:
        lea     poly_env_stage(%pc),%a1
        mvz.b   (%a1,%d0.l),%d1
        beq.s   .enr_done                 | idle
        moveq   #ENV_RELEASE,%d1
        move.b  %d1,(%a1,%d0.l)
.enr_done:
        rts

| Mix the active voices of track d2 (mask d6, gains poly_g0 / poly_g1, d5
| frames) into the output buffer at 40(a5): each voice at its own envelope
| gain, then a limiter that turns the sum down only where it would clip.
| (Images <= 94 divided the sum by 2 or 4 by voice count, so a held chord
| jumped 6 dB every time a voice started or stopped.)  Clobbers d0/d1/d3/
| d4/d6/d7/a0-a2.
.mix:
| One voice, held at unity, the limiter at rest: its frames are the output.
        move.l  %d6,%d0
        subq.l  #1,%d0
        and.l   %d6,%d0
        bne.s   .mx_full                  | more than one voice
        moveq   #0,%d3
.mx_one:
        btst    %d3,%d6
        bne.s   .mx_one_got
        addq.l  #1,%d3
        bra.s   .mx_one
.mx_one_got:
        lea     poly_g0(%pc),%a1
        mvz.w   (%a1,%d3.l*2),%d0
        cmpi.l  #ENV_UNITY,%d0
        bne.s   .mx_full
        lea     poly_g1(%pc),%a1
        mvz.w   (%a1,%d3.l*2),%d0
        cmpi.l  #ENV_UNITY,%d0
        bne.s   .mx_full
        lea     poly_lim(%pc),%a1
        move.l  (%a1,%d2.l*4),%d0
        cmpi.l  #LIM_UNITY,%d0
        bne.s   .mx_full
        move.l  %d3,%d0
        moveq   #9,%d1
        lsl.l   %d1,%d0
        lea     poly_scratch(%pc),%a0
        adda.l  %d0,%a0
        movea.l 40(%a5),%a1
        move.l  %d5,%d7
        add.l   %d7,%d7
        subq.l  #1,%d7
.mx_copy:
        move.l  (%a0)+,(%a1)+
        subq.l  #1,%d7
        bpl.s   .mx_copy
        rts
.mx_full:
        lea     poly_sum(%pc),%a0
        move.l  %d5,%d0
        add.l   %d0,%d0
        subq.l  #1,%d0
.mx_clear:
        clr.l   (%a0)+
        subq.l  #1,%d0
        bpl.s   .mx_clear
        moveq   #0,%d3
.mx_voice:
        btst    %d3,%d6
        beq.w   .mx_next
        move.l  %d3,%d0
        moveq   #9,%d1
        lsl.l   %d1,%d0
        lea     poly_scratch(%pc),%a0
        adda.l  %d0,%a0
.mx_src:
        lea     poly_g0(%pc),%a1
        mvz.w   (%a1,%d3.l*2),%d0
        lea     poly_g1(%pc),%a1
        mvz.w   (%a1,%d3.l*2),%d1
        move.l  %d0,%d4
        or.l    %d1,%d4
        beq.w   .mx_next                  | silent this chunk
        cmpi.l  #ENV_UNITY,%d0            | held at unity: no multiply
        bne.s   .mx_gain
        cmp.l   %d0,%d1
        bne.s   .mx_gain
        lea     poly_sum(%pc),%a1
        move.l  %d5,%d7
        add.l   %d7,%d7
        subq.l  #1,%d7
.mx_unity:
        move.l  (%a0)+,%d4
        asr.l   #3,%d4                    | (PCM << 16) >> 14 * 8192 >> 2
        add.l   %d4,(%a1)+
        subq.l  #1,%d7
        bpl.s   .mx_unity
        bra.w   .mx_next
.mx_gain:
        sub.l   %d0,%d1
        swap    %d1
        clr.w   %d1
        divs.l  %d5,%d1                   | gain step per frame, Q16.16
        swap    %d0
        clr.w   %d0                       | gain, Q16.16
        lea     poly_sum(%pc),%a1
        lea     -12(%sp),%sp
        movem.l %d2-%d3/%d6,(%sp)
        moveq   #14,%d4
        move.l  %d5,%d7
        subq.l  #1,%d7
.mx_frame:
        move.l  %d0,%d6
        swap    %d6
        ext.l   %d6                       | this frame's gain, Q13
        move.l  (%a0)+,%d2                | left: sample (PCM << 16) >> 14 * gain
        asr.l   %d4,%d2
        muls.l  %d6,%d2
        asr.l   #2,%d2                    | Q28
        add.l   %d2,(%a1)+
        move.l  (%a0)+,%d2                | right
        asr.l   %d4,%d2
        muls.l  %d6,%d2
        asr.l   #2,%d2
        add.l   %d2,(%a1)+
        add.l   %d1,%d0
        subq.l  #1,%d7
        bpl.s   .mx_frame
        movem.l (%sp),%d2-%d3/%d6
        lea     12(%sp),%sp
.mx_next:
        addq.l  #1,%d3
        moveq   #4,%d0
        cmp.l   %d0,%d3
        bcs.w   .mx_voice

| The limiter: recover toward unity (time constant ~23 ms), never above the
| gain that keeps this chunk's peak inside full scale.
        lea     poly_sum(%pc),%a0
        move.l  %d5,%d7
        add.l   %d7,%d7
        subq.l  #1,%d7
        moveq   #0,%d0                    | peak
.mx_peak:
        move.l  (%a0)+,%d1
        bpl.s   .mx_abs
        neg.l   %d1
.mx_abs:
        cmp.l   %d0,%d1
        bls.s   .mx_peak_next
        move.l  %d1,%d0
.mx_peak_next:
        subq.l  #1,%d7
        bpl.s   .mx_peak
        lea     poly_lim(%pc),%a0
        move.l  (%a0,%d2.l*4),%d6         | the gain the last chunk ended at
        move.l  %d6,%d1
        move.l  #LIM_UNITY,%d3
        sub.l   %d1,%d3
        asr.l   #6,%d3
        add.l   %d3,%d1                   | recovering toward unity
        cmpi.l  #LIM_FS,%d0
        bls.s   .mx_lim
        lsr.l   #8,%d0
        lsr.l   #5,%d0
        move.l  #0x7fffffff,%d3           | 2^31 / (peak >> 13) = FS / peak, Q16
        divu.l  %d0,%d3
        cmp.l   %d1,%d3
        bcc.s   .mx_lim
        move.l  %d3,%d1
.mx_lim:
        move.l  %d1,(%a0,%d2.l*4)         | this chunk ends at d1

        lea     poly_sum(%pc),%a0
        movea.l 40(%a5),%a1
        move.l  %d5,%d7
        subq.l  #1,%d7
        move.l  #LIM_FS-1,%d3
        move.l  #-LIM_FS,%d4
        cmpi.l  #LIM_UNITY,%d6            | unity at both ends: no multiply
        bne.s   .mx_ramp
        cmpi.l  #LIM_UNITY,%d1
        bne.s   .mx_ramp
        add.l   %d7,%d7
        addq.l  #1,%d7
.mx_out:
        move.l  (%a0)+,%d0
        cmp.l   %d3,%d0
        ble.s   .mx_hi
        move.l  %d3,%d0
.mx_hi:
        cmp.l   %d4,%d0
        bge.s   .mx_lo
        move.l  %d4,%d0
.mx_lo:
        lsl.l   #3,%d0                    | Q28 -> PCM << 16
        move.l  %d0,(%a1)+
        subq.l  #1,%d7
        bpl.s   .mx_out
        rts
| The limiter's gain moves linearly across the chunk (a gain that stepped
| at each 16-sample boundary clicked while a chord was being held down).
.mx_ramp:
        sub.l   %d6,%d1
        divs.l  %d5,%d1                   | per-frame step, Q16
        lea     -8(%sp),%sp
        movem.l %d2/%d5,(%sp)
.mx_rframe:
        move.l  %d6,%d5
        lsr.l   #6,%d5                    | this frame's gain, Q10
        move.l  (%a0)+,%d0
        asr.l   #8,%d0
        asr.l   #2,%d0
        muls.l  %d5,%d0
        cmp.l   %d3,%d0
        ble.s   .mx_rhi
        move.l  %d3,%d0
.mx_rhi:
        cmp.l   %d4,%d0
        bge.s   .mx_rlo
        move.l  %d4,%d0
.mx_rlo:
        lsl.l   #3,%d0
        move.l  %d0,(%a1)+
        move.l  (%a0)+,%d0
        asr.l   #8,%d0
        asr.l   #2,%d0
        muls.l  %d5,%d0
        cmp.l   %d3,%d0
        ble.s   .mx_rhi2
        move.l  %d3,%d0
.mx_rhi2:
        cmp.l   %d4,%d0
        bge.s   .mx_rlo2
        move.l  %d4,%d0
.mx_rlo2:
        lsl.l   #3,%d0
        move.l  %d0,(%a1)+
        add.l   %d1,%d6
        subq.l  #1,%d7
        bpl.s   .mx_rframe
        movem.l (%sp),%d2/%d5
        lea     8(%sp),%sp
        rts

| Voices of track d2 whose release has ended stop: an extension by clearing
| its active byte, the primary through stock's stop (0x40006820, which stock
| also calls from the frame interrupt, 0x4000d45a; the selector is 0 here so
| poly_stop_voice passes it through).  Clobbers d0/d1/d3/a0/a1.
.env_reap:
        moveq   #0,%d3
.er_slot:
        move.l  %d2,%d0
        lsl.l   #2,%d0
        add.l   %d3,%d0
        lea     poly_env_stage(%pc),%a1
        mvz.b   (%a1,%d0.l),%d1
        cmpi.l  #ENV_RELEASE,%d1
        bne.s   .er_next
        lea     poly_env_level(%pc),%a1
        tst.l   (%a1,%d0.l*4)
        bne.s   .er_next
        bsr.w   .env_clear
        tst.l   %d3
        bne.s   .er_ext
        move.l  %d2,-(%sp)
        jsr     (STOCK_STOP).l
        addq.l  #4,%sp
        lea     poly_primary_note(%pc),%a1
        moveq   #-1,%d0
        move.b  %d0,(%a1,%d2.l)
        bra.s   .er_next
.er_ext:
        move.l  %d2,%d0
        add.l   %d2,%d0
        add.l   %d2,%d0
        add.l   %d3,%d0
        subq.l  #1,%d0                    | flat extension index
        lea     poly_extra_note(%pc),%a1
        moveq   #-1,%d1
        move.b  %d1,(%a1,%d0.l)
        move.l  #VOICE_SIZE,%d1
        mulu.l  %d1,%d0
        lea     poly_extra_voices(%pc),%a1
        clr.b   (%a1,%d0.l)
.er_next:
        addq.l  #1,%d3
        moveq   #4,%d0
        cmp.l   %d0,%d3
        bcs.s   .er_slot
        rts

| Detour at 0x40004d66, the end of the per-track pass of the DSP record's
| command-word builder (0x40004bd4: d4 = track, a2 = the track's record, a1
| = its command word).  A POLY track's amp envelopes run per voice
| (.env_track), so the DSP's single envelope must stay open: the record's ATK
| goes to 0, HOLD to INF and the AMP mode to ANLG (a retrigger at full level
| stays at full; RTRG, the default, restarted every held voice from zero on
| each new key), and while any voice sounds the gate bit stays set and the
| trigger, its sub-block offset and the release bit are dropped: a trigger
| restarts the DSP's handling of the whole track (every sounding voice
| stepped at each new key, octemu 25 Sep 2026), so an FX envelope now
| retriggers only on a note that starts from silence.  The real values are
| kept for .env_track first.
poly_amp_hook:
        movea.w 54(%sp),%a0               | displaced
        move.w  %a0,62(%a2)               | displaced
        lea     -12(%sp),%sp
        movem.l %d0-%d1/%a0,(%sp)
        move.l  %d4,%d0
        bsr.w   poly_is_track             | d1/a0 scratch
        tst.l   %d0
        beq.s   .pah_done
        move.l  %d4,%d0
        lsl.l   #2,%d0
        lea     poly_amp(%pc),%a0
        adda.l  %d0,%a0
        move.b  (%a2),(%a0)+              | ATK
        move.b  2(%a2),(%a0)+             | HOLD
        move.b  4(%a2),(%a0)+             | REL
        move.b  0x2b(%a2),(%a0)           | SYNC
        clr.w   (%a2)
        move.l  #0x7f00,%d0
        move.w  %d0,2(%a2)
        clr.b   0x2a(%a2)
        lea     poly_sounding(%pc),%a0
        tst.b   (%a0,%d4.l)
        beq.s   .pah_done
        mvz.w   (%a1),%d0
        andi.l  #0xff40,%d0               | no trigger, offset or release
        ori.l   #0x40,%d0                 | gate held
        move.w  %d0,(%a1)
.pah_done:
        movem.l (%sp),%d0-%d1/%a0
        lea     12(%sp),%sp
        jmp     (0x40004d6e).l

| POLY keeps its own octave, -2..+2 (0 = stock's octave 0), in poly_octave;
| stock's octave 0x460d16fc stays stock's (0/1): POLY images <= 94 walked it
| 0..2 and a stock track left at octave 2 played only TRIG1.  Detour at
| 0x400449b8, where the keyboard draw prints the octave: a POLY track shows
| its own, signed.
poly_oct_number:
        mvz.b   (CURRENT_TRACK).l,%d0
        bsr.w   poly_is_track             | d1/a0 are dead here
        tst.l   %d0
        beq.s   .pon_stock
        mvs.b   poly_octave(%pc),%d0
        jmp     (0x400449be).l
.pon_stock:
        move.l  (STOCK_OCTAVE).l,%d0
        jmp     (0x400449be).l

| Detour at 0x4004d442, where the chromatic LED routine picks the octave
| lamp: four lamps for five octaves, -2 and -1 share the first.  (Stock
| indexes two 8-entry stack arrays by 2*octave: any value above 3 smashed
| its stack, image 92.)
poly_oct_led:
        mvz.b   (CURRENT_TRACK).l,%d0
        bsr.w   poly_is_track             | d1/a0 are dead here
        tst.l   %d0
        beq.s   .pol_stock
        mvs.b   poly_octave(%pc),%d0
        addq.l  #1,%d0
        bpl.s   .pol_lamp
        moveq   #0,%d0
.pol_lamp:
        jmp     (0x4004d47e).l
.pol_stock:
        move.l  (STOCK_OCTAVE).l,%d0
        jmp     (0x4004d47e).l

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

| Stock audio chromatic mode toggles only octave 0/1.  A POLY track walks its
| own octave, poly_octave, -2..+2 (FUNC+LEFT / FUNC+RIGHT stop at the ends);
| stock's 0x460d16fc is left to stock tracks (images <= 94 walked it 0..2,
| and a stock track left at 2 played only TRIG1).  Keys above +24 semitones
| from the sample still fold down an octave: the stock caller fetches at most
| 63 source frames per 16-sample chunk (poly_increment_shift).
        .equ    POLY_OCTAVE_MIN, -2
        .equ    POLY_OCTAVE_MAX, 2
poly_octave_button:
        move.l  %d0,-(%sp)
        mvz.b   (CURRENT_TRACK).l,%d0
        bsr.w   poly_is_track
        tst.l   %d0
        beq.s   .pob_stock
        mvs.b   poly_octave(%pc),%d0
        cmpi.l  #52,%d2                  | down button
        bne.s   .pob_up
        subq.l  #1,%d0
        moveq   #POLY_OCTAVE_MIN,%d1
        cmp.l   %d1,%d0
        bge.s   .pob_store
        move.l  %d1,%d0
        bra.s   .pob_store
.pob_up:
        addq.l  #1,%d0
        moveq   #POLY_OCTAVE_MAX,%d1
        cmp.l   %d1,%d0
        ble.s   .pob_store
        move.l  %d1,%d0
.pob_store:
        move.b  %d0,poly_octave
        move.l  (%sp)+,%d0
        jmp     (CONTINUE_OCTAVE_BUTTON).l
.pob_stock:
        move.l  (%sp)+,%d0
        moveq   #1,%d2
        eor.l   %d2,(STOCK_OCTAVE).l
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

| ---------------------------------------------------------------------------
| Keys.  A POLY track keeps the set of keys the player holds (panel keys and
| MIDI notes, up to HOLD_SLOTS), queues presses that arrive while stock's
| one-command mailbox is busy, and addresses each release to the voices the
| key owns.  Every change runs with interrupts masked, stock's own idiom
| (0x40006844): the frame ISR drains the queue and promotes the armed key,
| and the MIDI task (priority 6) can preempt the UI task (3) mid-update.
        .equ    HOLD_SLOTS, 8
        .equ    CMD_TRIGGER, 29           | stock's chromatic trigger, 0x1d
        .equ    CMD_RELEASE, 0x40
        .equ    NOTE_OUT, 0x4003f3a8      | AUDIO NOTE OUT: (track, note, velocity)
        .equ    POLY_KEY_ZERO, 36         | the panel key that plays the sample's pitch
        .equ    NOTE_OUT_BASE, 84-POLY_KEY_ZERO | key K goes out as MIDI note K + 48 (84 = unison, as stock)
        .equ    TRIG_KEYS, 17             | trigs 1-16 and the keyboard's 17th key
        .equ    STOCK_OCTAVE, 0x460d16fc
        .equ    CURRENT_TRACK, 0x100b14cc
        .equ    NOTE_CONFIG, 0x8000004c   | bit 0 INT (play the track), bit 1 EXT
        .equ    NOTE_OUT_HOLD, 0x46c7dd26 | stock sends no press note while set
        .equ    STOCK_HELD, 0x460d171d    | stock's held panel key per track, key + 1

| Detour at 0x4004fb94, the panel chromatic key handler (track, key, edge).
| Stock owns one held key per track and one pending command, so a second
| press released the first and two presses in one frame collapsed into one.
| POLY presses and releases each key on its own.  The caller's key is the
| trig plus 12 * stock's octave (0x40050254); POLY takes the trig and adds its
| own octave: key K = trig + 12 * (poly_octave + 2), K = POLY_KEY_ZERO plays
| the sample's own pitch.  Each trig remembers the key it pressed, so its
| release finds it whatever the octave is by then.  STATIC and FLEX replay
| the exact displaced prologue.
poly_chromatic_key:
        lea     -16(%sp),%sp
        movem.l %d2-%d4/%a2,(%sp)
        move.l  20(%sp),%d0              | track
        bsr.w   poly_is_track
        tst.l   %d0
        beq.w   .pck_stock
        move.l  (STOCK_OCTAVE).l,%d0
        move.l  %d0,%d1
        lsl.l   #3,%d0
        lsl.l   #2,%d1
        add.l   %d1,%d0
        move.l  24(%sp),%d4
        sub.l   %d0,%d4                  | the trig, 0..16
        cmpi.l  #TRIG_KEYS-1,%d4
        bhi.w   .pck_stock
        move.l  20(%sp),%d0
        move.l  %d0,%d1
        lsl.l   #4,%d1
        add.l   %d0,%d1                  | track * 17
        add.l   %d4,%d1
        lea     poly_trig_key(%pc),%a2
        adda.l  %d1,%a2                  | the key this trig pressed

        move.l  28(%sp),%d0              | edge: 1 press, 0 release
        beq.s   .pck_release
        cmpi.l  #1,%d0
        bne.w   .pck_stock
        mvs.b   poly_octave(%pc),%d0
        addq.l  #2,%d0
        move.l  %d0,%d1
        lsl.l   #3,%d0
        lsl.l   #2,%d1
        add.l   %d1,%d0
        add.l   %d4,%d0
        move.l  %d0,%d3                  | K
        move.b  %d3,(%a2)
        moveq   #127,%d2
        mvs.b   (NOTE_CONFIG).l,%d0
        btst    #0,%d0
        beq.s   .pck_note_out            | INT off: stock plays nothing, sends only
        move.l  20(%sp),%d0
        move.l  %d3,%d1
        bsr.w   poly_press_key
        tst.l   (NOTE_OUT_HOLD).l
        bne.s   .pck_done
        bra.s   .pck_note_out
.pck_release:
        mvz.b   (%a2),%d3
        moveq   #-1,%d0
        move.b  %d0,(%a2)
        cmpi.l  #0xff,%d3
        beq.s   .pck_done                | nothing pressed through POLY
        move.l  20(%sp),%d0
        move.l  %d3,%d1
        bsr.w   poly_release_key
        moveq   #0,%d2
.pck_note_out:
        move.l  %d2,-(%sp)               | velocity
        move.l  %d3,%d0
        addi.l  #NOTE_OUT_BASE,%d0       | the MIDI note stock would send for it
        move.l  %d0,-(%sp)
        move.l  28(%sp),-(%sp)           | track
        jsr     (NOTE_OUT).l
        lea     12(%sp),%sp
.pck_done:
        moveq   #0,%d0
        movem.l (%sp),%d2-%d4/%a2
        lea     16(%sp),%sp
        rts
.pck_stock:
        movem.l (%sp),%d2-%d4/%a2
        lea     16(%sp),%sp
        lea     -16(%sp),%sp              | replay displaced prologue
        movem.l %d2-%d4/%a2,(%sp)
        jmp     (CONTINUE_CHROMATIC_KEY).l

| Detour at 0x4000e746, MIDI chromatic note-on (notes 72..96), once per
| listening track d2; a3 = the message's note.  Stock writes its trigger and
| PTCH lock straight into the one-command mailbox, so the notes of a chord
| that reach the MIDI task within one frame collapsed into one, and its
| note-off matched only the last note.  POLY presses the note like a panel
| key (owner MIDI_KEY + note) and rejoins stock for the held-note byte, the
| gate bit and the recorder event.
poly_midi_note_on:
        move.l  %d2,%d0
        bsr.w   poly_is_track            | d1/a0 scratch
        tst.l   %d0
        beq.s   .pmon_stock
        mvz.b   (%a3),%d1
        addi.l  #MIDI_KEY,%d1
        move.l  %d2,%d0
        bsr.w   poly_press_key
        jmp     (MIDI_ON_HELD).l
.pmon_stock:
        moveq   #CMD_TRIGGER,%d1          | displaced
        move.l  %d1,(%a5,%d2.l*4)
        mvs.b   (%a3),%d0
        jmp     (CONTINUE_MIDI_ON).l

| Detour at 0x4000dfd4, MIDI chromatic note-off, once per listening track d2;
| a0 = the track's held-note byte (0x400d64c2 + t), a3 = the note, d3 =
| 1 << track.  Stock releases the track only when the note is its one held
| note.  POLY stops the voices this note owns; the gate bit clears (and
| stock's release posts) only when the track holds no key.
poly_midi_note_off:
        move.l  %a0,-(%sp)
        move.l  %d2,%d0
        bsr.w   poly_is_track            | d1/a0 scratch
        movea.l (%sp)+,%a0
        tst.l   %d0
        beq.s   .pmof_stock
        mvz.b   (%a3),%d1
        cmp.b   (%a0),%d1
        bne.s   .pmof_release
        moveq   #-1,%d0
        move.b  %d0,(%a0)                | stock's held-note byte, as stock
.pmof_release:
        addi.l  #MIDI_KEY,%d1
        move.l  %d2,%d0
        move.l  %a0,-(%sp)
        bsr.w   poly_release_key
        movea.l (%sp)+,%a0
        tst.l   %d0
        beq.s   .pmof_next
        move.l  %d3,%d0
        not.l   %d0
        move.b  (MIDI_GATES).l,%d1
        and.l   %d1,%d0
        move.b  %d0,(MIDI_GATES).l
.pmof_next:
        jmp     (MIDI_OFF_NEXT).l
.pmof_stock:
        mvs.b   (%a0),%d1                | displaced compare
        mvs.b   (%a3),%d0
        cmp.l   %d1,%d0
        bne.s   .pmof_next
        jmp     (MIDI_OFF_MATCH).l

| Detour at 0x400437b6: stock's "drop the live-held key" of a chromatic track
| (0x40043728, called by the UI on track and mode changes) looks only at its
| one held-key byte, which POLY never sets, so keys held across a track
| change left their voices ringing.  Release every PANEL key held on a POLY
| track instead, and forget which trig pressed what; MIDI notes stay held,
| as stock leaves them.  d3 = track; d2/a2/a3 are the function's own and
| restored by its exit.
poly_release_held:
        move.l  %d3,%d0
        bsr.w   poly_is_track
        tst.l   %d0
        beq.w   .prh_stock
        moveq   #0,%d2
.prh_slot:
        move.l  %d3,%d0
        lsl.l   #3,%d0
        lea     poly_held(%pc),%a2
        adda.l  %d0,%a2
        mvz.b   (%a2,%d2.l),%d1
        cmpi.l  #PANEL_KEYS,%d1
        bcc.s   .prh_next                | empty, or a MIDI note
        move.l  %d1,%a3
        move.l  %d3,%d0
        bsr.w   poly_release_key
        clr.l   -(%sp)                   | note off, as stock's release does
        move.l  %a3,%d0
        addi.l  #NOTE_OUT_BASE,%d0
        move.l  %d0,-(%sp)
        move.l  %d3,-(%sp)
        jsr     (NOTE_OUT).l
        lea     12(%sp),%sp
.prh_next:
        addq.l  #1,%d2
        cmpi.l  #HOLD_SLOTS,%d2
        bcs.s   .prh_slot
        move.l  %d3,%d0
        move.l  %d0,%d1
        lsl.l   #4,%d1
        add.l   %d0,%d1                  | track * 17
        lea     poly_trig_key(%pc),%a2
        adda.l  %d1,%a2
        moveq   #TRIG_KEYS-1,%d2
        moveq   #-1,%d0
.prh_forget:
        move.b  %d0,(%a2)+
        subq.l  #1,%d2
        bpl.s   .prh_forget
        jmp     (0x400438d2).l           | the function's exit
.prh_stock:
        lea     (STOCK_HELD).l,%a0       | displaced
        jmp     (0x400437bc).l

| d0 = track, d1 = owner key.  Adds the key to the held set and presses it:
| straight into stock's mailbox when that is empty, else queued behind it (up
| to three, one per frame after it).  Clobbers d0/d1.
poly_press_key:
        lea     -24(%sp),%sp
        movem.l %d2-%d5/%a0-%a1,(%sp)
        move.w  %sr,%d5
        move.w  #0x2700,%sr
        move.l  %d0,%d4
        move.l  %d1,%d3
        bsr.w   .hold_add
        lea     (PENDING_COMMANDS).l,%a0
        tst.l   (%a0,%d4.l*4)
        beq.s   .ppk_arm
        lea     poly_chord_count(%pc),%a0
        mvz.b   (%a0,%d4.l),%d2
        cmpi.l  #3,%d2
        bcc.s   .ppk_done                | queue full: the press is dropped
        move.l  %d4,%d0
        add.l   %d4,%d0
        add.l   %d4,%d0                  | track * 3
        add.l   %d2,%d0
        lea     poly_chord_notes(%pc),%a1
        move.b  %d3,(%a1,%d0.l)
        addq.l  #1,%d2
        move.b  %d2,(%a0,%d4.l)
        bra.s   .ppk_done
.ppk_arm:
        bsr.w   .arm_key
.ppk_done:
        move.w  %d5,%sr
        movem.l (%sp),%d2-%d5/%a0-%a1
        lea     24(%sp),%sp
        rts

| d0 = track, d1 = owner key.  Releases the key: a press still queued never
| plays, a press armed but not yet taken is withdrawn, every voice the key
| owns stops, and the key leaves the held set.  When that was the track's
| last held key, posts stock's release (bit 6): it ends the live-played state
| that keeps the sequencer off the track (0x4000b52a) and releases the AMP
| envelope -- without it a POLY track never played the sequencer again after
| a chromatic note (octemu, 22 Sep 2026).  Returns d0 = 1 in that case.
poly_release_key:
        lea     -32(%sp),%sp
        movem.l %d2-%d6/%a0-%a2,(%sp)
        move.w  %sr,%d5
        move.w  #0x2700,%sr
        move.l  %d0,%d4
        move.l  %d1,%d3

        lea     poly_chord_count(%pc),%a2
        mvz.b   (%a2,%d4.l),%d2
        move.l  %d4,%d0
        add.l   %d4,%d0
        add.l   %d4,%d0
        lea     poly_chord_notes(%pc),%a1
        adda.l  %d0,%a1                  | this track's queue
        moveq   #0,%d0                   | read
        moveq   #0,%d1                   | write
.prk_queue:
        cmp.l   %d2,%d0
        bcc.s   .prk_queued
        move.b  (%a1,%d0.l),%d6
        cmp.b   %d6,%d3
        beq.s   .prk_queue_next          | dropped
        move.b  %d6,(%a1,%d1.l)
        addq.l  #1,%d1
.prk_queue_next:
        addq.l  #1,%d0
        bra.s   .prk_queue
.prk_queued:
        move.b  %d1,(%a2,%d4.l)

| Armed and still in the mailbox: withdraw it, as stock's note-off does by
| overwriting the command (0x4000dfde).  The next queued press then takes
| the mailbox here, since no consumer will run to re-arm it.
        lea     poly_armed_key(%pc),%a0
        cmp.b   (%a0,%d4.l),%d3
        bne.s   .prk_voices
        lea     (PENDING_COMMANDS).l,%a1
        moveq   #CMD_TRIGGER,%d0
        cmp.l   (%a1,%d4.l*4),%d0
        bne.s   .prk_voices              | mixed with a release: it plays
        clr.l   (%a1,%d4.l*4)
        moveq   #-1,%d1
        move.b  %d1,(%a0,%d4.l)
        lea     poly_armed_shift(%pc),%a0
        clr.b   (%a0,%d4.l)
        move.l  %d4,%d0
        lsl.l   #5,%d0
        lea     (LIVE_LOCKS).l,%a0
        move.b  %d1,(%a0,%d0.l)          | no PTCH lock, as the consumer leaves it
        tst.b   (%a2,%d4.l)
        beq.s   .prk_voices
        move.l  %d3,%d6
        bsr.w   .queue_pop
        bsr.w   .arm_key
        move.l  %d6,%d3

.prk_voices:
        move.l  %d4,%d0
        move.l  %d3,%d1
        bsr.w   poly_release_note
        bsr.w   .hold_find
        tst.l   %d0
        bmi.s   .prk_busy                | was not held
        moveq   #-1,%d1
        move.b  %d1,(%a0,%d0.l)
        moveq   #0,%d0
.prk_any:
        cmp.b   (%a0,%d0.l),%d1
        bne.s   .prk_busy
        addq.l  #1,%d0
        cmpi.l  #HOLD_SLOTS,%d0
        bcs.s   .prk_any
        lea     (PENDING_COMMANDS).l,%a0
        move.l  (%a0,%d4.l*4),%d0
        moveq   #CMD_RELEASE,%d1
        or.l    %d1,%d0
        move.l  %d0,(%a0,%d4.l*4)
        moveq   #1,%d0
        bra.s   .prk_out
.prk_busy:
        moveq   #0,%d0
.prk_out:
        move.w  %d5,%sr
        movem.l (%sp),%d2-%d6/%a0-%a2
        lea     32(%sp),%sp
        rts

| Track d4, owner d3: adds the key to the track's held set (a full set still
| plays the key, it is only not shown).  Clobbers d0/d1/a0.
.hold_add:
        bsr.s   .hold_find
        tst.l   %d0
        bpl.s   .ha_done                 | already held
        moveq   #-1,%d1
        moveq   #0,%d0
.ha_free:
        cmp.b   (%a0,%d0.l),%d1
        beq.s   .ha_store
        addq.l  #1,%d0
        cmpi.l  #HOLD_SLOTS,%d0
        bcs.s   .ha_free
        rts
.ha_store:
        move.b  %d3,(%a0,%d0.l)
.ha_done:
        rts

| a0 = track d4's held set; d0 = the slot holding owner d3, or -1.
.hold_find:
        move.l  %d4,%d0
        lsl.l   #3,%d0
        lea     poly_held(%pc),%a0
        adda.l  %d0,%a0
        moveq   #0,%d0
.hf_loop:
        cmp.b   (%a0,%d0.l),%d3
        beq.s   .hf_done
        addq.l  #1,%d0
        cmpi.l  #HOLD_SLOTS,%d0
        bcs.s   .hf_loop
        moveq   #-1,%d0
.hf_done:
        rts

| Track d4 (queue non-empty): pops the oldest queued owner into d3.
| Clobbers d0-d2/a0-a1.
.queue_pop:
        lea     poly_chord_count(%pc),%a0
        mvz.b   (%a0,%d4.l),%d2
        move.l  %d4,%d0
        add.l   %d4,%d0
        add.l   %d4,%d0
        lea     poly_chord_notes(%pc),%a1
        adda.l  %d0,%a1
        mvz.b   (%a1),%d3
        move.b  1(%a1),%d1
        move.b  %d1,(%a1)
        move.b  2(%a1),%d1
        move.b  %d1,1(%a1)
        subq.l  #1,%d2
        move.b  %d2,(%a0,%d4.l)
        rts

| Track d4, owner d3: arms the key and its octave shift first, then the PTCH
| lock, then stock's trigger command.  The consumer promotes the armed pair
| when it takes the command, so the command is the last write (a frame
| between them would otherwise take a command whose owner is not written
| yet).  Clobbers d0-d2/a0.
.arm_key:
        move.l  %d3,-(%sp)
        move.l  %d3,%d1
        bsr.w   .pck_encode              | d3 = pitch byte, d2 = octave shift
        lea     poly_armed_key(%pc),%a0
        move.b  %d1,(%a0,%d4.l)
        lea     poly_armed_shift(%pc),%a0
        move.b  %d2,(%a0,%d4.l)
        move.l  %d4,%d0
        lsl.l   #5,%d0
        lea     (LIVE_LOCKS).l,%a0
        move.b  %d3,(%a0,%d0.l)
        lea     (PENDING_COMMANDS).l,%a0
        moveq   #CMD_TRIGGER,%d0
        move.l  %d0,(%a0,%d4.l*4)
        move.l  (%sp)+,%d3
        rts

| Owner d1 -> d3 = stock's PTCH lock byte, d2 = octave shift; d0 clobbered.
| A panel key K plays pitch K mod 12 of octave K/12 - 3, K - POLY_KEY_ZERO
| semitones (the shift reaches the increment in poly_increment_shift); a
| MIDI note n takes stock's own MIDI lock, 5n - 100, and no shift.
.pck_encode:
        cmpi.l  #PANEL_KEYS,%d1
        bcs.s   .pcke_panel
        move.l  %d1,%d3
        subi.l  #MIDI_KEY,%d3
        move.l  %d3,%d0
        lsl.l   #2,%d3
        add.l   %d0,%d3
        subi.l  #100,%d3
        moveq   #0,%d2
        rts
.pcke_panel:
        move.l  %d1,%d0
        moveq   #-POLY_KEY_ZERO/12,%d2
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

| Detour at 0x400449f0 in the keyboard draw (0x40044920).  Its audio branch
| boxes each track's held key from the eight bytes at STOCK_HELD (key + 1,
| 0 = none), which POLY never sets: a POLY chord drew no box at all (octemu,
| 25 Sep 2026).  The loop walks poly_kbd instead, HOLD_SLOTS entries per
| track: stock's byte for any other machine, every held key for POLY, placed
| on the keys shown for poly_octave (a MIDI note n as the key that plays it,
| n - 48).  The draw boxes entry v at v - 1 - 12 * stock's octave.
poly_kbd_fill:
        lea     -28(%sp),%sp
        movem.l %d0-%d4/%a0-%a1,(%sp)
        mvs.b   poly_octave(%pc),%d4
        addq.l  #2,%d4
        move.l  (STOCK_OCTAVE).l,%d0
        sub.l   %d0,%d4
        move.l  %d4,%d0
        lsl.l   #3,%d4
        lsl.l   #2,%d0
        add.l   %d0,%d4
        subq.l  #1,%d4                   | v = K - d4
        lea     poly_kbd(%pc),%a1
        moveq   #0,%d2
.pkf_track:
        move.l  %d2,%d0
        bsr.w   poly_is_track            | d1/a0 scratch
        tst.l   %d0
        bne.s   .pkf_poly
        lea     (STOCK_HELD).l,%a0
        move.b  (%a0,%d2.l),(%a1)+
        moveq   #HOLD_SLOTS-2,%d0
.pkf_zero:
        clr.b   (%a1)+
        subq.l  #1,%d0
        bpl.s   .pkf_zero
        bra.s   .pkf_next
.pkf_poly:
        move.l  %d2,%d0
        lsl.l   #3,%d0
        lea     poly_held(%pc),%a0
        adda.l  %d0,%a0
        moveq   #HOLD_SLOTS-1,%d3
.pkf_key:
        mvz.b   (%a0)+,%d0
        cmpi.l  #PANEL_KEYS,%d0
        bcs.s   .pkf_value
        cmpi.l  #0xff,%d0
        beq.s   .pkf_none
        subi.l  #MIDI_KEY+NOTE_OUT_BASE,%d0
.pkf_value:
        sub.l   %d4,%d0
        bra.s   .pkf_store
.pkf_none:
        moveq   #0,%d0
.pkf_store:
        move.b  %d0,(%a1)+
        subq.l  #1,%d3
        bpl.s   .pkf_key
.pkf_next:
        addq.l  #1,%d2
        moveq   #8,%d0
        cmp.l   %d0,%d2
        bcs.s   .pkf_track
        movem.l (%sp),%d0-%d4/%a0-%a1
        lea     28(%sp),%sp
        lea     poly_kbd(%pc),%a2
        jmp     (0x400449f6).l

| Detour at 0x40044b5c: the draw loop's step and end test, over poly_kbd.
poly_kbd_next:
        addq.l  #1,%a2
        cmpa.l  #poly_kbd_end,%a2
        bne.s   1f
        jmp     (0x40044b68).l
1:      jmp     (0x40044abc).l
| d0 = track, d1 = owner key.  Every primary or extension voice the key owns
| enters its release (its own REL), and stops owning the key; .env_reap stops
| the voice when the release has ended.  The same key may own more than one
| stolen slot.  Runs with interrupts masked (poly_release_key).
poly_release_note:
        lea     -20(%sp),%sp
        movem.l %d2-%d4/%a0/%a1,(%sp)
        move.l  %d0,%d2
        move.l  %d1,%d3
        lea     poly_primary_note(%pc),%a0
        cmp.b   (%a0,%d2.l),%d3
        bne.s   .prn_extra
        moveq   #-1,%d0
        move.b  %d0,(%a0,%d2.l)
        move.l  %d2,%d0
        lsl.l   #2,%d0
        bsr.w   .env_release
.prn_extra:
        moveq   #0,%d4
.prn_loop:
        move.l  %d2,%d0
        add.l   %d2,%d0
        add.l   %d2,%d0
        add.l   %d4,%d0                  | flat extension index
        lea     poly_extra_note(%pc),%a0
        cmp.b   (%a0,%d0.l),%d3
        bne.s   .prn_next
        moveq   #-1,%d1
        move.b  %d1,(%a0,%d0.l)
        move.l  %d2,%d0
        lsl.l   #2,%d0
        add.l   %d4,%d0
        addq.l  #1,%d0                   | its voice index
        bsr.w   .env_release
.prn_next:
        addq.l  #1,%d4
        cmpi.l  #EXTRA_PER_TRACK,%d4
        bcs.s   .prn_loop
        movem.l (%sp),%d2-%d4/%a0/%a1
        lea     20(%sp),%sp
        rts

| Called where the frame consumer has finished copying and clearing the live
| lock block.  Re-arm one queued key for the following frame, then replay
| the displaced clear/LEA sequence.  Spreading a chord over adjacent 16-sample
| frames prevents the stock one-command mailbox from collapsing its presses.
| A press (or the re-arm below) leaves its key and octave shift ARMED; the
| consumer taking that track's command promotes them to the pending pair
| the trigger consumes.  One stage was not enough: this hook runs between
| the consumer copying a command and the trigger it causes (measured order:
| here -> initializer -> recompute -> render), so re-arming the next queued
| key overwrote the key of the note about to start -- it played the right
| pitch under the wrong key and octave, and the chord's last voice owned no
| key and never released (octemu, 22 Sep 2026).  d4 = track (stock's).
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
        tst.b   (%a0,%d4.l)
        beq.s   .pcd_done
        bsr.w   .queue_pop                | d3 = the oldest queued key
        bsr.w   .arm_key
.pcd_done:
        movem.l (%sp),%d0-%d3/%a0-%a1
        lea     24(%sp),%sp
        lea     0x46c802a6.l,%a0          | displaced instruction
        jmp     (CONTINUE_CHORD_DEQUEUE).l
| Per-frame envelope rates (16 samples at 44.1 kHz), from the laws measured
| on stock (see Per-voice AMP): the attack's level step (Q30) and the
| release's fall (Q32 fraction of the level); REL 127 = INF falls by 0.
        .balign 4
poly_atk_step:
        .long   0x06d97bba,0x064e70be,0x05ce6c46,0x05588e81,0x04ec095f,0x04881f27,0x042c212a,0x03d76e93
        .long   0x03897351,0x0341a70c,0x02ff8c3f,0x02c2af58,0x028aa5ef,0x02570e0c,0x02278d7b,0x01fbd131
        .long   0x01d38cb6,0x01ae79a6,0x018c572e,0x016ce9a2,0x014ffa0f,0x013555de,0x011cce7d,0x01063908
        .long   0x00f16e05,0x00de4918,0x00cca8ca,0x00bc6e4a,0x00ad7d39,0x009fbb77,0x009310f7,0x00876795
        .long   0x007caaed,0x0072c839,0x0069ae31,0x00614ced,0x005995c4,0x00527b3a,0x004bf0e3,0x0045eb52
        .long   0x00405ffd,0x003b4534,0x0036920a,0x00323e48,0x002e425d,0x002a9752,0x002736bd,0x00241ab7
        .long   0x00213dd0,0x001e9b06,0x001c2dbe,0x0019f1ba,0x0017e312,0x0015fe2d,0x00143fba,0x0012a4af
        .long   0x00112a3b,0x000fcdca,0x000e8cfa,0x000d659b,0x000c55a7,0x000b5b44,0x000a74bc,0x0009a07b
        .long   0x0008dd0f,0x00082922,0x0007837a,0x0006eaf4,0x00065e87,0x0005dd3c,0x00056631,0x0004f897
        .long   0x000493ae,0x000436c6,0x0003e13b,0x00039279,0x000349f5,0x00030732,0x0002c9ba,0x00029121
        .long   0x00025d06,0x00022d0c,0x000200e0,0x0001d835,0x0001b2c4,0x0001904a,0x0001708c,0x00015353
        .long   0x0001386b,0x00011fa5,0x000108d6,0x0000f3d6,0x0000e080,0x0000ceb3,0x0000be4f,0x0000af38
        .long   0x0000a153,0x00009488,0x000088c1,0x00007de9,0x000073ed,0x00006abc,0x00006245,0x00005a7a
        .long   0x0000534e,0x00004cb3,0x0000469e,0x00004104,0x00003bdc,0x0000371d,0x000032be,0x00002eb8
        .long   0x00002b04,0x0000279b,0x00002477,0x00002193,0x00001ee9,0x00001c76,0x00001a34,0x00001820
        .long   0x00001636,0x00001473,0x000012d4,0x00001156,0x00000ff6,0x00000eb2,0x00000d88,0x00000c75
poly_rel_fall:
        .long   0xa8c44f4c,0xa137c60d,0x99ac25a3,0x922d4213,0x8ac5cdfb,0x837f46cd,0x7c61ec8b,0x7574c316
        .long   0x6ebd9b46,0x684121f8,0x6202f378,0x5c05b1d3,0x564b1ce1,0x50d42afc,0x4ba121a2,0x46b1ad52
        .long   0x4204f844,0x3d99bf94,0x396e66c4,0x35810964,0x31cf8aeb,0x2e57a4bb,0x2b16f261,0x280afc40
        .long   0x2531409b,0x22873b53,0x200a6c49,0x1db85caf,0x1b8ea34a,0x198ae7da,0x17aae5ba,0x15ec6dd5
        .long   0x144d680a,0x12cbd417,0x1165ca17,0x10197ab1,0x0ee52ef8,0x0dc7481a,0x0cbe3ed9,0x0bc8a2e9
        .long   0x0ae51a29,0x0a125fd0,0x094f4389,0x089aa882,0x07f38480,0x0758dee7,0x06c9cfc8,0x06457ef9
        .long   0x05cb2324,0x055a00eb,0x04f16a0e,0x0490bc96,0x04376210,0x03e4cecd,0x0398812b,0x035200ed
        .long   0x0310de94,0x02d4b2c9,0x029d1dcc,0x0269c6ea,0x023a5c03,0x020e910d,0x01e61fa7,0x01c0c6b4
        .long   0x019e49f3,0x017e71ac,0x01610a54,0x0145e444,0x012cd36d,0x0115af15,0x01005197,0x00ec982a
        .long   0x00da62a7,0x00c9935a,0x00ba0ed0,0x00abbbb1,0x009e828f,0x00924dc9,0x00870963,0x007ca2e9
        .long   0x00730950,0x006a2cdb,0x0061ff02,0x005a7258,0x00537a79,0x004d0bf5,0x00471c3b,0x0041a18a
        .long   0x003c92e1,0x0037e7f0,0x0033990a,0x002f9f1a,0x002bf396,0x00289073,0x00257020,0x00228d77
        .long   0x001fe3b8,0x001d6e81,0x001b29c7,0x001911cd,0x00172321,0x00155a95,0x0013b537,0x00123053
        .long   0x0010c968,0x000f7e27,0x000e4c6e,0x000d3245,0x000c2ddb,0x000b3d84,0x000a5fb3,0x000992fc
        .long   0x0008d60c,0x000827ac,0x000786bd,0x0006f236,0x00066922,0x0005ea9f,0x000575dc,0x00050a1a
        .long   0x0004a6a6,0x00044add,0x0003f627,0x0003a7f9,0x00035fd1,0x00031d3a,0x0002dfc5,0x00000000

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
poly_held:
        .fill   8*HOLD_SLOTS,1,0xff         | keys held per track, 0xff = none
poly_kbd:
        .zero   8*HOLD_SLOTS                | the keyboard draw's boxes, key + 1
poly_kbd_end:
poly_octave:
        .byte   0                           | POLY's octave, -2..+2
poly_trig_key:
        .fill   8*TRIG_KEYS,1,0xff          | the key each trig pressed, 0xff = none
poly_env_stage:
        .zero   32                          | per voice (track * 4 + slot)
poly_sounding:
        .zero   8
poly_amp:
        .rept   8
        .byte   0,127,127,1                 | ATK HOLD REL SYNC until the DSP record is read
        .endr
        .balign 2
poly_env_gain:
        .zero   64                          | Q13, at the end of the last chunk
poly_g0:
        .zero   8
poly_g1:
        .zero   8
        .balign 4
poly_env_level:
        .zero   128                         | Q30
poly_env_timer:
        .zero   128
poly_lim:
        .rept   8
        .long   LIM_UNITY
        .endr
poly_sum:
        .zero   512                         | 64 frames * 2 * Q28
        .balign 4
poly_voice_inc:
        .zero   128                         | per voice: its own Q26 increment
poly_rs_phase:
        .zero   128                         | per voice: resampler phase, Q16 in [0,1)
poly_rs_carry:
        .zero   128                         | per voice: carried frames (0..2)
poly_rs_hist:
        .zero   512                         | per voice: two carried stereo frames
poly_fetch:
        .zero   (FETCH_FRAMES+2)*8          | one extension's raw source frames
poly_extra_voices:
        .zero   4032                        | 8 tracks * 3 * 168 bytes
poly_scratch:
        .zero   2048                        | 4 voices * (64 frames * 2 * 4 bytes)
| objcopy omits trailing all-zero bytes. Keep all state inside the image.
poly_runtime_end_marker:
        .long   0x504f4c59                  | "POLY"
