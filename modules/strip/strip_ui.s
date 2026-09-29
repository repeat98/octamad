| strip_ui -- the MIXER window pages the master strip (MIXER.md section 7).
|
| The layout Jannik locked on 29 Sep 2026: LEFT / RIGHT walk the strips
| (MIXER, MASTER; the returns join later), UP / DOWN walk a strip's slots
| (MASTER: INS 1, INS 2). The MIXER strip is the stock page, untouched but
| for the arrow in its title that says there is a strip to its right.
| MASTER keeps the window's frame and the MUTE band (the mutes and FUNC work
| as on the stock page) and redraws the three boxes above the band as two:
| box 1 the strip's level, MAIN, over a speaker (LEVEL turns it, the stock
| MAIN handler as A on the MIXER page); box 2 the slot, INS 1 or INS 2 down
| its side, and its effect's six page-1 knobs as numbers, named and printed
| by the effect's own descriptor, turned by A-F. A knob writes strip_model
| (strip_xport.s), which core 0 gets in the next frame's record. While the
| MIXER is open the arrow keys are the pages', so the tempo nudge LEFT and
| RIGHT make on the stock page is off (the choice made on 29 Sep 2026).
|
| Three detours, all in the stock MIXER window (0x4007c458..0x4007d478):
|   0x4007d41c  the opener registers the window's input layer: ours (the
|               arrow keys) goes on top, the page is MIXER
|   0x4007d2a4  the close unregisters it: ours come off first
|   0x4007c458  the draw, every caller's (the opener, each stock knob, the
|               mutes, FUNC, ours): the stock draw, then the page's overlay
| Every drawing call is one the stock MIXER draw makes, in the shape it
| makes it: the frame and title (0x400570b8), boxes, fills, dotted rules,
| the MIX box's icon, labels (0x40013904) and values as numbers (0x400479b4
| with flags 6, as MAIN, CUE and the GAINs). Surface coordinates, y up: the
| screen's x is the surface's + 10, its y 63 - the surface's.
|
| The knobs take the stock knobs' step (0x400328e4, with the tails a stock
| page gives its knobs, from the effect's minimum and count) and are held
| inside that range. A slot with no effect, or a knob the effect
| does not draw, turns nothing.
|
| YES on MASTER opens the slot's SETUP (mx_yes, MIXER.md section 14): a
| second window, one level above the MIXER's, drawn and keyed as stock's
| EFFECT 2 SETUP with the strip's list and strip_model where stock reads a
| track's FX2. The MIXER's draw redraws it while it is open, which is how
| the knobs' lift decays (the tick 0x4005213c redraws the open MIXER).

        .equ    WINH,     0x460e7424   | long: the MIXER window's handle, 0 = closed
        .equ    EDITED,   0x460e742a   | long: a knob turned since the open (MIXER's release closes on it)
        .equ    SCRDIRTY, 0x46c7c72c   | long: screen refresh request
        .equ    LPUSH,    0x40031494   | (layer): register an input layer, the last on top
        .equ    LPOP,     0x4003146c   | (layer): unregister it
        .equ    SBODY,    0x4007c460   | the stock draw past its 8-byte prologue
        .equ    TITLE,    0x400570b8   | (handle, str, 0): frame, title band, title
        .equ    T_MIXER,  0x400b73dd   | the stock "MIXER" the opener titles with
        .equ    FONT,     0x400ba876   | the small UI font
        .equ    TEXTF,    0x40013904   | (font, surf, x, y, align, dark, template, fmt, ...)
        .equ    RECT,     0x40012170   | (surf, x1, y1, x2, y2, 1)
        .equ    FILL,     0x40012254   | (surf, x1, y1, x2, y2, colour)
        .equ    DOTTED,   0x40012004   | (surf, x1, y1, x2, y2, 1)
        .equ    ICON,     0x400128a8   | (icon, surf, x, y): y its bottom row
        .equ    VALUE,    0x400479b4   | (x, y, encoder, value, flags, formatter, surf)
        .equ    SIGNED,   0x4003c7a0   | (buf, v): the MIXER's formatter, 64 = +0
        .equ    MAINV,    0x80000035   | byte: MAIN
        .equ    MAINH,    0x4007d03c   | (index, delta): the stock MAIN knob handler
        .equ    ETOUCH,   0x4003256c   | (index): every stock knob handler's first call
        .equ    ESTEP,    0x400328e4   | (index, delta, value) -> the stepped value
        .equ    ETAILS,   0x40032784   | (records, index, 0, min, max): a knob's step, as the opener sets its own
        .equ    DESC2,    0x400d5fdc   | FX descriptor table [id] -> P
        .equ    NAMES,    0x16         | P+: twelve 6-byte names
        .equ    MINS,     0x6a         | P+: twelve u32 minimums
        .equ    COUNTS,   0x9a         | P+: twelve u32 value counts
        .equ    FMTS,     0xca         | P+: twelve formatter pointers, 0 = plain
        .equ    ENABLE,   0x18e        | P+: u32, a nibble a slot 0..7, bit 0 = drawn
        .equ    KRIGHT,   0x21
        .equ    KDOWN,    0x20
        .equ    KUP,      0x33
        .equ    STRIPS,   4            | MIXER, MASTER, RETURN A, RETURN B
| The slot's SETUP window: the calls the stock EFFECT 2 SETUP makes (its
| opener 0x4005996c, draw 0x40037590, keys and knobs in its layer 0x400bc470)
        .equ    WINNEW,   0x4005829c   | (w, h, x, y, level, close) -> handle
        .equ    WINDEL,   0x40055db4   | (&handle): the window gone, the handle 0
        .equ    PCLEAR,   0x400125ac   | (surf, 0, 1): its planes cleared
        .equ    VLINE,    0x40011b94   | (surf, x, y1, y2, 1): a solid vertical line
        .equ    HDOT,     0x40011a58   | (surf, x1, y, x2): a dotted horizontal line
        .equ    TEXT,     0x40012bd8   | (font, surf, x, y, -1, str)
        .equ    LINIT,    0x4007ec60   | (list, rows, count): {top, row, cursor, rows, count}
        .equ    LUP,      0x4007ec7c   | (list)
        .equ    LDOWN,    0x4007eca4   | (list)
        .equ    LSET,     0x4007edb0   | (list, index)
        .equ    PSTAGE,   0x400326d4   | (P, page, records): a page's tails into its knobs
        .equ    NIBBLE,   0x400a6994   | (P+0x18a, P+0x18e, 4 * param) -> d1: its enable nibble
        .equ    ENCACT,   0x4003256c   | (encoder): its activity 20, the tick counts it down
        .equ    PSTEP,    0x4003240c   | (index, delta, value): a page-2 knob's step
        .equ    NOKEY,    0x400321ec   | rts: the stock SETUP's LEFT and RIGHT
        .equ    T_NONE,   0x400b44b5   | ""
        .equ    T_BLANK,  0x400b439d   | four spaces: an undrawn knob's name
        .equ    T_4X,     0x400b451d   | "XXXX": a knob name's box
        .equ    T_SFMT,   0x400b37cf   | "%s"
        .equ    T_UPA,    0x400b4315   | the list's arrows
        .equ    T_DNA,    0x400b4317
        .equ    FULLN,    0x09         | P+: the full name
        .equ    DEFS,     0x5e         | P+: twelve default bytes
        .equ    FMTS2,    0xe2         | P+: page 2's formatters (A[6..11])
        .equ    WIDG2,    0x112        | P+: page 2's widgets (B[6..11]), 0 = the knob
        .equ    STEP2,    0x142        | P+: page 2's steppers, 0 = PSTEP
        .equ    NAMES2,   0x3a         | P+: page 2's names

        .text
        .globl  mx_push, mx_pop, mx_draw, mx_strip, mx_slot, su_win, SU_IDS

| ---- 0x4007d41c: the opener's `jsr LPUSH` of its layer lands here ------
mx_push:
        move.l  4(%sp),-(%sp)          | the stock layer, as the opener asked
        jsr     LPUSH
        pea     MX_KEYL                | ours on top of it: the arrow keys
        jsr     LPUSH
        addq.l  #8,%sp
        clr.b   mx_strip
        clr.b   mx_slot
        clr.b   mx_encon
        rts

| ---- 0x4007d2a4: the close's `jsr LPOP` of its layer lands here ---------
mx_pop: bsr.w   su_close               | the SETUP window first, if it is open
        bsr.w   encoff
        pea     MX_KEYL
        jsr     LPOP
        addq.l  #4,%sp
        jmp     LPOP                   | the stock layer: the close's own argument

| The knobs' layer is on only while a page other than MIXER shows. Its
| records get the tails a stock page gives a knob before it goes on (the
| layer takes them in when it is registered): the stock opener's
| ETAILS(records, index, 0, 0, 127) for its own knobs, here with the knob's
| minimum and maximum, so a knob of 128 values turns as MAIN does and a
| select as a stock page's select.
encon:  tst.b   mx_encon
        bne.s   9f
        lea     -16(%sp),%sp
        movem.l %d2-%d3/%a2-%a3,(%sp)
        moveq   #0,%d2                 | d2 = the knob
1:      bsr.w   slot
        beq.s   4f
        bsr.w   drawn                  | (clobbers d0/d1)
        beq.s   4f
        move.l  MINS(%a3,%d2.l*4),%d3
        lea     COUNTS(%a3),%a0
        move.l  (%a0,%d2.l*4),%d1
        ble.s   4f
        add.l   %d3,%d1
        subq.l  #1,%d1
        bra.s   2f
4:      moveq   #0,%d3                 | min 0, max 127: a knob that turns nothing
        moveq   #127,%d1
2:      move.l  %d1,-(%sp)             | max
        move.l  %d3,-(%sp)             | min
        clr.l   -(%sp)
        move.l  %d2,-(%sp)
        pea     MX_ENCS
        jsr     ETAILS
        lea     20(%sp),%sp
        addq.l  #1,%d2
        moveq   #6,%d0
        cmp.l   %d0,%d2
        blt.s   1b
        movem.l (%sp),%d2-%d3/%a2-%a3
        lea     16(%sp),%sp
        pea     MX_ENCL
        jsr     LPUSH
        addq.l  #4,%sp
        moveq   #1,%d0
        move.b  %d0,mx_encon
9:      rts
encoff: tst.b   mx_encon
        beq.s   1f
        pea     MX_ENCL
        jsr     LPOP
        addq.l  #4,%sp
        clr.b   mx_encon
1:      rts

| A handler reached with the window gone takes our layers off.
gone:   bsr.w   encoff
        pea     MX_KEYL
        jsr     LPOP
        addq.l  #4,%sp
        rts

| ---- LEFT / RIGHT: the strip ---------------------------------------------
mx_lr:  tst.l   WINH
        beq.s   gone
        moveq   #0,%d0
        move.b  mx_strip,%d0
        moveq   #KRIGHT,%d1
        cmp.l   4(%sp),%d1
        beq.s   1f
        subq.l  #1,%d0                 | LEFT: MIXER is the first
        bmi.w   9f
        bra.s   2f
1:      addq.l  #1,%d0                 | RIGHT: MASTER is the last, for now
        moveq   #STRIPS,%d1
        cmp.l   %d1,%d0
        bge.w   9f
2:      move.b  %d0,mx_strip
        lea     ROWN,%a0
        moveq   #0,%d1
        move.b  (%a0,%d0.l),%d1
        cmp.b   mx_slot,%d1            | the row the new strip does not have
        bhi.s   21f
        clr.b   mx_slot
21:
| the title, the knobs' layer, the page. The title routine draws the frame's
| top two rows (the tab around the title) over what is there, so they go
| back to dark first, as a new window has them.
        move.l  WINH,%a0
        lea     36(%a0),%a0            | the surface {w, h, ...}
        clr.l   -(%sp)
        move.l  4(%a0),%d1
        subq.l  #1,%d1
        move.l  %d1,-(%sp)             | y2 = h - 1
        move.l  (%a0),%d1
        subq.l  #1,%d1
        move.l  %d1,-(%sp)             | x2 = w - 1
        move.l  4(%a0),%d1
        subq.l  #2,%d1
        move.l  %d1,-(%sp)             | y1 = h - 2
        clr.l   -(%sp)                 | x1 = 0
        move.l  %a0,-(%sp)
        jsr     FILL
        lea     24(%sp),%sp
        moveq   #0,%d0
        move.b  mx_strip,%d0
        clr.l   -(%sp)
        lea     TITLES,%a0
        move.l  (%a0,%d0.l*4),-(%sp)
        move.l  WINH,-(%sp)
        jsr     TITLE
        lea     12(%sp),%sp
        tst.b   mx_strip
        beq.s   3f
        bsr.w   encon
        bra.w   mx_draw
3:      bsr.w   encoff
        bra.w   mx_draw
9:      rts

| ---- UP / DOWN: the slot (MASTER: INS 1 above INS 2) ---------------------
mx_ud:  tst.l   WINH
        beq.w   gone
        tst.b   mx_strip
        beq.s   9f                     | MIXER has one page, for now
        moveq   #0,%d0
        move.b  mx_slot,%d0
        moveq   #KDOWN,%d1
        cmp.l   4(%sp),%d1
        bne.s   1f
        addq.l  #1,%d0                 | DOWN: the next row
        lea     ROWN,%a0
        moveq   #0,%d1
        move.b  mx_strip,%d1
        move.b  (%a0,%d1.l),%d1        | the strip's row count
        cmp.l   %d1,%d0
        bge.s   9f
        bra.s   2f
1:      subq.l  #1,%d0                 | UP: the one above
        bmi.s   9f
2:      move.b  %d0,mx_slot
        bsr.w   encoff                 | the knobs take the new row's tails
        bsr.w   encon
        bra.w   mx_draw
9:      rts

| ---- LEVEL on MASTER: MAIN, the stock handler (it redraws, marks EDITED) --
mx_lvl: tst.l   WINH
        beq.w   gone
        moveq   #0,%d0
        move.b  mx_strip,%d0
        cmp.l   #2,%d0
        bhs.s   1f
        jmp     MAINH
1:      lea     -20(%sp),%sp           | a return's LEVEL: its cell's level, stepped as
        movem.l %d2-%d4/%a2-%a3,(%sp)  | MAIN's knob is, held 0..127
        moveq   #0,%d0
        move.b  mx_strip,%d0
        lea     LVLP,%a2
        move.l  -8(%a2,%d0.l*4),%a2    | strips 2, 3: the level's byte
        moveq   #6,%d2
        move.l  %d2,-(%sp)
        jsr     ETOUCH
        addq.l  #4,%sp
        moveq   #0,%d0
        move.b  (%a2),%d0
        move.l  %d0,-(%sp)             | (index, delta, value)
        move.l  32(%sp),-(%sp)
        move.l  %d2,-(%sp)
        jsr     ESTEP
        lea     12(%sp),%sp
        tst.l   %d0
        bge.s   2f
        moveq   #0,%d0
2:      cmp.l   #127,%d0
        ble.s   3f
        moveq   #127,%d0
3:      move.b  %d0,(%a2)
        bsr.w   keep                   | the Part keeps it
        bsr.w   mx_draw
        moveq   #1,%d0
        move.l  %d0,EDITED
        movem.l (%sp),%d2-%d4/%a2-%a3
        lea     20(%sp),%sp
        rts

| ---- A-F on MASTER: (index, delta), the slot's page-1 knob <index> -------
mx_enc: tst.l   WINH
        beq.w   gone
        lea     -20(%sp),%sp
        movem.l %d2-%d4/%a2-%a3,(%sp)
        move.l  24(%sp),%d2            | the knob, 0..5
        bsr.w   slot                   | a2 = the slot's model, a3 = P
        beq.w   eout
        bsr.w   drawn
        beq.w   eout                   | a knob the effect does not draw
        lea     COUNTS(%a3),%a0
        move.l  (%a0,%d2.l*4),%d4
        ble.w   eout
        move.l  MINS(%a3,%d2.l*4),%d3  | d3 = min
        add.l   %d3,%d4
        subq.l  #1,%d4                 | d4 = max
        move.l  %d2,-(%sp)
        jsr     ETOUCH
        addq.l  #4,%sp
        moveq   #0,%d0
        move.b  4(%a2,%d2.l),%d0
        move.l  %d0,-(%sp)             | (index, delta, value)
        move.l  32(%sp),-(%sp)
        move.l  %d2,-(%sp)
        jsr     ESTEP
        lea     12(%sp),%sp
        cmp.l   %d3,%d0
        bge.s   1f
        move.l  %d3,%d0
1:      cmp.l   %d4,%d0
        ble.s   2f
        move.l  %d4,%d0
2:      move.b  %d0,4(%a2,%d2.l)
        bsr.w   keep                    | the Part keeps it
        bsr.w   mx_draw
        moveq   #1,%d0
        move.l  %d0,EDITED
eout:   movem.l (%sp),%d2-%d4/%a2-%a3
        lea     20(%sp),%sp
        rts

| rowptr: a0 = the shown row's entry in ROWS: {the model's cell, its descriptor (0: the
| effect its id names)}, four rows a strip from MASTER on (clobbers d0/d1)
rowptr: moveq   #0,%d0
        move.b  mx_strip,%d0
        subq.l  #1,%d0
        lsl.l   #2,%d0
        moveq   #0,%d1
        move.b  mx_slot,%d1
        add.l   %d1,%d0
        lsl.l   #3,%d0
        lea     ROWS,%a0
        add.l   %d0,%a0
        rts

| keep: the Part keeps what the page edited: MASTER's slots as strip_store does, the
| returns' cells as ret_store (main context, every register but d0/d1/a0/a1 kept)
keep:   moveq   #0,%d0
        move.b  mx_strip,%d0
        cmp.l   #1,%d0
        bne.s   1f
        jmp     strip_store
1:      jmp     ret_store

| slot: a2 = the shown row's model, a3 = its descriptor P; Z set when the row is an
| effect slot with no effect (clobbers d0/d1/a0)
slot:   bsr.s   rowptr
        move.l  (%a0),%a2
        move.l  4(%a0),%a3
        move.l  %a3,%d0
        bne.s   1f                     | a sends or outputs row: never empty
        moveq   #0,%d0
        move.b  (%a2),%d0
        beq.s   1f
        lea     DESC2,%a0
        move.l  (%a0,%d0.l*4),%d0
        move.l  %d0,%a3
1:      rts

| drawn: d2 = the knob; Z clear when P's enable nibble draws it (clobbers d0/d1)
drawn:  move.l  ENABLE(%a3),%d0
        move.l  %d2,%d1
        lsl.l   #2,%d1
        lsr.l   %d1,%d0
        moveq   #1,%d1
        and.l   %d1,%d0
        rts

| ---- YES on MASTER: the shown slot's SETUP ---------------------------------
| A window as EFFECT 2 SETUP's (115 x 64, the same calls): the strip's list
| down the left (NONE and the effects the DSP runs on the strip, tail.asm),
| the slot's effect marked, a cursor that UP and DOWN move and YES takes;
| on the right the effect's page-2 knobs, drawn and turned as EFFECT 2
| SETUP draws and turns a track's. NO closes it. On the MIXER strip YES
| stays what the stock page makes it, nothing.
mx_yes: tst.l   WINH
        beq.w   gone
        tst.b   mx_strip
        beq.w   9f
        tst.l   su_win
        bne.w   9f
        bsr.w   rowptr
        tst.l   4(%a0)
        bne.w   9f                     | a sends or outputs row: no SETUP
        moveq   #0,%d0
        move.b  mx_strip,%d0
        subq.l  #1,%d0
        lsl.l   #3,%d0
        lea     SL_LISTS,%a0
        move.l  (%a0,%d0.l),%d1
        move.l  %d1,su_idsp
        move.l  4(%a0,%d0.l),%d1
        move.l  %d1,su_nn
        move.b  mx_strip,%d0           | (the title, below, wants the strip again)
        lea     -12(%sp),%sp
        movem.l %d2/%a2-%a3,(%sp)
        pea     su_close               | the window, as the stock opener makes its own,
        pea     2                      | one level above the MIXER's: WINNEW closes
                                       | every window at the new one's level or
                                       | above, so stock's 1 would take the MIXER
                                       | down (stock opens level-2 windows at
                                       | 0x400647be and 0x40080eb2)
        clr.l   -(%sp)
        clr.l   -(%sp)
        pea     0x40
        pea     0x73
        jsr     WINNEW
        lea     24(%sp),%sp
        move.l  %d0,su_win
        beq.w   8f
        move.l  %d0,%a0
        pea     1
        clr.l   -(%sp)
        pea     36(%a0)
        jsr     PCLEAR
        lea     12(%sp),%sp
        pea     T_NONE
        moveq   #0,%d0
        move.b  mx_slot,%d0
        moveq   #0,%d1
        move.b  mx_strip,%d1
        cmp.l   #2,%d1
        blo.s   41f
        move.l  %d1,%d0                | the returns' SETUPs are titles 2 and 3
41:     lea     SU_TITLES,%a0
        move.l  (%a0,%d0.l*4),-(%sp)
        move.l  su_win,-(%sp)
        jsr     TITLE
        lea     12(%sp),%sp
        move.l  su_nn,-(%sp)           | the list: every row shows
        move.l  su_nn,-(%sp)
        pea     su_ls
        jsr     LINIT
        lea     12(%sp),%sp
        bsr.w   spos                   | the cursor on the slot's effect
        bpl.s   1f
        moveq   #0,%d0
1:      move.l  %d0,-(%sp)
        pea     su_ls
        jsr     LSET
        addq.l  #8,%sp
        bsr.w   stails
        pea     SU_KEYL
        jsr     LPUSH
        addq.l  #4,%sp
        bsr.w   su_draw
8:      movem.l (%sp),%d2/%a2-%a3
        lea     12(%sp),%sp
9:      rts

| spos: d0 = the slot's effect's row in the list, -1 if it is not on it;
| a2 = the slot's model (clobbers d1/a0)
spos:   bsr.w   rowptr
        move.l  (%a0),%a2
        moveq   #0,%d1
        move.b  (%a2),%d1
        move.l  su_idsp,%a0
        moveq   #0,%d0
1:      cmp.l   su_nn,%d0
        bge.s   2f
        cmp.b   (%a0,%d0.l),%d1
        beq.s   3f
        addq.l  #1,%d0
        bra.s   1b
2:      moveq   #-1,%d0
3:      tst.l   %d0
        rts

| sdesc: a3 = the descriptor of the slot's effect, NONE's for none; a2 =
| the slot's model; Z set when there is none (clobbers d0/a0)
sdesc:  bsr.w   rowptr
        move.l  (%a0),%a2
        moveq   #0,%d0
        move.b  (%a2),%d0
        lea     DESC2,%a0
        move.l  (%a0,%d0.l*4),%d0
        move.l  %d0,%a3
        rts

| stails: the page-2 knobs take the slot's effect's tails, as the stock
| opener stages its own (PSTAGE with page 1: parameters 6..11)
stails: bsr.s   sdesc
        beq.s   9f
        pea     SU_ENCS
        pea     1
        move.l  %a3,-(%sp)
        jsr     PSTAGE
        lea     12(%sp),%sp
9:      rts

| nib: d1 = the enable nibble of parameter d0 of a3 (clobbers d0/a0/a1)
nib:    lsl.l   #2,%d0
        move.l  %d0,-(%sp)
        move.l  0x18e(%a3),-(%sp)
        move.l  0x18a(%a3),-(%sp)
        jsr     NIBBLE
        lea     12(%sp),%sp
        rts

| ---- the SETUP's keys -------------------------------------------------------
su_ud:  tst.l   su_win
        beq.s   9f
        pea     su_ls
        moveq   #KUP,%d0
        cmp.l   8(%sp),%d0
        bne.s   1f
        jsr     LUP
        bra.s   2f
1:      jsr     LDOWN
2:      addq.l  #4,%sp
        bra.w   su_draw
9:      rts

| YES: the row under the cursor becomes the slot's effect, its knobs at the
| effect's defaults (a knob it does not draw at 0, as the boot starts OXIDE)
su_yes: tst.l   su_win
        beq.w   9f
        lea     -16(%sp),%sp
        movem.l %d2-%d3/%a2-%a3,(%sp)
        move.l  su_ls+8,%d0            | the cursor
        move.l  su_idsp,%a0
        moveq   #0,%d2
        move.b  (%a0,%d0.l),%d2        | d2 = its id
        bsr.w   sdesc
        moveq   #0,%d0
        move.b  (%a2),%d0
        cmp.l   %d0,%d2
        beq.s   8f                     | the slot's own: nothing changes
        move.b  %d2,(%a2)
        bsr.w   sdesc                  | a3 = the new effect's
        moveq   #0,%d3                 | d3 = the parameter
1:      moveq   #0,%d2
        move.l  %a3,%d0
        beq.s   2f
        move.l  %d3,%d0
        bsr.w   nib
        btst    #0,%d1
        beq.s   2f
        move.b  DEFS(%a3,%d3.l),%d2
2:      move.b  %d2,4(%a2,%d3.l)
        addq.l  #1,%d3
        moveq   #12,%d0
        cmp.l   %d0,%d3
        blt.s   1b
        pea     SU_KEYL                | the knobs take the new effect's tails
        jsr     LPOP
        addq.l  #4,%sp
        bsr.w   stails
        pea     SU_KEYL
        jsr     LPUSH
        addq.l  #4,%sp
        bsr.w   keep                    | the Part keeps the new effect
        moveq   #1,%d0
        move.l  %d0,EDITED
        bsr.w   su_draw
8:      movem.l (%sp),%d2-%d3/%a2-%a3
        lea     16(%sp),%sp
9:      rts

| A-F: (index, delta), the slot's page-2 knob, stepped as the stock page-2
| editor steps a track's (the descriptor's stepper or PSTEP), held inside
| the parameter's range
su_enc: tst.l   su_win
        beq.w   9f
        lea     -20(%sp),%sp
        movem.l %d2-%d4/%a2-%a3,(%sp)
        move.l  24(%sp),%d2            | the knob, 0..5
        bsr.w   sdesc
        beq.w   8f
        moveq   #6,%d0
        add.l   %d2,%d0
        bsr.w   nib
        btst    #0,%d1
        beq.w   8f                     | a knob the effect does not draw
        move.l  %d2,%d0
        lsl.l   #2,%d0
        lea     STEP2(%a3),%a0
        move.l  (%a0,%d0.l),%d1
        bne.s   1f
        move.l  #PSTEP,%d1
1:      move.l  %d1,%a0
        move.b  10(%a2,%d2.l),%d1
        extb.l  %d1
        move.l  %d1,-(%sp)             | (index, delta, value)
        move.l  32(%sp),-(%sp)
        move.l  %d2,-(%sp)
        jsr     (%a0)
        lea     12(%sp),%sp
        move.l  %d2,%d1
        lsl.l   #2,%d1
        add.l   #MINS+24,%d1
        move.l  (%a3,%d1.l),%d3        | d3 = min
        cmp.l   %d3,%d0
        bge.s   2f
        move.l  %d3,%d0
2:      move.l  %d2,%d1
        lsl.l   #2,%d1
        add.l   #COUNTS+24,%d1
        move.l  (%a3,%d1.l),%d4
        add.l   %d3,%d4
        subq.l  #1,%d4                 | d4 = max
        cmp.l   %d4,%d0
        ble.s   3f
        move.l  %d4,%d0
3:      move.b  %d0,10(%a2,%d2.l)
        bsr.w   keep                    | the Part keeps it
        moveq   #1,%d0
        move.l  %d0,EDITED
        move.l  %d2,-(%sp)             | the knob lifts and shows its value, as
        jsr     ENCACT                 | stock's page-2 editor sets it (0x4003ab14)
        addq.l  #4,%sp
        bsr.w   su_draw
8:      movem.l (%sp),%d2-%d4/%a2-%a3
        lea     20(%sp),%sp
9:      rts

| NO, and the window's close (the window manager's callback, the MIXER's
| close): the window and its layer go, MASTER's knobs take the slot's
| effect's tails again and the page redraws
su_no:
su_close:
        tst.l   su_win
        beq.s   9f
        pea     su_win
        jsr     WINDEL
        addq.l  #4,%sp
        pea     SU_KEYL
        jsr     LPOP
        addq.l  #4,%sp
        tst.l   WINH
        beq.s   9f
        tst.b   mx_encon
        beq.s   1f
        bsr.w   encoff
        bsr.w   encon
1:      bra.w   mx_draw
9:      rts

| ---- the SETUP's draw: 0x40037590's, from the strip's list and model -------
su_draw:
        move.l  su_win,%d0
        beq.w   9f
        lea     -40(%sp),%sp
        movem.l %d2-%d7/%a2-%a5,(%sp)
        move.l  %d0,%a5
        lea     36(%a5),%a5            | a5 = the surface
        lea     FILL,%a4
        moveq   #3,%d0
        moveq   #3,%d1
        moveq   #0x6e,%d2
        moveq   #0x35,%d3
        moveq   #0,%d4
        bsr.w   shape
        pea     1
        pea     0x36
        pea     2
        pea     0x34
        move.l  %a5,-(%sp)
        jsr     VLINE
        lea     20(%sp),%sp
| the list's rows, top down from row 47, 7 apart: each effect's full name
        moveq   #0,%d2                 | d2 = the row
        moveq   #47,%d3                | d3 = its y
1:      cmp.l   su_ls+12,%d2
        bge.s   2f
        move.l  su_ls,%d0
        add.l   %d2,%d0
        move.l  su_idsp,%a0
        moveq   #0,%d1
        move.b  (%a0,%d0.l),%d1
        lea     DESC2,%a0
        move.l  (%a0,%d1.l*4),%a0
        pea     FULLN(%a0)
        pea     -1
        move.l  %d3,-(%sp)
        pea     4
        move.l  %a5,-(%sp)
        pea     FONT
        jsr     TEXT
        lea     24(%sp),%sp
        addq.l  #1,%d2
        subq.l  #7,%d3
        bra.s   1b
| the arrows: more above the top row, more below the last
2:      tst.l   su_ls
        ble.s   3f
        lea     FILL,%a4
        moveq   #0x2e,%d0
        moveq   #0x2e,%d1
        moveq   #0x32,%d2
        moveq   #0x34,%d3
        moveq   #0,%d4
        bsr.w   shape
        pea     T_UPA
        pea     -1
        pea     0x2f
        pea     0x2f
        move.l  %a5,-(%sp)
        pea     FONT
        jsr     TEXT
        lea     24(%sp),%sp
3:      move.l  su_ls+12,%d5
        move.l  %d5,%d0
        add.l   su_ls,%d0
        cmp.l   su_ls+16,%d0
        bge.s   4f
        moveq   #-7,%d0
        muls.l  %d0,%d5                | d5 = -7 * rows
        lea     FILL,%a4
        moveq   #0x2e,%d0
        moveq   #0x35,%d1
        add.l   %d5,%d1
        moveq   #0x32,%d2
        moveq   #0x3b,%d3
        add.l   %d5,%d3
        moveq   #0,%d4
        bsr.w   shape
        pea     T_DNA
        pea     -1
        moveq   #0x36,%d0
        add.l   %d5,%d0
        move.l  %d0,-(%sp)
        pea     0x2f
        move.l  %a5,-(%sp)
        pea     FONT
        jsr     TEXT
        lea     24(%sp),%sp
| the slot's effect, inverted; the cursor, boxed
4:      bsr.w   spos
        bmi.s   5f
        sub.l   su_ls,%d0
        bmi.s   5f
        cmp.l   su_ls+12,%d0
        bge.s   5f
        moveq   #-7,%d5
        muls.l  %d0,%d5
        lea     FILL,%a4
        moveq   #-1,%d4
        bsr.w   srow
5:      moveq   #-7,%d5
        move.l  su_ls+4,%d0
        muls.l  %d0,%d5
        lea     RECT,%a4
        moveq   #1,%d4
        bsr.w   srow
| the knobs' grid
        move.l  (%a5),%d0
        subq.l  #4,%d0
        move.l  %d0,-(%sp)
        pea     0x1c
        pea     0x34
        move.l  %a5,-(%sp)
        jsr     HDOT
        lea     16(%sp),%sp
        lea     DOTTED,%a4
        moveq   #0x48,%d0
        moveq   #2,%d1
        moveq   #0x48,%d2
        moveq   #0x36,%d3
        moveq   #1,%d4
        bsr.w   shape
        moveq   #0x5c,%d0
        moveq   #2,%d1
        moveq   #0x5c,%d2
        moveq   #0x36,%d3
        bsr.w   shape
        bsr.w   knobs2
        moveq   #1,%d0
        move.l  %d0,SCRDIRTY
        movem.l (%sp),%d2-%d7/%a2-%a5
        lea     40(%sp),%sp
9:      rts

| srow: (a4)(surf, 3, 52 + d5, 0x32, 46 + d5, d4): a list row's box
srow:   moveq   #3,%d0
        moveq   #0x34,%d1
        add.l   %d5,%d1
        moveq   #0x32,%d2
        moveq   #0x2e,%d3
        add.l   %d5,%d3
        bra.w   shape

| knobs2: the slot's effect's page-2 knobs in the 3 x 2 grid, each by the
| descriptor's widget (the knob when 0) at x 0x35 + 20 col, y 29 - 27 row,
| and its name centred over it; a knob it does not draw: a blank name
knobs2: bsr.w   sdesc
        beq.w   9f
        moveq   #0,%d2                 | d2 = the knob
1:      moveq   #6,%d0
        add.l   %d2,%d0
        bsr.w   nib
        move.l  %d1,%d6                | d6 = its nibble
        move.l  %d2,%d5                | d5 = the column, d7 = the row
        moveq   #0,%d7
        moveq   #3,%d0
        cmp.l   %d0,%d5
        blt.s   11f
        subq.l  #3,%d5
        moveq   #27,%d7                | d7 = 27 row
11:     mulu.w  #20,%d5                | d5 = 20 col
        btst    #0,%d6
        beq.s   3f
        move.l  %d2,%d0
        lsl.l   #2,%d0
        lea     WIDG2(%a3),%a0
        move.l  (%a0,%d0.l),%d1
        bne.s   2f
        move.l  #VALUE,%d1
2:      move.l  %a5,-(%sp)
        lea     FMTS2(%a3),%a0
        move.l  (%a0,%d0.l),-(%sp)
        move.l  %d1,%a0
        moveq   #0,%d1
        btst    #2,%d6
        beq.s   21f
        moveq   #8,%d1
21:     move.l  %d1,-(%sp)             | flags
        move.b  10(%a2,%d2.l),%d1
        extb.l  %d1
        move.l  %d1,-(%sp)             | value
        move.l  %d2,-(%sp)             | encoder
        moveq   #29,%d1
        sub.l   %d7,%d1
        move.l  %d1,-(%sp)             | y
        moveq   #0x35,%d1
        add.l   %d5,%d1
        move.l  %d1,-(%sp)             | x
        jsr     (%a0)
        lea     28(%sp),%sp
        move.l  %d2,%d0
        mulu.w  #6,%d0
        pea     NAMES2(%a3,%d0.l)
        pea     T_SFMT
        bra.s   4f
3:      pea     T_BLANK
        pea     T_BLANK
4:      pea     T_4X
        clr.l   -(%sp)
        pea     1
        moveq   #48,%d1
        sub.l   %d7,%d1
        move.l  %d1,-(%sp)
        moveq   #0x3e,%d1
        add.l   %d5,%d1
        move.l  %d1,-(%sp)
        move.l  %a5,-(%sp)
        pea     FONT
        jsr     TEXTF
        lea     36(%sp),%sp
        addq.l  #1,%d2
        moveq   #6,%d0
        cmp.l   %d0,%d2
        blt.w   1b
9:      rts

| ---- 0x4007c458: the draw -------------------------------------------------
mx_draw:
        bsr.s   sdraw                  | the stock window
        move.l  WINH,%d0
        beq.s   9f
        lea     -40(%sp),%sp
        movem.l %d2-%d7/%a2-%a5,(%sp)
        move.l  %d0,%a5
        lea     36(%a5),%a5            | a5 = the window's surface {w, h, ...}
        bsr.w   arrows
        tst.b   mx_strip
        beq.s   1f
        bsr.w   master
1:      moveq   #1,%d0
        move.l  %d0,SCRDIRTY
        tst.l   su_win                 | the SETUP over it: the knobs' lift runs
        beq.s   2f                     | on the tick that redraws the MIXER
        bsr.w   su_draw                | (0x4005213c -> 0x4007cf28 -> here)
2:      movem.l (%sp),%d2-%d7/%a2-%a5
        lea     40(%sp),%sp
9:      rts
sdraw:  lea     -52(%sp),%sp           | the displaced prologue; the stock
        movem.l %d2-%d7/%a2-%a6,(%sp)  | draw's rts comes back to mx_draw
        jmp     SBODY

| The title band's arrows: where LEFT and RIGHT lead.
arrows: tst.b   mx_strip
        beq.s   1f
        moveq   #3,%d0
        lea     T_LA,%a0
        bsr.s   glyph
1:      moveq   #0,%d0
        move.b  mx_strip,%d0
        addq.l  #1,%d0
        moveq   #STRIPS,%d1
        cmp.l   %d1,%d0
        bge.s   2f
        moveq   #100,%d0
        lea     T_RA,%a0
        bsr.s   glyph
2:      rts

| glyph: the one-character string a0, dark, on the title band at x d0,
| drawn as the title routine draws the title; the routine lights the row
| above the band behind it, which goes back to the frame's dark (clobbers
| d0/d1/a0/a1)
glyph:  move.l  %d0,-(%sp)
        move.l  %a0,-(%sp)             | fmt
        move.l  %a0,-(%sp)             | template
        pea     1                      | dark
        clr.l   -(%sp)                 | from x
        move.l  4(%a5),%d1
        subq.l  #7,%d1                 | the title's row: h - 7
        move.l  %d1,-(%sp)
        move.l  %d0,-(%sp)
        move.l  %a5,-(%sp)
        pea     FONT
        jsr     TEXTF
        lea     32(%sp),%sp
        move.l  (%sp)+,%d0
        clr.l   -(%sp)
        move.l  4(%a5),%d1
        subq.l  #2,%d1                 | h - 2
        move.l  %d1,-(%sp)
        addq.l  #5,%d0
        move.l  %d0,-(%sp)
        move.l  %d1,-(%sp)
        subq.l  #5,%d0
        move.l  %d0,-(%sp)
        move.l  %a5,-(%sp)
        jsr     FILL
        lea     24(%sp),%sp
        rts

| ---- MASTER: box 1 the level, box 2 the slot -----------------------------
master: lea     FILL,%a4               | the three stock boxes, cleared
        moveq   #3,%d0
        moveq   #0x15,%d1
        moveq   #0x67,%d2
        moveq   #0x35,%d3
        moveq   #0,%d4
        bsr.w   shape
        lea     RECT,%a4               | box 1: MIX's box
        moveq   #3,%d0
        moveq   #0x15,%d1
        moveq   #0x17,%d2
        moveq   #0x35,%d3
        moveq   #1,%d4
        bsr.w   shape
        lea     T_MAIN,%a0
        moveq   #0,%d0
        move.b  mx_strip,%d0
        cmp.l   #2,%d0
        blo.s   12f
        lea     T_LVL,%a0
12:     moveq   #0xd,%d0
        moveq   #0x2f,%d1
        bsr.w   ctext
        moveq   #4,%d0                 | MAIN's value where MIX's crossfade is
        moveq   #0x26,%d1
        moveq   #6,%d2                 | LEVEL's encoder
        moveq   #0,%d3
        move.b  MAINV,%d3
        lea     SIGNED,%a0
        moveq   #0,%d0
        move.b  mx_strip,%d0
        cmp.l   #2,%d0
        blo.s   11f
        | a return: its level, a plain number
        lea     LVLP,%a1
        move.l  -8(%a1,%d0.l*4),%a1
        moveq   #0,%d3
        move.b  (%a1),%d3
        sub.l   %a0,%a0
11:     moveq   #4,%d0
        moveq   #0x26,%d1
        moveq   #6,%d2
        bsr.w   num
        lea     DOTTED,%a4
        moveq   #5,%d0
        moveq   #0x25,%d1
        moveq   #0x15,%d2
        moveq   #0x25,%d3
        moveq   #1,%d4
        bsr.w   shape
        pea     0x17                   | the speaker where MIX's headphones are
        pea     5
        move.l  %a5,-(%sp)
        pea     SPEAKER
        jsr     ICON
        lea     16(%sp),%sp
        lea     RECT,%a4               | box 2: OUT's and the AB/CD box, as one
        moveq   #0x19,%d0
        moveq   #0x15,%d1
        moveq   #0x67,%d2
        moveq   #0x35,%d3
        bsr.w   shape
        lea     FILL,%a4               | the slot down its side, as OUT
        moveq   #0x1b,%d0
        moveq   #0x17,%d1
        moveq   #0x1f,%d2
        moveq   #0x33,%d3
        bsr.w   shape
        bsr.w   sidelabel
        bsr.w   cells
        lea     DOTTED,%a4             | the rules last, over what a label cleared
        moveq   #1,%d4
        moveq   #0x21,%d0
        moveq   #0x17,%d1
        moveq   #0x21,%d2
        moveq   #0x33,%d3
        bsr.w   shape
        moveq   #0x39,%d0
        moveq   #0x17,%d1              | d0/d1 do not survive a call
        moveq   #0x39,%d2
        bsr.w   shape
        moveq   #0x50,%d0
        moveq   #0x17,%d1
        moveq   #0x50,%d2
        bsr.w   shape
        moveq   #0x22,%d0
        moveq   #0x25,%d1
        moveq   #0x66,%d2
        moveq   #0x25,%d3
        bra.w   shape

| sidelabel: the row's four letters down the side, dark, at rows 0x2c, 0x26, 0x20, 0x1a
| as the stock draw writes OUT (clobbers d0/d1/a0/a1, d6)
sidelabel:
        bsr.w   rowptr
        move.l  %a0,%d0
        lea     ROWS,%a1
        sub.l   %a1,%d0
        lsr.l   #3,%d0                 | the row's index
        lea     SIDE,%a0
        lsl.l   #2,%d0
        add.l   %d0,%a0                | its four letters
        moveq   #0x2c,%d6
1:      moveq   #0,%d0
        move.b  (%a0)+,%d0
        lsl.l   #8,%d0                 | the letter and its NULs, on the stack
        lsl.l   #8,%d0
        lsl.l   #8,%d0
        move.l  %d0,-(%sp)
        move.l  %sp,%d0
        move.l  %a0,-(%sp)
        move.l  %d0,-(%sp)
        pea     T_X
        pea     1
        clr.l   -(%sp)
        move.l  %d6,-(%sp)
        pea     0x1c
        move.l  %a5,-(%sp)
        pea     FONT
        jsr     TEXTF
        lea     32(%sp),%sp
        move.l  (%sp)+,%a0
        addq.l  #4,%sp
        subq.l  #6,%d6
        cmp.l   #0x1a,%d6
        bge.s   1b
        rts

| cells: the slot's page-1 knobs the effect draws, name over value
cells:  bsr.w   slot
        beq.s   9f
        moveq   #0,%d2                 | d2 = the knob
1:      bsr.w   drawn
        beq.s   8f
        lea     CELLX,%a0
        moveq   #0,%d5
        move.b  (%a0,%d2.l),%d5        | d5 = the cell's centre
        lea     CELLY,%a0
        moveq   #0,%d6
        move.b  (%a0,%d2.l),%d6        | d6 = its label's row
        move.l  %d2,%d0
        mulu.w  #6,%d0
        lea     NAMES(%a3,%d0.l),%a0
        move.l  %d5,%d0
        move.l  %d6,%d1
        bsr.w   ctext
        move.l  %d5,%d0
        subq.l  #8,%d0
        subq.l  #1,%d0                 | the value, centred at x + 9
        move.l  %d6,%d1
        subq.l  #8,%d1
        subq.l  #1,%d1
        moveq   #0,%d3
        move.b  4(%a2,%d2.l),%d3
        lea     FMTS(%a3),%a0
        move.l  (%a0,%d2.l*4),%a0
        bsr.w   num
8:      addq.l  #1,%d2
        moveq   #6,%d0
        cmp.l   %d0,%d2
        blt.s   1b
9:      rts

| shape: (a4)(surf, d0, d1, d2, d3, d4) (clobbers d0/d1/a0/a1)
shape:  move.l  %d4,-(%sp)
        move.l  %d3,-(%sp)
        move.l  %d2,-(%sp)
        move.l  %d1,-(%sp)
        move.l  %d0,-(%sp)
        move.l  %a5,-(%sp)
        jsr     (%a4)
        lea     24(%sp),%sp
        rts

| ctext: the string a0, light on dark, centred at x d0, row d1 (clobbers d0/d1/a0/a1)
ctext:  move.l  %a0,-(%sp)
        pea     T_S
        move.l  %a0,-(%sp)             | the template: its own width
        clr.l   -(%sp)
        pea     1                      | centred
        move.l  %d1,-(%sp)
        move.l  %d0,-(%sp)
        move.l  %a5,-(%sp)
        pea     FONT
        jsr     TEXTF
        lea     36(%sp),%sp
        rts

| vchar: the one-character string a0, dark on the side label, row d1, as
| the stock draw writes OUT (clobbers d0/d1/a0/a1)
vchar:  move.l  %a0,-(%sp)
        pea     T_X
        pea     1
        clr.l   -(%sp)
        move.l  %d1,-(%sp)
        pea     0x1c
        move.l  %a5,-(%sp)
        pea     FONT
        jsr     TEXTF
        lea     32(%sp),%sp
        rts

| num: the value d3 as a number centred at x d0 + 9, row d1 + 2, by the
| formatter a0 (0: plain), for encoder d2 (clobbers d0/d1/a0/a1)
num:    move.l  %a5,-(%sp)
        move.l  %a0,-(%sp)
        pea     6
        move.l  %d3,-(%sp)
        move.l  %d2,-(%sp)
        move.l  %d1,-(%sp)
        move.l  %d0,-(%sp)
        jsr     VALUE
        lea     28(%sp),%sp
        rts

| ---- data ------------------------------------------------------------------
        .balign 4
TITLES: .long   T_MIXER, T_MASTER, T_RETA, T_RETB
| Input layers as the stock ones: {next, keys, encoders, 0, 0, -1, -1}; a
| zero list leaves the layers under it alone.
MX_KEYL:
        .long   0, MX_KEYS, 0, 0, 0, -1, -1
MX_ENCL:
        .long   0, 0, MX_ENCS, 0, 0, -1, -1
| Key records, 26 B: {code, 0, press, release, repeat, 0, 0, delay, rate}.
MX_KEYS:
        .irp    k, 0x34, 0x21
        .byte   \k, 0
        .long   mx_lr, 0, 0, 0, 0
        .word   0, 0
        .endr
        .irp    k, 0x33, 0x20
        .byte   \k, 0
        .long   mx_ud, 0, 0, 0, 0
        .word   0, 0
        .endr
        .byte   0x31, 0
        .long   mx_yes, 0, 0, 0, 0
        .word   0, 0
        .byte   0xff, 0
        .long   0, 0, 0, 0, 0
        .word   0, 0
| Encoder records, 22 B: {index, 0, handler, then the tails}. A-F's are
| set by encon; LEVEL's are the ones ETAILS(records, 6, 0, 0, 127) gives
| the stock opener's LEVEL: -1, 32768 / 127, 0, 127.
MX_ENCS:
        .irp    k, 0, 1, 2, 3, 4, 5
        .byte   \k, 0
        .long   mx_enc, -1, 258, 0, 127
        .endr
        .byte   6, 0
        .long   mx_lvl, -1, 258, 0, 127
        .byte   0xff, 0
        .long   0, 0, 0, 0, 0
| The SETUP's layer, as EFFECT 2 SETUP's (0x400bc470): UP and DOWN the list
| (held: repeating, 15 then 4), LEFT and RIGHT nothing, YES takes the row,
| NO closes; A-F the page-2 knobs, LEVEL nothing.
SU_KEYL:
        .long   0, SU_KEYS, SU_ENCS, 0, 0, -1, -1
SU_KEYS:
        .irp    k, 0x20, 0x33
        .byte   \k, 0
        .long   su_ud, 0, su_ud, 0, 0
        .word   15, 4
        .endr
        .irp    k, 0x34, 0x21
        .byte   \k, 0
        .long   NOKEY, 0, 0, 0, 0
        .word   0, 0
        .endr
        .byte   0x31, 0
        .long   su_yes, 0, 0, 0, 0
        .word   0, 0
        .byte   0x32, 0
        .long   su_no, 0, 0, 0, 0
        .word   0, 0
        .byte   0xff, 0
        .long   0, 0, 0, 0, 0
        .word   0, 0
SU_ENCS:
        .irp    k, 0, 1, 2, 3, 4, 5
        .byte   \k, 0
        .long   su_enc, 0, 0, 0, 0
        .endr
        .byte   6, 0
        .long   NOKEY, -1, 258, 0, 127
        .byte   0xff, 0
        .long   0, 0, 0, 0, 0
        .balign 4
SU_TITLES:
        .long   T_S1, T_S2, T_S3, T_S4
su_ls:  .long   0, 0, 0, 0, 0          | the list: top, row, cursor, rows, count
su_win: .long   0                      | the SETUP window's handle, 0 = closed
| The strip's list: NONE, then what tail.asm runs (OXIDE); a row is an id,
| its name the descriptor's
        .equ    SU_N, 2
SU_IDS: .byte   0x00, 0x1f, 0xff              | 0xff ends it: strip_xport checks a stored id against it
| The returns' lists: NONE, OXIDE, and the server of the return's core (tail.asm, reta.asm)
SL_A:   .byte   0x00, 0x1f, 0x06, 0xff
SL_B:   .byte   0x00, 0x1f, 0x07, 0xff
        .balign 4
SL_LISTS:
        .long   SU_IDS, 2, SL_A, 3, SL_B, 3
su_idsp: .long  SU_IDS                 | the list the SETUP shows (mx_yes sets it)
su_nn:   .long  2
| The rows of a return's page: {the model's cell, the descriptor}: MASTER's two effect slots,
| then, for RETURN A and RETURN B, the effect slot (its id names the descriptor), the sends
| into it (T1..T6 in one row, the rest in the next: the row's cell is offset by six bytes),
| and its output (level, CUE send). Four rows a strip, from MASTER on.
        .balign 4
ROWS:
        .long   strip_model, 0, strip_model+16, 0, 0, 0, 0, 0
        .long   ret_model+16, 0, aux_model, P_SND1, aux_model+6, P_SND2, retlvl_model+16, P_OUT
        .long   ret_model, 0, aux_model+16, P_SND1, aux_model+16+6, P_SND2, retlvl_model, P_OUT
ROWN:   .byte   0, 2, 4, 4
SIDE:   .ascii  "INS1INS2        "
        .ascii  "INS1SND1SND2OUT "
        .ascii  "INS1SND1SND2OUT "
        .balign 4
LVLP:   .long   retlvl_model+16+4, retlvl_model+4   | RETURN A's level byte, RETURN B's
| Descriptors for the rows that are not effects, as the page code reads one: names at 0x16,
| minimums at 0x6a, counts at 0x9a, formatters at 0xca (0: a plain number), the enable
| nibbles at 0x18e (bit 0 a knob drawn)
P_SND1:
        .space  0x16
        .ascii  "T1"
        .space  4
        .ascii  "T2"
        .space  4
        .ascii  "T3"
        .space  4
        .ascii  "T4"
        .space  4
        .ascii  "T5"
        .space  4
        .ascii  "T6"
        .space  4
        .space  6
        .space  6
        .space  6
        .space  6
        .space  6
        .space  6
        .space  0x6a-0x5e
        .rept   12
        .long   0
        .endr
        .rept   12
        .long   128
        .endr
        .rept   12
        .long   0
        .endr
        .space  0x18e-0xfa
        .long   0x111111
P_SND2:
        .space  0x16
        .ascii  "T7"
        .space  4
        .ascii  "T8"
        .space  4
        .ascii  "INAB"
        .space  2
        .ascii  "INCD"
        .space  2
        .ascii  "RTNA"
        .space  2
        .ascii  "RTNB"
        .space  2
        .space  6
        .space  6
        .space  6
        .space  6
        .space  6
        .space  6
        .space  0x6a-0x5e
        .rept   12
        .long   0
        .endr
        .rept   12
        .long   128
        .endr
        .rept   12
        .long   0
        .endr
        .space  0x18e-0xfa
        .long   0x111111
P_OUT:
        .space  0x16
        .ascii  "LEVL"
        .space  2
        .ascii  "CUE"
        .space  3
        .space  6
        .space  6
        .space  6
        .space  6
        .space  6
        .space  6
        .space  6
        .space  6
        .space  6
        .space  6
        .space  0x6a-0x5e
        .rept   12
        .long   0
        .endr
        .rept   12
        .long   128
        .endr
        .rept   12
        .long   0
        .endr
        .space  0x18e-0xfa
        .long   0x11
| A stock icon, 17 x 13 as MIX's headphones: {w, h, 1, pixels, mask}, a u32
| per column, the top row at bit 19, lit = 1. A speaker, dark on the lit tile:
|   ......#......
|   .....##......
|   ....###..#...
|   .######...#..
|   .######.#.#..
|   .######.#.#..
|   .######.#.#..
|   .######...#..
|   ....###..#...
|   .....##......
|   ......#......
        .balign 4
SPEAKER:
        .long   17, 13, 1, SPK_PX, SPK_MASK, 0
SPK_PX: .long   0xfff80000, 0xfff80000, 0xfff80000, 0xf0780000, 0xf0780000, 0xf0780000
        .long   0xe0380000, 0xc0180000, 0x80080000, 0xfff80000, 0xf8f80000, 0xefb80000
        .long   0xf0780000, 0xfff80000, 0xfff80000, 0xfff80000, 0xfff80000
SPK_MASK:
        .rept   17
        .long   0xfff80000
        .endr
| The cells: centres 45, 68, 91 between the rules at 57 and 80; label rows
| 47 and 31, as the stock boxes' labels.
CELLX:  .byte   0x2d, 0x44, 0x5b, 0x2d, 0x44, 0x5b
CELLY:  .byte   0x2f, 0x2f, 0x2f, 0x1f, 0x1f, 0x1f
T_MASTER: .asciz "MASTER"
T_RETA: .asciz  "RETURN A"
T_RETB: .asciz  "RETURN B"
T_LVL:  .asciz  "LVL"
T_MAIN: .asciz  "MAIN"
T_S:    .asciz  "%s"
T_X:    .asciz  "X"
T_LA:   .byte   0x13, 0                | the font's left and right triangles
T_RA:   .byte   0x14, 0
T_VI:   .asciz  "I"
T_VN:   .asciz  "N"
T_VS:   .asciz  "S"
T_V1:   .asciz  "1"
T_V2:   .asciz  "2"
T_S1:   .asciz  "INS 1 SETUP"
T_S2:   .asciz  "INS 2 SETUP"
T_S3:   .asciz  "RET A SETUP"
T_S4:   .asciz  "RET B SETUP"
mx_strip: .byte 0                      | 0 MIXER, 1 MASTER, 2 RETURN A, 3 RETURN B
mx_slot:  .byte 0                      | the strip's row: MASTER 0 INS 1, 1 INS 2; a return: 0 INS 1, 1 SND1, 2 SND2, 3 OUT
mx_encon: .byte 0                      | the knobs' layer is registered
