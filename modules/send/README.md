# SEND

The bus client: one knob, SEND, this track's level into the one aux bus
(delay, then reverb; each engine's wet comes out on the track that hosts it).

It taps the audio buffer and never writes it, so a SEND at SEND 0 is
indistinguishable from no effect. A fresh, unassigned track (FX2 id 0) is
aliased to it rather than to NONE because SEND does the per-block bus
housekeeping, so no track can stall the bus. It is also the fallback: an id
a bus-carrying remix does not implement resolves here. The send is refused
on track 8 by construction: with MASTER TRACK on, T8's input is the mix,
the hosts' wet included, and a send from it would put that wet back into
the bus. The alias also puts SEND on every FX1 slot set to NONE; there it
returns at proc entry (r7 0x6100/0x6400/0x6700/0x6a00, image 48), so an
empty FX1 slot neither sends nor touches the rotation tracker
(`docs/effects/XBUS.md`).

## The auto-gain

The accumulator is divided by 1/√N of the registered clients, so eight
senders drive a server as hard as one. A quiet sender turns the loud sender's
reverb down: three senders, two of them 10–15 dB quieter, measured 4.8 dB
below the loud sender alone. A client that registers and contributes nothing
dilutes everyone (−3.0 dB with one sender under 1/√N; the −6.02 dB
measured on 17 Aug 2026 was under 1/N), which is why every level knob
gates its own registration. A track already sending loses 3 dB of wet each
time the sender count doubles (1→2, 2→4, 4→8), stepped per block when a
SEND knob leaves 0; N counts knobs, not signal.

[`docs/effects/XBUS.md`](../../docs/effects/XBUS.md).
