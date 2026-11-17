# HANDOFF FASE D3 — MCP client stdio mínimo (el enchufe universal)
# Generado por Hermes, 17-nov-2026 (sesión 13). Punto de entrada para una
# sesión con CERO contexto: leer este archivo completo, cargar la skill
# `tlamati-harness-project` (skill_view), y seguir §5 en orden.
# Protocolo VIGENTE: un paso → entrega → OK verbal del fundador → Hermes
# auto-audita (pytest + ruff check + ruff FORMAT --check + mypy --strict +
# baseline REAL) y fusiona. Fundador NO-técnico: NUNCA pedirle revisar código;
# presentar evidencia de COMPORTAMIENTO en cristiano. Clase del día al cierre
# (edu/PROMPT_CLASE_DIARIA.md v2; la próxima es CLASE_10 — CLASE_9 ya escrita).

## 1. ESTADO ACTUAL (17-nov sesión 13, verified)
- main = 5a1c909: FASES A+B+C + D1 + D2 FUSIONADAS. CI verde (run
  44162087904, 26s).
- 325 tests verdes (17 nuevos en tests/test_plugins_d2.py), ruff+format+
  mypy strict limpios (42 archivos src).
- Baseline REAL vigente: evals/d2_check.jsonl — 5/5 OK qwen/qwen3-coder
  OpenRouter, cache_read 92-96%. ESTE es el ratchet: ningún merge baja de 5/5.
- D2 (plugins) HECHO: src/tlamati/plugins/__init__.py (~195 LOC) —
  HookRegistry con SOLO before_tool/after_tool/on_error; descubrimiento
  fail-soft (entry-points tlamati.plugins + ~/.config/tlamati/plugins +
  .tlamati/plugins + --plugins-dir, primero gana duplicados); veto solo
  ENDURECE (decisión ledger NUEVA "plugin_denied", append-only); plugin
  INTERNO de auditoría (plugins/internal/ledger_plugin.py) = migración real
  de Registry._log (tests B5 verdes SIN cambios); after_tool recibe TODA
  decisión; on_error observa sin cambiar; subagente D1 HEREDA los hooks del
  padre; prefijo byte-idéntico con/sin plugins (smoke $0: system=471
  tools=957); CLI --plugins-dir/--no-plugins + config plugins.extra_dirs;
  SECURITY.md stub creado (se completa en E4).
- CLASE_9 escrita (edu/DESARROLLO_TLAMATI_CLASE_9.md): everything-plugin —
  hooks como costuras, regla anti-speculative, migración como prueba.
  Error del día: variable local `report` colisionaba tipos con DreamReport
  del auto-dream (mypy strict la cazó) → renombrada plugin_report.
- ASTERISCO DEL FUNDADOR (decisión 17-nov sesión 13, en research/06 §final):
  OpenCrawl COMPLETAMENTE DESCARTADO como integración. Queda anotada la
  investigación "MULTIPLAYER para nuestro agente" — paso natural: DESPUÉS de
  D3. Precondición detectada: el transcript completo de subagentes NO se
  persiste (padre recibe solo final_text; intermedios del hijo solo viven en
  tool_events del ledger). Multiplayer exigiría transcript verbatim en el
  session store (C1) o store propio. NO empezar esa investigación sin pedido
  explícito del fundador.
- NUEVA RAMA DE NEGOCIO planteada por el fundador (17-nov, pendiente de
  diseño): "POOL DE TALENTO" — perfiles de programador derivados de sus
  sesiones de agente (juicio, historial, resolución de problemas) para un
  matchmaking anonimizado tipo Bumble con empresas (pool de 50k en sus
  servicios). Hermes entregó diseño inicial en esta sesión (qué medir, cómo,
  formato de perfil). SI el fundador lo ratifica, el punto de integración en
  Tlamati sería: exporter desde session store C1 + ledger B5 (datos YA
  capturados localmente) vía PLUGIN D2 (consumidor concreto, sin tocar
  núcleo) — NUNCA subir sesiones sin consentimiento explícito (privacidad:
  las sesiones contienen código y secretos; ver aviso de OpenCrawl
  "team-visible by default" como contra-ejemplo). Detalle en §3-D3b.
- Ramas viejas borrables (low prio): d2-plugins local+remota (fusionada);
  d1-subagent, c6-routing locales+remotas; b5-ledger, c1-session,
  c5-plan-mode locales; origin/b2-tools, origin/fase-b, origin/c5-plan-mode.
- Untracked intencional: evals/b5_check2.jsonl + b5_check3.jsonl (evidencia
  rate-limit 16-nov; NO borrar sin leer).
- QUÉ HAY CONSTRUIDO (src/tlamati/): core/loop+messages; providers/; tools/
  (registry con escalera deny>ask>auto + hooks D2, files, search, terminal,
  builtin); context/ (budget, compaction, instructions, routing); sandbox/
  bwrap; policy/ (config+ledger); session/store; memory/ (store+dream,
  skills); plan/; subagent/; plugins/ (D2 + internal/ledger_plugin); evals/
  runner + 5 fixtures; cli.py (subcomandos sessions/audit; flags --plan-mode
  --dream --skills-dir --workspace --no-routing --no-subagents --plugins-dir
  --no-plugins etc.).

## 2. QUÉ LEER ANTES DE CODIFICAR (orden, ~20 min)
a) Este handoff completo.
b) skill_view(name='tlamati-harness-project') — protocolo, decisiones
   zanjadas (NO re-litigar), pitfalls acumulados, política de copiado.
c) GUIA_IMPLEMENTACION.md §"FASE D" (D3) — la spec (1 línea):
   "MCP client stdio mínimo: initialize → tools/list → mapear a Tool
   registry con permission='ask' default (no confiar en MCP: treat as
   untrusted)".
d) PRD_TLAMATI.md §6 MoSCoW: F8 MCP [SHOULD].
e) DONORS D3:
   - research/06_OPENCRAWL_MULTIPLAYER_CONTEXT.md §"QUÉ SÍ PODEMOS TOMAR":
     src/mcp/overview.md de OpenCrawl = modelo de descriptions honestas
     (qué NO prueba test_connection; zero results ≠ no existe).
   - vendor/opencrawl-core/src/mcp/ (Apache-2.0): leer la forma del
     handshake, NO copiar líneas (es TS; reescribir en Python).
   - hermes-agent soporta MCP: semántica de mapeo tool-MCP → tool-local.
   - Spec oficial: modelcontextprotocol.io (JSON-RPC 2.0 sobre stdio;
     methods initialize, notifications/initialized, tools/list, tools/call).
   - ANOTACIÓN D2→D3 (research/06): OpenCrawl expone MCP por Streamable
     HTTP, no solo stdio → la config de D3 debería aceptar `url:` además de
     `command:` O al menos dejar la puerta abierta SIN construirla (regla
     anti-speculative: stdio es el consumidor concreto de hoy; documentar
     url: como extensión futura en el docstring de config).

## 3. SPEC DESTILADA
### D3 — mcp/client.py (F8, ~200-300 LOC)
- Config en tlamati.yaml (NUNCA auto-descubrir servidores: un MCP en el
  proyecto de un repo ajeno es código de terceros — mismo razonamiento que
  SECURITY.md para plugins, pero MCP además ejecuta un PROCESO):
  ```yaml
  mcp:
    servers:
      - name: rea
        command: ["npx", "-y", "@morluto/rea-mcp"]   # argv, sin shell
        # url: ...  (puerta abierta Streamable HTTP, NO construir en D3)
  ```
- Ciclo de vida: subprocess del servidor (stdio), handshake JSON-RPC
  `initialize` → notificación `notifications/initialized` → `tools/list` →
  cada tool remota se envuelve como Tool local:
  * nombre: `mcp_<server>_<tool>` (prefijo evita colisiones con el Registry
    — duplicado = ValueError fail-fast B1, mejor prefijar).
  * permission=ASK SIEMPRE (default del handoff; la escalera permite
    endurecer vía policy, NUNCA relajar a auto — ni por config).
  * produces_untrusted=True SIEMPRE (contenido de terceros → trifecta B4:
    tras consumir un resultado MCP, egreso escala a ASK).
  * input_schema = el que declare el servidor (validate_schema B1 ya lo
    valida antes de llamar — un schema roto del servidor = error honesto
    "harness bug" existente, no crash).
  * timeout por llamada (default 60s, configurable) → resultado honesto.
- `tools/call` → resultado: content como string (si el servidor devuelve
  structured content, serializar JSON); isError del protocolo → ToolResult
  is_error honesto.
- Cierre limpio: al terminar la corrida, terminar el subprocess (terminate →
  wait con timeout → kill). Un servidor colgado NUNCA cuelga la corrida.
- Fail-soft total (patrón C3/C6/D2): servidor que no arranca / handshake
  inválido / tools/list que falla = aviso honesto stderr + corrida SIN ese
  servidor. NUNCA romper.
- ORDEN DE TOOLS EN EL PREFIJO: las tools MCP se añaden AL FINAL del
  tool_list (append-only, tras delegate_task) y en orden estable por
  (server, tool) — cache sagrada. El prefijo SÍ cambia cuando hay servidores
  MCP configurados (las tools son visibles al modelo — a diferencia de los
  plugins D2): documentar que añadir/quitar servidores MCP invalida caché
  (esperado, es configuración de corrida, estable dentro de la corrida).
- Auditoría: sin trabajo extra — las tools MCP son Tools normales, el plugin
  interno D2 las registra en el ledger automáticamente (prueba #2 del
  mecanismo de plugins).
- Compaction: ¿entra a DEFAULT_COMPACTABLE_TOOLS? NO por default — un
  resultado MCP puede no ser re-obtenible (side-effect o servidor con
  estado). Dejar fuera; documentar la decisión en el docstring.
- CLI: --mcp-config PATH (override del yaml) y --no-mcp (kill switch).
  Log "[mcp] server=X tools=N" por servidor cargado.
- Tests SIN servidor real: FakeMCPServer = script Python que habla JSON-RPC
  por stdio (responde initialize/tools/list/tools/call con guion fijo).
  Unidades: handshake ok/roto, tools/list vacío, tool call ok/error/timeout,
  permission ASK innegociable, produces_untrusted marca la trifecta,
  subprocess colgado → corrida sigue, prefijo estable en corrida fría.
- SECURITY.md: actualizar §MCP con lo implementado (hoy dice "se tratarán").

### D3b (NO ES PARA ESTA SESIÓN) — exporter de talento (pool)
Diseño completo en research/07_POOL_DE_TALENTO.md (5 señales a medir,
mecánica de 3 capas, ficha de 1 pantalla, privacidad opt-in, anti-gaming,
integración vía plugin D2). Solo si el fundador lo pide explícitamente:
plugin D2 que derive métricas de sesión (session store C1 + ledger B5) a un
perfil exportable, CON consentimiento explícito (--talent-export opt-in,
nunca por default). NO codificar nada de esto en D3.

### ORDEN DE TRABAJO
D3 es la unidad de ESTA sesión (cierra la FASE D). Después: Fase E (TUI,
headless --json, evals ampliados, docs, publish v0.1). Cada unidad con: rama
nueva de main (git checkout -b d3-mcp), tests + lint trio + baseline real,
commit, push, OK verbal, merge, CI verde verificado. NO encadenar fases sin
entrega intermedia. Ventanas yolo del fundador: al corte, TERMINAR la unidad
en curso + resumen; no arrancar lo siguiente si no cabe.

## 4. ¿GASTA?
- Construir D3 + tests: $0 (FakeMCPServer local, cero red de pago).
- Baseline real tras la fase: centavos vía OpenRouter (qwen/qwen3-coder).
  Si falla: leer campo `error` del JSONL — 429/504 es upstream (pasó DOS
  veces seguidas en D2 antes del 5/5 final — paciencia, reintentar tras
  45-60s, NUNCA asumir fallo propio sin leer el error).

## 5. SIGUIENTE ACCIÓN EXACTA (sesión nueva)
1. `cd ~/code/tlamati && git checkout main && git pull` (verificar
   main=5a1c909 o posterior, CI verde `gh run list --branch main --limit 1`).
2. `uv run pytest tests/ -q` → confirmar 325 verdes ANTES de tocar nada.
3. Leer §2 (skill + GUIA + spec MCP oficial + vendor/opencrawl-core/src/mcp/).
4. `git checkout -b d3-mcp` → implementar mcp/client.py + envoltorio Tool +
   config yaml + CLI --mcp-config/--no-mcp + FakeMCPServer en tests +
   SECURITY.md §MCP actualizado.
5. Auditoría completa (§6) + baseline real (§7) + commit + push + evidencia
   de comportamiento al fundador → OK verbal → merge main → CI verde.
6. CLASE_10 al cierre (v2). Tema natural: MCP como territorio no-confiable
   — el protocolo, por qué ASK+untrusted innegociables, y la trifecta en
   acción. Continuidad: Clase 9 (costuras) → el MCP server es "un plugin
   que vive en otro proceso".

## 6. CÓMO VERIFICAR SIN GASTAR (audit local = CI exacto)
```
uv run pytest tests/ -q          # ≥325 verdes
uv run ruff check src tests
uv run ruff format --check .
uv run mypy --strict src
```
Smokes gratis: FakeMCPServer como comando real (python3 fake_server.py) en
un /tmp con tlamati.yaml de prueba + OPENROUTER_API_KEY=*** el log
"[mcp] server=... tools=N" sale a stderr ANTES del 401 (técnica Clase 7).
Prefijo: comparar ctx: system/tools con y sin --no-mcp (debe crecer solo
con servidores configurados).

## 7. BASELINE REAL (tras la fase, gasta centavos)
```
uv tool install --from . tlamati --reinstall
tlamati-eval --out evals/d3_check.jsonl
```
Esperado: `[eval] 5/5 OK`, cache_read ~90%+ (primera tarea fría ~74-92% =
normal). Ratchet: si baja de 5/5 por código propio (no 429/504), NO mergear.
OJO: evals ENJAULADOS con bwrap — los evals NO configuran servidores MCP
(ninguno debe arrancar en la suite).

## 8. PITFALLS ACUMULADOS (lista completa en la skill; nuevos de la sesión 13)
- AUDITORÍA LOCAL = pytest + ruff check + ruff FORMAT --check + mypy
  --strict. CI solo corre en main/PR (push de rama NO dispara run).
- Nombres locales genéricos en funciones largas colisionan TIPOS (report
  DreamReport vs PluginReport, sesión 13) → nombres de dominio; mypy strict
  es el que los caza.
- Tests async del proyecto: asyncio_mode=auto de pytest-asyncio — NO usar
  @pytest.mark.anyio (ruido; corre pero sobra).
- Ledger para leer en tests: NO hay led.tool_events(); usar
  Ledger.read_session(db_path, session_id) → (events, costs) con atributos
  .decision/.is_error (dataclass ToolEvent).
- `git add -A` atrapa untracked intencionales (b5_check2/3) — paths
  específicos + revisar git status/diff --cached --stat antes del commit.
- Comandos simples, uno por llamada (protocolo #6): &&-chains con verbos
  destructivos, heredocs raros y `curl | python3` disparan bloqueos falsos.
  Excepción estable: git commit -F - con heredoc.
- OpenRouter 429/504: el campo `error` del JSONL es la fuente de verdad;
  en D2 hizo falta el 3er intento — no entrar en pánico ni tocar código.
- Policy nunca relaja; tools MCP: ASK + produces_untrusted innegociables.
- Orden tools.specs() append-only; estado dinámico en primer mensaje.
- run_loop exige budget= keyword. uv cache clean tlamati si wheel raro.
- Background processes mueren con la sesión — corridas largas idempotentes.

## 9. AL CIERRE DE LA PRÓXIMA SESIÓN
CLASE_10 (edu/DESARROLLO_TLAMATI_CLASE_10.md) formato v2. Tema natural:
MCP territorio no-confiable (D3). Alternativos: el exporter de talento
(D3b, solo si el fundador arranca esa rama), multiplayer (solo si el
fundador arranca la investigación del asterisco).

-- Hermes, 17-nov-2026 sesión 13. Main = 5a1c909 (A+B+C+D1+D2 COMPLETAS,
-- CI verde, 325 tests, baseline 5/5 cache 92-96%). Falta D3 (MCP) para
-- cerrar la FASE D, luego Fase E (TUI/evals ampliados/docs/publish v0.1). --
