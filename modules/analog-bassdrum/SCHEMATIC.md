# Original 909 circuit review — 28 September 2026

## Evidence

Roland's [June 1984 service notes](https://notebook.zoeblade.com/Downloads/Documentation/Roland/TR-909_service_notes.pdf), pp. 6, 11–12, show a triggered/reset VCO, separate tonal and noise envelopes, and a continuously clocked noise circuit. The BD is not an 808-style ringing resonator. Q6 gates the noise contribution; there is no evidence here for a calibrated constant audible BD hiss.

The drawn output path has R473/R474 = 1 kΩ, R530/R532 = 2.2 kΩ, C511/C512 = 0.01 µF, and R531/R533 = 10 kΩ. Ignoring the audio-band impedance of the coupling capacitors and assuming a high-impedance external load:

```
Rth = (1k + 2.2k) || 10k = 2424.24 Ω
fc = 1 / (2π Rth × 10nF) = 6565.14 Hz
DC gain = 10k / (10k + 3.2k) = 0.757576
```

This describes the shown stereo output network, not every production revision or the mono-jack summing/loading case. Component tolerances and external loading change the result.

[Tom Wiltshire's circuit examination](https://electricdruid.net/tr-909-noise-generator/) identifies the feedback chain as 31 stages with taps 31/13, despite the service prose saying 32. He gives a roughly 300 kHz clock and explains why its state runs independently of drum triggers. Our implementation is original C, not copied PIC code.

## Implementation and scope

LPF uses an 88.2 kHz matched-pole RC discretization. It normalizes DC gain so AMP remains the volume control. Position 64 selects the calculated nominal cutoff; 0 bypasses; the remaining range is an intentional 500 Hz–18 kHz extension. The state tracks the signal even in bypass. No resonance or arbitrary master saturation is added.

The existing empirical 4 kHz voice pole remains separate: it softened an attack judged too sharp by the user. It is **not** claimed as a value read from the original schematic.

The 31-bit sequence advances at an approximate 300 kHz rate and averages three/four bit levels per internal sample before the existing noise-color pole. This is a reduced-bandwidth approximation, not an exact analog reconstruction. Each machine instance owns a generator; it does not reproduce the original shared generator's correlation with snare/tom voices. Its state and filter continue through silence. Quiet voice retirement no longer resets them. The trigger shaper discharges between hits rather than resetting its capacitor on every trigger.

The tonal VCO still resets at a hit. There is no random pitch wobble, arbitrary tolerance drift, added mains hum, or claimed hardware-measured leakage floor. Physical-unit recordings are still needed for those claims. 808 synthesis is unchanged by the 909-only output control.

## Verification

The engine gate compares actual rendered LPF transfer against the analog RC expression at 1, 6.5 and 10 kHz (0.4 dB tolerance), exercises idle-time-dependent attack noise and deterministic noise-free pitch/body, and checks bounds/retirement. ColdFire/native tests compare all state words and audio, including LPF changes. The UI gate edits LPF through stock encoder events. These prove implementation behavior, not hardware authenticity.
