import numpy as np
from fractions import Fraction as Fr

def brentq(f,a,b,xtol=1e-14):
    fa=f(a)
    for _ in range(200):
        m=(a+b)/2; fm=f(m)
        if (fm>0)==(fa>0): a,fa=m,fm
        else: b=m
        if b-a<xtol: break
    return (a+b)/2
class _R: pass
def minimize_scalar(f,bounds,method=None):
    a,b=bounds; g=(5**.5-1)/2
    for _ in range(100):
        c=b-g*(b-a); d=a+g*(b-a)
        if f(c)<f(d): b=d
        else: a=c
    r=_R(); r.x=(a+b)/2; r.fun=f(r.x); return r

print("=== 11/12 (Oct 5, eq. prime-extract) ===")
for th in [0.1,0.01,0.001,0.0]:
    t1=(2+th)-(1+th)/6   # D^{2+th}/Y, Y=H^{1/6}
    t2=2-2*(1+th)/6      # D^2/Y^2
    print(th, "2*exp terms:",t1,t2," A1 exp=",max(t1,t2)/2, " (11+5th)/12=",(11+5*th)/12)
# Y-optimization: |A1|^2 << D H/Y + D^2/Y^2, Y<=H^{1/6}
th=0.01; ys=np.linspace(0,(1+th)/6,7)
print("exp vs log_D Y:", [round(max(2+th-y,2-2*y)/2,5) for y in ys])

print("=== 7/8 (Sept 30) ===")
b,h,ell=Fr(1,8),Fr(13,16),Fr(1,6)
lx=1+ell-h; ly=lx+b
print("lx,ly",lx,ly,"low exp lx/2+b/12=",lx/2+b/12,"; C(s)=s-1+lx/2+h/6 -> sigma0=1-h/6+b/12=",1-h/6+b/12)
al=Fr(5,6)
def Estar(d,x):
    D=3-17*x/9; P=(2-8*x/9)*(1-x); J=(al-d)*D+d*P
    R=1-d+(al-d)*d*P/(2*J); q=x*d
    a=(1+d)/2; E=a-Fr(7,8)+h*(Fr(17,50)-Fr(1,6))-a*ly-(1-a)*ell-(d/2-q)*ell+h*(R+d/2-Fr(17,50))
    E2=Fr(-1,48)+Fr(2,3)*d+q/6-h*(1-R)
    assert E==E2
    return E
dd=np.linspace(0,5/6,2001); xx=np.linspace(0,.5,201)
DD,XX=np.meshgrid(dd,xx)
def Ef(d,x):
    D=3-17*x/9; P=(2-8*x/9)*(1-x); J=(5/6-d)*D+d*P
    R=1-d+(5/6-d)*d*P/(2*J); return -1/48+2/3*d+x*d/6-13/16*(1-R)
G=Ef(DD,XX); i=np.unravel_index(G.argmax(),G.shape)
print("max E* grid",G.max(),"at delta,x",DD[i],XX[i])
dc=Fr(79,204); print("exact -E* at delta=79/204,x=1/2:",-Estar(dc,Fr(1,2)),float(-Estar(dc,Fr(1,2))),"bound 49/440640=",49/440640)

print("=== Liu ===")
def liuE(b,l,kap,d,x):
    c=2/(3*kap); D=3-(1+c)*x; P=(2-c*x)*(1-x); J=(5/6-d)*D+d*P
    R=1-d+(5/6-d)*d*P/(2*J); h=(1+b+3*l)/2
    return -0.25+b/6+5*l/4+(0.5+l)*d+l*x*d-h*(1-R)
p=lambda s:1188*s**3-2160*s**2+171*s+190
xi=brentq(p,0.38858,0.38859)
B=(18*xi+7)/(18*xi+9); l=(5-6*xi)/(9+18*xi)
b=8*(3*xi-1)*(12*xi**2-40*xi+15)/(9*(2*xi+1)*(24*xi**2-20*xi+5))
kap=(18*xi**2-57*xi+20)/(6*(36*xi**2-78*xi+25))
print("xi",xi,"B",B,"11/12-l/4",11/12-l/4,"b",b,"l",l,"kappa",kap,"2B-1",2*B-1)
c=2/(3*kap); D=(5-c)/2; P=1-c/4; J=(5/6-xi)*D+xi*P; R=1-xi+(5/6-xi)*xi*P/(2*J)
print("R_kappa(xi,1/2)",R)
e=1e-6
print("E at crit",liuE(b,l,kap,xi,.5),"dE/ddelta",(liuE(b,l,kap,xi+e,.5)-liuE(b,l,kap,xi-e,.5))/(2*e),
      "dE/db",(liuE(b+e,l,kap,xi,.5)-liuE(b-e,l,kap,xi,.5))/(2*e))
G=liuE(b,l,kap,DD,XX); i=np.unravel_index(G.argmax(),G.shape); print("max E grid",G.max(),DD[i],XX[i])
# kappa(xi) from critical polynomial
k=kap; print("crit poly",(216*k-18)*xi**2-(468*k-57)*xi+150*k-20)
# Liu alg (kappa=3/4)
x0=(49-np.sqrt(921))/48; la=(33+8*np.sqrt(921))/1653; ba=-4/29+230*np.sqrt(921)/26709
print("alg: delta_c",x0,"l(x0)",(5-6*x0)/(9+18*x0),la,"B",11/12-la/4,(1507-2*np.sqrt(921))/1653,"maxE",liuE(ba,la,.75,DD,XX).max())
# iteration
kk=0.75
for n in range(6):
    xin=brentq(lambda s:(216*kk-18)*s**2-(468*kk-57)*s+150*kk-20,0.3,0.45)
    Bn=(18*xin+7)/(18*xin+9); print(" iter",n,"kappa",kk,"B",repr(Bn)); kk=2*Bn-1

print("=== Xu-Sang ===")
def xsR(kap,d,x):
    c=1/(3*kap); D=3-(1+2*c)*x; P=(2-2*c*x)*(1-x); J=(5/6-d)*D+d*P
    return 1-d+(5/6-d)*d*P/(2*J)
def xsE(b,l,kap,d,x):
    c=1/(3*kap); h=(1+b+3*l)/2; ly=(1+b-l)/2
    return -0.25+b/6+5*l/4+d/2+d*x*(l+c*(h/4-ly/2))-3*h/4*(1-xsR(kap,d,x))
def xsEs(b,l,kap,d,x):
    h=(1+b+3*l)/2
    return -0.25+b/6+5*l/4+d/2+l*d*x*(0.5+2*l/h)-3*h/4*(1-xsR(kap,d,x))
d1=np.linspace(1/8,5/6,3001); d2=np.linspace(1e-9,1/8,500)
for (k,b,l,g,Bst) in [(Fr(3,4),Fr(173,2000),Fr(10027,60000),1e-6,"69991/80000"),(Fr(29991,40000),Fr(17307,200000),Fr(1253399,7500000),1e-7,"8748867/10^7")]:
    B=Fr(11,12)-l/4; print("B(l)=",B,float(B),"stated",Bst," (1+k)/2=",(1+k)/2, float((1+k)/2))
    k,b,l=float(k),float(b),float(l); h=(1+b+3*l)/2;lx=(1-b-l)/2;ly=(1+b-l)/2
    A,X=np.meshgrid(d1,xx); M=xsE(b,l,k,A,X).max(); A2,X2=np.meshgrid(d2,xx); M2=xsEs(b,l,k,A2,X2).max()
    C0=-.25+b/6+5*l/4; Asm=.5+(l/2)*(.5+2*l/h)-h/2
    print("  max E(delta>=1/8)",M,"<-g?",M<-g,"; max Esmall",M2)
    print("  conds: lx>l",lx>l," ly-l>11b/6",ly-l>11*b/6," 6kl>3/4",6*k*l>.75," l/h<1/(6k)",l/h<1/(6*k)," h/2<ly<1/2",h/2<ly<.5,
          " max(C0,C0+Asm/8)<-1/250",max(C0,C0+Asm/8)<-1/250," floor",C0+(.5+1.5*l)/50<-.01," small",h*(17/50-1/6)-ly/2+.02<-.05)
# what limit does the method allow at fixed kappa? (own computation)
def maxE(b,l,k): 
    A,X=np.meshgrid(np.linspace(1/8,5/6,801),np.linspace(0,.5,101)); return xsE(b,l,k,A,X).max()
for k in [0.75,29991/40000]:
    def bestmax(l): return minimize_scalar(lambda b:maxE(b,l,k),bounds=(0.05,0.12),method='bounded').fun
    lstar=brentq(bestmax,0.1667,0.1680,xtol=1e-10)
    bb=minimize_scalar(lambda b:maxE(b,lstar,k),bounds=(0.05,0.12),method='bounded').x
    print(" OWN: kappa",k,"sup l with min_b max E=0:",lstar,"b",bb,"B=",11/12-lstar/4)
