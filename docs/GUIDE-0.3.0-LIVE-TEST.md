# PSE Riemann 0.3.0~rc7 — installation and live test (for Andrej)

This guide is only for you and does not go into the package. Follow it in order: every step has "what you should see", and you write the result in the table at the end (or just dictate it to me).

## 0. What is new in rc2 (after your first live test)

- **Gemini 2.5 no longer cuts answers off.** Thinking gets its own budget on top of the answer limit (rule 48 a).
- **A cut answer** (any provider) gets one retry with twice the limit. If the second one is cut too, the app says so (48 b).
- **The SHARED_LIB voice:**
  - invalid SQL gets one more try with the error, then a plain sentence, never a raw "QueryRefused" (48 c);
  - mission names are links;
  - a question that asks for judgment gets a link "Talk about the mission: X" (47).
- **The reader** has a limit of 200 + the thinking budget. A cut JSON shows in the Laboratory as "reader cut off", not silently as "no reader" (48 d).
- **The Missions tab is a workspace** (42): cards on the left, details, "Where you left off" and the memory upper right, the conversation lower right.
- **A click on a mission starts the agent at once** (43). The agent reads the last choice of papers and the new papers (🆕), and "Give it to read…" hands it more (44).
- **Mission memory** (45–46): the agent proposes it at the end of a session, and you review and save it. It no longer reads the old conversation.

## 1. Installing your package

The package is `~/Desktop/PSE Riemann/pse-riemann-andrej_0.3.0~rc7_amd64.deb`. It replaces rc1, and your results in "PSE Riemann rezultati" stay.

```bash
sudo apt install "$HOME/Desktop/PSE Riemann/pse-riemann-andrej_0.3.0~rc7_amd64.deb"
```

```bash
pse-riemann --selftest
```

**You should see:**
- **✅ SVE PROLAZI** (all pass) at the end;
- "Izdanje: andrej";
- "PSE: svaki agent je jedinica …".

## 2. The live test, step by step

Let the main AI be **Gemini 2.5 Flash** (that is where the problem was), and the skeptic/reader OpenRouter or GGUF, as in rc1.

| # | Do | You should see |
|---|---|---|
| 1 | Chat, SHARED_LIB mode: "which missions do I have?" | sentences; mission names are **links**; a click opens the Missions tab on that mission |
| 2 | Chat, SHARED_LIB mode: a free question (e.g. "how many cards have an arXiv source?") | an answer in sentences, **not** "QueryRefused"; if it fails, a plain sentence, with the detail under "▸ show where from" |
| 3 | Chat, SHARED_LIB mode: "What is the easiest next step for mission 1?" | "the base does not answer that" + a link **"Talk about the mission: …"** |
| 4 | Chat, math mode: a long question | the answer **to the end**, not cut mid-word; if it still is: "[answer cut off: …]" |
| 5 | Laboratory → choose the chat unit | the line **"Reader (last move)"**: write down how many of the last 30 were **cut** |
| 6 | Missions → **click mission 1** | the agent writes the first message itself (what it sees, where you stopped, ≤ 3 questions); the first time it reads all papers |
| 7 | The strip "N of M papers chosen ▾" → untick a couple, fold the strip | "Papers chosen: …" in the conversation; the agent reads the new choice |
| 8 | "Give it to read…" → Full text of an arXiv paper | "Given…"/"Loaded the full text…" in the conversation |
| 9 | Talk 2–3 moves, then **End the conversation** | within seconds, upper right: **Mission memory · unreviewed** with items |
| 10 | Untick one item, double-click to correct another, **Save the memory** | "reviewed"; the items as you left them |
| 11 | Click mission 1 again | the agent starts from the memory ("last time we…"), not from the old conversation; papers = last choice + 🆕 new |
| 12 | Talk about mission 2, then click mission 3 (without "End") | mission 2 gets an "unreviewed" memory (switching missions) |
| 13 | Drag the border between the upper and the lower part | both parts change; the conversation input always visible |
| 14 | Close the app mid-conversation | status line "The mission agent is proposing the session's memory…", then it closes (at most ~30 s) |
| 15 | On the Acer (1366 pixels) | the workspace fits; nothing important off screen |
| 16 | Work normally for **1 hour** | **write down how many Doctor's measures arrived** |

## 3. Calibration (left over from rc1)

θ is still read **literally per move** (rule 40). Write down:

- **Doctor's measures in 1 hour of work:** ___ (which units, which triggers — Laboratory → Doctor's log)
- **Duration of one AI move with the reader:** cloud ___ s, GGUF ___ s
- **Reader cut off** (step 5): ___ of 30
- Did the measures make sense? ___

## 4. The public package (optional)

`pse-riemann_0.3.0~rc7_amd64.deb` is for other people: empty missions, an empty vault and "+ New mission". Do not install it over yours; try it on another computer or in a virtual machine.

## 5. Results

| # | passed? | note |
|---|---|---|
| 1–16 | | |
| calibration | | |

When you are done, tell me the results. Before that (or then) say "push" so I send the local commits, and "merge into main" only when everything is fine (`docs/ZA-ANDREJA.md`).
