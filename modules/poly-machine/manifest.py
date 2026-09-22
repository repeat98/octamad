"""POLY MACHINE -- selectable four-voice untimestretched sample machine."""

from remix.schema import Detour, Kind, Linked, Module, Poke

H = bytes.fromhex
U32 = lambda value: value.to_bytes(4, "big")

MODULE = Module(
    name="poly-machine",
    key="POLY MACHINE",
    kind=Kind.CF_PATCH,
    doc="Experimental selectable POLY sample machine: the stock newest voice "
        "plus three rotating DRAM voices, mixed before the track FX chain.",
    linked=(Linked("polyphony", "modules/poly-machine/polyphony.s", dram=True),),
    detours=(
        Detour(0x400041C4, H("4eba379a4fef0018"), "polyphony", "polyphony_call",
               "render and mix four states only for raw POLY tracks", pad_to=8),
        Detour(0x40006820, H("2f0a2f02222f000c"), "polyphony", "poly_stop_voice",
               "stop the selected POLY extension without clearing the primary", pad_to=8),
        Detour(0x40007978, H("223c000000a8"), "polyphony", "voice_pointer",
               "select the stock or POLY extension voice state"),
        Detour(0x4000C0D6, H("713008002a40d080"), "polyphony", "poly_config_type",
               "alias POLY to FLEX while indexing machine configuration", pad_to=8),
        Detour(0x4000BFE8, H("733228007007"), "polyphony", "poly_live_type",
               "publish stored POLY as FLEX in the per-ping live machine mirror"),
        Detour(0x4000F450, H("4fefffc448d77cfc"), "polyphony", "poly_voice_trigger",
               "preserve the active primary before the common sample retrigger",
               pad_to=8),
        Detour(0x400334D8, H("2f02222f0008"), "polyphony", "poly_machine_name",
               "format raw machine type 5 as POLY"),
    ),
    pokes=(
        Poke(0x4000244E, H("7204"), H("7205"),
             "project loader accepts stored machine type 5"),
        Poke(0x40002454, H("7004"), H("7005"),
             "project loader clamps machine values above POLY to 5"),
        Poke(0x40078678, H("7004"), H("7005"),
             "machine chooser draws raw type 5"),
        Poke(0x400786CE, H("7004"), H("7005"),
             "machine chooser highlights raw type 5"),
        Poke(0x40079904, H("7604"), H("7605"),
             "machine chooser persists raw type 5"),
        Poke(0x400971BE, H("7005"), H("7001"),
             "operational resolver aliases stored POLY to FLEX"),
        Poke(0x400D5F4C, U32(0x400D34D2), U32(0x400D31AE),
             "POLY uses the FLEX playback-page descriptor"),
        Poke(0x400D6448, U32(0x400047F0), U32(0x40004008),
             "POLY uses the STATIC/FLEX playback-increment builder"),
        Poke(0x400D6468, U32(0x00000000), U32(0x4000F450),
             "POLY uses the STATIC/FLEX common voice initializer"),
        Poke(0x4000C02C, H("7004"), H("7005"),
             "machine-change bookkeeping accepts raw POLY"),
    ),
)
