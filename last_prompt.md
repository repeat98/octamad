The layout direction is settled. It needs a small, limited cost on T8 and nothing else on T5–T8. Everything is pushed as c321aeb.

What I found:

The sine must sit at 0x38000. It is read as a 32K "modulo" buffer (an addressing mode that wraps within the block), so it needs a whole 32K-aligned block. In the window that means 0x30000 (T7/T8's half) or 0x38000 (T3/T4's half). The shipping BusDelay already overwrites the 19 stock words at 0x38000, so that's safe.
Core 1's private memory: 11.2K words of usable free X, plus about 45K of Y once T1–T4 give up their FX memory.
Private P is 8K per core. This is inferred from NXP's figure of 248K words of RAM on the DSP56721, split as 64K shared plus two cores' X, Y and P. Core 1 can give about 6.8K of it, and only by dropping T1–T4's stock FX code.
How much of a T5–T8 FX2 slot each stock effect uses: DARK and PLATE use almost the whole 16K slot. FLANGER and SPRING use about half, COMB and CHORUS about 3K. FILTER, EQ, DJ EQ, PHASER, LO-FI and COMPRESSOR use none, and neither does DELAY, which runs on the ColdFire.
A full MD with 16 P-I voices is about 105K words. Core 1 alone offers about 97K, and too little of it is X memory. So full fidelity needs one T7/T8 slot.
Where everything goes:

Part	Placement
MD instance	Core 1, playable on T1–T4. T1–T4 lose their stock FX.
Sine	Core 1's half of the window, 0x38000
Code	As much as fits in core 1's private P (about 6.8K), which also avoids the slower window fetches
Tables and P-I buffers read through X	Core 1's private Y, by patching those reads from X to Y where the instruction form allows it
Everything else	T8's FX2 memory (16K of the window)
The cost on T5–T8: T8's FX2 can only run effects that use no slot memory (FILTER, EQ, DJ EQ, PHASER, LO-FI, COMPRESSOR, DELAY). T5, T6 and T7, and every FX1, stay stock.

Next: an audit of the table and P-I reads, to check that each can be patched from X to Y. It covers the placement's one real risk: some reads may be paired X-and-Y instructions that can't be converted on one side. If too many are, the fallback is to take T7's FX2 memory as well.

Caveats:

Six of the twelve kits drift from the reference under the interpreter build I used for measuring (the known WP-R3 mismatch), so their late reads come from a slightly different run.
The 8K private P is inferred from NXP's total, not probed on the unit.
Sources:

NXP DSP56721 product page
DSP56720/DSP56721 datasheet