"""POLYPHONY PROTOTYPE -- four untimestretched render voices per audio track."""

from remix.schema import Detour, Kind, Linked, Module

H = bytes.fromhex

MODULE = Module(
    name="polyphony-proto",
    key="POLYPHONY PROTO",
    kind=Kind.CF_PATCH,
    doc="Experimental four-voice untimestretched renderer: three DRAM voice "
        "clones per audio track, with the four outputs averaged.",
    linked=(Linked("polyphony", "modules/polyphony-proto/polyphony.s", dram=True),),
    detours=(
        Detour(0x400041C4, H("4eba379a4fef0018"), "polyphony", "polyphony_call",
               "render each OFF-mode track through four voice-state slots",
               pad_to=8),
        Detour(0x40007978, H("223c000000a8"), "polyphony", "voice_pointer",
               "select the stock or prototype DRAM voice-state slot"),
    ),
)
