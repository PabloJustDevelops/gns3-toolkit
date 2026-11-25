"""Dobles locales para probar `gns3core` sin servidor GNS3 ni red externa.

Tres dobles, todos en 127.0.0.1 con puerto efímero:

- `FakeApi`    — `http.server` que imita las rutas `/v2` que usa `Client`.
- `FakeTelnet` — `socketserver.ThreadingTCPServer` que habla como una consola.
- `FakeHmp`    — igual, pero imitando el canal HMP de QEMU (eco con ANSI).

Cada doble guarda lo que recibe para que los tests comprueben lo enviado, no sólo
lo devuelto.
"""
from __future__ import annotations

import json
import socketserver
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

# El smoke del MCP habla con el GNS3 real y con una ruta absoluta del equipo de
# Pablo: no puede formar parte de una suite sin servidor. Se ejecuta a mano.
collect_ignore = ["test_mcp_smoke.py"]


# ───────────────────────────── API REST falsa ─────────────────────────────
def _encode(payload) -> tuple[bytes, str]:
    """Serializa el payload de una ruta falsa a bytes + Content-Type."""
    if isinstance(payload, bytes):
        return payload, "application/octet-stream"
    if isinstance(payload, str):
        return payload.encode(), "text/plain; charset=utf-8"
    return json.dumps(payload).encode(), "application/json"


class FakeApi:
    """Servidor HTTP con rutas declarativas y registro de peticiones."""

    def __init__(self):
        self.routes: dict[tuple[str, str], tuple[int, object]] = {}
        self.requests: list[dict] = []
        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), _ApiHandler)
        self._httpd.daemon_threads = True
        self._httpd.owner = self
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        self.url = f"http://127.0.0.1:{self._httpd.server_address[1]}"

    def route(self, method: str, path: str, status: int = 200, payload=None) -> None:
        self.routes[(method.upper(), path)] = (status, payload)

    def set_projects(self, projects: list[dict]) -> None:
        self.route("GET", "/v2/projects", 200, projects)

    def set_nodes(self, project_id: str, nodes: list[dict]) -> None:
        self.route("GET", f"/v2/projects/{project_id}/nodes", 200, nodes)

    def close(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()
        self._thread.join(timeout=5)

    # comodidad para los tests
    def last(self, method: str, path: str) -> dict:
        for req in reversed(self.requests):
            if req["method"] == method and req["path"] == path:
                return req
        raise AssertionError(f"no hubo {method} {path}; vistas: "
                             f"{[(r['method'], r['path']) for r in self.requests]}")


class _ApiHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _handle(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        path = self.path.split("?", 1)[0]
        req = {
            "method": self.command,
            "path": path,
            "headers": {k.lower(): v for k, v in self.headers.items()},
            "body": body,
        }
        api: FakeApi = self.server.owner
        api.requests.append(req)
        status, payload = api.routes.get(
            (self.command, path),
            (404, {"message": f"sin ruta: {self.command} {path}"}),
        )
        raw, ctype = _encode(payload)
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        if raw:
            self.wfile.write(raw)

    do_GET = _handle
    do_POST = _handle
    do_PUT = _handle
    do_DELETE = _handle

    def log_message(self, fmt: str, *args) -> None:  # silencio en pytest
        pass


@pytest.fixture
def fake_api():
    api = FakeApi()
    api.route("GET", "/v2/version", 200, {"version": "2.2.61", "local": True})
    yield api
    api.close()


# ─────────────────────────── consola telnet falsa ───────────────────────────
class FakeTelnet:
    """Consola telnet mínima.

    - `on_connect`: bytes nada más aceptar la conexión.
    - `on_line(line)`: respuesta a una línea completa (sin el `\\n`).
    - `on_space()`: respuesta a un espacio suelto (paginación `--More--`).
    - `echo`: si True, devuelve la línea tecleada antes de la respuesta.
    - `lines` / `spaces`: lo que recibió, para las aserciones.
    """

    def __init__(self):
        self.on_connect = b""
        self.on_line = lambda line: b""
        self.on_space = lambda: b""
        self.echo = True
        self.lines: list[str] = []
        self.spaces = 0
        self._server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), _TelnetHandler)
        self._server.daemon_threads = True
        self._server.owner = self
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        self.port = self._server.server_address[1]

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)


class _TelnetHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        owner: FakeTelnet = self.server.owner
        self._send(owner.on_connect)
        buf = b""
        while True:
            chunk = self.connection.recv(4096)
            if not chunk:
                return
            for byte in chunk:
                if byte == 0x0A:                      # \n
                    line = buf.decode(errors="replace")
                    buf = b""
                    owner.lines.append(line)
                    if owner.echo:
                        self._send((line + "\r\n").encode())
                    self._send(owner.on_line(line))
                elif byte == 0x20 and not buf:        # espacio suelto: paginar
                    owner.spaces += 1
                    self._send(owner.on_space())
                elif byte == 0x0D:                    # \r se descarta
                    continue
                else:
                    buf += bytes([byte])

    def _send(self, data: bytes) -> None:
        if not data:
            return
        self.wfile.write(data)
        self.wfile.flush()


@pytest.fixture
def telnet_factory():
    servers: list[FakeTelnet] = []

    def make(**attrs) -> FakeTelnet:
        srv = FakeTelnet()
        for key, value in attrs.items():
            setattr(srv, key, value)
        servers.append(srv)
        return srv

    yield make
    for srv in servers:
        srv.close()


# ───────────────────────────── HMP de QEMU falso ─────────────────────────────
class FakeHmp:
    """Canal HMP: banner, eco carácter a carácter con ANSI y respuesta por comando."""

    def __init__(self):
        self.banner = b"QEMU 9.0.0 monitor - type 'help' for more information\r\n(qemu) "
        self.responses: dict[str, str] = {"info status": "VM status: running"}
        self.commands: list[str] = []
        self._server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), _HmpHandler)
        self._server.daemon_threads = True
        self._server.owner = self
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        self.port = self._server.server_address[1]

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)


class _HmpHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        owner: FakeHmp = self.server.owner
        self.wfile.write(owner.banner)
        self.wfile.flush()
        while True:
            line = self.rfile.readline()
            if not line:
                return
            cmd = line.decode(errors="replace").rstrip("\r\n")
            owner.commands.append(cmd)
            # HMP repinta cada carácter con ESC[K y corrige con ESC[D.
            echo = b"".join(bytes([b]) + b"\x1b[K" for b in cmd.encode())
            echo += b"\x1b[D"
            resp = owner.responses.get(cmd, f"Error: unknown command '{cmd}'")
            self.wfile.write(echo + b"\r\n" + resp.encode() + b"\r\n(qemu) ")
            self.wfile.flush()


@pytest.fixture
def hmp_factory():
    servers: list[FakeHmp] = []

    def make(**attrs) -> FakeHmp:
        srv = FakeHmp()
        for key, value in attrs.items():
            setattr(srv, key, value)
        servers.append(srv)
        return srv

    yield make
    for srv in servers:
        srv.close()
