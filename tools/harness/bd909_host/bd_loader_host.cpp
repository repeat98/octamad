// Execute real ColdFire-produced packets through the resident DSP source seam.
#include <fstream>
#include <sstream>
#include <iostream>
#include <vector>
#include <cstdlib>
#include "dsp56kEmu/dsp.h"
#include "dsp56kEmu/memory.h"
#include "dsp56kEmu/peripherals.h"
using namespace dsp56k;
struct Allow : IMemoryValidator {bool memValidateAccess(EMemArea,TWord,bool) const override{return true;}};
int main(int argc,char**argv){
 if(argc!=7 && argc!=8)return 2;
 Allow allow;Memory mem(allow,0x80000,0x800000,0x200000);
 Peripherals56362 px;Peripherals56367 py;DSP dsp(mem,&px,&py);
 unsigned org=std::strtoul(argv[2],nullptr,16),cont=std::strtoul(argv[3],nullptr,16);
 std::ifstream code(argv[1],std::ios::binary);std::vector<unsigned char>b((std::istreambuf_iterator<char>(code)),{});
 for(unsigned i=0;i<b.size()/3;++i)mem.set(MemArea_P,org+i,b[3*i]|b[3*i+1]<<8|b[3*i+2]<<16);
 std::ifstream data(argv[4]);std::string line;
 while(std::getline(data,line)){std::istringstream s(line);unsigned a,w;s>>std::hex>>a;while(s>>w)mem.set(MemArea_X,a++,w);}
 std::ifstream packets(argv[5]);std::ofstream log(std::string(argv[6])+".log"),dump(std::string(argv[6])+".dump",std::ios::binary);
 std::ofstream audio;
 if(argc==8)audio.open(argv[7],std::ios::binary);
 unsigned step=0;
 while(std::getline(packets,line)){
  std::istringstream s(line);unsigned slot,w,a=0x500;s>>std::hex>>slot;while(s>>w)mem.set(MemArea_X,a++,w|0xa00000);
  mem.set(MemArea_X,0x209,0x500);mem.set(MemArea_X,0x418,slot*32);mem.set(MemArea_X,0x20c,0xffffff);
  for(unsigned k=0;k<8;++k)dsp.regs().m[k].var=0xffffff;
  dsp.setPC(0x3f000);dsp.jsr(org);auto start=dsp.getInstructionCounter();unsigned calls=0;
  while(dsp.getPC().toWord()!=cont && calls++<50000)dsp.execInterpreter();
  if(calls>=50000){std::cerr<<"hang "<<step<<" pc "<<std::hex<<dsp.getPC().toWord()<<"\n";return 3;}
  if(audio)for(unsigned k=0;k<32;++k){uint32_t v=mem.get(MemArea_X,k);audio.write((char*)&v,4);}
  log<<std::dec<<step++<<' '<<dsp.getInstructionCounter()-start;
  for(unsigned k=0;k<8;++k)log<<' '<<std::hex<<mem.get(MemArea_X,0x3800+k);log<<'\n';
  // The loader gate captures memory; audition captures audio without huge dumps.
  if(!audio)for(auto area:{MemArea_P,MemArea_X})for(unsigned k=0;k<0x4000;++k){uint32_t v=mem.get(area,k);dump.write((char*)&v,4);}
 }
}
