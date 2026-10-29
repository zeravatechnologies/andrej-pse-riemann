import numpy as np, json
def Ef(d,x):
    D=3-17*x/9; P=(2-8*x/9)*(1-x); J=(5/6-d)*D+d*P
    R=1-d+(5/6-d)*d*P/(2*J); return -1/48+2/3*d+x*d/6-13/16*(1-R)
def liuE(b,l,kap,d,x):
    c=2/(3*kap); D=3-(1+c)*x; P=(2-c*x)*(1-x); J=(5/6-d)*D+d*P
    R=1-d+(5/6-d)*d*P/(2*J); h=(1+b+3*l)/2
    return -0.25+b/6+5*l/4+(0.5+l)*d+l*x*d-h*(1-R)
def xsR(kap,d,x):
    c=1/(3*kap); D=3-(1+2*c)*x; P=(2-2*c*x)*(1-x); J=(5/6-d)*D+d*P
    return 1-d+(5/6-d)*d*P/(2*J)
def xsE(b,l,kap,d,x):
    c=1/(3*kap); h=(1+b+3*l)/2; ly=(1+b-l)/2
    return -0.25+b/6+5*l/4+d/2+d*x*(l+c*(h/4-ly/2))-3*h/4*(1-xsR(kap,d,x))
xi=0.388583354266; B=(18*xi+7)/(18*xi+9); l=(5-6*xi)/(9+18*xi)
b=8*(3*xi-1)*(12*xi**2-40*xi+15)/(9*(2*xi+1)*(24*xi**2-20*xi+5))
kap=(18*xi**2-57*xi+20)/(6*(36*xi**2-78*xi+25))
d=np.linspace(0.02,5/6-0.01,120)
out={}
out['oai_d']=d.round(4).tolist(); out['oai_E']=(Ef(d,.5)*1e3).round(5).tolist()
out['liu_E']=(liuE(b,l,kap,d,.5)*1e3).round(5).tolist()
# liu with l slightly bigger (B lower) -> E crosses zero
out['liu_Ebad']=(liuE(b,l+0.002,kap,d,.5)*1e3).round(5).tolist()
dz=np.linspace(0.30,0.48,90); out['zoom_d']=dz.round(4).tolist()
out['liu_Ez']=(liuE(b,l,kap,dz,.5)*1e6).round(4).tolist()
s0=(0.75,173/2000,10027/60000); s1=(29991/40000,17307/200000,1253399/7500000)
dx=np.linspace(0.125,5/6,140); out['xs_d']=dx.round(4).tolist()
out['xs0']=(xsE(s0[1],s0[2],s0[0],dx,.5)*1e6).round(4).tolist()
out['xs1']=(xsE(s1[1],s1[2],s1[0],dx,.5)*1e6).round(4).tolist()
i0=np.argmax(out['xs0']); i1=np.argmax(out['xs1'])
print('maxima',max(out['oai_E']),max(out['liu_E']),max(out['liu_Ez']),max(out['xs0']),max(out['xs1']),dx[i0],dx[i1], max(out['liu_Ebad']))
json.dump(out,open('plotdata.json','w'))
xx=np.linspace(0,.5,501)
A,X=np.meshgrid(dx,xx)
for k,s in (('xs0',s0),('xs1',s1)):
    G=xsE(s[1],s[2],s[0],A,X).max(axis=0)*1e6
    out[k]=G.round(4).tolist(); print(k,G.max(),dx[G.argmax()])
json.dump(out,open('plotdata.json','w'))
