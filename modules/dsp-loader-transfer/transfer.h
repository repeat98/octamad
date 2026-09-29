#ifndef DL_TRANSFER_H
#define DL_TRANSFER_H
#include <stdint.h>
#define DL_WORDS 64
#define DL_DATA 24
#define DL_MAGIC 0x4c44
#define DL_ACK 0x414b
/* A firmware transport diagnostic. EXEC/COMMIT is deliberately not an opcode. */
enum { DL_IDLE=0, DL_PROBE=1 };
extern volatile uint16_t dl_tx[2][DL_WORDS], dl_rx[2][32];
extern volatile uint32_t dl_frames, dl_accepted[2], dl_rejected[2], dl_errors;
extern volatile uint32_t dl_request_probe, dl_modal_pending, dl_modal_shown;
void dl_frame(void);
void dl_ui(void);
#endif
