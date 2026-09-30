; Runtime extension: verified P uploads, then bind/unbind an existing FX id.
; First 64 table words retain the original init/proc pointers (32 ids).
; BYPASS (6) points an id at dlstubinit/dlstubproc, a word-for-word copy of
; stock's null stub (P:0x7c8 A, P:0x588 B): an unbound managed id runs dry,
; never its original entry, which is what reclaiming the originals needs.
; The rest of the table is the bounded code arena; the table's size is the
; build's DLWORDS define, reported to the ColdFire. No live compaction.
; Both frame hooks run before any effect on this core. Entry changes preserve
; the stock per-instance state; they do not call init or change the Part.
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
        move    r3,x:(r0+63)
        move    x:(r0+2),a
        and     #>$ffff,a
        cmp     #>1,a
        beq     accepted
        cmp     #>3,a
        beq     upload
        cmp     #>4,a
        beq     binding
        cmp     #>5,a
        beq     binding
        cmp     #>6,a
        beq     binding
        cmp     #>7,a
        beq     setbase
        bra     badsaved
upload:
        move    x:(r0+4),a
        and     #>$ffff,a
        cmp     #>1,a
        blt     badsaved
        cmp     #>24,a
        bgt     badsaved
        move    a1,x1
        move    x:(r0+5),a
        and     #>$ffff,a
        cmp     #>64,a
        blt     badsaved
        add     x1,a
        cmp     #>@DLWORDS@,a
        bgt     badsaved
        sub     x1,a
        move    a1,x0
        bsr     tablebase
        add     x0,a
        move    a,r3
        move    r0,a
        add     #>8,a
        move    a,r1
        move    x1,a
        do      a,written
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
written:
        ; Read back the entire chunk through P before acknowledging it.
        move    x:(r0+5),a
        and     #>$ffff,a
        move    a1,x0
        bsr     tablebase
        add     x0,a
        move    a,r3
        move    #>0,x1
        move    x:(r0+4),a
        and     #>$ffff,a
        do      a,verified
        move    p:(r3),x0
        move    x1,a
        add     x0,a
        move    a1,x1
        move    r3,a
        add     #>1,a
        move    a,r3
verified:
        move    x1,a
        and     #>$ffff,a
        move    a1,x:>$2364
        move    a1,x:>$4364
        move    x1,a
        lsr     #16,a
        move    a1,x:>$2365
        move    a1,x:>$4365
        bra     accepted
binding:
        move    x:(r0+4),a
        and     #>$ffff,a
        cmp     #>31,a
        bgt     badsaved
        move    a1,x1
        asl     a
        move    a1,x0
        bsr     tablebase
        add     x0,a
        move    a,r3
        move    x1,a
        add     #>$215,a
        move    a,r1
        move    x:(r0+2),a
        and     #>$ffff,a
        cmp     #>5,a
        beq     restoreentry
        cmp     #>6,a
        beq     stubentry
        ; Check both offsets before touching either dispatch entry.
        move    x:(r0+5),a
        and     #>$ffff,a
        cmp     #>64,a
        blt     badsaved
        cmp     #>@DLWORDS@,a
        bge     badsaved
        move    x:(r0+7),a
        and     #>$ffff,a
        cmp     #>64,a
        blt     badsaved
        cmp     #>@DLWORDS@,a
        bge     badsaved
        move    p:(r3),x0
        move    x0,a
        tst     a
        bne     retained
        move    x:(r1),x0
        move    x0,p:(r3)
        move    r3,a
        add     #>1,a
        move    a,r3
        move    x:(r1+32),x0
        move    x0,p:(r3)
retained:
        move    x:(r0+5),a
        and     #>$ffff,a
        move    a1,x0
        bsr     tablebase
        add     x0,a
        move    a1,x:(r1)
        move    x:(r0+7),a
        and     #>$ffff,a
        move    a1,x0
        bsr     tablebase
        add     x0,a
        move    a1,x:(r1+32)
        bra     accepted
restoreentry:
        move    p:(r3),x0
        move    x0,a
        tst     a
        beq     accepted
        move    x0,x:(r1)
        move    r3,a
        add     #>1,a
        move    a,r3
        move    p:(r3),x0
        move    x0,x:(r1+32)
        bra     accepted
stubentry:
        move    p:(r3),x0
        move    x0,a
        tst     a
        bne     stubsaved
        move    x:(r1),x0
        move    x0,p:(r3)
        move    r3,a
        add     #>1,a
        move    a,r3
        move    x:(r1+32),x0
        move    x0,p:(r3)
stubsaved:
        move    #>dlstubinit,x0
        move    x0,x:(r1)
        move    #>dlstubproc,x0
        move    x0,x:(r1+32)
; BASE (7): the Y buffer table entry X:0x255 + (r0+4), 0..7, becomes
; (r0+7) << 16 | (r0+5). Stock reads it only in an effect's init, through
; X:0x213 (buffers.h): the ColdFire writes it before the new id is published.
setbase:
        move    x:(r0+4),a
        and     #>$ffff,a
        cmp     #>7,a
        bgt     badsaved
        add     #>$255,a
        move    a1,r1
        move    x:(r0+7),a
        and     #>$ff,a
        asl     #16,a,a
        move    a1,x0
        move    x:(r0+5),a
        and     #>$ffff,a
        or      x0,a
        move    a1,x:(r1)
        bra     accepted
accepted:
        bsr     tablebase
        move    a1,x:>$2366
        move    a1,x:>$4366
        move    #>@DLWORDS@,a
        move    a1,x:>$2367
        move    a1,x:>$4367
        move    x:(r0+63),r3
        move    #>0,a
        bra     reply
badsaved:
        move    x:(r0+63),r3
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
tablebase:
        move    #>$fab1e0,a
        rts
; Stock's null stub, word for word: init returns, process copies the
; interleaved stereo block onto itself (the dispatcher's in-place contract).
dlstubinit:
        rts
dlstubproc:
        move    r0,r1
        do      n7,dlstubdone
        move    x:(r0)+,a
        move    x:(r0)+,b
        move    a,x:(r1)+
        move    b,x:(r1)+
dlstubdone:
        rts
