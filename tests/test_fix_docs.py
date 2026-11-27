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
    # 931 es el recuento de la base del brief; este fichero añade tres tests de regresión.
    assert "**931 tests**" in texto


def test_agents_md_documenta_python_m_pytest():
    texto = AGENTS.read_text(encoding="utf-8")
    assert "python -m pytest -q" in texto
    for numero, linea in enumerate(texto.splitlines(), 1):
        if re.search(r"(?<![\w.-])pytest\s+-q", linea):
            assert "-m pytest" in linea, f"AGENTS.md:{numero}: pytest -q sin -m"


def test_verify_detecta_deriva_en_agents_md(tmp_path):
    """El guard debe mirar AGENTS.md, no sólo README/PROJECT/docs."""
    root = tmp_path / "repo"
    (root / "cli").mkdir(parents=True)
    (root / "docs").mkdir()
    (root / "scripts").mkdir()
    for nombre in ("gns3core.py", "gns3_mcp_server.py"):
        shutil.copy2(REPO / nombre, root / nombre)
    shutil.copy2(REPO / "cli/gns3lab", root / "cli/gns3lab")
    shutil.copy2(REPO / "scripts/install.sh", root / "scripts/install.sh")
    cifras = verify.count_all(root)
    (root / "README.md").write_text(
        f"# repo\n\n{cifras['areas']} áreas, {cifras['tools']} tools, "
        f"{cifras['comandos']} comandos.\n", encoding="utf-8")
    (root / "PROJECT.md").write_text("# proyecto\n\nSin cifras.\n", encoding="utf-8")
    (root / "docs/GUI-PORTADA.md").write_text("# portada\n\nSin cifras.\n", encoding="utf-8")
    (root / "AGENTS.md").write_text("# agentes\n\nCLI de 1 comandos.\n", encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, str(VERIFY), str(root)],
        cwd=REPO, capture_output=True, text=True,
    )
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "AGENTS.md:3" in proc.stdout, proc.stdout
