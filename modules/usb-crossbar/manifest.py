"""USB CROSSBAR -- the USB controller bursts, and goes first, on the crossbar.

SCM BCR = 0x3ff and, on the SDRAM and SRAM-backdoor slaves, USB first under
fixed priority (XBS PRS 0x60504321, CRS 0x10), written once at the stock USB
controller init and left on. Without it the controller's one 16-byte RX
FIFO loses the tails of isochronous OUT packets under a busy project
(Bryan T's MKII, 26 Sep 2026: 1,189 bad packets a minute at stock, 0 in ten
minutes with this). USB AUDIO IN requires it; it helps every USB transfer.
usbcrossbar.s has the numbers; README.md what is and is not measured.
"""
from remix.schema import Category, Detour, Kind, Linked, Module, Proof

H = bytes.fromhex

MODULE = Module(
    name="usb-crossbar", key="USB CROSSBAR", kind=Kind.CF_PATCH,
    category=Category.MIDI_USB, author="bryantysinger", author_url="https://github.com/bryantysinger",
    proof=Proof.HARDWARE, proof_note="the register values, written at stream-up by usbin-test builds 12-16 on Bryan T's MKII (26-27 Sep 2026); this boot-time write under the port only",
    doc="The USB controller bursts and arbitrates first on the SDRAM and SRAM crossbar ports (SCM BCR, XBS PRS/CRS), set at boot; cures lost isochronous packet tails.",
    linked=(Linked("usbcrossbar", "modules/usb-crossbar/usbcrossbar.s", cpu="5475", dram=True),),
    detours=(
        Detour(0x4001e030, H("203c08000000"), "usbcrossbar", "crossbar_init_shim",
               "USB controller init: SCM BCR and XBS PRS/CRS for slaves 2 and 4, then the displaced load"),
    ),
)
