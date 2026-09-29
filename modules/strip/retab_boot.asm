; ---------------------------------------------------------------------------
; MASTER STRIP -- RET A's boot, payload B (core 1).
;
; Reached by `jsr` over P:0x40's `move #>$8000,b`, the first instruction of
; payload B after the upload, as boot.asm is on core 0. Runs once per DSP boot.
; Core 1's X:0x7c00..0x7fff is RET A's (reta.asm has the map); X is not zeroed
; on the unit (the dirty-state trap), so the slot starts from nothing it did not
; write: id 0, proc 0, its record and block zero.
; ---------------------------------------------------------------------------
entry:
        move    #>$7c00,r0
        clr     a
        do      #>$400,rbzero
        move    a,x:(r0)+
rbzero:
        move    #>$8000,b               ; the displaced instruction, as stock has it
        rts
