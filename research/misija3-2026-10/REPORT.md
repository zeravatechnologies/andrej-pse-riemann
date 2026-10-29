# Misija 3: kompleksna verzija — izvještaj (2026-10-26)

**Nivo: NAŠE-NERECENZIRANO.** Sve brojke se mogu ponoviti: lab eksperiment „QRH: kompleksna verzija (misija 3)“ (`qrh_complex`), kod u `app/pse_r/methods/complexver.py`, testovi u `app/tests/test_r3_mission3.py`.

## Pitanja (plan, stavka 32)

- (a) Zavisi li granica od visine γ? Postaje li prava Re s = B kriva σ\*(γ), i savija li se igdje prema 1/2?
- (b) Šta su funkcije eksponenata kad im se dozvoli kompleksni argument, i gdje se signal i niska strana „sijeku“ u kompleksnom smislu?

## (a) σ\*(γ)

U Liu i Xu–Sang sistemima eksponent E(b, ℓ, κ, δ, x) **ne sadrži γ**. Razlog je |X^s| = X^σ: faza ulazi samo kroz poništavanje, a to poništavanje eksponenti već sažimaju. Zato je **u okviru tih metoda σ\*(γ) ≡ B**, odnosno prava se ne savija ni prema 1/2 ni od nje.

Zavisnost od γ mogla bi doći samo iz članova koje metoda guta u ε (stepeni log γ). To je čitanje formalizma, a ne teorema. Van ovih metoda pitanje ostaje otvoreno.

## (b) E sa kompleksnim δ

Pri validiranoj kritičnoj tački x = 1/2, brojilac E(δ) je **kvadratni polinom u δ** (tačno, sympy). Tri slučaja:

| ℓ | korijeni E(δ) = 0 | metoda |
|---|---|---|
| ℓ < ℓ\* | konjugovani par, Im δ ≠ 0 | prolazi (E < 0 za svako realno δ) |
| ℓ = ℓ\* | dvostruki korijen δ\* | granica: diskriminanta = 0 |
| ℓ > ℓ\* | dva realna korijena | pada (E > 0 između njih) |

| | Liu | Xu–Sang |
|---|---|---|
| ℓ\* (optimum) | 0.166838588986286 | 0.167120078506798 |
| ℓ iz nule diskriminante | 0.166838588986252 | 0.167120078506764 |
| razlika | 3.4·10⁻¹⁴ | 3.4·10⁻¹⁴ |
| δ\* (dvostruki korijen) | 0.38858323 | 0.46934493 |
| c u \|Im δ\| ≈ c·√(ℓ\* − ℓ) | 2.6216 | 2.3767 |

**Šta ovo znači:**
- Kompleksna verzija **ne daje novo B**, i to je rezultat.
- Daje **algebarsku karakterizaciju granice**: B\* = B(ℓ) u nuli diskriminante kvadratnog brojioca (uz b = b\*, κ = 2B − 1).
- Daje i **mjeru margine**: |Im δ|, koja raste kao korijen udaljenosti od granice.

U tabu Grafovi (Kompleksni prikaz, ugrađena „E_Liu(δ) za kompleksno δ“) pomjeranje klizača ℓ pokazuje kako se dvije realne nule stapaju u ℓ\* i odlaze u kompleksnu ravan.

## Šta ostaje otvoreno

- (a) van Liu/Xu–Sang formalizma, npr. ako se ε zamijeni eksplicitnim stepenima log γ;
- da li se karakterizacija „nula diskriminante“ prenosi na sisteme sa više grana E (metode-kao-podatak), gdje brojilac ne mora biti kvadratni;
- veza sa Liuovim kubnim polinomom za B\* (diskriminanta kao funkcija ℓ uz optimalne b, κ): nije izvedena.
