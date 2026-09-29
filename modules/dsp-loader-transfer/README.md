# DSP loader transfer probe (experimental)

This module is on `codex/dsp-part-loader`, separate from the Analog BD PR.
It qualifies the firmware transport before any live executable-memory writes.
It is not a finished dynamic loader and must not be flashed.

The general memory manager is intended for both stock and new effects/engines.
Stock code needs build-time packaging from the user's image, pinned per-payload
entry points, shared-helper dependencies and buffer ownership. Being stock is
not an exemption from resource accounting; being a module is not proof of safe
relocation. Fixed system code and unaudited stock algorithms remain resident.

The state-7 eDMA extension writes a 64-halfword packet to each core's working
bank +0x320, then reads 32-halfword status from +0x360. DSP frame-head hooks
validate magic, packet checksum, opcode and count, and publish acknowledgement
with the request sequence and core tag. There is currently only a PROBE opcode;
no path can write program memory or effect state.

The transfer interrupt acknowledges channel 1 as well as channel 0 and restores
channel 1's stock NBYTES at exit. Its first version missed those requirements
and produced a repeated-interrupt loop under the port; it never ran on hardware.
The firmware otherwise clears channel 1 in state 1, a path this extension does
not visit between its two status reads.

The UI-task hook displays a deferred error using the stock message function.
The messages include DSP memory full, DSP processing limit and DSP transfer
failed. Memory/processing refusal is not yet wired to the effect chooser.

Memory: packet mailboxes X:0x2320..0x235f / 0x4320..0x435f; status mirrors
X:0x2360..0x237f / 0x4360..0x437f, private to each core. The isolated remix
uses no USB input or Analog BD module. Its CF and DSP detour claims collide
with those modules where appropriate; shared transport scheduling is future
work. Do not infer general composability from this isolated probe.

Generate the freestanding ColdFire source with `python3
modules/dsp-loader-transfer/generate.py`; `--check` checks reproducibility.
Build with `make bus REMIX=dsp-loader-transfer`. The experimental verifier is
`python3 -m tools.experimental.dsp_part_loader.verify_transfer`.
