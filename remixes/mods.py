"""mods -- MIDI SCENES, Octakit and the fixes in one image, stock effects only.

MIDI SCENES (bkkbrls-del), Octakit (Em), the LO-FI AMF fix (Bryan T) and
CC PAGE 2 (Sam Banks); SCENES KITS bridges CC PAGE 2 and Octakit at the CC
dispatch entry. No DSP module; the 14 stock effects are listed so the FX2
chooser is stock's. Booted under the ColdFire port; unflashed as a whole
(ok-ms, its subset, has run on hardware).

Octakit migrates Parts into Kits on load: back up projects first. midisc's
Part save/reload menu hooks against Octakit's Kit menus are unmeasured.
"""

from remix.schema import Remix

REMIX = Remix(
    name="mods",
    doc="MIDI SCENES + Octakit + the LO-FI AMF fix + CC to page 2, bridged, "
        "on the stock effects.",
    modules=("MIDI SCENES", "OCTAKIT", "LOFI AMF FIX", "CC PAGE 2", "SCENES KITS", "KITS RELOAD",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
             "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY",
             "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
