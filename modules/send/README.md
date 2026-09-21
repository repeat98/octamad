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
the bus.

## The auto-gain

The accumulator is divided by 1/√N of the registered clients, so eight
senders drive a server as hard as one. A quiet sender turns the loud sender's
reverb down: three senders, two of them 10–15 dB quieter, measured 4.8 dB
below the loud sender alone. A client that registers and contributes nothing
dilutes everyone (−6.02 dB with one sender), which is why every level knob
gates its own registration.

[`docs/effects/XBUS.md`](../../docs/effects/XBUS.md).
