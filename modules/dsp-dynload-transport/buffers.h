#ifndef DL_BUFFERS_H
#define DL_BUFFERS_H
#include <stdint.h>
/* Dynamic Y buffers: which slot owns which of its core's effect blocks.
 *
 * Stock gives every slot a fixed block through the 8-word table at X:0x255
 * (FX1/FX2 interleaved per position), and an effect reads its entry once, in
 * init, through X:0x213 (tools/experimental/dsp_dynload/README.md "Y buffers").
 * Here a block goes only to a slot whose effect reads its base (the catalog's
 * `buffer` byte), chosen from the blocks stock itself uses for that slot kind
 * on that core (so an effect sees a base it could have had from stock, and
 * FX1 bases stay below 0x4000, FX2 at or above), and the table entry is
 * written before the new effect's init. An outgoing effect's block stays
 * reserved until the transition retires (it runs its last sub-block on its
 * stashed base in the frame the new one inits). A target that does not fit
 * is refused, as the P allocator refuses code.
 *
 * Slot index i: FX1 for i < 8, FX2 for i >= 8; track i & 7; tracks 0..3 on
 * core 1, 4..7 on core 0; table entry 2 * (track & 3) + (i >= 8).
 * A slot that has not been through a committed transition keeps its stock
 * block while what runs there reads its base: the loader did not place it. */
#define DL_BUF_NONE 255
#define DL_BUF_BLOCKS 4
struct dl_buffers {
    uint8_t live[16], target[16], known[16];
    uint32_t table[2][8], want[2][8], saved[2][8];
    uint8_t valid[2][2];            /* per core, per kind (0 FX1, 1 FX2): a mask of usable blocks */
    uint8_t open;
};
enum { DL_BUF_OK=1, DL_BUF_MEMORY=-1, DL_BUF_BUSY=-4 };
/* `pmap16`: the 16K program map, where Y ends at 0x9FFF and the FX2 block at
 * 0x8000 (half of it gone) is never handed out. */
void dl_buffers_init(struct dl_buffers *,unsigned pmap16);
/* running: the ids the firmware runs now (its live FX arrays); ids: the
 * target; reads: per id, 1 when its init reads its buffer base. Plans target[]
 * and want[][] (live held throughout). */
int dl_buffers_prepare(struct dl_buffers *,const uint8_t running[16],const uint8_t ids[16],
                       const uint8_t reads[32]);
/* the next table entry (core * 8 + entry) whose written value is not the
 * wanted one, or -1; and the note that it was written */
int dl_buffers_next(const struct dl_buffers *,uint32_t *value);
void dl_buffers_written(struct dl_buffers *,unsigned index);
void dl_buffers_retire(struct dl_buffers *);   /* after the committed transition's unbinds */
void dl_buffers_cancel(struct dl_buffers *);   /* want: the table as it was before */
uint32_t dl_buffers_base(unsigned core,unsigned kind,unsigned block);
unsigned dl_buffers_core(unsigned i);
unsigned dl_buffers_entry(unsigned i);
#endif
