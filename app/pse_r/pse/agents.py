"""
Every agent of PSE Riemann as a PSE unit [rules 1, 9, 21]: the mission
{state, action, outcome}, the lifespan and the domain SHARED_LIB writes into
each unit's Core at instantiation.

Lifespans: guardians, seal keepers and the Doctor have an OPEN lifespan; the
mission agent is a first-contact unit (open while its mission is open); every
other agent gets N_max = 1000 moves (INITIAL). Chat and the SHARED_LIB voice
are reactive (§2 would give N_max/100 — see ZA-ANDREJA), and take 1000 too.
When a unit's life ends, SHARED_LIB instantiates its successor (next
generation), which inherits its organelles at 0.70.
"""
from __future__ import annotations

from ..pse import constants as K
from ..pse.unit import Mission

# agent key → (mission, n_max, domain, uses_model, splittable)
AGENTS = {
    # with a model (P1)
    "chat": (Mission("razgovor s operaterom", "odgovara uz izvore i provjere",
                     "operater dobija tačan, provjerljiv odgovor"), K.N_MAX_DEFAULT,
             "razgovor", True, False),
    "voice": (Mission("pitanje operatera o bazi", "čita SHARED_LIB (samo SELECT)",
                      "odgovor samo iz baze, sa porijeklom"), K.N_MAX_DEFAULT,
              "SHARED_LIB", True, False),
    "skeptic": (Mission("tvrdnja drugog agenta ili rada", "napada tvrdnju",
                        "slabosti tvrdnje su izrečene prije nego što je operater vidi"),
                K.N_MAX_DEFAULT, "provjera", True, False),
    "extractor": (Mission("rad odobren iz arXiv reda", "izvlači paket metode",
                          "paket prolazi vrata ili je odbijen sa razlogom"),
                  K.N_MAX_DEFAULT, "metode", True, True),
    "reader": (Mission("rad u korpusu", "čita i sažima uz izvore",
                       "prijedlog kartice koji prolazi kapiju"), K.N_MAX_DEFAULT,
               "korpus", True, True),
    "curator": (Mission("prikupljeni izvori", "trijaža i unapređenje",
                        "korpus bez smeća, sa nivoima izvora"), K.N_MAX_DEFAULT,
                "korpus", True, True),
    "ideas": (Mission("nova literatura oko misija", "predlaže inspiracije",
                      "najviše 3 sedmično, napadnute od skeptika"), K.N_MAX_DEFAULT,
              "ideje", True, False),
    "whiteboard": (Mission("crtež operatera", "prepisuje tablu u tekst",
                           "vjeran prepis, operater ga potvrđuje"), K.N_MAX_DEFAULT,
                   "tabla", True, False),
    # without a model (P2)
    "net-guardian": (Mission("mrežni saobraćaj aplikacije", "brani",
                             "integritet očuvan"), None, "mreža", False, False),
    "ssh-guardian": (Mission("SSH prijave na računar", "brani",
                             "integritet očuvan"), None, "ssh", False, False),
    "keepers": (Mission("pečaćeni izvještaji i fajlovi", "čuva i patrolira",
                        "svaka izmjena je otkrivena i vraćena"), None, "pečati", False, False),
    "adversary": (Mission("tvrdnja metode", "traži kontraprimjer brojevima",
                          "bolje B ili kršenje zida, ili certifikat praznine"),
                  K.N_MAX_DEFAULT, "metode", False, True),
    "arxiv": (Mission("arXiv za aktivne misije", "straži jednom dnevno",
                      "novi relevantni radovi u redu za operatera"), K.N_MAX_DEFAULT,
              "arxiv", False, False),
    "paper": (Mission("rezultati misija", "sastavlja radni tekst",
                      "tekst bez nedokazanih tvrdnji, svaki broj sa izvorom"),
              K.N_MAX_DEFAULT, "rad", False, False),
    "doctor": (Mission("jedinice roja", "pregleda i liječi",
                       "zdrav roj; mjere idu operateru"), None, "roj", False, False),
    # 33b: only when the operator starts it
    "translator": (Mission("tekst koji operater želi na drugom jeziku", "prevodi",
                           "vjeran mašinski prevod, original netaknut"), K.N_MAX_DEFAULT,
                   "prevod", True, False),
    # P3
    "mission-agent": (Mission("misija i izabrani radovi", "razgovara s operaterom o misiji",
                              "prijedlozi u „Čeka tvoju odluku“"), None, "misija", True, False),
    # test units for the Laboratory
    "lab": (Mission("laboratorija", "probna jedinica", "provjera jezgra"), 50,
            "laboratorija", False, True),
}

LABELS_SR = {"chat": "chat", "voice": "glas SHARED_LIB-a", "skeptic": "skeptik",
             "extractor": "ekstraktor", "reader": "čitač", "curator": "kurator",
             "ideas": "ideje", "whiteboard": "tabla", "net-guardian": "čuvar mreže",
             "ssh-guardian": "SSH čuvar", "keepers": "čuvari pečata",
             "adversary": "adversarijalni mod", "arxiv": "arXiv stražar",
             "paper": "sastavljač rada", "doctor": "Doktor",
             "mission-agent": "agent misije", "translator": "prevodilac", "lab": "probna jedinica"}
LABELS_EN = {"chat": "chat", "voice": "SHARED_LIB voice", "skeptic": "skeptic",
             "extractor": "extractor", "reader": "reader", "curator": "curator",
             "ideas": "ideas", "whiteboard": "whiteboard", "net-guardian": "network guardian",
             "ssh-guardian": "SSH guardian", "keepers": "seal keepers",
             "adversary": "adversarial mode", "arxiv": "arXiv watcher",
             "paper": "paper builder", "doctor": "Doctor",
             "mission-agent": "mission agent", "translator": "translator", "lab": "test unit"}


def define_all(lib) -> None:
    from ..shared_lib.pse_registry import AgentSpec
    for key, (m, n, dom, model, split) in AGENTS.items():
        lib.define(AgentSpec(key, m, n, dom, model, splittable=split))
