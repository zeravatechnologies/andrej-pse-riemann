"""
Start the guardian at login (round 3, items 8.6 and 20) — the operator's choice.

Two ways, both per user (no root):
  * XDG autostart  ~/.config/autostart/pse-riemann-guardian.desktop — the tray
                   guardian starts with the desktop session (default);
  * systemd user service  ~/.config/systemd/user/pse-riemann-guardian.service —
                   headless, with hardening (Svarog S9). One honest exception:
                   NoNewPrivileges blocks sudo, so it is set only while there is
                   NO sudoers rule for the helper (then the guardian can only
                   alarm anyway); with the rule it is left off, and the unit
                   says why.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


def _cfg() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")


def desktop_path() -> Path:
    return _cfg() / "autostart" / "pse-riemann-guardian.desktop"


def unit_path() -> Path:
    return _cfg() / "systemd" / "user" / "pse-riemann-guardian.service"


def _cmd(headless: bool) -> list[str]:
    from .guardian_app import launch_command
    c = launch_command()
    return c + (["--headless"] if headless else [])


def enable_xdg() -> Path:
    p = desktop_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("[Desktop Entry]\nType=Application\nName=PSE Riemann — čuvar\n"
                 "Comment=SSH čuvar i prekidač za online AI (ikona u traci)\n"
                 f"Exec={' '.join(_q(x) for x in _cmd(False))}\n"
                 "X-GNOME-Autostart-enabled=true\nNoDisplay=false\nTerminal=false\n",
                 encoding="utf-8")
    return p


def _q(s: str) -> str:
    return f'"{s}"' if " " in s else s


def unit_text(has_sudo_rule: bool) -> str:
    nnp = ("# NoNewPrivileges je ISKLJUČEN: čuvar mora pokrenuti `sudo -n "
           "pse-guard-helper` (usko pravilo)\nNoNewPrivileges=no"
           if has_sudo_rule else
           "# nema sudoers pravila → čuvar samo alarmira; zato NoNewPrivileges=yes\n"
           "NoNewPrivileges=yes")
    return f"""[Unit]
Description=PSE Riemann — SSH čuvar (bez prozora)
After=network-online.target

[Service]
Type=simple
ExecStart={' '.join(_q(x) for x in _cmd(True))}
Restart=on-failure
RestartSec=10
# hardening (Svarog S9) — compatible with reading the journal and calling sudo
{nnp}
PrivateTmp=yes
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectKernelLogs=yes
ProtectControlGroups=yes
ProtectClock=yes
ProtectHostname=yes
RestrictRealtime=yes
RestrictNamespaces=yes
LockPersonality=yes
SystemCallArchitectures=native
UMask=0077

[Install]
WantedBy=default.target
"""


def enable_service(start: bool = True) -> Path:
    from .guardian import containment as C
    p = unit_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(unit_text(C.have_rights()[0]), encoding="utf-8")
    if start and shutil.which("systemctl"):
        subprocess.run(["systemctl", "--user", "daemon-reload"], timeout=20)
        subprocess.run(["systemctl", "--user", "enable", "--now", p.name], timeout=30)
    return p


def disable_all() -> None:
    if desktop_path().exists():
        desktop_path().unlink()
    if unit_path().exists():
        if shutil.which("systemctl"):
            subprocess.run(["systemctl", "--user", "disable", "--now", unit_path().name],
                           timeout=30)
        unit_path().unlink()


def apply_setting(enabled: bool, mode: str = "xdg") -> str:
    """From the setup / settings: on → install the chosen way; off → remove both."""
    if not enabled:
        disable_all()
        return "isključeno"
    if mode == "service":
        return str(enable_service())
    return str(enable_xdg())
