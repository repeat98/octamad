; CF METER -- the DSP half: prints the two words the ColdFire meter writes
; into this track's FX2 page-2 lane (modules/cfmeter/meter.s) as a square
; wave, L = x:(r6+$c) / 2, R = x:(r6+$d) / 2, the sign flipped every block.
; The ratio of the two amplitudes is the value, whatever the gain after
; this slot. The track's own audio is replaced.
;
; r7 block: $00 = the sign, 0 or 1 (cleared by init).

init:
        clr     a
        move    a,x:(r7)
        rts

proc:
        move    x:(r6+$c),a
        asr     a
        move    a,x0                    ; +L
        neg     a
        move    a,x1                    ; -L
        move    x:(r6+$d),a
        asr     a
        move    a,y0                    ; +R
        neg     a
        move    a,y1                    ; -R
        move    #>1,a
        move    x:(r7),b
        sub     b,a                     ; next sign = 1 - sign; Z when it was 1
        move    a,x:(r7)
        move    x0,a
        teq     x1,a
        move    y0,b
        teq     y1,b
        move    #$1,n0                  ; (Character's form: n0 is not 1 on entry)
        do      n7,>cm_end
        move    a,x:(r0)
        move    b,x:(r0+n0)
        move    (r0)+n0
        move    (r0)+n0
cm_end:
        rts
