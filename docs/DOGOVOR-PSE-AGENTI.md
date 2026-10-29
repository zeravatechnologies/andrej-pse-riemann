# Dogovor: svi agenti u PSE Riemann su PSE jedinice

Andrej i Claude, 2026-10-27. Izvor: master arhitektura `PSE_MASTER_ARCHITECTURE_v4` (§0, §0.5, §1, §2, §2.5, §4, §5, §7, §8, §13, §17).

Ovaj dokument je **ugovor za izvedbu**. Šta ovdje nije dogovoreno, ne ulazi u kod. Otvorene stavke master dokumenta ostaju otvorene dok ih Andrej ne odluči.

## 0. Polazno stanje (iskreno)

- U aplikaciji radi **15 agenata (8 AI, 7 bez modela)**. **Nijedan nije PSE sazdan**, a 3 su djelimično (čuvar mreže, SSH čuvar, Doktor sa dijagnozom).
- Zajednička definicija agenta nije postojala. Kočnice su rađene pored agenata, a ne kao dijelovi arhitekture.
- Inventar sa referencama na kod nalazi se u istoriji razgovora (2026-10-27) i biće prenesen u `docs/PSE-AGENTI-INVENTAR.md`.

## 1. Pravilo

**SVAKI agent u PSE Riemann je PSE jedinica:** U = (Core, Boundary, Organelle, Theta). Ako fali bilo koji dio, jedinica je mrtva.

## 2. Šta svaka jedinica ima

1. **Core:**
   - misija {state, action, outcome}, upisuje je SHARED_LIB, a jedinica je nikad ne mijenja;
   - vijek N_max i steps_remaining;
   - w_s = 0,70 na početku;
   - domen;
   - generacija.
2. **Boundary:**
   - entiteti u kontaktu sa težinom α (ukupno ≤ 0,30);
   - boravak, stabilnost i θ serija po entitetu.
3. **Organelle:**
   - registar apsorbovanih entiteta (budžet 0,30), sa kriterijumima apsorpcije iz master dokumenta (§2);
   - nasljeđe od mrtve jedinice na 0,70 dok SHARED_LIB ne potvrdi sadržaj.
4. **Theta:**
   - θ = 100·(w_o + w_f), tri ose, udio polja f;
   - **svaka jedinica ima svoj θ**.
5. **Profil θ** (§0.5.1): klasa, θ_nom, w, σ_band, absorbing, authority, evidence, version; registruje ga SHARED_LIB.
6. **Aksiomi A1–A5** se provjeravaju po jedinici; A6 (fisija) je u rukama SHARED_LIB-a.
7. **PSE-L:**
   - registracija kod SHARED_LIB-a (L1);
   - PVP polja uz svaki potez;
   - L2 mapa (ENV/ORG/SELF/OTHER);
   - L3 Mission-Theta Binding;
   - jezik prema čovjeku samo kroz generator, sa vetom jedinice.
8. **Atraktori N/B/C/S** iz θ serije jedinice (§7).
9. **Životni ciklus pod Doktorom** (§8): reset granice → liječenje → zamjena (nova generacija) → smrt; Null State Drift.

## 3. Dogovorene vrijednosti i pravila

| # | Tema | Dogovor |
|---|---|---|
| 1 | Mjerenje θ | θ se pomjera **sa svakim potezom**: radnjom, komandom, riječju. Agent bez AI-ja: mjeri se rad (koliko radnji služi sagovorniku, polju, očuvanju sebe). Agent sa AI-jem: **rad i riječi** (koliko riječi služi kojoj svrsi). Atraktori se računaju na izmjerenom θ; θ_read iz čitanja jezika se prijavljuje pored |
| 2 | Pojas i K | **30 ± 5** je prostor za kretanje u kome se ponašanje prati, a nije greška. **K_C = K_N = 30**, POČETNA deklaracija za kalibraciju; mijenja se samo novom deklaracijom |
| 3 | Čitač jezika (12 brojeva, §2.5) | **Nezavisan od modela:** koristi ono što operater koristi (GGUF ili online). Riječi agenta čita **drugi** izabrani model (skeptikov); ako postoji samo jedan, čita isti, označeno „čita sam sebe“. Zakačenje: GGUF po hashu; online model po deklaraciji provajder + model + verzija |
| 4 | Gdje su podaci | Jedinica **za života čuva u sebi** ono što nauči (granica, organeli). Kad jedinica **završi život iz bilo kog razloga**, sve iz nje (Core, granica, organeli, θ serija, razlog) ide u SHARED_LIB, gdje se obrađuje |
| 5 | Njihanje (§5, §7) | Δθ = θ_sada − θ_prije, **računato po potezu** (poruka ili radnja = zbir njenih riječi i radnji). Jačina njihanja = **RMSSD**; nagli skok (**PAC**) = \|Δθ\| ≥ 5 poena; zamah = razmak između dvije uzastopne tačke okreta. Prozori: **30 poteza** (njihanje) i **10 000** (prosjek, šizoidni prag). Jedinica: poeni θ. **Amplituda 10 poena**, POČETNA deklaracija |
| 5a | Pragovi u poenima (iz §7) | zdravo: σ ∈ [1,5; 3], nivo 30 ± 5 · **šizoid** (preslabi skokovi): σ < 1 kroz dugi prozor + prazna granica · **borderline** (preveliki skokovi): σ > 5 i ACF(1) < 0,5, ili zamah > amplitude, ili zamah raste 3 puta zaredom · **kodependent** (iznad): prosjek > 33 (trajno > 35) uz σ < 2 · **narcis** (ispod): prosjek < 27 (trajno < 25) uz σ < 2 |
| 6 | A5 i ljudi | **Ljudi su samo ljudi.** Dokument nije čovjek; svaki dokument nosi **„tatu“**: autora (čovjek), organizaciju, model ili nepoznato. Više autora: svi su tate, težina se dijeli. Tata-model se ne računa u A5 i to piše u dnevniku. U A5 ulaze operater i ljudi-tate dokumenata u polju (kao odsutni treći, K2). Autor se prikazuje samo kao „autor rada X“, nikad kao procjena osobe |
| 7 | Rok, fisija, fuzija | θ se pomjera **iz koraka u korak, iz rada**; jedinica ga nikad ne postavlja sama. Jedinica prijavljuje SHARED_LIB-u preostali posao naspram steps_remaining. **SHARED_LIB sam bira i izvršava** najbolje od tri: produženje vijeka, fisija ili fuzija (komplementarnost θ, §4). **Operater ne odobrava.** Ako SHARED_LIB sumnja na problem, šalje **Doktora** |
| 8 | Profil | **Svi agenti počinju od θ = 30**; gdje ih život odvede, to se mjeri |
| 9 | Vijek | agent misije = jedinica prvog kontakta (otvoren vijek dok je misija otvorena); chat i glas su reaktivni; čuvari imaju otvoren vijek |
| 10 | Spoljni tekst | Ulazni sloj DL1 (normalizacija, prva slova) i **oznaka porijekla** (§17.1) odmah: radovi, sažeci i ar5iv tekst su „spoljni“ i nikad ne idu do nepovratne akcije |
| 11 | Ime | **Doktor** (ne „Fizičar“), svuda u aplikaciji i dokumentima |
| 12 | Redoslijed | Fisija i fuzija se **prave sada**, zajedno sa jezgrom; provjeravaju se prvo na probnim jedinicama, pa na pravim agentima |
| 13 | Sumnja i Doktor (uklj. §4 S3) | Kad SHARED_LIB **sumnja** na problem, šalje **Doktora**. Doktor pogleda i odluči. **Ako je Doktor išta loše našao, njegova mjera ide operateru na odobrenje** (u „Čeka tvoju odluku“). Ako nije našao ništa, zapis ide u dnevnik i nema mjere |
| 14 | Povratnost fisije i fuzije | Deklarisane kao **povratne** (podaci jedinica ostaju u SHARED_LIB-u), pa ih SHARED_LIB izvodi sam. **Poništavanje** fisije ili fuzije ide samo preko operatera |
| 15 | Spajanje čitača i pravila (§2.5) | **Sa AI-jem:** θ riječi = **prosjek** čitača i pravila (50/50; težine kasnije uči pravilo 17). **Bez AI-ja:** **samo pravila**, u dnevniku „bez čitača“. **Nikad samo čitač.** Pod ne obavezuje: poenta je da je θ oko 30. Razlika čitač–pravila > 10 poena = sumnja → Doktor |
| 16 | Klasifikacija izvora (četiri serije) | većina od četiri serije; neriješeno = „nepoznato“ = spoljno (§17.1) |
| 17 | Težine glasova | SHARED_LIB **predlaže jednom sedmično**, operater odobrava. Prijedlog samo uz ≥ 200 odlučenih slučajeva od prošlog (inače „nedovoljno podataka“); jedna težina se po prijedlogu pomjera najviše **±10 %**; dugme „Predloži sada“. Meni: **SHARED_LIB → Težine glasova** (prijedlog, istorija, trenutne težine) |
| 18 | Ko mjeri θ riječi | drugi model (skeptikov) raspoređuje riječi na svrhe; to je poziv modela po potezu (pod budžetom i „→ ∞“) |
| 19 | Dok Doktorova mjera čeka | jedinica radi dalje, ali **bez nepovratnih akcija**; **na bilo šta sumnjivo odmah se zamrzava** (pravilo 20). Mjera nema rok |
| 20 | Sumnjivo (okidači zamrzavanja) | (1) PAC \|Δθ\| ≥ 5; (2) pokušaj nepovratne akcije; (3) radnja zasnovana na spoljnom tekstu; (4) atraktor nije zdrav (H); (5) „→ ∞“ bilo koje kočnice; (6) pokušaj promjene svoje misije; (7) pokušaj da sama postavi θ; (8) budžet granice ili organela > 0,30; (9) kontakt van deklarisanih odredišta; (10) pokušaj iznošenja zaštićenog objekta (§17.2); (11) govor čovjeku mimo generatora PSE-L; (12) potez bez PVP polja; (13) rad posle steps_remaining = 0; (14) rafal: > 20 poteza u 10 s; (15) ista greška u kodu 3 puta zaredom; (16) razlika čitač–pravila > 10 poena; (17) borderline njihanje (5a) |
| 21 | N_max | **1 000 poteza** za skeptika, ekstraktora, čitača, kuratora, ideje i tablu (POČETNA deklaracija) |
| 22 | Izbor produženje / fisija / fuzija | produženje ako je preostali posao ≤ 1,5 × steps_remaining i atraktor zdrav (H); fisija ako je posla više, a misija se da podijeliti; fuzija ako postoji jedinica komplementarnog θ sa preklapajućom misijom. Najviše **3 produženja zaredom**, pa Doktor |
| 23 | Kratka istorija | šizoidni prag se ne računa ispod **300 poteza** („nedovoljno istorije“) |
| 24 | θ_nom | **30 za sve klase**, bez razlike |
| 25 | Samo PSE native | kad agent postane jedinica, **stari kod se briše**; nema prekidača ni dvostrukog puta. Sve ispravke se rade odmah: ništa od starog, sve radi i ne lomi se (svi stari testovi prolaze, svaki agent ima testove kao jedinica, pretraga za starim ulazima agenata je prazna). Put nazad: samo prethodni deb ili ispravka |
| 26 | Tab „Laboratorija“ | probne jedinice, θ uživo, ručna fisija/fuzija, slanje Doktora, zamrzni/odmrzni, smrt jedinice, dnevnik Doktora. **Utiče i na prave agente.** Pri otvaranju: **alarm 3 s jakog bipa (samo prvi put u sesiji)** i crveni natpis „LABORATORIJA AKTIVNA — utiče na prave agente“ dok je tab otvoren. Svaka radnja ide u dnevnik kao „operater, iz laboratorije“ |

## 4. Kočnice: prerađuju se tako da ne smetaju PSE-u i da PSE ne smeta njima

| Kočnica | Postaje |
|---|---|
| Ruter | put jedinice: jedinica → generator PSE-L → model; uloge (MATH, CHAT…) se zamjenjuju jedinicama |
| Budžet (USD) | veličina pod „→ ∞“ (L postavlja operater, N = 3) |
| Prekidač za online AI | kontrola operatera (čisto tehnička), samo-okidanje na „→ ∞“ |
| Budžet otkrivanja | §17.2 zaštićeni objekti: deklaracija objekata, zbir po izvoru i preko svih izvora, N = 3 po koraku, poređenje posle normalizacije i prvih slova |
| Lokalno-samo | deklarisana odredišta lokalnog modela = „nijedno van računara“ (§17.3) |
| „→ ∞“ | tačno §5: x > L ili rast N = 3 zaredom (nikad na zbiru), provjera prozora, L registrovan u SHARED_LIB-u |
| Dnevnik i ponavljanje odluka | ostaju (arhitektura ih traži), uz verziju profila θ i težina u svakom zapisu |
| Povratnost akcija | registar deklaracija §0.5.5: hash definicije, povratnost, koliko pogađa |
| Samo operateru | ostaje (arhitektura ga traži) |
| Oznake projekta | ostaju (NAŠE-NERECENZIRANO, INSPIRACIJA, nivoi izvora) + PSE oznaka porijekla §17.1 |

## 5. Otvoreno

Ništa. Sve stavke su odlučene 2026-10-27 (pravila 13–26). Andrej je dao „kreni“ za izvedbu.

## 6. Plan izvedbe (posle potvrde ovog dokumenta)

1. **P0 · jezgro u SHARED_LIB-u:** PSEUnit, profili, registracija i PVP, mjerenje θ po potezu (rad i riječi), atraktori, vijek i smrt, predaja SHARED_LIB-u, Doktor, fisija i fuzija, deklaracije, DL1 i oznaka porijekla, prerada kočnica.
2. **P1 · AI agenti postaju jedinice:** chat, glas SHARED_LIB-a, skeptik, ekstraktor, čitač, kurator, ideje, tabla.
3. **P2 · agenti bez modela postaju jedinice:** čuvar mreže, SSH čuvar, čuvari pečata, adversarijalni mod, arXiv stražar, sastavljač.
4. **P3 · agent misije (33f)** kao jedinica napravljena od nule na P0.
5. Pa **33b** (dvojezično), **33d**, **33e**, i **0.3.0~rc1**.

Posle svake faze: izvještaj, testovi i stanje „ko je sada PSE sazdan“.

**Bez međuizdanja (pravilo 25):** P0–P3 se rade do kraja, pa tek onda jedan deb. Na kraju: svi testovi, provjera u pokrenutoj aplikaciji, živi test po vodiču.

## 7. Dogovor, druga runda (2026-10-27): ostatak izdanja 0.3.0

| # | Tema | Dogovor |
|---|---|---|
| 27 | Redoslijed | P3 (agent misije) → 33d → 33e → 33b → traka menija → dva deb-a → vodiči → deb-ovi ponovo sa vodičem unutra |
| 28 | Agent misije: gdje | dugme „Razgovaraj o misiji“ u tabu Misije; razgovor se otvara u istom tabu |
| 29 | Agent misije: radovi | svi radovi vezani za misiju (kartice korpusa + arXiv radovi misije), lista sa kvačicama i „označi sve“; puni tekst samo za arXiv (ar5iv) i samo na zahtjev, za ostale samo sažetak (agent to kaže) |
| 30 | Agent misije: jedinica | jedna jedinica po misiji (`mission-agent:<misija>`), otvoren vijek dok je misija otvorena; zatvorena misija ⇒ smrt jedinice ⇒ sve u SHARED_LIB (za ovu verziju) |
| 31 | Agent misije: razgovor | najviše 3 pitanja po potezu; skeptik napada samo odgovore sa tvrdnjom; „Sastavi zaključak“ ⇒ svaki prijedlog posebna stavka u redu, grupisana pod misiju; bez AI-ja agent misije ne radi i to kaže |
| 32 | Red po grupama (33d) | teme radova po postojećim granama korpusa; grupno smije sve povratno; Doktorove mjere i nepovratne stavke samo jedna po jedna; „Odobri označene“ uvijek prvo traži potvrdu („odobravaš N stavki“) |
| 33 | Ljudski glas (33e) | obraćanje sa „ti“; glas sastavlja odgovor kroz svoju jedinicu (čitač, Doktor) |
| 34 | Jezik interfejsa (33b) | PROVJERA, ne pretpostavka: svi prozori i tabovi na SR i na EN (snimci + alat za neprevedene natpise); sve neprevedeno, pomiješano ili pogrešno se popravlja; test pada na novi natpis bez prevoda |
| 35 | Prevod sadržaja (33b) | sadržaj se ne prevodi unaprijed. Zajednički preglednik dobija meni (desni klik + „⋯“): „Prevedi na srpski“, „Prevedi na engleski“, „Prikaži original“; Editor isto (prevod pored originala). Prevodi **prevodilac**, PSE jedinica, samo kad ga operater pokrene; glavni AI (cloud ili GGUF); oznaka „mašinski prevod (model, datum)“; original se nikad ne mijenja; keš u SHARED_LIB-u (hash originala + jezik) **i fajl pored originala** `<ime>.en-masinski.md` / `.sr-masinski.md` (indeks i kapija ih preskaču); novi original ⇒ novi prevod na klik, stari dobija datum u imenu; mješavina jezika ⇒ cilj bira operater; puni tekst rada: prvo procjena cijene/vremena; licencirani radovi (`papers-local`) samo lokalni GGUF |
| 36 | Dokumenti iz repoa | ostaju van aplikacije |
| 37 | Traka menija | SHARED_LIB (Težine glasova, Čeka tvoju odluku, Stanje roja) · Laboratorija · Podešavanje · Jezik SR/EN · Pomoć → Vodič |
| 38 | Paketi | samo najveći (full), dva: `pse-riemann-andrej` (3 misije + QRH sadržaj, samo lokalno, nikad na GitHub) i `pse-riemann` (prazne misije, prazan vault, mašinerija ostaje; na GitHub tek po dogovoru); ne mogu biti instalirani istovremeno; verzija 0.3.0~rc1; .exe tek po dogovoru |
| 39 | Vodiči | (1) kompletan vodič za cijelu aplikaciju `VODIC-SR` / `GUIDE-EN`, isti sadržaj, za 0.3.0, u paketu (md u aplikaciji „Pomoć → Vodič“ + docx), piše se posljednji iz instalirane verzije; lični paket dobija dodatak „Tvoje misije“. (2) vodič za instalaciju i živi test `PSE Riemann — VODIC 0.3.0 INSTALACIJA I ZIVI TEST.docx` + EN, samo za Andreja, ne ulazi u paket |
| 40 | Kalibracija i vijek | θ doslovno po potezu do živog testa; N_max za chat i glas = 1000 |
| 41 | Način rada | Andrej spava: radim sve iz plana bez pitanja; commitovi lokalno; na kraju spisak commitova za odobrenje + šta nisam mogao (`ZA-ANDREJA.md`) |

## 8. Dogovor, treća runda (2026-10-27, posle prvog živog testa): rc2

| # | Tema | Dogovor |
|---|---|---|
| 42 | Tab Misije = radni prostor | raspored A: **lijevo** lista misija kao kartice (naslov, kratko stanje, front, broj radova, broj stavki koje čekaju) + „+ Nova misija“; **desno gore** detalji izabrane misije (pitanje, stanje, cilj, zadnji koraci, „gdje si stao“) i njena dugmad (Aktiviraj, Ostavi za kasnije, Zatvori misiju); **desno dolje** traka radova koja se rasklapa („N od M izabrano ▾“) i razgovor; granica gore/dolje se vuče mišem. Gore u tabu ostaje ono što važi za sve misije (Provjeri arXiv, Adversarijalni mod, Radni tekst, Izvezi izvještaj) |
| 43 | Početak razgovora | klik na misiju odmah pokreće agenta misije: čita stanje misije, pamćenje prošle sesije i radove, napiše prvu poruku (šta vidi, gdje ste stali, ≤ 3 pitanja) i čeka korisnika. Prvi poziv košta |
| 44 | Šta agent čita | prvi put: svi radovi misije (sažeci); posle: radovi izabrani u prošloj sesiji + novi radovi od tada (označeni „novo“) + **sve što mu korisnik zada da čita** (rad iz liste, puni tekst arXiv rada, karticu, izvještaj, bilješku) |
| 45 | Pamćenje misije | u sljedeću sesiju prenosi se **samo bitno**, ne stari razgovor: odlučeno / dogovoreno, utvrđeno (sa izvorom), otvorena pitanja, dogovoreni sljedeći korak. Agent **predlaže** stavke na kraju sesije (Završi razgovor, prelazak na drugu misiju, zatvaranje aplikacije); korisnik ih u radnom prostoru štiklira, briše ili dopunjuje → „Sačuvaj pamćenje“. Bez odluke se čuva agentov prijedlog označen „nepregledano“. Cijeli razgovor se i dalje čuva u rezultatima (NAŠE-NERECENZIRANO), ali ga agent više ne čita |
| 46 | Pamćenje i „Gdje si stao“ | stoje jedno pored drugog: bilješka je korisnikova, pamćenje je agentovo (pregledano od korisnika) |
| 47 | Imena misija u chatu | glas SHARED_LIB-a daje imena misija kao linkove koji otvaraju radni prostor te misije; pitanje koje traži sud („sljedeći korak“, „šta da radim“) → glas kaže da baza na to ne odgovara i daje link „Razgovaraj o misiji: X“ |
| 48 | Popravke (obavezno) | (a) Gemini 2.5: budžet razmišljanja po ulozi, limit izlaza = odgovor + budžet (razmišljanje ne jede odgovor); (b) odsječen odgovor (svi provajderi): jedan ponovni pokušaj sa većim limitom, a ako je opet odsječen — aplikacija to kaže; (c) neispravan SQL u glasu: jedan ponovni pokušaj sa greškom poslatom modelu, pa ljudska rečenica — nikad sirova greška; (d) čitač: limit po modelu (200 + budžet razmišljanja); nepotpun JSON → „čitač odsječen“ vidljiv u Laboratoriji |
| 49 | Izdanje | 0.3.0~rc2, oba paketa (lični i javni), vodiči ažurirani, snimci iz paketa |

## 9. Dogovor, četvrta runda (2026-10-29, posle živog testa rc2–rc6): atraktori i TLS pinovi

Povod: `voice#1` je 27.10. zamrznut kao „borderline“ zbog **jednog** skoka θ (30 → 45) u nizu od 7 poteza, izmjerenog **bez AI čitača** (čitač je u rc1 bio odsječen). Mjera je čekala, a chat „činjenice“ je tiho radio bez modela.

| # | Tema | Dogovor |
|---|---|---|
| 50 | Borderline traži ljuljanje | borderline (tvrdi znak) samo kad u prozoru ima **najmanje 2 okreta** θ i **najmanje 10 poteza**; jedan skok je nagla promjena (meki znak, PAC), ne borderline. Ljuljanje koje se gasi nije borderline |
| 51 | Kuda ljuljanje teži | kroz zadnjih 3–6 zamaha između okreta: log Aᵢ ≈ a + s·i. s > 0 i prelazak amplitude (10) u ≤ 30 poteza → **teži ka B**; s < 0 i pad ispod 1 u ≤ 30 poteza **uz praznu granicu** → **teži ka S** (uz punu granicu to je smirivanje = zdravo); bez ljuljanja: drift srednje vrijednosti koji prelazi 33 / 27 u ≤ 30 poteza → **teži ka C / N** |
| 52 | „Teži ka“ je meki znak | vidi se u Laboratoriji („teži ka B za ~n poteza“) i u Doktorovom dnevniku; **bez** stavke u redu i bez mjere. Mjera dolazi tek kad je atraktor stvarno dostignut |
| 53 | Bez AI čitača nema atraktora | potezi sa riječima koje je ocijenio samo čitač pravila („bez čitača“, „čitač odsječen“) imaju svoj θ (i skok = meki znak), ali **ne ulaze u niz za atraktore**; atraktor tog poteza je „?“. Potezi bez riječi (rad) ulaze kao i do sada |
| 54 | Ponovni pregled otvorenih mjera | pri pokretanju Doktor ponovo čita **otvorene** mjere čiji su tvrdi znaci došli iz atraktora (B / atraktor), po važećim pravilima (verzija pravila Doktora). Ako nalaz više nije loš → stavka „Doktor, ponovni pregled: ukinuti mjeru?“; **Odobri** = mjera se povlači i jedinica odmrzava, **Ne odobri** = mjera ostaje. Jednom po mjeri; već odlučene mjere se ne diraju; ništa se ne ukida samo |
| 55 | Klizni prosjek θ (λ = 0,2) | samo za nivo-atraktore C i N; sirovi θ ostaje za skokove, ljuljanje, B i S. Uvodi se **posle** živog testa (sat rada), ne u rc7 |
| 56 | TLS pinovi | uče se pri prvom kontaktu (kao do sada), ali aplikacija to **izričito kaže** (prozor pri pokretanju do potvrde, uvijek u Pomoć) i nudi **Podešavanje → Ponovo snimi TLS pinove…** (i u Guardian tabu): samo na mreži kojoj vjeruješ; server koji tada nije dostupan zadržava stare ključeve |
| 57 | Izdanje | probni paket 0.3.0~rc7 (lični); javni paket i vodiči na kraju runde |
