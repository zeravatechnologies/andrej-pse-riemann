# Primopredaja runde 3 (za novi chat), stanje 2026-10-26

**Prvo pročitaj:** `CLAUDE.md` (pravila), `docs/PLAN.md` §6 (stavke 1–38), `docs/WORKLOG.md` (tabela napretka i šta je nađeno). Plan za Andreja: `PSE Riemann — PLAN.docx` (regeneriši ga posle svake izmjene plana: `node tools/plan-docx/make_plan_docx.js`).

## Gdje smo
- Grana `feature/runda3`, lokalno i na GitHubu (`andrejristic/pse-riemann`). `main` = kraj runde 2 (`6f428b4`).
- Testovi prolaze, 210/210 (`cd app && .venv/bin/python -m pytest -q`, oko 3 min). Selftest: `app/.venv/bin/python app/main.py --selftest`.
- **Gotovo:** stavke 1–33 + 28a (misije u krug), 29b (snimak F12), prilagođavanje ekranu, ⤢ na panelima — detalji u WORKLOG. Ranije: stavke 1–27, sve provjereno testovima, a gdje se moglo i živo:
  - DeepSeek GGUF: strujanje, rok i lokalni model zatvoren za mrežu;
  - SSH čuvar na pravom journalu;
  - proces čuvara sa SIGTERM.
- **Nema nijednog API ključa** na računaru, pa cloud provajderi nisu testirani uživo. To ide u stavku 35 (vodič za živi test).

## Šta je ostalo, redom (brojevi iz `docs/PLAN.md`)
1. **28 · Engine za inspiracije („Ideje“):**
   - posle arXiv/egress čitanja predlaže ideje, nikad tvrdnje;
   - oznaka INSPIRACIJA, izvor, misija i zašto;
   - operater bira: zadrži / odbaci / pretvori u otvoreno pitanje;
   - najviše 3 sedmično, rangirano, bez duplikata, mala značka, sedmični pregled, „odgodi“;
   - skeptik napada svaku ideju prije operatera;
   - geometrijski Langlands ulazi ovdje kao INSPIRACIJA.
2. **29 · Interaktivni grafovi (tab Grafovi), najveća stavka.** Uzor je Calculus Tools: tri panela Funkcije / Grafovi / Kalkulacije, tamna pozadina, više funkcija u boji, zum i pomjeranje, režim miša „sve o tački“, računi na zahtjev uz procjenu trajanja (izvod, gradijent, Hesijan, tačan korijen + interval-certifikat, površina „rezerve“, pomak do cilja). Pored toga:
   - kompleksne funkcije: fazni portret, krive Re = 0 i Im = 0, presjeci duž prave, oblasti u ravni;
   - povezani prikazi: ravan eksponenata (σ, eksponent) ↔ kompleksna ravan;
   - klizač „niska strana + Δ“ (σ* = 11/16 + niska strana);
   - 3D površi (|ζ| iznad ravni; dvije površi eksponenata iznad (σ, ℓ) sijeku se po krivoj B(ℓ));
   - 4. dimenzija kao boja, dalje kao klizači ili animacija, male slike, paralelne koordinate;
   - matplotlib je već u paketu; profil mašine smanjuje mrežu na Aceru.
3. **30 · Graf znanja vizuelno:** čvorovi i veze; klik otvara karticu.
4. **31 · Adversarijalni mod:**
   - potraga po parametrima metode za boljim B ili za kršenjem zida;
   - certifikat praznine iznad B*;
   - rezultat ide u red, na graf i u lab run.
5. **32 · Misija 3, kompleksna verzija:**
   - σ*(γ): da li se granica savija prema 1/2;
   - E(s; …) sa kompleksnim argumentom;
   - isti meni ciljeva; aplikacija samo predlaže.
6. **33 · Radni tekst rada iz misija 2 i 3:** NAŠE-NERECENZIRANO, kroz kapiju, skeptik i adversarijalni mod.
7. **34–38 · Izdanje, uvijek posljednje:**
   - 34: uputstvo za .deb i vodiči SR/EN;
   - 35: vodič za živi test (test radi Andrej);
   - 36: CI koji instalira .deb na čistom sistemu i radi pravi poziv;
   - 37: verzija 0.2.0, tag `v0.2.0`, .exe samo kao Release;
   - 38: tri .deb + .exe, testovi, snimci, spajanje u `main` **samo uz Andrejevo „spoji u main“**, odluka o sedmičnom podsjetniku.
   - Paket mora nositi i `packaging/pse-guard-helper` (root:root, 0755, u `/usr/lib/pse-riemann/`), `app/bench/corpus.json` i `research/langlands-2026-10/REPORT.md`.

## Dogovoreno, ne mijenjati bez Andreja
- Operater je samo ime (P4 izbačen).
- Misija 2: cilj 1 (mapa prenosivosti) je obavezan; ciljeve 2 i 3 aplikacija samo predlaže, a operater bira u meniju „Cilj misije“.
- Ctrl+K je prekidač za online AI; paleta komandi je Ctrl+Shift+P.
- Zakazani zadatak: samo sedmični podsjetnik (pon 10:00), pokreće se iz foldera MORANA — ne dirati.
- Fajlovi se pišu samo u ovaj repo i na GitHub; privremeni fajlovi idu u `scratch/` (gitignored).
- Izvještaj posle svake stavke: šta je urađeno i koliko je ostalo. Pitanja u chatu, ne u popupu. Na problem: stani i javi.

## Poznata ograničenja (iskreno)
- Benchmark korpus je sintetički i na njemu su detektori podešavani; nula promašaja ≠ nula u stvarnosti.
- Acer profil je procjena, nije mjeren.
- Prefill u llama-cpp se ne može prekinuti usred.
- Prevod: sadržaj (dnevnik, kartice, odgovori modela, promptovi) ostaje na izvornom jeziku, namjerno.
- Preostalo: oko 46–90 h.


## Dopuna 2026-10-26
- Stavke 28–33 gotove (Ideje, Grafovi 6 koraka, graf znanja, adversarijalni mod, misija 3, radni tekst). Testovi 281/281, selftest ✅.
- Ostaje samo izdanje 34–38. Andrej: kompletni SR/EN vodiči za cijelu aplikaciju pišu se POSLE izgradnje .deb/.exe (pa se paketi grade još jednom). Paket mora nositi i `docs/VODIC-GRAFOVI-*.md`, `research/misija3-2026-10/REPORT.md`.
- Andrej: radi bez pitanja („ma samo radi“); izvještaj posle svake stavke.
