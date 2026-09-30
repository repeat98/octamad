#ifndef DL_TRANSFER_H
#define DL_TRANSFER_H
#include <stdint.h>
#define DL_WORDS 64
#define DL_DATA 24
#define DL_MAGIC 0x4c44
#define DL_ACK 0x414b
/* The original probe accepts only PROBE/STAGE. The runtime receiver also
 * supports verified uploads and dispatch binding inside its owned P arena. */
/* UNBIND restores an id's original entry; BYPASS points it at the dry stub. */
/* BASE writes one entry of the Y buffer table X:0x255 (id = the entry 0..7,
 * init = the base's low 16 bits, proc = its high 8; buffers.h). */
enum { DL_IDLE=0, DL_PROBE=1, DL_STAGE=2, DL_WRITE=3, DL_BIND=4, DL_UNBIND=5, DL_BYPASS=6, DL_BASE=7 };
extern volatile uint16_t dl_tx[2][DL_WORDS], dl_rx[2][32];
extern volatile uint32_t dl_frames, dl_accepted[2], dl_rejected[2], dl_errors;
extern volatile uint32_t dl_request_probe, dl_request_stage, dl_modal_pending, dl_modal_shown;
/* The receiver reports its table size (arena + 64 saved entries) with its
 * base on every acknowledgement; the ColdFire bounds everything by that,
 * so one runtime serves any arena the build gave the receiver. */
#define DL_POOL_LIMIT 0x2000
#define DL_CODE_START 64
struct dl_upload {
    const uint32_t *words;
    const uint16_t *relocations;
    uint16_t count, relocation_count, offset;
};
/* One producer (UI), one consumer (frame ISR). A descriptor becomes visible
 * only when state is published; its backing arrays must outlive completion. */
int dl_upload_start(unsigned core,const struct dl_upload *);
int dl_command_start(unsigned core,unsigned opcode,unsigned id,unsigned init,unsigned proc);
int dl_job_status(unsigned core); /* 0 pending, 1 complete, -1 failure, -2 idle */
void dl_job_release(unsigned core);
extern volatile uint32_t dl_pool_base[2], dl_pool_words[2];
unsigned dl_frame(void);
void dl_ui(void);
#endif
