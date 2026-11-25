"""Guard de deriva: verify.py debe leer el código y no fiarse de las cifras escritas."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts"
VERIFY = SCRIPTS / "verify.py"

sys.path.insert(0, str(SCRIPTS))
import verify  # noqa: E402  (helper de conteo, sin dependencias de terceros)


def ejecutar(root):
    return subprocess.run(
        [sys.executable, str(VERIFY), str(root)],
        cwd=REPO, capture_output=True, text=True,
    )


def repo_limpio(tmp_path):
    """Copia del código real con documentación coherente, derivada de ese código."""
    root = tmp_path / "repo"
    (root / "cli").mkdir(parents=True)
    (root / "docs").mkdir()
    (root / "scripts").mkdir()
    (root / "skill-sync").mkdir()
    for nombre in ("gns3core.py", "gns3_mcp_server.py"):
        shutil.copy2(REPO / nombre, root / nombre)
    shutil.copy2(REPO / "cli" / "gns3lab", root / "cli" / "gns3lab")
    shutil.copy2(REPO / "scripts" / "install.sh", root / "scripts" / "install.sh")
    cifras = verify.count_all(root)
    (root / "README.md").write_text(
        f"# repo\n\n{json.dumps(cifras, sort_keys=True)}\n"
        f"{cifras['areas']} áreas, {cifras['tools']} tools, "
        f"{cifras['comandos']} comandos.\n",
        encoding="utf-8",
    )
    (root / "PROJECT.md").write_text(
        f"# proyecto\n\n{cifras['tools']} tools y {cifras['comandos']} comandos; "
        f"{cifras['areas']} áreas.\n",
        encoding="utf-8",
    )
    (root / "docs" / "GUI-PORTADA.md").write_text(
        f"# portada\n\n{cifras['areas']} áreas y {cifras['tools']} tools.\n",
        encoding="utf-8",
    )
    (root / "skill-sync" / "SKILL.md").write_text(
        f"# skill\n\n{cifras['tools']} tools, {cifras['comandos']} comandos, "
        f"{cifras['areas']} áreas.\n",
        encoding="utf-8",
    )
    return root


def test_verifica_repo_limpio_sin_hallazgos(tmp_path):
    resultado = ejecutar(repo_limpio(tmp_path))
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr
    assert "OK" in resultado.stdout
    assert "DRIFT" not in resultado.stdout


def test_cifra_falsa_en_readme_da_drift(tmp_path):
    root = repo_limpio(tmp_path)
    (root / "README.md").write_text("# repo\n\nUn servidor MCP de 1 tools.\n", encoding="utf-8")
    resultado = ejecutar(root)
    assert resultado.returncode == 1, resultado.stdout + resultado.stderr
    assert "README.md:3" in resultado.stdout
    assert "DRIFT" in resultado.stdout


def test_repo_actual_informa_coherente():
    """Contra el repo real: la salida y el exit code deben concordar."""
    resultado = ejecutar(REPO)
    assert "comandos=" in resultado.stdout and "tools=" in resultado.stdout
    if resultado.returncode == 0:
        assert "OK" in resultado.stdout
    else:
        assert resultado.returncode == 1
        assert "DRIFT" in resultado.stdout
