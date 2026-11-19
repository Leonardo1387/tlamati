# Desarrollo Tlamati — Clase 13
## 19-nov-2026: El delta como argumento y la autopsia de un video reprobado

En la clase 12 aprendimos a medir: benchmarks ajenos, fixtures propias, la carrera justa. Hoy esa maquinaria nos devolvió dos cosas: números reales de los 4 arneses corriendo el mismo cerebro, y — mucho más valioso — una autopsia. Porque resulta que la mejor manera de encontrar bugs de producto no es un benchmark: es usar tu propio producto para algo de verdad, verlo fallar, y leer las cenizas. Eso se llama dogfooding (comer tu propia comida de perro: usar tú mismo lo que vendes), y hoy cobró su primera víctima famosa: un video doodle que salió mal.

## 1. LA ESCENA: EL VIDEO QUE SALIÓ CORTADO

El fundador agarró tlamati por primera vez en solitario, en la TUI, y le pidió lo que Hermes ya le había hecho bien antes: un video doodle 9:16 estilo NVIDIA a partir de un MP3 de 87.8 segundos. El resultado: video reprobado, audio cortado a los 50 segundos, y la sesión frenada en seco a los 20 turnos.

Aquí viene la parte importante del método: no adivinamos. Leímos la evidencia forense que el propio arnés guarda. tlamati tiene dos bitácoras (bases de datos que registran todo lo que pasa): `~/.local/share/tlamati/sessions.db` guarda los 197 mensajes de la sesión, y `~/.local/share/tlamati/audit.db` guarda cada llamada a herramienta con su costo. La autopsia completa: 98 llamadas al modelo, 2.74 millones de tokens de entrada, 94% de cache, $0.33, 31.6 minutos.

El veredicto fue sorprendente: el arnés NO perdió por tokens ni por dinero. Perdió por dos bugs de producto. Y los dos los encontramos con SQL básico sobre esas bitácoras, a costo cero:

1. La TUI ignoraba `--skills-dir`. El fundador había pasado la bandera correcta, pero el código de la TUI tenía una lista vacía escrita a mano donde debían ir las skills. Sin la skill del video, el modelo nunca recibió la receta (que manda usar Whisper sobre el MP3 para obtener los tiempos reales), inventó los tiempos a mano, y cortó el audio a 50s porque su plan decía 50s desde antes de escuchar el audio.
2. La TUI tenía `max_turns = 20` hardcodeado (escrito a fuego en el código). El fundador topó el muro y tuvo que reiniciar a mano, sin explicación.

Fíjate en la cadena: un bug pequeño (un flag que no se cablea) causa un fallo gigante (un video reprobado). Por eso la autopsia vale más que la queja.

## 2. QUÉ SE CONSTRUYÓ HOY Y CÓMO (sección replicable)

Arreglamos los dos bugs y además construimos una idea nueva del fundador. Los comandos exactos de la sesión:

```
git checkout -b e3d-tui-skills          # rama nueva para el PASO A
uv run pytest tests/ -q                 # suite completa (404 tests al final)
uv run ruff check .                     # linter: estilo y errores comunes
uv run ruff format --check .            # formateador: verifica sin tocar
uv run mypy --strict src/               # tipos estrictos en todo el código
git push -u origin e3d-tui-skills       # subir rama para respaldo/CI
```

Archivos clave tocados (todos bajo `~/code/tlamati/`):

- `src/tlamati/tui/app.py` — la TUI. Ahora recibe las skills por bandera Y por configuración, igual que el modo headless. Antes: lista vacia a fuego.
- `src/tlamati/memory/skills.py` — aquí vive la ceremonia cero: la función `default_skill_roots()` ahora añade `~/.hermes/skills` al final SIEMPRE que exista. Prueba real: `tlamati` a secas ve las 47 skills de Hermes sin ninguna bandera.
- `src/tlamati/core/loop.py` — el corazón (el ciclo que llama al modelo y ejecuta herramientas). Aquí entró el detector de estancamiento y el yolo, que explico abajo.
- `src/tlamati/cli.py` — las banderas nuevas `--max-turns` (default subió de 20 a 60) y `--stall-repeats` (default 3), con resolución bandera > config > default.
- `tests/test_stall_e3d.py` — 13 tests nuevos, todos a $0 con proveedores simulados (FakeProvider: un modelo de mentira que responde según un guion escrito).

La verificación de que hoy quedó bien: `uv run pytest tests/ -q` → 404 passed, y el trío de lint limpio. La evidencia de comportamiento (la que ve el fundador, que no revisa código): tlamati a secas lista 47 skills; el bucle muerto se corta en el turno 3 con mensaje honesto; al topar el muro la TUI ofrece "continúa" o "resumen".

## 3. LA TEORÍA DETRÁS: DETECTOR DE PROGRESO vs MURO CIEGO

El fundador hizo hoy una observación de diseño que vale más que cualquier línea de código: "50 turnos pueden ser un mismo bucle en el que está atorado... más bien poner un límite cerrado a esos bucles que no generan ningún avance, y límite con pregunta para bucles que sí avanzan".

Traducido a principio general: **un presupuesto de turnos es un proxy burdo del progreso**. Contar turnos no distingue al agente que trabaja del que gira en círculos. La solución en cualquier sistema de este tipo es un detector de progreso. El nuestro es deliberadamente tonto y por eso es bueno: firma del turno = nombre de herramienta + argumentos exactos, serializados a JSON canónico (con las llaves ordenadas, para que `{a:1,b:2}` y `{b:2,a:1}` den la misma firma). Misma firma 3 turnos seguidos = bucle muerto = corte duro con `stop_reason="stall"`.

La belleza está en lo que NO cuenta como bucle: editar el mismo archivo con contenido distinto cambia los argumentos, luego cambia la firma, luego es progreso. El patrón legítimo "edita → prueba → edita" nunca se castiga. Cero falsos positivos por construcción, porque la firma se compara byte a byte, no con heurísticas.

El donor (de quién copiamos la idea, que así se aprende ingeniería): Hermes fuerza un resumen automático a los 90 turnos. Nosotros lo adoptamos pero invertimos la decisión: al topar el muro, tlamati OFRECE "escribe 'continúa' o 'resumen'" y el humano decide. Reusa el mismo ModelSummarizer de la Fase A6 (modelo barato con cadena de respaldo), y el gasto del resumen se cuenta al ledger (turn=-1, fuera de corrida) porque la contabilidad honesta es innegociable en este proyecto.

Y el modo yolo (`--max-turns 0`) enseña otra lección de diseño: quitar UN techo no debe quitar TODOS los techos. En yolo el muro desaparece pero el detector de bucles sigue activo y el presupuesto de contexto sigue siendo sagrado. Regla reusable: los límites defensivos se quitan uno por uno y explícitamente, nunca en cascada.

## 4. LOS NÚMEROS DEL BENCH (el delta como argumento)

La corrida 4 arneses × 15 tareas × 3 réplicas con el MISMO cerebro (qwen3-coder vía OpenRouter) terminó en 3 de 4 arneses. Regla de honestidad de la clase 12: los números crudos, con sus asteriscos.

- tlamati: 37/45 corridas OK, $0.18, 1.39M tokens de entrada, 92% cache, 16.9 min. ASTERISCO GRANDE: sus 8 fallos son TODOS errores del proveedor upstream ("Provider returned error", rc=4) — OpenRouter se indigestó a media corrida. Donde el modelo pudo trabajar, resolvió: al-menos-una-réplica 14/15.
- opencode: 42/45, $0.49, 4.05M tokens, 95.6% cache. Fallos reales de modelo: aritmética del conversor ×2.
- codex: 43/45, $0.86, 7.35M tokens, 96.1% cache, 38 min. Único fallo: la edición quirúrgica grande ×2 por timeout de 600s.
- hermes: no corrió en esta vuelta — decisión del fundador de dejarlo al final (es el más tardado).

El argumento publicable, provisional hasta repetir con upstream sano: tlamati resolvió con 5.3× menos tokens que codex y 2.9× menos que opencode, y corrió 2.2× más rápido que codex. Ese es el delta del PRD medido, no prometido. La campaña de modelos (flash → deepseek → kimi con tlamati+codex, y hermes al cierre) sigue corriendo en background con un orquestador idempotente que diseñamos hoy: vigila, corta, salta lo completado, y se puede relanzar si muere.

## 5. QUÉ DECIDIMOS NO CONSTRUIR

La opción B de skills (`tlamati skills link` manual) murió en favor de la ceremonia cero automática: el fundador eligió cero comandos. El onboarding tutorial para primerizos (P3 de su visión) se documentará como F16 en el PRD pero NO se implementa ahora. Y la campaña de modelos se redujo: tlamati+codex solamente (opencode se queda con su dato de qwen-coder), porque el dato que importa es arnés × modelo, y cada arnés extra son dólares y horas.

## 6. EL ERROR DEL DÍA

Cuatro tests viejos se rompieron... y estaba bien que se rompieran. Quemaban turnos llamando la MISMA herramienta con los MISMOS argumentos (para probar el muro), y el detector nuevo — haciendo exactamente su trabajo — los cortaba antes por "stall". El test que fallaba no era el código: era la suposición del test. Arreglo: dar avance real a los guiones (offset variable en read_file). Sub-error dentro del error: en un test de compactación el offset variable cambió la salida de la lectura y rompió el umbral que el test medía; solución fina: campo inerte `_tick` en los argumentos — cambia la firma sin cambiar la salida. Moraleja doble: cuando un detector nuevo rompe tests viejos, pregunta primero si el test era realista; y cuando parches un test, cuida no alterar la variable que justamente mide.

Queda abierta para mañana: **¿debe el detector de estancamiento mirar solo la firma exacta, o conviene una segunda capa más suave — mismo tool, args parecidos, resultados de error idénticos — para cazar al modelo que varía un byte del argumento para seguir girando en círculos?**
