# HANDOFF FASE C5 — PLAN-MODE (para sesión desde cero)
# Generado por Hermes, 16-nov-2026, sesión 8. Reemplaza HANDOFF_FASE_B5.md como
# punto de entrada de TRABAJO NUEVO (B5 sigue pendiente de baseline+merge, ver §7).
# Protocolo SIGUE VIGENTE: un paso → entrega → OK verbal del fundador → Hermes
# auto-audita (tests+ruff+FORMAT+mypy+baseline REAL) y fusiona; clase del día
# al cierre (edu/PROMPT_CLASE_DIARIA.md v2 = tutorial con teoría).

## 1. OBJETIVO GENERAL
Tlamati = agent harness OSS local-first (~/code/tlamati, Apache-2.0, repo privado
leonardoGH/tlamati, gh auth OK). Diferenciadores (PRD): prefijo cacheable con
overhead visible (<8k vs 33k de Claude Code), seguridad trifecta (sandbox bwrap +
permisos + auditoría), loop simple (~300 LOC), memoria durable (el +17pt de Letta).
Métrica de éxito: overhead del prefijo bajo y VISIBLE. Fases A y B completas
(B5 en rama por rate-limit). Fase C original (C1-C4) COMPLETA en rama c1-session.
Ahora: Fase C+ — C5 plan-mode (este handoff), luego C6 workspaces/routing.

## 2. CONTEXTO / DE DÓNDE VENIMOS
Sesión 8 (16-nov): el fundador cachó que la Fase C de la guía NO había absorbido
la investigación → se destiló (commit 47559f1) y se implementaron C1 (session
store SQLite), C2 (memoria MEMORY.md/USER.md con techos duros + AUTO-DREAM),
C3 (skills formato hermes/CC, migración 1-flag probada REAL con 47 skills) y
C4 (loader AGENTS.md+CLAUDE.md). Todo en rama c1-session, 5 commits, 224 tests
verdes. OpenRouter saturado TODO el día (504/429 DeepInfra/Venice): baselines
reales imposibles el 16-nov → merges B5 y C1-C4 pendientes de eso + OK verbal.

## 3. LO QUE HAY QUE LEER ANTES DE CODIFICAR (orden, ~15 min)
a) Este handoff completo.
b) GUIA_IMPLEMENTACION.md §"FASE C+" — la spec destilada de C5/C6 (commit 47559f1).
c) research/02_ESTUDIO_HARNESSES.md — hallazgo #5: "Plan mode / ask-user /
   task-complete como primitivas: el arnés bueno separa explorar→aprobar→
   ejecutar→cerrar" (qwen enter/exitPlanMode + askUserQuestion; gemini
   enter/exit-plan-mode + ask-user + complete-task; reasonix plancontract).
d) vendor/qwen-code/docs/design/explicit-plan-exit-approval.md — EL doc de
   diseño más valioso para C5 (leer completo, 33 líneas). Destilado abajo (§5).
e) vendor/gemini-cli/docs/tools/planning.md — semántica de las 2 tools
   (enter con reason opcional + confirmación; exit con plan_path obligatorio
   DENTRO de un dir de planes, aprobación formal, rechazo = feedback al modelo).
f) src/tlamati/policy/config.py — el mecanismo de permisos B4 que C5 reutiliza
   (escalera deny>ask>auto NUNCA relaja; overrides por tool).

## 4. QUÉ ES C5 (spec de la guía destilada)
Plan-mode: tools `enter_plan_mode`/`exit_plan_mode` — explorar→aprobar→ejecutar.
En plan-mode las tools de escritura/terminal pasan a DENY por policy (B4 ya da
el mecanismo: 0 código nuevo de permisos). `ask_user` + `complete_task` como
primitivas gemini/qwen. PRD F1 lo declara MUST — estaba sin fase hasta el 16-nov.

## 5. DISEÑO RECOMENDADO (destilado de los donors — decidir y confirmar con
   evidencia de comportamiento al fundador; esto NO es código todavía)
ESTADO: un `plan_mode: bool` en el estado de corrida (CLI flag `--plan-mode`
para arrancar en plan + tools para conmutar). NO mutar PolicyConfig global:
mejor una capa de resolución dinámica (Policy.resolve ya es escalera; añadir
"si plan_mode y tool no es read-only → deny" como regla transversal, o
overrides runtime). VERIFICAR cómo encajar sin romper los tests de B4.
TOOLS READ-ONLY EN PLAN-MODE (whitelist v1): read_file, search_files,
skill_view, skill_list, search_memory. TODO lo demás (write_file, edit,
terminal, memory) → DENY con error honesto que diga "estás en plan-mode,
sal con exit_plan_mode aprobado".
LECCIONES DE QWEN (explicit-plan-exit-approval.md) — adoptar las 4 de oro:
1. exit_plan_mode REQUIERE interacción real del usuario: reglas de auto-
   aprobación / YOLO / allow-lists NO pueden aprobar la salida del plan
   (requiresUserInteraction intrínseco). Headless v1: --approve-tool NO
   cuenta para exit_plan_mode; sin host interactivo → fail closed (el plan
   sigue activo, error honesto).
2. FAIL CLOSED en todo estado rancio: salida sin aprobación, aprobación
   vieja (revisión de modo cambió), doble salida contra la misma revisión →
   plan-mode SIGUE ACTIVO. Nunca relajar por error.
3. La aprobación registra UNA de N decisiones explícitas (restaurar modo
   previo / auto-edit / default / cancelar) y NO cambia el modo hasta que la
   ejecución valida todo (modo actual, señal activa, revisión coincide).
4. enter_plan_mode guarda el "pre-plan mode" para poder restaurarlo al salir.
GEMINI (planning.md) — adoptar:
5. exit_plan_mode recibe `plan_path`: el plan es un ARCHIVO markdown real en
   un dir controlado (tlamati: .tlamati/plans/ del proyecto; path-escape
   guard como en skill_view C3). El modelo debe escribir el plan ANTES de
   pedir aprobación — pero OJO: en plan-mode write_file está en deny →
   el plan se escribe por una vía especial (tool `save_plan` read-only-safe
   que SOLO escribe dentro de .tlamati/plans/, o el plan viaja como argumento
   del exit y el harness lo persiste). DECISIÓN ABIERTA #1 — proponer al
   fundador con trade-offs.
6. Rechazo del plan = el usuario da feedback, el modelo sigue en plan-mode y
   refina (nunca ejecutar tras rechazo).
7. enter NO disponible en modo yolo (gemini) — en tlamati: --plan-mode y
   --approve-tool '*' son mutuamente exclusivos (fail fast al parsear).
COMPLETE_TASK/ASK_USER (gemini+qwen): evaluar si entran en C5 o se difieren
al TUI (Fase E). Sin TUI, ask_user headless = imprime pregunta y termina la
corrida con stop_reason propio (honesto). DECISIÓN ABIERTA #2.
CACHE: los specs de las 2-3 tools nuevas van AL FINAL del orden estable de
tools.specs() (append, nunca reorder — prefijo cacheable intacto). El bloque
de plan-mode en el system prompt debe ser estático (siempre presente, no
condicional por corrida) o el prefijo cambia entre corridas — DECISIÓN
ABIERTA #3 (recomendado: texto estático + estado dinámico viaja en el primer
mensaje, no en el prefijo; donor CC attribution-header, research/05).

## 6. SIGUIENTE ACCIÓN (exacta)
1. `cd ~/code/tlamati && git checkout c1-session && uv tool install --from .
   tlamati --reinstall` (trabajar SOBRE c1-session o rama nueva c5-plan-mode
   saliendo de c1-session — preferible rama nueva: `git checkout -b
   c5-plan-mode`).
2. Resolver las 3 decisiones abiertas de §5 ANTES de codificar; si el
   fundador está presente, preguntarle con opciones (protocolo: él decide,
   Hermes implementa). Si no está y la ventana es yolo: elegir la opción
   recomendada y documentarla en el commit.
3. Implementar: policy (capa plan-mode), tools enter/exit/save_plan,
   CLI --plan-mode, system prompt estático, tests (unidad + integración con
   FakeProvider: entrar→write denegado→exit sin aprobación fail-closed→exit
   aprobado→write permitido; doble-salida; rechazo con feedback).
4. Auditoría completa: `uv run pytest tests/ -q` (esperado ≥224+ verdes),
   `uv run ruff check src tests`, `uv run ruff format --check .`,
   `uv run mypy --strict src`.
5. Baseline real (¿GASTA? SÍ): `tlamati-eval --out evals/c5_check.jsonl` —
   SOLO cuando OpenRouter respire. Si 429/504: leer campo `error` del JSONL,
   NUNCA asumir fallo propio; esperar o pedir BYOK al fundador.

## 7. ¿GASTA?
- Construir C5 + tests + lint: $0.
- Baselines reales (B5, c1-session, C5): SÍ, OpenRouter centavos por corrida.
  Estado 16-nov noche: SATURADO (504/429 todo el día, evidencia
  evals/b5_check2.jsonl + b5_check3.jsonl, ambas 1/5). Opciones: esperar
  horas / otro día, o fundador agrega BYOK DeepInfra (ya se le explicó,
  https://openrouter.ai/workspaces/default/byok).
- ORDEN DE MERGES cuando haya baseline verde + OK verbal: B5 (rama
  b5-ledger, commit 81c5235) PRIMERO → luego c1-session (C1-C4) → luego C5.
  c1-session sale de main SIN B5: al mergear revisar conflictos en cli.py y
  loop.py (ambas ramas los tocan; b5-ledger añade ledger/audit, c1-session
  añade session/memory/skills/instructions —大概率 merge manual sencillo
  pero NO automático a ciegas: correr la suite completa después).

## 8. CÓMO VERIFICAR SIN GASTAR
- Suite completa: `uv run pytest tests/ -q` → 224 passed en c1-session.
- Lint trio: `uv run ruff check src tests && uv run ruff format --check . &&
  uv run mypy --strict src`.
- Smoke gratis C1: `tlamati sessions --session-db /tmp/x.db`.
- Smoke gratis C3 (migración 1-flag, ya probado REAL):
  `uv run python -c "from pathlib import Path; from tlamati.memory.skills
  import SkillLibrary; print(len(SkillLibrary([Path.home()/'.hermes'/'skills']).catalog()))"`
  → 47 activas (.archive excluido).
- Smoke gratis C4: crear /tmp/repo-prueba/.git + AGENTS.md y correr
  load_instructions desde un subdir (ver tests/test_instructions.py).

## 9. ESTADO GIT (16-nov ~19:00)
- main = 777eb8a (handoff B5; B4 fusionado 4140c20; CI verde run 43972038230).
- rama b5-ledger = 81c5235 (B5 completo, pendiente baseline+OK+merge).
- rama c1-session = 5 commits sobre main: 47559f1 (guía destilada), f9bcc3d
  (C1 session store), c75d86d (C2 memoria+dream), c32e2a9 (C3 skills+edu v2),
  592334a (C4 instructions). NADA fusionado a main aún.
- Untracked: evals/b5_check2.jsonl + b5_check3.jsonl (evidencia rate-limit,
  NO borrar sin leer).
- Ramas remotas viejas: origin/b2-tools, origin/fase-b (borrables, low prio).

## 10. PITFALLS ACUMULADOS (no repetir)
- AUDITORÍA LOCAL COMPLETA = pytest + ruff check + ruff FORMAT --check + mypy
  --strict. Olvidar format-check = CI rojo y correo "run failed" al fundador.
- OpenRouter 429/504: el campo `error` del JSONL es la fuente de verdad;
  NUNCA asumir fallo propio; reintentos por tarea tras 15-60s.
- `git branch -d` / merge / push encadenados con && disparan bloqueo del
  parser aunque el usuario aprobó (NO es veto, protocolo #6): comandos
  simples, uno por llamada.
- uv wheel cache obsoleto tras installs raros → `uv cache clean tlamati`.
- Tools nuevos re-obtenibles DEBEN agregarse a DEFAULT_COMPACTABLE_TOOLS
  (context/compaction.py) o su output se limpia sin reporte (pitfall qwen
  #4239). save_plan NO es re-obtenible (side-effect) → NO agregarlo.
- Orden de tools.specs() estable = append-only (cache sagrada).
- El fundador es NO-técnico: NUNCA pedirle revisar código; presentar
  evidencia de COMPORTAMIENTO en cristiano; su OK verbal autoriza el merge.
- Ventanas yolo cronometradas: al corte, terminar la unidad en curso +
  resumen; no arrancar lo siguiente si no cabe.

## 11. AL CIERRE DE LA PRÓXIMA SESIÓN
CLASE_5 (edu/DESARROLLO_TLAMATI_CLASE_5.md) con formato v2 (TUTORIAL: pasos +
herramientas + sección (c2) LA TEORÍA DETRÁS + continuidad con Clase 4).
Temas disponibles: jaula bwrap (B3), trifecta letal (B4), ledger append-only
(B5), CI verde, la destilación guía-investigación, session store (C1),
techos de memoria + auto-dream (C2), migración skills 1-flag (C3), estándares
AGENTS.md (C4), fail-closed del plan-mode (C5 si se hace).

-- Hermes, 16-nov-2026, sesión 8. Fase C original completa en rama c1-session
-- (sin mergear). C5 plan-mode = siguiente paso; donors destilados en §5.
-- Baselines bloqueadas por rate-limit upstream todo el 16-nov. --
