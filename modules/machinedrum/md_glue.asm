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
;          cleared by stock. Clear the driver's private Y state explicitly;
;          the MD's own boot init (relocated) builds the sine at
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
;          x:$20c). On the frame's first call (r0 = 0) it writes the
;          ColdFire's record packets into the voice records (WP-C1, below),
;          triggers slot 0 on the OT trig while no packet has ever arrived,
;          runs the driver (half of the sixteen slots), and after every
;          second call mixes the finished 32-sample period. Every call
;          writes its part of the frame from the mix at the fixed proof gain.
;
; The record transport (WP-C1). The ColdFire sends one block a frame
; (modules/machinedrum/md_xport.s) to X:$7d40; payload B's host-command
; handler masks the destination per frame, so it lands at @MBOXA@ or
; @MBOXB@, and this frame's bank is x:$207 + @MBOXOFF@ (x:$207 is $2000 or
; $4000, payload B's P:$76). Every word carries 16 bits:
;   [0] seq     1..$ffff, one more per block sent
;   [1] flags   bit 0: sync, the block precedes a period's slots 0-7
;   [2] npkt    packets that follow, at most 64
;   then npkt x [dest] [count] [hi lo] x count
; dest is the Machinedrum's own Y address of the first word (a voice record,
; $800 + $40 x slot + k), as the MD's host sends it; each word is hi<<16|lo.
; The words go to the relocated records exactly as the MD's DMA5 writes
; them: word 0 is the trigger, which the driver clears. A bank whose seq is
; not newer than the last one taken is skipped (the ColdFire sent nothing
; that frame, or it is the other frame's). A packet outside the records or
; past the bank is refused and ends the block (@BAD@).
;
; The fixed trigger (WP-B4): bit 16 of word $1e of the track's state block
; (x:(x:$419)+$1e) is set on the frame of an OT trig. Measured under the
; port on core 1's four tracks, 24 Sep 2026: set on exactly the trig frames
; (3, 347, 692, 1036 at 120 BPM). On it, @FIXED@'s fourteen words go to slot
; 0's record at @VOICE@: word 0 is the engine's routine index, which the
; driver treats as "trigger".
;
; The OT-side stereo mix: L/R each sum sixteen slot samples multiplied by
; @GAIN@/@GAINR@. Both tables default to 1/4 per slot (centered proof).
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
; ---- WP-C1: the ColdFire's record packets for this frame
        move    #>$ffffff,m2
        move    #>$ffffff,m3
        move    x:>$207,a               ; this frame's host bank, $2000 or $4000
        add     #>@MBOXOFF@,a
        move    a,r3
        add     #>@MBOXLEN@,a
        move    a,y0                    ; the bank's end
        clr     a
        move    x:(r3)+,a1
        and     #>$ffff,a               ; seq
        move    a1,y1
        move    x:>@LSEQ@,x0
        sub     x0,a                    ; seq - LSEQ, modulo $10000
        bge     xpos
        add     #>$10000,a
xpos:
        tst     a
        beq     xnone                   ; nothing new in this bank
        move    #>$8000,x0
        cmp     x0,a
        bge     xnone                   ; older than the last block taken
        move    y1,x:>@LSEQ@
        sub     #<$1,a
        move    x:>@GAPS@,x0
        add     x0,a
        move    a,x:>@GAPS@
        move    x:>@NAPPLY@,a
        add     #<$1,a
        move    a,x:>@NAPPLY@
        clr     a
        move    x:(r3)+,a1
        and     #>$1,a                  ; sync
        beq     xnosync
        move    y:>@HALF@,a
        tst     a
        beq     xnosync
        clr     a
        move    a,y:>@HALF@             ; the driver's next half is slots 0-7
        move    x:>@SLIPS@,a
        add     #<$1,a
        move    a,x:>@SLIPS@
xnosync:
        clr     a
        move    x:(r3)+,a1
        and     #>$ffff,a               ; npkt
        tst     a
        beq     xnone
        move    #>$41,x0
        cmp     x0,a
        bge     xtoomany
        move    a1,x0
        do      x0,xpend
        clr     b
        move    x:(r3)+,b1
        and     #>$ffff,b
        move    b1,x1                   ; dest
        clr     a
        move    x:(r3)+,a1
        and     #>$ffff,a               ; count
        tst     a
        beq     xpnext
        move    a1,x0
        move    x1,b
        sub     #>$800,b
        blt     xpbad                   ; below the records
        add     x0,b
        move    #>$400,y1
        cmp     y1,b
        bgt     xpbad                   ; past the sixteen records
        move    r3,b
        add     x0,b
        add     x0,b
        cmp     y0,b
        bgt     xpbad                   ; past the bank
        move    x1,b
        add     #>@VOICEOFF@,b
        move    b,r2
        do      x0,xwend
        clr     b
        move    x:(r3)+,b1
        and     #>$ff,b
        asl     #$10,b,b
        clr     a
        move    x:(r3)+,a1
        and     #>$ffff,a
        move    a1,x1
        add     x1,b                    ; = or: hi<<16 has no low bits (add, a
        move    b1,y:(r2)+              ; stock form); a1/b1 moves do not limit
xwend:
        move    x:>@NWORDS@,b
        add     x0,b
        move    b,x:>@NWORDS@
        bra     xpnext
xpbad:
        move    x:>@BAD@,b
        add     #<$1,b
        move    b,x:>@BAD@
        move    y0,r3                   ; the rest of the block is not read
xpnext:
        nop
xpend:
        bra     xnone
xtoomany:
        move    x:>@BAD@,b
        add     #<$1,b
        move    b,x:>@BAD@
xnone:
        move    x:>@NAPPLY@,a           ; the fixed trigger stands in only
        tst     a                       ; until the ColdFire drives the MD
        bne     gnotrg
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
gdone:                                  ; the gates sample here: the half just rendered
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
        move    #>@GAINR@,r2            ; independent right gain, m2 = $f
        move    #>$f,m2
        move    #>@MIX@,r5
        do      #32,gmixlp
        clr     a
        clr     b
        do      #16,gslotlp             ; ALU op and parallel move kept apart:
        move    x:(r1)+,x0      y:(r4)+n4,y0 ; the pinned dsp_asm turned the
        mac     y0,x0,a                 ; combined form into one unrelated word
        move    x:(r2)+,x0
        mac     y0,x0,b
gslotlp:
        move    (r4)+
        move    a,x:(r5)+
        move    b,x:(r5)+
gmixlp:
        move    #>$ffffff,x0
        move    x0,m1
        move    x0,m2
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
        move    #>$640000,y1            ; proof gain 100/128, independent of FX2
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
        move    #>$ffffff,m1           ; the driver Y span needs linear writes
        move    #>@DRIVERBASE@,r1
        clr     a
        do      #>@DRIVERWORDS@,gbdrv
        move    a,y:(r1)+
gbdrv:
        clr     a                       ; both mailbox banks: no block yet
        move    #>@MBOXA@,r1
        do      #@MBOXLEN@,gbza
        move    a,x:(r1)+
gbza:
        move    #>@MBOXB@,r1
        do      #@MBOXLEN@,gbzb
        move    a,x:(r1)+
gbzb:
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
