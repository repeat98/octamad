#ifndef DL_PUBLICATION_H
#define DL_PUBLICATION_H
#include <stdint.h>
struct dl_project_target { uint32_t bank,pattern,part; uint8_t ids[16],source[8]; };
int dl_project_metadata(const char *,struct dl_project_target *);
int dl_publication_prepare(const uint8_t ids[16],const uint8_t sources[8],uint32_t token);
int dl_publication_idle(void);
int dl_publication_poll(uint32_t token);
void dl_publication_arm(uint32_t token);
int dl_publication_ready(const uint8_t ids[16]);
void dl_publication_tick(void);
void dl_publication_finish(void);
unsigned dl_pattern_boundary(void);
#endif
