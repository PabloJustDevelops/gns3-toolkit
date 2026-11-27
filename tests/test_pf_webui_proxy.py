"""Pruebas de la puerta WebUI de pfSense, con servidores falsos en loopback.

No hay red real: el proxy y los firewalls de mentira escuchan en 127.0.0.1 y el
certificado autofirmado se escribe en un directorio temporal. Se comprueba el
enrutado por nombre, el 404, el relaying de cuerpo/cabeceras y que un redirect
a otro host no se sigue.
"""
from __future__ import annotations

import http.client
import importlib.util
import ssl
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

RAIZ = Path(__file__).resolve().parent.parent
SCRIPT = RAIZ / "scripts" / "pf_webui_proxy.py"

CERT = """-----BEGIN CERTIFICATE-----
MIIDBDCCAeygAwIBAgIUd1Xmiin29smVPGxoDyGAS1nimYAwDQYJKoZIhvcNAQEL
BQAwFDESMBAGA1UEAwwJMTI3LjAuMC4xMB4XDTI2MTEyNzE2MDIzOVoXDTM2MTEy
NDE2MDIzOVowFDESMBAGA1UEAwwJMTI3LjAuMC4xMIIBIjANBgkqhkiG9w0BAQEF
AAOCAQ8AMIIBCgKCAQEAtPFyJi8VGi/HydFIgA42bGuouAKIL7NLbVpoMktIm3M6
nMJ4Eg81iRT2ZyT96PhvZC3MTJgREJHIHusnLOzhxd3+v03yzHN5bK5UVplIy7z1
NcmgDWno6NeWT5FqOFXsxhQ5Mzvr8e1hhgC3tVy/nr1iENwPBArrkX8ubKKpgTA8
ZwRYtbH8a4anWMInwiVw5IC7PEiM1WDacBneCUHt9pvOpLIGTo3/p2AMUxHUY5NZ
EruuugEon0prIVndSXkOUATr7dj1hiEbzmDLgc/xPl0aw5ooupv7VpJ/3uZsjFIz
6pxB9Rbp6DMEhaR6vrin39j5p4aQHfOgFhMIKMOJhwIDAQABo04wTDAdBgNVHQ4E
FgQUUY8W1DfM2P/YAcnpg83QYgUSFGUwDwYDVR0TAQH/BAUwAwEB/zAaBgNVHREE
EzARhwR/AAABgglsb2NhbGhvc3QwDQYJKoZIhvcNAQELBQADggEBAA+H+MiKkEXf
IXltAmvULt4BaFr6UofOApsbluosW5QvXTAHJONdDoA+TWBeNhKp06Qz1F7gcXhC
zEQCWZAt9HU53L9FfvMmchhh37afG4GzNw+KgKdW0rLBrUsZlAQ5eMzYNQexftHy
zbEGXlHip9pPj+5y+fIRSCZYJtO5an2NNzlRIg+cuEzojpGMqGrU26mH8oPRPXiT
84aHQZ9wGuGpbD5DEjj+oo4KZw3grojJhft0Odkm9KAiK2zzAnOVv5BmK9sRqNJ8
7MAp9gFlu6TC7QJZ3WlLmKfj0bVoAqvTb4n1sUCTQexx3HCdRamUqGxkOhBieSh8
ylpHQFyrelQ=
-----END CERTIFICATE-----
"""

KEY = """-----BEGIN PRIVATE KEY-----
MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC08XImLxUaL8fJ
0UiADjZsa6i4Aogvs0ttWmgyS0ibczqcwngSDzWJFPZnJP3o+G9kLcxMmBEQkcge
6ycs7OHF3f6/TfLMc3lsrlRWmUjLvPU1yaANaejo15ZPkWo4VezGFDkzO+vx7WGG
ALe1XL+evWIQ3A8ECuuRfy5soqmBMDxnBFi1sfxrhqdYwifCJXDkgLs8SIzVYNpw
Gd4JQe32m86ksgZOjf+nYAxTEdRjk1kSu666ASifSmshWd1JeQ5QBOvt2PWGIRvO
YMuBz/E+XRrDmii6m/tWkn/e5myMUjPqnEH1FunoMwSFpHq+uKff2PmnhpAd86AW
Ewgow4mHAgMBAAECggEASd8Y/0XRk7NWGar7smwbBACgDR/bgb3tWWPDjmT166EL
mNw8MQNMk/6e6lVL5EUpFPkto0eiD+W0kgrnH4xGUIXlbyzfp2CtfhVeEUzbT3KB
mcgLM+69S/JYR3vSpdVOqT+wap5YIZkMa6z3U2/eO2yOENwGtVvP+MK3rVprYXYi
pThddgWL+TeUUA37NCO+gD3KcU31H6iIka95Oxbpy1cGD/RBemZJbFbWtse2mr7M
8chGZQ8xww7nndT1XeNaxTUsSVvqOCKgc0Y843mFQc4s98RY/kUwdsTTKyKOLGre
11SgSLbQR0RrU4QM0QbEf3nvliQ2FpjlbrBWI3ABQQKBgQD18fDTb7UFcVY8Mcw0
DbWsgYzpZr0J2AJbnVybAhWxL2qeg/mS8GsB613uTJYmjNA7bkvQn/RhOM+3/xqR
OmU65CGFLsTfVQniUUVl83R7lyKPWgt0e00fq9M5Rz5YLzlegDpiX9dqtvT5/qVM
FnhJOszDRM5DvYTj9t+Hes+j3wKBgQC8VzIJLGTQt6OGhSAsQA/oyHwUb4v8aSBq
mC7c5PTZhI2Z2CKQiy9Q/Rsn9eNh4lhXKMTn4vYr6zMRUEhgDD0JzN6aY5thqcq2
siBBcwvisi4Km/Lkcdgc4ew6AFoH5Zo819hAb6KwFXNKZ1BQtXWNi2HfqTfuvK1i
r0cNNzaPWQKBgAN4p7qEQBzUjbAJz+UIMIE/ztpYfeCOsPHUFcOGUwIONkYIfNRL
GmeLh+beI9xlbmb4Vo+aQlvA7oWdTyWvmlAreiGkGFlCnQIZvY4D0qgP6Qf28GRz
fRIuXavYSpP6Dqg7zRcoXST/chO5OWIKiyYVc2BqLzMbkK2bBWqnHBknAoGAXjBh
NpM8C+F650BWearECg+RdgrfACl267gV36SlCs8unZyolI7259LcrNxcjcxLj7M0
3h70K7yhOmxi9Z3JPMh3HtDnmSz30uw8E188t2+SdP3OuA5zHOajY9JfNAnQW9M6
M+dgfh0MHk6SrPpCwrnNBbSz4zH6qBquNt7A62kCgYEAq6Saqw9Lb3B9WjxL0m8H
Ga0yN31k1bmjRpwkRjIjJteNEOpi/xECA6cAa0eZFhPpEHyPagBJ5abWL40CswL8
pE3WEniZnEFrKgReLxHeNyxayOo/6O8IfElCC2cuhDJwAMrjKQ6W8SeybFoTCy1G
cgVR7F18SFZl+t4ZvA8bsa4=
-----END PRIVATE KEY-----
"""


def cargar():
    spec = importlib.util.spec_from_file_location("pf_webui_proxy", SCRIPT)
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modulo
    spec.loader.exec_module(modulo)
    return modulo


class _Upstream(BaseHTTPRequestHandler):
    """Firewall de mentira: responde a las rutas que usa la suite."""

    def log_message(self, *args):  # pragma: no cover - ruido de servidor
        pass

    def _send(self, codigo, cuerpo, extra=()):
        self.send_response(codigo)
        for clave, valor in extra:
            self.send_header(clave, valor)
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def do_GET(self):
        self.server.peticiones.append(("GET", self.path))
        if self.path == "/":
            self._send(200, b"raiz-pfsense")
        elif self.path == "/index.php":
            self._send(200, b"panel-pfsense")
        elif self.path == "/redir-local":
            self.send_response(302)
            self.send_header("Location", "/index.php")
            self.send_header("Content-Length", "0")
            self.end_headers()
        elif self.path == "/redir-externo":
            self.send_response(302)
            self.send_header("Location", self.server.destino_externo)
            self.send_header("Content-Length", "0")
            self.end_headers()
        elif self.path == "/cookie":
            self._send(200, b"con-cookie", [("Set-Cookie", "sid=abc; Path=/")])
        else:
            self._send(404, b"no-existe")

    def do_POST(self):
        largo = int(self.headers.get("Content-Length", "0"))
        cuerpo = self.rfile.read(largo)
        self.server.peticiones.append(("POST", self.path, cuerpo))
        self._send(200, b"eco:" + cuerpo)


def _arrancar_upstream(cert, key, destino_externo=""):
    servidor = ThreadingHTTPServer(("127.0.0.1", 0), _Upstream)
    servidor.daemon_threads = True
    servidor.peticiones = []
    servidor.destino_externo = destino_externo
    contexto = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    contexto.load_cert_chain(str(cert), str(key))
    servidor.socket = contexto.wrap_socket(servidor.socket, server_side=True)
    hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
    hilo.start()
    return servidor


def _perfil(tmp_path, nombre, webui_name, puerto):
    ruta = tmp_path / f"{nombre}.yaml"
    ruta.write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "project": nombre,
                "pfsense": {
                    "node": "PF1",
                    "pfsense_ip": "127.0.0.1",
                    "webui_port": puerto,
                    "webui_name": webui_name,
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return ruta


@pytest.fixture(scope="module")
def certificado(tmp_path_factory):
    carpeta = tmp_path_factory.mktemp("tls")
    cert = carpeta / "cert.pem"
    key = carpeta / "key.pem"
    cert.write_text(CERT, encoding="utf-8")
    key.write_text(KEY, encoding="utf-8")
    return cert, key


@pytest.fixture()
def puerta(tmp_path, certificado):
    modulo = cargar()
    a = _arrancar_upstream(*certificado)
    b = _arrancar_upstream(*certificado)
    perfiles = [
        _perfil(tmp_path, "ejemplo-a", "pfsense-ejemplo-a", a.server_address[1]),
        _perfil(tmp_path, "ejemplo-b", "pfsense-ejemplo-b", b.server_address[1]),
    ]
    rutas = modulo.load_profiles(perfiles)
    servidor = modulo.make_server(rutas, "127.0.0.1", 0)
    hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
    hilo.start()
    yield SimpleNamespace(
        modulo=modulo,
        direccion=("127.0.0.1", servidor.server_address[1]),
        a=a,
        b=b,
    )
    servidor.shutdown()
    servidor.server_close()
    for upstream in (a, b):
        upstream.shutdown()
        upstream.server_close()


def pedir(puerta, metodo, ruta, cuerpo=None, cabeceras=None):
    conexion = http.client.HTTPConnection(*puerta.direccion, timeout=5)
    try:
        conexion.request(metodo, ruta, body=cuerpo, headers=cabeceras or {})
        respuesta = conexion.getresponse()
        return respuesta.status, dict(respuesta.getheaders()), respuesta.read()
    finally:
        conexion.close()


def test_indice_lista_las_dos_puertas(puerta):
    estado, _, cuerpo = pedir(puerta, "GET", "/")
    assert estado == 200
    assert b"pfsense-ejemplo-a" in cuerpo
    assert b"pfsense-ejemplo-b" in cuerpo


def test_cada_nombre_va_a_su_perfil(puerta):
    estado_a, _, cuerpo_a = pedir(puerta, "GET", "/pfsense-ejemplo-a/")
    estado_b, _, cuerpo_b = pedir(puerta, "GET", "/pfsense-ejemplo-b/")
    assert (estado_a, cuerpo_a) == (200, b"raiz-pfsense")
    assert (estado_b, cuerpo_b) == (200, b"raiz-pfsense")
    assert puerta.a.peticiones == [("GET", "/")]
    assert puerta.b.peticiones == [("GET", "/")]


def test_nombre_desconocido_es_404(puerta):
    estado, _, cuerpo = pedir(puerta, "GET", "/pfsense-inventado/")
    assert estado == 404
    assert b"no hay WebUI" in cuerpo
    assert puerta.a.peticiones == []
    assert puerta.b.peticiones == []


def test_sin_barra_final_redirige_al_prefijo(puerta):
    estado, cabeceras, _ = pedir(puerta, "GET", "/pfsense-ejemplo-a?x=1")
    assert estado == 302
    assert cabeceras["Location"] == "/pfsense-ejemplo-a/?x=1"


def test_redirect_local_se_reescribe_al_proxy(puerta):
    estado, cabeceras, _ = pedir(puerta, "GET", "/pfsense-ejemplo-a/redir-local")
    assert estado == 302
    assert cabeceras["Location"] == "/pfsense-ejemplo-a/index.php"
    estado_final, _, cuerpo = pedir(puerta, "GET", cabeceras["Location"])
    assert (estado_final, cuerpo) == (200, b"panel-pfsense")


def test_redirect_a_otro_host_no_se_sigue(tmp_path, certificado):
    modulo = cargar()
    # El firewall redirige a un tercer servidor, que no debe recibir la petición.
    externo = _arrancar_upstream(*certificado)
    ajeno = _arrancar_upstream(
        *certificado,
        destino_externo=f"https://127.0.0.1:{externo.server_address[1]}/robo",
    )
    perfiles = [_perfil(tmp_path, "ejemplo", "pfsense-ejemplo", ajeno.server_address[1])]
    servidor = modulo.make_server(modulo.load_profiles(perfiles), "127.0.0.1", 0)
    hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
    hilo.start()
    try:
        estado, cabeceras, cuerpo = pedir(
            SimpleNamespace(direccion=("127.0.0.1", servidor.server_address[1])),
            "GET",
            "/pfsense-ejemplo/redir-externo",
        )
    finally:
        servidor.shutdown()
        servidor.server_close()
        for s in (ajeno, externo):
            s.shutdown()
            s.server_close()
    assert estado == 502
    assert "Location" not in cabeceras
    assert b"127.0.0.1" not in cuerpo
    assert externo.peticiones == []


def test_post_conserva_el_cuerpo(puerta):
    estado, _, cuerpo = pedir(
        puerta,
        "POST",
        "/pfsense-ejemplo-a/form.php",
        cuerpo=b"a=1&b=2",
        cabeceras={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert estado == 200
    assert cuerpo == b"eco:a=1&b=2"
    assert puerta.a.peticiones == [("POST", "/form.php", b"a=1&b=2")]


def test_cookie_se_relaya(puerta):
    estado, cabeceras, _ = pedir(puerta, "GET", "/pfsense-ejemplo-a/cookie")
    assert estado == 200
    assert cabeceras["Set-Cookie"] == "sid=abc; Path=/"


def test_ejemplos_del_repo_se_cargan():
    modulo = cargar()
    rutas = modulo.load_profiles([str(RAIZ / "examples" / "pf-perfiles")])
    assert sorted(rutas) == ["pfsense-ejemplo-a", "pfsense-ejemplo-b"]
    assert rutas["pfsense-ejemplo-a"].ip != rutas["pfsense-ejemplo-b"].ip


def test_perfil_sin_webui_name_falla(tmp_path):
    modulo = cargar()
    ruta = tmp_path / "incompleto.yaml"
    ruta.write_text(
        yaml.safe_dump({"pfsense": {"pfsense_ip": "127.0.0.1"}}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="webui_name"):
        modulo.load_profiles([ruta])


def test_nombres_duplicados_fallan(tmp_path):
    modulo = cargar()
    a = _perfil(tmp_path, "a", "pfsense-repetido", 443)
    b = _perfil(tmp_path, "b", "pfsense-repetido", 443)
    with pytest.raises(ValueError, match="pfsense-repetido"):
        modulo.load_profiles([a, b])


def test_host_no_loopback_se_rechaza(puerta):
    with pytest.raises(ValueError, match="127.0.0.1"):
        puerta.modulo.make_server({}, "0.0.0.0", 0)
