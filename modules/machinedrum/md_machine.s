| Machinedrum registration. The Part stores an MD track as FLEX (raw type 1)
| and marks it MD with a signature in that track's NEIGHBOR page-1 slot:
| NEIGHBOR has no parameters (all six slots `---`, PARAM_PAGES.md section 3),
| so stock never reads or writes those six bytes, and the Part saves,
| reloads and copies them with everything else. Every stock reader of the
| machine type therefore sees a FLEX track. Until 24 Sep 2026 the Part held
| raw type 6, and the ~48 stock sites that index a Part's page stores by
| type x 6 (the page-1 writer 0x40054d5c among them) wrote an MD track's
| knob edits into the NEXT track's FLEX slot (MACHINEDRUM_MACHINE.md
| section 12, "MD tracks are FLEX with a signature"). Stock firmware opens
| such a project as a FLEX track.
|
| The signature: 'M', 'D', 1 at Part + 0x2a + track x 30 + 18 (the working
| Part and its SRAM copy 0x100a4ece + part x 0x18b2, as the stock commit
| writes the type byte). The chooser row 6 (MACHINEDRUM) commits FLEX plus
| the signature; any other row clears it. Row 5 stays reserved for POLY.
|
| Displays that name the type of a track resolve MD through md_ui_md_type,
| the working-Part address of the MD track's type byte, which the control
| engine publishes each frame (md_ctl.c): a site whose a0 holds a track's
| type-byte address compares it.
        .text
        .global md_machine_name
        .global md_src_names
        .global md_main_commit
        .global md_src_commit
        .global md_pack_fx2
        .global md_name_a, md_name_b
        .global md_setup_row, md_chooser_row
        .global md_resolve_pb
        .global md_trig_key
        .global md_sig_check

        .equ    MD_ROW, 6                 | the chooser row
        .equ    FLEX, 1
        .equ    SRC_CURSOR, 0x460d5c30
        .equ    BANK_PTR, 0x46c82456
        .equ    PART_IDX, 0x100b14cf
        .equ    UI_TRACK, 0x100b14cc
        .equ    PART_STRIDE, 6322
        .equ    PART_OFF, 0x8ed80         | bank + this = Part 0
        .equ    SRAM_PART, 0x100a4ece     | the SRAM copy of Part 0
        .equ    SIG_OFF, 0x2a + 18        | + track x 30: NEIGHBOR page-1 slot
        .equ    PART_FX2, 8               | + track: the Part's FX2 id
        .equ    LIVE_FX2, 0x80000ecc      | + track: the FX2 id the DSP records carry
        .equ    MD_FX2, 0x1e              | the MD's DSP dispatch id (manifest fx2_id)
        .equ    FLEX_P, 0x400d31ae        | stock FLEX playback descriptor (P)
        .equ    PB_TABLE, 0x400d5f38
        .equ    KEY_ROWS, 0x46100b18      | the panel's held-key rows (PANEL.md 4b)

| md_sig_check: a0 = a Part base, d0 = track 0..7. Returns d0 = 1 when the
| track is MD (type FLEX and the signature), else 0. Keeps every other
| register.
md_sig_check:
        lea     -8(%sp),%sp
        movem.l %d1/%a1,(%sp)
        moveq   #0,%d1
        move.b  0x22(%a0,%d0.l),%d1       | the type byte
        cmpi.l  #FLEX,%d1
        bne.s   .sc_no
        move.l  %d0,%d1
        mulu.w  #30,%d1
        lea     SIG_OFF(%a0,%d1.l),%a1
        move.b  (%a1),%d1                | ColdFire compares a register only
        cmpi.b  #'M',%d1
        bne.s   .sc_no
        move.b  1(%a1),%d1
        cmpi.b  #'D',%d1
        bne.s   .sc_no
        move.b  2(%a1),%d1
        cmpi.b  #1,%d1
        bne.s   .sc_no
        moveq   #1,%d0
        bra.s   .sc_done
.sc_no:
        moveq   #0,%d0
.sc_done:
        movem.l (%sp),%d1/%a1
        lea     8(%sp),%sp
        rts

| md_sig_write: a0 = a Part base, d0 = track, d1 = 1 set / 0 clear.
| Writes the working Part and, for the same part index, its SRAM copy
| (a0 - bank - PART_OFF gives part x stride). Keeps every register.
md_sig_write:
        lea     -16(%sp),%sp
        movem.l %d0-%d2/%a1,(%sp)
        mulu.w  #30,%d0
        lea     SIG_OFF(%a0,%d0.l),%a1
        bsr.s   .sw_one
        move.l  %a0,%d2                   | the SRAM copy: same part offset
        sub.l   (BANK_PTR).l,%d2
        subi.l  #PART_OFF,%d2
        addi.l  #SRAM_PART + SIG_OFF,%d2
        add.l   %d0,%d2
        movea.l %d2,%a1
        bsr.s   .sw_one
        movem.l (%sp),%d0-%d2/%a1
        lea     16(%sp),%sp
        rts
.sw_one:
        tst.l   %d1
        beq.s   .sw_clear
        move.b  #'M',(%a1)
        move.b  #'D',1(%a1)
        move.b  #1,2(%a1)
        rts
.sw_clear:
        move.b  (%a1),%d2                | clear only our own mark; d1 (the
        cmpi.b  #'M',%d2                 | set/clear flag) is read again for
        bne.s   .sw_out                  | the SRAM copy
        clr.b   (%a1)
        clr.b   1(%a1)
        clr.b   2(%a1)
.sw_out:
        rts

md_machine_name:
        move.l  4(%sp),%d0
        cmpi.l  #MD_ROW,%d0
        beq.s   1f
        cmpi.l  #5,%d0
        beq.s   2f
        move.l  %d2,-(%sp)               | displaced stock formatter
        move.l  8(%sp),%d1
        jmp     (0x400334de).l
1:      lea     md_name(%pc),%a0
        move.l  %a0,%d0
        rts
2:      lea     md_reserved_name(%pc),%a0
        move.l  %a0,%d0
        rts

        .balign 4
md_src_names:
        .long   0x400b3eac               | STATIC
        .long   0x400b3e98               | FLEX
        .long   0x400b7c67               | THRU
        .long   0x400b5413               | NEIGHBOR
        .long   0x400b7a63               | PICKUP
        .long   md_reserved_name          | row 5: reserved for POLY
        .long   md_name

| The admission check: a0 = the Part base, d0 = this track (0-based).
| Returns d0 = 1 if the track is T1-T4 and no other track of T1-T4 in the
| Part is MD, else 0. Keeps every other register.
md_admit:
        cmpi.l  #4,%d0
        bcc.s   .no
        lea     -12(%sp),%sp
        movem.l %d1-%d3,(%sp)
        move.l  %d0,%d2                  | this track
        moveq   #0,%d3
.scan:
        cmp.l   %d2,%d3
        beq.s   .next
        move.l  %d3,%d0
        bsr     md_sig_check
        tst.l   %d0
        bne.s   .occupied
.next:
        addq.l  #1,%d3
        cmpi.l  #4,%d3
        bne.s   .scan
        moveq   #1,%d0
        bra.s   .ad_done
.occupied:
        moveq   #0,%d0
.ad_done:
        movem.l (%sp),%d1-%d3
        lea     12(%sp),%sp
        rts
.no:
        moveq   #0,%d0
        rts

| Main machine chooser commit (0x4007981c): a0 = the working Part's type
| byte of track d1, d0 = part x stride, d2 = part, a1 = the bank, d4 = the
| chosen row. Displaced: mvs.b (a0),d3 / move.b d4,(a0) / add.l d1,d0.
md_main_commit:
        cmpi.l  #5,%d4
        beq.w   .reserved
        lea     -12(%sp),%sp
        movem.l %d0-%d1/%a0,(%sp)
        movea.l %a1,%a0                  | the Part base
        adda.l  %d0,%a0
        adda.l  #PART_OFF,%a0
        move.l  %d1,%d0                  | the track
        cmpi.l  #MD_ROW,%d4
        bne.s   .mc_other
        bsr     md_admit
        tst.l   %d0
        beq.s   .mc_refuse
        move.l  %d1,%d0
        moveq   #1,%d1
        bsr     md_sig_write
        moveq   #FLEX,%d4                | the Part stores FLEX
        bra.s   .mc_store
.mc_other:
        moveq   #0,%d1
        bsr     md_sig_write             | any other machine: not MD
.mc_store:
        movem.l (%sp),%d0-%d1/%a0
        lea     12(%sp),%sp
        .word   0x7710,0x1084,0xd081     | displaced: old byte, store d4, add d1,d0
        jmp     (0x40079822).l
.mc_refuse:
        movem.l (%sp),%d0-%d1/%a0
        lea     12(%sp),%sp
        pea     0x30.w
        pea     md_reject_name(%pc)
        jsr     (0x4005a2b8).l
        addq.l  #8,%sp
        jmp     (0x4007989c).l
.reserved:
        pea     0x30.w
        pea     md_reserved_reject(%pc)
        jsr     (0x4005a2b8).l
        addq.l  #8,%sp
        jmp     (0x4007989c).l

| SRC SETUP's machine commit (0x4005a616): a0 = the working Part's type
| byte of track d2, d0 = part x stride, d3 = part, a1 = the bank. The
| stock commit stores the cursor; for MD it stores FLEX and leaves the
| cursor at FLEX, so the code after the store (slot assignment) takes
| FLEX's path. A refusal restores the cursor to the stored machine.
md_src_commit:
        move.l  (SRC_CURSOR).l,%d1
        cmpi.l  #5,%d1
        beq.w   .sr_reserved
        lea     -12(%sp),%sp
        movem.l %d0/%d2/%a0,(%sp)
        movea.l %a1,%a0
        adda.l  %d0,%a0
        adda.l  #PART_OFF,%a0
        move.l  %d2,%d0
        cmpi.l  #MD_ROW,%d1
        bne.s   .sc_other
        bsr     md_admit
        tst.l   %d0
        beq.s   .sc_refuse
        move.l  %d2,%d0
        moveq   #1,%d1
        bsr     md_sig_write
        moveq   #FLEX,%d1
        move.l  %d1,(SRC_CURSOR).l
        bra.s   .sc_go
.sc_other:
        move.l  %d1,-(%sp)
        moveq   #0,%d1
        bsr     md_sig_write
        move.l  (%sp)+,%d1
.sc_go:
        movem.l (%sp),%d0/%d2/%a0
        lea     12(%sp),%sp
        jmp     (0x4005a61c).l
.sc_refuse:
        movem.l (%sp),%d0/%d2/%a0
        lea     12(%sp),%sp
        moveq   #0,%d1
        move.b  (%a0),%d1
        move.l  %d1,(SRC_CURSOR).l
        pea     0x30.w
        pea     md_reject_name(%pc)
        jsr     (0x4005a2b8).l
        addq.l  #8,%sp
        jmp     (0x4005a61c).l
.sr_reserved:
        moveq   #0,%d1
        move.b  (%a0),%d1
        move.l  %d1,(SRC_CURSOR).l
        pea     0x30.w
        pea     md_reserved_reject(%pc)
        jsr     (0x4005a2b8).l
        addq.l  #8,%sp
        jmp     (0x4005a61c).l

| The frame builder's per-track loop, run every frame: find the MD track,
| tell the control engine which it is, and select the MD's DSP dispatch
| for it without writing id 0x1e to the Part's FX2 setting or its chooser.
| d3 counts 8..1, a3 points at this track's record, a0 at the compact copy
| this site writes. That copy is not what the DSP reads: each track's DSP
| record takes its FX2 id from the live byte LIVE_FX2 + track
| (0x40004d38..0x40004d46), which stock refreshes from the Part's FX2 when
| a Part is applied (0x4000938e, 0x4000c41e). So the MD track's live byte
| is set to the MD id here, every frame, and a T1-T4 track that is not MD
| gets its Part's FX2 back if it still carries the MD id (the FX2 chooser
| hides that id, so only this code writes it). Until 25 Sep 2026 this site
| rewrote the compact copy instead, which changes no dispatch: the gates
| passed because their project stored 0x1e as T1's FX2 (measured under
| the port: the live byte came from the card's Part). This remains a
| bridge through the FX2 DSP dispatch until a native machine render seam
| replaces it.
md_pack_fx2:
        lea     -12(%sp),%sp
        movem.l %d1/%a0-%a1,(%sp)
        cmpi.l  #8,%d3
        bne.s   .pack_next
        clr.l   md_ui_md_type
        moveq   #-1,%d0
        move.l  %d0,md_ui_md_track
.pack_next:
        moveq   #8,%d1
        sub.l   %d3,%d1
        cmpi.l  #4,%d1
        bcc.s   .pack_stock
        movea.l (BANK_PTR).l,%a0
        moveq   #0,%d0
        move.b  (PART_IDX).l,%d0
        mulu.w  #PART_STRIDE,%d0
        adda.l  %d0,%a0
        adda.l  #PART_OFF,%a0
        move.l  %d1,%d0
        bsr     md_sig_check
        movea.l #LIVE_FX2,%a1
        adda.l  %d1,%a1                  | this track's live FX2 id
        tst.l   %d0
        beq.s   .pack_unmark
        move.b  #MD_FX2,(%a1)            | the DSP dispatches the MD
        lea     0x22(%a0,%d1.l),%a1       | this signed track's type byte
        move.l  %a1,md_ui_md_type
        move.l  %d1,md_ui_md_track
        move.l  %d1,%d0                  | tell the control engine the MD track
        addq.l  #1,%d0                   | (md_ctl.c: 1 + track, cleared per frame)
        move.l  %d0,md_parent_track
        bra.s   .pack_stock
.pack_unmark:
        move.b  (%a1),%d0
        cmpi.b  #MD_FX2,%d0
        bne.s   .pack_stock
        move.b  PART_FX2(%a0,%d1.l),(%a1) | no longer MD: the Part's own FX2
.pack_stock:
        move.w  0x20(%a3),%d0
        movem.l (%sp),%d1/%a0-%a1
        lea     12(%sp),%sp
        move.w  %d0,(%a0)+
        adda.l  #0x3a,%a2                | displaced
        jmp     (0x4000d150).l

| Name lookups by a track's type: 0x4003d718 and 0x4004c36a index the
| names table by the type byte a0 points at. An MD track reads FLEX there;
| show the control engine's info name instead (md_ui_name, "P05 TRX-SD").
md_name_a:
        bsr.s   md_name_pick
        jmp     (0x4003d722).l
md_name_b:
        bsr.s   md_name_pick
        jmp     (0x4004c374).l
md_name_pick:                             | d0 = type, a0 = its address -> d1
        cmpi.l  #FLEX,%d0
        bne.s   1f
        cmpa.l  md_ui_md_type,%a0
        bne.s   1f
        move.l  #md_ui_name,%d1
        rts
1:      lea     md_src_names(%pc),%a0   | a1 is live at 0x4003d722
        move.l  (%a0,%d0.l*4),%d1
        rts

| SRC SETUP's machine list boxes the committed machine's row
| (0x4003c980: d0 = the type a0 points at, compared with the row d2): an
| MD track boxes MACHINEDRUM, not FLEX. Displaced: mvs.b (a0),d0 /
| lea 24(sp),sp.
md_setup_row:
        mvs.b   (%a0),%d0                | displaced
        lea     24(%sp),%sp
        bsr.s   md_row_type
        jmp     (0x4003c986).l
| The main chooser's box (0x400786c8): the same, then cmp d0,d2 / bne.
md_chooser_row:
        mvs.b   (%a0),%d0                | displaced
        bsr.s   md_row_type
        cmp.l   %d0,%d2
        bne.s   1f
        jmp     (0x400786ce).l
1:      jmp     (0x400786fc).l
md_row_type:
        cmpi.l  #FLEX,%d0
        bne.s   1f
        cmpa.l  md_ui_md_type,%a0
        bne.s   1f
        moveq   #MD_ROW,%d0
1:      rts

| The per-track playback descriptor (0x40031e74, in the resolver
| 0x40031da4: d5 = the type byte a0 points at, d3 the track): an MD track
| gets the control engine's MD page (md_desc_p), every FLEX track stock's
| FLEX page -- never the table entry, which md_ctl.c points at the MD page
| while the selected track is MD (the SETUP window's readers index it by
| the cursor, not by a track). Displaced: mvs.b d5,d0 / lea table,a0.
md_resolve_pb:
        mvs.b   %d5,%d0                  | displaced
        cmpi.l  #FLEX,%d0
        bne.s   1f
        cmpa.l  md_ui_md_type,%a0
        bne.s   2f
        move.l  md_desc_p,%d0
        bne.s   3f
2:      move.l  #FLEX_P,%d0
3:      jmp     (0x40031ed6).l
1:      lea     (PB_TABLE).l,%a0
        jmp     (0x40031ece).l

| A trig key with the MD track's own track key held selects that internal
| part (and plays it once), in and out of grid recording: the stock trig
| handler (0x40060ce0; args key, edge 1 press / 2 release) never tests a
| held track key (WP-D1). Both edges are taken while the track key is held.
| Displaced: move.l 4(sp),d1 / move.l 8(sp),d0.
md_trig_key:
        move.l  4(%sp),%d1
        move.l  8(%sp),%d0
        cmpi.l  #16,%d1
        bcc.s   .tk_stock
        move.l  md_ui_md_track,%d0       | 0..3, or -1 without an MD track
        bmi.s   .tk_reload
        btst    %d0,(KEY_ROWS + 2).l     | row 2 = track keys 0x10..0x17
        beq.s   .tk_reload
        move.l  8(%sp),%d0
        cmpi.l  #1,%d0
        bne.s   .tk_done                 | a release: taken, nothing to do
        move.l  %d1,-(%sp)
        jsr     md_ui_select             | md_ctl.c: select and audition
        addq.l  #4,%sp
.tk_done:
        rts
.tk_reload:
        move.l  8(%sp),%d0
.tk_stock:
        jmp     (0x40060ce8).l

        .data
        .balign 4
        .global md_ui_md_type, md_ui_md_track, md_desc_p, md_ui_name
md_ui_md_type:
        .long 0
md_ui_md_track:
        .long -1
md_desc_p:
        .long 0
md_ui_name:
        .asciz "MACHINEDRUM"
        .balign 4
        .text
md_name:
        .asciz  "MACHINEDRUM"
md_reserved_name:
        .asciz  "RESERVED"
md_reject_name:
        .asciz  "MD: T1-T4, 1/PART"
md_reserved_reject:
        .asciz  "TYPE 5 RESERVED"
        .balign 2
