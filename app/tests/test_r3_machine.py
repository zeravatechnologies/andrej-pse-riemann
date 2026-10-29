"""Round 3, item 24: automatic machine profile (Dell measured, Acer simulated)."""
import pytest

from pse_r import machine as M
from pse_r.llm import limits as L


@pytest.fixture
def as_machine(monkeypatch):
    def use(key):
        monkeypatch.setenv("PSE_RIEMANN_MACHINE", key)
        M.profile(refresh=True)
    yield use
    monkeypatch.delenv("PSE_RIEMANN_MACHINE", raising=False)
    M.profile(refresh=True)


def test_classify_real_cpus():
    assert M.classify({"model": "Intel(R) Core(TM) i5-6600T CPU @ 2.70GHz", "cores": 4}).key == "dell"
    assert M.classify({"model": "Intel(R) Core(TM) i3-7020U CPU @ 2.30GHz", "cores": 2}).key == "acer"
    g = M.classify({"model": "AMD Ryzen 7", "cores": 8})
    assert g.key == "generic" and g.threads == 7


def test_acer_limits_are_gentler(as_machine):
    as_machine("dell")
    d = L.Limits.from_settings()
    as_machine("acer")
    a = L.Limits.from_settings()
    assert a.n_ctx < d.n_ctx and a.think_budget < d.think_budget
    assert a.call_timeout_s > d.call_timeout_s and a.L_latency_s > d.L_latency_s
    assert a.threads() == 2
    assert not M.ACER.measured and M.DELL.measured          # the Acer numbers are an estimate


def test_deepseek_warning_only_on_acer(as_machine):
    as_machine("acer")
    assert "spor" in M.gguf_warning("gguf:DeepSeek-R1-0528-Qwen3-8B-Q5_K_M.gguf")
    as_machine("dell")
    assert M.gguf_warning("gguf:DeepSeek-R1-0528-Qwen3-8B-Q5_K_M.gguf") == ""


def test_this_machine_detected():
    info = M._cpuinfo()
    assert info["threads"] >= 1 and info["ram_gb"] > 0
