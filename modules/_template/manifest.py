"""<Module name> -- one line on what it is.

Copy this directory to modules/<yourname>/ and edit. Directories starting
with `_` are skipped by the registry, so this file is never built.

Say what the module is, what it changes, what is measured and what is
open. Delete every comment below once answered.

docs/contributing/MODULES.md is the guide; tools/remix/schema.py the field list.
This is the skeleton of a DSP effect. modules/character/ is a finished one
(an in-place insert with its own render gate). A module that changes what
the firmware does starts from modules/_template_cf/ (then modules/repitch/,
modules/midi-scenes/).
"""

from remix.schema import (BusRole, DspSection, Formatter, Gate, Harness, Kind,
                          MenuEntry, Module, Param, YBase)

MODULE = Module(
    # `name` MUST equal the directory name. `key` is the build identifier and
    # appears in the build report, which other tools parse -- so it is API.
    name="_template",
    key="TEMPLATE",
    kind=Kind.DSP_EFFECT,          # or DSP_CLIENT / CF_PATCH / HYBRID
    doc="One line, shown by `make modules`.",

    menu=MenuEntry(
        # 0x00-0x03 are stock's "no effect" synonyms and are rejected. Pick an
        # id no other module claims; the ledger will tell you if you clash.
        fx2_id=0x0a,
        # The stock descriptor this one is cloned from. EVERY FIELD YOU DO NOT
        # WRITE STAYS THE DONOR'S -- including formatters, which override the
        # value counts you do write.
        donor_desc=0x400d58b8,     # DARK REV
        # Both fields are NUL-terminated: abbr is 5 bytes = four characters,
        # fullname 13 bytes = twelve (a 5-char abbr crashes the unit on LFO
        # modulation). The schema rejects both over-lengths.
        abbr=b"TMPL",              # <=4 chars
        fullname=b"Template",      # <=12 chars, before any build tag
        build_tag=False,           # append the image's build tag to the name
    ),

    # Exactly twelve slots. Page 1 is 0-5; page 2 is 6-11. The page-2
    # knob field carries even slots, the companion field odd slots.
    # Either can carry a stepped value; put MODE on an EVEN slot, where
    # the panel's page-2 knob editor has been proven to reach it (Param).
    #
    #   name=None inherits the donor's label; b"" blanks it. Prefer writing
    #   the label even when the donor has it: the test harness reads these.
    #   count=None leaves the donor's value count.
    #   active=False means the panel does not draw it, which makes it
    #   unreachable no matter how completely it is implemented.
    #   A default outside its count is used as an INDEX and is rejected.
    params=(
        Param(b"P0", 64, active=True, formatter=Formatter.PLAIN),
        Param(b"P1", 0, active=True, formatter=Formatter.PLAIN),
        Param(), Param(), Param(), Param(),
        Param(), Param(), Param(), Param(), Param(), Param(),
    ),

    dsp=DspSection(
        asm="modules/_template/engine.asm",
        # BYTE-LOAD-BEARING: the donor region is packed in this order, so
        # changing it moves everything after it.
        priority=10,
        bus_role=BusRole.NONE,
        # When `$30000` is rewritten to this payload's half of the shared
        # window. The rewrite is a BLANKET string replace, comments included.
        ybase=YBase.NEVER,
        r7_latch_slot=None,
        gate_label=None,
    ),

    # A letter for send_probe layout strings, if this is something a local
    # render should be able to place on a track.
    harness=Harness(layout_char=None, is_server=False),

    # The checks `make check` runs when a remix carries this module: your
    # render gates (modules/character has verify_character.py). stage="image" for one that reads the built image.
    gates=(Gate("tools/verify/verify_template.py", remix_arg=False),),
    # Every knob at its DEAREST setting, by name: the mode the pricer calls
    # the worst loop, work-gating knobs at maximum. The pressure render and
    # the stress fixture use it; without it `make accept` is blocked for
    # every remix that carries the module. Checked against `params`.
    dear={"P0": 127, "P1": 127},
)
