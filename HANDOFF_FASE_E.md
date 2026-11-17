# HANDOFF FASE E — Superficies + eval completo + pulido OSS (v0.1)
# Generado por Hermes, 17-nov-2026 (sesión 14). Punto de entrada para una
# sesión con CERO contexto: leer este archivo completo, cargar la skill
# `tlamati-harness-project` (skill_view) + references/fase-d-state.md, y
# seguir §5 en orden.
# Protocolo VIGENTE: un paso → entrega → OK verbal del fundador → Hermes
# auto-audita (pytest + ruff check + ruff FORMAT --check + mypy --strict +
# baseline REAL) y fusiona. Fundador NO-técnico: NUNCA pedirle revisar código;
# presentar evidencia de COMPORTAMIENTO en cristiano. Clase del día al cierre
# (edu/PROMPT_CLASE_DIARIA.md v2; la próxima es CLASE_11 — CLASE_10 ya escrita).

## 1. ESTADO ACTUAL (17-nov sesión 14, verified)
- main = aafb595 (merge de d3-mcp): FASES A+B+C+D COMPLETAS. CI verde (run
  44169349318, 34s).
- 345 tests verdes (20 nuevos en tests/test_mcp_d3.py), ruff+format+mypy
  strict limpios (44 archivos src).
- Baseline REAL vigente: evals/d3_check.jsonl — 5/5 OK qwen/qwen3-coder
  OpenRouter, cache_read 2560-4496 (~70-95% del input). ESTE es el ratchet:
  ningún merge baja de 5/5.
- D3 (MCP) HECHO Y FUSIONADO (OK verbal del fundador en vivo: "haz el
  baseline, lo que falta del push a las clase_10 y handoff"):
  * src/tlamati/mcp/client.py (~354 LOC): MCPClient = subprocess stdio +
    JSON-RPC 2.0 (initialize → notifications/initialized → tools/list →
    tools/call); parse_mcp_config fail-soft; make_mcp_tools envuelve cada
    tool remota como mcp_<server>_<tool> con permission=ASK +
    produces_untrusted=True SIEMPRE (innegociable); timeout por llamada
    (default 60s, configurable timeout_s); cierre terminate→wait 5s→kill;
    NUNCA auto-descubre servidores (solo mcp.servers en tlamati.yaml o
    --mcp-config); url: (Streamable HTTP) = puerta abierta documentada NO
    construida (anti-speculative); resultados MCP NO entran a
    DEFAULT_COMPACTABLE_TOOLS (pueden no ser re-obtenibles).
  * CLI: --mcp-config PATH + --no-mcp; bloque de carga TRAS D1 (tools MCP al
    FINAL del tool_list, append-only, orden estable por nombre); cierre
    limpio de clientes tras run_loop. Log "[mcp] server=X tools=N".
  * tests/fake_mcp_server.py = PROCESO real con 8 modos (ok, bad_handshake,
    garbage_init, empty_tools, error_on_call, hang_on_call, hang_on_init,
    die_immediately).
  * SECURITY.md §MCP actualizado (contrato real, no promesa).
  * Smoke $0 verificado: [mcp] sale ANTES del 401; tools 1448→1528 tokens
    con servidor (prefijo SÍ cambia — esperado, visible al modelo);
    fail-soft real con muerto+vivo en la misma config.
- CLASE_10 escrita (edu/DESARROLLO_TLAMATI_CLASE_10.md): MCP como territorio
  no-confiable, zero-trust en fronteras de proceso, subprocess con pipes.
  Errores del día: (a) variable local `loaded` colisionaba con StoredSession
  (SEGUNDA vez el mismo patrón — nombres de dominio SIEMPRE); (b)
  tlamati-eval --task X --out Y SOBRESCRIBE el archivo completo (no hace
  merge) — re-correr baseline entero para evidencia limpia.
- Ramas viejas borrables (low prio): d3-mcp local+remota (fusionada);
  d2-plugins, d1-subagent, c6-routing, b5-ledger, c1-session, c5-plan-mode
  locales; origin/b2-tools, origin/fase-b, origin/c5-plan-mode, origin/d2-*,
  origin/d1-*.
- Untracked intencional: evals/b5_check2.jsonl + b5_check3.jsonl (evidencia
  rate-limit 16-nov; NO borrar sin leer).
- QUÉ HAY CONSTRUIDO (src/tlamati/): core/loop+messages; providers/; tools/
  (registry con escalera deny>ask>auto + hooks D2 + trifecta B4, files,
  search, terminal, builtin); context/ (budget, compaction, instructions,
  routing); sandbox/ bwrap; policy/ (config+ledger); session/store; memory/
  (store+dream, skills); plan/; subagent/; plugins/ (D2 + internal/
  ledger_plugin); mcp/ (D3); evals/ runner + 5 fixtures; cli.py (subcomandos
  sessions/audit; flags --plan-mode --dream --skills-dir --workspace
  --no-routing --no-subagents --plugins-dir --no-plugins --mcp-config
  --no-mcp etc.).

## 2. QUÉ LEER ANTES DE CODIFICAR (orden, ~20 min)
a) Este handoff completo.
b) skill_view(name='tlamati-harness-project') — protocolo, decisiones
   zanjadas (NO re-litigar), pitfalls acumulados, política de copiado.
c) GUIA_IMPLEMENTACION.md §"FASE E" — la spec:
   * E1. TUI Textual: input multilínea, stream con markdown, diff viewer con
     approve/reject, barra de costo/tokens por turno (context_breakdown
     visible), panel de sesiones.
   * E2. Headless: `tlamati -p "..." --json` (JSONL events) para CI; exit
     codes honestos.
   * E3. Evals ampliados: más fixtures terminal-bench-lite; comparar
     harness-vs-opencode en las mismas tareas (el delta que mide el
     diferenciador del PRD).
   * E4. Docs OSS + SECURITY.md completo (reporting de vulnerabilidades) +
     publish v0.1: repo privado → PÚBLICO, PyPI (nombre tlamati verificado
     libre el 14-nov).
d) PRD_TLAMATI.md §6 MoSCoW: F7 TUI [MUST], F10 evals [MUST]; §métrica de
   éxito overhead <8k tokens.
e) DONORS E:
   - vendor/opencode packages/core (Apache-2.0): permission.ts para el
     approve/reject del diff viewer.
   - vendor/qwen-code (Apache-2.0): UI de terminal con stream markdown.
   - hermes-agent (MIT): semántica de exit codes honestos y eventos JSONL.
   - Textual (MIT): la librería TUI de Python — verificar si entra como dep
     (decisión: ¿optional extra `tlamati[tui]` o dep base? Recomendado:
     optional extra, el headless no debe pagarla).

## 3. DECISIONES ABIERTAS DE LA FASE E (preguntar al fundador EN CRISTIANO)
1. Pregunta abierta de CLASE_10: ¿qué ve un extraño en los primeros 5 min
   del repo público — TUI bonita (E1 primero) o `tlamati -p` real (E2
   primero)? La respuesta fija el orden. Recomendación Hermes: E2 primero
   (barato, habilita CI/evals ampliados) y E1 después.
2. E3 evals ampliados: ¿cuántas fixtures nuevas y de qué dificultad? Las 5
   actuales son terminal-bench-lite triviales; el delta harness-vs-opencode
   necesita tareas donde el arnés muerda (contexto largo, multi-tool).
3. v0.1 público: ¿el repo pasa a público al terminar E4 o el fundador fija
   otra fecha? (Decisión SUYA — preguntar, no asumir.)
4. TUI: Textual como optional extra (recomendado) — ratificar.

## 4. ¿GASTA?
- Construir E1/E2/E4 + tests: $0 (TUI se prueba con FakeProvider; headless
  --json con mocks; docs no gastan).
- E3 evals ampliados: SÍ gasta (cada fixture nueva corre contra OpenRouter;
  qwen/qwen3-coder, centavos por corrida). Pedir OK ANTES de correr.
- Baseline real tras cada unidad: centavos vía OpenRouter. Si falla: leer
  campo `error` del JSONL — 429/504 es upstream (pasó en B5, D2 y D3 —
  paciencia, reintentar tras 45-60s, NUNCA asumir fallo propio sin leer el
  error). OJO NUEVO (sesión 14): `tlamati-eval --task X --out Y` SOBRESCRIBE
  Y — si re-corres una sola tarea, el JSONL final debe regenerarse completo.

## 5. SIGUIENTE ACCIÓN EXACTA (sesión nueva)
1. `cd ~/code/tlamati && git checkout main && git pull` (verificar
   main=aafb595 o posterior, CI verde `gh run list --branch main --limit 1`).
2. `uv run pytest tests/ -q` → confirmar 345 verdes ANTES de tocar nada.
3. Presentar al fundador las 4 decisiones abiertas de §3 EN CRISTIANO (con
   recomendación por cada una) y obtener respuesta ANTES de codificar — la
   Fase E tiene más superficie de producto que las anteriores y el orden
   depende de su respuesta.
4. Con el orden decidido: `git checkout -b e<N>-<tema>` → implementar la
   unidad + tests + lint trio + baseline real (si toca corrida con modelo) →
   commit + push + evidencia de comportamiento al fundador → OK verbal →
   merge main → CI verde. UNA unidad por sesión (no encadenar E1+E2+E3).
5. CLASE_11 al cierre (v2). Temas naturales según unidad: TUI = "la cara del
   agente" (stream, diff viewer, approve/reject); headless --json = "el
   agente como ciudadano de CI"; evals ampliados = "cómo se mide un arnés"
   (el delta harness-vs-opencode es EL dato del PRD).

## 6. CÓMO VERIFICAR SIN GASTAR (audit local = CI exacto)
```
uv run pytest tests/ -q          # ≥345 verdes
uv run ruff check src tests
uv run ruff format --check .
uv run mypy --strict src
```
Smokes gratis: TUI se arranca con FakeProvider/scripted (sin red); headless
--json con OPENROUTER_API_KEY=*** muere en 401 PERO los eventos JSONL ya
salieron (técnica Clase 7 — la evidencia de comportamiento precede al
provider). MCP: /tmp con tlamati.yaml + tests/fake_mcp_server.py sigue
siendo el banco de pruebas ($0).

## 7. BASELINE REAL (tras cada unidad que toque corrida, gasta centavos)
```
uv tool install --from . tlamati --reinstall
tlamati-eval --out evals/e<N>_check.jsonl
```
Esperado: `[eval] 5/5 OK`, cache_read ~70-95%. Ratchet: si baja de 5/5 por
código propio (no 429/504), NO mergear. OJO: evals ENJAULADOS con bwrap —
los evals NO configuran servidores MCP (ninguno debe arrancar en la suite).

## 8. PITFALLS ACUMULADOS (lista completa en la skill; nuevos de la sesión 14)
- AUDITORÍA LOCAL = pytest + ruff check + ruff FORMAT --check + mypy
  --strict. CI solo corre en main/PR (push de rama NO dispara run).
- `tlamati-eval --task X --out Y` SOBRESCRIBE Y completo — el JSONL de
  evidencia debe regenerarse con la corrida COMPLETA (no vale merge manual).
- Nombres locales genéricos en funciones largas colisionan TIPOS: pasó con
  `report` (sesión 13) y `loaded` (sesión 14) → nombres de dominio SIEMPRE;
  mypy strict es el que los caza.
- Tests async del proyecto: asyncio_mode=auto de pytest-asyncio — NO usar
  @pytest.mark.anyio (ruido; corre pero sobra).
- Ledger para leer en tests: NO hay led.tool_events(); usar
  Ledger.read_session(db_path, session_id) → (events, costs) con atributos
  .decision/.is_error (dataclass ToolEvent).
- `git add -A` atrapa untracked intencionales (b5_check2/3) — paths
  específicos + revisar git status/diff --cached --stat antes del commit.
- Comandos simples, uno por llamada (protocolo #6): &&-chains con verbos
  destructivos, heredocs raros y `curl | python3` disparan bloqueos falsos.
  Excepción estable: git commit -F - con heredoc.
- OpenRouter 429/504: el campo `error` del JSONL es la fuente de verdad;
  reintentar tras 45-60s (en D3 bastó 1 retry; en D2 hicieron falta 3).
- Policy nunca relaja; tools MCP: ASK + produces_untrusted innegociables.
- Orden tools.specs() append-only; estado dinámico en primer mensaje.
- run_loop exige budget= keyword. uv cache clean tlamati si wheel raro.
- Background processes mueren con la sesión — corridas largas idempotentes.
- ruff format reescribe ternarios/if largos a su forma canónica — correr
  `ruff format` ANTES del commit, no `format --check` y parchar a mano.

## 9. AL CIERRE DE LA PRÓXIMA SESIÓN
CLASE_11 (edu/DESARROLLO_TLAMATI_CLASE_11.md) formato v2. Continuidad:
Clase 10 (MCP/zero-trust) → según la unidad E que toque (ver §5.5).
Alternativos pendientes del fundador: perfilador de talento (D3b, SOLO post
v0.1 y con pedido explícito) e investigación multiplayer (asterisco, SOLO
con pedido explícito — precondición: persistir transcript de subagentes).

-- Hermes, 17-nov-2026 sesión 14. Main = aafb595 (A+B+C+D COMPLETAS,
-- CI verde, 345 tests, baseline 5/5 evals/d3_check.jsonl). Sigue FASE E
-- (TUI/headless --json/evals ampliados/docs+publish v0.1) — decidir orden
-- con el fundador (§3) antes de codificar. --
