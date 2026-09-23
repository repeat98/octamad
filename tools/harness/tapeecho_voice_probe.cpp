// Reproducible voicing gate for the actual fixed-point CPU engine. Targets
// are measurements, not a second implementation of its equations. Reference:
// modules/tapeecho/VOICING.md (local FX-pedal 44.1k; historical Galaxy 48k).
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <vector>
extern "C" {
#include "../../modules/tapeecho/cpu.h"
}
constexpr int fs=44100;
constexpr double pi=3.141592653589793, q=2147483648.;
static int failures=0;
static void check(const char* name,bool yes,double value) {
    std::printf("  [%s] %s: %.5f\n",yes?"PASS":"FAIL",name,value);
    failures+=!yes;
}
static double db(double x) { return 20*std::log10(std::max(x,1e-15)); }
static double rms(const std::vector<double>& x,int begin,int end) {
    double sum=0;for(int i=begin;i<end;++i)sum+=x[i]*x[i];
    return std::sqrt(sum/(end-begin));
}
static TapeParams params(unsigned feedback=0,unsigned wow=0,unsigned age=0) {
    return {60,feedback,wow,0,127,age,2880};
}
static std::vector<double> render(TapeParams p,double seconds,double hz=0,double amp=.01,bool burst=false) {
    unsigned length=unsigned(seconds*fs)/16*16, write=0;
    std::vector<double> output(length);
    std::vector<int32_t> ring(TE_RING*2);
    TapeState state{};
    for(unsigned n=0;n<length;n+=16) {
        int32_t audio[32],record[32];
        for(unsigned j=0;j<16;++j) {
            unsigned t=n+j;
            double envelope=(!burst || t<1024)?1:0;
            if(burst && t<1024) envelope=std::min({1.,t/64.,(1024-t)/64.});
            audio[2*j]=audio[2*j+1]=int32_t(q*amp*envelope*std::sin(2*pi*hz*t/fs));
        }
        te_process(&state,&p,ring.data(),write,audio,record);
        std::copy(record,record+32,ring.begin()+write*2);
        write=(write+16)%TE_RING;
        for(unsigned j=0;j<16;++j)output[n+j]=audio[2*j]/q;
    }
    return output;
}
static double pitch(const std::vector<double>& x) {
    std::vector<double> crossings;
    for(unsigned n=fs;n<x.size();++n)if(x[n-1]<=0 && x[n]>0)
        crossings.push_back(n-1-x[n-1]/(x[n]-x[n-1]));
    double sum=0,squares=0;unsigned count=0;
    for(unsigned n=10;n<crossings.size();++n) {
        double c=1200*std::log2(10.*fs/(crossings[n]-crossings[n-10])/3000);
        sum+=c;squares+=c*c;++count;
    }
    return std::sqrt(squares/count-std::pow(sum/count,2));
}
static double echoGain(unsigned feedback,double hz=1000) {
    auto x=render(params(feedback),.5,hz,.003,true);
    return db(rms(x,2*5888+128,2*5888+896)/rms(x,5888+128,5888+896));
}
int main() {
    const double reference[3][4]={{-6.07,-2.30,-12.21,-17.73},
        {-6.03,-2.97,-15.11,-22.43},{-5.97,-3.83,-18.03,-26.46}};
    const unsigned ages[]={0,64,127}; const double frequencies[]={100,4000,8000,10000};
    double maxError=0;
    for(unsigned a=0;a<3;++a) {
        auto ref=render(params(0,0,ages[a]),2,1000);
        double level=rms(ref,fs,ref.size());
        for(unsigned f=0;f<4;++f) {
            auto x=render(params(0,0,ages[a]),2,frequencies[f]);
            double response=db(rms(x,fs,x.size())/level);
            maxError=std::max(maxError,std::abs(response-reference[a][f]));
            std::printf("  [FR] AGE=%u %.0f Hz: %.3f dB relative to 1 kHz; pedal %.2f\n",
                        ages[a],frequencies[f],response,reference[a][f]);
        }
    }
    // OCTACLID5 deliberately folds two low-passes and uses a record FIR
    // for the owner's eight-instance economy target. Keep the original
    // measured reference: allow 2 dB colour error, not an updated oracle.
    check("Economy 12 frequency/age points within 2 dB of measured pedal",maxError<2,maxError);
    double clean=pitch(render(params(),5,3000,.2));
    double normal=pitch(render(params(0,44),5,3000,.2));
    double full=pitch(render(params(0,127),5,3000,.2));
    check("WOW=0 stays pitch-stable (cents RMS)",clean<.05,clean);
    check("WOW=35% approaches Galaxy/pedal ~8 cents RMS",normal>6.5&&normal<9.5,normal);
    check("WOW=100% remains substantially stronger",full>normal*2.5&&full<30,full);
    double worn=pitch(render(params(0,44,127),5,3000,.2));
    check("Worn tape retains wow and adds flutter",worn>normal&&worn<12,worn);
    const unsigned feedbacks[]={32,64,76,83,89};
    const double decayReference[]={-19.9,-6.1,-2.6,-1.1,.3};
    double decayError=0;
    for(unsigned i=0;i<5;++i) {
        double g=echoGain(feedbacks[i]);
        decayError=std::max(decayError,std::abs(g-decayReference[i]));
        std::printf("  [DECAY] FDBK=%u 1 kHz per repeat: %.3f dB; Galaxy %.1f\n",feedbacks[i],g,decayReference[i]);
    }
    check("Feedback decay curve follows measured Galaxy within 1 dB",decayError<1,decayError);
    double highLoss=echoGain(64,8000)-echoGain(64);
    check("Each repeat loses treble inside the loop",highLoss < -9,highLoss);
    auto noise=render(params(102,25,64),20);
    double first=db(rms(noise,0,fs)),last=db(rms(noise,19*fs,noise.size()));
    check("80% feedback grows from silence by >70 dB",last-first>70,last-first);
    // The owner explicitly permits economy-model voicing differences.
    // Removing emphasis changes saturation/noise dynamics: allow 1.5 dB
    // versus OCTACLID3, but keep the original reference, not a moving target.
    check("Economy noise build-up stays within 1.5 dB of OCTACLID3",std::abs(last+8.83032)<1.5,last);
    // The floor is the hiss, measured without DC. Until 23 Sep 2026 this
    // took the plain RMS against OCTACLID3 (-119.05/-118.03/-114.23 dB), but
    // that engine's output carried a constant -120 dBFS truncation offset
    // which dominated the number; the EMAC rewrite removed it (-147 dBFS)
    // and left the hiss itself within 0.11 dB. References are the AC floors
    // of the engine before that rewrite (f80f45e).
    double floors[3];
    for(unsigned i=0;i<3;++i) {
        auto x=render(params(0,0,ages[i]),3);
        double mean=0;for(unsigned n=fs;n<x.size();++n)mean+=x[n];mean/=x.size()-fs;
        double square=0;for(unsigned n=fs;n<x.size();++n)square+=(x[n]-mean)*(x[n]-mean);
        floors[i]=db(std::sqrt(square/(x.size()-fs)));
        const double referenceFloor[]={-128.90197,-123.56168,-116.38375};
        check("Economy hiss floor stays within 1 dB of the pre-EMAC engine",std::abs(floors[i]-referenceFloor[i])<1,floors[i]);
        check("Silent tape leaves no DC offset on the output (dBFS)",db(std::abs(mean))<-130,db(std::abs(mean)));
    }
    check("Tape age increases the noise floor",floors[2]-floors[0]>4,floors[2]-floors[0]);
    auto low=render(params(),2,1000,.001),hot=render(params(),2,1000,1);
    double compression=db(rms(hot,fs,hot.size())/rms(low,fs,low.size()))-60;
    check("Fixed DRIVE=0 retains gentle record compression (dB)",compression<0&&compression>-4,compression);
    auto fast=params(),slow=params();fast.time=20;slow.time=100;
    auto f1=render(fast,2,1000),f8=render(fast,2,8000);
    auto s1=render(slow,2,1000),s8=render(slow,2,8000);
    double loss=db(rms(s8,fs,s8.size())/rms(s1,fs,s1.size()))-
                db(rms(f8,fs,f8.size())/rms(f1,fs,f1.size()));
    check("Slower transport darkens playback",loss < -10,loss);
    // Aggressive control changes/full-scale signed input across three ring
    // wraps; also run this binary with ASan/UBSan. Exercise coefficients,
    // motor reversals and gain ramps, not just settled sine waves.
    TapeState state{};auto p=params();std::vector<int32_t> ring(TE_RING*2);
    uint32_t rng=0x12345678;unsigned write=0;bool safe=true;
    auto random=[&](){rng^=rng<<13;rng^=rng>>17;rng^=rng<<5;return rng;};
    for(unsigned block=0;block<35000;++block) {
        if(!(block%8)) {
            p.time=random()%128;p.feedback=random()%128;p.wow=random()%128;
            p.sync=random()%2;p.mix=random()%128;
            p.age=random()%128;p.tempo=(30+random()%271)*24;
        }
        int32_t audio[32],record[32];for(auto& v:audio)v=(int32_t)random();
        te_process(&state,&p,ring.data(),write,audio,record);
        for(unsigned i=0;i<16;++i) safe &= record[2*i]==record[2*i+1] &&
            std::abs(double(record[2*i])/q)<.59;
        std::copy(record,record+32,ring.begin()+write*2);write=(write+16)%TE_RING;
    }
    check("Rapid controls/full-scale input across three wraps retain bounded mono tape",safe,35000);
    return failures?1:0;
}
