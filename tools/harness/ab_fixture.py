"""Prepare owned Analog BD test copies without inheriting mixer/UI state."""
import pathlib
import re
import shutil
import sys
ROOT=pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/hw'))
import ot_project as otp


def prepare(source, destination):
    source=pathlib.Path(source);destination=pathlib.Path(destination)
    if source.resolve()==destination.resolve():
        raise ValueError('fixture preparation requires a separate output directory')
    if destination.exists():shutil.rmtree(destination)
    destination.mkdir(parents=True)
    for path in source.iterdir():
        if path.is_file() and path.suffix.lower() in ('.work','.strd'):
            shutil.copy2(path,destination/path.name)
    values=dict(BANK=0,PATTERN=0,PART=0,TRACK=0,TRACK_OTHERMODE=0,
                ARRANGEMENT_MODE=0,MIDI_MODE=0,MASTER_TRACK=0,
                CUE_STUDIO_MODE=0,MAIN_TO_CUE=0,MAIN_LEVEL=64,CUE_LEVEL=64,
                TRACK_CUE_MASK=0,TRACK_MUTE_MASK=0,TRACK_SOLO_MASK=0,
                MIDI_TRACK_MUTE_MASK=0,MIDI_TRACK_SOLO_MASK=0,
                SCENE_A_MUTE=1,SCENE_B_MUTE=1,TEMPOx24=2880)
    for path in destination.glob('project.*'):
        raw=path.read_bytes()
        for key,value in values.items():
            pattern=rb'(?m)^'+key.encode()+rb'=[^\r\n]*'
            raw,count=re.subn(pattern,key.encode()+b'='+str(value).encode(),raw)
            if not count:raise ValueError(f'{path.name}: missing fixture field {key}')
        path.write_bytes(raw)
    for path in destination.glob('bank*.work'):
        def mutate(data):
            for part in range(8):
                base=otp.PART_BASE+part*otp.PART_STRIDE+9
                for track in range(8):
                    data[base+0x22+track]=1 # ordinary FLEX, never preselect Analog BD
                    data[base+60+30*track:base+63+30*track]=bytes(3)
                    data[base+track]=data[base+8+track]=0 # FX1/FX2 NONE
                    data[base+0x12+2*track]=127 # track LEVEL
                    page=base+0x11a+24*track
                    data[page+3:page+6]=bytes(3) # no LFO depth
                    data[page+6:page+12]=bytes((0,127,127,64,64,127)) # stock AMP
                    setup=base+0x2f2+30*track
                    data[setup:setup+6]=bytes(6)
                    data[setup+6:setup+12]=bytes((1,1,0,0,0,0))
            for pattern in range(16):
                for track in range(8):
                    at=otp.trac_off(pattern,track)
                    data[at:at+64]=bytes(64) # all eight trig/lock masks
        otp._bank_write(destination,int(path.stem[4:]),mutate,guard=False)
    return destination
