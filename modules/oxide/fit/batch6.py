import json, numpy as np, oxide as o
o.setp(input_level=0.0, output_level=0.0, path_select="Repro", ips="15 IPS",
       emphasis_eq="NAB", noise_reduct=True, power=True, master_bypass=False)
res = {}
lv = list(range(-45, 25, 3))
lf = [5.0, 6.0, 7.0, 8.5, 10.0, 12.0, 14.0, 17.0]
res["lowsplit"] = {"fs": lf, "lv": lv, "gain": [[o.tone(f, L)[0] for L in lv] for f in lf]}
fs = [12, 15, 20, 25, 30, 40, 50, 60, 80, 100, 150, 200, 400, 700, 1000, 1500, 2000, 3000, 4000, 5000, 6000]
res["harm"] = {}
for L in (-6, 0, 6):
    res["harm"][str(L)] = []
    for f in fs:
        h = o.tone_c(float(f), L, nh=5)
        res["harm"][str(L)].append([f] + [[h[k].real, h[k].imag] if k in h else None for k in (1, 3, 5)])
json.dump(res, open("batch6.json", "w")); print("done")
