# Skripte
Okruženje: `python3 -m venv venv && venv/bin/pip install sympy numpy scipy mpmath`
- `check.py`, `cert.py` — provjera izvučenih formula (11/12, 7/8, Liu, Xu–Sang)
- `plotdata.py` — podaci za fig2
- `pipeline.py` — eliminacija; **validacija: reprodukuje Liuov kubni**
- `step1.py` — numerički optimum Liu i Xu–Sang · `step1_sym2.py`/`step1_sym3.py` — polinom 4. stepena za Xu–Sang
- `continuity.py` — V(ℓ) duž prave (11/12, 7/8, Liu u jednoj familiji)
- `step23.py` — osjetljivosti, iteracija licence (njegov stari step-3 dio je zamijenjen sa step3c/step3d)
- `step3c.py`, `step3d.py` — ograničeni sweep po w i t · `walls_ladder.py` — zidovi
- `sys_.py` — zajedničke funkcije
