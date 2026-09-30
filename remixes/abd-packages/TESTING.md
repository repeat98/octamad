# Testing build 93 (10 minutes)

This build is stock 1.40C with Analog BD, Tape Echo, Miniverb and Euclid
added. Effects now load only when used, to free up memory.
**We need to know: does changing effects or Parts ever cause silence, clicks or freezes?**

## Setup

1. Back up your card, then flash `OCTATRACK_OCTABAM93.bin`.
2. Make a **new project**.
3. Put a looping sample on **track 1** and **track 5**, and press play.

## Test (keep the pattern playing)

- [ ] On tracks 1 and 5, scroll through **every effect** on FX1 and FX2.
- [ ] Switch between two Parts that use different effects.
- [ ] Put **Analog BD** on a track (double-tap it to pick 808 or 909).
- [ ] Save, then power off and on.

A very short moment of the old effect is fine. **Silence, clicks or freezes are bugs.**

## Found a bug?

Send us what you did, what you heard and whether it happens every time.
A phone video with sound helps a lot.

**Won't start?** Reflash stock 1.40C.
