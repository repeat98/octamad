; Resident source dispatcher and bounded Part loader. Engine code is not in
; the boot upload. Host words are tagged 16-bit halves, including loader data.
; Metadata: four entry points, ready, checksum, next sequence, saved m7.
zd01:
        move a,x:>$20e
        move x:>$209,r4
        move x:(r4),b
        and #>$ffff,b
        move b1,b
        cmp #>$ab09,b
        bne zd02
        move x:(r4+$2),b
        and #>$ffff,b
        move b1,b
        cmp #>$0909,b
        beq zd03
zd02:
        rts
zd03:
        move #>$ffffff,m0
        move #>$ffffff,m1
        move #>$ffffff,m5
        move #>$ffffff,m6
        move x:(r4+$4),a
        and #>$ffff,a
        move a1,a
        tst a
        beq zd04
        bsr zl01
zd04:
        move x:>$20b,a
        add #>$80,a
        move a,x:>$20b
        move #$0,r0
        move x:>$3804,a
        tst a
        beq zd07
        move x:>$418,a
        asl a
        move #>$3700,x0
        add x0,a
        move a1,r5
        lua (r5+$30),r6
        lua (r4+$8),r1
        do #<$c,zd05
        move x:(r1)+,a
        and #>$7f,a
        move a1,x:(r6)+
zd05:
        move x:>$20c,a
        move #>$ffffff,x0
        move x:(r4+$3),b
        and #>$ffff,b
        move b1,b
        tst b
        teq x0,a
        cmp #2,b
        move #0,x0
        teq x0,a
        move a,x:(r6)
        lua (r5+$30),r6
        move x:>$418,a
        asr #$5,a,a
        move a1,n1
        move #>$3800,r1
        move x:(r1+n1),r2
        move #>$10,n7
        jsr (r2)
        bra zd08
zd07:
        clr a
        do #<$20,zd09
        move a,x:(r0)+
zd09:
zd08:
        move ssh,x0
        jmp @CONT@

; Header command 1=P, 2=X, 3=begin, 4=commit. At most 16 words/record.
zl01:
        cmp #3,a
        beq zl02
        move a1,x1
        move x:(r4+$7),a
        and #>$ffff,a
        move a1,a
        move x:>$3806,x0
        cmp x0,a
        bne zl03
        add #1,a
        move a1,x:>$3806
        lua (r4+$14),r1
        move x:>$3805,y1
        move x:>$3804,a
        tst a
        bne zl03
        move x1,a
        cmp #4,a
        beq zl04
        cmp #2,a
        bgt zl03
        move x:(r4+$5),a
        and #>$ffff,a
        move a1,a
        tst a
        beq zl03
        cmp #>$10,a
        bgt zl03
        move a1,y0
        move x:(r4+$6),a
        and #>$ffff,a
        move a1,a
        move #>@PBASE@,x0
        move #>@PEND@,r2
        move x1,b
        cmp #1,b
        beq zl05
        move #>$2b40,x0
        move #>$3804,r2
zl05:
        cmp x0,a
        blt zl03
        move a1,r7
        add y0,a
        move r2,x0
        cmp x0,a
        bgt zl03
        move r7,a
        add y0,a
        add x1,a
        move x:(r4+$7),b
        and #>$ffff,b
        move b1,x0
        add x0,a
        add y1,a
        move a1,y1
        move m7,x:>$3807
        move #>$ffffff,m7
        move #1,n7
        move y0,a
        do a,zl06
        bsr zl07
        move x1,b
        cmp #1,b
        bne zl08
        move x0,p:(r7)+n7
        bra zl09
zl08:
        move x0,x:(r7)+n7
zl09:
        move x0,a
        add y1,a
        move a1,y1
zl06:
        move y1,x:>$3805
        move x:>$3807,m7
        rts
zl02:
        clr a
        move a,x:>$3805
        move #>$1,x0
        move x0,x:>$3806
        move a,x:>$3804
        rts
zl04:
        bsr zl07
        move y1,a
        cmp x0,a
        bne zl03
        move #>$1,x0
        move x0,x:>$3804
        rts
zl03:
        move #>$ffffff,x0
        move x0,x:>$3806
        clr a
        move a,x:>$3804
        rts
zl07:
        move x:(r1)+,a
        and #>$ff,a
        asl #$10,a,a
        move x:(r1)+,b
        and #>$ffff,b
        move b1,b
        move b1,x0
        or x0,a
        move a1,x0
        rts
