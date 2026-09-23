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
        Detour(0x40004100, H("a1c0eca027400024"), "polyphony", "poly_increment_shift",
               "a POLY key's octave shift reaches the DSP increment and the fetch rate",
               pad_to=8),
        Detour(0x4000C140, H("242f0072e78a"), "polyphony", "poly_config_tstr",
               "POLY plays untimestretched: live TSTR forced OFF (the Part keeps its value)"),
        Detour(0x4000BFE8,H("733228007007"), "polyphony", "poly_live_type",
               "publish stored POLY as FLEX in the per-ping live machine mirror"),
        Detour(0x4000F450, H("4fefffc448d77cfc"), "polyphony", "poly_voice_trigger",
               "preserve the active primary before the common sample retrigger",
               pad_to=8),
        Detour(0x400334D8, H("2f02222f0008"), "polyphony", "poly_machine_name",
               "format raw machine type 5 as POLY"),
        Detour(0x4003C928, H("4bf9400a78c8"), "polyphony", "poly_src_names",
               "point SRC SETUP at a six-entry machine-name table", kind="lea"),
        # The same five-entry lookup is inlined at two more sites (the four
        # references to 0x400a78c8 in the image are these, SRC SETUP's, and
        # the function poly_machine_name replaces). Both are repointed the
        # same way: the table where the name comes from, the bound where
        # the row is admitted, no code in the path. Without them a POLY
        # track drew the out-of-range default, the string ERROR, on the
        # main page footer (measured, image 90).
        Detour(0x4003D718, H("41f9400a78c8"), "polyphony", "poly_src_names",
               "inline machine-name lookup A reads the six-entry table", kind="lea"),
        Detour(0x4004C36A, H("41f9400a78c8"), "polyphony", "poly_src_names",
               "inline machine-name lookup B reads the six-entry table", kind="lea"),
        # Restored 22 Sep 2026. These six were pulled in builds 84-89 after
        # octemu showed the UI stalling on the first track change and
        # crashing on the SRC double-click -- measured that day on an
        # emulator that never landed the DRAM runtime (it depacks through
        # the uncached alias, which octemu mapped as separate memory), so
        # EVERY detour into the runtime jumped into a zero-filled window.
        # The instrument is fixed; the hooks go back in and the bisect is
        # being re-run against a runtime that is actually there.
        Detour(0x400788C4, H("71907401b48055c07100528023c0460e739a"),
               "polyphony", "poly_sample_ui_init",
               "the sample browser opens on a POLY track as if it were FLEX",
               pad_to=18),
        Detour(0x40078950, H("42b9460e739a"), "polyphony", "poly_sample_ui_left",
               "returning left from the browser restores the POLY machine"),
        Detour(0x40079102, H("2039460e738e7601"), "polyphony", "poly_sample_ui_right",
               "entering the browser presents POLY to stock code as FLEX",
               pad_to=8),
        # SRC SETUP's own copy of the chooser (double-click SRC, FUNC+SRC)
        # keys STATIC/FLEX behaviour on its machine cursor 0x460d5c30 and
        # tests 0 and 1 only: on POLY, RIGHT did nothing (measured under
        # octemu: the handler is 0x4003d1c0, not the 0x4007909c the hooks
        # above patch, which never runs from this page). Each read that
        # picks a slot list, a Part slot byte or the load record sees FLEX;
        # the two commit sites (0x4005a616, 0x4005a850) keep the raw 5.
        Detour(0x4003A4B4, H("2439460d5c30"), "polyphony", "poly_src_cursor_scroll",
               "SRC SETUP slot-list scrolling treats POLY as FLEX"),
        Detour(0x4003C8C4, H("2c39460d5c30"), "polyphony", "poly_src_cursor_draw",
               "SRC SETUP redraw keeps a POLY slot pane open and draws the FLEX list"),
        Detour(0x4003D016, H("2239460d5c30"), "polyphony", "poly_src_cursor_record",
               "SRC SETUP load record names the FLEX slot pool for POLY"),
        Detour(0x4003D07C, H("2639460d5c30"), "polyphony", "poly_src_cursor_updown_old",
               "SRC SETUP UP/DOWN move the FLEX slot list on POLY"),
        Detour(0x4003D0FA, H("2239460d5c30"), "polyphony", "poly_src_cursor_updown_new",
               "SRC SETUP reads POLY's FLEX slot byte, not the next track's STATIC"),
        Detour(0x4003D1DA, H("2239460d5c30"), "polyphony", "poly_src_cursor_right",
               "SRC SETUP RIGHT opens the FLEX slot pane on POLY"),
        Detour(0x4005A67C, H("2039460d5c30"), "polyphony", "poly_src_cursor_commit_list",
               "SRC SETUP shows the FLEX slot list after committing POLY"),
        Detour(0x4005A766, H("2839460d5c30"), "polyphony", "poly_src_cursor_slot_yes",
               "SRC SETUP slot YES takes the FLEX path on POLY"),
        Detour(0x4005A806, H("2f39460d5c30"), "polyphony", "poly_src_cursor_slot_lookup",
               "SRC SETUP slot lookup is asked for FLEX on POLY"),
        Detour(0x4004FB94,H("4feffff048d7041c"), "polyphony", "poly_chromatic_key",
               "queue simultaneous chromatic presses; release by originating key",
               pad_to=8),
        Detour(0x4000B7BC, H("42b04c0041f946c802a6"), "polyphony", "poly_chord_dequeue",
               "drain one queued chromatic press per frame", pad_to=10),
        Detour(0x40045918, H("7401b5b9460d16fc"), "polyphony", "poly_octave_button",
               "POLY walks octaves 0..2 where stock toggles two", pad_to=8),
    ),
    pokes=(
        Poke(0x4000244E, H("7204"), H("7205"),
             "project loader accepts stored machine type 5"),
        Poke(0x40002454, H("7004"), H("7005"),
             "project loader clamps machine values above POLY to 5"),
        Poke(0x40079248, H("48780005"), H("48780006"),
             "machine chooser contains six entries, including POLY"),
        Poke(0x400585FA, H("48780005"), H("48780006"),
             "SRC SETUP selector contains six entries, including POLY"),
        Poke(0x4003C950, H("7204"), H("7205"),
             "SRC SETUP name lookup admits the POLY row"),
        Poke(0x4003D712, H("7404"), H("7405"),
             "inline machine-name lookup A admits the POLY row"),
        Poke(0x4004C364, H("7404"), H("7405"),
             "inline machine-name lookup B admits the POLY row"),
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
