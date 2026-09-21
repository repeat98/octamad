| PREVIEW VOL -- a sample preview plays at the default AMP VOL, whatever
| the active track's AMP VOL is.
|
| Both preview starters (STATIC 0x400940ac, FLEX 0x40096c54) queue the
| track's preview overrides in the pending record 0x46c7dfda + 32*t (0xff =
| no change; a per-frame routine copies the rest into the live values at
| 0x80000810 + 72*t): the SRC page neutral and the AMP envelope forced
| (ATK 0, HOLD 127, REL 32, BAL 64, XVOL 127) -- but not AMP VOL, so a track
| at VOL 0 previews silent. FUNC+YES and CUE+YES both start here; CUE only
| adds the track's cue and mute bits. Stopping a preview rebuilds the live
| values from the part (0x40001f18), which restores the track's own VOL.
        .text

        .global vol_static
        .global vol_flex

        .equ    AMP_VOL, 15             | pending-record offset: SRC 0..5, LFO 6..11, AMP 12..17
        .equ    VOL_DEFAULT, 64         | the AMP descriptor's default (shown as 0)

| 0x40094296 (STATIC), a0 = the track's pending record. Displaced
| `moveq #32,%d0; move.b %d0,14(%a0)` (REL); d0 is reloaded after.
vol_static:
        moveq   #32,%d0
        move.b  %d0,14(%a0)
        move.b  #VOL_DEFAULT,AMP_VOL(%a0)
        jmp     (0x4009429c).l

| 0x40096eb2 (FLEX), the same with d1.
vol_flex:
        moveq   #32,%d1
        move.b  %d1,14(%a0)
        move.b  #VOL_DEFAULT,AMP_VOL(%a0)
        jmp     (0x40096eb8).l
