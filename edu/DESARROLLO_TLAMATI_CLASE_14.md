# CLASE 14 — Cuando el modelo es chico, el arnés importa más: autopsia de un fracaso y los 4 bugs que dejó al descubierto

*Serie: DESARROLLO_TLAMATI. Sesión 24, 19-nov-2026. Anterior: CLASE_13 (el detector de bucles: "castigar el bucle muerto, preguntar el avance").*

En la clase 13 cerramos con el detector de estancamiento funcionando y la campaña de modelos corriendo. Hoy no construimos una feature nueva: hoy hicimos algo que vale igual o más en ingeniería — **una autopsia**. El fundador corrió Tlamati de verdad por segunda vez (dogfooding #2: el video doodle), lo percibió "10 veces peor" que la primera, y en lugar de discutir percepciones fuimos a las bases de datos del propio arnés a preguntar qué había pasado realmente. De esa autopsia salieron 4 bugs, todos fixeados hoy, más una limpieza de higiene antes de publicar el repo.

## 1. LA REGLA DE LAS TRES CAPAS (por qué la percepción del fundador y la evidencia decían cosas distintas)

Lo primero que enseña esta sesión es un patrón de diagnóstico que sirve en CUALQUIER sistema de agente. Cuando algo falla, hay tres culpables posibles y hay que separarlos siempre:

1. **Falló el arnés** (el programa que envuelve al modelo).
2. **Falló el modelo** (el cerebro contratado no obedeció).
3. **El arnés dejó de estorbar y el fallo del modelo se volvió visible.**

La tercera es la contraintuitiva y fue exactamente lo que pasó. La autopsia (sesión real `20261119-162706-440f1646`: 89 turnos, 2.75M tokens, 19 minutos) demostró que los fixes de la sesión anterior SÍ funcionaron: la skill se cargó (antes no), no hubo muro de turnos (antes sí), no hubo estancamiento. Y aun así el video salió mal — porque el modelo (qwen3-coder) tuvo la receta enfrente y la ignoró: se saltó Whisper, inventó los tiempos a mano, y puso `duration:50` sobre un audio real de 87.8 segundos.

Moraleja reusable: **arreglar el arnés no arregla al modelo — solo deja de taparlo.** Y eso es progreso: un fallo visible se puede medir, un fallo tapado por un bug del arnés no. La tesis del proyecto (que un modelo chico se acerque a lo que logran los frontera) tiene exactamente este techo: la obediencia a recetas largas. El bench flash que corría en paralelo lo confirma por el otro lado: con las 45 tareas del bench, tlamati×flash salió 45/45 perfecto ($0.13) — cuando la tarea está bien especificada y verificada por máquina, el modelo chico rinde; cuando la receta es larga y suelta, la ignora.

## 2. LA FORENSIA: CÓMO SE LE PREGUNTA A UN AGENTE QUÉ HIZO (herramientas y comandos reales)

Tlamati guarda dos bases de datos SQLite en `~/.local/share/tlamati/`:

- `sessions.db` — la conversación (mensajes, turnos, por qué terminó la sesión).
- `audit.db` — el ledger de auditoría: cada llamada a herramienta con su turno, argumentos, decisión y si terminó en error.

La consulta que reconstruyó los 89 turnos (sqlite3 viene en cualquier Linux):

```
sqlite3 ~/.local/share/tlamati/audit.db \
  "SELECT turn, tool, decision, is_error FROM tool_events WHERE session_id='20261119-162706-440f1646' ORDER BY ts"
```

El patrón que delata un bug estructural (vs. mala suerte): **una secuencia de `is_error=1` repetida sobre la misma herramienta**. La varianza no se repite cuatro veces seguidas con el mismo error; un bug sí. Así encontramos el bug 1: cuatro errores seguidos de `skill_view` — el catálogo publicaba el nombre con prefijo de categoría (`creative/doodle-blackboard-video`) pero la función de búsqueda solo aceptaba el nombre pelado. El arnés publicaba una forma y rechazaba esa misma forma.

## 3. LOS 4 BUGS Y SUS FIXES (todos en main hoy, con test que reproduce cada uno)

**Bug 1 — el catálogo mentía.** Fix en `memory/skills.py`: `get()` ahora acepta ambas formas (nombre pelado Y `categoria/nombre`; el prefijo se descarta con `rpartition("/")[2]`). ~8 líneas. Test: armar una librería con categoría, verificar que el catálogo publica el prefijo y que `get()` resuelve las dos formas.

**Bug 2 — la TUI nunca cerraba la sesión.** `cli.py` (modo headless) llamaba `finish_session` al terminar; `tui/app.py` no. Resultado: `sessions.db` quedaba con `stop_reason=''` y `turns=0` en TODAS las sesiones interactivas — justo las que el fundador usa. Fix: actualizar tras CADA corrida (crash-safe: si la app muere de golpe, el último estado ya quedó escrito) + cierre en `on_unmount`. Principio reusable: la telemetría se escribe durante, no al final — el "al final" nunca llega cuando hay crash.

**Bug 3 — el modelo vagó 8 turnos buscando el escritorio.** En WSL `~/Desktop` no existe; los archivos de Windows viven en `/mnt/c/Users/<usuario>/Desktop`. Ningún error se lo dijo. Fix (deliberadamente tonto y por eso bueno): cuando `read_file`/`edit`/`search_files` fallan sobre una ruta que no existe y contiene `Desktop|Documents|Downloads|Escritorio|Documentos|Descargas`, el error honesto añade una PISTA con candidatos REALES encontrados con un glob (`/mnt/*/Users/*`). NO auto-resuelve — fallar honesto sigue siendo el contrato; sugerir es gratis y la magia es cara.

**Bug 4 — el costo decía NULL.** El campo `cost_usd` de `turn_costs` quedaba vacío, así que la auditoría no pudo decir cuántos dólares costó la sesión. Diagnóstico: OpenRouter SÍ reporta el costo real en el campo `cost` del último chunk de usage del stream — y nuestro parser lo ignoraba (leía tokens pero no costo). Fix en `providers/openai_compat.py`: capturar `cost` cuando existe; si el proveedor no lo manda, `None` honesto — nunca un costo inventado ni estimado con tabla propia (la tabla PRICES del runner externo es para el bench; el arnés en vivo usa el número real del proveedor).

Los cuatro con su test que reproduce el error real primero. Suite final: **437 tests verdes**, ruff + ruff format + mypy strict limpios, CI verde en GitHub (run 44641227072).

## 4. HIGIENE DE PUBLICACIÓN (el repo va a ser público y la memoria git no olvida)

Segunda mitad de la sesión: preparar el repo para ojos extraños.

- `.gitignore` += `video_build*/` (el dogfooding escribió la VOZ del fundador en mp3 dentro del repo — un `git add -A` la publicaría), los JSONL con user_id de OpenRouter, y los HANDOFF (notas internas de sesión: fuera del repo con `git rm --cached`, que borra del índice PERO deja el archivo en disco — `rm -f` lo destruiría).
- Barrido PII con script reusable (`pii_scan.py` en el skill del proyecto): patrones de usuario, rutas `/home/`, rutas Windows, `user_...`, `sk-...`, emails, teléfonos, nombres de negocios del fundador, IPs — sobre los 257 archivos tracked. Lo que salió, se saneará: `usuario` → `usuario`, rutas reales → genéricas, nombres de negocio → "plataforma edtech (caso real)", "[REDACTED_PROYECTO]".
- **LA LECCIÓN GRANDE de esta parte**: sanear el working tree NO limpia la historia. `git log -S "cadena"` encuentra cualquier string en cualquier commit viejo. Por eso existe `git-filter-repo` (reescritura de historia) como puerta OBLIGATORIA antes de `--visibility public`. Hoy lo dejamos instalado y probado; la reescritura se hace cuando termine la campaña (filter-repo toca todo el repo y no se corre con el bench en vuelo).
- Regla de oro del commit higiénico: nunca `git add -A` mientras haya untracked intencionales — siempre paths específicos.

## 5. TEORÍA REUSABLE DE HOY

- **Las tres capas del fallo** (arnés / modelo / visibilidad): todo reporte de "el agente falló" debe decir cuál de las tres es, con evidencia del log. Sin esa separación, se "arreglan" cosas que no estaban rotas.
- **El contrato del error honesto + pista**: el error nunca miente ni auto-corrige, pero puede SUGERIR. Es el punto medio entre el silencio inútil ("no such file") y la magia peligrosa (adivinar qué quiso decir).
- **Telemetría durante, no al final** (bug 2): si tu sistema solo escribe su estado al terminar, un crash borra la evidencia.
- **Donor citado**: la pista de rutas Windows es prima hermana de lo que Hermes (MIT) hace en WSL — traducir `/mnt/c` de facto. No copiamos código; copiamos la decisión de diseño de que el arnés conoce su entorno.
- **Sanear working tree ≠ sanear historia**: la memoria de git es append-only por diseño; borrar datos sensibles de verdad requiere reescritura (filter-repo) ANTES de publicar.

## 6. EL ERROR DEL DÍA

El parser de aprobaciones de Hermes bloqueó un `python3 -c "..."` con comillas anidadas (tercera vez que pasa este patrón — quedó en el skill del proyecto como pitfall). La solución estable: escribir el script a un archivo en /tmp con `write_file` y ejecutarlo (`python3 /tmp/bench_summary.py ...`). Los comandos simples pasan; las acrobacias de quoting no. Cuando una herramienta te bloquea dos veces, no insistas con variantes — cambia de forma.

## 7. CONTINUIDAD

La campaña sigue viva en background mientras escribo esto: deepseek×tlamati cerró 45/45 ($0.65), deepseek×codex a mitad, después kimi, después {opencode, hermes}×los tres modelos. Quedan para la próxima sesión: tabla completa en EVALS.md cuando termine, reescritura filter-repo + reinstalar el binario (los fixes 1-4 de hoy NO están en el binario que la campaña está midiendo — se reinstala al cierre para no contaminar la tabla), correo real en SECURITY.md, versión 0.1.0 + PyPI, y la pregunta abierta de la clase 13 (detector de bucles de segunda capa).

**Gancho**: hoy arreglamos lo que la autopsia encontró. La próxima pregunta es más incómoda: si el modelo chico ignora recetas largas aunque las tenga en contexto... ¿el arnés puede OBLIGARLO a seguirlas? Eso es la verificación de receta — y es el siguiente techo de producto.
