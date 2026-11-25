# SECURITY.md — Tlamati

Sin marketing: en un harness OSS los límites explícitos son feature. Este
documento dice qué protege cada capa, qué NO protege y por qué es una
decisión y no un descuido.

## La matriz honesta (auditoría FASE SEC, 21-nov-2026)

Toda restricción de seguridad del harness cayó en una de tres categorías:

### REAL — protege de verdad

- **La trifecta letal** (`policy/` + `tools/registry.py`): cuando un turno
  consume contenido no-confiable (resultado web, MCP, o terminal con red —
  tools marcadas `produces_untrusted`), las tools de EGRESO escalan AUTO→ASK.
  Es la defensa anti-exfiltración tras leer contenido web no confiable: el
  modelo puede leer la web libremente, pero para SALIR (curl POST, ssh, etc.)
  después de consumirla, un humano aprueba.
  - TUI: modal once / **always** / reject. "Always" dura la corrida y aplica
    solo a esa tool; NUNCA toca la Policy (la escalera solo endurece).
  - Headless: `--approve-tool NAME` pre-aprueba tools ASK (`'*'` = todas;
    default: nada — nunca yolo silencioso).
- **MCP siempre ASK + untrusted**: los servidores MCP son territorio
  no-confiable por construcción. Cada tool remota se envuelve como
  `mcp_<server>_<tool>` con `permission=ASK` y `produces_untrusted=True`
  SIEMPRE (la policy puede endurecer a deny, nunca relajar).
- **Escalera de permisos `deny > ask > auto`**: overrides, patrones y plugins
  `before_tool` solo pueden ENDURECER. Nada relaja permisos en caliente.
- **El agente SABE su entorno** (SEC.3): el system prompt declara si el
  terminal tiene red o no, con la MISMA fórmula que usa el tool
  (`net_efectiva = sandbox_net or not sandbox`). Prompt y tool nunca se
  contradicen (test de punta a punta lo bloquea). Un agente que no sabe que
  tiene red miente al usuario ("no puedo") — eso también es un fallo de
  seguridad honesta.

### ILUSORIO / PARIDAD — no protege, y es decisión documentada

- **La jaula bwrap NO es una frontera de filesystem.** Los file tools
  (read_file, write_file, patch...) corren LIBRES y en AUTO, y `_resolve`
  (files.py) resuelve cualquier ruta absoluta — write_file bypasea la jaula
  por completo. DECISIÓN de paridad Hermes: el harness no promete confinar
  filesystem; promete AUDITAR (ledger append-only) y REVISAR (trifecta).
  La jaula del terminal es una **red-de-accidentes-shell** (protege de `rm -rf`
  accidental fuera del workdir, no de un agente malicioso con file tools).
- **API keys NO visibles al comando enjaulado** (endurecido 25-nov): la jaula
  arranca con `--clearenv` y solo recibe una whitelist de variables inocuas
  (PATH/HOME/LANG/TERM/...). Fail-closed: `OPENROUTER_API_KEY` y cualquier
  otro secret del env del padre quedan fuera del comando enjaulado. El
  harness llama al modelo FUERA de la jaula; los comandos enjaulados no
  necesitan credenciales. OJO: esto aplica al tool *terminal* — los file
  tools y plugins corren en el proceso del harness (puntos siguiente y
  anterior), donde el env sí es visible.
- **Plugins sin sandbox**: corren en el proceso del harness. Son código del
  DUEÑO de la máquina (mismo modelo que hermes-agent). Un plugin de un repo
  ajeno (`.tlamati/plugins/` clonado) es código de terceros con tus
  credenciales: revisa antes de correr `tlamati` en repos que no conoces.

### FRENA SIN PROTEGER — eliminado

- **Red OFF por defecto** (estado anterior a SEC.1): era un segundo candado
  redundante que NO añadía defensa real (la trifecta ya cubre exfiltración)
  y solo frenaba trabajo legítimo (pip, railway, curl, git clone).
  **BREAKING CHANGE 21-nov-2026**: el default de red pasó OFF→ON. La jaula
  sigue disponible (`--no-sandbox-net` / `sandbox: {net: false}`) para quien
  quiera el candado extra, pero ya no se impone por omisión. Debe registrarse
  en STABILITY.md (fase G1).

## Sandbox y flags (referencia rápida)

```yaml
# config.yaml (~/.config/tlamati/ o tlamati.yaml del proyecto)
sandbox:
  enabled: true   # jaula bwrap para el tool terminal
  net: true       # red dentro de la jaula (default ON desde SEC.1)
```

Precedencia: **flag explícito > config > default**. Los flags nacen
"sin opinión" (`None`) para que la config mande cuando el usuario no dice
nada (`resolve_sandbox_flags` en cli.py, núcleo único compartido por
headless y TUI).

| Flag | Efecto |
|---|---|
| `--no-sandbox` | apaga la jaula bwrap (avisa `[sin sandbox]`, nunca silencio) |
| `--sandbox-net` / `--no-sandbox-net` | red ON/OFF dentro de la jaula |
| `--approve-tool NAME` | headless: pre-aprueba tool ASK (equivalente al "siempre" de la TUI) |
| `--plan-mode` | explora → aprueba plan → ejecuta (mutuamente exclusivo con `--approve-tool '*'`) |

Degradación honesta: sin binario `bwrap`, el terminal corre SIN jaula pero el
CLI lo avisa al arrancar y el resultado del tool lleva la nota. El usuario
siempre sabe si está protegido o no.

## Modelo de confianza (capas)

- **Subagentes (D1)**: el hijo NUNCA es más poderoso que el padre — toolset
  read-only por construcción (whitelist ∩ permission AUTO), profundidad
  máxima 1, topes duros de turnos y tokens que bloquean ANTES de gastar.
  Los hooks de plugins del padre se heredan al hijo (solo endurecen).
- **MCP (D3)**: nunca auto-descubrimiento (solo servidores declarados por el
  dueño en `tlamati.yaml` / `--mcp-config`). Timeout por llamada (default
  60s) y cierre terminate→wait→kill: un servidor colgado nunca cuelga la
  corrida. Los resultados MCP NO entran a la microcompactación por default.
- **Auditoría (B5)**: todo tool_event y turn_cost queda en un ledger SQLite
  append-only (`tlamati audit`). Plugin INTERNO no desactivable; los eventos
  de subagentes viajan al mismo db con prefijo `<padre>:sub-NN`. Nada de
  ejecuciones invisibles.

## Reporting

Report vulnerabilities PRIVATELY — do not open a public issue.

- **GitHub Private Vulnerability Reporting** (preferred): on the repo page,
  Security → Report a vulnerability.
- **Email**: leonardo@convrsations.ai — include "tlamati security"
  in the subject.

Scope we care most about: permission escalation paths (anything that turns
ASK/DENY into silent AUTO), audit-ledger tampering, plugin/MCP
trust-boundary violations, prompt-cache poisoning (history edits before the
last cache breakpoint), and trifecta bypasses (egress after untrusted
content without ASK). Note: "sandbox escape via file tools" is NOT in scope
— it is documented behavior (parity decision, see ILUSORIO above).

We follow a 90-day disclosure window: we ask for a private report first and
coordinate a fix + advisory; credit to reporters who want it.
