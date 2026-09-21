// Offline black-box reference host for the user's installed VintageVerb AU.
// No audio device, GUI, preset files or plugin code inspection. macOS only.
// Build: clang++ -std=c++17 tools/harness/au_reference.cpp -framework AudioToolbox
//        -framework CoreFoundation -o out/vintage_study/au_reference
// Usage: au_reference [--set PARAM_ID NORMALIZED_VALUE] [--in mono_q23.raw --out stereo_float.raw]
#include <AudioToolbox/AudioToolbox.h>
#include <CoreFoundation/CoreFoundation.h>
#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <string>
#include <vector>

static void check(OSStatus s, const char* what) {
    if (s) { std::fprintf(stderr, "%s: OSStatus %d\n", what, int(s)); std::exit(1); }
}
static std::string str(CFStringRef s) {
    char b[2048] = {};
    if (s) CFStringGetCString(s, b, sizeof b, kCFStringEncodingUTF8);
    return b;
}
struct Input { std::vector<int32_t> samples; size_t pos = 0; };
static OSStatus input(void* ctx, AudioUnitRenderActionFlags*, const AudioTimeStamp*,
                      UInt32, UInt32 count, AudioBufferList* data) {
    auto& in = *static_cast<Input*>(ctx);
    for (UInt32 c=0; c<data->mNumberBuffers; ++c) {
        auto* p = static_cast<float*>(data->mBuffers[c].mData);
        if (!p) return kAudio_ParamError;
        for (UInt32 n=0; n<count; ++n)
            p[n] = in.pos+n < in.samples.size() ? in.samples[in.pos+n]/8388608.0f : 0.0f;
        data->mBuffers[c].mDataByteSize = count*sizeof(float);
    }
    in.pos += count;
    return noErr;
}
int main(int argc, char** argv) {
    std::string source, dest;
    std::vector<std::pair<AudioUnitParameterID,float>> params;
    for (int i=1; i<argc; ++i) {
        const std::string opt=argv[i];
        if (opt=="--set" && i+2<argc) {
            const auto id=static_cast<AudioUnitParameterID>(std::stoul(argv[++i]));
            const float value=std::stof(argv[++i]);
            params.emplace_back(id,value);
        } else if (opt=="--in" && i+1<argc) source=argv[++i];
        else if (opt=="--out" && i+1<argc) dest=argv[++i];
        else { std::fprintf(stderr,"invalid/incomplete option: %s\n",opt.c_str()); return 2; }
    }
    AudioComponentDescription d={'aufx','vee3','oDin',0,0};
    auto component=AudioComponentFindNext(nullptr,&d);
    if (!component) { std::fprintf(stderr,"VintageVerb Audio Unit is not installed\n"); return 1; }
    UInt32 version=0;
    check(AudioComponentGetVersion(component,&version),"component version");
    std::printf("# component_version\t%u.%u.%u\n",unsigned(version>>16),
                unsigned((version>>8)&255),unsigned(version&255));
    AudioUnit unit=nullptr;
    check(AudioComponentInstanceNew(component,&unit),"instantiate AU");
    AudioStreamBasicDescription fmt={};
    fmt.mSampleRate=44100; fmt.mFormatID=kAudioFormatLinearPCM;
    fmt.mFormatFlags=kAudioFormatFlagsNativeFloatPacked|kAudioFormatFlagIsNonInterleaved;
    fmt.mBytesPerPacket=fmt.mBytesPerFrame=4; fmt.mFramesPerPacket=1;
    fmt.mChannelsPerFrame=2; fmt.mBitsPerChannel=32;
    check(AudioUnitSetProperty(unit,kAudioUnitProperty_StreamFormat,kAudioUnitScope_Input,0,&fmt,sizeof fmt),"input format");
    check(AudioUnitSetProperty(unit,kAudioUnitProperty_StreamFormat,kAudioUnitScope_Output,0,&fmt,sizeof fmt),"output format");
    UInt32 frames=512;
    check(AudioUnitSetProperty(unit,kAudioUnitProperty_MaximumFramesPerSlice,kAudioUnitScope_Global,0,&frames,sizeof frames),"max frames");
    Input in;
    AURenderCallbackStruct cb={input,&in};
    check(AudioUnitSetProperty(unit,kAudioUnitProperty_SetRenderCallback,kAudioUnitScope_Input,0,&cb,sizeof cb),"input callback");
    check(AudioUnitInitialize(unit),"initialize AU");
    for (auto p:params) check(AudioUnitSetParameter(unit,p.first,kAudioUnitScope_Global,0,p.second,0),"set parameter");
    UInt32 size=0; Boolean writable=false;
    check(AudioUnitGetPropertyInfo(unit,kAudioUnitProperty_ParameterList,kAudioUnitScope_Global,0,&size,&writable),"parameter list size");
    std::vector<AudioUnitParameterID> ids(size/sizeof(AudioUnitParameterID));
    check(AudioUnitGetProperty(unit,kAudioUnitProperty_ParameterList,kAudioUnitScope_Global,0,ids.data(),&size),"parameter list");
    std::puts("id\tname\tvalue\tmin\tmax\tdisplay");
    for (auto id:ids) {
        AudioUnitParameterInfo info={}; size=sizeof info;
        check(AudioUnitGetProperty(unit,kAudioUnitProperty_ParameterInfo,kAudioUnitScope_Global,id,&info,&size),"parameter info");
        Float32 value; check(AudioUnitGetParameter(unit,id,kAudioUnitScope_Global,0,&value),"parameter value");
        AudioUnitParameterStringFromValue display={id,&value,nullptr}; size=sizeof display;
        auto status=AudioUnitGetProperty(unit,kAudioUnitProperty_ParameterStringFromValue,kAudioUnitScope_Global,0,&display,&size);
        const auto name=(info.flags&kAudioUnitParameterFlag_HasCFNameString)?str(info.cfNameString):std::string(info.name);
        std::printf("%u\t%s\t%.9g\t%.9g\t%.9g\t%s\n",unsigned(id),name.c_str(),value,info.minValue,info.maxValue,
                    status==noErr?str(display.outString).c_str():"");
        if (status==noErr && display.outString) CFRelease(display.outString);
        if ((info.flags&kAudioUnitParameterFlag_CFNameRelease) && info.cfNameString) CFRelease(info.cfNameString);
    }
    if (!source.empty()) {
        if (dest.empty()) { std::fprintf(stderr,"--out required with --in\n"); return 2; }
        std::ifstream f(source,std::ios::binary|std::ios::ate);
        if (!f) { std::fprintf(stderr,"cannot read source\n"); return 2; }
        const auto length=f.tellg();
        if (length<0 || length%4) return 2;
        in.samples.resize(size_t(length)/4); f.seekg(0);
        f.read(reinterpret_cast<char*>(in.samples.data()),length);
        std::ofstream out(dest,std::ios::binary);
        if (!out) return 2;
        std::vector<float> left(frames),right(frames);
        struct StereoBuffers { UInt32 count; AudioBuffer buffer[2]; } buffers={2,{{1,frames*4,left.data()},{1,frames*4,right.data()}}};
        for (size_t at=0;at<in.samples.size();at+=frames) {
            auto n=static_cast<UInt32>(std::min<size_t>(frames,in.samples.size()-at));
            buffers.buffer[0].mDataByteSize=buffers.buffer[1].mDataByteSize=n*4;
            AudioTimeStamp stamp={}; stamp.mSampleTime=double(at); stamp.mFlags=kAudioTimeStampSampleTimeValid;
            AudioUnitRenderActionFlags flags=0;
            check(AudioUnitRender(unit,&flags,&stamp,0,n,reinterpret_cast<AudioBufferList*>(&buffers)),"render");
            for (UInt32 j=0;j<n;++j) { out.write(reinterpret_cast<char*>(&left[j]),4); out.write(reinterpret_cast<char*>(&right[j]),4); }
        }
        if (!out) return 2;
    }
    check(AudioUnitUninitialize(unit),"uninitialize AU");
    check(AudioComponentInstanceDispose(unit),"dispose AU");
}
