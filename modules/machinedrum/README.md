# Machinedrum module

The core-1 layout, relocator, and driver match the plain replay baseline on
all twelve captured kits. `tools/build/md_payload.py` builds a verified
payload-B load-record artifact from the user's pinned MD OS 1.63 update,
under ignored `out/machinedrum/build/`. The original and relocated boot-init
paths also agree on all twelve captures (`md_init_gate.py`).

The manifest is still a `CF_PATCH` placeholder. The native OT machine
registration, engine and parameter delivery, sequencing, DSP loading and
hardware timing proof remain open. `make bus REMIX=machinedrum` therefore
does not yet build a usable Machinedrum machine. No flash image, sample,
`.syx`, or extracted firmware blob belongs in Git. See
`docs/proposals/MACHINEDRUM_MACHINE.md` and the WP-A2/WP-B2 reports.
