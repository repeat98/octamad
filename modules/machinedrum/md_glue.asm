; ---------------------------------------------------------------------------
; md_glue -- the Machinedrum's host on core 1 (payload B, tracks 1-4): its
; boot, its dispatch entries, the stereo mix and the fixed trigger (WP-B3,
; WP-B4, WP-A5 option A). It sits in the shared window, beside the MD code
; that does not fit private P, and tools/build/md_image.py fills the
; placeholders between at-signs from layout.py, the payload's reloc.txt and
; the driver's symbols.
;
; gboot    payload B's startup calls it where stock cleared Y:$4000-$bfff
;          and the window's upper half (P:$47-$4a). Those words now hold
;          the MD's tables, P-I buffers and driver state, so nothing is
;          cleared; the MD's own boot init (relocated) builds the sine at
;          @SINE@, zeroes the P-I buffers and the voice records' word 0.
;          It then keeps a copy of the sine's first sixteen words: payload
;          B's boot handshake parks sixteen of its own words there while it
;          waits for core A, and gfxproc puts the sine back once.
; gaclr    CORE 0 calls it where payload A cleared Y:$4000-$bfff and
;          Y:$30000-$37fff. It clears the first range and $30000-$33fff
;          only: $34000-$37fff carries the MD's window code and tables,
;          loaded by payload B's upload before core 0 reaches its clear.
; gfxinit  the dispatch INIT entry for the MACHINEDRUM id on core 1. The
;          track whose FX slot selects the MD owns the instance; r1 is left
;          alone (the FX1 dispatcher keeps the id there across the call).
; gfxproc  the dispatch PROCESS entry. Called once or twice per frame per
;          slot (the dispatcher splits a frame at a trig's sample offset,
;          x:$20c). On the frame's first call (r0 = 0) it triggers slot 0
;          on the OT trig, runs the driver (half of the sixteen slots), and
;          after every second call mixes the finished 32-sample period. Every
;          call writes its part of the frame from the mix, times p0 (VOL).
;
; The fixed trigger (WP-B4): bit 16 of word $1e of the track's state block
; (x:(x:$419)+$1e) is set on the frame of an OT trig. Measured under the
; port on core 1's four tracks, 24 Sep 2026: set on exactly the trig frames
; (3, 347, 692, 1036 at 120 BPM). On it, @FIXED@'s fourteen words go to slot
; 0's record at @VOICE@: word 0 is the engine's routine index, which the
; driver treats as "trigger".
;
; The mix (decision D1 open; this is option A's shape): out = sum over the
; sixteen slots of slot x @GAIN@[slot], L = R. The gains default to 1/4.
; Latency: a period is mixed on the frame its second half is rendered and
; played over that frame and the next.
;
; Registers. The dispatcher reloads everything it uses after an effect
; except the modifiers, and the driver's engines leave modulo modes behind,
; so every modifier is set linear before gfxproc returns. r6 (the parameter
; block) and n7 (the frame count) are kept across the driver.
;
; dsp_asm (the shared build, pin c051afad): no backward branch, jmp/jsr only
; in the short form, "cmp a,b" encodes as max. So: jsr through r1, loops by
; do/rep, compares against x0. No label is a prefix of another (labels
; resolve by prefix; md_image.py checks). md_image.py disassembles the result
; and refuses max/dc/illegal and any mac or mpy that decodes as su/uu.
; ---------------------------------------------------------------------------

gfxinit:
        move    x:>$418,x0              ; this track's offset in the ring
        move    x0,x:>@OWNER@
        rts

gfxproc:
        move    x:>$418,x0
        move    x:>@OWNER@,a
        cmp     x0,a
        beq     gmine
        rts                             ; not the owner: its audio is in place
gmine:
        move    r0,a
        tst     a
        bne     gcopy                   ; the frame's second part: output only
        move    r6,x:>@SAVER6@
        move    n7,x:>@SAVEN7@
        move    x:>@ONCE@,a
        tst     a
        bne     gsined
        move    #>@SINE16@,r1
        move    #>@SINE@,r2
        do      #16,gsinelp
        move    x:(r1)+,x0
        move    x0,x:(r2)+
gsinelp:
        move    #>$1,x0
        move    x0,x:>@ONCE@
gsined:
        move    x:>$419,r1              ; this frame's track state
        move    #>$1e,n1
        move    x:(r1+n1),a
        and     #>$10000,a              ; only Z is used: no store of a follows
        beq     gnotrg
        move    #>@FIXED@,r1
        move    #>@VOICE@,r2
        do      #14,gfixlp
        move    x:(r1)+,x0
        move    x0,y:(r2)+
gfixlp:
        move    x:>@TRIGS@,a            ; the trigs taken, for the gates
        add     #<$1,a
        move    a,x:>@TRIGS@
gnotrg:
        move    #>@ENTER@,r1
        jsr     (r1)
        move    #>$ffffff,x0
        move    x0,m0
        move    x0,m1
        move    x0,m2
        move    x0,m3
        move    x0,m4
        move    x0,m5
        move    x0,m6
        move    x0,m7
        move    y:>@HALF@,a
        tst     a
        bne     gsecnd                  ; slots 0-7 of a new period: play the second half
        move    #>@OUTBUF@,r4           ; 512-aligned: m4 = $1ff wraps each column
        move    #>$20,n4
        move    #>$1ff,m4
        move    #>@GAIN@,r1             ; 16-aligned: m1 = $f
        move    #>$f,m1
        move    #>@MIX@,r5
        do      #32,gmixlp
        clr     a
        do      #16,gslotlp             ; ALU op and parallel move kept apart:
        move    x:(r1)+,x0      y:(r4)+n4,y0 ; the pinned dsp_asm turned the
        mac     y0,x0,a                 ; combined form into one unrelated word
gslotlp:
        move    (r4)+
        move    a,x:(r5)+
        move    a,x:(r5)+
gmixlp:
        move    #>$ffffff,x0
        move    x0,m1
        move    x0,m4
        move    #>@MIX@,x0
        move    x0,x:>@GOUT@
        bra     grest
gsecnd:
        move    #>@MIX2@,x0
        move    x0,x:>@GOUT@
grest:
        move    x:>@SAVER6@,r6
        move    x:>@SAVEN7@,n7
        move    #$0,r0
gcopy:
        move    x:>@GOUT@,a
        move    r0,x0
        add     x0,a
        move    a,r1
        move    x:(r6),y1               ; p0 VOL, val<<16 = val/128
        do      n7,gcpylp
        move    x:(r1)+,x0
        mpy     x0,y1,a                 ; the sample in x0: a signed order
        move    a,x:(r0)+
        move    x:(r1)+,x0
        mpy     x0,y1,a
        move    a,x:(r0)+
gcpylp:
        rts

gboot:
        move    #>@MDINIT@,r1
        jsr     (r1)
        move    #>@SINE@,r1
        move    #>@SINE16@,r2
        do      #16,gbtlp
        move    x:(r1)+,x0
        move    x0,x:(r2)+
gbtlp:
        move    #>$ffffff,x0
        move    x0,m0
        move    x0,m1
        move    x0,m4
        rts

gaclr:
        do      b,gacl1                 ; b = $8000, r4 = $4000: payload A's own
        move    a,y:(r4)+
gacl1:
        move    #>$4000,x0
        do      x0,gacl2                ; r5 = $30000: the lower half only
        move    a,y:(r5)+
gacl2:
        rts
