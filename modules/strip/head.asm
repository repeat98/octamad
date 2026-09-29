; ---------------------------------------------------------------------------
; MASTER STRIP -- head: MAIN's first sample, before stock's tail.
;
; Reached by `jsr` over the seam's two-word `move x:>$206,r0` (payload A,
; P:0x2d5), where both mixdown paths have written this frame's 16 samples
; into the TX ring (x:$203, eight words a sample: CUE L/R at +0/+1, MAIN L/R
; at +2/+3, the phones at +4/+5) and nothing has read them yet.
;
; WHY THE PASS IS SPLIT. The output DMA enters the ring about half a sample
; after the mixdown lands (MIXER.md section 2, under the port), and stock's
; tail, after the pack (P:0x2df..), writes sample 0 of two things it reads:
; the metronome click into CUE and MAIN (P:0x2ec..) and the cue mix into the
; phones (P:0x33f..). A whole 16-sample pass here (~2,700 cycles) held both
; back, and under the port the phones' first sample of every frame went out
; two frames stale (29 Sep 2026, verify_strip). So the head does sample 0
; only and returns; stock's tail runs on time with it; the tail (tail.asm,
; P:0x35d) does samples 1..15 and redoes what stock's tail made from them.
;
; Here: gather MAIN's 16 dry pairs into D (X:0x7c40, L/R adjacent, the
; tail's source for 1..15), run the insert on D's sample 0, and put it back
; in the ring. The pack, the click and the cue mix then read it as stock
; reads MAIN.
;
; The insert contract is a track slot's: r0 the frames (L, R adjacent), r6
; the parameter record, r7 the instance block, n7 the frame count. Every
; register this body writes that stock might read after the return is saved
; and put back; x0/x1 and the accumulators are written by stock before it
; reads them (func_00055a loads them), and the insert leaves m1..m4 linear,
; as stock effects leave them (stock's frame code never sets m1, m3, m4).
; ---------------------------------------------------------------------------
entry:
        move    r7,x:>$7c3f             ; the caller's r7
        move    #>$7c00,r7              ; -> the strip's block (boot.asm's map)
        move    r1,x:(r7+$30)
        move    r2,x:(r7+$31)
        move    r3,x:(r7+$32)
        move    r4,x:(r7+$33)
        move    r5,x:(r7+$34)
        move    r6,x:(r7+$35)
        move    n0,x0
        move    x0,x:(r7+$36)
        move    n1,x0
        move    x0,x:(r7+$37)
        move    n2,x0
        move    x0,x:(r7+$38)
        move    n3,x0
        move    x0,x:(r7+$39)
        move    n7,x0
        move    x0,x:(r7+$3a)
; ---- gather MAIN, dry, into D ------------------------------------------------
        move    x:>$203,r1              ; the ring the mixdown wrote
        lua     (r1+$2),r1              ; sample 0's MAIN L
        move    #$7,n1                  ; R, then the next sample's L
        move    #>$7c40,r0              ; D
        do      #$10,hgath
        move    x:(r1)+,x0
        move    x:(r1)+n1,x1
        move    x0,x:(r0)+
        move    x1,x:(r0)+
hgath:
; ---- the insert on sample 0, back into the ring ----------------------------
        move    #>$7c40,r0              ; D's sample 0
        move    #>$7c80,r6              ; the strip's parameter record
        move    #$1,n7                  ; one frame
        move    x:>$254,r2              ; PROC_TABLE[0x1f]: OXIDE's proc
        jsr     (r2)
        move    #>$7c40,r0
        move    x:>$203,r1
        lua     (r1+$2),r1
        move    x:(r0)+,x0
        move    x0,x:(r1)+
        move    x:(r0)+,x0
        move    x0,x:(r1)+
; ---- back as stock left them -------------------------------------------------
        move    x:(r7+$3a),n7
        move    x:(r7+$39),n3
        move    x:(r7+$38),n2
        move    x:(r7+$37),n1
        move    x:(r7+$36),n0
        move    x:(r7+$35),r6
        move    x:(r7+$34),r5
        move    x:(r7+$33),r4
        move    x:(r7+$32),r3
        move    x:(r7+$31),r2
        move    x:(r7+$30),r1
        move    x:>$7c3f,r7
        move    x:>$206,r0              ; the displaced instruction, as stock has it
        rts
