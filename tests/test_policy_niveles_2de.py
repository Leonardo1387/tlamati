"""NIVEL 2d/2e — gates de policy por patrón regex (dogfood #6).

2d: pip install --break-system-packages → ASK (el dogfood lo corrió 2 veces
    y sustituyó el Pillow del sistema WSL).
2e: sobrescritura de artefactos de producción indexados (07-index/, dist/)
    vía operadores shell o write_file/edit → ASK.

Ambos default ON, configurables (permissions.ask_command_regex /
ask_path_regex; lista vacía = OFF). La escalera nunca relaja: ASK/DENY
declarados siguen ganando.
"""

from __future__ import annotations

from typing import Any

import pytest

from tlamati.policy.config import (
    DEFAULT_ASK_COMMAND_REGEX,
    DEFAULT_ASK_PATH_REGEX,
    Policy,
    PolicyConfig,
)
from tlamati.tools.registry import Permission


def _resolve(
    tool: str, args: dict[str, Any], declared: Permission = Permission.AUTO, **cfg: Any
) -> Permission:
    return Policy(PolicyConfig.from_dict(cfg or None)).resolve(tool, args, declared)


class TestNivel2dPipBreakSystem:
    def test_pip_break_system_packages_ask(self) -> None:
        cmd = "pip install --break-system-packages Pillow==9.5"
        assert _resolve("terminal", {"command": cmd}) is Permission.ASK

    def test_pip3_variante(self) -> None:
        cmd = "pip3 install --break-system-packages -r req.txt"
        assert _resolve("terminal", {"command": cmd}) is Permission.ASK

    def test_flag_antes_del_install(self) -> None:
        cmd = "python -m pip install --break-system-packages numpy"
        # el patrón cubre `pip install ... --break-system-packages`;
        # aquí el flag va DESPUÉS de pip install en el string → matchea igual
        assert _resolve("terminal", {"command": cmd}) is Permission.ASK

    def test_pip_normal_sin_gate(self) -> None:
        cmd = "pip install requests"
        assert _resolve("terminal", {"command": cmd}) is Permission.AUTO

    def test_dentro_de_un_venv_tambien_pide(self) -> None:
        """Conservador: el gate no adivina contexto; pide aprobación y el
        humano decide (advisory de dureza mínima, nunca bloqueo mudo)."""
        cmd = "source .venv/bin/activate && pip install --break-system-packages x"
        assert _resolve("terminal", {"command": cmd}) is Permission.ASK

    def test_ask_declarado_no_se_relaja(self) -> None:
        cmd = "pip install --break-system-packages Pillow"
        assert _resolve("terminal", {"command": cmd}, declared=Permission.ASK) is Permission.ASK

    def test_deny_commands_gana_sobre_regex(self) -> None:
        cmd = "pip install --break-system-packages Pillow"
        got = _resolve(
            "terminal",
            {"command": cmd},
            deny_commands=["pip*"],
        )
        assert got is Permission.DENY


class TestNivel2eArtefactosShell:
    @pytest.mark.parametrize(
        "cmd",
        [
            "python pipeline.py --fase 7 > 07-index/consumidor.json",
            "cat nuevo.json > data/07-index/viejo.json",
            "echo x >> dist/bundle.js",
            "cp local/index.json 07-index/index.json",
            "mv nuevo.json dist/app.js",
            "tee dist/salida.txt < entrada",
            "rm -rf 07-index/old",
        ],
    )
    def test_escritura_en_artefactos_ask(self, cmd: str) -> None:
        assert _resolve("terminal", {"command": cmd}) is Permission.ASK, cmd

    @pytest.mark.parametrize(
        "cmd",
        [
            "cat dist/app.js",  # lectura
            "ls 07-index/",  # listado
            "python -c \"import json; json.load(open('dist/manifest.json'))\"",
            "echo dist/ > notas.txt",  # destino NO es dir de artefactos
            "grep -r falla 07-index/ | head",
        ],
    )
    def test_lectura_en_artefactos_sin_gate(self, cmd: str) -> None:
        assert _resolve("terminal", {"command": cmd}) is Permission.AUTO, cmd


class TestNivel2eArtefactosFileTools:
    def test_write_file_en_dist_ask(self) -> None:
        assert (
            _resolve("write_file", {"path": "dist/app.js", "content": "x"})
            is Permission.ASK
        )

    def test_edit_en_07_index_ask(self) -> None:
        assert (
            _resolve("edit", {"path": "data/07-index/idx.json", "old_string": "a"})
            is Permission.ASK
        )

    def test_write_file_path_normal_auto(self) -> None:
        assert (
            _resolve("write_file", {"path": "src/main.py", "content": "x"})
            is Permission.AUTO
        )

    def test_read_file_no_gatea_aunque_lea_dist(self) -> None:
        """read_file NO escribe → fuera de _WRITE_PATH_TOOLS."""
        assert _resolve("read_file", {"path": "dist/app.js"}) is Permission.AUTO

    def test_directorio_distinto_no_falso_positivo(self) -> None:
        """distribution/ o dist_old/ NO deben matchear el dir dist/."""
        assert (
            _resolve("write_file", {"path": "distribution/x.txt", "content": ""})
            is Permission.AUTO
        )
        assert (
            _resolve("write_file", {"path": "dist_old/x.txt", "content": ""})
            is Permission.AUTO
        )


class TestConfiguracion:
    def test_defaults_on(self) -> None:
        cfg = PolicyConfig.from_dict(None)
        assert len(cfg.ask_command_regex) == len(DEFAULT_ASK_COMMAND_REGEX)
        assert len(cfg.ask_path_regex) == len(DEFAULT_ASK_PATH_REGEX)

    def test_lista_vacia_explicita_off(self) -> None:
        cfg = PolicyConfig.from_dict({"ask_command_regex": [], "ask_path_regex": []})
        assert cfg.ask_command_regex == () and cfg.ask_path_regex == ()
        p = Policy(cfg)
        cmd = "pip install --break-system-packages x"
        assert p.resolve("terminal", {"command": cmd}, Permission.AUTO) is Permission.AUTO

    def test_patron_custom_suma(self) -> None:
        cfg = PolicyConfig.from_dict({"ask_command_regex": [r"\bgit push\b"]})
        p = Policy(cfg)
        got = p.resolve("terminal", {"command": "git push origin main"}, Permission.AUTO)
        assert got is Permission.ASK
        # default OFF al configurar explícitamente: pip ya no gatea
        cmd = "pip install --break-system-packages x"
        assert p.resolve("terminal", {"command": cmd}, Permission.AUTO) is Permission.AUTO

    def test_regex_invalido_fail_fast(self) -> None:
        with pytest.raises(ValueError, match="inválido"):
            PolicyConfig.from_dict({"ask_command_regex": ["([unclosed"]})

    def test_patrones_default_compilan(self) -> None:
        import re

        for p in [*DEFAULT_ASK_COMMAND_REGEX, *DEFAULT_ASK_PATH_REGEX]:
            re.compile(p)
