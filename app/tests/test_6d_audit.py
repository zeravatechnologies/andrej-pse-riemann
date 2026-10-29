"""Faza 6d, rule 25: PSE native only — no old agent entry point remains, and every
agent of the app has a PSE unit definition."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_audit_is_clean():
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "pse_audit.py")],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-3000:]


def test_every_agent_is_a_unit():
    from pse_r.pse import agents as AG
    from pse_r.shared_lib import pse_registry as PR
    PR.reset_for_tests()
    lib = PR.pse()
    expected = {"chat", "voice", "skeptic", "extractor", "reader", "curator", "ideas",
                "whiteboard", "net-guardian", "ssh-guardian", "keepers", "adversary",
                "arxiv", "paper", "doctor", "mission-agent"}
    assert expected <= set(AG.AGENTS)
    for key in expected:
        u = lib.unit(key)
        assert u.complete() and u.alive and u.agent == key
        assert u.core.w_s == 0.70 and u.theta.current is not None
