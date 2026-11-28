# CHANGELOG

Formato: secciones por release; lo no liberado vive en "Unreleased".
Los cambios que rompen la superficie estable (STABILITY.md) se etiquetan
`BREAKING` y siguen la regla de deprecation documentada allí.

## Unreleased

### Agregado

- **Muro de turnos interactivo (T3)** — default `max_turns` 60→90 (loop,
  CLI, TUI, config). Al topar el muro el loop emite el evento nuevo
  `turn_limit_reached` {turns, max_turns}; la TUI abre un modal "Seguir 30
  turnos más (s) / Cerrar (c)" mid-run (donor: QuasiAskScreen) y la
  extensión ocurre DENTRO de la misma corrida: `LoopState` intacto — la
  ventana cuasi-stall (T1) y el detector exacto NO se reinician ("seguir"
  nunca evade detectores; dos tests lo protegen). Evento
  `turn_limit_extended` {extra, max_turns} al conceder. Headless nunca
  cuelga: sin handler el muro cierra honesto (stop=max_turns, exit 1) y, si
  hay summarizer, imprime un resumen de cierre en stderr.

- **Detector de cuasi-stall (T1)** — el agente que reintentaba la misma
  estrategia con mutaciones menores (timeout 90→110, un flag extra, ruta
  cambiada) quemaba el presupuesto entero: el detector exacto
  (`stall_repeats`, firma idéntica) nunca lo cazaba. Ahora el loop firma
  cada turno NORMALIZADO (dígitos→`#`, whitespace colapsado) y compara
  similitud (`SequenceMatcher`) contra una ventana deslizante. Umbrales:
  ≥5 cuasi-idénticas en las últimas 15 (similitud ≥0.85) → aviso SOFT
  inyectado al modelo como user message al final del turno (prefijo
  cacheable intacto); ≥8 → ASK al usuario. Configurable vía
  `stall.quasi_similarity` / `stall.quasi_window` / `stall.quasi_warn_count`
  / `stall.quasi_ask_count` en `tlamati.yaml` (`quasi_similarity: 0`
  desactiva). En la TUI el ASK abre un modal seguir/redirigir/parar
  (donor: ApproveScreen); en headless degrada a corte honesto
  `stop_reason=stall` con exit code 8. "seguir"/"redirigir" limpian la
  ventana y continúan — NUNCA hay corte duro por cuasi-similitud (el
  detector exacto sigue operando independiente). Eventos nuevos:
  `quasi_stall_warning`, `quasi_stall_ask`, `quasi_stall_stop`.

- **examples/skills/** — tres skills de apps creativas saneadas para
  publicación (clon + sustitución de rutas/nombres de proyecto; los
  originales locales quedan intactos): `unreal-engine-playbook` (UE 5.8
  como herramienta: iluminación, cámaras, archviz, VR, PCG),
  `blender-game-art-playbook` (pipeline de assets low-poly→game-ready) y
  `creative-apps-mcp-bridges` (puentes MCP WSL⇄Windows medidos en
  producción). Verificación: grep de patrones privados = 0 hits.

## v2.1.0 (2026-11-26)

### Agregado

- **Visión nativa v2.1** — `ImageBlock` en el waist del loop: `read_file`
  ve imágenes, `--image` en CLI las adjunta al primer mensaje. Los adapters
  las serializan al formato nativo de cada proveedor (OpenAI content blocks
  / Anthropic image blocks).

### Arreglado

- **Retry con backoff en errores transitorios del proveedor** — un rate
  limit del upstream (p.ej. Alibaba vía OpenRouter) mataba la corrida con
  respuesta vacía (`stop=error`, `in=0 out=0`): el loop nunca consultaba
  `ProviderError.retryable`. Ahora `_stream_one_turn` reintenta hasta 4
  veces con backoff exponencial 4s·2^n + jitter ante 429/5xx/transporte o
  mensajes transitorios en `MessageEnd(error)` ("rate limit", "overloaded",
  "upstream error", in-flight credits). Errores deterministas no se
  reintentan. Nuevo evento `retry` {attempt, delay_s, error} para TUI/JSON.

## v2.0.0 (2026-11-26)

Release de especialización creativa: el arnés ya habla con aplicaciones
creativas (Blender, Unreal Engine) DENTRO del loop, no alrededor.

### Agregado

- **MCP Streamable HTTP** (`mcp.servers[].url`) — el transporte que faltaba
  para el MCP oficial de Epic (HTTP/SSE-only). Carnet `Mcp-Session-Id`
  automático con renegociación si el editor reinicia, llamadas en serie
  (restricción medida del servidor de Unreal), header `Origin`. Verificado
  contra Unreal Engine 5.8.4 vivo: 53 toolsets navegables con 3 meta-tools
  (`list_toolsets`/`describe_toolset`/`call_tool`). Dogfooding completo:
  nivel construido desde un DXF importado, limpieza de escenario y spawn
  de actores, todo vía arnés.
- **web_fetch** — lectura de URLs (GET, solo texto, cap 200 KB cortado en
  la fuente con marcador honesto). ASK + `produces_untrusted` SIEMPRE;
  corre fuera de la jaula bwrap (la puerta de red es el permiso).
- **ctrl+c detiene al agente** sin matar la app + **steering** a mitad de
  turno (mensajes out-of-band mientras el modelo trabaja).
- **ctrl+c copia selección** en reposo (ya no sale de la TUI; ctrl+q sale).
- (Ya incluido en el tag v0.1.0 remapeado: endurecimiento sandbox
  `bwrap --clearenv` + whitelist fail-closed — las API keys del proceso
  padre ya NO son visibles dentro de la jaula.)
- `tlamati audit`: eventos MCP registrados en el ledger append-only como
  cualquier tool (decisión + args + hash de resultado).

### Cambiado

- README: instalación vía `pip install git+https://...` (PyPI aún no);
  documentación de `web_fetch` y `mcp.servers` con `url:`; ejemplo de
  config MCP corregido (lista de servidores, no mapa).
- Sanitización completa de historia pública (filter-repo) + poda de ramas
  de desarrollo pre-sanitización del remoto.

### Notas de la release

- Salto 0.1.0 → 2.0.0 por convención de producto del maintainer (el
  breaking SEC.1 de red del sandbox, documentado en STABILITY.md, y la
  superficie nueva de v2: red + MCP HTTP).
- Suite: 690 tests, ruff + mypy strict verdes, CI GitHub Actions.

## v0.1.0

- Primera release taggeada (tag `v0.1.0`).
