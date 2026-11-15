# HANDOFF 3 — FASE A COMPLETA · ALTO (Fase B gated)
# Generado por Hermes, 14-nov-2026, sesión 5 (cierre). Reemplaza a HANDOFF_FASE_A2.md
# en cuanto a estado; el protocolo de HANDOFF_FASE_A.md SIGUE VIGENTE.

## PROTOCOLO (no negociable)
1. Carga skill `tlamati-harness-project` + lee PRD_TLAMATI.md y GUIA_IMPLEMENTACION.md.
2. Un paso → entrega → el fundador revisa → siguiente. NUNCA encadenar.
3. **Fase B NO arranca sin luz verde explícita del fundador.**
4. Cierre de sesión: "clase del día" (edu/, serie numerada — la próxima es CLASE_4).
5. Hermes = auditor: auto-revisión honesta contra PRD §7 tras cada tarea.

## ESTADO REAL AL CIERRE (verificado con ejecución, no de memoria)

GIT: ~/code/tlamati, rama main, working tree limpio. Commits relevantes:
  71d1211 A1+A2 · 890175f A3 · 62ad808 A4+A5 (demo) · 2e83795 A6 · 90f6a62 fix
  · d85e3fb A7 + BASELINE REAL.
CALIDAD: 72 tests verdes · ruff limpio · mypy --strict limpio (16 archivos).
INSTALADO: uv tool (tlamati + tlamati-eval en PATH). Pitfall: caché de wheel
  obsoleto → `uv cache clean tlamati && uv tool install --reinstall --force --from . tlamati`.

### A-1d (A6 compaction) — ENTREGADO
- src/tlamati/context/compaction.py (288 LOC): M2 microcompaction (whitelist de
  tools re-obtenibles, placeholder exacto anti-colisión "[Old tool result content
  cleared]", nunca limpia errores/chicos, idempotente, flag ToolResult.
  microcompacted permanente — lección qwen #4239) + resumen con cadena de modelos
  baratos (ModelSummarizer, ProviderError/vacío → siguiente) + degradación
  honesta "[COMPACTACIÓN DE EMERGENCIA]" si toda la cadena falla (donor codex
  compact_token_budget). Política: warn → solo M2 (gratis); exceeded → M2 + resumen.
- REGLA DE ORO verificada: solo se reconstruye el SUFIJO; head anchor
  (retain_first=2) y cola (retain_recent=8) byte-estables; test compara lo que
  VIAJA POR LA RED (as_dict sin id) en las 9 llamadas de sesión larga.
- Loop: hook en budget check ANTES del provider call (entre turnos, nunca
  mid-stream); run_loop(compactor=None) por defecto = comportamiento viejo.
- CLI: --compact-model (lista=fallback chain), --no-compact; evento [compaction].
- Smoke real (dev/smoke_compaction.py): resumen correcto de transcript real vía
  OpenRouter; 2ª corrida cache_read=80 (caché del gateway viva).

### A-1e (A7 evals) — ENTREGADO, FASE A CERRADA
- fixtures/ (5 tareas terminal-bench-lite): promedio (aritmético), offbyone
  (IndexError), conversor (fórmula), import_roto (módulo inexistente),
  crear_modulo (creación). Cada semilla FALLA sin fix — invariante testeado
  (test_seeds_all_fail_before_fix).
- src/tlamati/evals/runner.py: copia semilla a workspace → run_loop headless →
  verify.py decide (exit 0 + "VERIFY OK", éxito verificado no supuesto). JSONL
  schema: {task, success, turns, tokens_in, tokens_out, cache_read, cost_usd,
  stop_reason, duration_s, error}. Crash del loop = reporta y sigue.
  Flags: --task/--fixtures/--model/--base-url/--workspace/--out/--max-turns(12).
- BASELINE evals/baseline_2026-11-14.jsonl (qwen/qwen3-coder, OpenRouter):
  **5/5 OK**, 3-5 turnos/tarea, in=14888 out=870, cache_read=12720 (**85% del
  input por caché de prefijo** — el invariante medido), 16.7s total.
  Este archivo es el ratchet: fase futura que lo rompa → detener y revisar.
- Clase del día: edu/DESARROLLO_TLAMATI_CLASE_3.md (A6+A7+baseline+error del día).

## PENDIENTE (Fase B, GATED — GUIA_IMPLEMENTACION.md §B)
B1 tools/registry.py (Tool con permission, jsonschema antes de ejecutar) —
  reemplaza tools_min/ provisional. B2 herramientas formales (read/write/edit
  fuzzy 9 estrategias/search rg/terminal). B3 sandbox/bwrap.py (aquí SÍ se pide
  la clave de apt para bubblewrap+ripgrep — regla del protocolo #5: pedir EN ESE
  momento). B4 policy/ (auto|ask|deny + trifecta: tool result untrusted → salida
  escala a ask). B5 policy/ledger.py SQLite append-only + `tlamati audit`.
NOTAS: A7 corrió SOLO OpenRouter (Ollama fuera, deliberado — no re-añadir sin
preguntar). REA v4 NO relanzar (AST v3 suficiente). Comparación de arnés vs
opencode mismo modelo = experimento natural post-B (la vara: baseline 5/5, 85% cache).

## PITFALLS NUEVOS DE ESTA SESIÓN (acumulativos en skill references/fase-a-state.md)
- El loop crea Message(system) nuevo por llamada: ids internos difieren aunque el
  contenido sea idéntico → tests de estabilidad de prefijo comparan as_dict() SIN id.
- Budget de test mal calibrado enmascara compaction: si cada tool result ≈ 879
  tokens y retain_recent no cabe en el budget, la corrida muere en exceeded aunque
  el Compactor funcione. Calibrar: resultado_medio × retain_recent < 0.95 × budget.
- FixProvider de tests: marcar `done` tras el primer turno con tools o el loop
  repite el write_file hasta max_turns.

-- Hermes, 14-nov-2026, sesión 5. FASE A COMPLETA. --
