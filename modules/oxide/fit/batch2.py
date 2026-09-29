import json, time
import numpy as np
import oxide as o
BASE = dict(input_level=0.0, output_level=0.0, path_select="Repro", ips="15 IPS",
            emphasis_eq="NAB", noise_reduct=True, power=True, master_bypass=False)
o.setp(**BASE)
res = {}
# (a) level curves at several frequencies, out to +24 dBFS
lv = list(range(-42, 25, 3))
res["curves"] = {str(f): o.sweep_level(f, lv) for f in (40, 100, 400, 1000, 4000, 10000)}
# (b) knobs: input_level +12 with input -12 dB vs plain 0 dBFS; output_level linearity
res["knob"] = {}
for il in (-12.0, 0.0, 12.0, 24.0):
    o.setp(input_level=il)
    res["knob"][str(il)] = [dict(level=L, **dict(zip(("gain","h2","h3","resid"),
        (lambda g,h,r,dc:(g,h[2],h[3],r))(*o.tone(1000, L))))) for L in (-36,-24,-12,-6,0)]
o.setp(input_level=0.0)
for ol in (-12.0, 12.0):
    o.setp(output_level=ol)
    g = o.tone(1000, -12)
    res["knob"]["out"+str(ol)] = dict(gain=g[0], h3=g[1][3])
o.setp(output_level=0.0)
# (c) dynamics: 1 kHz burst at level, per-cycle amplitude vs time; then step down
SR = o.SR
def env(level_db, f=1000, pre=0.2, on=0.5, off=0.5, lvl2=None):
    n = int((pre+on+off)*SR); t = np.arange(n)/SR
    a = np.zeros(n)
    a[int(pre*SR):int((pre+on)*SR)] = 10**(level_db/20)
    if lvl2 is not None: a[int((pre+on)*SR):] = 10**(lvl2/20)
    y = o.run(a*np.sin(2*np.pi*f*t))
    # amplitude per 5 ms window via LS
    w = int(0.005*SR); out=[]
    for k in range(0, n-w, w):
        tt=t[k:k+w]; A=np.stack([np.sin(2*np.pi*f*tt),np.cos(2*np.pi*f*tt)],1)
        c,*_=np.linalg.lstsq(A,y[k:k+w],rcond=None); out.append(o.db(np.hypot(*c)))
    return out
res["burst"] = {str(L): env(L, off=0.1) for L in (-24, -6, 0, 6)}
res["stepdown"] = {"0->-30": env(0, on=0.6, off=0.6, lvl2=-30, pre=0.05),
                   "-30->0": env(-30, on=0.6, off=0.6, lvl2=0, pre=0.05)}
# (d) noise
res["noise"] = {}
for nr in (True, False):
    o.setp(noise_reduct=nr)
    z = o.run(np.zeros(SR*3))[SR:]
    res["noise"]["nr_on" if nr else "nr_off"] = dict(zero_rms_db=o.db(np.sqrt(np.mean(z**2))))
    a = 10**(-60/20); t=np.arange(SR*3)/SR
    y = o.run(a*np.sin(2*np.pi*1000*t))[SR:]
    res["noise"]["nr_on_tone" if nr else "nr_off_tone"] = dict(rms_db=o.db(np.sqrt(np.mean(y**2))))
o.setp(noise_reduct=True)
# (e) two-tone: LF 100 Hz at 0 dBFS + HF 8 kHz at -20: HF gain vs HF alone
def two(lf_db, hf_db, lf=100, hf=8000):
    n=SR*2; t=np.arange(n)/SR
    x = 10**(lf_db/20)*np.sin(2*np.pi*lf*t)+10**(hf_db/20)*np.sin(2*np.pi*hf*t+0.7)
    y = o.run(x)[SR//2:]; tt=t[SR//2:]
    def amp(f):
        A=np.stack([np.sin(2*np.pi*f*tt),np.cos(2*np.pi*f*tt)],1); c,*_=np.linalg.lstsq(A,y,rcond=None); return np.hypot(*c)
    # sidebands hf +/- lf
    sb=[o.db(amp(hf-lf)/amp(hf)), o.db(amp(hf+lf)/amp(hf))]
    return dict(hf_gain=o.db(amp(hf)/10**(hf_db/20)), lf_gain=o.db(amp(lf)/10**(lf_db/20)), sb=sb)
res["imd"] = {"hf_alone": two(-200, -20), "lf0_hf-20": two(0, -20), "lf-12_hf-20": two(-12,-20), "lf-6_hf-20": two(-6,-20)}
json.dump(res, open("batch2.json","w"))
print("done", flush=True)
