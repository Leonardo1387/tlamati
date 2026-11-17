# CLASE 9 — Everything-plugin: cómo hacer un programa extensible sin romperlo

Serie: Desarrollo de Tlamati (capítulo 9). Sesión 13, 17-nov-2026.
Anterior: CLASE_8 (delegación con límites — el subagente read-only con topes).

---

## 0. DÓNDE VENIMOS

En la Clase 8 Tlamati aprendió a contratar ayudantes (subagentes) con
presupuesto y poderes limitados. Hoy cerramos la Fase D con la pieza que
convierte un programa cerrado en una PLATAFORMA: los plugins. La idea es
que terceros (o nosotros mismos mañana) puedan colgar comportamiento nuevo
—auditar, vetar, observar— SIN tocar el código del núcleo.

Y no es teoría: la prueba de fuego fue tomar algo que YA funcionaba (la
auditoría B5, atornillada dentro del Registry) y MIGRARLO a plugin. Si la
costura está mal hecha, los 22 tests de B5 se rompen. Siguieron verdes sin
tocarles una coma.

## 1. EL PROBLEMA (por qué los plugins mal diseñados destruyen programas)

Un harness de agentes tiene puntos donde "pasan cosas": antes de ejecutar
una herramienta, después, cuando algo truena. La tentación es abrir TODOS
los puntos posibles como extensibles (el modelo de gemini-cli: 10+ eventos
de hook). El problema: cada hook es un contrato público que ya no puedes
cambiar, y un hook sin consumidor real es especulación — código que se
mantiene solo y no sirve a nadie.

La regla que usamos (donor: hermes, "anti-speculative"): SOLO hooks con un
consumidor concreto HOY. Para D2 son exactamente 3:
- `before_tool` → consumidor: vetos de política de equipo.
- `after_tool` → consumidor #1 REAL: la auditoría del ledger (B5).
- `on_error` → consumidor: observabilidad de fallos.

Y una regla de seguridad que no se negocia: un plugin SOLO PUEDE ENDURECER.
`before_tool` puede vetar (devolver un string de error), pero NUNCA puede
aprobar ni relajar permisos — el invariante B4 ("policy nunca relaja")
sigue intacto aunque instales 50 plugins.

## 2. LO QUE HICIMOS, PASO A PASO

### Paso 1 — Verificar el piso
```
cd ~/code/tlamati && git checkout main && git pull
gh run list --branch main --limit 1   # CI verde (26s)
uv run pytest tests/ -q               # 308 verdes ANTES de tocar nada
git checkout -b d2-plugins
```

### Paso 2 — Leer los donors antes de escribir
- `vendor/gemini-cli/packages/core/src/hooks/types.ts`: su enum
  HookEventName tiene 10 eventos (BeforeTool, AfterTool, BeforeAgent,
  SessionStart...). Lo leímos para aprender la FORMA (registro + runner +
  agregador) y para decidir qué NO copiar: 10 hooks sin consumidores =
  el anti-patrón que nuestra regla evita.
- `vendor/opencrawl-core/plugins/` (MIT): valida que el formato de
  descubrimiento por archivos simples sigue siendo el estándar.

### Paso 3 — El módulo nuevo: src/tlamati/plugins/__init__.py (~195 líneas)

Herramientas: write_file para crear, patch para cirugía, ruff+mypy como
red de seguridad tras cada paso.

Tres piezas:

(a) **HookRegistry**: tres listas de funciones + tres métodos `fire_*`.
Cada fire envuelve la llamada del plugin en try/except: un plugin que lanza
se reporta honesto por stderr y se ignora — un plugin NUNCA rompe el
harness (fail-soft, mismo patrón que skills C3 y routing C6).

(b) **load_plugins**: descubre en orden estable — entry-points de paquetes
instalados (`importlib.metadata`, stdlib puro, cero deps), luego
`~/.config/tlamati/plugins/*.py`, luego `.tlamati/plugins/*.py` del
proyecto, luego dirs del CLI. Duplicados: primero gana + aviso. Rotos:
aviso + reporte + seguir. Devuelve un PluginReport (loaded/failed/
duplicates) = evidencia honesta para el log y los tests.

(c) **Plugin interno de auditoría**
(plugins/internal/ledger_plugin.py): una función de 20 líneas que registra
el after_tool que escribe tool_events. Se registra SIEMPRE que el Registry
recibe un ledger — no es descubrible ni desactivable (auditar no es
opcional).

### Paso 4 — La migración real (el momento de verdad)

En `tools/registry.py`, el método `execute` tenía una función interna
`_log` que escribía directo al ledger en cada salida. La reemplazamos por:
```python
def _log(decision, result, logged_args=None) -> ToolResult:
    self.hooks.fire_after_tool(name, args_efectivos, decision, result)
    return result
```
El `_log` ya NO sabe nada del ledger — solo dispara el hook. Quien sabe del
ledger es el plugin interno. Comportamiento observable: idéntico (por eso
B5 sigue verde sin cambios). Eso es una migración exitosa: mover el mecanismo
sin mover la semántica.

Añadimos también el punto de veto en execute (tras validar schema, ANTES
del permission gate) con decisión NUEVA "plugin_denied" (la lista de
decisiones del ledger es append-only: nunca reescribimos valores viejos), y
el fire de on_error en el except del run.

### Paso 5 — CLI y herencia al subagente

Flags `--plugins-dir` (repeatable) y `--no-plugins`, más config
`plugins.extra_dirs` en tlamati.yaml. Log: `[plugins] N cargado(s), M
fallido(s)`.

Detalle fino: los hooks se crean ANTES del bloque D1 en cli.py, y el
delegate_task los recibe — el subagente HEREDA los plugins del padre. Si un
plugin veta `terminal` para ti, también está vetado dentro de tu ayudante.
La escalera solo endurece, también hacia los lados.

### Paso 6 — Auditoría completa + humo gratis + baseline real
```
uv run pytest tests/ -q          # 325 verdes (17 nuevos)
uv run ruff check src tests && uv run ruff format --check . && uv run mypy --strict src
```
Humo $0 (técnica de la Clase 7): proyecto falso /tmp/d2_smoke con un plugin
bueno y uno sin `register`, API key dummy. La corrida muere con 401 en el
proveedor PERO antes el stderr ya mostró la evidencia:
```
[plugins] plugin 'malo' (.../malo.py) ignorado: no define register(hooks)
[plugins] 1 cargado(s), 1 fallido(s)
ctx: system=471 tools=957 ...
```
Y lo crítico: con `--no-plugins` el ctx fue BYTE-IDÉNTICO (system=471
tools=957) — los plugins no tocan el prefijo, la caché sagrada intacta.

Baseline real (ratchet de Osmani): `tlamati-eval --out evals/d2_check.jsonl`
→ dos intentos con 504/429 upstream (leer el campo `error` del JSONL:
"rate-limited upstream" = OpenRouter, no nuestro código), tercer intento
**5/5 OK**, cache_read 92-96%.

## 3. LA TEORÍA DETRÁS

**Patrón: Everything-plugin / arquitectura de costuras (seams).**
Una "costura" es un punto del programa donde el comportamiento puede
cambiarse desde fuera sin editar el núcleo. El patrón completo tiene 4
reglas que vimos en acción:

1. **Descubrimiento declarativo**: el núcleo no importa plugins a mano;
   los DESCUBRE (entry-points + convenciones de directorios). Donor:
   setuptools/pytest — todo el ecosistema Python se enchufa así.
2. **Fail-soft en la carga**: un plugin roto se reporta y se ignora; el
   núcleo arranca siempre. Donor: nuestro propio C3/C6 (skills y routing),
   y los loaders de gemini-cli.
3. **Contratos mínimos**: pocos hooks, con semántica precisa (¿puede
   vetar? ¿solo observar?). Contra-donor: gemini-cli con 10 eventos — más
   superficie = más contratos que congelar. Regla anti-speculative de
   hermes: cada hook nace con un consumidor real.
4. **El mecanismo se prueba MIGRANDO**: la prueba de que una costura sirve
   es mover código existente a ella sin cambiar comportamiento observable.
   Los tests viejos verdes sin edits = especificación ejecutable de la
   migración. Donor: los refactors "behavior-preserving" de Fowler.

**El error del día**: en cli.py nombré una variable local `report` (el
PluginReport del cargador de plugins) en una función donde MÁS ABAJO ya
existía `report` (un DreamReport del auto-dream C2). Python no se queja
(ambas son locales, la segunda reasigna), pytest tampoco (rutas distintas),
pero **mypy --strict** lo cazó al instante: "Incompatible types in
assignment (DreamReport vs PluginReport)". Lección doble: (a) en funciones
largas los nombres genéricos colisionan — usa nombres de dominio
(`plugin_report`); (b) esta es exactamente la razón por la que el trio de
lint es gate de merge y no adorno. Mención honoraria: escribí los tests con
`@pytest.mark.anyio` cuando el proyecto usa `asyncio_mode=auto` de
pytest-asyncio — corrían igual, pero era ruido; fuera.

**Métrica de la clase**: +630 líneas, 17 tests nuevos, 325 totales,
prefijo +0 bytes (los plugins son invisibles al modelo), baseline 5/5.

## 4. CONTINUIDAD

- Cerramos con el asterisco del fundador en research/06: OpenCrawl
  DESCARTADO como integración; investigación "multiplayer" anotada para
  post-D3, con su precondición descubierta en vivo: hoy el padre recibe
  solo el resumen del hijo (final_text); el transcript completo del
  subagente NO se persiste en el session store. Para single-player basta
  (re-delegar + ledger); para multiplayer sería bloqueante.
- **Siguiente capítulo (CLASE_10 / Fase D3): MCP — el enchufe universal.**
  Tlamati aprenderá a hablar con servidores externos de herramientas
  (Model Context Protocol) como cliente stdio mínimo: initialize →
  tools/list → cada tool remota entra al Registry con permission=ASK y
  produces_untrusted=True (territorio no-confiable, trifecta B4). Con D3
  aterrizado, cualquier memoria compartida externa —incluido un servidor
  tipo OpenCrawl— se conecta sin tocar el núcleo.

— Hermes, sesión 13 (17-nov-2026). Main = 5a1c909, CI verde, 325 tests.
