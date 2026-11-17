# Desarrollo Tlamati — Clase 11
## 17-nov-2026: Dos caras nuevas — el modo robot y la pantalla viva

En la clase 10 cerramos la Fase D dejando una pregunta abierta: cuando el repo sea público, ¿qué ve primero un extraño — la pantalla bonita o un comando que resuelve algo real? Hoy el fundador contestó esa y tres preguntas más, y con esas respuestas construimos DOS unidades completas de la Fase E: E2 (el modo máquina) y E1 (la cara humana). Empecemos por cómo se le pide una decisión a alguien que no es técnico, porque eso también es ingeniería.

## 1. CUATRO DECISIONES, EXPLICADAS EN CRISTIANO

El handoff traía cuatro preguntas abiertas. La regla del proyecto: el fundador decide, Hermes recomienda y explica. Cada pregunta se presentó con tres piezas: qué genera tu respuesta (la consecuencia concreta), las opciones, y una recomendación con razones. Las cuatro quedaron zanjadas: E2 antes que E1; evals ampliados con benchmark contra opencode usando el mismo modelo; repo público al terminar E4 pero con una auditoría de seguridad completa como última puerta; y la librería de pantalla (Textual) como extra opcional.

Fíjate en un detalle: ninguna pregunta era "¿qué código escribo?" sino "¿qué orden, qué alcance, qué fecha, qué peso de instalación?". Eso es lo que un fundador debe decidir. El cómo técnico lo audita Hermes con tests y evidencia. Este reparto se llama **separación de concerns** (separación de responsabilidades) y aplica igual entre dos módulos de código que entre dos personas.

## 2. E2: EL AGENTE COMO CIUDADANO DE CI

Hasta hoy, `tlamati -p "..."` hablaba en cristiano: texto suelto a la pantalla. Un humano lo entiende, pero un script de CI (integración continua: el robot que corre pruebas en cada cambio) no. E2 añade el flag `--json`: ahora la salida es **JSONL** — JSON Lines, un objeto JSON por renglón, como una bitácora donde cada línea es una ficha independiente que se puede leer sin cargar todo el archivo.

El vocabulario de eventos: `init` (qué corrida es), `text` (lo que dice el modelo), `tool_run`/`tool_result` (herramientas), `budget` (cuánto contexto va), y al final SIEMPRE `result` con todo el resumen: stop_reason, tokens, error y exit_code. Los **exit codes honestos** son la otra mitad: cada final tiene su número — 0 terminó bien, 1 se acabaron los turnos, 3 presupuesto excedido, 4 error, 5 abortado, 6 el modelo se rehusó, 7 tope de tokens. Y la regla de oro: una razón desconocida devuelve 4 (error), NUNCA 0. Un programa jamás debe afirmar éxito ante algo que no entiende — es la misma filosofía fail-closed (fallar cerrado, como una puerta que se traba sin electricidad en vez de abrirse) de la escalera de permisos de la Fase B.

El donor declarado: hermes-agent (MIT). Aprender ingeniería es leer a los grandes y reimplementar en limpio.

### Lo que se construyó y cómo verificarlo (E2)

```
# archivo nuevo: contrato de eventos + mapa de exit codes (~110 LOC)
src/tlamati/core/json_events.py
# modificado: flag --json + emisor cableado al loop
src/tlamati/cli.py
# 14 tests nuevos con FakeProvider (sin red, sin costo)
tests/test_headless_json_e2.py
```

```
uv run pytest tests/ -q        # 359 verdes tras E2 (345 previos + 14)
```

El smoke real ($0, técnica de la Clase 7): con una API key falsa la corrida muere en 401, PERO el stream JSONL ya salió completo y el proceso terminó con código 4 — la evidencia de comportamiento precede al proveedor. La prueba de que no rompimos nada: el evento budget mostró `system=471 tools=957`, exactamente los mismos números del smoke de D3. El **prefijo cacheable** (la parte inicial del prompt que el proveedor guarda en caché y cobra barato) quedó intacto — "la caché es sagrada" sigue siendo la regla número uno del proyecto.

## 3. E1: LA CARA DEL AGENTE

Después del merge de E2 (baseline real re-corrido: 5/5, caché ~95%, CI verde), tocó la pantalla. **Textual** es la librería estándar de Python para interfaces de terminal (TUI): dibuja cajas, botones y texto con formato usando caracteres, sin navegador ni ventanas del sistema. Su mecánica clave para nosotros: una clase `App` con método `compose()` que declara qué widgets existen, y `run_test()` — un driver virtual que levanta la app en memoria y permite simular teclas desde un test. Por eso los 13 tests de la TUI no necesitan terminal real ni cuestan un centavo.

`tui/app.py` (~513 LOC) monta la pantalla SOBRE `run_loop` tal cual: el loop no sabe que existe la TUI; la TUI solo consume los eventos y aporta un aprobador interactivo. Eso es el **narrow waist** (cintura estrecha) del proyecto: un punto angosto por donde todo pasa, y cada superficie nueva se enchufa ahí sin tocar el corazón. Chat multilínea, respuestas en markdown que aparecen en vivo, barra de costo siempre visible (la métrica del PRD a la vista), panel de sesiones, y lo más importante: cuando una herramienta pide permiso (ASK), se abre un modal con el diff REAL contra el disco — rojo lo que se quita, verde lo que se pone — y tres botones: permitir una vez (a), permitir siempre esta sesión (A), rechazar (r). Esc = rechazar. "Siempre" es solo comodidad tuya: nunca modifica la política de permisos, porque la escalera solo endurece.

Decidimos NO cablear en la TUI lo que ya existía en headless (routing, plugins, MCP, subagentes): v1 honesto, mejor menos y funcionando que mucho y a medias. Y el arranque es con red de seguridad: `tlamati` sin argumentos solo abre la pantalla si hay terminal interactiva de verdad (`isatty`); un script de CI sigue viendo el help de siempre.

### Verificación (E1)

```
uv run pytest tests/ -q        # 372 verdes (359 + 13 de TUI)
uv run mypy --strict src       # limpio, 47 archivos
uv run tlamati                 # en TU terminal real: se abre la pantalla
```

## 4. EL ERROR DEL DÍA: LA RÁFAGA QUE SE COMÍA PALABRAS

El smoke de la TUI mostró algo raro: el texto acumulado decía "PRIMERO SEGUNDO TERCERO" pero el widget terminaba mostrando solo "PRIMERO". Diagnóstico con un wrapper que imprimía el estado tras cada llamada: cada `Markdown.update()` de Textual devuelve un AwaitComplete (una tarea asíncrona programada "para cuando se pueda"). Al llamarlo en ráfaga — delta tras delta sin pausa — decenas de reconstrucciones del documento quedaban en vuelo y se pisaban entre sí.

El arreglo es un patrón clásico de interfaces: **throttle** (estrangulador): los deltas solo marcan "hay cambios pendientes" y un temporizador de 150 ms vuelca el acumulado — una reconstrucción a la vez, en orden — más un vuelco final forzado al cerrar turno. Y su test de regresión: 52 deltas en ráfaga, el texto final debe empezar en "PRIMERO" y terminar en "TERCERO". Cuando encuentres un bug así, la reparación sin el test que lo reproduzca es medio arreglo: el test es lo que impide que regrese.

Bonus de vocabulario Textual que quedó en los pitfalls: no existe el color `$red` (es `$error`); un CSS inválido tumba TODA la app en tests; `push_screen_wait` solo corre dentro de un worker; y NUNCA nombres métodos propios `_on_*` — ese prefijo pertenece al framework. Es la tercera vez que el proyecto tropieza con colisión de nombres (report en D2, loaded en D3, _on_ en E1): los nombres de dominio, siempre.

## 5. LA PREGUNTA QUE QUEDA ABIERTA

Con E2 y E1 fusionados en main (CI verde, 372 tests), sigue E3: cinco exámenes nuevos de dificultad media-alta y, el plato fuerte que pidió el fundador, el **benchmark harness-vs-opencode** — las mismas 10 tareas, el mismo modelo (qwen3-coder), dos arneses distintos. La pregunta para el próximo capítulo: cuando dos herramientas usan el mismo cerebro, ¿qué tan grande es la diferencia que hace el cuerpo? Los números de la investigación (Vercel 80→100%, Letta 59 vs 41) dicen que mucha. E3 es donde Tlamati demuestra la suya — o descubre, con datos, dónde no.

---

— Hermes, sesión 15 (17-nov-2026). Main = e5ca031 + handoff E3 (ecad3f3),
CI verde run 44185714863, 372 tests, baseline REAL 5/5 (evals/e2_check.jsonl).
E2 y E1 FUSIONADOS. Sigue E3a: fixtures nuevas (ver HANDOFF_FASE_E3.md).
