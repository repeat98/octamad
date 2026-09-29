; ---------------------------------------------------------------------------
; MASTER STRIP -- boot: the slots' state before the first record.
;
; Reached by `jsr` over P:0x40's `move #>$8000,b`, the first instruction of
; payload A after the upload (the zeroing loop and the poll loop follow, and
; nothing jumps back here). Runs once per DSP boot, before the first frame,
; so the strip never starts from what the RAM held: X is not zeroed on the
; unit (CLAUDE.md, the dirty-state trap).
;
; It starts the slots where strip_xport.s's strip_model starts, OXIDE at
; IN 48 / OUT 80 on slot 1 and slot 2 empty, so the frames before the first
; record (and a unit whose record never arrives) run what the record then
; says, and the record's first arrival changes nothing.
;
; X:0x7c00..0x7eff is the strip's (docs/proposals/MIXER.md "Step 2"): outside
; every X module of payload A (the curve table ends at 0x7a91, the TX ring
; starts at 0x8000) and written by nothing under the port on the user's
; project (`ot_emu --dsp-writes`: 0x7c00..0x7cff over 900 frames,
; 0x7d00..0x7fff over 300, 29 Sep 2026). The strip's own block, r7 =
; 0x7c00 in head.asm and tail.asm:
;   $00..$0a  the registers head.asm and tail.asm save around their passes
;             (r1..r6, n0..n3, n7)
;   $0b..$0e  the tail's loop: the ring's sample j, D's sample j, the cue
;             mix's gains for sample j (a Y address), the cue mix's L/R word
;   $0f       the caller's r7
;   $10, $11  slot 1: the id it runs, its proc (0: the slot is dry)
;   $12, $13  slot 2: the same
;   $14       the pair the slots run on (head.asm / tail.asm's hrun, trun)
;   $15..$17  the record's apply (tail.asm): the id asked for, the record's
;             cursor, a slot's id/proc address parked across an init
;   $18..$1f  spare
;   $20..$2e  slot 1's parameter record (its r6): page 1 at $20..$25 as
;             val << 16, page 2 at $2c..$2e two a word; $26..$2b stay zero
;             (a track's are FX2's page 1, no insert's)
;   $30..$3e  slot 2's
;   $40..$5f  D: MAIN's 16 pairs, L/R adjacent; the head gathers them dry and
;             the slots run on them in place
;   $60..$7f  C: what the click added to MAIN, samples 1..15 (tail.asm)
; and each slot's instance block (its r7), 256-aligned as the dispatcher's:
;   X:0x7d00..0x7d83  slot 1
;   X:0x7e00..0x7e83  slot 2
;
; The slots reach their effects through the stock dispatch tables, as a
; track slot does: INIT_TABLE at X:0x215 and PROC_TABLE at X:0x235, indexed
; by the FX id (OXIDE's is 0x1f; tail.asm has the list the strip runs).
; ---------------------------------------------------------------------------
entry:
        move    #>$7c00,r0              ; the strip's block, zeroed to the
        clr     a                       ; end of slot 2's record
        do      #$40,bzero
        move    a,x:(r0)+
bzero:
        move    #>$1f,x0                ; slot 1 runs OXIDE
        move    x0,x:>$7c10
        move    x:>$254,x0              ; PROC_TABLE[0x1f]
        move    x0,x:>$7c11
        move    #>$300000,x0            ; IN 48: 0 dB into the tape
        move    x0,x:>$7c20
        move    #>$500000,x0            ; OUT 80: 0 dB out
        move    x0,x:>$7c21
        move    #>$7c20,r6              ; its record
        move    #>$7d00,r7              ; its instance block
        move    #>$1f,r1                ; its id, where the dispatcher has it
        move    x:>$234,r2              ; INIT_TABLE[0x1f]: OXIDE's init
        jsr     (r2)
        move    #>$8000,b               ; the displaced instruction, as stock has it
        rts
