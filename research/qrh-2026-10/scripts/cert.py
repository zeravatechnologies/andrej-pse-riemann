from fractions import Fraction as Fr
import numpy as np
def E(b,l,k,d,x):
    c=1/(3*k); h=(1+b+3*l)/2; ly=(1+b-l)/2
    D=3-(1+2*c)*x; P=(2-2*c*x)*(1-x); J=(Fr(5,6)-d)*D+d*P
    R=1-d+(Fr(5,6)-d)*d*P/(2*J)
    return -Fr(1,4)+b/6+5*l/4+d/2+d*x*(l+c*(h/4-ly/2))-3*h/4*(1-R), J
k,b,l=Fr(3,4),Fr(173,2000),Fr(10027,60000); g=Fr(1,10**6); L=2916000000
for (d,x) in [(Fr(1,3),Fr(1,5)),(Fr(2,5),Fr(1,2)),(Fr(1,7),Fr(0))]:
    e,J=E(b,l,k,d,x); y=Fr(1,2)-x
    A=1209956550+2343372300*y+1740394800*y**2+794068800*y**3
    B=-1135891798-1173235148*y+258347816*y**2; C=266598135+244982070*y
    print(2*L*J*(-e-g)==A*d*d+B*d+C)
# refine own optimum
def xsE(b,l,kap,d,x):
    c=1/(3*kap); h=(1+b+3*l)/2; ly=(1+b-l)/2
    D=3-(1+2*c)*x; P=(2-2*c*x)*(1-x); J=(5/6-d)*D+d*P
    R=1-d+(5/6-d)*d*P/(2*J)
    return -0.25+b/6+5*l/4+d/2+d*x*(l+c*(h/4-ly/2))-3*h/4*(1-R)
A,X=np.meshgrid(np.linspace(1/8,5/6,6001),np.linspace(0,.5,51))
print("argmax x stays at 1/2? ", X.ravel()[xsE(0.0869,0.1671,.75,A,X).argmax()])
dd=np.linspace(0.3,0.5,200001)
def M(b,l,k): return xsE(b,l,k,dd,0.5).max()
def gold(f,a,b):
    g=(5**.5-1)/2
    for _ in range(80):
        c=b-g*(b-a); d=a+g*(b-a)
        if f(c)<f(d): b=d
        else: a=c
    return (a+b)/2
def lstar(k):
    lo,hi=0.1668,0.1675
    for _ in range(50):
        m=(lo+hi)/2; bb=gold(lambda b:M(b,m,k),0.06,0.11)
        if M(bb,m,k)<0: lo=m
        else: hi=m
    return lo,bb
for k in [0.75,29991/40000]:
    l,bb=lstar(k); print("kappa",k,"l*",l,"b*",bb,"B*",11/12-l/4)
k=0.75
for i in range(4):
    l,bb=lstar(k); B=11/12-l/4; print("fixed-pt iter",i,k,B); k=2*B-1
