# PSE Riemann 0.3.0 on Windows — what happened (2026-11-19)

Dhiraj (Zerava) installed PSE Riemann 0.3.0 on a Windows 11 machine from the GitHub
release to try the app, with Claude Code assisting. This note records what was found,
what was changed on branch `fix/windows-guardian-fcntl`, how it was verified, and what
is still open. Nothing in `docs/PLAN.md` or `docs/WORKLOG.md` was touched.

## Summary

- The published Windows installer `PSERiemann-Setup-0.3.0.exe` installs and runs the
  first-run wizard, then **crashes as soon as the main window is built**:
  `ModuleNotFoundError: No module named 'fcntl'`.
- Cause: `app/pse_r/guardian_app.py` imports `fcntl` (POSIX-only) at module level, and
  `GuardianTab` imports `guardian_app` while `MainWindow` is constructed. The same code
  is on `main`. The Windows CI job (`build-exe.yml`) only checks that the process is
  alive 18 s after start, which is still inside the wizard, so it never reaches the
  main window.
- Fixed on this branch. Verified with the GUI smoke test on Windows and with a locally
  built PyInstaller bundle that now reaches the main window.

## Timeline

1. Cloned the repo on Windows and created `app/.venv` on Python 3.12.10 (python.org).
   Side finding: a venv created from the Anaconda interpreter on the same machine
   cannot import PySide6 6.12 (`DLL load failed while importing QtWidgets: The
   specified procedure could not be found`), because Anaconda's `Library\bin` ships
   old MSVC runtime DLLs. A venv on the python.org interpreter works.
2. From source: `--selftest` 47/48 (see open items), `--lab`, `--briefing` and the GUI
   all start. The GUI was only taken as far as the wizard at that point.
3. Installed the release silently, per user. The wizard completed. English was obtained
   by writing `"lang": "en"` into `%APPDATA%\pse-riemann\settings.json` before the first
   start; the wizard has no language switch (the `sr | EN` toggle lives in the main
   window's top bar and restarts the app).
4. After "Finish" and the operator prompt: dialog "Unhandled exception in script —
   No module named 'fcntl'". Traceback: `main.py` → `gui/main_window.py:94` →
   `gui/tabs.py` (`GuardianTab.__init__` → `refresh_host` → `_md` → `_ssh_md`) →
   `guardian_app.py:16`.
5. Reproduced from source on Windows with `pytest tests/test_gui_smoke.py` (same error).
6. Fixed, tested, rebuilt with `app/packaging/build_exe.sh` (PyInstaller step only;
   Inno Setup is not installed on that machine, so the ISCC step was skipped), and the
   bundle was copied over the installed files. The app now reaches the main window in
   English; the Guardian pill reports ok.

## What changed

- `pse_r/guardian_app.py`: `fcntl` is optional; on Windows the single-instance lock
  uses `msvcrt.locking`. The lock file is opened with `"a"` instead of `"w"`: a
  truncating open fails on Windows while another process holds the lock, and the
  file never carries anything (the pid is in `guardian.pid`). New `supported()`:
  the SSH guardian reads the Linux auth log and acts through sudo, so on Windows
  `ensure_running()`, `run_tray()` and `run_headless()` return without starting it.
- `pse_r/guardian/ssh/keys.py`: `pwd` is optional; `local_accounts()` returns an
  empty set without it.
- `pse_r/gui/tabs.py`: the Guardian tab shows "SSH guardian — not available on
  Windows" instead of probing sudo.
- `main.py`: the operator prompt (title, label, warning) goes through `tr()`; it was
  hard-coded Serbian and stayed Serbian in the English interface.
- `pse_r/setup_flow.py`, `pse_r/gui/setup.py`: the setup summary notes ("key saved",
  "guardian at login", "none", "no AI") go through `tr()`.
- `pse_r/i18n_en.py`: the matching English entries. `tools/i18n_audit.py` is clean.
- `pse_r/config.py`: on Windows `XDG_CONFIG_HOME` is honoured before `APPDATA`, so the
  self-test and the tests use their throwaway config directory as `conftest.py` and
  `main.py --selftest` intend. Before this, on Windows they silently used the real one.
- Tests: `test_xdg_autostart_and_unit_text` reads the file as UTF-8 (cp1252 decode
  error on Windows). Linux-only tests are skipped on win32 with a reason: the headless
  guardian / SIGTERM test, the logrotate rename test, the bash sudo-helper tests.

## Verification (Windows 11, Python 3.12.10, PySide6 6.12.0)

| check | result |
|---|---|
| `tests/test_gui_smoke.py` | 2 passed (failed before with the fcntl error) |
| gui smoke + `test_r3_guardian_process.py` + `test_r3_ssh.py` | 24 passed, 9 skipped |
| `tools/i18n_audit.py` | 0 without translation, 0 outside `tr()` |
| `main.py --selftest` (source) | 47/48, only "SPKI parser" fails (see below) |
| full suite | 376 passed, 9 skipped, 8 failed |
| packaged build (PyInstaller, public edition, llama-cpp included) | operator prompt in English, main window "PSE Riemann 0.3.0" builds, no crash |

The 8 full-suite failures also fail on untouched `origin/main` on Windows, so they are
pre-existing, not regressions: `test_selftest_never_touches_the_given_vault` (cp1252
decoding of the subprocess output, plus the SPKI check), two in `test_r3_grafovi_gui`
(`KeyError: 'area'` / `'count'`), `test_jobs_cache_record_and_cancel` (job reports
"prekinuto"), `test_this_machine_detected` (RAM detected as 0.0), two in
`test_r3_providers` (Windows socket hang-up semantics), and
`test_every_window_fits_four_screens` (MainWindow 4026 px wide offscreen).

## Open items

- **The published Windows release 0.3.0 is broken for every Windows user** (crash right
  after the wizard). A new Windows build from this branch is needed; `build-exe.yml`
  produces the Inno Setup installer on a pull request or a `v*` tag.
- The `v0.3.0` tag predates two fixes already on `main` (`--selftest` on the frozen exe
  opened the GUI; the `_edition` fallback), so a rebuild picks those up as well.
- `--selftest` on Windows: "SPKI parser — 0/5" because it reads `/etc/ssl/certs/*.pem`.
  The check needs a Windows source of certificates (or a bundled PEM) to mean anything
  there; today the self-test can never say "SVE PROLAZI" on Windows.
- Windows CI only exercises the wizard stage. Building `MainWindow` offscreen in CI
  (what `test_gui_smoke.py` does) would have caught this crash.
- The 8 pre-existing Windows test failures listed above.
- The SSH guardian is Linux-only by design; on Windows the "start the guardian at
  login" option has nothing to start.
- On Dhiraj's machine the installed app is the locally built bundle copied over the
  0.3.0 install (the Inno uninstaller was kept). Uninstalling from Settings may leave
  files behind in `%LOCALAPPDATA%\Programs\PSE Riemann`; the official installer built
  from this branch should replace it.
