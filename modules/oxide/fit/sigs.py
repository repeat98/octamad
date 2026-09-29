import numpy as np
from scipy import signal
import oxide as o
SR = o.SR
def amp_at(y,t,f):
    A=np.stack([np.sin(2*np.pi*f*t),np.cos(2*np.pi*f*t)],1); c,*_=np.linalg.lstsq(A,y,rcond=None); return np.hypot(*c)
def imd(run,lf_db,hf_db=-20,lf=100,hf=8000):
    n=SR*2; t=np.arange(n)/SR
    x=10**(lf_db/20)*np.sin(2*np.pi*lf*t)+10**(hf_db/20)*np.sin(2*np.pi*hf*t+0.7)
    y=run(x)[SR//2:]; tt=t[SR//2:]; a=amp_at(y,tt,hf)
    return o.db(a/10**(hf_db/20)), [o.db(0.5*(amp_at(y,tt,hf-k*lf)+amp_at(y,tt,hf+k*lf))/a) for k in (1,2,3,4)]
def pink(n,seed):
    r=np.random.default_rng(seed); w=r.standard_normal(n); b,a=signal.butter(1,[0.0005,0.45],btype="band"); w=signal.lfilter(b,a,w); return w/np.std(w)
def drums(n,seed=5):
    r=np.random.default_rng(seed); x=np.zeros(n); t=np.arange(n)/SR
    for k in range(0,n,SR//2):
        m=min(n-k,SR//3); tt=np.arange(m)/SR
        x[k:k+m]+=1.0*np.sin(2*np.pi*(45+90*np.exp(-tt*30))*tt)*np.exp(-tt*9)          # kick
        if (k//(SR//2))%2==1: x[k:k+m]+=0.7*r.standard_normal(m)*np.exp(-tt*25)        # snare-ish
    x+=0.25*(np.sin(2*np.pi*220*t)+np.sin(2*np.pi*277*t)+np.sin(2*np.pi*330*t))         # chord
    return x/np.max(abs(x))
bands=[(20,60),(60,120),(120,250),(250,500),(500,1000),(1000,2000),(2000,4000),(4000,8000),(8000,16000)]
def bandlevels(y):
    f,P=signal.welch(y,SR,nperseg=8192); return [10*np.log10(P[(f>=a)&(f<b)].sum()+1e-30) for a,b in bands]
