import sys; import os; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from scipy.optimize import minimize_scalar, brentq
from sys_ import R, geom, Bof
def E_liu(b,l,k,d,x): g=geom(b,l); return -0.25+b/6+5*l/4+(0.5+l)*d+l*x*d-g['h']*(1-R(k,d,x,0))
def E_xs(b,l,k,d,x,w=.25):
    g=geom(b,l); c=1/(3*k); return -0.25+b/6+5*l/4+d/2+d*x*(l+c*(g['h']/4-g['ly']/2))-g['h']*(1-w)*(1-R(k,d,x,0))
def vmax(Ef,b,l,k,dlo,xs=(0.5,)):
    return max(-minimize_scalar(lambda d:-Ef(b,l,k,d,x),bounds=(dlo,5/6),method='bounded',options={'xatol':1e-12}).fun for x in xs)
def opt(Ef,dlo,kfix=None,bfix=None,xs=(0.5,),iters=8):
    k=0.75 if kfix is None else kfix
    for _ in range(iters):
        ls=lambda b: brentq(lambda l: vmax(Ef,b,l,k,dlo,xs),0.0,0.6,xtol=1e-14)
        if bfix is None:
            r=minimize_scalar(lambda b:-ls(b),bounds=(0.0,0.3),method='bounded',options={'xatol':1e-10}); b,l=r.x,-r.fun
        else: b,l=bfix,ls(bfix)
        if kfix is not None: break
        k=2*Bof(l)-1
    return Bof(l),l,b,k
def walls(B,l,b,k):
    g=geom(b,l); h,lx,ly=g['h'],g['lx'],g['ly']
    return {'6kl-3/4':6*k*l-.75,'1/(6k)-l/h':1/(6*k)-l/h,'lx-l':lx-l,'ly-l-11b/6':ly-l-11*b/6,'1/2-ly':.5-ly,'ly-h/2':ly-h/2,'1/5-l':.2-l,'B-0.87':B-.87,'(1+k)/2-B':(1+k)/2-B}
print("== STEP 2: points, sensitivities, walls ==")
pts={}
pts['Liu']=opt(E_liu,1e-6); pts['XS*']=opt(E_xs,1/8)
for n,(B,l,b,k) in pts.items():
    print(f"{n}: B={B:.12f} l={l:.9f} b={b:.6f} k={k:.9f}")
    W=walls(B,l,b,k); print("   walls (positive=ok):",{a:round(v,5) for a,v in W.items()})
# sensitivities: dB/dkappa at fixed kappa
for n,Ef,dlo in (('Liu',E_liu,1e-6),('XS',E_xs,1/8)):
    k0=pts['Liu' if n=='Liu' else 'XS*'][3]; e=1e-4
    Bp=opt(Ef,dlo,kfix=k0+e)[0]; Bm=opt(Ef,dlo,kfix=k0-e)[0]
    dBdk=(Bp-Bm)/(2*e); print(f"{n}: dB/dkappa={dBdk:.6f} -> licence-iteration contraction 2dB/dk={2*dBdk:.6f}")
print("== licence iteration from kappa=3/4 (transition d) ==")
for n,Ef,dlo in (('Liu',E_liu,1e-6),('XS',E_xs,1/8)):
    k=0.75; s=[]
    for i in range(5):
        B=opt(Ef,dlo,kfix=k)[0]; s.append(B); k=2*B-1
    print(n,[f"{v:.12f}" for v in s],' gaps',[f"{s[i]-s[i+1]:.2e}" for i in range(4)])
print("== STEP 3: candidate transforms ==")
B_xs0=opt(lambda b,l,k,d,x:E_xs(b,l,k,d,x,0.0),1/8)[0]
print(f"T_struct (XS structure, w=0): B={B_xs0:.10f}  vs Liu {pts['Liu'][0]:.10f}  -> structure change alone gives {B_xs0-pts['Liu'][0]:+.2e}")
print(f"T_amp (w 0->1/4 inside XS structure): {pts['XS*'][0]-B_xs0:+.2e}")
print("-- extend T_amp: continuous w, and iterated quarter-recovery w_n=1-(3/4)^n --")
for w in [0,0.25,0.4375,0.578125,0.6835,0.8,0.9,1.0]:
    try:
        B,l,b,k=opt(lambda b,l,k,d,x:E_xs(b,l,k,d,x,w),1/8,iters=6)
        W=walls(B,l,b,k); bad=[a for a,v in W.items() if v<=0]
        print(f" w={w:.4f}: B*={B:.8f} l={l:.5f} b={b:.4f} k={k:.5f}  broken walls: {bad}")
    except Exception as ex: print(' w',w,'fail',ex)
print("-- extend T_interp: E_Liu + t*(E_xs - E_Liu) --")
for t in [0,1,2,3,4]:
    Ef=lambda b,l,k,d,x,t=t:E_liu(b,l,k,d,x)+t*(E_xs(b,l,k,d,x)-E_liu(b,l,k,d,x))
    B,l,b,k=opt(Ef,1/8,iters=6); W=walls(B,l,b,k); bad=[a for a,v in W.items() if v<=0]
    print(f" t={t}: B*={B:.8f} l={l:.5f} b={b:.4f}  broken walls: {bad}")
