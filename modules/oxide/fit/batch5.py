import json, numpy as np, oxide as o
BASE = dict(input_level=0.0, output_level=0.0, path_select="Repro", ips="15 IPS",
            emphasis_eq="NAB", noise_reduct=False, power=True, master_bypass=False)
o.setp(**BASE)
fs=[float(f) for f in np.geomspace(20,20000,64)]
lv=list(range(-45,25,3))
res={"fs":fs,"lv":lv,"gain":[[o.tone(f,L)[0] for L in lv] for f in fs]}
json.dump(res,open("batch5.json","w")); print("done")
