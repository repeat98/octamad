| Machinedrum machine registration (raw Part type 6). Type 5 remains
| reserved for POLY. The stock sample configuration code sees FLEX for MD;
| the Part and its machine chooser retain the distinct type 6.
        .text
        .global md_config_type
        .global md_live_type
        .global md_machine_name
        .global md_src_names
        .global md_main_commit
        .global md_src_commit
        .global md_pack_fx2

        .equ    MD_TYPE, 6
        .equ    SRC_CURSOR, 0x460d5c30

md_config_type:
        .word   0x7130,0x0800             | displaced mvs.b (a0,d0.l),d0
        cmpi.l  #5,%d0                    | reserved POLY value is safe to load
        beq.s   1f
        cmpi.l  #MD_TYPE,%d0
        bne.s   2f
1:
        moveq   #1,%d0                    | FLEX configuration layout
2:      movea.l %d0,%a5
        add.l   %d0,%d0
        jmp     (0x4000c0de).l

md_live_type:
        .word   0x7332,0x2800             | displaced mvs.b (a2,d2.l),d1
        cmpi.l  #5,%d1
        beq.s   1f
        cmpi.l  #MD_TYPE,%d1
        bne.s   2f
1:
        moveq   #1,%d1
        move.b  %d1,(%a2,%d2.l)
2:      moveq   #7,%d0
        and.l   %d1,%d0
        jmp     (0x4000bff0).l

md_machine_name:
        move.l  4(%sp),%d0
        cmpi.l  #MD_TYPE,%d0
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
        .long   md_reserved_name          | serialized type 5: POLY
        .long   md_name

| The common admission check uses the address of this track's machine byte
| in a0 and its zero-based track index in d0. It preserves every register
| except d0 and returns 1 if the same track already owns MD, 0 on refusal.
md_admit:
        cmpi.l  #4,%d0
        bcc.s   .no
        lea     -16(%sp),%sp
        movem.l %d1-%d2/%a0-%a1,(%sp)
        movea.l %a0,%a1
        suba.l  %d0,%a1                  | first track in the active Part
        moveq   #4,%d2
.scan:
        cmpa.l  %a0,%a1
        beq.s   .next
        moveq   #0,%d1
        move.b  (%a1),%d1
        cmpi.l  #MD_TYPE,%d1
        beq.s   .occupied
.next:
        addq.l  #1,%a1
        subq.l  #1,%d2
        bne.s   .scan
        moveq   #1,%d0
        bra.s   .ad_done
.occupied:
        moveq   #0,%d0
.ad_done:
        movem.l (%sp),%d1-%d2/%a0-%a1
        lea     16(%sp),%sp
        rts
.no:
        moveq   #0,%d0
        rts

| Main machine chooser: a0 points to the Part's machine byte; d1 is track
| and d4 is the selected type. The rejected choice leaves Part untouched.
md_main_commit:
        cmpi.l  #5,%d4
        beq.w   .reserved
        cmpi.l  #MD_TYPE,%d4
        bne.s   .commit
        lea     -20(%sp),%sp
        movem.l %d0-%d2/%a0-%a1,(%sp)
        move.l  %d1,%d0
        bsr     md_admit
        tst.l   %d0
        movem.l (%sp),%d0-%d2/%a0-%a1
        lea     20(%sp),%sp
        bne.s   .commit
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
.commit:
        .word   0x7710,0x1084,0xd081   | displaced: old byte, store d4, add d1,d0
        jmp     (0x40079822).l

| SRC SETUP's independent machine chooser. On refusal, keep its previous
| machine and restore the cursor; the stock commit then writes the old type.
md_src_commit:
        move.l  (SRC_CURSOR).l,%d1
        cmpi.l  #5,%d1
        beq.w   .sr_reserved
        cmpi.l  #MD_TYPE,%d1
        bne.s   .sc_done
        lea     -16(%sp),%sp
        movem.l %d0/%d2/%a0-%a1,(%sp)
        move.l  %d2,%d0
        bsr     md_admit
        tst.l   %d0
        movem.l (%sp),%d0/%d2/%a0-%a1
        lea     16(%sp),%sp
        bne.s   .sc_done
        moveq   #0,%d1
        move.b  (%a0),%d1
        move.l  %d1,(SRC_CURSOR).l
        pea     0x30.w
        pea     md_reject_name(%pc)
        jsr     (0x4005a2b8).l
        addq.l  #8,%sp
.sc_done:
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

| The stock frame builder copies each track's two FX setup bytes into its
| transient DSP snapshot here. Select the MD dispatch for a raw MD machine
| without writing id 0x1e to the Part's FX2 setting or its visible chooser.
| d3 counts 8..1, a3 points at this track's source record, a0 at its
| destination. This remains a bridge through the FX2 DSP dispatch until the
| native machine render seam replaces it.
md_pack_fx2:
        lea     -12(%sp),%sp
        movem.l %d1-%d2/%a1,(%sp)
        moveq   #8,%d1
        sub.l   %d3,%d1
        cmpi.l  #4,%d1
        bcc.s   .pack_stock
        movea.l (0x46c82456).l,%a1
        moveq   #0,%d2
        move.b  (0x100b14cf).l,%d2
        move.l  #6322,%d0
        mulu.l  %d0,%d2
        adda.l  %d2,%a1
        adda.l  %d1,%a1
        adda.l  #0x8eda2,%a1
        moveq   #0,%d2
        move.b  (%a1),%d2
        cmpi.l  #MD_TYPE,%d2
        bne.s   .pack_stock
        move.l  %d1,%d0                  | tell the control engine the MD track
        addq.l  #1,%d0                   | (md_ctl.c: 1 + track, cleared per frame)
        move.l  %d0,md_parent_track
        moveq   #0,%d0
        move.w  0x20(%a3),%d0
        andi.l  #0xff00,%d0
        ori.l   #0x1e,%d0
        bra.s   .pack_write
.pack_stock:
        move.w  0x20(%a3),%d0
.pack_write:
        movem.l (%sp),%d1-%d2/%a1
        lea     12(%sp),%sp
        move.w  %d0,(%a0)+
        adda.l  #0x3a,%a2                | displaced
        jmp     (0x4000d150).l

md_name:
        .asciz  "MACHINEDRUM"
md_reserved_name:
        .asciz  "RESERVED"
md_reject_name:
        .asciz  "MD: T1-T4, 1/PART"
md_reserved_reject:
        .asciz  "TYPE 5 RESERVED"
        .balign 2
