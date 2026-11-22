"""O1: compatibilidad agentskills.io verificada contra skills REALES.

Fixture: fixtures/agentskills_compat/ — los 7 skills del plugin oficial de
Obsidian (github.com/obsidianmd/obsidian-skills, MIT, © Steph Ango). Copia
vendada a propósito: si el repo upstream desaparece o cambia formato, este
test sigue midiendo contra el spec que certificamos (ver NOTICE.md).

Contrato probado: tlamati lee cualquier skill compatible con agentskills.io
sin crashear y sin perder campos — los campos extra del spec que tlamati no
consume hoy se ignoran honestamente.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from tlamati.memory.skills import parse_skill

FIXTURE = Path(__file__).parent.parent / "fixtures" / "agentskills_compat"

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)


def _skills_dirs() -> list[Path]:
    return sorted(d for d in FIXTURE.iterdir() if (d / "SKILL.md").is_file())


def test_fixture_presente_con_al_menos_tres_skills():
    """Si alguien borra/mueve el fixture, el test lo dice en cristiano."""
    assert len(_skills_dirs()) >= 3, (
        f"fixture incompleto: {FIXTURE} tiene {len(_skills_dirs())} skills "
        "(esperados ≥3 del vendado de obsidian-skills)"
    )


@pytest.mark.parametrize("skill_dir", _skills_dirs(), ids=lambda d: d.name)
def test_todo_skill_real_parsea(skill_dir: Path):
    s = parse_skill(skill_dir / "SKILL.md")
    assert s is not None, f"{skill_dir.name} no parseó (spec agentskills.io roto)"
    assert s.name and s.description
    # el nombre declarado en frontmatter coincide con el directorio (spec)
    assert s.name == skill_dir.name


@pytest.mark.parametrize("skill_dir", _skills_dirs(), ids=lambda d: d.name)
def test_campos_extra_del_spec_se_ignoran_sin_crashear(skill_dir: Path):
    """El spec agentskills.io admite campos que tlamati no consume (license,
    metadata, allowed-tools...). parse_skill debe quedárselos fuera sin
    reventar — el frontmatter sigue siendo YAML válido leíble."""
    text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    m = _FRONTMATTER_RE.match(text)
    assert m is not None, f"{skill_dir.name}: sin frontmatter"
    fm = yaml.safe_load(m.group(1))
    assert isinstance(fm, dict)
    assert "name" in fm and "description" in fm
    # parse_skill no crashea y preserva solo su contrato mínimo
    s = parse_skill(skill_dir / "SKILL.md")
    assert s is not None
    assert s.name == str(fm["name"]).strip()
    assert s.description == str(fm["description"]).strip()


def test_linked_files_no_confunde_licencia_con_asset():
    """El fixture trae LICENSE-OBSIDIAN-SKILLS en la raíz (no dentro de un
    skill); linked_files() de un skill no debe inventarse archivos de más."""
    s = parse_skill(FIXTURE / "defuddle" / "SKILL.md")
    assert s is not None
    for files in s.linked_files().values():
        for f in files:
            assert "LICENSE" not in f
