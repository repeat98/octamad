// FORCE FILENAME BPM, executed. The module's two live entry points are run
// under the ColdFire port against a fabricated sample settings record, and
// the tempo word (+0x114, BPM*24) is read back.
//
// Why a probe and not a render: this is ColdFire, not DSP, and the value it
// writes is a field in a record, not audio. The build's byte assertions
// prove the hooks LANDED; only this proves they COMPUTE. It also pins the
// stock facts the module stands on -- the explicit-tempo setter 0x40099090
// runs for real here, reciprocal table and all.
//
// Usage: ot_fnbpm_test [image]   (default out/mainos_bus.bin)
// SKIPs cleanly on an image that does not carry the module.
#include <cstdio>
#include <cstring>
#include <fstream>
#include <iterator>
#include <string>
#include <vector>
#include "machine.h"
#include "mc68k/Musashi/m68k.h"
#include "mc68k/cpuState.h"

namespace
{
	constexpr uint32_t FLAG        = 0x800000d4;	// the PERSONALIZE checkbox
	constexpr uint32_t BPM100_SITE = 0x40086b24;	// project [SAMPLE] BPMx100
	constexpr uint32_t BPM100_BACK = 0x40086b2e;
	constexpr uint32_t LOAD_SITE   = 0x400992ea;	// per-slot attribute init
	constexpr uint32_t LOAD_BACK   = 0x400992f0;

	constexpr uint32_t REC   = 0x47100000;	// a fabricated settings record
	constexpr uint32_t SP    = 0x47200000;
	constexpr uint32_t TEMPO = 0x114;

	int g_failures = 0;

	void check(const char* _what, const bool _ok, const char* _detail = "")
	{
		g_failures += !_ok;
		std::printf("  [%s] %s%s%s\n", _ok ? "PASS" : "FAIL", _what,
			*_detail ? "  " : "", _detail);
	}
}

int main(int argc, char** argv)
{
	const std::string path = argc > 1 ? argv[1] : "out/mainos_bus.bin";
	std::ifstream input(path, std::ios::binary);
	if(!input)
	{
		std::printf("SKIP: %s is not present (make bus REMIX=filename-bpm)\n", path.c_str());
		return 0;
	}
	std::vector<uint8_t> image((std::istreambuf_iterator<char>(input)), {});
	constexpr uint32_t imageBase = 0x40000400;
	const auto read32 = [&](const uint32_t address) {
		const auto i = address - imageBase;
		return (uint32_t(image[i]) << 24) | (uint32_t(image[i + 1]) << 16) |
		       (uint32_t(image[i + 2]) << 8) | uint32_t(image[i + 3]);
	};
	const auto isJmp = [&](const uint32_t address) {
		const auto i = address - imageBase;
		return image.size() > i + 6 && image[i] == 0x4e && image[i + 1] == 0xf9;
	};
	if(image.size() < 1112560 || !isJmp(BPM100_SITE) || !isJmp(LOAD_SITE))
	{
		std::printf("SKIP: %s is not a FORCE FILENAME BPM image\n", path.c_str());
		return 0;
	}
	const uint32_t bpm100Hook = read32(BPM100_SITE + 2);
	const uint32_t loadHook   = read32(LOAD_SITE + 2);
	std::printf("FORCE FILENAME BPM, executed (bpm100_hook 0x%08x, load_hook 0x%08x):\n",
		bpm100Hook, loadHook);

	// Run one hook over one name. `stored` is the tempo the stock path had
	// already produced -- the project's saved BPMx100 for the restore hook,
	// the half/double guess for the load hook -- so a result equal to it
	// means the module left stock alone.
	const auto run = [&](const uint32_t entry, const uint32_t back, const char* name,
	                     const uint32_t stored, const bool on) -> uint32_t {
		ot::Machine machine(image);
		auto* cpu = machine.getCpuState();
		machine.write32(FLAG, on ? 1 : 0);
		for(uint32_t i = 0; i < 0x200; i += 4)
			machine.write32(REC + i, 0);
		for(uint32_t i = 0; name[i]; ++i)
			machine.write8(REC + i, uint8_t(name[i]));
		machine.write32(REC + TEMPO, stored);
		// The trim words the explicit setter reads to derive +0x11c/+0x120:
		// a four-beat 120 BPM loop, 88,200 frames, untrimmed.
		machine.write32(REC + 0x12c, 0);
		machine.write32(REC + 0x130, 88200);
		machine.write32(REC + 0x134, 0);
		m68k_set_reg(cpu, M68K_REG_SP, SP);
		m68k_set_reg(cpu, M68K_REG_A2, REC);
		m68k_set_reg(cpu, M68K_REG_D0, stored);
		m68k_set_reg(cpu, M68K_REG_D5, 64);
		m68k_set_reg(cpu, M68K_REG_PC, entry);
		unsigned steps = 0;
		while(machine.pc() != back && steps++ < 200000)
			if(!machine.step()) break;
		if(machine.pc() != back)
		{
			std::printf("  [FAIL] '%s' never reached 0x%08x (stopped at 0x%08x: %s)\n",
				name, back, machine.pc(), machine.why().c_str());
			++g_failures;
			return 0;
		}
		return machine.read32(REC + TEMPO);
	};

	struct Case { const char* name; uint32_t want; const char* why; };
	// BPM*24 is the field's unit. 2880 = 120 BPM is "the stock value was
	// kept", the value fed in as `stored` below.
	const Case cases[] = {
		{"amen_170.wav",            4080, "a plain trailing number"},
		{"170_amen.wav",            4080, "a leading number"},
		{"loop_126.5.wav",          3036, "one decimal place, 126*24+12"},
		{"Break 087.wav",           2088, "a leading zero"},
		{"kick.wav",                2880, "no number: stock is kept"},
		{"sr44100_hit.wav",         2880, "44100 is outside 30..300"},
		{"clap_29.wav",             2880, "29 is below the tempo clamp"},
		{"x_301.wav",               2880, "301 is above the tempo clamp"},
		{"loop_01_128.wav",         3072, "the last in-range number wins"},
		{"2024_session_140.wav",    3360, "a year is out of range, 140 is not"},
		{"/AUDIO/170bpm/loop_90.wav", 2160, "the BASENAME, not the path"},
		{"128bpm.wav",              3072, "a number the stock guess cannot reach"},
	};

	for(const auto& c : cases)
	{
		const auto got = run(bpm100Hook, BPM100_BACK, c.name, 2880, true);
		char d[192];
		std::snprintf(d, sizeof d, "'%s' -> %u (want %u), %s", c.name, got, c.want, c.why);
		check("project restore", got == c.want, d);
	}

	// The checkbox off is a stock unit: every name keeps the stored tempo.
	bool offOk = true;
	for(const auto& c : cases)
		offOk &= run(bpm100Hook, BPM100_BACK, c.name, 2880, false) == 2880;
	check("checkbox off: every name keeps the project's tempo", offOk);

	// The load hook goes through the firmware's own explicit-tempo setter,
	// so it also proves +0x118 (the reciprocal) and +0x128 were written.
	{
		const auto got = run(loadHook, LOAD_BACK, "amen_170.wav", 2880, true);
		char d[96];
		std::snprintf(d, sizeof d, "-> %u (want 4080)", got);
		check("attribute init: 170 in the name beats the length guess", got == 4080, d);
	}
	{
		ot::Machine machine(image);
		auto* cpu = machine.getCpuState();
		machine.write32(FLAG, 1);
		for(uint32_t i = 0; i < 0x200; i += 4)
			machine.write32(REC + i, 0);
		const char* name = "amen_170.wav";
		for(uint32_t i = 0; name[i]; ++i)
			machine.write8(REC + i, uint8_t(name[i]));
		machine.write32(REC + TEMPO, 2880);
		machine.write32(REC + 0x12c, 0);
		machine.write32(REC + 0x130, 88200);
		machine.write32(REC + 0x134, 0);
		m68k_set_reg(cpu, M68K_REG_SP, SP);
		m68k_set_reg(cpu, M68K_REG_A2, REC);
		m68k_set_reg(cpu, M68K_REG_D5, 64);
		m68k_set_reg(cpu, M68K_REG_PC, loadHook);
		unsigned steps = 0;
		while(machine.pc() != LOAD_BACK && steps++ < 200000)
			if(!machine.step()) break;
		const auto recip = machine.read32(REC + 0x118);
		const auto mode = machine.read8(REC + 0x128);
		// 0x400abf38 is the stock reciprocal bank, indexed by tempo*24 - 720.
		const auto want = read32(0x400abf38 + (4080 - 720) * 4);
		char d[128];
		std::snprintf(d, sizeof d, "+0x118 = %u (bank says %u), +0x128 = %u",
			recip, want, mode);
		check("the setter wrote the derived fields too", recip == want && mode == 0, d);
		check("the displaced clr.l 1092(a2) was replayed",
			machine.read32(REC + 1092) == 0);
		char e[64];
		std::snprintf(e, sizeof e, "d1 = %u", m68k_get_reg(cpu, M68K_REG_D1));
		check("the displaced moveq #1,d1 was replayed",
			m68k_get_reg(cpu, M68K_REG_D1) == 1, e);
	}

	std::printf("%s\n", g_failures ? "FAILED" : "ALL GATES PASSED");
	return g_failures ? 1 : 0;
}
