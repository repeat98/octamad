| usbcrossbar.s -- USB CROSSBAR: the USB controller served first on the crossbar.
|
| MCF54455RM ch. 10 (USB), 14 (SCM), 15 (XBS). In device mode the controller
| has one 16-byte RX FIFO (10.4.3), about 270 ns of slack at 480 Mbit/s. SCM
| BCR, which lets it burst to and from the crossbar's slaves, resets to 0 and
| neither the OS nor the bootloader sets it (the unit read 0), so the FIFO
| was emptied one beat at a time and lost packet tails under a busy project:
| the controller reports that as a transaction error. Measured by Bryan T on
| his MKII (26 Sep 2026, one minute each, the same busy session): BCR 0 =
| 1,189 bad isochronous OUT packets, BCR 0x3ff = 5-11, BCR 0x3ff + USB first
| on the SDRAM and SRAM-backdoor slaves under fixed priority = 0 in ten
| minutes, with no audible or UI change. Ruled out on the way: the cable,
| USBMODE.SDIS, RXPBURST 1-8, buffers in SRAM alone, a smaller IN stream.
|
| Written once, at the stock USB controller init (0x4001e030, before the
| controller runs), and left on: stock's own USB traffic is bulk and
| retried, and never relied on the reset values. The XBS PRS registers
| bus-error on any value giving two masters one level, so each is written
| whole; PRS before CRS (inert while the port still round-robins).
| Not measured: CAPTURE and card writes under this priority on a MKI
| (nordseele, 27 Sep 2026).
| SPDX-License-Identifier: MIT

.set SCM_BCR,     0xfc040024
.set BCR_ON,      0x000003ff        | GBR + GBW + all slaves burst-enabled
.set XBS_PRS2,    0xfc004200        | slave 2: SDRAM
.set XBS_CRS2,    0xfc004210
.set XBS_PRS4,    0xfc004400        | slave 4: the SRAM backdoor
.set XBS_CRS4,    0xfc004410
.set PRS_USB1ST,  0x60504321        | M6 USB 0, M0 core 1, M1 eDMA 2, M2 3, M3 4, M5 5, M7 6
                                    | (stock 0x65403210: USB at level 6 of 7)
.set CRS_FIXED,   0x00000010        | ARB fixed, park on the last master (stock 0x110: round robin)
.set USBINIT_REJOIN, 0x4001e036

    .text
| ---- USB controller init (0x4001e030) ---------------------------------------
| Displaced: movel #0x08000000,%d0 (the next instruction stores it to a
| controller register), so d0 is free here and reloaded on the way out.
    .global crossbar_init_shim
crossbar_init_shim:
    movel   #BCR_ON,%d0
    movel   %d0,SCM_BCR
    movel   #PRS_USB1ST,%d0
    movel   %d0,XBS_PRS2
    movel   %d0,XBS_PRS4
    moveq   #CRS_FIXED,%d0
    movel   %d0,XBS_CRS2
    movel   %d0,XBS_CRS4
    movel   #0x08000000,%d0         | displaced
    jmp     USBINIT_REJOIN
