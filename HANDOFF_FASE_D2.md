# HANDOFF FASE D2 — plugins + hooks (everything-plugin)
# Generado por Hermes, 17-nov-2026 (sesión 12). Punto de entrada para una
# sesión con CERO contexto: leer este archivo completo, cargar la skill
# `tlamati-harness-project` (skill_view), y seguir §5 en orden.
# Protocolo VIGENTE: un paso → entrega → OK verbal del fundador → Hermes
# auto-audita (pytest + ruff check + ruff FORMAT --check + mypy --strict +
# baseline REAL) y fusiona. Fundador NO-técnico: NUNCA pedirle revisar código;
# presentar evidencia de COMPORTAMIENTO en cristiano. Clase del día al cierre
# (edu/PROMPT_CLASE_DIARIA.md v2; la próxima es CLASE_9 — CLASE_8 ya escrita).

## 1. ESTADO ACTUAL (17-nov sesión 12, verified)
- main = d67fb60: FASES A+B+C completas + D1 FUSIONADO (merge --no-ff
  d1-subagent, sin conflictos). CI verde (run 44151620765, 21s).
- 308 tests verdes (16 nuevos en tests/test_subagent_d1.py), ruff+format+
  mypy strict limpios (39 archivos src).
- Baseline REAL vigente: evals/d1_check.jsonl — 5/5 OK con qwen/qwen3-coder
  vía OpenRouter, cache_read 74% (frío) → 94-95%. ESTE es el ratchet de
  Osmani: ningún merge baja de 5/5.
- D1 (subagentes) HECHO: src/tlamati/subagent/spawn.py (~270 LOC). Tool
  `delegate_task`(goal/context/max_turns) permission ASK; hijo read-only
  (PLAN_READONLY_TOOLS ∩ permission AUTO del padre — build_child_tools);
  profundidad 1 fail fast (ValueError → resultado honesto); _CappedProvider
  con tope de gasto acumulado in+out (default 200k) que bloquea ANTES de
  gastar; Budget de ventana heredado min(cfg, padre); padre recibe SOLO
  final_text + metadata honesta; auditoría del hijo al MISMO ledger con
  prefijo de sesión hija "<parent>:sub-NN" (decisión (a), sin migrar schema);
  NO entró a DEFAULT_COMPACTABLE_TOOLS (side-effect). CLI: bloque estático
  DELEGATE_PROMPT_BLOCK tras PLAN_MODE_PROMPT + tool AL FINAL (append-only);
  --no-subagents; config tlamati.yaml `subagent:` (max_turns_default/
  max_turns_cap/max_total_tokens/max_context_tokens). En plan-mode queda
  DENEGADA sola (fuera de whitelist C5).
- CLASE_8 escrita (edu/DESARROLLO_TLAMATI_CLASE_8.md): delegación con
  límites — padre/hijo, profundidad 1, presupuesto heredado, donores
  hermes delegate_task + Raschka #6.
- INVESTIGACIÓN NUEVA (esta sesión): research/06_OPENCRAWL_MULTIPLAYER_
  CONTEXT.md — OpenCrawl (YC, Apache-2.0, MCP server de memoria compartida
  entre agentes). Veredicto: NO integrar dentro de Tlamati (choca con
  no-goal multi-agente); SÍ conectable como MCP server externo cuando D3
  aterrice; NO construir algo así (otro proyecto). ANOTACIÓN PARA D3:
  OpenCrawl expone MCP por Streamable HTTP, no solo stdio — la config de D3
  debería aceptar `url:` además de `command:` (o al menos dejar la puerta
  abierta sin construirla — regla anti-speculative).
- vendor/opencrawl-core/ clonado (depth 1) para el estudio — NO commitear
  (vendor/ está fuera del repo, verificar git status antes de add -A).
- Ramas viejas borrables (low prio): d1-subagent local+remota ya fusionada;
  c6-routing local+remota; b5-ledger, c1-session, c5-plan-mode locales;
  origin/b2-tools, origin/fase-b, origin/c5-plan-mode remotas.
- Untracked intencional: evals/b5_check2.jsonl + b5_check3.jsonl (evidencia
  rate-limit 16-nov; NO borrar sin leer).
- QUÉ HAY CONSTRUIDO (src/tlamati/): core/loop.py + messages; providers/
  openai_compat (+anthropic_messages); tools/ (registry con escalera
  deny>ask>auto, files, search, terminal, builtin); context/ (budget,
  compaction M1+M2, instructions C4, ROUTING C6); sandbox/bwrap; policy/
  (config B4 + ledger B5); session/store (C1); memory/ (store+dream C2,
  skills C3); plan/ (C5); subagent/ (D1); evals/runner + 5 fixtures;
  cli.py con subcomandos sessions/audit y flags --plan-mode/--dream/
  --skills-dir/--workspace/--no-routing/--no-subagents/etc.
- Pregunta abierta heredada de Clase 6: ¿save_plan fuera de plan-mode como
  bitácora? → diferida a Fase E.

## 2. QUÉ LEER ANTES DE CODIFICAR (orden, ~20 min)
a) Este handoff completo.
b) skill_view(name='tlamati-harness-project') — protocolo, decisiones
   zanjadas (NO re-litigar), pitfalls acumulados, política de copiado.
c) GUIA_IMPLEMENTACION.md §"FASE D" (D2) — la spec (~150-250 LOC).
d) PRD_TLAMATI.md §6 MoSCoW: F11 plugins [SHOULD].
e) DONORS D2:
   - research/02_ESTUDIO_HARNESSES.md: Reasonix "everything is a plugin"
     [DEAD 12-nov, reference-only] + hook registry de gemini-cli:
     vendor/gemini-cli/packages/core/src/hooks/ (index.ts, hookSystem.test.ts,
     hookPlanner.test.ts, hookTranslator.test.ts) y
     vendor/gemini-cli/packages/core/src/scheduler/scheduler_hooks.test.ts.
   - REGLA anti-speculative (hermes): SOLO hooks con consumidor concreto.
     Los 3 y solo 3: before_tool / after_tool / on_error.
   - CONSUMIDOR #1 YA EXISTE: la auditoría del ledger está HOY hardcodeada
     en DOS sitios: (i) Registry.execute._log (tools/registry.py, registra
     tool_events con la decisión exacta) y (ii) _ledger_wrapper en cli.py
     (registra turn_costs desde el evento turn_end del loop). Ver §3 para
     la decisión de diseño central de D2.
   - OpenCrawl plugins/ (MIT, vendor/opencrawl-core/plugins/) — ejemplo de
     plugin que instala skills en otros agentes; valida formato SKILL.md.
f) Para el descubrimiento: importlib.metadata entry_points(group=
   "tlamati.plugins") — stdlib, cero deps nuevas.

## 3. SPEC DESTILADA (HANDOFF_FASE_D §3 D2 + diseño abierto)
### D2 — plugins/ (F11, ~150-250 LOC)
- Descubrimiento en 3 fuentes (orden estable): entry-point `tlamati.plugins`
  (importlib.metadata) + ~/.config/tlamati/plugins/*.py (usuario) +
  .tlamati/plugins/*.py (proyecto). Duplicados de nombre: primero gana +
  aviso honesto (donor C3 skills).
- Plugin = módulo Python con función `register(hooks)`; HookRegistry con
  before_tool/after_tool/on_error (SOLO esos 3).
- Carga fail-soft: plugin roto (import error, register que truena, sin
  register) = aviso honesto por stderr + seguir sin él, NUNCA romper la
  corrida (patrón skills C3, routing C6).
- Seguridad: plugins corren SIN sandbox (código del dueño de la máquina —
  mismo modelo que hermes). Documentar en SECURITY.md (tarea E4: si no
  existe, crear stub honesto que diga esto + la trifecta B4 + reporting).
- DECISIÓN DE DISEÑO CENTRAL (resolver primero, documentar en commit):
  ¿dónde se disparan los hooks y qué pueden hacer?
  Recomendación de Hermes (elegida en ventana yolo salvo que algo la
  contradiga al implementar):
  * before_tool(name, args) se dispara en Registry.execute ANTES del
    permission gate; puede VETAR devolviendo un string de error (→ ToolResult
    is_error honesto, decisión ledger "plugin_denied" o similar NUEVA — la
    lista de decisiones es append-only). NUNCA puede APROBAR ni relajar:
    policy nunca relaja (invariante B4 — un plugin solo ENDURECE).
  * after_tool(name, args, decision, result) se dispara TRAS la ejecución
    (o tras la decisión deny/ask_*) — es el punto donde el plugin de ledger
    registra tool_events (migración de Registry._log).
  * on_error(name, args, exception) cuando tool.run lanza — hoy el Registry
    ya lo convierte en resultado honesto; el hook OBSERVA, no cambia el
    comportamiento.
  * MIGRACIÓN del consumidor #1: mover el registro de tool_events (hoy en
    Registry.execute._log) a un plugin INTERNO (src/tlamati/plugins/
    internal/ledger_plugin.py o similar) cargado SIEMPRE (no descubrible/
    desactivable — es la auditoría, B5 no es opcional). PRUEBA REAL: los
    tests B5 existentes deben seguir verdes SIN CAMBIOS (comportamiento
    observable idéntico). turn_costs sigue en el _ledger_wrapper del CLI
    (es evento de loop, no de tool — no inventar un 4o hook).
  * Si al implementar la migración completa resulta demasiado invasiva para
    una unidad, alternativa honesta: HookRegistry + 3 hooks + fail-soft +
    plugin interno que SOLO añade (p.ej. duplica el registro) → NO. Preferir
    la migración real: es la prueba del mecanismo. Si no cabe en la ventana,
    entregar HookRegistry+descubrimiento+tests y dejar la migración como
    D2b documentado (nunca a medias sin decirlo).
- NO entra a DEFAULT_COMPACTABLE_TOOLS: los plugins no son tools (no hay
  tool nueva que el modelo vea — si un plugin expone tools al modelo, eso
  es Fase E+, regla anti-speculative).
- Prefijo cacheable: los plugins NO añaden nada al system prompt (no son
  visibles al modelo en D2). Si algo cambia el prefijo → violación de la
  cache sagrada; verificar con FakeProvider (test de prefijo byte-idéntico
  con y sin plugins cargados).
- CLI: --plugins-dir (extra, repeatable, donor --skills-dir) y
  --no-plugins (kill switch). Log "[plugins] N cargado(s), M fallido(s)"
  (donor routing/instructions).

### ORDEN DE TRABAJO
D2 es la unidad de ESTA sesión. Después vendrá D3 (MCP client stdio) en
otra sesión. Cada uno con: rama nueva saliendo de main (git checkout -b
d2-plugins), tests + lint trio + baseline real, commit, push, OK verbal,
merge a main, CI verde verificado (gh run list). NO encadenar dos fases sin
entrega intermedia (corrección del fundador 14-nov). Fundador usa ventanas
yolo cronometradas: al corte, TERMINAR la unidad en curso + resumen;
preferible no arrancar lo siguiente si no cabe en el tiempo.

## 4. ¿GASTA?
- Construir D2 + tests + lint: $0 (FakeProvider, cero red).
- Baseline real tras la fase: SÍ, centavos vía OpenRouter (qwen/qwen3-coder).
  Si falla: leer el campo `error` del JSONL — 429/504 es upstream, NUNCA
  asumir fallo propio; reintentar tras 15-60s. Alternativa: BYOK DeepInfra.

## 5. SIGUIENTE ACCIÓN EXACTA (sesión nueva)
1. `cd ~/code/tlamati && git checkout main && git pull` (verificar
   main=d67fb60 o posterior, CI verde con `gh run list --branch main --limit 1`).
2. `uv run pytest tests/ -q` → confirmar 308 verdes ANTES de tocar nada.
3. Leer §2 (skill + GUIA FASE D + donors: gemini hooks en vendor/, el
   Registry._log actual en tools/registry.py, _ledger_wrapper en cli.py).
4. Resolver la decisión de diseño de §3 (hooks en Registry.execute; plugin
   interno de ledger = migración real de _log; policy nunca relaja).
5. `git checkout -b d2-plugins` → implementar plugins/ (HookRegistry,
   descubrimiento 3 fuentes, fail-soft) + plugin interno ledger + SECURITY.md
   (stub honesto si no existe) + CLI flags + tests. Unidades de test:
   - HookRegistry: before_tool veta → ToolResult is_error honesto + decisión
     nueva en ledger; after_tool observa; on_error observa sin cambiar.
   - Descubrimiento: entry-point (mock), dir usuario, dir proyecto; nombre
     duplicado = primero gana + aviso; plugin roto (sin register / import
     error / register que lanza) = aviso + corrida sigue.
   - Plugin interno: tests B5 existentes verdes SIN cambios (migración real).
   - Prefijo byte-idéntico con y sin plugins (FakeProvider, donor C6).
   - --no-plugins mata todo; --plugins-dir añade.
6. Auditoría completa (§6) + baseline real (§7) + commit + push + presentar
   al fundador evidencia de comportamiento → OK verbal → merge main → CI verde.
7. CLASE_9 al cierre (v2: tutorial + teoría con donors + continuidad con
   Clase 8 + gancho). Tema natural: everything-plugin (D2) — hooks como
   costuras, el consumidor concreto como regla anti-speculative, y la
   migración del ledger a plugin interno como prueba real del mecanismo.

## 6. CÓMO VERIFICAR SIN GASTAR (audit local = CI exacto)
```
uv run pytest tests/ -q          # ≥308 verdes
uv run ruff check src tests
uv run ruff format --check .
uv run mypy --strict src
```
Smokes gratis: `tlamati sessions --session-db /tmp/x.db`; `tlamati audit`;
plugin smoke: proyecto falso en /tmp con .tlamati/plugins/malo.py (sin
register) + OPENROUTER_API_KEY=*** el log "[plugins] ..." sale a
stderr ANTES del 401 del proveedor (técnica de la Clase 7).

## 7. BASELINE REAL (tras la fase, gasta centavos)
```
uv tool install --from . tlamati --reinstall
tlamati-eval --out evals/d2_check.jsonl
```
Esperado: `[eval] 5/5 OK` y cache_read ~90%+ (la primera tarea puede dar
~74% en frío — normal). Ratchet: si baja de 5/5 por código propio (no por
429/504), NO mergear — revisar. OJO: los evals corren ENJAULADOS con bwrap
(B3) — verificar que el descubrimiento de plugins del proyecto no intenta
escribir nada dentro de la jaula.

## 8. PITFALLS ACUMULADOS (no repetir — lista completa en la skill)
- AUDITORÍA LOCAL = pytest + ruff check + ruff FORMAT --check + mypy
  --strict. Olvidar format-check = CI rojo y correo "run failed" al
  fundador. Verificar `gh run list` tras cada push (CI solo corre en main
  y pull_request — el push de rama NO lo dispara; se verifica tras merge).
- `git branch -d` / merge / push encadenados con && disparan bloqueo del
  parser aunque el usuario aprobó (NO es veto, protocolo #6): comandos
  simples, uno por llamada; heredocs → python3 -c o write_file (excepción
  que sí funciona: git commit -F - con heredoc, sin &&). NUEVO (sesión 12):
  `curl ... | python3 -c` también dispara bloqueo (pipe a intérprete) —
  descargar y parsear por separado, o leer con read_file.
- Tools nuevas re-obtenibles DEBEN entrar a DEFAULT_COMPACTABLE_TOOLS
  (context/compaction.py). Tools con side-effect NO entran. En D2 NO hay
  tools nuevas (los hooks no son tools del modelo).
- Orden de tools.specs() estable = append-only (cache sagrada). Bloques de
  system prompt nuevos = estáticos; estado dinámico viaja en el primer
  mensaje (decisión #3 de C5, probada: cache_read 94-95%).
- run_loop exige budget= keyword (TypeError si falta).
- mypy --strict: Protocolos con atributos → read-only properties; imports
  del mismo módulo con alias → forma paréntesis única (ruff I001); líneas
  ≤100 chars (ruff E501) — correr ruff format ANTES del commit.
- OpenRouter 429/504: el campo `error` del JSONL es la fuente de verdad.
- uv wheel cache obsoleto tras installs raros → `uv cache clean tlamati`.
- Policy nunca relaja: los plugins (before_tool) solo pueden ENDURECER.
- Background processes mueren con la sesión — corridas largas: comando
  idempotente-reiniciable con output a path fijo.

## 9. AL CIERRE DE LA PRÓXIMA SESIÓN
CLASE_9 (edu/DESARROLLO_TLAMATI_CLASE_9.md) formato v2. Temas disponibles:
everything-plugin (D2 — hooks como costuras + migración del ledger a plugin
interno), MCP como territorio no-confiable (D3, si toca), OpenCrawl y la
frontera harness-vs-servidor (research/06).

-- Hermes, 17-nov-2026 sesión 12. Main = d67fb60 (A+B+C + D1 COMPLETAS, CI
-- verde, 308 tests, baseline 5/5 cache 94-95%). Falta D2 (plugins) y D3
-- (MCP) de la FASE D, luego Fase E (TUI/evals ampliados/docs/publish v0.1). --
