# Za Andreja: šta čeka tebe

## 0. Stanje 2026-10-29: 0.3.0 izašao, objava čeka tvoje „može“

Sve lokalno je gotovo. Na tvoje „može“ ide, ovim redom:
1. `.exe` (`PSERiemann-Setup-0.3.0.exe`, sha256 `2bb91668…ea96`) + novi `SHA256SUMS.txt` + novi opis u izdanja **v0.3.0** na oba repoa (andrejristic, zeravatechnologies);
2. sajt: push zadnjeg commita na granu `claude/pse-riemann-0-3` (PR #56), CI sajta, spajanje → objava;
3. push lokalnih commitova PSE Riemann (WORKLOG, ZA-ANDREJA, .gitignore) na oba repoa;
4. „spoji u main“ (PSE Riemann) — samo kad kažeš.

Stanje 2026-10-27, noć. Treća runda (R9–R14, izdanje **0.3.0~rc2**) je **urađena**. Ovdje je sve što ne mogu bez tebe, redom kojim predlažem da ide.

## 1. Push grane `feature/runda3` (na tvoje „pushuj“)

Na GitHubu je zadnji `5c2288a` (dogovor treće runde i plan R9–R14). Lokalno čekaju:

| commit | šta |
|---|---|
| `7bc0a4d` | R9 — pravilo 48 a, b, d: budžet razmišljanja iznad limita odgovora, ponovni pokušaj odsječenog odgovora, „čitač odsječen“ |
| `c1ab293` | R10 — pravila 47 i 48 c: misije kao linkovi, pitanje koje traži sud ide agentu misije, SQL: jedan ponovni pokušaj pa rečenica |
| `0b9960d` | R11–R13 — radni prostor misije, razgovor na klik, „Zadaj da čita…“, pamćenje misije |
| `8004e60` | R14 — izdanje 0.3.0~rc2: vodiči, slike iz paketa, docx, WORKLOG, ovaj fajl |

Push je bez force-a. Paketi (`*.deb`) nikad ne idu u git.

## 2. Instalacija rc2 i živi test (tvoj posao)

Vodič je **`PSE Riemann — VODIC 0.3.0 INSTALACIJA I ZIVI TEST.docx`** u `~/Desktop/PSE Riemann` (EN: `… GUIDE 0.3.0 INSTALL AND LIVE TEST.docx`). U njemu je 16 koraka, sa naglaskom na četiri stvari koje su pukle u rc1. Instalacija traži `sudo`, a to ne mogu ja.

Paketi u `~/Desktop/PSE Riemann/`:
- `pse-riemann-andrej_0.3.0~rc2_amd64.deb` (tvoj);
- `pse-riemann_0.3.0~rc2_amd64.deb` (javni).

Selftest iz oba raspakovana paketa daje **SVE PROLAZI**. Paketi rc1 su još tu; obriši ih kad ti više ne trebaju.

Posle živog testa slijedi **„spoji u main“**, i to samo kad kažeš.

## 2a. Moja tumačenja treće runde (provjeri, ništa ne blokira)

1. **Budžet razmišljanja po ulozi** ide preko „effort“ uloge: low = 512, medium = 1024, high = 4096 tokena, uvijek **iznad** limita odgovora.
   - Čitač i senzori: low, pa je čitač 200 + 512.
   - Glas i chat: medium, pa je SQL 600 + 1024, a odgovor 900 + 1024.
   - Matematika: high.
   - Važi za modele koji razmišljaju (Gemini 2.5/3, DeepSeek R1, o-serija, Claude 5, `openrouter/auto` …); kod ostalih se ništa ne mijenja.
2. **Ponovni pokušaj** (48 b) ide sa **dvostrukim** limitom odgovora. Ako i on bude odsječen, na kraj odgovora ide „[odgovor odsječen: ni dvostruki limit nije bio dovoljan …]“. Važi za sve provajdere (MAX_TOKENS / max_tokens / length).
3. **Pitanje koje traži sud** prepoznajem po izrazima („sljedeći korak“, „šta da radim“, „preporuči“, „najlakši“, „trebam li“, „what should“ …). Glas tada ne pravi SQL. Ako pitanje imenuje misiju, link vodi na nju; inače na sve otvorene misije, aktivna prva.
4. **Pamćenje** se čuva odmah kao „nepregledano“, čim ga agent predloži. Tvoj pregled ga zamjenjuje. Stavke „utvrđeno“ bez izvora dobijaju izvor „razgovor <id>“, a tvrdnje o dokazu se odbacuju.
5. **Zatvaranje aplikacije** čeka prijedlog pamćenja najviše 30 s. Ako model ne stigne, razgovor ostaje sačuvan u rezultatima, ali bez pamćenja.
6. **Prelazak na drugu misiju** (klik na drugu karticu) završava sesiju prethodne i pokreće prijedlog njenog pamćenja u pozadini.
7. **Cilj i „dok čeka“** su u jednom meniju „Cilj i pozadina ▾“, da gornji dio stane na Acer (1366 piksela).
8. **„Sljedeća misija ⟳“ i „Pređi na izabranu“** više ne postoje. Zamjenjuju ih klik na karticu i „Aktiviraj“.

## 2b. Jedna moja greška (iskreno)

Pri provjeri javnog paketa (R14) jedna moja skripta zbog greške u lancu komandi nije napravila privremeni HOME. Zbog toga je jedno pokretanje GUI-ja (oko 10 s) koristilo **razvojni** `vault/` i `models/` u repou umjesto privremenih foldera.
- **Tvoj pravi vault („PSE Riemann rezultati“) nije bio u igri.**
- U razvojni `vault/.state/` (gitignored) upisani su redovi o pokretanju (operater „Ana“, događaji pokretanja).
- `config/` i `.cache/` koje je skripta napravila u korijenu repoa sam obrisao.
- Provjeru sam ponovio ispravno, sa privremenim HOME-om.

## 3. Kalibracija — najvažnije za živi test (ostalo iz rc1)

1. **Koliko često Doktor zove tebe.** θ se uzima doslovno po potezu (pravilo 40). Jedan odgovor sa „naravno, evo“ i bez provjere daje θ oko 45. Zamah je tada 15, a to je veće od amplitude 10, pa je atraktor borderline i Doktorova mjera ide tebi. Na mom malom korpusu (23 bezazlena odgovora) okidač je bio na 2 poteza, a nijedan nije postao mjera. Ako u živom radu bude previše, postoje dvije opcije:
   - (a) klizni prosjek θ (λ = 0,2);
   - (b) veća amplituda.
2. **Čitač usporava AI poteze.** Drugi model čita svaki AI potez (pravilo 18). Sa GGUF DeepSeek-om to može dodati desetine sekundi. Treba izmjeriti.

## 4. Moja tumačenja (provjeri, ništa ne blokira)

1. **N_max za chat i glas = 1000**: potvrdio si.
2. **Ispravka teksta dogovora.** U pravilima 20(4) i 22 bilo je „atraktor N“ u smislu „zdrav“. Promijenio sam to u „zdrav (H)“, jer N u §7 znači narcis.
3. **Doktorova odluka.** Meki znaci su nagli skok, rafal, razlika čitač–pravila, povratna radnja na spoljnom tekstu i slabiji znak štetnog izlaza. Uz zdrav atraktor ti znaci daju „ništa“. Kad se isti meki znak ponovi 3 puta zaredom (razlika ili štetni izlaz), to je „loše“. Sve ostalo je „loše“, pa mjera ide tebi.
4. **Liječenje** = reset granice + θ prozor kreće ispočetka od 30. Istorija ostaje u SHARED_LIB-u.
5. **Klasifikacija izvora po većini:** serija sa prosjekom ≥ 0,5 glasa za svoj oblik; najjači pobjeđuje, a neriješeno je „nepoznato“.
6. **Težine glasova:** za sada se uče samo težine čitača (pravila naspram modela). Šest glasova ostaje na 1,0 dok ne postoji oznaka za podjelu θ.
7. **Dodata dva okidača:** 18 (štetan izlaz) i 19 (slabiji znak). To su „tri zla“ iz starog čuvara.
8. **Zamrznut čuvar mreže** i dalje posmatra saobraćaj (ne otvara mrežu), ali bilježi poteze tek kad se odmrzne.
9. **Sadržaj na EN.** Misije, dnevnik, kartice i rezultati lab računanja ostaju na izvornom jeziku i prevode se na zahtjev (pravilo 35). Interfejs i tekst koji aplikacija sama sastavlja (brifing, budžet, ideje, čuvar, glas, red, Laboratorija, katalog lab eksperimenata) su na oba jezika.
10. **Javni paket.** Nema misija ni QRH sadržaja, a ima „Nova misija…“. Nema ni paketa metoda, izvještaja istraživanja ni dugmeta „Radni tekst (misije 2 i 3)“. arXiv QRH straža radi samo uz svoju misiju.
11. **„Nova misija…“** je dodata u oba izdanja. Bez nje javni paket ne bi imao smisla.

## 5. Šta nisam mogao / nisam radio

- **Instalacija i živi test:** traže `sudo` i tebe.
- **.exe i GitHub Release:** tek kad se dogovorimo (pravilo 38/21).
- **Spajanje u `main`:** tek na tvoje „spoji u main“.
- **Snimci iz instalirane verzije.** Pravio sam ih iz raspakovanog paketa (njegov kod i njegove biblioteke, sistemski `python3`), ne iz `apt install`-ovane verzije, jer instalacija traži sudo. Sadržaj je isti.
