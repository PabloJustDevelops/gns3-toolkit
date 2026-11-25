"""Contrato del `--json` global de la CLI con handlers falsos."""
from __future__ import annotations

import importlib.util
import inspect
import json
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest

CLI_PATH = Path(__file__).resolve().parents[1] / "cli" / "gns3lab"
LOADER = SourceFileLoader("gns3lab_json_extests", str(CLI_PATH))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
assert SPEC is not None
cli = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = cli
LOADER.exec_module(cli)


def _has_global_json() -> bool:
    """Comprueba el contrato sin ejecutar `main()` ni tocar la configuración real."""
    source = inspect.getsource(cli.main).split("add_subparsers", 1)[0]
    return '"--json"' in source or "'--json'" in source


requires_global_json = pytest.mark.skipif(
    not _has_global_json(),
    reason="BRIEF-jsoncli pendiente: main() no declara --json global",
)


@pytest.fixture
def run_cli(monkeypatch, tmp_path):
    """Aísla la configuración y permite sustituir el handler de un subcomando."""
    conf_path = tmp_path / "gns3lab.json"
    conf_path.write_text("{}")
    monkeypatch.setattr(cli, "CONF", conf_path)
    monkeypatch.setattr(cli, "load_conf", lambda: {
        "servers": {},
        "default_server": "local",
    })

    def run(argv, handler_name, handler):
        monkeypatch.setattr(sys, "argv", ["gns3lab", *argv])
        monkeypatch.setattr(cli, handler_name, handler)
        return cli.main()

    return run


@requires_global_json
def test_json_valido_se_pasa_tal_cual(run_cli, capsys):
    raw = '{\n  "version": "2.2.61",\n  "ok": true\n}\n'

    def handler(args, conf):
        assert args.cmd == "status"
        sys.stdout.write(raw)
        return 0

    rc = run_cli(["--json", "status"], "cmd_status", handler)

    captured = capsys.readouterr()
    assert rc == 0
    assert captured.out == raw
    assert captured.err == ""


@requires_global_json
@pytest.mark.parametrize("rc", [0, 7])
def test_texto_se_envuelve_y_se_conserva_el_exit_code(run_cli, capsys, rc):
    def handler(args, conf):
        assert args.cmd == "status"
        sys.stdout.write("linea uno\nlinea dos")
        return rc

    result = run_cli(["--json", "status"], "cmd_status", handler)

    captured = capsys.readouterr()
    assert result == rc
    assert json.loads(captured.out) == {
        "cmd": "status",
        "ok": rc == 0,
        "output": "linea uno\nlinea dos",
    }
    assert captured.err == ""


@requires_global_json
def test_stderr_no_se_captura(run_cli, capsys):
    def handler(args, conf):
        print("salida normal")
        print("aviso por stderr", file=sys.stderr)
        return 3

    result = run_cli(["--json", "status"], "cmd_status", handler)

    captured = capsys.readouterr()
    assert result == 3
    assert json.loads(captured.out) == {
        "cmd": "status",
        "ok": False,
        "output": "salida normal",
    }
    assert captured.err == "aviso por stderr\n"


@requires_global_json
def test_system_exit_conserva_su_codigo(run_cli, capsys):
    def handler(args, conf):
        print("no se pudo completar")
        raise SystemExit(9)

    result = run_cli(["--json", "status"], "cmd_status", handler)

    captured = capsys.readouterr()
    assert result == 9
    assert json.loads(captured.out) == {
        "cmd": "status",
        "ok": False,
        "output": "no se pudo completar",
    }
    assert captured.err == ""


@requires_global_json
def test_json_local_no_se_convierte_en_doble_json(run_cli, capsys):
    raw = '{"ok":false,"problems":["sin VPCS"]}\n'

    def handler(args, conf):
        assert args.cmd == "doctor"
        assert args.json is True
        sys.stdout.write(raw)
        return 1

    result = run_cli(["--json", "doctor", "--json"], "cmd_doctor", handler)

    captured = capsys.readouterr()
    assert result == 1
    assert captured.out == raw
    assert json.loads(captured.out) == {"ok": False, "problems": ["sin VPCS"]}
    assert captured.err == ""
