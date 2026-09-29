import json, numpy as np
from scipy import interpolate
from model import fit_eq, cascade_resp
rows=np.array(json.load(open("split5.json")))
f=rows[:,0]; fd=np.geomspace(20,20000,300)
for name,col in (("E1",2),("E2",3)):
    t=interpolate.PchipInterpolator(np.log(f),rows[:,col])(np.log(fd))
    for n in (3,4,5):
        p,e=fit_eq(fd,t,n,seed=3)
        mx=np.max(np.abs(20*np.log10(np.abs(cascade_resp(p,fd)))-t))
        print(name,n,"rms",round(e,3),"max",round(mx,3))
        if n==4: json.dump(p.tolist(),open(f"{name}_4.json","w"))
        if n==3: json.dump(p.tolist(),open(f"{name}_3.json","w"))
