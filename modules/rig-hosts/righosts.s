| RIG HOSTS -- a new part is born hosted (22 Sep 2026).
|
| The part-defaults initialiser (0x40005638) runs once per track (d3 = the
| track index, 0..7; the loop's back edge is `bnew 0x4000567e` at
| 0x400059ca). Three of its sites read a STOCK descriptor by address:
|
|   4000567e  lea    0x400d47ad,%a0        | FILTER descriptor + 3: id 4
|   40005684  moveb  %a0@,%a2@(0,%d3:l)    | FX1[track] = 4
|   40005688  lea    0x400d4ad1,%a0        | DELAY descriptor + 3: id 8
|   4000568e  moveal %sp@(68),%a1          | the FX2 id row (part + 0x11)
|   40005692  moveb  %a0@,%a1@(8)          | FX2[track] = 8
|   40005696  moveq  #108,%d0              | (next: level bytes; a0, d0 dead)
|
| and, in the per-slot copy of the FX2 page defaults (d2 = the slot):
|
|   40005830  lea    0x400d4ace,%a1        | DELAY descriptor P
|   40005836  lea    %a1@(5e,%d2:l),%a0    | its page-1 default for slot d2
|   4000583a  moveal %d5,%a1 ...           | (a1 reloaded: free)
|   40005840  lea    0x400d4ace,%a1
|   40005846  lea    %a1@(64,%d2:l),%a1    | its page-2 default for slot d2
|   4000584a  moveb  %a1@,%a5@(18)
|
| With stock's ids that gives every new part FX1 = FILTER and FX2 = DELAY
| with DELAY's page bytes -- on this image Spectrum's id with FILTER's bytes
| ("muted and quiet and modulated", Sam, image 52 on the unit) and the bus
| engines with the stock delay's. The three sites are jumps here: FX1 is
| NONE (id 0; the FX1 page keeps FILTER's bytes, which NONE never reads,
| and choosing a station writes its own defaults), FX2 is the rig's id by
| track -- BusDelay on T1, BusVerb on T5, the stock delay (Echo Freeze) on
| T8 the master, SEND everywhere else -- and the FX2 page defaults come
| from THAT id's descriptor through the id table (FX2_IDS[id] = descriptor
| P, the table the build fills). The ids come from the manifests (the
| include the build generates). d0/d1 are live in the copy loop and saved.
|
| Measured under the port: a project name the card does not carry makes
| the firmware create one; its live ids read FX1 0 x8, FX2 6 9 9 9 7 9 9 8.

        .include "remix.inc"           | ID_DELAY, ID_VERB, ID_SEND, ID_ECHO
        .set    FX2_IDS, 0x400d5fdc    | id -> descriptor P (build_bus.py FX2_IDS)
        .set    IDS_NEXT, 0x40005696
        .set    P1_NEXT,  0x4000583a
        .set    P2_NEXT,  0x4000584a

        .text
        .globl  fx_ids, fx2_page1, fx2_page2

| ---- 0x4000567e..0x40005695 (24 bytes): FX1 = NONE, FX2 = the rig's id ----
fx_ids:
        clrb    %a2@(0,%d3:l)           | FX1[track] = NONE
        moveal  %sp@(68),%a1            | displaced (a jmp: the stack is stock's)
        bsr     id_by_track             | d0 = the FX2 id for track d3
        moveb   %d0,%a1@(8)
        jmp     IDS_NEXT

| ---- 0x40005830 (10 bytes): a0 = page-1 default of slot d2, from the rig's id
fx2_page1:
        bsr     desc_by_track           | a1 = descriptor P
        lea     %a1@(0x5e,%d2:l),%a0    | displaced
        jmp     P1_NEXT

| ---- 0x40005840 (10 bytes): a1 = page-2 default of slot d2 ----------------
fx2_page2:
        bsr     desc_by_track
        lea     %a1@(0x64,%d2:l),%a1    | displaced
        jmp     P2_NEXT

| ---- d0 = the FX2 id for track d3 (d1 untouched) ---------------------------
id_by_track:
        moveq   #ID_SEND,%d0
        tstl    %d3
        bne     1f
        moveq   #ID_DELAY,%d0           | track 1: BusDelay
        rts
1:      cmpl    #4,%d3
        bne     2f
        moveq   #ID_VERB,%d0            | track 5: BusVerb
        rts
2:      cmpl    #7,%d3
        bne     3f
        moveq   #ID_ECHO,%d0            | track 8, the master: the stock delay
3:      rts

| ---- a1 = the descriptor P of track d3's FX2 (d0 saved: live in the loop) --
desc_by_track:
        movel   %d0,%sp@-
        bsr     id_by_track
        lea     FX2_IDS,%a1
        moveal  %a1@(0,%d0:l:4),%a1
        movel   %sp@+,%d0
        rts
