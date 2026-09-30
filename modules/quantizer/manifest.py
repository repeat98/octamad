"""SCALE QUANTIZER -- a SCALE row in PROJECT > CONTROL > SEQUENCER (OFF, then
24 scales) and, since 2.9, a ROOT row under it (C .. B): the PTCH knob,
parameter locks and CHROMATIC trig keys snap to the scale built on the root,
key 1 of the CHROMATIC keyboard sounds the root, and a sample track's
keyboard plays the one complete root-to-root octave; a GLIDE row (OFF,
1..127) is the slide time of the synth's and a sample track's legato (the
LEG box on AMP SETUP); polyphonic chromatic keys on a synth track whose VOIC
is 2..4; the three bytes survive a power cycle in battery RAM.

Source: `upstream/` is Tim Hastie's repository (timhastie/octatrick-modules,
submodule, pinned to v2.9 (525f4b1) = Octatrick 2.9, 29 Sep 2026; the test builds 2.3 .. 2.8 and the 2.9
line up to its previous build flashed on his MKI, the last two 2.9 fixes
emulator-verified). The declaration is
`upstream/quantizer/manifest.py`: since 2.9 the quantizer itself is a DRAM
unit (`quantizer.s`, `Linked(dram=True)`, in the platform reserve with the
synth's engine), and the OS image keeps a 192-byte ROM core (`core.s`: the
boot clamps, the defaults, the root-rotated scale mask) and the two pinned
stubs (`keys.s` at KEYS_AT, `scale.s` at SCALE_AT, the trampolines the
synth's engine reads); detours, pokes and a TableGrow for the menu rows
(3 + 3 since ROOT). SCALE, GLIDE and ROOT are battery-RAM bytes
(0x100b14ec / ed / ee). The ROM footprint went from 3,319 B at 2.8 to 243 B.
Its source paths are derived from its own directory, so it is executed here
from the source on disk, as the registry does for every manifest, and this
file only re-exports its MODULE. Nothing inside `upstream/` is edited here.

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

_UPSTREAM = pathlib.Path(__file__).resolve().parent / "upstream" / "quantizer" / "manifest.py"

MODULE = runpy.run_path(str(_UPSTREAM), run_name="remix_manifest_quantizer")["MODULE"]
# The module table's fields are octabam's (README.md, `make docs`), so they
# are added here rather than in his manifest.
MODULE = dataclasses.replace(
    MODULE, category=Category.MACHINES, author="timhastie/octatrick-modules", author_url="https://github.com/timhastie/octatrick-modules",
    proof=Proof.HARDWARE, proof_note="`octatrick-usb` on his MKI, 26 Sep 2026 (OCTATRICK9) through 2.9; the last two 2.9 fixes under the port")
