# PSE Riemann

Asistent za dvadesetodnevno izučavanje Rimanove zeta funkcije, na PSE kernelu.
Radi na Surfaceu (4 GB, Linux Mint), na tuđim mrežama. Zavisnosti idu u
lokalni venv (`app/.venv`) — ništa sistemski.

- **Vodič:** [VODIC-SR.md](VODIC-SR.md) — počni tu, posebno §2 (uradi prije puta)
- **English:** [GUIDE-EN.md](GUIDE-EN.md)
- **Prvi put:** `cd app && ./setup.sh` (jednom, kod kuće, treba internet)
- **Pokretanje:** `cd app && ./run.sh`
- **Provjera:** `cd app && ./run.sh --selftest`
- **Plan razvoja v2:** [docs/PLAN.md](docs/PLAN.md) · napredak: [docs/WORKLOG.md](docs/WORKLOG.md)
- **Istraživanje QRH (7/8):** [research/qrh-2026-10/REPORT.md](research/qrh-2026-10/REPORT.md)

Četiri stvari koje ovo razlikuju od bilježnice sa chatom:

1. **Lab** — dvanaest mpmath eksperimenata; jedini izvor istine koji aplikacija
   sama proizvodi, svaki reproducibilan iz snimljene skripte.
2. **Kapija** — jedan put upisa. `COMPUTED` traži lab-run + sha256, `CITED`
   traži razrješiv izvor, tvrdnja o dokazu RH se odbija.
3. **Guardian** — sav saobraćaj kroz jednu funkciju: default-deny allowlist,
   TLS SPKI pinning, ključevi samo model API-jima, detekcija captive portala.
4. **Ravnoteža** — mjeri koliko čitaš tuđe naspram koliko sam izvodiš.

## Author

Created by **Andrej Ristić**, [Zerava Technologies Inc.](https://www.zeravatech.ca), Toronto.

Source: <https://github.com/zeravatechnologies/andrej-pse-riemann>
