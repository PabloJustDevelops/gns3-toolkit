"""Ramas de `Console` que un servidor telnet sano no produce a demanda."""
import time

import pytest

import gns3core
from gns3core import Console, ConsoleError, console_for

BANNER = b"VPCS v0.8.3\r\nPC1> "


def _open(srv) -> Console:
    return Console("127.0.0.1", srv.port, timeout=5)


# ─────────────────────────────── vida y socket ───────────────────────────────
def test_close_marca_cerrado_y_traga_el_oserror(telnet_factory, stub_sock):
    con = _open(telnet_factory(on_connect=BANNER))
    con.sock = stub_sock(close_exc=OSError("socket ya cerrado"))
    con.close()
    assert con.closed is True


def test_send_sobre_socket_roto_lanza_consoleerror(telnet_factory, stub_sock):
    con = _open(telnet_factory(on_connect=BANNER))
    con.sock = stub_sock(send_exc=BrokenPipeError("roto"))
    with pytest.raises(ConsoleError, match="se cerró al escribir"):
        con.send("hola")
    assert con.closed is True


def test_pump_con_eof_marca_cerrado(telnet_factory, stub_sock):
    con = _open(telnet_factory(on_connect=BANNER))
    con.sock = stub_sock(recv=[b""])
    assert con.drain(0.1) == ""
    assert con.closed is True


def test_pump_con_oserror_marca_cerrado(telnet_factory, stub_sock):
    con = _open(telnet_factory(on_connect=BANNER))
    con.sock = stub_sock(recv=[OSError("el par se fue")])
    assert con.drain(0.1) == ""
    assert con.closed is True


def test_wake_manda_enter_y_devuelve_la_respuesta(telnet_factory):
    srv = telnet_factory(on_connect=BANNER, on_line=lambda line: b"PC1> ")
    with _open(srv) as con:
        salida = con.wake(seconds=0.2)
    assert "" in srv.lines
    assert "PC1>" in salida


# ──────────────────────────────── wait_ready ────────────────────────────────
def test_wait_ready_con_expect_no_espera_al_prompt(telnet_factory):
    srv = telnet_factory(on_connect=b"arrancando\r\nSISTEMA LISTO\r\n")
    with _open(srv) as con:
        res = con.wait_ready(timeout=5, expect="SISTEMA LISTO")
    assert res["ready"] is True
    assert res["prompt"] == "SISTEMA LISTO"
    assert "SISTEMA LISTO" in res["output"]


def test_wait_ready_pulsa_enter_en_grub(telnet_factory):
    def on_line(line):
        if line == "":
            return b"Booting from hard disk...\r\nPC1> "
        return b"PC1> "

    srv = telnet_factory(on_connect=b"GNU GRUB version 2.06\r\n", on_line=on_line)
    inicio = time.time()
    with _open(srv) as con:
        res = con.wait_ready(timeout=5, grub_retries=1)
    assert res["ready"] is True
    assert res["prompt"] == "PC1>"
    assert srv.lines.count("") >= 2, f"no pulsó Enter en GRUB: {srv.lines}"
    assert time.time() - inicio < 5


def test_wait_ready_devuelve_no_ready_sin_prompt(telnet_factory):
    srv = telnet_factory(on_connect=b"", on_line=lambda line: b"")
    with _open(srv) as con:
        res = con.wait_ready(timeout=1.0)
    assert res["ready"] is False
    assert res["prompt"] is None
    assert res["output"].strip() == ""


# ─────────────────────────────────── run ───────────────────────────────────
def test_run_para_en_cuanto_aparece_el_expect(telnet_factory):
    def on_line(line):
        return b"LISTO\r\n" if line == "go" else b"PC1> "

    srv = telnet_factory(on_connect=BANNER, on_line=on_line)
    with _open(srv) as con:
        assert con.wait_ready(timeout=5)["ready"] is True
        inicio = time.time()
        res = con.run("go", expect="LISTO", timeout=5, idle=30)

    assert "LISTO" in res["output"]
    assert res["ok"] is True
    assert res["eof"] is False
    assert res["matched"] is True
    assert res["timed_out"] is False
    assert time.time() - inicio < 2, "el expect no cortó la espera"


def test_run_con_eof_no_cumple_expect_ni_es_exito(telnet_factory, stub_sock):
    con = _open(telnet_factory(on_connect=BANNER))
    con.sock = stub_sock(recv=[b""])

    res = con.run("show ip", expect="LISTO", timeout=1, idle=0.01)

    assert res["ok"] is False
    assert res["eof"] is True
    assert res["matched"] is False
    assert res["timed_out"] is False


def test_run_con_quietud_sin_expect_no_es_exito(telnet_factory, stub_sock):
    con = _open(telnet_factory(on_connect=BANNER))
    con.sock = stub_sock()

    res = con.run("show ip", expect="LISTO", timeout=1, idle=0.01)

    assert res["ok"] is False
    assert res["eof"] is False
    assert res["matched"] is False
    assert res["timed_out"] is False


def test_run_timeout_es_distinto_de_eof_y_expect_incumplido(telnet_factory, stub_sock):
    con = _open(telnet_factory(on_connect=BANNER))
    con.sock = stub_sock()

    res = con.run("show ip", expect="LISTO", timeout=0.02, idle=30)

    assert res["ok"] is False
    assert res["eof"] is False
    assert res["matched"] is False
    assert res["timed_out"] is True


def test_run_responde_al_prompt_de_password_una_sola_vez(telnet_factory):
    def on_line(line):
        if line == "enable":
            return b"Password: "
        if line == "s3creto":
            return b"modo enable\r\nPC1# "
        return b"PC1> "

    srv = telnet_factory(on_connect=BANNER, on_line=on_line)
    with _open(srv) as con:
        assert con.wait_ready(timeout=5)["ready"] is True
        res = con.run("enable", password="s3creto", timeout=5)

    assert "modo enable" in res["output"]
    assert srv.lines.count("s3creto") == 1, f"contestó {srv.lines}"


def test_run_sale_si_la_consola_ya_esta_cerrada(telnet_factory, stub_sock):
    con = _open(telnet_factory(on_connect=BANNER))
    con.sock = stub_sock()
    con.closed = True
    res = con.run("show ip", timeout=1)
    assert res["timed_out"] is False


def test_run_deja_de_paginar_tras_200_paginas(telnet_factory, monkeypatch, stub_sock):
    """La guarda de `more_hits > 200` evita un bucle infinito con `--More--` eterno."""
    con = _open(telnet_factory(on_connect=BANNER))
    con.sock = stub_sock()
    paginas = {"n": 0}

    def pump(_seconds):
        paginas["n"] += 1
        return "--More--" if paginas["n"] <= 201 else ""

    monkeypatch.setattr(con, "_pump", pump)
    res = con.run("show run", timeout=5, idle=0.05)
    assert res["more_pages"] == 201
    assert con.sock.sent.count(b" ") == 201


# ──────────────────────────────── run_many ────────────────────────────────
def test_run_many_encadena_y_para_al_primer_timeout(telnet_factory):
    def on_line(line):
        if line == "uno":
            return b"RESPUESTA UNO\r\nPC1> "
        if line == "dos":
            return b""                      # se cuelga: sólo el eco
        return b"PC1> "

    srv = telnet_factory(on_connect=BANNER, on_line=on_line)
    with _open(srv) as con:
        assert con.wait_ready(timeout=5)["ready"] is True
        # El primer comando corta por `expect`; el segundo se queda sin respuesta
        # y agota el timeout antes de que la quietud lo tape.
        res = con.run_many(["uno", "dos", "tres"], expect="RESPUESTA UNO", timeout=0.8)

    assert [r["cmd"] for r in res] == ["uno", "dos"]
    assert res[0]["timed_out"] is False
    assert res[1]["timed_out"] is True
    assert "tres" not in srv.lines, "siguió tras el timeout"


def test_run_many_para_si_no_se_cumple_expect(telnet_factory):
    def on_line(line):
        return b"RESPUESTA UNO\r\nPC1> " if line == "uno" else b"PC1> "

    srv = telnet_factory(on_connect=BANNER, on_line=on_line)
    with _open(srv) as con:
        assert con.wait_ready(timeout=5)["ready"] is True
        res = con.run_many(["uno", "dos"], expect="LISTO", timeout=1, idle=0.01)

    assert [r["cmd"] for r in res] == ["uno"]
    assert res[0]["ok"] is False
    assert res[0]["eof"] is False
    assert res[0]["matched"] is False
    assert "dos" not in srv.lines, "siguió tras no cumplir expect"


def test_shell_es_alias_de_run(telnet_factory):
    srv = telnet_factory(on_connect=BANNER, on_line=lambda line: b"ok\r\nPC1> ")
    with _open(srv) as con:
        assert con.wait_ready(timeout=5)["ready"] is True
        res = con.shell("comando", timeout=2)
    assert res["cmd"] == "comando"
    assert "ok" in res["output"]


# ─────────────────────────────── console_for ───────────────────────────────
def test_console_for_rechaza_consola_no_telnet():
    node = {"name": "R1", "node_id": "n1", "console_type": "vnc", "console": 5000}
    with pytest.raises(ConsoleError, match="no telnet"):
        console_for(gns3core.Client("http://127.0.0.1:1"), "p1", node)


def test_console_for_pide_el_puerto_al_detalle_si_falta(fake_api, telnet_factory):
    srv = telnet_factory(on_connect=BANNER)
    fake_api.route("GET", "/v2/projects/p1/nodes/n1", 200,
                   {"console": srv.port, "console_type": "telnet"})
    node = {"name": "PC1", "node_id": "n1", "console_type": "telnet", "console": None}

    con = console_for(gns3core.Client(fake_api.url), "p1", node)
    try:
        assert con.port == srv.port
        assert con.host == "127.0.0.1"
    finally:
        con.close()


def test_console_for_falla_si_el_detalle_tampoco_trae_puerto(fake_api):
    fake_api.route("GET", "/v2/projects/p1/nodes/n1", 200, {"console": None})
    node = {"name": "PC1", "node_id": "n1", "console_type": "telnet", "console": 0}
    with pytest.raises(ConsoleError, match="no expone puerto de consola"):
        console_for(gns3core.Client(fake_api.url), "p1", node)


def test_console_for_normaliza_el_host_comodin(fake_api, telnet_factory):
    srv = telnet_factory(on_connect=BANNER)
    node = {"name": "PC1", "node_id": "n1", "console_type": "telnet",
            "console": srv.port, "console_host": "0.0.0.0"}
    con = console_for(gns3core.Client(fake_api.url), "p1", node)
    try:
        assert con.host == "127.0.0.1"
    finally:
        con.close()


def test_console_for_normaliza_el_host_vacio(fake_api, telnet_factory):
    srv = telnet_factory(on_connect=BANNER)
    node = {"name": "PC1", "node_id": "n1", "console_type": "Telnet",
            "console": srv.port, "console_host": ""}
    con = console_for(gns3core.Client(fake_api.url), "p1", node)
    try:
        assert con.host == "127.0.0.1"
    finally:
        con.close()
