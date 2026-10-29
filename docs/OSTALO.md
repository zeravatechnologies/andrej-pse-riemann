# PSE Riemann — šta je ostalo (stanje 2026-10-26, uveče)

Grana `feature/runda3` na GitHubu (`andrejristic/pse-riemann`). Testovi: 281/281, selftest prolazi. **U `main` se ništa ne spaja dok Andrej ne kaže „spoji u main“.**

## Šta je spremno za jutro

- Paket **B — `pse-riemann_0.2.0~rc2_amd64.deb`** (puni: sve, uključujući lokalni DeepSeek preko llama-cpp) leži na Desktopu i u `app/build/`.
- **rc1** znači „kandidat za izdanje“. Tilda (~) u verziji znači da je ovo *prije* 0.2.0, pa se konačni 0.2.0 kasnije instalira normalno preko njega.
- Ovaj fajl je na dva mjesta: na Desktopu (`PSE Riemann — OSTALO.docx`) i u repou (`docs/OSTALO.md` + docx u korijenu repoa, na GitHubu).

## Zašto 3 paketa i koji je koji

| Paket | Šta je | Kome |
|---|---|---|
| **B `pse-riemann`** (puni) | sve: GUI, numerika, sympy, scipy, llama-cpp (lokalni GGUF) | **ovaj se testira; ovo je glavni paket** |
| A `pse-riemann-lean` (lagani) | bez scipy, manji; isti program | mašina sa malo mjesta ili bez lokalnog modela |
| C `pse-riemann-research` (dodatak) | samo scipy; ide UZ A (A + C ≈ B) | ko je uzeo A, pa mu zatreba istraživački dio |

**.exe** (Windows) odgovara paketu **B**. Postoji samo jedan.

## Jutro: živi test (radi Andrej) — stavka 35

1. Instalacija (traži lozinku, jer je sistemska):
   `sudo apt install ~/Desktop/pse-riemann_0.2.0~rc2_amd64.deb`
2. Pokreni iz menija „PSE Riemann“ ili komandom `pse-riemann`.
3. Pri prvom otvaranju upiši ime operatera. Ako se otvori podešavanje, izaberi glavni AI:
   - bez ključa: lokalni DeepSeek GGUF, ako je u `models/`; inače „bez AI“;
   - skeptik je drugi model ili „bez“.
4. Prođi tabove i javi šta ne valja (snimak ekrana: **F12**, slike idu u `~/Pictures/PSE-Riemann/`):
   - **Pregled**, **Misije**: tri misije, „Sljedeća misija ⟳“, „Ostavi za kasnije…“;
   - **Ideje**: značka;
   - **Grafovi**: tri panela, ⤢ na svakom, prikazi u meniju „prikaz“, klik na krivu = sve o tački;
   - **Lab**: pokreni „Hardy Z(t)“ i „QRH: adversarijalni mod“;
   - **Graf**: Mreža;
   - **Misije** → „Radni tekst (misije 2 i 3)…“.
5. Selftest iz paketa: `pse-riemann --selftest` (očekivano „SVE PROLAZI“; nalazi pod „Host“ su stanje računara, ne aplikacije).
6. Ako imaš API ključ (Claude ili drugi): unesi ga u Podešavanju i probaj chat. To je jedini dio koji nikad nije proban uživo.
7. Javi mi: šta radi, šta ne, i snimke.

## Ostatak posla, redom

1. ~~35 · Vodič za živi test~~ — **gotovo**: `PSE Riemann — VODIC ZIVI TEST.docx` (Desktop i repo). Radi test po njemu.
2. **36 · CI** (GitHub, na svaki tag):
   - čist Ubuntu i Windows;
   - instalira .deb, odnosno .exe, iz nule;
   - pokreće selftest i jedan pravi mali poziv kroz aplikaciju;
   - ako sve prođe, kači pakete kao GitHub Release.

   Tako znamo da paket radi i van ovog računara.
3. **Popravke iz tvog živog testa** (koliko ih bude).
4. **37 · Verzija 0.2.0** i tag `v0.2.0` (tag pokreće CI → .deb + .exe u Release).
5. **38 · Izdanje:**
   - sva tri .deb + .exe;
   - testovi i snimci iz instaliranog paketa;
   - odluka o sedmičnom podsjetniku.
6. **34 · Kompletni SR/EN vodiči za cijelu aplikaciju:** pišu se **posle izgradnje paketa** (Andrej), da opisuju tačno ono što je u njima. Zatim se paketi grade još jednom sa vodičima unutra.
7. **Na kraju:**
   - (1) konačni paketi na Desktopu;
   - (2) **spajanje u `main`** samo na „spoji u main“.

Procjena preostalog: oko 10–25 h, najviše zavisi od nalaza živog testa.

## Iskreno, prije testa

- Cloud provajderi (Claude, OpenAI…) **nikad nisu probani uživo**, jer na računaru nema ključa.
- Benchmark korpus je sintetički i na njemu su detektori podešavani.
- Acer profil je procjena, nije mjeren.
- Adversarijalni mod i certifikat praznine rade samo za Liu i Xu–Sang geometriju. Metode zadate kao podatak se pošteno odbijaju.
- Kompleksna verzija (misija 3) **ne daje novo B**. Daje karakterizaciju granice i mjeru margine, i to je zapisano.
