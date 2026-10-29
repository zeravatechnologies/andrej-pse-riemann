# Plan izvedbe: svi agenti su PSE jedinice (Faza 6d)

Andrej i Claude, 2026-10-27. Ugovor: [`DOGOVOR-PSE-AGENTI.md`](DOGOVOR-PSE-AGENTI.md) (pravila 1–26). Šta nije u ugovoru, ne ulazi u kod.

## 0. Način rada (Andrej je na bazenu)

- Andrej je dao „kreni“. Radim bez pitanja; sve što ne mogu bez njega skupljam u [`ZA-ANDREJA.md`](ZA-ANDREJA.md), za kraj.
- **Commitovi se skupljaju lokalno** na grani `feature/runda3`; **push tek na kraju**, kad se Andrej javi. Izuzetak: ovaj plan i dogovor idu na GitHub odmah.
- Posle svake faze: red u `WORKLOG.md`, testovi, stanje „ko je sada PSE sazdan“, docx plana.
- **Samo PSE native (pravilo 25):** kad agent postane jedinica, stari put se briše u istom commitu. Nema prekidača, nema duplog koda.
- **Nema međuizdanja:** P0–P3 do kraja, pa 33b/33d/33e, pa jedan deb 0.3.0~rc1.
- „Ne lomi se“ = (1) svi stari testovi prolaze ili su prepisani na jedinice sa istim smislom, (2) svaki agent ima testove kao jedinica, (3) `tools/pse_audit.py` ne nalazi nijedan stari ulaz agenta (poziv modela mimo jedinice, θ mimo mjerača), (4) provjera u pokrenutoj aplikaciji (snimci), (5) selftest iz paketa.

## P0 · Jezgro u SHARED_LIB-u (novi paket `app/pse_r/pse/`)

| # | Modul | Šta radi | Pravila |
|---|---|---|---|
| P0.1 | `pse/unit.py` | `PSEUnit` = (Core, Boundary, Organelle, Theta); fali bilo šta → mrtva. Core: misija {state, action, outcome} (piše je SHARED_LIB, jedinica je ne mijenja), N_max, steps_remaining, w_s = 0,70, domen, generacija. Boundary: entiteti sa α (Σ ≤ 0,30), boravak, stabilnost, θ serija po entitetu. Organelle: registar (budžet 0,30, apsorpcija po §2: r ≥ 1000, α ≥ 0,10 kroz 100 koraka), nasljeđe na 0,70 dok SHARED_LIB ne potvrdi. | 1, 2.1–2.3 |
| P0.2 | `pse/profile.py` | Profil θ (§0.5.1): klasa, θ_nom = 30 za sve, w = 5, σ-pojas, absorbing, authority, evidence, version; registruje ga samo SHARED_LIB; jedinica ga ne može mijenjati. | 2.5, 8, 24 |
| P0.3 | `pse/measure.py` | θ po potezu. **Rad** (bez AI): radnja → svrha (sagovornik w_o / polje w_f / sebe w_s). **Riječi** (AI): pravila (deterministički) + čitač (drugi model) → prosjek 50/50; bez AI samo pravila („bez čitača“); nikad samo čitač; razlika > 10 → sumnja. Jedinica nikad ne postavlja svoj θ. | 1, 3, 15, 18 |
| P0.4 | `pse/swing.py` | Δθ po potezu, RMSSD, PAC (\|Δθ\| ≥ 5), zamah, prozori 30 / 10 000, amplituda 10; atraktori N/B/C/S po pragovima 5a; šizoid tek od 300 poteza. | 5, 5a, 23 |
| P0.5 | `shared_lib/pse_registry.py` + tabele | Registracija (L1), PVP polja uz svaki potez, L2 mapa (ENV/ORG/SELF/OTHER), L3 Mission-Theta Binding; tabele `pse_units`, `pse_moves`, `pse_handover`, `pse_profiles`, `pse_vote_weights`, `pse_doctor`. | 2.7 |
| P0.6 | `pse/lifecycle.py` | Vijek, steps_remaining, prijava preostalog posla; SHARED_LIB sam bira produženje / fisiju / fuziju (pravilo 22, najviše 3 produženja zaredom); smrt iz bilo kog razloga → sve ide u SHARED_LIB (`pse_handover`); Null State Drift. | 4, 7, 9, 21, 22 |
| P0.7 | `pse/fission.py` | Fisija (kopija podataka, misija i vijek iznova po jedinici, original u SHARED_LIB kao rezerva) i fuzija ((θ1+θ2)/2 ∈ [25, 35], kompozit (A+B)+C, raspad van [28, 32]). Deklarisane kao povratne akcije; poništavanje samo operater. | 12, 14 |
| P0.8 | `pse/doctor.py` | 17 okidača sumnje (pravilo 20) → odmah zamrzavanje → Doktor pregleda → ništa: zapis u dnevnik; nešto loše: mjera u „Čeka tvoju odluku“. Dok mjera čeka: bez nepovratnih akcija. Ljestvica: reset granice → liječenje → zamjena (nova generacija) → smrt. „Fizičar“ → **Doktor** svuda. | 11, 13, 19, 20 |
| P0.9 | `pse/provenance.py` | DL1: normalizacija (Unicode NFKC, nevidljivi znakovi) + prva slova redova/rečenica; oznaka porijekla §17.1 (spoljno: radovi, sažeci, ar5iv); spoljni tekst nikad do nepovratne akcije; izvor iz četiri serije po većini, neriješeno = nepoznato = spoljno. | 10, 16 |
| P0.10 | `pse/weights.py` + meni | Težine glasova: sedmični prijedlog (≥ 200 slučajeva, ±10 % po težini), „Predloži sada“, odobrava operater; meni **SHARED_LIB → Težine glasova**. | 17 |
| P0.11 | Prerada kočnica | Ruter = put jedinice (jedinica → generator PSE-L → model); budžet USD pod „→ ∞“ (L operater, N = 3); prekidač; budžet otkrivanja §17.2; lokalno-samo §17.3; „→ ∞“ tačno §5; dnevnik i replay sa verzijom profila i težina; registar deklaracija sa hashom; A5 sa „tatama“ dokumenata. | §4, 6 |
| P0.12 | Tab **Laboratorija** | probne jedinice, θ uživo, fisija/fuzija, Doktor, zamrzni/odmrzni, smrt; utiče i na prave agente; alarm 3 s (prvi put u sesiji) + crveni natpis; dnevnik „operater, iz laboratorije“. | 26 |
| P0.13 | Testovi P0 | jedinica umire bez dijela; θ samo iz mjerača; atraktori na sintetičkim serijama; 17 okidača; fisija/fuzija i poništavanje; predaja pri smrti; težine (200 / ±10 %); DL1 i porijeklo; laboratorija. | — |

## P1 · AI agenti postaju jedinice (stari kod se briše)

chat, glas SHARED_LIB-a, skeptik, ekstraktor, čitač, kurator, ideje, tabla. Za svakog: jedinica sa misijom i N_max (pravila 9 i 21), poziv modela samo kroz put jedinice, θ iz rada i riječi, PVP uz svaki potez, Doktor nad njim, testovi, uklonjen stari ulaz.

## P2 · Agenti bez modela postaju jedinice

čuvar mreže, SSH čuvar, čuvari pečata, adversarijalni mod, arXiv stražar, sastavljač (rad), i sam Doktor kao jedinica (§8: Doktor može biti bolestan). Postojeći `guardian/unit.py`, `guardian/diagnosis.py`, `guardian/healing.py` i `core/theta.py` se prelijevaju u P0 jezgro i brišu.

## P3 · Agent misije (33f)

Jedinica prvog kontakta napravljena od nule na P0: izbor radova + misija → čitanje → razgovor u oba smjera (skeptik napada) → „Sastavi zaključak“ → prijedlozi u „Čeka tvoju odluku“.

## Posle P3

33b (potpuno dvojezično) → 33d („Čeka tvoju odluku“ po grupama) → 33e (SHARED_LIB razgovara ljudski) → svi testovi + snimci → **jedan** deb 0.3.0~rc1 → push (kad se Andrej javi).

## Procjena

P0 ≈ 20–30 h · P1 ≈ 12–18 h · P2 ≈ 8–12 h · P3 ≈ 6–10 h · 33b/33d/33e ≈ 14–22 h · deb i provjera ≈ 3–5 h. Ukupno **≈ 63–97 h** rada.

## Druga runda (2026-10-27, dogovor pravila 27–41): plan do 0.3.0~rc1

Stanje: P0, P1, P2 gotovi (`e15e252`, `f27680b`, `fe1a079`, pushano). Andrej spava; radim bez pitanja, commitovi lokalno.

| # | Korak | Šta tačno | Gotovo kada | Procjena |
|---|---|---|---|---|
| R1 | P3 · agent misije (33f) | jedinica po misiji `mission-agent:<id>` (otvoren vijek, smrt pri zatvaranju misije); dugme „Razgovaraj o misiji“ u Misijama; izbor radova sa kvačicama; čitanje sažetaka, puni tekst samo arXiv na zahtjev; razgovor u oba smjera (≤ 3 pitanja po potezu), skeptik samo na tvrdnje; „Sastavi zaključak“ ⇒ stavke u redu po vrsti; razgovor u rezultatima (NAŠE-NERECENZIRANO) + „gdje si stao“; bez AI-ja jasna poruka | testovi sa lažnim modelom, snimak taba | 6–10 h |
| R2 | 33d · red po grupama | stablo vrsta → misija/tema (grane korpusa); kvačice; grupno samo povratno; Doktorove mjere i nepovratno jedna po jedna; potvrda „odobravaš N stavki“; klik = cijeli sažetak | testovi + snimak | 4–6 h |
| R3 | 33e · ljudski glas | odgovor glasom asistenta (ti), činjenice samo iz SELECT; „prikaži odakle“ (SQL + redovi sklopljeni); bez AI-ja šablonske ljudske rečenice; sve kroz jedinicu glasa | testovi | 4–7 h |
| R4 | 33b · jezik + prevod | (a) revizija interfejsa SR i EN (alat + snimci), popravke, test za nove natpise; (b) prevodilac kao PSE jedinica; meni u pregledniku i Editoru; keš + fajl `-masinski.md`; indeks/kapija ih preskaču; procjena za puni tekst; `papers-local` samo GGUF | test revizije prazan, testovi prevoda | 6–9 h |
| R5 | Traka menija | SHARED_LIB · Laboratorija · Podešavanje · Jezik · Pomoć → Vodič | snimak | 1 h |
| R6 | Dva deb-a | `pse-riemann-andrej` (misije + QRH) i `pse-riemann` (prazno), full, 0.3.0~rc1, konflikt jedan s drugim; selftest iz raspakovanog paketa | selftest prolazi za oba | 2–3 h |
| R7 | Vodiči | kompletan `VODIC-SR` / `GUIDE-EN` (isti sadržaj, + dodatak „Tvoje misije“ u ličnom), md + docx, snimci iz paketa; vodič za instalaciju i živi test (docx SR + EN) | docx pregledan kao PDF | 4–6 h |
| R8 | Deb-ovi ponovo | sa vodičem unutra; svi testovi; revizija PSE; WORKLOG, ZA-ANDREJA, plan docx | sve zeleno | 1–2 h |

Ukupno oko 28–44 h. Na kraju: spisak lokalnih commitova za odobrenje push-a i šta nisam mogao.

## Treća runda (2026-10-27, dogovor pravila 42–49): plan za 0.3.0~rc2

Stanje: rc1 izgrađen i pushan (`0cb32d4`); prvi živi test našao dva velika problema (glas: sirova greška SQL-a i odsječen odgovor; tab Misije ne vodi u konkretnu misiju). Rad počinje tek na „kreni“.

| # | Korak | Šta tačno | Gotovo kada | Procjena |
|---|---|---|---|---|
| R9 | Popravke modela (48 a, b, d) | Gemini 2.5 budžet razmišljanja po ulozi + limit izlaza; prepoznavanje odsječenog odgovora za sve provajdere (razlog prekida), jedan ponovni pokušaj, pa poruka „odgovor je odsječen“; čitač sa limitom po modelu, nepotpun JSON → „čitač odsječen“ u Laboratoriji | testovi sa lažnim provajderima (odsječen / cio odgovor) | 1,5–2 h |
| R10 | Glas (48 c, 47) | neispravan SQL → jedan ponovni pokušaj uz grešku, pa ljudska rečenica; pitanje koje traži sud → poruka + link „Razgovaraj o misiji: X“; imena misija kao linkovi `mission:` koji otvaraju radni prostor | testovi + snimak chata | 1–1,5 h |
| R11 | Radni prostor misije (42) | tab Misije: lista misija (kartice) lijevo; desno gore detalji + dugmad; desno dolje traka radova + razgovor; vučena granica; globalna dugmad gore | snimci SR/EN, uski ekran (Acer) bez prekoračenja | 3–4 h |
| R12 | Razgovor na klik (43, 44) | klik na misiju → agent čita stanje + pamćenje + radove i piše prvi; „novo“ za nove radove; „Zadaj da čita…“ (rad, puni tekst arXiv, kartica, izvještaj, bilješka) | testovi sa lažnim modelom | 1,5–2 h |
| R13 | Pamćenje misije (45, 46) | na kraju sesije agent predlaže stavke (odlučeno, utvrđeno sa izvorom, otvoreno, sljedeći korak); kvačice / brisanje / dopuna → „Sačuvaj pamćenje“; bez odluke „nepregledano“; sljedeća sesija čita pamćenje, ne stari razgovor; pored „Gdje si stao“ | testovi + snimak | 2–3 h |
| R14 | Izdanje rc2 (49) | svi testovi, PSE revizija, revizija jezika; paketi 0.3.0~rc2 (lični i javni), selftest iz oba; vodiči (SR/EN, md + docx, slike iz paketa) i vodič za živi test ažurirani; WORKLOG, ZA-ANDREJA; commitovi lokalno, push na odobrenje | sve zeleno | 2–3 h |

Ukupno oko 11–15,5 h.

**Stanje (2026-10-27, noć):** R9–R14 urađeni — `7bc0a4d` (R9), `c1ab293` (R10), `0b9960d` (R11–R13), zatim izdanje R14. pytest 369/369, selftest iz oba paketa 0.3.0~rc2: SVE PROLAZI. Čeka Andreja: push, živi test rc2, „spoji u main“ (`docs/ZA-ANDREJA.md`).

## Četvrta runda (2026-10-29, dogovor pravila 50–57): plan za 0.3.0~rc7

| # | Korak | Šta | Provjera | Stanje |
|---|---|---|---|---|
| R15 | Atraktori (50–53) | `pse/swing.py`: okreti (plato se spaja), ovojnica zamaha, `tendency()`, borderline traži ≥ 2 okreta i ≥ 10 poteza; `pse_registry`: niz za atraktore samo iz poteza sa AI čitačem, „?“ za poteze samo pravila, „teži ka“ u Doktorovom dnevniku; Laboratorija prikazuje osnovu i tendenciju | testovi (11), kopija pravog vaulta: voice#1 → zdrav | ✅ |
| R16 | Ponovni pregled (54) | `review_open_measures()` pri pokretanju, stavka `doctor-review`, odluka operatera | testovi; na kopiji vaulta stavka za voice#1 | ✅ |
| R17 | TLS pinovi (56) | obavještenje, `tls.rescan()`, meni + Guardian tab | testovi (4), snimak | ✅ (rc6) |
| R18 | Probni paket rc7 | lični paket, selftest iz paketa | SVE PROLAZI | ✅ |
