import sympy as sp
d,l,b=sp.symbols('delta ell b')
x=sp.Rational(1,2)
def Rf(k,d,x):
    c=2/(3*k); D=3-(1+c)*x; P=(2-c*x)*(1-x); J=(sp.Rational(5,6)-d)*D+d*P
    return 1-d+(sp.Rational(5,6)-d)*d*P/(2*J)
k=sp.Rational(5,6)-l/2
h=(1+b+3*l)/2; ly=(1+b-l)/2; c=1/(3*k)
E=-sp.Rational(1,4)+b/6+5*l/4+d/2+d*x*(l+c*(h/4-ly/2))-h*sp.Rational(3,4)*(1-Rf(k,d,x))
E=sp.together(E)
N=sp.expand(sp.numer(E))
print('deg in b of numerator:',sp.degree(N,b),' deg d:',sp.degree(N,d),' deg l:',sp.degree(N,l))
Nb=sp.expand(sp.numer(sp.together(sp.diff(E,b))))
Nd=sp.expand(sp.numer(sp.together(sp.diff(E,d))))
sol={d:sp.Float('0.46934485869814306749',40),l:sp.Float('0.16712007850681014289',40),b:sp.Float('0.086534959255841828205',40)}
sol={kk:sp.Float(str(vv),40) for kk,vv in sp.nsolve([N,Nb,Nd],[d,l,b],[0.4693,0.16712,0.0865],prec=45,dict=True)[0].items()}
print('check',[sp.N(q.subs(sol),10) for q in (N,Nb,Nd)])
r1=sp.factor_list(sp.resultant(N,Nb,b)); r2=sp.factor_list(sp.resultant(Nd,Nb,b))
pick=lambda fl:[f for f,m in fl[1] if f.has(d) and abs(sp.N(f.subs(sol),30))<1e-12]
f1=pick(r1); f2=pick(r2)
print('f1 degs',[ (sp.degree(f,d),sp.degree(f,l)) for f in f1],' f2',[ (sp.degree(f,d),sp.degree(f,l)) for f in f2])
r=sp.factor_list(sp.resultant(f1[0],f2[0],d))
B=sp.symbols('B')
for f,m in r[1]:
    v=sp.N(f.subs(sol),30)
    print(' factor deg_l',sp.degree(f,l),' value',sp.N(v,5))
    if f.has(l) and abs(v)<1e-10:
        pB=sp.Poly(sp.expand(f.subs(l,4*(sp.Rational(11,12)-B))),B).primitive()[1]
        print('POLY in B (deg %d):'%pB.degree(), pB.as_expr())
        rts=[rt for rt in sp.Poly(pB).nroots(n=25) if rt.is_real and 0.8<rt<0.9]
        print('real roots in (0.8,0.9):',rts)
