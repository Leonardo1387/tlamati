# HANDOFF FASE E3 — Evals ampliados + benchmark harness-vs-opencode
# Generado por Hermes, 17-nov-2026 (sesión 15). Punto de entrada para una
# sesión con CERO contexto: leer este archivo completo, cargar la skill
# `tlamati-harness-project` (skill_view), y seguir §5 en orden.
# Protocolo VIGENTE: un paso → entrega → OK verbal del fundador → Hermes
# auto-audita (pytest + ruff check + ruff FORMAT --check + mypy --strict +
# baseline REAL) y fusiona. Fundador NO-técnico: NUNCA pedirle revisar código;
# presentar evidencia de COMPORTAMIENTO en cristiano. Clase del día al cierre
# (edu/PROMPT_CLASE_DIARIA.md v2; la próxima es CLASE_11 — CLASE_10 ya escrita).

## 1. ESTADO ACTUAL (17-nov sesión 15, verified)
- main = e5ca031 (merge de e1-tui): FASES A+B+C+D COMPLETAS, E2 y E1
  FUSIONADAS. CI verde (run 44185714863, 45s).
- 372 tests verdes (14 nuevos test_headless_json_e2.py + 13 nuevos
  test_tui_e1.py), ruff+format+mypy strict limpios (47 archivos src).
- Baseline REAL vigente: evals/e2_check.jsonl — 5/5 OK qwen/qwen3-coder
  OpenRouter, cache_read hasta 4496/4742 (~95%). ESTE es el ratchet:
  ningún merge baja de 5/5. (evals/d3_check.jsonl era el anterior.)
- E2 HECHO Y FUSIONADO (OK verbal fundador):
  * core/json_events.py (~110 LOC): JsonlEmitter fail-soft, vocabulario
    init/text/tool_*/turn_end/budget/compaction/error/result, mapa
    stop_reason→exit code FAIL-CLOSED (0 end_turn, 1 max_turns, 2 uso,
    3 budget, 4 error, 5 aborted, 6 refusal, 7 max_tokens; desconocido=4).
  * CLI --json: stdout EXCLUSIVO del stream JSONL, evento init primero y
    result SIEMPRE último. Modo humano intacto (0/1/2).
  * Smoke $0 real: key dummy → 401 → RC=4 + result con error honesto;
    prefijo intacto (system=471 tools=957, idéntico a D3).
- E1 HECHO Y FUSIONADO (OK verbal fundador):
  * tui/app.py (~513 LOC): TlamatiApp sobre run_loop TAL CUAL. Chat
    multilínea (TextArea ctrl+enter), stream markdown (throttle 150 ms —
    ver §6 bug del día), ApproveScreen diff viewer once/always/reject
    (donor opencode permission.ts), barra ctxbar siempre visible, panel
    sesiones ctrl+s, approver interactivo REAL (promesa B4 cumplida),
    multi-turno con _history + session C1 + ledger B5.
  * textual = extra opcional tlamati[tui] (decisión #4). CLI: `tlamati`
    sin args Y con tty → TUI; sin tty → help (CI intacto).
  * Scope v1 honesto: routing/plugins/MCP/subagentes SOLO en headless
    (documentado en el docstring del módulo). E1b opcional post-v0.1.
- DECISIONES ZANJADAS FASE E (fundador 17-nov sesión 15, handoff §3 del
  HANDOFF_FASE_E.md — NO re-litigar): E2 primero (HECHO), E1 después
  (HECHO); E3 = 5 fixtures nuevas media-alta (total 10) + benchmark
  harness-vs-opencode con MISMO modelo; repo público al terminar E4 con
  AUDITORÍA DE SEGURIDAD COMPLETA como última puerta (barrido parcial ya
  hecho y limpio: .gitignore OK, sin claves en historia git, autor
  genérico); Textual extra opcional.

## 2. QUÉ LEER ANTES DE CODIFICAR (orden, ~15 min)
a) Este handoff completo.
b) skill_view(name='tlamati-harness-project') — protocolo, decisiones
   zanjadas, pitfalls acumulados.
c) GUIA_IMPLEMENTACION.md §"FASE E" E3: "Suite eval: ≥20 tareas
   (terminal/file/git/reasoning/latencia), 3 modelos objetivo (sonnet-4
   vía OR, coder80B Enverge, qwen3-ollama). Matriz ARNÉS×modelo
   documentada en EVALS.md — nuestro argumento del Paso 1". OJO: el
   fundador zanjó algo MÁS CORTO que la guía (decisión #2): 10 fixtures
   Tlamati + benchmark vs opencode con qwen3-coder. La guía es techo, no
   piso obligatorio — si el fundador quiere ampliar, preguntar.
d) research/01_HALLAZGOS_PASO1.md — los números que inspiran el benchmark
   (Vercel 80→100%, LangChain 52.8→66.5% harness-only, Letta 59.1 vs CC
   41.6 mismo modelo). Nuestro delta debe leerse igual: MISMO modelo,
   distinto arnés.
e) src/tlamati/evals/runner.py — el runner actual: recorre fixtures/,
   copia a workspace tmp, run_loop headless, verify.py decide (exit 0 +
   'VERIFY OK'), JSONL schema congelado {task, success, turns, tokens_in,
   tokens_out, cache_read, cost_usd, stop_reason, duration_s, error}.
f) fixtures/ — las 5 actuales (promedio/offbyone/conversor/import_roto/
   crear_modulo): cada una = repo semilla + instruction.md + verify.py.
   Invariante: la semilla FALLA antes del fix. OJO: hay __pycache__
   untracked dentro de fixtures (ignorar, no commitear).

## 3. PLAN E3 (dos unidades — UNA por sesión, no encadenar)

### E3a: 5 fixtures nuevas media-alta (total 10)
Dónde el arnés "muerda" (decisión #2 del fundador): tareas donde contexto
largo / multi-tool / memoria-plan importen. Candidatos concretos (elegir
5, o proponer variantes al fundador EN CRISTIANO antes de construirlas):
1. multi_archivo: bug repartido en 3 módulos que se llaman entre sí
   (fuerza search+read multi-paso).
2. output_grande: archivo/log de miles de líneas donde la respuesta está
   al final (fuerza truncado M1 + re-lectura con offset — el arnés que no
   trunca revienta el contexto).
3. git_history: repo semilla con .git y 5-6 commits; la tarea pide
   averiguar qué commit rompió algo (terminal multi-paso).
4. instruccion_en_archivo: el instruction.md apunta a un SPEC.md grande
   con las reglas; el fix debe cumplirlas (fuerza leer docs largos).
5. test_driven: semilla con tests que fallan (pytest en verify.py) y el
   fix exige pasar los 10 (itera edit→terminal→edit).
Reglas: cada fixture nueva prueba su invariante (semilla FALLA pre-fix,
verificado en test); verify.py = exit 0 + 'VERIFY OK'; mismo schema JSONL
(sin tocar el schema congelado); el runner las descubre solo (glob de
fixtures/ — verificar que no haya hardcode de nombres).
Costo: cada corrida de la suite de 10 = centavos vía OpenRouter. Pedir OK
ANTES de correr (AGENTS.md/skill: los evals GASTAN).
Ratchet: la suite vieja (5 triviales) sigue debiendo dar 5/5; la nueva se
reporta por separado hasta tener estabilidad (fixtures nuevas pueden
fallar legítimamente por dificultad — el punto ES medir, no que todo pase).

### E3b: benchmark harness-vs-opencode (el número publicable)
Pregunta central: con el MISMO modelo (qwen/qwen3-coder vía OpenRouter),
¿cuánto mejor/más barato resuelve Tlamati vs opencode las MISMAS tareas?
Pasos propuestos:
1. Verificar cómo correr opencode headless en esta máquina: vendor/opencode
   es el source (TS/bun). Opciones: (a) instalar el binario oficial
   `npm i -g opencode-ai` o bun (PREGUNTAR al fundador antes de instalar
   nada global); (b) si no corre, alternativa honesta documentada: baseline
   "raw model" (mismo modelo SIN arnés: system prompt mínimo + loop trivial)
   como piso de comparación, y decirlo con todas las letras en EVALS.md.
   NUNCA inventar números del competidor: si no se puede correr, se reporta
   lo que SÍ se corrió.
2. Mismo corpus: las 10 fixtures (instruction.md + verify.py son
   harness-agnostic — el verify decide, no nosotros).
3. Métricas por arnés: % tareas OK, tokens in/out totales, turnos,
   duration_s. De Tlamati además: overhead del prefijo (budget breakdown:
   system+tools ≈ 1.4k tokens) y cache_read %.
4. EVALS.md: tabla ARNÉS×modelo con fecha, modelo exacto, comando exacto
   de reproducción y JSONL crudos en evals/benchmark_<fecha>/. Estilo
   research/01: el delta es el titular ("mismo modelo, X% menos tokens /
   +Y pts de éxito").
5. Cada corrida GASTA (ambos arneses contra OpenRouter): OK del fundador
   ANTES, y reportar cuántas tareas × qué modelo = cuántas corridas.
Riesgos: opencode puede no soportar el provider OpenRouter con qwen3-coder
o requerir login propio — investigar ANTES de prometer la tabla completa;
si solo corre con Anthropic/OpenAI, el benchmark justo sería con ese mismo
modelo en AMBOS arneses (y cuesta más — decidir con el fundador).

## 4. ¿GASTA?
- Escribir fixtures + tests de invariante + runner: $0.
- Correr la suite ampliada (10 tareas) o el benchmark: SÍ gasta (centavos
  por corrida Tlamati; opencode añade lo suyo). Pedir OK ANTES.
- Baseline real tras merge: centavos vía OpenRouter. Si falla: leer campo
  `error` del JSONL — 429/504 es upstream (reintentar tras 45-60s, NUNCA
  asumir fallo propio sin leer). `tlamati-eval --task X --out Y` SOBRESCRIBE
  Y completo — regenerar la suite entera para evidencia limpia.

## 5. SIGUIENTE ACCIÓN EXACTA (sesión nueva)
1. `cd ~/code/tlamati && git checkout main && git pull` (verificar
   main=e5ca031 o posterior, CI verde `gh run list --branch main --limit 1`).
2. `uv run pytest tests/ -q` → confirmar 372 verdes ANTES de tocar nada.
3. E3a: `git checkout -b e3a-fixtures` → diseñar las 5 fixtures (si hay
   duda sobre cuáles, presentar candidatos al fundador EN CRISTIANO y
   esperar OK) → implementar + tests de invariante + lint trio → commit +
   push → pedir OK para la corrida REAL de la suite de 10 → evidencia al
   fundador → OK verbal → merge → CI verde.
4. E3b en OTRA sesión: investigar opencode runnable primero ($0), presentar
   opciones al fundador, y solo después correr el benchmark con OK.
5. CLASE_11 al cierre de la sesión (v2). Tema natural E3a: "cómo se mide un
   arnés" (fixtures, invariantes, el ratchet); si toca E3b: "el delta como
   argumento" (misma tarea, distinto arnés, mismo modelo).
6. Tras E3: E4 (docs OSS + SECURITY.md completo + AUDITORÍA DE SEGURIDAD
   FINAL + publicar v0.1 público + PyPI). La auditoría es la ÚLTIMA puerta
   antes del botón público (decisión #3): revisar docs/research por datos
   personales del fundador, verificar que vendor/ y rea-out/ jamás subieron,
   repasar historial git completo, y presentar evidencia al fundador — el
   gatillo final es SUYO.

## 6. PITFALLS NUEVOS (sesión 15, E1+E2) + heredados
- BUG REAL E1 (con test de regresión): Markdown.update() de Textual por
  delta SIN await programa AwaitCompletes concurrentes que corrompen el
  documento (source final ≠ acumulado). FIX: throttle — deltas marcan
  dirty, un set_interval(0.15) vuelca el buffer, force=True en turn_end y
  fin de corrida. REGLA: nunca llamar update() en ráfaga sin serializar.
- Textual 8: la variable de CSS `$red` NO existe (es `$error`);
  push_screen_wait SOLO corre dentro de un worker (@work); Markdown.source
  es el atributo del texto (render() devuelve Blank opaco); en tests,
  clases definidas dentro de bucles → fábrica para no capturar variables
  (B023).
- En Textual, métodos `_on_*` propios colisionan con la convención de
  message handlers del framework (mypy/pyright lo cazan) — prefijos de
  dominio SIEMPRE (mismo patrón que report/loaded en D2/D3): _handle_event,
  _persist_message.
- BINDINGS/CSS en App Textual: ClassVar[list[BindingType]] (invarianza de
  list en mypy strict; BindingType acepta tuplas además de Binding).
- RUF012 en tests: atributos de clase mutables (scripts de FakeProvider)
  → ClassVar.
- HEREDADOS (lista completa en la skill): auditoría local = pytest + ruff
  check + ruff FORMAT --check + mypy --strict; CI solo corre en main/PR;
  git add -A atrapa untracked intencionales (b5_check2/3) — paths
  específicos; 429/504 = leer campo error antes de tocar código; policy
  nunca relaja; prefijo append-only (cache sagrada); run_loop exige
  budget= keyword; ruff format ANTES del commit.

## 7. BASELINE REAL (tras cada unidad que toque corrida, gasta centavos)
```
uv tool install --from . tlamati --reinstall
tlamati-eval --out evals/e3a_check.jsonl
```
Esperado: `[eval] 5/5 OK` en las fixtures viejas (ratchet) + reporte aparte
de las nuevas. OJO: evals ENJAULADOS con bwrap — los evals NO configuran
servidores MCP (ninguno debe arrancar en la suite).

## 8. AL CIERRE DE LA PRÓXIMA SESIÓN
CLASE_11 (edu/DESARROLLO_TLAMATI_CLASE_11.md) formato v2. Continuidad:
Clase 10 (MCP/zero-trust) → "cómo se mide un arnés" (E3). La serie es un
LIBRO DE TEXTO: abrir conectando con la anterior, cerrar con gancho.
Alternativos pendientes del fundador (SOLO con pedido explícito, post
v0.1): perfilador de talento (piloto sobre ~/.hermes/state.db) e
investigación multiplayer (precondición: persistir transcript de
subagentes).

-- Hermes, 17-nov-2026 sesión 15. Main = e5ca031 (A+B+C+D + E1 + E2
-- COMPLETAS, CI verde, 372 tests, baseline 5/5 evals/e2_check.jsonl).
-- Sigue E3a (5 fixtures nuevas) → E3b (benchmark vs opencode) → E4
-- (docs + auditoría de seguridad + público v0.1). --
