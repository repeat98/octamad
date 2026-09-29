import json, numpy as np
b2=json.load(open("batch2.json")); b4=json.load(open("batch5.json"))
ref=b2["curves"]["1000"]
Lr=np.array([d["level"] for d in ref],float); Gr=np.array([d["gain"] for d in ref])
Nr=Lr+Gr
def N(l):
    l=np.asarray(l,float)
    lo=Nr[0]+(l-Lr[0])                     # below grid: linear, gain = small-signal gain
    out=np.interp(l,Lr,Nr)
    out=np.where(l<Lr[0],lo,out)
    return out
lv=np.array(b4["lv"],float); G=np.array(b4["gain"]); fs=np.array(b4["fs"])
g1k_small=Gr[0]
print("    f  Gsmall  E1     E2    rms_err(dB)")
rows=[]
for i,f in enumerate(fs):
    tot=G[i,0]-g1k_small
    best=None
    for e1 in np.arange(-10,10.01,0.05):
        e2=tot-e1
        pred=N(lv+e1)+e2-lv - g1k_small*0   # N already includes 1k offset
        # pred defined relative: 1k ref has E1=E2=0 -> gain = N(L)-L
        err=np.sqrt(np.mean((pred-G[i])**2))
        if best is None or err<best[0]: best=(err,e1,e2)
    rows.append((f,tot,best[1],best[2],best[0]))
    print(f"{f:7.0f} {tot:6.2f} {best[1]:6.2f} {best[2]:6.2f}  {best[0]:.3f}")
json.dump(rows,open("split5.json","w"))
