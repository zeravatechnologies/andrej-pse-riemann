"""
TLS hardening + SPKI pinning — the single most valuable defense on foreign WiFi.

Threat being addressed
----------------------
You are on a public/hotel/airport network for 20 days. The realistic attacks are
not exotic: a rogue access point, a captive portal that intercepts TLS, DNS
spoofing, or a device on the LAN with a CA it convinced you (or some other app)
to trust. All of them end the same way — your API key and your traffic go through
somebody else's box.

Certificate validation alone does not stop this, because it trusts the SYSTEM CA
store, and the system CA store is exactly what an attacker (or a corporate/hotel
middlebox) subverts. Pinning does stop it: we remember the public keys we saw the
first time we successfully talked to a host, and we refuse to talk to it again
unless one of those keys is still in the chain.

Implementation notes
--------------------
  * We pin the SPKI (SubjectPublicKeyInfo) of EVERY certificate in the verified
    chain — leaf, intermediates, root. A match on ANY of them is accepted, so a
    routine leaf rotation (every ~90 days) does not false-alarm, while a MITM
    (whose chain shares no key with ours) is refused.
  * SPKI extraction is a ~40-line DER walk. No `cryptography` dependency: nothing
    gets installed on the machine before the trip.
  * TOFU (trust on first use) is honest about its one weakness: if the very first
    connection is already MITM'd, we pin the attacker. So the wizard tells you to
    do first-run pinning on a network you trust (home), before you leave.
"""
from __future__ import annotations

import base64
import hashlib
import json
import ssl
import threading
from pathlib import Path
from typing import Optional

from .. import config
from ..core import journal as J


# --------------------------------------------------------------------------- #
# Minimal DER reader — just enough to reach subjectPublicKeyInfo
# --------------------------------------------------------------------------- #
def _der_read(buf: bytes, i: int) -> tuple[int, int, int, int]:
    """Return (tag, header_len, value_start, value_len) of the TLV at offset i."""
    tag = buf[i]
    j = i + 1
    n = buf[j]
    j += 1
    if n & 0x80:
        k = n & 0x7F
        if k == 0 or k > 4:
            raise ValueError("unsupported DER length")
        n = int.from_bytes(buf[j:j + k], "big")
        j += k
    return tag, j - i, j, n


def _der_children(buf: bytes, start: int, length: int) -> list[tuple[int, int, int]]:
    """List of (tag, tlv_start, tlv_end) for the children of a constructed TLV."""
    out, i, end = [], start, start + length
    while i < end:
        tag, hlen, vstart, vlen = _der_read(buf, i)
        out.append((tag, i, vstart + vlen))
        i = vstart + vlen
    return out


def spki_pin(der_cert: bytes) -> str:
    """
    base64(sha256(DER of subjectPublicKeyInfo)) — the HPKP-style pin.

    Certificate ::= SEQUENCE { tbsCertificate, signatureAlgorithm, signature }
    TBSCertificate ::= SEQUENCE { [0] version?, serial, sigalg, issuer,
                                  validity, subject, subjectPublicKeyInfo, ... }
    """
    _, _, cvs, cvl = _der_read(der_cert, 0)
    kids = _der_children(der_cert, cvs, cvl)
    if not kids:
        raise ValueError("empty certificate")
    _, tbs_s, tbs_e = kids[0]
    _, _, tvs, tvl = _der_read(der_cert, tbs_s)
    fields = _der_children(der_cert, tvs, tvl)
    # skip the optional EXPLICIT [0] version tag (0xA0)
    if fields and fields[0][0] == 0xA0:
        fields = fields[1:]
    if len(fields) < 6:
        raise ValueError("malformed tbsCertificate")
    _, s, e = fields[5]                      # subjectPublicKeyInfo
    return base64.b64encode(hashlib.sha256(der_cert[s:e]).digest()).decode()


# --------------------------------------------------------------------------- #
# Pin store
# --------------------------------------------------------------------------- #
class PinStore:
    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path or config.PIN_STORE)
        self._lock = threading.RLock()
        self._data: dict[str, dict] = {}
        self.load()

    def load(self) -> None:
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._data = {}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def pins(self, host: str) -> list[str]:
        return list(self._data.get(host, {}).get("pins", []))

    def trusted_network(self, host: str) -> str:
        return self._data.get(host, {}).get("pinned_on", "")

    def issuer(self, host: str) -> str:
        return self._data.get(host, {}).get("issuer", "")

    def remember(self, host: str, pins: list[str], network: str = "",
                 issuer: str = "") -> None:
        with self._lock:
            entry = self._data.setdefault(host, {"pins": [], "pinned_on": network})
            known = set(entry["pins"])
            # keep the most recent keys; an unbounded set would eventually
            # accept anything this host ever presented
            entry["pins"] = sorted(known | set(pins))[-8:]
            entry.setdefault("pinned_on", network)
            if issuer:
                entry["issuer"] = issuer
            self.save()

    def forget(self, host: str) -> None:
        with self._lock:
            self._data.pop(host, None)
            self.save()

    def hosts(self) -> list[str]:
        return sorted(self._data)


_PINS: Optional[PinStore] = None


def pins() -> PinStore:
    global _PINS
    if _PINS is None:
        _PINS = PinStore()
    return _PINS


# --------------------------------------------------------------------------- #
# Hardened context
# --------------------------------------------------------------------------- #
def hardened_context() -> ssl.SSLContext:
    """TLS 1.2+, hostname checked, certs required, no compression, no weak ciphers."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = True
    ctx.verify_mode = ssl.CERT_REQUIRED
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    try:
        ctx.set_ciphers("ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:!aNULL:!eNULL:!MD5")
    except ssl.SSLError:
        pass
    ctx.options |= ssl.OP_NO_COMPRESSION
    return ctx


class PinMismatch(Exception):
    """Raised when a live chain shares no public key with what we pinned."""


def chain_pins(sock: ssl.SSLSocket) -> tuple[list[str], bool]:
    """
    (SPKI pins, whole_chain). On Python 3.13+ `get_verified_chain()` gives us
    leaf + intermediates + root, and pinning all of them means a routine leaf
    rotation still matches on the intermediate.

    On 3.12 (this laptop's host Python) that call does not exist, so we can only
    see the leaf — and leaf certificates rotate every 60-90 days. Pinning the
    leaf alone would raise a false MITM alarm mid-trip. `whole_chain=False`
    tells check_pins to fall back to issuer identity for that case.
    """
    out: list[str] = []
    whole = False
    try:
        chain = sock.get_verified_chain()          # Python 3.13+
        for cert in chain:
            try:
                out.append(spki_pin(cert.public_bytes()))
            except (ValueError, AttributeError):
                continue
        whole = bool(out)
    except (AttributeError, ssl.SSLError, OSError):
        pass
    if not out:
        der = sock.getpeercert(binary_form=True)
        if der:
            try:
                out.append(spki_pin(der))
            except ValueError:
                pass
    return out, whole


def issuer_id(sock: ssl.SSLSocket) -> str:
    """
    A stable identity for whoever signed the leaf: the issuer RDN, flattened.
    Used only on Python < 3.13, where we cannot see the intermediate's key.

    This is the honest trade: a hotel middlebox or a rogue local CA signs with
    a DIFFERENT issuer, so this still catches the attack we are actually worried
    about. It would not catch a genuine mis-issuance by the same CA — but that
    is a far higher bar than the one this trip is exposed to.
    """
    try:
        cert = sock.getpeercert() or {}
    except (ssl.SSLError, OSError):
        return ""
    parts = []
    for rdn in cert.get("issuer", ()):
        for k, v in rdn:
            parts.append(f"{k}={v}")
    return "|".join(sorted(parts))


def check_pins(host: str, sock: ssl.SSLSocket, network: str = "",
               learn: bool = True) -> tuple[bool, str, list[str]]:
    """
    Compare the live chain against the store.
      (True,  'pinned',   pins)  first sight, remembered
      (True,  'match',    pins)  a known key is still in the chain
      (True,  'rotated',  pins)  leaf key changed but the ISSUER is the one we
                                 recorded — accepted, and the new key learned.
                                 Only reachable on Python < 3.13, where we
                                 cannot see the intermediate to pin it.
      (False, 'mismatch', pins)  neither key nor issuer known — treat as MITM
    """
    live, whole = chain_pins(sock)
    if not live:
        return False, "no-chain", []
    iss = issuer_id(sock)
    known = pins().pins(host)
    if not known:
        if learn:
            pins().remember(host, live, network, iss)
            J.log(J.EGRESS, "guardian.tls",
                  {"host": host, "pins": live, "issuer": iss,
                   "whole_chain": whole, "network": network},
                  subject=host, verdict="pinned")
            return True, "pinned", live
        return False, "unpinned", live
    if set(live) & set(known):
        # a rotated leaf under a known intermediate: absorb the new key too
        if learn and not set(live) <= set(known):
            pins().remember(host, live, network, iss)
        return True, "match", live

    # No key match. On 3.13+ that is decisive — we pinned the whole chain, so a
    # legitimate rotation would still have matched an intermediate. On 3.12 we
    # only ever saw the leaf, so check whether the same CA signed this one.
    known_iss = pins().issuer(host)
    if not whole and iss and known_iss and iss == known_iss:
        if learn:
            pins().remember(host, live, network, iss)
        J.log(J.EGRESS, "guardian.tls",
              {"host": host, "issuer": iss, "network": network,
               "note": "leaf rotated, issuer unchanged — accepted"},
              subject=host, verdict="rotated")
        return True, "rotated", live

    J.log(J.THREAT, "guardian.tls",
          {"host": host, "expected": known, "got": live,
           "expected_issuer": known_iss, "got_issuer": iss,
           "network": network,
           "interpretation": "neither public key nor issuer matches what we pinned"},
          subject=host, verdict="mismatch")
    return False, "mismatch", live


# --------------------------------------------------------------------------- #
# Re-scan (live test rc5, Andrej): pins are learned on first contact — the
# operator is told so, and can learn them again from the menu if something
# goes wrong. Only on a network he trusts.
# --------------------------------------------------------------------------- #
NOTICE_KEY = "tls_pins_notice_ack"


def rescan_hosts() -> list[str]:
    """Every host pinned so far plus the hosts of the chosen models."""
    from ..llm import providers as P
    from ..llm import selection as SEL
    out = set(pins().hosts())
    for mid in (SEL.get_main(), SEL.get_skeptic()):
        pr = P.get(mid or "")
        if pr and pr.host:
            out.add(pr.host)
    return sorted(out)


def rescan(hosts: Optional[list] = None, probe=None) -> list[dict]:
    """Forget each host's pins and learn them again NOW, through the egress (the
    only network path; allowlist, kill switch, journal). A host that cannot be
    reached keeps its old pins — a re-scan never leaves a host less protected.
    Operator only; journalled. Returns [{host, state, ok, detail}]."""
    from ..shared_lib import operator as OP
    who = OP.require_operator()
    if probe is None:
        from .egress import egress
        probe = egress().probe
    from .unit import guardian
    out = []
    for host in (hosts if hosts is not None else rescan_hosts()):
        old = dict(pins()._data.get(host, {}))
        was_q = guardian().is_quarantined(host)
        with pins()._lock:
            pins()._data.pop(host, None)
            pins().save()
        if was_q:
            guardian().release(host, "operater: ponovo snimljeni TLS pinovi")
        try:
            state = probe(host)
            out.append({"host": host, "state": state, "ok": True, "detail": ""})
        except Exception as e:                          # noqa: BLE001 — reported per host
            with pins()._lock:
                if old:
                    pins()._data[host] = old            # keep the old pins
                    pins().save()
            if was_q:
                guardian().quarantine(host, "ponovno snimanje pinova nije uspjelo")
            out.append({"host": host, "state": "", "ok": False, "detail": str(e)[:200]})
    J.log(J.EGRESS, who, {"event": "pins_rescanned",
                          "ok": [r["host"] for r in out if r["ok"]],
                          "failed": [r["host"] for r in out if not r["ok"]]},
          subject="tls-pins", verdict="rescanned")
    return out
