import numpy as np
from scipy.optimize import minimize_scalar, brentq, minimize
# ---- common geometry (Liu / Xu-Sang) ----
def geom(b,l): return dict(lx=(1-b-l)/2, ly=(1+b-l)/2, h=(1+b+3*l)/2)
def R(kap,d,x,cfac):
    # cfac: Liu c=2/(3k) with D=3-(1+c)x ; XS c=1/(3k) with 2c -> same; use Liu form
    c=2/(3*kap); D=3-(1+c)*x; P=(2-c*x)*(1-x); J=(5/6-d)*D+d*P
    return 1-d+(5/6-d)*d*P/(2*J)
def E_liu(b,l,k,d,x):
    g=geom(b,l); return -0.25+b/6+5*l/4+(0.5+l)*d+l*x*d-g['h']*(1-R(k,d,x,0))
def E_xs(b,l,k,d,x,w=0.25):
    g=geom(b,l); c=1/(3*k)
    return -0.25+b/6+5*l/4+d/2+d*x*(l+c*(g['h']/4-g['ly']/2))-g['h']*(1-w)*(1-R(k,d,x,0))
def Bof(l): return 11/12-l/4
def vmax(Ef,b,l,k,dlo=1/8,dhi=5/6):
    # max over x in [0,1/2], d in [dlo,dhi]
    best=-1e9;arg=None
    for x in np.linspace(0,.5,51):
        r=minimize_scalar(lambda d:-Ef(b,l,k,d,x),bounds=(dlo,dhi),method='bounded',options={'xatol':1e-12})
        if -r.fun>best: best,arg=-r.fun,(r.x,x)
    # refine x
    d0,x0=arg
    r=minimize(lambda v:-Ef(b,l,k,v[0],min(max(v[1],0),.5)),[d0,x0],method='Nelder-Mead',options={'xatol':1e-12,'fatol':1e-16,'maxiter':4000})
    v=-r.fun
    return (v,(r.x[0],min(max(r.x[1],0),.5))) if v>best else (best,arg)
