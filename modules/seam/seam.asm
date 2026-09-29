; ---------------------------------------------------------------------------
; MIXER SEAM -- the empty hook after the stock mixdown (payload A, P:0x2d5).
;
; Reached by `jsr` over the two-word instruction below, so it replays that
; instruction and returns to P:0x2d7. Nothing else: no register, no memory
; and no condition code is touched (a move does not set CCR), which is what
; makes the port's bit-identity gate the right test. A master strip replaces
; the `rts`-only tail with its own work between the replay and the return.
; ---------------------------------------------------------------------------
entry:
        move    x:>$206,r0              ; the displaced instruction, as stock has it
        rts
