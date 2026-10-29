"""Every test runs against a throwaway vault and config dir — never the real one."""
import os
import sys
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="pse-riemann-test-"))
os.environ["PSE_RIEMANN_VAULT"] = str(_TMP / "vault")
os.environ["XDG_CONFIG_HOME"] = str(_TMP / "config")
# never let a test see (or load) the operator's real GGUF models
os.environ["PSE_RIEMANN_MODELS"] = str(_TMP / "models")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["PSE_RIEMANN_SILENT"] = "1"          # the Laboratory alarm never sounds in tests
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh_operator():
    from pse_r.shared_lib import operator as OP
    OP._reset_for_tests()
    yield
    OP._reset_for_tests()


@pytest.fixture
def operator():
    from pse_r.shared_lib import operator as OP
    OP.set_operator("Test Operater")
    return "Test Operater"
