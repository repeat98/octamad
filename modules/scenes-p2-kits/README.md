# SCENES P2 KITS: the editor-entry bridge

Lets SCENES P2 and Octakit share the two page-2 editor entries (FX2
`0x4003a9dc`, FX1 `0x4003abe4`). `Kind.CF_PATCH`: two `Override`s, nothing
of its own to use. Requires both modules (`Module.requires`; the ledger
refuses a remix with the bridge and without them).

Her recipe writes `jmp <wrapper>` at each entry; the wrapper prepares a
kit-write token, calls the stock body and validates at her marker inside it
that the body stored what she expected (`track_twelve_byte_editor.S`). A
turn with a scene held must not reach the body. With the bridge her writes
are skipped and `P2_NEXT2` / `P2_NEXT1` are defined as the wrappers they
carried; SCENES P2's stubs sit at the entries and jump on to her wrapper
whenever no scene is held.

The stubs' detours displace eight bytes, the span her entry write takes,
so her trampoline's continuation at entry+8 finds the stock slot load
intact. Measured under the port (rig-kits, bottleservice, 28 Sep 2026):
the held-scene call returns and writes the pool; the unheld call reaches
her wrapper, whose protocol runs whole (marker 1, result validated), from
a `--call` and from the panel alike. Until 28 Sep the detours displaced
twelve bytes and that load was a nop under her: every unheld page-2 turn
halted in `gk_track_setup_byte_fatal`, which had been read as her wrapper
refusing a call without UI context (`docs/remixer/FAILURE_MODES.md`).
