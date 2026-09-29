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
; tail's source for 1..15), run the two slots on D's sample 0, slot 1 then
; slot 2, and put it back in the ring. The pack, the click and the cue mix
; then read it as stock reads MAIN.
;
; The slot contract is a track slot's: r0 the frames (L at x:(r0), R at
; x:(r0+n0), n0 = 1), r6 the parameter record, r7 the instance block, n7
; the frame count (boot.asm has the map). n0 is set before every call: the
; head used to run on the 1 stock happened to leave there. Every register this body writes that stock might read after
; the return is saved and put back; x0/x1 and the accumulators are written
; by stock before it reads them (func_00055a loads them), and the effects
; leave m1..m4 linear, as stock effects leave them (stock's frame code never
; sets m1, m3, m4).
; ---------------------------------------------------------------------------
entry:
        move    r7,x:>$7c0f             ; the caller's r7
        move    #>$7c00,r7              ; -> the strip's block (boot.asm's map)
        move    r1,x:(r7+$0)
        move    r2,x:(r7+$1)
        move    r3,x:(r7+$2)
        move    r4,x:(r7+$3)
        move    r5,x:(r7+$4)
        move    r6,x:(r7+$5)
        move    n0,x0
        move    x0,x:(r7+$6)
        move    n1,x0
        move    x0,x:(r7+$7)
        move    n2,x0
        move    x0,x:(r7+$8)
        move    n3,x0
        move    x0,x:(r7+$9)
        move    n7,x0
        move    x0,x:(r7+$a)
; ---- gather MAIN, dry, into D ------------------------------------------------
        move    x:>$203,r1              ; the ring the mixdown wrote
        lua     (r1+$2),r1              ; sample 0's MAIN L
        move    #$7,n1                  ; R, then the next sample's L
        move    #>$7c40,r0              ; D
        move    #>$7e90,r4              ; the returns' wet at their levels: MAIN's add
        move    #>$7eb0,r3              ; and CUE's (tail.asm's retmix)
        move    x:>$203,r2              ; CUE L of sample 0
        move    #$7,n2
        do      #$10,hgath
        move    x:(r2),a                ; CUE L, R: the CUE send of the returns
        move    x:(r3)+,x0
        add     x0,a            x:(r3)+,x1
        move    x:(r2+$1),b
        add     x1,b            a,x:(r2)+
        move    b,x:(r2)+n2
        move    x:(r1),a                ; MAIN L, R plus the returns' wet, into the ring
        move    x:(r4)+,x0              ; and D (the strip's inserts hear the returns)
        add     x0,a            x:(r4)+,x1
        move    x:(r1+$1),b
        add     x1,b            a,x:(r1)+
        move    b,x:(r1)+n1
        move    a,x:(r0)+
        move    b,x:(r0)+
hgath:
; ---- the slots on sample 0, back into the ring --------------------------------
        move    #>$7c40,r0              ; D's sample 0
        bsr     hrun
        move    #>$7c40,r0
        move    x:>$203,r1
        lua     (r1+$2),r1
        move    x:(r0)+,x0
        move    x0,x:(r1)+
        move    x:(r0)+,x0
        move    x0,x:(r1)+
; ---- back as stock left them -------------------------------------------------
        move    x:(r7+$a),n7
        move    x:(r7+$9),n3
        move    x:(r7+$8),n2
        move    x:(r7+$7),n1
        move    x:(r7+$6),n0
        move    x:(r7+$5),r6
        move    x:(r7+$4),r5
        move    x:(r7+$3),r4
        move    x:(r7+$2),r3
        move    x:(r7+$1),r2
        move    x:(r7+$0),r1
        move    x:>$7c0f,r7
        move    x:>$206,r0              ; the displaced instruction, as stock has it
        rts

; ---- the two slots on one pair at r0, in place; r7 the strip's block, and
; again on return. A slot whose proc word is 0 is dry (tail.asm's apply).
hrun:
        move    r0,x:(r7+$14)
        move    x:(r7+$11),a            ; slot 1's proc
        tst     a
        beq     hskp1
        move    x:(r7+$11),r2
        move    #>$7c20,r6              ; its record
        move    #>$7d00,r7              ; its instance block
        move    #$1,n7                  ; one frame
        move    #$1,n0                  ; R next to L (the contract's x:(r0+n0))
        jsr     (r2)
        move    #>$7c00,r7
        move    x:(r7+$14),r0
hskp1:
        move    x:(r7+$13),a            ; slot 2's proc
        tst     a
        beq     hskp2
        move    x:(r7+$13),r2
        move    #>$7c30,r6
        move    #>$7e00,r7
        move    #$1,n7
        move    #$1,n0
        jsr     (r2)
        move    #>$7c00,r7
hskp2:
        rts
