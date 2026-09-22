| RIG HOSTS -- a new part is born hosted (22 Sep 2026).
|
| The part-defaults initialiser (0x40005638) runs once per track (d3 = the
| track index, 0..7; the loop's back edge is `bnew 0x4000567e` at
| 0x400059ca) and writes the track's FX2 id from the stock DELAY
| descriptor's id byte:
|
|   40005688  lea    0x400d4ad1,%a0        | DELAY descriptor + 3: id 8
|   4000568e  moveal %sp@(68),%a1          | the FX2 id row (part + 0x11)
|   40005692  moveb  %a0@,%a1@(8)          | FX2[track] = 8
|   40005696  moveq  #108,%d0              | (next: level bytes; a0, d0 dead)
|
| Those fourteen bytes are a `jmp fx2_default` (the Detour, pad_to 14); this
| unit replays the row load and writes the rig's id instead: BusDelay on T1,
| BusVerb on T5, the stock delay (Echo Freeze) on T8 the master, SEND
| everywhere else -- so a project made on the unit
| hosts the bus with no chooser row and no stamp. The ids come from the
| manifests (the include the build generates). a0 and d0 are dead at the
| jump-back; a1 is what stock needs (it writes %a1@(34) next).
|
| Measured under the port: a project name the card does not carry makes
| the firmware create one, and its live FX2 ids read 6 9 9 9 7 9 9 8.

        .include "remix.inc"           | ID_DELAY, ID_VERB, ID_SEND from the manifests
        .set    NEXT, 0x40005696

        .text
        .globl  fx2_default
fx2_default:
        moveal  %sp@(68),%a1            | displaced (a jmp: the stack is stock's)
        moveq   #ID_SEND,%d0
        tstl    %d3
        bne     3f
        moveq   #ID_DELAY,%d0           | track 1: BusDelay
        bra     2f
3:      cmpl    #4,%d3
        bne     4f
        moveq   #ID_VERB,%d0            | track 5: BusVerb
        bra     2f
4:      cmpl    #7,%d3
        bne     2f
        moveq   #ID_ECHO,%d0            | track 8, the master: the stock delay
2:      moveb   %d0,%a1@(8)             | (Echo Freeze, ColdFire; its DSP dispatch
        jmp     NEXT                    | is stock's, no chooser row)
