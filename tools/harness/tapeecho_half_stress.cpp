// Native arithmetic stress for the opt-in half-rate candidate. Run with UBSan.
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <vector>
extern "C" {
#include "../../modules/tapeecho_half/cpu.h"
}
int main(){
 std::vector<int32_t> ring(TE_RING*2); TapeState s{}; TapeParams p{};
 uint32_t rng=123,write=TE_RING-160;
 for(unsigned b=0;b<50000;++b){
  p={b/3%128,b/11%128,b/5%128,b/37%2,b/7%128,b/13%128,(30+b/19%271)*24,b%8};
  int32_t audio[32],record[32];
  for(auto &x:audio){rng=rng*1664525u+1013904223u;x=rng;}
  te_process(&s,&p,ring.data(),write,audio,record);
  std::copy(record,record+32,ring.begin()+write*2);write=(write+16)%TE_RING;
 }
 std::puts("PASS: 50000 half-rate blocks, full-range input/all controls, UBSan, multiple wraps");
}
