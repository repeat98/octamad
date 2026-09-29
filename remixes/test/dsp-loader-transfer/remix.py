"""Isolated transport probe, never part of the Analog BD PR."""
from remix.schema import Remix, Proof
REMIX=Remix(name='dsp-loader-transfer',doc='Two-core dynamic-loader transport qualification.',
    family='probes',proof=Proof.PORT,proof_note='Both-core DMA, bounded P staging and UI message; not for flashing.',
    modules=('DSP LOADER TRANSFER','DSP LOADER TRANSFER B','FILTER','EQUALIZER',
             'DJ EQ','PHASER','FLANGER','CHORUS','SPATIALIZER','COMB FILTER','COMPRESSOR','LO-FI','DELAY'),
    fallback='NONE')
