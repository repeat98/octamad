/* Test-only initialization and lossless EMAC observation; never in an image. */
    .text
    .global probe_init, probe_capture
    .global probe_extension_roundtrip
probe_init:
    move.l #0x20,%macsr
    moveq #0,%d0
    move.l %d0,%acc0
    move.l %d0,%acc1
    move.l %d0,%acc2
    move.l %d0,%acc3
    moveq #-1,%d0
    move.l %d0,%mask
    rts
probe_capture:
    move.l %macsr,%d0
    move.l %d0,(%a3)+
    /* Integer readout preserves raw low 32 bits, without fractional rounding
     * or saturation. Extension registers supply the remaining bits. */
    move.l #0,%macsr
    move.l %acc0,%d0
    move.l %d0,(%a3)+
    move.l %acc1,%d0
    move.l %d0,(%a3)+
    move.l %acc2,%d0
    move.l %d0,(%a3)+
    move.l %acc3,%d0
    move.l %d0,(%a3)+
    move.l %accext01,%d0
    move.l %d0,(%a3)+
    move.l %accext23,%d0
    move.l %d0,(%a3)+
    move.l %mask,%d0
    move.l %d0,(%a3)+
    rts
probe_extension_roundtrip:
    move.l #0,%macsr
    move.l %d0,%acc0
    move.l %d0,%acc1
    move.l %d1,%accext01
    move.l %acc0,%d0
    rts
