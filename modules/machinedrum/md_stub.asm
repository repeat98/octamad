; ---------------------------------------------------------------------------
; MACHINEDRUM's dispatch stub: what the id runs on CORE 0 (payload A, T5-T8),
; where no Machinedrum lives -- a passthrough, the frames already in place.
; On core 1 tools/build/md_image.py points the id at md_glue.asm's
; gfxinit/gfxproc instead, and this copy in payload B's harvested region is
; overwritten by the MD's own code during the core-1 upload.
;
; The empty `do n7` loop is for tools/build/cycle_count.py, which prices a
; module by its sample loop: its one cycle per sample is this stub's, on core
; 0. The Machinedrum's own cost is on core 1 and is measured under the port
; (the driver's instruction span per frame), not by the static counter.
; ---------------------------------------------------------------------------

init:
        rts

proc:
        do      n7,>mds_end
        nop
mds_end:
        rts
