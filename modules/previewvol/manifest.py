"""PREVIEW VOL -- sample previews (FUNC+YES and CUE+YES) ignore the active
track's AMP VOL and play at its default (64).

Both stock preview starters queue AMP overrides for the previewing track
but leave VOL, so a track at VOL 0 previews silent and one at 127 about
12 dB hot (measured under the port, 16 Sep 2026). One detour in each adds
VOL. docs/firmware/PREVIEW.md has the ground.
"""

from remix.schema import Detour, Kind, Linked, Module

H = bytes.fromhex

MODULE = Module(
    name="previewvol",
    key="PREVIEW VOL",
    kind=Kind.CF_PATCH,
    doc="Sample previews (FUNC+YES, CUE+YES) play at the default AMP VOL, "
        "not the active track's.",
    linked=(Linked("previewvol", "modules/previewvol/previewvol.s"),),
    detours=(
        Detour(0x40094296, H("70201140000e"), "previewvol", "vol_static",
               "STATIC preview: queue AMP VOL 64 beside REL"),
        Detour(0x40096EB2, H("72201141000e"), "previewvol", "vol_flex",
               "FLEX preview: queue AMP VOL 64 beside REL"),
    ),
)
