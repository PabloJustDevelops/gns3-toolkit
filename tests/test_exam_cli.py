"""Contrato de `gns3lab examen` con Namespace y API GNS3 falsos."""
from __future__ import annotations

import importlib.util
import json
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path
from types import SimpleNamespace

import pytest

CLI_PATH = Path(__file__).resolve().parents[1] / "cli" / "gns3lab"
LOADER = SourceFileLoader("gns3lab_extests", str(CLI_PATH))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
assert SPEC is not None
cli = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = cli
LOADER.exec_module(cli)

EXAM_READY = callable(getattr(cli, "cmd_examen", None))
requires_exam = pytest.mark.skipif(
    not EXAM_READY,
    reason="BRIEF-examcli pendiente: falta el handler cmd_examen",
)


@pytest.fixture
def exam_conf(fake_api):
    """Configuración aislada: el único servidor posible es el API falso."""
    project = {
        "project_id": "11111111-aaaa-bbbb-cccc-000000000001",
        "name": "Kit de examen",
        "status": "opened",
    }
    fake_api.set_projects([project])
    fake_api.route("GET", f"/v2/projects/{project['project_id']}", 200, project)
    fake_api.set_nodes(project["project_id"], [])
    fake_api.route("GET", f"/v2/projects/{project['project_id']}/links", 200, [])
    fake_api.route("GET", "/v2/templates", 200, [])
    fake_api.route("GET", "/v2/computes", 200, [])
    fake_api.route("GET", "/v2/computes/local", 200, {"compute_id": "local"})
    fake_api.route("GET", "/v2/computes/local/qemu/images", 200, [])
    return {
        "servers": {
            "prueba": {"url": fake_api.url, "auth": None},
        },
        "default_server": "prueba",
    }


def _args(action: str, **overrides) -> SimpleNamespace:
    values = {
        "action": action,
        "server": "prueba",
        "name": "Kit de examen",
        "from_project": None,
        "json": False,
        "yes": False,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@requires_exam
def test_examen_verify_json_devuelve_ok_y_problems(exam_conf, fake_api, capsys):
    try:
        cli.cmd_examen(_args("verify", json=True), exam_conf)
    except SystemExit as exc:
        assert exc.code not in (None, 0)

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert isinstance(payload["ok"], bool)
    assert isinstance(payload["problems"], list)
    assert payload["ok"] is False
    assert payload["problems"]


@requires_exam
def test_examen_reset_sin_yes_se_rechaza_antes_de_tocar_servidor(
    exam_conf, fake_api, capsys
):
    try:
        result = cli.cmd_examen(_args("reset"), exam_conf)
    except SystemExit as exc:
        result = exc.code

    assert result not in (None, 0)
    captured = capsys.readouterr()
    assert "--yes" in captured.out + captured.err
    assert fake_api.requests == []
