#include "usb.h"

#include <algorithm>
#include <cerrno>
#include <cstdlib>
#include <cstdio>
#include <cstring>
#include <fcntl.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>

namespace ot
{
	UsbDevice::~UsbDevice()
	{
		closeClient();
		if(m_listenFd >= 0)
			::close(m_listenFd);
	}

	// ---- the register window ------------------------------------------------

	uint32_t UsbDevice::read(const uint32_t _off, const uint32_t _size)
	{
		const auto word = _off & ~3u;
		uint32_t val = m_regs[word / 4];
		if(word == R_OTGSC)
		{
			// The cable is always plugged: without B-session valid the
			// firmware never brings the controller up (octemu measured no
			// bring-up writes until OTGSC reported a session).
			val |= OTGSC_BSV | m_otgscIs;
		}
		else if(word == R_PORTSC1 && connected())
		{
			// CCS + the speed in bits 27:26 (2 = high), which the descriptor
			// responder 0x4001d858 picks its config table by.
			val = 1u | (m_speedHs ? 2u << 26 : 0u);
		}
		else if(word == R_EPFLUSH && connected())
			val = 0;						// flushes complete at once
		if(_size == 4)
			return val;
		const auto shift = 8 * (4 - _size - (_off & 3));
		return (val >> shift) & ((1u << (8 * _size)) - 1);
	}

	void UsbDevice::write(const uint32_t _off, const uint32_t _size, const uint32_t _val, const bool _replay)
	{
		const auto word = _off & ~3u;
		auto& reg = m_regs[word / 4];
		uint32_t val = _val;
		if(_size != 4)
		{
			// The firmware writes these registers as longwords; a narrower
			// write merges, so a replayed byte store lands where it went.
			const auto shift = 8 * (4 - _size - (_off & 3));
			const auto mask = ((1u << (8 * _size)) - 1) << shift;
			val = (reg & ~mask) | ((_val << shift) & mask);
		}
		const auto old = reg;
		if(word == R_OTGSC)
		{
			// Status bits are write-1-to-clear. BSVIS latches on a BSVIE
			// ENABLE EDGE only: the cable is constant, so "session became
			// valid" happens once per enable. Latching on every write with
			// BSVIE set made an interrupt storm in octemu's first model (the
			// firmware's ack keeps BSVIE set, which re-latched).
			reg = val & ~0x00ff0000u;	// the interrupt-status byte is not storage: it is the latch below
			m_otgscIs &= ~(val & OTGSC_BSVIS);
			if((val & OTGSC_BSVIE) && !(old & OTGSC_BSVIE))
				m_otgscIs |= OTGSC_BSVIS;
			return;
		}
		if(_replay)
		{
			// The boot's writes, replayed at install: values only, no
			// side effects -- nothing was primed before the RTOS ran.
			reg = val;
			return;
		}
		switch(word)
		{
		case R_USBSTS:
		case R_EPSETUPSR:
		case R_EPCOMPLETE:
			reg = old & ~val;				// write-1-to-clear
			return;
		case R_EPPRIME:
		{
			// Priming latches the dQH's next-dTD now; the prime bit clears
			// at once (the firmware polls for exactly that after every prime,
			// 0x4001e646) and the transfer stays pending in ENDPTSTAT until
			// the host moves the bytes.
			const auto eplist = m_regs[R_EPLISTADDR / 4];
			for(int ep = 0; ep < g_endpoints; ++ep)
				for(int dir = 0; dir < 2; ++dir)
					if(val & (1u << (ep + (dir ? 16 : 0))))
					{
						const uint32_t qh = eplist + (ep * 2 + dir) * 0x40u;
						if(m_hwFaithful)
						{
							const auto tok = ld32(qh + 0x0c);
							if(tok & 0x80u)
							{
								if(m_stats.badQh++ < 8)
									std::fprintf(stderr, "usb: UNINITIALIZED dQH: ep%d %s primed with token %#010x (ACTIVE set) at %#010x -- "
										"the guest never cleared this queue head; on hardware the controller DMAs through its stale pointers\n",
										ep, dir ? "IN" : "OUT", tok, qh);
							}
						}
						m_curTd[ep + 4 * dir] = ld32(qh + 8);
						++m_stats.primes;
					}
			m_regs[R_EPSR / 4] |= val;
			reg = 0;
			tryAll();
			return;
		}
		case R_EPFLUSH:
			m_regs[R_EPSR / 4] &= ~val;
			reg = 0;
			return;
		case R_EPCTRL0:
			// A STALL on EP0 is an ANSWER: the stock control handler stalls
			// every request it does not recognise, and a host reads that as
			// "unsupported". Without this a stalled request and a hung guest
			// looked identical (octemu).
			reg = val;
			stallCheck();
			return;
		default:
			reg = val;
			return;
		}
	}

	bool UsbDevice::irq() const
	{
		const bool otg = (m_regs[R_OTGSC / 4] & OTGSC_BSVIE) && (m_otgscIs & OTGSC_BSVIS);
		const bool dev = (m_regs[R_USBSTS / 4] & m_regs[R_USBINTR / 4]) != 0;
		return otg || dev;
	}

	void UsbDevice::sof()
	{
		busReset();
		if(!connected() || !running())
			return;
		// SRI only. The interrupt fires if the guest enabled SRE in USBINTR
		// (the stock 0x57 does not), which is the hardware's rule; octemu
		// raises UI beside it so the stock ISR's UI-only path reaches a
		// hook site, and that storm of empty UI passes clears EPCOMPLETE
		// under a real completion (measured here 25 Sep 2026: an EP2 OUT
		// packet accepted and never decoded).
		m_regs[R_USBSTS / 4] |= USBSTS_SRI;
		++m_stats.sofs;
	}

	// ---- guest memory -------------------------------------------------------

	uint32_t UsbDevice::ld32(const uint32_t _a) const
	{
		return (uint32_t(m_read8(_a)) << 24) | (uint32_t(m_read8(_a + 1)) << 16) | (uint32_t(m_read8(_a + 2)) << 8) | m_read8(_a + 3);
	}

	void UsbDevice::st32(const uint32_t _a, const uint32_t _v) const
	{
		m_write8(_a, uint8_t(_v >> 24));
		m_write8(_a + 1, uint8_t(_v >> 16));
		m_write8(_a + 2, uint8_t(_v >> 8));
		m_write8(_a + 3, uint8_t(_v));
	}

	// Copy `_len` bytes between guest memory and `_buf` along the dTD's 4 KB
	// buffer-page list (page 0 carries the starting offset).
	void UsbDevice::tdCopy(const uint32_t _td, const size_t _len, uint8_t* _buf, const bool _toHost) const
	{
		uint32_t ptr = ld32(_td + 8);
		size_t done = 0;
		int page = 0;
		while(done < _len && ptr)
		{
			const uint32_t pageEnd = (ptr & ~0xfffu) + 0x1000u;
			const size_t n = std::min(_len - done, size_t(pageEnd - ptr));
			for(size_t i = 0; i < n; ++i)
				if(_toHost)
					_buf[done + i] = m_read8(ptr + uint32_t(i));
				else
					m_write8(ptr + uint32_t(i), _buf[done + i]);
			done += n;
			++page;
			ptr = page <= 4 ? (ld32(_td + 8 + 4 * page) & ~0xfffu) : 0;
		}
	}

	// ---- transfers ----------------------------------------------------------

	// One rendezvous: the guest has an active transfer on (ep, dir) and the
	// host an outstanding op for it. Walks the dTD chain, moves bytes, retires
	// each dTD (ACTIVE cleared, remaining bytes written back), raises
	// ENDPTCOMPLETE + USBSTS.UI, answers the host.
	void UsbDevice::service(const int _ep, const bool _in)
	{
		const uint32_t bit = 1u << (_ep + (_in ? 16 : 0));
		const int slot = _ep + (_in ? 4 : 0);
		uint32_t td = m_curTd[slot];
		static uint8_t buf[g_maxTransfer];
		size_t moved = 0;
		// ⚠️ ISOCHRONOUS endpoints send exactly ONE dTD per poll. Walking the
		// chain as one transfer is bulk semantics; on linked iso dTDs it
		// merged two packets and desynced the guest's queue from the bench's
		// cursor (octemu). The type comes from ENDPTCTRLn.
		const uint32_t epctrl = m_regs[(R_EPCTRL0 + 4u * _ep) / 4];
		const bool iso = (((_in ? epctrl >> 18 : epctrl >> 2)) & 3u) == 1u;
		if(_in)
		{
			auto& op = m_in[_ep];
			while(!(td & 1u) && moved < size_t(op.want))
			{
				const auto token = ld32(td + 4);
				if(!(token & 0x80u))
					break;
				const size_t total = (token >> 16) & 0x7fff;
				const size_t n = std::min(total, size_t(op.want) - moved);
				tdCopy(td, n, buf + moved, true);
				moved += n;
				st32(td + 4, (uint32_t(total - n) << 16) | (token & 0x8000u));
				td = ld32(td);
				if(iso || total < 64)		// one packet per poll; a short packet ends a bulk transfer
					break;
			}
			op.pending = false;
			++m_stats.ins;
			m_stats.bytesIn += moved;
			std::string hex;
			hex.reserve(2 * moved);
			for(size_t i = 0; i < moved; ++i)
			{
				char h[3];
				std::snprintf(h, sizeof h, "%02x", buf[i]);
				hex += h;
			}
			reply(moved ? "in " + std::to_string(_ep) + " " + hex + "\n" : "in " + std::to_string(_ep) + "\n");
		}
		else
		{
			auto& op = m_out[_ep];
			do
			{
				if(td & 1u)
					break;
				const auto token = ld32(td + 4);
				if(!(token & 0x80u))
					break;
				const size_t total = (token >> 16) & 0x7fff;
				const size_t n = std::min(total, op.data.size() - op.off);
				tdCopy(td, n, op.data.data() + op.off, false);
				op.off += n;
				moved += n;
				st32(td + 4, (uint32_t(total - n) << 16) | (token & 0x8000u));
				td = ld32(td);
			}
			while(op.off < op.data.size());
			op.pending = false;
			++m_stats.outs;
			m_stats.bytesOut += moved;
			reply("out " + std::to_string(_ep) + " " + std::to_string(moved) + "\n");
		}
		m_curTd[slot] = td;
		// A chain remainder still ACTIVE keeps the transfer pending (MSC
		// queues INQUIRY data with the CSW linked behind it).
		if((td & 1u) || !(ld32(td + 4) & 0x80u))
			m_regs[R_EPSR / 4] &= ~bit;
		m_regs[R_EPCOMPLETE / 4] |= bit;
		m_regs[R_USBSTS / 4] |= USBSTS_UI;
	}

	// The pending bus reset lands once the controller runs with an endpoint
	// list; the host's "ok" follows it.
	void UsbDevice::busReset()
	{
		if(!m_resetPending || !running() || !m_regs[R_EPLISTADDR / 4])
			return;
		m_resetPending = false;
		m_regs[R_DEVICEADDR / 4] = 0;
		m_regs[R_EPPRIME / 4] = 0;
		m_regs[R_EPSR / 4] = 0;
		m_regs[R_EPCOMPLETE / 4] = 0;
		m_regs[R_EPSETUPSR / 4] = 0;
		m_regs[R_USBSTS / 4] |= USBSTS_URI | USBSTS_PCI;
		reply("ok\n");
	}

	bool UsbDevice::isIso(const int _ep, const bool _in) const
	{
		const uint32_t epctrl = m_regs[(R_EPCTRL0 + 4u * _ep) / 4];
		return (((_in ? epctrl >> 18 : epctrl >> 2)) & 3u) == 1u;
	}

	void UsbDevice::tryAll()
	{
		busReset();
		if(!connected() || !m_regs[R_EPLISTADDR / 4])
			return;
		for(int ep = 0; ep < g_endpoints; ++ep)
		{
			if(m_in[ep].pending && !isIso(ep, true) && (m_regs[R_EPSR / 4] & (1u << (ep + 16))))
				service(ep, true);
			if(m_out[ep].pending && !isIso(ep, false) && (m_regs[R_EPSR / 4] & (1u << ep)))
				service(ep, false);
		}
	}

	void UsbDevice::isoPoll()
	{
		if(!connected() || !m_regs[R_EPLISTADDR / 4])
			return;
		for(int ep = 0; ep < g_endpoints; ++ep)
		{
			// A DISABLED endpoint (TXE/RXE clear, the stream torn down at
			// alt 0) answers the poll empty as well: nothing will ever be
			// primed on it, and a real host's IN gets no data.
			const uint32_t epctrl = m_regs[(R_EPCTRL0 + 4u * ep) / 4];
			const bool txDisabled = ep != 0 && !(epctrl & (1u << 23)), rxDisabled = ep != 0 && !(epctrl & (1u << 7));
			if(m_in[ep].pending && (isIso(ep, true) || txDisabled))
			{
				if(m_regs[R_EPSR / 4] & (1u << (ep + 16)))
					service(ep, true);
				else
				{
					m_in[ep].pending = false;
					++m_stats.ins;
					reply("in " + std::to_string(ep) + "\n");
				}
			}
			if(m_out[ep].pending && (isIso(ep, false) || rxDisabled))
			{
				if(m_regs[R_EPSR / 4] & (1u << ep))
					service(ep, false);
				else
				{
					m_out[ep].pending = false;
					++m_stats.outs;
					reply("out " + std::to_string(ep) + " 0\n");
				}
			}
		}
	}

	// The controller answers the host's next EP0 IN/OUT with a STALL while
	// the stall bit is set. The bits clear on the next SETUP, as on the core.
	void UsbDevice::stallCheck()
	{
		const auto c = m_regs[R_EPCTRL0 / 4];
		if((c & EPCTRL_TXS) && m_in[0].pending)
		{
			m_in[0].pending = false;
			++m_stats.stalls;
			reply("in 0 stall\n");
		}
		if((c & EPCTRL_RXS) && m_out[0].pending)
		{
			m_out[0].pending = false;
			++m_stats.stalls;
			reply("out 0 stall\n");
		}
	}

	static size_t hexBytes(const char* _s, std::vector<uint8_t>& _out, const size_t _max)
	{
		_out.clear();
		while(_s[0] && _s[1] && _out.size() < _max)
		{
			unsigned v;
			if(std::sscanf(_s, "%2x", &v) != 1)
				break;
			_out.push_back(uint8_t(v));
			_s += 2;
		}
		return _out.size();
	}

	void UsbDevice::command(const std::string& _line, const std::function<void(const std::string&)>& _reply)
	{
		// Every reply, immediate or from a later `service`, goes to the
		// caller's sink -- the socket writer, or a test's collector. A
		// command() caller is a host, socket or not.
		m_sink = _reply;
		m_hostPresent = true;
		const auto& l = _line;
		if(l.rfind("setup ", 0) == 0)
		{
			std::vector<uint8_t> pkt;
			hexBytes(l.c_str() + 6, pkt, 8);
			pkt.resize(8, 0);
			const auto eplist = m_regs[R_EPLISTADDR / 4];
			if(!eplist)
			{
				_reply("err no-eplist\n");
				return;
			}
			// The setup buffer is at +0x28 of the EP0 OUT dQH as two
			// LITTLE-ENDIAN dwords: in the big-endian bus view each 4-byte
			// group is wire-reversed, which the firmware's byterev of its
			// BE loads undoes (usb_setup_read, 0x4001d5d4).
			const uint8_t rev[8] = { pkt[3], pkt[2], pkt[1], pkt[0], pkt[7], pkt[6], pkt[5], pkt[4] };
			for(int i = 0; i < 8; ++i)
				m_write8(eplist + 0x28 + i, rev[i]);
			m_regs[R_EPCTRL0 / 4] &= ~(EPCTRL_TXS | EPCTRL_RXS);	// a new SETUP clears an EP0 stall
			m_regs[R_EPSETUPSR / 4] |= 1u;
			m_regs[R_USBSTS / 4] |= USBSTS_UI;
			++m_stats.setups;
			_reply("ok\n");
		}
		else if(l.rfind("in ", 0) == 0)
		{
			int ep = 0, want = 0;
			std::sscanf(l.c_str() + 3, "%d %d", &ep, &want);
			ep &= 3;
			m_in[ep].pending = true;
			m_in[ep].want = std::min(want, int(g_maxTransfer));
			stallCheck();
			tryAll();
		}
		else if(l.rfind("out ", 0) == 0)
		{
			int ep = 0;
			std::sscanf(l.c_str() + 4, "%d", &ep);
			ep &= 3;
			const auto sp = l.find(' ', 4);
			auto& op = m_out[ep];
			if(sp != std::string::npos)
				hexBytes(l.c_str() + sp + 1, op.data, g_maxTransfer);
			else
				op.data.clear();
			op.off = 0;
			op.pending = true;
			stallCheck();
			tryAll();
		}
		else if(l.rfind("reset", 0) == 0)
		{
			// Deferred until the device is attached: a host cannot reset a
			// device that has not pulled up, and a script that connects the
			// moment the port starts is ahead of the firmware's bring-up
			// (the "err no-eplist" it got for its first SETUP, 25 Sep 2026).
			m_resetPending = true;
			busReset();
		}
		else if(l.rfind("speed ", 0) == 0)
		{
			m_speedHs = l.compare(6, 2, "hs") == 0;
			_reply("ok\n");
		}
		else if(l.rfind("poke ", 0) == 0 || l.rfind("call ", 0) == 0)
		{
			auto r = std::make_unique<Request>();
			r->kind = l.substr(0, 4);
			std::string rest = l.substr(5);
			const auto sp = rest.find(' ');
			r->addr = uint32_t(std::strtoul(rest.substr(0, sp).c_str(), nullptr, 0));
			if(sp != std::string::npos)
			{
				rest = rest.substr(sp + 1);
				if(r->kind == "poke")
					hexBytes(rest.c_str(), r->bytes, g_maxTransfer);
				else
					for(size_t q = 0; q < rest.size();)
					{
						auto e = rest.find(' ', q);
						if(e == std::string::npos) e = rest.size();
						if(e > q) r->args.push_back(uint32_t(std::strtoul(rest.substr(q, e - q).c_str(), nullptr, 0)));
						q = e + 1;
					}
			}
			m_request = std::move(r);		// answered by whoever serves it
		}
		else
			_reply("err unknown\n");
	}

	bool UsbDevice::takeRequest(Request& _out)
	{
		if(!m_request)
			return false;
		_out = *m_request;
		m_request.reset();
		return true;
	}

	// ---- the socket ---------------------------------------------------------

	bool UsbDevice::listen(const std::string& _path)
	{
		m_listenFd = ::socket(AF_UNIX, SOCK_STREAM, 0);
		if(m_listenFd < 0)
			return false;
		sockaddr_un addr{};
		addr.sun_family = AF_UNIX;
		if(_path.size() >= sizeof addr.sun_path)
		{
			// macOS caps sun_path at 104 bytes and a truncated path binds
			// somewhere else in silence.
			std::fprintf(stderr, "usb: socket path is %zu bytes, the limit is %zu\n", _path.size(), sizeof addr.sun_path - 1);
			::close(m_listenFd);
			m_listenFd = -1;
			return false;
		}
		std::strncpy(addr.sun_path, _path.c_str(), sizeof addr.sun_path - 1);
		::unlink(_path.c_str());
		if(::bind(m_listenFd, reinterpret_cast<sockaddr*>(&addr), sizeof addr) || ::listen(m_listenFd, 1))
		{
			::close(m_listenFd);
			m_listenFd = -1;
			return false;
		}
		::fcntl(m_listenFd, F_SETFL, ::fcntl(m_listenFd, F_GETFL) | O_NONBLOCK);
		return true;
	}

	void UsbDevice::closeClient()
	{
		if(m_fd >= 0)
			::close(m_fd);
		m_fd = -1;
		m_hostPresent = false;
		m_sink = nullptr;
		m_line.clear();
		for(auto& i : m_in) i = InOp{};
		for(auto& o : m_out) o = OutOp{};
	}

	void UsbDevice::reply(const std::string& _s)
	{
		if(m_sink)
			m_sink(_s);
		else
			writeSocket(_s);
	}

	void UsbDevice::writeSocket(const std::string& _s)
	{
		if(m_fd < 0)
			return;
		size_t off = 0;
		while(off < _s.size())
		{
			const auto n = ::write(m_fd, _s.data() + off, _s.size() - off);
			if(n <= 0)
				break;
			off += size_t(n);
		}
	}

	void UsbDevice::pollIo()
	{
		if(m_listenFd < 0)
			return;
		if(m_fd < 0)
		{
			const int fd = ::accept(m_listenFd, nullptr, nullptr);
			if(fd < 0)
				return;
			::fcntl(fd, F_SETFL, ::fcntl(fd, F_GETFL) | O_NONBLOCK);
			m_fd = fd;
			m_sawClient = true;
		}
		char buf[1024];
		for(;;)
		{
			const auto n = ::read(m_fd, buf, sizeof buf);
			if(n == 0 || (n < 0 && errno != EAGAIN && errno != EWOULDBLOCK))
			{
				closeClient();
				return;
			}
			if(n < 0)
				return;
			for(ssize_t i = 0; i < n; ++i)
			{
				if(buf[i] == '\n')
				{
					command(m_line, [this](const std::string& s) { writeSocket(s); });
					m_sink = nullptr;		// back to the socket for replies raised by later primes
					m_line.clear();
				}
				else if(m_line.size() < 2 * g_maxTransfer + 64)
					m_line += buf[i];
			}
		}
	}
}
