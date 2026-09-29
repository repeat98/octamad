#include <assert.h>
#include <string.h>
#include "allocator.h"
static struct dl_package catalog[32];
static struct dl_allocator a;
static uint8_t ids[16];
static void empty(void) { memset(ids,DL_NONE,sizeof ids); }
static void commit(unsigned token) {
    for(unsigned c=0;c<2;++c) if(a.required & (1u<<c))
        assert(dl_allocator_ack(&a,token,c)==1);
    assert(dl_allocator_commit(&a,token)==1);
}
static void disjoint(void) {
    for(unsigned c=0;c<2;++c) for(unsigned p=0;p<32;++p) {
        struct dl_placement x=a.live[c][p];
        if(!x.present) continue;
        assert(x.offset+x.words<=a.capacity[c]);
        for(unsigned q=p+1;q<32;++q) {
            struct dl_placement y=a.live[c][q];
            if(y.present) assert(x.offset+x.words<=y.offset || y.offset+y.words<=x.offset);
        }
    }
}
int main(void) {
    catalog[1]=(struct dl_package){24,8,100,3,0,1};
    catalog[2]=(struct dl_package){24,16,120,3,0,1};
    catalog[3]=(struct dl_package){50,1,200,1,0,1};
    catalog[4]=(struct dl_package){0,1,20,3,1,1};
    dl_allocator_init(&a,catalog,64,64,1000,1000);
    empty(); ids[0]=ids[1]=ids[4]=1;
    assert(dl_allocator_prepare(&a,ids,1)==1);
    assert(a.target[0][1].present && a.target[1][1].present);
    assert(dl_allocator_commit(&a,1)==0); /* acknowledgements required */
    assert(dl_allocator_ack(&a,99,0)==DL_ALLOC_STALE);
    commit(1); assert(dl_allocator_prepare(&a,ids,2)==DL_ALLOC_BUSY);
    assert(dl_allocator_retire(&a,1)==1); disjoint();
    ids[0]=ids[1]=2;
    assert(dl_allocator_prepare(&a,ids,2)==1);
    assert(a.target[1][2].offset==32); /* preserve outgoing 24 words + alignment */
    assert(dl_allocator_cancel(&a,99)==DL_ALLOC_STALE);
    assert(dl_allocator_cancel(&a,2)==1);
    assert(a.live[1][1].present && !a.live[1][2].present);
    assert(dl_allocator_prepare(&a,ids,3)==1); commit(3);
    assert(a.live[1][1].present && a.live[1][2].present); disjoint();
    assert(dl_allocator_retire(&a,3)==1 && !a.live[1][1].present);
    ids[0]=3; ids[1]=DL_NONE;
    assert(dl_allocator_prepare(&a,ids,4)==DL_ALLOC_TRANSITION);
    assert(a.phase==0 && a.live[1][2].present);
    ids[1]=2;
    assert(dl_allocator_prepare(&a,ids,5)==DL_ALLOC_MEMORY);
    ids[1]=DL_NONE; ids[0]=32;
    assert(dl_allocator_prepare(&a,ids,6)==DL_ALLOC_UNAVAILABLE);
    ids[0]=DL_NONE; ids[8]=3;
    assert(dl_allocator_prepare(&a,ids,7)==DL_ALLOC_UNAVAILABLE); /* FX1 only */
    empty(); ids[0]=4;
    assert(dl_allocator_prepare(&a,ids,8)==1); commit(8);
    assert(dl_allocator_retire(&a,8)==1 && !a.live[1][2].present);
    /* No unsigned overflow can turn a huge processing cost into admission. */
    catalog[5]=(struct dl_package){1,1,0xffffffffu,3,0,1}; ids[0]=5;
    assert(dl_allocator_prepare(&a,ids,9)==DL_ALLOC_CYCLES);
    /* Seeded churn checks every retained and target interval after each commit. */
    unsigned rng=0x12345,token=10;
    for(unsigned n=0;n<2000;++n,++token) {
        empty();
        for(unsigned i=0;i<16;++i) {
            rng=rng*1664525u+1013904223u;
            unsigned p=(rng>>24)%4; ids[i]=p ? p:DL_NONE;
        }
        int result=dl_allocator_prepare(&a,ids,token);
        if(result==1) { commit(token); disjoint(); assert(dl_allocator_retire(&a,token)==1); disjoint(); }
        else assert(!a.phase);
    }
    return 0;
}
