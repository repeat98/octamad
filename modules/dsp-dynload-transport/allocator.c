/* Freestanding transactional P residency allocator. No malloc, OS calls, DMA,
 * dispatch writes or implicit retirement. All mutations belong to one owner
 * task; the frame transport communicates through its own request mailbox. */
#include "allocator.h"
static unsigned core_of(unsigned i) { return (i&7)<4 ? 1 : 0; }
static void copy(void *to,const void *from,unsigned bytes) {
    volatile uint8_t *d=to; const uint8_t *s=from;
    for(unsigned i=0;i<bytes;++i) {
        uint8_t value=s[i];
        /* Keep source and destination accesses separate. A combined MOVE with
         * postincrement and a displacement from the same base is not covered
         * by the port's native C test; firmware gates caught shifted copies. */
#ifdef __m68k__
        __asm__ volatile("" : "+d"(value) :: "memory");
#else
        __asm__ volatile("" : "+r"(value) :: "memory");
#endif
        d[i]=value;
    }
}
static void zero(void *to,unsigned bytes) {
    volatile uint8_t *d=to; for(unsigned i=0;i<bytes;++i) d[i]=0;
}
void dl_allocator_init(struct dl_allocator *a,const struct dl_package *catalog,
                       unsigned w0,unsigned w1,uint32_t c0,uint32_t c1) {
    zero(a,sizeof *a); a->catalog=catalog;
    /* Reject truncation: zero capacity makes every nonempty allocation fail. */
    if(w0<=65535 && w1<=65535) { a->capacity[0]=w0; a->capacity[1]=w1; }
    a->allowance[0]=c0; a->allowance[1]=c1;
    for(unsigned i=0;i<16;++i) a->active[i]=DL_NONE;
}
static int place(struct dl_allocator *a,unsigned c,const uint8_t *ids,unsigned preserve) {
    struct dl_placement used[DL_PACKAGES*2]; unsigned n=0;
    zero(a->target[c],sizeof a->target[c]);
    if(preserve) for(unsigned p=0;p<DL_PACKAGES;++p)
        if(a->live[c][p].present) copy(&used[n++],&a->live[c][p],sizeof used[0]);
    for(unsigned i=0;i<16;++i) {
        unsigned p=ids[i];
        if(core_of(i)!=c || p==DL_NONE || a->catalog[p].resident || a->target[c][p].present) continue;
        const struct dl_package *pkg=&a->catalog[p];
        struct dl_placement *dest=&a->target[c][p];
        if(preserve && a->live[c][p].present) { copy(dest,&a->live[c][p],sizeof *dest); continue; }
        uint32_t base=0,align=pkg->alignment;
        for(;;) {
            base=(base+align-1)&~(align-1);
            if(base+pkg->words>a->capacity[c]) return DL_ALLOC_MEMORY;
            unsigned moved=0;
            for(unsigned j=0;j<n;++j) {
                uint32_t end=(uint32_t)used[j].offset+used[j].words;
                if(base<end && base+pkg->words>used[j].offset) { base=end; moved=1; break; }
            }
            if(!moved) break;
        }
        dest->offset=base; dest->words=pkg->words; dest->present=1;
        copy(&used[n++],dest,sizeof *dest);
    }
    return DL_ALLOC_OK;
}
int dl_allocator_prepare(struct dl_allocator *a,const uint8_t ids[16],uint32_t token) {
    uint32_t steady[2]={0,0},overlap[2]={0,0};
    if(a->phase) return DL_ALLOC_BUSY;
    if(!token || token==a->token) return DL_ALLOC_STALE;
    for(unsigned i=0;i<16;++i) {
        unsigned p=ids[i],c=core_of(i);
        if(p==DL_NONE) continue;
        if(p>=DL_PACKAGES) return DL_ALLOC_UNAVAILABLE;
        const struct dl_package *pkg=&a->catalog[p];
        if(!pkg->qualified || !(pkg->slots & (i<8 ? 1:2)) ||
           (!pkg->resident && (!pkg->words || !pkg->alignment ||
            (pkg->alignment & (pkg->alignment-1))))) return DL_ALLOC_UNAVAILABLE;
        if(pkg->cycles>a->allowance[c]-steady[c]) return DL_ALLOC_CYCLES;
        steady[c]+=pkg->cycles;
    }
    overlap[0]=steady[0]; overlap[1]=steady[1];
    for(unsigned i=0;i<16;++i) {
        unsigned p=a->active[i],c=core_of(i);
        if(p==DL_NONE || p==ids[i]) continue;
        uint32_t cost=a->catalog[p].cycles;
        if(cost>a->allowance[c]-overlap[c]) return DL_ALLOC_CYCLES;
        overlap[c]+=cost;
    }
    /* Distinguish an impossible target from one requiring unsafe overwrite. */
    for(unsigned c=0;c<2;++c) if(place(a,c,ids,0)<0) return DL_ALLOC_MEMORY;
    for(unsigned c=0;c<2;++c) if(place(a,c,ids,1)<0) return DL_ALLOC_TRANSITION;
    copy(a->requested,ids,16); a->token=token; a->ready=0; a->required=0;
    for(unsigned i=0;i<16;++i)
        if(ids[i]!=a->active[i]) a->required|=1u<<core_of(i);
    a->phase=1;
    return DL_ALLOC_OK;
}
int dl_allocator_ack(struct dl_allocator *a,uint32_t token,unsigned core) {
    if(a->phase!=1 || a->token!=token) return DL_ALLOC_STALE;
    if(core>1 || !(a->required & (1u<<core))) return DL_ALLOC_UNAVAILABLE;
    a->ready|=1u<<core; return DL_ALLOC_OK;
}
int dl_allocator_commit(struct dl_allocator *a,uint32_t token) {
    if(a->phase!=1 || a->token!=token) return DL_ALLOC_STALE;
    if(a->ready!=a->required) return DL_ALLOC_WAIT;
    for(unsigned c=0;c<2;++c) for(unsigned p=0;p<DL_PACKAGES;++p)
        if(a->target[c][p].present) copy(&a->live[c][p],&a->target[c][p],sizeof a->live[c][p]);
    copy(a->active,a->requested,16); a->phase=2; ++a->generation;
    return DL_ALLOC_OK;
}
int dl_allocator_retire(struct dl_allocator *a,uint32_t token) {
    if(a->phase!=2 || a->token!=token) return DL_ALLOC_STALE;
    copy(a->live,a->target,sizeof a->live); a->phase=0;
    return DL_ALLOC_OK;
}
int dl_allocator_cancel(struct dl_allocator *a,uint32_t token) {
    if(a->phase!=1 || a->token!=token) return DL_ALLOC_STALE;
    zero(a->target,sizeof a->target); a->phase=0; a->ready=0;
    return DL_ALLOC_OK;
}
