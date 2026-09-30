"""SYNTH MACHINE -- a two-operator FM synth machine: a FLEX track whose
sample is named FMSYNTH*.wav (or SYNTH*.wav) plays an FM voice instead of
the sample, with its own PLAYBACK page (PTCH RATO INDX FINE FDBK DEC) and, on
the LFO page, VOIC (1 = mono, 2..4 = paraphonic) and CHRD (32 chord shapes
with three inversions each, lockable per step, snapped onto SCALE QUANTIZER's
scale and root); MIDI IN plays it like the keys, fingered chords are
recorded as PTCH / CHRD / VOIC locks, LEG (AMP SETUP) is a legato switch on
every audio track, and a held trig + FUNC + UP / DOWN transposes its lock.
Since 2.9 the engine owns the AMP envelope (ATK / HOLD / REL from the AMP
page, the DSP's laws), no voice is ever cut, the peak limiter is gone, FINE
reads 0c the moment a track becomes a synth track, a sequencer trig on a
sounding note is delivered in the panel key's form, and a warm START ramps
the index envelope.

Source: `upstream/` is Tim Hastie's repository (timhastie/octatrick-modules,
submodule, pinned to v2.9 (525f4b1) = Octatrick 2.9, 29 Sep 2026; the test builds 2.3 .. 2.8 and the 2.9
line up to its previous build flashed on his MKI, the last two 2.9 fixes
emulator-verified). The declaration is
`upstream/synth/manifest.py`: the voice engine as a DRAM unit (`poly.s`,
`Linked(dram=True)`, in the platform reserve with the other DRAM modules),
the page as a pinned ROM cave (`page.s` at 0x400d24d0, the start of the
second free gap; its FM SYNTH descriptor a runtime clone of the stock
record), a SymbolRef on the kind table's FLEX and STATIC renderer entries,
detours and pokes. Its source paths are derived from its own directory, so
it is executed here from the source on disk, as the registry does for every
manifest, and this file only re-exports its MODULE. Nothing inside
`upstream/` is edited here.

2.9's engine (poly.s): sy_render presents the DSP with an always-open AMP
envelope on a synth track and applies ATK / HOLD / REL from the live lane
itself with the DSP's laws as measured (ATK linear, HOLD a timer from the
START, REL exponential floored at 1 ms; 127 = INF); a voice that still
sounds continues its oscillator from its current level, a faded one starts
from silence over 16 frames; voice stealing and hand-overs fade (8 frames,
2.9 ms); a VOIC change hands the sounding tone over; STOP ends the engine's
voices at the stock voice kill. The per-frame peak limiter is removed (the
sum is clamped; the 1/sqrt(VOIC) level law stays, a 4-note chord about
-10 dBFS). po_retrig rewrites a sequencer START on a sounding synth track
to the panel key's form so the DSP keeps its voice (the +5.6 dB bump at
every trig on a still-audible note gone: x24.8 -> x1.01 the tone's slope);
a warm START ramps the FM index envelope over 16 frames (x7.5 -> x1.07).
Cost against 2.8 (static count): +6 instructions a sample a voice in the
FM loops with the limiter's per-sample stage gone, about +15-20 % of a
VOIC 1 synth track's frame work, ~0.1-0.2 % of the frame budget; the
platform reserve and FREE MEM unchanged. Known limit: a MACHINE change
while a REL INF note sounds leaves it sounding until the next key.

On hardware as OCTATRICK9 (remix octatrick-usb) on Tim's MKI, 26 Sep 2026,
and every test build 2.3 .. 2.8 since; the 2.9 line up to the build before its
last two fixes (ROOT, the DRAM quantizer, FINE 0c, the envelope engine, no
limiter) has run on the same MKI; the last two fixes (sequencer trigs, the
index ramp) are emulator-verified only.
"""

import dataclasses
import pathlib
import runpy

from remix.schema import Category, Proof

_UPSTREAM = pathlib.Path(__file__).resolve().parent / "upstream" / "synth" / "manifest.py"

MODULE = runpy.run_path(str(_UPSTREAM), run_name="remix_manifest_synth")["MODULE"]
# The module table's fields are octabam's (README.md, `make docs`), so they
# are added here rather than in his manifest.
MODULE = dataclasses.replace(
    MODULE, category=Category.MACHINES, author="timhastie/octatrick-modules", author_url="https://github.com/timhastie/octatrick-modules",
    proof=Proof.HARDWARE, proof_note="`octatrick-usb` on his MKI, 26 Sep 2026 (OCTATRICK9) through 2.9; the last two 2.9 fixes under the port")
