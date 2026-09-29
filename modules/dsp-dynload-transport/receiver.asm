; Transfer qualification only. P writes are bounded to the 128-word
; manifest table reserved for staging; it is never dispatched or executed.
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
        beq     validop
        cmp     #>2,a
        bne     badpacket
validop:
        move    x:(r0+4),a
        and     #>$ffff,a
        cmp     #>24,a
        bne     badpacket
        move    x:(r0+2),a
        and     #>$ffff,a
        cmp     #>2,a
        bne     accepted
        move    x:(r0+5),a
        and     #>$ffff,a
        cmp     #>104,a
        bgt     badpacket
        add     #>$fab1e0,a
        move    r3,x:(r0+63)
        move    a,r3
        move    r0,a
        add     #>8,a
        move    a,r1
        do      #<$18,stagedone
        move    x:(r1)+,a
        and     #>$ffff,a
        asl     #8,a,a
        move    a1,x0
        move    x:(r1)+,a
        and     #>$ff,a
        or      x0,a
        move    a1,x0
        move    x0,p:(r3)
        move    r3,a
        add     #>1,a
        move    a,r3
stagedone:
        move    x:(r0+63),r3
accepted:
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
        move    #>0,a
        move    a1,x:(r0)
finish:
        rts
