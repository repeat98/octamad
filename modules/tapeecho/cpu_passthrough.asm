; CPU Tape Echo owns no DSP audio memory. Preserve the stock FX2 signal for
; the post-FX2 ColdFire delay stage; in particular preserve r1 during init.
init:
        rts
proc:
        ; Keep a counted, empty sample loop for the generic insert cycle gate.
        ; No audio, state or buffer word is read or written.
        do n7,>te_cpu_end
        nop
te_cpu_end:
        rts
