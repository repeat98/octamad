| clamp.s -- the descriptor responder's two length clamps, as shims.
| markandrus/octemu custom/coldfire/usb-audio.s audio_clamp shims (MIT),
| reading the linked length instead of his defsym.
    .text
| The stock responder clamps GET_DESCRIPTOR(CONFIG / OTHER_SPEED) replies
| to a hardcoded length via `moveq #32` (0x4001d858 / 0x4001d896), which
| cannot hold a grown configuration above 127; each shim computes
| min(wLength, cfg_len) and rejoins with it in d1. d2 = wLength (host
| order). cfg_len is the descriptor unit's absolute symbol (descriptors.py).
    .global usbmidi_clamp1_shim, usbmidi_clamp2_shim
usbmidi_clamp1_shim:
    movel   %d2,%d1
    cmpil   #cfg_len,%d1
    blss    1f
    movel   #cfg_len,%d1
1:  jmp     0x4001d864
usbmidi_clamp2_shim:
    movel   %d2,%d1
    cmpil   #cfg_len,%d1
    blss    1f
    movel   #cfg_len,%d1
1:  jmp     0x4001d8a2

