import json, sys, numpy as np
from scipy import signal
import oxide as o
from model import peaking, SR
def sos_from(params):
    return np.array([np.r_[peaking(f0,Q,g)[0],peaking(f0,Q,g)[1]] for f0,Q,g in np.array(params).reshape(-1,3)])
S1=sos_from(json.load(open("E1_4.json"))); S2=sos_from(json.load(open("E2_4.json")))
E=lambda x,S: signal.sosfilt(S,x,axis=0)
K=60; UMAX=7.0
nodes=np.linspace(-UMAX,UMAX,2*K+1); dn=nodes[1]-nodes[0]
def basis(u):
    idx=np.clip((u+UMAX)/dn,0,len(nodes)-1-1e-9); i=idx.astype(int); w=idx-i
    B=np.zeros((len(u),len(nodes))); r=np.arange(len(u)); B[r,i]=1-w; B[r,i+1]=w; return B
def make_model(sol):
    return lambda x: E(np.interp(E(x,S1),nodes,sol),S2)
if __name__=="__main__":
    o.setp(input_level=0.0,output_level=0.0,path_select="Repro",ips="15 IPS",emphasis_eq="NAB",noise_reduct=False,power=True,master_bypass=False)
    cols=[];ys=[]
    for f in (300,600,1000,1700):
        for L in np.arange(-45,24.1,1.5):
            dur=0.6; t=np.arange(int(dur*SR))/SR; x=10**(L/20)*np.sin(2*np.pi*f*t)
            y=np.r_[o.run(x)[1:],0.0]; sk=int(0.25*SR)
            u=E(x,S1)[sk:]; B=E(basis(u),S2)      # E2 applied down each basis column
            # weight quiet levels more so the small-signal region is not swamped by the loud ones
            w=1.0/max(10**(min(L,6)/20),0.02)
            cols.append(B*w); ys.append(y[sk:]*w)
    A=np.vstack(cols); Y=np.concatenate(ys)
    D=np.diff(np.eye(len(nodes)),2,axis=0)*float(sys.argv[1] if len(sys.argv)>1 else 0.02)
    sol,*_=np.linalg.lstsq(np.vstack([A,D]),np.r_[Y,np.zeros(len(D))],rcond=None)
    np.save("table2.npy",np.c_[nodes,sol]); print("solved; residual rms rel", np.sqrt(np.mean((A@sol-Y)**2))/np.sqrt(np.mean(Y**2)))
