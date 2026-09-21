| All storage is part of the loaded image, independent of the DRAM loader.
| UART0 is MIDI. Normal telemetry is dropped unless its queue is empty.
        .text
        .balign 4
        .global trace_frame, trace_fault, trace_frames, trace_wait, trace_dropped
        .global trace_started, trace_packet, trace_exception
trace_frame:
        lea -36(%sp),%sp
        movem.l %d0-%d5/%a0-%a2,(%sp)
        move.w %sr,%d5
        addq.l #1,trace_frames
        subq.l #1,trace_wait
        bne trace_done
        move.l #2756,%d0
        move.l %d0,trace_wait
        move.w #0x2700,%sr
        tst.l 0x460ba978             | stock MIDI output disabled
        bne trace_skip
        tst.l 0x400b967c             | ordinary queue
        bne trace_skip
        tst.l 0x400b9688             | priority queue
        bne trace_skip
        move.l 0x460ba988,%d0
        cmpi.l #-16,%d0       | never insert into an open SysEx
        beq trace_skip
        move.l 0x400b966c,%a0
        cmpa.l #0x40000000,%a0
        blo trace_skip
        cmpa.l #0x47fff000,%a0       | complete 4096-byte ring must fit
        bhi trace_skip
        move.l 0x400b9678,%d0
        cmpi.l #4095,%d0
        bhi trace_skip
        lea trace_packet+8,%a1
        move.l trace_frames,%d0
        bsr trace_word
        move.l 0x4610757c,%d0
        bsr trace_word
        move.l 0x800065b8,%d0
        bsr trace_word
        move.l 0x8000181c,%d0
        bsr trace_word
        move.l trace_dropped,%d0
        bsr trace_word
        move.l 0x800068fc,%d0
        bsr trace_word
        | Actual outgoing FX IDs, two slots per track, four IDs per word.
        move.l 0x800000e0,%d0
        andi.l #1,%d0
        lsl.l #8,%d0
        add.l %d0,%d0
        lea 0x80000110,%a2
        adda.l %d0,%a2
        moveq #3,%d4
trace_fx:
        moveq #0,%d0
        move.b 55(%a2),%d0
        lsl.l #8,%d0
        move.b 57(%a2),%d0
        lsl.l #8,%d0
        move.b 119(%a2),%d0
        lsl.l #8,%d0
        move.b 121(%a2),%d0
        bsr trace_word
        lea 128(%a2),%a2
        subq.l #1,%d4
        bpl trace_fx
        lea trace_packet,%a1
        moveq #90,%d4
        bsr trace_checksum
        lea trace_packet,%a1
        move.l 0x400b9678,%d0
        moveq #89,%d1
trace_enqueue:
        move.b (%a1)+,(%a0,%d0.l)
        subq.l #1,%d0
        andi.l #4095,%d0
        subq.l #1,%d1
        bpl trace_enqueue
        move.l %d0,0x400b9678
        moveq #90,%d0
        move.l %d0,0x400b967c
        moveq #-9,%d0
        move.l %d0,0x460ba988        | F7 cancels running status
        moveq #3,%d0
        move.b %d0,0xfc060014
        moveq #1,%d0
        move.l %d0,trace_started
        bra trace_restore
trace_skip:
        addq.l #1,trace_dropped
trace_restore:
        move.w %d5,%sr
trace_done:
        move.w %d5,%sr
        movem.l (%sp),%d0-%d5/%a0-%a2
        lea 36(%sp),%sp
        move.l #0x75180000,%d0       | displaced, including CCR
        jmp 0x4000d56e

| Encode a raw word as eight MIDI-safe nibbles, most significant first.
| ColdFire has no ROL instruction; shifts are deliberately <=8 bits.
trace_word:
        moveq #7,%d2
trace_nibble:
        move.l %d0,%d1
        lsr.l #8,%d1
        lsr.l #8,%d1
        lsr.l #8,%d1
        lsr.l #4,%d1
        move.b %d1,(%a1)+
        lsl.l #4,%d0
        subq.l #1,%d2
        bpl trace_nibble
        rts

| XOR bytes 1..length-3, then checksum and F7. A1=packet, D4=length.
trace_checksum:
        moveq #0,%d0
        addq.l #1,%a1
        move.l %d4,%d1
        subq.l #3,%d1
trace_xor:
        moveq #0,%d2
        move.b (%a1)+,%d2
        eor.l %d2,%d0
        subq.l #1,%d1
        bne trace_xor
        move.b %d0,(%a1)+
        move.b #0xf7,(%a1)
        rts

trace_fault:
        lea -36(%sp),%sp
        movem.l %d0-%d5/%a0-%a2,(%sp)
        move.w %sr,%d5
        tst.l trace_started         | UART not proven initialized yet
        beq trace_fault_done
        move.l 40(%sp),%a2          | stock printer's exception-frame arg
        move.l %a2,%d0
        andi.l #3,%d0
        bne trace_fault_done
        cmpa.l #0x40000000,%a2
        blo trace_fault_done
        cmpa.l #0x47fffff8,%a2
        bhi trace_fault_done
        lea trace_exception+8,%a1
        move.l trace_frames,%d0
        bsr trace_word
        move.l %a2,%d0
        bsr trace_word
        move.l (%a2),%d0            | raw format/vector/SR
        bsr trace_word
        move.l 4(%a2),%d0           | saved PC
        bsr trace_word
        lea trace_exception,%a1
        moveq #42,%d4
        bsr trace_checksum
        | Fatal-path only. Interrupts are already masked by the default
        | exception trampoline. One TOTAL polling budget; never endless.
        | F7 terminates any partly transmitted SysEx before our new F0.
        lea trace_fault_prefix,%a1
        moveq #42,%d4
        move.l #2000000,%d3
trace_poll:
        subq.l #1,%d3
        beq trace_fault_done
        move.b 0xfc060004,%d0
        btst #2,%d0
        beq trace_poll
        move.b (%a1)+,0xfc06000c
        subq.l #1,%d4
        bpl trace_poll
trace_fault_done:
        move.w %d5,%sr
        movem.l (%sp),%d0-%d5/%a0-%a2
        lea 36(%sp),%sp
        lea -44(%sp),%sp            | displaced stock printer prologue
        movem.l %d2-%d3/%a2,(%sp)
        jmp 0x4003af9c
        .balign 4
trace_frames: .long 0
trace_wait: .long 1
trace_dropped: .long 0
trace_started: .long 0
trace_packet:
        .byte 0xf0,0x7d,0x4f,0x54,0x44,1,108,1
        .zero 82
trace_fault_prefix: .byte 0xf7
trace_exception:
        .byte 0xf0,0x7d,0x4f,0x54,0x44,1,108,2
        .zero 34
        .balign 4
