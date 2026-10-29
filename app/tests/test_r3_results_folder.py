"""Live test 0.2.0~rc1, finding 3 (Andrej: option 1): an installed app keeps its
results in a VISIBLE folder on the Desktop, "PSE Riemann rezultati"; the old hidden
~/.local/share vault is moved there once, nothing is lost."""
from pathlib import Path

from pse_r import config as C


def test_installed_vault_is_on_the_desktop(monkeypatch, tmp_path):
    monkeypatch.setattr(C, "is_packaged", lambda: True)
    monkeypatch.setattr(C, "_desktop_dir", lambda: tmp_path / "Desktop")
    v = C._default_vault()
    assert v == tmp_path / "Desktop" / "PSE Riemann rezultati" / "vault"


def test_old_hidden_vault_is_moved_once(monkeypatch, tmp_path):
    old = tmp_path / "share" / "pse-riemann" / "vault"
    (old / "lab" / "run1").mkdir(parents=True)
    (old / "lab" / "run1" / "result.json").write_text("{}")
    (old / ".state").mkdir()
    (old / ".state" / "journal.db").write_bytes(b"db")
    new = tmp_path / "Desktop" / "PSE Riemann rezultati" / "vault"
    monkeypatch.setattr(C, "is_packaged", lambda: True)
    monkeypatch.delenv("PSE_RIEMANN_VAULT", raising=False)
    monkeypatch.setattr(C, "_old_data_vault", lambda: old)
    monkeypatch.setattr(C, "VAULT", new)
    monkeypatch.setattr(C, "DIR_MODELS", new.parent / "models")
    moved = C.migrate_old_vault()
    assert moved and (new / "lab" / "run1" / "result.json").exists()
    assert (new / ".state" / "journal.db").read_bytes() == b"db" and not old.exists()
    assert "PSE Riemann rezultati" in (old.parent / "PREMJESTENO.txt").read_text()
    assert C.migrate_old_vault() == []                        # once only, never twice


def test_screenshots_go_beside_the_results(monkeypatch, tmp_path):
    from pse_r.gui import snapshot as SNAP
    monkeypatch.setattr(C, "is_packaged", lambda: True)
    monkeypatch.setattr(C, "RESULTS_DIR", tmp_path / "PSE Riemann rezultati")
    monkeypatch.setattr(C, "VAULT", tmp_path / "PSE Riemann rezultati" / "vault")
    assert SNAP.default_dir() == tmp_path / "PSE Riemann rezultati" / "snimci ekrana"
