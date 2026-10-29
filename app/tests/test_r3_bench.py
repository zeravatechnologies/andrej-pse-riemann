"""Round 3, item 22: the measured benchmark runs through the app's own decision
paths and its numbers are a regression guard (synthetic corpus — see note)."""
from pse_r import bench as BN


def test_benchmark_numbers():
    res = BN.run()
    assert "Sintetički" in res["note"]
    for name, r in (("harms", res["harms"]), ("ssh-report", res["ssh"]["report_level"]),
                    ("ssh-block", res["ssh"]["block_level"]), ("killswitch", res["killswitch"])):
        assert r["FP"] == 0 and r["FN"] == 0, (name, r["misses"])
    md = BN.markdown(res)
    assert "lažno pozitivni" in md and "lažno negativni" in md
