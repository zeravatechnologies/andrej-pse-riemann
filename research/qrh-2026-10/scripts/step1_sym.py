import sympy as sp
d,l,b,k=sp.symbols('delta ell b kappa',positive=True)
x=sp.Rational(1,2); w=sp.Rational(1,4)
def Rf(k,d,x):
    c=2/(3*k); D=3-(1+c)*x; P=(2-c*x)*(1-x); J=(sp.Rational(5,6)-d)*D+d*P
    return 1-d+(sp.Rational(5,6)-d)*d*P/(2*J)
h=(1+b+3*l)/2; ly=(1+b-l)/2; c=1/(3*k)
def EXS(w):
    return -sp.Rational(1,4)+b/6+5*l/4+d/2+d*x*(l+c*(h/4-ly/2))-h*(1-w)*(1-Rf(k,d,x))
def solve(E,label,guess):
    E=sp.together(E.subs(k,sp.Rational(5,6)-l/2))
    N=sp.numer(E)
    eqs=[sp.expand(N), sp.expand(sp.numer(sp.together(sp.diff(E,d)))), sp.expand(sp.numer(sp.together(sp.diff(E,b))))]
    sol=sp.nsolve(eqs,[d,l,b],guess,prec=40)
    print(label,'numeric:',[sp.N(s,20) for s in sol],' B=',sp.N(sp.Rational(11,12)-sol[1]/4,20))
    # eliminate b then delta -> polynomial in ell
    r1=sp.resultant(eqs[0],eqs[2],b); r2=sp.resultant(eqs[1],eqs[2],b)
    r1=sp.factor(r1); r2=sp.factor(r2)
    r=sp.resultant(sp.Poly(r1,d).as_expr(),sp.Poly(r2,d).as_expr(),d)
    fl=sp.factor_list(sp.expand(r))
    Bs=sp.symbols('B')
    for f,m in fl[1]:
        if f.has(l):
            val=f.subs(l,sol[1])
            if abs(sp.N(val,30))<1e-15*max(1,abs(sp.N(f.subs(l,sol[1]+sp.Rational(1,10**6)),30))*1e6):
                pB=sp.factor(sp.expand(f.subs(l,4*(sp.Rational(11,12)-Bs))))
                print('   factor in ell (deg',sp.degree(f,l),') vanishing at optimum;')
                print('   in B:',sp.Poly(pB,Bs).monic().as_expr() if sp.degree(pB,Bs)<=8 else '(deg %d)'%sp.degree(pB,Bs))
                print('   poly(B) primitive:',sp.Poly(pB,Bs).primitive()[1].as_expr())
    return sol
solve(EXS(w),'XS w=1/4',[0.4693,0.16712,0.0865])
