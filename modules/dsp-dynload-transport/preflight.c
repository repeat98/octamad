/* Read-only project admission metadata. No writes to firmware project state.
 * File I/O uses a private uncached sector buffer. */
#include <stdint.h>
#include "selection.h"
#include "publication.h"
#ifdef DL_NATIVE_TEST
extern int dl_read_file(const char *,unsigned,void *,unsigned);
extern int dl_file_size(const char *);
#else
/* Use a private uncached sector buffer rather than the stock buffered reader's
 * global scratch: the engine can be reading another file while UI preflights. */
static uint8_t file_buffer[512] __attribute__((aligned(512)))={0};
#define FS(address,type) ((type)(uintptr_t)*(volatile uint32_t *)(uintptr_t)(address))
static int file_open(const char *path) {
    return FS(0x46c8242au,int (*)(const char *,const char *))(path,"r");
}
static int file_close(int fd) { return FS(0x46c82422u,int (*)(int))(fd); }
static int dl_file_size(const char *path) {
    int fd=file_open(path);if(fd<1)return -1;
    int size=FS(0x46c8241eu,int (*)(int))(fd);
    return file_close(fd)<0 ? -1:size;
}
static int dl_read_file(const char *path,unsigned offset,void *to,unsigned count) {
    int fd=file_open(path);if(fd<1)return 0;
    int size=FS(0x46c8241eu,int (*)(int))(fd);
    unsigned done=0;int ok=size>=0 && offset<=(unsigned)size && count<=(unsigned)size-offset;
    volatile uint8_t *buffer=(volatile uint8_t *)((uintptr_t)file_buffer+0x08000000u);
    while(ok && done<count) {
        unsigned position=offset+done,within=position&511u,n=512-within;
        if(n>count-done)n=count-done;
        if(FS(0x46c8243eu,int (*)(int,unsigned))(fd,position&~511u)<0 ||
           FS(0x46c82426u,int (*)(int,volatile void *,unsigned))(fd,buffer,1)<=0) { ok=0;break; }
        for(unsigned i=0;i<n;++i) ((uint8_t *)to)[done+i]=buffer[within+i];
        done+=n;
    }
    return file_close(fd)>=0 && ok;
}
#endif
static unsigned append(char *out,unsigned n,const char *s) {
    while(*s && n<255) out[n++]=*s++;
    if(*s) return 0;
    out[n]=0;return n;
}
/* Fixed v1 bank structure is qualified against the same fixture parser used
 * by the repository gates. Reject unsupported/missing metadata, never guess. */
int dl_project_metadata(const char *directory,struct dl_project_target *target) {
    char path[256];uint8_t text[512];char line[96];unsigned used=0,found=0,offset=0;
    unsigned n=append(path,0,directory);if(!n || !append(path,n,"/project.work")) return 0;
    target->bank=target->pattern=target->part=0;
    /* Read complete lines without relying on a NUL terminator in the file.
     * Scan the whole file: a second STATE assignment must not bypass admission. */
    int size=dl_file_size(path);
    if(size<=0 || size>65536) return 0;
    while(offset<(unsigned)size) {
        unsigned length=(unsigned)size-offset;if(length>sizeof text)length=sizeof text;
        if(!dl_read_file(path,offset,text,length)) return 0;
        offset+=length;
        unsigned last=offset==(unsigned)size;
        for(unsigned i=0;i<length+last;++i) {
            uint8_t ch=i==length ? '\n':text[i];
            if(ch=='\r') continue;
            if(ch!='\n') { if(used<sizeof line-1) line[used++]=ch;else used=sizeof line;continue; }
            if(used==sizeof line &&
               ((line[0]=='B' && line[1]=='A' && line[2]=='N' && line[3]=='K' && line[4]=='=') ||
                (line[0]=='P' && line[1]=='A' && line[2]=='R' && line[3]=='T' && line[4]=='=') ||
                (line[0]=='P' && line[1]=='A' && line[2]=='T' && line[3]=='T' && line[4]=='E' &&
                 line[5]=='R' && line[6]=='N' && line[7]=='='))) return 0;
            if(used<sizeof line) {
                line[used]=0;
                const char *keys[3]={"BANK=","PATTERN=","PART="};
                for(unsigned k=0;k<3;++k) {
                    unsigned j=0;while(keys[k][j] && line[j]==keys[k][j]) ++j;
                    if(keys[k][j]) continue;
                    if(found&(1u<<k)) return 0;
                    unsigned value=0,digits=0;
                    while(line[j]>='0' && line[j]<='9') { value=value*10+line[j++]-'0';if(++digits>2) return 0; }
                    if(!digits || line[j] || value>(k==2 ? 3u:15u)) return 0;
                    if(k==0) target->bank=value;else if(k==1) target->pattern=value;else target->part=value;
                    found|=1u<<k;
                }
            }
            used=0;
        }
    }
    if(found!=7) return 0;
    n=append(path,0,directory);n=append(path,n,"/bank");if(!n || n+12>=sizeof path) return 0;
    unsigned bank=target->bank+1;path[n++]=(char)('0'+bank/10);path[n++]=(char)('0'+bank%10);path[n]=0;
    if(!append(path,n,".work")) return 0;
    uint8_t header[16];if(!dl_read_file(path,0,header,sizeof header)) return 0;
    const char magic[]="FORM";for(unsigned i=0;i<4;++i) if(header[i]!=(uint8_t)magic[i]) return 0;
    const char kind[]="DPS1BANK";
    for(unsigned i=0;i<8;++i) if(header[8+i]!=(uint8_t)kind[i]) return 0;
    /* The loader can apply the pattern-linked Part as well as STATE.PART.
     * Until multi-target project staging exists, refuse a disagreement. */
    uint8_t linked;
    if(!dl_read_file(path,0x16u+(target->pattern+1u)*0x8eecu-5u,&linked,1) ||
       linked!=target->part) return 0;
    unsigned part_offset=0x8eed6u+target->part*0x18bbu;
    uint8_t data[9+0x2a];if(!dl_read_file(path,part_offset,data,sizeof data)) return 0;
    if(data[0]!='P'||data[1]!='A'||data[2]!='R'||data[3]!='T') return 0;
    for(unsigned i=0;i<16;++i) target->ids[i]=data[9+i];
    for(unsigned i=0;i<8;++i) target->source[i]=data[9+0x22+i];
    return 1;
}
