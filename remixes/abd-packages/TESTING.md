# Testing build 93 (abd-packages)

Thanks for testing! This takes about **30 minutes**. No tools needed, just
your Octatrack, headphones and a pattern that plays.

## What is this build?

It's the stock 1.40C firmware with Analog BD, Tape Echo, Miniverb and Euclid
added, and **every stock effect is still there**.

What's new under the hood: effects are no longer permanently stored in the
DSP's memory. Each effect is loaded when a Part uses it. That frees up memory,
so more new effects can be added later without removing stock ones.

**The one thing we need to know:** does it still behave exactly like stock?
Specifically, do you ever hear silence, dropouts, clicks or freezes when you
change effects or Parts?

## Before you start

1. **Back up your CF card.**
2. Flash `OCTATRACK_OCTABAM93.bin` the usual way. The start screen should
   show build **93**.
3. **Make a NEW project for testing.** Please don't open old projects with
   this build yet.
4. Put a sample that plays constantly (a loop, pad or drone) on **track 1**
   and **track 5**, and start the pattern. Keep it playing for every test.

> Why tracks 1 and 5? The Octatrack has two DSP chips: tracks 1–4 run on one
> and tracks 5–8 on the other. We want to test both.

## The tests

Tick each box as you go. If something goes wrong, write down what you did
just before (see "Reporting" at the bottom).

### 1. Switching FX1 on a playing track (5 min)

On **track 1**, go to FX1 and scroll slowly through every effect: Filter,
EQ, DJ EQ, Phaser, Flanger, Chorus, Spatializer, Comb Filter, Compressor,
Lo-Fi, Euclid. Turn a knob on each one.

- [ ] Every effect sounds like it should, and its knobs work
- [ ] No silence, dropout or click while switching

*A very short moment where you still hear the previous effect is OK and
expected. Silence is not.*

Now do the same on **track 5**.

- [ ] Same result on track 5

### 2. Switching FX2 on a playing track (5 min)

On **track 1**, go to FX2 and scroll through every effect, including Delay,
Plate Rev, Spring Rev, Dark Rev, **Tape Echo** and **Miniverb**. Turn up the
mix or send so you can hear each one.

- [ ] Every effect sounds right, and the reverbs and delays have tails
- [ ] No silence, dropout or click while switching

Repeat on **track 5**.

- [ ] Same result on track 5

### 3. Switching Parts (5 min)

1. In **Part 1**, give tracks 1 and 5 some effects (for example Filter + Plate Rev).
2. Go to **Part 2** and give the same tracks different effects (for example
   Chorus + Tape Echo). Save both Parts.
3. While the pattern plays, switch between Part 1 and Part 2 many times.
4. Make two patterns that use different Parts and let them change into each other.

- [ ] The effects change with the Part
- [ ] No silence, dropout or freeze

### 4. Analog BD (5 min)

1. On **track 3**, choose the **ANALOG BD** machine and add some trigs.
2. Double-tap the track to open the engine list, then pick **808**, then **909**.
3. Put an effect on it (for example Filter on FX1 and Dark Rev on FX2).

- [ ] Both 808 and 909 play
- [ ] The effects work on it
- [ ] No dropouts on the other tracks

### 5. Load it up (5 min)

On tracks **1, 2, 3 and 4**, give every track a different **big** effect on
FX2 (Dark Rev, Spring Rev, Plate Rev, Miniverb) and a different effect on
FX1. Then try the same on tracks 5–8.

Either of these is fine:
- it all works, or
- you see a **"memory full"** style message and the change is refused. The old
  effects keep playing.

- [ ] Never silence, a crash or a freeze

### 6. LFO on an effect (2 min)

On any track, point an LFO at a parameter of **Tape Echo**, **Miniverb** or
**Euclid** and give it some depth.

- [ ] The parameter moves, and nothing crashes

### 7. Save, reload, power off (3 min)

1. Save the project, then load a different one and load this one back.
2. Switch the Octatrack off and on and load the project again.

- [ ] Everything comes back with the right effects and sound

## What counts as a bug

- silence, even for a moment, when changing an effect or Part
- a dropout, click or crackle that stock firmware doesn't make
- a freeze, crash or reboot
- an effect that sounds wrong or doesn't react to its knobs
- any message you didn't expect

## Reporting

For each problem, send us:

```
Build: 93
Unit: MK1 / MK2
What I did (step by step):
What I heard/saw:
Tracks and effects involved:
Does it happen every time? yes / sometimes / once
```

A short phone video with sound helps a lot.

**If the unit won't start:** hold the power-up menu and reflash the stock
1.40C OS as usual. Your backed-up card is untouched.
