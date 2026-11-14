# PASO 2.6 — Mecanismos de ahorro de tokens en los sustratos + red de Claude Code (evidencia REA v3)

Fecha: 14-nov-2026. Fuente: lectura directa de vendor/ (Apache/MIT) + grafo REA de cli.js
(evidence_id ev_88097eb4254fc1d6bb285ae480e8a8a8c137062fb6eaec3067db8eda2ceadb81, coverage
AST completo: 3.12M nodos, 1,034 findings; fase semántica en v4).

## 1. Los 5 mecanismos verificados (quién los tiene y dónde)

M1. TRUNCADO EN LA BOCA DE LA HERRAMIENTA (primera línea; barato; siempre activo)
- gemini-cli: packages/core/src/context/truncation.ts + processors/nodeTruncationProcessor
  (cap por línea: MAX_LINE_LENGTH_TEXT_FILE + '... [truncated]' honesto).
- qwen-code: utils/toolResultDisplayCompaction.ts (compacta el display del resultado,
  separado del historial).
- hermes-agent: read_file ~100KB cap + truncado por línea con next_offset.
- Principio Tlamati: NINGÚN tool result entra gigante al historial. El límite vive en la
  herramienta, no en el historial. ~80% del ahorro de sesión con ~0 riesgo de caché.

M2. MICROCOMPACTACIÓN — borrar tool outputs viejos SIN resumir con modelo (la joya)
- qwen-code: services/microcompaction/microcompact.ts (1,093 LOC Apache-2.0). Mecánica:
  * Whitelist COMPACTABLE_TOOLS (read_file, shell, grep, glob, web_fetch, web_search,
    edit, write_file, skill, search_memory, read_mcp_resource) — solo se borran outputs
    REPRODUCIBLES (la herramienta los puede volver a producir si hacen falta).
  * Umbral por caracteres TOTALES de tool results (DEFAULT_TOOL_RESULTS_TOTAL_CHARS_THRESHOLD,
    configurable via settings.toolResultsTotalCharsThreshold).
  * Reemplazo por placeholder: '[Old tool result content cleared]' e imagen
    '[Old inline media cleared: <mime>]' con regex anti-colisión que valida la forma
    COMPLETA del placeholder (no solo prefijo) para no borrar texto real del usuario
    que empiece igual — lección de precisión fina (issue #4239 documentado en el propio
    comentario del código: tool de archivos nuevo sin entrada en FILE_PATH_TOOLS =
    eviction silenciosa).
- Claude Code: strings "microcompact", "microcompact_boundary", "microcompact_start/end"
  en cli.js + uso de la API oficial de Anthropic context_management /
  clear_tool_uses_20250919 / cache_edits → corta detrás del último breakpoint de caché
  para no invalidar el prefijo. Esto RESUELVE el dilema del Paso 1 (ahorrar sin romper
  "caching is sacred"): editar el historial por la cola, no por la cabeza.
- Principio Tlamati: M2 es la capa BARATA y REVERSIBLE (el borrado deja pointer: tool +
  args → re-ejecutable) que corre ANTES de cualquier compaction con LLM.

M3. RETENCIÓN SELECTIVA POR OUTPUT (qué sobrevive a los cortes)
- codex: core/src/compact_retained_tool_outputs.rs — flag retain_across_windows en el
  envelope de cada FunctionCallOutput; outputs "client_authored" o marcados se conservan
  a través de la ventana; el resto es podable.
- Principio Tlamati: cada tool result lleva metadato de retención (ephemeral|sticky) en
  tiempo de escritura; la política vive en la herramienta, la ejecución en el podador.

M4. COMPACTIÓN CON PRESUPUESTO + FALLBACK DE VENTANA NUEVA
- codex: 14 compact_*.rs verificados (antes decía 12; corregido). compact_token_budget.rs:
  token-budget compaction SKIPPIA la summarización (local y remote) e instala ventana
  fresca — a veces tirar+resumen estructurado es más barato que resumir con modelo.
  compact_model_fallback.rs: si el modelo de resumen falla, degradar sin romper turno.
  compact_pending_input.rs: el input del usuario que llega DURANTE la compaction no se
  pierde (cola pendiente). history/src/compaction_checkpoint.rs: checkpoint para retomar.
- Principio Tlamati: 3 niveles: M2 (gratis) → resumen con modelo barato → ventana nueva.
  Umbrales 80/95%. Todo el subsistema tras el breakpoint de caché.

M5. PRESUPUESTO DE ITERACIONES/COSTO (evitar tokens que no deberían existir)
- hermes-agent: agent/iteration_budget.py — presupuesto compartido padre→hijo; el modelo
  solo es NOTIFICADO cuando agota de verdad (sin ruido preventivo).
- Anti-patrón documentado Paso 1: OpenHands loop infinito = sandbox no protege la factura.
- Principio Tlamati: spend cap por tarea + max_turns + grace call (una última llamada para
  que el agente cierre ordenado).

## 2. Red de Claude Code — evidencia REA v3 + strings cli.js (para el PRD local-first)

Endpoints hardcoded relevantes (grep cli.js, consistente con nodos `endpoint` del grafo):
- api.anthropic.com/v1/messages, /v1/models/... (core legítimo)
- /api/claude_code/metrics + /organizations/metrics_enabled + host http-intake.logs.us5.datadog
  (→ TELEMETRÍA a Datadog existe en el bundle; el gating por org confirma opt-in
    organizacional; mods/privacy del repo público existe precisamente para esto)
- /api/claude_cli_feedback, /api/claude_code_shared_session_transcripts (→ sesiones
  compartidas/transcritas suben al servidor si se usa; el flag /privacy y mods/sec-default
  mitigan)
- /mcp-registry/v0/servers + mcp-proxy.anthropic.com (→ descubrimiento de MCP por defecto
  pasa por proxy de Anthropic: para un arnés local-first esto es call-home estrutural)
- OAuth Google/Azure/AWS SDKs presentes en el bundle (dependencias, no necessarily activas).

Decisión PRD reafirmada (F local-first estricto): Tlamati NO debe tener NINGÚN endpoint
hardcoded excepto los que el usuario configure en providers; test automático: `--net off`
en sandbox + asertividad en eval de que una sesión completa funciona sin red salvo la
URL del provider en config. El grafo REA de su propio bundle nos da el patrón de
"evidencia de red" que un reviewer puede pedirle a cualquier arnés: inventario de
endpoints + workers + storage.

Nota lethal-trifecta: storage local del bundle = 3 nodos (localStorage/indexedDB como
claves) — su persistencia de sesión es local (SQLite/archivos), el call-out es por
transcripts compartidos opcionales. Exactamente la separación que Tlamati debe imitar:
memoria local, red opt-in explícita por herramienta.

## 3. Efecto en el diseño Tlamati (resumen ejecutivo para usuario)

Jerarquía de ahorro en orden de ejecución por turno:
  M1 truncar en herramienta (límite duro al volver del syscall)
  → M5 budget check (turno/costo/iters)
  → M2 microcompact cuando tool-results-bytes > umbral (placeholder + pointer,
     solo whitelist reproducible, solo DETRAS del último cache breakpoint)
  → M4 compaction con modelo barato al 80/95% → ventana nueva como último recurso.
Todos los mecanismos M2-M4 son TEMPORALES según el test de Han Lee (un modelo con
ventana enorme + cache abarato los reduce), PERO M1/M5/M2 son baratos de mantener y
M2 es el que más factura baja hoy (tool results = 60-90% de los tokens de sesión en
agentes de código — hallazgo consistente en los foros del Paso 1).
