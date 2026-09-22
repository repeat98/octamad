"""RIG HOSTS -- a new part is born hosted: T1's FX2 = BusDelay, T5's =
BusVerb, T8's (the master) = the stock DELAY (Echo Freeze, for its beat
repeat), every other track's = SEND.

One detour in the part-defaults initialiser (0x40005638), the routine that
gives a new part FX1 = FILTER and FX2 = DELAY per track: the fourteen bytes
that load the FX2 default (0x40005688..0x40005695) become a jump to
righosts.s, which writes the id by track from the manifests' ids and jumps
back. With the engines hidden from the FX2 chooser (remix `hidden`) and
locked to their host slot (`locked`), this is what makes a project made on
the unit host the bus with no stamp; an older project still needs
`ot_project.py host <project>`.

Measured under the port (22 Sep 2026): loading a project name the card does
not carry makes the firmware create one; its live FX2 ids read
6 9 9 9 7 9 9 8. FX1 stays stock's FILTER (Spectrum's id, a bit-exact
passthrough at its defaults).
"""

from remix.schema import Detour, Kind, Linked, Module

H = bytes.fromhex


def ids_inc(modules):
    """The four ids the unit writes, from the manifests. The stock DELAY
    need not be in the remix (its dispatch stays stock either way), so its
    id comes from the registry."""
    from remix import registry
    every = dict(registry.modules()); every.update(modules)
    return "".join(f"        .set    {name}, {every[key].menu.fx2_id}\n"
                   for name, key in (("ID_DELAY", "DELAY SERVER"),
                                     ("ID_VERB", "REVERB SERVER"),
                                     ("ID_SEND", "SEND"),
                                     ("ID_ECHO", "DELAY")))


MODULE = Module(
    name="rig-hosts",
    key="RIG HOSTS",
    kind=Kind.CF_PATCH,
    doc="A new part is born hosted: T1 FX2 = BusDelay, T5 = BusVerb, T8 = the stock DELAY, the rest SEND.",
    linked=(Linked("righosts", "modules/rig-hosts/righosts.s", include=ids_inc),),
    detours=(
        Detour(0x40005688, H("41f9400d4ad1226f004413500008"), "righosts", "fx2_default",
               "part-defaults initialiser: the FX2 id per track", kind="jmp", pad_to=14),
    ),
)
