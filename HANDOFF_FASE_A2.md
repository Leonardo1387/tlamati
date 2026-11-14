# HANDOFF 2 — CONTINUAR FASE A (pasos A-1d y A-1e)
# Generado por Hermes, 14-nov-2026, sesión 4 (cierre). Reemplaza a HANDOFF_FASE_A.md
# en cuanto a estado; el protocolo de ese archivo SIGUE VIGENTE.

## PROTOCOLO (no negociable, igual que antes)
1. Carga skill `tlamati-harness-project` + lee PRD_TLAMATI.md y GUIA_IMPLEMENTACION.md.
2. Un paso → entrega → el fundador revisa → siguiente. NUNCA encadenar.
3. Tras A7: ALTO, Fase B requiere luz verde.
4. Cierre de sesión: "clase del día" (edu/PROMPT_CLASE_DIARIA.md).
5. Hermes = auditor: auto-revisión honesta contra PRD §7 tras cada tarea.

## ESTADO REAL AL CIERRE DE ESTA SESIÓN (verificado con ejecución, no de memoria)

GIT: ~/code/tlamati, rama main, 4 commits:
  71d1211 A1+A2 scaffolding + core/messages.py
  890175f A3 provider adapters (base.py + OpenAICompat + AnthropicMessages)
  62ad808 A4+A5 loop + budget + tools_min + cli + DEMO FUNCIONAL
  (+ commit inicial docs). Working tree limpio.

CALIDAD: 54 tests verdes · ruff limpio · mypy --strict limpio (15 archivos).
INSTALADO: `uv tool install --force --from . tlamati` → tlamati + tlamati-eval en PATH.
  PITFALL: uv tool puede usar caché de wheel obsoleto → si falta un módulo recién
  agregado: `uv cache clean tlamati && uv tool install --reinstall --force --from . tlamati`.

DEMUESTRO (el demo de Fase A YA PASÓ, 14-nov):
  /tmp/tlamati-demo/calc.py con bug (promedio restaba 1) →
  `tlamati -p "El test de calc.py falla... arréglalo y verifica"` con qwen/qwen3-coder
  vía OpenRouter → read_file → write_file corregido → terminal corre test → TEST OK →
  "TERMINADO". stop=end_turn, 4 turnos, 2993 in/282 out, cache_read=2224.
  Overhead pre-primer-prompt: 258 tokens (system=52 tools=140 history=66) vs meta
  PRD §5 <8000 → 3%. Verificación independiente post-demo: TEST OK real.
  (El repo /tmp/tlamati-demo puede no sobrevivir; A7 trae sus propias fixtures.)

## LO CONSTRUIDO (mapa rápido para no releer todo)

- src/tlamati/core/messages.py (223 LOC): Message/ToolCall/ToolResult/Usage frozen;
  roundtrip as_dict/from_dict; eventos TextDelta/ToolCallStart/ToolCallArgsDelta/
  MessageEnd(stop_reason: end_turn|tool_use|max_tokens|refusal|error).
  Invariantes: assistant vacío = ValueError (el loop usa placeholder "(sin contenido)"
  cuando el stream muere sin nada — bug cazado por test en esta sesión).
- src/tlamati/providers/base.py: Provider Protocol (model = property read-only),
  ToolSpec, ProviderError(kind/retryable/status/raw), iter_sse, post_stream
  (429/5xx retryable), tools_to_openai, tools_to_anthropic (cache_control en última
  tool).
- src/tlamati/providers/openai_compat.py: OpenRouter/Ollama/vLLM; acumulación de
  tool-args por índice; finish_reason raro → error tipado con raw; usage con
  cached_tokens; error-body dentro de HTTP 200.
- src/tlamati/providers/anthropic_messages.py: tool_use/tool_result, merge de roles
  consecutivos, strip de huérfanos, breakpoints (último bloque system + última tool),
  usage cache_read/write visible. NO probado contra red real aún (sin key nativa;
  en A-1d/e se puede probar vía OpenRouter base_url).
- src/tlamati/core/loop.py (290 LOC, tope 500): run_loop() función + LoopState;
  SIGINT#1 = interjección al siguiente turno, SIGINT#2 = _Abort; tool desconocido o
  args inválidos → ToolResult is_error (autocorrección del modelo); LoopResult con
  stop_reason tipado.
- src/tlamati/context/budget.py: count_tokens (tiktoken cl100k_base + fallback
  chars/4 honesto), Budget.breakdown(system,tools,history) → ContextBreakdown con
  SectionCost nombradas (system/tools/history) y umbrales WARN 80% / HARD 95%.
- src/tlamati/tools_min/mini.py: PROVISIONAL (corrección aprobada por el fundador
  14-nov, documentada en HANDOFF_FASE_A.md A4): read_file numerado, write_file,
  terminal foreground 120s; truncado M1 50KB con marcador honesto; make_tools(workdir)
  pinneado al cwd. B1-B3 lo reemplaza por registry formal con permisos+sandbox.
- src/tlamati/cli.py: -p headless, --model/--base-url/--max-turns/--max-context/
  --quiet; config en tlamati.yaml o ~/.config/tlamati/config.yaml; key por
  OPENROUTER_API_KEY con fallback a ~/.hermes/.env (lee en Python, NUNCA exportar
  en shell — el parser de Hermes bloquea comandos que exponen keys).
- dev/smoke_openrouter.py: transcript real contra OpenRouter (usar modelo
  qwen/qwen3-coder — el slug :free murió, 404 honesto).

## PENDIENTE EXACTO (siguiente sesión)

PASO A-1d = A6 context/compaction.py:
  - Resumen con MODELO BARATO configurable (fallback chain) cuando budget.status
    == warn/exceeded.
  - REGLA DE ORO: reconstruye SOLO el sufijo; jamás muta el prefijo cacheable
    (system+tools+primeros mensajes estables). Invariante "caching is sacred".
  - Retención de tool outputs recientes (donor: codex compact_retained_tool_outputs).
  - Considerar ANTES microcompactación M2 (qwen microcompact.ts: borrar contenido de
    tool-results viejos reproducibles con placeholder + anti-collision regex) — es más
    barata que resumir con modelo y el mapa de 5 capas (research/04 + skill) dice:
    truncar → microcompactar → budget-compaction → resumen → ventana nueva. Decidir
    con el fundador si A6 incluye M2 o solo el resumen (mi recomendación: A6 = resumen
    mínimo + M2 queda documentado como extensión; no inflar el paso).
  - Prueba: sesión larga sintética (FakeProvider con muchos turnos) que dispara
    compaction sin romper caché + demo real opcional.
  - Integración: el loop debe llamarla al entrar en status exceeded/warn (hoy solo
    retorna budget_exceeded). Cuidado: hook en _run_inner ANTES del provider call.

PASO A-1e = A7 fixtures/ + tlamati-eval:
  - 5 tareas terminal-bench-lite propias en fixtures/ (cada una: repo semilla con bug
    + instrucción + verificador ejecutable tipo test_basico).
  - runner src/tlamati/evals/runner.py (hoy stub exit 2): recorre tareas, corre
    run_loop headless, emite JSONL {task, success, turns, tokens_in, tokens_out,
    cost_usd, stop_reason, duration}.
  - Baseline con qwen/qwen3-coder vía OpenRouter (key: fallback ~/.hermes/.env ya
    cableado en cli.py; reusar _resolve_api_key).
  - costo: el modelo ya NO es :free (~centavos por corrida, visto en smoke).
  - Cierre: clase del día que cierra la fase + ALTO (Fase B gated).

## DECISIONES/CONTEXTOS NUEVOS DE ESTA SESIÓN (no re-litigar)
- Overhead chico NO pierde calidad: contenido de tarea viaja en history; evidencia
  research/01 (Vercel +20pts quitando herramientas; Letta>CC mismo modelo). La guía
  conductual extra entra bajo demanda vía AGENTS.md/skills/routing.md (Fase C/F6b),
  no en el prefijo fijo. Validación final = A7 (delta de arnés vs opencode).
- Provider Protocol: model como property read-only (frozen dataclasses satisfacen).
- interjección SIGINT entra SOLO al inicio del siguiente turno (nunca mid-stream,
  invariante hermes: no mensajes user sintéticos a mitad del loop).
- El test test_interjection manda SIGINT real al proceso: vigilar flakiness en el
  primer push a GH Actions; si falla en CI, marcar @pytest.mark.skipif(en_ci).

-- Hermes, 14-nov-2026, sesión 4. --
