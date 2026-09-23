| Audio kernels for the fixed-point CPU Tape Echo. No firmware bytes.
| The C/native oracle and full ColdFire test pin arithmetic and ABI.
| Written the way stock's delay loops are (0x40003664/0x40003734): EMAC
| multiply-with-load, accumulator loads, several accumulators, and the
| saturating MOVCLR read-out (MACSR OMC) instead of explicit clamps.
| Every EMAC form used here has sites in stock 1.40C. Each accumulation
| ends in MOVCLR, so all four accumulators are empty on return.
        .text

| Both playback sections in one pass over the 16-sample block, in place.
| te_filter_block(buffer, lp, z): z = {x1,x2,y1,y2,w1,w2,err_hp,err_lp}.
| Low cut:  y = g*(x - 2*x1 + x2) + y1 + (a1-1)*y1 + a2*y2   (acc0)
| Tone:     w = gl*(y + 2*y1 + y2) + w1 + (bl-1)*w1 + cl*w2  (acc2)
| The tone section's input history IS the low cut's output history. Both
| carry their eight low accumulator bits to the next sample (fraction
| saving). d0/d1 x, d2/d3 y, d4/d5 w histories swap roles every sample;
| a1-a3 low-cut operands, a4 the carry scale, a6 streams the tone operands
| from lp[] through multiply-with-load.
        .balign 4
        .global te_filter_block
te_filter_block:
        lea     -48(%sp),%sp
        movem.l %d2-%d7/%a2-%a6,(%sp)
        move.l  52(%sp),%a0
        lea     64(%a0),%a1
        move.l  %a1,44(%sp)
        move.l  60(%sp),%a1
        movem.l (%a1),%d0-%d7
        move.l  56(%sp),%a5
        lea     te_hp,%a4
        movem.l (%a4),%a1-%a3
        move.l  #8388608,%a4
        move.l  (%a5),%a6
        .macro TE_FILTER_SAMPLE x1,x2,y1,y2,w1,w2
        move.l  \y1,%acc0
        mac.l   %d6,%a4,%acc0
        mac.l   \x2,%a1,(%a0),\x2,%acc0
        mac.l   \x2,%a1,%acc0
        msac.l  \x1,%a1,%acc0
        msac.l  \x1,%a1,%acc0
        mac.l   \y1,%a2,%acc0
        mac.l   \y2,%a3,%acc0
| Tone terms that need the oldest low-cut output before it is replaced.
        move.l  \w1,%acc2
        mac.l   %d7,%a4,%acc2
        mac.l   \y2,%a6,4(%a5),%a6,%acc2
        mac.l   \w1,%a6,8(%a5),%a6,%acc2
        mac.l   \w2,%a6,(%a5),%a6,%acc2
        move.l  %accext01,%d6
        movclr.l %acc0,\y2
        mvz.b   %d6,%d6
        mac.l   \y2,%a6,%acc2
        mac.l   \y1,%a6,%acc2
        mac.l   \y1,%a6,%acc2
        move.l  %accext23,%d7
        movclr.l %acc2,\w2
        mvz.b   %d7,%d7
        move.l  \w2,(%a0)+
        .endm
.Lfilter_pair:
        TE_FILTER_SAMPLE %d0,%d1,%d2,%d3,%d4,%d5
        TE_FILTER_SAMPLE %d1,%d0,%d3,%d2,%d5,%d4
        cmpa.l  44(%sp),%a0
        bne     .Lfilter_pair
        move.l  60(%sp),%a1
        movem.l %d0-%d7,(%a1)
        movem.l (%sp),%d2-%d7/%a2-%a6
        lea     48(%sp),%sp
        rts

| Record sum, [1,6,1]/8 FIR, signed tape curve, stereo DMA staging and the
| output mix in one pass. te_tape_block(s, wet, audio, record, dm, df, dn).
| The record sum is one saturating accumulator (Q3.29, +/-4 FS):
| drive*L + drive*R (drive/2 each) + 2 x feedback*wet + hiss*rng. The FIR
| and curve index run in Q6.26. Settled full wet writes sat(4*wet); other
| MIX values sat(4*mix*wet + (1-mix)*dry) per channel; MIX=0 writes nothing.
| Knob ramps (any of dm/df/dn) advance before every sample.
| a0 audio, a1 record, a2 wet, a3 hiss operand (ramp: hiss), a4 curve
| centre, a5 drive, a6 ONE (full wet) or mix; d0 rng, d1/d2 FIR history
| (roles swap per sample), d3 wet, d4 record, d5/d6 scratch, d7 feedback.
| Locals: 44(sp) LCG multiplier, 48(sp) wet end, 52(sp) 1-mix.
        .balign 4
        .global te_tape_block
te_tape_block:
        lea     -56(%sp),%sp
        movem.l %d2-%d7/%a2-%a6,(%sp)
        move.l  #1664525,%d0
        move.l  %d0,44(%sp)
        move.l  60(%sp),%a3
        move.l  64(%sp),%a2
        lea     64(%a2),%a0
        move.l  %a0,48(%sp)
        move.l  68(%sp),%a0
        move.l  72(%sp),%a1
        lea     te_tape_curve+4096,%a4
        move.l  te_record_gain,%a5
        move.l  20(%a3),%d0
        move.l  44(%a3),%d1
        move.l  48(%a3),%d2
        move.l  28(%a3),%d7
        move.l  24(%a3),%a6
        move.l  40(%a3),%d3
        move.l  76(%sp),%d4
        or.l    80(%sp),%d4
        or.l    84(%sp),%d4
        bne     .Ltape_ramp
| Settled: one signed hiss operand, (hiss >> 16) * 8, for the block.
        swap    %d3
        ext.l   %d3
        lsl.l   #3,%d3
        move.l  %d3,%a3
        move.l  %a6,%d4
        beq     .Ltape_dry
        cmp.l   #2147483640,%d4
        beq     .Ltape_wet
        move.l  #2147483647,%d5
        sub.l   %d4,%d5
        move.l  %d5,52(%sp)
        bra     .Ltape_mix

        .macro TE_TAPE_RECORD x1,x2,ramp
        mulu.l  44(%sp),%d0
        add.l   #1013904223,%d0
        move.l  (%a0),%d5
        mac.l   %d5,%a5,4(%a0),%d6,%acc0
        mac.l   %d6,%a5,(%a2)+,%d3,%acc0
        mac.l   %d3,%d7,%acc0
        mac.l   %d3,%d7,%acc0
        .if \ramp
        move.l  %a3,%d4
        swap    %d4
        ext.l   %d4
        lsl.l   #3,%d4
        mac.l   %d0,%d4,%acc0
        .else
        mac.l   %d0,%a3,%acc0
        .endif
        movclr.l %acc0,%d4
        asr.l   #3,%d4
| x2 <- x1 + ((record - 2*x1 + x2) >> 3), the shaped sample.
        add.l   %d4,\x2
        sub.l   \x1,\x2
        sub.l   \x1,\x2
        asr.l   #3,\x2
        add.l   \x1,\x2
| Curve entry 1024 + (shaped >> 18) as a signed byte offset from the
| centre; fraction (shaped & 0x3ffff) << 13. Interpolate t0*(1-f) + t1*f.
        move.l  \x2,%d5
        swap    %d5
        ext.l   %d5
        and.l   #-4,%d5
        and.l   #262143,\x2
        lsl.l   #8,\x2
        lsl.l   #5,\x2
        move.l  (%a4,%d5.l),%d6
        move.l  4(%a4,%d5.l),%d5
        move.l  %d6,%acc1
        msac.l  %d6,\x2,%acc1
        mac.l   %d5,\x2,%acc1
        movclr.l %acc1,%d5
        move.l  %d5,(%a1)+
        move.l  %d5,(%a1)+
        move.l  %d4,\x2
        .endm

        .macro TE_TAPE_WET
        mac.l   %d3,%a6,%acc2
        mac.l   %d3,%a6,%acc2
        mac.l   %d3,%a6,%acc2
        mac.l   %d3,%a6,%acc2
        movclr.l %acc2,%d5
        move.l  %d5,(%a0)+
        move.l  %d5,(%a0)+
        .endm

| Per channel: 4*mix*wet + (1-mix)*dry. d4 holds 1-mix; dry L/R reload
| through multiply-with-load while the wet products accumulate.
        .macro TE_TAPE_MIX load
        .if \load
        mac.l   %d3,%a6,52(%sp),%d4,%acc2
        .else
        mac.l   %d3,%a6,%acc2
        .endif
        mac.l   %d3,%a6,(%a0),%d5,%acc2
        mac.l   %d3,%a6,4(%a0),%d6,%acc2
        mac.l   %d3,%a6,%acc2
        mac.l   %d5,%d4,%acc2
        mac.l   %d3,%a6,%acc3
        mac.l   %d3,%a6,%acc3
        mac.l   %d3,%a6,%acc3
        mac.l   %d3,%a6,%acc3
        mac.l   %d6,%d4,%acc3
        movclr.l %acc2,%d5
        move.l  %d5,(%a0)+
        movclr.l %acc3,%d6
        move.l  %d6,(%a0)+
        .endm

        .macro TE_TAPE_RAMP x1,x2
        adda.l  76(%sp),%a6
        add.l   80(%sp),%d7
        adda.l  84(%sp),%a3
        TE_TAPE_RECORD \x1,\x2,1
        tst.l   %a6
        beq     .Lramp_dry\@
        move.l  #2147483647,%d4
        sub.l   %a6,%d4
        TE_TAPE_MIX 0
.Lramp_next\@:
        .subsection 1
.Lramp_dry\@:
        addq.l  #8,%a0
        bra     .Lramp_next\@
        .subsection 0
        .endm

.Ltape_wet:
        move.l  #2147483647,%a6
.Ltape_wet_pair:
        TE_TAPE_RECORD %d1,%d2,0
        TE_TAPE_WET
        TE_TAPE_RECORD %d2,%d1,0
        TE_TAPE_WET
        cmpa.l  48(%sp),%a2
        bne     .Ltape_wet_pair
        bra     .Ltape_done
.Ltape_mix:
        TE_TAPE_RECORD %d1,%d2,0
        TE_TAPE_MIX 1
        TE_TAPE_RECORD %d2,%d1,0
        TE_TAPE_MIX 1
        cmpa.l  48(%sp),%a2
        bne     .Ltape_mix
        bra     .Ltape_done
.Ltape_dry:
        TE_TAPE_RECORD %d1,%d2,0
        addq.l  #8,%a0
        TE_TAPE_RECORD %d2,%d1,0
        addq.l  #8,%a0
        cmpa.l  48(%sp),%a2
        bne     .Ltape_dry
        bra     .Ltape_done
.Ltape_ramp:
        move.l  %d3,%a3
.Ltape_ramp_pair:
        TE_TAPE_RAMP %d1,%d2
        TE_TAPE_RAMP %d2,%d1
        cmpa.l  48(%sp),%a2
        bne     .Ltape_ramp_pair
        move.l  60(%sp),%a5
        move.l  %a6,24(%a5)
        move.l  %d7,28(%a5)
        move.l  %a3,40(%a5)
.Ltape_done:
        move.l  60(%sp),%a5
        move.l  %d0,20(%a5)
        move.l  %d1,44(%a5)
        move.l  %d2,48(%a5)
        movem.l (%sp),%d2-%d7/%a2-%a6
        lea     56(%sp),%sp
        rts

| A bounded contiguous head block, after the C wrapper has checked history
| and the wrap seam. Sample i reads position base + 256*i - (wobble_i >> 8),
| wobble_i = wobble + (i+1)*step, and interpolates a*(1-f) + b*f with the
| 8-bit fraction and a raw ring word (Q1.31 -> Q3.29 through the 1/4
| operand). The position is a DDA: phase(i) = 256*(base&255) - wobble_i
| + 255 + 65536*i makes floor(phase/256) exact for any sign; its low 16
| bits live in d0's top half, so each sample is one add and a carry test.
| Adjacent reads reuse the previous sample's newer word: a contiguous block
| costs 17 uncached ring loads, a skipped or repeated frame reloads.
| te_read_linear(out, ring, base, wobble, step, blend): blend < 0 writes
| the head; otherwise this is a BEAT crossfade's outgoing head, blended
| into the incoming head already in out[] as old*(1-g) + new*g with
| g = blend + i*2^22.
        .balign 4
        .global te_read_linear
te_read_linear:
        lea     -44(%sp),%sp
        movem.l %d2-%d7/%a2-%a6,(%sp)
        move.l  48(%sp),%a0
        move.l  52(%sp),%a2
        move.l  56(%sp),%d0
        move.l  60(%sp),%d1
        move.l  64(%sp),%d6
        lea     64(%a0),%a1
        move.l  #0x20000000,%d5
        mvz.b   %d0,%d4
        lsl.l   #8,%d4
        sub.l   %d1,%d4
        sub.l   %d6,%d4
        add.l   #255,%d4
        asr.l   #8,%d0
        move.l  %d4,%d1
        swap    %d1
        ext.l   %d1
        add.l   %d1,%d0
| Form the byte offset explicitly: scaled-*8 loads fault on the hardware.
        lsl.l   #3,%d0
        adda.l  %d0,%a2
        move.l  %d4,%d0
        swap    %d0
        clr.w   %d0
        move.l  %d0,%d4
        lsr.l   #3,%d4
        and.l   #0x1fe00000,%d4
        move.l  (%a2),%d2
        move.l  %d6,%d1
        neg.l   %d1
        swap    %d1
        clr.w   %d1
        move.l  68(%sp),%d7
        bpl     .Lread_blend
        tst.l   %d6
        beq     .Lread_fixed
        bmi     .Lread_behind
        bra     .Lread_ahead
.Lread_blend:
        tst.l   %d6
        beq     .Lblend_fixed
        bmi     .Lblend_behind
        bra     .Lblend_ahead

| The outgoing sample is crossfaded with out[i] (loaded into a3 by the
| multiply-with-load) before it is stored.
        .macro TE_READ_EMIT blend
        .if \blend
        move.l  %d6,%acc2
        msac.l  %d6,%d7,%acc2
        mac.l   %a3,%d7,%acc2
        add.l   #4194304,%d7
        movclr.l %acc2,%d6
        .endif
        move.l  %d6,(%a0)+
        .endm
        .macro TE_READ_INTERP a,b,blend
        mac.l   \a,%d5,8(%a2),\b,%acc1
        .if \blend
        msac.l  \a,%d4,(%a0),%a3,%acc1
        .else
        msac.l  \a,%d4,%acc1
        .endif
        mac.l   \b,%d4,%acc1
        movclr.l %acc1,%d6
        TE_READ_EMIT \blend
        .endm
| Advance one sample. Step > 0 (under one frame per sample): a carry is
| the usual one frame, none stays. Step < 0: always one frame, a carry adds
| another. Either exception reloads the older word into \next (the next
| sample's a).
        .macro TE_READ_ADVANCE next,behind
        add.l   %d1,%d0
        .if \behind
        bcs     .Lread_skip\@
        .else
        bcc     .Lread_stay\@
        .endif
        addq.l  #8,%a2
.Lread_frac\@:
        move.l  %d0,%d4
        lsr.l   #3,%d4
        and.l   #0x1fe00000,%d4
        .subsection 1
        .if \behind
.Lread_skip\@:
        lea     16(%a2),%a2
        .else
.Lread_stay\@:
        .endif
        move.l  (%a2),\next
        bra     .Lread_frac\@
        .subsection 0
        .endm
        .macro TE_READ_MOVING behind,blend
        TE_READ_INTERP %d2,%d3,\blend
        TE_READ_ADVANCE %d3,\behind
        TE_READ_INTERP %d3,%d2,\blend
        TE_READ_ADVANCE %d2,\behind
        TE_READ_INTERP %d2,%d3,\blend
        TE_READ_ADVANCE %d3,\behind
        TE_READ_INTERP %d3,%d2,\blend
        .endm
| Constant TIME/WOW offset: fixed fraction, every frame adjacent.
        .macro TE_READ_FIXED a,b,blend
        mac.l   \a,%d5,8(%a2),\b,%acc1
        .if \blend
        msac.l  \a,%d4,(%a0),%a3,%acc1
        .else
        msac.l  \a,%d4,%acc1
        .endif
        mac.l   \b,%d4,%acc1
        addq.l  #8,%a2
        movclr.l %acc1,%d6
        TE_READ_EMIT \blend
        .endm
        .macro TE_READ_LOOPS name,blend
.L\name\()_ahead:
        TE_READ_MOVING 0,\blend
        cmpa.l  %a0,%a1
        beq     .Lread_done
        TE_READ_ADVANCE %d2,0
        bra     .L\name\()_ahead
.L\name\()_behind:
        TE_READ_MOVING 1,\blend
        cmpa.l  %a0,%a1
        beq     .Lread_done
        TE_READ_ADVANCE %d2,1
        bra     .L\name\()_behind
.L\name\()_fixed:
        TE_READ_FIXED %d2,%d3,\blend
        TE_READ_FIXED %d3,%d2,\blend
        cmpa.l  %a0,%a1
        bne     .L\name\()_fixed
        bra     .Lread_done
        .endm
        TE_READ_LOOPS read,0
        TE_READ_LOOPS blend,1
.Lread_done:
        movem.l (%sp),%d2-%d7/%a2-%a6
        lea     44(%sp),%sp
        rts
