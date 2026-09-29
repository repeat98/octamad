/* Exercise the actual freestanding controller, including failed/stale replies.
 * No hardware timing or DSP execution is claimed by this native test. */
#include <assert.h>
#include <string.h>
#include "transfer.h"
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
    return 0;
}
