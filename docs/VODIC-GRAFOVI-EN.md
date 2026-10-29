# Guide: the Grafovi (Graphs) tab

The **Grafovi** tab draws functions and tells you everything the app knows about any point on them. It is modelled on the Android app "Calculus Tools". There the three parts were three tabs; here they are three panels side by side:

| Panel | What it does |
|---|---|
| **Funkcije / Functions** (left) | the list of functions, each in its own colour, and the parameter sliders |
| **Grafovi / Graphs** (middle) | the plot: zoom, move, read-out under the mouse |
| **Kalkulacije / Calculations** (right) | "everything about the point" for the point you click, and calculations on demand |

**Each of the three panels has its own ⤢ button** in its header (next to the titles "Funkcije", "Graf", "Kalkulacije"):
- a click spreads that panel over the whole tab and hides the other two;
- the button turns into **⤡**, and a second click brings all three panels back.

The **⤢ spread** button at the top of the tab does the same as the plot's ⤢.

If you need more room, also widen the chat with its own ⤢; Esc always brings the chat back. On a screen with large text (e.g. the Surface at 26 pt) three panels and the chat are cramped. The side panels then get a scroll bar, and it is best to spread the panel you are working in.

---

## 1. Functions

### The project's built-in functions ("+ built-in")

| Function | Level | What a point on it means |
|---|---|---|
| B(ℓ) = 11/12 − ℓ/4 | RAD (paper) | the common line: for a given ℓ, the boundary B. 11/12 is ℓ = 0, 7/8 is ℓ = 1/6 |
| E_Liu(δ) at the optimum | RAD | the high-side exponent (Liu) in δ. If max ≤ 0, the method passes |
| E_XS(δ) at the optimum | RAD | the same for Xu–Sang; E_XS = E_Liu + T |
| max_δ E_Liu(ℓ) | NAŠE-NERECENZIRANO (ours, unreviewed) | the worst δ for a given ℓ; its zero is the method boundary ℓ* |
| B*(t) — extension t | ours, unreviewed | the method boundary along extension t (mission 1) |
| B*(w) — extension w | ours, unreviewed | the boundary along the weight w (w = 0.25 is Xu–Sang) |

B*(t) and B*(w) are expensive: about 4.6 s and 1.9 s per point on the Dell (on the Acer, an estimate of about 1.8 times slower). They are drawn in the background from 9 points; meanwhile the plot title shows "računam: …" (computing).

### Your own functions ("+ function")

Pick a kind and type an expression:

| Kind | Variable | Example |
|---|---|---|
| real y = f(x) | `x` | `11/12 - x/4` · `x**3 - 2` · `sin(30*x)/x` |
| complex w = f(s) | `s` | `zeta(s)` · `gamma(s)*zeta(s)` |
| surface z = f(x, y) | `x`, `y` | `x**2 - y**2` |
| parametric | `u` | `cos(u); sin(u)` (x and y separated by `;`) |
| polar r = f(θ) | `th` | `1 + cos(th)` |

**What is allowed:**
- operations `+ − * / **` (`^` works too);
- functions `sin cos tan exp log sqrt abs atan asin acos sinh cosh tanh re im arg conj floor min max zeta Z gamma`;
- constants `pi e i`;
- the sliders `l b k t w d low delta`.

Everything else is refused **before** anything is compiled: attributes, imports, lists, text and the like. So typed text can do nothing but arithmetic. A huge number (e.g. `10**10**10`) becomes a gap in the curve, not a frozen computer.

The domain "from/to" is used by calculations (roots, area, shift to a target). Typed functions are drawn across the whole view.

**Editing:**
- double-click or "Edit" changes a function; "Colour" picks its colour; "Remove" deletes it;
- the tick shows or hides it;
- the list is kept in SHARED_LIB, so it survives a restart and is part of a mission's "where you stopped" note.

### Sliders (parameters)

ℓ, b, κ, t, w, d, **low side** and **Δ**. Moving a slider redraws at once. Next to "low side" the app shows **σ\* = 11/16 + low side**. The low-side slider is prepared for step 4 of this item (linked views); in an expression you use a slider by its name, e.g. `11/12 - x/4 + low`.

---

## 2. Moving around the plot

| You want to | Mouse | Keyboard (click the plot first) | Button |
|---|---|---|---|
| move left / right | drag with the left button | ← / → | ◀ / ▶ |
| move up / down | drag with the left button | ↑ / ↓ | ▲ / ▼ |
| a bigger step | — | **Shift** + arrow (40 % instead of 10 %) | — |
| zoom in / out | wheel (around the cursor) | + / − | + / − |
| back to the starting view | — | Home | ⌂ |

Dragging moves the view. **A click without dragging** on a curve picks the point. **A double-click** on a curve opens its source card, if it has one.

**Targets** (dashed lines 7/8, 0.87, 5/6, 3/4, 1/2) and **walls** (red dotted lines B ≥ 0.87 and ℓ ≤ 1/5) are switched on and off with the ticks at the top.

The plot title always shows the **level** of what is drawn, e.g. "nivo: KORISNIK · RAD".

---

## 3. Everything about the point

**When you hover** over a curve, the line below the plot shows: which function, the coordinates, the level, and the nearest target with the difference.

**When you click** a curve, the Calculations panel shows everything known about that point:
- the coordinates x and y;
- which function or method, its level, and a link to its source card (a click opens the card);
- what the point **means** (e.g. "ℓ → boundary B");
- what kind of point it is: zero, intersection (with which function), wall, stationary point (possible optimum), and for exponents "E ≤ 0: the method passes" or "E > 0: it does not";
- f′ at the point;
- the **distance to every target** (with sign);
- the values of all sliders.

---

## 4. Calculations on demand

Below "everything about the point" there are **at most 4 offers** that fit the kind of point. The rest are under "more…".

| Point | Offer |
|---|---|
| anywhere on a curve | derivative and tangent · second derivative (concavity) · Taylor polynomial |
| intersection | exact intersection + interval certificate |
| zero | exact root (sympy) + interval certificate |
| stationary (f′ ≈ 0) | second derivative: is it an optimum, and how sharp |
| B close to a target | the parameter shift that reaches the target, or proof that the domain or a wall prevents it |
| extension B*(t), B*(w) | which way the extension moves B: closer to or further from the target (mission 1) |
| two functions | the shaded area between them (the "reserve") |

**Duration estimates.** Each offer shows "(odmah)" (at once), "(~N s)" or "(~N min)". The estimate is the number of evaluations needed times the time of one evaluation:
- for typed functions that time is measured;
- for built-ins it was measured on the Dell; the Acer figure is an estimate.

Anything cheap (up to 0.3 s) is computed at once. Anything more expensive is only **offered**, as "Želiš li da izračunam … (~N s)?" (Shall I compute …?).

**How the computing works:**
- **Python computes, deterministically.** An AI only explains, and only when you ask.
- Calculations run **in the background**, one at a time. **Prekini** (Stop) stops them all.
- The background queue respects the limiters: it waits while a "→ ∞" pause is active or while free memory is below 0.5 GB.
- Every result is **cached** (the same calculation a second time is instant) and recorded in SHARED_LIB (table `graph_runs`) with the label **NAŠE-NERECENZIRANO** and your name.

**What the interval certificate means.** f is evaluated in interval arithmetic at the ends of a small interval around the root. If the values have strictly opposite signs **as intervals**, a root certainly exists (rounding cannot fake this). If the interval of the derivative does not contain 0, the root is **unique**. The certificate is available only for typed expressions, because built-ins are code. Example: Liu's cubic `-7884*x**3 + 18819*x**2 - 14643*x + 3686` on the domain [0.87, 0.88] gives the root B\* = 0.874957019420, certified and exact (sympy).

**Taylor polynomial:**
- typed functions go through mpmath at 40 digits;
- built-ins are obtained by a fit on a small symmetric stencil, and the result says so ("estimate").

---

## 5. Views (the "view" drop-down)

| View | What it draws | Example |
|---|---|---|
| **Cartesian** | y = f(x): real and built-in curves, targets, walls, the shaded reserve | B(ℓ), E_Liu(δ), E_XS(δ) |
| **Parametric** | paths (x(u), y(u)) together with curves y = f(x) | the built-in paths (ℓ\*(t), B\*(t)) and (ℓ\*(w), B\*(w)): how the method boundary moves along the line B(ℓ) as the extension grows. An arrow at the end shows the direction of the parameter |
| **Polar** | r = f(θ), with equal axes | `1 + cos(th)`, `cos(3*th)` |
| **Vector field** | a surface z = f(x, y) as colour (blue < 0 < red), the yellow line z = 0, and arrows of steepest descent (−∇f) | the built-in "max_δ E_Liu over (ℓ, κ)" |

**The vector field over (ℓ, κ):**
- the colour is the worst exponent;
- **the yellow line E = 0 is the method boundary** ℓ\*(κ); in the Liu family it lies at ℓ ≈ 0.1668, almost independent of κ;
- the arrows show which way to go for the method to pass (E ≤ 0).

A click on the field gives the value, the gradient, the kind of point by the Hessian (minimum, maximum or saddle), and "if this is the boundary: B = 11/12 − ℓ/4".

**Extension paths** are expensive: about 7 points at 2–4 s each, computed in the background; meanwhile the title shows "računam …" (computing).

**Reserve.** When you compute "shaded area between two functions" in the Cartesian view, the area between them (on their common domain) stays shaded on the plot. Changing the view clears the shading.

### Complex views (step 4)

You need a visible **complex** function: "+ function" → kind "complex" → e.g. `zeta(s)`.

| View | What you see |
|---|---|
| **Complex (phase portrait)** | colour = arg f, brightness = \|f\| (zeros dark, poles bright). **White** lines are Re f = 0, **black** lines Im f = 0, and the zeros are where they cross. Dashed: the critical strip 0 < Re s < 1 and the line 1/2. **Green**: the zero-free half-plane Re s > σ\*. For ζ the known zeros are drawn as small circles |
| **Slice along Re s = 1/2** | \|f(1/2+it)\| (solid), Re (dashed), Im (dotted); for ζ also Hardy's Z(t) (orange), which changes sign at every zero |
| **Linked: exponent plane ↔ ℂ** | on the left the line B(ℓ) and the horizontal σ\*, whose crossing is the method's ℓ; on the right the same σ\* as the edge of the zero-free half-plane. Move a slider and both sides change |

**The "low side + Δ" slider.** σ\* = 11/16 + low side + Δ:
- the low side starts at 3/16, so σ\* = 7/8, i.e. the 7/8 method;
- Δ is an extra loss the method suffers;
- when σ\* reaches 1, **the zero-free region disappears**, and this is written both on the plot and next to the slider;
- the 7/8 method tolerates Δ up to 1/8.

This is the yardstick for the transfer map (mission 2): how much loss a step in higher degree may bring.

**The phase portrait** is computed in the background: a 160×160 grid on the Dell (about 2 s for ζ), 100×100 on the Acer. Meanwhile the title shows "računam …" (computing). Every move or zoom draws a new grid.

**A click on a complex point** gives:
- s, f(s), |f| and arg f;
- the distance to the line 1/2;
- whether the point is in the critical strip or in the zero-free half-plane;
- for ζ, the nearest known zero and the distance to it.

Offers:
- **complex derivative** f′(s);
- **number of zeros in the visible rectangle**: the argument principle (the winding of f along the boundary, refined where the phase jumps); if it is still not sure after refining, it says "NESIGURNO" (unsure). For ζ on [0.1 · 0.9] × [1 · 30] it gives 3 zeros (γ = 14.13, 21.02, 25.01);
- **residue at the point** (circle integral); for ζ at s = 1 it gives 1.

### 3D and more dimensions (step 5)

**The rule:** at most 3 dimensions are on screen. The 4th is colour, and the 5th and beyond are sliders or animation, always visible.

| View | What you see |
|---|---|
| **3D** | a surface above a plane. For a complex f it is \|f(s)\| above ℂ (cut off at 6), **coloured by arg f**: zeros are pits, and the pole of ζ at s = 1 is a spike. For a surface z = f(x, y) the height is z. The built-ins "z = σ" and "z = B(ℓ) over (ℓ, σ)" together give **two surfaces that cross along the curve σ = B(ℓ)** (the yellow line) |
| **Small multiples** | the same picture for **6 values** of the parameter chosen in "5th dim.". For the surface max_δ E over (ℓ, κ) and the parameter b you see how the boundary (yellow) moves with b: it is furthest at b ≈ 0.12 (Liu's optimum) |
| **Parallel coordinates** | all method parameters at once: axes ℓ, b, κ, B, one polyline per method (Liu, Xu–Sang, t = 0.25 / 0.5 / 0.75, w = 0.05 / 0.15 / 0.2). The numbers above and below each axis are its maximum and minimum. Under the mouse you get the exact row. It is computed in the background (8 optima, about 10–40 s) |

**Rotating in 3D:**
- drag with the mouse;
- the arrow keys rotate by 10° (with Shift by 30°);
- the ◀ ▲ ▼ ▶ buttons rotate by 9°;
- ⌂ restores the starting angle.

**Colour (4th dim.):**
- "height / arg f" is the default;
- you can also pick another visible surface; the first surface is then coloured by the values of the second (blue < 0 < red).

**5th dim. and ▶:** pick a parameter (e.g. w or b). **▶** runs it through its range (animation), and **⏸** stops it. Small multiples use the same choice.

The surface max_δ E over (ℓ, κ) is computed for **b from the slider**. The b slider starts at Liu's optimum (≈ 0.1234), so the first picture matches Liu, and moving b really moves the boundary.

**Grid:** 3D is 70×70 on the Dell and 40×40 on the Acer; small multiples are 60×60 and 36×36 per picture.

## 6. Export

- **PNG / SVG**: the plot as on screen, on the dark background, with the level in the title.
- **CSV**: the points of every visible curve in the current view, columns `function, level, x, y`.

---

## 7. Lab plots (step 6)

The plots in the **Lab** tab are now interactive, with the same movement as here:
- the wheel, + and − zoom;
- dragging, the arrow keys (Shift = bigger step) and ◀ ▲ ▼ ▶ move the view;
- ⌂ resets it;
- the value under the mouse is shown below the plot;
- **⤢** gives the plot the whole output area;
- if a run has several plots, you pick one in the "graf:" (plot) menu.

**The PNG stays.** Every run still writes its PNG next to its result, and cards refer to it. The **"Sačuvaj PNG"** (Save PNG) button saves the plot exactly as you see it now (zoomed, moved). **SVG** and **CSV** (the points in view) are there too.

Old runs, made before this step, have no stored plot description, so their PNG is shown.

## 8. What next

Item 29 is complete. This guide becomes part of the full SR/EN guides of the app, written after the .deb and .exe are built.
