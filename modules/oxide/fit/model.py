import json, numpy as np
from scipy import signal, optimize
SR=44100
def peaking(f0,Q,gdb,sr=SR):
    A=10**(gdb/40); w=2*np.pi*f0/sr; al=np.sin(w)/(2*Q)
    b=np.array([1+al*A,-2*np.cos(w),1-al*A]); a=np.array([1+al/A,-2*np.cos(w),1-al*A/A*0+ (1-al/A)-1+0]) if False else None
    a=np.array([1+al/A,-2*np.cos(w),1-al/A])
    return b/a[0],a/a[0]
def cascade_resp(params,f,sr=SR):
    h=np.ones_like(f,dtype=complex)
    for f0,Q,g in params.reshape(-1,3):
        b,a=peaking(f0,Q,g,sr); h*=signal.freqz(b,a,worN=f,fs=sr)[1]
    return h
def fit_eq(f,target_db,n=4,seed=0):
    rng=np.random.default_rng(seed); best=None
    for trial in range(60):
        p0=[]
        for k in range(n):
            p0+= [10**rng.uniform(np.log10(25),np.log10(12000)), rng.uniform(0.4,2.0), rng.uniform(-4,4)]
        lo=[15,0.2,-24]*n; hi=[19000,6,24]*n
        try:
            r=optimize.least_squares(lambda p:20*np.log10(np.abs(cascade_resp(p,f)))-target_db,p0,bounds=(lo,hi))
        except Exception: continue
        if best is None or r.cost<best.cost: best=r
    return best.x, np.sqrt(2*best.cost/len(f))
if __name__=="__main__":
    rows=np.array(json.load(open("split.json")))
    f=rows[:,0]; E1=rows[:,2]; E2=rows[:,3]
    for name,t in (("E1",E1),("E2",E2)):
        for n in (3,4,5):
            p,e=fit_eq(f,t,n); print(name,n,"rms dB",round(e,3))
            if n==4: json.dump(p.tolist(),open(f"{name}.json","w"))
