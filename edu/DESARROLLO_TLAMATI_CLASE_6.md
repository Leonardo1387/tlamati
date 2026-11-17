# CLASE 6 — Plan-mode: enseñarle modales al agente (explorar → aprobar → ejecutar)

*Serie "Desarrollo de Tlamati", capítulo 6. Sesión 9, 16-nov-2026 (noche, ventana yolo). Rama `c5-plan-mode`, commit 236b907.*

## Conexión con la clase anterior

La Clase 5 cerró con una pregunta abierta: **en plan-mode el agente tiene prohibido
escribir archivos… pero para aprobar un plan, el plan debe existir como archivo. ¿Cómo
se escribe?** El fundador la respondió en esta sesión: **opción A — una tool especial
`save_plan` que SOLO puede escribir dentro de `.tlamati/plans/`**. Es la opción
auditable: el plan queda como archivo real en el proyecto, se puede abrir, leer y
refinar en varias vueltas. Y con esa decisión arrancamos a construir C5, el plan-mode,
el último MUST del PRD que estaba sin fase asignada.

## ¿Qué es plan-mode y por qué importa?

Imagina un contratista que llega a tu casa. Dos estilos posibles:

1. **Estilo salvaje**: entra, tira un muro, y al final te dice "listo, era un muro de carga".
2. **Estilo profesional**: primero recorre la casa, dibuja un plano, TE LO MUESTRA, y solo
   cuando tú lo firmas empieza a romper cosas.

Los agentes de código sin plan-mode son el estilo 1. Plan-mode fuerza el estilo 2: el
agente entra en un estado donde **solo puede explorar** (leer archivos, buscar, consultar
skills y memoria). Todo lo que modifica — escribir, editar, terminal — queda DENEGADO.
Para poder actuar debe: guardar un plan como archivo markdown, pedir tu aprobación, y
solo con tu OK humano real vuelve a tener manos.

## Los pasos de esta sesión (tutorial replicable)

### Paso 1 — Leer el punto de entrada

```bash
cd ~/code/tlamati
git checkout c1-session
git checkout -b c5-plan-mode
```

Regla del proyecto: cada sesión nueva arranca leyendo su HANDOFF (este fue
`HANDOFF_FASE_C5.md`, que la sesión 8 dejó escrito con los donors destilados y 3
decisiones abiertas). La rama nueva sale de `c1-session` porque C5 se construye SOBRE
C1-C4 (memoria, skills, sessions), no sobre main.

### Paso 2 — Resolver las decisiones abiertas ANTES de codificar

El handoff traía 3. Se resolvieron así:

- **#1 (cómo se escribe el plan)**: `save_plan`, opción del fundador (ver arriba).
- **#2 (¿ask_user/complete_task entran ahora?)**: NO — se difieren a Fase E (el TUI).
  En headless, `exit_plan_mode` sin un aprobador humano disponible **falla cerrado**:
  error honesto y el plan-mode sigue activo. Mejor decir "no puedo" que inventar una
  aprobación.
- **#3 (¿el bloque de prompt cambia por corrida?)**: NO — el texto del plan-mode es
  ESTÁTICO en el system prompt (siempre los mismos bytes), y el estado dinámico
  ("estás EN plan-mode desde el arranque") viaja en el primer mensaje del usuario.
  Razón: el prefijo cacheable. Si el system prompt cambiara entre corridas, la cache
  del proveedor se invalida y cada turno cuesta más.

### Paso 3 — Escribir el estado (la pieza pequeña que sostiene todo)

Archivo nuevo: `src/tlamati/plan/mode.py`. La clase `PlanState` tiene solo 4 atributos
(`active`, `revision`, `pre_plan_mode`, `pending_revision`) y 4 métodos (`enter`,
`request_exit`, `commit_exit`, `cancel_exit`). El concepto clave es la **revisión**: un
contador que sube en cada cambio real de modo. Una aprobación queda ligada a la revisión
que vio; si el estado cambió debajo de ella, la validación final no coincide y **no se
conmuta** (falla cerrado).

### Paso 4 — Las 3 tools

Archivo nuevo: `src/tlamati/plan/tools.py`:

- `enter_plan_mode(reason)` — entra y guarda el modo previo.
- `save_plan(name, content)` — escribe SOLO en `.tlamati/plans/`, con validación de
  nombre (slug: letras/dígitos/guiones, nada de `../../escapes`) y path-escape guard
  (el truco de resolver la ruta y verificar que cae dentro del directorio permitido —
  mismo donor que `skill_view` de C3).
- `exit_plan_mode(plan_path)` — el corazón del fail-closed: verifica que estás en
  plan-mode, que el archivo existe y está dentro del dir controlado, reserva la señal
  de salida (una sola petición en vuelo por revisión → doble salida falla cerrado),
  llama al aprobador humano, y solo con `True` explícito conmuta. Rechazo con texto =
  feedback para que el modelo refine; excepción del aprobador = falla cerrado.

### Paso 5 — Reutilizar el mecanismo de permisos de B4 (cero código nuevo)

Aquí está la elegancia: la escalera `deny > ask > auto` ya existía desde la Fase B4
(`policy/config.py`). Plan-mode es solo **una regla transversal más** en
`Policy.resolve()`: si `plan_state.active` y la tool no está en la whitelist read-only
(`read_file`, `search_files`, `skill_view`, `skill_list`, `search_memory`) → DENY.
El `Registry` detecta que el DENY viene del plan-mode y devuelve un error específico:
*"estás en PLAN-MODE, guarda el plan con save_plan y pide aprobación con
exit_plan_mode"* — el modelo lee eso y se autocorrige.

### Paso 6 — CLI y cache sagrada

- Flag `--plan-mode` para arrancar en plan.
- **Mutuamente exclusivo con `--approve-tool '*'`** (YOLO): falla rápido al parsear con
  exit code 2, nunca en caliente. Regla donor de gemini-cli: si el modo YOLO pudiera
  aprobar planes, la aprobación humana dejaría de ser obligatoria.
- Las 3 tools nuevas se registran **AL FINAL** del orden de `tools.specs()`
  (append-only). Reordenar tools cambia los bytes del prefijo y rompe la cache.

### Paso 7 — Auditoría completa (el estándar del proyecto)

```bash
uv run pytest tests/ -q          # 252 verdes (224 previos + 28 nuevos)
uv run ruff check src tests      # limpio
uv run ruff format --check .     # limpio
uv run mypy --strict src         # limpio, 35 archivos
```

Los 28 tests nuevos (`tests/test_plan_mode.py`) incluyen el **flujo de integración
completo** con un FakeProvider (proveedor guionado, cero red, cero costo): entrar →
intentar escribir → DENEGADO → save_plan → exit aprobado → escribir PERMITIDO → fin.
Verificado contra el sistema de archivos real de pytest: el archivo solo cambia tras la
aprobación.

### Paso 8 — Baseline REAL (la prueba que gasta centavos y vale cada uno)

```bash
tlamati-eval --out evals/c5_check.jsonl
# → 5/5 OK · modelo=qwen/qwen3-coder
```

Todo el 16-nov OpenRouter estuvo saturado (504/429, evidencia `evals/b5_check2.jsonl`);
por la noche respiró. Resultado:
**5/5 tareas de terminal-bench-lite resueltas**, con `cache_read ≈ 94%` de los tokens
de entrada (4480 de 4772 en una tarea). Ese número es la prueba empírica de la decisión
#3: el bloque estático de plan-mode + las 3 tools nuevas NO rompieron la cache. El
baseline además valida C1-C4 (esta rama los carga encima) — su baseline pendiente
también queda resuelta con esta corrida.

## LA TEORÍA DETRÁS

### Patrón 1: Fail-closed (fallar cerrado)

Principio general de seguridad: cuando un sistema entra en un estado inesperado,
rancio o ambiguo, debe caer al estado MÁS restrictivo, nunca al más permisivo. Una
puerta con cerradura eléctrica debe ABRIRSE con fallo de energía (para evacuación) o
BLOQUEARSE (para seguridad) según el contexto — pero el diseño siempre decide la
dirección del fallo ANTES, explícitamente. Aquí: aprobación vieja, doble salida,
excepción del aprobador, todo → el plan-mode SIGUE ACTIVO. Lo contrario (fail-open)
es el bug clásico donde "si el sistema de permisos truena, dejamos pasar".

**Donor**: qwen-code, `docs/design/explicit-plan-exit-approval.md` (las 4 reglas de
oro). Aprender ingeniería = leer a los grandes y reimplementar en limpio.

### Patrón 2: Revisión / token de versión optimista (optimistic concurrency)

De las bases de datos: dos procesos pueden intentar modificar el mismo registro; la
solución no es un candado pesado sino un NÚMERO DE VERSIÓN — "solo aplica mi cambio si
la versión sigue siendo la que yo leí". `PlanState.revision` es exactamente eso: la
aprobación humana dice "apruebo la revisión 1"; si para cuando se va a conmutar el
estado ya va en la revisión 2, la aprobación es rancia y se descarta. Mismo principio
que los ETags de HTTP (`If-Match`) y que los campos `version` de bases de datos.

### Patrón 3: Regla transversal sobre mecanismo existente (policy layering)

No construimos un segundo sistema de permisos: añadimos UNA capa a la escalera que ya
resolvía deny>ask>auto desde B4. Principio general: cuando una feature nueva parece
necesitar "su propio mecanismo", primero pregunta si es una POLÍTICA que puede montarse
sobre el mecanismo viejo. Menos código, menos tests, menos caminos que divergen. La
capa transversal solo puede ENDURECER (auto→deny), nunca relajar — invariante de la
escalera.

### Herramienta de la sesión: FakeProvider (test doble / proveedor guionado)

Mecánica: una clase que implementa el mismo Protocol que un proveedor real (su
`stream()` yields eventos), pero en vez de llamar a una API reproduce un guion escrito
a mano turno por turno. Sirve en general para probar cualquier sistema que consume un
servicio externo caro/lento/no determinista: se inyecta el doble y el test corre en
milisegundos, sin red y sin costo, pudiendo forzar escenarios imposibles de provocar a
voluntad contra la API real (¿cuándo te rechaza un humano un plan? Aquí, cuando el
guion lo dice). Es el patrón Dependency Injection aplicado a pruebas.

## El error del día

Dos menores, ambos cazados por la auditoría antes del commit: (1) un test asumía que
`exit_plan_mode` con un path relativo inexistente daría "no existe", pero el
path-escape guard lo rechaza ANTES (está fuera de `.tlamati/plans/` porque se resuelve
contra el cwd) — el orden de las validaciones importa y el test se corrigió para
ejercitar el caso real; (2) siete violaciones de estilo (líneas >100 chars, un import
sin usar, orden de imports) que `ruff check` señaló exactas. Ninguna llegó al commit:
para eso existe el lint trio como gate local idéntico al CI.

## Estado al cierre y gancho

Rama `c5-plan-mode` (commit 236b907, subida a origin): C5 completo, 252 tests verdes,
mypy estricto limpio, baseline real 5/5 con cache al 94%. **NO fusionada** — el
protocolo pide el OK verbal del fundador, y el orden de merges sigue siendo:
B5 (rama `b5-ledger`) PRIMERO → `c1-session` (C1-C4) → `c5-plan-mode`. Revisar
conflictos en `cli.py` y `loop.py` al mergear (ambas ramas los tocan).

Siguiente frente de trabajo: **C6 — workspaces/routing** (PRD F6b): carpetas de agente
con su propio `routing.md` para que Tlamati sepa qué configuración usar según el
proyecto, donor del video "agents as folders" (research/03). Y cuando el fundador esté:
presentarle la evidencia de comportamiento de C5 en cristiano para el OK verbal.

**Pregunta abierta para mañana: si el plan-mode bloquea escribir archivos pero permite `save_plan`… ¿debería `save_plan` estar disponible también FUERA de plan-mode, para que el agente deje planes escritos como bitácora auditable aunque nadie se los pida? Gemini lo permite; qwen no. Es la diferencia entre "el plan es un trámite para salir del modo" y "el plan es un artefacto del proyecto".**
