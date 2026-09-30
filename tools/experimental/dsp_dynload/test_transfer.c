/* Exercise the actual freestanding controller, including failed/stale replies.
 * No hardware timing or DSP execution is claimed by this native test. */
#include <assert.h>
#include <string.h>
#include "transfer.h"
void dl_selection_tick(void) {}
void dl_residency_tick(void) {}
static unsigned messages;
static const char *last_message;
void dl_show_message(const char *text, unsigned duration) {
    assert(duration == 0x30); ++messages; last_message=text;
}
static void ack(unsigned c, unsigned status, unsigned tag) {
    dl_rx[c][0]=DL_ACK; dl_rx[c][1]=dl_tx[c][1];
    dl_rx[c][2]=status; dl_rx[c][3]=tag;
}
static void request(void) { ++dl_request_probe; dl_frame(); }
int main(void) {
    dl_frame(); assert(dl_frames==1 && dl_tx[0][0]==0);
    request();
    for(unsigned c=0;c<2;++c) {
        unsigned sum=0;
        for(unsigned i=0;i<DL_WORDS;++i) sum+=dl_tx[c][i];
        assert((sum&65535)==0 && dl_tx[c][0]==DL_MAGIC);
        assert(dl_tx[c][3]==c && dl_tx[c][4]==DL_DATA);
        ack(c,0,c);
    }
    dl_frame(); assert(dl_accepted[0]==1 && dl_accepted[1]==1);
    dl_frame(); assert(dl_accepted[0]==1 && dl_tx[0][0]==0);
    request(); dl_frame(); /* old replies must not acknowledge new sequence */
    assert(dl_accepted[0]==1 && dl_accepted[1]==1);
    ack(0,1,0); ack(1,0,0); /* checksum refusal and wrong-core reply */
    dl_frame(); assert(dl_errors==2 && dl_rejected[0]==1 && dl_rejected[1]==1);
    assert(messages==0); dl_ui(); assert(messages==1);
    assert(strcmp(last_message,"DSP LOAD FAILED")==0);
    dl_ui(); assert(messages==1);
    request();
    for(unsigned i=0;i<64;++i) dl_frame();
    assert(dl_errors==4 && dl_tx[0][0]==0 && dl_tx[1][0]==0);
    dl_modal_pending=2; dl_ui(); assert(strcmp(last_message,"DSP MEMORY FULL")==0);
    dl_modal_pending=3; dl_ui(); assert(strcmp(last_message,"DSP OVERLOAD")==0);
    /* Every request, including the 16-bit wrap, gets a nonzero sequence. */
    for(unsigned i=0;i<65536;++i) {
        request();
        assert(dl_tx[0][1]!=0 && dl_tx[1][1]!=0);
        ack(0,0,0); ack(1,0,1); dl_frame();
    }
    assert(dl_accepted[0]==65537 && dl_accepted[1]==65537 && dl_errors==4);
    /* Real job protocol: chunking, both relocation directions and readback. */
    assert(dl_command_start(0,DL_PROBE,0,0,0)); dl_frame();
    ack(0,0,0); dl_rx[0][6]=0x1000; dl_rx[0][7]=1408;
    dl_frame(); assert(dl_pool_base[0]==0x1000 && dl_job_status(0)==1); dl_job_release(0);
    uint32_t words[25]; for(unsigned i=0;i<25;++i) words[i]=i+1;
    uint16_t reloc[2]={1,0x8018};
    struct dl_upload u={words,reloc,25,2,64};
    assert(dl_upload_start(0,&u)); assert(!dl_upload_start(0,&u)); dl_frame();
    assert(dl_tx[0][2]==DL_WRITE && dl_tx[0][4]==24 && dl_tx[0][5]==64);
    for(unsigned chunk=0;chunk<2;++chunk) {
        unsigned n=chunk ? 1:24; uint32_t sum=0;
        for(unsigned i=0;i<n;++i) {
            unsigned index=chunk*24+i;
            uint32_t expected=words[index];
            if(index==1) expected+=0x1040;
            if(index==24) expected=(expected-0x1040)&0xffffff;
            uint32_t sent=((uint32_t)dl_tx[0][8+2*i]<<8)|dl_tx[0][9+2*i];
            assert(sent==expected); sum=(sum+sent)&0xffffff;
        }
        ack(0,0,0); dl_rx[0][4]=sum&65535; dl_rx[0][5]=sum>>16;
        dl_frame();
    }
    assert(dl_job_status(0)==1); dl_job_release(0);
    assert(!dl_command_start(0,DL_BIND,12,63,80));
    assert(dl_command_start(0,DL_BIND,12,64,80)); dl_frame();
    ack(0,0,0); dl_frame(); assert(dl_job_status(0)==1); dl_job_release(0);
    assert(dl_upload_start(0,&u)); dl_frame();
    ack(0,0,0); dl_rx[0][4]=0; dl_rx[0][5]=0; dl_frame();
    assert(dl_job_status(0)==-1); dl_job_release(0); /* corrupted readback */
    return 0;
}
