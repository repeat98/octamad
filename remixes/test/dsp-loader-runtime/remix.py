from remix.schema import Remix,Proof
REMIX=Remix(name='dsp-loader-runtime',doc='Experimental real residency and dispatch qualification.',
    family='probes',proof=Proof.PORT,proof_note='Emulator only; not for flashing.',
    modules=('DSP LOADER RUNTIME','DSP LOADER RUNTIME B','FILTER','EQUALIZER',
             'DJ EQ','PHASER','FLANGER','CHORUS','SPATIALIZER','COMB FILTER','COMPRESSOR','CHARACTER','DELAY'),
    fallback='NONE')
