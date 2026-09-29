/* Synthetic format fixtures contain no firmware or user project data. */
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "publication.h"
static unsigned char bank[0x9c000];
static const char *project;
static unsigned bank_size=sizeof bank;
static int unreadable;
int dl_file_size(const char *path) {
    return strcmp(path,"/set/project/project.work") ? -1:(int)strlen(project);
}
int dl_read_file(const char *path,unsigned offset,void *out,unsigned count) {
    if(unreadable)return 0;
    if(!strcmp(path,"/set/project/project.work")) {
        if(offset+count>strlen(project))return 0;
        memcpy(out,project+offset,count);return 1;
    }
    if(strcmp(path,"/set/project/bank01.work") || offset>bank_size || count>bank_size-offset)return 0;
    memcpy(out,bank+offset,count);return 1;
}
static int read_target(void) {
    struct dl_project_target p;
    int r=dl_project_metadata("/set/project",&p);
    if(r) {
        assert(p.bank==0 && p.pattern==0 && p.part==0);
        assert(p.ids[0]==12 && p.ids[4]==28);
        for(unsigned i=0;i<16;++i)if(i!=0 && i!=4)assert(p.ids[i]==0);
        for(unsigned i=0;i<8;++i)assert(p.source[i]==1);
    }
    return r;
}
int main(void) {
    memcpy(bank,"FORM\0\0\0\0DPS1BANK",16);
    memcpy(bank+0x8eed6,"PART",4);bank[0x8eed6+9]=12;bank[0x8eed6+13]=28;
    memset(bank+0x8eed6+9+0x22,1,8);
    project="[STATE]\r\nBANK=0\r\nPATTERN=0\r\nPART=0";assert(read_target());
    project="BANK=0\nPATTERN=0\nPART=0\nPART=1\n";assert(!read_target());
    char long_state[200];memset(long_state,' ',sizeof long_state);
    memcpy(long_state,"BANK=0\nPATTERN=0\nPART=0\nPART=1",30);long_state[199]=0;
    project=long_state;assert(!read_target());
    project="BANK=0\nPATTERN=0\n";assert(!read_target());
    project="BANK=16\nPATTERN=0\nPART=0\n";assert(!read_target());
    project="BANK=0\nPATTERN=0\nPART=4\n";assert(!read_target());
    project="BANK=0\nPATTERN=0\nPART=-1\n";assert(!read_target());
    project="BANK=0\nPATTERN=0\nPART=0x0\n";assert(!read_target());
    project="BANK=0\nPATTERN=0\nPART=0\n";
    unreadable=1;assert(!read_target());unreadable=0;
    bank_size=0x8eed6+10;assert(!read_target());bank_size=sizeof bank;
    bank[8]='X';assert(!read_target());bank[8]='D';
    bank[0x16+0x8eec-5]=1;assert(!read_target());bank[0x16+0x8eec-5]=0;
    bank[0x8eed6]='X';assert(!read_target());bank[0x8eed6]='P';
    assert(read_target());
    struct dl_project_target p;char long_path[300];memset(long_path,'a',299);long_path[299]=0;
    assert(!dl_project_metadata(long_path,&p));
    puts("PASS: project preflight, full scan, duplicate/missing/range/format/truncation and linked-Part refusal");
}
