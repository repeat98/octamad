"""MASTER STRIP -- two insert slots on the summed MAIN, inline after the mixdown.

The master strip of docs/proposals/MIXER.md, step 2: the slots run in place
in the TX ring at the seam (payload A, P:0x2d5) where both mixdown paths
have finished and nothing has read the buses yet. The recorder, USB audio
and the phones' MAIN share all hear them; the metronome click, added after
the pack, is added after the slots. It grows from MIXER SEAM's empty hook,
which it replaces (the ledger refuses the two together).

Three DSP sites. `boot` runs once per DSP boot (P:0x40, the first
instruction after the upload) and starts the slots where the ColdFire's
model starts (OXIDE at its 0 dB points on slot 1, slot 2 empty), so the
strip never starts from the unit's unzeroed RAM. `head` (P:0x2d5) runs the
slots on MAIN's sample 0 only, so stock's tail (the pack, the click, the cue
mix) writes sample 0 as early as stock does: the output DMA reads it about
half a sample after the mixdown. `tail` (P:0x35d, after the cue mix) runs
samples 1..15 in order and redoes what stock's tail made from them: MAIN
plus the click, the phones' cue mix, the MAIN pack. Then it takes the next
frame's slots from the record. The slots reach their effects through the
stock dispatch tables by FX id, as a track slot does.

One ColdFire unit (strip_xport.s, in DRAM) holds the model, strip_model
(two slots: an FX id and twelve knob values), and sends it to core 0 every
frame as one more burst in the host-transfer chain (state 3's entry,
MIXER.md section 7 decision 6). The DSP takes a record only when its magic
and checksum hold, masks every value to 0..127, and runs an id only from
its own list (OXIDE for now). State and records live at X:0x7c00..0x7eff
(boot.asm has the map).

A second (strip_ui.s) pages the MIXER window, in the layout Jannik locked
on 29 Sep 2026: LEFT/RIGHT walk the strips (MIXER, MASTER), UP/DOWN the
master's slots (INS 1, INS 2), A-F turn the shown slot's page-1 knobs in
strip_model with a stock MIXER knob's step, LEVEL turns MAIN, YES opens
the slot's SETUP (the strip's effect list and the effect's page-2 knobs,
drawn and turned as stock's EFFECT 2 SETUP, one window level above the
MIXER). Three detours: the window's opener and close register and remove
its input layers, and the stock draw's entry (every caller) draws the
page after the stock page.

The replaced words are pinned by hash, read from the user's own image at
build time; the manifest holds no Elektron byte.
"""

from remix.schema import Category, Detour, DspSite, Gate, Kind, Linked, Module, Proof, SymbolRef

H = bytes.fromhex

MODULE = Module(
    name="strip",
    key="MASTER STRIP",
    kind=Kind.HYBRID,
    category=Category.BUS,
    author="repeat98", author_url="https://github.com/repeat98",
    proof=Proof.PORT,
    proof_note="`verify_strip`: under the port, with and without the metronome and from dirty "
               "RAM, the main out, the phones' MAIN share and the recorder/USB pack are OXIDE's "
               "model of the stock MAIN at 0 LSB, every other TX0 word and host-port block "
               "stock's; edits of the ColdFire's model mid-run (a knob, an empty slot, a new id, "
               "the second slot) reach MAIN on a frame boundary, 0 LSB. `verify_mixerpages`: "
               "the MIXER page is stock's but for its arrow, MASTER draws its slots, the knobs "
               "step as stock's and reach core 0's record, mutes and close as stock; the "
               "slot SETUP's knob grid is stock EFFECT 2 SETUP's pixel for pixel after the "
               "same turns, and its choice reaches core 0 (29 Sep 2026); not flashed",
    doc="Two insert slots on the summed MAIN, inline after the mixdown (payload A, P:0x2d5 "
        "and P:0x35d), their effects and knobs sent from a ColdFire model every frame; "
        "a MASTER page in the MIXER window edits them.",
    requires=("OXIDE",),
    # The record: strip_model, sent to core 0 every frame by one more burst
    # in the host-transfer chain, before stock state 3 (DSP.md section 6c).
    # The MIXER window pages it (strip_ui.s): LEFT/RIGHT the strips, UP/DOWN
    # the slots, A-F the slot's knobs, YES the slot's SETUP, all writing
    # strip_model.
    linked=(Linked("stripxport", "modules/strip/strip_xport.s", dram=True),
            Linked("stripui", "modules/strip/strip_ui.s", dram=True)),
    detours=(
        Detour(0x4007D41C, H("4eb940031494"), "stripui", "mx_push",
               "MIXER opener: its input layer, then ours on top (the arrow keys)", kind="jsr"),
        Detour(0x4007D2A4, H("4eb94003146c"), "stripui", "mx_pop",
               "MIXER close: our layers off, then its own", kind="jsr"),
        Detour(0x4007C458, H("4fefffcc48d77cfc"), "stripui", "mx_draw",
               "MIXER draw (every caller): the stock draw, then the page", pad_to=8),
    ),
    symbol_refs=(
        SymbolRef(0x400ab626, 0x400049ca, "stripxport", "strip_xport",
                  note="host-transfer chain state 3 -> the strip's record first"),
    ),
    dsp_sites=(
        DspSite(
            label="boot",
            site=0x40,
            words=2,                       # `move #>$8000,b`, replayed last by the body
            stock_sha256="f801758605f2b681e59a7501b204ad6f708a1c3183e1ec6b9ae8f59549dda1ad",
            kind="jsr",
            payloads=frozenset({"A"}),
            asm="modules/strip/boot.asm",
        ),
        DspSite(
            label="head",
            site=0x2d5,
            words=2,                       # `move x:>$206,r0`, replayed last by the body
            stock_sha256="ec029b6c32da3745b6cfe7e781e84050214454fcaa3f9e5db0f52f1bbe77e971",
            kind="jsr",
            payloads=frozenset({"A"}),
            asm="modules/strip/head.asm",
        ),
        DspSite(
            label="tail",
            site=0x35d,
            words=2,                       # `move x:>$207,r0`, replayed last by the body
            stock_sha256="a0b5ecb722245d0453b9f2a04d507ade10f0a5ca2555f24760312d803f24712b",
            kind="jsr",
            payloads=frozenset({"A"}),
            asm="modules/strip/tail.asm",
        ),
    ),
    gates=(Gate("tools/verify/verify_strip.py"), Gate("tools/verify/verify_mixerpages.py")),
)
