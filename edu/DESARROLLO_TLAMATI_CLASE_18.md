# Desarrollo Tlamati — Clase 18
## 22-nov-2026: El experimento mentiroso y las reglas que llegan tarde

Serie: Desarrollo de Tlamati (capítulo 18). Sesión 28, noche del 21 al 22-nov-2026.
Anterior: CLASE_17 (seguridad real vs teatro; las tres categorías de candado).

---

## 0. DÓNDE VENIMOS

En la clase 17 clasificamos cada candado del arnés en REAL, TEATRO o RUIDO.
Hoy esa clasificación se pone a prueba de verdad, en dos frentes: un
experimento que casi nos cuenta un cuento, y un fix para el bug más caro del
dogfooding #6 — el agente que deployó Producto A sin haber leído NUNCA las
reglas del repo.

Imagínate la escena cotidiana: contratas a un empleado excelente, lo mandas a
trabajar a la oficina equivocada, y cuando comete errores te sorprendes. El
empleado no era malo — nadie le dio el manual. Eso fue el dogfood #6: la
sesión arrancó desde `~` (home), el cargador de instrucciones camina del
directorio actual hacia el primer ancestro con `.git` (un archivo oculto que
marca "aquí empieza un repositorio"), y desde home no encontró nada. Las
reglas del proyecto NUNCA entraron al contexto del agente.

## 1. LO QUE ENTENDIMOS HOY (los números mandan)

Primero, una lección de humildad estadística. El spike exploratorio del
skillopt con n=3 corridas por brazo decía: baseline 1/3 (33%), mutación 2
lograba 3/3 (100%) — "+67 puntos, señal fuerte". La confirmación con n=10
(qwen3.8-flash) y n=5 (qwen3-coder) contó otra historia:

- El baseline real era **8/10 (80%)**, no 33%. Con 3 monedas al aire, un solo
  fallo te pinta un "baseline malo" que no existe.
- mut1, que parecía mejorar (2/3), resultó **PEOR** que el baseline en los
  dos modelos: 60% y 40%.
- mut2 sí metió 15/15 perfectos entre ambos modelos — pero el **test exacto
  de Fisher** (una fórmula que calcula: "si el baseline fuera 80%, ¿qué tan
  raro es meter 10 de 10 por pura suerte?") dio p=0.24. Traducción: un 24% de
  probabilidad de que sea azar. No alcanza el estándar científico (p<0.05).

Veredicto honesto, escrito tal cual en el apéndice de `dev/SPIKE_SKILLOPT.md`:
**skillopt como feature queda EN SUSPENSO**. La mejora probablemente es real
pero más chica; este diseño no tiene potencia para probarla. Costo total de
la confirmación: $0.445 contra un tope de $2.

## 2. QUÉ SE CONSTRUYÓ Y CÓMO (sección replicable)

Los arreglos del dogfood #6 vivieron en una rama aparte
`feat/niveles-integracion` y ya están mergeados a `main` (commit b401ea4):

- **NIVEL 1a** (`src/tlamati/context/late_instructions.py`, commit 02bdc6f):
  cuando el agente toca un archivo dentro de un repo (con write_file, edit o
  `cd` en terminal), se detecta el repo y sus AGENTS.md/CLAUDE.md se adjuntan
  como recordatorio AL RESULTADO DE LA HERRAMIENTA. Se inyecta una vez por
  versión de contenido; sin repo o sin archivo de reglas, silencio total.
- **NIVEL 2d+2e** (`src/tlamati/policy/config.py`, commit ba6a2cd): dos
  patrones regex nuevos en la escalera de permisos, default ON y
  configurables en config.yaml. `pip install --break-system-packages` ahora
  pide aprobación humana (en el dogfood sustituyó el Pillow del sistema WSL).
  Y escribir hacia `07-index/` o `dist/` (dirs de artefactos de producción)
  también pide aprobación. Leer, NO: el gate es de sobreescritura.
- **NIVEL 2f+3g** (commit 7e69d80): advisory pre-commit (si el índice de git
  toca archivos que el AGENTS.md marca como compartido/crítico, se le
  recuerda al agente la no-regresión — mensaje, nunca bloqueo) y 2 líneas al
  prompt del sistema: "si TU script ve corrupto lo que la fuente entrega
  limpio, el bug es de tu parsing".

Cómo se verifica (los comandos exactos de hoy):

```bash
cd ~/code/tlamati && source .venv/bin/activate
ruff check .                      # lint: debe decir "All checks passed!"
python -m pytest tests/ -q        # 624 passed (baseline eran 564; +60 nuevos)
python -m mypy src/tlamati/context/late_instructions.py  # Success: no issues
```

Y la prueba REAL, con LLM de verdad (no solo tests): se arrancó el agente en
/tmp con un repo cuyo AGENTS.md exigía escribir la palabra BANANA en la
respuesta final. El agente editó el archivo del repo sin leer jamás el
AGENTS.md por su cuenta — y respondió: "el repo tiene un AGENTS.md con la
instrucción de escribir BANANA — la acato — BANANA". La evidencia dura está
en el conteo de tokens: la historia creció +222 tokens justo en el resultado
del `edit` — eso ES el recordatorio viajando.

## 3. LA TEORÍA DETRÁS (c2)

**Patrón 1 — inyección tardía (late injection / system-reminder).** Cuando
una regla no estaba disponible al arrancar pero aparece a mitad de la
conversación, NO se edita el prompt del sistema: se adjunta al mensaje más
reciente. ¿Por qué? Los proveedores de LLM cachearizan el prefijo de la
conversación (system prompt + tools): cada token del prefijo que no cambia se
cobra más barato en turnos siguientes. Mutar el prefijo a mitad de la corrida
rompe la caché y encarece TODO lo que sigue. Donor: Claude Code, que usa
exactamente este mecanismo ("system-reminder" pegado a tool results) para
reglas que llegan tarde. La regla de oro del proyecto: **el prefijo es
byte-estable; lo volátil viaja al final** (STABILITY.md v0.1).

**Patrón 2 — escalera que solo endurece (monotonic policy).** Cada capa de
permisos (override de herramienta → patrones fnmatch → patrones regex →
trifecta untrusted) puede subir auto→ask→deny pero NUNCA bajar. Un patrón
nuevo jamás puede relajar un candado existente: hace imposible que una capa
configurada con descuido abra una puerta que otra cerró. Es el mismo
principio que en redes se llama "deny by default, allow by exception".

**Patrón 3 — git worktree como mesa de cirugía.** `git worktree add
../tlamati-niveles main` crea una SEGUNDA copia de trabajo del mismo repo, en
otro directorio, con su propia rama y su propio venv. Hoy fue salvavidas: la
batería de evals corría contra el `.venv` editable del repo principal — si
edito `src/` ahí en caliente, cada corrida siguiente del experimento usa
código distinto y los resultados quedan contaminados. Regla reusable: **nunca
operes al paciente y al donante en la misma mesa** — si un proceso consume tu
código en vivo, tus edits van en un worktree aparte.

**Mecánica de Fisher exacto (lo usamos sin scipy):** dado un 2x2 (éxitos/
fallos de dos brazos), suma las probabilidades hipergeométricas
(`math.comb`) de todas las tablas igual o más extremas que la observada, con
los mismos marginales. Devuelve el p-value exacto — no una aproximación
asintótica — y cabe en 30 líneas de stdlib.

## 4. QUÉ DECIDIMOS NO CONSTRUIR

- NO se mutó el prefijo para el 1a (rompería la caché — ver Patrón 1).
- NO se hizo el 2f bloqueante: un advisory que bloquea commits falsos
  positivos frenaría al agente legítimo; la filosofía M8 dice "advisory no
  muta comportamiento".
- NO se commiteó nada en GitHub todavía: el push sigue siendo decisión
  explícita del fundador tras el último dogfood (§4-5 del handoff).
- NO se promovió skillopt a feature: los números no dieron (sección 1).

## 5. EL ERROR DEL DÍA

La batería de confirmación se había MUERTO en silencio a las 22:06 (mut1|4 de
45). ¿Cómo se detectó? El proceso watcher de Hermes terminó antes de tiempo y
`pgrep spike_confirm` no mostró nada vivo, pero `dev/spike_confirm_results.json`
tampoco existía: proceso terminado SIN resultado = muerte, no éxito. El diseño
reanudable (progreso persistido run-a-run en `dev/spike_confirm_progress.json`)
permitió re-correr y que saltara los 15 runs ya hechos — cero gasto duplicado.

Y un segundo error, más fino: mi primer smoke test del 1a "falló" — el grep
buscó el recordatorio en el JSONL de eventos y encontró 0 coincidencias. ¿Falso
negativo? Sí: el JSONL de eventos de tlamati solo registra metadatos
(`tool_result: {id, is_error}`), NO el contenido del resultado. El contenido
vive en la historia que ve el modelo. Detecté la verdad por dos vías: el salto
de tokens en la historia (+222 en el turno del edit) y la respuesta final del
agente citando el AGENTS.md. Lección: **cuando tu verificación dice "falló",
verifica primero la verificación** — es la misma lección del 3g (¿output
corrupto o parsing corrupto?), aplicada a mí mismo en la misma noche.

## 6. CONTINUIDAD

Merge a main listo y con gate verde (624 tests). Quedan para la próxima
sesión, por decisión del fundador: el **último dogfood** (arrancar tlamati
desde ~ contra una tarea real de proyecto-legal y verificar que 1a/2d/2e/2f
funcionen en vivo, con autopsia posterior vía sessions.db) y la
**publicación v0.1** (README honesto con la sección "qué sabemos / qué no"
del spike, revisión de qué NO se pushea, decisión de filter-repo, push a
leonardoGH/tlamati private→public). La rama `spike/skillopt` queda viva con
su commit 7afb977 — no se mergea sola.

**¿El último dogfood debería correrse contra proyecto-legal (reglas conocidas, riesgo de romper producción) o contra un repo de juguete creado para la ocasión (riesgo cero, pero prueba menos)? ¿Qué probarías tú primero: el 1a desde home, o el gate 2e escribiendo a un 07-index/ real?**
