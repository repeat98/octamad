import json, numpy as np
from lin import *
from fo import fitE2, S1, e1
out = json.load(open("fo.json"))
for n2, spec, p0 in (("ls+hs1+AP", ["ls", "hs1", "ap1"], [13.2, .71, -21.5, 9000, 1.6, 52.8]),
                     ("ls+hs+AP",  ["ls", "hs", "ap1"],  [13.2, .71, -21.5, 7400, .75, 1.6, 52.8])):
    p, mr, mx, pr, px = fitE2(S1, spec, p0, -1, seeds=10)
    print(f"{n2:12s}: 20 Hz-17 kHz mag rms {mr:.3f} max {mx:.2f} dB | 20-1500 Hz phase rms {pr:5.2f} max {px:6.2f} | {np.round(p, 3).tolist()}")
    out[n2] = dict(spec1=e1["spec"], p1=e1["p"], spec2=spec, p2=p[:-1].tolist(), gain=float(p[-1]), sign=-1, D=2)
json.dump(out, open("fo.json", "w"), indent=1)
