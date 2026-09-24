| Explicit editor storage: the runtime copies a linked image and has no .bss.
| MdUi's first 10 bytes are selection/cache state; 0xff means unseen.
        .data
        .balign 4
        .global md_ui
md_ui:
        .byte 0,255,255,255,255,255,255,255,255,255
        .zero 30
        .zero 0x1cc
