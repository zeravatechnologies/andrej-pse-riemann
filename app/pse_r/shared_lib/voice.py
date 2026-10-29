"""
The voice of SHARED_LIB (plan F4, master §5, §2.5).

SHARED_LIB sees every process and remembers everything; this is the one place it
speaks to a human in natural language. The rules are strict because the subject
(the Riemann zeta function) is the largest magnet for confident nonsense in
mathematics:

  * it speaks ONLY to a registered operator;
  * every answer is produced from a SINGLE read-only SQL query over the fact
    views (views.py), and the operator ALWAYS sees that query;
  * every sentence about the library carries a citation — [card:<id>] or
    [run:<id>] — back to the row it came from;
  * every number in the answer must appear in the returned rows; a number that
    does not is removed and the claim marked UNKNOWN;
  * when there is no row, the answer is "nema u biblioteci" (UNKNOWN), never a
    guess;
  * forbidden internal vocabulary (psel) and proof claims are scrubbed out.

Without a model the voice still works: a small set of canned questions map to
SQL, and the answer is rendered deterministically from the rows — as sentences a
colleague would say (plan 33e), never a dump of rows; the SQL and the rows stay
one click away ("prikaži odakle"). A model, when
present, may draft nicer prose, but it is held to the SAME guarantees — its
numbers are verified against the rows and its proof claims are refused.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Optional

from ..llm import psel
from ..vault import gate as GATE
from . import operator as OP
from . import views as V

# question (lowercased substring) -> (SQL, citation column)
_CANNED: list[tuple[str, str, str]] = [
    ("metod", "SELECT title, tier, status FROM cards WHERE dir='methods' "
              "ORDER BY title", "title"),
    ("misij", "SELECT id, title, state, best_B FROM missions ORDER BY created", "id"),
    ("kartic", "SELECT id, title, status, tier FROM cards ORDER BY updated DESC "
               "LIMIT 50", "id"),
    ("lab", "SELECT run_id, experiment, reading FROM lab_runs ORDER BY created "
            "DESC LIMIT 50", "run_id"),
    ("skeptik", "SELECT id, title FROM pending WHERE kind='skeptic' AND "
                "status='open'", "id"),
    ("čeka", "SELECT id, kind, title FROM pending WHERE status='open' "
             "ORDER BY created", "id"),
]

_NUM_RE = re.compile(r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")


class VoiceRefused(Exception):
    pass


@dataclass
class VoiceAnswer:
    question: str
    sql: str
    columns: list = field(default_factory=list)
    rows: list = field(default_factory=list)
    answer: str = ""
    citations: list = field(default_factory=list)
    unknown: bool = False
    warnings: list = field(default_factory=list)


def _numbers(text: str) -> set:
    return {m.group(0) for m in _NUM_RE.finditer(text or "")}


def verify_numbers(prose: str, allowed: set) -> tuple[str, list]:
    """
    Every number in `prose` must be one of `allowed` (the numbers in the rows).
    Any other is replaced by [UNKNOWN] and reported. This is what stops a drafted
    answer from inventing a value that looks as solid as a real one.
    """
    warns = []
    allowed_norm = {_norm_num(a) for a in allowed}

    def repl(m):
        tok = m.group(0)
        if _norm_num(tok) in allowed_norm:
            return tok
        warns.append(f"broj '{tok}' nije u redovima — zamijenjen [UNKNOWN]")
        return "[UNKNOWN]"

    return _NUM_RE.sub(repl, prose or ""), warns


def _norm_num(s: str) -> str:
    try:
        return repr(round(float(s), 9))
    except (TypeError, ValueError):
        return str(s)


def _canned_sql(question: str) -> Optional[tuple[str, str]]:
    q = (question or "").lower()
    for key, sql, cite in _CANNED:
        if key in q:
            return sql, cite
    return None


def _cite_token(row: dict) -> str:
    if "run_id" in row:
        return f"[run:{row['run_id']}]"
    for k in ("id", "card", "subject"):
        if k in row and row[k]:
            return f"[card:{row[k]}]"
    return "[card:?]"


def _ground(res: dict, question: str) -> tuple[str, list, bool, list]:
    cols, rows = res["columns"], res["rows"]
    if not rows:
        return ("Nema u biblioteci za to pitanje (UNKNOWN).", [], True, [])
    lines, cites = [], []
    for r in rows:
        d = dict(zip(cols, r))
        cite = _cite_token(d)
        cites.append(cite)
        shown = ", ".join(f"{k}={d[k]}" for k in cols
                          if k not in ("id", "run_id") and d[k] not in (None, ""))
        lines.append(f"- {shown or d.get('id') or d.get('run_id')} {cite}")
    note = "" if not res.get("truncated") else "\n(više redova — prikazano prvih)"
    return ("\n".join(lines) + note, cites, False, [])


def _fmt(v) -> str:
    if isinstance(v, float):
        return f"{v:.12g}"
    return str(v)


def human(question: str, res: dict, cites: list) -> str:
    """Plan 33e: the same facts, said like a colleague at work ("ti"), with no
    model. Only values from the rows appear; every sentence keeps its [cite]."""
    from ..i18n import tr
    cols, rows = res["columns"], res["rows"]
    if not rows:
        return tr("Toga nema u biblioteci — nemam red koji bi to potvrdio (UNKNOWN).")
    ds = [dict(zip(cols, r)) for r in rows]
    q = (question or "").lower()
    n = len(ds)
    more = tr(" (prikazujem prve)") if res.get("truncated") else ""

    def cite(i):
        return cites[i] if i < len(cites) else ""
    if "misij" in q and "best_B" in cols:
        parts = []
        for i, d in enumerate(ds):
            b = (tr(", front B = {0}").format(_fmt(d["best_B"])) if d.get("best_B") is not None
                 else tr(", bez fronta"))
            name = d.get("title") or d.get("id")
            st = str(d.get("state") or "")
            st = st if len(st) <= 90 else st[:89] + "…"
            link = mission_link(d.get("id"), name) if d.get("id") else f"„{name}“"
            parts.append(tr("{0} — stanje: {1}{2}").format(link, st, b))
        head = tr("Imaš {0} misiju{1}: ") if n == 1 else tr("Imaš {0} misije{1}: ")
        return head.format(n, more) + "; ".join(parts) + "."
    if "metod" in q and "title" in cols:
        return (tr("U biblioteci je {0} metoda{1}: ").format(n, more) +
                "; ".join(tr("{0} (nivo {1}, {2}) {3}").format(d["title"], d.get("tier"),
                                                                d.get("status"), cite(i))
                          for i, d in enumerate(ds)) + ".")
    if "lab" in q and "experiment" in cols:
        return (tr("Zadnja lab računanja{0}: ").format(more) +
                "; ".join(f"{d['experiment']} — {d.get('reading') or tr('bez očitavanja')} {cite(i)}"
                          for i, d in enumerate(ds[:10])) + ".")
    if ("čeka" in q or "skeptik" in q) and "title" in cols:
        return ((tr("Na tebe čeka {0} stavka{1}: ") if n == 1 else
                 tr("Na tebe čeka {0} stavki{1}: ")).format(n, more) +
                "; ".join(f"{d['title']} {cite(i)}" for i, d in enumerate(ds[:10])) + ".")
    if "title" in cols:
        return ((tr("Našao sam {0} red{1}: ") if n == 1 else
                 tr("Našao sam {0} redova{1}: ")).format(n, more) +
                "; ".join(f"{d['title']} {cite(i)}" for i, d in enumerate(ds[:10])) + ".")
    first = ", ".join(f"{k} {_fmt(v)}" for k, v in ds[0].items() if v not in (None, ""))
    return tr("Našao sam {0} redova{1}; prvi: {2} {3}.").format(n, more, first, cite(0))


# --- rule 47: mission names as links; a judgment question goes to the mission agent --- #
_JUDGMENT = ("sljedeći korak", "sledeći korak", "sljedeci korak", "šta da radim", "sta da radim",
             "šta dalje", "sta dalje", "šta bi trebal", "šta mi preporuč", "preporuči",
             "preporuc", "najlakši", "najlaksi", "najbolji sledeći", "najbolji sljedeći",
             "da li da ", "trebam li", "treba li da", "šta predlažeš", "sta predlazes",
             "what should", "next step", "what do i do", "recommend", "should i",
             "easiest", "what next")


def needs_judgment(question: str) -> bool:
    """A question that asks for a judgment ("the easiest next step", "what should
    I do") — the fact base cannot answer it (rule 47)."""
    q = (question or "").lower()
    return any(k in q for k in _JUDGMENT)


def mission_link(mid: str, title: str = "") -> str:
    """Markdown link `mission:<id>` that opens the mission's workspace."""
    t = (title or mid).replace("[", "(").replace("]", ")")
    return f"[{t}](mission:{mid})"


def _open_missions(question: str) -> list[dict]:
    from . import missions as MIS
    ms = [m for m in MIS.all_missions() if (m.get("state") or "") != "zatvorena"]
    q = (question or "").lower()
    named = [m for m in ms if m["title"].lower() in q or m["id"].lower() in q]
    if not named:                                  # words of the title (≥ 5 letters)
        named = [m for m in ms if any(w in q for w in re.findall(r"\w{5,}", m["title"].lower()))]
    if named:
        return named
    act = MIS.active()
    return sorted(ms, key=lambda m: m["id"] != act)


def judgment_answer(question: str) -> "VoiceAnswer":
    from ..i18n import tr
    ms = _open_missions(question)
    if not ms:
        txt = tr("Baza čuva činjenice, a na pitanje koje traži sud ne odgovara. "
                 "Nema otvorene misije o kojoj bi se razgovaralo — napravi je u tabu Misije.")
    else:
        links = [f"[{tr('Razgovaraj o misiji: {0}').format(m['title'])}](mission:{m['id']})"
                 for m in ms[:5]]
        txt = (tr("Baza čuva činjenice, a na pitanje koje traži sud ne odgovara — "
                  "to je posao agenta misije, koji zna stanje, pamćenje i radove. ") +
               " · ".join(links))
    return VoiceAnswer(question, "", [], [], txt, [], True, [])


def link_missions(prose: str) -> str:
    """[card:<mission id>] → the mission's name as a `mission:` link (rule 47)."""
    from . import missions as MIS
    try:
        titles = {m["id"]: m["title"] for m in MIS.all_missions()}
    except Exception:                               # noqa: BLE001
        return prose
    def rep(mt):
        mid = mt.group(1).strip()
        return mission_link(mid, titles[mid]) if mid in titles else mt.group(0)
    return re.sub(r"\[card:([^\]]+)\]", rep, prose or "")


def _sql_failed(question: str, err: str) -> "VoiceAnswer":
    """Rule 48 c: a human sentence, never the raw error (the error goes to warnings,
    which the operator sees under „prikaži odakle“)."""
    from ..i18n import tr
    txt = tr("Nisam uspio da to pitanje pretvorim u ispravan upit nad bazom ni iz drugog "
             "pokušaja. Probaj ga reći drugačije ili kraće — npr. „koje misije imam“, "
             "„šta čeka moju odluku“, „zadnja lab računanja“.")
    return VoiceAnswer(question, "", [], [], txt, [], True, [f"SQL: {err[:300]}"])


def ask(question: str, translate: Optional[Callable[[str, dict], str]] = None,
        compose: Optional[Callable[[str, dict], str]] = None,
        conn=None) -> VoiceAnswer:
    """
    Answer a question over the fact layer, grounded and cited.

    `translate(question, schema) -> sql`  : optional model NL→SQL. If absent, a
        canned question is matched; if neither, the voice refuses and shows the
        schema so the operator can type SQL (via views.query) directly.
    `compose(question, context) -> prose` : optional model prose draft, held to
        the same guarantees (numbers verified, proof claims and jargon scrubbed).
    """
    OP.require_operator()                       # the voice speaks only to the operator

    if needs_judgment(question):                # rule 47: not a question for the facts
        return judgment_answer(question)
    cite_col = None
    if translate is not None:
        schema = V.schema()
        sql = translate(question, schema)
        try:
            res = V.query(sql, conn=conn)
        except Exception as e1:                 # noqa: BLE001 — rule 48 c: one retry
            try:
                sql = translate(question, schema, error=f"{type(e1).__name__}: {e1}",
                                bad_sql=sql)
            except TypeError:                   # a translate without the error hook
                sql = translate(question, schema)
            try:
                res = V.query(sql, conn=conn)
            except Exception as e2:             # noqa: BLE001
                return _sql_failed(question, f"{type(e2).__name__}: {e2}")
    else:
        hit = _canned_sql(question)
        if hit is None:
            raise VoiceRefused(
                "glas zahtijeva model za slobodno pitanje ili poznato pitanje "
                "(metode / misije / kartice / lab / čeka). Shema je dostupna "
                "(views.schema); operater može upisati SQL direktno.")
        sql, cite_col = hit
        res = V.query(sql, conn=conn)           # read-only enforced by the engine
    _raw, cites, unknown, warns = _ground(res, question)
    prose = human(question, res, cites)          # 33e: a person's sentences, not rows

    if compose is not None and not unknown:
        allowed = set()
        for r in res["rows"]:
            for v in r:
                allowed |= _numbers(str(v))
        draft = compose(question, {"columns": res["columns"], "rows": res["rows"],
                                   "citations": cites})
        draft, nwarn = verify_numbers(draft, allowed)
        warns += nwarn
        # a drafted sentence may not claim a proof of an open problem
        claims, sentence = GATE._claims_proof(draft)
        if claims:
            warns.append(f"nacrt je tvrdio dokaz — odbijeno: „{sentence[:80]}“")
        else:
            prose = draft

    prose = link_missions(psel.scrub(prose))
    return VoiceAnswer(question, sql, res["columns"], res["rows"], prose, cites,
                       unknown, warns)
