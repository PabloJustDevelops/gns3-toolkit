#!/usr/bin/env python3
"""Una única puerta local para las WebUI de pfSense, con nombre por perfil.

El proxy escucha en `127.0.0.1` y traduce rutas con nombre a la IP declarada
en el perfil YAML:

    http://127.0.0.1:8080/pfsense-examen/  ->  https://<pfsense_ip>/

Sólo este proxy de laboratorio acepta el certificado autofirmado del firewall
(`CERT_NONE`): el núcleo (`gns3core.py`) no relaja la verificación. Los perfiles
no guardan credenciales y los mensajes de error no publican la IP del invitado.

Uso:
    python scripts/pf_webui_proxy.py examples/pf-perfiles/

El perfil es el mismo YAML del laboratorio con un bloque `pfsense:`:

    pfsense:
      pfsense_ip: 192.168.1.1
      webui_name: pfsense-examen
      webui_port: 443        # opcional, para pruebas o puertos no estándar
"""
from __future__ import annotations

import argparse
import http.client
import re
import ssl
import sys
from dataclasses import dataclass
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import yaml

LOOPBACK = {"127.0.0.1", "localhost", "::1"}
DEFAULT_PORT = 8080
DEFAULT_UPSTREAM_PORT = 443
TIMEOUT = 30.0
REDIRECT_CODES = {301, 302, 303, 307, 308}

# Cabeceras hop-by-hop o recalculadas: no se copian de una punta a la otra.
SALTAR = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
    "content-length",
}

NOMBRE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


@dataclass(frozen=True)
class Route:
    """Una WebUI publicada bajo `/name/`."""

    name: str
    ip: str
    port: int = DEFAULT_UPSTREAM_PORT


def _contexto_laboratorio() -> ssl.SSLContext:
    """Acepta el certificado autofirmado del pfSense de laboratorio.

    Vive sólo aquí: el cliente de la API y `pfsense.py` mantienen la
    verificación normal.
    """
    contexto = ssl.create_default_context()
    contexto.check_hostname = False
    contexto.verify_mode = ssl.CERT_NONE
    return contexto


CONTEXTO = _contexto_laboratorio()


def _ruta_desde_perfil(fichero: Path, datos: dict) -> Route:
    nombre = str(datos.get("webui_name") or "").strip()
    if not nombre:
        raise ValueError(f"{fichero}: falta pfsense.webui_name")
    if not NOMBRE_RE.match(nombre):
        raise ValueError(
            f"{fichero}: webui_name sólo admite letras, dígitos, punto, guion y guion bajo"
        )
    ip = str(datos.get("pfsense_ip") or "").strip()
    if not ip:
        raise ValueError(f"{fichero}: falta pfsense.pfsense_ip")
    if "://" in ip or "/" in ip or any(caracter.isspace() for caracter in ip):
        raise ValueError(f"{fichero}: pfsense_ip debe ser una IP o nombre, sin esquema ni ruta")
    try:
        puerto = int(datos.get("webui_port", DEFAULT_UPSTREAM_PORT))
    except (TypeError, ValueError):
        raise ValueError(f"{fichero}: webui_port debe ser un entero") from None
    if not 1 <= puerto <= 65535:
        raise ValueError(f"{fichero}: webui_port fuera de rango")
    return Route(nombre, ip, puerto)


def _rutas_de_fichero(fichero: Path) -> list[Route]:
    try:
        documento = yaml.safe_load(fichero.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"{fichero}: YAML inválido ({exc})") from exc
    if documento is None:
        return []
    if not isinstance(documento, dict):
        raise ValueError(f"{fichero}: el perfil debe ser un objeto YAML")
    bloque = documento.get("pfsense")
    if bloque is None:
        return []
    if not isinstance(bloque, dict):
        raise ValueError(f"{fichero}: pfsense debe ser un objeto")
    return [_ruta_desde_perfil(fichero, bloque)]


def load_profiles(entradas: list[str]) -> dict[str, Route]:
    """Carga perfiles YAML (fichero o directorio) indexados por `webui_name`."""
    ficheros: list[Path] = []
    for entrada in entradas:
        ruta = Path(entrada)
        if ruta.is_dir():
            ficheros.extend(sorted(ruta.glob("*.yaml")))
            ficheros.extend(sorted(ruta.glob("*.yml")))
        elif ruta.is_file():
            ficheros.append(ruta)
        else:
            raise ValueError(f"no existe el perfil ni el directorio: {ruta}")
    if not ficheros:
        raise ValueError("no hay ficheros YAML en los perfiles indicados")
    rutas: dict[str, Route] = {}
    for fichero in ficheros:
        for ruta in _rutas_de_fichero(fichero):
            if ruta.name in rutas:
                raise ValueError(f"webui_name duplicado: {ruta.name} ({fichero})")
            rutas[ruta.name] = ruta
    if not rutas:
        raise ValueError("ningún perfil declara pfsense.webui_name")
    return rutas


def _netloc(route: Route) -> str:
    host = route.ip
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    return f"{host}:{route.port}"


def _origen(url: str) -> tuple[str, str, int | None]:
    partes = urlsplit(url)
    puerto = partes.port
    if puerto is None:
        puerto = 443 if partes.scheme == "https" else 80
    return partes.scheme.lower(), (partes.hostname or "").lower(), puerto


class _Puerta(BaseHTTPRequestHandler):
    routes: dict[str, Route]
    protocol_version = "HTTP/1.1"
    server_version = "pf-webui-proxy"
    sys_version = ""

    def log_message(self, formato, *args):
        # Sólo método, ruta y cliente local: nunca el destino del invitado.
        sys.stderr.write(f"[pf-webui-proxy] {self.address_string()} {formato % args}\n")

    def do_GET(self):
        self._proxy()

    def do_HEAD(self):
        self._proxy()

    def do_POST(self):
        self._proxy()

    def do_PUT(self):
        self._proxy()

    def do_PATCH(self):
        self._proxy()

    def do_DELETE(self):
        self._proxy()

    def do_OPTIONS(self):
        self._proxy()

    def _responder(self, estado: int, cuerpo: bytes, cabeceras=()):
        self.send_response(estado)
        for clave, valor in cabeceras:
            self.send_header(clave, valor)
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(cuerpo)

    def _texto(self, estado: int, mensaje: str):
        self._responder(
            estado,
            (mensaje + "\n").encode("utf-8"),
            [("Content-Type", "text/plain; charset=utf-8")],
        )

    def _indice(self):
        enlaces = "\n".join(
            f'<li><a href="/{escape(nombre)}/">{escape(nombre)}</a></li>'
            for nombre in sorted(self.routes)
        )
        cuerpo = (
            "<!doctype html><html lang=\"es\"><meta charset=\"utf-8\">"
            "<title>WebUI de pfSense</title>"
            "<h1>WebUI de pfSense</h1>"
            "<p>Una ruta por perfil. La consola telnet sigue siendo la vía de configuración; "
            "la WebUI del controller GNS3 es un problema separado.</p>"
            f"<ul>{enlaces}</ul></html>\n"
        ).encode("utf-8")
        self._responder(200, cuerpo, [("Content-Type", "text/html; charset=utf-8")])

    def _proxy(self):
        partes = urlsplit(self.path)
        camino = partes.path
        if self.headers.get("Transfer-Encoding"):
            self.close_connection = True
            return self._texto(411, "411: el proxy no acepta cuerpos chunked")
        largo = self.headers.get("Content-Length")
        try:
            cuerpo = self.rfile.read(int(largo)) if largo else None
        except ValueError:
            self.close_connection = True
            return self._texto(400, "400: Content-Length inválido")
        if camino == "/":
            return self._indice()
        nombre = camino.lstrip("/").split("/", 1)[0]
        ruta = self.routes.get(nombre)
        if ruta is None:
            return self._texto(404, f"404: no hay WebUI para el perfil '{nombre}'")
        prefijo = f"/{nombre}"
        if camino == prefijo:
            destino = prefijo + "/"
            if partes.query:
                destino += f"?{partes.query}"
            return self._responder(302, b"", [("Location", destino)])
        resto = camino[len(prefijo):]
        consulta = resto + (f"?{partes.query}" if partes.query else "")

        cabeceras = {
            clave: valor
            for clave, valor in self.headers.items()
            if clave.lower() not in SALTAR and clave.lower() != "host"
        }
        base = f"https://{_netloc(ruta)}"
        try:
            conexion = http.client.HTTPSConnection(
                ruta.ip, ruta.port, timeout=TIMEOUT, context=CONTEXTO
            )
            try:
                conexion.request(self.command, consulta, body=cuerpo, headers=cabeceras)
                respuesta = conexion.getresponse()
                datos = respuesta.read()
                estado = respuesta.status
                originales = respuesta.getheaders()
            finally:
                conexion.close()
        except (OSError, http.client.HTTPException):
            return self._texto(
                502, f"502: no se pudo contactar con la WebUI del perfil '{nombre}'"
            )

        salida = [
            (clave, valor)
            for clave, valor in originales
            if clave.lower() not in SALTAR
        ]
        location = next(
            (valor for clave, valor in originales if clave.lower() == "location"), None
        )
        if location:
            absoluta = urljoin(base + consulta, location)
            if _origen(absoluta) != _origen(base + "/"):
                if estado in REDIRECT_CODES:
                    return self._texto(
                        502,
                        f"502: el perfil '{nombre}' redirige fuera de su WebUI; no se sigue",
                    )
                salida = [(c, v) for c, v in salida if c.lower() != "location"]
            else:
                destino = urlsplit(absoluta)
                nuevo = prefijo + (destino.path or "/")
                if destino.query:
                    nuevo += f"?{destino.query}"
                salida = [
                    (clave, nuevo if clave.lower() == "location" else valor)
                    for clave, valor in salida
                ]
        self._responder(estado, datos, salida)


def make_server(
    routes: dict[str, Route], host: str = "127.0.0.1", port: int = DEFAULT_PORT
) -> ThreadingHTTPServer:
    """Crea el servidor local; rechaza escuchar fuera de loopback."""
    if host not in LOOPBACK:
        raise ValueError("la puerta solo escucha en 127.0.0.1; no la expongas a la red")
    if not routes:
        raise ValueError("no hay rutas WebUI que publicar")
    handler = type("Handler", (_Puerta,), {"routes": routes})
    servidor = ThreadingHTTPServer((host, port), handler)
    servidor.daemon_threads = True
    return servidor


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="pf_webui_proxy.py",
        description="Publica cada WebUI de pfSense en http://127.0.0.1:<puerto>/<webui_name>/.",
    )
    ap.add_argument("perfiles", nargs="+", help="perfil YAML o directorio de perfiles")
    ap.add_argument("--host", default="127.0.0.1", help="escucha (solo loopback)")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT, help="puerto local (8080)")
    args = ap.parse_args(argv)
    try:
        routes = load_profiles(args.perfiles)
        servidor = make_server(routes, args.host, args.port)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"WebUI de pfSense en http://{args.host}:{servidor.server_address[1]}/")
    for nombre in sorted(routes):
        print(f"  /{nombre}/")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        servidor.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
