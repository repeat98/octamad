# CF METER IDLE

Main's idle loop, timed, for [CF METER](../cfmeter/README.md)'s idle-time
slot. It replaces main's last init call (`0x4001fc96`, `jsr 0x40098a2c`)
and the `bras .` after it with the call and a loop that reads DMA timer 3.
A step shorter than twice the shortest step seen, + 8 counts, is added to
CF METER's idle counter; a longer step was taken by an interrupt or a
task. The shortest step goes to slot 6.

Main is the priority-0 task and never blocks (`docs/firmware/KERNEL.md`),
so it runs only when no other task is ready and no interrupt is being
served.

**Under the port** an image with this loop boots and, since 28 Sep 2026,
loads a project and answers the scripted host calls: the port reads the
`jmp` this detour leaves at `0x4001fc96` and counts PCs inside the loop's
first 0x80 bytes as main's park for its idle skip, its burst end and its
run-to-park (`tools/emu/ot_emu/rtos.cpp`, `Rtos::atSpin`,
`spinRange`); the narrative prints `main's park is detoured to ...`. A
borrowed call (`--call`, the sequencer branch) still returns to the stock
`bras .` behind the detour, where main then parks for good, so the loop's
own idle accounting stops at the first such call: the idle slot's number
needs the unit. Before 28 Sep the port advanced its clock only at the
stock `bras .` and `cfmeter` never posted its load (card ready 0); remix
`cfmeter-port` leaves the loop out. `OT_PROJECT=<dir> make check
REMIX=cfmeter`: every gate passes.
