# SECURITY.md — Tlamati

(stub honesto creado en D2; se completa en E4 con reporting de vulnerabilidades)

## Modelo de confianza

- **Tools del modelo**: escalera de permisos `deny > ask > auto` (B4). Policy
  NUNCA relaja: overrides y patrones solo pueden endurecer. La "trifecta
  letal" (contenido no-confiable consumido + tool de egreso + aprobación)
  escala a ASK cuando el turno consumió resultados marcados
  `produces_untrusted` (web, MCP, terminal con red).
- **Sandbox**: el tool `terminal` corre enjaulado con bubblewrap (B3):
  filesystem read-only fuera del workdir, red OFF por defecto
  (`--sandbox-net` opt-in). Sin bwrap, degradación honesta `[sin sandbox]`.
- **Subagentes (D1)**: el hijo NUNCA es más poderoso que el padre — toolset
  read-only por construcción (whitelist ∩ permission AUTO), profundidad
  máxima 1, topes duros de turnos y tokens que bloquean ANTES de gastar.
  Los hooks de plugins del padre se heredan al hijo (solo endurecen).
- **Plugins (D2)**: corren SIN sandbox, en el proceso del harness. Son código
  del DUEÑO de la máquina — el mismo modelo de confianza que hermes-agent:
  si instalas un plugin, confías en él como confías en tu propio código.
  Fuentes de descubrimiento: entry-points de paquetes instalados,
  `~/.config/tlamati/plugins/`, `.tlamati/plugins/` del proyecto y
  `--plugins-dir`. Un plugin de un repo ajeno (`.tlamati/plugins/` clonado)
  es código de terceros ejecutándose con tus credenciales: revisa antes de
  correr `tlamati` en repos que no conoces. Un plugin `before_tool` solo
  puede VETAR (endurecer), nunca aprobar ni relajar permisos.
- **Auditoría (B5)**: todo tool_event y turn_cost queda en un ledger SQLite
  append-only (`tlamati audit`). La auditoría es un plugin INTERNO no
  desactivable; los eventos de subagentes viajan al mismo db con prefijo de
  sesión `<padre>:sub-NN`. Nada de ejecuciones invisibles.
- **Contenido no-confiable (MCP, D3)**: los resultados de servidores MCP se
  tratarán como `produces_untrusted` + permission ASK por default.

## Reporting

(Pendiente E4: canal de reporte de vulnerabilidades.)
