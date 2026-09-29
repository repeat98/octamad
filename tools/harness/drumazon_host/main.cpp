// Offline VST3 reference host. Every output bus receives a real buffer.
// No device is opened and no sound is sent to the user's speakers.
#include <juce_audio_processors/juce_audio_processors.h>
#include <juce_audio_formats/juce_audio_formats.h>
#include <iostream>
#include <cstdlib>
#include <vector>
using namespace juce;
// Optional capture shape, from the environment so the argument list stays
// "plugin state output [name value]...": DRUMAZON_VEL (1..127, default 100),
// DRUMAZON_NOTES (comma-separated note-on sample positions, default 4410),
// DRUMAZON_SECONDS (default 3).
static std::vector<int> envList(const char* name,int fallback) {
    std::vector<int> out; const char* v=std::getenv(name);
    if(!v||!*v){out.push_back(fallback);return out;}
    for(auto& t:StringArray::fromTokens(String(v),",",""))out.push_back(t.getIntValue());
    return out;
}
struct Clock : AudioPlayHead {
    int64 sample=0;
    Optional<PositionInfo> getPosition() const override {
        PositionInfo p; p.setTimeInSamples(sample); p.setTimeInSeconds(sample/44100.0);
        p.setBpm(120.0); p.setPpqPosition(sample/22050.0); p.setTimeSignature(TimeSignature{4,4});
        p.setIsPlaying(true);return p;
    }
};
int main(int argc,char** argv) {
    if(argc<4) {std::cerr<<"usage: host plugin.vst3 init.state output.wav [parameter-name normalized-value]...\n";return 2;}
    ScopedJuceInitialiser_GUI gui;
    AudioPluginFormatManager formats; formats.addDefaultFormats();
    OwnedArray<PluginDescription> types;
    for(auto* f:formats.getFormats())f->findAllTypesForFile(types,argv[1]);
    if(types.isEmpty()){std::cerr<<"No VST3 instrument\n";return 2;}
    String error;auto p=formats.createPluginInstance(*types[0],44100,256,error);
    if(!p){std::cerr<<error<<"\n";return 2;}
    MemoryBlock state;
    if(!File(String(argv[2])).loadFileAsData(state))return 2;
    p->setStateInformation(state.getData(),int(state.getSize()));
    p->enableAllBuses();
    for(int i=0;i<p->getBusCount(false);++i)
        std::cout<<"bus "<<i<<" "<<p->getBus(false,i)->getName()<<" "<<p->getChannelCountOfBus(false,i)<<"\n";
    for(int i=4;i+1<argc;i+=2) {
        bool found=false;
        for(auto* v:p->getParameters())if(v->getName(128)==argv[i]){
            v->setValueNotifyingHost(String(argv[i+1]).getFloatValue());found=true;
            std::cout<<v->getName(128)<<"="<<v->getValue()<<" "<<v->getCurrentValueAsText()<<"\n";
        }
        if(!found){std::cerr<<"Unknown parameter "<<argv[i]<<"\n";return 2;}
    }
    Clock clock;p->setPlayHead(&clock);p->setNonRealtime(true);
    p->setRateAndBufferSizeDetails(44100,256);p->prepareToPlay(44100,256);
    int channels=jmax(2,jmax(p->getTotalNumOutputChannels(),p->getTotalNumInputChannels()));
    std::cout<<"channels "<<channels<<std::endl;
    const int velocity=jlimit(1,127,envList("DRUMAZON_VEL",100)[0]);
    const auto notes=envList("DRUMAZON_NOTES",4410);
    const int seconds=jmax(1,envList("DRUMAZON_SECONDS",3)[0]);
    AudioBuffer<float> block(channels,256),output(2,44100*seconds);output.clear();
    MidiBuffer midi;
    for(int n=0;n<output.getNumSamples();n+=256) {
        int count=jmin(256,output.getNumSamples()-n);block.clear();midi.clear();clock.sample=n;
        for(int at:notes)if(at>=n && at<n+256)
            midi.addEvent(MidiMessage::noteOn(1,36,uint8(velocity)),at-n);
        p->processBlock(block,midi);
        for(int c=0;c<2;++c)output.copyFrom(c,n,block,c,0,count);
    }
    p->releaseResources();p->setPlayHead(nullptr);
    WavAudioFormat wav;std::unique_ptr<FileOutputStream> stream(File(String(argv[3])).createOutputStream());
    if(!stream||!stream->openedOk())return 2;
    stream->setPosition(0);stream->truncate();
    std::unique_ptr<AudioFormatWriter> writer(wav.createWriterFor(stream.release(),44100,2,32,{},0));
    if(!writer||!writer->writeFromAudioSampleBuffer(output,0,output.getNumSamples()))return 2;
    std::cout<<"peak "<<output.getMagnitude(0,output.getNumSamples())<<std::endl;
}
