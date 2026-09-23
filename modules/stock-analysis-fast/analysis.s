/* Stock 1.40C analysis recurrence, body sourced from the operator's image.
 * Entry/exit contract: 0x40098494 -> 0x400984be. No stack or extra state.
 * d7 is used only as the iteration counter inside this loop. Retain the
 * last SUBQ/MOVE-from-ACC/BGT sequence so outgoing CCR/X match stock.
 * The original MAC/load/store order and accumulator reads are unchanged.
 */
    .text
    .balign 2
    .global analysis_fast
analysis_fast:
.Lgroups:
    cmpi.l #8,%d7
    blt.w .Ltail
    subq.l #7,%d7
    .rept 7
    .incbin "out/raw/section_3_MAIN_OS.bin",0x98094,0x24
    move.l %acc0,%d1
    .endr
    .incbin "out/raw/section_3_MAIN_OS.bin",0x98094,0x24
    subq.l #1,%d7
    move.l %acc0,%d1
    bgt.w .Lgroups
    jmp 0x400984be
.Ltail:
    .incbin "out/raw/section_3_MAIN_OS.bin",0x98094,0x24
    subq.l #1,%d7
    move.l %acc0,%d1
    bgt.w .Ltail
    jmp 0x400984be
