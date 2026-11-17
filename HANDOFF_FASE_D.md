# HANDOFF FASE D — subagentes → plugins → MCP
# Generado por Hermes, 17-nov-2026 (sesión 11). Punto de entrada para una sesión
# con CERO contexto: leer este archivo completo, cargar la skill
# `tlamati-harness-project` (skill_view), y seguir §5 en orden.
# Protocolo VIGENTE: un paso → entrega → OK verbal del fundador → Hermes
# auto-audita (pytest + ruff check + ruff FORMAT --check + mypy --strict +
# baseline REAL) y fusiona. Fundador NO-técnico: NUNCA pedirle revisar código;
# presentar evidencia de COMPORTAMIENTO en cristiano. Clase del día al cierre
# (edu/PROMPT_CLASE_DIARIA.md v2; la próxima es CLASE_8 — CLASE_7 ya escrita).

## 1. ESTADO ACTUAL (17-nov sesión 11, verified)
- main = cdf8e4a: FASES A + B + C COMPLETAS (C1-C6). CI verde (run 44128533570,
  47s). 292 tests verdes, ruff+format+mypy strict limpios.
- C6 FUSIONADO con OK verbal del fundador (merge --no-ff c6-routing, sin
  conflictos). Baseline REAL vigente: evals/c6_check.jsonl — 5/5 OK con
  qwen/qwen3-coder vía OpenRouter, cache_read 94-95% (74% solo en la primera
  tarea fría). ESTE es el ratchet de Osmani: ningún merge baja de 5/5.
- CLASE_7 escrita (edu/DESARROLLO_TLAMATI_CLASE_7.md): routing.md + 3 capas +
  fnmatch + fail-soft + error del día (test con supuesto malo, no código malo).
- Ramas viejas borrables (low prio): c6-routing local+remota ya fusionada;
  b5-ledger, c1-session, c5-plan-mode locales; origin/b2-tools, origin/fase-b,
  origin/c5-plan-mode remotas.
- Untracked intencional: evals/b5_check2.jsonl + b5_check3.jsonl (evidencia del
  rate-limit OpenRouter del 16-nov; NO borrar sin leer).
- QUÉ HAY CONSTRUIDO (src/tlamati/): core/loop.py + messages; providers/
  openai_compat (+anthropic_messages); tools/ (registry con escalera de
  permisos deny>ask>auto, files, search, terminal, builtin); context/ (budget,
  compaction M1+M2, instructions C4, ROUTING C6); sandbox/bwrap; policy/
  (config B4 + ledger B5); session/store (C1); memory/ (store+dream C2, skills
  C3 con catalog_text(only=) para filtro por workspace); plan/ (C5, fail-closed);
  evals/runner + 5 fixtures; cli.py con subcomandos sessions/audit y flags
  --plan-mode/--dream/--skills-dir/--workspace/--no-routing/etc.
- Pregunta abierta heredada de Clase 6: ¿save_plan fuera de plan-mode como
  bitácora? → diferida a Fase E.

## 2. QUÉ LEER ANTES DE CODIFICAR (orden, ~20 min)
a) Este handoff completo.
b) skill_view(name='tlamati-harness-project') — protocolo, decisiones zanjadas
   (NO re-litigar), pitfalls acumulados, política de copiado (donors).
c) GUIA_IMPLEMENTACION.md §"FASE D" (D1-D3) — la spec.
d) PRD_TLAMATI.md §6 MoSCoW: F9 subagentes [SHOULD] · F11 plugins [SHOULD] ·
   F8 MCP [SHOULD]. No-goals: NO flota multi-agente (D1 es UN hijo a la vez,
   profundidad 1 — no construir orquestación).
e) Para D1: patrón delegate_task de hermes (DONOR SANCIONADO MIT — leer
   ~/.hermes o la doc de delegation; semántica: padre crea presupuesto, hijo
   hereda tope, padre recibe SOLO el resumen final) + Raschka #6 (límites:
   max_turns + max_cost duros). Semilla natural del toolset read-only del hijo:
   PLAN_READONLY_TOOLS de src/tlamati/plan/mode.py.
f) Para D2: research/02 (Reasonix everything-plugin [DEAD 12-nov,
   reference-only] + hook registry de gemini-cli: before_tool/after_tool/
   on_error). REGLA anti-speculative (hermes): SOLO hooks con consumidor
   concreto. Consumidor #1 YA EXISTE: _ledger_wrapper en cli.py es hoy un
   wrapper hardcoded → migrarlo a plugin interno es la prueba real.
g) Para D3: MCP spec stdio (initialize → tools/list → tools/call). Servidor de
   prueba: FakeMCP escrito para los tests (subprocess echo); REA ya soporta
   modo MCP server (npx rea-agents) para un smoke real opcional.

## 3. SPEC DESTILADA
### D1 — subagent/spawn.py (F9, ~150-250 LOC)
- Tool `delegate_task`: args = goal/context/max_turns. Permission ASK por
  default (un subagente suelto es costo suelto).
- Corre run_loop RECURSIVO con: Registry reducido READ-ONLY (semilla:
  PLAN_READONLY_TOOLS), Budget propio hijo (padre crea, hijo hereda tope),
  mismo provider. SIN sandbox-net nuevo.
- Profundidad máxima = 1: el hijo NO registra delegate_task (fail fast al
  construir el Registry del hijo). Nietos = error honesto, no excepción muda.
- El padre recibe SOLO LoopResult.final_text (invariante de contexto: nunca el
  transcript completo).
- AUDITORÍA: eventos del hijo al MISMO ledger con prefijo de sesión hija o
  columna parent — decidir al implementar (verificar política B5; nada de
  ejecuciones invisibles).
- Tool NO entra a DEFAULT_COMPACTABLE_TOOLS (tiene side-effect: gasta dinero).
- PREGUNTA ABIERTA (Clase 7, plantear al fundador con opciones si está
  presente): ¿el padre puede dar escritura al hijo? Posición recomendada v1:
  NO — la escalera solo ENDURECE hacia abajo (política del proyecto); escritura
  en subagente podría llegar en v1.1 con permission explícita.
### D2 — plugins/ (F11, ~150-250 LOC)
- Descubrimiento: entry-point `tlamati.plugins` (importlib.metadata) +
  ~/.config/tlamati/plugins/*.py + .tlamati/plugins/*.py de proyecto.
- Plugin = módulo Python con función `register(hooks)`; HookRegistry con
  before_tool/after_tool/on_error (SOLO esos 3 — cada uno con consumidor
  concreto; no inventar más "por si acaso").
- Carga fail-soft: plugin roto = aviso honesto + seguir sin él, NUNCA romper
  la corrida.
- Consumidor concreto #1: migrar _ledger_wrapper (cli.py) a plugin INTERNO —
  prueba real del mecanismo sin cambiar comportamiento observable.
- Seguridad: plugins corren SIN sandbox (código del dueño de la máquina —
  mismo modelo que hermes). Documentar en SECURITY.md (tarea E4 si no existe
  aún, crear stub honesto).
### D3 — MCP client stdio mínimo (F8, ~150-250 LOC)
- Protocolo: initialize → tools/list → tools/call sobre stdio (subprocess).
- Config en tlamati.yaml: `mcp_servers: {nombre: {command, args, env}}`.
- Cada tool MCP → Tool del registry con permission=ASK default Y
  produces_untrusted=True (NO confiar en MCP: la trifecta B4 se activa sola en
  el egress subsiguiente — no relajar NUNCA).
- Timeouts + degradación honesta: server que no arranca = tools ausentes +
  aviso, nunca corrida rota.
- Tests con FakeMCP (subprocess de juguete que habla JSON-RPC por stdio).
### ORDEN DE TRABAJO
D1 → D2 → D3, UNO por unidad de sesión, cada uno con: rama nueva saliendo de
main (`git checkout -b d1-subagent` etc.), tests + lint trio + baseline real,
commit, push, OK verbal, merge a main, CI verde verificado (`gh run list`).
NO encadenar dos fases sin entrega intermedia (corrección del fundador 14-nov:
nunca pasos "de corrido"). Fundador usa ventanas yolo cronometradas: al corte,
TERMINAR la unidad en curso + resumen; preferible no arrancar lo siguiente si
no cabe en el tiempo.

## 4. ¿GASTA?
- Construir D1/D2/D3 + tests + lint: $0 (FakeProvider/FakeMCP, cero red).
- Baseline real tras cada fase: SÍ, centavos vía OpenRouter (qwen/qwen3-coder).
  Hoy 17-nov funcionó a la primera (c6_check 5/5). Si falla: leer el campo
  `error` del JSONL — 429/504 es upstream, NUNCA asumir fallo propio;
  reintentar tras 15-60s. Alternativa: BYOK DeepInfra del fundador.

## 5. SIGUIENTE ACCIÓN EXACTA (sesión nueva)
1. `cd ~/code/tlamati && git checkout main && git pull` (verificar main=cdf8e4a
   o posterior, CI verde con `gh run list --branch main --limit 1`).
2. `uv run pytest tests/ -q` → confirmar 292 verdes ANTES de tocar nada.
3. Leer §2 (skill + GUIA FASE D + donor delegate de hermes).
4. Resolver decisiones abiertas de D1: si el fundador está presente, preguntar
   con opciones (clarify, máx 4); si es ventana yolo, elegir recomendadas y
   documentar en el commit. (a) ¿escritura en subagente? recomendada: NO v1.
   (b) ¿auditoría del hijo: prefijo de sesión hija o columna parent? elegir la
   que NO requiera migración del schema B5 existente (preferir prefijo).
   (c) nombre de la tool: `delegate_task` (alineado con hermes) vs
   `spawn_subagent`.
5. `git checkout -b d1-subagent` → implementar subagent/spawn.py + tool +
   CLI/config + tests (unidad: toolset read-only del hijo, profundidad 1 fail
   fast, presupuesto heredado se agota y retorna honesto, resumen-no-transcript;
   integración FakeProvider: padre delega → hijo corre → padre recibe solo
   final_text; ledger registra eventos del hijo).
6. Auditoría completa (§6) + baseline real (§7) + commit + push + presentar al
   fundador evidencia de comportamiento → OK verbal → merge main → CI verde.
7. CLASE_8 al cierre (v2: tutorial + teoría con donors + continuidad con
   Clase 7 + gancho). Tema natural: delegación con límites (D1) y lo que se
   haga en la sesión.

## 6. CÓMO VERIFICAR SIN GASTAR (audit local = CI exacto)
```
uv run pytest tests/ -q          # ≥292 verdes
uv run ruff check src tests
uv run ruff format --check .
uv run mypy --strict src
```
Smokes gratis: `tlamati sessions --session-db /tmp/x.db`; `tlamati audit`;
routing smoke: copiar /tmp/c6_smoke de la Clase 7 (§replicable) con key dummy —
el log "[routing] workspace=X v:hash" sale ANTES del 401 del proveedor.

## 7. BASELINE REAL (tras cada fase, gasta centavos)
```
uv tool install --from . tlamati --reinstall
tlamati-eval --out evals/<fase>_check.jsonl
```
Esperado: `[eval] 5/5 OK` y cache_read ~90%+ (la primera tarea puede dar ~74%
en frío — normal, la caché se calienta). Ratchet: si baja de 5/5 por código
propio (no por 429/504), NO mergear — revisar.

## 8. PITFALLS ACUMULADOS (no repetir — lista completa en la skill)
- AUDITORÍA LOCAL = pytest + ruff check + ruff FORMAT --check + mypy --strict.
  Olvidar format-check = CI rojo y correo "run failed" al fundador. Verificar
  `gh run list` tras cada push.
- `git branch -d` / merge / push encadenados con && disparan bloqueo del parser
  aunque el usuario aprobó (NO es veto, protocolo #6): comandos simples, uno
  por llamada; heredocs → python3 -c o write_file (excepción que sí funcionó
  hoy: git commit -F - con heredoc, sin &&).
- Tools nuevas re-obtenibles DEBEN entrar a DEFAULT_COMPACTABLE_TOOLS
  (context/compaction.py). Tools con side-effect (save_plan, delegate_task,
  cualquier tool MCP que ejecute) NO entran.
- Orden de tools.specs() estable = append-only (cache sagrada). Tools nuevas al
  FINAL del orden. Bloques de system prompt nuevos = estáticos; estado dinámico
  viaja en el primer mensaje (decisión #3 de C5, probada: cache_read 94%).
- OpenRouter 429/504: el campo `error` del JSONL es la fuente de verdad.
- uv wheel cache obsoleto tras installs raros → `uv cache clean tlamati`.
- Policy nunca relaja: cualquier capa nueva (subagentes, plugins, MCP) solo
  puede ENDURECER la escalera deny>ask>auto.
- run_loop exige budget= keyword (TypeError si falta — lo vimos hoy en tests).
- Background processes mueren con la sesión — corridas largas: comando
  idempotente-reiniciable con output a path fijo.

## 9. AL CIERRE DE LA PRÓXIMA SESIÓN
CLASE_8 (edu/DESARROLLO_TLAMATI_CLASE_8.md) formato v2. Temas disponibles:
delegación con límites (D1 — patrón padre/hijo, profundidad 1, presupuesto
heredado), everything-plugin (D2), MCP como territorio no-confiable (D3), los
merges reales de la serie.

-- Hermes, 17-nov-2026 sesión 11. Main = cdf8e4a (A+B+C COMPLETAS, CI verde,
-- 292 tests, baseline 5/5 cache 94-95%). Falta FASE D (D1-D3) y Fase E
-- (TUI/evals ampliados/docs/publish v0.1). --
