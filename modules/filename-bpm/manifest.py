"""FORCE FILENAME BPM -- a PERSONALIZE checkbox that makes the number in a
sample's filename its tempo, strictly.

Stock 1.40C does NOT read a tempo out of a filename. `0x40020ad8(count,
name)` guesses a POWER-OF-TWO beat count from the sample's length, forms
three candidate tempos from it (half, the guess, double), prints each as a
TRUNCATED INTEGER and asks `strstr(basename, that string)`; the first hit
wins and no hit keeps the middle candidate. So the name is a half/double
tiebreaker over three values, exactly as the manual says and no more: a
number that is not one of those three is ignored, and a loop whose length
is not a power-of-two number of beats can never match its own name. The
load path also skips the name entirely for samples of 50,000 samples or
fewer (~1.13 s), which get a flat 120 BPM. All measured here, 17 Sep 2026,
from the user's own 1.40C (`out/raw/section_3_MAIN_OS.bin`).

With the checkbox on this module parses the basename itself and calls the
firmware's own explicit-tempo setter `0x40099090(settings, bpm*24, len)` --
the routine behind CAL BPM FROM SELECTION -- so every derived field is
written by stock code. Three hook sites, because a tempo reaches a slot
from three directions:

  0x400992ea  the per-slot attribute init 0x40099148, after the trim words
              the setter reads are stored and after both stock arms (the
              tiebreaker's tempo, or the short arm's 120 BPM) have written
              theirs.
  0x40086b24  the project file's [SAMPLE] BPMx100 restore.
  0x40086b62  the same block's BPMx24 restore. Without these two the
              checkbox loses to the project, which is the case a user
              actually meets: a slot that has been saved once is restored,
              not re-estimated.

Off is the power-on state (the flag word starts cleared), so a user who
never opens PERSONALIZE has a stock unit.

Open: the toggle is a bare RAM word, so it does NOT survive a power cycle
-- persisting it means a new project-settings key and its writer. The
PERSONALIZE growth is the retired `patch_menu` module's mechanism (`git
show 40a1f19:tools/patch_menu.s`), which ran on hardware; this module's
own hooks have not been on a unit.
"""

from remix.schema import Detour, Kind, Linked, Module, Poke, TableGrow

H = bytes.fromhex

# The three parallel PERSONALIZE arrays, 16 u32 each, contiguous and
# immediately followed by unrelated data, so they cannot grow in place.
LABELS = 0x400B2A34
GETTERS = 0x400B2A74
SETTERS = 0x400B2AC0

# Only FIFTEEN stock entries are copied: our row takes index 15 and
# LED BRIGHTNESS is re-appended at 16 through forwarders. The item count
# is `15 - (0x46c8d18c != 0 ? -1 : 0)` = 15 or 16, a hardware-variant
# word probed from GPIO at boot (0x4001f8ce), so index 15 is the entry
# stock hides on the variant that reads zero. Appending would have hidden
# OUR row there instead; this ordering is right on both.
STOCK_ROWS = 15

MODULE = Module(
    name="filename-bpm",
    key="FORCE FILENAME BPM",
    kind=Kind.CF_PATCH,
    doc="PERSONALIZE: force a sample's tempo to the BPM in its filename "
        "(stock only uses it to pick half/double).",
    linked=(Linked("fnbpm", "modules/filename-bpm/fnbpm.s"),),
    tables=(
        TableGrow("personalize labels", old=LABELS, count=STOCK_ROWS,
                  symbols=(("fnbpm", "lbl_force"), ("fnbpm", "lbl_led")),
                  refs=((0x40068EFE, LABELS),)),
        TableGrow("personalize getters", old=GETTERS, count=STOCK_ROWS,
                  symbols=(("fnbpm", "get_force"), ("fnbpm", "get_led")),
                  refs=((0x40068F0A, GETTERS),)),
        TableGrow("personalize setters", old=SETTERS, count=STOCK_ROWS,
                  symbols=(("fnbpm", "set_force"), ("fnbpm", "set_led")),
                  refs=((0x40069022, SETTERS), (0x4006903E, SETTERS),
                        (0x40069056, SETTERS))),
    ),
    detours=(
        Detour(0x400992EA, H("42aa04447201"), "fnbpm", "load_hook",
               "sample attribute init: the filename's BPM overrides the "
               "half/double guess and the short-sample 120"),
        Detour(0x40086B24, H("254001142079460fab50"), "fnbpm", "bpm100_hook",
               "project [SAMPLE] BPMx100 restore", pad_to=10),
        Detour(0x40086B62, H("254001142079460fab50"), "fnbpm", "bpm24_hook",
               "project [SAMPLE] BPMx24 restore", pad_to=10),
    ),
    pokes=(
        Poke(0x40068FB2, expect=H("720f"), write=H("7210"),
             note="PERSONALIZE item count 15/16 -> 16/17"),
    ),
)
