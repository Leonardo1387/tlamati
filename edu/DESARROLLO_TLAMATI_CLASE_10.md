# CLASE 10 — MCP: cómo enchufar herramientas de terceros sin darles tus llaves

Serie: Desarrollo de Tlamati (capítulo 10). Sesión 14, 17-nov-2026.
Anterior: CLASE_9 (everything-plugin — hooks como costuras, auditoría migrada).

---

## 0. DÓNDE VENIMOS

En la Clase 9 aprendimos a colgar comportamiento nuevo DENTRO del proceso de
Tlamati (plugins: código que corre en el mismo programa, con la confianza del
dueño). Hoy cerramos la FASE D con el complemento: conectar herramientas que
viven en OTRO proceso, escritas por gente que no conocemos. Eso es MCP
(Model Context Protocol) — piénsalo como el USB de los agentes: un enchufe
estándar para que cualquier programa externo ofrezca herramientas, sin que
cada agente tenga que reescribir su integración.

Y la clase entera gira alrededor de una sola idea de seguridad: el enchufe es
universal, pero lo que entra por él es territorio NO-confiable.

## 1. EL PROBLEMA (la escena cotidiana)

Imagina que contratas a un plomero que nunca has visto (el servidor MCP: un
programa de terceros que el harness arranca como subprocess). Le abres la
puerta de tu casa (le das stdin/stdout), y te ofrece sus servicios
(tools/list: "sé destapar caños, sé reparar fugas"). Un mal diseño dejaría
que el plomero trabaje sin supervisión y que lo que te diga ("encontré esto,
manda este correo") se tome como verdad. El buen diseño: cada servicio que
haga te lo pregunta primero (permission=ASK), y todo lo que te reporte se
marca como "dicho por un desconocido" (produces_untrusted) — si después el
agente quiere enviar datos afuera, se le vuelve a preguntar (la trifecta B4
que ya conoces de la Clase 5).

## 2. QUÉ ENTENDIMOS HOY

- MCP es JSON-RPC 2.0 sobre stdio: mensajes de una línea en formato JSON, con
  `id` para preguntas-que-esperan-respuesta y sin `id` para avisos que no la
  esperan (notifications). El ciclo de vida son 4 pasos: `initialize`
  (¿hablamos el mismo idioma?), `notifications/initialized` (ok, empezamos),
  `tools/list` (¿qué sabes hacer?), `tools/call` (haz esto).
- Un servidor colgado NO puede colgar la corrida: cada llamada tiene timeout
  (default 60s) y al cerrar: terminate → wait 5s → kill. Lo probamos con un
  servidor falso que hace `time.sleep(3600)`: Tlamati respondió "expiró tras
  1s" y siguió tan campante.
- Las herramientas MCP SÍ crecen el prefijo cacheable (a diferencia de los
  plugins D2, que eran invisibles al modelo): medido en el smoke, tools pasó
  de 1448 a 1528 tokens con un servidor de 2 tools configurado. Es esperado y
  está documentado: es configuración de corrida, estable dentro de la corrida.

## 3. QUÉ SE CONSTRUYÓ Y CÓMO (sección replicable)

Archivos clave:
- `src/tlamati/mcp/client.py` (~354 LOC): MCPClient (subprocess + handshake +
  call con timeout), `parse_mcp_config` (fail-soft: entrada inválida = aviso,
  nunca crash), `make_mcp_tools` (envoltorio Tool con ASK+untrusted),
  `load_mcp_servers`/`close_mcp`.
- `tests/fake_mcp_server.py`: servidor MCP de juguete que es un PROCESO REAL
  hablando JSON-RPC, con 8 modos de falla (bad_handshake, garbage_init,
  hang_on_call, die_immediately...).
- `tests/test_mcp_d3.py`: 20 tests nuevos → suite total 345 verdes.
- `src/tlamati/cli.py`: flags `--mcp-config PATH` y `--no-mcp`; bloque de
  carga tras D1 (append-only al final del tool_list).
- `SECURITY.md` §MCP: de "se tratarán" (promesa) a lo implementado (contrato).

Comandos para replicar la verificación (todo $0, sin red de pago):

```bash
cd ~/code/tlamati
uv run pytest tests/ -q              # 345 passed
uv run ruff check src tests          # lint
uv run ruff format --check .         # formato
uv run mypy --strict src             # tipos estrictos: 44 archivos, 0 errores
```

Smoke $0 (la técnica de la Clase 7: key inválida → la corrida muere en el
proveedor con 401, PERO todo lo de MCP ya se ejecutó y dejó su log):

```bash
mkdir -p /tmp/d3_smoke && cd /tmp/d3_smoke
printf 'mcp:\n  servers:\n    - name: fake\n      command: ["python3", "/home/usuario/code/tlamati/tests/fake_mcp_server.py", "ok"]\n' > tlamati.yaml
OPENROUTER_API_KEY=*** tlamati -p "hola" --quiet
# → [mcp] server=fake tools=2   (sale ANTES del 401 = evidencia real)
# → con --no-mcp la línea no sale
```

La prueba fail-soft real (servidor muerto + vivo en la misma config):

```bash
OPENROUTER_API_KEY=*** tlamati -p "hola" --quiet --mcp-config roto.yaml
# → [mcp] servidor 'muerto' no cargó: el servidor cerró stdout durante
#    initialize — corrida SIN él
# → [mcp] server=vivo tools=2   (el sano sigue funcionando)
```

El baseline REAL (esto sí gasta centavos): `tlamati-eval --out
evals/d3_check.jsonl` → primer intento 4/5 (HTTP 504 upstream en
'conversor': Venice abortó tras un 429 de DeepInfra — el campo `error` del
JSONL es la fuente de verdad, NO es nuestro código). Retry tras 60s → OK.
Corrida completa final: **5/5 OK**, cache_read 2560-4496 por tarea. Ratchet
de Osmani cumplido: merge a main (aafb595), CI verde run 44169349318 (34s).

## 4. LA TEORÍA DETRÁS

**Patrón: zero-trust en fronteras de proceso.** Un plugin (Clase 9) es código
que TÚ instalas: corre en tu proceso, con tus credenciales, y el modelo de
confianza es "confías en él como en tu propio código". Un servidor MCP es
peor: es un PROCESO DE TERCEROS que el harness arranca y cuyo stdout entra
directo al contexto del modelo. La regla general (y la encuentras en
firewalls, en Kubernetes, en los navegadores con su same-origin policy):
todo lo que cruza una frontera de confianza se MARCA y se re-verifica en la
siguiente salida. En Tlamati eso son dos flags innegociables por construcción
—`permission=ASK` y `produces_untrusted=True`— que la policy puede endurecer
(nunca relajar). Donors: la spec oficial (modelcontextprotocol.io) para el
protocolo; vendor/opencrawl-core/src/mcp/ (Apache-2.0, TypeScript) para
leer la FORMA del handshake sin copiar líneas; hermes-agent (MIT) para la
semántica de mapeo tool-MCP → tool-local; y su overview.md como modelo de
descriptions honestas.

**Herramienta: subprocess con pipes.** `asyncio.create_subprocess_exec(*argv)`
(sin shell: argv directo, cero riesgo de inyección) devuelve un proceso con
stdin/stdout como tuberías. Escribir una línea JSON + `\n` y leer líneas hasta
encontrar la que lleva TU `id` es todo el protocolo. El detalle fino: envolver
la lectura en `asyncio.wait_for(..., timeout)` convierte un servidor colgado
en un error honesto en vez de un programa congelado.

**Patrón: fail-soft con evidencia.** Igual que skills (C3), routing (C6) y
plugins (D2): cada fallo se anota en un reporte y se avisa por stderr, y la
corrida sigue con lo que sí funcionó. Un sistema que se rompe entero por una
pieza opcional es frágil; uno que degrada con avisos honestos es confiable.

## 5. QUÉ DECIDIMOS NO CONSTRUIR (decir que no también es clase)

- `url:` (Streamable HTTP, lo que usa OpenCrawl): la puerta quedó ABIERTA y
  documentada en el docstring, pero NO construida — regla anti-speculative:
  stdio es el consumidor concreto de hoy.
- Auto-descubrimiento de servidores (lo que hacen otros agentes con
  .mcp.json del repo): rechazado de plano. Un MCP en el repo de un tercero
  es código ajeno que además EJECUTA UN PROCESO en tu máquina. Solo lo que
  el dueño declara en tlamati.yaml o --mcp-config.
- Microcompactar resultados MCP: NO entraron a DEFAULT_COMPACTABLE_TOOLS —
  un resultado MCP puede no ser re-obtenible (side-effects, servidor con
  estado). Borrarlo del historial sería mentir.

## 6. EL ERROR DEL DÍA (otra vez el mismo villano)

En `cli.py` nombré una variable local `loaded` dentro del bloque MCP. Pero
200 líneas más arriba YA existía `loaded = store.load_session(...)` de tipo
StoredSession. mypy --strict las vio como la misma variable con dos tipos
distintos y tronó: "Incompatible types in assignment". Es el MISMO error de
la sesión 13 (`report` vs DreamReport): en funciones largas, los nombres
genéricos colisionan. Arreglo: `loaded_mcp`. La lección que ya está en el
handoff: nombres de dominio, nunca genéricos, y mypy strict es el que los caza.

Error bonus (de herramienta): `tlamati-eval --task conversor --out
evals/d3_check.jsonl` SOBRESCRIBE el archivo completo — me dejó un JSONL de
una sola línea y hubo que re-correr el baseline entero para tener la
evidencia limpia de 5/5. Nota mental: --out siempre escribe el archivo
completo, no hace merge.

## 7. LA PREGUNTA QUE QUEDA ABIERTA

Con D3 aterrizado, la FASE D CIERRA (subagentes + plugins + MCP: las tres
formas de extender un agente). Sigue la FASE E: TUI con Textual, headless
--json para CI, evals ampliados, docs y el publish de v0.1 (el repo pasa de
privado a público). La pregunta para el próximo capítulo: **cuando Tlamati
sea público, ¿qué debe ver un extraño en los primeros 5 minutos — una TUI
bonita o un `tlamati -p` que resuelve algo real?** La respuesta decide el
orden de E1 vs E2.

---

— Hermes, sesión 14 (17-nov-2026). Main = aafb595, CI verde run 44169349318,
345 tests, baseline REAL 5/5 (evals/d3_check.jsonl). FASE D COMPLETA.
