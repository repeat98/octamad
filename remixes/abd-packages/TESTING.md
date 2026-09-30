# Testing build 93 (about 15 minutes)

This build is stock 1.40C with **Analog BD, Tape Echo, Miniverb and Euclid**
added. Every stock effect is still there. Effects now load only when a Part
uses them, which frees memory for more effects later.

**We need to know: does changing effects or Parts ever cause silence, clicks
or freezes?**

## Setup

1. Back up your card, then flash `OCTATRACK_OCTABAM93.bin`.
2. Make a **new project** (please don't use old projects with this build).
3. Put a looping sample on **track 1** and **track 5**, and press play.
   Keep it playing for all the tests.

*Tracks 1–4 and 5–8 run on different DSP chips, so we test one of each.*

## Tests

**Effects**
- [ ] On tracks 1 and 5, scroll through **every FX1 effect** (including Euclid) and turn a knob on each.
- [ ] On tracks 1 and 5, scroll through **every FX2 effect** (including Tape Echo and Miniverb). Turn the mix up so you hear it.

**Parts**
- [ ] Give Part 1 and Part 2 different effects, then switch between them while playing.
- [ ] Make two patterns that use different Parts, and let them change into each other.

**Analog BD**
- [ ] Put Analog BD on track 3, double-tap it and try **808** and **909**, with an effect on it.

**Extras**
- [ ] Point an LFO at a knob of Tape Echo, Miniverb or Euclid.
- [ ] Put a big reverb on FX2 of all four tracks 1–4 (Dark, Spring, Plate, Miniverb).
- [ ] Save, load another project, then load this one again. Power off and on.

## What's OK and what's a bug

- **OK:** hearing the old effect for a split second after switching.
- **OK:** a "memory full" message when you load a lot of big effects. The
  change is refused and the old effects keep playing.
- **Bug:** any silence, click, crackle, freeze or crash, an effect that
  sounds wrong or ignores its knobs, or any other message.

## Found a bug?

Send us:

```
Build 93, MK1 / MK2
What I did:
What I heard/saw:
Every time / sometimes / once
```

A phone video with sound helps a lot. **Won't start?** Reflash stock 1.40C.
