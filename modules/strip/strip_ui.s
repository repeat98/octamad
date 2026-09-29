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
        .equ    STRIPS,   2            | MIXER, MASTER

        .text
        .globl  mx_push, mx_pop, mx_draw, mx_strip, mx_slot

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
mx_pop: bsr.w   encoff
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
        bmi.s   9f
        bra.s   2f
1:      addq.l  #1,%d0                 | RIGHT: MASTER is the last, for now
        moveq   #STRIPS,%d1
        cmp.l   %d1,%d0
        bge.s   9f
2:      move.b  %d0,mx_strip
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
        moveq   #0,%d0                 | UP: INS 1
        moveq   #KDOWN,%d1
        cmp.l   4(%sp),%d1
        bne.s   1f
        moveq   #1,%d0                 | DOWN: INS 2
1:      moveq   #0,%d1
        move.b  mx_slot,%d1
        cmp.l   %d1,%d0
        beq.s   9f
        move.b  %d0,mx_slot
        bsr.w   encoff                 | the knobs take the new slot's tails
        bsr.w   encon
        bra.w   mx_draw
9:      rts

| ---- LEVEL on MASTER: MAIN, the stock handler (it redraws, marks EDITED) --
mx_lvl: tst.l   WINH
        beq.w   gone
        jmp     MAINH

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
        bsr.w   mx_draw
        moveq   #1,%d0
        move.l  %d0,EDITED
eout:   movem.l (%sp),%d2-%d4/%a2-%a3
        lea     20(%sp),%sp
        rts

| slot: a2 = the shown slot's model, a3 = its effect's descriptor P; Z set
| when the slot is empty (clobbers d0/a0)
slot:   moveq   #0,%d0
        move.b  mx_slot,%d0
        lsl.l   #4,%d0
        lea     strip_model,%a2
        add.l   %d0,%a2
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
        movem.l (%sp),%d2-%d7/%a2-%a5
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
        moveq   #0xd,%d0
        moveq   #0x2f,%d1
        bsr.w   ctext
        moveq   #4,%d0                 | MAIN's value where MIX's crossfade is
        moveq   #0x26,%d1
        moveq   #6,%d2                 | LEVEL's encoder
        moveq   #0,%d3
        move.b  MAINV,%d3
        lea     SIGNED,%a0
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
        lea     T_VI,%a0
        moveq   #0x2c,%d1
        bsr.w   vchar
        lea     T_VN,%a0
        moveq   #0x26,%d1
        bsr.w   vchar
        lea     T_VS,%a0
        moveq   #0x20,%d1
        bsr.w   vchar
        lea     T_V1,%a0
        tst.b   mx_slot
        beq.s   1f
        lea     T_V2,%a0
1:      moveq   #0x1a,%d1
        bsr.w   vchar
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
TITLES: .long   T_MIXER, T_MASTER
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
mx_strip: .byte 0                      | 0 MIXER, 1 MASTER
mx_slot:  .byte 0                      | MASTER's: 0 INS 1, 1 INS 2
mx_encon: .byte 0                      | the knobs' layer is registered
