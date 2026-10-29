"""
THE EGRESS GATE — every byte this application sends leaves through here.

There is exactly one HTTP function in the whole app (`Egress.request`). The LLM
layer uses it, the scraper uses it, the wizard's connectivity test uses it. That
is not tidiness: it is what makes the Guardian's guarantees true rather than
aspirational. A second HTTP path anywhere would be a hole in all of them at once.

Enforced on every request, in this order:

   1. scheme must be https           — plaintext is refused, never downgraded to
   2. host must be on the allowlist  — default deny (policy.py)
   3. host must not be quarantined   — a tier-2 finding cuts the host off
   4. rate limit                     — our own politeness cap, tightened further
                                       by a tier-1 finding
   5. credential containment         — Authorization/x-api-key ONLY to the four
                                       model APIs; any key material heading to a
                                       literature host blocks the request outright
   6. hardened TLS + SPKI pinning    — see tls.py; a chain sharing no key with the
                                       pinned chain is a hard stop, not a warning
   7. manual redirects, max 3        — every hop re-enters this list at step 1
   8. response caps                  — size, timeout, decompression-bomb guard
   9. observation                    — features go to the Guardian unit, which
                                       scores the seven axes and may intervene

Captive portals are detected rather than walked into: a portal either fails the
pin check (it is a MITM by construction) or answers an API request with HTML,
and both are refused before a key is ever sent.
"""
from __future__ import annotations

import gzip
import http.client
import json
import socket
import ssl
import threading
import time
import urllib.parse
import zlib
from dataclasses import dataclass, field
from typing import Optional

from .. import config
from ..core import journal as J
from . import policy, secrets as SEC, tls
from .anomaly import PacketFeatures, shannon_entropy
from .unit import guardian

USER_AGENT = (f"PSE-Riemann/{config.VERSION} (research assistant; "
              f"single user; contact via mailto param)")


class EgressBlocked(Exception):
    """The gate refused. Message is user-facing and explains the refusal."""


class PinFailure(EgressBlocked):
    """TLS chain did not match the pinned keys — treat as MITM."""


@dataclass
class Response:
    status: int
    headers: dict
    body: bytes
    url: str
    elapsed: float
    pin_state: str = ""

    @property
    def text(self) -> str:
        cs = "utf-8"
        ct = self.headers.get("content-type", "")
        if "charset=" in ct:
            cs = ct.split("charset=", 1)[1].split(";")[0].strip() or "utf-8"
        try:
            return self.body.decode(cs, errors="replace")
        except LookupError:
            return self.body.decode("utf-8", errors="replace")

    def json(self):
        return json.loads(self.text)


class _Bucket:
    """Token bucket, one per host."""

    def __init__(self, rps: float):
        self.rps = max(rps, 0.05)
        self.tokens = 1.0
        self.last = time.monotonic()
        self.lock = threading.Lock()

    def take(self, factor: float = 1.0) -> float:
        with self.lock:
            rps = max(self.rps * factor, 0.02)
            now = time.monotonic()
            self.tokens = min(1.0, self.tokens + (now - self.last) * rps)
            self.last = now
            if self.tokens >= 1.0:
                self.tokens -= 1.0
                return 0.0
            return (1.0 - self.tokens) / rps


def network_id() -> str:
    """
    A cheap fingerprint of the network we are on: default gateway IP + its MAC.
    Used to record WHERE a pin was first learned, so the wizard can tell you
    "you pinned these on a different network than the one you are on now".
    No subprocess, no dependency — just /proc.
    """
    gw = ""
    try:
        with open("/proc/net/route", encoding="utf-8") as fh:
            for line in fh.read().splitlines()[1:]:
                f = line.split()
                if len(f) > 2 and f[1] == "00000000":
                    gw = ".".join(str(b) for b in
                                  int(f[2], 16).to_bytes(4, "little"))
                    break
    except OSError:
        return "unknown"
    mac = ""
    try:
        with open("/proc/net/arp", encoding="utf-8") as fh:
            for line in fh.read().splitlines()[1:]:
                f = line.split()
                if f and f[0] == gw and len(f) > 3:
                    mac = f[3]
                    break
    except OSError:
        pass
    return f"{gw}/{mac}" if mac else (gw or "unknown")


class Egress:
    def __init__(self):
        self._buckets: dict[str, _Bucket] = {}
        self._counters: dict[str, dict] = {}
        self._last_call: dict[str, float] = {}
        self._iat: dict[str, list] = {}
        self._ctx = tls.hardened_context()
        self._lock = threading.Lock()
        self.network = network_id()
        self.learn_pins = True          # wizard turns this off after first run
        self._live: dict = {}           # open streaming connection → its raw socket
        self._killed: set = set()       # hung up by kill_streams()
        self._live_lock = threading.Lock()

    # ------------------------------------------------------------------ #
    def request(self, method: str, url: str, *, headers: Optional[dict] = None,
                body: Optional[bytes] = None, secret_name: str = "",
                auth_style: str = "", max_bytes: int = 0,
                timeout: Optional[float] = None, _depth: int = 0) -> Response:
        """
        The only outbound call in the application.

        `secret_name` names a key in the secret store; the key VALUE is fetched
        here and injected here, so callers never hold it and it cannot end up in
        a log line by accident. `auth_style` is one of: x-api-key, bearer,
        query:<param>.
        """
        t0 = time.monotonic()
        url, headers, host, endpoint, parts, rule, privesc = self._gate(
            method, url, headers, body, secret_name, auth_style)
        max_bytes = max_bytes or config.LIM["max_response_bytes"]
        timeout = timeout or config.LIM["http_timeout"]
        g = guardian()

        # 6-8. connect, pin, fetch
        try:
            resp = self._fetch(host, parts, url, method, headers, body,
                               max_bytes, timeout)
        except PinFailure:
            raise
        except (socket.timeout, TimeoutError) as e:
            self._observe(host, endpoint, 0, 0, 0.0, privesc, ok=False)
            raise EgressBlocked(f"{host}: isteklo vrijeme ({e})") from e
        except ssl.SSLError as e:
            self._observe(host, endpoint, 0, 0, 0.0, privesc + 1, ok=False)
            raise EgressBlocked(
                f"{host}: TLS greška ({e}). Na javnoj mreži ovo je često znak "
                f"presretanja ili captive portala — ne unosi ključeve dok se ne razriješi"
            ) from e
        except (socket.gaierror, ConnectionError, OSError) as e:
            self._observe(host, endpoint, 0, 0, 0.0, privesc, ok=False)
            raise EgressBlocked(f"{host}: mreža nedostupna ({e})") from e

        # 7. redirects — manual, capped, each hop revalidated from step 1
        if resp.status in (301, 302, 303, 307, 308):
            loc = resp.headers.get("location", "")
            if _depth >= 3:
                raise EgressBlocked(f"{host}: previše preusmjeravanja")
            nxt = urllib.parse.urljoin(url, loc)
            nhost = (urllib.parse.urlsplit(nxt).hostname or "").lower()
            if not policy.is_allowed(nhost):
                g.quarantine(host, f"preusmjerava na host van allowliste: {nhost}")
                raise EgressBlocked(
                    f"{host} preusmjerava na '{nhost}' koji nije dozvoljen. "
                    f"Ovo je potpis captive portala ili otetog DNS-a. Host je u karantinu.")
            # a credentialed request never follows a redirect carrying its key
            return self.request(method, nxt, headers=None, body=body,
                                secret_name="", max_bytes=max_bytes,
                                timeout=timeout, _depth=_depth + 1)

        # captive-portal shape: an API call carrying a key that "succeeds" with HTML.
        # An HTML ERROR page (404 on "/", 5xx) is an ordinary error, not an attack —
        # quarantining on it took Gemini down at every start (live test, 0.2.0~rc1).
        ctype = resp.headers.get("content-type", "")
        if rule.klass == policy.CREDENTIALED and "html" in ctype.lower():
            if secret_name and resp.status < 400:
                g.quarantine(host, "API host vratio HTML — captive portal ili presretanje")
                raise EgressBlocked(
                    f"{host} je vratio HTML umjesto JSON-a. Skoro sigurno si iza captive "
                    f"portala. Prijavi se na mrežu pa probaj ponovo.")
            raise EgressBlocked(f"{host}: HTTP {resp.status}, HTML umjesto JSON-a (pogrešan put "
                                f"ili greška servera) — nije napad, host NIJE u karantinu")

        sent = len(body or b"") + sum(len(k) + len(v) for k, v in headers.items())
        self._observe(host, endpoint, sent, len(resp.body),
                      shannon_entropy(resp.body), privesc,
                      ok=True, status=resp.status)
        resp.elapsed = time.monotonic() - t0
        J.log(J.EGRESS, "egress",
              {"host": host, "path": endpoint, "method": method,
               "status": resp.status, "bytes": len(resp.body),
               "ms": int(resp.elapsed * 1000), "pin": resp.pin_state,
               "network": self.network, "replay": _policy_record(host)},
              subject=host, verdict="allow")
        return resp

    def probe(self, host: str, timeout: float = 5.0) -> str:
        """Is the host reachable, untampered? Same gates (allowlist, kill switch,
        quarantine), then TCP + TLS + pin check, and close — no HTTP request, so no
        page can be misread as an attack. Returns the pin state; raises EgressBlocked."""
        url = f"https://{host}/"
        _u, _h, host, _e, parts, _rule, _p = self._gate("GET", url, None, None, "", "")
        try:
            conn, state = self._connect(host, parts, timeout)
        except PinFailure:
            raise
        except (socket.gaierror, ConnectionError, OSError, ssl.SSLError) as e:
            raise EgressBlocked(f"{host}: mreža nedostupna ({e})") from e
        try:
            conn.close()
        except Exception:                               # noqa: BLE001
            pass
        return state

    def _gate(self, method: str, url: str, headers: Optional[dict], body: Optional[bytes],
              secret_name: str, auth_style: str):
        """Steps 1–5 + rate limit, shared by request() and stream(): scheme,
        allowlist, quarantine, credential containment, key-leak scan."""
        headers = dict(headers or {})
        g = guardian()
        parts = urllib.parse.urlsplit(url)
        host = (parts.hostname or "").lower()
        endpoint = parts.path or "/"
        privesc = 0

        # 1. scheme
        if parts.scheme != "https":
            privesc += 1
            self._refuse(host, endpoint, privesc,
                         f"nešifrovana veza odbijena ({parts.scheme or 'bez šeme'}://) — "
                         f"na tuđoj mreži nikad plaintext")

        # 2. allowlist
        rule = policy.rule_for(host)
        if rule is None:
            privesc += 2
            self._refuse(host, endpoint, privesc,
                         f"host '{host}' nije na allowlisti — default deny. "
                         f"Dozvoljeni su samo izvori iz policy.py")

        # 2b. kill switch: when online AI is off, no model host is reachable
        if "llm" in (rule.tags or ()):
            from . import killswitch as KS
            if KS.closed():
                raise EgressBlocked("online AI je ISKLJUČEN (prekidač) — nijedan poziv "
                                    "prema cloud modelu ne izlazi. Uključuje ga samo "
                                    "operater (dugme „Online AI“).")

        # 3. quarantine
        if g.is_quarantined(host):
            self._refuse(host, endpoint, 1,
                         f"host '{host}' je u karantinu poslije tier-2 nalaza. Ako je lažna "
                         f"uzbuna: „Čeka tvoju odluku“ → stavka „Karantin: {host}“ → Odobri "
                         f"(= oslobodi), ili Guardian tab → „Oslobodi host iz karantina“")

        # 5a. credential containment — decide BEFORE building the request
        if secret_name:
            if rule.klass != policy.CREDENTIALED:
                privesc += 3
                self._refuse(host, endpoint, privesc,
                             f"pokušaj slanja ključa '{secret_name}' anonimnom izvoru "
                             f"'{host}' — blokirano (ključevi idu samo model API-jima)")
            if rule.key_env and secret_name != rule.key_env:
                privesc += 3
                self._refuse(host, endpoint, privesc,
                             f"ključ '{secret_name}' ne pripada hostu '{host}' "
                             f"(očekivan: {rule.key_env})")
            key = SEC.store().get(secret_name)
            if not key:
                raise EgressBlocked(f"nema ključa '{secret_name}' — podesi ga u čarobnjaku")
            url, headers = self._inject(url, headers, key, auth_style)

        headers.setdefault("User-Agent", USER_AGENT)
        headers.setdefault("Accept-Encoding", "gzip")
        headers.setdefault("Connection", "close")

        # 5b. no key material may leak to an anonymous host by any other route
        if rule.klass == policy.ANONYMOUS:
            probe = url + "\n" + "\n".join(f"{k}: {v}" for k, v in headers.items())
            if body:
                probe += "\n" + body[:4096].decode("utf-8", "replace")
            if SEC.contains_secret(probe):
                privesc += 3
                self._refuse(host, endpoint, privesc,
                             f"zahtjev prema '{host}' sadrži materijal koji liči na "
                             f"ključ — blokiran u cjelini (ne čistim ga, odbijam ga)")

        # 4. rate limit
        wait = self._bucket(host, rule.max_rps).take(g.rps_factor(host))
        if wait > 0:
            time.sleep(min(wait, 10.0))
        return url, headers, host, endpoint, parts, rule, privesc

    # ------------------------------------------------------------------ #
    # streaming (round 3, item 10): every model call streams, so cutting the
    # connection really stops the generation (and, where the provider honours
    # it, the billing). The same gate as request(); the socket is shut down
    # hard on cancel, on close of the generator, and by kill_streams().
    # ------------------------------------------------------------------ #
    def stream_post(self, url: str, payload: dict, *, headers: Optional[dict] = None,
                    secret_name: str = "", auth_style: str = "",
                    timeout: Optional[float] = None, max_bytes: int = 0,
                    cancel: Optional[threading.Event] = None):
        """Generator of raw response lines (bytes). Close it to hang up."""
        h = dict(headers or {})
        h["Content-Type"] = "application/json"
        h["Accept"] = "text/event-stream"
        body = json.dumps(payload).encode("utf-8")
        url, h, host, endpoint, parts, rule, privesc = self._gate(
            "POST", url, h, body, secret_name, auth_style)
        h["Accept-Encoding"] = "identity"          # line framing needs plain bytes
        timeout = timeout or config.LIM["http_timeout"]
        max_bytes = max_bytes or config.LIM["max_response_bytes"] * 4
        t0 = time.monotonic()
        parts = urllib.parse.urlsplit(url)
        try:
            conn, state = self._connect(host, parts, timeout)
        except PinFailure:
            raise
        except (socket.timeout, TimeoutError, ssl.SSLError, OSError) as e:
            self._observe(host, endpoint, 0, 0, 0.0, privesc, ok=False)
            raise EgressBlocked(f"{host}: veza nije uspostavljena ({e})") from e
        # http.client drops conn.sock once a "close" response arrives, so the raw
        # socket is kept here: it is what a hang-up must shut down.
        with self._live_lock:
            self._live[conn] = conn.sock
        total, status, cancelled, err = 0, 0, False, ""
        try:
            path = urllib.parse.urlunsplit(("", "", parts.path or "/", parts.query, ""))
            conn.request("POST", path, body=body, headers=h)
            r = conn.getresponse()
            status = r.status
            if status >= 400:
                raw = self._read_capped(r, config.LIM["max_response_bytes"], host)
                err = raw.decode("utf-8", "replace")[:600]
                raise EgressBlocked(f"{host}: HTTP {status}: {err}")
            while True:
                if cancel is not None and cancel.is_set():
                    cancelled = True
                    break
                try:
                    line = r.readline(1 << 16)
                except (OSError, ValueError, AttributeError,
                        http.client.HTTPException) as e:
                    # kill_streams() shut the socket under us — that is a hang-up
                    if self._was_killed(conn):
                        cancelled = True
                        break
                    raise EgressBlocked(f"{host}: tok prekinut ({e})") from e
                if not line:
                    cancelled = cancelled or self._was_killed(conn)
                    break
                total += len(line)
                if total > max_bytes:
                    raise EgressBlocked(f"{host}: tok prelazi {max_bytes // 1024} KB — prekinut")
                yield line
        except GeneratorExit:
            cancelled = True
            raise
        finally:
            self._hangup(conn)
            with self._live_lock:
                self._killed.discard(conn)
            self._observe(host, endpoint, len(body), total, 0.0, privesc,
                          ok=(200 <= status < 300), status=status)
            J.log(J.EGRESS, "egress",
                  {"host": host, "path": endpoint, "method": "POST", "stream": True,
                   "status": status, "bytes": total, "cancelled": cancelled,
                   "ms": int((time.monotonic() - t0) * 1000), "pin": state,
                   "network": self.network, "replay": _policy_record(host)},
                  subject=host, verdict="allow")

    def _was_killed(self, conn) -> bool:
        with self._live_lock:
            return conn in self._killed

    def _hangup(self, conn) -> None:
        with self._live_lock:
            sock = self._live.pop(conn, None) or getattr(conn, "sock", None)
        if sock is not None:
            try:
                sock.shutdown(socket.SHUT_RDWR)     # FIN now, not when GC runs
            except OSError:
                pass
        try:
            conn.close()
        except OSError:
            pass

    def kill_streams(self) -> int:
        """Hang up every open model stream at once (kill switch). Returns count."""
        with self._live_lock:
            live = list(self._live.items())
            self._live.clear()
            self._killed.update(c for c, _ in live)
        for c, sock in live:
            if sock is not None:
                try:
                    sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
        return len(live)

    def live_streams(self) -> int:
        with self._live_lock:
            return len(self._live)

    def _connect(self, host: str, parts, timeout: float):
        """TCP + TLS + pin check. Returns (connection, pin_state). Raises PinFailure."""
        port = parts.port or 443
        conn = http.client.HTTPSConnection(host, port, timeout=timeout,
                                           context=self._ctx)
        try:
            conn.connect()
            sock = conn.sock
            ok, state, live = tls.check_pins(host, sock, self.network,
                                             learn=self.learn_pins)
            if not ok:
                guardian().quarantine(
                    host, f"TLS pin mismatch ({state}) na mreži {self.network}")
                raise PinFailure(
                    f"⛔ {host}: sertifikat NE odgovara zapamćenom ključu.\n"
                    f"Zapamćeno: {tls.pins().pins(host)[:2]}\n"
                    f"Viđeno:    {live[:2]}\n"
                    f"Na mreži {self.network}. Ovo je ili rotacija sertifikata ili "
                    f"presretanje. Na tuđem WiFi-ju pretpostavi presretanje: prekini "
                    f"rad na ovoj mreži. Ako si siguran da je rotacija: Podešavanje → "
                    f"„Ponovo snimi TLS pinove…“ (ili Guardian tab) — ali samo sa mreže "
                    f"kojoj vjeruješ.")
        except BaseException:
            try:
                conn.close()
            except OSError:
                pass
            raise
        return conn, state

    # ------------------------------------------------------------------ #
    def _fetch(self, host: str, _stale_parts, url: str, method: str,
               headers: dict, body: Optional[bytes], max_bytes: int,
               timeout: float) -> Response:
        # Re-split the URL HERE, from the string we are actually about to send.
        # The caller's copy was parsed before credential injection, so for a
        # query-style key (`?key=…`) it does not contain the credential — using
        # it silently sends an unauthenticated request, which Google reports as
        # "method doesn't allow unregistered callers" and which looks for all
        # the world like a bad key.
        parts = urllib.parse.urlsplit(url)
        conn, state = self._connect(host, parts, timeout)
        try:
            path = urllib.parse.urlunsplit(("", "", parts.path or "/",
                                            parts.query, ""))
            conn.request(method, path, body=body, headers=headers)
            r = conn.getresponse()
            hdrs = {k.lower(): v for k, v in r.getheaders()}
            raw = self._read_capped(r, max_bytes, host)
            data = self._decompress(raw, hdrs.get("content-encoding", ""), max_bytes)
            return Response(r.status, hdrs, data, url, 0.0, state)
        finally:
            try:
                conn.close()
            except OSError:
                pass

    def _read_capped(self, r, max_bytes: int, host: str) -> bytes:
        chunks, total = [], 0
        while True:
            c = r.read(65536)
            if not c:
                break
            total += len(c)
            if total > max_bytes:
                guardian().observe(host, PacketFeatures(privesc_calls=1,
                                                        ingress_bytes=total))
                raise EgressBlocked(
                    f"{host}: odgovor prelazi {max_bytes // 1024} KB — prekinuto "
                    f"(zaštita od preplavljivanja memorije na 4 GB mašini)")
            chunks.append(c)
        return b"".join(chunks)

    @staticmethod
    def _decompress(raw: bytes, encoding: str, max_bytes: int) -> bytes:
        """Incremental inflate with a hard output cap — decompression-bomb guard."""
        enc = (encoding or "").lower()
        if not raw or enc not in ("gzip", "deflate", "x-gzip"):
            return raw
        try:
            d = zlib.decompressobj(zlib.MAX_WBITS | 32 if enc != "deflate" else -zlib.MAX_WBITS)
            out = d.decompress(raw, max_bytes + 1)
            if len(out) > max_bytes:
                raise EgressBlocked(
                    f"dekompresovani odgovor prelazi {max_bytes // 1024} KB — "
                    f"odbijeno kao potencijalna zip-bomba")
            return out
        except zlib.error:
            try:
                return gzip.decompress(raw)
            except (OSError, zlib.error):
                return raw

    # ------------------------------------------------------------------ #
    @staticmethod
    def _inject(url: str, headers: dict, key: str, style: str) -> tuple[str, dict]:
        """
        Put the credential where this provider expects it.

        Header styles are preferred over `query:` wherever the provider supports
        them: a key in a query string ends up in URLs that get logged, echoed in
        error messages, and copied into bug reports. `query:` is kept only for
        APIs that accept nothing else.
        """
        if style == "bearer":
            headers["Authorization"] = f"Bearer {key}"
        elif style.startswith("header:"):
            headers[style.split(":", 1)[1]] = key
        elif style.startswith("query:"):
            param = style.split(":", 1)[1]
            sp = urllib.parse.urlsplit(url)
            q = dict(urllib.parse.parse_qsl(sp.query))
            q[param] = key
            url = urllib.parse.urlunsplit(
                (sp.scheme, sp.netloc, sp.path, urllib.parse.urlencode(q), sp.fragment))
        else:
            headers["x-api-key"] = key
        return url, headers

    def _bucket(self, host: str, rps: float) -> _Bucket:
        with self._lock:
            b = self._buckets.get(host)
            if b is None:
                b = self._buckets[host] = _Bucket(rps)
            return b

    def _refuse(self, host: str, endpoint: str, privesc: int, msg: str):
        self._observe(host, endpoint, 0, 0, 0.0, privesc, ok=False)
        J.log(J.EGRESS, "egress", {"host": host, "path": endpoint, "reason": msg,
                                   "replay": _policy_record(host)},
              subject=host, verdict="block")
        raise EgressBlocked(msg)

    def _observe(self, host: str, endpoint: str, sent: int, got: int,
                 entropy: float, privesc: int, ok: bool, status: int = 0) -> None:
        now = time.monotonic()
        prev = self._last_call.get(host)
        self._last_call[host] = now
        iat = self._iat.setdefault(host, [])
        if prev is not None:
            iat.append(now - prev)
            del iat[:-20]
        var = 0.0
        if len(iat) >= 3:
            m = sum(iat) / len(iat)
            var = sum((x - m) ** 2 for x in iat) / len(iat)
        c = self._counters.setdefault(host, {"n": 0, "auth_fail": 0})
        c["n"] += 1
        if status in (401, 403):
            c["auth_fail"] += 1
        pf = PacketFeatures(
            conns_per_sec=(1.0 / max(now - prev, 0.001)) if prev else 0.0,
            distinct_endpoints=1, shannon_entropy=entropy,
            auth_fail=c["auth_fail"], auth_total=c["n"], privesc_calls=privesc,
            egress_bytes=sent, ingress_bytes=got, interarrival_var=var)
        guardian().observe(host, pf, endpoint)

    # ------------------------------------------------------------------ #
    # convenience
    # ------------------------------------------------------------------ #
    def get(self, url: str, **kw) -> Response:
        return self.request("GET", url, **kw)

    def post_json(self, url: str, payload: dict, **kw) -> Response:
        h = dict(kw.pop("headers", None) or {})
        h["Content-Type"] = "application/json"
        return self.request("POST", url,
                            body=json.dumps(payload).encode("utf-8"),
                            headers=h, **kw)

    def preflight(self, host: str = "api.crossref.org") -> dict:
        """
        Classify the network before you trust it. Run this on arrival at a new WiFi.
        Returns state: online | offline | captive_portal | mitm_suspect
        """
        try:
            r = self.get(f"https://{host}/works?rows=1", max_bytes=200_000)
            state = "online" if r.status < 500 else "degraded"
            return {"state": state, "host": host, "status": r.status,
                    "pin": r.pin_state, "network": self.network}
        except PinFailure as e:
            return {"state": "mitm_suspect", "host": host, "network": self.network,
                    "detail": str(e)}
        except EgressBlocked as e:
            det = str(e)
            state = "captive_portal" if ("portal" in det or "HTML" in det) else "offline"
            return {"state": state, "host": host, "network": self.network,
                    "detail": det}


_EG: Optional[Egress] = None


def _policy_record(host: str) -> dict:
    """What the allowlist said about this host — replayable (round 3, item 6).
    The record covers only the policy part of the decision; rate limits,
    quarantine and pinning are journalled alongside as facts."""
    from ..core import replay as RPL
    from ..core.replay_deciders import policy_sha
    r = policy.rule_for(host)
    return RPL.record("egress.policy", {"host": host, "policy_sha": policy_sha()},
                      {"allowed": r is not None, "klass": r.klass if r else ""})


def egress() -> Egress:
    global _EG
    if _EG is None:
        _EG = Egress()
    return _EG
