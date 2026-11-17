# Desarrollo Tlamati — Clase 5
## 16-nov-2026: El día que tlamati aprendió a recordar

En la Clase 4 vimos cómo el agente recibió manos seguras: la jaula (B3), los
permisos (B4) y el libro de auditoría (B5). Pero un agente con manos y sin
memoria es como un trabajador brillante que cada mañana olvida quién es su
jefe y en qué proyecto trabaja. Hoy construimos la memoria completa — y antes,
el alumno le cachó un error de proceso al maestro, que resultó ser la lección
más importante del día.

### El problema: el agente amnésico

Imagina que contratas a un asistente que resuelve todo bien, pero al terminar
la jornada se le borra el cerebro. Mañana le vuelves a explicar todo. Eso era
tlamati hasta ayer: cada corrida empezaba de cero. Los agentes comerciales
(Claude Code, ChatGPT) no funcionan así: recuerdan tus preferencias, retoman
conversaciones. Hoy tlamati aprendió las cuatro piezas que hacen eso posible:
C1 sesión, C2 memoria, C3 skills, C4 instrucciones de proyecto.

### La cachada del alumno: investigar no es lo mismo que destilar

Antes de codificar, el fundador hizo una pregunta que valió oro: "de todo lo
que investigaste de los 8 arneses, ¿qué hace que el nuestro sobresalga en
memoria y skills?". Al revisar la guía de implementación contra los documentos
de investigación, apareció el problema: la Fase C se había escrito ANTES de que
la investigación profunda existiera, y nadie regresó a actualizarla. La
investigación decía cosas brutales (Claude Code consolida memoria en segundo
plano al cerrar sesión; tiene techos duros de entradas; codex marca qué
resultados sobreviven una compactación) y la guía solo decía "C2: memory/,
2 archivos fijos". Cuatro líneas flacas donde debía haber un diseño.

Se corrigió antes de tocar código: cada decisión de la Fase C quedó destilada
en la guía CON SU FUENTE (commit 47559f1). Regla nueva del proyecto: al inicio
de cada fase, verificar que la guía absorbió la investigación vigente; si no,
destilar primero. Investigar es reunir leña; destilar es hacer el plano de la
casa — sin plano, la leña no calienta nada.

### QUÉ SE CONSTRUYÓ Y CÓMO (sección replicable)

Todo en la rama c1-session (5 commits + 2 de handoff), partiendo de main.

C1 — Session store (commit f9bcc3d). Archivo nuevo:
src/tlamati/session/store.py. Una base de datos SQLite local guarda cada
mensaje de cada corrida. Comandos para usarlo:

```
tlamati -p "arregla X"          # al terminar imprime [session] <id>
tlamati sessions                # lista las sesiones guardadas (GRATIS, sin LLM)
tlamati -p "sigue con Y" --continue        # retoma la última sesión
tlamati -p "sigue" --resume <SESSION_ID>   # retoma una específica
```

Verificación: `uv run pytest tests/test_session_store.py -q` (13 tests, incluye
uno de integración: corrida 1 persiste → corrida 2 resume y el proveedor VE la
historia previa).

C2 — Memoria durable + auto-dream (commit c75d86d). Archivos:
src/tlamati/memory/store.py, tools.py, dream.py. Dos archivos markdown con
techos duros (100 entradas / 24,000 caracteres cada uno):

```
# los vive en ~/.local/share/tlamati/memory/MEMORY.md y USER.md
tlamati -p "..." --dream     # al cerrar, un modelo barato destila aprendizajes
tlamati -p "..." --no-memory # apagado
```

Verificación: `uv run pytest tests/test_memory.py -q` (23 tests; el de caps
baja el techo a 2 con monkeypatch y comprueba que la tercera entrada es
rechazada obligando a consolidar).

C3 — Skills compatibles con Hermes (commit c32e2a9). Archivo:
src/tlamati/memory/skills.py. La prueba de fuego real:

```
tlamati --skills-dir ~/.hermes/skills -p "..."
```

Eso leyó las 47 skills activas del Hermes de esta máquina SIN conversión
alguna, excluyendo automáticamente las jubiladas en .archive/. Verificación:
`uv run pytest tests/test_skills.py -q` (17 tests, incluye uno que escribe una
skill con el frontmatter real de Hermes y comprueba que parsea).

C4 — Instrucciones de proyecto (commit 592334a). Archivo:
src/tlamati/context/instructions.py. Lee AGENTS.md (estándar de codex, Cursor,
Jules) y CLAUDE.md (Claude Code), fusionando desde la raíz del repo hasta el
subdirectorio actual:

```
tlamati -p "..."                  # inyecta AGENTS.md si existe; imprime
                                  # [instrucciones] N archivo(s) v:ed3fe2926cc8
tlamati -p "..." --no-instructions
```

Verificación: `uv run pytest tests/test_instructions.py -q` (14 tests).

Auditoría completa de cada paso (la regla que aprendimos con el CI en Clase 4):

```
uv run pytest tests/ -q          # 224 passed al final del día
uv run ruff check src tests
uv run ruff format --check .
uv run mypy --strict src
```

Costo de TODO el día de código: $0. Las únicas corridas que gastan (baselines)
están bloqueadas porque OpenRouter pasó el 16-nov entero saturado (errores
504/429 de sus proveedores DeepInfra/Venice — evidencia guardada en
evals/b5_check3.jsonl).

### LA TEORÍA DETRÁS (para llevar a cualquier proyecto)

Patrón 1 — ALMACÉN APENDABLE CON DEGRADACIÓN HONESTA. La base de sesiones y la
memoria siguen la regla del ledger de la Clase 4: si el almacenamiento falla,
el programa NUNCA se cae; marca `broken` y sigue trabajando sin persistir,
avisando. En cualquier sistema real (pagos, logs, inventarios) la escritura
auxiliar no debe poder matar la operación principal.

Patrón 2 — TECHOS DUROS COMO PRESIÓN DE DISEÑO (donor: Claude Code, vía
ingeniería inversa). La memoria no crece infinito: al llegar a 100 entradas,
añadir más es rechazado y el sistema obliga a CONSOLIDAR (fusionar dos
entradas en una, borrar lo viejo). Es el mismo principio que una bodega llena:
o tiras cajas, o no entra mercancía nueva. Los clones open-source de agentes
casi ninguno tiene esto; Claude Code sí, y lo detectamos leyendo sus eventos
de telemetría (`team_mem_entries_capped`).

Patrón 3 — TRABAJO EN SEGUNDO PLANO / AUTO-DREAM (donor: Claude Code). La
consolidación de memoria corre al CERRAR la sesión, nunca en medio de tu
conversación. Herramienta general: todo proceso de "ordenar y limpiar"
(distill, index, garbage-collect) debe ir fuera del turno caliente. Por eso
ChatGPT no se pone lento cuando "te recuerda": lo hace después.

Patrón 4 — CATÁLOGO BARATO, CUERPO CARO BAJO DEMANDA (donor: Hermes). En el
prefijo del modelo solo viaja nombre+descripción de cada skill (~50 tokens por
skill); el cuerpo completo (que puede medir 25,000 caracteres) solo se carga
cuando el modelo llama a `skill_view`. Es el patrón de biblioteca: el catálogo
de fichas siempre visible, el libro se baja del estante solo cuando lo pides.
Y como el libro se puede volver a bajar, la compactación puede tirar su
contenido del contexto sin perder nada (whitelist de microcompactación).

Patrón 5 — ESTÁNDARES DE FACTO COMO PUENTE. SKILL.md (frontmatter YAML +
markdown) lo inventó Anthropic como "Agent Skills"; Hermes lo adoptó; tlamati
lo lee nativo → migración con un flag. AGENTS.md es el estándar que usan
codex, Cursor, Jules y Factory → tlamati lo lee también, y CLAUDE.md de paso.
La lección general: cuando exista un formato que varios competidores ya
comparten, adóptalo en vez de inventar el tuyo — cada formato propio es un
muro, cada estándar es una puerta.

### Qué decidimos NO construir hoy

- C2 sin los 4 scopes de Claude Code (user/project/local/team): solo user y
  proyecto. Los otros dos, si hay demanda real.
- ask_user/complete_task como herramientas: sin interfaz gráfica (Fase E) no
  tienen dónde vivir; quedaron anotados como decisión abierta en el handoff.
- Adaptadores de skills para Cursor (.mdc) y prompts de codex: pendientes y
  documentados honestamente. DeepSeek ni aplica: es modelo, no tiene formato
  de skills.
- Baselines y merges: no se forzaron contra un OpenRouter saturado. Esperar es
  parte del trabajo; reintentar a lo tonto quema dinero y confianza.

### El error del día

Dos, ambos instructivos. (1) El de proceso: la guía sin destilar que el
fundador detectó con una sola pregunta — ya contado arriba; la corrección vive
en el commit 47559f1 y la regla nueva en la skill del proyecto. (2) El de
código: al excluir directorios ocultos del escaneo de skills, la primera
versión del escáner se tragó las 46 skills jubiladas de `.archive/` junto con
las 47 activas (93 en total). Se detectó EN la prueba real contra la librería
de Hermes — para eso sirven las pruebas contra datos reales y no solo contra
casos de juguete. Fix: saltar cualquier componente de ruta que empiece con
punto, más un test que lo congela (`test_hidden_dirs_skipped`).

### Estado al cierre y gancho

Rama c1-session: C1+C2+C3+C4 completos, 224 tests verdes, mypy estricto limpio.
HANDOFF_FASE_C5.md creado y subido a main (commit 743c5b0, CI verde) para que
una sesión desde cero pueda retomar: sigue C5 plan-mode (explorar→aprobar→
ejecutar), con las 4 reglas de oro "fail-closed" destiladas de qwen-code y la
semántica de gemini-cli, más 3 decisiones abiertas para el fundador. Y cuando
OpenRouter respire: baselines reales y los merges pendientes (B5 primero, luego
C1-C4).

**Pregunta abierta para mañana: en plan-mode el agente tiene prohibido escribir archivos — pero para aprobar un plan, el plan debe existir como archivo markdown. ¿Cómo debería escribirse: con una herramienta especial que solo puede escribir dentro de .tlamati/plans/, o el plan viaja como texto en la llamada y es el arnés quien lo guarda? La primera es más auditable; la segunda más simple. Los dos arneses donantes eligieron distinto.**
