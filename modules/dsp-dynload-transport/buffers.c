/* Dynamic Y buffers (buffers.h). Pure bookkeeping: the manager issues the
 * table writes (DL_BASE) this plans, before the transition is published. */
#include "buffers.h"
static const uint32_t fx1_base[DL_BUF_BLOCKS]={0x1000,0x1c00,0x2800,0x3400};
static const uint32_t fx2_base[2][DL_BUF_BLOCKS]={{0x4000,0x8000,0x30000,0x34000},
                                                  {0x4000,0x8000,0x38000,0x3c000}};
uint32_t dl_buffers_base(unsigned core,unsigned kind,unsigned block) {
    return kind ? fx2_base[core&1][block&3] : fx1_base[block&3];
}
unsigned dl_buffers_core(unsigned i) { return (i&7)<4 ? 1 : 0; }
unsigned dl_buffers_entry(unsigned i) { return 2*((i&7)&3)+(i>=8); }
static unsigned kind_of(unsigned i) { return i>=8; }
void dl_buffers_init(struct dl_buffers *b,unsigned pmap16) {
    for(unsigned c=0;c<2;++c) {
        b->valid[c][0]=0xf; b->valid[c][1]=pmap16 ? 0xd : 0xf;
        for(unsigned e=0;e<8;++e)
            b->table[c][e]=b->want[c][e]=b->saved[c][e]=dl_buffers_base(c,e&1,e>>1);
    }
    for(unsigned i=0;i<16;++i) {
        unsigned c=dl_buffers_core(i),k=kind_of(i),p=(i&7)&3;
        /* Before the loader first commits a slot, whatever runs there holds
         * its stock block (if that block still exists under the map). */
        b->live[i]=b->target[i]=((b->valid[c][k]>>p)&1u) ? (uint8_t)p : DL_BUF_NONE;
        b->known[i]=0;
    }
    b->open=0;
}
int dl_buffers_prepare(struct dl_buffers *b,const uint8_t running[16],const uint8_t ids[16],
                       const uint8_t reads[32]) {
    if(b->open) return DL_BUF_BUSY;
    /* A slot the loader has not committed holds its stock block only while
     * what runs there reads it; a non-reader there frees it now. */
    for(unsigned i=0;i<16;++i)
        if(!b->known[i] && b->live[i]!=DL_BUF_NONE && !(running[i]<32 && reads[running[i]]))
            b->live[i]=DL_BUF_NONE;
    uint8_t used[2][2]={{0,0},{0,0}};
    for(unsigned i=0;i<16;++i)
        if(b->live[i]!=DL_BUF_NONE) used[dl_buffers_core(i)][kind_of(i)]|=(uint8_t)(1u<<b->live[i]);
    uint8_t target[16];
    /* Kept blocks first, so a new one never takes a block a kept slot holds. */
    for(unsigned i=0;i<16;++i) {
        unsigned reader=ids[i]<32 && reads[ids[i]];
        unsigned same=ids[i]==running[i];
        target[i]=DL_BUF_NONE;
        if(same && b->live[i]!=DL_BUF_NONE && (reader || !b->known[i])) target[i]=b->live[i];
    }
    for(unsigned i=0;i<16;++i) {
        unsigned reader=ids[i]<32 && reads[ids[i]];
        if(!reader || target[i]!=DL_BUF_NONE) continue;
        unsigned c=dl_buffers_core(i),k=kind_of(i);
        unsigned taken=used[c][k];
        for(unsigned j=0;j<16;++j)
            if(target[j]!=DL_BUF_NONE && dl_buffers_core(j)==c && kind_of(j)==k) taken|=1u<<target[j];
        unsigned free=b->valid[c][k]&~taken&0xfu, n=0;
        if(!free) return DL_BUF_MEMORY;   /* live stays as it was: nothing planned */
        while(!((free>>n)&1u)) ++n;
        target[i]=(uint8_t)n;
    }
    for(unsigned c=0;c<2;++c)
        for(unsigned e=0;e<8;++e) b->saved[c][e]=b->want[c][e]=b->table[c][e];
    for(unsigned i=0;i<16;++i) {
        b->target[i]=target[i];
        if(target[i]!=DL_BUF_NONE)
            b->want[dl_buffers_core(i)][dl_buffers_entry(i)]=dl_buffers_base(dl_buffers_core(i),kind_of(i),target[i]);
    }
    b->open=1;
    return DL_BUF_OK;
}
int dl_buffers_next(const struct dl_buffers *b,uint32_t *value) {
    for(unsigned c=0;c<2;++c)
        for(unsigned e=0;e<8;++e)
            if(b->table[c][e]!=b->want[c][e]) { *value=b->want[c][e]; return (int)(c*8+e); }
    return -1;
}
void dl_buffers_written(struct dl_buffers *b,unsigned index) {
    unsigned c=(index>>3)&1u,e=index&7u;
    b->table[c][e]=b->want[c][e];
}
void dl_buffers_retire(struct dl_buffers *b) {
    for(unsigned i=0;i<16;++i) { b->live[i]=b->target[i]; b->known[i]=1; }
    b->open=0;
}
void dl_buffers_cancel(struct dl_buffers *b) {
    for(unsigned i=0;i<16;++i) b->target[i]=b->live[i];
    for(unsigned c=0;c<2;++c)
        for(unsigned e=0;e<8;++e) b->want[c][e]=b->saved[c][e];
    b->open=0;
}
