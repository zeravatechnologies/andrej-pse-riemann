"""Round 3, item 13 (Perun P8): the local model may only reach this computer."""
import socket
import threading

import pytest

from pse_r.core import journal as J
from pse_r.llm import gguf as G
from pse_r.llm import limits as L
from pse_r.llm.backend import Msg
from pse_r.llm.local_only import NonLocalAddress, local_only


def test_non_local_connect_refused_inside_block():
    with local_only("test"):
        with pytest.raises(NonLocalAddress):
            socket.create_connection(("1.1.1.1", 443), timeout=0.5)
        with pytest.raises(NonLocalAddress):
            socket.getaddrinfo("example.org", 443)
    assert any(e["payload"].get("event") == "non_local_address_refused"
               for e in J.journal().tail(20, kind=J.THREAT))


def test_loopback_allowed_and_other_threads_untouched():
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]
    with local_only("test"):
        c = socket.create_connection(("127.0.0.1", port), timeout=1)
        c.close()
        seen = {}

        def other():                                  # not inside the block
            try:
                socket.getaddrinfo("localhost", 80)
                seen["ok"] = True
            except NonLocalAddress:
                seen["blocked"] = True
        t = threading.Thread(target=other)
        t.start(); t.join()
        assert seen.get("ok")
    srv.close()


def test_gguf_call_that_tries_the_network_is_stopped(monkeypatch):
    class PhoningLlama:
        def create_chat_completion(self, **kw):
            socket.create_connection(("8.8.8.8", 53), timeout=0.5)

        def tokenize(self, b, add_bos=False):
            return []
    L.resume()
    b = G.GGUFBackend("/nope/m.gguf", lim=L.Limits())
    monkeypatch.setattr(b, "_ensure_loaded", lambda: PhoningLlama())
    monkeypatch.setattr(L, "free_ram_gb", lambda: 10.0)
    with pytest.raises(NonLocalAddress):
        b.chat([Msg("user", "x")])
    # and outside a GGUF call the hook is inert
    socket.getaddrinfo("localhost", 80)
