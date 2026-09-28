# SCENES KITS: the CC bridge

Lets CC MAP and Octakit share the MIDI CC dispatch entry (`0x400d64a0`).
`Kind.CF_PATCH`: one `Override`, nothing of its own to use.

Her recipe installs `gk_stock_midi_control_parameter` at the entry; CC MAP
repoints it to its cave. With the bridge the cave keeps the entry, its
fall-through symbol `CC_NEXT` becomes her handler (the build defines it from
her skipped write), and hers falls through to stock's. Order: CCs 62–73 ours,
then hers, then stock's.

`schema.Override` is the mechanism: the build skips the overridden recipe
write and, when the override names a `defsym`, defines it as the target the
skipped write carried. The ledger owns the site to the bridge and still
refuses CC MAP + OCTAKIT in a remix that does not carry it. The `octakit`
remix alone is unchanged.

The apply_part entry (`0x40009094`) needed bridging until midisc 1.40MSCN6
(13 Sep 2026) left it stock; the chain stub for it (`chains.s`) is in history.

## Measured

- `mods`, `kits` and `rig-*` build and pass every gate; the
  `octakit`-alone identities are untouched.
- Under the ColdFire port (`docs/remixer/PLACEMENT.md`): every `apply_part`
  during a project load goes to her entry; her fatal never runs.

Not measured: MIDI CCs through the chained dispatch on hardware (the port has
no MIDI input).
