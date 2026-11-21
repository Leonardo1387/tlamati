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
- **Contenido no-confiable (MCP, D3)**: los servidores MCP son territorio
  NO-confiable por construcción. Reglas innegociables:
  - NUNCA se auto-descubren: solo servidores declarados por el dueño en
    `tlamati.yaml` / `--mcp-config` (un MCP en el repo de un tercero es
    código ajeno que además EJECUTA UN PROCESO — mismo razonamiento que los
    plugins, agravado).
  - Cada tool remota se envuelve como `mcp_<server>_<tool>` con
    `permission=ASK` SIEMPRE (policy puede endurecer a deny, nunca relajar)
    y `produces_untrusted=True` SIEMPRE (tras consumir un resultado MCP, el
    egreso escala a ASK — trifecta letal B4).
  - Timeout por llamada (default 60s) y cierre terminate→wait→kill: un
    servidor colgado nunca cuelga la corrida (fail-soft total, aviso
    honesto + corrida sin él).
  - Los resultados MCP NO entran a la microcompactación por default (pueden
    no ser re-obtenibles: side-effects o servidor con estado).
  - La auditoría los cubre sin trabajo extra: son Tools normales → el plugin
    interno D2 registra cada llamada en el ledger.

## Reporting

Report vulnerabilities PRIVATELY — do not open a public issue.

- **GitHub Private Vulnerability Reporting** (preferred): on the repo page,
  Security → Report a vulnerability.
- **Email**: leonardo@convrsations.ai — include "tlamati security"
  in the subject.

Scope we care most about: sandbox escapes from the bwrap jail, permission
escalation paths (anything that turns ASK/DENY into silent AUTO), audit-ledger
tampering, plugin/MCP trust-boundary violations, and prompt-cache poisoning
(history edits before the last breakpoint).

We follow a 90-day disclosure window: we ask for a private report first and
coordinate a fix + advisory; credit to reporters who want it.
