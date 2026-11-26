# CHANGELOG

Formato: secciones por release; lo no liberado vive en "Unreleased".
Los cambios que rompen la superficie estable (STABILITY.md) se etiquetan
`BREAKING` y siguen la regla de deprecation documentada allí.

## Unreleased

(vacío)

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
