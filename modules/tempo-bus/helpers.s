| TEMPO BUS helpers -- the host lookup and the value read/write, linked
| before tempobus.s (which calls them), pinned at 0x400d24d0.
        .set    WINH,     0x460d16a0   | long: TEMPO window handle, 0 = closed
        .set    SCRDIRTY, 0x46c7c72c   | long: screen refresh request
        .set    CLEAR,    0x40035624   | (surface): the stock TEMPO draw's first call
        .set    FONT,     0x400ba876   | the small UI font
        .set    TEXT,     0x40012bd8   | (font, surf, x, y, limit, str)
        .set    TWIDTH,   0x40012f30   | (font, limit, str) -> pixels
        .set    ICON,     0x400128a8   | (icon, surf, x, y)
        .set    RULE,     0x40011910   | (surf, x, y, x2, 1)
        .set    BOX,      0x4007efd0   | (surf, x, y, w, h, title, 0, focused)
        .set    INVERT,   0x40012254   | (surf, x1, y1, x2, y2, -1)
        .set    SPRINTF,  0x40013a08   | (buf, fmt, ...)
        .set    TEMPOGET, 0x4009c5f4   | (&whole, &tenths)
        .set    TICON,    0x400cbc5c   | CONTROL's category icon, as CONTROL INPUT
        .set    LPUSH,    0x40031494   | (layer): register an input layer
        .set    LPOP,     0x4003146c   | (layer): unregister it
        .set    PUSHED,   0x4003171c   | (key): nonzero while that key is held
        .set    P1WRITE,  0x40054cd8   | (track, flat, value): page-1 writer
        .set    P1TOKEN,  0x54500000
| P1TOKEN goes on the stack above the writer's three arguments. With
| Octakit in the image the writer's last store (0x40054fec) runs her check,
| which halts unless that word's top half is GK_TRACK_PARAMETER_TOKEN_ARMED
| (her abi.inc; her own wrapper pushes it there). Stock ignores the word.
| modules/octakit/manifest.py refuses a build whose abi.inc changes it.
        .set    DESC2,    0x400d5fdc   | FX2 descriptor table [id] -> P
        .set    DBPTR,    0x46c82456   | long: Part DB base
        .set    PARTB,    0x80000003   | byte: the current part
        .set    IDOFF,    0x8ed88      | Part: FX2 id per track
        .set    P1OFF,    0x8ee9a      | Part: page-1 values, track*24, FX2 at +18
        .set    P2OFF,    0x8f084      | Part: FX2 page-2 values, track*30
        .set    SHADOW,   0x100a51d2   | FX2 page-2 shadow: +part*6322+track*30+slot2
        .set    LIVEB,    0x80000810   | live block, 72 B per track; FX2 page 2 at +0x38
        .set    CHGBITS,  0x95048      | DB+: |= 1<<part
        .set    MODBITS,  0x100b145e   | byte: |= 1<<part
        .set    CHGFLAG,  0x9b332      | DB+: long = 1
        .set    GCHG,     0x100f8598   | long = 1
        .set    NAMES,    0x16         | P+: twelve 6-byte names
        .set    MINS,     0x6a         | P+: twelve u32 minimums
        .set    COUNTS,   0x9a         | P+: twelve u32 value counts
        .set    FMTS,     0xca         | P+: twelve formatter pointers, 0 = plain
        .set    ROWS,     4            | rows visible per box
        .set    BOXW,     53
        .set    BOXH,     34

        .weak   CC_MODEDEF2            | MODE DEFAULTS' re-default, when present

        .text
        .globl  engine, getval, setval, rows, NV, VIS
| ---- engine: d0 = box -> d4 = host track or -1, a3 = the engine's
| descriptor P, a4 = DB + part*6322, d5 = part. Clobbers d0/a0.
engine: lea     ENGIDS,%a0
        moveq   #0,%d4
        moveb   %a0@(0,%d0:l),%d4      | the engine's FX2 id
        lea     DESC2,%a0
        moveal  %a0@(0,%d4:l:4),%a3
        moveq   #0,%d5
        moveb   PARTB,%d5
        movel   #6322,%d0
        mulu.l  %d5,%d0
        addl    DBPTR,%d0
        moveal  %d0,%a4
        moveal  %a4,%a0
        addal   #IDOFF,%a0
        movel   %d4,%d0                | d0 = id
        moveq   #0,%d4
1:      cmpb    %a0@(0,%d4:l),%d0
        beq.s   2f
        addql   #1,%d4
        cmpil   #8,%d4
        blt.s   1b
        moveq   #-1,%d4
2:      rts

| ---- getval: d4 = track, d6 = slot, a4 = DB+part -> d2 = the stored value
getval: moveal  %a4,%a0
        moveq   #6,%d0
        cmpl    %d0,%d6
        bge.s   1f
        moveq   #24,%d0
        mulu.l  %d4,%d0
        addal   #P1OFF+18,%a0
        bra.s   2f
1:      moveq   #30,%d0
        mulu.l  %d4,%d0
        addal   #P2OFF-6,%a0
2:      addal   %d0,%a0
        moveq   #0,%d2
        moveb   %a0@(0,%d6:l),%d2
        rts

| ---- setval: d4 = track, d5 = part, d6 = slot, d2 = value, a4 = DB+part
setval: moveq   #6,%d0
        cmpl    %d0,%d6
        bge.s   p2
        movel   #P1TOKEN,%sp@-         | page 1: the stock writer, Octakit's token above its arguments
        movel   %d2,%sp@-
        moveq   #24,%d0
        addl    %d6,%d0
        movel   %d0,%sp@-
        movel   %d4,%sp@-
        jsr     P1WRITE
        lea     %sp@(16),%sp
        rts
p2:     movel   %d6,%d3
        subql   #6,%d3                 | d3 = slot2
        moveq   #30,%d0
        mulu.l  %d4,%d0
        addl    %d3,%d0                | d0 = track*30 + slot2
        moveal  %a4,%a0
        addal   %d0,%a0
        addal   #P2OFF,%a0
        moveb   %d2,%a0@               | Part
        movel   %a4,%d1
        subl    DBPTR,%d1              | part*6322
        addl    %d0,%d1
        addil   #SHADOW,%d1
        moveal  %d1,%a0
        moveb   %d2,%a0@               | shadow
        moveq   #72,%d0
        mulu.l  %d4,%d0
        addl    %d3,%d0
        lea     LIVEB+0x38,%a0
        moveb   %d2,%a0@(0,%d0:l)      | live lane
        moveq   #1,%d0
        lsll    %d5,%d0                | 1 << part
        moveal  DBPTR,%a0
        moveal  %a0,%a1
        addal   #CHGBITS,%a1
        moveb   %a1@,%d1
        orl     %d0,%d1
        moveb   %d1,%a1@               | DB+0x95048 |= 1<<part
        moveb   MODBITS,%d1
        orl     %d0,%d1
        moveb   %d1,MODBITS            | 0x100b145e |= 1<<part
        addal   #CHGFLAG,%a0
        moveq   #1,%d1
        movel   %d1,%a0@               | DB+0x9b332 = 1
        movel   %d1,GCHG               | 0x100f8598 = 1
        lea     CC_MODEDEF2,%a0        | a2 = slot2, d2 = value, d4 = track,
        cmpal   #0,%a0                 | d5 = part (its register contract)
        beq.s   1f
        moveal  %d3,%a2
        jsr     %a0@
1:      rts

| ---- rows: d1 = box, a2 = its names table (NTABS[box], as the mode cave
| left it) -> VIS[box] = the named slots whose name is not "---", MODE first,
| NV[box] = their count, d3 = the count. Clobbers d0/d2/d5/a0/a1.
rows:   movel   %d4,%sp@-
        movel   %d1,%d0
        mulu.w  #12,%d0
        lea     VIS,%a1
        addal   %d0,%a1                | a1 = VIS[box]
        lea     NAMED,%a0
        movew   %a0@(0,%d1:l:2),%d2    | the named slots, bit per slot
        lea     ORDER,%a0
        addal   %d0,%a0                | a0 = ORDER[box], its 12 slots in row order
        moveq   #12,%d3                | slots left to look at
        moveq   #0,%d5                 | the rows listed
1:      moveq   #0,%d0
        moveb   %a0@+,%d0              | the slot
        btst    %d0,%d2
        beq.s   2f
        movel   %d0,%d4
        mulu.w  #6,%d4
        moveb   %a2@(0,%d4:l),%d4      | the screen's name for the slot
        cmpib   #0x2d,%d4              | '-'
        beq.s   2f
        moveb   %d0,%a1@+
        addql   #1,%d5
2:      subql   #1,%d3
        bne.s   1b
        lea     NV,%a0
        moveb   %d5,%a0@(0,%d1:l)
        movel   %d5,%d3
        movel   %sp@+,%d4
        rts

        .include "remix.inc"           | ENGIDS, NAMED, the name tables
        ORDERTAB                       | ORDER: per box, the slots in row order (the manifest's ROW_ORDER); NAMED leaves out 0, 1
        NAMETAB_0                      | the delay's: NAMES_<its id>
NV:     .byte   0, 0                   | the rows listed per box, by the last draw
VIS:    .space  24                     | their slots, 12 per box
