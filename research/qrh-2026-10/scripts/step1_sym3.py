import sympy as sp
exec(open(__import__('os').path.join(__import__('os').path.dirname(__import__('os').path.abspath(__file__)),'step1_sym2.py')).read().split("r1=sp.factor_list")[0])
N1=sp.expand(N.coeff(b,1)); N0=sp.expand(N.coeff(b,0))
bexpr=-N0/N1
g=sp.factor(sp.numer(sp.together(sp.diff(E,d).subs(b,bexpr))))
c1=sp.factor(N1)
print('N1 (b-coefficient) =',c1)
gl=[f for f,m in sp.factor_list(g)[1] if f.has(d) and abs(sp.N(f.subs(sol),30))<1e-12]
cl=[f for f,m in sp.factor_list(c1)[1] if f.has(d) and abs(sp.N(f.subs(sol),30))<1e-12]
print('cond b-flat:',cl,'\n cond d-stationary factor degs:',[(sp.degree(f,d),sp.degree(f,l)) for f in gl])
r=sp.factor_list(sp.resultant(cl[0],gl[0],d))
B=sp.symbols('B')
for f,m in r[1]:
    if f.has(l) and abs(sp.N(f.subs(sol),30))<1e-10:
        pB=sp.Poly(sp.expand(f.subs(l,4*(sp.Rational(11,12)-B))),B).primitive()[1]
        print('POLY in B (deg %d):'%pB.degree(), pB.as_expr())
        print('roots in (0.8,0.95):',[r_ for r_ in pB.nroots(n=30) if r_.is_real and 0.8<r_<0.95])
        pl=sp.Poly(f,l).primitive()[1]; print('POLY in ell:',pl.as_expr())
# also the critical delta condition alone
print('b-flat condition solved for delta at optimum:',sp.N(sol[d],25))
