// The MCF5445x USB OTG module as the firmware drives it: a Chipidea/ARC
// device controller at 0xfc0b0000, and a scripted HOST on a unix socket so a
// test can enumerate the unit, talk mass storage, USB-MIDI or an isochronous
// stream to it, and fail on a hang.
//
// WHAT THE FIRMWARE DOES WITH IT (measured from the 1.40C image, 25 Sep
// 2026; the symbol names are markandrus/octemu's `re/coldfire.syms`):
//   * boot sets PORTSC1's transceiver select to ULPI (0x400e0b1c) -- an
//     external high-speed PHY -- and the bring-up 0x4001d630 writes USBMODE
//     = 0x0e (device controller, big-endian, setup lockout off), EPLISTADDR
//     = 0x4ec94800 and USBINTR = 0x57. Nothing in the image runs the
//     controller as a host.
//   * the ISR (0x4001e594, INTC1 source 47, level 4) reads the SETUP packet
//     out of the EP0 OUT queue head's +0x28 buffer with the SUTW tripwire,
//     answers GET_DESCRIPTOR from the tables at 0x400e2000 (idVendor 0x1935,
//     idProduct 0x0002, one MSC/SCSI/BOT interface on EP1), and runs the
//     bulk-only-transport SCSI worker (0x4001ee30) over EP1.
//   * without a session (OTGSC.BSV) the firmware never brings the controller
//     up; with one at boot it brings it up immediately and answers SCSI with
//     "no medium" until USB DISK MODE unmounts the card (0x4007ebd4).
//
// WHAT IS MODELLED. The register file (stored and read back), the semantics
// the driver depends on: OTGSC's B-session-valid and its interrupt latch on
// the enable edge, write-1-to-clear status words, ENDPTPRIME latching each
// primed queue head's next-dTD and clearing itself (the firmware polls for
// that at 0x4001e646), ENDPTFLUSH, the EP0 stall bits, PORTSC1's speed. And
// the transfers themselves: the bench walks the queue heads and transfer
// descriptors IN GUEST MEMORY (dTD: +0 next, +4 token, +8..+0x18 buffer
// pages; dQH: +8 next-dTD, +0x28 setup buffer; all big-endian, as the
// firmware writes them), moves the bytes, retires each dTD, raises
// ENDPTCOMPLETE + USBSTS.UI and the interrupt.
//
// The shape follows octemu's bench (src/board/ot-board.c, MIT) so its
// tests/usb-host.py drives this port unchanged; the protocol is documented
// on `UsbDevice::command`. ⚠️ Not modelled: timing. A lock-step emulator
// serialises the host's polls, the frame interrupt and the eDMA, so a race
// between the USB-audio producer and the read-back bank swap cannot show
// here (CLAUDE.md, instrument blindness). Bytes, descriptors, hooks and
// crashes from a bad queue head can.
#pragma once

#include <array>
#include <cstdint>
#include <functional>
#include <memory>
#include <string>
#include <vector>

namespace ot
{
	class UsbDevice
	{
	public:
		static constexpr uint32_t g_base = 0xfc0b0000, g_size = 0x200;

		// Register offsets (MCF54455RM rev 5 ch. 32; the identification block
		// is below 0x100 and the operational registers at 0x140+).
		enum : uint32_t
		{
			R_USBCMD = 0x140, R_USBSTS = 0x144, R_USBINTR = 0x148,
			R_DEVICEADDR = 0x154, R_EPLISTADDR = 0x158, R_PORTSC1 = 0x184,
			R_OTGSC = 0x1a4, R_USBMODE = 0x1a8, R_EPSETUPSR = 0x1ac,
			R_EPPRIME = 0x1b0, R_EPFLUSH = 0x1b4, R_EPSR = 0x1b8,
			R_EPCOMPLETE = 0x1bc, R_EPCTRL0 = 0x1c0,
		};
		static constexpr uint32_t USBSTS_UI = 0x01, USBSTS_PCI = 0x04, USBSTS_URI = 0x40, USBSTS_SRI = 0x80;
		static constexpr uint32_t OTGSC_BSV = 0x800, OTGSC_BSVIS = 0x80000, OTGSC_BSVIE = 0x8000000;
		static constexpr uint32_t EPCTRL_RXS = 0x1, EPCTRL_TXS = 0x10000;
		static constexpr int g_endpoints = 4;			// pairs the firmware's dQH list covers (EP0..EP3)
		static constexpr size_t g_maxTransfer = 8192;

		// Guest memory, byte-wise: the bench's DMA. Byte access keeps the
		// buffer copies endian-free; the longword helpers below compose the
		// big-endian descriptor fields the firmware writes with `movel`.
		using Read8 = std::function<uint8_t(uint32_t)>;
		using Write8 = std::function<void(uint32_t, uint8_t)>;
		UsbDevice(Read8 _r, Write8 _w) : m_read8(std::move(_r)), m_write8(std::move(_w)) {}
		~UsbDevice();

		// -- the register window ---------------------------------------------
		uint32_t read(uint32_t _off, uint32_t _size);
		void write(uint32_t _off, uint32_t _size, uint32_t _val, bool _replay);
		bool irq() const;					// (USBSTS & USBINTR) or the OTG session latch

		// -- the host ----------------------------------------------------------
		// A unix socket the bench listens on; one client at a time. `pollIo`
		// runs from the emulator's poll cadence: accepts, reads lines, runs
		// commands. Returns false if the socket could not be created.
		bool listen(const std::string& _path);
		bool listening() const { return m_listenFd >= 0; }
		// A host is present while a socket client is connected, or from the
		// first direct `command()` (a test) until `closeClient()`.
		bool connected() const { return m_fd >= 0 || m_hostPresent; }
		bool sawClient() const { return m_sawClient; }
		void pollIo();
		// One protocol line, without the newline (the socket's reader calls
		// this; tests call it directly):
		//   setup <16 hex>     SETUP packet into the EP0 OUT dQH        -> ok
		//   in <ep> <maxlen>   IN transfer on EP n                       -> in <ep> [<hex>|stall]
		//   out <ep> [<hex>]   OUT transfer (bytes, or a ZLP) to EP n    -> out <ep> <count>|stall
		//   reset              bus reset (URI + PCI, address cleared)    -> ok
		//   speed hs|fs        the port speed PORTSC1 reports            -> ok
		// `in`/`out` answer when the transfer completes, which may be after
		// the guest primes the endpoint -- one outstanding op per endpoint
		// direction. Replies go to `_reply`.
		void command(const std::string& _line, const std::function<void(const std::string&)>& _reply);

		// Two bench commands the machine itself has to serve, from OUTSIDE
		// the run loop (a borrowed call re-enters it):
		//   poke <addr> <hex>      write bytes into guest memory   -> poke ok
		//   call <addr> [arg ...]  run a firmware routine as main   -> call <d0> | call err <why>
		// The run loop stops when one is queued (`hasRequest`), the caller
		// serves it and answers with `answerRequest`.
		struct Request { std::string kind; uint32_t addr = 0; std::vector<uint32_t> args; std::vector<uint8_t> bytes; };
		bool hasRequest() const { return m_request != nullptr; }
		bool takeRequest(Request& _out);
		void answerRequest(const std::string& _reply) { reply(_reply); }

		// The host's isochronous poll, once per 500 us of DEVICE time (the
		// bInterval-3 high-speed schedule): a pending IN on an isochronous
		// endpoint is served now if a packet is primed, else answered empty
		// -- the zero-length packet a real host gets, an underrun the guest
		// can count. A bulk IN is served the moment it can be (tryAll);
		// an isochronous one only here, so a host script that polls as fast
		// as the socket allows still drains at the device's own rate.
		void isoPoll();
		bool isIso(int _ep, bool _in) const;

		// The host's start-of-frame, raised by the run loop per audio block
		// while a host is connected and the controller is running: USBSTS.SRI,
		// an interrupt only if the guest enabled SRE (stock does not).
		void sof();

		// -- diagnostics -------------------------------------------------------
		struct Stats { uint64_t setups = 0, ins = 0, outs = 0, bytesIn = 0, bytesOut = 0, sofs = 0, primes = 0, stalls = 0, badQh = 0; };
		const Stats& stats() const { return m_stats; }
		bool running() const { return (m_regs[R_USBCMD / 4] & 1) != 0; }
		uint32_t reg(uint32_t _off) const { return m_regs[_off / 4]; }
		// A primed queue head whose token still has ACTIVE set was never
		// cleared by the guest: on silicon the controller DMAs through its
		// stale pointers (octemu crashed a unit twice this way). Counted, and
		// the first few named on stderr.
		void setHwFaithful(bool _on) { m_hwFaithful = _on; }

	private:
		struct InOp { bool pending = false; int want = 0; };
		struct OutOp { bool pending = false; std::vector<uint8_t> data; size_t off = 0; };

		uint32_t ld32(uint32_t _a) const;
		void st32(uint32_t _a, uint32_t _v) const;
		void tdCopy(uint32_t _td, size_t _len, uint8_t* _buf, bool _toHost) const;
		void service(int _ep, bool _in);
		void tryAll();
		void busReset();
		void stallCheck();
		void reply(const std::string& _s);
		void writeSocket(const std::string& _s);
		void closeClient();

		Read8 m_read8;
		Write8 m_write8;
		std::array<uint32_t, g_size / 4> m_regs = {};
		uint32_t m_otgscIs = 0;				// the latched BSVIS
		bool m_speedHs = true;
		bool m_hwFaithful = true;
		std::array<uint32_t, 2 * g_endpoints> m_curTd = {};	// ep + 4*dir
		std::array<InOp, g_endpoints> m_in;
		std::array<OutOp, g_endpoints> m_out;
		int m_listenFd = -1, m_fd = -1;
		bool m_sawClient = false;
		bool m_hostPresent = false;
		bool m_resetPending = false;
		std::unique_ptr<Request> m_request;
		std::function<void(const std::string&)> m_sink;	// where replies go while a command is being served
		std::string m_line;
		Stats m_stats;
	};
}
