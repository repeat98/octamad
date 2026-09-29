| The existing USB IN state-7 extension is the transport precedent. This
| module owns that same hook and cannot compose with USB IN until a shared
| scheduler is implemented. It transfers to both cores, then reads status.
| No busy wait in the IRQ; each completion re-enters state 7.
        .text
        .global dl_state7, dl_tick
        .equ UNCACHED,0x08000000
        .equ DONE,0x40004bc8

dl_state7:
        lea -44(%sp),%sp
        movem.l %d2-%d7/%a2-%a6,(%sp)
        moveq #1,%d0
        move.b %d0,0xfc04401c   | acknowledge our channel-1 completion too
        move.l dl_phase,%d2
        bne dl_next
        move.l 0xfc045028,%d0
        move.l %d0,dl_rx_nbytes
        jsr dl_frame
        moveq #1,%d2
        move.l %d2,dl_phase
        bra dl_write

dl_next:
        addq.l #1,%d2
        move.l %d2,dl_phase
        cmpi.l #3,%d2
        bcs dl_write
        cmpi.l #5,%d2
        bcs dl_read
        move.l dl_rx_nbytes,%d0
        move.l %d0,0xfc045028
        clr.l dl_phase
        moveq #0,%d0
        move.b %d0,0xfc0a400c   | next frame takes core 0 bank word without selecting it
        movem.l (%sp),%d2-%d7/%a2-%a6
        lea 44(%sp),%sp
        moveq #1,%d1
        move.b %d1,0xfc04801d
        jmp DONE

dl_write:
        subq.l #1,%d2
        move.b %d2,0xfc0a400c
        lsl.l #7,%d2
        lea dl_tx,%a0
        adda.l #UNCACHED,%a0
        adda.l %d2,%a0
        move.l %a0,0xfc045000
        moveq #64,%d0
        move.l %d0,0xfc045008
        move.w #0x81,%d0
        move.w %d0,0x20000000
        move.w #0x6320,%d0
        move.w %d0,0x2000001c
        move.w #63,%d0
        move.w %d0,0x2000001c
        move.w #0x88,%d0
        move.w %d0,0x20000004
        move.w #0x8002,%d0
        move.w %d0,0xfc045014
        move.w #0x8002,%d0
        move.w %d0,0xfc04501c
        clr.b 0xfc04401e
        bra dl_return

dl_read:
        subq.l #3,%d2
        move.b %d2,0xfc0a400c
        lsl.l #6,%d2
        lea dl_rx,%a0
        adda.l #UNCACHED,%a0
        adda.l %d2,%a0
        move.l %a0,0xfc045030
        moveq #64,%d0
        move.l %d0,0xfc045028
        move.w #2,%d0
        move.w %d0,0xfc04503e
        move.w #0x81,%d0
        move.w %d0,0x20000000
        move.w #0x6360,%d0
        move.w %d0,0x2000001c
        move.w #31,%d0
        move.w %d0,0x2000001c
        move.w #0x89,%d0
        move.w %d0,0x20000004
        move.w #0x8201,%d0
        move.w %d0,0xfc045034
        move.w #0x8201,%d0
        move.w %d0,0xfc04503c
        move.b #1,%d0
        move.b %d0,0xfc04401e

dl_return:
        movem.l (%sp),%d2-%d7/%a2-%a6
        lea 44(%sp),%sp
        jmp DONE

| Same UI tick seam as Analog BD; ledger refuses coexistence at present.
dl_tick:
        lea -60(%sp),%sp
        movem.l %d0-%d7/%a0-%a6,(%sp)
        jsr dl_ui
        movem.l (%sp),%d0-%d7/%a0-%a6
        lea 60(%sp),%sp
        jsr 0x4005213c
        jsr 0x4007e940
        jmp 0x40052228
        .data
        .balign 4
dl_phase: .long 0
dl_rx_nbytes: .long 0
