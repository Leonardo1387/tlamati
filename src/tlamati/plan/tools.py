"""C5 — plan/tools.py: enter_plan_mode / save_plan / exit_plan_mode.

Decisiones del handoff resueltas:
- #1 (fundador, 16-nov): opción A — `save_plan` es la vía especial que escribe
  el plan como archivo markdown real SOLO dentro de .tlamati/plans/ (con
  path-escape guard, donor skill_view C3). write_file sigue en DENY en plan-mode.
- #2: ask_user/complete_task se DIFIEREN a Fase E (TUI). En su lugar,
  exit_plan_mode en headless sin aprobador interactivo falla CERRADO con un
  error honesto (regla de oro 1 de qwen: --approve-tool NO cuenta aquí).
- #3: bloque de prompt estático (ver plan/mode.py PLAN_MODE_PROMPT); el estado
  dinámico NO viaja en el prefijo.

Las 3 tools van AL FINAL del orden estable de tools.specs() (append-only:
prefijo cacheable intacto).
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from tlamati.plan.mode import PlanState
from tlamati.tools.registry import Permission, Tool

# Un nombre de plan: slug seguro (nada de rutas ni escapes).
_NAME_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")

MAX_PLAN_CHARS = 100_000

# Aprobador de planes: recibe la ruta del plan y su contenido, devuelve
#   True          → aprobado
#   False         → rechazado sin feedback
#   str           → rechazado CON feedback (el modelo refina, regla gemini 6)
PlanApprover = Callable[[str, str], Awaitable[bool | str]]


def plans_dir(cwd: Path) -> Path:
    """Dir controlado de planes del proyecto (donor gemini planning.md)."""
    return cwd / ".tlamati" / "plans"


def make_plan_tools(
    cwd: Path,
    state: PlanState,
    plan_approver: PlanApprover | None = None,
) -> list[Tool]:
    """Las 3 tools de planificación. ``plan_approver`` es el ÚNICO canal que
    puede aprobar una salida (regla de oro 1: ni --approve-tool ni allow-lists
    cuentan; sin aprobador → fail closed con error honesto)."""

    pdir = plans_dir(cwd)

    def _resolve_plan_path(raw: str) -> Path | None:
        """Path-escape guard (donor skill_view C3): el plan debe vivir DENTRO
        de .tlamati/plans/. Acepta ruta absoluta, relativa al cwd, o solo el
        nombre del archivo."""
        candidate = Path(raw)
        if not candidate.is_absolute():
            candidate = cwd / candidate
        target = candidate.resolve()
        base = pdir.resolve()
        try:
            target.relative_to(base)
        except ValueError:
            return None
        return target

    async def enter_run(args: dict[str, Any]) -> str:
        reason = str(args.get("reason", "")).strip()
        err = state.enter()
        if err is not None:
            return err
        msg = (
            "Plan-mode ACTIVO. Tools de escritura/terminal DENEGADAS; solo "
            "exploración (read_file, search_files, skill_view, skill_list, "
            "search_memory) y save_plan. Escribe el plan con save_plan y pide "
            "aprobación con exit_plan_mode."
        )
        if reason:
            msg = f"Entraste a plan-mode: {reason}\n{msg}"
        return msg

    async def save_plan_run(args: dict[str, Any]) -> str:
        name = str(args.get("name", "")).strip()
        content = str(args.get("content", ""))
        if not _NAME_RE.match(name):
            return (
                f"ERROR: name {name!r} inválido — usa solo letras, dígitos, "
                "'-' o '_' (máx. 64 chars)"
            )
        if not content.strip():
            return "ERROR: el plan no puede estar vacío"
        if len(content) > MAX_PLAN_CHARS:
            return f"ERROR: plan demasiado grande ({len(content)} > {MAX_PLAN_CHARS} chars)"
        try:
            pdir.mkdir(parents=True, exist_ok=True)
            target = pdir / f"{name}.md"
            target.write_text(content, encoding="utf-8")
        except OSError as e:
            # Degradación honesta (invariante del proyecto): nunca rompe la corrida.
            return f"ERROR: no se pudo guardar el plan ({type(e).__name__}: {e})"
        return (
            f"Plan guardado en {target} ({len(content)} chars). Pide aprobación con exit_plan_mode."
        )

    async def exit_run(args: dict[str, Any]) -> str:
        raw_path = str(args.get("plan_path", "")).strip()
        if not raw_path:
            return "ERROR: plan_path es obligatorio (ruta del plan guardado con save_plan)"

        # Estado rancio → fail closed ANTES de tocar nada (regla 2).
        if not state.active:
            return "ERROR: no estás en plan-mode; nada que aprobar"

        target = _resolve_plan_path(raw_path)
        if target is None:
            return (
                f"ERROR: plan_path {raw_path!r} está fuera de .tlamati/plans/ — "
                "el plan debe guardarse con save_plan dentro del dir controlado"
            )
        if not target.is_file():
            return f"ERROR: el plan {target} no existe — guárdalo primero con save_plan"

        # Señal de salida: una sola petición en vuelo por revisión (regla 2:
        # doble salida contra la misma revisión → fail closed).
        revision = state.request_exit()
        if revision is None:
            return (
                "ERROR: ya hay una petición de salida en vuelo para esta revisión "
                "del plan-mode (fail closed). El plan-mode SIGUE ACTIVO."
            )

        # Regla de oro 1 (qwen): SOLO interacción humana real aprueba la salida.
        # Sin host interactivo → fail closed, el plan sigue activo.
        if plan_approver is None:
            state.cancel_exit()
            return (
                "ERROR: no hay un usuario interactivo disponible para aprobar el "
                "plan (headless sin aprobador). Fail closed: plan-mode SIGUE "
                "ACTIVO. --approve-tool NO puede aprobar la salida de plan-mode."
            )

        try:
            plan_text = target.read_text(encoding="utf-8", errors="replace")
            verdict = await plan_approver(str(target), plan_text)
        except Exception as e:  # un bug del aprobador nunca relaja el modo
            state.cancel_exit()
            return (
                f"ERROR: la aprobación falló ({type(e).__name__}: {e}). Fail closed: "
                "plan-mode SIGUE ACTIVO."
            )

        if verdict is not True:
            # Rechazo → feedback al modelo, sigue en plan-mode (gemini regla 6).
            state.cancel_exit()
            feedback = str(verdict).strip() if isinstance(verdict, str) else ""
            if feedback:
                return (
                    f"Plan RECHAZADO por el usuario. Feedback: {feedback} — "
                    "sigues en plan-mode: refina el plan con save_plan y vuelve "
                    "a pedir aprobación."
                )
            return (
                "Plan RECHAZADO por el usuario (sin feedback). Sigues en "
                "plan-mode: refina el plan y vuelve a pedir aprobación."
            )

        # Regla 3: la conmutación valida TODO (modo actual + revisión coincide)
        # antes de cambiar nada; si el estado cambió debajo → fail closed.
        restored = state.commit_exit(revision)
        if restored is None:
            return (
                "ERROR: el estado de plan-mode cambió durante la aprobación "
                "(revisión rancia). Fail closed: plan-mode SIGUE ACTIVO; vuelve "
                "a pedir exit_plan_mode."
            )
        return (
            f"Plan APROBADO. Plan-mode desactivado (modo restaurado: {restored}). "
            "Ya puedes ejecutar: write_file, edit y terminal están habilitadas."
        )

    return [
        Tool(
            name="enter_plan_mode",
            description=(
                "Entrar en modo de planificación: solo exploración y trabajo "
                "con el plan; toda escritura/terminal queda denegada hasta que "
                "el usuario apruebe un plan con exit_plan_mode."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "opcional: por qué entras a plan-mode",
                    },
                },
            },
            run=enter_run,
            permission=Permission.AUTO,
        ),
        Tool(
            name="save_plan",
            description=(
                "Guardar/refinar el plan como archivo markdown dentro de "
                ".tlamati/plans/ (ÚNICA escritura permitida en plan-mode). "
                "name = slug (letras/dígitos/-/_); content = markdown del plan."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["name", "content"],
            },
            run=save_plan_run,
            permission=Permission.AUTO,
        ),
        Tool(
            name="exit_plan_mode",
            description=(
                "Pedir al USUARIO la aprobación del plan guardado (plan_path "
                "dentro de .tlamati/plans/). Solo una aprobación humana real "
                "sale de plan-mode; rechazo = feedback para refinar. Sin "
                "usuario interactivo falla cerrado."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "plan_path": {
                        "type": "string",
                        "description": "ruta del plan guardado con save_plan",
                    },
                },
                "required": ["plan_path"],
            },
            run=exit_run,
            permission=Permission.AUTO,
        ),
    ]
