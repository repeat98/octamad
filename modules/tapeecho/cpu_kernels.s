| Audio kernels for the fixed-point CPU Tape Echo. No firmware bytes.
| The C/native oracle and full ColdFire test pin arithmetic and ABI.
        .text
        .balign 4
        .global te_filter_block
te_filter_block:
        lea     -44(%sp),%sp
        movem.l %d2-%d7/%a2-%a6,(%sp)
        move.l  56(%sp),%a1
        movem.l (%a1),%d2-%d5
        move.l  16(%a1),%d1
        move.l  52(%sp),%a1
        movem.l (%a1),%a2-%a6
        move.l  48(%sp),%a0
        lea     64(%a0),%a1
        move.l  #8388608,%d6
| d2/d3 input history; d4/d5 output history (both Q5.27); d1 error.
| a2..a6 coefficients; a0 buffer; a1 end; d6 fraction-carry multiplier.
| Swap history roles every sample instead of moving four registers. Two
| samples restore the mapping. Rare overload clamps live off the hot path.
        .macro TE_FILTER_SAMPLE x1,x2,y1,y2
| Consume the old x2 before replacing it with the current input. Each
| product retains its own EMAC truncation; the bounded sum is unchanged.
        mac.l   %d1,%d6,%acc0
        mac.l   \x2,%a4,%acc0
        move.l  (%a0),\x2
        add.l   \x2,\x2
        mac.l   \x2,%a2,%acc0
        mac.l   \x1,%a3,%acc0
        mac.l   \y1,%a5,%acc0
        mac.l   \y2,%a6,%acc0
        move.l  %accext01,%d1
        movclr.l %acc0,%d0
        cmp.l   #268435456,%d0
        bgt     .Lfilter_hi\@
        cmp.l   #-268435456,%d0
        blt     .Lfilter_lo\@
        mvz.b   %d1,%d1
.Lfilter_emit\@:
        move.l  %d0,(%a0)+
        add.l   %d0,%d0
        move.l  %d0,\y2
        .subsection 1
.Lfilter_hi\@:
        move.l  #268435456,%d0
        clr.l   %d1
        bra     .Lfilter_emit\@
.Lfilter_lo\@:
        move.l  #-268435456,%d0
        clr.l   %d1
        bra     .Lfilter_emit\@
        .subsection 0
        .endm
.Lfilter_pair:
        .rept 2
        TE_FILTER_SAMPLE %d2,%d3,%d4,%d5
        TE_FILTER_SAMPLE %d3,%d2,%d5,%d4
        .endr
        cmp.l   %a0,%a1
        bne     .Lfilter_pair
        move.l  56(%sp),%a0
        movem.l %d2-%d5,(%a0)
        move.l  %d1,16(%a0)
        movem.l (%sp),%d2-%d7/%a2-%a6
        lea     44(%sp),%sp
        rts

| Recording, sample-accurate gain ramps and stereo mix. Fixed DRIVE=0.
| Keep live gains and constants in registers for both moving and settled
| controls; no per-sample state traffic or compiler spills. Arithmetic is
| independently reproduced by the native engine, including truncation.
        .balign 4
        .global te_record_block
te_record_block:
        lea     -44(%sp),%sp
        movem.l %d2-%d7/%a2-%a6,(%sp)
        move.l  48(%sp),%a6
        move.l  52(%sp),%a2
        move.l  56(%sp),%a0
        move.l  60(%sp),%a1
        lea     64(%a2),%a3
        move.l  #100193576,%a4
        move.l  #377433008,%a5
        move.l  20(%a6),%d0
        move.l  24(%a6),%d7
        move.l  28(%a6),%d5
        move.l  40(%a6),%d6
        move.l  64(%sp),%d1
        or.l    68(%sp),%d1
        or.l    72(%sp),%d1
        bne     .Lrecord_ramp
| Settled hiss has one signed high word for the entire block.
        swap    %d6
        ext.l   %d6
        tst.l   %d7
        beq     .Lrecord_dry
        cmp.l   #2147483640,%d7
        beq     .Lrecord_wet
        bra     .Lrecord_mix

        .macro TE_CLIP reg,limit
        cmp.l   #\limit,\reg
        bgt     .Lclip_hi\@
        cmp.l   #-\limit-1,\reg
        blt     .Lclip_lo\@
.Lclip_done\@:
        .subsection 1
.Lclip_hi\@:
        move.l  #\limit,\reg
        bra     .Lclip_done\@
.Lclip_lo\@:
        move.l  #-\limit-1,\reg
        bra     .Lclip_done\@
        .subsection 0
        .endm

        .macro TE_RECORD_SAMPLE ramp,mode
        .if \ramp
        add.l   64(%sp),%d7
        add.l   68(%sp),%d5
        add.l   72(%sp),%d6
        .endif
        move.l  #1664525,%d2
        mulu.l  %d2,%d0
        add.l   #1013904223,%d0
        move.l  (%a0),%d3
        move.l  4(%a0),%d4
        asr.l   #5,%d3
        asr.l   #5,%d4
        move.l  %d3,%d2
        add.l   %d4,%d2
        bpl     .Lrecord_nonnegative\@
        addq.l  #1,%d2
.Lrecord_nonnegative\@:
        asr.l   #1,%d2
        mac.l   %d2,%a4,%acc0
        movclr.l %acc0,%d2
        move.l  %d2,%a6
        move.l  (%a2)+,%d1
        mac.l   %d1,%d5,%acc0
        movclr.l %acc0,%d2
        add.l   %d2,%a6
        .if \ramp
        move.l  %d6,%d2
        swap    %d2
        ext.l   %d2
        mac.l   %d2,%d0,%acc0
        .else
        mac.l   %d6,%d0,%acc0
        .endif
        movclr.l %acc0,%d2
| a6 holds the two independently rounded record products. Scale before
| adding hiss, which must retain its low-level Q6.26 precision.
        move.l  %a6,%d1
        lsl.l   #3,%d1
        add.l   %d2,%d1
        cmp.l   #268435456,%d1
        bgt     .Lrec_hi\@
        cmp.l   #-268435456,%d1
        blt     .Lrec_lo\@
.Lrec_emit\@:
        move.l  %d1,(%a1)+
        .if \mode != 0
        .if \ramp
        tst.l   %d7
        beq     .Lrecord_next\@
        .endif
        move.l  -4(%a2),%d1
        mac.l   %d1,%a5,%acc0
        movclr.l %acc0,%d1
        lsl.l   #3,%d1
        .if \mode == 2
        asr.l   #3,%d1
        move.l  %d1,%d3
        move.l  %d1,%d4
        .else
        move.l  %d1,%d2
        sub.l   %d3,%d2
        mac.l   %d2,%d7,%acc0
        movclr.l %acc0,%d2
        add.l   %d2,%d3
        sub.l   %d4,%d1
        mac.l   %d1,%d7,%acc0
        movclr.l %acc0,%d1
        add.l   %d1,%d4
        asr.l   #3,%d3
        asr.l   #3,%d4
        .endif
        TE_CLIP %d3,8388607
        .if \mode == 2
        move.l  %d3,%d4
        .else
        TE_CLIP %d4,8388607
        .endif
        lsl.l   #8,%d3
        lsl.l   #8,%d4
        move.l  %d3,(%a0)
        move.l  %d4,4(%a0)
        .endif
.Lrecord_next\@:
        addq.l  #8,%a0
        .subsection 1
.Lrec_hi\@:
        move.l  #268435456,%d1
        bra     .Lrec_emit\@
.Lrec_lo\@:
        move.l  #-268435456,%d1
        bra     .Lrec_emit\@
        .subsection 0
        .endm
.Lrecord_ramp:
        .rept 2
        TE_RECORD_SAMPLE 1,1
        .endr
        cmp.l   %a2,%a3
        bne     .Lrecord_ramp
        move.l  48(%sp),%a6
        move.l  %d6,40(%a6)
        bra     .Lrecord_done
.Lrecord_mix:
        .rept 2
        TE_RECORD_SAMPLE 0,1
        .endr
        cmp.l   %a2,%a3
        bne     .Lrecord_mix
        bra     .Lrecord_done
.Lrecord_wet:
        .rept 2
        TE_RECORD_SAMPLE 0,2
        .endr
        cmp.l   %a2,%a3
        bne     .Lrecord_wet
        bra     .Lrecord_done
.Lrecord_dry:
        .rept 2
        TE_RECORD_SAMPLE 0,0
        .endr
        cmp.l   %a2,%a3
        bne     .Lrecord_dry
.Lrecord_done:
        move.l  48(%sp),%a6
        move.l  %d0,20(%a6)
        move.l  %d7,24(%a6)
        move.l  %d5,28(%a6)
        movem.l (%sp),%d2-%d7/%a2-%a6
        lea     44(%sp),%sp
        rts

| Record FIR + interpolated tape curve + stereo DMA staging. Incoming
| samples and the two histories are bounded to +/-4 FS; [1,6,1]/8 is
| convex, so the curve's generic +/-8 FS input clamp is unnecessary here.
        .balign 4
        .global te_finish_record
te_finish_record:
        lea     -40(%sp),%sp
        movem.l %d2-%d7/%a2-%a5,(%sp)
        move.l  44(%sp),%a0
        move.l  48(%sp),%a1
        move.l  52(%sp),%a3
        move.l  56(%sp),%a2
        move.l  (%a3),%d1
        move.l  4(%a3),%d2
        lea     64(%a0),%a4
        .macro TE_FINISH_SAMPLE x1,x2
        move.l  (%a0)+,%d0
        move.l  %d0,%d7
        sub.l   \x1,%d0
        sub.l   \x1,%d0
        add.l   \x2,%d0
        asr.l   #3,%d0
        add.l   \x1,%d0
        move.l  %d7,\x2
        move.l  %d0,%d3
        bpl     .Lfinish_positive\@
        neg.l   %d0
.Lfinish_positive\@:
        move.l  %d0,%d4
        swap    %d4
        and.l   #0x3ffc,%d4
        lea     (%a2,%d4.l),%a5
        move.l  (%a5),%d6
        move.l  4(%a5),%d5
        sub.l   %d6,%d5
        and.l   #262143,%d0
        moveq   #13,%d4
        lsl.l   %d4,%d0
        mac.l   %d0,%d5,%acc0
        movclr.l %acc0,%d5
        add.l   %d6,%d5
        tst.l   %d3
        bpl     .Lfinish_emit\@
        neg.l   %d5
.Lfinish_emit\@:
        lsl.l   #5,%d5
        move.l  %d5,(%a1)+
        move.l  %d5,(%a1)+
        .endm
.Lfinish_record:
        TE_FINISH_SAMPLE %d1,%d2
        TE_FINISH_SAMPLE %d2,%d1
        cmp.l   %a0,%a4
        bne     .Lfinish_record
        move.l  %d1,(%a3)
        move.l  %d2,4(%a3)
        movem.l (%sp),%d2-%d7/%a2-%a5
        lea     40(%sp),%sp
        rts

| Settled full-wet fast path: record construction, [1,6,1]/8 FIR, tape
| curve, stereo DMA staging, and mono wet output in one pass. Arithmetic
| matches the separate kernels except for the deliberate full-wet change:
| clip once and duplicate instead of retaining a dry-dependent one-LSB quirk.
        .balign 4
        .global te_record_wet_finish
te_record_wet_finish:
        lea     -44(%sp),%sp
        movem.l %d2-%d7/%a2-%a6,(%sp)
        move.l  48(%sp),%a6
        move.l  52(%sp),%a2
        move.l  56(%sp),%a0
        move.l  60(%sp),%a1
        lea     64(%a2),%a3
        move.l  20(%a6),%d0
        move.l  28(%a6),%d5
        move.l  40(%a6),%d6
        swap    %d6
        ext.l   %d6
        move.l  44(%a6),%d7
        move.l  48(%a6),%d4
        move.l  #100193576,%a5
        move.l  #377433008,%a6
        .macro TE_WET_FINISH_SAMPLE x1,x2
        move.l  #1664525,%d2
        mulu.l  %d2,%d0
        add.l   #1013904223,%d0
        move.l  (%a0),%d3
        move.l  4(%a0),%d2
        asr.l   #5,%d3
        asr.l   #5,%d2
        move.l  %d3,%d1
        add.l   %d2,%d1
        bpl     .Lwet_nonnegative\@
        addq.l  #1,%d1
.Lwet_nonnegative\@:
        asr.l   #1,%d1
        mac.l   %d1,%a5,%acc0
        movclr.l %acc0,%d1
        move.l  %d1,%d3
        move.l  (%a2)+,%d1
        mac.l   %d1,%d5,%acc0
        movclr.l %acc0,%d2
        add.l   %d2,%d3
        mac.l   %d6,%d0,%acc0
        movclr.l %acc0,%d2
        lsl.l   #3,%d3
        add.l   %d2,%d3
        cmp.l   #268435456,%d3
        bgt     .Lwet_rec_hi\@
        cmp.l   #-268435456,%d3
        blt     .Lwet_rec_lo\@
.Lwet_rec_ready\@:
| d3 is current record input; rotate FIR histories in the unrolled pair.
        move.l  %d3,%d2
        sub.l   \x1,%d2
        sub.l   \x1,%d2
        add.l   \x2,%d2
        asr.l   #3,%d2
        add.l   \x1,%d2
        move.l  %d3,\x2
        move.l  %d2,%d3
        bpl     .Lwet_curve_positive\@
        neg.l   %d2
.Lwet_curve_positive\@:
        move.l  %d2,%d1
        swap    %d1
        and.l   #0x3ffc,%d1
        lea     te_curve,%a4
        lea     (%a4,%d1.l),%a4
        and.l   #262143,%d2
        moveq   #13,%d1
        lsl.l   %d1,%d2
        move.l  4(%a4),%d1
        move.l  (%a4),%a4
        sub.l   %a4,%d1
        mac.l   %d2,%d1,%acc0
        movclr.l %acc0,%d1
        add.l   %a4,%d1
        tst.l   %d3
        bpl     .Lwet_curve_sign\@
        neg.l   %d1
.Lwet_curve_sign\@:
        lsl.l   #5,%d1
        move.l  %d1,(%a1)+
        move.l  %d1,(%a1)+
| Full-wet output: makeup product is already in Q23 after movclr.
        move.l  -4(%a2),%d1
        mac.l   %d1,%a6,%acc0
        movclr.l %acc0,%d1
        TE_CLIP %d1,8388607
        lsl.l   #8,%d1
        move.l  %d1,(%a0)+
        move.l  %d1,(%a0)+
        .subsection 1
.Lwet_rec_hi\@:
        move.l  #268435456,%d3
        bra     .Lwet_rec_ready\@
.Lwet_rec_lo\@:
        move.l  #-268435456,%d3
        bra     .Lwet_rec_ready\@
        .subsection 0
        .endm
.Lwet_finish_loop:
        TE_WET_FINISH_SAMPLE %d7,%d4
        TE_WET_FINISH_SAMPLE %d4,%d7
        cmp.l   %a2,%a3
        bne     .Lwet_finish_loop
        move.l  48(%sp),%a6
        move.l  %d0,20(%a6)
        move.l  %d7,44(%a6)
        move.l  %d4,48(%a6)
        movem.l (%sp),%d2-%d7/%a2-%a6
        lea     44(%sp),%sp
        rts

| A bounded contiguous head block, after the C wrapper has checked history
| and the wrap seam. Fractional interpolation matches the general reader;
| no sample-level bounds/geometry checks or redundant unity gain remain.
        .balign 4
        .global te_read_linear
te_read_linear:
        lea     -44(%sp),%sp
        movem.l %d2-%d7/%a2-%a6,(%sp)
        move.l  48(%sp),%a0
        move.l  52(%sp),%a1
        move.l  56(%sp),%d0
        move.l  60(%sp),%d1
        move.l  64(%sp),%d2
        lea     64(%a0),%a6
        tst.l   %d2
        bne     .Lread_moving
| Constant TIME/WOW offset: the fraction is fixed and every address is
| adjacent. Read the first endpoint once, then advance one sample at a time.
        asr.l   #8,%d1
        sub.l   %d1,%d0
        move.l  %d0,%d7
        moveq   #23,%d4
        lsl.l   %d4,%d7
        and.l   #0x7f800000,%d7
        lsr.l   #8,%d0
        lsl.l   #3,%d0
        lea     (%a1,%d0.l),%a1
        move.l  (%a1),%d3
        asr.l   #5,%d3
        .macro TE_READ_FIXED older,newer
        move.l  8(%a1),\newer
        addq.l  #8,%a1
        asr.l   #5,\newer
        move.l  \newer,%d6
        sub.l   \older,%d6
        mac.l   %d6,%d7,%acc0
        movclr.l %acc0,%d6
        add.l   \older,%d6
        move.l  %d6,(%a0)+
        .endm
.Lread_fixed:
        TE_READ_FIXED %d3,%d5
        TE_READ_FIXED %d5,%d3
        cmp.l   %a0,%a6
        bne     .Lread_fixed
        bra     .Lread_done
.Lread_moving:
| Anchor the pointer at floor(base/256). Keep only its fractional part
| in a Q16 read phase: (base&255)*256 - wobble + 255. The +255 preserves
| base - floor(wobble/256) exactly, including negative offsets. Keeping
| the integer ring address out of this phase avoids overflow on a 4s ring.
        neg.l   %d1
        mvz.b   %d0,%d4
        lsl.l   #8,%d4
        add.l   %d4,%d1
| Subtract one sample so the first preincrement applies only -step.
        add.l   #-65281,%d1
        neg.l   %d2
        add.l   #65536,%d2
        asr.l   #8,%d0
        lsl.l   #3,%d0
        lea     (%a1,%d0.l),%a1
        moveq   #15,%d4
        sub.l   %a4,%a4
        .macro TE_READ_SAMPLE older,newer
        add.l   %d2,%d1
        move.l  %d1,%d7
        lsl.l   %d4,%d7
        and.l   #0x7f800000,%d7
        move.l  %d1,%d0
        swap    %d0
        ext.l   %d0
| Form the byte offset explicitly: scaled-*8 loads fault on the hardware.
        lsl.l   #3,%d0
        lea     (%a1,%d0.l),%a2
| Alternating registers already hold the preceding read's newer sample.
| Repeated/skipped addresses reload; only overlap skips an uncached load.
        cmp.l   %a2,%a4
        beq     .Lread_new\@
        move.l  (%a2),\older
        asr.l   #5,\older
.Lread_new\@:
        move.l  8(%a2),\newer
        lea     8(%a2),%a4
        asr.l   #5,\newer
        move.l  \newer,%d6
        sub.l   \older,%d6
        mac.l   %d6,%d7,%acc0
        movclr.l %acc0,%d6
        add.l   \older,%d6
        move.l  %d6,(%a0)+
        .endm
.Lread_linear:
        TE_READ_SAMPLE %d3,%d5
        TE_READ_SAMPLE %d5,%d3
        cmp.l   %a0,%a6
        bne     .Lread_linear
.Lread_done:
        movem.l (%sp),%d2-%d7/%a2-%a6
        lea     44(%sp),%sp
        rts
