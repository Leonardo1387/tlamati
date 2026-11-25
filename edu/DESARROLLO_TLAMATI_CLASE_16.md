# Desarrollo Tlamati — Clase 16
## 20-nov-2026: Las cuatro capas de la memoria y la autopsia del dogfooding

Serie: Desarrollo de Tlamati (capítulo 16). Sesión 26, 20/21-nov-2026.
Anterior: CLASE_15 (ModelRouter: el modelo es un enchufe; auditoría git).

---

## 0. DÓNDE VENIMOS

En la Clase 9 volvimos Tlamati una plataforma con plugins. Hoy la pregunta
cambió de forma: ya no "¿cómo lo extiendo?" sino "¿cómo le injerto un
CEREBRO?" El fundador trajo un mapa de su propio agente (Hermes) dividido
en cuatro capas de memoria, y la tarea fue decidir qué vale la pena clonar
como comportamiento por DEFAULT del arnés... sin matar la ventaja de que
tlamati es ~2x más barato que codex.

## 1. LAS CUATRO CAPAS (el mapa que organizó toda la sesión)

Fíjate que "la memoria de un agente" no es una cosa, son cuatro:

- CAPA 1, declarativa: hechos destilados ("COMEX solo APPEND, nunca
  rebuild"). Texto plano, portable al 100%. Tlamati YA la tenía:
  ~/.local/share/tlamati/memory/MEMORY.md + USER.md.
- CAPA 2, procedimental: los workflows paso a paso (skills). Tlamati YA la
  tenía: SkillLibrary compatible con el formato de Hermes, catálogo en el
  prefijo y cuerpos bajo demanda vía skill_view.
- CAPA 3, episódica: el historial de sesiones. Aquí estaba EL HUECO:
  tlamati guarda todo en sessions.db (SQLite)... pero no podía BUSCARLO.
- CAPA 4, persona: reglas de estilo del fundador. Decisión clave: esto NO
  se clona al arnés — vive en el USER.md de cada usuario. El arnés viene
  genérico; el fundador se injerta encima.

La lección de diseño: antes de construir, verifica qué capas ya existen.
De las cuatro, tres ya estaban resueltas. Solo la 3 pedía código nuevo.

## 2. LA CORRECCIÓN DEL FUNDADOR (la teoría económica de la sesión)

La primera propuesta fue "clonar session_search Y ordenar cargar skills
agresivamente, como Hermes". El fundador la frenó con una observación que
vale oro: "eso no solo son tokens del system prompt — las ACCIONES generan
tokens en masa". Y es verdad: cargar una skill puede inyectar 100,000
caracteres al contexto (pasó en vivo esa misma sesión). Hermes es caro no
por su prefijo sino porque OBLIGA a cargar ("MUST load skills").

De ahí salió la regla que gobernó todo lo demás — **capability sin orden**:
le das al modelo la herramienta (cuesta ~100 tokens de descripción una sola
vez, cacheable) pero NO le ordenas usarla siempre. Si no la necesita, el
costo es $0. La disponibilidad es barata; la obligación es cara.

## 3. QUÉ SE CONSTRUYÓ Y CÓMO (sección replicable)

Cinco cambios, todos commiteados en ~/code/tlamati (commit 5eed650):

1. `src/tlamati/session/search.py` (NUEVO, ~200 líneas) — la tool
   `session_search` sobre el sessions.db existente. Dos modos: query
   (busca términos, devuelve top-3 sesiones con snippets) y session_id
   (devuelve una ventana ±N mensajes, NUNCA la sesión completa). Índice
   FTS5 reconstruido en cada búsqueda (DELETE+INSERT sobre DB local = ms;
   siempre fresco, cero triggers). Si el sqlite no trae FTS5, degrada a
   LIKE honestamente. Salida SIEMPRE acotada: snippets de ±150 chars,
   mensajes truncados a 200.
2. `src/tlamati/cli.py` — DEFAULT_SYSTEM += "REGLAS DE HIGIENE" (~150
   tokens): ejecuta la tool en el mismo turno en que prometes algo; nunca
   fabriques resultados que no pudiste producir; diagnostica la causa raíz
   antes de parchar. Es lo único de la capa 4 de Hermes que generaliza a
   cualquier usuario.
3. `src/tlamati/tools/terminal.py` — la description ahora DECLARA el
   contrato real: "Shell = /bin/sh (POSIX): SIN brace expansion" + estado
   de red según el sandbox (la jaula bwrap no tiene red por default).
4. `src/tlamati/memory/store.py` — seeds en los headers: guardar hechos
   declarativos nuevos, NO progreso que caduque en días; USER guarda
   correcciones en el mismo turno.
5. `src/tlamati/tui/app.py` — scroll follow-tail (ver error del día abajo).

Verificación (los comandos exactos):

```
cd ~/code/tlamati
.venv/bin/python -m pytest tests -q     # 483 passed (antes: 474; +9 nuevos)
.venv/bin/ruff check .                  # All checks passed!
.venv/bin/ruff format src/tlamati/session/search.py
```

Tests nuevos en `tests/test_session_search.py` (9): discovery encuentra la
sesión correcta con snippet, no-contaminación entre sesiones, fallback LIKE
forzando `ss._fts = False`, DB inexistente = error honesto nunca crash, y
`test_output_is_bounded` que asserts `len(out) < 5_000` — la regla del
fundador hecha test.

Ojo, detalle de instalación: el `tlamati` del PATH es un uv tool
EDITABLE (el .pth apunta a ~/code/tlamati/src), así que los fixes entran
solos en la próxima corrida. Pero un proceso YA abierto corre el código que
cargó al arrancar — por eso el dogfooding de hoy usó la versión vieja.

## 4. LA TEORÍA DETRÁS

Dos patrones reusable salieron hoy:

**Tool description = contrato.** El modelo no adivina tu entorno: lo que
no está declarado, no existe para él. Dogfooding #3 fue "no puedo ver tu
escritorio" (faltaba env_info); dogfooding #4 fue `{a,b}` creando un
directorio literal y curl exit 6 sin entender por qué (faltaba declarar
sh-POSIX y la jaula sin red). Mismo bug dos veces con distinta cara: prompt
ambiental incompleto. Donor: el propio env_info.py de tlamati, que ya lo
documentaba. La cura es siempre la misma: declarar capacidades en el
contrato de la tool, no en la buena voluntad del modelo.

**Follow-tail.** En cualquier UI que streamea (logs, chat, consola), el
auto-scroll al final SOLO debe ocurrir si el usuario YA estaba al final.
Se implementa capturando el estado ANTES de mutar el contenido:

```python
follow = t.is_vertical_scroll_end  # ¿el usuario está abajo?
t.mount(widget_nuevo)  # el contenido crece
if follow:
    t.scroll_end(animate=False)  # solo seguir si estaba abajo
```

Es el mismo patrón de `tail -f` inteligente en los visores de log serios.

## 5. QUÉ SE DECIDIÓ NO CONSTRUIR

No se clonaron: el estilo del fundador (capa 4 → USER.md, no al arnés),
delegate_task/cronjobs/clarify (features de plataforma, no de arnés mínimo),
el out-of-band steering (requiere gateway). Y sobre todo: NO se copió el
"MUST load skills" de Hermes — la autopsia lo confirmó empíricamente:
nemotron corrió 51 turnos sin cargar NINGUNA skill y produjo un PRD de 245
líneas con grounding correcto. La postura capability-sin-orden funciona.

## 6. LA AUTOPSIA (dogfooding #4, calificación 7/10)

La sesión continuó de 11 a 51 turnos (131 mensajes). Lo bueno: PRD real
(~/code/puente-latam/docs/PRD.md, 12.9KB, métricas numéricas, las 5 ramas
correctas); diagnóstico de arquitectura VERIFICADO contra search.py ("el
motor usa filtro_ciudad, una rama a la vez; el cruce multi-FAISS no existe
aún"); y cuando el fundador lo acusó de alucinar, no se defendió — verificó
con curl. Lo malo: ~8 turnos chocando contra la jaula sin red (curl,
python, huggingface, tres evidencias ignoradas); bashisms repetidos
(`source` no existe en sh, `${VAR:0:20}` tampoco); y dijo "no hay internet
en este entorno" cuando la afirmación correcta era "mi terminal corre
enjaulado SIN red" — conflicto de comunicación, no de hechos. Los fixes 3 y
4 de hoy atacan exactamente eso. Dejó basura en proyecto-legal
(_test_puente_latam.py) — borrada a mano tras la sesión.

Y el error del día del lado del arnés: el scroll del TUI arrastraba la
pantalla aunque el usuario subiera a leer (scroll_end incondicional en dos
puntos: _note y _flush_stream). Detectado por el fundador en vivo, fixeado
con follow-tail, y costó además recalibrar un test de compaction
(Budget 1250→1350) porque la description nueva de terminal engordó el
prefijo ~90 tokens — el pitfall "prefijo crece → budget se recalibra" ya
estaba documentado en el propio test; se siguió el patrón establecido.

## 7. LA PREGUNTA ABIERTA

**Los seeds de memoria dicen "guarda hechos nuevos"... pero nemotron no
guardó nada en 51 turnos. ¿Bastará el seed en el header, o hace falta que
el arnés sugiera activamente (un nudge al final de la corrida: "¿algo que
recordar?")? La próxima corrida de dogfooding es el experimento: dato nuevo
en vivo, y se revisa si MEMORY.md creció solo.**
