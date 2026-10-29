# Is there ONE continuous function through 11/12, 7/8 and Liu? V(l)=min_b max_{delta,x} E_Liu along B=11/12-l/4, kappa=2B-1
import sys,os; sys.path.insert(0,os.path.dirname(__file__))
import numpy as np
from scipy.optimize import minimize_scalar
from sys_ import R, geom
def E_liu(b,l,k,d,x): g=geom(b,l); return -0.25+b/6+5*l/4+(0.5+l)*d+l*x*d-g['h']*(1-R(k,d,x,0))
def V(b,l,k,dlo=1e-6): return max(-minimize_scalar(lambda d:-E_liu(b,l,k,d,x),bounds=(dlo,5/6),method='bounded',options={'xatol':1e-12}).fun for x in np.linspace(0,.5,26))
print("OpenAI point inside Liu family: V(b=1/8,l=1/6,k=3/4) =",V(1/8,1/6,.75),"  (OpenAI paper slack: -2.28e-4)")
for k in (5/6,.75):
  for b in (0.0,0.06,0.125):
    print(f" l=0 (B=11/12) b={b} k={k:.3f}: V={V(b,0.0,k):.4f}")
print("V_min(l) along the line, licence k=2B-1:")
for l in np.linspace(0,0.2,11):
    k=2*(11/12-l/4)-1
    print(f"  l={l:.3f} B={11/12-l/4:.5f}  min_b V={min(V(b,l,k) for b in np.linspace(0,.2,21)):+.5f}")
