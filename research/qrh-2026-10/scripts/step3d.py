import sys; import os; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import step3c as S, numpy as np
_orig=S.lstar
def lstar(Vf,b,k,lo=0.12,hi=0.2,step=1e-3):
    r=_orig(Vf,b,k,lo,hi,step)
    if r is None:   # probe just above the 6*kappa*l>3/4 wall
        l=0.75/(6*k)+1e-9
        if S.walls_ok(l,b,k) and Vf(b,l,k)<=0:
            a,c=l,l+step
            for _ in range(40):
                m=(a+c)/2
                if S.walls_ok(m,b,k) and Vf(b,m,k)<=0: a=m
                else: c=m
            return a
    return r
S.lstar=lstar
def job(a):
    kind,v=a; return kind,v,S.optimum(S.Vxs(v) if kind=='w' else S.Vt(v))
if __name__=="__main__":
    import multiprocessing as mp
    jobs=[('t',0.0),('t',0.5),('w',0.26),('w',0.27),('w',0.28),('w',0.3)]
    with mp.Pool(4) as P:
        for kind,v,r in P.imap_unordered(job,jobs):
            print(f"{kind}={v:.3f}:",None if r is None else f"B*={r[0]:.8f} l={r[1]:.6f} b={r[2]:.5f} k={r[3]:.6f} 6kl-3/4={6*r[3]*r[1]-.75:.2e}",flush=True)
