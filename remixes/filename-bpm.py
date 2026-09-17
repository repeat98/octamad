"""filename-bpm -- FORCE FILENAME BPM alone.

One ColdFire module, no DSP, no menu row: the PERSONALIZE checkbox and its
three tempo hooks on an otherwise stock image.
"""

from remix.schema import Remix

REMIX = Remix(
    name="filename-bpm",
    doc="FORCE FILENAME BPM: the filename's number is the sample's tempo.",
    modules=("FORCE FILENAME BPM",),
    fallback="NONE",
)
