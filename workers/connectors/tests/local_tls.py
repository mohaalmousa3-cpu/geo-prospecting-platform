"""Local-only TLS test infrastructure for the urllib3 transport proof (Phase 3b R8).

Everything binds to the loopback interface. A throw-away CA and server certificates are generated with the `openssl`
command line tool into a temporary directory at test time (nothing is committed). No DNS, no external host.
"""

from __future__ import annotations

import gzip
import socket
import ssl
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

HOST = "catalog.test.example"  # controlled logical names; they exist only in this test's resolver
OTHER_HOST = "other.test.example"


def _run(*args: str, cwd: Path) -> None:
    subprocess.run(args, cwd=cwd, check=True, capture_output=True, timeout=60)  # noqa: S603


@dataclass(frozen=True)
class Pki:
    ca_pem: str
    certs: dict[str, tuple[str, str]]  # logical name -> (cert pem, key pem)


def make_pki(directory: Path, names: tuple[str, ...] = (HOST, OTHER_HOST)) -> Pki:
    """A test CA plus one server certificate per logical name (SAN = that name only)."""
    _run(
        "openssl", "req", "-x509", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:prime256v1", "-nodes",
        "-keyout", "ca.key", "-out", "ca.pem", "-days", "2", "-subj", "/CN=geo-test-ca",
        "-addext", "basicConstraints=critical,CA:TRUE", "-addext", "keyUsage=critical,keyCertSign,cRLSign",
        cwd=directory,
    )  # fmt: skip
    certs: dict[str, tuple[str, str]] = {}
    for name in names:
        stem = name.split(".")[0]
        ext = directory / f"{stem}.ext"
        ext.write_text(
            f"subjectAltName=DNS:{name}\nbasicConstraints=CA:FALSE\n"
            "keyUsage=digitalSignature\nextendedKeyUsage=serverAuth\n"
        )
        _run(
            "openssl", "req", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:prime256v1", "-nodes",
            "-keyout", f"{stem}.key", "-out", f"{stem}.csr", "-subj", f"/CN={name}",
            cwd=directory,
        )  # fmt: skip
        _run(
            "openssl", "x509", "-req", "-in", f"{stem}.csr", "-CA", "ca.pem", "-CAkey", "ca.key", "-CAcreateserial",
            "-out", f"{stem}.pem", "-days", "2", "-extfile", f"{stem}.ext",
            cwd=directory,
        )  # fmt: skip
        certs[name] = (str(directory / f"{stem}.pem"), str(directory / f"{stem}.key"))
    return Pki(str(directory / "ca.pem"), certs)


@dataclass
class Recorder:
    """What the server observed. Appended from server threads, read by the test thread."""

    lock: threading.Lock = field(default_factory=threading.Lock)
    requests: list[dict[str, Any]] = field(default_factory=list)
    sni: list[str | None] = field(default_factory=list)

    def count(self, path: str | None = None) -> int:
        with self.lock:
            return sum(1 for r in self.requests if path is None or r["path"] == path)

    def last(self) -> dict[str, Any]:
        with self.lock:
            return self.requests[-1]


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server: _Server  # type: ignore[assignment]

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002 - silence
        return

    def _send(
        self, status: int, body: bytes = b"", headers: dict[str, str] | None = None, length: bool = True
    ) -> None:
        self.send_response(status)
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        if length:
            self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path, query = parsed.path, parse_qs(parsed.query)
        with self.server.recorder.lock:
            self.server.recorder.requests.append(
                {
                    "path": path,
                    "headers": [(k, v) for k, v in self.headers.items()],
                    "server_ip": self.server.server_address[0],
                    "client_ip": self.client_address[0],
                }
            )
        if path == "/ok":
            self._send(
                200, b'{"ok": true}', {"Content-Type": "application/json", "Set-Cookie": "sid=1; Path=/"}
            )
        elif path == "/empty":
            self._send(204)
        elif path == "/big":
            self._send(200, b"x" * int(query["n"][0]), {"Content-Type": "application/octet-stream"})
        elif path == "/stream-nolen":  # no Content-Length: the body ends when the connection closes
            self.send_response(200)
            self.send_header("Connection", "close")
            self.end_headers()
            self.close_connection = True
            try:
                for _ in range(200):
                    self.wfile.write(b"y" * 1024)
            except OSError:
                pass
        elif path == "/gzip":
            self._send(200, gzip.compress(b"hello"), {"Content-Encoding": "gzip"})
        elif path == "/identity":
            self._send(200, b"plain", {"Content-Encoding": "identity"})
        elif path == "/redirect":
            self._send(302, b"REDIRECT-BODY", {"Location": f"https://{OTHER_HOST}/x"})
        elif path == "/status500":
            self._send(500, b"SECRETBODY")
        elif path == "/status404":
            self._send(404, b"SECRETBODY")
        elif path == "/reset":  # read the request, then drop the connection without answering
            self.close_connection = True
            self.connection.close()
        elif path == "/hang":
            self.server.stop.wait(5)
            self._send(200, b"late")
        elif path == "/drip":  # a body that never stalls long enough to hit the read timeout
            self.send_response(200)
            self.send_header("Content-Length", "100000")
            self.end_headers()
            try:
                for _ in range(100000):
                    if self.server.stop.is_set():
                        break
                    self.wfile.write(b"z")
                    self.wfile.flush()
                    time.sleep(0.05)
            except OSError:
                pass
            self.close_connection = True
        else:
            self._send(404, b"unknown")


class _Server(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 16
    recorder: Recorder
    stop: threading.Event

    def handle_error(
        self, request: Any, client_address: Any
    ) -> None:  # failed handshakes are expected in tests
        return


class TlsServer:
    """A loopback HTTPS server presenting the certificate of `cert_name`; records SNI and every request."""

    def __init__(self, pki: Pki, cert_name: str, ip: str = "127.0.0.1", port: int = 0) -> None:
        assert ip.startswith("127."), "local test servers bind to loopback only"
        self.recorder = Recorder()
        self.ip = ip
        httpd = _Server((ip, port), _Handler)
        httpd.recorder = self.recorder
        httpd.stop = threading.Event()
        cert, key = pki.certs[cert_name]
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(cert, key)
        ctx.sni_callback = self._on_sni  # type: ignore[assignment]
        httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True, do_handshake_on_connect=False)
        self._httpd = httpd
        self.port: int = httpd.server_address[1]
        self._thread = threading.Thread(
            target=httpd.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True
        )

    def _on_sni(self, _sock: ssl.SSLObject, name: str | None, _ctx: ssl.SSLContext) -> None:
        with self.recorder.lock:
            self.recorder.sni.append(name)

    def __enter__(self) -> TlsServer:
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._httpd.stop.set()
        self._httpd.shutdown()
        self._httpd.server_close()
        self._thread.join(timeout=5)


def unused_loopback_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


# ---- audit hook: the only network events allowed during a transport call are loopback connects ----------------
_events: list[tuple[str, tuple[Any, ...], int]] = []
_recording = threading.Event()
_WATCH = (
    "socket.connect",
    "socket.getaddrinfo",
    "socket.gethostbyname",
    "socket.gethostbyaddr",
    "socket.sendto",
)


def _hook(event: str, args: tuple[Any, ...]) -> None:
    if _recording.is_set() and event in _WATCH:
        _events.append((event, args[1:] if event == "socket.connect" else args, threading.get_ident()))


sys.addaudithook(_hook)  # cannot be removed; inert unless `_recording` is set


class NetworkAudit:
    """Context manager: records the socket events raised by the *calling* thread only."""

    def __enter__(self) -> NetworkAudit:
        _events.clear()
        self._tid = threading.get_ident()
        _recording.set()
        return self

    def __exit__(self, *exc: object) -> None:
        _recording.clear()

    @property
    def events(self) -> list[tuple[str, tuple[Any, ...]]]:
        return [(e, a) for e, a, t in _events if t == self._tid]
