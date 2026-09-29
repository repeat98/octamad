; ---------------------------------------------------------------------------
; MASTER STRIP -- boot: the insert's instance block and the strip's record.
;
; Reached by `jsr` over P:0x40's `move #>$8000,b`, the first instruction of
; payload A after the upload (the zeroing loop and the poll loop follow, and
; nothing jumps back here). Runs once per DSP boot, before the first frame,
; so the strip never starts from what the RAM held: X is not zeroed on the
; unit (CLAUDE.md, the dirty-state trap).
;
; X:0x7c00..0x7cff is the strip's (docs/proposals/MIXER.md "Step 2"): outside
; every X module of payload A (the curve table ends at 0x7a91, the TX ring
; starts at 0x8000) and written by nothing under the port on the user's
; project (`ot_emu --dsp-writes`, 900 frames, 29 Sep 2026).
;   $00..$2f  the insert's instance block (OXIDE: two channel states, the
;             ring flag, the coefficient ring at $20, 16-aligned for m3 = 15)
;   $30..$3a  the registers head.asm and tail.asm save around their passes
;   $3b..$3e  the tail's loop: the ring's sample j, D's sample j, the cue
;             mix's gains for sample j (a Y address), the cue mix's L/R word
;   $3f       the caller's r7
;   $40..$5f  D: MAIN's 16 pairs, L/R adjacent; the head gathers them dry and
;             the insert runs on them in place
;   $60..$7f  C: what the click added to MAIN, samples 1..15 (tail.asm)
;   $80, $81  the parameter record the insert reads through r6: IN, OUT as
;             val << 16. Fixed here until the ColdFire ships a record per
;             strip (MIXER.md section 7, decision 6).
;
; OXIDE is reached through the stock dispatch tables, as a track slot reaches
; it: INIT_TABLE at X:0x215 and PROC_TABLE at X:0x235, indexed by the FX id
; (0x1f). The manifest requires OXIDE; the strip's gate checks the id.
; ---------------------------------------------------------------------------
entry:
        move    #>$7c00,r7              ; the strip's instance block
        move    x:>$234,r2              ; INIT_TABLE[0x1f]: OXIDE's init
        jsr     (r2)
        move    #>$300000,x0            ; IN 48: 0 dB into the tape
        move    x0,x:>$7c80
        move    #>$500000,x0            ; OUT 80: 0 dB out
        move    x0,x:>$7c81
        move    #>$8000,b               ; the displaced instruction, as stock has it
        rts
