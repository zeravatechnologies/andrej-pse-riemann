# PSE Riemann 0.3.0~rc7 — instalacija i živi test (za Andreja)

Ovaj vodič je samo za tebe i ne ulazi u paket. Prati ga redom: svaki korak ima „šta treba da vidiš“, a rezultat upiši u tabelu na kraju (ili mi ga samo izdiktiraj).

## 0. Šta je novo u rc2 (posle tvog prvog živog testa)

- **Gemini 2.5 više ne odsijeca odgovore.** Razmišljanje dobija svoj budžet iznad limita odgovora (pravilo 48 a).
- **Odsječen odgovor** (bilo koji provajder) dobija jedan ponovni pokušaj sa dvostrukim limitom. Ako je i drugi odsječen, aplikacija to kaže (48 b).
- **Glas SHARED_LIB-a:**
  - neispravan SQL dobija još jedan pokušaj sa greškom, a onda običnu rečenicu, nikad sirovo „QueryRefused“ (48 c);
  - imena misija su linkovi;
  - na pitanje koje traži sud daje link „Razgovaraj o misiji: X“ (47).
- **Čitač** ima limit 200 + budžet razmišljanja. Odsječen JSON se u Laboratoriji vidi kao „čitač odsječen“, a ne tiho kao „bez čitača“ (48 d).
- **Tab Misije je radni prostor** (42): kartice lijevo, detalji, „Gdje si stao“ i pamćenje gore desno, razgovor dolje desno.
- **Klik na misiju odmah pokreće agenta** (43). Agent čita prošli izbor radova i nove radove (🆕), a „Zadaj da čita…“ mu daje još štiva (44).
- **Pamćenje misije** (45–46): agent ga predlaže na kraju sesije, a ti ga pregledaš i sačuvaš. Stari razgovor više ne čita.

## 1. Instalacija tvog paketa

Paket je `~/Desktop/PSE Riemann/pse-riemann-andrej_0.3.0~rc7_amd64.deb`. Zamjenjuje rc1, a tvoji rezultati u „PSE Riemann rezultati“ ostaju.

```bash
sudo apt install "$HOME/Desktop/PSE Riemann/pse-riemann-andrej_0.3.0~rc7_amd64.deb"
```

```bash
pse-riemann --selftest
```

**Treba da vidiš:**
- na kraju **✅ SVE PROLAZI**;
- „Izdanje: andrej“;
- „PSE: svaki agent je jedinica …“.

## 2. Živi test, korak po korak

Glavni AI neka bude **Gemini 2.5 Flash** (tu je bio problem), a skeptik/čitač OpenRouter ili GGUF, kao u rc1.

| # | Uradi | Treba da vidiš |
|---|---|---|
| 1 | Chat, mod SHARED_LIB: „koje misije imam?“ | rečenice; imena misija su **linkovi**; klik otvara tab Misije na toj misiji |
| 2 | Chat, mod SHARED_LIB: slobodno pitanje (npr. „koliko kartica ima izvor sa arXiv-a?“) | odgovor rečenicama, **ne** „QueryRefused“; ako ne uspije, obična rečenica, a detalj je pod „▸ prikaži odakle“ |
| 3 | Chat, mod SHARED_LIB: „Koji je najlakši sljedeći korak za misiju 1?“ | „baza na to ne odgovara“ + link **„Razgovaraj o misiji: …“** |
| 4 | Chat, mod math: dugo pitanje | odgovor **do kraja**, nije odsječen usred riječi; ako ipak jeste: „[odgovor odsječen: …]“ |
| 5 | Laboratorija → izaberi jedinicu chat | red **„Čitač (zadnji potez)“**: zapiši koliko je **odsječen** od zadnjih 30 |
| 6 | Misije → **klik na misiju 1** | agent sam napiše prvu poruku (šta vidi, gdje ste stali, ≤ 3 pitanja); prvi put čita sve radove |
| 7 | Traka „N od M radova izabrano ▾“ → odštikliraj par radova, sklopi traku | u razgovoru „Izbor radova: …“; agent čita novi izbor |
| 8 | „Zadaj da čita…“ → Puni tekst arXiv rada | „Zadato…“/„Učitan puni tekst…“ u razgovoru |
| 9 | Razgovaraj 2–3 poteza, pa **Završi razgovor** | za par sekundi gore desno **Pamćenje misije · nepregledano** sa stavkama |
| 10 | Odštikliraj jednu stavku, dvoklikom ispravi drugu, **Sačuvaj pamćenje** | „pregledano“; stavke kako si ih ostavio |
| 11 | Ponovo klik na misiju 1 | agent kreće od pamćenja („prošli put smo…“), ne od starog razgovora; radovi = prošli izbor + 🆕 novi |
| 12 | Razgovaraj o misiji 2, pa klik na misiju 3 (bez „Završi“) | misija 2 dobija pamćenje „nepregledano“ (prelazak na drugu misiju) |
| 13 | Povuci granicu između gornjeg i donjeg dijela | oba dijela se mijenjaju; unos razgovora uvijek vidljiv |
| 14 | Zatvori aplikaciju usred razgovora | statusna linija „Agent misije predlaže pamćenje…“, pa se zatvori (najviše ~30 s) |
| 15 | Na Aceru (1366 piksela) | radni prostor stane; ništa bitno van ekrana |
| 16 | Radi normalno **1 sat** | **zapiši koliko je Doktorovih mjera stiglo** |

## 3. Kalibracija (ostala iz rc1)

θ se i dalje mjeri **doslovno po potezu** (pravilo 40). Zapiši:

- **Doktorovih mjera za 1 sat rada:** ___ (koje jedinice, koji okidači — Laboratorija → Dnevnik Doktora)
- **Trajanje jednog AI poteza sa čitačem:** cloud ___ s, GGUF ___ s
- **Čitač odsječen** (korak 5): ___ od 30
- Da li su mjere imale smisla? ___

## 4. Javni paket (opciono)

`pse-riemann_0.3.0~rc7_amd64.deb` je za druge ljude: prazne misije, prazan vault i „+ Nova misija“. Ne instaliraj ga preko svog; probaj ga na drugom računaru ili u virtuelnoj mašini.

## 5. Rezultati

| # | prošlo? | napomena |
|---|---|---|
| 1–16 | | |
| kalibracija | | |

Kad završiš, javi mi rezultate. Prije toga (ili tada) reci „pushuj“ da pošaljem lokalne commitove, a „spoji u main“ tek kad je sve u redu (`docs/ZA-ANDREJA.md`).
