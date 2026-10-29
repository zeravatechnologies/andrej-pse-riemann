import sys; import os; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from sys_ import *
for name,Ef,dlo in [('Liu',E_liu,0.0),('XS',E_xs,1/8)]:
    def lstar(b,k):
        return brentq(lambda l: vmax(Ef,b,l,k,dlo=max(dlo,1e-6))[0],0.15,0.19,xtol=1e-13)
    k=0.75
    for it in range(6):
        r=minimize_scalar(lambda b:-lstar(b,k),bounds=(0.05,0.14),method='bounded',options={'xatol':1e-9})
        b=r.x; l=-r.fun; B=Bof(l); k=2*B-1
    v,(d,x)=vmax(Ef,b,l,k,dlo=max(dlo,1e-6))
    print(f"{name}: B*={B:.12f} l={l:.10f} b={b:.6f} kappa={k:.10f} crit delta={d:.8f} x={x:.6f} V={v:.2e}")
    # flatness in b
    for db in (-.01,.01): print("   l*(b%+.2f)=%.10f"%(db,lstar(b+db,k)))
