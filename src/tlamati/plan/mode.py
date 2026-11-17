"""C5 — plan/mode.py: estado de plan-mode + whitelist read-only + prompt estático.

Donors (HANDOFF_FASE_C5 §5):
- qwen-code explicit-plan-exit-approval.md → las 4 reglas de oro FAIL-CLOSED:
  1. exit_plan_mode requiere interacción REAL del usuario (auto-aprobaciones,
     YOLO y allow-lists NO cuentan; sin host interactivo → fail closed).
  2. Todo estado rancio falla CERRADO: salida sin aprobación, aprobación vieja
     (revisión cambió), doble salida contra la misma revisión → plan SIGUE ACTIVO.
  3. La aprobación valida TODO antes de conmutar (modo actual, señal activa,
     revisión coincide) — el modo no cambia hasta que la ejecución valida.
  4. enter guarda el modo previo para restaurarlo al salir.
- gemini-cli planning.md → exit con plan_path obligatorio (archivo real dentro
  de un dir de planes); rechazo = feedback al modelo, sigue en plan-mode.

CACHE SAGRADA: el bloque de prompt es ESTÁTICO (siempre los mismos bytes si las
plan-tools están registradas); el estado dinámico viaja en el primer mensaje,
nunca en el prefijo (decisión abierta #3 del handoff, donor CC attribution-header).
"""

from __future__ import annotations

# Tools que siguen permitidas EN plan-mode (whitelist v1, handoff §5).
PLAN_READONLY_TOOLS = frozenset(
    {"read_file", "search_files", "skill_view", "skill_list", "search_memory"}
)

# Las tools del propio plan-mode nunca se bloquean a sí mismas.
PLAN_TOOLS = frozenset({"enter_plan_mode", "exit_plan_mode", "save_plan"})

PLAN_MODE_PROMPT = """

# PLAN-MODE (explorar → aprobar → ejecutar)
Dispones de tres tools de planificación:
- enter_plan_mode(reason): entras en modo de planificación. Mientras esté
  activo, TODA tool que modifique algo (write_file, edit, terminal, memory)
  queda DENEGADA; solo puedes explorar (read_file, search_files, skill_view,
  skill_list, search_memory) y trabajar con el plan.
- save_plan(name, content): escribe/refina el plan como archivo markdown real
  dentro de .tlamati/plans/ del proyecto. Es la ÚNICA escritura permitida en
  plan-mode. Úsala antes de pedir la salida.
- exit_plan_mode(plan_path): pide al USUARIO aprobar el plan guardado. Solo una
  aprobación humana real te saca de plan-mode; si el usuario rechaza, recibirás
  su feedback y seguirás en plan-mode para refinar el plan (nunca ejecutes tras
  un rechazo). Si no hay usuario interactivo disponible, la salida falla
  CERRADO y el plan-mode sigue activo.
Trabajo recomendado en tareas no triviales: entrar en plan-mode, explorar,
guardar el plan, pedir aprobación, ejecutar."""


class PlanState:
    """Estado de corrida (no global): ``plan_mode`` activo/inactivo + revisión.

    La REVISIÓN se incrementa en cada conmutación real de modo; una aprobación
    queda ligada a la revisión que vio — si el estado cambió debajo de ella,
    la validación final falla CERRADO (regla de oro 2/3 de qwen).

    ``pending_revision`` modela la "señal activa": solo puede haber UNA
    petición de salida en vuelo por revisión; una doble petición contra la
    misma revisión falla cerrado (regla 2).
    """

    def __init__(self, active: bool = False) -> None:
        self.active = active
        self.revision = 0
        self.pre_plan_mode = "normal"  # regla 4: enter guarda el modo previo
        self.pending_revision: int | None = None

    def enter(self, pre_plan_mode: str = "normal") -> str | None:
        """→ None si entró; string de error honesto si ya estaba activo."""
        if self.active:
            return "ERROR: ya estás en plan-mode (revisión activa)"
        self.pre_plan_mode = pre_plan_mode
        self.active = True
        self.revision += 1
        return None

    def request_exit(self) -> int | None:
        """Reserva la señal de salida. → revisión a validar, o None si el
        estado es rancio (no activo) o ya hay una petición en vuelo contra la
        misma revisión (doble salida → fail closed, regla 2)."""
        if not self.active:
            return None
        if self.pending_revision == self.revision:
            return None
        self.pending_revision = self.revision
        return self.revision

    def commit_exit(self, revision: int) -> str | None:
        """Conmuta el modo SOLO si la revisión aprobada coincide con la actual
        (regla 3: la ejecución valida todo antes de cambiar nada).
        → modo previo restaurado, o None si falló cerrado."""
        if not self.active or revision != self.revision:
            return None
        restored = self.pre_plan_mode
        self.active = False
        self.pending_revision = None
        self.revision += 1
        return restored

    def cancel_exit(self) -> None:
        """Libera la señal tras rechazo/fallo — el modelo puede refinar y
        volver a pedir salida (flujo de rechazo de gemini, regla 6)."""
        self.pending_revision = None
