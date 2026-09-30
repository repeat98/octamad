from remix.schema import Remix,Proof
REMIX=Remix(name='dsp-dynload',doc='Experimental real residency and dispatch qualification.',
    family='probes',proof=Proof.PORT,proof_note='Emulator-gated; a first hardware test image keeps the static originals.',
    modules=('DSP DYNLOAD','DSP DYNLOAD B','FILTER','EQUALIZER',
             'DJ EQ','PHASER','FLANGER','CHORUS','SPATIALIZER','COMB FILTER','COMPRESSOR','LO-FI','DELAY'),
    fallback='NONE')
