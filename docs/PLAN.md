# PSE Riemann — plan rada (v2, dogovoren 2026-10-25)

Ovaj dokument je ugovor za sljedeću fazu razvoja. Sve odluke ispod su dogovorene sa autorom (Andrej Ristić) u razgovoru 2026-10-25. Rad počinje tek na izričito "kreni". Napredak se vodi u [`WORKLOG.md`](WORKLOG.md).

Osnova: [PSE MASTER ARCHITECTURE v4](../../PSE_MASTER_ARCHITECTURE_v4%20(2).pdf) (lokalno na Desktopu, nije u repou). Istraživanje koje je pokrenulo ovaj plan: [`research/qrh-2026-10/REPORT.md`](../research/qrh-2026-10/REPORT.md).

---

## 0. Poenta

> **Tab Misije + novi QRH rad sa arXiva → prijedlog nove metode → operater potvrđuje.**
> Ako ovo dvoje ne radi, ništa nije urađeno.

**Test prihvatanja (definicija uspjeha):** ponavljanje stvarne istorije u aplikaciji:
1. Start: samo OpenAI 7/8 (i 11/12).
2. Uvoz Liu (arXiv 2610.12234) → prijedlog metode → test reprodukcije prolazi (**0.874957019420**, kubni polinom) → operater potvrđuje → T od 7/8, misija se ažurira ("bliže, zid ~0.870 / 5/6").
3. Uvoz Xu–Sang (arXiv 2610.15291) → **polinom 4. stepena, 0.874886647040**, T = E_XS − E_Liu, proširenja t i w, misija ažurirana.

## 1. Temeljne odluke

| Tema | Odluka |
|---|---|
| **SHARED_LIB** | SHARED_LIB **jeste** nadzornik (master §3): vidi sve procese, pamti sve, ništa ne izmišlja. Nema posebnog "nadzornika". |
| **Glas** | PSE-L generator (§5) je glas SHARED_LIB-a — jedino mjesto gdje nastaje prirodni jezik za čovjeka. Drugarski, ali hladan prema problemu. Govori **samo registrovanom operateru**. |
| **Hladne činjenice** | Svaka rečenica o biblioteci nosi `[kartica]` ili `[run]`; svaki broj se provjerava protiv izvora; kad podatka nema → UNKNOWN / "nema u biblioteci". |
| **Operater** | Pri pokretanju upiše **samo ime** (bez lozinke). Ime se veže za svaki run, upis i izvještaj. |
| **AI** | **Jedan glavni AI** radi sve uloge, + **skeptik koji je uvijek drugi model** i zadužen je isključivo da bude skeptik. Podrazumijevano: glavni = **Claude** (cloud), skeptik = **DeepSeek-R1-0528-Qwen3-8B** (lokalni GGUF). Operater može promijeniti oba; isti model ne smije biti oba. |
| **Skeptikov mandat** | Samo napada (tvrdnje, prijedloge metoda, izvještaje); nikad ne piše kao autor; nema pravo upisa; izlaz fiksnog oblika: prigovor · razlog · gdje · ozbiljnost; prigovori idu u "Čeka tvoju odluku". I skeptik je PSE jedinica (liječi se/zamjenjuje ako postane C ili N oblik). |
| **Bez interneta** | Aplikacija **pita** koji GGUF da koristi; ako ima 2+ GGUF-a → glavni + skeptik; ako 1 → glavni, skeptik "nedostupan" (samo determinističke provjere); ako 0 → AI miruje, lab/kapija/istraživač/čuvari rade. |
| **Determinističke provjere iznad svih modela** | test reprodukcije, porijeklo brojeva, kapija, nivoi izvora. Nijedan model ih ne može zaobići. |
| **GGUF lokacija** | DeepSeek se preuzima **samo unutar foldera PSE Riemann** (npr. `models/`), nikad na git (`*.gguf` je u `.gitignore`). Odobreno 2026-10-25. |
| **Paketi** | Tri varijante: **B full** (sympy + scipy) — **prva**; **A lean** (sympy, bez scipy; vlastite numeričke rutine); **C dodatak za istraživanje** (zaseban .deb, offline). Isto za .exe (preko CI). |
| **Repo** | Sve ide na oba mjesta (Desktop + GitHub `andrejristic/pse-riemann`, grana `main`). Rad na grani `feature/qrh-shared-lib`, spajanje u `main` na kraju uz odobrenje. |

## 2. Faze (redoslijed rada)

### F1 · SHARED_LIB sloj — master §3, §0.5.5
- vault + dnevnik + lab + Guardian zapisi formalno su SHARED_LIB; read-only pogledi (`cards`, `sources`, `lab_runs`, `journal`, `guardian_events`, `methods`, `missions`, `reports`)
- operater: ime pri pokretanju
- deklaracije: hash modela, dozvoljeni izvori, odredišta izvještaja

### F2 · Nivoi izvora u kapiji
- REFEREED / PREPRINT / LEAN / AI-UNREVIEWED / NAŠE-NERECENZIRANO
- preprint ne može biti oslonac za utvrđenu tvrdnju

### F8 · Istraživač metoda + "otvorena vrata" — master §0.5.4
- registar metoda: E(δ,x; ℓ,b,κ), parametri, zidovi, izvor, broj koji rad tvrdi
- računa V(ℓ), optimum, egzaktni polinom (sympy, rezultante — validirano na Liuovom kubnom), transformaciju T između metoda, proširenja (t, w), presudu **bliže / dalje / zid**
- **paket metode (`method pack`)**: jedan fajl = E + parametri + zidovi + izvor + tvrđeni broj + **test reprodukcije**; ulazi **samo kroz kapiju**; kapija odbija paket koji ne reprodukuje broj iz rada; prihvaćen ide u "Čeka tvoju odluku"
- dugme "Uvezi metodu"
- lab: `qrh_line`, `qrh_poly`, `qrh_transform`, `qrh_walls`, `qrh_licence`

### F9 · Misije i arXiv — srž projekta
- tab **Misije**: misija = {stanje, akcija, ishod} (PSE-L L3)
- prva misija: *postoji li kontinualna funkcija transformacije između QRH metoda i vodi li njeno proširenje bliže ili dalje od ciljeva (0.87, 5/6, 3/4, 1/2)?*
- arXiv praćenje ("quasi-Riemann hypothesis"): novi rad → **prijedlog** metode (izvlači glavni AI) → test reprodukcije → skeptik → operater potvrđuje (master §0.5.5: predloži, pa potvrdi)

### F3 · Glavni AI + skeptik + limiteri
- jedan aktivni glavni model; nezavisni skeptik (drugi model); postojeći router po ulogama se zamjenjuje
- GGUF u procesu (llama-cpp), ne učitava se dok se ne izabere; **sha256 provjera** pri prijemu i svakoj promjeni (master §8)
- **limiteri** (za bilo koji model):
  - RAM: ne učitava ako slobodno < model + 2 GB; odmah oslobađa ako slobodno < 1.5 GB
  - CPU: najviše 3 od 4 niti, niži prioritet procesa
  - kontekst n_ctx 8K, istorija se reže
  - budžet razmišljanja (`<think>`, npr. 1500 tokena) + ukupni limit izlaza
  - timeout po pozivu; jedan poziv u isto vrijeme (red)
  - detekcija ponavljanja (vrtnja ukrug → prekid)
  - cloud: budžet, ograničenje broja poziva, timeout
  - **PSE-L "→ ∞"** (§5): latencija, memorija, dužina reda; preko L ili raste 3 koraka zaredom → pauza, oslobađanje, javljanje operateru; L postavlja operater
- kartice "kad birati" (✓ bolje kada… / ✗ slabije kada…) za svaki izbor

### F4 · Glas SHARED_LIB-a — master §5, §2.5
- vidi sve procese; proza o cijelom sistemu ili dijelu
- prirodni jezik → validiran read-only SQL nad pogledima; operater uvijek vidi upit
- citati uz svaku rečenicu, provjera brojeva, UNKNOWN, lista zabranjenih termina
- samo operateru

### F5 · Čuvari finalnih izvještaja + liječenje od tri zla
**Čuvari:** čim se pojavi finalni izvještaj, SHARED_LIB šalje PSE jedinicu-čuvara čija je jedina misija da čuva te fajlove "kao zlato" (drugi čuvari mogu imati druge misije). Broj čuvara proporcionalan resursima, ne 1:1. Zaštita: zapečaćena kopija + sha256 u lancu dnevnika, fajl samo za čitanje, inotify + periodična provjera; napad → vraćanje iz pečata + zadržavanje + javljanje. Čuvar koji "zaspi" (šizoidni obrazac, §10.7) se zamjenjuje.

**Tri zla** (provjera pri izdavanju i kontinuirano nad svim agentima):

| Zlo | Znaci |
|---|---|
| čovjeku | broj bez izvora, preprint kao činjenica, tvrdnja o dokazu, curenje privatnog (IP, MAC, ključ) |
| agentu | primljena instrukcija iz podataka (injekcija); radnje izvan misije; odgovor bez provjere ("sir, yes sir", C); skok thete |
| fajlu | upis mimo kapije, hash ne odgovara a trag vodi do agenta, izmjena/brisanje zapečaćenog fajla |

**Agent sa ijednim zlom je zaražen i mora se liječiti** (master §4 S3, §8 Doktor, §10.6 dva stepena):
1. **Zadržavanje** (stepen 1, automatski, povratno): zamrznut upis i LLM pozivi; izlazi u "Čeka tvoju odluku"; sve od prvog lošeg traga → SUSPECT
2. **Dijagnoza** (Doktor): koje zlo, od kada ("nulti pacijent" iz dnevnika), praćenje kontakata po provenance tragu, atraktor N/B/C/S
3. **Liječenje**, od najblažeg: boundary reset → vraćanje fajlova iz pečata i označavanje upisa REFUTED/SUSPECT (ne briše se) → zaštitna fisija S3 (čista A nastavlja, zadržana B za forenziku pa umire; **traži odobrenje**) → zamjena (čuvari/Guardiani se ne popravljaju) → ako je uzrok model: oslobađanje i ponovni prijem (§8)
4. **Dekontaminacija**: nova čista jedinica ponovo provjerava sve što je zaraženi proizveo; potrošači zagađenih podataka ponovo rade; finalni izvještaji se ponovo pečate tek posle čiste provjere
5. **Oporavak**: OBSERVE-ONLY, znanje na težini 0.70 dok SHARED_LIB ne potvrdi; puna prava posle N čistih ciklusa
6. **Imunitet**: potpis infekcije u registar SHARED_LIB-a; izvještaj o slučaju operateru
7. **Smrt**: ponovna infekcija 3 puta zaredom ("→ ∞") → harvest-and-terminate (samo potvrđeno znanje)

Ko liječi liječnika: SHARED_LIB zamjenjuje bolesnog Doktora svježim (nasljeđuje registar obrazaca, ne bolesnu thetu). Sve iz stepena 2 (fisija, smrt, vraćanje operaterovih fajlova) odlučuje čovjek.

### F6 · GUI u stilu Svaroga (PySide6 + QSS)
- tamna tema `#12151d`, paneli, ćilibarni akcenat `#ffc257`, zaobljene kartice
- gornja traka: logo, tabovi kao pilule, statusne pilule (theta, budžet, Guardian, glavni AI, skeptik, limiteri), SR/EN
- tab **Pregled** sa metrikama; red **"Čeka tvoju odluku"** (Odobri / Ne odobri); chat koji se širi preko cijelog prozora; ulaz sa imenom operatera

### F7 · QRH sadržaj
- kartice izvora (OpenAI 7/8, 11/12, Siegel; Liu; Xu–Sang; Quanta), `tema-quasi-rh`, dan u planu, otvorena pitanja, barijere
- naši rezultati kao NAŠE-NERECENZIRANO: polinom 4. stepena, litica kod w ≈ 0.26, zid 5/6

### F10 · Završnica
- testovi, offline selftest, vodiči SR/EN
- **.deb full (B) prvi**
- → **izvlačenje** (paketi metoda za 11/12, 7/8, Liu, Xu–Sang; radi Claude Code, provjera u Pythonu)
- → **ubacivanje kroz vrata** (bez novog .deb-a)
- → **test prihvatanja** na pravoj aplikaciji
- → A lean, C dodatak, .exe varijante (CI)
- → spajanje u `main` uz odobrenje, oba repoa

## 3. Kako se pazi na računar i na rad (dugo, autonomno)

- rad na grani; svaka faza = commit + push; `main` netaknut do kraja
- kapija faze: novi testovi prolaze, stari testovi i selftest ne pucaju; 2–3 neuspjela pokušaja popravke → stop i javljanje
- zabranjeno: `sudo`, sistemske instalacije, globalna podešavanja, brisanje van radnog foldera, force-push
- prije teških koraka provjera RAM-a i diska; teški poslovi u pozadini, niži prioritet, vremensko ograničenje; gase se samo vlastiti procesi
- `docs/WORKLOG.md` posle svake faze: urađeno, testovi, sljedeće, procjena preostalog
- **auto-nastavak**: zakazani zadatak svaka 2 sata čita `CLAUDE.md` + PLAN + WORKLOG i nastavlja; **brava** (`.worklock` sa otkucajem) sprečava dva istovremena rada; zadatak se sam isključuje kad je plan gotov. Uslov: aplikacija Claude otvorena, računar budan.

## 4. Procjena
Oko **40–60 sati rada**, kalendarski realno **2–4 dana**. Mogu produžiti: kompajliranje `llama-cpp-python` (20–40 min po buildu), PyInstaller sa sympy/scipy, .exe preko CI, preuzimanje DeepSeek-a (~6 GB).

## 5. Ograde
- Sve oko QRH je nerecenzirano (radovi i naši računi).
- Automatsko izvlačenje sistema eksponenata iz rada od 200 strana je teško; zato test reprodukcije odlučuje, ne model.
- `app/.venv` je pokvaren od ranije — prvi korak je `./setup.sh`.

---

## 6. Runda 3 (dogovorena 2026-10-25; „kreni“ dato 2026-10-25)

Završni proizvod: **.deb i .exe** (verzija **0.3.0**, tag `v0.3.0`, `.exe` kao GitHub Release; Andrej 2026-10-27: izdanje se zove v0.3.0, kandidati 0.3.0~rcN). Oznake: S = od Svaroga, P = od Peruna, A = greška nađena poređenjem. Brojevi S/P odgovaraju redovima B/C u [`SLJEDECA-VERZIJA.md`](SLJEDECA-VERZIJA.md) (S2 = B2, P1 = C1 …).

**P4 (prava prijava) je izbačen** (Andrej, 2026-10-25: „zaboravi p4“). Operater ostaje **samo ime**; nema lozinki, šefa ni ranga.

### Faza 0 · Početak
1. Spajanje trenutnog stanja u `main` (lokalno i GitHub); novi rad na novoj grani, spajanje na kraju uz odobrenje.
2. Zakazani zadatak: auto-nastavak je **ugašen** (2026-10-25); zadatak je sada sedmični podsjetnik koji pita da li ga ponovo aktivirati. Pokreće se iz foldera PSE MORANA; Andrej je rekao da je to u redu i da se više ne dira. Kontroliše se samo iz Claude aplikacije.

### Faza 1 · Temelj: popravke i integritet odluka
3. Popravke A1–A4: „→ ∞“ čuvar se zaista pokreće; detekcija vrtnje prekida generisanje u toku; timeout pokriva i generisanje; nema trke u redu odluka.
4. Odobrenje se troši jednom (S2) i atomično rješavanje stavki (P5, **bez ranga**): jedna odluka = jedno izvršenje.
5. Svaki alat i akcija deklariše povratnost; nedeklarisano = nepovratno (S4). Od toga zavisi šta čuvari i liječenje smiju sami, a šta ide čovjeku.
6. Ponovljive odluke (P1): svaka odluka se može ponovo izvesti iz dnevnika; neslaganje = narušen integritet. Zapis koji je jednom ponovljen istovjetno se preskače dok se ne promijeni ni on ni kod koji odlučuje (keš po hash-u zapisa + hash koda), jer ponavljanje vrata košta ~10 s po zapisu.
7. Ograničena retencija + sidra arhive (S8 + P3): dnevnik se skraćuje bez gubitka dokaza; arhiva dobija sha256 i pečat; lanac se nastavlja preko sidra.

### Faza 2 · Operater i početno podešavanje
8. Početno podešavanje pri prvom otvaranju, prije glavnog prozora:
   1. ime operatera (samo ime);
   2. glavni AI: OpenAI ili kompatibilni (proizvoljna adresa), Claude, Gemini ili GGUF sa bilo kog mjesta (po putanji i hash-u, bez kopiranja);
   3. skeptik: drugi model;
   4. deklaracije za svaki izabrani model (GGUF hash poređen sa objavljenim; nova cloud adresa kao prijedlog koji operater potvrđuje);
   5. „bez AI za sada“, uz jasan spisak šta radi, a šta ne;
   6. da li čuvar kreće sam pri prijavi u sistem.
   Sve se kasnije može mijenjati.

### Faza 3 · Modeli, strujanje, naplata, prekidač
9. Provajderi: OpenAI i kompatibilni (gotove postavke za Mistral, Groq, DeepSeek, xAI, OpenRouter, Together, Fireworks), Claude, Gemini i GGUF, za obje uloge.
10. Strujanje za sve pozive kroz Guardian egress, sa pravim prekidom veze.
11. Savjetovanje o naplati: po provajderu opcije + šta je najbolje (prekid strujanja zaustavlja naplatu kod Anthropic, OpenAI, DeepSeek, xAI, Together, Fireworks; **ne** kod Gemini, Mistral, Groq; bez strujanja uvijek puna naplata; ulazni tokeni se uvijek naplaćuju); stroži `max_tokens` i limit ulaza za provajdere bez prekida; budžet računa najgori slučaj kad nema podatka o potrošnji.
12. Prekidač za online AI: dugme u gornjoj traci, u meniju ikone u traci i Ctrl+K; zatvara put u egress-u, prekida pozive u toku, briše ključeve iz memorije (po izboru ih trajno zaboravlja); prelazi na GGUF ili „bez AI“; preživljava restart, uključuje ga samo operater; automatski se okida na „→ ∞“ broja, veličine i troška poziva, uz alarm i link za opoziv ključa.
13. Lokalni model ne smije se obraćati nijednoj adresi osim ovog računara (P8).

### Faza 4 · SSH čuvar i zaštita domaćina
14. SSH čuvar (PSE jedinica, radi uvijek): čita SSH dnevnik bez root-a, otporno na rotaciju (S6); računa po izvoru, uz „→ ∞“; theta blizu 30, ali ne ravna; skupi, prijavi SHARED_LIB-u i ukloni smetnju; kad su tri principa narušena, blokira prekršioca.
15. Povratno zadržavanje sa automatskim poništavanjem (S3): prekid sesije i privremena IP blokada 24 h (sama se skida, preživljava restart) su automatski. Gašenje SSH-a i trajne blokade su prijedlog operateru sa tačnom komandom.
16. Bez sudoers pravila → opasno upozorenje: veliki prozor, crvena pilula, SHARED_LIB i uporno bip-bip-bip dok operater ne klikne „U redu“, uz tačnu komandu.
17. Šablonske poruke za kritične stvari (P6): alarmi, liječenje i upozorenja koriste samo provjerene šablone, ne tekst modela.
18. Uputstvo za usko sudoers pravilo (ufw deny/delete od IP, systemctl stop/start ssh), korak po korak.
19. Pozadinski rad i gašenje: čuvar je proces sa ikonom u traci (Otvori · Stanje θ · Prekini online AI · Ugasi čuvara); pri zatvaranju pitanje „Ugasi sve“ ili „Zatvori prozor, čuvar ostaje“; korisnički servis po izboru, sa systemd hardeningom (S9).

### Faza 5 · Pametniji Doktor (ranije „Fizičar“) i mjerenje
20. Statistički jača dijagnoza (S5) u liječenju i čuvarima: CUSUM, posterior i pravilo 3-od-3, manje lažnih „infekcija“.
21. Budžeti otkrivanja + takmičenje hipoteza (P7).
22. Mjereni benchmark (S7): označeni primjeri za tri zla, SSH napade i prekidač; lažno pozitivni i lažno negativni ulaze u izvještaj.

### Faza 6 · Interfejs i mašina
23. SR/EN prekidač za cijeli interfejs.
24. Automatski profil mašine (Dell i5-6600 / Acer i3, oba 16 GB): ograničenja se sama prilagode, kartice „kad birati“ upozore da je DeepSeek spor na Aceru, testovi rade i sa simuliranim Acerom.

### Faza 6b · Druga misija, inspiracije, grafovi (dodato 2026-10-25; radi se prije Faze 7 — izdanje je uvijek posljednje)
Sve iz ove faze mora biti u završnom .deb i .exe.

25. **Istraživanje sa izvorima (internet):** geometrijski Langlands (dokaz 2024); aritmetička funkcionalnost (npr. automorfnost simetričnih stepena); zero-free i zero-density rezultati za L-funkcije višeg stepena (GL(2), Artin); šta u dokazima 7/8, Liu i Xu–Sang zavisi od Dirichletovih karaktera, a šta ne. Rezultat: `research/langlands-2026-10/REPORT.md` + kartice izvora sa nivoima (REFEREED / PREPRINT), označeno DJELIMIČNO gdje treba. Kartice idu u seed vaulta, pa ih paketi nose.
26. **Dogovor o cilju druge misije** (Andrej odlučuje, prije ubacivanja u softver). Pitam čim 25 završi; ništa od 27 ne počinje prije odgovora. Prijedlozi su u chatu 2026-10-25. **Odluka (Andrej, 2026-10-25):** cilj 1 (mapa prenosivosti) je obavezan i podrazumijevan; ciljevi 2 (E_d i T_d uslovno) i 3 (samo praćenje) su opcije. Promjenu cilja aplikacija NIKAD ne radi sama: predloži je u „Čeka tvoju odluku“ sa obrazloženjem; izbor 1 / 2 / 3 je uvijek dostupan u meniju misije (tab Misije → „Cilj misije“), svaka promjena zapisana sa imenom operatera.
27. **Misija 2 u aplikaciji:** „Prenosi li se metoda 7/8, Liu ili Xu–Sang na L-funkcije višeg stepena? Ako da, kako se E mijenja sa stepenom d i postoji li T_d između porodica?“ Registar metoda dobija polje *porodica / stepen d*; T_d je podatak, ne kod; misija 2 je otvoreno pitanje dok ga račun ne zatvori. Dodatna polja (Andrej, 2026-10-25, iz skeletona „tri pravca“):
    - **vrsta rezultata**: poluravan bez nula (npr. 7/8) · gustina nula · udio nula na kritičnoj pravoj (npr. 2/3) — aplikacija nikad ne poredi niti crta zajedno ono što se ne može porediti;
    - **pretpostavke** (npr. „funkcionalnost do GL(3)“, „pod RH“): kapija odbija bezuslovnu tvrdnju koja se oslanja na nedokazanu pretpostavku, kao što sada traži „pod RH“.
28a. **Rad po misijama u krug** (Andrej, 2026-10-25; radi se prije 28, jer „Ideje“ treba da znaju aktivnu misiju): u svakom trenutku je **jedna aktivna misija**, vidljiva u gornjoj traci; operater je mijenja slobodno (meni) ili dugmetom **„Sljedeća misija“** (krug 1 → 2 → 3 → 1). **„Ostavi za kasnije“**: misija prelazi u stanje *na čekanju* sa bilješkom „gdje sam stao“ (rečenica operatera + automatski: front B, zadnji korak, otvorene stavke u redu, ideje; kasnije i prikaz u Grafovima). Pri povratku prvo kartica **„Gdje si stao“** (bilješka + šta se desilo u međuvremenu). Misija na čekanju: **podrazumijevano potpuno zamrznuta**; operater je uvijek može prebaciti na „tiho skuplja“ (arXiv, ideje, bez značke; pri nastavku „dok te nije bilo: …“) i nazad. Aktivna misija određuje kontekst chata, rangiranje i značku „Ideja“, podrazumijevani prikaz u Grafovima i cilj adversarijalnog moda. Aplikacija nikad sama ne mijenja misiju (najviše predloži); svaka promjena u dnevniku sa imenom operatera. Misija 3 ulazi u krug kad nastane (stavka 32).
28. **Engine za inspiracije („Ideje“):** posle čitanja onoga što se dešava na internetu (arXiv i izvori sa allowliste, kroz Guardian egress), predlaže **ideje**, ne tvrdnje. Svaka ideja: oznaka INSPIRACIJA, izvor (kartica), za koju misiju i zašto, šta bi trebalo da postane provjerljiva metoda. Nikad ne ulazi u vault kao činjenica. Operater bira: zadrži · odbaci · pretvori u otvoreno pitanje. **Da ne preplavi:** najviše 3 ideje sedmično (operater mijenja), rangirane po vezi sa misijom, bez duplikata, mala značka umjesto iskačućih prozora, sedmični pregled, „odgodi“. Skeptik napada svaku ideju prije nego što je operater vidi.
29. **Interaktivni grafovi** (matplotlib je već dio paketa, radi offline): tab **Grafovi** sa zumom, pomjeranjem i očitavanjem vrijednosti pod mišem; klizači za parametre (ℓ, b, κ, t, w, d) koji odmah crtaju funkcije eksponenata, presjeke, zidove i ciljeve (7/8, 0.87, 5/6, 3/4, 1/2); poređenje metoda jednu preko druge; klik na tačku otvara karticu/izvor; izvoz PNG/SVG + podaci CSV; svaki graf označen nivoom (RAD / NAŠE-NERECENZIRANO). Lab grafovi (sada statični PNG) prelaze na isti interaktivni prikaz.
    **Uzor: Android aplikacija „Calculus Tools“** (Andy McSherry, `com.andymc.derivative`; skinuta sa Google Playa 2018). Po izvorima je imala izvode, određene integrale, dužinu luka, Taylorove redove i grafove (kartezijanski, polarni, parametarski, vektorska polja). Interakciju je potvrdio Andrej (ispod). Prevod za naš tab:
    - kartezijanski: funkcije eksponenata E(δ), prava B(ℓ) = 11/12 − ℓ/4, presjeci;
    - parametarski: putanje (ℓ(t), B(t)) za proširenja t i w;
    - vektorsko polje nad ravni parametara (npr. ℓ, κ): strelice pokazuju kuda proširenje gura B (bliže ili dalje od cilja), što je srž prve misije;
    - izvod u tački + tangenta: osjetljivost dB/dℓ, dB/dκ;
    - osjenčana površina između funkcija: vizuelna „rezerva“ (npr. −E* = 7/30672 kod 7/8);
    - Taylorov polinom oko optimuma;
    - traženje nula i presjeka (tačni korijeni, npr. Liuov kubni polinom);
    - praćenje kursorom, zum točkićem, pomjeranje prevlačenjem, tabela vrijednosti;
    - polarni graf kao jeftin dodatak.
    **Potvrđeno (Andrej, 2026-10-25), kako je aplikacija radila:** zum; režim miša u kojem kursor na tački grafa pokazuje sve što se zna o značenju te tačke; neograničen broj funkcija na jednom grafu, svaka svojom bojom; tamna pozadina. Tri odvojena dijela: **Grafovi** (samo crtanje), **Funkcije** (upis funkcija), **Kalkulacije** (računi nad upisanom funkcijom). Na telefonu su to tri taba; **za ekran računara prilagoditi**, npr. tri panela jedan pored drugog sa mogućnošću da se graf raširi preko cijelog prozora. Kod nas „sve o tački“ znači: koordinate, koja funkcija/metoda, parametri, da li je presjek/zid/cilj, udaljenost do ciljeva, nivo izvora (RAD / NAŠE-NERECENZIRANO) i link na karticu.
    **Računi na zahtjev u tački** (Andrej, 2026-10-25): jeftino se prikazuje odmah; skuplje se nudi pitanjem „Želiš li da izračunam…?“, uz procjenu trajanja, najviše 3–4 ponude prilagođene vrsti tačke (ostalo pod „više…“):
    - bilo gdje na krivoj: izvod i tangenta, drugi izvod (konkavnost), Taylorov polinom;
    - u ravni parametara: gradijent (smjer najbržeg rasta/pada B);
    - optimum: Hesijan (da li je optimum i koliko je oštar);
    - presjek: tačan algebarski korijen (sympy) + strogi interval-certifikat;
    - blizu cilja/zida: koliki i koji pomak parametara dostiže cilj, ili dokaz da zid to sprečava;
    - između dvije funkcije: osjenčana površina („rezerva“);
    - za misiju: kuda proširenje (t, w, kasnije d) pomjera tačku — bliže ili dalje od cilja.
    Pravila: računa Python deterministički (AI samo objašnjava, i to na zahtjev); red u pozadini sa „prekini“, poštuje limitere (RAM, CPU, „→ ∞“) i profil mašine; rezultat se kešira i bilježi kao lab run u SHARED_LIB-u sa oznakom NAŠE-NERECENZIRANO.
    **Kompleksni brojevi i više dimenzija (Andrej, 2026-10-25):**
    - funkcije kompleksne promjenljive (f(s) = ζ(s), L(s, χ), bilo šta u s); fazni portret (boja = argument, svjetlina = modul); krive Re f = 0 i Im f = 0 (nule su njihovi presjeci); presjeci duž prave (|ζ(1/2+it)|, Hardyjeva Z(t), Re/Im); oblasti u ravni (poluravan Re s > B, kritična traka, prava 1/2, nule kao tačke); „sve o tački“ za kompleksnu tačku (s, f(s), |f|, arg f, udaljenost do najbliže nule i do prave 1/2, u oblasti bez nula ili ne); računi na zahtjev: kompleksni izvod, nule u pravougaoniku (princip argumenta), rezidui;
    - **povezani prikazi:** ravan eksponenata (σ, eksponent) i kompleksna ravan — isti broj σ\* je tačka presjeka u prvoj i granica poluravni u drugoj; pomjeranje parametra mijenja oba;
    - **klizač „niska strana + Δ“:** σ\* = 11/16 + niska strana — koliko gubitka metoda podnosi prije nego što oblast bez nula nestane (σ\* → 1); mjerilo za mapu prenosivosti;
    - **3D:** površi koje se rotiraju (|ζ(s)| iznad kompleksne ravni — nule su jame; eksponenti iznad (σ, ℓ) — dvije površi se sijeku po krivoj presjeka = B(ℓ)); **4. dimenzija kao boja** (npr. |f| obojen po arg f); **5. i dalje kao klizači ili animacija**; **male slike** (ista površ za više vrijednosti parametra); **paralelne koordinate** za sve parametre metoda odjednom. Pravilo: najviše 3 dimenzije na ekranu, ostale uvijek vidljive kao klizači; profil mašine smanjuje mrežu na Aceru.
    **Kretanje po grafu i vodič (Andrej, 2026-10-26):** pomjeranje gore/dolje/lijevo/desno prevlačenjem mišem, strelicama na tastaturi (Shift = veći korak) i dugmićima ◀ ▲ ▼ ▶ na ekranu; zum točkićem, „+ / −“ i „⌂“ (vrati pogled). Uz tab ide **detaljan vodič** `docs/VODIC-GRAFOVI-SR.md` i `-EN.md` (otvara se iz taba dugmetom „?“ i iz Pomoći): tri panela, upis funkcija sa primjerima, klizači, kretanje, „sve o tački“, računi na zahtjev i šta znači procjena trajanja, nivoi (RAD / NAŠE-NERECENZIRANO / KORISNIK), kompleksni i 3D prikazi, izvoz; ulazi u paket.
29b. **Snimak ekrana u bilo kom trenutku** (Andrej, 2026-10-26): dugme 📷 u gornjoj traci i prečica **F12** (cijeli prozor) / **Shift+F12** (samo aktivni tab ili panel); PNG sa datumom i vremenom u imenu ide u `~/Pictures/PSE-Riemann/` (folder mijenja operater u Podešavanju); poruka u statusnoj traci sa putanjom i „Otvori folder“, bez iskačućih prozora; zapis u dnevniku (ime fajla, ne sadržaj). Radi u svakom tabu i dijalogu glavnog prozora. Ide u vodič.
30. **Graf znanja vizuelno:** tab Graf (sada stablo) dobija i prikaz čvorova i veza (teme, kartice, metode, misije), klik otvara karticu.
31. **Adversarijalni mod** (iz skeletona „tri pravca“, Andrej, 2026-10-25): deterministička potraga po prostoru parametara (ℓ, b, κ, t, w…) jedne metode traži (a) tačku koja daje **bolje B** od tvrđenog (tvrdnja nije optimum) i (b) tačku u kojoj se **krši zid ili uslov**. Računska dopuna skeptiku (skeptik napada riječima, ovo brojevima). Uz to **certifikat praznine** (pravac A): za datu metodu strogi interval da iznad B* nema dopustivih parametara. Rezultati: „Čeka tvoju odluku“, tab Grafovi (tačka kontraprimjera), lab run NAŠE-NERECENZIRANO; poštuje limitere. Ne ulazi: apstraktna „mašina“ bez implementacije, „Langlands transfer“ kao konstanta (samo kao otvoreno pitanje / INSPIRACIJA, stavka 28), Lean.

### Faza 6c · Misija 3 i radni tekst (dodato 2026-10-25, prije izdanja)
32. **Misija 3 — kompleksna verzija:** dokaz 7/8 gleda samo σ = Re ρ, jer |X^s| = X^σ; imaginarni dio γ nosi fazu, a poništavanje u dokazu dolazi iz oscilacija. Pitanja: (a) zavisi li granica od visine γ — da li vertikalna prava Re s = B postaje kriva σ\*(γ) i savija li se igdje prema 1/2; (b) šta su funkcije eksponenata kad im se dozvoli kompleksni argument E(s; ℓ, b, κ) i gdje se signal i niska strana „sijeku“ u kompleksnom smislu. Otvoreno pitanje; svaki korak NAŠE-NERECENZIRANO; isti meni ciljeva i isto pravilo (aplikacija predlaže, operater bira).
33. **Radni tekst rada iz misija 2 i 3:** aplikacija sastavlja radni tekst (uvod, metode, računi sa lab run-ovima, grafovi, izvori sa nivoima, otvorena pitanja), označen NAŠE-NERECENZIRANO; kapija i dalje odbija svaku tvrdnju o dokazu; svaki broj nosi izvor ili lab run; skeptik i adversarijalni mod napadaju tekst prije nego što ga operater vidi. Rezultat „kompleksna verzija ne daje ništa novo“ je takođe rezultat i piše se.

33a. **Nalazi živog testa 0.2.0~rc1** (Andrej, 2026-10-27), popravlja se redom: (1) Gemini u karantinu pri svakom startu — provjera dostupnosti radila `GET /` na API hostu, Google vraća HTML 404, čuvar to čitao kao captive portal → **popravljeno**; (2) karantin nije bilo moguće naći/osloboditi kroz meni → sada stavka u „Čeka tvoju odluku“ (Odobri = oslobodi) i poruka kaže gdje; (3) rezultati instalirane verzije u skrivenom `~/.local/share/pse-riemann/` — Andrej bira vidljivo mjesto; (4) Groq proba vratila 404 (put/model) — provjeriti.
33b. **Potpuno dvojezično** (Andrej): sve, uključujući planove i sadržaj, mora postojati na SR i EN. (a) sav tekst koji kod sastavlja kroz prevod sa fiksnim EN verzijama; (b) zasijani sadržaj (teme, izvori, misije, koraci, ideje, PLAN, otvorena pitanja) dobija napisanu EN verziju; (c) sve ostalo (planovi, kartice, misije, ideje, odgovori, izvještaji) glavni AI prevodi automatski pri prebacivanju jezika — u pozadini, keširano, označeno „mašinski prevod“, original se nikad ne mijenja. Prije izdanja.

33c. **„⚙ Podešavanje“ u meniju tabova** (Andrej, 2026-10-27): posljednji tab otvara podešavanje (provajder AI-ja, ključevi, modeli, skeptik) — isto kao prvo pokretanje.
33d. **„Čeka tvoju odluku“ po grupama, sa izborom** (Andrej): stablo po vrsti, a radovi po temama koje mašina sama izvuče iz naslova i sažetaka (deterministički); kvačica na stavci i grupi; „Odobri označene“ / „Ne odobri označene“ — jedna, više ili sve; klik prikaže cijeli sažetak.
33e. **SHARED_LIB razgovara ljudski** (Andrej): činjenice i dalje samo iz baze (SELECT, nijedan izmišljen broj), ali glasom asistenta na poslu; SQL i redovi sklopljeni ispod („prikaži odakle“); bez AI-ja šablonske ljudske rečenice.
33f. **Razgovor o misiji — srce misije** (Andrej): izbor jednog, više ili svih radova + misija → agent misije čita (sažetak, na traženje puni tekst) uz stanje misije → razgovor u oba smjera (agent ispituje operatera, operater agenta; skeptik napada tvrdnje u toku) → „Sastavi zaključak“: prijedlozi (koraci misije, otvorena pitanja, ideje, cilj, metoda za vrata) idu u „Čeka tvoju odluku“, ništa se ne upisuje samo; razgovor sačuvan u rezultatima (NAŠE-NERECENZIRANO) i u „gdje si stao“.
    **Redoslijed:** 33c → 33b (prvo sloj za prevođenje, da 33d–33f nastanu dvojezično) → 33d → 33e → 33f → rc3.

### Faza 6d · SVI AGENTI SU PSE JEDINICE (Andrej, 2026-10-27 — prije svega ostalog)
Ugovor za izvedbu: [`DOGOVOR-PSE-AGENTI.md`](DOGOVOR-PSE-AGENTI.md) / [`AGREEMENT-PSE-AGENTS.md`](AGREEMENT-PSE-AGENTS.md) (+ docx), pravila 1–26, **sve odlučeno** 2026-10-27. Detaljan plan: [`PLAN-PSE-AGENTI.md`](PLAN-PSE-AGENTI.md) / [`PLAN-PSE-AGENTS.md`](PLAN-PSE-AGENTS.md) (+ docx). Stanje 2026-10-27: 15 agenata, **0 PSE sazdano**, 3 djelimično. P0 jezgro u SHARED_LIB-u → P1 AI agenti → P2 agenti bez modela → P3 agent misije (33f) → 33b → 33d → 33e → 0.3.0~rc1. **Samo PSE native:** stari kod agenata se briše, bez prekidača. **Bez međuizdanja**; commitovi lokalno, push na kraju (Andrej). „Fizičar“ se svuda zove **Doktor**. Šta čeka Andreja: [`ZA-ANDREJA.md`](ZA-ANDREJA.md). **Stanje 2026-10-27 (jutro): R1–R8 GOTOVI** — paketi 0.3.0~rc1 (lični i javni) izgrađeni. Prvi živi test → treća runda dogovora (pravila 42–49) i plan R9–R14 za 0.3.0~rc2 u `PLAN-PSE-AGENTI.md`; čeka „kreni“. Ranije: P0–P2 gotovi; druga runda dogovora (pravila 27–41) i plan R1–R8 u `PLAN-PSE-AGENTI.md`: P3 → 33d → 33e → 33b → traka menija → dva full deb-a (`pse-riemann-andrej`, `pse-riemann`) → vodiči → deb-ovi ponovo.

### Faza 7 · Dokumentacija i izdanje
34. Uputstvo za instalaciju .deb, vodiči SR/EN ažurirani.
    **Redoslijed (Andrej, 2026-10-26):** kompletni SR/EN vodiči za **cijelu aplikaciju** pišu se tek **kad se naprave .deb i .exe**, da opisuju tačno ono što je u paketima (snimci iz instaliranog paketa); posle toga paketi se još jednom grade sa vodičima unutra. Vodiči za pojedine dijelove (npr. `docs/VODIC-GRAFOVI-*`) nastaju usput i ulaze u kompletne.
35. Detaljan vodič za živi test sa pravim AI-jem (git i računar). Test radi Andrej.
36. CI koji instalira .deb na čistom sistemu i radi pravi poziv (P9).
37. Verzija **0.3.0** (Andrej, 2026-10-27; bilo 0.2.0), tag `v0.3.0`, .exe samo kao GitHub Release. Kandidati: 0.3.0~rc1, rc2 … (instaliraju se preko 0.2.0~rc2).
38. Tri .deb paketa ponovo izgrađena i provjerena, .exe, testovi, snimci ekrana, oba repoa, spajanje u `main` uz odobrenje, odluka o sedmičnom podsjetniku (ostaje ili se briše).

**Ne ulazi sada** (u `SLJEDECA-VERZIJA.md`, odjeljak E): P4 i S1 (prijava), S10 (mTLS federacija), P2 (vanjski merač sa potpisom).

**Procjena:** oko 62–92 sata rada (bez P4) + oko 36–55 sati za Fazu 6b (sa stavkom 31 i poljima uz 27) + oko 14–24 h za Fazu 6c i kompleksne/3D grafove = **oko 112–171 sat**, kalendarski oko 8–12 dana (bez auto-nastavka sporije: rad ide samo dok je chat otvoren). Napredak faza po fazu u WORKLOG.
