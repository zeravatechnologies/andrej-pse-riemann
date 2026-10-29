# PSE Riemann — upute za Claude Code

Ovaj fajl Claude Code čita na početku svakog chata u ovom folderu. Sve što Claude treba znati o projektu stoji **u ovom repou** (ovaj fajl, `docs/PLAN.md`, `docs/WORKLOG.md`, `docs/SLJEDECA-VERZIJA.md`), a ne u memoriji van repoa.

**Plan u Wordu:** `PSE Riemann — PLAN.docx` u korijenu repoa — Andrej plan kontroliše odatle. Izvor istine je `docs/PLAN.md`; posle SVAKE izmjene plana ili WORKLOG-a pokreni `node tools/plan-docx/make_plan_docx.js` i commituj docx zajedno sa izmjenom.

## Gdje se piše (strogo)
- Fajlovi se pišu **samo** u `~/Desktop/PSE Riemann` i na GitHub `andrejristic/pse-riemann`. Ništa drugdje.
- Privremeni fajlovi idu u `scratch/` u repou (gitignored), ne u `/tmp` ni u druge foldere.
- **Odvojenost od drugih projekata** (PSE MORANA, Svarog, Perun, PSE-Kali): smijemo **porediti i prepisivati**, ali ništa se ne dijeli niti se poziva preko granice projekta. **Jedini izuzetak: GGUF poziv** (model fajl i llama-cpp poziv). Kad se nešto prepiše iz drugog projekta, zapiši odakle je i šta jedan ima a drugi nema (vidi `docs/SLJEDECA-VERZIJA.md`).

## Kako radim sa Andrejem
- Jezik: srpski/bosanski, ijekavica.
- Pitanja postavljaj **u tekstu chata** (kratka numerisana lista + preporuka), ne u popup prozoru za izbor.
- Posle svakog završenog dijela: kratko **šta je urađeno** i **koliko je ostalo** (procjena).
- Kad iskrsne problem na dugom ili rizičnom poslu: **stani i javi**, ne guraj dalje.
- Uz svaki izbor koji nudiš: „✓ bolje kada… / ✗ slabije kada…“.
- Djelimični rezultati se prikazuju, jasno označeni kao djelimični.
- Hladne činjenice: ništa se ne tvrdi bez pokretanja. „N/N testova“ nije dovoljno; provjeri u **pokrenutoj aplikaciji** (snimci ekrana, selftest iz paketa). Zakazani rad je ranije pravio biblioteku + testove koji nisu bili povezani u aplikaciju.
- Rad počinje tek na izričito „kreni“; spajanje u `main` tek na „spoji u main“.

## Git
- Lokalni `master` prati `origin/main` (GitHub podrazumijevana grana je `main`). Push u main: `git push origin HEAD:main`, samo uz odobrenje.
- Rad na grani: runda 3 = `feature/runda3` (runda 2 je spojena u `main` @ `6f428b4`).
- Na ovom računaru nema globalnog git identiteta: `git -c user.name="Andrej Ristić" -c user.email=andrej.s.ristic@gmail.com commit …`
- Commit poruka završava sa `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Zabranjeno: force-push, `sudo`, sistemske instalacije, globalna podešavanja, brisanje van projekta.
- `vault/.state/` se ne commituje (TLS pinovi sadrže lokalnu IP/MAC adresu).

## Ključne odluke (detalji u `docs/PLAN.md`)
- **Operater = samo ime** (bez lozinke). Prava prijava (Perun P4 / Svarog S1) je odložena za sljedeću verziju.
- **SHARED_LIB je nadzornik**; PSE-L generator je samo njegov glas i govori samo registrovanom operateru.
- **AI:** jedan glavni AI za sve uloge + skeptik koji je uvijek **drugi** model. Podrazumijevano glavni = Claude, skeptik = DeepSeek-R1-0528-Qwen3-8B Q5_K_M (GGUF). Nikad Gemma.
- **GGUF** samo u `models/` u ovom repou, nikad na git. Limiteri obavezni (RAM, CPU, ctx, budžet razmišljanja, timeout, „→ ∞“).
- **Paketi:** B full (prvi), A lean, C dodatak za istraživanje. Završni proizvod runde 3: **.deb i .exe** (`.exe` kao GitHub Release, verzija `v0.2.0`). `.deb` se gradi jednom, na kraju, ne posle svake stavke.
- Dva graditelja: `build_deb.sh` (PyInstaller, CI) i `build_deb_pip.sh` (lokalni pip --target).
- Mašine: Dell i5-6600 (4 jezgra, 16 GB) i Acer i3 (2c/4t, 16 GB).

## Istraživanje
- `research/qrh-2026-10/` (REPORT.md, skripte, rezultati, slike). `papers-local/` je gitignored (licence), samo lokalno.
- Misija: postoji li kontinualna funkcija transformacije između QRH metoda (Liu → Xu–Sang: E_XS = E_Liu + T, provjereno) i vodi li njeno proširenje bliže ili dalje od ciljeva?
- XS optimum = korijen 133488B⁴−376596B³+384534B²−167541B+26231 (B = 0.8748866470399641); cjevovod validiran reprodukcijom Liuovog kubnog polinoma.
- Master arhitektura (van repoa, samo za čitanje): `~/Desktop/PSE_MASTER_ARCHITECTURE_v4 (2).pdf` (SHARED_LIB §3, PSE-L §5, Doktor §8, Guardian §10).

## Autonomni rad
- Brava: `tools/worklock.sh beat|check|release`. Alarm: `tools/alert.py`.
- Pravilo alarma: kvar koji ne blokira ostalo → upiši pod „Otvoreni problemi“ u WORKLOG i nastavi, bez alarma. Alarm + „**STATUS: ČEKA ANDREJA**“ + stop **samo** kad ništa ne može dalje bez korisnika.
- Zakazani zadatak `pse-riemann-autobuild`: **auto-nastavak je UGAŠEN** (Andrej, 2026-10-25). Zadatak je sada samo **sedmični podsjetnik** (ponedjeljak 10:00) koji pita da li Andrej želi ponovo aktivirati auto-nastavak; ne radi nikakav posao. Aktivira se samo na Andrejevu riječ u chatu. Pokreće se iz foldera PSE MORANA — Andrej: to je u redu, ne dirati. Kontroliše se samo iz Claude aplikacije.
- `app/.venv` je ranije bio pokvaren — ako ne radi, `app/setup.sh`.
