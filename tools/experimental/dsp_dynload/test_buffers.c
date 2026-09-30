/* Native test of the dynamic Y buffer planner (modules/dsp-dynload-transport/buffers.c). */
#include <assert.h>
#include <string.h>
#include "buffers.h"
enum { NONE=0, FILTER=0x0f, FLANGER=0x11, CHORUS=0x12, PLATE=0x14, DARK=0x16 };
static uint8_t reads[32];
static void sync(struct dl_buffers *b) {
    uint32_t v; int i;
    while((i=dl_buffers_next(b,&v))>=0) dl_buffers_written(b,(unsigned)i);
}
static uint32_t entry_of(const struct dl_buffers *b,unsigned slot) {
    return b->table[dl_buffers_core(slot)][dl_buffers_entry(slot)];
}
static int step(struct dl_buffers *b,uint8_t active[16],const uint8_t ids[16]) {
    int r=dl_buffers_prepare(b,active,ids,reads);
    if(r!=DL_BUF_OK) return r;
    sync(b); dl_buffers_retire(b); memcpy(active,ids,16);
    return r;
}
int main(void) {
    reads[FLANGER]=reads[CHORUS]=reads[PLATE]=reads[DARK]=1;
    struct dl_buffers b; uint8_t active[16]={0}, ids[16]={0};
    dl_buffers_init(&b,0);
    /* Stock's table at boot, and every slot holds its stock block until known. */
    assert(b.table[0][0]==0x1000 && b.table[0][1]==0x4000 && b.table[0][5]==0x30000 && b.table[1][7]==0x3c000);
    for(unsigned i=0;i<16;++i) assert(b.live[i]==((i&7)&3));
    /* Unknown slots: one running a reader keeps its stock block, the others free
     * theirs, and nothing is written for a slot that does not change. */
    active[12]=DARK; ids[12]=DARK;               /* track 5's FX2: core 0, position 0 */
    assert(dl_buffers_prepare(&b,active,ids,reads)==DL_BUF_OK);
    uint32_t v; assert(dl_buffers_next(&b,&v)<0);
    assert(b.target[12]==0 && b.live[13]==DL_BUF_NONE && b.live[0]==DL_BUF_NONE);
    dl_buffers_retire(&b);
    ids[13]=DARK;                                /* a new reader never takes the kept block */
    assert(step(&b,active,ids)==DL_BUF_OK);
    assert(entry_of(&b,12)==0x4000 && entry_of(&b,13)!=0x4000 && entry_of(&b,13)>=0x4000);
    ids[12]=ids[13]=NONE;
    assert(step(&b,active,ids)==DL_BUF_OK);
    for(unsigned i=0;i<16;++i) assert(b.live[i]==DL_BUF_NONE);
    /* Four DARKs on core 0's FX2 (tracks 5..8, slots 12..15): exactly its four FX2 blocks. */
    for(unsigned i=12;i<16;++i) ids[i]=DARK;
    assert(step(&b,active,ids)==DL_BUF_OK);
    uint32_t seen=0;
    for(unsigned i=12;i<16;++i) {
        uint32_t base=entry_of(&b,i);
        assert(base>=0x4000);                       /* FX2 blocks only */
        seen|=base==0x4000 ? 1u : base==0x8000 ? 2u : base==0x30000 ? 4u : base==0x34000 ? 8u : 16u;
    }
    assert(seen==15);
    /* Changing one DARK to PLATE: the outgoing block stays held, so no block is free. */
    ids[12]=PLATE;
    assert(dl_buffers_prepare(&b,active,ids,reads)==DL_BUF_MEMORY);
    assert(!b.open && dl_buffers_next(&b,&v)<0);   /* a refusal writes nothing */
    /* A DARK going to FILTER frees its block after retirement, not before. */
    ids[12]=FILTER;
    assert(step(&b,active,ids)==DL_BUF_OK);
    ids[12]=PLATE;
    assert(step(&b,active,ids)==DL_BUF_OK);
    assert(entry_of(&b,12)>=0x4000);
    /* An FX1 reader gets an FX1 block (below 0x4000), on its own core only. */
    ids[0]=CHORUS; ids[1]=FLANGER; ids[2]=CHORUS; ids[3]=FLANGER;  /* core 1, FX1 */
    assert(step(&b,active,ids)==DL_BUF_OK);
    for(unsigned i=0;i<4;++i) assert(entry_of(&b,i)<0x4000 && b.table[1][dl_buffers_entry(i)]==entry_of(&b,i));
    /* Cancel: the table goes back to what it held, the plan is dropped. */
    ids[8]=DARK;                                   /* core 1 FX2 slot 0 */
    assert(dl_buffers_prepare(&b,active,ids,reads)==DL_BUF_OK);
    uint32_t before=b.saved[1][1];
    sync(&b); dl_buffers_cancel(&b); sync(&b);
    assert(b.table[1][1]==before && b.live[8]==DL_BUF_NONE && !b.open);
    /* The 16K map: 0x8000 is never handed out; four FX2 readers on one core are refused. */
    dl_buffers_init(&b,1); memset(active,0,16); memset(ids,0,16);
    assert(b.live[9]==DL_BUF_NONE && b.live[13]==DL_BUF_NONE);  /* position 1's FX2 block is gone */
    assert(step(&b,active,ids)==DL_BUF_OK);        /* known now */
    assert(step(&b,active,ids)==DL_BUF_OK);        /* and released */
    for(unsigned i=12;i<15;++i) ids[i]=DARK;
    assert(step(&b,active,ids)==DL_BUF_OK);
    for(unsigned i=12;i<15;++i) assert(entry_of(&b,i)!=0x8000);
    ids[15]=DARK;
    assert(dl_buffers_prepare(&b,active,ids,reads)==DL_BUF_MEMORY);
    return 0;
}
