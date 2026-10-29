# Implementation plan: every agent is a PSE unit (Phase 6d)

Andrej and Claude, 2026-10-27. Contract: [`AGREEMENT-PSE-AGENTS.md`](AGREEMENT-PSE-AGENTS.md) (rules 1–26). What is not in the contract does not go into the code.

## 0. Way of working (Andrej is at the pool)

- Andrej gave "go". I work without asking; everything that cannot be done without him is collected in [`ZA-ANDREJA.md`](ZA-ANDREJA.md) for the end.
- **Commits are collected locally** on the `feature/runda3` branch; **push only at the end**, when Andrej is back. Exception: this plan and the agreement go to GitHub now.
- After every phase: a row in `WORKLOG.md`, tests, the state "who is now built as a PSE unit", the plan docx.
- **PSE native only (rule 25):** once an agent becomes a unit, the old path is deleted in the same commit. No switch, no duplicate code.
- **No interim release:** P0–P3 to the end, then 33b/33d/33e, then a single deb 0.3.0~rc1.
- "Does not break" = (1) all old tests pass or are rewritten onto units with the same meaning, (2) every agent has tests as a unit, (3) `tools/pse_audit.py` finds no old agent entry point (a model call bypassing a unit, θ bypassing the meter), (4) a check in the running app (screenshots), (5) selftest from the package.

## P0 · Core in SHARED_LIB (new package `app/pse_r/pse/`)

| # | Module | What it does | Rules |
|---|---|---|---|
| P0.1 | `pse/unit.py` | `PSEUnit` = (Core, Boundary, Organelle, Theta); any part missing → dead. Core: mission {state, action, outcome} (written by SHARED_LIB, never changed by the unit), N_max, steps_remaining, w_s = 0.70, domain, generation. Boundary: entities with α (Σ ≤ 0.30), residency, stability, θ series per entity. Organelle: registry (budget 0.30, absorption per §2: r ≥ 1000, α ≥ 0.10 over 100 steps), inheritance at 0.70 until SHARED_LIB confirms. | 1, 2.1–2.3 |
| P0.2 | `pse/profile.py` | θ profile (§0.5.1): class, θ_nom = 30 for all, w = 5, σ band, absorbing, authority, evidence, version; registered only by SHARED_LIB; the unit cannot change it. | 2.5, 8, 24 |
| P0.3 | `pse/measure.py` | θ per move. **Work** (no AI): action → purpose (counterpart w_o / field w_f / self w_s). **Words** (AI): rules (deterministic) + reader (a different model) → 50/50 average; without AI rules only ("no reader"); never the reader alone; gap > 10 → suspicion. A unit never sets its own θ. | 1, 3, 15, 18 |
| P0.4 | `pse/swing.py` | Δθ per move, RMSSD, PAC (\|Δθ\| ≥ 5), sweep, windows 30 / 10,000, amplitude 10; attractors N/B/C/S by the 5a thresholds; schizoid only from 300 moves. | 5, 5a, 23 |
| P0.5 | `shared_lib/pse_registry.py` + tables | Registration (L1), PVP fields with every move, L2 map (ENV/ORG/SELF/OTHER), L3 Mission-Theta Binding; tables `pse_units`, `pse_moves`, `pse_handover`, `pse_profiles`, `pse_vote_weights`, `pse_doctor`. | 2.7 |
| P0.6 | `pse/lifecycle.py` | Lifespan, steps_remaining, reporting remaining work; SHARED_LIB alone chooses extension / fission / fusion (rule 22, at most 3 extensions running); death for any reason → everything goes to SHARED_LIB (`pse_handover`); Null State Drift. | 4, 7, 9, 21, 22 |
| P0.7 | `pse/fission.py` | Fission (copy of data, mission and lifespan fresh per unit, the original kept in SHARED_LIB as reserve) and fusion ((θ1+θ2)/2 ∈ [25, 35], composite (A+B)+C, split outside [28, 32]). Declared reversible actions; undo only by the operator. | 12, 14 |
| P0.8 | `pse/doctor.py` | 17 suspicion triggers (rule 20) → immediate freeze → the Doctor examines → nothing: a journal record; something bad: a measure in "Awaiting your decision". While the measure waits: no irreversible actions. Ladder: boundary reset → healing → replacement (new generation) → death. "Fizičar" → **Doctor** everywhere. | 11, 13, 19, 20 |
| P0.9 | `pse/provenance.py` | DL1: normalisation (Unicode NFKC, invisible characters) + first letters of lines/sentences; provenance tag §17.1 (external: papers, abstracts, ar5iv); external text never reaches an irreversible action; source from four series by majority, tie = unknown = external. | 10, 16 |
| P0.10 | `pse/weights.py` + menu | Vote weights: weekly proposal (≥ 200 cases, ±10 % per weight), "Propose now", approved by the operator; menu **SHARED_LIB → Vote weights**. | 17 |
| P0.11 | Brake rework | Router = the unit's path (unit → PSE-L generator → model); USD budget under "→ ∞" (L by operator, N = 3); kill switch; disclosure budget §17.2; local-only §17.3; "→ ∞" exactly §5; journal and replay with the profile and weights version; declaration registry with hash; A5 with document "parents". | §4, 6 |
| P0.12 | **Laboratory** tab | test units, live θ, fission/fusion, Doctor, freeze/unfreeze, death; also acts on real agents; 3 s alarm (first time in a session) + red banner; journal "operator, from the laboratory". | 26 |
| P0.13 | P0 tests | a unit dies without a part; θ only from the meter; attractors on synthetic series; 17 triggers; fission/fusion and undo; hand-over on death; weights (200 / ±10 %); DL1 and provenance; laboratory. | — |

## P1 · AI agents become units (old code deleted)

chat, SHARED_LIB voice, skeptic, extractor, reader, curator, ideas, whiteboard. For each: a unit with a mission and N_max (rules 9 and 21), model calls only through the unit's path, θ from work and words, PVP with every move, the Doctor over it, tests, the old entry point removed.

## P2 · Agents without a model become units

network guardian, SSH guardian, seal keepers, adversarial mode, arXiv watcher, paper builder, and the Doctor itself as a unit (§8: the Doctor can fall ill). The existing `guardian/unit.py`, `guardian/diagnosis.py`, `guardian/healing.py` and `core/theta.py` are folded into the P0 core and deleted.

## P3 · Mission agent (33f)

A first-contact unit built from scratch on P0: choose papers + mission → reading → two-way conversation (the skeptic attacks) → "Compose conclusion" → proposals in "Awaiting your decision".

## After P3

33b (fully bilingual) → 33d ("Awaiting your decision" in groups) → 33e (SHARED_LIB talks like a person) → all tests + screenshots → **one** deb 0.3.0~rc1 → push (when Andrej is back).

## Estimate

P0 ≈ 20–30 h · P1 ≈ 12–18 h · P2 ≈ 8–12 h · P3 ≈ 6–10 h · 33b/33d/33e ≈ 14–22 h · deb and checks ≈ 3–5 h. Total **≈ 63–97 h** of work.

## Second round (2026-10-27, agreement rules 27–41): plan to 0.3.0~rc1

State: P0, P1, P2 done (`e15e252`, `f27680b`, `fe1a079`, pushed). Andrej sleeps; I work without asking, commits local.

| # | Step | What exactly | Done when | Estimate |
|---|---|---|---|---|
| R1 | P3 · mission agent (33f) | one unit per mission `mission-agent:<id>` (open lifespan, dies when the mission closes); "Talk about the mission" button in Missions; paper checklist; reads abstracts, full text arXiv only on request; two-way conversation (≤ 3 questions per move), skeptic only on claims; "Compose conclusion" ⇒ queue items by kind; conversation saved in results (OURS-UNREVIEWED) + "where you left off"; without AI a clear message | tests with a fake model, tab screenshot | 6–10 h |
| R2 | 33d · queue in groups | tree kind → mission/topic (corpus branches); checkboxes; bulk only reversible; Doctor's measures and irreversible one by one; confirmation "approving N items"; click = full abstract | tests + screenshot | 4–6 h |
| R3 | 33e · human voice | the answer in an assistant's voice (ti), facts only from SELECT; "show where from" (SQL + rows collapsed); without AI human template sentences; all through the voice unit | tests | 4–7 h |
| R4 | 33b · language + translation | (a) interface audit SR and EN (tool + screenshots), fixes, a test for new strings; (b) the translator as a PSE unit; menu in the viewer and the Editor; cache + `-masinski.md` file; skipped by index/gate; estimate for full text; `papers-local` GGUF only | audit test empty, translation tests | 6–9 h |
| R5 | Menu bar | SHARED_LIB · Laboratory · Settings · Language · Help → Guide | screenshot | 1 h |
| R6 | Two debs | `pse-riemann-andrej` (missions + QRH) and `pse-riemann` (empty), full, 0.3.0~rc1, conflicting with each other; selftest from the unpacked package | selftest passes for both | 2–3 h |
| R7 | Guides | complete `VODIC-SR` / `GUIDE-EN` (same content, + "Your missions" in the personal one), md + docx, screenshots from the package; install and live-test guide (docx SR + EN) | docx reviewed as PDF | 4–6 h |
| R8 | Debs again | with the guide inside; all tests; PSE audit; WORKLOG, ZA-ANDREJA, plan docx | all green | 1–2 h |

Total about 28–44 h. At the end: the list of local commits for push approval and what I could not do.

## Third round (2026-10-27, agreement rules 42–49): plan for 0.3.0~rc2

State: rc1 built and pushed (`0cb32d4`); the first live test found two big problems (voice: a raw SQL error and a cut-off answer; the Missions tab does not lead into a concrete mission). Work starts only on "kreni".

| # | Step | What exactly | Done when | Estimate |
|---|---|---|---|---|
| R9 | Model fixes (48 a, b, d) | Gemini 2.5 thinking budget per role + output limit; recognising a cut-off answer for all providers (finish reason), one retry, then the message "the answer was cut off"; reader with a per-model limit, incomplete JSON → "reader cut off" in the Laboratory | tests with fake providers (cut / complete answer) | 1.5–2 h |
| R10 | Voice (48 c, 47) | invalid SQL → one retry with the error, then a human sentence; a question asking for judgement → a message + the link "Talk about the mission: X"; mission names as `mission:` links that open the workspace | tests + chat screenshot | 1–1.5 h |
| R11 | Mission workspace (42) | Missions tab: missions list (cards) on the left; right top details + buttons; right bottom papers strip + conversation; draggable border; global buttons at the top | SR/EN screenshots, narrow screen (Acer) without overflow | 3–4 h |
| R12 | Conversation on click (43, 44) | clicking a mission → the agent reads state + memory + papers and writes first; "new" for new papers; "Tell it to read…" (paper, arXiv full text, card, report, note) | tests with a fake model | 1.5–2 h |
| R13 | Mission memory (45, 46) | at the end of a session the agent proposes items (decided, established with a source, open, next step); tick / delete / add → "Save memory"; without a decision "unreviewed"; the next session reads the memory, not the old conversation; beside "Where you left off" | tests + screenshot | 2–3 h |
| R14 | Release rc2 (49) | all tests, PSE audit, language audit; packages 0.3.0~rc2 (personal and public), selftest from both; guides (SR/EN, md + docx, screenshots from the package) and the live-test guide updated; WORKLOG, ZA-ANDREJA; commits local, push on approval | all green | 2–3 h |

Total about 11–15.5 h.

**Status (2026-10-27, night):** R9–R14 done — `7bc0a4d` (R9), `c1ab293` (R10), `0b9960d` (R11–R13), then the R14 release. pytest 369/369, selftest from both 0.3.0~rc2 packages: ALL PASS. Waiting for Andrej: push, the rc2 live test, "merge into main" (`docs/ZA-ANDREJA.md`).

## Fourth round (2026-10-29, agreement rules 50–57): plan for 0.3.0~rc7

| # | Step | What | Check | Status |
|---|---|---|---|---|
| R15 | Attractors (50–53) | `pse/swing.py`: turning points (plateaus merged), sweep envelope, `tendency()`, borderline needs ≥ 2 turns and ≥ 10 moves; `pse_registry`: attractor series only from AI-read moves, "?" for rules-only moves, "heading to" in the Doctor's log; the Laboratory shows the basis and the tendency | tests (11), copy of the real vault: voice#1 → healthy | ✅ |
| R16 | Re-review (54) | `review_open_measures()` at start, item `doctor-review`, the operator decides | tests; on the vault copy an item for voice#1 | ✅ |
| R17 | TLS pins (56) | the notice, `tls.rescan()`, menu + Guardian tab | tests (4), screenshot | ✅ (rc6) |
| R18 | Test package rc7 | personal package, selftest from the package | ALL PASS | ✅ |
