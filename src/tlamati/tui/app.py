"""E1: TUI Textual — la cara del agente.

Requisitos (GUIA §E1):
- Input multilínea (TextArea; ctrl+enter envía).
- Stream con markdown (un widget Markdown por turno, actualizado con deltas).
- Diff viewer con approve/reject (ModalScreen; donor opencode permission.ts:
  allow once / allow always / reject).
- Barra de costo/tokens por turno (context_breakdown del evento budget +
  usage de turn_end, visible SIEMPRE en el footer de contexto).
- Panel de sesiones (ctrl+s; SessionStore.list_sessions).

Invariantes del proyecto respetadas:
- La corrida usa run_loop TAL CUAL (el loop no sabe que existe la TUI; la TUI
  solo consume on_event + inyecta el approver interactivo — narrow waist).
- Default NUNCA yolo: toda tool ASK pasa por el modal de aprobación; el
  "allow always" es por tool y por corrida de la app (memoria del usuario,
  nunca relaja la policy — la escalera sigue endureciendo sola).
- Fail-soft textual: si `textual` no está instalado, el CLI da un error
  honesto con la instrucción de instalación (extra opcional `tlamati[tui]`,
  decisión #4 del fundador — el headless no paga la pantalla).

Scope v1 honesto: composición = config/provider/tools/policy/ledger/session/
instrucciones/memoria/skills. Routing/plugins/MCP/subagentes quedan cableados
solo en headless (E1b); la TUI nunca los invoca a medias.
"""

from __future__ import annotations

import difflib
import json
import os
import sqlite3
import sys
import time
import uuid
from pathlib import Path
from typing import Any, ClassVar

from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Footer,
    Header,
    Label,
    ListItem,
    ListView,
    Markdown,
    Static,
    TextArea,
)

from tlamati import __version__
from tlamati.cli import (
    DEFAULT_AUDIT_DB,
    DEFAULT_BASE_URL,
    DEFAULT_COMPACT_MODEL,
    DEFAULT_MAX_CONTEXT,
    DEFAULT_MODEL,
    DEFAULT_SESSION_DB,
    DEFAULT_SYSTEM,
    _resolve_api_key,
    load_config,
)
from tlamati.context.budget import Budget
from tlamati.context.compaction import CompactionConfig, Compactor, ModelSummarizer
from tlamati.context.instructions import load_instructions, render_for_prompt
from tlamati.core.loop import LoopResult, run_loop
from tlamati.core.messages import Message
from tlamati.core.model_router import ModelRouter
from tlamati.memory.skills import SkillLibrary, default_skill_roots, make_skill_tools
from tlamati.memory.store import MemoryStore, default_memory_dir, seed_if_empty
from tlamati.memory.tools import make_memory_tools
from tlamati.plan.mode import PlanState
from tlamati.policy.config import Policy, PolicyConfig
from tlamati.policy.ledger import Ledger
from tlamati.providers.anthropic_messages import AnthropicMessages
from tlamati.providers.base import ProviderError
from tlamati.providers.openai_compat import OpenAICompat
from tlamati.session.store import SessionStore
from tlamati.tools.builtin import make_tools
from tlamati.tools.registry import Registry

CSS = """
#transcript { height: 1fr; border: none; }
#ctxbar { dock: bottom; height: 1; background: $surface; color: $text-muted; }
#prompt { height: auto; max-height: 8; border: tall $accent; }
#prompt:focus { border: tall $accent-darken-2; }
.user-line { color: $accent; margin-top: 1; }
.tool-line { color: $text-muted; margin-left: 2; }
.tool-error { color: $error; margin-left: 2; }
.note-line { color: $warning; margin-left: 2; }
#sessions { width: 46; border-left: solid $panel; display: none; }
#sessions.visible { display: block; }
ApproveScreen { align: center middle; }
ApproveScreen > Vertical { width: 96; height: auto; max-height: 80%;
    border: thick $warning; background: $surface; padding: 1 2; }
#diff { height: auto; max-height: 26; overflow-y: auto; color: $text; }
#ask-buttons { height: 3; align: center middle; }
"""


def build_diff_preview(name: str, args: dict[str, Any]) -> str:
    """Cuerpo del modal: diff real para write_file/edit, args crudos si no.

    El diff se calcula contra el disco (fuente de verdad) con difflib —
    preview honesto: si el archivo no existe, el diff muestra todo como
    añadido; si el edit fuzzy no pega exacto, la vista previa es la
    sustitución literal (la ejecución real sigue siendo la del tool)."""
    path_raw = str(args.get("path") or "")
    if name == "write_file" and path_raw:
        p = Path(path_raw)
        old = p.read_text(errors="replace").splitlines() if p.is_file() else []
        new = str(args.get("content") or "").splitlines()
        return _unified(old, new, path_raw)
    if name == "edit" and path_raw:
        p = Path(path_raw)
        if p.is_file():
            old_text = p.read_text(errors="replace")
            old = old_text.splitlines()
            new = old_text.replace(
                str(args.get("old_string") or ""), str(args.get("new_string") or ""), 1
            ).splitlines()
            return _unified(old, new, path_raw)
    safe = {k: (str(v)[:400]) for k, v in args.items()}
    return json.dumps(safe, ensure_ascii=False, indent=2)[:4000]


def _unified(old: list[str], new: list[str], label: str) -> str:
    lines = list(
        difflib.unified_diff(old, new, fromfile=f"a/{label}", tofile=f"b/{label}", lineterm="")
    )
    return "\n".join(lines[:600]) if lines else "(sin cambios visibles)"


class ApproveScreen(ModalScreen[str]):
    """Modal de aprobación ASK (donor opencode permission.ts: once/always/reject).

    Devuelve "once" | "always" | "reject". Escape/ventana cerrada = reject
    (fail closed, nunca relaja)."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("a", "once", "Permitir una vez", priority=True),
        Binding("A", "always", "Permitir siempre (esta corrida)", priority=True),
        Binding("r", "reject", "Rechazar", priority=True),
        Binding("escape", "reject", "Rechazar", priority=True),
    ]

    def __init__(self, tool_name: str, body: str) -> None:
        super().__init__()
        self.tool_name = tool_name
        self.body = body

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Static(
                f"El agente pide usar: [b]{self.tool_name}[/b]  (permiso ASK)",
                markup=True,
            )
            yield Static("")
            yield Static(self.body[:4000], id="diff")
            yield Static("")
            with Horizontal(id="ask-buttons"):
                yield Button("Permitir una vez (a)", id="b-once", variant="success")
                yield Button("Siempre (A)", id="b-always", variant="primary")
                yield Button("Rechazar (r)", id="b-reject", variant="error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        mapping = {"b-once": "once", "b-always": "always", "b-reject": "reject"}
        self.dismiss(mapping.get(str(event.button.id), "reject"))

    def action_once(self) -> None:
        self.dismiss("once")

    def action_always(self) -> None:
        self.dismiss("always")

    def action_reject(self) -> None:
        self.dismiss("reject")


class ModelPalette(ModalScreen[int]):
    """F1: selector de modelo (lista OptionsView). Dismiss con el indice
    elegido; Escape = None (no cambia nada, fail closed como ApproveScreen).
    El caller ya sabe construir (id, etiqueta) — aquí solo se pinta y se
    elige."""

    def __init__(self, options: list[tuple[str, str]], current: str) -> None:
        super().__init__()
        self.options = options
        self.current = current

    def compose(self) -> ComposeResult:
        rows: list[ListItem] = []
        for mid, bits in self.options:
            mark = "▶ " if mid == self.current else "  "
            rows.append(ListItem(Label(f"{mark}{mid}   [dim]{bits}[/dim]")))
        with Vertical(id="model-palette"):
            yield Static(
                f"Modelo activo: [b]{self.current}[/b] — ↑/↓ elegir · Enter cambiar · Esc cancelar",
                markup=True,
            )
            yield ListView(*rows, id="model-list")

    async def on_list_view_selected(self, event: ListView.Selected) -> None:
        lv = self.query_one("#model-list", ListView)
        self.dismiss(lv.index)

    def key_escape(self) -> None:
        self.dismiss(None)


class TlamatiApp(App[None]):
    """Chat agéntico interactivo: la cara humana de run_loop."""

    TITLE = "tlamati"
    CSS = CSS
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("ctrl+enter", "submit", "Enviar", priority=True),
        Binding("ctrl+j", "submit", "Enviar (alt)", priority=True),
        Binding("ctrl+s", "toggle_sessions", "Sesiones"),
    ]

    def __init__(
        self,
        workdir: Path | None = None,
        session_db: str | None = None,
        skills_extra_dirs: list[Path] | None = None,
        max_turns: int = 60,
        stall_repeats: int = 3,
        sandbox: bool | None = None,
        sandbox_net: bool | None = None,
    ) -> None:
        super().__init__()
        self.workdir = workdir or Path.cwd()
        self._session_db_arg = session_db
        # SEC.2: la TUI recibe los flags de sandbox IGUAL que headless (antes
        # llamaba make_tools() sin flags → red inalcanzable aunque el flag
        # existiera; mismo patrón que el pitfall #5 de E3d con --skills-dir).
        # None = "no opinó" → resuelve config.yaml > default (net=True).
        self._sandbox_flag = sandbox
        self._sandbox_net_flag = sandbox_net
        # E3d PASO A: la TUI recibe --skills-dir / config skills.extra_dirs
        # IGUAL que headless (pitfall #5 sesión 20: el flag existía en cli.py
        # desde C3 y la TUI lo ignoró — el fundador lo descubrió usándola).
        self._skills_extra_dirs = list(skills_extra_dirs or [])
        # E3d PASO B: límites configurables (antes 20 hardcodeado = muro con
        # frenazo seco). max_turns <= 0 = yolo; stall_repeats = detector de
        # bucles muertos (mismo tool call N turnos seguidos → corte + aviso).
        self._stall_repeats = stall_repeats
        self._always_allow: set[str] = set()
        self._history: list[Message] = []
        self._turn_text: list[str] = []
        self._turn_md: Markdown | None = None
        self._stream_dirty = False
        self._busy = False
        self._last_result: LoopResult | None = None
        self._total_turns = 0  # turnos acumulados de TODA la sesión TUI
        # Componentes de corrida (se construyen en on_mount).
        self.registry: Registry | None = None
        # F1: el provider ES un ModelRouter (façade Provider). Intercambiable
        # en frontera de turno con /model; loop.py nunca se entera.
        self.provider: ModelRouter | None = None
        self._base_url = ""
        self._api_key = ""
        self._model_tiers: dict[str, str] = {}  # small/medium/frontier -> id
        self.budget: Budget | None = None
        self.compactor: Compactor | None = None
        self.store: SessionStore | None = None
        self.session_id: str | None = None
        self.ledger: Ledger | None = None
        self.max_turns = max_turns
        # E3d PASO B: al topar el muro NO hay frenazo seco — se ofrece
        # continuar ("continúa") o pedir un resumen ("resumen").
        self._awaiting_wall_choice = False
        self.setup_error: str | None = None

    # ------------------------------------------------------------------ UI

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal():
            with VerticalScroll(id="transcript"):
                yield Static(
                    f"[b]tlamati {__version__}[/b] — ctrl+enter envía, "
                    "ctrl+s sesiones, ctrl+q sale",
                    markup=True,
                    classes="note-line",
                )
            yield ListView(id="sessions")
        yield Static("ctx: —", id="ctxbar")
        yield TextArea(id="prompt")
        yield Footer()

    def on_unmount(self) -> None:
        """Cierre honesto de la sesión al salir de la TUI (ctrl+q / exit)."""
        if self.store is not None:
            if self.session_id is not None:
                stop = self._last_result.stop_reason if self._last_result else "closed"
                self.store.finish_session(
                    self.session_id, stop_reason=stop, turns=self._total_turns
                )
            self.store.close()

    def on_mount(self) -> None:
        self.title = f"tlamati {__version__}"
        self._setup_run()
        if self.provider is not None and not self.setup_error:
            self.sub_title = f"modelo: {self.provider.model}"
        if self.setup_error:
            self._note(f"ERROR de arranque: {self.setup_error}", cls="tool-error")
        self._refresh_sessions()
        # E1 stream throttle: los deltas de texto se ACUMULAN y un timer los
        # vuelca al widget Markdown cada 150 ms. Llamar Markdown.update() por
        # delta (sin await) programa AwaitCompletes concurrentes que corrompen
        # el documento final (bug real cazado en el smoke: source final ≠
        # acumulado). El timer serializa: un solo rebuild en vuelo a la vez.
        self.set_interval(0.15, self._flush_stream)

    # ------------------------------------------------------------- setup

    def _setup_run(self) -> None:
        """Composición de corrida (subconjunto honesto del headless).

        Fallo de arranque = setup_error + corrida deshabilitada (fail-fast
        visible, nunca una app que parece viva y no puede hablar)."""
        try:
            cfg = load_config()
            cfg_provider = cfg.get("provider") or {}
            model = str(cfg_provider.get("model") or DEFAULT_MODEL)
            base_url = str(cfg_provider.get("base_url") or DEFAULT_BASE_URL)
            api_key = _resolve_api_key(cfg_provider)
            if not api_key:
                self.setup_error = "falta la API key (OPENROUTER_API_KEY)"
                return
            self._base_url = base_url
            self._api_key = api_key
            self.provider = self._make_router(model, base_url, api_key, cfg)

            system_prompt = str(cfg.get("system_prompt") or DEFAULT_SYSTEM)
            # Sesión 25 (dogfooding #3): el modelo debe saber que SÍ ve el
            # filesystem y dónde está el Desktop REAL (WSL: /mnt/c/Users/...).
            # Estático por corrida → prefijo cacheable byte-estable.
            from tlamati.env_info import environment_block

            system_prompt += "\n\n" + environment_block(self.workdir)
            instr = load_instructions(self.workdir)
            if instr.found:
                system_prompt += render_for_prompt(instr)
            self._system_prompt = system_prompt

            # SEC.2 (bug raíz): cablear sandbox/net — flag > config > default
            # (enabled=True, net=True). Mismo núcleo que headless (cli.py).
            from tlamati.cli import resolve_sandbox_flags

            sandbox, sandbox_net = resolve_sandbox_flags(
                cfg, enabled_flag=self._sandbox_flag, net_flag=self._sandbox_net_flag
            )
            tool_list = make_tools(self.workdir, sandbox=sandbox, sandbox_net=sandbox_net)
            policy = Policy(
                PolicyConfig.from_dict(cfg.get("permissions")), plan_state=PlanState(active=False)
            )

            # Sesión (C1): persistir durante la corrida, crash-safe.
            store = SessionStore(self._session_db_arg or str(DEFAULT_SESSION_DB))
            if store.broken:
                self.store = None
                self._note(f"[session] aviso: {store.broken} — sin persistir")
            else:
                self.store = store
                self.session_id = f"{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
                store.create_session(
                    self.session_id, cwd=str(self.workdir), model=model, first_prompt=""
                )
                # C7: session_search — capability sin orden (igual que headless).
                from tlamati.session.search import make_session_search_tools

                tool_list.extend(make_session_search_tools(store.path))

            # Ledger (B5): auditoría append-only (fail-soft como en headless).
            try:
                self.ledger = Ledger(Path(DEFAULT_AUDIT_DB), self.session_id or "tui")
            except sqlite3.Error:
                self.ledger = None

            # Memoria + skills (C2/C3): prefijo + tools (mismos helpers que CLI).
            try:
                mem_store = MemoryStore(default_memory_dir())
                seed_if_empty(mem_store)
                mem_block = mem_store.render_for_prompt()
                if mem_block:
                    self._system_prompt += (
                        "\n\n# MEMORIA DURABLE (leída al inicio; usa el tool `memory` "
                        "para actualizarla)\n" + mem_block
                    )
                tool_list.extend(make_memory_tools(mem_store))
            except OSError:
                pass
            try:
                # E3d PASO A: mismas raíces que headless — extra dirs (flag/
                # config) + ~/.hermes/skills al final SI existe (ceremonia
                # cero, decisión del fundador opción A).
                cfg_skills = cfg.get("skills") or {}
                extra = list(self._skills_extra_dirs) + [
                    Path(os.path.expanduser(str(d))) for d in cfg_skills.get("extra_dirs") or []
                ]
                library = SkillLibrary(default_skill_roots(self.workdir, extra))
                if library.catalog():
                    self._system_prompt += "\n\n# SKILLS\n" + library.catalog_text()
                tool_list.extend(make_skill_tools(library))
            except OSError:
                pass

            self.registry = Registry(
                tool_list,
                approver=self._approver,
                policy=policy,
                ledger=self.ledger,
            )
            self.budget = Budget(max_context_tokens=DEFAULT_MAX_CONTEXT)
            cfg_compact = cfg.get("compaction") or {}
            chain = str(cfg_compact.get("model") or DEFAULT_COMPACT_MODEL)
            summarizer = ModelSummarizer(
                [
                    OpenAICompat(model=m.strip(), base_url=base_url, api_key=api_key)
                    for m in chain.split(",")
                    if m.strip()
                ]
            )
            self.compactor = Compactor(CompactionConfig(), summarizer)
        except (ValueError, OSError) as e:
            self.setup_error = f"{type(e).__name__}: {e}"

    # ---------------------------------------------------------- approver

    async def _approver(self, name: str, args: dict[str, Any]) -> bool:
        """Approver interactivo REAL (B4 lo anunciaba: 'el TUI de Fase E lo
        traerá'). allow-always es por corrida de la app, por tool, y NUNCA
        toca la Policy (la escalera solo endurece; esto es conveniencia del
        usuario humano presente, no relajación)."""
        if name in self._always_allow:
            return True
        body = build_diff_preview(name, args)
        verdict = await self.push_screen_wait(ApproveScreen(name, body))
        if verdict == "always":
            self._always_allow.add(name)
            return True
        if verdict == "once":
            return True
        self._note(f"tool {name!r} RECHAZADA por el usuario", cls="tool-error")
        return False

    # ------------------------------------------------------------- F1: modelos

    def _make_provider(self, model: str) -> OpenAICompat | AnthropicMessages:
        """Un provider segun la familia del modelo (F1). Anthropic por
        key/`claude-` usa el adapter nativo; el resto, OpenAI-compat.
        El prefijo del system prompt NO menciona el modelo: los swaps
        respetan la cache sagrada."""
        is_anth = model.startswith(("anthropic/", "claude-")) and (
            self._api_key.startswith("sk-ant-") or "anthropic.com" in self._base_url
        )
        if is_anth:
            return AnthropicMessages(model=model, api_key=self._api_key, base_url=self._base_url)
        return OpenAICompat(model=model, base_url=self._base_url, api_key=self._api_key)

    def _make_router(
        self, model: str, base_url: str, api_key: str, cfg: dict[str, Any]
    ) -> ModelRouter:
        """Router con el modelo default + los modelos nombrados en config
        ([models] tier=... y available=[...]). La lista remota se trae
        bajo demanda en /model; aquí solo lo barato y determinista."""
        self._base_url, self._api_key = base_url, api_key
        mcfg = cfg.get("models") or {}
        tiers = {str(k): str(v) for k, v in (mcfg.get("tiers") or {}).items()}
        self._model_tiers = tiers
        ids = [model] + [v for v in tiers.values() if v != model]
        for extra in mcfg.get("available") or []:
            if str(extra) not in ids:
                ids.append(str(extra))
        providers = {mid: self._make_provider(mid) for mid in ids}
        return ModelRouter(providers=providers, active=model, on_swap=self._log_swap)

    def _log_swap(self, ts: float, out: str, ins: str) -> None:
        """El swap es una decision del usuario: se audita como tool-evento
        (mismo ledger append-only, tool='model_swap')."""
        if self.ledger is None:
            return
        self.ledger.record_tool_event(
            tool="model_swap",
            args={"out": out, "in": ins},
            decision="user",
        )

    async def _open_model_palette(self) -> None:
        assert self.provider is not None
        router = self.provider
        # Traer la lista remota (fail-soft) y FILTRARLA: OpenRouter expone
        # 400+ modelos; la palette solo muestra los config + los que pasan
        # [models] filter (globs; "*" = todo). Pitfall HANDOFF §5: la lista
        # cruda es el problema de las 80 tools en miniatura.
        try:
            remote = await router.list_models()
        except Exception as e:
            remote = []
            self._note(
                f"[model] lista remota no disponible ({type(e).__name__}); usando config",
                cls="tool-error",
            )
        import fnmatch

        cfg = load_config()
        mcfg = cfg.get("models") or {}
        patterns = [str(p) for p in (mcfg.get("filter") or [])]
        show_all = "*" in patterns
        if not patterns:
            patterns = [str(v) for v in self._model_tiers.values()]
        visible = set(router.providers) | {str(v) for v in self._model_tiers.values()}
        if show_all:
            visible |= set(remote)
        else:
            visible |= {m for m in remote if any(fnmatch.fnmatch(m, p) for p in patterns)}
        tier_by_id = {v: k for k, v in self._model_tiers.items()}
        options: list[tuple[str, str]] = []
        for mid in sorted(visible, key=str.lower):
            bits = []
            if mid in tier_by_id:
                bits.append(tier_by_id[mid])
            if mid not in router.providers:
                bits.append("nuevo")
            hint = router.cache_hint(mid) if mid in router.providers else "nuevo"
            bits.append(f"cache:{hint}")
            options.append((mid, " · ".join(bits)))
        if not options:
            options = [
                (m, "cache:hot" if m == router.model else "cache:?")
                for m in sorted(router.providers, key=str.lower)
            ]
        idx = await self.push_screen_wait(ModelPalette(options, router.model))
        if idx is None or idx < 0 or idx >= len(options):
            return
        mid = options[idx][0]
        if mid not in router.providers:
            try:
                router.add_provider(self._make_provider(mid))
            except ProviderError as e:
                self._note(f"[model] no se pudo crear provider: {e}", cls="tool-error")
                return
        out = router.set_model(mid)
        if out != mid:
            self.sub_title = f"modelo: {mid}"
            cold = router.cache_hint(mid) == "cold"
            extra = (
                " — cache FRIO: el proximo turno reescribe el prefijo "
                "(pago unico, luego vuelve a hit)"
                if cold
                else " — cache caliente: el regreso es casi gratis"
            )
            self._note(f"[model] {out} → {mid}{extra}", cls="tool-line")

    def _handle_slash(self, text: str) -> bool:
        """True = el texto era un comando y ya fue manejado (no enviar al
        modelo). Por ahora solo /model; la familia de comandos crece aqui."""
        if text == "/model":
            if self._busy:
                self._note(
                    "[model] espera a que termine el turno actual "
                    "(el swap aplica en frontera de turno)",
                    cls="tool-error",
                )
                return True
            self.run_worker(self._open_model_palette(), exclusive=True)
            return True
        if text.startswith("/"):
            self._note(f"comando desconocido: {text} (disponible: /model)", cls="tool-error")
            return True
        return False

    # ------------------------------------------------------------- chat

    def action_submit(self) -> None:
        ta = self.query_one("#prompt", TextArea)
        text = ta.text.strip()
        if not text or self._busy or self.registry is None:
            return
        if self._handle_slash(text):
            ta.clear()
            return
        ta.clear()
        # E3d PASO B: tras topar el muro, el siguiente mensaje del usuario
        # decide — "continúa" reanuda con la historia intacta, "resumen" pide
        # un resumen de lo hecho (donor: Hermes lo fuerza a los 90 turnos;
        # aquí se OFRECE, nunca se fuerza). Cualquier otro texto = mensaje
        # normal (igual reanuda, la sesión C1 persiste).
        if self._awaiting_wall_choice and text.lower().startswith("resumen"):
            self._busy = True
            self._add_user(text)
            self.run_worker(self._make_summary(), exclusive=True)
            return
        if self._awaiting_wall_choice:
            self._awaiting_wall_choice = False
        self._busy = True
        self._add_user(text)
        self.run_worker(self._run_prompt(text), exclusive=True)

    def action_toggle_sessions(self) -> None:
        panel = self.query_one("#sessions", ListView)
        panel.toggle_class("visible")
        if panel.has_class("visible"):
            self._refresh_sessions()

    def _refresh_sessions(self) -> None:
        panel = self.query_one("#sessions", ListView)
        panel.clear()
        if self.store is None:
            return
        for s in self.store.list_sessions(limit=30):
            panel.append(ListItem(Label(s.human().splitlines()[0][:44])))

    async def _run_prompt(self, text: str) -> None:
        assert self.registry is not None and self.provider is not None
        assert self.budget is not None
        try:
            result = await run_loop(
                self.provider,
                system=self._system_prompt,
                user_prompt=text,
                tools=self.registry,
                budget=self.budget,
                max_turns=self.max_turns,
                stall_repeats=self._stall_repeats,
                on_event=self._handle_event,
                compactor=self.compactor,
                history=list(self._history) or None,
                on_message=self._persist_message,
            )
        except Exception as e:  # un bug nunca cuelga la app (loop invariant)
            self._note(f"corrida falló: {type(e).__name__}: {e}", cls="tool-error")
            self._busy = False
            return
        self._last_result = result
        # Bug 2 dogfooding #2: la TUI NUNCA llamaba finish_session → sessions.db
        # quedaba con stop_reason='' y turns=0 (forensia post-sesión rota; cli.py
        # sí lo hace). Fix: actualizar tras CADA corrida (crash-safe: si la app
        # muere, la última corrida ya quedó registrada) + cierre en on_unmount.
        self._total_turns += result.turns
        if self.store is not None and self.session_id is not None:
            self.store.record_usage(self.session_id, self._total_turns, result.usage)
            self.store.finish_session(
                self.session_id, stop_reason=result.stop_reason, turns=self._total_turns
            )
        u = result.usage
        status_cls = "" if result.stop_reason == "end_turn" else "tool-error"
        self._note(
            f"[fin] stop={result.stop_reason} turnos={result.turns} "
            f"tokens: in={u.input_tokens} out={u.output_tokens} "
            f"cache_read={u.cache_read_tokens}"
            + (f" · error={result.error}" if result.error else ""),
            cls=status_cls,
        )
        # E3d PASO B: al topar un límite NO hay frenazo seco — se explica y se
        # ofrece elegir. stall = bucle muerto (el aviso ya viene en result.error).
        if result.stop_reason == "max_turns":
            self._awaiting_wall_choice = True
            self._note(
                f"Límite de {self.max_turns} turnos alcanzado. Escribe 'continúa' "
                "para seguir donde quedamos (la historia está intacta), o "
                "'resumen' para un resumen de lo hecho.",
            )
        elif result.stop_reason == "stall":
            self._note(
                "Bucle detectado y cortado automáticamente (misma llamada, "
                "mismos argumentos, sin avance). Escribe qué ajustar, o "
                "'resumen' para un resumen de lo hecho.",
                cls="tool-error",
            )
            self._awaiting_wall_choice = True
        self._flush_stream(force=True)
        self._turn_md = None
        self._turn_text = []
        self._busy = False

    async def _make_summary(self) -> None:
        """E3d PASO B (donor Hermes, que lo fuerza a los 90 turnos; aquí se
        OFRECE): resumen del transcript con el ModelSummarizer de A6 (modelo
        barato + cadena de fallback). Gasto real, contado en la sesión."""
        self._awaiting_wall_choice = False
        summarizer = self.compactor.summarizer if self.compactor else None
        if summarizer is None:
            self._note("[resumen] sin summarizer disponible", cls="tool-error")
            self._busy = False
            return
        transcript = "\n".join(f"{m.role}: {m.content}" for m in self._history if m.content)[
            -60_000:
        ]
        summary, summary_usage = await summarizer.summarize(
            "Resume en cristiano qué se ha hecho en esta sesión, qué falta y "
            "dónde quedó el trabajo:\n\n" + transcript
        )
        # Contabilidad honesta: el resumen es gasto real → al ledger.
        if self.ledger is not None and summary_usage.input_tokens:
            self.ledger.record_turn_cost(
                turn=-1,  # fuera de la corrida (evento de cierre)
                input_tokens=summary_usage.input_tokens,
                output_tokens=summary_usage.output_tokens,
                cache_read=summary_usage.cache_read_tokens,
                cost_usd=summary_usage.cost_usd,
            )
        if summary is None:
            self._note("[resumen] el modelo de resumen falló (cadena agotada)", cls="tool-error")
        else:
            self._note("[resumen] de lo hecho hasta ahora:", cls="")
            self._turn_text = [summary]
            self._flush_stream(force=True)
            self._turn_md = None
            self._turn_text = []
        self._busy = False

    def _persist_message(self, m: Message) -> None:
        # La historia de la app crece con CADA mensaje (multi-turno real);
        # run_loop recibe copia, así que aquí mantenemos la fuente de verdad.
        # OJO nombre: `_on_*` en Textual es convención de message handlers —
        # NUNCA usar prefijo _on_ para callbacks propios (colisión silenciosa).
        self._history.append(m)
        if self.store is not None and self.session_id is not None:
            self.store.append_message(self.session_id, m)

    def _handle_event(self, kind: str, data: dict[str, Any]) -> None:
        """Consumidor de eventos del loop (mismo vocabulario que E2 --json)."""
        if self.ledger is not None and kind == "turn_end":
            self.ledger.turn = data["turn"]
            u = data["usage"]
            self.ledger.record_turn_cost(
                turn=data["turn"],
                input_tokens=u.input_tokens,
                output_tokens=u.output_tokens,
                cache_read=u.cache_read_tokens,
                cost_usd=u.cost_usd,
            )
        if kind == "text":
            self._turn_text.append(str(data["text"]))
            self._update_stream()
        elif kind == "budget":
            bar = self.query_one("#ctxbar", Static)
            u_note = ""
            if self._last_result is not None:
                lu = self._last_result.usage
                u_note = (
                    f" | último: in={lu.input_tokens} out={lu.output_tokens} "
                    f"cache_read={lu.cache_read_tokens}"
                )
            bar.update(f"{data['breakdown']}{u_note}")
        elif kind == "tool_run":
            args = str(data["args"])
            self._note(f"[tool] {data['name']} {args[:160]}")
        elif kind == "tool_result":
            if data.get("is_error"):
                self._note("[tool] ERROR (ver transcript)", cls="tool-error")
        elif kind == "turn_end":
            u = data["usage"]
            self._note(
                f"[turn {data['turn']}] in={u.input_tokens} out={u.output_tokens} "
                f"cache_read={u.cache_read_tokens}"
            )
            self._flush_stream(force=True)  # vuelco final del turno (no dejar deltas pendientes)
            self._turn_md = None
            self._turn_text = []
        elif kind == "compaction":
            self._note(
                f"[compaction] micro={data['microcompacted']} "
                f"resumidos={data['summarized']} tokens "
                f"{data['tokens_before']}→{data['tokens_after']}"
            )

    # ------------------------------------------------------- transcript

    def _add_user(self, text: str) -> None:
        t = self.query_one("#transcript", VerticalScroll)
        t.mount(Static(f"» {text}", classes="user-line", markup=False))
        t.scroll_end(animate=False)

    def _note(self, text: str, cls: str = "tool-line") -> None:
        t = self.query_one("#transcript", VerticalScroll)
        follow = t.is_vertical_scroll_end  # solo seguir si el usuario está abajo
        t.mount(Static(text, classes=cls, markup=False))
        if follow:
            t.scroll_end(animate=False)

    def _update_stream(self) -> None:
        """Los deltas solo MARCAN sucio el buffer; el timer serializa el
        volcado al Markdown (ver comentario en on_mount — bug real de
        AwaitCompletes concurrentes)."""
        self._stream_dirty = True

    def _flush_stream(self, *, force: bool = False) -> None:
        """Vuelco throttled del stream al widget Markdown del turno.
        force=True = vuelco final incondicional (fin de turno/corrida)."""
        if not self._turn_text:
            return
        if not (force or self._stream_dirty):
            return
        self._stream_dirty = False
        t = self.query_one("#transcript", VerticalScroll)
        follow = t.is_vertical_scroll_end  # bug UX real (20-nov): el scroll del
        # stream arrastraba la pantalla aunque el usuario hubiera subido a leer.
        # Fix: solo seguir al final si YA estaba al final (patrón follow-tail).
        if self._turn_md is None:
            self._turn_md = Markdown("".join(self._turn_text))
            t.mount(self._turn_md)
        else:
            self._turn_md.update("".join(self._turn_text))
        if follow:
            t.scroll_end(animate=False)


def run_tui(
    workdir: Path | None = None,
    session_db: str | None = None,
    skills_extra_dirs: list[Path] | None = None,
    max_turns: int = 60,
    stall_repeats: int = 3,
    sandbox: bool | None = None,
    sandbox_net: bool | None = None,
) -> int:
    """Entry point del CLI. `textual` es extra opcional (decisión #4)."""
    try:
        import textual  # noqa: F401
    except ImportError:
        print(
            "tlamati: la TUI necesita el extra opcional — instala con: pip install 'tlamati[tui]'",
            file=sys.stderr,
        )
        return 2
    app = TlamatiApp(
        workdir=workdir,
        session_db=session_db,
        skills_extra_dirs=skills_extra_dirs,
        max_turns=max_turns,
        stall_repeats=stall_repeats,
        sandbox=sandbox,
        sandbox_net=sandbox_net,
    )
    app.run()
    return 0
