"""
SHARED_LIB — the overseer (PSE master architecture v4, §3).

SHARED_LIB is not a component beside the others: it IS the orchestrating
intelligence. It sees every process (journal, gate, lab, guardian, models),
remembers everything, and invents nothing. Units never own it.

What lives here:
  operator      the registered human (just a name) — the only one the voice speaks to
  store         mutable SHARED_LIB state: the human queue ("Čeka tvoju odluku"),
                declarations, methods, missions, reports, units
  views         the read-only fact layer: every question asked of SHARED_LIB is a
                SELECT over these views, never free recall
  declarations  facts a guard cannot work out for itself (§0.5.5): propose, then
                a human confirms

The voice (PSE-L generator, §5) is SHARED_LIB's mouth, not a separate overseer.
"""
from .operator import current as current_operator, set_operator, require_operator
from .store import store
from .views import query, QueryRefused

__all__ = ["current_operator", "set_operator", "require_operator", "store",
           "query", "QueryRefused"]
