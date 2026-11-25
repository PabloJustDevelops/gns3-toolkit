"""`QemuMonitor` contra un HMP falso que imita el eco ANSI de QEMU."""
import time

from gns3core import QemuMonitor


def _esperar_comandos(srv, n, timeout=2.0):
    fin = time.time() + timeout
    while len(srv.commands) < n and time.time() < fin:
        time.sleep(0.01)
    return srv.commands


def test_run_info_status_sin_eco(hmp_factory):
    srv = hmp_factory()
    with QemuMonitor(srv.port) as mon:
        res = mon.run("info status")

    assert res["output"] == "VM status: running"
    assert res["error"] is None
    assert "\x1b" not in res["output"]
    assert srv.commands == ["info status"]


def test_run_rellena_error_con_la_linea_error(hmp_factory):
    srv = hmp_factory()
    srv.responses["sendkey nope"] = "Error: invalid key name"
    with QemuMonitor(srv.port) as mon:
        res = mon.run("sendkey nope")

    assert res["error"] == "invalid key name"
    assert "Error: invalid key name" in res["output"]


def test_type_text_traduce_cada_caracter_a_sendkey(hmp_factory):
    srv = hmp_factory()
    with QemuMonitor(srv.port) as mon:
        res = mon.type_text("A-:@ ?", delay=0, wake=False)
        comandos = _esperar_comandos(srv, 6)

    assert res["unknown"] == []
    assert res["keys_sent"] == 6
    assert comandos == [
        "sendkey shift-a",
        "sendkey minus",
        "sendkey shift-semicolon",
        "sendkey shift-2",
        "sendkey spc",
        "sendkey shift-slash",
    ]


def test_type_text_despierta_antes_de_la_primera_tecla(hmp_factory):
    srv = hmp_factory()
    with QemuMonitor(srv.port) as mon:
        mon.type_text("a", delay=0)
        comandos = _esperar_comandos(srv, 2)

    assert comandos[:2] == ["sendkey shift", "sendkey a"]


def test_type_text_ignora_caracteres_sin_tecla(hmp_factory):
    srv = hmp_factory()
    with QemuMonitor(srv.port) as mon:
        res = mon.type_text("añ", delay=0, wake=False)
        comandos = _esperar_comandos(srv, 1)

    assert res["unknown"] == ["ñ"]
    assert res["keys_sent"] == 1
    assert comandos == ["sendkey a"]
