# PSE Riemann — vodič za živi test (0.2.0~rc2)

Stavka 35 runde 3. Test radi **Andrej**, na Dellu. Paket: **B** (puni), fajl `pse-riemann_0.2.0~rc2_amd64.deb`. Leži na Desktopu i na GitHubu (Releases → `test-0.2.0-rc2`).

**Svrha:** potvrditi na pravom ekranu i u pravoj instalaciji ono što sam ja mogao provjeriti samo testovima, snimcima bez ekrana i selftestom iz raspakovanog paketa. Sve što ovdje ne radi je nalaz, a ne tvoja greška.

**Trajanje:** oko 60–90 minuta bez API ključa, plus 15–30 minuta ako probaš i cloud AI (dio G).

---

## Prije početka

- **Snimak ekrana u bilo kom trenutku:**
  - **F12** = prozor ispred;
  - **Shift+F12** = samo aktivni tab;
  - **📷** u gornjoj traci = cijeli prozor.

  Slike idu u `~/Desktop/PSE Riemann rezultati/snimci ekrana/`. Snimaj sve što izgleda čudno.
- **Zapisnik:** na kraju ovog vodiča je tabela. Za svaki test upiši ✓, ✗ ili ~ (djelimično) i kratku napomenu.
- **Svi rezultati su u vidljivom folderu `~/Desktop/PSE Riemann rezultati/`** (dugme 📂 u traci ga otvara; `PROČITAJ.txt` objašnjava podfoldere). Ono što je rc1 sačuvao u skrivenom `~/.local/share/pse-riemann/` premjesti se tamo samo, pri prvom pokretanju. Potpuno je odvojeno od foldera `PSE Riemann` (kod) na Desktopu.
- Za sudo, mrežu i ključeve sve radiš ti. Aplikacija ključeve nikad ne traži u chatu.

---

## A · Instalacija

**T1 · Instalacija paketa**

```
sudo apt install ~/Desktop/pse-riemann_0.2.0~rc2_amd64.deb
```

Očekuješ: apt instalira `pse-riemann` 0.2.0~rc2 bez greške (eventualno doda nekoliko sistemskih biblioteka). Ako je ranije bio instaliran 0.1.0, ovaj ga zamijeni.

**T2 · Provjera verzije i pomoćnog programa**

```
dpkg -s pse-riemann | grep Version
ls -l /usr/lib/pse-riemann/pse-guard-helper
```

Očekuješ:
- `Version: 0.2.0~rc2`;
- `-rwxr-xr-x 1 root root … pse-guard-helper`, tj. vlasnik root i niko drugi ne može pisati u njega. Čuvar ga koristi samo pod tim uslovom.

**T3 · Selftest iz instaliranog paketa**

```
pse-riemann --selftest
```

Očekuješ: na kraju **„✅ SVE PROLAZI“**, oko 44 kvačice, uključujući „Test prihvatanja (poenta)“ i „SR/EN“.

Nalazi pod „Host“ (npr. SSH na 0.0.0.0:22, NetBIOS) su stanje tvog računara, ne aplikacije. Zapiši ih, ali nisu greška paketa.

---

## B · Prvo pokretanje

**T4 · Pokretanje iz menija**

Otvori aplikaciju iz menija (Aktivnosti → „PSE Riemann“) ili komandom `pse-riemann`.

Očekuješ:
- prozor se otvori na ekranu na kome je miš, ne veći od ekrana, centriran;
- naslov prozora sadrži `0.2.0~rc2`;
- čuvar (Guardian) se pokrene kao poseban proces sa ikonom u traci sistema.

**T5 · Prvo podešavanje (5 koraka)**

1. **Ime operatera:** upiši „Andrej“.
2. **Glavni AI:**
   - bez ključa izaberi **lokalni GGUF**: „GGUF sa bilo kog mjesta“ → `~/Desktop/PSE Riemann/models/DeepSeek-R1-0528-Qwen3-8B-Q5_K_M.gguf`, ne kopira se;
   - ili izaberi „bez AI“.
3. **Skeptik:** mora biti drugi model.
   - Ako imaš samo DeepSeek, izaberi „bez skeptika“.
   - Ako želiš lokalnog skeptika, izaberi `~/Downloads/Qwen2.5-7B-Instruct-Q6_K.gguf`.
4. **Deklaracije:**
   - DeepSeek hash treba da se poklopi sa objavljenim (`044519a2…1140e`); potvrdi;
   - za Qwen ne postoji objavljeni hash u aplikaciji, pa ga deklarišeš ti.
5. **Čuvar pri prijavi** + email: po želji.

Očekuješ:
- svaki korak staje na ekran;
- polja se ne brišu kad ideš naprijed-nazad;
- na kraju se otvori glavni prozor.

**T6 · Gornja traka**

Očekuješ:
- pilule: misija, operater, θ, kartice, budžet, Guardian, glavni, skeptik, RAM, „Online AI“, SR | en, 📷, „Čeka tvoju odluku“;
- na užem prozoru traka se lomi u dva reda, a ništa ne izlazi van ekrana.

---

## C · Ekran i izgled

**T7 · Veličina teksta i prozora**

Očekuješ: tekst je iste fizičke veličine kao u drugim programima. Aplikacija mjeri ekran: na Dellovom HDMI monitoru oko 12–13 pt.
- Probaj **Ctrl +**, **Ctrl −** i **Ctrl 0**: tvoja veličina uvijek ima prednost.
- Prevuci prozor na drugi monitor, zatvori ga i ponovo otvori: zapamćena pozicija se koristi samo ako još staje na ekran.

**T8 · Raširi / vrati (⤢ / ⤡)**

Probaj ⤢ u gornjem desnom uglu panela u tabovima **Lab**, **Corpus**, **Editor**, **Tabla**, **Ideje**, na obje kartice u **Pregledu**, na sva tri panela u **Grafovima** i na chatu.

Očekuješ: panel zauzme mjesto susjeda, a ⤡ vraća tačno kako je bilo.

**T9 · SR | EN**

Klikni „SR | en“.

Očekuješ:
- prozor se ponovo otvori na engleskom; svi tekstovi interfejsa su prevedeni;
- sadržaj (dnevnik, kartice, odgovori modela) namjerno ostaje na izvornom jeziku.

Vrati na SR.

---

## D · Misije, Ideje, red odluka

**T10 · Tri misije u krug**

U tabu **Misije**:
- vide se tri misije (kontinualna transformacija, viši stepen, kompleksna verzija);
- probaj „Sljedeća misija ⟳“ dva puta (pita bilješku „gdje si stao“), pa treći put: vrati se na prvu i vidiš karticu **„Gdje si stao“** sa svojom bilješkom;
- pilula „misija“ u traci prati izbor;
- probaj „Dok čeka“: zamrznuta ↔ tiho skuplja.

**T11 · Cilj misije**

Promijeni cilj misije 2 na 2, pa nazad na 1.

Očekuješ: mijenja samo operater, a promjena je zapisana (vidi se u Pregledu → Zadnji događaji).

**T12 · Ideje**

Tab „Ideje“:
- vidi se zasijana INSPIRACIJA o geometrijskom Langlandsu, uz napomenu „skeptik nedostupan“ ako nemaš drugog modela;
- probaj „Zadrži“ ili „Pretvori u otvoreno pitanje“; potonje dodaje korak misiji 2;
- značka „Ideje (n)“ se smanji.

**T13 · Čeka tvoju odluku**

Očekuješ:
- dugi naslovi se prelamaju;
- dugmad **Odobri** / **Ne odobri** su na ekranu;
- odluka se izvršava samo jednom.

---

## E · Grafovi (vodič: dugme „?“ u tabu)

**T14 · Kretanje**

Prikaz „Kartezijanski“, ugrađena B(ℓ). Probaj:
- prevlačenje mišem, točkić;
- strelice na tastaturi (prvo klikni na graf), Shift + strelica;
- dugmad ◀ ▲ ▼ ▶ + − ⌂.

Očekuješ: sve pomjera i zumira, a ⌂ vraća početni pogled.

**T15 · Sve o tački**

Klikni na pravu B(ℓ) kod ℓ ≈ 0.1667.

Očekuješ: desno „Sve o tački“ (nivo RAD, kartica izvora, cilj 7/8 sa udaljenošću ≈ 0), najviše 4 ponude, a „izvod i tangenta“ se izračuna odmah. Dvoklik na krivu otvara karticu.

**T16 · Skup račun**

Dodaj ugrađenu „B*(t) — proširenje t“.

Očekuješ: u naslovu piše „računam…“, a za oko 30–40 s pojavi se 9 tačaka. Ponude za nju pitaju „Želiš li da izračunam … (~N s)?“. Dugme **Prekini** zaustavlja.

**T17 · Prikazi** (meni „prikaz“)

| Prikaz | Šta treba da vidiš |
|---|---|
| Parametarski | dodaj „putanja (ℓ*(w), B*(w))“: tačke na pravoj B(ℓ), strelica smjera |
| Polarni | „+ funkcija“ → polarna → `1 + cos(th)`: kardioida |
| Vektorsko polje | ugrađena „max_δ E_Liu nad (ℓ, κ)“: žuta linija kod ℓ ≈ 0.1668, strelice |
| Kompleksni | „+ funkcija“ → kompleksna → `zeta(s)`: fazni portret, nule kao kružići na pravoj 1/2 (oko 2 s računa) |
| Presjek | isto `zeta(s)`: \|ζ\|, Re, Im i Hardy Z, nule u 14.13, 21.02, 25.01… |
| Povezani | klizač Δ desno: kad σ* pređe 1, piše „oblast bez nula je nestala“ |
| 3D | `zeta(s)` kao površ obojena po arg; rotacija mišem i strelicama |
| Male slike | površ max_δ E, „5. dim.“ = b: 6 slika, granica se blago pomjera |
| Paralelne koordinate | 8 metoda (Liu, XS, t ×3, w ×3), za ~10–40 s |

Klik na kompleksnu tačku → „broj nula u vidljivom pravougaoniku“. Očekuješ tačan broj nula u kadru.

**T18 · Izvoz**

PNG, SVG i CSV iz Grafova; snimi u neki folder i otvori.

---

## F · Lab, Graf znanja, adversarijalni mod, radni tekst

**T19 · Lab je interaktivan**

Pokreni „Hardy Z(t)“ (brz).

Očekuješ:
- graf na tamnoj pozadini, sa crvenim tačkama u nulama;
- kretanje radi isto kao u Grafovima;
- **„Sačuvaj PNG“** snima pogled kakav vidiš;
- run se pojavi u „Prethodna pokretanja“.

**T20 · Graf znanja**

Tab „Graf“ → „Mreža“.

Očekuješ: dvije povezane cjeline gore (misija 2 sa Langlands izvorima; QRH tema sa metodama), usamljene teme u redovima dolje. Klik na karticu je otvara, a „nađi čvor…“ centrira.

**T21 · Adversarijalni mod**

Misije → „Adversarijalni mod…“ → liu. Za oko 5–15 s stiže stavka u „Čeka tvoju odluku“:

> „liu — tvrdnja odolijeva; 38 boljih tačaka traži kršenje uslova; certifikat kompletan do B = 0.874956…“

Odobri, i u misiji 1 se pojavi korak. U Grafovima (B(ℓ), zumiraj oko ℓ = 0.167) vide se zeleni romb i crveni krstići.

**T22 · Radni tekst**

Misije → „Radni tekst (misije 2 i 3)…“.

Očekuješ:
- za oko 10–60 s otvori se tekst sa tabelom misije 3 i citatima `[lab:…]` uz svaki broj;
- piše NAŠE-NERECENZIRANO i „kompleksna verzija ne daje novo B“;
- u redu odluka je stavka „pročitaj“.

---

## G · AI (samo ako imaš ključ ili lokalni model)

**T23 · Lokalni DeepSeek**

Chat → mod „Model“, pitanje npr. „Šta je kritična prava?“.

Očekuješ:
- prvi odgovor za ~20–60 s (učitavanje 6 GB), dalje ~0.5 s po tokenu;
- „Prekini“ radi;
- u traci RAM pada dok model radi.

Za vrijeme poziva lokalni model ne smije izaći na mrežu (P8). Ako vidiš upozorenje o tome, to je nalaz.

**T24 · Cloud ključ i izbor modela**

Popravljeno u rc2: spisak modela se sam učita sa servera čim upišeš ključ (ne više samo jedan model), a „Testiraj“ provjerava **izabrani** model i pamti ga. Ako je model povučen (Groq je u rc1 vratio 404), sam izabere najbliži koji postoji. Gemini više ne ide u karantin pri pokretanju; ako bilo koji host ode u karantin, u „Čeka tvoju odluku“ dolazi stavka (Odobri = oslobodi).

Podešavanje → glavni AI → npr. Claude → upiši ključ → „Testiraj“, pa jedno kratko pitanje u chatu.

Očekuješ:
- poziv prođe;
- u traci se pojavi trošak;
- **Ctrl+K** (prekidač za online AI) odmah prekida i pilula postane crvena.

Ključ ne kucaj nigdje osim u polje za ključ u Podešavanju.

---

## H · Čuvar i zatvaranje

**T25 · Čuvar**

Tab Guardian: SSH čuvar radi, θ, prava („nema“ je normalno bez sudoers pravila; vodič SUDOERS-SR.md je u `/usr/share/doc/pse-riemann/`).

Ikona čuvara u traci sistema ima meni: Otvori · Stanje θ · Prekini online AI · Ugasi čuvara.

**T26 · Zatvaranje**

Zatvori glavni prozor.

Očekuješ:
- pitanje „Ugasi sve / Zatvori prozor, čuvar ostaje / Odustani“;
- bez rušenja i bez poruke „QThread destroyed“ u terminalu.

---

## I · Ako nešto pukne

- Pokreni iz terminala (`pse-riemann`) da vidiš grešku i snimi je.
- Dnevnik je u `~/Desktop/PSE Riemann rezultati/vault/.state/journal.db`. Ne brisati; ja ga čitam ako mi ga pošalješ.
- Uklanjanje paketa: `sudo apt remove pse-riemann`. Folder `PSE Riemann rezultati` ostaje.

---

## Zapisnik (popuni i pošalji)

| Test | ✓ / ✗ / ~ | Napomena (i ime snimka) |
|---|---|---|
| T1 instalacija | | |
| T2 verzija + pomoćni program | | |
| T3 selftest iz paketa | | |
| T4 pokretanje | | |
| T5 prvo podešavanje | | |
| T6 gornja traka | | |
| T7 veličina teksta/prozora | | |
| T8 ⤢ / ⤡ | | |
| T9 SR / EN | | |
| T10 misije u krug | | |
| T11 cilj misije | | |
| T12 ideje | | |
| T13 red odluka | | |
| T14 kretanje u Grafovima | | |
| T15 sve o tački | | |
| T16 skup račun + Prekini | | |
| T17 prikazi (koji ne radi?) | | |
| T18 izvoz | | |
| T19 Lab interaktivan + PNG | | |
| T20 graf znanja | | |
| T21 adversarijalni mod | | |
| T22 radni tekst | | |
| T23 lokalni DeepSeek | | |
| T24 cloud ključ | | |
| T25 čuvar | | |
| T26 zatvaranje | | |

**Šta mi pošalješ:** popunjen zapisnik (ili samo ✗ i ~ redove) i snimke iz `~/Pictures/PSE-Riemann/`. Ja onda popravljam redom, pa idu CI (36), verzija 0.2.0 (37), paketi (38), kompletni vodiči i spajanje u `main` na tvoje „spoji u main“.
