# Langlands i druga misija: istraživanje sa izvorima (runda 3, stavka 25)

Datum: 2026-10-25. Status: **istraživačka bilješka, ništa nije recenzirano od nas.**

Oznake:
- **[RAD]**: piše u navedenom radu (pročitan apstrakt ili, gdje piše, tekst);
- **[STANJE]**: status rada (recenziran ili preprint);
- **[NAŠE]**: moje čitanje, nerecenzirano;
- **[DJELIMIČNO]**: nepotpuno, ne oslanjati se.

Pitanje druge misije (plan, stavka 27): *prenosi li se metoda 7/8, Liu ili Xu–Sang na L-funkcije višeg stepena (GL(2), Artin)? Ako da, kako se eksponent E mijenja sa stepenom d, i postoji li transformacija T_d između porodica?*

---

## 1. Šta je „proboj od prije dvije godine“: geometrijski Langlands

- **[RAD]** Gaitsgory, Raskin i saradnici: serija od pet radova, ukupno više od 800 strana. Dokazuju (nerazgranatu) geometrijsku Langlandsovu hipotezu u de Rhamovom i Bettijevom okruženju, u karakteristici 0.
  - I: arXiv:2405.03599 (maj 2024, revizije 2024 i 2025);
  - II: arXiv:2405.03648;
  - IV: arXiv:2409.08670;
  - V: arXiv:2409.09856, „multiplicity one“.
- **[STANJE]** Serija je preprint. U pretrazi nisam našao potvrdu da je objavljena u recenziranom časopisu.
- **[NAŠE]** Geometrijski Langlands govori o snopovima na krivama nad ℂ, a ne o brojevnim poljima. **Ne daje** nijedan eksponent, nultu oblast ni ocjenu gustine nula za L-funkcije nad ℚ. Za prvu i drugu misiju je to **kontekst, a ne alat**. U aplikaciju ulazi kao kartica izvora i, najviše, kao INSPIRACIJA (stavka 28).

## 2. Šta dokaz 7/8 stvarno koristi, iz lokalne kopije rada

- **[RAD]** OpenAI, „The Quasi-Riemann Hypothesis“ (30. 9. 2026; sa Lean dijelom za ζ; nerecenzirano). Prema samom tekstu (`papers-local/oai5`, `oai30`):
  - Möbiusove sume i sekstične karaktere;
  - Poissonovu sumaciju, posle koje sekstične Gaussove sume prelaze u **kubne Gaussove sume**;
  - **Kubotinu kubnu theta funkciju** (metaplektička, nad ℚ(√−3)) i **Pattersonove koeficijente**;
  - **kvadratni large sieve** nad brojevnim poljima (Goldmakher–Louvel, Heath-Brown).
- **[NAŠE]** To su alati **GL(1)**: Dirihleovih i Heckeovih karaktera i njihovih Gaussovih suma. Ključni trik (Gaussove sume kao koeficijenti kubne thete) koristi strukturu **karaktera**. Za GL(2) forme ne postoji poznat analog „Gaussove sume = koeficijent thete“. Zato prenos **nije direktan**.
- **[NAŠE]** Liu i Xu–Sang su optimizacije **istog** sistema eksponenata (naš REPORT za qrh-2026-10, B(ℓ) = 11/12 − ℓ/4). Za njih važi isto.

## 3. Šta postoji za viši stepen (alati koji bi trebali prenosu)

| Rad | Šta daje | Status | Veza sa misijom 2 |
|---|---|---|---|
| Newton–Thorne I, *Symmetric power functoriality for holomorphic modular forms* (Publ. IHÉS 134, 2021; arXiv:1912.11261) | automorfnost Sym^n f za svako n, nivo 1 | **recenzirano** | daje analitičko produženje L(Sym^n f, s): preduslov da se uopšte postavi pitanje nulte oblasti za te porodice |
| Newton–Thorne II (arXiv:2009.07180) | isto, za svaku formu bez CM | preprint u našim izvorima (objava nije provjerena) | isto |
| Harcos–Thorner (arXiv:2303.16889) | nova nulta oblast za GL(1)-uvijanja Rankin–Selberg L-funkcija | preprint | najbliže „nultoj oblasti za viši stepen“, ali tipa de la Vallée Poussin (blizu Re s = 1), ne poluravan |
| *Large sieves for GL_n and applications* (arXiv:2508.14888) | large sieve za koeficijente automorfnih L-funkcija u porodicama, procjene gustine nula | preprint | **kandidat za zamjenu kvadratnog large sieve-a** iz 7/8 dokaza |
| Creech i dr. (arXiv:2509.20873) | eksplicitna nulta oblast za GL(2) newform | preprint | klasični tip, korisno kao kontrola |
| Alpöge–Furman (arXiv:2608.13637), Claude kao pisac argumenta, Lean | > 2/3 nula ζ prostih i na kritičnoj pravoj | preprint | **drugi tip rezultata** (udio na pravoj, ne poluravan): ne smije se porediti niti crtati sa 7/8 kao ista vrsta (plan, stavka 27, „vrsta rezultata“) |

## 4. Mapa prenosivosti (prvi nacrt, [NAŠE] [DJELIMIČNO])

| Korak dokaza 7/8 | Za GL(2) / Artin | Ocjena |
|---|---|---|
| Möbiusove sume nad karakterima | postoji analog (koeficijenti 1/L) | vjerovatno se prenosi |
| Gaussove sume prelaze u kubnu thetu (Kubota/Patterson) | nema poznatog analoga | **glavna prepreka** |
| kvadratni large sieve | GL_n large sieve postoji (2508.14888), ali sa drugačijim gubicima | prenosi se uz gubitak; utiče na eksponent |
| funkcionalna jednačina i analitičko produženje | Sym^n: Newton–Thorne; Artin: uglavnom pretpostavka | uslovno („pod funkcionalnošću“) |

**Zaključak [NAŠE]:** pitanje misije 2 je danas **otvoreno pitanje, a ne račun**. Nije poznato da li se 7/8 prenosi. Ako se prenosi, najvjerovatnija tačka gubitka je zamjena kubne thete i large sieve-a. Eksponent bi tada zavisio od gubitaka u GL_n large sieve-u, a ne samo od stepena d. Zato T_d, ako postoji, nije poznat zatvoren izraz.

## 5. Prijedlozi cilja druge misije (stavka 26, odlučuje Andrej)

1. **Mapa prenosivosti** (preporuka): za svaki korak 7/8, Liu i Xu–Sang odlučiti „prenosi se“, „prenosi se uz gubitak“ ili „ne prenosi se“, sa izvorom. Rezultat je tabela iz §4, ali sa provjerom korak po korak.
   - ✓ Bolje kada želimo realan i provjerljiv rezultat.
   - ✗ Slabije kada želimo broj.
2. **E_d i T_d uslovno:** pod pretpostavkom GL_n large sieve-a sa poznatim gubitkom, računati koliko se eksponent pogoršava sa d, kao sistem eksponenata u aplikaciji (kao podatak), sa oznakom „pod pretpostavkom“.
   - ✓ Bolje kada želimo grafove i brojeve u misiji.
   - ✗ Slabije kada je pretpostavka pogrešna, jer su tada svi brojevi uslovni.
3. **Samo praćenje:** kartice i inspiracije, bez računa, dok neki rad ne objavi prenos.
   - ✓ Bolje kada želimo najmanje rada.
   - ✗ Slabije kada želimo da aplikacija išta otkriva.

## Izvori

- [Gaitsgory–Raskin, GLC I, arXiv:2405.03599](https://arxiv.org/abs/2405.03599)
- [GLC II, arXiv:2405.03648](https://arxiv.org/abs/2405.03648)
- [GLC IV, arXiv:2409.08670](https://arxiv.org/abs/2409.08670)
- [GLC V, arXiv:2409.09856](https://arxiv.org/abs/2409.09856)
- [IHES o dokazu](https://www.ihes.fr/en/tag/non-scientific-ihes/page/3)
- [Newton–Thorne I, arXiv:1912.11261](https://arxiv.org/abs/1912.11261), [Publ. IHÉS](https://pmihes.centre-mersenne.org/articles/10.1007/s10240-021-00127-3/)
- [Newton–Thorne II, arXiv:2009.07180](https://arxiv.org/abs/2009.07180)
- [Harcos–Thorner, arXiv:2303.16889](https://arxiv.org/abs/2303.16889)
- [Large sieves for GL_n, arXiv:2508.14888](https://arxiv.org/abs/2508.14888)
- [Creech i dr., arXiv:2509.20873](https://arxiv.org/abs/2509.20873)
- [Alpöge–Furman, arXiv:2608.13637](https://arxiv.org/abs/2608.13637)
- OpenAI QRH 7/8: lokalna kopija u `research/qrh-2026-10/papers-local/` (licenca, nije na gitu); [Wikipedia o objavi](https://en.wikipedia.org/wiki/OpenAI_bulk_release_of_mathematical_papers)
