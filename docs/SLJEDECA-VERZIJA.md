# PSE Riemann — šta sljedeća verzija treba preuzeti (od Svaroga i Peruna)

Nastalo 2026-10-25 iz poređenja koda tri projekta (GitHub `main`: Svarog `d6e85bb`, Perun od 2026-10-23, PSE Riemann grana `feature/qrh-shared-lib` `3310560`). Svaki od tri projekta ima ovakav dokument: **sljedeća verzija svakog treba imati najbolje od sva tri.** Parnjaci: `svarog/docs/SLJEDECA-VERZIJA.md`, `perun/docs/SLJEDECA-VERZIJA.md`.

Oznake truda: **S** (sati), **M** (dan), **L** (više dana).

---

## A. Greške u PSE Riemannu koje je poređenje otkrilo (popraviti prvo)

| # | Šta | Gdje | Trud |
|---|---|---|---|
| A1 | „→ ∞“ čuvar (`Watchdog`) postoji, ali se **nigdje ne instancira** — pravilo iz master §5 ne radi za latenciju/memoriju/red | `app/pse_r/llm/limits.py:153` | S |
| A2 | Detekcija vrtnje (ponavljanja) radi tek **poslije** generisanja, ne prekida ga u toku | `llm/limits.py:103`, `llm/gguf.py` | S |
| A3 | Timeout pokriva samo čekanje na bravu, **ne i samo generisanje** | `llm/limits.py:78-95` | S |
| A4 | Mala trka u ljudskom redu: `decide` provjeri status pa radi `UPDATE` bez `AND status='open'` — dvije istovremene odluke mogu proći | `shared_lib/store.py:131-135` | S |

## B. Od Svaroga

| # | Šta preuzeti | Kod Svaroga | Zašto | Trud |
|---|---|---|---|---|
| B1 | **Prava prijava operatera**: lozinka, šef sa kodom za odobrenje, zaključavanje poslije neuspjelih pokušaja, CSRF + Origin provjera (za web dio) | `src/svarog/console.py:31-32, :499-511` | PSE Riemann operater je samo upisano ime — dovoljno za jednog korisnika, slabo čim ima više ljudi ili mreže | M |
| B2 | **Odobrenje se troši jednom** (consume-once) | `src/svarog/daemon.py:168` | Isto kao A4: jedna odluka = jedno izvršenje | S |
| B3 | **Vremenski ograničeno, povratno zadržavanje sa automatskim poništavanjem** (zapis na disku preživi restart) | `daemon.py:25-27, :177-191` | Za SSH čuvara: privremena IP blokada 24 h koja se sama skida | M |
| B4 | **Svaki alat deklariše da li je povratan; nedeklarisan = nepovratan** | `core/response.py:13-21, :75-76` | Za liječenje i SSH čuvara: šta smije automatski, a šta ide čovjeku | S |
| B5 | Statistički bogatija dijagnoza (CUSUM, posterior, pravilo 3-od-3) | `core/diagnosis.py`, `core/physician.py` | Naš Doktor je pragmatičan; ovo bi smanjilo lažne „infekcije“ | M |
| B6 | Čitanje dnevnika koje preživi rotaciju | `sensors/live.py` | Direktno potrebno SSH čuvaru (auth.log/journal) | S |
| B7 | Mjereni benchmark nad označenim korpusom | `bench/`, `demo/` | Tri zla i čuvari trebaju brojke lažno-pozitivnih/negativnih | M |
| B8 | Ograničena retencija (ali vidi napomenu: kod nas arhivirati + lančati, ne brisati) | `core/retention.py` | Naš dnevnik raste zauvijek | M |
| B9 | systemd hardening (`NoNewPrivileges`, `ProtectSystem`) | `packaging/deb/*.service` | Za korisnički servis SSH čuvara | S |
| B10 | mTLS federacija sa pinovanim certifikatom primarnog | `fed/node.py:62-69` | Ako PSE Riemann ikad radi u više čvorova | L |

## C. Od Peruna

| # | Šta preuzeti | Kod Peruna | Zašto | Trud |
|---|---|---|---|---|
| C1 | **Ponovljive odluke**: odluka se može ponovo izvesti iz dnevnika; neslaganje = narušen integritet | `src/perun/chain.py:29-108` | Naš lanac dokazuje da zapis nije mijenjan, ali ne i da je odluka bila ispravna | M |
| C2 | **Vanjski merač + ključ za potpis + potpisani otkucaji i pečati** | `meter.py`, `sharedlib.py:88-97` | Neko izvan procesa potvrđuje da je lanac živ i neizmijenjen | M |
| C3 | **Sidra arhive** — lanac preživi sabijanje | `chainlog.py:20-27`, `cleaning.py` | Rješenje za B8 bez gubitka dokaza | M |
| C4 | Prava autentikacija (scrypt, rang, „practice gate“, prigušenje prijava, kod šefa) | `operators.py`, `control.py:159-175` | Isto kao B1, zrelija implementacija | M |
| C5 | Atomično rješavanje stavki + rang pri promjeni odgovora | `sharedlib.py:257-297` | Rješava A4 kako treba | S |
| C6 | Operater vidi **samo šablonske rečenice** (nijedan tekst modela) | `present.py:22-37` | Naš glas citira i provjerava brojeve, ali i dalje prenosi prozu modela; za kritične poruke (alarmi, liječenje) šabloni su sigurniji | S |
| C7 | Budžeti otkrivanja (disclosure budgets) i takmičenje hipoteza | `care.py`, `thinking.py` | Uz tri zla: koliko zaštićenog sadržaja smije izaći | M |
| C8 | Klasifikator štete odbija svaku adresu koja nije ovaj računar | `harm.py:67-68` | Isti princip za naš lokalni GGUF/izvlačenje | S |
| C9 | **CI koji instalira .deb na čistom kontejneru i radi pravi poziv** | `.github/workflows/ci.yml:75-110` | Mi provjeravamo raspakivanjem; instalacija na čistom sistemu je jača provjera | S |

## D. Šta PSE Riemann već radi bolje (zadržati; detalji u dokumentima Svaroga i Peruna)

Jedna mrežna kapija (allowlist, samo https, SPKI pinning, ključ samo svom hostu, redirect bez ključa), append-only dnevnik sa okidačima i hash lancem, kapija sa „istinom statusa“ i nivoima izvora, činjenični sloj (samo SELECT kroz SQLite authorizer), prijem modela po hash-u (deklaracija → objavljeni → odbij), limiteri modela, nezavisni skeptik, pečati i čuvari izvještaja, tri zla + ljestvica liječenja (povezano u aplikaciji), siguran kompajler izraza + vrata sa testom reprodukcije, pitanje „bez interneta“, izolovani testovi, tri .deb varijante sa Provides/Conflicts i pravim dodatkom.

## E. Odloženo iz runde 3 (2026-10-25)

Ove stavke **ne ulaze** u rundu 3 (v0.2.0); ostaju za kasnije:

- **B1 / C4 — prava prijava operatera** (lozinka, šef, kod, rang, prigušenje). Andrej je odlučio „zaboravi p4“: operater ostaje samo ime. Zbog toga i C5 ulazi **bez ranga**.
- **B10 — mTLS federacija.**
- **C2 — vanjski merač + potpis.**
