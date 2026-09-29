#!/usr/bin/env python3
"""Compare DSP 808 to a local clean reference folder; never copies inputs to source.
Run with numpy/scipy installed: compare_bd808.py /path/to/BassDrum.
Only names matching 808BD_T<number>D<number>_Orig.wav are accepted.
"""
import argparse,hashlib,json,re,warnings
from pathlib import Path
import numpy as np
from scipy.io import wavfile
from scipy.signal import find_peaks
import bd808,bd909

def metrics(y,fs):
    peaks,_=find_peaks(y,distance=round(fs/65),prominence=.005)
    peaks=peaks[(peaks>fs*.007)&(y[peaks]>.02)]
    return dict(decay_seconds=float(-1/np.polyfit(peaks/fs,np.log(y[peaks]),1)[0]) if len(peaks)>2 else None,
                median_hz=float(1/np.median(np.diff(peaks/fs))) if len(peaks)>1 else None)

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('references',type=Path);a=ap.parse_args()
    out=bd808.OUT/'original-comparison';out.mkdir(parents=True,exist_ok=True)
    labels=bd808.build();rows=[]
    for path in sorted(a.references.glob('*_Orig.wav')):
        match=re.fullmatch(r'808BD_T(\d+)D(\d+)_Orig.wav',path.name)
        if not match:continue
        tone,decay=map(int,match.groups());assert 1<=tone<=11 and 1<=decay<=11
        with warnings.catch_warnings():
            warnings.simplefilter('ignore',wavfile.WavFileWarning);fs,raw=wavfile.read(path)
        assert fs==44100 and raw.ndim==1,(path,fs,raw.shape)
        y=raw.astype(float)/(2**(np.iinfo(raw.dtype).bits-1))
        k=bd808.INIT.copy();k[1]=round((decay-1)*127/10);k[2]=round((tone-1)*127/10);k[7]=127
        z,_=bd808.render(labels,bd909.hits(k,seconds=min(2,len(y)/fs),at=(0,)),path.stem)
        z=np.asarray(z);y=y[:len(z)]
        # No phase alignment: the residual includes the attack and pitch mismatch.
        scale=float(np.dot(y,z)/max(np.dot(z,z),1e-20))
        error=float(20*np.log10(max(np.linalg.norm(y-scale*z),1e-20)/max(np.linalg.norm(y),1e-20)))
        rows.append(dict(file=path.name,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),tone=tone,decay=decay,original=metrics(y,fs),dsp=metrics(z,fs),fitted_gain=scale,residual_db=error))
        if (tone,decay)==(7,7):
            gap=np.zeros(fs//3);bd909.wav(out/'T7D7-original-then-dsp.wav',np.concatenate([y,gap,z]))
    assert rows,'No explicitly clean original recordings found'
    (out/'measurements.json').write_text(json.dumps(rows,indent=2)+'\n')
    print(f'{len(rows)} clean originals; median gain-adjusted residual {np.median([r["residual_db"] for r in rows]):.1f} dB; {out}')
if __name__=='__main__':main()
