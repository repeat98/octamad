"""RECORDER HOLD -- a recorder-buffer FLEX voice that reads one sample past
its recording repeats the last sample instead of reading zero.

Sound-on-sound (a REC3 trig with SRC3 = the track, on the step of the PLAY
trig) arms the recorder 64 samples after the play trig binds, so the voice
plays the PREVIOUS pass: its window is the current arm spacing, its content
the previous one. At a tempo whose bar is not a whole number of samples the
spacings alternate (82,687 / 82,688 at 128 BPM), and on every pass where the
window is one sample longer the voice reads index END (+0x64). No block is
mapped there: the fetch returns the pool base 0x40a955e0, a zero sample is
played, and SRC3 records it back into the loop.

Three caves, one per fetch site of the forward copy paths (the plain copy at
0x400086c2 and both reads of the crossfade copy at 0x4000853e/0x4000854e),
share one fixup (fix.inc): a fetch of index END that came back unmapped
becomes a fetch of END - 1 with a count of one, so the last sample is
repeated once. It acts only on a recorder-buffer voice (+0x15 negative)
reading forward at exactly END; every other fetch, and any index beyond END,
is stock.

Measured in the port: README.md.

Assemble (from the repo root, for the .include): `m68k-elf-as -mcpu=5475
-o x.o modules/recorder-hold/<cave>.s`; the build re-assembles and compares
against the pinned bytes below.
"""

from remix.schema import Category, Proof, CavePatch, Kind, Module

MODULE = Module(
    name="recorder-hold",
    key="RECORDER HOLD",
    kind=Kind.CF_PATCH,
    category=Category.FIXES, author="sambanks", author_url="https://github.com/sambanks",
    proof=Proof.PORT, proof_note="26 Sep 2026",
    doc="ColdFire cave: a recorder-buffer FLEX voice reading one sample past its "
        "recording repeats the last sample instead of reading zero.",
    cf_patches=(
        CavePatch(
            label="hold cave (copy)",
            cave_addr=None,
            pinned=bytes.fromhex("225f206f0004508f6100000826004a814ed10c8040a955e0660000504a816f00004a4a2a00156c000042b1ea00646600003a538820086b00002c2f012f092f002f0a206effbc4e90508f225f0c8040a955e06700000e4a816f000008588f72014e75221f203c40a955e04e75"),
            source="modules/recorder-hold/hold_copy.s",
            pool_base_literals=3,
            hook_addr=0x400086c2,
            hook_stock=bytes.fromhex("2600" "508f" "4a81"),        # move.l d0,d3 / addq.l #8,sp / tst.l d1
            report_note=" (recorder voice at END reads END - 1, not the null block)",
        ),
        CavePatch(
            label="hold cave (crossfade, +0x48)",
            cave_addr=None,
            pinned=bytes.fromhex("225f206f00046100000c264028012f2a004c4ed10c8040a955e0660000504a816f00004a4a2a00156c000042b1ea00646600003a538820086b00002c2f012f092f002f0a206effbc4e90508f225f0c8040a955e06700000e4a816f000008588f72014e75221f203c40a955e04e75"),
            source="modules/recorder-hold/hold_xfade_a.s",
            pool_base_literals=3,
            hook_addr=0x4000853e,
            hook_stock=bytes.fromhex("2640" "2801" "2f2a004c"),    # movea.l d0,a3 / move.l d1,d4 / move.l (76,a2),-(sp)
            report_note=" (as above, the crossfade copy's first read)",
        ),
        CavePatch(
            label="hold cave (crossfade, +0x4c)",
            cave_addr=None,
            pinned=bytes.fromhex("225f206f00046100000c2e004fef00104a844ed10c8040a955e0660000504a816f00004a4a2a00156c000042b1ea00646600003a538820086b00002c2f012f092f002f0a206effbc4e90508f225f0c8040a955e06700000e4a816f000008588f72014e75221f203c40a955e04e75"),
            source="modules/recorder-hold/hold_xfade_b.s",
            pool_base_literals=3,
            hook_addr=0x4000854e,
            hook_stock=bytes.fromhex("2e00" "4fef0010" "4a84"),    # move.l d0,d7 / lea (16,sp),sp / tst.l d4
            report_note=" (as above, the crossfade copy's second read)",
        ),
    ),
)
