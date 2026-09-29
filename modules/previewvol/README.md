# Preview Vol

Sample previews ([FUNC] + [YES] on the main outputs, [CUE] + [YES] on the
cue outputs) play at the default AMP VOL, whatever the active track's AMP
VOL is. Stock previews through the active track and keeps its AMP VOL, so a
track turned down on the AMP page previews quietly or not at all.

Only AMP VOL changes. The track's FX (unless PREVIEW WITHOUT FX), its main
and cue LEVEL and the MIXER volumes still apply. The track's own VOL comes
back when the preview stops.

Status: measured under the ColdFire port (`docs/firmware/PREVIEW.md`,
`python3 tools/verify/verify_previewvol.py`); not yet on hardware.
