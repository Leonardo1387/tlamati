# HANDOFF FASE C6 + FASE D — workspaces/routing → subagentes/plugins/MCP
# Generado por Hermes, 17-nov-2026 (sesión 9 continuación). Punto de entrada para
# una sesión con CERO contexto: leer este archivo completo, cargar la skill
# `tlamati-harness-project` (skill_view), y seguir §5 en orden.
# Protocolo VIGENTE: un paso → entrega → OK verbal del fundador → Hermes
# auto-audita (pytest + ruff check + ruff FORMAT --check + mypy --strict +
# baseline REAL) y fusiona. Fundador NO-técnico: NUNCA pedirle revisar código;
# presentar evidencia de COMPORTAMIENTO en cristiano. Clase del día al cierre
# (edu/PROMPT_CLASE_DIARIA.md v2 = tutorial-libro con teoría; la próxima es
# CLASE_7).

## 1. OBJETIVO GENERAL
Tlamati = agent harness OSS local-first (~/code/tlamati, Apache-2.0, repo privado
leonardoGH/tlamati, gh CLI auth OK, CI GitHub Actions verde). Diferenciadores
(PRD): prefijo cacheable con overhead VISIBLE (<8k vs 33k de Claude Code),
seguridad trifecta (sandbox bwrap + permisos + auditoría append-only), loop
simple (~340 LOC), memoria durable (el +17pt de Letta). Métrica de éxito:
overhead del prefijo bajo y medible en los evals (campo cache_read del JSONL).

## 2. ESTADO ACTUAL (17-nov, verified)
- main = ecb0fdf: FASES A + B + C (C1-C5) COMPLETAS Y FUSIONADAS. CI verde
  (run 44123502059). 266 tests verdes, ruff+format+mypy strict limpios.
- Baseline REAL vigente: evals/c5_check.jsonl — 5/5 OK con qwen/qwen3-coder
  vía OpenRouter, cache_read ≈ 94% del input. ESTE es el ratchet de Osmani:
  ningún merge puede bajar de 5/5 ni romper la cache.
- Ramas ya fusionadas (borrables cuando el parser lo permita, low prio):
  b5-ledger, c1-session, c5-plan-mode locales; origin/b2-tools, origin/fase-b,
  origin/c5-plan-mode remotas.
- Untracked intencional: evals/b5_check2.jsonl + b5_check3.jsonl (evidencia del
  rate-limit OpenRouter del 16-nov; NO borrar sin leer).
- Qué hay construido (todo en src/tlamati/): core/loop.py + messages; providers/
  openai_compat (+anthropic_messages); tools/ (registry con escalera de permisos,
  files, search, terminal, builtin); context/ (budget, compaction con M1+M2,
  instructions AGENTS.md/CLAUDE.md); sandbox/bwrap; policy/ (config B4 + ledger
  B5); session/store (C1); memory/ (store+dream C2, skills C3); plan/ (C5:
  mode+tools, fail-closed); evals/runner + fixtures (5 tareas); cli.py con
  subcomandos sessions/audit y flags --plan-mode/--dream/--skills-dir/etc.
- CLASE_6 escrita (edu/DESARROLLO_TLAMATI_CLASE_6.md, plan-mode). CLASE_7
  pendiente: tema natural = los merges (resolución de conflictos real B5+C1-C5)
  y lo que se haga en esta sesión (C6/D).

## 3. QUÉ LEER ANTES DE CODIFICAR (orden, ~20 min)
a) Este handoff completo.
b) skill_view(name='tlamati-harness-project') — protocolo de trabajo, decisiones
   zanjadas (NO re-litigar), pitfalls acumulados, política de copiado (donors).
c) research/03_AGENTES_COMO_CARPETAS_Y_ESTADO_REA.md §1 — la fuente de C6:
   "agents as folders", routing de 3 capas (MAPA/HABITACIONES/MESAS), lo que se
   copia y lo que se DESCARTA (está destilado ahí).
d) GUIA_IMPLEMENTACION.md §"FASE C+" (C6) y §"FASE D" (D1-D3) — la spec.
e) PRD_TLAMATI.md §6 MoSCoW: F6b workspaces [SHOULD v1] · F9 subagentes [SHOULD]
   · F11 plugins [SHOULD] · F8 MCP [SHOULD]. F6b MUST en v1.1.
f) src/tlamati/context/instructions.py — el loader C4 (AGENTS.md merge con
   frontera .git y versionado sha256) que C6 EXTIENDE (mismo patrón).
g) Para D1: el patrón delegate_task de hermes (donor sancionado MIT) + patrón
   Raschka #6 (límites). Para D2: research/02 (Reasonix everything-plugin [DEAD,
   reference-only] + hook registry de gemini). Para D3: MCP spec stdio.

## 4. SPEC DESTILADA
### C6 — context/routing.py (~100-150 LOC, cierra la Fase C)
Workspaces + routing.md (donor research/03, acción concreta §1):
- ARCHIVO: `.tlamati/routing.md` en la raíz del proyecto (markdown declarativo,
  SIN base de datos ni magia RAG). Tabla: tarea/patrón → qué archivos cargar,
  cuáles omitir, qué skills cablear just-in-time.
- 3 CAPAS = FRONTERAS DE CACHÉ (lección #4 de research/03): capa 1 MAPA
  (routing.md, estable → va en prefijo cacheable versionado por hash como C4);
  capa 2 HABITACIONES (contexto por workspace, semi-estable); capa 3 MESAS
  (archivos reales, variables — NUNCA en prefijo, se leen con read_file).
- LOADER: parsear la tabla de routing.md, resolver el workspace activo (por cwd,
  por flag, o por match de la tarea), inyectar en el prefijo SOLO el mapa +
  contexto del workspace activo. Convención de nombre como índice (lección #2):
  artefactos por slug predecible, no embeddings.
- CABLEAR CON LO EXISTENTE: load_instructions (C4) ya hace merge+hash; el
  routing va DESPUÉS de instructions en el prefijo (orden estable, append);
  skills del workspace (capa 2) pueden filtrar el catálogo de SkillLibrary (C3)
  — OJO: filtrar el catálogo CAMBIA el prefijo entre corridas → hacerlo solo por
  workspace (estable por corrida), nunca por turno.
- CLI: --workspace NAME (forzar), --no-routing. Log "[routing] workspace=X v:hash".
- DECISIONES ABIERTAS C6 (proponer al fundador con opciones; si es ventana yolo,
  elegir la recomendada y documentar en el commit):
  1. Formato de la tabla en routing.md: markdown table parseable (recomendado,
     determinista) vs secciones con headers libres (más humano, parser frágil).
  2. ¿routing.md también a nivel usuario (~/.config/tlamati/routing.md) o solo
     proyecto? (recomendado v1: solo proyecto, KISS).
  3. ¿El match tarea→workspace lo hace el harness (fnmatch/globs, determinista,
     recomendado) o el modelo (tool `switch_workspace`)? v1 determinista; la
     tool puede llegar en D2 con plugins.

### D1 — subagent/spawn.py (subagentes, F9)
Task aislada con toolset reducido READ-ONLY default, max_turns + max_cost,
resultado = resumen (donor: patrón delegate de hermes; límites = Raschka #6).
- Herramienta `delegate_task` (o `spawn_subagent`): args = goal/context/max_turns.
- Corre run_loop RECURSIVO con un Registry reducido (read-only por defecto —
  reutilizar PLAN_READONLY_TOOLS de plan/mode.py como semilla natural), Budget
  propio hijo (donor hermes iteration_budget: padre crea, hijo hereda tope),
  mismo provider. SIN sandbox-net nuevo. El padre recibe SOLO el resumen final
  (LoopResult.final_text), nunca el transcript completo (invariante de contexto).
- Profundidad máxima = 1 (hijo no puede spawnear nietos — fail fast al registrar
  la tool en el hijo).
- AUDITORÍA: los eventos del hijo van al MISMO ledger con prefijo de sesión hija
  (o columna parent) — verificar política al implementar; nada de ejecuciones
  invisibles.
- Permission de la tool: ask por default (consume presupuesto; un subagente
  suelto es costo suelto).

### D2 — plugins/ (everything-plugin, F11)
Entry-point `tlamati.plugins` (importlib.metadata) + descubrimiento
`~/.config/tlamati/plugins/*.py` y `.tlamati/plugins/*.py` de proyecto.
- Hook registry (donor gemini): before_tool / after_tool / on_error — SOLO hooks
  con consumidor concreto (regla anti-speculative de hermes: no inventar hooks
  "por si acaso"). Consumidor concreto #1 ya existe: el ledger B5 es hoy un
  wrapper hardcoded (_ledger_wrapper en cli.py) → migrarlo a plugin interno es
  la prueba real del mecanismo.
- Plugin = módulo Python con función `register(hooks)`; carga fail-soft (plugin
  roto = aviso honesto + seguir sin él, nunca romper la corrida).
- Seguridad: plugins corren SIN sandbox (son código del usuario dueño de la
  máquina — mismo modelo que hermes). Documentarlo en SECURITY.md (E4).

### D3 — MCP client stdio mínimo (F8)
initialize → tools/list → tools/call sobre stdio (subprocess).
- Mapear cada tool MCP a Tool del registry con permission=ASK por default
  (NO confiar en MCP: treat as untrusted → produces_untrusted=True activa la
  trifecta B4 automáticamente en egress subsiguiente).
- Config en tlamati.yaml: `mcp_servers: {nombre: {command, args, env}}`.
- Servidor de prueba local: REA ya soporta modo MCP server (npx rea-agents);
  también sirve un server echo de juguete escrito para los tests (FakeMCP).
- Timeouts + degradación honesta: server que no arranca = tools ausentes + aviso,
  nunca corrida rota.

### ORDEN DE TRABAJO
C6 → D1 → D2 → D3, UNO por unidad de sesión, cada uno con: rama nueva saliendo
de main (`git checkout -b c6-routing` etc.), tests + lint trio + baseline real,
commit, push, OK verbal, merge a main, CI verde verificado (`gh run list`).
NO encadenar dos fases sin entrega intermedia (protocolo del proyecto, corrección
del fundador 14-nov: nunca hacer pasos "de corrido").

## 5. SIGUIENTE ACCIÓN EXACTA (sesión nueva)
1. `cd ~/code/tlamati && git checkout main && git pull` (verificar main=ecb0fdf
   o posterior, CI verde).
2. `uv run pytest tests/ -q` → confirmar 266 verdes ANTES de tocar nada (estado
   base sano).
3. Leer §3 (skill + research/03 + instructions.py).
4. Resolver las 3 decisiones abiertas de C6: si el fundador está presente,
   preguntarle con opciones (clarify, máximo 4); si es ventana yolo, elegir las
   recomendadas y documentar en el commit.
5. `git checkout -b c6-routing` → implementar context/routing.py + CLI + tests
   (unidad: parser de tabla, resolución de workspace, versión hash estable,
   fail-soft con routing.md roto; integración con FakeProvider: prefijo contiene
   el mapa del workspace activo y NO el de otros).
6. Auditoría completa (§7) + baseline real (§8) + commit + push + presentar al
   fundador evidencia de comportamiento → OK verbal → merge main → CI verde.
7. CLASE_7 al cierre (v2: tutorial + LA TEORÍA DETRÁS con donors + continuidad
   con Clase 6 + gancho).

## 6. ¿GASTA?
- Construir C6/D1/D2/D3 + tests + lint: $0 (FakeProvider, cero red).
- Baseline real tras cada fase: SÍ, centavos vía OpenRouter (qwen/qwen3-coder).
  El 16-nov estuvo saturado TODO el día (504/429); la noche del 16 respiró
  (c5_check 5/5). Si falla: leer el campo `error` del JSONL — 429/504 es
  upstream, NUNCA asumir fallo propio; reintentar tras 15-60s u otro día.
  Alternativa: BYOK DeepInfra del fundador (ya se le explicó cómo).

## 7. CÓMO VERIFICAR SIN GASTAR (audit local = CI exacto)
```
uv run pytest tests/ -q          # ≥266 verdes
uv run ruff check src tests
uv run ruff format --check .
uv run mypy --strict src
```
Smokes gratis: `tlamati sessions --session-db /tmp/x.db`; `tlamati audit --session ...`;
migración skills 1-flag: `uv run python -c "from pathlib import Path; from tlamati.memory.skills import SkillLibrary; print(len(SkillLibrary([Path.home()/'.hermes'/'skills']).catalog()))"` → 47.

## 8. BASELINE REAL (tras cada fase, gasta centavos)
```
uv tool install --from . tlamati --reinstall
tlamati-eval --out evals/<fase>_check.jsonl
```
Esperado: `[eval] 5/5 OK` y cache_read alto (~90%+ del input). Ratchet: si baja
de 5/5 por código propio (no por 429/504), NO mergear — revisar.

## 9. PITFALLS ACUMULADOS (no repetir — lista completa en la skill)
- AUDITORÍA LOCAL = pytest + ruff check + ruff FORMAT --check + mypy --strict.
  Olvidar format-check = CI rojo y correo "run failed" al fundador (ruido que
  destruye confianza en la alerta). Verificar `gh run list` tras cada push.
- `git branch -d` / merge / push encadenados con && disparan bloqueo del parser
  aunque el usuario aprobó (NO es veto, protocolo #6 de la skill): comandos
  simples, uno por llamada; heredocs → python3 -c o write_file.
- Tools nuevas re-obtenibles DEBEN entrar a DEFAULT_COMPACTABLE_TOOLS
  (context/compaction.py) o su output se limpia sin reporte (pitfall qwen
  #4239). Tools con side-effect (save_plan, delegate_task) NO entran.
- Orden de tools.specs() estable = append-only (cache sagrada). Bloques de
  system prompt nuevos = estáticos; el estado dinámico viaja en el primer
  mensaje (decisión #3 de C5, probada: cache_read 94%).
- OpenRouter 429/504: el campo `error` del JSONL es la fuente de verdad.
- uv wheel cache obsoleto tras installs raros → `uv cache clean tlamati`.
- Policy nunca relaja: cualquier capa nueva (routing, subagentes) solo puede
  ENDURECER la escalera deny>ask>auto.
- El fundador usa ventanas yolo cronometradas: al corte, TERMINAR la unidad en
  curso (no dejar a medias) + resumen de qué se hizo y dónde se va. Preferible
  no arrancar el siguiente paso si no cabe en el tiempo.
- Background processes (terminal background=true) mueren con la sesión — para
  corridas largas, comando idempotente-reiniciable con output a path fijo.

## 10. AL CIERRE DE LA PRÓXIMA SESIÓN
CLASE_7 (edu/DESARROLLO_TLAMATI_CLASE_7.md) formato v2: tutorial-libro con
pasos + herramientas + (c2) LA TEORÍA DETRÁS (patrón reusable + donor citado) +
continuidad con Clase 6 + gancho. Temas disponibles: los 3 merges reales y la
resolución de conflictos (ya ocurridos, material de esta sesión), routing
declarativo como presupuesto de contexto (C6), subagentes con límites (D1),
everything-plugin (D2), MCP como territorio no-confiable (D3).

-- Hermes, 17-nov-2026. Main = ecb0fdf (A+B+C completas, CI verde, 266 tests,
-- baseline 5/5). Falta C6 para cerrar la letra C; luego Fase D (D1-D3) y
-- Fase E (TUI/evals ampliados/docs/publish v0.1). --
