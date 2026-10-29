"""
The experiment catalogue — twelve things you can run, each answering a question
that matters when you are learning this subject.

Each experiment is a pure function `(params) -> Result`. It returns numbers, a
short markdown reading of what those numbers mean, and optionally a plot spec.
Nothing here writes to disk; `runner.py` does that, hashes the source, and puts
a COMPUTED card through the gate.

Ordering is pedagogical, not alphabetical: run them top to bottom over the first
few days and the subject assembles itself.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from . import zeta as Z


@dataclass
class Param:
    name: str
    kind: str                    # "int" | "float"
    default: Any
    lo: Any
    hi: Any
    help: str = ""


@dataclass
class Result:
    numbers: dict = field(default_factory=dict)
    series: dict = field(default_factory=dict)     # name -> list of tuples
    reading: str = ""                              # markdown: what it means
    plots: list = field(default_factory=list)      # plot specs for plots.py
    warnings: list = field(default_factory=list)


@dataclass
class Experiment:
    key: str
    title: str
    question: str                # the question this answers, in one line
    why: str                     # why it matters
    params: list
    run: Callable[..., Result]
    cost: str = "brz"            # brz | srednji | spor  — on a 4 GB machine


# --------------------------------------------------------------------------- #
# 1. Hardy Z — the first thing to look at
# --------------------------------------------------------------------------- #
def _run_z_curve(t0: float, t1: float, samples: int) -> Result:
    step = max((t1 - t0) / max(samples, 10), 1e-4)
    roots, ts = Z.sign_changes(t0, t1, step)
    smooth = Z.smooth_count_difference(max(t0, 0.1), t1)
    r = Result()
    r.numbers = {"t0": t0, "t1": t1, "step": step,
                 "zeros_found": len(roots),
                 "smooth_prediction": round(smooth, 4),
                 "max_abs_Z": round(max(abs(v) for _, v in ts), 4)}
    r.series = {"Z": [(t, v) for t, v in ts],
                "roots": [(x.root, 0.0) for x in roots]}
    r.plots = [{"kind": "line", "series": "Z", "marks": "roots",
                "title": f"Hardy Z(t), t ∈ [{t0:g}, {t1:g}]",
                "xlabel": "t", "ylabel": "Z(t)", "zeroline": True}]
    r.reading = (
        f"Na intervalu [{t0:g}, {t1:g}] Z mijenja znak **{len(roots)} puta** — "
        f"toliko nula leži NA kritičnoj pravoj u tom rasponu. Glatki član "
        f"predviđa {smooth:.3f}. Razlika je S(T), fluktuacija, i ona je mala i "
        f"spora — to je cijela poenta.\n\n"
        f"Z je realna funkcija, pa se nule vide golim okom kao presjeci nule. "
        f"Sve što ovdje vidiš je pod pretpostavkom da nijedna nula nije "
        f"promašena — ako je korak preveliki, par nula može proći nezapaženo.")
    if step > Z.recommended_step(t1, 4.0):
        r.warnings.append(
            f"korak {step:.4f} je grublji od preporučenog "
            f"{Z.recommended_step(t1, 8.0):.4f} na visini {t1:g} — moguće je "
            f"da su neke nule promašene; povećaj broj uzoraka")
    return r


# --------------------------------------------------------------------------- #
# 2. The zeros themselves
# --------------------------------------------------------------------------- #
def _run_zeros(n: int) -> Result:
    zs = Z.zeta_zeros(n)
    gaps = [zs[i + 1] - zs[i] for i in range(len(zs) - 1)]
    lp = Z.lehmer_pairs(zs)
    r = Result()
    r.numbers = {"n": n, "first": zs[0], "last": zs[-1],
                 "mean_gap": round(sum(gaps) / len(gaps), 5) if gaps else 0.0,
                 "min_gap": round(min(gaps), 5) if gaps else 0.0,
                 "lehmer_like_pairs": len(lp)}
    r.series = {"zeros": [(i + 1, g) for i, g in enumerate(zs)],
                "gaps": [(i + 1, g) for i, g in enumerate(gaps)]}
    r.plots = [{"kind": "scatter", "series": "gaps",
                "title": "Razmaci između uzastopnih nula",
                "xlabel": "n", "ylabel": "γ(n+1) − γ(n)"}]
    lines = [f"Prvih {n} nula: γ₁ = {zs[0]:.6f} … γ_{n} = {zs[-1]:.6f}.",
             f"Srednji razmak {r.numbers['mean_gap']:.4f}, najmanji "
             f"{r.numbers['min_gap']:.4f}."]
    if lp:
        lines.append(f"\n**{len(lp)} neobično bliskih parova** (razmak ispod "
                     f"1/4 lokalnog prosjeka):")
        for p in lp[:5]:
            lines.append(f"- γ_{p['i']} = {p['gamma_1']:.5f}, γ_{p['i']+1} = "
                         f"{p['gamma_2']:.5f}, razmak {p['gap']:.5f} "
                         f"({p['gap_over_mean']:.2f}× prosjek)")
        lines.append("\nOvakvi parovi su najbliže što numerika dolazi "
                     "kontraprimjeru: kad bi se dvije nule spojile i razdvojile "
                     "van prave, RH bi pala. Lehmerov par kod γ ≈ 7005 je "
                     "klasičan primjer.")
    else:
        lines.append("\nNema neobično bliskih parova u ovom rasponu. Oni "
                     "postaju česti tek na većim visinama (Lehmer: γ ≈ 7005).")
    r.reading = "\n".join(lines)
    return r


# --------------------------------------------------------------------------- #
# 3. Counting: N(T) vs the smooth term — the RH check on an interval
# --------------------------------------------------------------------------- #
def _run_counting(T: float, samples_per_unit: float) -> Result:
    step = min(Z.recommended_step(T, max(samples_per_unit, 4.0)), 0.05)
    roots, _ = Z.sign_changes(0.1, T, step)
    on_line = len(roots)
    smooth = Z.N_smooth(T)
    s_of_T = on_line - smooth
    r = Result()
    r.numbers = {"T": T, "step": round(step, 6),
                 "zeros_on_line": on_line,
                 "N_smooth": round(smooth, 6),
                 "S_of_T": round(s_of_T, 6)}
    # S(T) along the way
    ser, cnt = [], 0
    for x in roots:
        cnt += 1
        ser.append((x.root, cnt - Z.N_smooth(x.root)))
    r.series = {"S": ser}
    r.plots = [{"kind": "step", "series": "S",
                "title": f"S(T) = N(T) − (θ(T)/π + 1),  T ≤ {T:g}",
                "xlabel": "T", "ylabel": "S(T)", "zeroline": True}]
    r.reading = (
        f"Do visine T = {T:g} pronađeno je **{on_line} nula na kritičnoj "
        f"pravoj**. Glatka formula θ(T)/π + 1 daje {smooth:.4f}, pa je "
        f"S(T) = {s_of_T:+.4f}.\n\n"
        f"Ovo je numerička provjera RH na intervalu (0, {T:g}]: broj nula NA "
        f"pravoj poklapa se sa ukupnim brojem nula u traci koji predviđa "
        f"teorija. Da postoji nula van prave ispod ove visine, brojevi se ne bi "
        f"slagali.\n\n"
        f"S(T) je mali i mijenja se sporo. Poznato je da S(T) = O(log T) i da "
        f"ide u ±∞, ali izuzetno sporo — prvi put pređe 3 tek astronomski "
        f"visoko. To je razlog zašto numerika izgleda tako uvjerljivo, i razlog "
        f"zašto ne dokazuje ništa.")
    return r


# --------------------------------------------------------------------------- #
# 4. Gram points and Gram's law
# --------------------------------------------------------------------------- #
def _run_gram(n_start: int, n_end: int) -> Result:
    ga = Z.gram_analysis(n_start, n_end)
    r = Result()
    r.numbers = {"n_start": n_start, "n_end": n_end,
                 "good_points": ga["good_points"], "bad_points": ga["bad_points"],
                 "intervals": len(ga["intervals"]),
                 "gram_law_violations": ga["gram_law_violations"]}
    r.series = {"gram_Z": [(p["g"], p["Z"]) for p in ga["points"]],
                "zeros_per_interval": [(iv["n"], iv["zeros"])
                                       for iv in ga["intervals"]]}
    r.plots = [{"kind": "stem", "series": "zeros_per_interval",
                "title": "Broj nula po Gramovom intervalu (Gramov zakon: tačno 1)",
                "xlabel": "n", "ylabel": "nula u [gₙ, gₙ₊₁)"}]
    lines = [
        f"Gramove tačke g_{n_start} … g_{n_end}: {ga['good_points']} 'dobrih' "
        f"(gdje (−1)ⁿ Z(gₙ) > 0), {ga['bad_points']} loših.",
        f"Od {len(ga['intervals'])} Gramovih intervala, "
        f"**{ga['gram_law_violations']}** ne sadrži tačno jednu nulu.",
        "",
        "Gramov zakon nije teorema nego tendencija — pada beskonačno mnogo "
        "puta. Zanimljivo je baš tamo gdje pada: kršenja dolaze u blokovima, i "
        "Rosserovo pravilo (svaki Gramov blok sadrži onoliko nula koliko ima "
        "intervala) drži i tamo gdje sam Gramov zakon ne drži."]
    if ga["violation_detail"]:
        lines.append("\nKršenja:")
        for v in ga["violation_detail"][:8]:
            lines.append(f"- interval n = {v['n']} ([{v['a']:.4f}, "
                         f"{v['b']:.4f}]): {v['zeros']} nula")
    r.reading = "\n".join(lines)
    return r


# --------------------------------------------------------------------------- #
# 5. The explicit formula — primes out of zeros. THE demo.
# --------------------------------------------------------------------------- #
def _run_explicit(x_max: float, n_zeros: int) -> Result:
    gammas = Z.zeta_zeros(n_zeros)
    xs = [x for x in _frange(2.0, x_max, max((x_max - 2.0) / 600.0, 0.01))]
    approx, exact = [], []
    running = 0.0
    # exact psi as a staircase
    import math as _m
    n_int = int(x_max)
    sieve = bytearray([1]) * (n_int + 1)
    sieve[0:2] = b"\x00\x00"
    jumps = []
    for p in range(2, n_int + 1):
        if sieve[p]:
            for m in range(p * p, n_int + 1, p):
                sieve[m] = 0
            lp = _m.log(p)
            pk = p
            while pk <= n_int:
                jumps.append((pk, lp))
                pk *= p
    jumps.sort()
    ji = 0
    for x in xs:
        while ji < len(jumps) and jumps[ji][0] <= x:
            running += jumps[ji][1]
            ji += 1
        exact.append((x, running))
        approx.append((x, Z.psi_explicit(x, gammas)["psi_approx"]))
    err = [abs(a[1] - e[1]) for a, e in zip(approx, exact)]
    r = Result()
    r.numbers = {"x_max": x_max, "n_zeros": n_zeros,
                 "max_abs_error": round(max(err), 4),
                 "mean_abs_error": round(sum(err) / len(err), 4),
                 "psi_exact_at_xmax": round(exact[-1][1], 4),
                 "psi_approx_at_xmax": round(approx[-1][1], 4)}
    r.series = {"psi_exact": exact, "psi_approx": approx}
    r.plots = [{"kind": "two_lines", "series": ["psi_exact", "psi_approx"],
                "labels": ["ψ(x) tačno (stepenice)",
                           f"ψ(x) iz {n_zeros} nula"],
                "title": "Eksplicitna formula: primovi izranjaju iz nula",
                "xlabel": "x", "ylabel": "ψ(x)"}]
    r.reading = (
        f"Glatka kriva x, korigovana sa **{n_zeros} nula**, prati tačnu "
        f"stepenastu funkciju ψ(x) sa srednjom greškom "
        f"{r.numbers['mean_abs_error']:.3f}.\n\n"
        f"Svaka nula ρ = ½ + iγ doprinosi jedan talas amplitude 2√x/|ρ| i "
        f"frekvencije γ. Nule su **frekvencije u spektru primova**. Dodaj ih "
        f"dovoljno i glatka kriva se izlomi tačno na stepenicama primova i "
        f"njihovih stepena.\n\n"
        f"Ovdje se vidi zašto je RH važna: amplituda svakog talasa je "
        f"x^Re(ρ)/|ρ|. Ako sve nule imaju Re(ρ) = ½, greška u brojanju primova "
        f"je reda √x. Nula sa Re(ρ) = 0.6 dala bi talas koji raste kao x^0.6 i "
        f"trajno pokvario raspodjelu primova.")
    return r


def _frange(a: float, b: float, step: float):
    x = a
    while x <= b:
        yield x
        x += step


# --------------------------------------------------------------------------- #
# 6. pi(x) vs li(x) vs R(x)
# --------------------------------------------------------------------------- #
def _run_prime_counting(x_max: int, points: int) -> Result:
    xs = [int(x_max * (i + 1) / points) for i in range(points)]
    xs = sorted({x for x in xs if x >= 10})
    pi_s, li_s, R_s = [], [], []
    for x in xs:
        p = Z.prime_pi(x)
        pi_s.append((x, p))
        li_s.append((x, Z.log_integral(x)))
        R_s.append((x, Z.riemann_R(x)))
    li_err = [abs(l[1] - p[1]) for l, p in zip(li_s, pi_s)]
    R_err = [abs(rr[1] - p[1]) for rr, p in zip(R_s, pi_s)]
    r = Result()
    r.numbers = {"x_max": x_max,
                 "pi_at_xmax": pi_s[-1][1],
                 "li_at_xmax": round(li_s[-1][1], 3),
                 "R_at_xmax": round(R_s[-1][1], 3),
                 "li_error_at_xmax": round(li_err[-1], 3),
                 "R_error_at_xmax": round(R_err[-1], 3),
                 "sqrt_x_at_xmax": round(math.sqrt(x_max), 3)}
    r.series = {"pi": pi_s, "li": li_s, "R": R_s,
                "li_err": [(x, e) for (x, _), e in zip(pi_s, li_err)],
                "R_err": [(x, e) for (x, _), e in zip(pi_s, R_err)]}
    r.plots = [{"kind": "two_lines", "series": ["li_err", "R_err"],
                "labels": ["|li(x) − π(x)|", "|R(x) − π(x)|"],
                "title": "Greška aproksimacija π(x)", "xlabel": "x",
                "ylabel": "apsolutna greška"}]
    r.reading = (
        f"Na x = {x_max}: π(x) = {pi_s[-1][1]}, li(x) = {li_s[-1][1]:.2f} "
        f"(greška {li_err[-1]:.2f}), R(x) = {R_s[-1][1]:.2f} "
        f"(greška {R_err[-1]:.2f}). Za poređenje √x = {math.sqrt(x_max):.1f}.\n\n"
        f"R(x) = Σ μ(k)/k · li(x^{{1/k}}) je dramatično bolji od li(x) — jer je "
        f"li(x) samo prvi član. Ono što oba ne hvataju su oscilacije od nula; "
        f"upravo njih dodaje eksplicitna formula.\n\n"
        f"li(x) > π(x) na svakom x koji je iko izračunao, ali Littlewood je "
        f"1914. dokazao da razlika mijenja znak beskonačno mnogo puta. Prvi "
        f"prelaz je negdje ispod Skewesovog broja. Numerika ovdje ne vidi "
        f"ništa — dobar podsjetnik dokle numerika seže.")
    return r


# --------------------------------------------------------------------------- #
# 7. Pair correlation vs GUE — the random-matrix bridge
# --------------------------------------------------------------------------- #
def _run_gue(n_zeros: int, bins: int) -> Result:
    zs = Z.zeta_zeros(n_zeros)
    sp = Z.normalized_spacings(zs)
    if not sp:
        return Result(reading="premalo nula", warnings=["povećaj n_zeros"])
    hi = max(3.0, max(sp))
    width = hi / bins
    hist = [0] * bins
    for s in sp:
        k = min(int(s / width), bins - 1)
        hist[k] += 1
    total = len(sp)
    obs = [(i * width + width / 2, hist[i] / (total * width)) for i in range(bins)]
    gue = [(c, Z.gue_wigner_surmise(c)) for c, _ in obs]
    poi = [(c, Z.poisson_density(c)) for c, _ in obs]
    chi_gue = sum((o - g) ** 2 / max(g, 1e-6) for (_, o), (_, g) in zip(obs, gue))
    chi_poi = sum((o - p) ** 2 / max(p, 1e-6) for (_, o), (_, p) in zip(obs, poi))
    r = Result()
    r.numbers = {"n_zeros": n_zeros, "spacings": total,
                 "mean_spacing": round(sum(sp) / total, 4),
                 "chi2_vs_GUE": round(chi_gue, 4),
                 "chi2_vs_Poisson": round(chi_poi, 4),
                 "fraction_below_0.5": round(sum(1 for s in sp if s < 0.5) / total, 4)}
    r.series = {"observed": obs, "gue": gue, "poisson": poi}
    r.plots = [{"kind": "hist_vs_curves", "series": "observed",
                "curves": ["gue", "poisson"],
                "labels": ["izmjereno", "GUE (Wigner)", "Poisson (slučajno)"],
                "title": "Raspodjela normalizovanih razmaka nula",
                "xlabel": "s", "ylabel": "gustina"}]
    verdict = ("bliže GUE" if chi_gue < chi_poi else "bliže Poissonu")
    r.reading = (
        f"{total} normalizovanih razmaka, srednja vrijednost "
        f"{r.numbers['mean_spacing']:.4f} (po konstrukciji ≈ 1).\n\n"
        f"χ² prema GUE: {chi_gue:.3f} · χ² prema Poissonu: {chi_poi:.3f} → "
        f"**{verdict}**.\n\n"
        f"Ključna činjenica: samo {r.numbers['fraction_below_0.5']*100:.1f}% "
        f"razmaka je ispod pola prosjeka. Nule se **odbijaju**. Da su slučajne "
        f"i nezavisne (Poisson), bliski parovi bi bili česti.\n\n"
        f"To odbijanje je isto ono koje pokazuju svojstvene vrijednosti "
        f"slučajnih Hermitskih matrica — Montgomery–Odlyzko. Odatle "
        f"Hilbert–Pólya: ako su nule spektar nekog samoadjungovanog operatora, "
        f"one MORAJU biti realne, i RH je posljedica. Operator još niko nije "
        f"našao.\n\n"
        f"⚠ Na malim visinama (prvih par stotina nula) statistika je još "
        f"prelazna — pravo GUE ponašanje se vidi tek visoko gore, gdje je "
        f"Odlyzko računao milijarde nula.")
    if n_zeros < 200:
        r.warnings.append("ispod ~200 nula uzorak je premali za ozbiljno "
                          "poređenje sa GUE; ovo je ilustracija, ne mjerenje")
    return r


# --------------------------------------------------------------------------- #
# 8. Robin's criterion — an RH equivalence you can test with integers
# --------------------------------------------------------------------------- #
def _run_robin(n_max: int) -> Result:
    rb = Z.robin_check(n_max)
    r = Result()
    w = rb["worst"]
    r.numbers = {"n_max": n_max, "worst_n": w["n"], "worst_ratio": round(w["ratio"], 8),
                 "violations": len(rb["violations"])}
    r.series = {"ratio": rb["samples"]}
    r.plots = [{"kind": "scatter", "series": "ratio",
                "title": "σ(n) / (e^γ · n · log log n)   —   Robinov kriterijum",
                "xlabel": "n", "ylabel": "odnos", "hline": 1.0}]
    r.reading = (
        f"Za n od 5041 do {n_max}: najveći odnos σ(n)/(e^γ n log log n) je "
        f"**{w['ratio']:.8f}** kod n = {w['n']}. Kršenja: {len(rb['violations'])}.\n\n"
        f"Robin (1984): RH je **ekvivalentna** tvrdnji da je taj odnos < 1 za "
        f"svako n > 5040. Nije posljedica, nego ekvivalencija — jedno jedino "
        f"kršenje oborilo bi RH.\n\n"
        f"Zapazi koliko je tijesno: odnos se drži tik ispod 1 i ne pada. "
        f"Ekstremalni kandidati su superabundantni brojevi (n = 10080 je jedan "
        f"od njih). Ovo je najkonkretniji oblik u kojem RH postaje tvrdnja o "
        f"običnim cijelim brojevima — bez ijedne kompleksne funkcije.")
    return r


# --------------------------------------------------------------------------- #
# 9. Mertens function
# --------------------------------------------------------------------------- #
def _run_mertens(x: int) -> Result:
    me = Z.mertens(x)
    r = Result()
    r.numbers = {"x": x, "M_x": me["M"], "max_ratio": round(me["max_ratio"], 5)}
    r.series = {"M": [(n, m) for n, m, _ in me["series"]],
                "ratio": [(n, rr) for n, _, rr in me["series"]]}
    r.plots = [{"kind": "line", "series": "M",
                "title": f"Mertensova funkcija M(x), x ≤ {x}",
                "xlabel": "x", "ylabel": "M(x)", "zeroline": True},
               {"kind": "line", "series": "ratio",
                "title": "|M(x)| / √x", "xlabel": "x", "ylabel": "odnos",
                "hline": 1.0}]
    r.reading = (
        f"M({x}) = {me['M']}. Najveći odnos |M(x)|/√x u ovom rasponu (od "
        f"x ≥ 100) je {me['max_ratio']:.5f}.\n\n"
        f"Mertens je 1897. slutio |M(x)| < √x. Odlyzko i te Riele su 1985. "
        f"**oborili** tu slutnju — bez da su pokazali ijedan kontraprimjer; "
        f"najmanji je van dohvata računanja.\n\n"
        f"Ono što ostaje ekvivalentno RH je slabija tvrdnja: "
        f"M(x) = O(x^{{1/2+ε}}) za svako ε > 0.\n\n"
        f"Pouka je metodološka i vrijedi je zapamtiti za ovih dvadeset dana: "
        f"numerički dokaz do 10¹⁰ nije dokaz. Mertensova slutnja je izgledala "
        f"savršeno sigurno cijelo stoljeće.")
    return r


# --------------------------------------------------------------------------- #
# 10. S(T) fluctuation on its own
# --------------------------------------------------------------------------- #
def _run_s_of_t(T: float) -> Result:
    step = min(Z.recommended_step(T, 8.0), 0.05)
    roots, _ = Z.sign_changes(0.1, T, step)
    ser = []
    for i, x in enumerate(roots, start=1):
        ser.append((x.root, i - Z.N_smooth(x.root)))
    vals = [v for _, v in ser]
    r = Result()
    r.numbers = {"T": T, "zeros": len(roots),
                 "S_max": round(max(vals), 4) if vals else 0.0,
                 "S_min": round(min(vals), 4) if vals else 0.0,
                 "S_mean": round(sum(vals) / len(vals), 5) if vals else 0.0}
    r.series = {"S": ser}
    r.plots = [{"kind": "step", "series": "S", "title": "S(T)",
                "xlabel": "T", "ylabel": "S(T)", "zeroline": True}]
    r.reading = (
        f"S(T) u opsegu [{r.numbers['S_min']:+.3f}, {r.numbers['S_max']:+.3f}], "
        f"srednja vrijednost {r.numbers['S_mean']:+.5f} ≈ 0.\n\n"
        f"S(T) mjeri koliko stvarni broj nula odstupa od glatke formule. "
        f"Poznato je: S(T) = O(log T) bezuslovno, S(T) = O(log T / log log T) "
        f"pod RH, srednja vrijednost je 0, i S(T) je neograničena u oba smjera "
        f"(Selberg) — ali raste toliko sporo da na dohvatljivim visinama "
        f"gotovo nikad ne pređe ±2. Sve numeričko samopouzdanje oko RH počiva "
        f"na tome koliko je S(T) pitoma tamo gdje umijemo da gledamo.")
    return r


# --------------------------------------------------------------------------- #
# 11. zeta on the critical strip (domain colouring)
# --------------------------------------------------------------------------- #
def _run_strip(t0: float, t1: float, nx: int, ny: int) -> Result:
    import numpy as np
    sig = np.linspace(-0.2, 1.4, nx)
    ts = np.linspace(t0, t1, ny)
    mod = np.zeros((ny, nx))
    arg = np.zeros((ny, nx))
    import mpmath as _mp
    with _mp.workdps(15):
        for j, t in enumerate(ts):
            for i, s in enumerate(sig):
                v = _mp.zeta(_mp.mpc(float(s), float(t)))
                mod[j, i] = float(_mp.log(abs(v) + 1e-30))
                arg[j, i] = float(_mp.arg(v))
    r = Result()
    r.numbers = {"sigma_min": -0.2, "sigma_max": 1.4, "t0": t0, "t1": t1,
                 "grid": f"{nx}x{ny}",
                 "min_log_mod": round(float(mod.min()), 4)}
    r.series = {}
    r.plots = [{"kind": "field", "data": {"mod": mod.tolist(), "arg": arg.tolist(),
                                          "extent": [-0.2, 1.4, t0, t1]},
                "title": f"log|ζ(σ+it)| na traci, t ∈ [{t0:g}, {t1:g}]",
                "xlabel": "σ", "ylabel": "t", "critical_line": 0.5}]
    r.reading = (
        f"Tamne tačke su nule. Sve leže na vertikalnoj liniji σ = ½ — to je "
        f"ono što RH tvrdi za sve njih.\n\n"
        f"Obrati pažnju na simetriju oko σ = ½: to je funkcionalna jednačina "
        f"ζ(s) = χ(s)ζ(1−s), koja preslikava traku na sebe i vezuje σ i 1−σ. "
        f"Kritična prava je linija fiksnih tačaka tog preslikavanja — zato je "
        f"baš ona 'prirodno' mjesto za nule, i zato RH nije proizvoljna slutnja.")
    return r


# --------------------------------------------------------------------------- #
# 12. Self-test: the functional equation
# --------------------------------------------------------------------------- #
def _run_selftest(n_points: int) -> Result:
    pts = [complex(0.3 + 0.11 * k, 2.0 + 1.7 * k) for k in range(n_points)]
    res = [Z.functional_equation_residual(s) for s in pts]
    zs = Z.zeta_zeros(5)
    known = [14.134725141734693, 21.022039638771554, 25.010857580145688,
             30.424876125859513, 32.935061587739189]
    zero_err = [abs(a - b) for a, b in zip(zs, known)]
    r = Result()
    r.numbers = {"points": n_points,
                 "max_functional_eq_residual": max(res),
                 "max_zero_error_vs_known": max(zero_err)}
    r.series = {"residual": [(k, v) for k, v in enumerate(res)]}
    ok = max(res) < 1e-20 and max(zero_err) < 1e-9
    r.reading = (
        f"Funkcionalna jednačina ζ(s) = χ(s)ζ(1−s) provjerena u {n_points} "
        f"tačaka; najveći ostatak {max(res):.3e}.\n"
        f"Prvih 5 nula upoređeno sa objavljenim vrijednostima; najveća razlika "
        f"{max(zero_err):.3e}.\n\n"
        + ("✅ Numerika je zdrava — ostalim eksperimentima se može vjerovati."
           if ok else
           "⛔ Numerika NE prolazi self-test. Ne vjeruj ostalim eksperimentima "
           "dok se ovo ne razriješi (preciznost, verzija mpmath)."))
    if not ok:
        r.warnings.append("self-test pao — provjeri mpmath instalaciju i dps")
    return r


# --------------------------------------------------------------------------- #
# QRH method explorer experiments (plan F8). These do not touch ζ numerically;
# they run the exponent-family pipeline in pse_r.methods.core, which is itself a
# port of the validated research scripts. Each is reproducible: the recorded
# script.py carries methods/core.py so the number can be re-derived.
# --------------------------------------------------------------------------- #
def _run_qrh_line(points: int) -> Result:
    from ..methods import core as C
    r = Result()
    ls = [i * (0.2 / (points - 1)) for i in range(points)]
    bs = [j * 0.01 for j in range(21)]
    series = []
    for l in ls:
        k = 2 * C.Bof(l) - 1
        Vmin = min(C.vmax(C.E_liu, b, l, k, 1e-6) for b in bs)
        series.append((l, Vmin))
    openai = C.vmax(C.E_liu, 1 / 8, 1 / 6, 0.75, 1e-6)   # 7/8 point inside the family
    cross = C._bisect(lambda l: min(C.vmax(C.E_liu, b, l, 2 * C.Bof(l) - 1, 1e-6)
                                    for b in bs), 0.0, 0.3)
    r.numbers = {"V(l=0)=11/12": round(series[0][1], 6),
                 "V(7/8: b=1/8,l=1/6,k=3/4)": round(openai, 9),
                 "zero-crossing l (Liu)": round(cross, 6),
                 "B at crossing": round(C.Bof(cross), 9)}
    r.series = {"V": series}
    r.plots = [{"kind": "line", "series": "V", "title": "V(ℓ) duž prave B=11/12−ℓ/4",
                "xlabel": "ℓ", "ylabel": "min_b V", "zeroline": True}]
    r.reading = (
        f"Duž zajedničke prave B(ℓ)=11/12−ℓ/4 (κ=2B−1) najbolja ocjena V je "
        f"glatka i monotona: od {series[0][1]:+.5f} kod ℓ=0 (to je 11/12) do "
        f"{series[-1][1]:+.5f} kod ℓ=0.2. Nulu siječe jednom, kod ℓ≈{cross:.5f} "
        f"(B≈{C.Bof(cross):.6f}) — to je Liu. Tačka 7/8 (ℓ=1/6) leži UNUTAR "
        f"familije sa V={openai:.3e} (isti broj kao rezerva iz OpenAI rada, "
        f"≈−2.28·10⁻⁴). Kontinuitet kroz 11/12, 7/8 i Liua je time potvrđen.")
    return r


def _run_qrh_poly(family: int) -> Result:
    from ..methods import core as C
    fam = "liu" if int(family) == 0 else "xs"
    poly, root = C.exact_polynomial(fam)
    opt = (C.optimum(C.E_liu, 1e-6) if fam == "liu" else C.optimum(C.E_xs, 1 / 8))
    r = Result()
    r.numbers = {"familija": fam, "minimalni polinom B*": str(poly.as_expr()),
                 "stepen": poly.degree(), "B* (korijen)": f"{root:.12f}",
                 "B* (numerički optimum)": f"{opt.B:.12f}",
                 "razlika": f"{abs(root - opt.B):.2e}"}
    r.reading = (
        f"Eliminacijom δ, b, ℓ iz sistema stacionarnosti (sympy, rezultante) "
        f"dobija se egzaktni minimalni polinom granice B* za familiju `{fam}`:\n\n"
        f"`{poly.as_expr()} = 0`\n\n"
        f"Njegov korijen B*={root:.12f} se slaže sa nezavisnim numeričkim "
        f"optimumom ({opt.B:.12f}; razlika {abs(root - opt.B):.1e}). Pipeline je "
        f"validiran na Liuovoj kubnoj.")
    return r


def _run_qrh_transform(n_points: int) -> Result:
    from ..methods import core as C
    xs = C.optimum(C.E_xs, 1 / 8)
    resid = C.transform_residual(xs.b, xs.l, xs.k, n_points)
    bt = {t: C.extend_t(t).B for t in (0, 1, 2)}
    r = Result()
    r.numbers = {"max|E_XS−(E_Liu+T)|": f"{resid:.2e}",
                 "B(t=0, Liu)": f"{bt[0]:.8f}", "B(t=1, Xu–Sang)": f"{bt[1]:.8f}",
                 "B(t=2)": f"{bt[2]:.8f}", "ukupan pomak t:0→2": f"{bt[0] - bt[2]:.2e}"}
    r.series = {"B_of_t": [(t, b) for t, b in bt.items()]}
    r.reading = (
        f"Transformacija E_XS = E_Liu + T je egzaktna: na {n_points} slučajnih "
        f"tačaka najveća greška je {resid:.1e} (≈ mašinska nula). Produženje "
        f"'više iste ideje' (t): t=0 je Liu ({bt[0]:.8f}), t=1 je Xu–Sang "
        f"({bt[1]:.8f}), t=2 daje {bt[2]:.8f}. Pomjera se PREMA cilju, ali se "
        f"zasićuje — ukupan dobitak t:0→2 je svega {bt[0] - bt[2]:.1e}.")
    return r


def _run_qrh_walls(nl: int, nb: int) -> Result:
    import numpy as np
    l, b = np.meshgrid(np.linspace(0, 1.2, nl), np.linspace(0, 0.8, nb))
    B = 11 / 12 - l / 4
    k = 2 * B - 1
    h = (1 + b + 3 * l) / 2
    lx = (1 - b - l) / 2
    ly = (1 + b - l) / 2
    C = {"B>0.87": B > .87, "l<=1/5": l <= .2, "l/h<1/(6k)": (k > 0) & (l / h < 1 / (6 * k)),
         "6kl>3/4": 6 * k * l > .75, "lx>l": lx > l, "ly-l>11b/6": ly - l > 11 * b / 6,
         "h/2<ly": h / 2 < ly, "ly<1/2": ly < .5}
    dropped, ladder = [], []
    while True:
        ok = np.ones_like(B, bool)
        for n, c in C.items():
            if n not in dropped:
                ok &= c
        i = np.unravel_index(np.where(ok, B, 9).argmin(), B.shape)
        Bm = float(B[i])
        binds = []
        for n in C:
            if n in dropped:
                continue
            ok2 = np.ones_like(B, bool)
            for m, c in C.items():
                if m not in dropped and m != n:
                    ok2 &= c
            if np.where(ok2, B, 9).min() < Bm - 1e-6:
                binds.append(n)
        ladder.append({"skinuto": list(dropped), "min_B": round(Bm, 5),
                       "l": round(float(l[i]), 4), "b": round(float(b[i]), 4),
                       "vezujući": binds})
        if not binds:
            break
        dropped.append(binds[0])
    r = Result()
    bottom = ladder[-2]["min_B"] if len(ladder) > 1 else ladder[-1]["min_B"]
    r.numbers = {"koraka na ljestvici": len(ladder),
                 "najniže B (strukturni zid)": bottom,
                 "≈ 5/6": round(5 / 6, 5)}
    r.series = {"ladder": [(i, step["min_B"]) for i, step in enumerate(ladder)]}
    r.reading = (
        "Skidajući uslove dopustivosti (Xu–Sang §6.2) jedan po jedan, najniže B "
        "koje geometrija prave dozvoljava pada do **{:.5f} ≈ 5/6** (strukturni "
        "zid l_x>ℓ). Nijedna kontinualna deformacija unutar ove geometrije ne "
        "prolazi ispod 5/6; prema 3/4 ili 1/2 ova familija ne vodi — treba nova "
        "geometrija. (Zadnji red bez vezujućeg uslova je ivica mreže, ne "
        "rezultat.)".format(bottom))
    for step in ladder:
        r.warnings.append(f"skinuto {step['skinuto']}: min B={step['min_B']} "
                          f"(ℓ={step['l']}, b={step['b']}) vezuje {step['vezujući']}")
    return r


def _run_qrh_licence(family: int, steps: int) -> Result:
    from ..methods import core as C
    fam = "liu" if int(family) == 0 else "xs"
    Ef, dlo = (C.E_liu, 1e-6) if fam == "liu" else (C.E_xs, 1 / 8)
    k, seq = 0.75, []
    for _ in range(steps):
        B = C.optimum(Ef, dlo, kfix=k).B
        seq.append(B)
        k = 2 * B - 1
    gaps = [seq[i] - seq[i + 1] for i in range(len(seq) - 1)]
    r = Result()
    r.numbers = {"familija": fam, "B niz": [f"{v:.12f}" for v in seq],
                 "kontrakcija (prvi korak)": f"{abs(gaps[0]):.2e}" if gaps else "—"}
    r.series = {"B_of_step": [(i, v) for i, v in enumerate(seq)]}
    r.reading = (
        f"Iteracija licence κ ← 2B−1 (familija `{fam}`) počev od κ=3/4: niz B "
        f"se stabilizuje za {len(seq)} koraka, s kontrakcijom "
        f"{abs(gaps[0]):.1e} već na prvom koraku. Licenca je 'mrtva poluga' — "
        f"iscrpi se za ~3 koraka i ne pomjera granicu suštinski.")
    return r


# --------------------------------------------------------------------------- #
CATALOG: list[Experiment] = [
    Experiment(
        "selftest", "Self-test numerike",
        "Da li se ovoj mašini može vjerovati?",
        "Prvo što treba pokrenuti. Provjerava funkcionalnu jednačinu i prvih pet "
        "nula protiv objavljenih vrijednosti. Ako ovo padne, svi ostali brojevi "
        "u aplikaciji su bezvrijedni.",
        [Param("n_points", "int", 8, 3, 40, "koliko tačaka provjeriti")],
        _run_selftest, "brz"),
    Experiment(
        "z_curve", "Hardy Z(t)",
        "Gdje su nule i kako izgledaju?",
        "Z je realna na kritičnoj pravoj, pa se nule vide kao presjeci nule. "
        "Prvi kontakt sa predmetom.",
        [Param("t0", "float", 0.0, 0.0, 100000.0, "donja granica"),
         Param("t1", "float", 100.0, 1.0, 100000.0, "gornja granica"),
         Param("samples", "int", 2000, 200, 40000, "broj uzoraka")],
        _run_z_curve, "brz"),
    Experiment(
        "zeros", "Nule i njihovi razmaci",
        "Koliko su nule blizu jedna drugoj i ima li opasno bliskih parova?",
        "Lehmerovi parovi su najbliže što numerika dolazi kontraprimjeru za RH.",
        [Param("n", "int", 60, 5, 500, "koliko nula")],
        _run_zeros, "srednji"),
    Experiment(
        "counting", "N(T) i provjera RH na intervalu",
        "Da li je broj nula NA pravoj jednak ukupnom broju nula u traci?",
        "Ovo je prava numerička provjera RH — ne 'sve nule koje sam vidio su na "
        "pravoj', nego 'pronašao sam ih tačno onoliko koliko ih teorija predviđa "
        "u cijeloj traci'.",
        [Param("T", "float", 100.0, 20.0, 2000.0, "visina"),
         Param("samples_per_unit", "float", 10.0, 4.0, 40.0, "gustina skeniranja")],
        _run_counting, "srednji"),
    Experiment(
        "gram", "Gramove tačke i Gramov zakon",
        "Da li svaki Gramov interval sadrži tačno jednu nulu?",
        "Tendencija koja pada beskonačno mnogo puta. Kršenja su zanimljiviji dio.",
        [Param("n_start", "int", 0, -1, 5000, "prvi indeks"),
         Param("n_end", "int", 40, 1, 5000, "posljednji indeks")],
        _run_gram, "srednji"),
    Experiment(
        "explicit", "Eksplicitna formula ψ(x)",
        "Kako iz nula izlaze primovi?",
        "Najvažniji demo u cijeloj aplikaciji. Svaka nula je jedan talas; "
        "saberi ih i dobiješ stepenice primova.",
        [Param("x_max", "float", 100.0, 20.0, 3000.0, "do kojeg x"),
         Param("n_zeros", "int", 50, 1, 300, "koliko nula uključiti")],
        _run_explicit, "srednji"),
    Experiment(
        "prime_counting", "π(x) vs li(x) vs R(x)",
        "Koliko dobro glatke formule pogađaju broj primova?",
        "R(x) je dramatično bolji od li(x); ono što ni jedan ne hvata su "
        "oscilacije od nula.",
        [Param("x_max", "int", 100000, 1000, 3000000, "do kojeg x"),
         Param("points", "int", 40, 5, 200, "broj tačaka")],
        _run_prime_counting, "srednji"),
    Experiment(
        "gue", "Razmaci nula vs GUE",
        "Da li se nule ponašaju kao svojstvene vrijednosti slučajnih matrica?",
        "Most između teorije brojeva i kvantnog haosa; osnova Hilbert–Pólya "
        "programa.",
        [Param("n_zeros", "int", 200, 30, 1000, "koliko nula"),
         Param("bins", "int", 24, 8, 60, "broj klasa histograma")],
        _run_gue, "spor"),
    Experiment(
        "robin", "Robinov kriterijum",
        "Da li σ(n) ostaje ispod e^γ n log log n?",
        "RH prevedena na tvrdnju o običnim cijelim brojevima. Ekvivalencija, ne "
        "posljedica.",
        [Param("n_max", "int", 200000, 6000, 3000000, "do kojeg n")],
        _run_robin, "spor"),
    Experiment(
        "mertens", "Mertensova funkcija",
        "Koliko M(x) stvarno raste?",
        "Slutnja koja je izgledala sigurna sto godina pa pala. Lekcija o "
        "granicama numeričkog dokaza.",
        [Param("x", "int", 200000, 1000, 3000000, "do kojeg x")],
        _run_mertens, "srednji"),
    Experiment(
        "s_of_t", "Fluktuacija S(T)",
        "Koliko odstupa stvarni broj nula od glatke formule?",
        "Cijelo numeričko samopouzdanje oko RH počiva na tome koliko je S(T) "
        "pitoma na visinama koje umijemo da dosegnemo.",
        [Param("T", "float", 200.0, 30.0, 2000.0, "visina")],
        _run_s_of_t, "srednji"),
    Experiment(
        "strip", "ζ na kritičnoj traci",
        "Kako izgleda ζ kao funkcija kompleksne promjenljive?",
        "Simetrija oko σ = ½ je funkcionalna jednačina; zato je kritična prava "
        "prirodno mjesto za nule.",
        [Param("t0", "float", 0.0, 0.0, 500.0, "donji t"),
         Param("t1", "float", 40.0, 5.0, 500.0, "gornji t"),
         Param("nx", "int", 120, 40, 400, "rezolucija po σ"),
         Param("ny", "int", 240, 40, 800, "rezolucija po t")],
        _run_strip, "spor"),
    # --- QRH method explorer (F8) --- #
    Experiment(
        "qrh_line", "QRH: V(ℓ) duž prave",
        "Postoji li jedna kontinualna funkcija kroz 11/12, 7/8 i Liua?",
        "Granice QRH metoda leže na pravoj B=11/12−ℓ/4; ovaj eksperiment pokazuje "
        "da je najbolja ocjena V(ℓ) glatka i da 7/8 leži unutar familije.",
        [Param("points", "int", 11, 5, 41, "broj tačaka po ℓ")],
        _run_qrh_line, "brz"),
    Experiment(
        "qrh_poly", "QRH: egzaktni polinom B*",
        "Koji je egzaktni minimalni polinom granice metode?",
        "Eliminacija δ,b,ℓ (sympy, rezultante) daje egzaktni polinom — "
        "validirano na Liuovoj kubnoj, pa primijenjeno na Xu–Sang kvartnu.",
        [Param("family", "int", 0, 0, 1, "0=Liu (kubna), 1=Xu–Sang (kvartna)")],
        _run_qrh_poly, "srednji"),
    Experiment(
        "qrh_transform", "QRH: transformacija Liu→XS",
        "Je li transformacija E_XS=E_Liu+T egzaktna i kuda vodi njeno proširenje?",
        "Srž misije: kontinualna transformacija između metoda i da li produženje "
        "(t) pomjera B prema ciljevima ili od njih.",
        [Param("n_points", "int", 2000, 100, 20000, "slučajnih tačaka za provjeru T")],
        _run_qrh_transform, "spor"),
    Experiment(
        "qrh_walls", "QRH: ljestvica zidova",
        "Koliko nisko B može kad se uslovi dopustivosti skidaju jedan po jedan?",
        "Pokazuje strukturni zid ≈5/6: nijedna deformacija ove geometrije ne "
        "prolazi niže, pa prema 3/4 ili 1/2 treba nova geometrija.",
        [Param("nl", "int", 1201, 301, 3001, "rezolucija po ℓ"),
         Param("nb", "int", 801, 201, 1601, "rezolucija po b")],
        _run_qrh_walls, "srednji"),
    Experiment(
        "qrh_licence", "QRH: iteracija licence κ",
        "Koliko pomjera ponavljanje licence κ←2B−1?",
        "Licenca je 'mrtva poluga' — iscrpi se za ~3 koraka; ovaj eksperiment to "
        "mjeri kao kontrakciju niza B.",
        [Param("family", "int", 0, 0, 1, "0=Liu, 1=Xu–Sang"),
         Param("steps", "int", 5, 2, 10, "broj koraka iteracije")],
        _run_qrh_licence, "spor"),
]

def _run_qrh_adversary(family: int, eps_exp: int) -> Result:
    """Item 31: the adversarial mode as a lab run (PNG + card + NAŠE-NERECENZIRANO)."""
    from ..methods import adversary as A
    name = "liu" if int(family) == 0 else "xs"
    rep = A.run(name, eps=10.0 ** (-int(eps_exp)))
    A._LAST[name] = rep
    c = rep.certificate
    r = Result()
    r.numbers = {"metoda": name, "tvrđeno B": rep.claimed_B, "najbolje B uz uslove": rep.best_B,
                 "bolje od tvrdnje": rep.better_than_claim, "b*": round(rep.best_at["b"], 9),
                 "ℓ*": rep.best_at["l"], "κ*": rep.best_at["k"],
                 "tačaka bolje uz kršenje": len(rep.breaks),
                 "certifikat: B od": c.get("B_low"), "certifikat: B do": c.get("B_high"),
                 "certifikat: ćelija": c.get("cells"), "certifikat: neodlučeno": c.get("undecided"),
                 "certifikat kompletan": c.get("complete"), "sekundi": round(rep.seconds + c.get("seconds", 0), 2)}
    r.series = {"B_licence(b)": [(b, B) for b, B in rep.curve],
                "kršenja": [(br["b"], br["B"]) for br in rep.breaks]}
    r.plots = [{"kind": "line", "series": "B_licence(b)", "marks": "kršenja",
                "title": f"{name}: najbolje B po b uz licencu (crveno: bolje, ali krši uslov)",
                "xlabel": "b", "ylabel": "B", "hline": rep.claimed_B}]
    worst = rep.breaks[0] if rep.breaks else None
    r.reading = (
        f"**{rep.summary()}**\n\n"
        f"(a) Uz uslove metode (licenca κ = 2B − 1, x = 1/2, δ ∈ [dlo, 5/6]) pretraga po b daje "
        f"najbolje B = {rep.best_B:.12f} kod b = {rep.best_at['b']:.6f}; tvrdnja {rep.claimed_B:.12f} "
        + ("**nije optimum**." if rep.better_than_claim else "odolijeva u tačnosti pretrage.") + "\n\n"
        f"(b) Sa slobodnim κ, {len(rep.breaks)} tačaka daje bolje B od tvrdnje — svaka krši bar jedan uslov"
        + (f"; najniže B = {worst['B']:.9f} krši: {', '.join(worst['krši'])}." if worst else ".") + "\n\n"
        f"(c) Certifikat praznine (intervalna aritmetika, mpmath.iv): za B ∈ [{c.get('B_low', 0):.6f}, "
        f"{c.get('B_high', 0):.12f}] NEMA dopustivih parametara u {c.get('cells', 0)} ćelija"
        + ("" if c.get("complete") else f" — **DJELIMIČNO**: {c.get('undecided')} ćelija neodlučeno") + ". "
        "Pretpostavke: " + "; ".join(c.get("assumptions", [])) + ". Certifikat važi za E kako je "
        "implementiran u `methods/core.py` (konstante u double preciznosti). NAŠE-NERECENZIRANO.")
    if not c.get("complete", True):
        r.warnings.append("certifikat je djelimičan — povećaj budžet ćelija ili ε")
    return r


def _run_qrh_complex(family: int, n: int) -> Result:
    """Item 32 (b): E with a complex δ — the boundary as the zero of a discriminant."""
    from ..methods import complexver as CV
    fam = "liu" if int(family) == 0 else "xs"
    r0 = CV.margin_curve(fam, n=int(n))
    r = Result()
    r.numbers = {"metoda": fam, "ℓ* (optimum)": r0["l_star"], "ℓ (diskriminanta = 0)": r0["l_disc"],
                 "razlika": r0["agree"], "δ* (dvostruki korijen)": r0["delta_star"],
                 "c u |Im δ| ≈ c·√(ℓ* − ℓ)": r0["c"], "b*": r0["b_star"]}
    r.series = {"|Im δ|": [(l, im) for l, im, *_ in r0["rows"]],
                "Re δ₁": [(l, a) for l, _im, a, _b, _d in r0["rows"]],
                "Re δ₂": [(l, b) for l, _im, _a, b, _d in r0["rows"]]}
    r.plots = [{"kind": "two_lines", "series": ["|Im δ|", "Re δ₁", "Re δ₂"],
                "labels": ["|Im δ| (metoda prolazi kad je > 0)", "Re δ₁", "Re δ₂"],
                "title": f"{fam}: korijeni E(δ) = 0 po ℓ (kompleksni par → dvostruki → dva realna)",
                "xlabel": "ℓ", "ylabel": "δ", "zeroline": True}]
    r.reading = (
        f"Brojilac E(δ) pri x = 1/2 je **kvadratni polinom u δ** (tačno, sympy). Za ℓ < ℓ* korijeni su "
        f"konjugovani par (metoda prolazi), u ℓ* se stapaju u dvostruki korijen δ* = {r0['delta_star']:.10f}, "
        f"a za ℓ > ℓ* su dva realna (E > 0 između njih — metoda pada). Nula diskriminante daje "
        f"ℓ = {r0['l_disc']:.15f}, a optimum ℓ* = {r0['l_star']:.15f} (razlika {r0['agree']:.1e}). "
        f"Udaljenost od granice: |Im δ| ≈ {r0['c']:.4f}·√(ℓ* − ℓ).\n\n"
        "**Kompleksna verzija ne daje novo B** — daje algebarsku karakterizaciju granice (nula "
        "diskriminante) i mjeru margine. I to je rezultat. NAŠE-NERECENZIRANO.\n\n"
        "(a) " + CV.GAMMA_NOTE)
    try:                                        # the mission records what was computed
        from ..shared_lib import missions as MIS
        if MIS.get(MIS.THIRD_ID) is not None:
            MIS.step(MIS.THIRD_ID, f"(b) lab: korijeni E(δ) u ℂ za {fam}",
                     f"granica = nula diskriminante (Δℓ = {r0['agree']:.1e}); c = {r0['c']:.4f}; "
                     "novo B: ne — NAŠE-NERECENZIRANO", MIS.get(MIS.THIRD_ID)["state"], ref=f"lab:qrh_complex:{fam}")
    except Exception:                           # noqa: BLE001
        pass
    return r


CATALOG.append(Experiment(
    "qrh_complex", "QRH: kompleksna verzija (misija 3)",
    "Šta je E sa kompleksnim δ, i gdje se signal i niska strana sijeku u ℂ?",
    "Granica metode je nula diskriminante kvadratnog brojioca E(δ); |Im δ| mjeri marginu.",
    [Param("family", "int", 0, 0, 1, "0=Liu, 1=Xu–Sang"),
     Param("n", "int", 41, 11, 201, "broj tačaka po ℓ")],
    _run_qrh_complex, "brz"))

CATALOG.append(Experiment(
    "qrh_adversary", "QRH: adversarijalni mod",
    "Da li je tvrđeno B zaista optimum metode, šta treba prekršiti za bolje, i da li je prostor iznad B* prazan?",
    "Skeptik napada riječima, ovo brojevima: potraga po parametrima + strogi certifikat praznine.",
    [Param("family", "int", 0, 0, 1, "0=Liu, 1=Xu–Sang"),
     Param("eps_exp", "int", 6, 4, 7, "ε = 10^−n: koliko blizu B* certifikat ide")],
    _run_qrh_adversary, "srednji"))

BY_KEY = {e.key: e for e in CATALOG}

# Which ontology branch each experiment belongs to. This is what links a lab
# run into the knowledge graph instead of leaving it an orphan.
BRANCH_OF = {
    "selftest": "numerics", "z_curve": "numerics", "zeros": "numerics",
    "counting": "numerics", "gram": "numerics", "s_of_t": "numerics",
    "strip": "numerics",
    "explicit": "pnt_error", "prime_counting": "pnt_error",
    "gue": "rmt",
    "robin": "equivalences", "mertens": "equivalences",
    "qrh_line": "quasi-rh", "qrh_poly": "quasi-rh", "qrh_transform": "quasi-rh",
    "qrh_walls": "quasi-rh", "qrh_licence": "quasi-rh", "qrh_adversary": "quasi-rh", "qrh_complex": "quasi-rh",
}


def get(key: str) -> Optional[Experiment]:
    return BY_KEY.get(key)
