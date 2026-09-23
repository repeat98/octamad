// md_profile: per-block cycle profile of the Machinedrum's two DSPs, run on
// the reference emulator (vendor/gearmulator-md-mm, JIT build with
// tools/patches/gearmulator-md-exechook.patch) against the user's own OS 1.63
// flash dump. GEARMULATOR_MDMM_BOUNDED_JIT=0 is forced so the scheduler runs
// one JIT block per exec() and every block passes the hook (the fork disables
// block linking and caps blocks at 32 instructions).
//
// Every scenario writes one file per DSP: lines of "pc count cycles words
// instructions" per JIT block that ran, keyed on its first address, with the
// cycles between its entry and the next block's entry (interrupts included;
// an idle loop's fast-forwarded cycles land on the idle loop's block).
//
//   md_profile <flash.bin> <outdir> [machine-id ...]
//
// Scenarios: "idle" (booted, nothing triggered), then per machine id: assign
// it to track 1 (SysEx ASSIGN MACHINE, 0x5B) and press TRIG 1 every 250 ms
// for 2 s; "load=<id,id,...>" assigns up to 16 tracks and presses all their
// trigs together on the same schedule. Rendering is Hardware::processAudio,
// as the fork's own tests do. Each file's header carries the peak work (all
// cycles minus the known wait loops) in any 10 ms window, per sample.

#include "mdLib/mddevice.h"
#include "mdLib/mdhardware.h"
#include "mdLib/mdpanel.h"
#include "mdLib/mdromloader.h"
#include "mdLib/mdtypes.h"

#include "baseLib/filesystem.h"
#include "synthLib/plugin.h"
#include "dsp56kEmu/dsp.h"
#include "dsp56kEmu/jitblockinfo.h"

#include <array>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <iostream>
#include <memory>
#include <string>
#include <vector>

namespace
{
	constexpr uint32_t g_pSize = 0x200000;
	constexpr uint32_t g_block = 441;			// 10 ms

	struct Profile
	{
		std::vector<uint64_t> count = std::vector<uint64_t>(g_pSize, 0);
		std::vector<uint64_t> cycles = std::vector<uint64_t>(g_pSize, 0);
		std::vector<bool> waitPc = std::vector<bool>(g_pSize, false);
		uint32_t lastPc = 0;
		uint64_t lastCycles = 0;
		bool valid = false;
		uint64_t outOfRange = 0;
		uint64_t total = 0, wait = 0;			// running, never reset
		uint64_t winTotal = 0, winWait = 0;		// at the current window's start
		uint64_t peakWork = 0;					// max work cycles in one window

		void reset()
		{
			std::fill(count.begin(), count.end(), 0);
			std::fill(cycles.begin(), cycles.end(), 0);
			valid = false;
			outOfRange = 0;
			peakWork = 0;
			winTotal = total;
			winWait = wait;
		}

		void endWindow()
		{
			peakWork = std::max(peakWork, (total - winTotal) - (wait - winWait));
			winTotal = total;
			winWait = wait;
		}
	};

	dsp56k::DSP* g_dsp[2] = {nullptr, nullptr};		// 0 = mixer (DSP1), 1 = producer (DSP2)
	Profile g_prof[2];

	void onExec(dsp56k::DSP* _dsp)
	{
		const int i = _dsp == g_dsp[0] ? 0 : 1;
		auto& p = g_prof[i];
		const auto pc = _dsp->getPC().toWord();
		const auto c = _dsp->getCycles();
		if(p.valid)
		{
			if(p.lastPc < g_pSize)
			{
				p.count[p.lastPc]++;
				p.cycles[p.lastPc] += c - p.lastCycles;
				if(p.waitPc[p.lastPc])
					p.wait += c - p.lastCycles;
			}
			else
				p.outOfRange++;
			p.total += c - p.lastCycles;
		}
		p.lastPc = pc;
		p.lastCycles = c;
		p.valid = true;
	}

	struct Rig
	{
		std::unique_ptr<md::Device> device;
		md::Hardware* hw = nullptr;
		std::array<std::vector<float>, 2> out;
		double sumSq = 0;
		uint64_t samples = 0;
		uint64_t total = 0;
		std::chrono::steady_clock::time_point start = std::chrono::steady_clock::now();

		void run(uint32_t _samples)
		{
			synthLib::TAudioOutputs outs{};
			for(size_t c = 0; c < out.size(); ++c)
				outs[c] = out[c].data();
			while(_samples)
			{
				const auto n = std::min(_samples, g_block);
				hw->processAudio(outs, n, 0);
				g_prof[0].endWindow();
				g_prof[1].endWindow();
				for(uint32_t s = 0; s < n; ++s)
					sumSq += out[0][s] * out[0][s] + out[1][s] * out[1][s];
				samples += n;
				_samples -= n;
				total += n;
				if(total % 44100 < n)
					std::fprintf(stderr, "[%6.1f s emulated, %6.1f s wall]\n", total / 44100.0,
						std::chrono::duration<double>(std::chrono::steady_clock::now() - start).count());
			}
		}

		void trig(int _track, bool _down)
		{
			const auto p = md::panelPacket(md::MachineModel::Machinedrum,
				static_cast<md::PanelControl>(static_cast<int>(md::PanelControl::Trigger1) + _track));
			if(!p)
			{
				std::cerr << "no panel mapping for trig " << _track + 1 << "\n";
				std::exit(1);
			}
			hw->sendPanelEvent(p->row, _down ? p->mask : 0);
		}

		void sysex(const std::vector<uint8_t>& _bytes)
		{
			synthLib::SMidiEvent e(synthLib::MidiEventSource::Host);
			e.assignRawData(_bytes.data(), _bytes.size(), synthLib::MidiEventSource::Host, 0);
			if(!hw->sendMidi(e))
			{
				std::cerr << "sysex not accepted\n";
				std::exit(1);
			}
		}
	};

	void dump(const std::string& _dir, const std::string& _name, const Rig& _rig)
	{
		for(int i = 0; i < 2; ++i)
		{
			const auto path = _dir + "/" + _name + (i ? ".producer.txt" : ".mixer.txt");
			FILE* f = std::fopen(path.c_str(), "w");
			if(!f)
			{
				std::cerr << "cannot write " << path << "\n";
				std::exit(1);
			}
			std::fprintf(f, "# samples %llu rms %.6f outOfRange %llu peakWorkPerSample %.1f\n",
				static_cast<unsigned long long>(_rig.samples),
				std::sqrt(_rig.sumSq / std::max<uint64_t>(1, 2 * _rig.samples)),
				static_cast<unsigned long long>(g_prof[i].outOfRange),
				g_prof[i].peakWork / static_cast<double>(g_block));
			for(uint32_t pc = 0; pc < g_pSize; ++pc)
			{
				if(!g_prof[i].count[pc])
					continue;
				const auto* info = g_dsp[i]->getJit().getBlockInfo(pc);
				std::fprintf(f, "%06x %llu %llu %u %u\n", pc,
					static_cast<unsigned long long>(g_prof[i].count[pc]),
					static_cast<unsigned long long>(g_prof[i].cycles[pc]),
					info ? info->memSize : 0u, info ? info->instructionCount : 0u);
			}
			std::fclose(f);
		}
		std::cout << _name << ": rms " << std::sqrt(_rig.sumSq / std::max<uint64_t>(1, 2 * _rig.samples)) << "\n";
	}

	// The 128x64 LCD as ASCII art, to see which screen the firmware is on.
	void lcd(const std::string& _dir, const std::string& _name, const Rig& _rig)
	{
		const auto fp = _rig.hw->getFrontPanelSnapshot();
		const auto path = _dir + "/" + _name + ".lcd.txt";
		FILE* f = std::fopen(path.c_str(), "w");
		if(!f)
			return;
		for(uint32_t y = 0; y < md::FrontPanel::g_lcdHeight; ++y)
		{
			for(uint32_t x = 0; x < md::FrontPanel::g_lcdWidth; ++x)
				std::fputc(fp.getLcdPixel(x, y) ? '#' : '.', f);
			std::fputc('\n', f);
		}
		std::fclose(f);
	}

	void begin(Rig& _rig)
	{
		g_prof[0].reset();
		g_prof[1].reset();
		_rig.sumSq = 0;
		_rig.samples = 0;
	}
}

int main(int _argc, char** _argv)
{
	setenv("GEARMULATOR_MDMM_BOUNDED_JIT", "0", 1);
	if(_argc < 3)
	{
		std::cerr << "usage: md_profile <flash.bin> <outdir> [machine-id ...]\n";
		return 2;
	}
	std::vector<uint8_t> firmware;
	if(!baseLib::filesystem::readFile(firmware, _argv[1])
		|| !md::RomLoader::isRomForModel(firmware, md::MachineModel::Machinedrum))
	{
		std::cerr << _argv[1] << ": not the MD OS 1.63 flash image the reference accepts\n";
		return 1;
	}
	const std::string outDir = _argv[2];

	synthLib::DeviceCreateParams params;
	params.romData = std::move(firmware);
	params.romName = _argv[1];
	params.customData = md::deviceCustomData(md::MachineModel::Machinedrum);

	Rig rig;
	rig.device = std::make_unique<md::Device>(params);
	if(!rig.device->isValid())
	{
		std::cerr << "device did not start\n";
		return 1;
	}
	for(auto& o : rig.out)
		o.assign(g_block, 0.0f);

	// A factory flash boots into the OS's first-run UW initialization and a
	// reboot prompt. Run it out and cold-boot the initialized image, the way
	// the fork's mdUwFirmwareTest does.
	if(rig.device->getHardware().isFactoryFlashInitializationExpected())
	{
		auto& init = rig.device->getHardware();
		for(uint32_t f = 0; f < 44100u * 18 && !init.isFactoryFlashReadyForReboot(); f += 128)
			init.advance(128);
		if(!init.isFactoryFlashReadyForReboot())
		{
			std::cerr << "first-run UW initialization never became reboot-ready\n";
			return 1;
		}
		std::vector<uint8_t> state;
		if(!rig.device->getState(state, synthLib::StateTypeGlobal))
		{
			std::cerr << "could not capture the initialized state\n";
			return 1;
		}
		auto prepared = md::Device::prepareState(rig.device->getPreparationContext(),
			state, synthLib::StateTypeGlobal);
		if(!prepared || !rig.device->commitPreparedState(*prepared))
		{
			std::cerr << "could not cold-boot the initialized state\n";
			return 1;
		}
		std::cout << "first-run UW initialization done, rebooted\n";
	}

	// The wait loops (measured 23 Sep 2026, docs/proposals/MACHINEDRUM_MACHINE.md
	// section 12): the producer's nop delay (P:100092..100098) and its port-C
	// poll (P:bb..bf), the mixer's DMA poll (P:3c..44).
	for(uint32_t pc = 0x100092; pc <= 0x100098; ++pc)
		g_prof[1].waitPc[pc] = true;
	for(uint32_t pc = 0xbb; pc <= 0xbf; ++pc)
		g_prof[1].waitPc[pc] = true;
	for(uint32_t pc = 0x3c; pc <= 0x44; ++pc)
		g_prof[0].waitPc[pc] = true;

	auto& hw = rig.device->getHardware();
	rig.hw = &hw;
	g_dsp[0] = &hw.getDspMixer().dsp();
	g_dsp[1] = &hw.getDspProducer().dsp();
	dsp56k::g_execHook = &onExec;

	// Boot until the firmware takes MIDI, then settle.
	uint32_t waited = 0;
	while(!hw.isFirmwareMidiReady() && waited < 44100 * 30)
	{
		rig.run(g_block);
		waited += g_block;
	}
	if(!hw.isFirmwareMidiReady())
	{
		std::cerr << "firmware never became MIDI-ready\n";
		return 1;
	}
	// MIDI-ready comes before the start-up animation and, after a first-run
	// initialization, PREPARING FLASH. Wait for the screen to hold still for
	// three seconds.
	{
		std::string last;
		int still = 0;
		uint32_t s = 0;
		for(; s < 180 && still < 3; ++s)
		{
			rig.run(44100);
			const auto fp = hw.getFrontPanelSnapshot();
			std::string cur;
			for(uint32_t y = 0; y < md::FrontPanel::g_lcdHeight; ++y)
				for(uint32_t x = 0; x < md::FrontPanel::g_lcdWidth; ++x)
					cur.push_back(fp.getLcdPixel(x, y) ? '#' : '.');
			still = (cur == last && cur.find('#') != std::string::npos) ? still + 1 : 0;
			last = cur;
		}
		if(still < 3)
		{
			std::cerr << "the screen never settled\n";
			return 1;
		}
		std::cout << "screen settled " << s << " s after MIDI-ready\n";
	}
	std::cout << "booted after " << waited / 44100.0 << " s\n";

	lcd(outDir, "booted", rig);
	begin(rig);
	rig.run(88200);
	dump(outDir, "idle", rig);

	// "load=<16 ids>": every track gets one machine, all sixteen fire together
	// every 250 ms for 2 s.
	int loads = 0;
	for(int a = 3; a < _argc; ++a)
	{
		const std::string arg = _argv[a];
		if(arg.rfind("load=", 0) == 0)
		{
			std::vector<uint8_t> ids;
			for(size_t pos = 5; pos < arg.size();)
			{
				const auto comma = arg.find(',', pos);
				ids.push_back(static_cast<uint8_t>(std::strtol(arg.substr(pos, comma - pos).c_str(), nullptr, 0)));
				if(comma == std::string::npos)
					break;
				pos = comma + 1;
			}
			for(size_t t = 0; t < ids.size() && t < 16; ++t)
			{
				rig.sysex({0xf0, 0x00, 0x20, 0x3c, 0x02, 0x00, 0x5b, static_cast<uint8_t>(t), ids[t], 0x00, 0xf7});
				rig.run(4410);
			}
			rig.run(22050);
			const auto lname = "load" + std::to_string(++loads);
			lcd(outDir, lname + ".assigned", rig);
			begin(rig);
			for(int hit = 0; hit < 8; ++hit)
			{
				for(size_t t = 0; t < ids.size() && t < 16; ++t)
					rig.trig(static_cast<int>(t), true);
				rig.run(441);
				for(size_t t = 0; t < ids.size() && t < 16; ++t)
					rig.trig(static_cast<int>(t), false);
				rig.run(11025 - 441);
			}
			dump(outDir, lname, rig);
			continue;
		}
		const auto id = static_cast<uint8_t>(std::strtol(_argv[a], nullptr, 0));
		rig.sysex({0xf0, 0x00, 0x20, 0x3c, 0x02, 0x00, 0x5b, 0x00, id, 0x00, 0xf7});
		rig.run(22050);
		char lname[32];
		std::snprintf(lname, sizeof(lname), "m%02x.assigned", id);
		lcd(outDir, lname, rig);
		begin(rig);
		for(int hit = 0; hit < 8; ++hit)
		{
			rig.trig(0, true);
			rig.run(441);
			rig.trig(0, false);
			rig.run(11025 - 441);
		}
		char name[32];
		std::snprintf(name, sizeof(name), "m%02x", id);
		dump(outDir, name, rig);
	}
	return 0;
}
