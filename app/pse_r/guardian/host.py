"""
Host posture check — honest about its own scope.

This application cannot secure your laptop. It can secure ITS OWN surface (traffic,
keys, data), which the rest of the guardian package does, and it can tell you what
the machine currently looks like to the network you are about to join. That second
part is what this module does, before you sit down in an airport.

Everything here is READ-ONLY: /proc and a few config files. Nothing is changed,
no sudo is asked for, no command is executed. Findings come with the exact command
you would run yourself, and you decide.

The check that matters most is `extra_ca_certs`: a locally installed CA is how a
middlebox (corporate proxy, some "security" suites, an attacker who got a moment
with your machine) makes interception invisible to ordinary TLS validation. Our
pinning defeats it for our own traffic, but its presence is worth knowing about.
"""
from __future__ import annotations

import os
import stat
from dataclasses import dataclass, field
from pathlib import Path

from .. import config

INFO, WARN, HIGH = "info", "warn", "high"

_WELL_KNOWN = {
    22: ("ssh", HIGH, "SSH sluša na svim interfejsima — na javnoj mreži je meta"),
    445: ("samba", HIGH, "dijeljenje fajlova otvoreno prema mreži"),
    139: ("netbios", HIGH, "NetBIOS otvoren prema mreži"),
    631: ("cups", WARN, "štampanje otvoreno prema mreži"),
    5353: ("avahi/mDNS", WARN, "mDNS objavljuje tvoju mašinu susjedima"),
    3389: ("rdp", HIGH, "udaljena radna površina otvorena"),
    5900: ("vnc", HIGH, "VNC otvoren"),
    8080: ("http-alt", WARN, "servis sluša na 8080"),
}


@dataclass
class Finding:
    key: str
    level: str
    title: str
    detail: str
    fix: str = ""


@dataclass
class Posture:
    findings: list = field(default_factory=list)

    def add(self, *a, **kw) -> None:
        self.findings.append(Finding(*a, **kw))

    @property
    def worst(self) -> str:
        for lv in (HIGH, WARN, INFO):
            if any(f.level == lv for f in self.findings):
                return lv
        return INFO

    def by_level(self, lv: str) -> list:
        return [f for f in self.findings if f.level == lv]

    def to_dict(self) -> dict:
        return {"worst": self.worst,
                "findings": [f.__dict__ for f in self.findings]}


# --------------------------------------------------------------------------- #
def _listening() -> list[tuple[str, int]]:
    """Parse /proc/net/tcp{,6} for sockets in LISTEN (0A) state."""
    out = []
    for fn, v6 in (("/proc/net/tcp", False), ("/proc/net/tcp6", True)):
        try:
            lines = Path(fn).read_text(encoding="utf-8").splitlines()[1:]
        except OSError:
            continue
        for line in lines:
            f = line.split()
            if len(f) < 4 or f[3] != "0A":
                continue
            addr, _, port = f[1].partition(":")
            try:
                p = int(port, 16)
            except ValueError:
                continue
            if v6:
                loopback = addr.upper().endswith("00000001") and addr.count("0") > 20
                ip = "::" if not loopback else "::1"
            else:
                b = int(addr, 16).to_bytes(4, "little")
                ip = ".".join(str(x) for x in b)
                loopback = ip.startswith("127.")
            if not loopback:
                out.append((ip, p))
    return sorted(set(out))


def _ufw_enabled() -> bool | None:
    p = Path("/etc/ufw/ufw.conf")
    if not p.exists():
        return None
    try:
        return "ENABLED=yes" in p.read_text(encoding="utf-8")
    except OSError:
        return None


def _extra_ca_certs() -> list[str]:
    out = []
    for d in ("/usr/local/share/ca-certificates", "/etc/ssl/certs/local"):
        dp = Path(d)
        if dp.is_dir():
            out += [str(x) for x in dp.glob("*.crt")] + [str(x) for x in dp.glob("*.pem")]
    return out


def _resolvers() -> list[str]:
    try:
        txt = Path("/etc/resolv.conf").read_text(encoding="utf-8")
    except OSError:
        return []
    return [l.split()[1] for l in txt.splitlines()
            if l.strip().startswith("nameserver") and len(l.split()) > 1]


def check() -> Posture:
    from ..i18n import tr
    p = Posture()

    # 1. locally installed CA certificates — interception enabler
    extra = _extra_ca_certs()
    if extra:
        p.add("extra_ca", HIGH, tr("{0} lokalno instaliranih CA sertifikata").format(len(extra)),
              tr("Lokalno dodat CA znači da neko (proxy, 'security' softver, ili napadač "
                 "koji je imao minut sa mašinom) može presretati TLS nevidljivo za obične "
                 "provjere. Naš pinning to ipak hvata, ali ovo treba da znaš.") + "\n"
              + "\n".join(extra[:5]),
              "ls -l /usr/local/share/ca-certificates/")
    else:
        p.add("extra_ca", INFO, tr("nema lokalno dodatih CA sertifikata"), tr("čisto"))

    # 2. firewall
    ufw = _ufw_enabled()
    if ufw is False:
        p.add("firewall", HIGH, tr("ufw je instaliran ali ISKLJUČEN"),
              tr("Na tuđoj mreži svaki otvoren port je izložen svima na toj mreži."),
              "sudo ufw default deny incoming && sudo ufw enable")
    elif ufw is None:
        p.add("firewall", WARN, tr("ufw nije instaliran"),
              tr("Bez firewalla se oslanjaš na to da ništa ne sluša."),
              "sudo apt install ufw && sudo ufw default deny incoming && sudo ufw enable")
    else:
        p.add("firewall", INFO, tr("ufw uključen"), tr("dobro"))

    # 3. listening services on non-loopback
    listen = _listening()
    if listen:
        rows, worst = [], WARN
        for ip, port in listen:
            name, lv, why = _WELL_KNOWN.get(port, (f"port {port}", WARN,
                                                   "nepoznat servis sluša prema mreži"))
            rows.append(f"  {ip}:{port}  {name} — {tr(why)}")
            if lv == HIGH:
                worst = HIGH
        p.add("listening", worst, tr("{0} servisa sluša izvan loopbacka").format(len(listen)),
              "\n".join(rows),
              "sudo ss -tlnp   # " + tr("vidi ko sluša, pa ugasi šta ti ne treba na putu"))
    else:
        p.add("listening", INFO, tr("ništa ne sluša izvan loopbacka"), tr("najbolji mogući ishod"))

    # 4. IP forwarding
    try:
        if Path("/proc/sys/net/ipv4/ip_forward").read_text().strip() == "1":
            p.add("ip_forward", WARN, tr("IP forwarding je uključen"),
                  tr("Mašina prosljeđuje pakete — rijetko potrebno na laptopu."),
                  "sudo sysctl -w net.ipv4.ip_forward=0")
    except OSError:
        pass

    # 5. DNS
    res = _resolvers()
    if res:
        local = all(r.startswith(("127.", "::1")) for r in res)
        p.add("dns", INFO if local else WARN,
              f"DNS: {', '.join(res[:3])}",
              tr("DNS koji ti daje tuđa mreža vidi svaki domen koji posjetiš i može "
                 "lagati. Naš TLS pinning to ne dozvoljava da postane presretanje, ali "
                 "metapodaci cure.") if not local else tr("lokalni resolver"))

    # 6. our own hygiene
    sf = Path(config.SECRETS_FILE)
    if sf.exists():
        mode = stat.S_IMODE(sf.stat().st_mode)
        p.add("secrets", INFO if mode == 0o600 else HIGH,
              tr("secrets.json ima prava {0}").format(oct(mode)),
              tr("ključevi moraju biti 0600 i van vaulta")
              if mode != 0o600 else tr("ispravno (0600, van vaulta)"),
              f"chmod 600 {sf}" if mode != 0o600 else "")
    else:
        p.add("secrets", INFO, tr("secrets.json još ne postoji"), tr("čarobnjak će ga napraviti"))

    # 7. pins learned on which network
    from .tls import pins as _pins
    from .egress import network_id
    ps = _pins()
    nets = {ps.trusted_network(h) for h in ps.hosts() if ps.trusted_network(h)}
    cur = network_id()
    if ps.hosts():
        if nets and cur not in nets:
            p.add("pins", INFO, tr("pinovi naučeni na drugoj mreži ({0})").format(", ".join(sorted(nets))[:60]),
                  tr("Sada si na {0}. To je dobro: pinovi su naučeni ranije i sada se "
                     "provjeravaju protiv ove mreže — tako i treba.").format(cur))
        else:
            p.add("pins", WARN if cur == "unknown" else INFO,
                  tr("pinovi naučeni na trenutnoj mreži ({0})").format(cur),
                  tr("Ako ovo NIJE tvoja mreža od povjerenja, pinovi ne vrijede ništa: "
                     "naučeni su možda od presretača. Obriši ih i ponovi sa mreže kojoj "
                     "vjeruješ.") if cur != "unknown" else tr("mreža neprepoznata"))
    else:
        p.add("pins", WARN, tr("nijedan TLS pin još nije naučen"),
              tr("Uradi prvi kontakt sa mrežom kojoj vjeruješ (kuća), PRIJE puta. "
                 "Trust-on-first-use vrijedi tačno onoliko koliko vrijedi prva mreža."))

    return p


def summary_line() -> str:
    from ..i18n import tr
    p = check()
    n_high = len(p.by_level(HIGH))
    n_warn = len(p.by_level(WARN))
    if n_high:
        return tr("⛔ {0} ozbiljnih nalaza, {1} upozorenja").format(n_high, n_warn)
    if n_warn:
        return tr("⚠ {0} upozorenja").format(n_warn)
    return tr("✅ host izgleda uredno")
