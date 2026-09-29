#ifndef DL_ALLOCATOR_H
#define DL_ALLOCATOR_H
#include <stdint.h>
#define DL_PACKAGES 32
#define DL_INSTANCES 16
#define DL_NONE 255
/* P offsets are relative to a ledger-owned arena. Resident packages have zero
 * arena words; their code and state are reserved outside this allocator. */
struct dl_package {
    uint16_t words, alignment;
    uint32_t cycles;
    uint8_t slots, resident, qualified;
};
struct dl_placement { uint16_t offset, words; uint8_t present; };
struct dl_allocator {
    const struct dl_package *catalog;
    uint16_t capacity[2];
    uint32_t allowance[2], generation, token;
    struct dl_placement live[2][DL_PACKAGES], target[2][DL_PACKAGES];
    uint8_t active[DL_INSTANCES], requested[DL_INSTANCES];
    uint8_t phase, required, ready;
};
enum { DL_ALLOC_OK=1, DL_ALLOC_WAIT=0, DL_ALLOC_MEMORY=-1,
       DL_ALLOC_CYCLES=-2, DL_ALLOC_UNAVAILABLE=-3, DL_ALLOC_BUSY=-4,
       DL_ALLOC_TRANSITION=-5, DL_ALLOC_STALE=-6 };
void dl_allocator_init(struct dl_allocator *,const struct dl_package *,
                       unsigned words0,unsigned words1,uint32_t cycles0,uint32_t cycles1);
int dl_allocator_prepare(struct dl_allocator *,const uint8_t ids[16],uint32_t token);
int dl_allocator_ack(struct dl_allocator *,uint32_t token,unsigned core);
int dl_allocator_commit(struct dl_allocator *,uint32_t token);
int dl_allocator_retire(struct dl_allocator *,uint32_t token);
int dl_allocator_cancel(struct dl_allocator *,uint32_t token);
#endif
