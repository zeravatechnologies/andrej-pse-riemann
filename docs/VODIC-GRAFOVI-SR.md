# Vodič: tab Grafovi

Tab **Grafovi** crta funkcije i za svaku tačku kaže sve što aplikacija zna o njoj. Uzor je Android aplikacija „Calculus Tools“. Tamo su tri dijela bila tri taba, a ovdje su tri panela jedan pored drugog:

| Panel | Šta radi |
|---|---|
| **Funkcije** (lijevo) | spisak funkcija, svaka u svojoj boji, i klizači parametara |
| **Grafovi** (sredina) | crtež: zum, pomjeranje, očitavanje pod mišem |
| **Kalkulacije** (desno) | „sve o tački“ za tačku na koju klikneš i računi na zahtjev |

**Svaki od tri panela ima svoje dugme ⤢** u zaglavlju (pored naslova „Funkcije“, „Graf“, „Kalkulacije“):
- klik raširi taj panel preko cijelog taba, a ostala dva se sakriju;
- dugme se pretvori u **⤡**, i ponovni klik vraća sva tri panela.

Dugme **⤢ raširi** na vrhu taba radi isto što i ⤢ grafa.

Ako ti treba još mjesta, raširi i sam chat na njegovom ⤢, a chat uvijek vraća Esc. Na ekranu sa krupnim tekstom (npr. Surface, 26 pt) tri panela i chat su tijesni. Tada bočni paneli dobiju klizač, a najbolje je raširiti panel na kome radiš.

---

## 1. Funkcije

### Ugrađene funkcije projekta (dugme „+ ugrađena“)

| Funkcija | Nivo | Šta znači tačka na njoj |
|---|---|---|
| B(ℓ) = 11/12 − ℓ/4 | RAD | zajednička prava: za dato ℓ, granica B. 11/12 je ℓ = 0, 7/8 je ℓ = 1/6 |
| E_Liu(δ) na optimumu | RAD | eksponent visoke strane (Liu) po δ. Ako je max ≤ 0, metoda prolazi |
| E_XS(δ) na optimumu | RAD | isto za Xu–Sang; E_XS = E_Liu + T |
| max_δ E_Liu(ℓ) | NAŠE-NERECENZIRANO | najgori δ za dato ℓ; nula je granica metode ℓ* |
| B*(t) — proširenje t | NAŠE-NERECENZIRANO | granica metode duž proširenja t (misija 1) |
| B*(w) — proširenje w | NAŠE-NERECENZIRANO | granica duž težine w (w = 0,25 je Xu–Sang) |

B*(t) i B*(w) su skupe: oko 4,6 s i 1,9 s po tački na Dellu (na Aceru je procjena oko 1,8 puta sporije). Crtaju se u pozadini iz 9 tačaka, a u naslovu grafa za to vrijeme piše „računam: …“.

### Tvoje funkcije (dugme „+ funkcija“)

Izaberi vrstu i upiši izraz:

| Vrsta | Promjenljiva | Primjer |
|---|---|---|
| realna y = f(x) | `x` | `11/12 - x/4` · `x**3 - 2` · `sin(30*x)/x` |
| kompleksna w = f(s) | `s` | `zeta(s)` · `gamma(s)*zeta(s)` |
| površ z = f(x, y) | `x`, `y` | `x**2 - y**2` |
| parametarska | `u` | `cos(u); sin(u)` (x i y razdvojeni sa `;`) |
| polarna r = f(θ) | `th` | `1 + cos(th)` |

**Šta je dozvoljeno:**
- operacije `+ − * / **` (može i `^`);
- funkcije `sin cos tan exp log sqrt abs atan asin acos sinh cosh tanh re im arg conj floor min max zeta Z gamma`;
- konstante `pi e i`;
- klizači `l b k t w d low delta`.

Sve ostalo se odbija **prije** prevođenja: atributi, uvoz, liste, tekst i slično. Tako upisani tekst ne može uraditi ništa osim računa. Ogroman broj (npr. `10**10**10`) postaje praznina u krivoj, a ne zaglavljen računar.

Domen „od/do“ koristi se za račune (korijeni, površina, pomak do cilja). Upisane funkcije crtaju se preko cijelog vidljivog dijela.

**Uređivanje:**
- dvoklik ili „Uredi“ mijenja funkciju; „Boja“ bira boju; „Ukloni“ je briše;
- kvačica uključuje ili isključuje prikaz;
- spisak se pamti u SHARED_LIB-u, pa preživi restart i ulazi u bilješku „gdje si stao“ misije.

### Klizači (parametri)

ℓ, b, κ, t, w, d, **niska strana** i **Δ**. Pomjeranjem klizača graf se odmah precrtava. Pored „niske strane“ piše **σ\* = 11/16 + niska strana**. Klizač niske strane je pripremljen za korak 4 ove stavke (povezani prikazi), a u izrazu se klizač koristi imenom, npr. `11/12 - x/4 + low`.

---

## 2. Kretanje po grafu

| Želiš | Miš | Tastatura (klikni na graf) | Dugme |
|---|---|---|---|
| pomjeriti lijevo / desno | prevuci lijevim tasterom | ← / → | ◀ / ▶ |
| pomjeriti gore / dolje | prevuci lijevim tasterom | ↑ / ↓ | ▲ / ▼ |
| veći korak | — | **Shift** + strelica (40 % umjesto 10 %) | — |
| uvećati / umanjiti | točkić (oko kursora) | + / − | + / − |
| vratiti početni pogled | — | Home | ⌂ |

Prevlačenje pomjera pogled. **Klik bez prevlačenja** na krivu bira tačku. **Dvoklik** na krivu otvara njenu karticu izvora, ako je ima.

**Ciljevi** (isprekidane linije 7/8, 0,87, 5/6, 3/4, 1/2) i **zidovi** (crvene tačkaste linije B ≥ 0,87 i ℓ ≤ 1/5) uključuju se kvačicama na vrhu.

Naslov grafa uvijek pokazuje **nivo** onoga što je nacrtano, npr. „nivo: KORISNIK · RAD“.

---

## 3. Sve o tački

**Kad pređeš mišem** preko krive, ispod grafa piše: koja funkcija, koordinate, nivo i najbliži cilj sa razlikom.

**Kad klikneš** na krivu, panel Kalkulacije pokaže sve što se zna o toj tački:
- koordinate x i y;
- koja funkcija ili metoda, njen nivo i link na karticu izvora (klik otvara karticu);
- **značenje** tačke (npr. „ℓ → granica B“);
- šta je tačka: nula, presjek (sa kojom funkcijom), zid, stacionarna tačka (moguć optimum), za eksponente „E ≤ 0: metoda prolazi“ ili „E > 0: ne prolazi“;
- f′ u tački;
- **udaljenost do svih ciljeva** (sa predznakom);
- vrijednosti svih klizača.

---

## 4. Računi na zahtjev

Ispod „sve o tački“ stoje **najviše 4 ponude** koje odgovaraju vrsti tačke. Ostale su pod „više…“.

| Tačka | Ponuda |
|---|---|
| bilo gdje na krivoj | izvod i tangenta · drugi izvod (konkavnost) · Taylorov polinom |
| presjek | tačan presjek + interval-certifikat |
| nula | tačan korijen (sympy) + interval-certifikat |
| stacionarna (f′ ≈ 0) | drugi izvod: da li je optimum i koliko je oštar |
| B blizu cilja | pomak parametra do cilja, ili dokaz da ga domen ili zid sprečava |
| proširenje B*(t), B*(w) | kuda proširenje pomjera B: bliže ili dalje od cilja (misija 1) |
| dvije funkcije | osjenčana površina između njih („rezerva“) |

**Procjena trajanja.** Uz svaku ponudu stoji „(odmah)“, „(~N s)“ ili „(~N min)“. Procjena je broj potrebnih izračunavanja pomnožen vremenom jednog izračunavanja:
- za upisane funkcije to vrijeme se izmjeri;
- za ugrađene je izmjereno na Dellu, a Acer je procjena.

Što je jeftino (do 0,3 s) računa se odmah. Skuplje aplikacija samo **nudi** pitanjem „Želiš li da izračunam … (~N s)?“.

**Kako se računa:**
- Računa **Python, deterministički**. AI samo objašnjava, i to kad ga pitaš.
- Račun ide **u pozadini**, jedan po jedan. Dugme **Prekini** zaustavlja sve.
- Pozadinski red poštuje limitere: stoji dok je aktivna „→ ∞“ pauza ili dok je slobodne memorije manje od 0,5 GB.
- Svaki rezultat se **kešira** (isti račun drugi put je trenutan) i zapisuje u SHARED_LIB (tabela `graph_runs`) sa oznakom **NAŠE-NERECENZIRANO** i tvojim imenom.

**Šta znači interval-certifikat.** f se računa intervalnom aritmetikom na krajevima malog intervala oko korijena. Ako su vrijednosti strogo suprotnog znaka **kao intervali**, korijen sigurno postoji (zaokruživanje to ne može lažirati). Ako interval izvoda ne sadrži 0, korijen je **jedinstven**. Certifikat važi samo za upisane izraze, jer ugrađene funkcije su kod. Primjer: Liuov kubni polinom `-7884*x**3 + 18819*x**2 - 14643*x + 3686` na domenu [0,87, 0,88] daje korijen B\* = 0,874957019420, certifikovan i tačan (sympy).

**Taylorov polinom:**
- upisane funkcije idu kroz mpmath sa 40 cifara;
- ugrađene se dobijaju fitom na malom simetričnom uzorku, što piše uz rezultat („procjena“).

---

## 5. Prikazi (padajući meni „prikaz“)

| Prikaz | Šta crta | Primjer |
|---|---|---|
| **Kartezijanski** | y = f(x): realne i ugrađene krive, ciljevi, zidovi, osjenčana rezerva | B(ℓ), E_Liu(δ), E_XS(δ) |
| **Parametarski** | putanje (x(u), y(u)) i krive y = f(x) zajedno | ugrađene putanje (ℓ\*(t), B\*(t)) i (ℓ\*(w), B\*(w)): kako se granica metode kreće po pravoj B(ℓ) dok raste proširenje. Strelica na kraju pokazuje smjer parametra |
| **Polarni** | r = f(θ), u jednakoj razmjeri osa | `1 + cos(th)`, `cos(3*th)` |
| **Vektorsko polje** | površ z = f(x, y) kao boja (plavo < 0 < crveno), žuta linija z = 0 i strelice smjera najbržeg pada (−∇f) | ugrađena „max_δ E_Liu nad (ℓ, κ)“ |

**Vektorsko polje nad (ℓ, κ):**
- boja je najgori eksponent;
- **žuta linija E = 0 je granica metode** ℓ\*(κ); u Liu familiji leži na ℓ ≈ 0,1668 skoro nezavisno od κ;
- strelice pokazuju kuda treba ići da metoda prođe (E ≤ 0).

Klik na polje daje vrijednost, gradijent, vrstu tačke po Hesijanu (minimum, maksimum ili sedlo) i „ako je ovo granica: B = 11/12 − ℓ/4“.

**Putanje proširenja** su skupe: oko 7 tačaka po 2–4 s, računaju se u pozadini, a u naslovu za to vrijeme piše „računam …“.

**Rezerva.** Kada u Kartezijanskom prikazu izračunaš „osjenčana površina između dvije funkcije“, površina između njih (na zajedničkom domenu) ostaje osjenčana na grafu. Promjena prikaza briše sjenčenje.

### Kompleksni prikazi (korak 4)

Treba ti vidljiva **kompleksna** funkcija: „+ funkcija“ → vrsta „kompleksna“ → npr. `zeta(s)`.

| Prikaz | Šta vidiš |
|---|---|
| **Kompleksni (fazni portret)** | boja = arg f, svjetlina = \|f\| (nule su tamne, polovi svijetli). **Bijele** linije su Re f = 0, **crne** Im f = 0, a nule su njihovi presjeci. Isprekidano: kritična traka 0 < Re s < 1 i prava 1/2. **Zeleno**: poluravan bez nula Re s > σ\*. Za ζ su poznate nule ucrtane kao kružići |
| **Presjek duž prave Re s = 1/2** | \|f(1/2+it)\| (puna linija), Re (crtice), Im (tačkice); za ζ i Hardyjeva Z(t) (narandžasto), koja mijenja znak u svakoj nuli |
| **Povezani: ravan eksponenata ↔ ℂ** | lijevo prava B(ℓ) i horizontala σ\*, a njihov presjek je ℓ metode; desno ista σ\* kao granica poluravni bez nula. Pomjeri klizač i mijenjaju se obje strane |

**Klizač „niska strana + Δ“.** σ\* = 11/16 + niska strana + Δ:
- početno je niska strana = 3/16, pa je σ\* = 7/8, tj. metoda 7/8;
- Δ je dodatni gubitak koji metoda trpi;
- kad σ\* dostigne 1, **oblast bez nula nestaje**, i to piše i na grafu i pored klizača;
- metoda 7/8 podnosi Δ do 1/8.

To je mjerilo za mapu prenosivosti (misija 2): koliko gubitka korak u višem stepenu smije donijeti.

**Fazni portret** se računa u pozadini: mreža 160×160 na Dellu (oko 2 s za ζ), 100×100 na Aceru. Dok traje, u naslovu piše „računam …“. Svako pomjeranje ili zum crta novu mrežu.

**Klik na kompleksnu tačku** daje:
- s, f(s), |f| i arg f;
- udaljenost do prave 1/2;
- da li je tačka u kritičnoj traci ili u poluravni bez nula;
- za ζ, najbližu poznatu nulu i udaljenost do nje.

Ponude:
- **kompleksni izvod** f′(s);
- **broj nula u vidljivom pravougaoniku**: princip argumenta (namotavanje f po rubu, profinjeno gdje faza skače); ako ni poslije profinjenja nije siguran, piše „NESIGURNO“. Za ζ u [0,1 · 0,9] × [1 · 30] daje 3 nule (γ = 14,13; 21,02; 25,01);
- **rezidua u tački** (kružni integral); za ζ u s = 1 daje 1.

### 3D i više dimenzija (korak 5)

**Pravilo:** na ekranu su najviše 3 dimenzije. Četvrta je boja, a peta i dalje su klizači ili animacija, i uvijek se vide.

| Prikaz | Šta vidiš |
|---|---|
| **3D** | površ iznad ravni. Za kompleksnu f to je \|f(s)\| iznad ℂ (odsječeno na 6), **obojeno po arg f**: nule su jame, a pol ζ u s = 1 je šiljak. Za površ z = f(x, y) visina je z. Ugrađene „z = σ“ i „z = B(ℓ) nad (ℓ, σ)“ zajedno daju **dvije površi koje se sijeku po krivoj σ = B(ℓ)** (žuta linija) |
| **Male slike** | ista slika za **6 vrijednosti** parametra izabranog u „5. dim.“. Za površ max_δ E nad (ℓ, κ) i parametar b vidi se kako se granica (žuto) pomjera sa b: najdalje je kod b ≈ 0,12 (Liuov optimum) |
| **Paralelne koordinate** | svi parametri metoda odjednom: ose ℓ, b, κ, B, jedna izlomljena linija po metodi (Liu, Xu–Sang, t = 0,25 / 0,5 / 0,75, w = 0,05 / 0,15 / 0,2). Brojevi iznad i ispod ose su njen maksimum i minimum. Pod mišem piše tačan red. Računa se u pozadini (8 optimuma, oko 10–40 s) |

**Okretanje u 3D:**
- prevuci mišem;
- strelice okreću za 10° (sa Shift za 30°);
- dugmad ◀ ▲ ▼ ▶ okreću za 9°;
- ⌂ vraća početni ugao.

**Boja (4. dim.):**
- „visina / arg f“ je podrazumijevano;
- možeš izabrati i drugu vidljivu površ, pa se prva boji vrijednostima druge (plavo < 0 < crveno).

**5. dim. i ▶:** izaberi parametar (npr. w ili b). **▶** ga pušta da prolazi kroz svoj opseg (animacija), a **⏸** ga zaustavlja. Isti izbor koriste i Male slike.

Površ max_δ E nad (ℓ, κ) računa se za **b sa klizača**. Klizač b počinje na Liuovom optimumu (≈ 0,1234), pa početna slika odgovara Liuu, a pomjeranje b zaista pomjera granicu.

**Mreža:** 3D je 70×70 na Dellu i 40×40 na Aceru; male slike su 60×60 i 36×36 po slici.

## 6. Izvoz

- **PNG / SVG**: slika grafa kakav je na ekranu, na tamnoj pozadini, sa oznakom nivoa u naslovu.
- **CSV**: tačke svih vidljivih krivih u trenutnom pogledu, kolone `function, level, x, y`.

---

## 7. Lab grafovi (korak 6)

Grafovi u tabu **Lab** su sada interaktivni, sa istim kretanjem kao ovdje:
- točkić, + i − za zum;
- prevlačenje, strelice (Shift = veći korak) i ◀ ▲ ▼ ▶ za pomjeranje;
- ⌂ vraća pogled;
- ispod grafa stoji vrijednost pod mišem;
- **⤢** daje grafu cijelo izlazno polje;
- ako run ima više grafova, biraš ih u meniju „graf:“.

**PNG ostaje.** Svaki run i dalje zapisuje svoj PNG pored rezultata, i kartice se pozivaju na njega. Dugme **„Sačuvaj PNG“** snima graf onako kako ga trenutno vidiš (zumiran, pomjeren). Tu su i **SVG** i **CSV** (tačke u vidljivom dijelu).

Stari runovi, nastali prije ovog koraka, nemaju zapisan opis grafa, pa se za njih prikazuje njihov PNG.

## 8. Šta dalje

Stavka 29 je završena. Ovaj vodič ulazi u kompletne SR/EN vodiče aplikacije, koji se pišu posle izgradnje .deb i .exe.
