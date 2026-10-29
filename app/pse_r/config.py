"""
PSE Riemann — single source of truth for paths, constants and profile.

Constants are LIFTED VERBATIM from the PSE kernel spec
(~/Desktop/123/PSE_MASTER_ARCHITECTURE.txt, §0 CORE CONSTANTS and §10 GUARDIAN).
That file is READ-ONLY reference; nothing here writes to it.

Hard rule enforced across the app (see vault.gate and guardian.egress):
  * every write lands inside APP_ROOT/../vault  (i.e. the "PSE Riemann" folder)
  * secrets live OUTSIDE the vault, in ~/.config/pse-riemann/
  * ~/Desktop/123 is never opened for writing
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "PSE Riemann"
APP_SLUG = "pse-riemann"
VERSION = "0.3.0"     # Faza 6d: every agent is a PSE unit

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #
APP_DIR = Path(__file__).resolve().parent          # .../app/pse_r
APP_ROOT = APP_DIR.parent                          # .../app
PROJECT_ROOT = APP_ROOT.parent                     # .../PSE Riemann


def _env_path(var: str, default: Path) -> Path:
    v = os.environ.get(var)
    return Path(v).expanduser().resolve() if v else default


PACKAGED_MARKER = APP_DIR.parent / ".packaged"


def is_packaged() -> bool:
    """True when running from an installed package rather than a checkout.
    A marker file the build drops — not a guess from write permissions, which
    would give a different answer for root than for you."""
    return getattr(sys, "frozen", False) or PACKAGED_MARKER.exists()


# Edition (agreement rule 38): "andrej" = the personal package with the three
# missions and the QRH content; "public" = empty missions, empty vault, all the
# machinery. The build writes app/.edition; a checkout is Andrej's own copy.
EDITION_FILE = APP_DIR.parent / ".edition"


def edition() -> str:
    e = os.environ.get("PSE_RIEMANN_EDITION", "").strip()
    if not e and EDITION_FILE.exists():
        e = EDITION_FILE.read_text(encoding="utf-8").strip()
    if not e:                       # a frozen build (PyInstaller) bakes it into the package
        try:
            from . import _edition  # type: ignore[attr-defined]
            e = str(getattr(_edition, "EDITION", "")).strip()
        except ImportError:
            pass
    return e if e in ("andrej", "public") else "andrej"


def personal() -> bool:
    return edition() == "andrej"


RESULTS_NAME = "PSE Riemann rezultati"


def _desktop_dir() -> Path:
    """The user's Desktop (xdg-user-dir on Linux — it may be localised, e.g. Radna površ)."""
    if sys.platform == "win32":
        return Path(os.environ.get("USERPROFILE", Path.home())) / "Desktop"
    try:
        import subprocess
        out = subprocess.run(["xdg-user-dir", "DESKTOP"], capture_output=True, text=True,
                             timeout=2).stdout.strip()
        if out and Path(out).is_dir() and Path(out) != Path.home():
            return Path(out)
    except (OSError, ValueError):
        pass
    d = Path.home() / "Desktop"
    return d if d.is_dir() else Path.home()


def _old_data_vault() -> Path:
    """Where 0.1.0 – 0.2.0~rc1 kept an installed app's vault (hidden; live-test finding)."""
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share")).expanduser()
    return base / APP_SLUG / "vault"


def _default_vault() -> Path:
    """
    Beside the code when running from a checkout. Installed as a package: a VISIBLE
    folder on the Desktop, "PSE Riemann rezultati" (Andrej, live test 2026-10-27 —
    the hidden ~/.local/share location made the results impossible to find).

    A .deb puts the code under /opt, which you cannot write to, so the vault can
    never sit beside the code there. Set PSE_RIEMANN_VAULT to put it anywhere else.
    """
    if is_packaged():
        return _desktop_dir() / RESULTS_NAME / "vault"
    return PROJECT_ROOT / "vault"


VAULT = _env_path("PSE_RIEMANN_VAULT", _default_vault())
# the folder "Otvori folder sa rezultatima" opens: the results folder when installed
RESULTS_DIR = VAULT.parent if (is_packaged() and VAULT.parent.name == RESULTS_NAME) else VAULT

# Vault subtrees. `knowledge` is the only place a verified card may live.
DIR_KNOWLEDGE = VAULT / "knowledge"        # CITED / COMPUTED cards
DIR_SPECULATION = VAULT / "speculation"    # SPECULATION cards — never promoted silently
DIR_SOURCES = VAULT / "sources"            # one card per external source (provenance)
DIR_NOTES = VAULT / "notes"                # free-form markdown, whiteboard notes
DIR_DAILY = VAULT / "daily"                # daily notes / briefings
DIR_LAB = VAULT / "lab"                    # experiment runs: json + png + script hash
DIR_INBOX = VAULT / "inbox"                # raw scraped material (EXTERNAL STORE, not corpus)
DIR_MEDIA = VAULT / "media"                # whiteboard svg/png
DIR_STATE = VAULT / ".state"               # journal db, indexes, baselines, caches

VAULT_DIRS = [DIR_KNOWLEDGE, DIR_SPECULATION, DIR_SOURCES, DIR_NOTES,
              DIR_DAILY, DIR_LAB, DIR_INBOX, DIR_MEDIA, DIR_STATE]

JOURNAL_DB = DIR_STATE / "journal.db"
INDEX_DB = DIR_STATE / "index.db"
BASELINE_DB = DIR_STATE / "guardian_baselines.json"
PIN_STORE = DIR_STATE / "tls_pins.json"
BUDGET_STORE = DIR_STATE / "budget.json"
SHARED_LIB_DB = DIR_STATE / "shared_lib.db"   # mutable SHARED_LIB state (queue, declarations, methods, missions, reports)
# Local GGUF models (llama-cpp). Beside the project by default, never in the vault,
# never on git (*.gguf is gitignored). Override with PSE_RIEMANN_MODELS.
# Local GGUF models. In a checkout: PSE Riemann/models. Installed: the code sits
# under read-only /opt, so models live beside the vault in the user's data dir.
DIR_MODELS = _env_path("PSE_RIEMANN_MODELS",
                       (VAULT.parent / "models") if is_packaged() else PROJECT_ROOT / "models")
DIR_REPORTS = VAULT / "reports"                # final reports (guarded by keeper units)
DIR_METHODS = VAULT / "methods"                # accepted method packs
VAULT_DIRS += [DIR_REPORTS, DIR_METHODS]
DIR_SEALS = DIR_STATE / "seals"                # sealed copies of final reports (keepers)

# Secrets NEVER live in the vault (the vault is meant to be syncable / shareable).
if sys.platform == "win32":
    CONFIG_DIR = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / APP_SLUG
else:
    CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME",
                                     Path.home() / ".config")).expanduser() / APP_SLUG
SECRETS_FILE = CONFIG_DIR / "secrets.json"
SETTINGS_FILE = CONFIG_DIR / "settings.json"

# Read-only reference — the PSE story. Opened for READ only, ever.
PSE_SPINE = Path.home() / "Desktop" / "123" / "PSE_MASTER_ARCHITECTURE.txt"

# --------------------------------------------------------------------------- #
# PSE kernel constants (spec §0) — do not tune casually
# --------------------------------------------------------------------------- #
SELF_WEIGHT = 0.70
OTHER_WEIGHT_MAX = 0.30
THETA_OPTIMAL = 30.00
THETA_HEALTHY = (25.00, 35.00)
THETA_TIMEAVG_HEALTHY = (27.50, 32.50)
SIGMA_HEALTHY = (0.015, 0.030)
SIGMA_SCHIZOID = 0.010          # sustained sigma below this -> schizoid screening
STABILITY_WINDOW = 10_000       # interactions
ORGANELLE_MAX_SINGLE = 0.20
ORGANELLE_BUDGET_TOTAL = 0.30

# --------------------------------------------------------------------------- #
# Guardian constants (spec §10)
# --------------------------------------------------------------------------- #
BENIGN, ELEVATED, CRITICAL = 0, 1, 2
THREAT_TIER1 = "observe_report"
THREAT_TIER2 = "isolate_quarantine"
GUARDIAN_THETA_MIN, GUARDIAN_THETA_MAX = 25.00, 35.00

ANOMALY_AXES = [
    "connection_cadence",
    "endpoint_spread",
    "payload_entropy",
    "auth_failure_rate",
    "privesc_attempts",
    "egress_volume",
    "timing_regularity",       # INVERTED: low variance = automated = suspicious
]
AXIS_WEIGHTS = {
    "connection_cadence": 0.15, "endpoint_spread": 0.15, "payload_entropy": 0.10,
    "auth_failure_rate": 0.20, "privesc_attempts": 0.25, "egress_volume": 0.20,
    "timing_regularity": 0.10,
}
RISK_ELEVATED_T, RISK_CRITICAL_T = 0.35, 0.65
MUTUAL_SUM_T = 0.50
PRIVESC_CAP = 5.0               # normalizer for the privesc axis

# --------------------------------------------------------------------------- #
# Profile — this build targets a 4 GB Surface on hostile (public) WiFi
# --------------------------------------------------------------------------- #
PROFILE = os.environ.get("PSE_RIEMANN_PROFILE", "surface")

LIMITS = {
    "surface": dict(
        max_response_bytes=8 * 1024 * 1024,     # per HTTP response
        max_pdf_bytes=25 * 1024 * 1024,
        http_timeout=30.0,
        max_concurrent_fetch=2,
        mp_dps_default=30,                      # mpmath precision
        mp_dps_max=120,
        plot_dpi=110,
        max_graph_nodes=400,
        chat_input_max_frac=0.50,               # input box grows to 50% of chat pane
    ),
}
LIM = LIMITS.get(PROFILE, LIMITS["surface"])


MIGRATED: list = []                     # what migrate_old_vault() moved (journalled at boot)

_README = """PSE Riemann — rezultati
=======================
Ovdje instalirana aplikacija čuva sve što uradiš u njoj.

  vault/lab/        lab run-ovi (skripta, brojevi, PNG grafovi)
  vault/knowledge/  provjerene kartice
  vault/reports/    zapečaćeni izvještaji (npr. radni tekst misija 2 i 3)
  vault/notes/      bilješke, teme, plan, otvorena pitanja
  vault/.state/     dnevnik (journal.db) i stanje — ne brisati, ne mijenjati rukom
  snimci ekrana/    F12 / Shift+F12 / dugme 📷
  models/           lokalni GGUF modeli (ako ih ovdje staviš)

Ključevi NISU ovdje (~/.config/pse-riemann/secrets.json, prava 0600).
"""


def migrate_old_vault() -> list:
    """Move a vault from the old hidden location to the visible results folder,
    once, before anything opens it. Nothing is copied twice or deleted: the old
    folder gets a note saying where everything went."""
    import shutil
    moved = []
    if not is_packaged() or os.environ.get("PSE_RIEMANN_VAULT"):
        return moved
    old = _old_data_vault()
    if old.exists() and not VAULT.exists() and any(old.iterdir()):
        VAULT.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(old), str(VAULT))
        moved.append((str(old), str(VAULT)))
        old_models = old.parent / "models"
        if old_models.exists() and any(old_models.iterdir()) and not DIR_MODELS.exists():
            shutil.move(str(old_models), str(DIR_MODELS))
            moved.append((str(old_models), str(DIR_MODELS)))
        try:
            (old.parent / "PREMJESTENO.txt").write_text(
                f"Rezultati su premješteni u vidljiv folder:\n{VAULT.parent}\n", encoding="utf-8")
        except OSError:
            pass
    MIGRATED[:] = moved
    return moved


def ensure_vault() -> None:
    """Create the vault skeleton. Idempotent. The only place that mkdirs the vault."""
    migrate_old_vault()
    if is_packaged() and VAULT.parent.name == RESULTS_NAME:
        VAULT.parent.mkdir(parents=True, exist_ok=True)
        readme = VAULT.parent / "PROČITAJ.txt"
        if not readme.exists():
            try:
                readme.write_text(_README, encoding="utf-8")
            except OSError:
                pass
    for d in VAULT_DIRS:
        d.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        CONFIG_DIR.chmod(0o700)
    except OSError:
        pass


def inside_vault(p: Path) -> bool:
    """True iff p resolves inside the vault. The write-containment predicate."""
    try:
        Path(p).resolve().relative_to(VAULT.resolve())
        return True
    except (ValueError, OSError):
        return False
