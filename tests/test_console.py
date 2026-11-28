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


# ─────────────────────── prompts terminados en `:` (#37) ───────────────────────
PFSENSE_PROMPT = b"[2.7.2-RELEASE][root@pfSense.home.arpa]/root: "


def test_wait_ready_detecta_el_shell_de_pfsense(telnet_factory):
    srv = telnet_factory(on_connect=PFSENSE_PROMPT, on_line=lambda line: PFSENSE_PROMPT)
    with _open(srv) as con:
        res = con.wait_ready(timeout=5)
    assert res["ready"] is True
    assert res["prompt"] == "[2.7.2-RELEASE][root@pfSense.home.arpa]/root:"


def test_wait_ready_detecta_el_menu_de_pfsense(telnet_factory):
    menu = b"*** Welcome to pfSense ***\r\n\r\nEnter an option: "
    srv = telnet_factory(on_connect=menu, on_line=lambda line: menu)
    with _open(srv) as con:
        res = con.wait_ready(timeout=5)
    assert res["ready"] is True
    assert res["prompt"] == "Enter an option:"


def test_wait_ready_detecta_un_shell_usuario_host_sin_corchetes(telnet_factory):
    prompt = b"root@fw1:/root: "
    srv = telnet_factory(on_connect=prompt, on_line=lambda line: prompt)
    with _open(srv) as con:
        res = con.wait_ready(timeout=5)
    assert res["ready"] is True
    assert res["prompt"] == "root@fw1:/root:"


@pytest.mark.parametrize("banner,prompt", [
    (b"Cisco IOS XE\r\nR1# ", "R1#"),
    (b"R1>", "R1>"),
    (b"VPCS v0.8.3\r\nPC1> ", "PC1>"),
    (b"Switch(config)# ", "Switch(config)#"),
    (b"[root@lab ~]# ", "[root@lab ~]#"),
    (b"usuario@host:~$ ", "usuario@host:~$"),
    (b"pablo% ", "pablo%"),
])
def test_wait_ready_conserva_los_prompts_de_siempre(telnet_factory, banner, prompt):
    srv = telnet_factory(on_connect=banner, on_line=lambda line: banner)
    with _open(srv) as con:
        res = con.wait_ready(timeout=5)
    assert res["ready"] is True
    assert res["prompt"] == prompt


@pytest.mark.parametrize("banner", [
    b"Arrancando...\r\nStarting NTP client:\r\nlogin as: ",
    b"login as: ",
    b"Password: ",
    b"Starting local daemons: nuage.",
])
def test_wait_ready_no_confunde_lineas_con_dos_puntos_con_un_prompt(telnet_factory, banner):
    srv = telnet_factory(on_connect=banner, on_line=lambda line: banner)
    with _open(srv) as con:
        res = con.wait_ready(timeout=0.8)
    assert res["ready"] is False
    assert res["prompt"] is None
