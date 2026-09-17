| FORCE FILENAME BPM -- a PERSONALIZE checkbox that makes the BPM in a
| sample's filename the sample's tempo, instead of the stock half/double
| tiebreaker.
|
| Stock (measured, 1.40C): 0x40020ad8(count, name) guesses a POWER-OF-TWO
| beat count from the length, forms three candidate tempos (half, the
| guess, double), prints each as a truncated integer and asks
| strstr(basename, that) -- first hit wins, no hit keeps the middle one.
| So a filename number is only ever a tiebreaker, it can only ever be one
| of three values, and a loop whose length is not a power-of-two number of
| beats can never match its own name.
|
| With the checkbox on, this unit reads the number out of the basename and
| calls the firmware's own explicit-tempo setter 0x40099090 -- the routine
| behind CAL BPM FROM SELECTION -- so every derived field (+0x118
| reciprocal, +0x11c/+0x120, +0x128 "explicitly set") is written by stock
| code with a value we did not have to compute.
|
| Off (the power-on state, since the flag word starts cleared) is stock.

        .equ    FLAG,       0x800000d4      | 0 = off; no stock reference
        .equ    GLYPH_ON,   0x400b5e90      | checked
        .equ    GLYPH_OFF,  0x400b5e8e      | unchecked
        .equ    BASENAME,   0x400204a8      | path -> after the last '/'
        .equ    SET_TEMPO,  0x40099090      | (settings, bpm*24, len)
        .equ    LED_GET,    0x40068c80      | stock LED BRIGHTNESS getter
        .equ    LED_SET,    0x4006907c      | stock LED BRIGHTNESS setter
        .equ    CUR_SAMPLE, 0x460fab50      | the [SAMPLE] block's record

        .text

        .global lbl_force, lbl_led
        .global get_force, get_led, set_force, set_led
        .global load_hook, bpm100_hook, bpm24_hook

| ---------------- the PERSONALIZE row ----------------------------------
| The three stock arrays are relocated with these appended (TableGrow).
| Our row goes in at index 15 and LED BRIGHTNESS moves to 16, because the
| item count is 15 or 16 depending on the hardware-variant word
| 0x46c8d18c: appending would have hidden our row on the variant that
| reads zero. The forwarders keep LED BRIGHTNESS pointing at stock code.

lbl_force:
        .asciz  "FORCE FILENAME BPM"
        .balign 2
lbl_led:
        .asciz  "LED BRIGHTNESS"
        .balign 2

get_force:
        move.l  #GLYPH_ON,%d0
        tst.l   FLAG
        bne.s   .gf_ret
        move.l  #GLYPH_OFF,%d0
.gf_ret:
        rts

get_led:
        jmp     (LED_GET).l

| The menu passes (delta, wrap); delta is 1 for [YES] and +-1 for the
| arrows, so (flag + delta) & 1 is the toggle all three want.
set_force:
        move.l  FLAG,%d0
        add.l   4(%sp),%d0
        andi.l  #1,%d0
        move.l  %d0,FLAG
        rts

set_led:
        jmp     (LED_SET).l

| ---------------- the parser -------------------------------------------
| parse_bpm: %a0 = a sample settings record (its path is at offset 0).
| Returns %d0 = BPM*24 in 720..7200, or 0 when the name carries no usable
| number. Clobbers %d0/%d1/%a0/%a1 only.
|
| The rule: every maximal run of digits in the BASENAME is a candidate,
| optionally followed by '.' or ',' and ONE more digit. The LAST candidate
| whose integer part is 30..300 wins -- the firmware's own tempo clamp, so
| a sample rate, a year or a track number in the name is ignored by the
| same bound the tempo field has. Later wins because the tempo is
| conventionally the tail of a name ("amen_170.wav", "170_amen.wav" both
| land on 170; "loop_01_128.wav" on 128).

parse_bpm:
        lea     -20(%sp),%sp
        movem.l %d2-%d5/%a1,(%sp)        | ColdFire movem: no -(An)
        move.l  %a0,-(%sp)
        jsr     (BASENAME).l
        addq.l  #4,%sp
        movea.l %d0,%a0
        clr.l   %d5                      | best so far
        move.l  %a0,%d0
        beq.w   .pb_done

.pb_scan:
        clr.l   %d0
        move.b  (%a0)+,%d0
        beq.w   .pb_done
        move.l  %d0,%d1
        subi.l  #48,%d1
        cmpi.l  #9,%d1
        bhi.s   .pb_scan                 | not a digit
        move.l  %d1,%d2                  | integer part

.pb_int:
        clr.l   %d0
        move.b  (%a0),%d0
        move.l  %d0,%d1
        subi.l  #48,%d1
        cmpi.l  #9,%d1
        bhi.s   .pb_intdone
        addq.l  #1,%a0
        cmpi.l  #1000000,%d2             | long runs cannot be a tempo;
        bhi.s   .pb_int                  | keep eating, stop accumulating
        move.l  %d2,%d3
        lsl.l   #3,%d2
        add.l   %d3,%d2
        add.l   %d3,%d2                  | *10
        add.l   %d1,%d2
        bra.s   .pb_int

.pb_intdone:
        clr.l   %d4                      | fractional part, in 1/24 BPM
        clr.l   %d0
        move.b  (%a0),%d0
        cmpi.l  #46,%d0                  | '.'
        beq.s   .pb_frac
        cmpi.l  #44,%d0                  | ','
        bne.s   .pb_test
.pb_frac:
        clr.l   %d0
        move.b  1(%a0),%d0
        move.l  %d0,%d1
        subi.l  #48,%d1
        cmpi.l  #9,%d1
        bhi.s   .pb_test                 | a bare separator ends the run
        addq.l  #2,%a0
        lea     .fractab(%pc),%a1
        move.b  (%a1,%d1.l),%d4          | round(tenths * 24 / 10)

.pb_test:
        cmpi.l  #30,%d2
        blt.w   .pb_scan
        cmpi.l  #300,%d2
        bgt.w   .pb_scan
        move.l  %d2,%d5
        add.l   %d2,%d5
        add.l   %d2,%d5                  | *3
        lsl.l   #3,%d5                   | *24
        add.l   %d4,%d5
        bra.w   .pb_scan

.pb_done:
        move.l  %d5,%d0
        movem.l (%sp),%d2-%d5/%a1
        lea     20(%sp),%sp
        rts

.fractab:
        .byte   0, 2, 5, 7, 10, 12, 14, 17, 19, 22
        .balign 2

| ---------------- hook 1: the sample's attributes at load ---------------
| 0x400992ea, inside the per-slot attribute init 0x40099148. Placed AFTER
| the trim words +0x12c/+0x130/+0x134 are stored, because SET_TEMPO reads
| them to derive +0x11c/+0x120. Both stock arms have already written a
| tempo by here: the filename tiebreaker's (samples > 50,000) or the flat
| 120 BPM the short arm hardcodes -- which is the other half of why a
| short loop never takes its name's number.
|
| Live here: %a2 = the settings record, %d5 = min(len, 64) (the length
| argument both stock calls pass), %d1 = about to be set to 1.

load_hook:
        clr.l   1092(%a2)                | displaced
        tst.l   FLAG
        beq.s   .lh_out
        lea     -16(%sp),%sp
        movem.l %d0-%d1/%a0-%a1,(%sp)
        movea.l %a2,%a0
        bsr.w   parse_bpm
        tst.l   %d0
        beq.s   .lh_pop
        move.l  %d5,-(%sp)
        move.l  %d0,-(%sp)
        move.l  %a2,-(%sp)
        jsr     (SET_TEMPO).l
        lea     12(%sp),%sp
.lh_pop:
        movem.l (%sp),%d0-%d1/%a0-%a1
        lea     16(%sp),%sp
.lh_out:
        moveq   #1,%d1                   | displaced
        jmp     (0x400992f0).l

| ---------------- hooks 2 and 3: the project's stored tempo -------------
| The project file's [SAMPLE] block carries BPMx100 and BPMx24 per slot,
| and its parser writes them straight into +0x114. Without these two the
| checkbox would lose to whatever tempo the project saved -- which is the
| case a user actually meets, because a slot that has been in a project
| once is restored from the project, not re-estimated.

bpm100_hook:
        bsr.w   substitute
        move.l  %d0,276(%a2)             | displaced
        movea.l (CUR_SAMPLE).l,%a0       | displaced
        jmp     (0x40086b2e).l

bpm24_hook:
        bsr.w   substitute
        move.l  %d0,276(%a2)             | displaced
        movea.l (CUR_SAMPLE).l,%a0       | displaced
        jmp     (0x40086b6c).l

| %d0 = the tempo the project stored, %a2 = the record. Returns the
| filename's tempo instead when the checkbox is on and the name has one.
substitute:
        tst.l   FLAG
        beq.s   .sb_ret
        lea     -8(%sp),%sp
        movem.l %d1/%a0,(%sp)
        move.l  %d0,-(%sp)               | %d1 is the parser's own scratch
        movea.l %a2,%a0
        bsr.w   parse_bpm
        tst.l   %d0
        bne.s   .sb_keep
        move.l  (%sp),%d0                | no number in the name: stock stands
.sb_keep:
        addq.l  #4,%sp
        movem.l (%sp),%d1/%a0
        lea     8(%sp),%sp
.sb_ret:
        rts
