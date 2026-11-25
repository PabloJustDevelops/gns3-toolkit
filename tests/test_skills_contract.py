"""Contrato de las skills curadas que viven en el repo.

Sólo stdlib y pytest: el frontmatter se parsea con el subconjunto YAML que usan
las skills (mapas anidados y listas en línea), sin depender de PyYAML.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = ROOT / "skills"
SKILLS_DIR = SKILLS_ROOT / "devops"
EXPECTED = {
    "gns3-toolkit-operator",
    "gns3-pfsense-native",
    "gns3-mcp-cli-contract",
}
AUTHOR = "Pablo Rodríguez Garijo (PabloJustDevelops), Hermes Agent"
SECTIONS = ("## When to Use", "## Pitfalls", "## Verification")
PLATFORMS = {"linux", "macos", "windows"}
LOCAL_PATH_RE = re.compile(r"/home/|/Users/|/root/|~/|C:\\\\Users\\\\")


def _frontmatter(text: str) -> tuple[dict, str]:
    """Devuelve el mapa del frontmatter y el cuerpo; falla si el bloque no cierra."""
    lines = text.splitlines()
    assert lines and lines[0] == "---", "el frontmatter debe empezar en el byte 0"
    try:
        end = lines.index("---", 1)
    except ValueError:
        pytest.fail("frontmatter sin cierre `---`")
    data: dict = {}
    stack = [(0, data)]
    for raw in lines[1:end]:
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        key, sep, value = raw.strip().partition(":")
        assert sep and key, f"línea de frontmatter inválida: {raw!r}"
        while stack and indent < stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        value = value.strip()
        if value:
            parent[key] = _scalar(value)
        else:
            child: dict = {}
            parent[key] = child
            stack.append((indent + 1, child))
    return data, "\n".join(lines[end + 1:])


def _scalar(value: str):
    if value.startswith("[") and value.endswith("]"):
        return [item.strip().strip("\"'") for item in value[1:-1].split(",") if item.strip()]
    return value.strip("\"'")


def _all_skills() -> dict[str, Path]:
    return {p.parent.name: p for p in sorted(SKILLS_ROOT.glob("*/**/SKILL.md"))}


def test_exactly_the_three_curated_skills() -> None:
    found = {p.parent.name for p in SKILLS_DIR.glob("*/SKILL.md")}
    assert found == EXPECTED


@pytest.mark.parametrize("skill", sorted(EXPECTED))
def test_skill_contract(skill: str) -> None:
    path = SKILLS_DIR / skill / "SKILL.md"
    assert path.is_file(), f"falta {path.relative_to(ROOT)}"
    text = path.read_text(encoding="utf-8")
    data, body = _frontmatter(text)

    assert data.get("name") == skill
    description = data.get("description")
    assert isinstance(description, str)
    assert len(description) <= 60, f"description de {len(description)} caracteres"
    assert description.endswith("."), "description sin punto final"
    assert data.get("version") == "0.1.0"
    assert data.get("author") == AUTHOR
    assert data.get("license") == "MIT"

    platforms = data.get("platforms")
    assert isinstance(platforms, list) and platforms
    assert set(platforms) <= PLATFORMS

    hermes = (data.get("metadata") or {}).get("hermes") or {}
    assert isinstance(hermes.get("tags"), list) and hermes["tags"]
    related = hermes.get("related_skills")
    assert isinstance(related, list) and related, "related_skills vacío"

    available = _all_skills()
    for other in related:
        assert other != skill, "related_skills no debe apuntar a la propia skill"
        assert other in available, f"related_skills apunta a {other!r}, que no existe"

    for section in SECTIONS:
        assert section in body, f"falta la sección {section!r}"
    assert re.search(r"^\d+\.\s", body, re.M), "faltan pasos numerados verificables"

    assert len(text.splitlines()) <= 150
    assert not LOCAL_PATH_RE.search(text), "ruta local en una skill versionada"
    assert len(list((path.parent / "references").glob("*.md"))) <= 1
