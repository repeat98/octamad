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
        .zero 1456
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
