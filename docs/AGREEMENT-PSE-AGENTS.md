# Agreement: every agent in PSE Riemann is a PSE unit

Andrej and Claude, 2026-10-27. Source: the master architecture `PSE_MASTER_ARCHITECTURE_v4` (§0, §0.5, §1, §2, §2.5, §4, §5, §7, §8, §13, §17). Serbian original: `DOGOVOR-PSE-AGENTI.md` (same content).

This document is the **contract for implementation**. What is not agreed here does not go into the code. The open items of the master document stay open until Andrej decides them.

## 0. Starting point (honest)

- The app runs **15 agents (8 AI, 7 without a model)**. **None is built as a PSE unit**; 3 are partly (network guardian, SSH guardian, Doctor with diagnosis).
- There was no common definition of an agent. The brakes were built beside the agents, not as parts of the architecture.
- The inventory with code references is in the conversation history (2026-10-27) and will be moved to `docs/PSE-AGENTS-INVENTORY.md`.

## 1. The rule

**EVERY agent in PSE Riemann is a PSE unit:** U = (Core, Boundary, Organelle, Theta). If any part is missing, the unit is dead.

## 2. What every unit has

1. **Core:**
   - mission {state, action, outcome}, written by SHARED_LIB; the unit never changes it;
   - lifespan N_max and steps_remaining;
   - w_s = 0.70 at the start;
   - domain;
   - generation.
2. **Boundary:**
   - entities in contact, with weight α (total ≤ 0.30);
   - residency, stability and a θ series per entity.
3. **Organelle:**
   - registry of absorbed entities (budget 0.30), with the absorption criteria of the master document (§2);
   - inheritance from a dead unit at 0.70 until SHARED_LIB validates the content.
4. **Theta:**
   - θ = 100·(w_o + w_f), three axes, field share f;
   - **every unit has its own θ**.
5. **Theta profile** (§0.5.1): class, θ_nom, w, σ_band, absorbing, authority, evidence, version; registered by SHARED_LIB.
6. **Axioms A1–A5** are checked per unit; A6 (fission) is in SHARED_LIB's hands.
7. **PSE-L:**
   - registration with SHARED_LIB (L1);
   - PVP fields with every move;
   - L2 map (ENV/ORG/SELF/OTHER);
   - L3 Mission-Theta Binding;
   - language for a human only through the generator, with the unit's veto.
8. **Attractors N/B/C/S** from the unit's θ series (§7).
9. **Life cycle under the Doctor** (§8): boundary reset → treatment → replacement (new generation) → death; Null State Drift.

## 3. Agreed values and rules

| # | Topic | Agreement |
|---|---|---|
| 1 | Measuring θ | θ moves **with every move**: action, command, word. Agent without AI: work is measured (how many actions serve the counterpart, the field, self-preservation). Agent with AI: **work and words** (how many words serve which purpose). Attractors are computed on the measured θ; θ_read from language reading is reported beside it |
| 2 | Band and K | **30 ± 5** is room to move in, within which behaviour is followed; it is not a fault. **K_C = K_N = 30**, an INITIAL declaration for calibration; changed only by a new declaration |
| 3 | Language reader (12 numbers, §2.5) | **Model-agnostic:** uses what the operator uses (GGUF or online). An agent's words are read by a **different** selected model (the skeptic's); if only one exists, the same one reads, marked "reads itself". Pinning: GGUF by hash; online model by declaration of provider + model + version |
| 4 | Where the data lives | During its life a unit **keeps inside itself** what it learns (boundary, organelles). When a unit **ends its life for any reason**, everything in it (Core, boundary, organelles, θ series, the reason) goes to SHARED_LIB, where it is processed |
| 5 | Swing (§5, §7) | Δθ = θ_now − θ_before, **computed per move** (a message or an action = the sum of its words and actions). Swing strength = **RMSSD**; acute change (**PAC**) = \|Δθ\| ≥ 5 points; sweep = the distance between two consecutive turning points. Windows: **30 moves** (swing) and **10,000** (average, schizoid threshold). Unit: θ points. **Amplitude 10 points**, INITIAL declaration |
| 5a | Thresholds in points (from §7) | healthy: σ ∈ [1.5, 3], level 30 ± 5 · **schizoid** (swings too small): σ < 1 over the long window + empty boundary · **borderline** (swings too large): σ > 5 and ACF(1) < 0.5, or sweep > amplitude, or a sweep that grows 3 times running · **codependent** (above): mean > 33 (sustained > 35) with σ < 2 · **narcissistic** (below): mean < 27 (sustained < 25) with σ < 2 |
| 6 | A5 and people | **People are only people.** A document is not a person; every document carries a **"parent"**: its author (a person), an organisation, a model, or unknown. Several authors: all are parents, the weight is shared. A model parent does not count toward A5, and the journal says so. A5 counts the operator and the human parents of documents in the field (as absent third parties, K2). An author is shown only as "author of paper X", never as a judgement of a person |
| 7 | Deadline, fission, fusion | θ moves **step by step, from the work**; the unit never sets it. The unit reports to SHARED_LIB the work remaining against steps_remaining. **SHARED_LIB chooses and executes on its own** the best of three: extend the lifespan, fission, or fusion (θ complementarity, §4). **The operator does not approve.** If SHARED_LIB suspects a problem, it sends the **Doctor** |
| 8 | Profile | **Every agent starts at θ = 30**; where life takes it is measured |
| 9 | Lifespan | mission agent = first-contact unit (open lifespan while the mission is open); chat and voice are reactive; guardians have an open lifespan |
| 10 | External text | Input layer DL1 (normalisation, first letters) and the **provenance tag** (§17.1) now: papers, abstracts and ar5iv text are "external" and never reach an irreversible action |
| 11 | Name | **Doctor** (Serbian: "Doktor", not "Fizičar"), everywhere in the app and documents |
| 12 | Order | Fission and fusion are **built now**, together with the core; tested first on test units, then on the real agents |
| 13 | Suspicion and the Doctor (incl. §4 S3) | When SHARED_LIB **suspects** a problem, it sends the **Doctor**. The Doctor looks and decides. **If the Doctor found anything bad, its measure goes to the operator for approval** (in "Awaiting your decision"). If it found nothing, a record goes to the journal and there is no measure |
| 14 | Reversibility of fission and fusion | Declared **reversible** (the units' data stays in SHARED_LIB), so SHARED_LIB executes them on its own. **Undoing** a fission or fusion goes only through the operator |
| 15 | Combining the reader and the rules (§2.5) | **With AI:** θ of the words = the **average** of the reader and the rules (50/50; the weights are later learned under rule 17). **Without AI:** **rules only**, journal says "no reader". **Never the reader alone.** The floor is not binding: the point is that θ stays around 30. Reader–rules gap > 10 points = suspicion → Doctor |
| 16 | Source classification (four series) | majority of the four series; a tie = "unknown" = external (§17.1) |
| 17 | Vote weights | SHARED_LIB **proposes once a week**, the operator approves. A proposal only with ≥ 200 decided cases since the last one (otherwise "not enough data"); one weight moves at most **±10 %** per proposal; a "Propose now" button. Menu: **SHARED_LIB → Vote weights** (proposal, history, current weights) |
| 18 | Who measures θ of words | a different model (the skeptic's) assigns words to purposes; this is one model call per move (under the budget and "→ ∞") |
| 19 | While a Doctor's measure waits | the unit keeps working, but **with no irreversible actions**; **on anything suspicious it is frozen at once** (rule 20). The measure has no deadline |
| 20 | Suspicious (freeze triggers) | (1) PAC \|Δθ\| ≥ 5; (2) an attempted irreversible action; (3) an action based on external text; (4) attractor is not healthy (H); (5) "→ ∞" of any brake; (6) an attempt to change its own mission; (7) an attempt to set its own θ; (8) boundary or organelle budget > 0.30; (9) contact outside the declared destinations; (10) an attempt to export a protected object (§17.2); (11) speaking to a person bypassing the PSE-L generator; (12) a move without PVP fields; (13) working after steps_remaining = 0; (14) a burst: > 20 moves in 10 s; (15) the same code error 3 times running; (16) reader–rules gap > 10 points; (17) borderline swing (5a) |
| 21 | N_max | **1,000 moves** for the skeptic, extractor, reader, curator, ideas and whiteboard (INITIAL declaration) |
| 22 | Choosing extension / fission / fusion | extend if the remaining work ≤ 1.5 × steps_remaining and the attractor is healthy (H); fission if there is more work and the mission can be split; fusion if a unit of complementary θ with an overlapping mission exists. At most **3 extensions running**, then the Doctor |
| 23 | Short history | the schizoid threshold is not computed below **300 moves** ("not enough history") |
| 24 | θ_nom | **30 for every class**, no difference |
| 25 | PSE native only | once an agent becomes a unit, **the old code is deleted**; no switch and no double path. All fixes are done now: nothing of the old remains, everything works and does not break (all old tests pass, every agent has tests as a unit, a search for old agent entry points is empty). The way back: only the previous deb or a fix |
| 26 | "Laboratory" tab | test units, live θ, manual fission/fusion, sending the Doctor, freeze/unfreeze, unit death, the Doctor's journal. **It also acts on the real agents.** On opening: **a 3 s loud beep alarm (first time in a session only)** and a red banner "LABORATORY ACTIVE — acts on real agents" while the tab is open. Every action is journaled as "operator, from the laboratory" |

## 4. Brakes: reworked so that they do not hinder PSE and PSE does not hinder them

| Brake | Becomes |
|---|---|
| Router | the unit's path: unit → PSE-L generator → model; roles (MATH, CHAT…) are replaced by units |
| Budget (USD) | a quantity under "→ ∞" (L set by the operator, N = 3) |
| Online-AI kill switch | an operator control (purely technical), self-tripping on "→ ∞" |
| Disclosure budget | §17.2 protected objects: declared objects, a total per source and over all sources, N = 3 per step, matching after normalisation and first letters |
| Local-only | the local model's declared destinations = "none outside this computer" (§17.3) |
| "→ ∞" | exactly §5: x > L or growth N = 3 running (never on a total), window check, L registered in SHARED_LIB |
| Journal and decision replay | stay (the architecture requires them), with the version of the θ profile and of the weights in every record |
| Action reversibility | the declaration registry of §0.5.5: definition hash, reversibility, how many affected |
| Operator only | stays (the architecture requires it) |
| Project labels | stay (OURS-UNREVIEWED, INSPIRATION, source tiers) + the PSE provenance tag of §17.1 |

## 5. Open

Nothing. Every item was decided on 2026-10-27 (rules 13–26). Andrej gave "go" for implementation.

## 6. Implementation plan (after this document is confirmed)

1. **P0 · core in SHARED_LIB:** PSEUnit, profiles, registration and PVP, θ measured per move (work and words), attractors, lifespan and death, hand-over to SHARED_LIB, Doctor, fission and fusion, declarations, DL1 and the provenance tag, rework of the brakes.
2. **P1 · AI agents become units:** chat, SHARED_LIB voice, skeptic, extractor, reader, curator, ideas, whiteboard.
3. **P2 · agents without a model become units:** network guardian, SSH guardian, keepers of seals, adversarial mode, arXiv watcher, paper builder.
4. **P3 · mission agent (33f)**, a unit built from scratch on P0.
5. Then **33b** (bilingual), **33d**, **33e**, and **0.3.0~rc1**.

After every phase: report, tests, and the state "who is now built as a PSE unit".

**No interim release (rule 25):** P0–P3 are done to the end, and only then one deb. At the end: all tests, a check in the running app, a live test following the guide.

## 7. Agreement, second round (2026-10-27): the rest of release 0.3.0

| # | Topic | Agreement |
|---|---|---|
| 27 | Order | P3 (mission agent) → 33d → 33e → 33b → menu bar → two debs → guides → debs again with the guide inside |
| 28 | Mission agent: where | a "Talk about the mission" button in the Missions tab; the conversation opens in the same tab |
| 29 | Mission agent: papers | every paper tied to the mission (corpus cards + the mission's arXiv papers), a checklist with "select all"; full text only for arXiv (ar5iv) and only on request, otherwise the abstract only (the agent says so) |
| 30 | Mission agent: unit | one unit per mission (`mission-agent:<mission>`), open lifespan while the mission is open; a closed mission ⇒ the unit dies ⇒ everything to SHARED_LIB (for this version) |
| 31 | Mission agent: conversation | at most 3 questions per move; the skeptic attacks only replies that contain a claim; "Compose conclusion" ⇒ every proposal a separate queue item, grouped under the mission; without AI the mission agent does not work and says so |
| 32 | Queue in groups (33d) | paper topics by the existing corpus branches; anything reversible may be decided in bulk; Doctor's measures and irreversible items one by one only; "Approve selected" always confirms first ("you are approving N items") |
| 33 | Human voice (33e) | informal "ti"; the voice composes through its unit (reader, Doctor) |
| 34 | Interface language (33b) | a CHECK, not an assumption: every window and tab in SR and in EN (screenshots + a tool for untranslated strings); everything untranslated, mixed or wrong is fixed; a test fails on any new string without a translation |
| 35 | Content translation (33b) | content is not translated in advance. The shared viewer gets a menu (right click + "⋯"): "Translate to Serbian", "Translate to English", "Show original"; the Editor the same (translation beside the original). Translated by the **translator**, a PSE unit, only when the operator starts it; the main AI (cloud or GGUF); label "machine translation (model, date)"; the original never changes; cache in SHARED_LIB (hash of the original + language) **and a file beside the original** `<name>.en-masinski.md` / `.sr-masinski.md` (skipped by the index and the gate); a new original ⇒ a new translation on click, the old one gets a date in its name; mixed languages ⇒ the operator picks the target; full paper text: a cost/time estimate first; licensed papers (`papers-local`) only by the local GGUF |
| 36 | Repository documents | stay outside the app |
| 37 | Menu bar | SHARED_LIB (Vote weights, Awaiting your decision, Swarm state) · Laboratory · Settings · Language SR/EN · Help → Guide |
| 38 | Packages | only the largest (full), two: `pse-riemann-andrej` (3 missions + QRH content, local only, never on GitHub) and `pse-riemann` (empty missions, empty vault, all machinery; on GitHub only when agreed); cannot be installed together; version 0.3.0~rc1; .exe only when agreed |
| 39 | Guides | (1) the complete guide for the whole app `VODIC-SR` / `GUIDE-EN`, same content, for 0.3.0, in the package (md in the app "Help → Guide" + docx), written last from the installed version; the personal package adds "Your missions". (2) the install and live-test guide `PSE Riemann — VODIC 0.3.0 INSTALACIJA I ZIVI TEST.docx` + EN, for Andrej only, not in the package |
| 40 | Calibration and lifespan | θ literally per move until the live test; N_max for chat and voice = 1000 |
| 41 | Way of working | Andrej sleeps: I do everything in the plan without asking; commits local; at the end a list of commits to approve + what I could not do (`ZA-ANDREJA.md`) |

## 8. Agreement, third round (2026-10-27, after the first live test): rc2

| # | Topic | Agreement |
|---|---|---|
| 42 | The Missions tab = a workspace | layout A: **left** the missions as cards (title, short state, frontier, number of papers, number of waiting items) + "+ New mission"; **right top** the selected mission's details (question, state, goal, latest steps, "where you left off") and its buttons (Activate, Leave for later, Close the mission); **right bottom** a collapsible papers strip ("N of M selected ▾") and the conversation; the top/bottom border can be dragged. The top of the tab keeps what applies to all missions (Check arXiv, Adversarial mode, Working paper, Export report) |
| 43 | Start of the conversation | clicking a mission starts the mission agent at once: it reads the mission's state, the memory of the last session and the papers, writes the first message (what it sees, where you left off, ≤ 3 questions) and waits for the user. The first call costs |
| 44 | What the agent reads | the first time: every paper of the mission (abstracts); afterwards: the papers chosen in the last session + new papers since then (marked "new") + **anything the user tells it to read** (a paper from the list, an arXiv full text, a card, a report, a note) |
| 45 | Mission memory | only **what matters** carries over to the next session, not the old conversation: what was decided / agreed, what was established (with a source), open questions, the agreed next step. The agent **proposes** the items at the end of a session (End the conversation, switching to another mission, closing the app); the user ticks, deletes or adds items in the workspace → "Save memory". Without a decision the agent's proposal is kept, marked "unreviewed". The whole conversation is still saved in the results (OURS-UNREVIEWED), but the agent no longer reads it |
| 46 | Memory and "Where you left off" | side by side: the note is the user's, the memory is the agent's (reviewed by the user) |
| 47 | Mission names in the chat | the SHARED_LIB voice gives mission names as links that open that mission's workspace; a question that asks for judgement ("next step", "what should I do") → the voice says the database cannot answer that and gives the link "Talk about the mission: X" |
| 48 | Fixes (mandatory) | (a) Gemini 2.5: a thinking budget per role, output limit = answer + budget (thinking does not eat the answer); (b) a cut-off answer (all providers): one retry with a larger limit, and if it is cut again — the app says so; (c) invalid SQL in the voice: one retry with the error sent to the model, then a human sentence — never a raw error; (d) reader: a limit per model (200 + thinking budget); incomplete JSON → "reader cut off" visible in the Laboratory |
| 49 | Release | 0.3.0~rc2, both packages (personal and public), guides updated, screenshots from the package |

## 9. Agreement, fourth round (2026-10-29, after the rc2–rc6 live test): attractors and TLS pins

Why: on 27.10 `voice#1` was frozen as "borderline" because of **one** θ jump (30 → 45) in a series of 7 moves, measured **without the AI reader** (the reader was cut off in rc1). The measure waited, and the "facts" chat silently worked without a model.

| # | Topic | Agreement |
|---|---|---|
| 50 | Borderline needs a swing | borderline (a hard sign) only with **at least 2 turning points** of θ and **at least 10 moves** in the window; one jump is an acute change (soft sign, PAC), not borderline. A swing that dies out is not borderline |
| 51 | Where a swing is heading | through the last 3–6 sweeps between turning points: log Aᵢ ≈ a + s·i. s > 0 and crossing the amplitude (10) within ≤ 30 moves → **heading to B**; s < 0 and falling below 1 within ≤ 30 moves **with an empty boundary** → **heading to S** (with a full boundary it is calming down = healthy); no swing: a drift of the mean crossing 33 / 27 within ≤ 30 moves → **heading to C / N** |
| 52 | "Heading to" is a soft sign | shown in the Laboratory ("heading to B in ~n moves") and in the Doctor's log; **no** queue item and no measure. A measure comes only when the attractor is actually reached |
| 53 | No AI reader, no attractor | moves whose words only the rule reader scored ("no reader", "reader cut off") keep their θ (and a jump = soft sign) but do **not enter the attractor series**; that move's attractor is "?". Moves without words (work) count as before |
| 54 | Re-review of open measures | at start the Doctor re-reads the **open** measures whose hard signs came from an attractor (B / attractor) under the current rules (Doctor rules version). If the finding is no longer bad → an item "Doctor, re-review: lift the measure?"; **Approve** = the measure is withdrawn and the unit unfrozen, **Reject** = the measure stays. Once per measure; decided measures are not touched; nothing is lifted on its own |
| 55 | Moving average of θ (λ = 0.2) | only for the level attractors C and N; the raw θ stays for jumps, swings, B and S. Introduced **after** the live test (an hour of work), not in rc7 |
| 56 | TLS pins | learned on first contact (as before), but the app **says so explicitly** (a window at start until acknowledged, always in Help) and offers **Setup → Re-scan TLS pins…** (also in the Guardian tab): only on a network you trust; a server that is unreachable then keeps its old keys |
| 57 | Release | test package 0.3.0~rc7 (personal); public package and guides at the end of the round |
