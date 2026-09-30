# `sos-capture` — the recorder fixes with a test signal in and the track outputs out over USB

The four recorder fixes on [`usb-io-tracks-ab`](../usb-io-tracks-ab/README.md):
the computer plays a test signal into inputs A/B and records the sixteen
track channels, digital end to end, so a sound-on-sound loop can be captured
sample-exact on a unit and compared with the port running the same project
on the same signal.

- **FLEX SEEK BIND**, **FLEX SEEK BIND CTR**, **RECORDER SPACING**,
  **RECORDER HOLD**: the loop click fixes,
  [`modules/recorder-hold`](../../../modules/recorder-hold/README.md#the-loop-click-what-it-is-and-how-to-test-it).
- **USB MIDI**, **USB AUDIO OUT TRACKS**, **USB CROSSBAR**, **USB AUDIO IN AB**:
  as in `usb-io-tracks-ab`. SPATIALIZER is on neither menu (its words hold
  the IN module's inject).

`tools/hw/sos_capture.py` is the procedure (fixture project, signal,
capture, port run, compare); its docstring has the commands.

```
make check REMIX=sos-capture
make image REMIX=sos-capture BUILD=1   # -> out/OCTATRACK_OCTABAM1.bin
```

Under the port only; not flashed in this form.
