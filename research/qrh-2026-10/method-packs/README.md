# Paketi metoda (extraction za PSE Riemann)

Izvučeni recepti četiri QRH metode kao paketi metode (plan F8/F10). Svaki paket
je recept iz kog aplikacija sama ponovo izvodi broj iz rada (test reprodukcije,
`pse_r.methods.pack.reproduce`). Paket ulazi u aplikaciju **samo kroz vrata**
(`pse_r.methods.door.import_pack`): prvo test reprodukcije, pa ljudski red.

| paket | sistem | tvrđeno B (iz rada) | kako se provjerava |
|---|---|---|---|
| `liu.json` | **kao podatak** (+ familija `liu` kao kontrola) | 0.874957019420 | optimum sistema; slaganje sa ugrađenim kodom ≤1e-9; kubna u B mijenja znak u B* |
| `xu-sang.json` | **kao podatak** (+ familija `xs` kao kontrola) | 0.8748867 (objavljeni B₁) | optimum sistema = 0.874886647040 (naš račun), razlika 5.3e-8 ≤ tol; kvartika mijenja znak u B* |
| `openai-11-12.json` | line | 0.9166666666666666 (11/12) | tačka ℓ=0 prave B=11/12−ℓ/4 |
| `openai-7-8.json` | line | 0.875 (7/8) | tačka ℓ=1/6 prave B=11/12−ℓ/4 |

## Sistem eksponenata kao podatak (prava „otvorena vrata“)

Nov rad NE traži nov kod. Paket nosi polje `system`: definicije (`defs`), grane
visoke strane (`branches`: izraz `E` i opseg δ), `x_grid`, nisku stranu (`line`),
licencu (`licence`), opsege i zidove (`walls`). Izrazi smiju sadržati samo
aritmetiku, dozvoljena imena (`b`, `ell`, `kappa`, `delta`, `x`, `B` i ranije
definicije) i funkcije sqrt/log/exp/abs/min/max — sve ostalo kapija odbija prije
kompajliranja (`pse_r/methods/expr.py`). Aplikacija iz sistema sama nađe granicu
B* (`pse_r/methods/system.py`), poštujući zidove i fiksnu tačku licence.

Liu i Xu–Sang imaju razrješiv arXiv id → ulaze kroz vrata kao CITED kartice
(nivo PREPRINT). OpenAI 11/12 i 7/8 nemaju razrješiv id u našem materijalu, pa
se provjeravaju kao tačke prave (reprodukcija), a u biblioteci stoje kao
orijentacioni FOLKLORE izvori (vidi `vault/qrh_seed.py`).

Provjera svih paketa (iz `app/`):

```bash
.venv/bin/python -c "
from pathlib import Path
from pse_r.methods.pack import MethodPack, reproduce
for p in sorted(Path('../research/qrh-2026-10/method-packs').glob('*.json')):
    r = reproduce(MethodPack.from_file(p))
    print(p.name, 'OK' if r['ok'] else 'NE', f\"B*={r['computed_B']:.12f}\")
"
```
