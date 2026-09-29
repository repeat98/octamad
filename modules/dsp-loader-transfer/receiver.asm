; Transfer qualification only. Never writes P or effect state.
; Both frame-head hooks replay move r6,x:207. Live r2/r4-r7 and b are
; preserved. a/x0/x1/r0/r1 are reloaded by the stock continuation on A/B.
; Mailbox: current working bank + 320. Reply mirrored at 2360/4360 so the
; host's bank mask cannot make its previous-frame acknowledgement disappear.
; No AGU modulo registers are modified.
frame:
        move    r6,x:>$207
        move    r6,a
        add     #>$320,a
        move    a,r0
        move    x:(r0),a
        and     #>$ffff,a
        cmp     #>$4c44,a
        bne     finish
        move    r0,r1
        move    #>0,x1
        do      #<$40,checksumdone
        move    x:(r1)+,a
        and     #>$ffff,a
        add     x1,a
        move    a1,x1
checksumdone:
        and     #>$ffff,a
        bne     badpacket
        move    x:(r0+2),a
        and     #>$ffff,a
        cmp     #>1,a
        bne     badpacket
        move    x:(r0+4),a
        and     #>$ffff,a
        cmp     #>24,a
        bne     badpacket
        move    #>0,a
        bra     reply
badpacket:
        move    #>1,a
reply:
        move    a1,x:>$2362
        move    a1,x:>$4362
        move    x:(r0+1),a
        and     #>$ffff,a
        move    a1,x:>$2361
        move    a1,x:>$4361
        move    x:(r0+3),a
        and     #>$ffff,a
        move    a1,x:>$2363
        move    a1,x:>$4363
        move    #>$414b,a
        move    a1,x:>$2360
        move    a1,x:>$4360
finish:
        rts
