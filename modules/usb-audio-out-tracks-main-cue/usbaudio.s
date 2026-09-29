| usbaudio.s -- USB AUDIO: twenty channels over USB (UAC2).
|
| Channels 1-16: the eight tracks' L/R, post-FX pre-fader, from the
| read-back arena the eDMA fills every block. Channels 17-20: MAIN L/R and
| CUE L/R, the DAC feed. 44.1 kHz, 24 bits in 4-byte subslots, a 250 us
| poll at high speed; the tracks' stereo sum at full speed.
|
| Based on markandrus/octemu custom/coldfire/usb-audio.s at 6a9ff68 (MIT).
| The shims, the EP3 bring-up and the UAC2 class-request replies are his.
| Here it is a DRAM unit: the loader places it and zeroes its data, every
| hook is a detour in manifest.py, and the ISR shim chains to USB MIDI's by
| symbol (the units link together; schema.Override). README.md has what
| was measured.
| SPDX-License-Identifier: MIT
|
| USB_LAYOUT (remix.inc, set by the module that assembles this source):
|   0  USB AUDIO OUT TRACKS MAIN CUE -- the twenty channels above;
|   1  USB AUDIO OUT TRACKS   -- channels 1-16 only, the tracks (no MAIN/CUE);
|   2  USB AUDIO OUT MASTER   -- two channels, track 8's post-FX pre-fader L/R,
|                               at both speeds: the producer reads T8's words
|                               alone and writes one 8-byte slot per frame,
|                               which both speeds send.
|   3  USB AUDIO OUT MAIN CUE -- four channels, MAIN L/R + CUE L/R, at the same
|                               250 us cadence as OUT TRACKS MAIN CUE and OUT
|                               TRACKS: the producer
|                               reads MAIN_CUE_BASE directly (not ping-ponged,
|                               so no bank bookkeeping) and writes one 16-byte
|                               slot per frame. Full speed carries MAIN alone,
|                               into aud_sum, as the twenty- and sixteen-channel
|                               layouts' stereo sum -- skipped at high speed.
|                               Pairs with USB AUDIO IN (the host's stereo
|                               pair -> inputs A/B) as usbin-test's AUD_IN4 did
|                               with its four-channel form, as two independent
|                               modules instead of one flag.
|   4  USB AUDIO OUT MAIN      -- two channels, MAIN L/R alone, from
|                               MAIN_CUE_BASE, one 8-byte slot per frame that
|                               both speeds send (the OUT MASTER shape), at
|                               the 250 us cadence at high speed (96 B packets)
|                               so USB AUDIO IN can take it as its feedback
|                               source: a two-in, two-out interface.
| Layouts 1-3 are ours; every USB_LAYOUT = 0 path is the source as it was.
    .include "remix.inc"
.set LAYOUT_TRACKS_MAIN_CUE,  0
.set LAYOUT_TRACKS, 1
.set LAYOUT_MASTER,   2
.set LAYOUT_MAIN_CUE,   3
.set LAYOUT_MAIN,     4
| gas's .if takes no ||: a sum of comparisons is non-zero when either holds.
.set SLOT8_LAYOUT, (USB_LAYOUT == LAYOUT_MASTER) + (USB_LAYOUT == LAYOUT_MAIN)   | one 8-byte (L,R) slot, both speeds send the ring

.set SUM_SHIFT,      8              | 32-bit read-back -> 24-bit units for the sum
.set UAC2_AC_IFACE,  3              | the audio function's AudioControl
.set UAC2_AS_IFACE,  4              | ... and its AudioStreaming
.set UAC2_CLOCK_ID,  0x10

| ---- firmware sites (1.40C) ----
.set SETUP_ALT,      0x46c8ce0a     | SETUP wValue low = alt setting
.set SETUP_IFACE,    0x46c8ce0c     | SETUP wIndex low = interface number
.set EP0_STATUS_IN,  0x4001d524     | zero-length EP0 IN status (ACK)
.set SETIFACE_DONE,  0x4001de74     | control-request-done
.set SETIFACE_STOCK, 0x4001dd0a     | rejoin after the displaced movel
.set GETIFACE_REJOIN,0x4001d81e     | GET_INTERFACE send tail (expects pea'd ptr)
.set GETIFACE_STOCKP,0x400e20a1     | the stock 1-byte "00" the send reads
.set SETUP_BMREQ,    0x46c8ce08     | SETUP bmRequestType
.set SETUP_BREQ,     0x46c8ce09     | SETUP bRequest
.set SETUP_WVALH,    0x46c8ce0b     | SETUP wValue high = control selector
.set SETUP_WIDXH,    0x46c8ce0d     | SETUP wIndex high = entity id
.set EP0_SEND_TAIL,  0x4001de5c     | jsr usb_ep0_send(len, buf); addq; done
.set CTRL_STOCK,     0x4001de6a     | the stock STALL, after the displaced movel

| ---- USB controller registers ----
.set EPLISTADDR, 0xfc0b0158         | the controller's OWN dQH list base
.set ENDPTSTAT,  0xfc0b01b8
.set EPPRIME,    0xfc0b01b0
.set EPFLUSH,    0xfc0b01b4
.set EPCOMPLETE, 0xfc0b01bc
.set ENDPTCTRL3, 0xfc0b01cc
.set USBCMD,     0xfc0b0140
.set ATDTW,      0x00004000         | USBCMD bit 14: the add-dTD tripwire
.set QH_EP3IN,   0x4ec949c0         | EP3 IN dQH, the fallback when ENDPTLISTADDR
                                    | reads outside SDRAM (audio_qh_resolve)
.set QH_EP3IN_OFF, 7*64             | EP3 IN is list entry (3*2)+1
.set EP3IN_BIT,  0x00080000         | ENDPTPRIME/STAT/COMPLETE bit for EP3 IN

| ---- the track source: the read-back arena ----
| The eDMA deposits every track's post-FX, pre-fader block into SRAM each
| frame; the RECEIVE machine sums the same memory. Layout: RB_BASE +
| bank*1024 + track*128 + frame*8, two 32-bit words (L,R) per frame, 16
| frames per block, 8 tracks, ping-pong banks. The producer reads the
| PREVIOUS bank (the pipeline is one block deep). Track level, the
| crossfader, MAIN volume and the master effects are downstream of this tap.
.set RB_BASE,      0x80003190
.set RB_PREV,      0x800000e4      | pingpong_prev: reads use prev
.set RB_TRACKS,    8
| MAIN and CUE: the DAC feed itself. Core 0's mixdown packs ESAI TX slots
| 2/3 and 0/1 (P:0x2df, P:0x2e2) into the host read-back after the track
| blocks; the frame ISR's chain ch1 -> ch6 -> ch7 lands them here, ch6
| writing 0x80005e60..0x80005f60 each frame: 16 x (L,R) at +0x00, then
| 16 x (L,R) at +0x80, 32-bit words in the read-back's format (24 bits,
| left-justified). The stock recorder reads the same buffer for SRC3 =
| MAIN (+0x00) / CUE (+0x80) from inside frame_isr (0x4000d2a0), before
| this hook; the next frame's ch6 cannot overwrite it until the next
| frame_isr. Single buffer, no ping-pong. MAIN = +0x00, CUE = +0x80
| (hardware: Bryan T's MKII, image 90, 25 Sep 2026).
.set MAIN_CUE_BASE,      0x80005e60
.set MAIN_CUE_MAIN_OFF,  0x00
.set MAIN_CUE_CUE_OFF,   0x80
| In the twenty-channel stream MAIN/CUE of a pull are the mix of the tracks
| one block EARLIER than the track words read beside them (the tracks come
| from the previous bank, the mixdown buffer from the current pull):
| measured under the port at 16 samples on every tone that reaches MAIN
| (tools/harness/usb_align.py, 28 Sep 2026; heard as MAIN lagging on Bryan
| T's unit, 25 Sep). The producer writes the pair this many blocks behind
| the tracks' slot; the consumer runs 512 frames behind, so that slot is
| unread when it is written.
.set MAIN_CUE_LAG_BLOCKS, 1

.if SLOT8_LAYOUT
| x -> x * SLOT_BYTES (8) in place.
.macro MUL_SLOT r, t
    lsll    #3,\r
.endm
.elseif USB_LAYOUT == LAYOUT_TRACKS
| x -> x * SLOT_BYTES (64) in place.
.macro MUL_SLOT r, t
    lsll    #6,\r
.endm
.elseif USB_LAYOUT == LAYOUT_MAIN_CUE
| x -> x * SLOT_BYTES (16) in place.
.macro MUL_SLOT r, t
    lsll    #4,\r
.endm
.else
| x -> x * SLOT_BYTES (80) in place; \t is scratch.
.macro MUL_SLOT r, t
    movel   \r,\t
    lsll    #4,\t                  | x * 16
    lsll    #6,\r                  | x * 64
    addl    \t,\r                 | x * 80
.endm
.endif

| ---- frame geometry --------------------------------------------------------
| The producer fills TWO rings per frame: an 80-byte slot (20 channels, each a
| 4-byte little-endian subslot carrying 24 bits: track 1 L/R first, track 8
| L/R on 15/16, then MAIN L/R on 17/18 and CUE L/R on 19/20) for the HIGH
| SPEED stream, and an 8-byte stereo sum of the eight
| tracks for FULL SPEED. Both are indexed by the same frame count, so the
| wrap arithmetic has one form.
|
| A sample is the read-back word with its low byte cleared: the arena's
| full scale is 2^31, so the subslot's 24 valid bits are its top 24.
|
| Why the poll is 250 us: 20 ch x 4 B at 44.1 kHz is 3,528 B per
| millisecond, and one high-speed isochronous transaction carries at most
| 1,024 B. At bInterval 2 a packet is 11.025 frames x 80 B = 882 B, at most
| 12 frames = 960 B with the servo. Full speed carries the stereo sum only:
| 44.1 frames x 8 B = 353 B per 1 ms frame, under the 1,023 B cap. UAC1
| cannot poll faster than 1 ms even at high speed (Apple TN3190: bInterval
| must be 4); this is why the descriptors are UAC2.
.if USB_LAYOUT == LAYOUT_MASTER
| Two channels: T8's (L,R) is the one slot, 8 bytes, the same ring at both
| speeds (the full-speed "sum" ring is this ring). High speed polls every
| 250 us like the other layouts (11/12 frames x 8 B = 96 B; until 28 Sep 2026
| it polled every 1 ms, 360 B, which a USB AUDIO IN module cannot take as its
| implicit-feedback source); full speed 44/45 frames x 8 B = 360 B.
| The packet buffer stride is 512.
.set SLOT_BYTES,   8            | ring slot: T8 (L,R), 4 B each
.set SUM_BYTES,    8
.set PKT_MAX_HS,   12*SLOT_BYTES | 96: the largest 250 us packet
.set PKT_MAX_FS,   45*SUM_BYTES | 360: the largest 1 ms packet
.set PKT_BUF,      512          | packet buffer stride (>= PKT_MAX_FS)
.elseif USB_LAYOUT == LAYOUT_MAIN
| Two channels, MAIN's (L,R), one 8-byte slot, the same ring at both speeds
| (as OUT MASTER), but polled every 250 us at high speed like the other
| 250 us layouts: 11/12 frames x 8 B = 96 B; full speed 44/45 x 8 = 360 B.
.set SLOT_BYTES,   8            | ring slot: MAIN (L,R), 4 B each
.set SUM_BYTES,    8
.set PKT_MAX_HS,   12*SLOT_BYTES | 96: the largest 250 us packet
.set PKT_MAX_FS,   45*SUM_BYTES | 360: the largest 1 ms packet
.set PKT_BUF,      512          | packet buffer stride (>= PKT_MAX_FS)
.elseif USB_LAYOUT == LAYOUT_TRACKS
.set SLOT_BYTES,   64           | ring slot: 8 tracks * (L,R), 4 B each
.set SUM_BYTES,    8            | sum slot: (L,R) * 4 B
.set PKT_MAX_HS,   12*SLOT_BYTES | 768: the largest 250 us packet
.set PKT_MAX_FS,   45*SUM_BYTES | 360: the largest 1 ms stereo packet
.set PKT_BUF,      PKT_MAX_HS   | packet buffer stride
.elseif USB_LAYOUT == LAYOUT_MAIN_CUE
| Four channels (MAIN L/R + CUE L/R) at the 250 us cadence: 11.025 frames x
| 16 B is 176 B a packet, well under the 1,024 B cap. Full speed carries
| MAIN alone (2 ch, the same SUM_BYTES shape every layout uses), and at
| 44.1 frames x 8 B = 360 B that packet is LARGER than the high-speed one
| here, unlike OUT TRACKS / OUT TRACKS MAIN CUE -- so the buffer stride is sized off the full-speed
| side, same reasoning as OUT MASTER's 512.
.set SLOT_BYTES,   16           | ring slot: MAIN (L,R) + CUE (L,R), 4 B each
.set SUM_BYTES,    8            | sum slot: MAIN (L,R) * 4 B
.set PKT_MAX_HS,   12*SLOT_BYTES | 192: the largest 250 us packet
.set PKT_MAX_FS,   45*SUM_BYTES | 360: the largest 1 ms stereo (MAIN-only) packet
.set PKT_BUF,      512          | packet buffer stride (>= PKT_MAX_FS)
.else
.set SLOT_BYTES,   80           | ring slot: 8 tracks * (L,R) + MAIN (L,R) + CUE (L,R), 4 B each
                                | not a power of two: index math is MUL_SLOT (x*64 + x*16)
.set SUM_BYTES,    8            | sum slot: (L,R) * 4 B
.set PKT_MAX_HS,   12*SLOT_BYTES | 960: the largest 250 us packet (<= 1,024 B, one transaction)
.set PKT_MAX_FS,   45*SUM_BYTES | 360: the largest 1 ms stereo packet
.set PKT_BUF,      PKT_MAX_HS   | packet buffer stride
.endif
.set STEP_HS,      11025        | 11.025 frames per 250 us packet, x1000 (every layout)
.set STEP_FS,      44100        | 44.1 frames per 1 ms packet, x1000
.set SERVO_STEP,   100          | +-0.1 frame per packet, x1000

| Four queue slots, so the host always finds a packet waiting: four packets
| cover 1 ms of polls. The frame ISR (every 363 us) is the only context that
| queues, so the queue must outlast one block plus that interrupt's latency.
.set NSLOT,        4            | power of two: slot arithmetic is a mask
.set UNCACHED,     0x08000000   | + an SDRAM address = the same memory,
                                | cache-inhibited (PLACEMENT.md)

| The rings live in the unit's data and are zeroed by the loader. 1024
| frames = 23 ms of buffer. Only the CPU reads the rings, through their
| cached addresses (the USB controller reads the packet buffers), so the
| rings need no cache maintenance.
.set AUD_FRAMES,   1024
.set AUD_TARGET,   512          | ring fill the stream starts at and the servo
                                    | steers towards: ~12 ms, so a momentary
                                    | producer stall is absorbed
.set AUD_BAND,     128          | servo deadband, so it does not hunt

.set PORTSC1,    0xfc0b0184         | bits 27:26 = port speed, 2 = high

    .text
| ---- SET_INTERFACE shim (installed at 0x4001dd04) ---------------------------
| Displaced: movel 0xfc0b01c4,%d0. Interface 4 (AudioStreaming) records the
| requested alt setting and completes the status stage; any other interface
| falls through to the stock handler unchanged.
|
| The shim RECORDS the request. Everything that builds EP3 state — the
| queue head, the dTDs, ENDPTCTRL3, the ring cursors — is done by the frame
| ISR (audio_ep3_up / audio_ep3_down), the one context that also queues
| packets. This runs from the USB interrupt; if it re-initialized the
| endpoint itself, a SET_INTERFACE landing in the middle of a kick would
| rewrite a queue the kick was still building, and the kick would then prime
| the remains. One owner, one byte of shared state.
|
| The one exception is alt 0's FLUSH, done here as well: the host may send
| its next IN within microseconds of the status stage, before the frame ISR
| has had its block, and a packet already queued would answer it — audio
| after teardown. A flush only cancels what is in flight, is idempotent, and
| builds nothing, so it is safe from this context; the kick checks the
| request byte before it queues, so nothing new follows it; and the frame
| ISR flushes again on its way down. (verify_usb asserts silence after
| alt 0.)
|
| Interrupt levels, from the firmware's own INTC writes: the USB interrupt
| is INTC1 source 47 at level 4 (moveq #4 / moveb ->0xfc04c06f at
| 0x4001e024); the frame IRQ is EPORT IRQ1 at level 5 (0x4001fc30). So the
| frame ISR can preempt this shim — harmless, it only ever sees the request
| byte — and this shim can never interrupt a kick.
    .global audio_setiface_shim
audio_setiface_shim:
    mvzb    SETUP_IFACE,%d0
    moveq   #UAC2_AS_IFACE,%d1
    cmpl    %d0,%d1
    bne     5f                      | not the AudioStreaming interface -> stock
    mvzb    SETUP_ALT,%d0
    tstl    %d0
    beqs    2f
    moveq   #1,%d0                  | any non-zero alt is the streaming one
    moveb   %d0,usbaudio_alt        | the request; the frame ISR brings EP3 up
    bras    3f
2:  clrb    usbaudio_alt            | the request FIRST: no kick queues past it
    bsr     audio_ep3_flush         | then cancel what is already queued
3:  jsr     EP0_STATUS_IN
    jmp     SETIFACE_DONE
5:  movel   0xfc0b01c4,%d0          | displaced
    jmp     SETIFACE_STOCK

| ---- GET_INTERFACE shim (installed at 0x4001d824) ---------------------------
| Displaced: pea 0x400e20a1 (the stock 1-byte "00"). Interface 4 reports the
| alt setting the host asked for (whether or not the frame ISR has acted on it
| yet, which it does within one block); every other interface keeps the stock
| answer.
    .global audio_getiface_shim
audio_getiface_shim:
    mvzb    SETUP_IFACE,%d0
    moveq   #UAC2_AS_IFACE,%d1
    cmpl    %d0,%d1
    bnes    1f
    pea     usbaudio_alt
    jmp     GETIFACE_REJOIN
1:
.if USB_IN
    | interface 5 (USB AUDIO IN, EP3 OUT) reports its own unit's alt byte
    moveq   #UAC2_AS_IFACE+1,%d1
    cmpl    %d0,%d1
    bnes    2f
    pea     in_alt
    jmp     GETIFACE_REJOIN
2:
.endif
    pea     GETIFACE_STOCKP
    jmp     GETIFACE_REJOIN

| ---- EP0 buffer-page fix (installed at 0x4001d4b2 inside usb_ep0_send) -------
| usb_ep0_send sets only the dTD's buffer PAGE 0 (0x4ec95028), never PAGE 1.
| A descriptor whose buffer crosses a 4 KB page then transmits only the bytes
| before the boundary and zeros after (seen in his build as the full-speed
| config truncated to the stock 32-byte MSC part). This shim also fills
| PAGE 1 = (buffer & ~0xfff) + 0x1000, so an EP0 send that spans a page
| boundary completes wherever the descriptors are linked.
|
| Displaced: movel %a0@,0x4ec95028 (a0 = &buffer-arg, set by the preceding
| lea %sp@(12),%a0); rejoin at the following lea (0x4001d4b8). %d0 is dead
| across the rejoin (reloaded at 0x4001d4da), so clobbering it is safe.
    .global audio_ep0page_shim
audio_ep0page_shim:
    movel   %a0@,%d0               | the descriptor buffer pointer (arg)
    movel   %d0,0x4ec95028         | dTD buffer page 0 (displaced instruction)
    andil   #0xfffff000,%d0
    addil   #0x1000,%d0
    movel   %d0,0x4ec9502c         | dTD buffer page 1 — the fix
    jmp     0x4001d4b8

| ---- usb_isr shim (installed at 0x4001e606, USB MIDI's site) ---------------
| Retires EP3 IN completions, then chains to USB MIDI's ISR shim, which
| handles EP2 and runs the original displaced instruction.
    .global audio_isr_shim
audio_isr_shim:
    lea     %sp@(-8),%sp
    moveml  %d0-%d1,%sp@            | all this shim touches
    | Exactly ONE place queues packets on EP3: the per-block producer in
    | frame_isr. This shim only retires the completion bit so it cannot go
    | stale; the queue's own state is the ACTIVE bit of each dTD, which the
    | controller clears itself, so there is no bookkeeping to race on. The
    | dTDs are queued WITHOUT IOC — 2000 completion interrupts a second buy
    | nothing when nobody needs to be told.
    movel   EPCOMPLETE,%d0
    movel   #EP3IN_BIT,%d1
    andl    %d1,%d0
    beqs    2f
    movel   #EP3IN_BIT,%d1
    movel   %d1,EPCOMPLETE          | W1C EP3 IN
2:  moveml  %sp@,%d0-%d1
    lea     %sp@(8),%sp
    jmp     usbmidi_isr_shim         | USB MIDI's shim, whose detour this one stands in for

| ---- the iso packet builder -------------------------------------------------
| Each packet holds the next n frames from the ring: n = 11/12 at high speed
| (11025/1000 per packet) or 44/45 at full speed (44100/1000), so the emitted
| stream is an exact, gap-free substring of what the producer wrote. Underrun
| queues nothing (the host's IN gets an empty packet); a producer that laps
| the ring (host stopped draining) resyncs and counts an overrun.
| Runs from the frame shim only; may clobber every register but %sp.
|
| An isochronous IN cannot NAK: an IN token that arrives with nothing primed
| is answered with a zero-length packet, and a hole in the stream is a
| click. The frame ISR keeps up to NSLOT packets queued and the controller
| chains from one to the next on its own.
|
| The slots are used in turn: aud_tail is the next to fill, so fill order is
| tail-3, tail-2, tail-1 (oldest to newest) and the controller retires them
| in that order. A slot whose dTD is still ACTIVE is in flight or queued and
| is left alone.
usbaudio_kick:
    tstb    usbaudio_alt            | alt 0 requested since this block began:
    beq     9f                      | queue nothing more (teardown follows)
    | THE FIRST POLL SETS THE CUSHION. The host polls EP3 IN some time after
    | its SET_INTERFACE (macOS: about 460 frames later, Bryan T's unit, 27
    | Sep 2026), and the producer keeps filling meanwhile, so a cursor set
    | at bring-up starts the stream that much further behind than
    | AUD_TARGET and the servo holds it there. So: bring-up queues NSLOT
    | packets and sets aud_await to 1; this block marks them queued (2);
    | from then on nothing more is built until one of them has RETIRED, the
    | controller's own record of a poll (the ACTIVE bit it clears), and at
    | that block the cursor is re-set to AUD_TARGET behind the producer.
    | The frames between are skipped once, before the host has audio;
    | usbaudio_anchor holds the count.
    mvzb    aud_await,%d0
    cmpil   #2,%d0
    bnes    .Lk_build
    moveq   #0,%d2                  | any slot no longer ACTIVE = a poll happened
.Lk_await:
    movel   %d2,%d0
    bsr     audio_dtd_of
    movel   %a0@(4),%d1
    btst    #7,%d1
    beqs    .Lk_anchor
    addql   #1,%d2
    cmpil   #NSLOT,%d2
    bcss    .Lk_await
    rts                             | all still queued: the host has not polled
.Lk_anchor:
    movel   aud_produced,%d0
    movel   %d0,%d1
    subl    usbaudio_consumed,%d1   | fill now
    subil   #AUD_TARGET,%d1         | beyond the cushion: skipped
    bles    .Lk_anchored            | at or under it already (a prompt host)
    movel   %d1,usbaudio_anchor
    subil   #AUD_TARGET,%d0
    movel   %d0,usbaudio_consumed
.Lk_anchored:
    clrb    aud_await
.Lk_build:
    moveq   #NSLOT,%d0
    movel   %d0,%sp@-               | builds left this block
1:  bsr     audio_pkt_build         | fill the tail slot, if free
    tstl    %d0
    beqs    2f
    subql   #1,%sp@
    bnes    1b
2:  addql   #4,%sp
    mvzb    aud_await,%d0
    cmpil   #1,%d0
    bnes    3f
    moveq   #2,%d0                  | the bring-up's packets are queued
    moveb   %d0,aud_await
3:
    | Self-heal. The add-dTD tripwire (audio_pkt_build) is the documented
    | way to append to a running queue, and its hazard window is reported by
    | the hardware clearing ATDTW. Should anything ever leave an ACTIVE dTD
    | behind with the endpoint idle — a missed hazard, a flush that raced a
    | prime — the stream would otherwise stall until the next alt 0/1. So
    | every block ends with: idle endpoint + queued dTD = prime the oldest,
    | and count it, so a silent recovery is still measurable.
    movel   ENDPTSTAT,%d0
    movel   EPPRIME,%d1
    orl     %d1,%d0
    andil   #EP3IN_BIT,%d0
    bnes    9f                      | primed or priming: running
    mvzb    aud_tail,%d2            | oldest first: fill order from the tail
    bsr     audio_oldest
    tstl    %d0
    beqs    9f                      | nothing queued: idle is correct
    bsr     audio_prime             | %a4 = head dTD
    addql   #1,usbaudio_reprimes
9:  rts

| %d0 = slot index (taken mod NSLOT) -> %a0 = its dTD, through the uncached
| alias. Clobbers d0.
audio_dtd_of:
    andil   #NSLOT-1,%d0
    lsll    #5,%d0
    moveal  #(aud_dtds+UNCACHED),%a0
    addal   %d0,%a0
    rts

| The oldest queued dTD: the first ACTIVE one from slot %d2 onward, in fill
| order. Returns d0 = 1 and %a4 = it, or d0 = 0 when none is ACTIVE.
| Clobbers d0-d3/a0.
audio_oldest:
    moveq   #NSLOT-1,%d3
1:  movel   %d2,%d0
    bsr     audio_dtd_of
    movel   %a0@(4),%d1
    btst    #7,%d1
    bnes    2f
    addql   #1,%d2
    subql   #1,%d3
    bpls    1b
    moveq   #0,%d0
    rts
2:  moveal  %a0,%a4
    moveq   #1,%d0
    rts

| Point the queue head at %a4 and prime EP3 IN — the "list empty" case of the
| Chipidea add-dTD procedure. Clobbers d0/a1.
audio_prime:
    moveal  qh_ep3,%a1
    movel   %a4,%a1@(8)             | dQH next dTD
    clrl    %a1@(12)                | dQH token: ACTIVE/HALT clear before a prime
    movel   #EP3IN_BIT,%d0
    movel   %d0,EPPRIME
    rts

| Build one packet into the tail slot and queue it. Returns d0 = 1 if a packet
| was queued, 0 if the slot was busy or the ring could not fill one.
audio_pkt_build:
    mvzb    aud_tail,%d0
    moveal  %d0,%a6                 | a6 = slot index, kept across the copy
    bsr     audio_dtd_of            | a0 = this slot's dTD
    movel   %a0@(4),%d1
    btst    #7,%d1                  | ACTIVE: in flight or queued
    bne     .Lpb_none
    tstb    usbaudio_alt            | (re-checked per packet: alt 0 can land
    beq     .Lpb_none               |  between two builds in one block)
    movel   aud_produced,%d0
    movel   usbaudio_consumed,%d1
    movel   %d0,%d2
    subl    %d1,%d2                 | d2 = frames available
    cmpil   #AUD_FRAMES,%d2
    blss    3f                      | within the ring: fine
    addql   #1,usbaudio_overruns
    movel   %d0,%d1
    subil   #AUD_FRAMES,%d1
    movel   %d1,usbaudio_consumed   | resync to the ring's trailing edge
    movel   #AUD_FRAMES,%d2
3:  tstb    aud_await               | low and high water since the first poll
    bnes    5f
    cmpl    usbaudio_minfill,%d2
    bccs    4f
    movel   %d2,usbaudio_minfill
4:  cmpl    usbaudio_maxfill,%d2
    blss    5f
    movel   %d2,usbaudio_maxfill
5:  movel   usbaudio_acc,%d3
    | RATE SERVO. The endpoint is ASYNCHRONOUS: the device sends at its own
    | clock and the host adapts. The host's polls run on ITS clock, so a fixed
    | 11.025 frames per poll would drain the ring faster or slower than the
    | producer fills it, by the two clocks' drift, and the ring would under-
    | or overrun within minutes. The servo nudges the drain by +-0.1 frame per
    | packet against a target fill, which is exactly "send what is produced".
    movel   aud_step,%d5            | nominal frames per packet, x1000
    cmpil   #(AUD_TARGET+AUD_BAND),%d2
    bcss    .Lsrv_low
    addil   #SERVO_STEP,%d5
    bras    .Lsrv_done
.Lsrv_low:
    cmpil   #(AUD_TARGET-AUD_BAND),%d2
    bccs    .Lsrv_done
    subil   #SERVO_STEP,%d5
.Lsrv_done:
    addl    %d5,%d3
    movel   #1000,%d7
    movel   %d3,%d4
    divu.l  %d7,%d4                 | d4 = n = (acc+step)/1000
    movel   %d4,%d5
    mulu.l  %d7,%d5
    movel   %d3,%d6
    subl    %d5,%d6                 | d6 = new acc
    cmpl    %d4,%d2
    bccs    .Lhave_frames
    addql   #1,usbaudio_underruns
    bra     .Lpb_none               | available < n: underrun, send nothing
.Lhave_frames:
    movel   %d6,usbaudio_acc
    movel   %d4,usbaudio_lastn
    movel   %d2,usbaudio_lastfill
    | ---- copy n frames into this slot's buffer -----------------------------
    | a3 = the buffer (aud_bufs + slot * 960, through the uncached alias),
    | a1 = write cursor. The ring is copied in at most two straight runs (up
    | to its end, then from its start), with no per-frame index masking.
    movel   %a6,%d0
.if SLOT8_LAYOUT
    lsll    #8,%d0
    lsll    #1,%d0                  | slot * 512 = slot * PKT_BUF
.elseif USB_LAYOUT == LAYOUT_MAIN_CUE
    lsll    #8,%d0
    lsll    #1,%d0                  | slot * 512 = slot * PKT_BUF
.elseif USB_LAYOUT == LAYOUT_TRACKS
    lsll    #8,%d0
    lsll    #2,%d0                  | slot * 1024
    movel   %a6,%d1
    lsll    #8,%d1                  | slot * 256
    subl    %d1,%d0                 | slot * 768 = slot * PKT_MAX_HS
.else
    lsll    #8,%d0
    lsll    #2,%d0                  | slot * 1024
    movel   %a6,%d1
    lsll    #6,%d1                  | slot * 64
    subl    %d1,%d0                 | slot * 960 = slot * PKT_MAX_HS
.endif
    moveal  #(aud_bufs+UNCACHED),%a3
    addal   %d0,%a3
    moveal  %a3,%a1
    movel   %d4,%d3                 | d3 = n
    movel   usbaudio_consumed,%d1
    andil   #AUD_FRAMES-1,%d1       | ring index of the first frame
    movel   #AUD_FRAMES,%d0
    subl    %d1,%d0                 | d0 = frames before the ring wraps (>= 1)
    tstb    aud_hs
    beqs    .Lcopy_fs
    lea     aud_ring,%a2
    MUL_SLOT %d1, %d2               | d2 is dead here (lastfill is stored)
    addal   %d1,%a2                 | a2 = the first frame's slot
    cmpl    %d0,%d3
    bhis    .Lhs_wrap               | n > frames to the end: two runs
    movel   %d3,%d0
.if SLOT8_LAYOUT
    bsr     audio_copy8             | an 8-byte slot, as the full-speed ring's
.elseif USB_LAYOUT == LAYOUT_MAIN_CUE
    bsr     audio_copy16
.elseif USB_LAYOUT == LAYOUT_TRACKS
    bsr     audio_copy64
.else
    bsr     audio_copy80
.endif
    bras    .Lcopied
.Lhs_wrap:
    subl    %d0,%d3
    moveal  %d3,%a5                 | a5 = frames in the second run (the copy
.if SLOT8_LAYOUT
    bsr     audio_copy8
    lea     aud_ring,%a2
    movel   %a5,%d0
    bsr     audio_copy8
.elseif USB_LAYOUT == LAYOUT_MAIN_CUE
    bsr     audio_copy16
    lea     aud_ring,%a2
    movel   %a5,%d0
    bsr     audio_copy16
.elseif USB_LAYOUT == LAYOUT_TRACKS
    bsr     audio_copy64
    lea     aud_ring,%a2
    movel   %a5,%d0
    bsr     audio_copy64
.else
    bsr     audio_copy80            |      clobbers every data register)
    lea     aud_ring,%a2
    movel   %a5,%d0
    bsr     audio_copy80
.endif
    bras    .Lcopied
.Lcopy_fs:
    lea     aud_sum,%a2
    lsll    #3,%d1
    addal   %d1,%a2
    cmpl    %d0,%d3
    bhis    .Lfs_wrap
    movel   %d3,%d0
    bsr     audio_copy8
    bras    .Lcopied
.Lfs_wrap:
    subl    %d0,%d3
    moveal  %d3,%a5
    bsr     audio_copy8
    lea     aud_sum,%a2
    movel   %a5,%d0
    bsr     audio_copy8
.Lcopied:
    movel   usbaudio_lastn,%d4      | n again (the copy clobbered it)
    addl    %d4,usbaudio_consumed
    movel   %d4,%d6
    tstb    aud_hs
    beqs    5f
    MUL_SLOT %d6, %d1               | nbytes = n * 80 (d1 is reloaded below)
    bras    6f
5:  lsll    #3,%d6                  | nbytes = n * 8
6:  | ---- the dTD: buffer pointers first, the ACTIVE token LAST -------------
    | The dTD and the buffer are written through the uncached alias, so these
    | stores reach memory in program order: the controller cannot see an
    | ACTIVE token over a half-built descriptor or a half-copied buffer.
    moveq   #1,%d1
    movel   %d1,%a0@                | next = terminate
    movel   %a3,%a0@(8)             | buffer page 0
    movel   %a3,%d1
    andil   #0xfffff000,%d1
    addil   #0x1000,%d1
    movel   %d1,%a0@(12)            | page 1: a 960-byte buffer can straddle a 4 KB page
    movel   %d6,%d1
    swap    %d1                     | nbytes << 16
    oril    #0x80,%d1               | ACTIVE (no IOC: completions buy nothing)
    movel   %d1,%a0@(4)
    | ---- queue it: the Chipidea "add dTD" procedure -------------------------
    | Case 1, list empty (the previous slot in fill order is not ACTIVE, so
    | nothing older is either): point the queue head at this dTD and prime.
    | Case 2, list running: link this dTD after the previous one, then the
    | tripwire — set ATDTW, sample ENDPTSTAT, trust the sample only if ATDTW
    | is still set (hardware clears it when the sample fell in its hazard
    | window). Still primed: the controller follows the link by itself. Not
    | primed: it retired the previous dTD before it saw the link, so the HEAD
    | to prime is the oldest dTD still ACTIVE (never skip a queued packet),
    | which is this one if every other has retired.
    moveal  %a0,%a4                 | a4 = the head to prime, if it comes to that
    moveal  %a0,%a5                 | a5 = this dTD (audio_dtd_of returns in a0)
    movel   %a6,%d0
    subql   #1,%d0
    bsr     audio_dtd_of
    moveal  %a0,%a2                 | a2 = the previous slot's dTD
    moveal  %a5,%a0
    movel   %a2@(4),%d0
    btst    #7,%d0
    beqs    .Lenq_prime             | case 1
    movel   %a0,%a2@                | case 2: previous.next = this
    movel   EPPRIME,%d0
    andil   #EP3IN_BIT,%d0
    bnes    .Lenq_done              | a prime is pending: it will read the list
    moveq   #16,%d2                 | tripwire attempts (bounded: this is an ISR)
.Lenq_trip:
    movel   USBCMD,%d0
    oril    #ATDTW,%d0
    movel   %d0,USBCMD
    movel   ENDPTSTAT,%d1
    andil   #EP3IN_BIT,%d1          | the sample
    movel   USBCMD,%d0
    andil   #ATDTW,%d0
    bnes    .Lenq_sampled
    subql   #1,%d2
    bnes    .Lenq_trip              | hazard: the sample is void, take another
    bras    .Lenq_done              | never settled: assume running; the
.Lenq_sampled:                      | self-heal re-primes next block if not
    movel   USBCMD,%d0
    andil   #0xffffbfff,%d0         | ~ATDTW
    movel   %d0,USBCMD
    tstl    %d1
    bnes    .Lenq_done              | still running: it will follow the link
    movel   %a6,%d2
    addql   #1,%d2                  | oldest first: tail+1 .. tail in fill order
    bsr     audio_oldest            | a4 = the oldest ACTIVE (this one at worst)
.Lenq_prime:
    bsr     audio_prime
.Lenq_done:
    movel   %a6,%d0
    addql   #1,%d0
    andil   #NSLOT-1,%d0
    moveb   %d0,aud_tail            | the next slot fills next
    moveq   #1,%d0
    rts
.Lpb_none:
    moveq   #0,%d0
    rts

.if USB_LAYOUT == LAYOUT_TRACKS
| Copy d0 (>= 1) 64-byte frames from %a2 to %a1, both advanced: two moveml
| pairs per frame. Clobbers d1-d7/a4.
audio_copy64:
1:  moveml  %a2@,%d1-%d7/%a4
    moveml  %d1-%d7/%a4,%a1@
    moveml  %a2@(32),%d1-%d7/%a4
    moveml  %d1-%d7/%a4,%a1@(32)
    lea     %a2@(64),%a2
    lea     %a1@(64),%a1
    subql   #1,%d0
    bnes    1b
    rts
.elseif USB_LAYOUT == LAYOUT_TRACKS_MAIN_CUE
| Copy d0 (>= 1) 80-byte frames from %a2 to %a1, both advanced: three moveml
| pairs per frame. Clobbers d1-d7/a4.
audio_copy80:
1:  moveml  %a2@,%d1-%d7/%a4
    moveml  %d1-%d7/%a4,%a1@
    moveml  %a2@(32),%d1-%d7/%a4
    moveml  %d1-%d7/%a4,%a1@(32)
    moveml  %a2@(64),%d1-%d4
    moveml  %d1-%d4,%a1@(64)
    lea     %a2@(80),%a2
    lea     %a1@(80),%a1
    subql   #1,%d0
    bnes    1b
    rts
.elseif USB_LAYOUT == LAYOUT_MAIN_CUE
| Copy d0 (>= 1) 16-byte frames from %a2 to %a1, both advanced: one moveml
| quad per frame. Clobbers d1-d4.
audio_copy16:
1:  moveml  %a2@,%d1-%d4
    moveml  %d1-%d4,%a1@
    lea     %a2@(16),%a2
    lea     %a1@(16),%a1
    subql   #1,%d0
    bnes    1b
    rts
.endif

| Copy d0 (>= 1) 8-byte stereo-sum frames from %a2 to %a1, both advanced.
audio_copy8:
1:  movel   %a2@+,%a1@+
    movel   %a2@+,%a1@+
    subql   #1,%d0
    bnes    1b
    rts

| Mark the queue idle: zero every dTD (ACTIVE clear, next = terminate) and
| start filling at slot 0. Written through the uncached alias, so no cpushl.
| Clobbers d0/d1/a1.
audio_dtds_clear:
    moveal  #(aud_dtds+UNCACHED),%a1
    moveq   #NSLOT*8-1,%d1
1:  clrl    %a1@+
    subql   #1,%d1
    bpls    1b
    moveal  #(aud_dtds+UNCACHED),%a1
    moveq   #1,%d0
    moveq   #NSLOT-1,%d1
2:  movel   %d0,%a1@                | next = terminate
    lea     %a1@(32),%a1
    subql   #1,%d1
    bpls    2b
    clrb    aud_tail
    rts

| Resolve EP3's queue head from ENDPTLISTADDR. Returns it in %a0 and caches it
| in qh_ep3. The firmware programs 0x4EC94800 here; a value outside SDRAM is
| not an endpoint list, and the known constant is used instead.
audio_qh_resolve:
    movel   EPLISTADDR,%d0
    andil   #0xfffff800,%d0
    cmpil   #0x40000000,%d0
    blts    .Lqh_fallback
    cmpil   #0x50000000,%d0
    bges    .Lqh_fallback
    bras    .Lqh_have
.Lqh_fallback:
    movel   #(QH_EP3IN - QH_EP3IN_OFF),%d0
.Lqh_have:
    addil   #QH_EP3IN_OFF,%d0
    movel   %d0,qh_ep3
    moveal  %d0,%a0
    rts

| ---- EP3 bring-up / teardown: frame-ISR context ONLY ------------------------
| The SET_INTERFACE shim records the host's request in usbaudio_alt; the frame
| shim compares it with aud_running once per block and calls one of these.
| Everything EP3 — queue head, dTDs, ENDPTCTRL3, ring cursors — is owned by
| that one context, so nothing here can interleave with a kick.
audio_ep3_up:
    | FLUSH FIRST. A dTD left primed by an earlier session must not be in
    | flight while the queue head is rewritten underneath it.
    bsr     audio_ep3_flush
    | ZERO THE WHOLE 64-BYTE dQH. EP3's queue head sits past anything the
    | stock firmware ever initializes, so on hardware its TOKEN (+0x0C) and
    | buffer pointers (+0x10..+0x1C) hold power-on garbage. The device
    | controller is a real bus master on silicon: it acts on that token's
    | ACTIVE bit and those pointers, then writes transfer status back through
    | them — an arbitrary memory write, which lands wherever the garbage
    | points (image code included). The firmware's own EP0 setup at
    | 0x4001d656 clears the token for exactly this reason; clearing the whole
    | structure is the safe superset.
    bsr     audio_qh_resolve        | %a0 = EP3 dQH, from the controller
    moveq   #15,%d1
1:  clrl    %a0@+
    subql   #1,%d1
    bpls    1b
    moveal  qh_ep3,%a0              | resolved just above
    | The SPEED decides the stream: 20 channels in <= 960 B packets every
    | 250 us at high speed, the stereo sum in <= 360 B packets every 1 ms at
    | full speed. PORTSC1 bits 27:26 are the negotiated speed (2 = high); the
    | responder picks the config descriptor by the same bits, so the format
    | the host was told and the packets it gets cannot disagree.
    movel   PORTSC1,%d0
    lsrl    #8,%d0
    lsrl    #8,%d0
    lsrl    #8,%d0
    lsrl    #2,%d0
    andil   #3,%d0
    cmpil   #2,%d0
    bnes    .Lspeed_fs
    moveq   #1,%d0
    moveb   %d0,aud_hs
    movel   #STEP_HS,%d0
    movel   %d0,aud_step
    movel   #(0x60000000+(PKT_MAX_HS<<16)),%d0  | dQH cap: Mult 1, ZLT off, maxpkt 960
    bras    .Lspeed_set
.Lspeed_fs:
    clrb    aud_hs
    movel   #STEP_FS,%d0
    movel   %d0,aud_step
    movel   #(0x60000000+(PKT_MAX_FS<<16)),%d0  | Mult 1, ZLT off, maxpkt 360
.Lspeed_set:
    movel   %d0,%a0@
    clrl    %a0@(4)                 | current dTD
    moveq   #1,%d0
    movel   %d0,%a0@(8)             | no dTD primed yet (terminate)
    clrl    %a0@(12)                | TOKEN — the field the firmware clears
    bsr     audio_dtds_clear        | every queue slot idle
    movel   ENDPTCTRL3,%d0          | ENDPTCTRL3: TXE + isochronous (the bench
    andil   #0x0000ffff,%d0         | reads the type to serve one dTD per poll);
    oril    #0x00840000,%d0         | the TX half only -- the RX half is EP3 OUT
    movel   %d0,ENDPTCTRL3          | (USB AUDIO IN), which must survive this
    movel   aud_produced,%d0
    subil   #AUD_TARGET,%d0         | start a full cushion BEHIND the producer:
    bccs    .Lcons_ok               | the ring is already full, so there is no
    moveq   #0,%d0                  | priming gap and no startup underruns
.Lcons_ok:
    movel   %d0,usbaudio_consumed
    clrl    usbaudio_acc
    moveq   #1,%d0
    moveb   %d0,aud_running
    moveb   %d0,aud_await           | 1: queue, then wait for the host's first poll
    movel   #0x7fffffff,%d0
    movel   %d0,usbaudio_minfill
    clrl    usbaudio_maxfill
    clrl    usbaudio_anchor
    rts

audio_ep3_down:
    | FLUSH the endpoint. Clearing ENDPTCTRL3 disables it but does NOT cancel
    | a dTD that is already primed, so a packet queued microseconds before
    | alt 0 would still go out and the host would see audio after teardown.
    bsr     audio_ep3_flush
    movel   ENDPTCTRL3,%d0          | TX half off; the RX half (EP3 OUT, USB
    andil   #0x0000ffff,%d0         | AUDIO IN) stays as it was. d0 is free
    movel   %d0,ENDPTCTRL3          | here: the flush above clobbered it
    bsr     audio_dtds_clear        | a flushed dTD still reads ACTIVE
    clrb    aud_running
    rts

| Flush EP3 IN and wait for it. The documented Chipidea sequence, not a
| single write: a prime that lands while a flush is in progress survives it,
| so after ENDPTFLUSH clears, ENDPTSTAT is checked and the flush repeated
| while the endpoint still shows primed. Bounded, because this runs in the
| frame ISR and a controller that never answers must not wedge the machine.
| Clobbers d0/d1.
audio_ep3_flush:
    moveq   #16,%d1                 | attempts
1:  movel   #EP3IN_BIT,%d0
    movel   %d0,EPFLUSH
2:  movel   EPFLUSH,%d0             | complete when the bit clears
    andil   #EP3IN_BIT,%d0
    bnes    2b
    movel   ENDPTSTAT,%d0
    andil   #EP3IN_BIT,%d0
    beqs    3f                      | idle: done
    subql   #1,%d1
    bnes    1b
3:  rts

| ---- the per-block producer (installed at 0x4000d9a0, inside frame_isr) ----
| frame_isr runs once per 16-frame block: the block clock, the audio and the
| trigger to send are all firmware events.
|
| The hook site is the LAST instruction before frame_isr's
| `moveml %sp@,%d0-%fp` epilogue, so every register is about to be reloaded
| from the stack — this shim may clobber d0-a6 freely. It must not touch %sp.
|
| Displaced: clrl 0x46104d4e (6 bytes), rejoin 0x4000d9a6.

| d -> saturated to 24 bits (-2^23 .. 2^23-1). Inline, used only for the
| stereo sum (two per frame). The bounds live in %a5 (0x7fffff) and %a6
| (-0x800000), loaded once per block.
.macro SAT24 d
    cmpl    %a5,\d
    jble    .Lsat_lo\@              | jbcc: gas picks the shortest branch
    movel   %a5,\d
    jbra    .Lsat_ok\@
.Lsat_lo\@:
    cmpl    %a6,\d
    jbge    .Lsat_ok\@
    movel   %a6,\d
.Lsat_ok\@:
.endm

    .global audio_frame_shim
audio_frame_shim:
    | The producer runs whether or not the host has opened the stream, so the
    | ring is full at alt 1 and the stream starts with no underruns (his build
    | idled until alt 1: 127 underruns at startup on hardware). aud_running
    | gates the sending, not the producing.
.if USB_LAYOUT == LAYOUT_MASTER
    | ---- two channels: track 8's (L,R), one 8-byte slot per frame -----------
    | The same read-back words as the twenty-channel build's channels 15/16,
    | the same format (top 24 bits, byte-reversed). Both speeds send this
    | ring, so there is no per-block speed test and no sum.
    movel   RB_PREV,%d0
    movel   %d0,%d2
    cmpl    usbaudio_lastbank,%d2
    bnes    .Lt8_bank_ok
    addql   #1,usbaudio_bankdup
.Lt8_bank_ok:
    movel   %d2,usbaudio_lastbank
    lsll    #8,%d0
    lsll    #2,%d0                  | prev * 1024
    addil   #(RB_BASE+(RB_TRACKS-1)*128),%d0
    moveal  %d0,%a2                 | a2 = this bank's track 8, frame 0
    movel   aud_produced,%d4
    movel   %d4,%d5
    andil   #AUD_FRAMES-1,%d5
    lsll    #3,%d5
    lea     aud_ring,%a3
    addal   %d5,%a3                 | a3 = the slot cursor (a block never wraps)
    moveq   #15,%d6                 | 16 frames
1:  movel   %a2@+,%d2               | T8 L
    clrb    %d2
    byterev %d2
    movel   %d2,%a3@+
    movel   %a2@+,%d2               | T8 R
    clrb    %d2
    byterev %d2
    movel   %d2,%a3@+
    subql   #1,%d6
    bpls    1b
    addql   #8,%d4
    addql   #8,%d4                  | 16 frames produced
    movel   %d4,aud_produced
.elseif USB_LAYOUT == LAYOUT_MAIN
    | ---- two channels: MAIN L/R, one 8-byte slot per frame ------------------
    | MAIN_CUE_BASE is not ping-ponged (ch6 overwrites it in place every
    | frame): no bank bookkeeping. Both speeds send this ring, so there is no
    | per-block speed test and no sum.
    movel   aud_produced,%d4
    movel   %d4,%d5
    andil   #AUD_FRAMES-1,%d5
    lsll    #3,%d5                  | slot * SLOT_BYTES (8)
    lea     aud_ring,%a3
    addal   %d5,%a3                 | a3 = the slot cursor (a block never wraps)
    lea     MAIN_CUE_BASE+MAIN_CUE_MAIN_OFF,%a2   | frame 0's MAIN (L,R), 8 B a frame
    moveq   #15,%d6                 | 16 frames
1:  movel   %a2@+,%d2               | MAIN L
    clrb    %d2
    byterev %d2
    movel   %d2,%a3@+
    movel   %a2@+,%d2               | MAIN R
    clrb    %d2
    byterev %d2
    movel   %d2,%a3@+
    subql   #1,%d6
    bpls    1b
    addql   #8,%d4
    addql   #8,%d4                  | 16 frames produced
    movel   %d4,aud_produced
.elseif USB_LAYOUT == LAYOUT_MAIN_CUE
    | ---- four channels: MAIN L/R + CUE L/R, one 16-byte slot per frame ----
    | MAIN_CUE_BASE is not ping-ponged (ch6 overwrites it in place every frame), so
    | there is no bank/ping-pong bookkeeping here, unlike the tracks' arena.
    | High speed always writes the 16-byte ring; full speed ALSO writes MAIN
    | alone into aud_sum (the same two-channel shape every layout sends at
    | full speed), skipped at high speed exactly like OUT TRACKS MAIN CUE's and OUT TRACKS's sum.
    moveq   #0,%d1
    movel   PORTSC1,%d0
    andil   #0x0c000000,%d0
    cmpil   #0x08000000,%d0
    seq     %d1                     | d1 = 0xff at high speed
    moveal  %d1,%a1                 | a1 != 0: skip the MAIN-only ring this block
    movel   aud_produced,%d4
    movel   %d4,%d5
    andil   #AUD_FRAMES-1,%d5
    MUL_SLOT %d5, %d0               | d0 is dead here; d5 -> slot * SLOT_BYTES (16)
    lea     aud_ring,%a3
    addal   %d5,%a3                 | a3 = the 16-byte slot cursor (a block
                                    | never wraps: 16 divides the ring size)
    movel   %d4,%d5
    andil   #AUD_FRAMES-1,%d5
    lsll    #3,%d5                  | slot * SUM_BYTES (8)
    lea     aud_sum,%a4
    addal   %d5,%a4                 | a4 = the MAIN-only cursor
    moveq   #15,%d6                 | 16 frames
1:
    | Frame f's pair sits at MAIN_CUE_BASE + f*8 (+MAIN_CUE_CUE_OFF for CUE); f = 15 - d6.
    moveq   #15,%d7
    subl    %d6,%d7
    lsll    #3,%d7                  | f * 8
    lea     MAIN_CUE_BASE,%a0
    addal   %d7,%a0
    movel   %a0@(MAIN_CUE_MAIN_OFF),%d3   | MAIN L, kept for the full-speed ring
    clrb    %d3
    byterev %d3
    movel   %d3,%a3@+
    movel   %a0@(MAIN_CUE_MAIN_OFF+4),%d2 | MAIN R
    clrb    %d2
    byterev %d2
    movel   %d2,%a3@+
    movel   %a1,%d0
    bne     .Lmc_sum_skip
    movel   %d3,%a4@+               | MAIN L, full speed
    movel   %d2,%a4@+               | MAIN R, full speed
.Lmc_sum_skip:
    movel   %a0@(MAIN_CUE_CUE_OFF),%d2    | CUE L
    clrb    %d2
    byterev %d2
    movel   %d2,%a3@+
    movel   %a0@(MAIN_CUE_CUE_OFF+4),%d2  | CUE R
    clrb    %d2
    byterev %d2
    movel   %d2,%a3@+
    subql   #1,%d6
    bpl     1b
    addql   #8,%d4
    addql   #8,%d4                  | 16 frames produced
    movel   %d4,aud_produced
.else
audio_frame_shim_body:
    | The stereo sum is only SENT at full speed; at high speed (PORTSC1 bits
    | 27:26 = 2) its store is skipped. Decided per block from the PORT, not
    | from aud_hs, so a re-enumeration at full speed refills the sum ring long
    | before the host can select alt 1 (enumeration alone takes >100 ms; the
    | ring holds 23 ms).
    moveq   #0,%d1
    movel   PORTSC1,%d0
    andil   #0x0c000000,%d0
    cmpil   #0x08000000,%d0
    seq     %d1                     | d1 = 0xff at high speed
    moveal  %d1,%a1                 | a1 != 0: skip the sum this block
    movel   RB_PREV,%d0
    | bankdup counts blocks where the ping-pong bank did not alternate (the
    | producer would then read one bank twice or skip one).
    movel   %d0,%d2
    cmpl    usbaudio_lastbank,%d2
    bnes    .Lbank_ok
    addql   #1,usbaudio_bankdup
.Lbank_ok:
    movel   %d2,usbaudio_lastbank
    lsll    #8,%d0
    lsll    #2,%d0                  | prev * 1024 (imm shift is 1-8)
    addil   #RB_BASE,%d0
    moveal  %d0,%a2                 | a2 = this bank's track 0, frame 0
    movel   aud_produced,%d4
    movel   %d4,%d5
    andil   #AUD_FRAMES-1,%d5
    movel   %d5,%d0
    MUL_SLOT %d0, %d2               | d2 is dead here (lastbank is stored)
    lea     aud_ring,%a3
    addal   %d0,%a3                 | a3 = 20-channel slot cursor (a block never
                                    | wraps: 16 divides the ring size)
    lsll    #3,%d5
    lea     aud_sum,%a4
    addal   %d5,%a4                 | a4 = stereo-sum cursor
    moveq   #SUM_SHIFT,%d1          | asr.l immediate is 1-8 only: shift via d1
    moveal  #0x7fffff,%a5           | SAT24 bounds
    moveal  #-0x800000,%a6
    moveq   #15,%d6                 | 16 frames
1:
    | ---- the eight tracks, one stereo pair each, plus their sum -----------
    | Per frame: track t's L,R (32-bit, post-FX, pre-fader) with the low byte
    | cleared -- 24 bits, left-justified in the subslot, no saturation needed
    | -- then BYTEREV (ISA_C) to little-endian, one
    | longword store each, at slot + t*8. The same words >> 8 accumulate into
    | the stereo sum in 24-bit units (d5 = L, d3 = R; eight tracks fit in 27
    | bits), which is what the full-speed stream carries.
    moveal  %a2,%a0                 | track 0, this frame
    moveq   #0,%d5                  | L sum
    moveq   #0,%d3                  | R sum
    moveq   #RB_TRACKS-1,%d7
2:  movel   %a0@,%d2                | track L
    movel   %d2,%d0
    asrl    %d1,%d0
    addl    %d0,%d5
    clrb    %d2                     | the top 24 bits
    byterev %d2
    movel   %d2,%a3@+
    movel   %a0@(4),%d2             | track R
    movel   %d2,%d0
    asrl    %d1,%d0
    addl    %d0,%d3
    clrb    %d2
    byterev %d2
    movel   %d2,%a3@+
    lea     %a0@(128),%a0           | next track, same frame
    subql   #1,%d7
    bpl     2b
.if USB_LAYOUT == LAYOUT_TRACKS_MAIN_CUE
    | ---- MAIN and CUE, channels 17-20: the same word format, top 24 bits --
    | Frame f's pair sits at MAIN_CUE_BASE + f*8 (+MAIN_CUE_CUE_OFF for CUE);
    | f = 15 - d6. It goes into the slot MAIN_CUE_LAG_BLOCKS blocks behind
    | this frame's (see the constant): slot (d4 + f - 16*LAG) & (AUD_FRAMES-1),
    | at +64 past its sixteen track words. a0, d0, d7 are free until the next
    | frame reloads them; d1 (the sum shift) is borrowed and restored; CUE R
    | is parked on the stack while d7 does the slot arithmetic.
    moveq   #15,%d7
    subl    %d6,%d7                 | f
    lsll    #3,%d7                  | f * 8
    lea     MAIN_CUE_BASE,%a0
    addal   %d7,%a0                 | a0 = this frame's MAIN (L,R); CUE at +MAIN_CUE_CUE_OFF
    movel   %a0@(MAIN_CUE_MAIN_OFF),%d0   | MAIN L
    movel   %a0@(MAIN_CUE_MAIN_OFF+4),%d1 | MAIN R
    movel   %a0@(MAIN_CUE_CUE_OFF),%d2    | CUE L
    movel   %a0@(MAIN_CUE_CUE_OFF+4),%d7  | CUE R
    movel   %d7,%sp@-
    moveq   #15,%d7
    subl    %d6,%d7                 | f again
    addl    %d4,%d7                 | this frame's index
    subil   #16*MAIN_CUE_LAG_BLOCKS,%d7
    andil   #AUD_FRAMES-1,%d7       | the slot MAIN_CUE_LAG_BLOCKS blocks back, wrapped
    lsll    #4,%d7                  | slot * 16
    lea     aud_ring+64,%a0         | + the track words' 64 B
    lea     %a0@(0,%d7:l:4),%a0     | + slot * 64
    addal   %d7,%a0                 | + slot * 16 = slot * 80
    clrb    %d0
    byterev %d0
    movel   %d0,%a0@+               | MAIN L
    clrb    %d1
    byterev %d1
    movel   %d1,%a0@+               | MAIN R
    clrb    %d2
    byterev %d2
    movel   %d2,%a0@+               | CUE L
    movel   %sp@+,%d2
    clrb    %d2
    byterev %d2
    movel   %d2,%a0@                | CUE R
    lea     %a3@(16),%a3            | this slot's MAIN/CUE field: the next block writes it
    moveq   #SUM_SHIFT,%d1          | the sum shift, borrowed above
.endif
    movel   %d5,%d2                 | the stereo sum, L
    movel   %a1,%d0
    bne     .Lsum_skip              | high speed: the sum ring is not sent
    | ---- the stereo sum: saturate, left-justify, store little-endian --------
    SAT24   %d2
    | srcjump counts steps in the summed L sample larger than 800 << 8 (his
    | threshold, 800 in 16-bit units) at production, before USB.
    movel   usbaudio_lastsamp,%d0
    subl    %d2,%d0
    bpls    .Lsj_abs
    negl    %d0
.Lsj_abs:
    cmpil   #(800<<8),%d0
    bcss    .Lsj_done
    addql   #1,usbaudio_srcjump
.Lsj_done:
    movel   %d2,usbaudio_lastsamp
    movel   %d2,%d0
    lsll    #8,%d0
    byterev %d0
    movel   %d0,%a4@+               | sum L
    movel   %d3,%d0
    SAT24   %d0
    lsll    #8,%d0
    byterev %d0
    movel   %d0,%a4@+               | sum R
.Lsum_skip:
    lea     %a2@(8),%a2             | next frame
    subql   #1,%d6
    bpl     1b                      | not bpls: the loop body is long
    addql   #8,%d4
    addql   #8,%d4                  | 16 frames produced
    movel   %d4,aud_produced
.endif
    | ---- EP3, owned by this context alone ---------------------------------
    | usbaudio_alt is what the host asked for (SET_INTERFACE); aud_running is
    | what EP3 currently is. Bring it up or down when they differ, and when
    | it is up the block clock IS the send clock: top the queue up now.
    mvzb    usbaudio_alt,%d0
    mvzb    aud_running,%d1
    cmpl    %d0,%d1
    beqs    .Lep3_same
    tstl    %d0
    beqs    .Lep3_down
    bsr     audio_ep3_up
    bras    .Lep3_kick
.Lep3_down:
    bsr     audio_ep3_down
    bras    9f
.Lep3_same:
    tstl    %d1
    beqs    9f                      | nobody listening: produce, but do not send
.Lep3_kick:
    bsr     usbaudio_kick
9:  clrl    0x46104d4e              | displaced
    jmp     0x4000d9a6

| ---- UAC2 class-request shim (installed at 0x4001de64) ----------------------
| Displaced: movel 0xfc0b01c0,%d0 — the first instruction of the stock
| "unknown request: STALL EP0" tail, which every request the dispatcher does
| not recognise falls into. A UAC2 host asks the CLOCK SOURCE for its sample
| rate before it will publish a device (RANGE + CUR of CS_SAM_FREQ_CONTROL,
| CUR of CS_CLOCK_VALID_CONTROL, all class GET to the AudioControl interface
| with the entity id in wIndex's high byte), and a STALL there means no
| audio device. Everything else falls through to the stock STALL, which is
| the legal answer for a control we do not implement.
|
| Reply the way the stock string-descriptor path does: push the buffer and
| min(wLength, len) and jump to the shared usb_ep0_send tail. d2 still holds
| wLength here (nothing between the dispatcher and the stall touches it). The
| reply buffers are constants in this unit's data: the EP0 send DMAs them
| straight out of memory.
    .global audio_ctrl_shim
audio_ctrl_shim:
    mvzb    SETUP_BMREQ,%d0
    | A vendor GET (bmRequestType 0xc0, bRequest 0x55) reads the
    | fifteen counters below back over EP0 as 60 big-endian bytes, so a
    | host -- the port's bench, or tools/hw/usb_counters.py on a unit --
    | can watch underruns, overruns and the bank-duplicate count during a
    | stream. Any driver a host attached to the interfaces is bypassed: a
    | device-recipient control request needs no interface claim.
    cmpil   #0xc0,%d0
    bnes    .Lctrl_class
    mvzb    SETUP_BREQ,%d0
    cmpil   #0x55,%d0
    bne     .Lctrl_stock
    pea     usbaudio_consumed
    moveq   #60,%d0
    bra     .Lctrl_send
.Lctrl_class:
    cmpil   #0xa1,%d0               | class GET, interface recipient
    bne     .Lctrl_stock
    mvzb    SETUP_IFACE,%d0
    cmpil   #UAC2_AC_IFACE,%d0      | the audio function's AudioControl
    bne     .Lctrl_stock
    mvzb    SETUP_WIDXH,%d0
    cmpil   #UAC2_CLOCK_ID,%d0      | the clock source entity
    bne     .Lctrl_stock
    mvzb    SETUP_WVALH,%d0         | control selector
    mvzb    SETUP_BREQ,%d1          | 1 = CUR, 2 = RANGE
    cmpil   #1,%d0                  | CS_SAM_FREQ_CONTROL
    beqs    .Lctrl_freq
    cmpil   #2,%d0                  | CS_CLOCK_VALID_CONTROL
    bne     .Lctrl_stock
    cmpil   #1,%d1
    bne     .Lctrl_stock            | only CUR exists for validity
    pea     uac2_clock_valid
    moveq   #1,%d0
    bras    .Lctrl_send
.Lctrl_freq:
    cmpil   #1,%d1
    bnes    .Lctrl_freq_range
    pea     uac2_freq_cur
    moveq   #4,%d0
    bras    .Lctrl_send
.Lctrl_freq_range:
    cmpil   #2,%d1
    bne     .Lctrl_stock
    pea     uac2_freq_range
    moveq   #14,%d0
.Lctrl_send:
    cmpl    %d2,%d0                 | min(wLength, len)
    blss    1f
    movel   %d2,%d0
1:  movel   %d0,%sp@-
    jmp     EP0_SEND_TAIL
.Lctrl_stock:
    movel   0xfc0b01c0,%d0          | displaced
    jmp     CTRL_STOCK

    .data
| UAC2 clock-source replies, little-endian on the wire (his; constant, the
| EP0 send DMAs them straight out of this unit).
    .balign 4
uac2_freq_cur:   .byte 0x44,0xac,0x00,0x00          | 44100
uac2_freq_range: .byte 0x01,0x00                    | wNumSubRanges = 1
                 .byte 0x44,0xac,0x00,0x00          | dMIN 44100
                 .byte 0x44,0xac,0x00,0x00          | dMAX 44100
                 .byte 0x00,0x00,0x00,0x00          | dRES 0
uac2_clock_valid: .byte 0x01

| ---- state -------------------------------------------------------------------
    .balign 4
    .global usbaudio_consumed, usbaudio_acc, usbaudio_overruns
    .global usbaudio_underruns, usbaudio_lastn, usbaudio_lastfill
    .global usbaudio_lastbank, usbaudio_bankdup, usbaudio_srcjump
    .global usbaudio_reprimes, usbaudio_minfill, usbaudio_maxfill, usbaudio_anchor
| The fifteen longs from usbaudio_consumed to aud_produced are what the
| vendor request 0xc0/0x55 returns, in this order.
usbaudio_consumed: .long 0          | frames pulled from the ring
usbaudio_acc:      .long 0          | frames-per-packet accumulator (x1000)
usbaudio_overruns: .long 0
usbaudio_underruns: .long 0    | packets we could not fill
usbaudio_lastn:    .long 0    | frames in the most recent packet
usbaudio_lastfill: .long 0    | ring fill at the most recent packet
usbaudio_lastbank: .long -1   | previous ping-pong bank
usbaudio_bankdup:  .long 0    | blocks where the bank did NOT alternate
usbaudio_lastsamp: .long 0    | previous summed L sample
usbaudio_srcjump:  .long 0    | discontinuities present at production
usbaudio_reprimes: .long 0    | idle endpoint found holding a queued dTD
usbaudio_minfill:  .long 0    | lowest fill at a packet build since the first poll
usbaudio_maxfill:  .long 0    | highest
usbaudio_anchor:   .long 0    | frames skipped at the host's first poll (this open)
aud_produced:      .long 0          | producer frame count
qh_ep3:            .long 0          | EP3 IN dQH, read from ENDPTLISTADDR
aud_step:          .long STEP_HS    | frames per packet x1000, set by the speed
.if SLOT8_LAYOUT
aud_ring:          .space AUD_FRAMES*SLOT_BYTES  | 1024 x (L,R): T8's, or MAIN's; 24 in 4 B LE
    .set aud_sum, aud_ring                       | the full-speed stream sends the same ring
.else
aud_ring:          .space AUD_FRAMES*SLOT_BYTES  | 1024 x 20 ch (16 OUT TRACKS, 4 OUT MAIN CUE), 24 in 4 B LE
aud_sum:           .space AUD_FRAMES*SUM_BYTES   | 1024 x stereo sum (MAIN alone in OUT MAIN CUE), 24 in 4 B LE
.endif
usbaudio_alt:      .byte 0          | alt setting the host asked for
aud_running:       .byte 0          | EP3 is up (frame-ISR owned)
aud_await:         .byte 0          | 1 = queue for the first poll, 2 = queued, 0 = anchored
aud_hs:            .byte 0          | 1 = high speed (20 ch), 0 = full (sum)
aud_tail:          .byte 0          | next dTD slot to fill (0..NSLOT-1)

| Everything the USB controller reads by DMA is read and written by the
| CPU ONLY through the uncached alias (address + UNCACHED). The unit runs
| from SDRAM that ACR0 maps cacheable copyback, and the controller is a bus
| master that does not snoop the CPU's data cache -- so a dTD written through
| its cached address can still be dirty in cache when the controller fetches
| it, and the controller then reads whatever RAM held before. That presented
| on hardware as ENDPTPRIME clearing (the prime was consumed) while ENDPTSTAT
| never armed (the descriptor it found was not ACTIVE); per-line cpushl did
| NOT fix it, in either form; uncached structures did (his build's window at
| 0x4ec94a00 is itself an alias address). The loader writes this
| unit through the same alias and no code names these two arrays by their
| cached addresses, so nothing allocates a cache line for them (inferred
| from the access paths, not measured). dTDs are
| 32-byte aligned (the dQH and dTD next pointers keep bits 31:5 only).
    .balign 32
aud_dtds:          .space NSLOT*32               | EP3 IN dTDs, one per queue slot
aud_bufs:          .space NSLOT*PKT_BUF          | their packets (<= 960 B; 768 OUT TRACKS, 360 OUT MASTER, 192 OUT MAIN CUE)

    .balign 4
