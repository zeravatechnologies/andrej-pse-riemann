"""
Local GGUF backend — llama-cpp in-process (plan F3, master §8).

The model runs inside this process (no server, no extra port), loaded lazily and
only when actually selected, with every limiter from limits.py applied:

  * sha256 of the weights is checked (master §8): against the operator's
    declaration if there is one; otherwise against the hash PUBLISHED by a known
    source (PUBLISHED below). A match with a published hash is admitted and a
    declaration is proposed to the operator; an unknown, undeclared file is
    refused until the operator declares it (propose_declaration);
  * it will not load unless free RAM ≥ file size + headroom, and it unloads at
    once if free RAM falls under the floor;
  * n_threads = cores − 1, n_ctx capped, one call at a time, per-call timeout,
    a <think> budget and a hard output cap, and repetition cut-off.

Absent llama-cpp, or with no .gguf present, the backend simply reports itself
unavailable — the app then runs with cloud models only, or (no models at all)
with the deterministic checks alone. Nothing here is required for the gate, the
lab or the explorer to work.
"""
from __future__ import annotations

import hashlib
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .. import config
from .backend import Backend, Msg, Reply
from . import limits as L


def have_llama() -> bool:
    try:
        import llama_cpp        # noqa: F401
        return True
    except Exception:           # noqa: BLE001
        return False


def list_models() -> list[dict]:
    """Every *.gguf under DIR_MODELS, with size in GiB (fully-downloaded ones)."""
    out = []
    d = config.DIR_MODELS
    if not d.exists():
        return out
    for p in sorted(d.glob("*.gguf")):
        try:
            gb = p.stat().st_size / (1024 ** 3)
        except OSError:
            continue
        out.append({"name": p.name, "path": str(p), "gb": round(gb, 2)})
    return out


# Hashes published by known sources (HuggingFace LFS sha256), checked 2026-10-25.
PUBLISHED: dict[str, dict] = {
    "DeepSeek-R1-0528-Qwen3-8B-Q5_K_M.gguf": {
        "sha256": "044519a2d9821f9a91fbc8bda4eb2333180842bf56845d130e71144c11a1140e",
        "size": 5851113984,
        "source": "huggingface.co/unsloth/DeepSeek-R1-0528-Qwen3-8B-GGUF"},
}


def propose_declaration(path, sha: str = "", note: str = "") -> Optional[str]:
    """Queue a model declaration for the operator (never applies it). Idempotent:
    no second proposal while one for the same path is open."""
    from ..shared_lib import declarations as DECL
    from ..shared_lib.store import store
    p = str(Path(path))
    for it in store().open_items(DECL.PROPOSAL_KIND):
        if p in it["payload"].get("changes", {}).get("models", {}):
            return None
    sha = sha or sha256_of(Path(p))
    pid = DECL.propose({"models": {p: sha}}, "gguf")
    if note:
        from ..core import journal as J
        J.log(J.SYSTEM, "gguf", {"event": "declaration_proposed", "path": p,
                                 "sha256": sha, "note": note}, subject=pid)
    return pid


def sha256_of(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


class GGUFUnavailable(Exception):
    pass


@dataclass
class _Loaded:
    path: str
    llm: object
    stamp: tuple = ()               # (size, mtime_ns, inode) at admission


class GGUFBackend(Backend):
    """One local model file. `provider` is 'gguf', `model` is the file path."""
    provider = "gguf"
    host = ""                       # local: never touches the egress gate
    key_name = ""
    supports_vision = False

    _lock = threading.Lock()
    _loaded: Optional[_Loaded] = None       # class-level: only one model resident

    def __init__(self, model: str = "", lim: Optional[L.Limits] = None):
        super().__init__(model)
        self.lim = lim or L.Limits.from_settings()

    # -- availability / verification ------------------------------------- #
    def path(self) -> Path:
        return Path(self.model)

    def verify(self) -> tuple[bool, str]:
        """
        Master §8 admission: the weights hash is compared with the operator's
        declaration, or — before any declaration — with the hash published by a
        known source. Unknown and undeclared → refused.
        """
        p = self.path()
        if not p.exists():
            return False, f"GGUF ne postoji: {p}"
        try:
            from ..shared_lib import declarations as DECL
            declared = DECL.model_hash(str(p))
        except Exception:           # noqa: BLE001
            declared = None
        if declared is None:
            actual = sha256_of(p)
            pub = PUBLISHED.get(p.name)
            if pub and pub["sha256"] == actual:
                propose_declaration(p, actual,
                                    f"odgovara objavljenom hash-u ({pub['source']})")
                return True, (f"sha256 odgovara objavljenom ({pub['source']}); "
                              f"deklaracija predložena — potvrdi u „Čeka tvoju odluku“")
            return False, ("nepoznat model: hash nije deklarisan i ne odgovara nijednom "
                           "objavljenom — deklariši ga (Modeli → Deklariši) pa potvrdi")
        actual = sha256_of(p)
        if actual != declared:
            return False, (f"sha256 se ne poklapa sa deklaracijom (deklarisano "
                           f"{declared[:16]}…, fajl {actual[:16]}…) — učitavanje odbijeno")
        return True, "sha256 se poklapa sa deklaracijom"

    def _stamp(self) -> tuple:
        """A changed file (size, mtime or inode) must pass sha256 admission again."""
        try:
            st = self.path().stat()
            return (st.st_size, st.st_mtime_ns, st.st_ino)
        except OSError:
            return ()

    def _model_gb(self) -> float:
        try:
            return self.path().stat().st_size / (1024 ** 3)
        except OSError:
            return 0.0

    # -- loading --------------------------------------------------------- #
    def _ensure_loaded(self):
        if not have_llama():
            raise GGUFUnavailable("llama-cpp nije instaliran")
        cur = GGUFBackend._loaded
        if cur is not None and cur.path == self.model and cur.stamp == self._stamp():
            return cur.llm                  # admitted at load, file unchanged since
        ok, why = self.verify()
        if not ok:
            raise GGUFUnavailable(why)
        if not self.lim.can_load(self._model_gb()):
            raise GGUFUnavailable(
                f"premalo slobodnog RAM-a: treba {self._model_gb():.1f}+"
                f"{self.lim.ram_headroom_gb:.1f} GB, slobodno {L.free_ram_gb():.1f} GB")
        with GGUFBackend._lock:
            cur = GGUFBackend._loaded
            if cur is not None and cur.path == self.model and cur.stamp == self._stamp():
                return cur.llm
            if cur is not None:                     # another model, or this file changed
                self._unload_locked()
            import llama_cpp
            llm = llama_cpp.Llama(
                model_path=self.model,
                n_ctx=self.lim.n_ctx,
                n_threads=self.lim.threads(),
                verbose=False,
                seed=0,
            )
            GGUFBackend._loaded = _Loaded(self.model, llm, self._stamp())
            return llm

    @classmethod
    def _unload_locked(cls):
        if cls._loaded is not None:
            try:
                del cls._loaded.llm
            except Exception:       # noqa: BLE001
                pass
            cls._loaded = None

    @classmethod
    def unload(cls):
        with cls._lock:
            cls._unload_locked()

    # -- the call -------------------------------------------------------- #
    def chat(self, messages, system="", max_tokens=4096, effort="high",
             cancel: Optional[threading.Event] = None) -> Reply:
        """
        Streamed generation under a CallGuard: the timeout covers the wait for
        the slot and the generation itself (A3); repetition, the RAM floor, the
        "→ ∞" pause and an external cancel stop the decode while it runs (A2),
        not after it. Latency and memory feed the live watchdogs (A1).
        """
        def refuse_if_stopped():
            try:
                L.CallGuard(self.lim, cancel=cancel).check()
            except L.Aborted as a:
                raise GGUFUnavailable(str(a)) from None
        refuse_if_stopped()                             # paused / cancelled up front
        from .local_only import local_only
        with local_only(f"gguf:{Path(self.model).name}"):
            return self._chat_local(messages, system, max_tokens, cancel)

    def _chat_local(self, messages, system, max_tokens, cancel) -> Reply:
        llm = self._ensure_loaded()                     # one-time load + sha256: not timed
        guard = L.CallGuard(self.lim, cancel=cancel)    # deadline = wait + generation
        if self.lim.must_unload():
            GGUFBackend.unload()
            raise GGUFUnavailable("slobodan RAM ispod praga — model oslobođen usred reda")
        msgs = []
        if system:
            msgs.append({"role": "system", "content": system})
        kept = L.trim_history(messages, keep_last=16)
        for m in kept:
            msgs.append({"role": m.role, "content": m.text or ""})

        cap = min(max_tokens, self.lim.think_budget + self.lim.max_output)
        parts: list[str] = []
        n_out, stop, raw_stop = 0, "", ""
        wait = guard.remaining()
        if wait <= 0:
            raise TimeoutError("isteklo vrijeme prije početka poziva")
        with L.one_at_a_time(timeout=wait):
            guard.started()
            gen = llm.create_chat_completion(
                messages=msgs, max_tokens=cap, temperature=0.4, seed=0, stream=True)
            try:
                for chunk in gen:
                    ch = (chunk.get("choices") or [{}])[0]
                    piece = (ch.get("delta") or {}).get("content") or ""
                    if piece:
                        parts.append(piece)
                        n_out += 1
                    raw_stop = ch.get("finish_reason") or raw_stop
                    guard.tick("".join(parts) if piece else "")
            except L.Aborted as a:
                stop = a.reason
                if a.reason == "ram":
                    GGUFBackend.unload()
            finally:
                close = getattr(gen, "close", None)
                if close:
                    close()                             # stop llama-cpp decoding now
        spt = guard.finish(n_out)
        text = "".join(parts)
        if stop:
            text = text.rstrip() + f"\n\n[prekinuto: {_STOP_TEXT.get(stop, stop)}]"
        else:
            stop = raw_stop
        return Reply(text, "gguf", Path(self.model).name,
                     self._count_prompt(llm, msgs), n_out, stop,
                     {"stream": True, "s_per_token": round(spt, 4)})

    @staticmethod
    def _count_prompt(llm, msgs) -> int:
        try:
            blob = "\n".join(m["content"] for m in msgs).encode("utf-8")
            return len(llm.tokenize(blob, add_bos=False))
        except Exception:           # noqa: BLE001
            return 0


_STOP_TEXT = {
    "loop": "detektovano ponavljanje",
    "timeout": "isteklo vrijeme poziva",
    "ram": "slobodan RAM ispod praga, model oslobođen",
    "diverging": "„→ ∞“ — memorija iznad granice, pauza do odluke operatera",
    "paused": "„→ ∞“ pauza — čeka operatera",
    "cancelled": "prekinuto spolja",
}
