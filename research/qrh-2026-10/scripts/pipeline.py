import sympy as sp
d,l,b,B=sp.symbols('delta ell b B')
H=sp.Rational(1,2)
def Rf(k,d,x):
    c=2/(3*k); D=3-(1+c)*x; P=(2-c*x)*(1-x); J=(sp.Rational(5,6)-d)*D+d*P
    return 1-d+(sp.Rational(5,6)-d)*d*P/(2*J)
k=sp.Rational(5,6)-l/2          # licence fixed point kappa = 2B-1, B=11/12-l/4
h=(1+b+3*l)/2; ly=(1+b-l)/2; c=1/(3*k); x=H
def E_liu(): return -sp.Rational(1,4)+b/6+5*l/4+(H+l)*d+l*x*d-h*(1-Rf(k,d,x))
def E_xs(w): return -sp.Rational(1,4)+b/6+5*l/4+d/2+d*x*(l+c*(h/4-ly/2))-h*(1-w)*(1-Rf(k,d,x))
def optimum_poly(E,guess):
    E=sp.together(E); N=sp.expand(sp.numer(E))
    sol=sp.nsolve([N,sp.diff(N,b) if sp.degree(N,b)==1 else sp.numer(sp.together(sp.diff(E,b))),sp.numer(sp.together(sp.diff(E,d)))],[d,l,b],guess,prec=40,dict=True)[0]
    N1=sp.expand(N.coeff(b,1)); N0=sp.expand(N.coeff(b,0))
    g=sp.numer(sp.together(sp.diff(E,d).subs(b,-N0/N1)))
    ok=lambda f:f.has(d) and abs(sp.N(f.subs(sol),30))<1e-12
    cl=[f for f,m in sp.factor_list(N1)[1] if ok(f)]; gl=[f for f,m in sp.factor_list(g)[1] if ok(f)]
    for f,m in sp.factor_list(sp.resultant(cl[0],gl[0],d))[1]:
        if f.has(l) and abs(sp.N(f.subs(sol),30))<1e-10:
            pB=sp.Poly(sp.expand(f.subs(l,4*(sp.Rational(11,12)-B))),B).primitive()[1]
            return sol,pB
if __name__=='__main__':
    sol,p=optimum_poly(E_liu(),[0.3886,0.16684,0.1234])
    print('Liu via pipeline: B=',sp.N(sp.Rational(11,12)-sol[l]/4,20),' poly:',p.as_expr())
    xi=sp.symbols('xi'); liu=1188*xi**3-2160*xi**2+171*xi+190
    # B=(18xi+7)/(18xi+9) -> xi=(9B-7)/(18(1-B))
    q=sp.Poly(sp.numer(sp.together(liu.subs(xi,(9*B-7)/(18*(1-B))))),B).primitive()[1]
    print('Liu paper cubic mapped to B:',q.as_expr(),'\n same polynomial?',sp.simplify(q.monic().as_expr()-p.monic().as_expr())==0)
