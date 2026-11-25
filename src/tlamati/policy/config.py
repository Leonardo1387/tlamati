"""B4 — policy/config.py: herramienta→auto|ask|deny + patrones + trifecta.

Tres capas sobre el permiso DECLARADO por cada Tool (GUIA §B4):

1. OVERRIDE por herramienta: ``permissions.tools.<name>: auto|ask|deny``.
   Solo puede endurecer o relajar a nivel de herramienta; la resolución es
   ``override si existe, else declarado``.
2. PATRONES de comando (solo tools con args["command"], p.ej. terminal):
   ``deny_commands`` (fnmatch) → DENY; ``ask_commands`` → al menos ASK.
   NIVEL 2d/2e: además ``ask_command_regex`` (regex search) → al menos ASK,
   default ON para `pip install --break-system-packages` y para escritura
   (redirección/tee/mv/cp/rm) hacia dirs de artefactos indexados
   (07-index/, dist/); ``ask_path_regex`` cubre write_file/edit cuyo
   ``path`` cae en esos dirs. Ambos configurables vía config.yaml
   (lista vacía explícita = OFF). DENY gana siempre: la escalera nunca
   RELAJA un permiso más duro.
3. TRIFECTA LETAL (research/01): si la corrida YA consumió un tool result
   ``untrusted=True``, toda herramienta de EGRESO (default: terminal — la
   única que puede hablar hacia afuera; red/env-mail) escala AUTO→ASK aunque
   su permiso diga auto. Nunca degrada ASK/DENY.

Estado: ``Policy`` es MUTABLE por corrida (``mark_untrusted()``) — la trifecta
es "alguna vez en esta sesión", no por turno. Se resetea creando un Policy
nuevo por run (el Registry lo recibe inyectado).

Regla de oro: default NUNCA yolo. Sin approver, ASK = error honesto (B1).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from fnmatch import fnmatch
from typing import TYPE_CHECKING, Any

from tlamati.tools.registry import Permission

if TYPE_CHECKING:  # C5: plan.mode no importa policy → sin ciclo real
    from tlamati.plan.mode import PlanState

DEFAULT_EGRESS_TOOLS = frozenset({"terminal"})

# NIVEL 2d/2e (dogfood #6): gates de policy por patrón regex, default ON y
# configurables vía config.yaml (permissions.ask_command_regex /
# permissions.ask_path_regex; lista vacía explícita = OFF). Genéricos: cero
# nombres de proyecto hardcodeados.
#
# 2d — `pip install --break-system-packages` sustituye paquetes del sistema
#      (en el dogfood #6 el agente lo corrió 2 veces y reemplazó el Pillow
#      de WSL) → aprobación humana.
# 2e — sobrescritura de artefactos de producción indexados: operadores de
#      escritura (redirección, tee, mv, cp, rm) cuyo destino cae en un dir
#      07-index/ o dist/ → aprobación humana. Lecturas (ls/cat de dist/)
#      NO matchean: el gate es de sobreescritura, no de acceso.
DEFAULT_ASK_COMMAND_REGEX: tuple[str, ...] = (
    r"pip3?\s+install\b[^|;&\n]*--break-system-packages",
    r"--break-system-packages[^|;&\n]*\bpip3?\s+install\b",
    r"(?:>>?|\btee\b|\bmv\b|\bcp\b|\brm\b)[^|;&\n]*[/'\"\s](?:07-index|dist)/",
)

# 2e para tools de archivo (write_file/edit): path DENTRO de un dir de
# artefactos indexados, sin necesitar operador de escritura (el tool YA
# escribe). read_file/list_dir no pasan por aquí (no tienen efecto).
DEFAULT_ASK_PATH_REGEX: tuple[str, ...] = (r"(?:^|/)(?:07-index|dist)/",)

# Tools cuyo args["path"] se somete a ask_path_regex (solo los que escriben).
_WRITE_PATH_TOOLS = frozenset({"write_file", "edit"})


def _compile_patterns(patterns: tuple[str, ...], *, key: str) -> tuple[re.Pattern[str], ...]:
    out: list[re.Pattern[str]] = []
    for p in patterns:
        try:
            out.append(re.compile(p))
        except re.error as e:
            raise ValueError(f"{key}: patrón regex inválido {p!r}: {e}") from None
    return tuple(out)


@dataclass(frozen=True)
class PolicyConfig:
    """Configuración declarativa (inmutable, viene de config.yaml)."""

    tool_overrides: Mapping[str, Permission] = field(default_factory=dict)
    deny_commands: tuple[str, ...] = ()
    ask_commands: tuple[str, ...] = ()
    egress_tools: frozenset[str] = DEFAULT_EGRESS_TOOLS
    # NIVEL 2d/2e: regex (search, no fnmatch) — default ON.
    ask_command_regex: tuple[re.Pattern[str], ...] = field(
        default_factory=lambda: _compile_patterns(
            DEFAULT_ASK_COMMAND_REGEX, key="permissions.ask_command_regex"
        )
    )
    ask_path_regex: tuple[re.Pattern[str], ...] = field(
        default_factory=lambda: _compile_patterns(
            DEFAULT_ASK_PATH_REGEX, key="permissions.ask_path_regex"
        )
    )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> PolicyConfig:
        """Parsea la sección ``permissions:`` de config.yaml. Clave inválida
        = ValueError (fail fast: una política mal escrita no debe degradar
        en silencio a permisiva)."""
        if not data:
            return cls()
        if not isinstance(data, Mapping):
            raise ValueError("permissions: debe ser un mapa")
        overrides: dict[str, Permission] = {}
        raw_tools = data.get("tools") or {}
        if not isinstance(raw_tools, Mapping):
            raise ValueError("permissions.tools: debe ser un mapa nombre→auto|ask|deny")
        for name, level in raw_tools.items():
            try:
                overrides[str(name)] = Permission(str(level))
            except ValueError:
                raise ValueError(
                    f"permissions.tools.{name}: {level!r} inválido (auto|ask|deny)"
                ) from None
        deny = tuple(str(p) for p in (data.get("deny_commands") or ()))
        ask = tuple(str(p) for p in (data.get("ask_commands") or ()))
        raw_egress = data.get("egress_tools")
        egress = (
            frozenset(str(t) for t in raw_egress)
            if raw_egress is not None
            else DEFAULT_EGRESS_TOOLS
        )
        # NIVEL 2d/2e: regex configurables; clave ausente = default ON,
        # lista vacía explícita = OFF (decisión del dueño, fail-fast si el
        # regex no compila — una política mal escrita no degrada en silencio).
        raw_cmd_re = data.get("ask_command_regex")
        cmd_re = (
            _compile_patterns(
                tuple(str(p) for p in raw_cmd_re), key="permissions.ask_command_regex"
            )
            if raw_cmd_re is not None
            else _compile_patterns(DEFAULT_ASK_COMMAND_REGEX, key="permissions.ask_command_regex")
        )
        raw_path_re = data.get("ask_path_regex")
        path_re = (
            _compile_patterns(tuple(str(p) for p in raw_path_re), key="permissions.ask_path_regex")
            if raw_path_re is not None
            else _compile_patterns(DEFAULT_ASK_PATH_REGEX, key="permissions.ask_path_regex")
        )
        return cls(
            tool_overrides=overrides,
            deny_commands=deny,
            ask_commands=ask,
            egress_tools=egress,
            ask_command_regex=cmd_re,
            ask_path_regex=path_re,
        )


class Policy:
    """Resolución de permisos con estado de corrida (trifecta + plan-mode C5)."""

    def __init__(
        self, config: PolicyConfig | None = None, plan_state: PlanState | None = None
    ) -> None:
        self.config = config or PolicyConfig()
        self.untrusted_seen = False
        self.plan_state = plan_state  # C5: capa transversal explorar→aprobar→ejecutar

    def mark_untrusted(self) -> None:
        """El loop/registry llama esto al consumir un ToolResult untrusted."""
        self.untrusted_seen = True

    def plan_denied(self, tool_name: str) -> bool:
        """True si el DENY efectivo de esta tool lo impone el plan-mode (C5) —
        el registry lo usa para dar el error honesto correspondiente."""
        if self.plan_state is None or not self.plan_state.active:
            return False
        from tlamati.plan.mode import PLAN_READONLY_TOOLS, PLAN_TOOLS

        return tool_name not in PLAN_READONLY_TOOLS and tool_name not in PLAN_TOOLS

    def resolve(self, tool_name: str, args: dict[str, Any], declared: Permission) -> Permission:
        """Permiso efectivo. La escalera NUNCA relaja: cada capa solo puede
        endurecer (deny > ask > auto)."""
        effective = self.config.tool_overrides.get(tool_name, declared)
        # C5 plan-mode: regla transversal — fuera de la whitelist read-only,
        # TODO pasa a DENY (el mecanismo de B4, 0 código nuevo de permisos).
        if self.plan_denied(tool_name):
            return Permission.DENY
        command = args.get("command")
        if isinstance(command, str):
            if any(fnmatch(command, pat) for pat in self.config.deny_commands):
                return Permission.DENY
            if any(fnmatch(command, pat) for pat in self.config.ask_commands):
                effective = _harder(effective, Permission.ASK)
            # NIVEL 2d/2e: gates regex sobre el comando (pip
            # --break-system-packages, escritura en dirs de artefactos).
            if any(rx.search(command) for rx in self.config.ask_command_regex):
                effective = _harder(effective, Permission.ASK)
        # NIVEL 2e (tools de archivo): write_file/edit cuyo path cae en un
        # dir de artefactos indexados → ASK. Solo tools que ESCRIBEN.
        path = args.get("path")
        if (
            tool_name in _WRITE_PATH_TOOLS
            and isinstance(path, str)
            and any(rx.search(path.replace("\\", "/")) for rx in self.config.ask_path_regex)
        ):
            effective = _harder(effective, Permission.ASK)
        # Trifecta: egress AUTO→ASK tras consumir contenido untrusted.
        if self.untrusted_seen and tool_name in self.config.egress_tools:
            effective = _harder(effective, Permission.ASK)
        return effective


_RANK = {Permission.AUTO: 0, Permission.ASK: 1, Permission.DENY: 2}


def _harder(a: Permission, b: Permission) -> Permission:
    return a if _RANK[a] >= _RANK[b] else b
