"""
A local model talks to nobody but this computer (round 3, item 13; Perun P8).

While a GGUF call runs, a Python audit hook watches every socket.connect /
getaddrinfo made by THAT thread: anything that is not a loopback address
(127.0.0.0/8, ::1, a Unix socket) is refused before it happens, and the
attempt is journalled as a threat. llama-cpp itself never opens a socket; this
is the guarantee that a dependency, a plugin or a future change cannot make the
"local" model phone home without it being stopped and seen.

Audit hooks cannot be removed once added, so the hook is installed once and is
inert outside a `local_only()` block (a thread-local flag).
"""
from __future__ import annotations

import ipaddress
import sys
import threading
from contextlib import contextmanager

_tls = threading.local()
_installed = False
_lock = threading.Lock()


class NonLocalAddress(PermissionError):
    pass


def _is_local(addr) -> bool:
    if isinstance(addr, (str, bytes)):                 # AF_UNIX path
        return True
    if not isinstance(addr, tuple) or not addr:
        return False
    host = addr[0]
    if isinstance(host, bytes):
        host = host.decode("ascii", "replace")
    if host in ("localhost",):
        return True
    try:
        return ipaddress.ip_address(str(host).split("%")[0]).is_loopback
    except ValueError:
        return False


def _hook(event: str, args) -> None:
    if not getattr(_tls, "on", False):
        return
    if event == "socket.connect":
        addr = args[1] if len(args) > 1 else None
        if not _is_local(addr):
            _refuse(f"socket.connect → {addr!r}")
    elif event == "socket.getaddrinfo":
        host = args[0] if args else None
        if isinstance(host, bytes):
            host = host.decode("ascii", "replace")
        if host not in (None, "localhost", "127.0.0.1", "::1") and not _is_local((host,)):
            _refuse(f"getaddrinfo → {host!r}")


def _refuse(what: str):
    _tls.on = False                     # the journal write below must not recurse
    try:
        from ..core import journal as J
        J.log(J.THREAT, "local-only", {"event": "non_local_address_refused",
                                       "what": what[:200], "who": getattr(_tls, "who", "")},
              subject="gguf", verdict="threat")
    finally:
        _tls.on = True
    raise NonLocalAddress(f"lokalni model ne smije na mrežu: {what}")


def install() -> None:
    global _installed
    with _lock:
        if not _installed:
            sys.addaudithook(_hook)
            _installed = True


@contextmanager
def local_only(who: str = "gguf"):
    install()
    prev = getattr(_tls, "on", False)
    _tls.on, _tls.who = True, who
    try:
        yield
    finally:
        _tls.on = prev
