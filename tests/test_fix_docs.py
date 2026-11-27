"""Regresión del hallazgo 1: AGENTS.md debe reflejar cifras reales y el pytest que funciona."""
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
AGENTS = REPO / "AGENTS.md"
SCRIPTS = REPO / "scripts"
VERIFY = SCRIPTS / "verify.py"

sys.path.insert(0, str(SCRIPTS))
import verify  # noqa: E402  (helper de conteo, sin dependencias de terceros)


def test_agents_md_cifras_reales():
    texto = AGENTS.read_text(encoding="utf-8")
    reales = verify.count_all(REPO)
    assert f"**{reales['comandos']} comandos**" in texto
    assert f"**{verify.count_tests(REPO)} tests**" in texto


def test_agents_md_documenta_python_m_pytest():
    texto = AGENTS.read_text(encoding="utf-8")
    assert "python -m pytest -q" in texto
    for numero, linea in enumerate(texto.splitlines(), 1):
        if re.search(r"(?<![\w.-])pytest\s+-q", linea):
            assert "-m pytest" in linea, f"AGENTS.md:{numero}: pytest -q sin -m"


def _repo_minimo(tmp_path, agents: str) -> Path:
    """Repo con código real, docs coherentes y el AGENTS.md que se quiera probar."""
    root = tmp_path / "repo"
    (root / "cli").mkdir(parents=True)
    (root / "docs").mkdir()
    (root / "scripts").mkdir()
    (root / "tests").mkdir()
    for nombre in ("gns3core.py", "gns3_mcp_server.py"):
        shutil.copy2(REPO / nombre, root / nombre)
    shutil.copy2(REPO / "cli/gns3lab", root / "cli/gns3lab")
    shutil.copy2(REPO / "scripts/install.sh", root / "scripts/install.sh")
    (root / "tests" / "test_muestra.py").write_text(
        "def test_uno():\n    pass\n\ndef test_dos():\n    pass\n", encoding="utf-8")
    cifras = verify.count_all(root)
    (root / "README.md").write_text(
        f"# repo\n\n{cifras['areas']} áreas, {cifras['tools']} tools, "
        f"{cifras['comandos']} comandos.\n", encoding="utf-8")
    (root / "PROJECT.md").write_text("# proyecto\n\nSin cifras.\n", encoding="utf-8")
    (root / "docs/GUI-PORTADA.md").write_text("# portada\n\nSin cifras.\n", encoding="utf-8")
    (root / "AGENTS.md").write_text(agents, encoding="utf-8")
    return root


def _verificar(root):
    return subprocess.run(
        [sys.executable, str(VERIFY), str(root)],
        cwd=REPO, capture_output=True, text=True,
    )


def test_verify_detecta_deriva_en_agents_md(tmp_path):
    """El guard debe mirar AGENTS.md, no sólo README/PROJECT/docs."""
    root = _repo_minimo(tmp_path, "# agentes\n\nCLI de 1 comandos.\n")
    proc = _verificar(root)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "AGENTS.md:3" in proc.stdout, proc.stdout


def test_verify_detecta_numero_de_tests_desfasado(tmp_path):
    """Un recuento de tests viejo en AGENTS.md debe hacer fallar el guard."""
    root = _repo_minimo(tmp_path, "# agentes\n\nLa suite tiene **7 tests**.\n")
    proc = _verificar(root)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "AGENTS.md:3" in proc.stdout, proc.stdout
    assert "7 tests" in proc.stdout and "2 tests" in proc.stdout, proc.stdout


def test_verify_detecta_pytest_sin_m_en_agents_md(tmp_path):
    """`pytest -q` a secas no arranca: el guard debe señalarlo."""
    root = _repo_minimo(
        tmp_path, "# agentes\n\nLa suite tiene **2 tests**.\n\npytest -q\n")
    proc = _verificar(root)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "AGENTS.md:5" in proc.stdout and "-m pytest" in proc.stdout, proc.stdout
