| WP-D7: the UI task's display loop runs the MD focus once a tick. The
| loop's first two calls (0x4005221e: a PC-relative and an absolute jsr)
| are displaced; md_ui_tick then pushes or pops the MD's input layer.
        .text
        .global md_tick_hook
md_tick_hook:
        jsr     0x4005213c
        jsr     0x4007e940
        jsr     md_ui_tick
        jmp     0x40052228

| Explicit editor storage: the runtime copies a linked image and has no .bss.
| MdUi's first 10 bytes are selection/cache state; 0xff means unseen.
        .data
        .balign 4
        .global md_ui
md_ui:
        .byte 0,255,255,255,255,255,255,255,255,255
        .zero 30
        .zero 0x1cc

| WP-D7: md_focus (MdFocus, md_ctl.h) and the MD's input layer, as the
| stock ones: {next, keys, encoders, 0, 0, -1, -1}. Key records, 26 B:
| {code, 0, press, release, repeat, sub-map, 0, delay, rate}; the trigs
| keep stock's repeat delay (16). No encoder records: the knobs reach the
| page underneath.
        .balign 4
        .global md_focus, md_layer
md_focus:
        .zero 296
md_layer:
        .long   0, md_layer_keys, md_layer_encs, 0, 0, -1, -1
md_layer_keys:
        .irp    k, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15
        .byte   \k, 0
        .long   md_layer_key, md_layer_key, md_layer_key, 0, 0
        .word   16, 0
        .endr
        .byte   0x31, 0
        .long   md_layer_key, md_layer_key, 0, 0, 0
        .word   0, 0
        .byte   0xff, 0
        .long   0, 0, 0, 0, 0
        .word   0, 0
md_layer_encs:
        .byte   0xff, 0
        .long   0, 0, 0, 0, 0

| WP-D8: the ENGINE window's layer. Its keys: the trigs (a part), UP/DOWN
| (repeating, as TEMPO's), LEFT/RIGHT, YES, NO, and the page and track keys
| held while it is open; FUNC as TEMPO's layer has it (0x400bb4ec: press
| taken, stock's release, a sub-layer for FUNC + key: FUNC+YES previews).
| Knobs A-F are held (a null handler swallows the turn), LEVEL scrolls.
        .balign 4
        .global md_eng_layer
md_eng_layer:
        .long   0, md_eng_keys, md_eng_encs, 0, 0, -1, -1
md_eng_func:
        .long   0, md_eng_fkeys, 0, 0, 0, -1, -1
md_eng_keys:
        .irp    k, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15
        .byte   \k, 0
        .long   md_eng_key, md_eng_key, md_eng_key, 0, 0
        .word   16, 0
        .endr
        .irp    k, 0x33, 0x20
        .byte   \k, 0
        .long   md_eng_key, 0, md_eng_key, 0, 0
        .word   15, 5
        .endr
        .irp    k, 0x34, 0x21, 0x31, 0x32, 0x22, 0x23, 0x24, 0x25, 0x26, 0x10, 0x11, 0x12, 0x13, 0x14, 0x15, 0x16, 0x17
        .byte   \k, 0
        .long   md_eng_key, 0, 0, 0, 0
        .word   0, 0
        .endr
        .byte   0x2d, 0
        .long   0, 0x400568e4, 0, md_eng_func, 0
        .word   0, 0
        .byte   0xff, 0
        .long   0, 0, 0, 0, 0
        .word   0, 0
md_eng_fkeys:
        .irp    k, 0x33, 0x20
        .byte   \k, 0
        .long   md_eng_key, 0, md_eng_key, 0, 0
        .word   15, 5
        .endr
        .irp    k, 0x31, 0x32
        .byte   \k, 0
        .long   md_eng_key, 0, 0, 0, 0
        .word   0, 0
        .endr
        .byte   0xff, 0
        .long   0, 0, 0, 0, 0
        .word   0, 0
md_eng_encs:
        .irp    k, 0, 1, 2, 3, 4, 5
        .byte   \k, 0
        .long   0, 0, 0, 0, 0
        .endr
        .byte   6, 0
        .long   md_eng_level, 0, 0, 0, 0
        .byte   0xff, 0
        .long   0, 0, 0, 0, 0
