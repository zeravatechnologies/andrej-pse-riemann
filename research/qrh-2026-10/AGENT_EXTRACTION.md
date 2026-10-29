# Izvlačenje sistema eksponenata iz izvornih LaTeX fajlova

(Sažetak izvještaja pod-agenta, 2026-10-25. Sve PASS provjere su ponovo pokrenute: `results/check_agent_verification.txt`, `results/cert.txt`.)

## 1. Oct 5 — 11/12 (§2 Step 2; §3 eq. prime-extract)
- 0<ϑ≤1/10, H=D^{1+ϑ}, Y=H^{1/6}. Mean square: Σ_{N(u)≤H}|A_u|² ≪ D^{2+ϑ+ε}.
- |A₁|² ≪ D^{2+ϑ}/Y + D²/Y² = D^{11/6+5ϑ/6} + D^{5/3−ϑ/3}; cap Y=H^{1/6} aktivan; prvi član dominira.
- A₁ ≪ D^{(11+5ϑ)/12+ε} → 11/12 kao limes ϑ→0⁺. Zašto ϑ≤1/10: nije u izvoru. — PASS

## 2. Sept 30 — 7/8 (Prop "Continuation from a common signal"; §17 old-5.1; probe-low old-5.10/5.11; §26)
- b=1/8, h=13/16, ℓ=1/6, l_x=17/48, l_y=23/48, M=5/6.
- Niska: |I| ≪ Z^{l_x/2+b/12} = Z^{3/16}. Signal: C(s)=s−11/16. σ₀=1−h/6+b/12=7/8 (egzaktno).
- Visoka: E(d)=C₀+(2/3)δ+q/6−h(1−R)+(d−h)(R+δ/2−17/50), C₀=−1/48; R iz presjeka R_short i L(t).
- Certifikat −E* ≥ 49/440640; tačno −E*(79/204,1/2)=7/30672≈2.28·10⁻⁴ (rezerva). — PASS
- [DJELIMIČNO] rad nikad ne rješava max E = 0 (Liu kasnije da).

## 3. Liu (eq. balanced-extension-exponent, iv-count, iv-fixed-point-identity, iv-dual-branches)
- l_x=(1−b−ℓ)/2, l_y=(1+b−ℓ)/2, h=(1+b+3ℓ)/2; B(ℓ)=11/12−ℓ/4.
- E_B = −1/4 + b/6 + 5ℓ/4 + (1/2+ℓ)δ + ℓxδ − h(1−R); c=2/(3κ), D=3−(1+c)x, P=(2−cx)(1−x).
- Kritično (ξ,1/2): R_κ=2/3 → κ(ξ)=(18ξ²−57ξ+20)/(6(36ξ²−78ξ+25)); E=0 → ℓ=(5−6ξ)/(9+18ξ); κ=2B−1 → p(ξ)=1188ξ³−2160ξ²+171ξ+190.
- Optimum: ξ=0.388583354266, B=0.874957019420, b=0.123405685420, ℓ=0.166838588986, κ=0.749914038840. — PASS

## 4. Xu–Sang (eqs. geometry, row-functions, full-exponent, endpoint, admissible-ranges, license)
- E = C₀ + δ/2 + δx{ℓ + c(h/4 − l_y/2)} − (3h/4)(1−R_κ), c=1/(3κ), δ≥1/8; mala grana δ<1/8: ℓδx(1/2+2ℓ/h).
- Dopustivost: 29991/40000≤κ≤3/4, B>87/100, l_x>ℓ, l_y−ℓ>11b/6, 6κℓ>3/4, ℓ/h<1/(6κ), ℓ/(h+ζ)>21/100, h/2<l_y<1/2, E≤−g.
- Stage 0 (g=10⁻⁶) i Stage 1 (g=10⁻⁷) egzaktno reprodukovani; grid max E −2.23·10⁻⁶ i −2.21·10⁻⁷. — PASS
- "No claim is made that the resulting exponent is optimal" (§8).
