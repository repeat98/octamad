// The peripheral gate: every rule these models carry, checked against the
// value route A's own model produces.
//
// The rules here are not obvious and several are counter-intuitive; each one
// below exists because getting it wrong produced a specific, silent failure in
// route A first (`docs/firmware/RTOS_FORK.md` §8.2, §4). Testing them is how a
// translation stays a translation rather than a rewrite.
#include <cstdio>
#include <cmath>

#include "card.h"
#include "periph.h"
#include "usb.h"

#include <map>
#include <string>
#include <vector>

namespace
{
	int g_failures = 0;

	void check(const char* _what, const bool _ok, const char* _detail = "")
	{
		if(!_ok)
			++g_failures;
		std::printf("  [%s] %s%s%s\n", _ok ? "PASS" : "FAIL", _what,
			*_detail ? "  " : "", _detail);
	}

	void checkEq(const char* _what, const uint64_t _got, const uint64_t _want)
	{
		char d[128];
		std::snprintf(d, sizeof d, "got %#llx want %#llx",
			static_cast<unsigned long long>(_got), static_cast<unsigned long long>(_want));
		check(_what, _got == _want, d);
	}
}

int main()
{
	std::printf("peripheral gate (models translated from tools/emu/emu_rtos.py):\n");

	// ---- PIT -------------------------------------------------------------
	{
		// Route A's PIT0: the kernel's 5 ms tick. At the default 264 MHz
		// prescaler input the period is 220.5 samples, which is what makes the
		// sequencer's tick count come out right (M6a's gate: 28 ticks in 400
		// frames, matching the cold run).
		ot::Pit pit("PIT0", 264e6);
		// prescaler 2^11, PMR such that the period is ~220.5 samples:
		//   (pmr+1) * 2048 / 264e6 * 44100 = 220.5  ->  pmr+1 = 645
		pit.write(2, 2, 644, 0.0);						// PMR
		pit.write(0, 2, ot::Pit::EN | ot::Pit::RLD | ot::Pit::PIE | (11u << 8), 0.0);
		const auto period = pit.periodSamples();
		char d[128];
		std::snprintf(d, sizeof d, "period %.2f samples (want ~220.5)", period);
		check("PIT period comes from (PMR+1) << prescaler", std::fabs(period - 220.5) < 0.5, d);

		check("no expiry before the period is up", pit.advance(period - 1.0) == 0);
		check("one expiry at the period", pit.advance(period + 0.1) == 1);
		check("PIF raises the line while PIE is set", pit.irq());

		// PIF is WRITE-1-TO-CLEAR: writing it back clears it, and the line
		// drops. An emulator that treats the write as "set" leaves the ISR
		// re-entering forever.
		pit.write(0, 2, ot::Pit::EN | ot::Pit::RLD | ot::Pit::PIE | ot::Pit::PIF | (11u << 8), period);
		check("PIF is write-1-to-clear", !pit.irq());

		// RLD: the timer reloads, so a long jump forward fires once per period
		// rather than once in total.
		const auto n = pit.advance(period * 4.5);
		std::snprintf(d, sizeof d, "fired %u times over 3.5 periods", n);
		check("RLD reloads (a jump forward fires every period)", n >= 3 && n <= 4, d);
	}

	// ---- DMA timers ------------------------------------------------------
	{
		// DTIM1 as the firmware programs it (0x40040498..0x400404a6): DTRR
		// 68750 as a long, then DTMR 0x1d as a word = RST, bus/16, restart,
		// reference interrupt. Off the 132 MHz bus that is 68751 * 16 / 132e6
		// = 8.333 ms = 367.5 samples: the LED countdown's tick (12 Sep 2026).
		ot::DmaTimer t("DTIM1", 132e6);
		t.write(4, 4, 68750, 0.0);
		t.write(0, 2, 0x1d, 0.0);
		const auto period = t.periodSamples();
		char d[128];
		std::snprintf(d, sizeof d, "period %.3f samples (want ~367.5)", period);
		check("DTIM period is (DTRR+1) * 16 / bus clock in restart mode", std::fabs(period - 367.5) < 0.01, d);
		check("no reference match before DTRR is reached", t.advance(period - 1.0) == 0);
		{
			const auto c = t.count(period / 2.0);
			std::snprintf(d, sizeof d, "count %u at half a period (want 34375 +-1)", c);
			check("DTCN counts from 0 at the programmed rate", c >= 34374 && c <= 34376, d);
		}
		check("one match at the reference", t.advance(period + 0.1) == 1);
		check("REF raises the line while ORRI is set", t.irq());
		checkEq("DTER reads REF as bit 1 (byte at +3)", t.read(3, 1, period + 0.1), 2);
		checkEq("a long read at +0 is DTMR:DTXMR:DTER", t.read(0, 4, period + 0.1), (0x1du << 16) | 2);

		// The handler's acknowledgement: `moveb #2, DTER`. Write-1-to-clear,
		// and it must not re-arm or disturb the count (a second match a few
		// instructions later would double every tick).
		t.write(3, 1, 2, period + 0.2);
		check("DTER is write-1-to-clear and the line drops", !t.irq());
		check("the acknowledgement does not fire the match again", t.advance(period + 5.0) == 0);

		// Restart mode reloads: a jump forward fires once per period.
		const auto n = t.advance(period * 4.6);
		std::snprintf(d, sizeof d, "fired %u times over ~3.5 more periods", n);
		check("restart mode fires every period", n >= 3 && n <= 4, d);

		// DTIM2's shape (0x40040430, and the handler 0x40040ac6..0x40040b02):
		// bus/1, FREE-RUN, DTRR 132,000,000 = one second; after a match the
		// count keeps going, so the next match is a 2^32 wrap away unless the
		// handler clears DTCN (any write) and reprograms DTRR -- which it does.
		ot::DmaTimer s("DTIM2", 132e6);
		s.write(4, 4, 132000000, 0.0);
		s.write(0, 2, 0x13, 0.0);
		check("free-run: no match before one second", s.advance(44100.0 - 1.0) == 0);
		check("free-run: the match at one second", s.advance(44100.0 + 0.5) == 1 && s.irq());
		s.write(3, 1, 2, 44101.0);
		check("free-run: no second match until the 2^32 wrap", s.advance(44100.0 * 3.0) == 0);
		s.write(0xc, 4, 0, 44100.0 * 3.0);		// the handler: clrl DTCN
		s.write(4, 4, 13200000, 44100.0 * 3.0);	// ... then a 0.1 s reference
		check("a DTCN write restarts the count", s.count(44100.0 * 3.0) == 0);
		check("the reprogrammed reference matches 0.1 s later",
			s.advance(44100.0 * 3.0 + 4409.0) == 0 && s.advance(44100.0 * 3.0 + 4411.0) == 1);

		// DTIM3 (DTMR 0x0b: bus/1, restart, no ORRI, DTRR untouched) is a
		// timestamp: it counts at 132 MHz, interrupts nothing and offers the
		// idle skip no expiry. DTIM0 (DTMR 7) counts the DTIN pin: no model,
		// it holds at 0.
		ot::DmaTimer u("DTIM3", 132e6);
		u.write(0, 2, 0x0b, 0.0);
		{
			const auto c = u.count(44100.0);
			std::snprintf(d, sizeof d, "count %u after a second (want 132,000,000 +-1)", c);
			check("a free-running bus-clock timestamp reads 132,000,000 after a second", c >= 131999999 && c <= 132000001, d);
		}
		double e;
		check("without ORRI it neither interrupts nor wakes the idle skip", u.advance(44100.0 * 40.0) >= 1 && !u.irq() && !u.nextExpiry(e));
		ot::DmaTimer z("DTIM0", 132e6);
		z.write(0, 2, 7, 0.0);
		checkEq("a DTIN-clocked channel holds at 0", z.count(44100.0), 0);
	}

	// ---- INTC ------------------------------------------------------------
	{
		ot::Intc intc("INTC0", 64);

		// A source is only deliverable once its ICR gives it a level: ICR 0 is
		// never delivered, whatever else is true.
		bool line = true;
		intc.addLine(1, [&]{ return line; });
		intc.write(0x1d, 1, 1);						// CIMR 1: unmask source 1
		check("a source with ICR 0 is never delivered", intc.pending().empty());

		intc.write(0x40 + 1, 1, 5);					// ICR1 = level 5
		const auto p = intc.pending();
		check("unmasked, with a level, it is delivered", p.size() == 1 && p[0].second == 1);

		intc.write(0x1c, 1, 1);						// SIMR 1: mask it again
		check("masked, it is not", intc.pending().empty());

		// ⚠️ THE RULE THAT COST 400 SILENT FRAMES: a FORCED source ignores the
		// mask entirely (MCF54455RM §17.2.3). The sequencer tick is source 32,
		// ICR 3, and nothing in the image ever unmasks it -- masking it here
		// leaves the sequencer dead.
		intc.write(0x40 + 32, 1, 3);				// ICR32 = level 3
		intc.write(0x1c, 1, 32);					// and MASK source 32
		intc.write(0x10, 4, 1u);					// INTFRCH bit 0 = source 32
		bool forcedDelivered = false;
		for(const auto& e : intc.pending())
			if(e.second == 32)
				forcedDelivered = true;
		check("a FORCED source is delivered THROUGH the mask (RM 17.2.3)", forcedDelivered);

		// MASKALL, and CIMR clearing it: inferred in route A, and the reason is
		// that nothing in the image writes IMRH/IMRL at all.
		ot::Intc other("INTC1", 128);
		other.addLine(2, []{ return true; });
		other.write(0x40 + 2, 1, 4);
		other.write(0x1c, 1, 0x40);					// SIMR 0x40: mask everything
		check("SIMR 0x40 masks all", other.pending().empty());
		other.write(0x1d, 1, 2);					// CIMR 2
		check("CIMR clears MASKALL with it (inferred)", !other.pending().empty());

		// Highest level first: the run loop delivers the head of this list.
		ot::Intc pri("INTC0", 64);
		pri.addLine(3, []{ return true; });
		pri.addLine(4, []{ return true; });
		pri.write(0x40 + 3, 1, 2);
		pri.write(0x40 + 4, 1, 6);
		pri.write(0x1d, 1, 3);
		pri.write(0x1d, 1, 4);
		const auto order = pri.pending();
		check("pending() is highest level first",
			order.size() == 2 && order[0].second == 4 && order[1].second == 3);

		// IPR reads back what is asserted, which is what the firmware polls.
		checkEq("IPRL reads back the asserted sources", pri.read(0x04, 4), (1u << 3) | (1u << 4));
	}

	// ---- eDMA ------------------------------------------------------------
	// The three completion rules. Each wrong version below is one route A
	// actually shipped, with the symptom it produced (RTOS_FORK.md §8.1), so
	// these are negative controls and not decoration.
	{
		const uint32_t tcd = ot::Edma::g_tcd;
		const auto csrAddr = [tcd](uint32_t ch) { return tcd + ch * 32 + 0x1e; };
		const auto saddr   = [tcd](uint32_t ch) { return tcd + ch * 32 + 0x00; };
		const auto daddr   = [tcd](uint32_t ch) { return tcd + ch * 32 + 0x10; };

		// RULE 1: a CSR.START of a HOST-PORT channel completes at the DSP's
		// NEXT 16-sample boundary, not instantly and not at kick + 16.
		{
			ot::Edma e;
			e.write(daddr(1), 4, 0x2000001c, false);		// ch1: host port -> RAM
			e.setBoundary(16.0);
			e.write(csrAddr(1), 2, ot::Edma::START | ot::Edma::INTMAJOR, false);
			check("a host-port START does NOT complete at once",
				!(e.read(csrAddr(1), 2) & ot::Edma::DONE) && !e.irq(1));
			e.advance(5.0);
			check("... nor part-way through the frame", !e.irq(1));
			// ❌ "kick + 16": kicked at 5, that version completed at 21 and
			// the period came out 18.5 samples, dropping every sixth frame.
			e.advance(15.9);
			check("... nor at kick + 16 (that gave an 18.5-sample period)", !e.irq(1));
			e.advance(16.0);
			check("... it completes AT the boundary", e.irq(1));
			checkEq("... and DONE is set", e.read(csrAddr(1), 2) & ot::Edma::DONE, ot::Edma::DONE);
		}

		// RULE 2: an SSRT is a control transfer over the same host port and
		// completes AT ONCE, even though the channel looks paced.
		{
			ot::Edma e;
			e.write(saddr(0), 4, 0x2000001c, false);
			e.write(csrAddr(0), 2, ot::Edma::INTMAJOR, false);	// no START bit
			e.setBoundary(16.0);
			e.write(ot::Edma::g_base + ot::Edma::SSRT, 1, 0, false);
			check("an SSRT completes at once, host port or not", e.irq(0));
		}

		// RULE 3: a memory-to-memory START completes at once -- the caller
		// busy-waits on it at 0x400035a8 and holding it for a frame spun
		// forever.
		{
			ot::Edma e;
			e.write(saddr(2), 4, 0x4f502c10, false);			// the delay ring
			e.write(daddr(2), 4, 0x46000000, false);
			e.setBoundary(16.0);
			e.write(csrAddr(2), 2, ot::Edma::START | ot::Edma::INTMAJOR, false);
			check("a memory-to-memory START completes at once", e.irq(2));
		}

		// THE CHAIN, which is the audio path: ch1 (0x621) links to ch6, ch6
		// (0x720) links to ch7, ch7 (0x0002) raises source 15. It is ONE
		// event at the boundary, not three -- a linked channel is a burst and
		// completes with its parent.
		{
			ot::Edma e;
			e.write(daddr(1), 4, 0x2000001c, false);
			e.write(csrAddr(6), 2, 0x0720, false);				// link to ch7
			e.write(csrAddr(7), 2, 0x0002, false);				// INTMAJOR, no link
			e.setBoundary(16.0);
			e.write(csrAddr(1), 2, 0x0621, false);				// START|MAJORELINK|link ch6
			check("the chain has not fired before the boundary", !e.irq(7));
			e.advance(16.0);
			// ✅ Only ch7 raises a line: 0x621 and 0x720 have no INTMAJOR, and
			// channel 7 is INTC0 source 8 + 7 = 15, which is exactly the
			// source route A names for the end of this chain.
			check("ch1 -> ch6 -> ch7 complete together, and only ch7 raises a line",
				e.irq(7) && !e.irq(1) && !e.irq(6));
			checkEq("the whole chain is one boundary event, 3 starts", e.started(), 3);
		}

		// CINT and CDNE, the acks.
		{
			ot::Edma e;
			e.write(saddr(3), 4, 0x46000000, false);
			e.write(daddr(3), 4, 0x46100000, false);
			e.write(csrAddr(3), 2, ot::Edma::START | ot::Edma::INTMAJOR, false);
			check("INTMAJOR holds the line until CINT", e.irq(3));
			e.write(ot::Edma::g_base + ot::Edma::CINT, 1, 3, false);
			check("CINT drops it", !e.irq(3));
			checkEq("DONE survives CINT", e.read(csrAddr(3), 2) & ot::Edma::DONE, ot::Edma::DONE);
			e.write(ot::Edma::g_base + ot::Edma::CDNE, 1, 3, false);
			checkEq("CDNE clears DONE", e.read(csrAddr(3), 2) & ot::Edma::DONE, 0);
		}
		{
			ot::Edma e;
			for(uint32_t ch : {4u, 5u})
			{
				e.write(saddr(ch), 4, 0x46000000, false);
				e.write(csrAddr(ch), 2, ot::Edma::START | ot::Edma::INTMAJOR, false);
			}
			check("two lines up", e.irq(4) && e.irq(5));
			e.write(ot::Edma::g_base + ot::Edma::CINT, 1, 0x40, false);
			check("CINT 0x40 clears them all", !e.irq(4) && !e.irq(5));
		}

		// A REPLAYED write is the boot's, not the firmware's: it must set the
		// register state and start NOTHING. Same rule the UART and the PIT
		// carry, and the reason `install` can seed from the boot's log.
		{
			ot::Edma e;
			e.write(saddr(8), 4, 0x46000000, true);
			e.write(csrAddr(8), 2, ot::Edma::START | ot::Edma::INTMAJOR, true);
			check("a replayed START does not run the channel", !e.irq(8));
			checkEq("... but the CSR is stored", e.read(csrAddr(8), 2) & ot::Edma::START, ot::Edma::START);
		}

		// A channel whose TCD does not ask for an interrupt must not raise
		// one: ch0 and ch1 carry INTMAJOR from the boot, and route A's note
		// is that nothing in the model asserts a source the TCD did not ask
		// for.
		{
			ot::Edma e;
			e.write(saddr(9), 4, 0x46000000, false);
			e.write(csrAddr(9), 2, ot::Edma::START, false);		// no INTMAJOR
			check("no INTMAJOR, no line", !e.irq(9));
		}
	}

	// ---- the ATA card ----------------------------------------------------
	// The task-file model. The image here is synthetic -- a real card image is
	// built by route A's own Python (`emu_rtos.stage_project`) and read from
	// disk, so the two emulators are looking at identical media.
	{
		std::vector<uint8_t> img(64 * ot::AtaCard::g_sector);
		for(size_t i = 0; i < img.size(); ++i)
			img[i] = static_cast<uint8_t>(i * 7 + (i >> 9));
		ot::AtaCard c(img);
		const uint32_t b = ot::AtaCard::g_base;	// offsets are window-relative
		(void)b;

		checkEq("the image is 64 sectors", c.totalSectors(), 64);

		// IDENTIFY: the words the driver's variant detection reads. Word 49
		// bit 8 CLEAR and word 53 zero are what keep it on the PIO path and
		// stop it programming the on-chip DMA channel.
		c.write(ot::AtaCard::R_CMD, 1, 0xec);
		check("IDENTIFY raises DRQ", (c.status() & ot::AtaCard::ST_DRQ) != 0);
		{
			const auto w = ot::AtaCard::identifyWords(64);
			checkEq("word 0 is the CF signature", w[0], 0x848a);
			checkEq("word 49: LBA supported, DMA bit CLEAR", w[49] & 0x0100, 0);
			checkEq("word 53 is zero, so words 54-58/64-70 are 'not valid'", w[53], 0);
			checkEq("words 60/61 carry the sector count", (w[61] << 16) | w[60], 64);
		}
		// The data register streams the buffer and drops DRQ at the end.
		size_t n = 0;
		while(c.status() & ot::AtaCard::ST_DRQ)
		{
			c.read(ot::AtaCard::R_DATA, 2);
			if(++n > 512)
				break;
		}
		checkEq("IDENTIFY streams exactly 256 words", n, 256);

		// READ SECTORS: count 0 means 256 in the TASK FILE.
		c.write(ot::AtaCard::R_LBA0, 1, 2);
		c.write(ot::AtaCard::R_COUNT, 1, 3);
		c.write(ot::AtaCard::R_CMD, 1, 0x20);
		checkEq("READ logs its LBA and count", c.log().back().lba, 2);
		checkEq("... and its count", c.log().back().count, 3);
		checkEq("... and the sector tally follows it", c.sectorsRead(), 3);
		{
			const auto first = c.read(ot::AtaCard::R_DATA, 2);
			const size_t o = 2 * ot::AtaCard::g_sector;
			checkEq("the data register returns the image, big-endian on the bus",
				first, static_cast<uint32_t>((img[o] << 8) | img[o + 1]));
		}

		// WRITE SECTORS: one sector streamed through the data register lands
		// in the image, and DRQ drops when the last one is absorbed.
		{
			ot::AtaCard w(img);
			w.write(ot::AtaCard::R_LBA0, 1, 5);
			w.write(ot::AtaCard::R_COUNT, 1, 1);
			w.write(ot::AtaCard::R_CMD, 1, 0x30);
			check("WRITE raises DRQ", (w.status() & ot::AtaCard::ST_DRQ) != 0);
			for(size_t i = 0; i < ot::AtaCard::g_sector / 2; ++i)
				w.write(ot::AtaCard::R_DATA, 2, 0xbeef);
			checkEq("one sector absorbed", w.sectorsWritten(), 1);
			check("DRQ drops when the count is exhausted",
				(w.status() & ot::AtaCard::ST_DRQ) == 0);
			// and it is readable back
			w.write(ot::AtaCard::R_LBA0, 1, 5);
			w.write(ot::AtaCard::R_COUNT, 1, 1);
			w.write(ot::AtaCard::R_CMD, 1, 0x20);
			checkEq("the written sector reads back", w.read(ot::AtaCard::R_DATA, 2), 0xbeef);
		}

		// An unsupported command ABORTs rather than being ignored: the
		// firmware checks the error register, and a silent success here would
		// send the storage stack down a path that never happened.
		c.write(ot::AtaCard::R_CMD, 1, 0x99);
		check("an unknown command sets ABRT and the error bit",
			(c.status() & 1) != 0 && c.log().back().what.rfind("UNSUPPORTED", 0) == 0);
	}


	// ---- USB device controller ------------------------------------------
	// The rules the firmware's driver and the bench depend on (usb.h), on a
	// fake guest memory: queue heads and transfer descriptors laid out the
	// way usb_dev_bringup (0x4001d630) and usb_ep0_send (0x4001d498) lay
	// them out, big-endian, at the firmware's own addresses.
	{
		std::map<uint32_t, uint8_t> mem;
		auto rd = [&](uint32_t a) { auto it = mem.find(a); return it == mem.end() ? uint8_t(0) : it->second; };
		auto wr = [&](uint32_t a, uint8_t v) { mem[a] = v; };
		auto st32 = [&](uint32_t a, uint32_t v) { for(int i = 0; i < 4; ++i) mem[a + i] = uint8_t(v >> (24 - 8 * i)); };
		auto ld32 = [&](uint32_t a) { uint32_t v = 0; for(int i = 0; i < 4; ++i) v = (v << 8) | rd(a + i); return v; };
		ot::UsbDevice u(rd, wr);
		std::vector<std::string> replies;
		auto reply = [&](const std::string& s) { replies.push_back(s); };
		using U = ot::UsbDevice;

		// OTGSC: the session is always valid; BSVIS latches on the enable EDGE
		// and clears by writing 1, and a rewrite with BSVIE still set does not
		// re-latch (the interrupt storm octemu's first model made).
		check("OTGSC reads B-session valid with nothing written", (u.read(U::R_OTGSC, 4) & U::OTGSC_BSV) != 0);
		check("no interrupt before the driver enables anything", !u.irq());
		u.write(U::R_OTGSC, 4, U::OTGSC_BSVIE, false);
		check("BSVIE enable edge latches BSVIS and interrupts", (u.read(U::R_OTGSC, 4) & U::OTGSC_BSVIS) && u.irq());
		u.write(U::R_OTGSC, 4, U::OTGSC_BSVIE | U::OTGSC_BSVIS, false);
		check("writing 1 to BSVIS clears it and the interrupt", !(u.read(U::R_OTGSC, 4) & U::OTGSC_BSVIS) && !u.irq());
		u.write(U::R_OTGSC, 4, U::OTGSC_BSVIE, false);
		check("a rewrite with BSVIE already set does not re-latch", !u.irq());

		// The bring-up, as replayed from the boot's writes: values only.
		u.write(U::R_USBMODE, 4, 0x0e, true);
		u.write(U::R_EPLISTADDR, 4, 0x4ec94800, true);
		u.write(U::R_USBINTR, 4, 0x57, true);
		u.write(U::R_USBCMD, 4, 0x1, true);
		checkEq("replayed registers read back", u.read(U::R_EPLISTADDR, 4), 0x4ec94800);
		check("no host connected: PORTSC1 is whatever was written", u.read(U::R_PORTSC1, 4) == 0);

		// A SETUP lands wire-reversed per dword in the EP0 OUT dQH's +0x28
		// buffer, sets EPSETUPSR bit 0 and USBSTS.UI, and interrupts (UI is
		// enabled in 0x57).
		u.command("setup 8006000100001200", reply);
		check("setup answers ok", !replies.empty() && replies.back() == "ok\n");
		checkEq("SETUP dword 0 wire-reversed", ld32(0x4ec94800 + 0x28), 0x01000680);
		checkEq("SETUP dword 1 wire-reversed", ld32(0x4ec94800 + 0x2c), 0x00120000);
		checkEq("EPSETUPSR bit 0", u.read(U::R_EPSETUPSR, 4), 1);
		check("USBSTS.UI + interrupt", (u.read(U::R_USBSTS, 4) & U::USBSTS_UI) && u.irq());
		u.write(U::R_USBSTS, 4, U::USBSTS_UI, false);
		u.write(U::R_EPSETUPSR, 4, 1, false);
		check("both are write-1-to-clear", u.read(U::R_USBSTS, 4) == 0 && u.read(U::R_EPSETUPSR, 4) == 0 && !u.irq());

		// EP0 IN: the host asks for 18 bytes before the guest has primed
		// anything; the reply waits. The guest then builds a dTD (token =
		// len << 16 | ACTIVE, buffer page 0) behind the EP0 IN dQH (+0x40),
		// primes PETB0 (bit 16): the prime bit clears at once, ENDPTSTAT
		// shows it, the bytes move, the dTD retires, ENDPTCOMPLETE + UI.
		replies.clear();
		u.command("in 0 18", reply);
		check("an IN with nothing primed does not answer", replies.empty());
		const uint32_t qh0in = 0x4ec94800 + 0x40, td = 0x4ec95020, buf = 0x400e2000;
		for(int i = 0; i < 18; ++i) mem[buf + i] = uint8_t(0x12 + i);
		st32(td, 1); st32(td + 4, (18u << 16) | 0x80u); st32(td + 8, buf);
		st32(qh0in + 8, td);
		st32(qh0in + 0x0c, 0);
		u.write(U::R_EPPRIME, 4, 1u << 16, false);
		checkEq("ENDPTPRIME clears itself", u.read(U::R_EPPRIME, 4), 0);
		check("the bytes moved and the reply carries them",
			!replies.empty() && replies.back().rfind("in 0 1213", 0) == 0 && replies.back().size() == 5 + 36 + 1);
		checkEq("the dTD retired: ACTIVE clear, 0 bytes left", ld32(td + 4), 0);
		checkEq("ENDPTCOMPLETE PETB0", u.read(U::R_EPCOMPLETE, 4), 1u << 16);
		checkEq("ENDPTSTAT clear again", u.read(U::R_EPSR, 4), 0);
		check("completion interrupts", u.irq());
		u.write(U::R_EPCOMPLETE, 4, 1u << 16, false);
		u.write(U::R_USBSTS, 4, U::USBSTS_UI, false);

		// A bulk IN chain (MSC: 36 bytes of INQUIRY data with the 13-byte CSW
		// linked behind it) is walked as ONE transfer up to the host's
		// appetite; the remainder stays ACTIVE and pending in ENDPTSTAT.
		const uint32_t qh1in = 0x4ec94800 + 0xc0, tdA = 0x4ec95100, tdB = 0x4ec95140, bufA = 0x4ecc0000, bufB = 0x4ecc0100;
		for(int i = 0; i < 36; ++i) mem[bufA + i] = uint8_t(i);
		for(int i = 0; i < 13; ++i) mem[bufB + i] = uint8_t(0x50 + i);
		st32(tdA, tdB); st32(tdA + 4, (36u << 16) | 0x80u); st32(tdA + 8, bufA);
		st32(tdB, 1); st32(tdB + 4, (13u << 16) | 0x80u); st32(tdB + 8, bufB);
		st32(qh1in + 8, tdA); st32(qh1in + 0x0c, 0);
		u.write(U::R_EPCTRL0 + 4, 4, 0x00c800c8, false);	// EP1 bulk both ways
		u.write(U::R_EPPRIME, 4, 1u << 17, false);
		replies.clear();
		u.command("in 1 36", reply);
		check("36 of the chain answered", !replies.empty() && replies.back().rfind("in 1 0001", 0) == 0 && replies.back().size() == 5 + 72 + 1);
		check("a short bulk packet (36 < 64) ends the transfer at the first dTD", ld32(tdA + 4) == 0 && (ld32(tdB + 4) & 0x80u));
		checkEq("the rest stays pending in ENDPTSTAT", u.read(U::R_EPSR, 4), 1u << 17);
		replies.clear();
		u.command("in 1 13", reply);
		check("the CSW follows on the next IN", !replies.empty() && replies.back().rfind("in 1 5051", 0) == 0);
		checkEq("chain done: ENDPTSTAT clear", u.read(U::R_EPSR, 4), 0);

		// An ISOCHRONOUS endpoint sends exactly ONE dTD per poll however
		// long the chain (EP3 IN, type 1 in ENDPTCTRL3 bits 19:18).
		const uint32_t qh3in = 0x4ec94800 + 0x1c0, tdI = 0x4ec95200, tdJ = 0x4ec95240, bufI = 0x4ecd0000, bufJ = 0x4ecd1000;
		for(int i = 0; i < 704; ++i) { mem[bufI + i] = uint8_t(i); mem[bufJ + i] = uint8_t(0x80 + i); }
		st32(tdI, tdJ); st32(tdI + 4, (704u << 16) | 0x80u); st32(tdI + 8, bufI);
		st32(tdJ, 1); st32(tdJ + 4, (704u << 16) | 0x80u); st32(tdJ + 8, bufJ);
		st32(qh3in + 8, tdI); st32(qh3in + 0x0c, 0);
		u.write(U::R_EPCTRL0 + 12, 4, 0x00c40000, false);	// EP3 IN iso, enabled
		u.write(U::R_EPPRIME, 4, 1u << 19, false);
		replies.clear();
		u.command("in 3 1024", reply);
		check("iso: an IN waits for the host's poll tick", replies.empty());
		u.isoPoll();
		check("iso: one 704-byte packet per poll, not the chain", !replies.empty() && replies.back().rfind("in 3 0001", 0) == 0 && replies.back().size() == 5 + 1408 + 1);
		check("iso: the second dTD is still ACTIVE and pending", (ld32(tdJ + 4) & 0x80u) && (u.read(U::R_EPSR, 4) & (1u << 19)));
		replies.clear();
		u.command("in 3 1024", reply);
		u.isoPoll();
		check("iso: the next poll takes the second", !replies.empty() && replies.back().rfind("in 3 8081", 0) == 0);
		replies.clear();
		u.command("in 3 1024", reply);
		u.isoPoll();
		check("iso: a poll with nothing primed answers empty (the host's ZLP)", !replies.empty() && replies.back() == "in 3\n");

		// OUT: bytes land in the primed buffer; a ZLP answers "out n 0".
		const uint32_t qh2out = 0x4ec94800 + 0x100, tdO = 0x4ec953e0, bufO = 0x4ecc9000;
		st32(tdO, 1); st32(tdO + 4, (64u << 16) | 0x80u); st32(tdO + 8, bufO);
		st32(qh2out + 8, tdO); st32(qh2out + 0x0c, 0);
		u.write(U::R_EPPRIME, 4, 1u << 2, false);
		replies.clear();
		u.command("out 2 09903c64", reply);
		check("OUT answers with the count", !replies.empty() && replies.back() == "out 2 4\n");
		checkEq("the bytes are in the guest buffer", ld32(bufO), 0x09903c64);
		checkEq("the dTD reports 60 bytes left", ld32(tdO + 4) >> 16, 60);

		// A stalled EP0 answers the pending op, and the next SETUP clears
		// the stall bits.
		replies.clear();
		u.command("in 0 64", reply);
		u.write(U::R_EPCTRL0, 4, U::EPCTRL_TXS, false);
		check("EP0 stall answers a pending IN", !replies.empty() && replies.back() == "in 0 stall\n");
		u.command("setup 0009010000000000", reply);
		checkEq("a SETUP clears the EP0 stall bits", u.read(U::R_EPCTRL0, 4) & (U::EPCTRL_TXS | U::EPCTRL_RXS), 0);

		// Reset: address and endpoint state cleared, URI + PCI raised.
		u.write(U::R_DEVICEADDR, 4, 1u << 25, false);
		u.command("reset", reply);
		check("reset clears the address and raises URI + PCI",
			u.read(U::R_DEVICEADDR, 4) == 0 && (u.read(U::R_USBSTS, 4) & (U::USBSTS_URI | U::USBSTS_PCI)) == (U::USBSTS_URI | U::USBSTS_PCI));

		// A primed queue head whose token still has ACTIVE set is counted.
		st32(qh0in + 0x0c, 0x80u);
		u.write(U::R_EPPRIME, 4, 1u << 16, false);
		checkEq("an uninitialised dQH is counted", u.stats().badQh, 1);

		// poke / call are queued for whoever runs the machine, and answered
		// by them; nothing is written from the socket reader.
		u.command("call 0x40010bc8 3 0x400d807c", reply);
		ot::UsbDevice::Request rq;
		check("a call is queued, not answered", u.hasRequest() && u.takeRequest(rq) && rq.kind == "call" && rq.addr == 0x40010bc8
			&& rq.args == std::vector<uint32_t>{3, 0x400d807c} && !u.hasRequest());
		u.command("poke 0x400d807c 903c64", reply);
		check("a poke carries its bytes", u.takeRequest(rq) && rq.kind == "poke" && rq.addr == 0x400d807c && rq.bytes == std::vector<uint8_t>{0x90, 0x3c, 0x64});

		// SOF: SRI only, no UI -- the stock USBINTR 0x57 has no SRE, so no
		// interrupt (a UI beside it cleared a real completion; usb.cpp).
		u.write(U::R_USBSTS, 4, 0x1ff, false);
		u.write(U::R_EPCOMPLETE, 4, ~0u, false);
		u.sof();
		check("SOF sets SRI and nothing else", u.read(U::R_USBSTS, 4) == U::USBSTS_SRI);
		check("SOF does not interrupt under the stock USBINTR", !u.irq());
		u.write(U::R_USBINTR, 4, 0x57 | 0x80, false);
		check("SOF interrupts once the guest enables SRE", u.irq());
	}

	// ---- the MKII panel's replies (periph.h MkiiPanel, docs/firmware/PANEL.md)
	{
		ot::Uart uart("UART@fc064000", 0xfc064000);
		ot::MkiiPanel panel(uart, 8);
		uart.setFarEnd([&panel](uint8_t _b) { panel(_b); });
		const auto drain = [&uart]()
		{
			std::vector<uint8_t> v;
			while(uart.read(0x04, 1) & ot::Uart::RXRDY)
				v.push_back(static_cast<uint8_t>(uart.read(0x0c, 1)));
			return v;
		};
		const auto send = [&uart](std::initializer_list<uint8_t> _b) { for(const auto b : _b) uart.write(0x0c, 1, b, false); };
		check("an MKI-style stream gets no answer", (send({0x43, 0x3f, 0x00, 0x20, 0x55}), drain().empty()));
		send({0x60, 0x02, 0x70, 0x00});
		check("the loader query `60 02 70 00` gets `70 05 <version> 00 00`",
			drain() == std::vector<uint8_t>{0x70, 0x05, 0x08, 0x00, 0x00});
		send({0x60, 0x00});
		send({0x10, 0x00, 0x74, 0x00, 0x74, 0x00, 0x74, 0x00, 0x74, 0x00});	// an LCD block full of 74 00
		check("0x74 inside an LCD block is not a command", drain().empty());
		send({0x70, 0x00});
		check("`70 00` outside the loader gets no answer", drain().empty());
		send({0x74, 0x00});
		const auto rep = drain();
		check("`74 00` gets the 0x7r report: header + 9 bytes, byte 1 = version, byte 3 = 1 (UI tested)",
			rep.size() == 10 && rep[0] == 0x70 && rep[2] == 0x08 && rep[4] == 0x01 && rep[5] == 0x00);
		send({0x74, 0x00});
		check("a replayed write is not seen by the far end",
			(uart.write(0x0c, 1, 0x74, true), uart.write(0x0c, 1, 0x00, true), drain().size() == 10));
	}

	std::printf("%s\n", g_failures ? "PERIPHERAL GATE FAILED" : "peripheral gate passed.");
	return g_failures ? 1 : 0;
}
