; CF BURN owns no DSP audio or state: its work is on the ColdFire. Leave the
; FX2 signal untouched; init preserves r1 (the FX1 dispatcher keeps the id there).
init:
        rts
proc:
        ; A counted, empty sample loop for the generic insert cycle gate.
        ; No audio, state or buffer word is read or written.
        do n7,>cfb_end
        nop
cfb_end:
        rts
