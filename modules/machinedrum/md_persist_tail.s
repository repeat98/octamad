| Appended to the generated md_persist.s (generate_ctl.py): the four stock
| detours WP-E1 needs and the unit's storage.
|
| Each wrapper runs the stock routine on the caller's own stack: it keeps
| the caller's return address, puts its own continuation in that slot, and
| runs the displaced first instructions and the rest of stock. Stock sees
| exactly the frame its caller built, whatever the number of arguments
| (the project load takes four and reads the fourth at sp@(344); a first
| draft that called it on three copied arguments stalled every load, found
| under octemu 25 Sep 2026). When stock returns to the continuation, the
| caller's arguments are at 0(sp): md_persist.c runs, stock's d0 is kept
| and the continuation returns to the caller. None of these routines is
| entered again before it returns (the copy of machinedrum.* uses
| md_copy_stock, which bypasses the detour).
        .text
        .balign 2
        .global md_hook_sram_save, md_hook_bank_save, md_hook_proj_load
        .global md_hook_copy, md_copy_stock

| 0x4000faf0(bank): stock copies a bank into SRAM; it is resident now.
| Displaced: move.l a2,-(sp) / move.l d2,-(sp) / move.l #0x8ed80,-(sp).
md_hook_sram_save:
        move.l  (%sp),md_ret_sram_save
        move.l  #.ss_after,(%sp)
        move.l  %a2,-(%sp)
        move.l  %d2,-(%sp)
        move.l  #0x8ed80,-(%sp)
        jmp     (0x4000fafa).l
.ss_after:                               | [bank]
        move.l  %d0,-(%sp)
        move.l  4(%sp),-(%sp)
        jsr     md_persist_sram_saved
        addq.l  #4,%sp
        move.l  (%sp)+,%d0
        move.l  md_ret_sram_save,-(%sp)
        rts

| 0x400917c8(ctx, bank mask): stock saves banks to the card.
| Displaced: link fp,#-324 / movem.l d2-d7/a2-a5,(sp).
md_hook_bank_save:
        move.l  (%sp),md_ret_bank_save
        move.l  #.bs_after,(%sp)
        link    %fp,#-324
        movem.l %d2-%d7/%a2-%a5,(%sp)
        jmp     (0x400917d0).l
.bs_after:                               | [ctx][mask]
        move.l  %d0,-(%sp)
        move.l  %d0,-(%sp)
        jsr     md_persist_bank_saved
        addq.l  #4,%sp
        move.l  (%sp)+,%d0
        move.l  md_ret_bank_save,-(%sp)
        rts

| 0x400905d4(ctx, bank mask, ., .): stock loads banks from the card.
| Displaced: lea -328(sp),sp / movem.l d2-d7/a2-fp,(sp).
md_hook_proj_load:
        move.l  (%sp),md_ret_proj_load
        move.l  #.pl_after,(%sp)
        lea     -328(%sp),%sp
        movem.l %d2-%d7/%a2-%fp,(%sp)
        jmp     (0x400905dc).l
.pl_after:                               | [ctx][mask]...
        move.l  %d0,-(%sp)
        move.l  8(%sp),-(%sp)            | the mask
        jsr     md_persist_loaded
        addq.l  #4,%sp
        move.l  (%sp)+,%d0
        move.l  md_ret_proj_load,-(%sp)
        rts

| 0x40016388(dst, src, flag): stock copies a file.
| Displaced: link fp,#-72 / movem.l d2-d6,(sp).
md_hook_copy:
        move.l  (%sp),md_ret_copy
        move.l  #.cp_after,(%sp)
        link    %fp,#-72
        movem.l %d2-%d6,(%sp)
        jmp     (0x40016390).l
.cp_after:                               | [dst][src][flag]
        move.l  %d0,-(%sp)               | [d0][dst][src]
        move.l  %d0,-(%sp)               | the result: [res][d0][dst][src]
        move.l  12(%sp),-(%sp)           | src
        move.l  12(%sp),-(%sp)           | dst
        jsr     md_persist_copied
        lea     12(%sp),%sp
        move.l  (%sp)+,%d0
        move.l  md_ret_copy,-(%sp)
        rts
| Stock's copy as a plain call (md_persist.c copies machinedrum.* with it).
md_copy_stock:
        link    %fp,#-72
        movem.l %d2-%d6,(%sp)
        jmp     (0x40016390).l

| No .bss in the runtime image: md_persist.c's state (MdPersist) and the
| wrappers' return addresses.
        .data
        .balign 4
        .global md_persist
md_persist:
        .zero   5216
md_ret_sram_save:
        .long   0
md_ret_bank_save:
        .long   0
md_ret_proj_load:
        .long   0
md_ret_copy:
        .long   0
        .text
