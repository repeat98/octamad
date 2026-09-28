; 808 DSP voice. Same ABI and desk state offsets as bd909.asm.
; Original coefficient model: dsp808.py. No samples embedded.
zv01:
        move #>$ffffff,m0
        move #>$ffffff,m1
        move #>$ffffff,m4
        move x:(r6+$0),a
        move a1,n1
        move #>@B_INC@,r1
        move x:(r1+n1),x0
        move x0,x:(r5+@INC@)
        move x:(r6+$1),a
        move a1,n1
        move #>@B_DE@,r1
        move x:(r1+n1),x0
        move x0,x:(r5+@DE@)
        move #>@B_DP@,r1
        move x:(r1+n1),x0
        move x0,x:(r5+@DP@)
        move #>@B_BEND@,r1
        move x:(r1+n1),x0
        move x0,x:(r5+@BEND@)
        move #>@B_GAIN@,r1
        move x:(r1+n1),x0
        move x0,x:(r5+@GAIN@)
        move x:(r6+$2),a
        move a1,n1
        move #>@B_TONE@,r1
        move x:(r1+n1),x0
        move x0,x:(r5+@KT@)
        move x:(r6+$7),a
        move a1,n1
        move #>@B_VEL@,r1
        move x:(r1+n1),x0
        move x0,x:(r5+@VEL@)
        move x:(r6+$3),a
        move a1,n1
        move #>@B_ATK@,r1
        move x:(r1+n1),x0
        move x0,x:(r5+@ATK@)
        move x:(r6+$8),a
        move a1,n1
        move #>@T_LPF@,r1
        move x:(r1+n1),x0
        move x0,x:(r5+@KLPF@)
; SWEEP 64 is the recorded excursion; zero removes it.
        move x:(r6+$4),a
        rep #$10
        asl a
        move a,x0
        move x:(r5+@BEND@),y0
        mpy y0,x0,a
        asl a
        move a,x:(r5+@BEND@)
@desk-decode@
        move x:(r6+$c),a
        tst a
        blt zv03
        move a,x:(r5+@SEG@)
        bsr zv04
        bsr zv06
        move n7,a
        move x:(r5+@SEG@),x0
        sub x0,a
        bsr zv04
        rts
zv03:
        move n7,a
        bsr zv04
        rts
zv04:
        tst a
        beq zv05
        do a1,zv07
; Phase and exponentially settling pitch.
        move x:(r5+@EP@),x0
        move x:(r5+@BEND@),y0
        move x:(r5+@INC@),a
        mac y0,x0,a
        move a,x1
        move x0,b
        move x:(r5+@DP@),y0
        mac -y0,x0,b
        move b,x:(r5+@EP@)
        move x:(r5+@U@),a
        add x1,a
        move a1,x:(r5+@U@)
; Triangle -> sine/2, odd degree-nine polynomial on [-1,1].
        move a1,x0
        move x0,a
        abs     a                       #>$400000,y0
        sub y0,a
        asl a
        neg a
        move a,x1
        move x1,x0
        mpy x0,x0,a
        move a,x0
        move #>@S9@,y0
        move #>@S7@,a
        mac y0,x0,a
        move a,y0
        move #>@S5@,a
        mac y0,x0,a
        move a,y0
        move #>@S3@,a
        mac y0,x0,a
        move a,y0
        move #>@S1@,a
        mac y0,x0,a
        move a,y0
        mpy x1,y0,a
        move a,x1
; Measured small second harmonic, body /4.
        move x1,x0
        mpy x0,x0,a
        move a,x0
        move #>$e08103,y0
        move #>$03eff2,b
        mac y0,x0,b
        add x1,b
        move b,x0
        move x:(r5+@GAIN@),y0
        mpy y0,x0,a
        move a,x1
        move x:(r5+@EH@),b
        move x:(r5+@EL@),b0
        move b1,x0
        move x:(r5+@DE@),y0
        mac -y0,x0,b
        move b,x:(r5+@EH@)
        move b0,x:(r5+@EL@)
        move b,y0
        mpy x1,y0,a
        move a,x:(r5+$11)
; Retire the inaudible trigger path after 4096 samples. This prevents a
; truncated 24-bit damping state leaving a permanent DC residue.
        move x:(r5+$16),a
        add #>$1,a
        move a,x:(r5+$16)
        cmp #>$1000,a
        bge zv09
; Damped trigger oscillator. Both states are quarter scale.
        move x:(r5+@PC@),x0
        move x:(r5+@PS@),x1
        move #>@PK@,y0
        move x0,b
        mac -x1,y0,b
        move b,x0
        move x1,a
        mac y0,x0,a
        move a,x1
        move #>@PD@,y0
        mac -x1,y0,a
        move a,x:(r5+@PS@)
        mac -y0,x0,b
        move b,x:(r5+@PC@)
        move x:(r5+@DC@),x0
        move x0,a
        move #>@DD@,y0
        mac -y0,x0,a
        move a,x:(r5+@DC@)
        move a,x0
        add x0,b
        move b,x0
        move x:(r5+@ATK@),y0
        mpy y0,x0,a
        asl a
        bra zv10
zv09:
        clr a
zv10:
        move x:(r5+$11),x0
        add x0,a
; TONE shapes the trigger edge and body together, before the clip.
        move a,x1
        move x:(r5+@TF@),x0
        move x0,b
        move x:(r5+@KT@),y0
        mac x1,y0,b
        mac -y0,x0,b
        move b,x:(r5+@TF@)
        asl b
        asl b
        move b,x0
        move x:(r5+@VEL@),y0
        mpy y0,x0,b
; Same LPF and Mackie stage as 909.
        move b,x0
        move x:(r5+@YL@),y1
        move y1,a
        move x:(r5+@KLPF@),y0
        mac y0,x0,a
        mac -y1,y0,a
        move a,x:(r5+@YL@)
@desk@
zv07:
zv05:
        rts
zv06:
        clr a
        move a,x:(r5+$16)
        move #>$7fffff,x0
        move x0,x:(r5+@EH@)
        move x0,x:(r5+@EP@)
        move #>$ffffff,x0
        move x0,x:(r5+@EL@)
        move #>@U0@,x0
        move x0,x:(r5+@U@)
        move #>@PC0@,x0
        move x0,x:(r5+@PC@)
        move #>@PS0@,x0
        move x0,x:(r5+@PS@)
        move #>@DC0@,x0
        move x0,x:(r5+@DC@)
        rts
zv02:
        clr a
        move r5,r1
        do #$30,zv08
        move a,x:(r1)+
zv08:
        move #>$7fffff,x0
        move x0,x:(r5+$16)
        rts
