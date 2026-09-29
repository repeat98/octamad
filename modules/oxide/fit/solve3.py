import json, sys, numpy as np
from scipy import signal
import oxide as o
from solve2 import S1,S2,E,SR
NODES=np.r_[0.0,np.geomspace(0.01,8.0,56)]          # |u| nodes, G(0)=0
def design(u):
    """columns: G-hat functions for |u| (odd part) * sign(u), then even terms u^2, u^4 (signed by nothing)"""
    a=np.abs(u); s=np.sign(u)
    idx=np.clip(np.searchsorted(NODES,a)-1,0,len(NODES)-2)
    w=(a-NODES[idx])/(NODES[idx+1]-NODES[idx]); w=np.clip(w,0,1)
    B=np.zeros((len(u),len(NODES))); r=np.arange(len(u))
    B[r,idx]=(1-w)*s; B[r,idx+1]+=w*s
    B[a>NODES[-1],:]=0; B[a>NODES[-1],-1]=s[a>NODES[-1]]        # hold beyond last node
    ev=np.c_[u**2*(a<3), (np.minimum(a,3)**2)*np.minimum(a,3)*0+ (np.minimum(a,3)**4)]   # even terms
    return np.c_[B[:,1:],ev]                                   # drop G(0) column
def coef_to_fn(sol):
    G=np.r_[0.0,sol[:len(NODES)-1]]; c2,c4=sol[len(NODES)-1:]
    def f(u):
        a=np.abs(u); return np.sign(u)*np.interp(a,NODES,G)+c2*u**2*(a<3)+c4*np.minimum(a,3)**4
    return f,G,(c2,c4)
def make_model(f): return lambda x: E(f(E(x,S1)),S2)
if __name__=="__main__":
    lam=float(sys.argv[1]) if len(sys.argv)>1 else 1e-3
    o.setp(input_level=0.0,output_level=0.0,path_select="Repro",ips="15 IPS",emphasis_eq="NAB",noise_reduct=False,power=True,master_bypass=False)
    cols=[];ys=[]
    for f in (300,600,1000):
        for L in np.arange(-42,24.1,1.5):
            t=np.arange(int(0.5*SR))/SR; x=10**(L/20)*np.sin(2*np.pi*f*t)
            y=np.r_[o.run(x)[1:],0.0]; sk=int(0.2*SR)
            u=E(x,S1)[sk:]; B=E(design(u),S2)
            w=1.0/np.sqrt(np.mean(y[sk:]**2))
            cols.append(B*w); ys.append(y[sk:]*w)
    A=np.vstack(cols); Y=np.concatenate(ys)
    nG=len(NODES)-1
    D=np.zeros((nG-2,A.shape[1])); 
    for i in range(nG-2): D[i,i:i+3]=[1,-2,1]           # second difference of G nodes (log-spaced -> rough smoothness)
    sol,*_=np.linalg.lstsq(np.vstack([A,lam*D*np.sqrt(len(Y)/nG)]),np.r_[Y,np.zeros(len(D))],rcond=None)
    np.save("sol3.npy",sol); print("residual rel",np.sqrt(np.mean((A@sol-Y)**2))/np.sqrt(np.mean(Y**2)))
    f,G,(c2,c4)=coef_to_fn(sol); print("even terms",c2,c4)
    print("G(u)/u:",[(round(u,2),round(float(np.interp(u,NODES,G))/u,3)) for u in (0.02,0.1,0.3,0.6,0.8,1.0,1.3,1.6,2.0,3.0,6.0)])
