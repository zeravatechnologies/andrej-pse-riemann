# Renders every figure of this research note as PNG (GitHub and file viewers show PNG, not Chart.js HTML).
# Usage: python make_png_figures.py   (needs numpy, matplotlib; reads ../results/plotdata_fig2.json)
import os, json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "figures")
D = json.load(open(os.path.join(HERE, "..", "results", "plotdata_fig2.json")))
BLUE, ORANGE, AQUA, VIOLET, RED, GRAY = "#2a78d6", "#eb6834", "#1baf7a", "#6250d6", "#e34948", "#898781"
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": "#e1e0d9", "grid.linewidth": .8, "figure.dpi": 130})
XI = 0.388583354266
def save(fig, name):
    fig.tight_layout(); fig.savefig(os.path.join(OUT, name), bbox_inches="tight"); plt.close(fig); print("wrote", name)

# ---------- fig1: strip, zoom, Liu cubic ----------
fig, ax = plt.subplots(3, 1, figsize=(7.5, 8.2), gridspec_kw={"height_ratios": [1, 1.1, 1.6]})
a = ax[0]; a.set_title("1 · Kritična traka: zona bez nula je desno od 7/8", loc="left")
a.axvspan(7/8, 1, color=AQUA, alpha=.18); a.axhline(0, color=GRAY, lw=.8)
for x, lab, c in ((.5, "1/2 (RH)", RED), (7/8, "7/8", AQUA), (11/12, "11/12", GRAY), (1, "1", GRAY)):
    a.axvline(x, color=c, lw=2 if c != GRAY else 1); a.text(x + .004, .6 - .45*(lab=="11/12"), lab, ha="left", fontsize=9)
a.set_xlim(.45, 1.02); a.set_ylim(-1, 1); a.set_yticks([]); a.grid(False)
a.text(.69, -.6, "jaz 1/2 → 7/8: treba nova ideja", ha="center", fontsize=9, color=GRAY)
a = ax[1]; a.set_title("2 · Zum oko 7/8 (lijevo = jača teorema)", loc="left")
pts = [(.875, "OpenAI 0.875", AQUA), (.874957019, "Liu 0.874957", VIOLET), (.8748875, "Xu–Sang B₀", ORANGE), (.8748867, "B₁", ORANGE)]
for i, (x, lab, c) in enumerate(pts):
    a.axvline(x, color=c, lw=2, ls="--" if lab == "B₁" else "-"); a.text(x + 1.5e-6 * (1 if lab != "Xu–Sang B₀" else -1), .55 - .35 * (i % 2), lab, ha="left" if lab != "Xu–Sang B₀" else "right", fontsize=9)
a.set_xlim(.87485, .87502); a.set_ylim(-1, 1); a.set_yticks([]); a.grid(False)
a.text(.874935, -.85, "B₀ − B₁ = 8·10⁻⁷ · Liu − OpenAI = −4.3·10⁻⁵", ha="center", fontsize=9, color=GRAY)
a.ticklabel_format(useOffset=False)
a = ax[2]; a.set_title("3 · Liu: f(ξ) = 1188ξ³ − 2160ξ² + 171ξ + 190, korijen ξ* ≈ 0.388583", loc="left")
x = np.linspace(.3, .48, 300); a.plot(x, 1188*x**3 - 2160*x**2 + 171*x + 190, color=VIOLET, lw=2)
a.axhline(0, color=GRAY, ls="--", lw=1); a.plot([XI], [0], "o", color=ORANGE)
a.annotate("ξ* → B = (18ξ+7)/(18ξ+9) = 0.8749570", (XI, 0), (0.40, 45), fontsize=9, arrowprops=dict(arrowstyle="->", color=GRAY))
a.set_xlabel("ξ"); a.set_ylabel("f(ξ)")
save(fig, "fig1_overview.png")

# ---------- fig2: six crossing charts ----------
fig, ax = plt.subplots(3, 2, figsize=(11, 11.5)); ax = ax.ravel()
a = ax[0]; a.set_title("1 · Svi na pravoj B(ℓ) = 11/12 − ℓ/4", loc="left")
l = np.linspace(.1660, .1676, 50)
a.plot(l, 11/12 - l/4, color=BLUE, lw=2, label="niska strana B(ℓ)")
a.plot(l, (1+XI)/2 + l*(1+3*XI)/2, color=ORANGE, lw=2, ls="--", label="Liuova visoka strana")
a.plot(1/6, .875, "o", color=GRAY, ms=8, label="OpenAI 7/8")
a.plot(.166838589, .874957019, "D", color=VIOLET, ms=8, label="Liu")
a.plot(10027/60000, 69991/80000, "^", color=AQUA, ms=8, label="Xu–Sang B₀")
a.plot(1253399/7500000, .8748867, "s", color=AQUA, ms=7, label="Xu–Sang B₁")
a.set_ylim(.8744, .8756); a.set_xlabel("ℓ (dužina primova)"); a.set_ylabel("B"); a.legend(fontsize=8); a.ticklabel_format(useOffset=False)
a = ax[1]; a.set_title("2 · 11/12: nema presjeka, limes ϑ → 0", loc="left")
t = np.linspace(0, .1, 50)
a.plot(t, (11+5*t)/12, color=BLUE, lw=2, label="e₁ = (11+5ϑ)/12 (dominira)")
a.plot(t, (5-t)/6, color=ORANGE, lw=2, label="e₂ = (5−ϑ)/6")
a.axhline(11/12, color=GRAY, ls="--", lw=1, label="11/12"); a.set_xlabel("ϑ"); a.set_ylabel("eksponent od A₁"); a.legend(fontsize=8)
a = ax[2]; a.set_title("3 · 7/8: signal s − 11/16 siječe 3/16 u s = 7/8", loc="left")
s = np.linspace(.8, .95, 10)
a.plot(s, s - 11/16, color=BLUE, lw=2, label="signal C(s)"); a.axhline(3/16, color=ORANGE, lw=2, label="niska ocjena 3/16")
a.plot(.875, .1875, "o", color=AQUA, ms=9); a.set_xlabel("s"); a.set_ylabel("eksponent"); a.legend(fontsize=8)
a = ax[3]; a.set_title("4 · Visoka strana E(δ) ≤ 0  (×10⁻³)", loc="left")
d = np.array(D["oai_d"])
a.plot(d, D["oai_E"], color=GRAY, lw=2, label="OpenAI 7/8: rezerva 2.3·10⁻⁴")
a.plot(d, D["liu_E"], color=VIOLET, lw=2, label="Liu: dotiče 0 u δ = ξ*")
a.plot(d, D["liu_Ebad"], color=RED, lw=2, ls="--", label="Liu, ℓ + 0.002: probija 0 (naš test)")
a.axhline(0, color=GRAY, ls=":", lw=1); a.set_xlim(.15, .65); a.set_ylim(-8, 3.5); a.set_xlabel("δ (klasa redova)"); a.set_ylabel("E ×10⁻³"); a.legend(fontsize=8)
a = ax[4]; a.set_title("5 · Liu: κ(ξ) siječe licencu 2B(ξ) − 1", loc="left")
x = np.linspace(.375, .3895, 200)   # kappa(xi) has a pole at xi≈0.3911 (36ξ²−78ξ+25=0); stay left of it
k = (18*x*x - 57*x + 20) / (6*(36*x*x - 78*x + 25)); Bx = (18*x+7)/(18*x+9)
a.plot(x, k, color=VIOLET, lw=2, label="κ(ξ) iz R = 2/3"); a.plot(x, 2*Bx-1, color=AQUA, lw=2, label="2B(ξ) − 1")
a.plot(XI, 2*(18*XI+7)/(18*XI+9)-1, "o", color=ORANGE, ms=8, label="ξ* (korijen kubne)"); a.set_ylim(.735, .765); a.set_xlabel("ξ  (pol κ(ξ) kod 0.3911 izostavljen)"); a.set_ylabel("κ"); a.legend(fontsize=8)
a = ax[5]; a.set_title("6 · Xu–Sang: max_x E(δ) vs prag −g  (×10⁻⁶)", loc="left")
for key, zd, c, lab, g in (("xs0_z", "xs0_zd", ORANGE, "faza 0 (κ=3/4), max −2.23", -1), ("xs1_z", "xs1_zd", BLUE, "faza 1, max −0.22", -.1)):
    dd = np.array(D[zd]); vv = np.array(D[key]); m = vv > -60
    a.plot(dd[m], vv[m], color=c, lw=2, label=lab); a.axhline(g, color=c, ls="--", lw=1)
a.set_ylim(-8, .5); a.set_xlabel("δ"); a.set_ylabel("E ×10⁻⁶"); a.legend(fontsize=8)
save(fig, "fig2_crossings.png")

# ---------- fig3: continuity, extension, walls ----------
fig, ax = plt.subplots(3, 1, figsize=(7.5, 11))
a = ax[0]; a.set_title("A · Kontinuitet: min_b V(ℓ) duž prave (Liuova familija)", loc="left")
L = [0, .02, .04, .06, .08, .1, .12, .14, .16, .18, .2]
V = [-.20833, -.185, -.16166, -.13829, -.11385, -.08839, -.06227, -.03573, -.0091, .01752, .04414]
a.plot(L, V, "o-", color=VIOLET, lw=2, ms=4, label="min_b V(ℓ)"); a.axhline(0, color=GRAY, ls=":", lw=1)
a.plot(0, -.20833, "o", color=GRAY, ms=9, label="11/12 (ℓ=0)"); a.plot(1/6, -.000228, "^", color=AQUA, ms=9, label="7/8 (rezerva)")
a.plot(.166839, 0, "D", color=ORANGE, ms=8, label="Liu (nula)"); a.set_xlabel("ℓ"); a.set_ylabel("V"); a.legend(fontsize=8)
a = ax[1]; a.set_title("B · Proširenje transformacije (naš račun)", loc="left")
T = [(0, .87495702), (.5, .87492636), (1, .87488665), (1.5, .87483318), (2, .87475723), (2.5, .87473555)]
W = [(0, .86998616), (.05, .86998617), (.1, .86998678), (.15, .87015337), (.2, .87155365), (.25, .87488665)]
a.plot(*zip(*T), "o-", color=BLUE, lw=2, label="po t: E_Liu + t·T  (t=3 nedopustivo)")
a.plot([4*w for w, _ in W], [b for _, b in W], "s--", color=ORANGE, lw=2, label="po 4w: cijena ideje  (w ≥ 0.26 metoda puca)")
a.plot(1, .87488665, "^", color=AQUA, ms=11, label="Xu–Sang (t=1, w=1/4)")
a.axvline(3, color=BLUE, ls=":", lw=1); a.axvline(1.04, color=RED, ls=":", lw=1)
a.set_xlabel("t   /   4w"); a.set_ylabel("B*"); a.legend(fontsize=8); a.ticklabel_format(useOffset=False)
a = ax[2]; a.set_title("C · Ljestvica zidova na pravoj (naš račun)", loc="left")
lad = [("B > 0.87 (uslov Xu–Sang)", .87007), ("ℓ/h, l_y−ℓ > 11b/6", .86717), ("ℓ ≤ 1/5", .86667),
       ("l_y−ℓ, h/2 < l_y", .86057), ("h/2 < l_y", .85427), ("l_x > ℓ  (≈ 5/6, geometrija)", .83337)]
a.barh([n for n, _ in lad][::-1], [v for _, v in lad][::-1], color=[RED] + [BLUE]*5, height=.55)
for i, (_, v) in enumerate(lad[::-1]): a.text(v + .0005, i, f"{v:.5f}", va="center", fontsize=9)
a.set_xlim(.82, .88); a.set_xlabel("najniže B koje zid dozvoljava"); a.grid(axis="y", visible=False)
save(fig, "fig3_continuity_walls.png")
