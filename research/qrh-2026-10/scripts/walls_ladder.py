# Geometry-only walls on the line B=11/12-l/4 with licence kappa=2B-1 (Xu-Sang admissibility conditions), peeled one by one
import numpy as np
l,b=np.meshgrid(np.linspace(0,1.2,3001),np.linspace(0,.8,1601))
B=11/12-l/4; k=2*B-1; h=(1+b+3*l)/2; lx=(1-b-l)/2; ly=(1+b-l)/2
C={'B>0.87':B>.87,'l<=1/5':l<=.2,'l/h<1/(6k)':(k>0)&(l/h<1/(6*k)),'6kl>3/4':6*k*l>.75,'lx>l':lx>l,'ly-l>11b/6':ly-l>11*b/6,'h/2<ly':h/2<ly,'ly<1/2':ly<.5}
dropped=[]
while True:
    ok=np.ones_like(B,bool)
    for n,c in C.items():
        if n not in dropped: ok&=c
    i=np.unravel_index(np.where(ok,B,9).argmin(),B.shape); Bm=B[i]; binds=[]
    for n in C:
        if n in dropped: continue
        ok2=np.ones_like(B,bool)
        for m,c in C.items():
            if m not in dropped and m!=n: ok2&=c
        if np.where(ok2,B,9).min()<Bm-1e-6: binds.append(n)
    print(f"dropped {dropped}: min B={Bm:.5f} (l={l[i]:.4f}, b={b[i]:.4f})  binding: {binds}")
    if not binds: break
    dropped.append(binds[0])
print("NOTE: last line (no binding wall) is the grid edge, not a result.")
