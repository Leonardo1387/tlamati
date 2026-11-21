"""F1 — core/model_router.py: cambio de modelo en vivo dentro de la sesión.

Un ModelRouter implementa el Provider Protocol del loop (`.model` property +
`stream()`), así que loop.py y las tools NO se enteran de que el modelo puede
cambiar entre turnos. Es el ÚNICO lugar donde vive el estado "modelo activo";
la TUI y el comando /model lo mutan.

Reglas de la casa (HANDOFF_F1 §3, §5):
- CACHE SAGRADA: el modelo activo viaja en el primer mensaje dinámico / estado
  por turno, NUNCA en el system prompt (el prefijo debe quedar byte-estable
  entre swaps). Aquí el router no toca mensajes: solo delega.
- El swap solo aplica en frontera de turno; `set_model` es O(n) y seguro porque
  el loop nunca muta el provider a mitad de stream (invariante verificada por
  test de loop: provider se lee por turno).
- Cada swap se AUDITA (ledger) si el caller pasa `on_swap`: el cambio de modelo
  es una decisión del usuario y las decisiones se registran.
- Fail-loud con fallback explícito: `list_models()` delega al provider de
  referencia; si el endpoint falla, Propaga ProviderError — el caller (TUI)
  decide la lista de config. El router NUNCA inventa modelos.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator, Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from tlamati.core.messages import Event, Message
from tlamati.providers.base import ProviderError, ToolSpec

# firma: (turno_or_ts, model_out, model_in) -> None
SwapHook = Callable[[float, str, str], None]


@dataclass
class ModelRouter:
    """Provider façade con registry {model_id → provider} y modelo activo.

    Cada provider registrado satisface el Protocol (expone `.model` y
    `stream()`). El router reporta `.model` = modelo activo y delega
    `stream()` al provider correspondiente.
    """

    providers: dict[str, Any]  # model_id → Provider (evita import circular de Protocol)
    active: str
    on_swap: SwapHook | None = None
    last_used_ts: dict[str, float] = field(default_factory=dict)
    _reference: Any = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self.active not in self.providers:
            raise ProviderError(
                f"modelo activo {self.active!r} no registrado "
                f"(disponibles: {sorted(self.providers)})",
                kind="config",
            )
        self._reference = self.providers[self.active]

    # ---- Provider Protocol -------------------------------------------------
    @property
    def model(self) -> str:
        return self.active

    async def stream(
        self, messages: Sequence[Message], tools: Sequence[ToolSpec] = ()
    ) -> AsyncIterator[Event]:
        # El modelo se captura AQUÍ (al iniciar el turno), no al iterar:
        # el async generator ni siquiera ejecuta su cuerpo hasta el primer
        # anext(), así que postergar la lectura de self.active permitiría
        # que un swap entre turnos contamine el stream en vuelo. Frontera
        # de turno = único punto de swap (HANDOFF_F1 §5).
        provider = self.providers[self.active]
        self.last_used_ts[self.active] = time.time()
        async for ev in provider.stream(messages, tools):
            yield ev

    # ---- API del router (TUI / comando /model) ------------------------------
    def set_model(self, model_id: str) -> str:
        """Cambia el modelo activo. Devuelve el modelo saliente (para el
        aviso honesto de cache). Si no existe → ProviderError(kind=config);
        el router NO agrega providers en silencio."""
        if model_id not in self.providers:
            raise ProviderError(
                f"modelo {model_id!r} no disponible en esta sesión "
                f"(disponibles: {sorted(self.providers)})",
                kind="config",
            )
        out = self.active
        if out == model_id:
            return out
        self.active = model_id
        if self.on_swap is not None:
            self.on_swap(time.time(), out, model_id)
        return out

    def add_provider(self, provider: Any) -> None:
        """Registra un provider extra (la TUI lo llama cuando la lista
        remota llega y el usuario elige un modelo nuevo no pre-cargado)."""
        mid = str(getattr(provider, "model", "")) or ""
        if not mid:
            raise ProviderError("provider sin .model: no enrutable", kind="config")
        self.providers[mid] = provider

    def cache_hint(self, model_id: str, *, ttl_s: float = 300.0) -> str:
        """Estado del cache del destino según tiempo de inactividad local:
        'hot' = último hit < TTL (el swap de regreso es casi gratis),
        'cold' = > TTL (probable re-escritura) o nunca usado.
        Es una ESTIMACIÓN LOCAL honesta, no el estado real del server."""
        ts = self.last_used_ts.get(model_id)
        if ts is None:
            return "cold"
        return "hot" if (time.time() - ts) <= ttl_s else "cold"

    async def list_models(self) -> list[str]:
        """Lista contra el provider de referencia (el primer modelo con el
        que arrancó la sesión). Fail-loud: si el endpoint falla o el
        provider no soporta list_models, ProviderError — el caller cae a
        config, nunca a lista inventada."""
        ref = self._reference
        fn = getattr(ref, "list_models", None)
        if fn is None:
            raise ProviderError("el provider de referencia no soporta list_models", kind="config")
        result = await fn()
        return list(result)
