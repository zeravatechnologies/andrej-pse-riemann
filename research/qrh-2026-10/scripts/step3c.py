import sys; import os; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from scipy.optimize import minimize_scalar
from sys_ import R, geom, Bof
XS=np.array([0,.25,.4,.5])
def E_liu(b,l,k,d,x): g=geom(b,l); return -0.25+b/6+5*l/4+(0.5+l)*d+l*x*d-g['h']*(1-R(k,d,x,0))
def E_xs(b,l,k,d,x,w=.25):
    g=geom(b,l); c=1/(3*k); return -0.25+b/6+5*l/4+d/2+d*x*(l+c*(g['h']/4-g['ly']/2))-g['h']*(1-w)*(1-R(k,d,x,0))
def E_xs_small(b,l,k,d,x,w=.25):
    g=geom(b,l); return -0.25+b/6+5*l/4+d/2+l*d*x*(0.5+2*l/g['h'])-g['h']*(1-w)*(1-R(k,d,x,0))
def V(Ef,b,l,k,dlo):
    return max(-minimize_scalar(lambda d:-Ef(b,l,k,d,x),bounds=(dlo,5/6),method='bounded',options={'xatol':1e-11}).fun for x in XS)
def Vsm(Ef,b,l,k):
    return max(-minimize_scalar(lambda d:-Ef(b,l,k,d,x),bounds=(1e-6,1/8),method='bounded',options={'xatol':1e-11}).fun for x in XS)
def walls_ok(l,b,k):
    g=geom(b,l); h,lx,ly=g['h'],g['lx'],g['ly']
    return (6*k*l>.75 and l/h<1/(6*k) and lx>l and ly-l>11*b/6 and h/2<ly<.5 and l<=.2)
def lstar(Vf,b,k,lo=0.12,hi=0.2,step=1e-3):
    ls=np.arange(hi,lo,-step)
    for i,l in enumerate(ls):
        if walls_ok(l,b,k) and Vf(b,l,k)<=0:
            a,c=l,(ls[i-1] if i>0 else l)    # a feasible, c infeasible
            for _ in range(40):
                m=(a+c)/2
                if walls_ok(m,b,k) and Vf(b,m,k)<=0: a=m
                else: c=m
            return a
    return None
def optimum(Vf,iters=2):
    k=.75
    for _ in range(iters):
        bs=np.linspace(0.0,0.2,21); best=None
        for b in bs:
            l=lstar(Vf,b,k)
            if l is not None and (best is None or l>best[0]): best=(l,b)
        if best is None: return None
        # refine b
        b0=best[1]; r=minimize_scalar(lambda b:-(lstar(Vf,b,k) or 0),bounds=(max(0,b0-.005),b0+.005),method='bounded',options={'xatol':1e-7})
        l,b=-r.fun,r.x; k=2*Bof(l)-1
    return Bof(l),l,b,k
def Vxs(w): return lambda b,l,k: max(V(lambda *a:E_xs(*a,w=w),b,l,k,1/8),Vsm(lambda *a:E_xs_small(*a,w=w),b,l,k))


def Vt(t):
    def f(b,l,k):
        Ef=lambda b,l,k,d,x:E_liu(b,l,k,d,x)+t*(E_xs(b,l,k,d,x)-E_liu(b,l,k,d,x))
        Es=lambda b,l,k,d,x:E_liu(b,l,k,d,x)+t*(E_xs_small(b,l,k,d,x)-E_liu(b,l,k,d,x))
        return max(V(Ef,b,l,k,1/8),Vsm(Es,b,l,k))
    return f
def job(a):
    kind,v=a
    r=optimum(Vxs(v) if kind=='w' else Vt(v)); return kind,v,r
if __name__=="__main__":
    import multiprocessing as mp
    jobs=[('w',x) for x in (0.25,0.0,0.05,0.1,0.15,0.2,0.3,0.35)]+[('t',x) for x in (0.0,0.5,1.0,1.5,2.0,2.5,3.0)]
    with mp.Pool(mp.cpu_count()) as P:
        for kind,v,r in P.imap_unordered(job,jobs):
            print(f"{kind}={v:.3f}:",None if r is None else f"B*={r[0]:.8f} l={r[1]:.6f} b={r[2]:.5f} k={r[3]:.6f}",flush=True)
