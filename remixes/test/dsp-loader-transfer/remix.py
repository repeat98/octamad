"""Isolated transport probe, never part of the Analog BD PR."""
from remix.schema import Remix, Proof
REMIX=Remix(name='dsp-loader-transfer',doc='Two-core dynamic-loader transport qualification.',
    family='probes',proof=Proof.RENDER,proof_note='Not for flashing; transfer gate in development.',
    modules=('DSP LOADER TRANSFER','DSP LOADER TRANSFER B','FILTER','EQUALIZER',
             'DJ EQ','PHASER','FLANGER','CHORUS','SPATIALIZER','COMB FILTER','COMPRESSOR','LO-FI','DELAY'),
    fallback='NONE')
