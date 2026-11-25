"""`Console` contra un servidor telnet falso (`socketserver.ThreadingTCPServer`)."""
import time

import pytest

from gns3core import Console

BANNER = b"VPCS v0.8.3\r\nPC1> "


def _open(srv) -> Console:
    return Console("127.0.0.1", srv.port, timeout=5)


def test_detecta_prompt_y_queda_ready(telnet_factory):
    srv = telnet_factory(on_connect=BANNER, on_line=lambda line: b"PC1> ")
    with _open(srv) as con:
        res = con.wait_ready(timeout=5)
    assert res["ready"] is True
    assert res["prompt"] == "PC1>"


def test_run_devuelve_la_salida_sin_el_eco_del_comando(telnet_factory):
    def on_line(line):
        if line == "show ip":
            return b"NAME       IP/MASK          GATEWAY\r\nPC1        192.168.1.10/24  192.168.1.1\r\nPC1> "
        return b"PC1> "

    srv = telnet_factory(on_connect=BANNER, on_line=on_line)
    with _open(srv) as con:
        assert con.wait_ready(timeout=5)["ready"] is True
        res = con.run("show ip", timeout=5)

    assert res["ok"] is True
    assert res["timed_out"] is False
    assert "192.168.1.10/24" in res["output"]
    assert "show ip" not in res["output"]
    assert "PC1>" not in res["output"]


def test_paginacion_responde_more_y_sigue(telnet_factory):
    paginas = iter([b"interface e1\r\ninterface e2\r\nPC1> ", b""])

    def on_line(line):
        if line == "show run":
            return b"interface e0\r\n--More--"
        return b"PC1> "

    srv = telnet_factory(on_connect=BANNER, on_line=on_line,
                         on_space=lambda: next(paginas, b""))
    with _open(srv) as con:
        assert con.wait_ready(timeout=5)["ready"] is True
        res = con.run("show run", timeout=8)

    assert srv.spaces >= 1, "el cliente no mandó espacio ante --More--"
    assert "interface e0" in res["output"]
    assert "interface e1" in res["output"]
    assert res["timed_out"] is False


@pytest.mark.xfail(
    strict=True,
    reason="BUG: Console.run repite 'y' mientras '[y/n]' siga en la ventana de 400 "
           "caracteres (18 respuestas medidas) y el `continue` de ASK_RE salta el "
           "chequeo de timeout, así que acaba en timed_out=True",
)
def test_confirmacion_responde_y_no_se_cuelga(telnet_factory):
    def on_line(line):
        if line == "erase startup":
            return b"Borrar la config? [y/n] "
        if line == "y":
            return b"config borrada\r\nPC1> "
        return b"PC1> "

    srv = telnet_factory(on_connect=BANNER, on_line=on_line)
    with _open(srv) as con:
        assert con.wait_ready(timeout=5)["ready"] is True
        inicio = time.time()
        res = con.run("erase startup", timeout=2.5)

    assert srv.lines.count("y") == 1, f"respuestas enviadas: {srv.lines}"
    assert res["timed_out"] is False
    assert res["ok"] is True
    assert "config borrada" in res["output"]
    assert time.time() - inicio < 3


def test_timeout_acotado_si_la_consola_no_responde(telnet_factory):
    srv = telnet_factory(
        on_connect=BANNER,
        on_line=lambda line: b"" if line == "hang" else b"PC1> ",
    )
    with _open(srv) as con:
        assert con.wait_ready(timeout=5)["ready"] is True
        inicio = time.time()
        # idle > timeout para que la quietud no tape el timeout.
        res = con.run("hang", timeout=1.0, idle=30)

    transcurrido = time.time() - inicio
    assert res["timed_out"] is True
    assert res["ok"] is False
    assert transcurrido < 4, f"tardó {transcurrido:.1f}s con timeout=1.0"
