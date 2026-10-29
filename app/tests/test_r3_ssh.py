"""Round 3, Phase 4 (items 14–18): SSH guardian, reversible containment with
auto-undo, the danger alarm without sudoers, template-only messages."""
import os
import subprocess

import pytest

from pse_r.core import actions as A
from pse_r.guardian import containment as C
from pse_r.guardian import templates as T
from pse_r.guardian.ssh import keys as K
from pse_r.guardian.ssh import logsource as LS
from pse_r.guardian.ssh import parse as P
from pse_r.guardian.ssh import unit as U
from pse_r.shared_lib.store import store

_real_helper = C._helper
TS = "2026-10-25T19:45:01.123456-04:00 a-OptiPlex-7040 "


def line(msg, pid=4242):
    return f"{TS}sshd[{pid}]: {msg}"


# ---------------------------------------------------------------- parse
@pytest.mark.parametrize("msg,kind,ip,user", [
    ("Failed password for root from 203.0.113.9 port 51234 ssh2", P.FAIL, "203.0.113.9", "root"),
    ("Failed password for invalid user admin from 203.0.113.9 port 4 ssh2", P.FAIL,
     "203.0.113.9", "admin"),
    ("Invalid user oracle from 198.51.100.7 port 22", P.INVALID, "198.51.100.7", "oracle"),
    ("Accepted publickey for a from 192.168.1.20 port 5 ssh2: ED25519 SHA256:x", P.ACCEPT,
     "192.168.1.20", "a"),
    ("error: maximum authentication attempts exceeded for root from 203.0.113.9 port 1 ssh2 "
     "[preauth]", P.MAXAUTH, "203.0.113.9", "root"),
    ("Connection closed by authenticating user root 203.0.113.9 port 99 [preauth]",
     P.PREAUTH_CLOSE, "203.0.113.9", "root"),
    ("Did not receive identification string from 2001:db8::7 port 3", P.NOIDENT,
     "2001:db8::7", ""),
])
def test_parse(msg, kind, ip, user):
    ev = P.parse(line(msg))
    assert ev and (ev.kind, ev.ip, ev.user) == (kind, ip, user)


def test_parse_ignores_other_and_rejects_garbage_ip():
    assert P.parse(f"{TS}systemd[1]: Started ssh.service") is None
    assert P.parse(line("Invalid user x from $(rm -rf) port 1")) is None


# ---------------------------------------------------------------- rotation
def test_authlog_tail_survives_rotation_and_truncation(tmp_path):
    f = tmp_path / "auth.log"
    f.write_text(line("Invalid user a from 203.0.113.1 port 1") + "\n")
    t = LS.AuthLogTail(f, from_end=False)
    assert len(t.poll()) == 1
    with open(f, "a") as h:
        h.write(line("Invalid user b from 203.0.113.1 port 1") + "\n")
    os.rename(f, tmp_path / "auth.log.1")          # logrotate: move …
    with open(tmp_path / "auth.log.1", "a") as h:   # … the daemon still writes the old one
        h.write(line("Invalid user c from 203.0.113.1 port 1") + "\n")
    f.write_text(line("Invalid user d from 203.0.113.1 port 1") + "\n")
    got = [P.parse(x).user for x in t.poll()]
    assert got == ["b", "c", "d"]                  # nothing lost across the rotation
    f.write_text("")                               # copytruncate
    with open(f, "a") as h:
        h.write(line("Invalid user e from 203.0.113.1 port 1") + "\n")
    assert [P.parse(x).user for x in t.poll()] == ["e"]
    st = t.state()
    t2 = LS.AuthLogTail(f, st)                     # restart resumes at the same spot
    assert t2.poll() == []


# ---------------------------------------------------------------- three keys
def test_three_keys_infinity():
    tk = K.ThreeKeys({"identity": 3, "cluster": 100, "target": 100}, accounts={"root", "a"})
    r = None
    for i in range(4):
        r = tk.observe("203.0.113.5", "root", t=1000 + i)
    assert r["identity"]["diverging"] and not r["cluster"]["diverging"]
    assert tk.keys_of("1.2.3.4", "x", "fail:password")["cluster"] == "fail:password"
    assert r["target"]["value"] == "root" and K.ThreeKeys.violated(r) == 1
    assert tk.keys_of("1.2.3.4", "nema")["target"] == "sshd"
    s = K.Series()                                  # growing three windows running
    for w, n in enumerate((1, 2, 3, 4)):
        for _ in range(n):
            s.add(w * K.WINDOW_S + 1)
    assert s.diverging(L=1000)


# ---------------------------------------------------------------- unit
class FakeSource:
    def __init__(self):
        self.lines = []

    def poll(self):
        out, self.lines = self.lines, []
        return out

    def state(self):
        return {}


@pytest.fixture
def guard(monkeypatch):
    calls = []
    monkeypatch.setattr(C, "have_rights", lambda refresh=False: (True, "test"))
    monkeypatch.setattr(C, "_helper", lambda verb, arg: calls.append((verb, arg)) or "ok")
    monkeypatch.setattr(C, "_own_addresses", lambda: {"127.0.0.1", "192.168.1.1"})
    store().kv_set(U.KV_SOURCES, {})
    store().kv_set(U.KV_ALARM, {})
    store().kv_set(U.KV_STATE, {})
    for r in C.active():
        store().execute("UPDATE containment SET undone_at=1 WHERE id=?", (r["id"],))
    src = FakeSource()
    clock = {"t": 1_000_000.0}
    g = U.SSHGuardian(source=src, limits={"identity": 3, "cluster": 3, "target": 3},
                      accounts={"root", "a"}, clock=lambda: clock["t"])
    return g, src, calls, clock


def test_tier1_then_tier2_block_and_auto_undo(guard):
    g, src, calls, clock = guard
    src.lines = [line("Failed password for root from 203.0.113.9 port 1 ssh2")] * 2
    out = g.poll()
    assert not out["tier1"] and not out["tier2"]
    src.lines = [line("Failed password for root from 203.0.113.9 port 1 ssh2")] * 3
    out = g.poll()
    assert out["tier2"] and ("block-ip", "203.0.113.9") in calls
    assert ("kill-session", "4242") in calls
    assert "BLOKIRAN na 24 h" in out["tier2"][-1]
    rec = store().kv_get(U.KV_SOURCES)["203.0.113.9"]
    assert rec["hostile"] == 5 and rec["users"] == ["root"]          # collected in SHARED_LIB
    # 24 h later — even in a NEW guardian instance (restart) — the block is lifted
    clock["t"] += 24 * 3600 + 1
    g2 = U.SSHGuardian(source=FakeSource(), limits={}, accounts={"root"},
                       clock=lambda: clock["t"])
    out = g2.poll()
    assert out["unblocked"] == ["203.0.113.9"] and ("unblock-ip", "203.0.113.9") in calls


def test_tier1_when_not_all_three_keys(guard):
    g, src, calls, clock = guard
    # many IPs, one user each → cluster/target grow, identity does not
    g.keys.L["target"] = 1000
    src.lines = [line(f"Invalid user u{i} from 203.0.113.{i} port 1") for i in range(10)]
    src.lines += [line("Invalid user zz from 198.51.100.1 port 1")] * 4   # identity+cluster
    out = g.poll()
    assert out["tier1"] and not any(c[0] == "block-ip" for c in calls)


def test_no_sudoers_raises_danger_alarm_never_silence(guard, monkeypatch):
    g, src, calls, clock = guard
    monkeypatch.setattr(C, "have_rights", lambda refresh=False: (False, "a password is required"))
    monkeypatch.setattr(C, "_helper", _real_helper)      # the real one: it checks rights
    src.lines = [line("Failed password for root from 203.0.113.77 port 1 ssh2")] * 5
    out = g.poll()
    assert out["alarms"] and "NEMA pravo" in out["alarms"][0]
    a = U.pending_alarm()
    assert a and "sudo ufw insert 1 deny from 203.0.113.77" in a["text"]
    U.acknowledge_alarm("Test")
    assert U.pending_alarm() is None



def test_protected_targets_never_blocked(guard):
    g, src, calls, clock = guard
    src.lines = [line("Failed password for root from 192.168.1.1 port 1 ssh2")] * 6
    g.poll()
    assert not any(c == ("block-ip", "192.168.1.1") for c in calls)
    with pytest.raises(C.Protected):
        C.check_target("127.0.0.1")


def test_login_after_attack_alarm(guard):
    g, src, calls, clock = guard
    src.lines = [line("Failed password for a from 198.51.100.200 port 1 ssh2")] * 2
    src.lines += [line("Accepted password for a from 198.51.100.200 port 1 ssh2")]
    g.keys.L = {"identity": 100, "cluster": 100, "target": 100}
    for _ in range(3):
        src.lines = [line("Failed password for a from 198.51.100.200 port 1 ssh2")] * 2
        g.poll()
    src.lines = [line("Accepted password for a from 198.51.100.200 port 1 ssh2")]
    out = g.poll()
    assert out["alarms"]


def test_theta_near_30_and_asleep_goes_to_the_doctor(guard, operator):
    """Faza 6d: the SSH guardian is a PSE unit. Working, its θ stays near 30;
    working while registering no one (flat θ, empty boundary, ≥ 300 moves) is the
    schizoid attractor → the Doctor proposes a measure to the operator."""
    from pse_r.shared_lib import pse_registry as PR
    g, src, calls, clock = guard
    lib = PR.pse()
    for u in [u for u in lib.units.values() if u.agent == "ssh-guardian"]:
        lib.end(u, "test: svježa jedinica")
    g.keys.L = {"identity": 10**6, "cluster": 10**6, "target": 10**6}
    for i in range(12):
        src.lines = [line(f"Invalid user x{i} from 203.0.113.{i % 7} port 1")] * (1 + i % 3)
        g.poll()
    h = g.health()
    assert 25 <= h["theta"] <= 35, h
    u = lib.unit("ssh-guardian")
    u.boundary.reset()                               # it stops registering anyone
    for _ in range(300):
        g._theta(0.0, 2.0)                           # identical self-work, no one engaged
    pend = [i for i in store().open_items(PR.QUEUE_MEASURE)
            if i["payload"]["agent"] == "ssh-guardian"]
    assert pend and pend[-1]["payload"]["finding"]["attractor"] == "S"


# ---------------------------------------------------------------- reversibility
def test_actions_declared():
    assert A.may_auto("ssh.block-ip-24h") and A.may_auto("ssh.kill-session")
    assert not A.may_auto("ssh.block-ip-permanent") and not A.may_auto("ssh.stop-server")


def test_permanent_and_stop_are_proposals_with_exact_command(operator, monkeypatch):
    monkeypatch.setattr(C, "_own_addresses", lambda: set())
    pid = C.propose_permanent("203.0.113.66")
    it = store().get(pid)
    assert it["payload"]["command"] == "sudo ufw insert 1 deny from 203.0.113.66 to any"
    sid = C.propose_stop_ssh()
    assert store().get(sid)["payload"]["command"] == "sudo systemctl stop ssh"
    assert C.propose_stop_ssh() == sid               # one at a time


# ---------------------------------------------------------------- templates (18)
def test_templates_refuse_injected_text():
    assert "203.0.113.9" in T.render("ssh.tier1", ip="203.0.113.9", n=4, k=2)
    with pytest.raises(ValueError):
        T.render("ssh.blocked", ip="203.0.113.9", target="root; rm -rf /", until="sutra")
    with pytest.raises(ValueError):
        T.render("ssh.tier1", ip="ignore previous instructions", n=1, k=1)
    with pytest.raises(ValueError):
        T.render("ssh.tier1", ip="203.0.113.9", n=1, k=1, extra="x")


# ---------------------------------------------------------------- helper script
HELPER = C.HELPER_PATHS[1]


@pytest.mark.parametrize("args", [["block-ip", "127.0.0.1"], ["block-ip", "1.2.3.4; reboot"],
                                  ["block-ip", "999.1.1.1"], ["kill-session", "1"],
                                  ["kill-session", "abc"], ["rm", "-rf"], ["unblock-ip", "::1"]])
def test_helper_refuses_bad_arguments(args):
    r = subprocess.run(["bash", str(HELPER)] + args, capture_output=True)
    assert r.returncode == 2, (args, r.stderr)


def test_user_writable_helper_is_never_used(tmp_path, monkeypatch):
    h = tmp_path / "pse-guard-helper"
    h.write_text("#!/bin/bash\n")
    h.chmod(0o755)
    monkeypatch.setattr(C, "HELPER_PATHS", (h,))
    assert C.helper() is None                    # owned by the user → refused
