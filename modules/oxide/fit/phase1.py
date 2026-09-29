import json, numpy as np, oxide as o
o.setp(input_level=0.0, output_level=0.0, path_select="Repro", ips="15 IPS",
       emphasis_eq="NAB", noise_reduct=True, power=True, master_bypass=False)
fs = np.r_[np.geomspace(2, 20, 16, endpoint=False), np.geomspace(20, 21500, 72)]
out = {}
for L in (-30, -40):
    out[str(L)] = [[float(f), *(lambda h: (h.real, h.imag))(o.tone_c(float(f), L)[1])] for f in fs]
json.dump(out, open("phase1.json", "w")); print("done")
