# GUÍA DE IMPLEMENTACIÓN TLAMATI — paso a paso
v0.1 · 14-nov-2026 · Compañera de PRD_TLAMATI.md
> Para Hermes: ejecutar con el skill writing-plans + subagent-driven-development, fase por fase.

## 0. Inventario real (verificado en esta máquina, 14-nov-2026)
### Con lo que YA contamos
| Recurso | Estado |
|---|---|
| WSL Ubuntu, 890GB libres en / (1TB disco) | OK |
| Python 3.12.3 + uv 0.11.16 (crea/instala venvs y apps CLI) | OK |
| Node v22.22.2 / npm 10.9.7 | OK |
| git 2.43, gh CLI 2.95 (auth OK), tmux, gcc 13.3 | OK |
| tiktoken, pydantic v2, openai SDK ya en pip global | OK |
| REA `rea@6.7.0` via `npx rea-agents` (funciona; capabilities: Linux OK, macOS n/a) | OK |
| Hermes Agent v0.18.2 con fuente completa en ~/.hermes/hermes-agent (MIT, 263k★) — DONANTE de patrones: adapters, toolsets, compaction, approval | OK |
| Claude Code 2.1.92 instalado npm (cli.js 59MB minificado) — blanco REA conductual | OK |
| Codex 0.133 instalado + fuente Rust vendor/codex (Apache-2.0) | OK |
| Clones en vendor/: codex, opencode, qwen-code, gemini-cli, grok-build, DeepSeek-Reasonix, harness2, claude-code + hermes local — 8 sustratos de estudio | OK |
| LLM acceso: OpenRouter (Anthropic claude-sonnet-4-6 vía base_url), GPU alquilada por hora (coder 80B + q35b), Ollama configurable | OK |
| Regla de negocio: latencia ≤30s, calidad intocable, $0 de dependencias de pago | OK |

### Falta descargar (pocos; TODO gratis/open-source)
1. `sudo apt install ripgrep bubblewrap sqlite3` ← ESTO REQUIERE TU CLAVE SUDO (intenté: "a password is required"). 3 pkgs: ~6MB.
2. `uv venv + uv add` en tlamati/: textual (TUI), rich, jsonschema, httpx, aiosqlite, pytest, ruff, mypy. (0 deps de pago)
3. Opcional v2: `npm i -g @zed-industries/agent-client-protocol` no — ACP es protocolo, se implementa sobre stdio JSON-RPC, sin pkg. Tree-sitter (`pip tree-sitter + grammars`, Apache) solo cuando toque búsqueda semántica.
4. gh repo: crear <usuario>/tlamati (privado → público al v0.1).

### NO se necesita ni se usará
- Ningún SDK de Anthropic/OpenAI pago adicional; todo por HTTP contra OpenRouter/Ollama/GPU-alquilada.
- Docker no es requisito (sandbox = bwrap; docker como backend opcional v2).

---
## FASE A — Semilla (F1+F3+F10 mínimo). ~1 jornada partida
Objetivo demo: `tlamati -p "arregla X"` resuelve un bug real en un repo de prueba con modelo local y presupuesto.

A1. Scaffolding: `uv init --package tlamati` → estructura del PRD §7. pyproject con `[project.scripts] tlamati`, ruff+mypy+pytest, CI GitHub Actions (lint+test). LICENSE Apache-2.0 + NOTICE.md.
  Verificar: `uv tool install --from . tlamati && tlamati --version`.
A2. `core/messages.py`: tipos internos (Message, ToolCall, ToolResult, Usage). Este es el NEGOLO: todo adapter traduce a/desde aquí.
A3. `providers/base.py`: Protocol `stream(messages, tools) -> AsyncIterator[Event]`. Implementar OpenAICompat (cubre OpenRouter+Ollama+vLLM; config: base_url+api_key+model) y AnthropicMessages (formato messages API nativo, tool_use/tool_result, cache_control breakpoints) — copiar la SEMÁNTICA de ~/.hermes/hermes-agent/agent/anthropic_adapter.py (MIT), no copiar líneas si no aporta.
  Test: contra `ollama` mock server (httpx MockTransport) validando normalización de tool_calls y que un refusal/finish_reason raros mapea a error tipado.
A4. `core/loop.py` ≤500 LOC: while turno → stream → ejecutar tool calls → append → repeat, hasta stop o presupuesto. Sin clases base raras: función + dataclass de estado. Interjección v1: SIGINT pone mensaje de usuario pendiente al siguiente turno.
A5. `context/budget.py`: conteo de tokens por modelo (cache de tiktoken + aproximador para modelos sin encoding), umbrales 80/95%, `context_breakdown` por sección (system/tools/history — patrón hermes).
A6. `context/compaction.py`: resumen con MODELO BARATO configurable (fallback chain), retención de tool outputs recientes, y regla de oro: la compactación RECONSTRUYE el sufijo, jamás muta el prefijo cacheable.
A7. Primer eval E2E: 5 tareas de terminal-bench-lite propias (fixtures/), runner `tlamati-eval` → JSONL con éxito/tokens/costo. Correr con qwen3-coder vía OpenRouter y Ollama local. Guardar baseline.

## FASE B — Herramientas + permisos (F2+F5). ~1.5 jornadas
B1. `tools/registry.py`: Tool(name, schema, permission, run, sandboxable). El schema via `jsonschema` validación ANTES de ejecutar. Ladder de footprint (regla hermes AGENTS.md): primero extensión, último new core tool.
B2. Herramientas: read_file (con line numbers + truncado honesto), write_file, edit (fuzzy-match estilo patch de hermes: 9 estrategias), search_files (rg subprocess), terminal (pty-less foreground primero; background+poll v1.1).
B3. `sandbox/bwrap.py`: jail de ejecución para terminal/edit: `--ro-bind / / --bind <workdir> <workdir> --dev/dev --unshare-net por defecto`; flag `--net` = permiso separado. Perfil default read-only fs + writable workdir. (Si apt de A4… digo del §0.1 no está instalado, pedirte la clave aquí.)
B4. `policy/`: política TOML-style en config.yaml: herramienta→auto|ask|deny + patrones de ruta/comando. Aprobación en TUI y en headless con `--yolo/--approve-…` (default NUNCA yolo). Regla trifecta: si el turno consumió tool result `untrusted=True`, cualquier tool de salida (network, env-mail) escala a ask aunque estuviera auto.
B5. `policy/ledger.py`: SQLite append-only: turno, tool args, resultado hash, costo, decisión de permiso. `tlamati audit --session <id>`.

## FASE C — Sesión + memoria + skills (F4+F6). ~1 jornada
> Destilada 16-nov (sesión 8) desde research/02 + research/05: cada decisión lleva su fuente.

C1. `session/store.py`: SQLite (aiosqlite): sessions, messages, summaries, usage. `tlamati resume`, `--continue`.
  - Esquema PREPARADO para compactación: tabla `summaries` (ventana→resumen, modelo usado) + columna `retention` por tool_result (flag sobrevive-ventana, fuente: codex `compact_retained_tool_outputs.rs`) + `content_cleared` booleano para microcompactación (fuente: qwen `microcompact.ts` — marcador honesto "[Old tool result content cleared]", anti-colisión regex derivada de la constante productora).
  - Invariante cache: toda edición de historia ocurre DETRÁS del último breakpoint o vía cache-edits nativos (fuente: mecanismo `clear_tool_uses_20250919`/`cache_edits` de Anthropic que usa CC, doc 05). Regla de re-obtenibilidad: lo que se puede volver a leer del disco (read_file, search, skill_view) es microcompactable; lo irreproducible (terminal output, resultados de red) lleva retention=true.
C2. `memory/`: MEMORY.md (hechos) + USER.md (preferencias), inyectados en prefijo cacheable; tool `memory` (add/replace/remove) batch atómico.
  - Techos DUROS (fuente: CC vía REA, eventos tengu_team_mem_sync_* y team_mem_entries_capped → hay CAP de entradas; doc 05 §2): límite de líneas/chars por archivo + cap de entradas; al llenarse el agente CONSOLIDA (fusiona/borra) en el mismo batch — nunca acumula.
  - Scopes mínimos v1: user + proyecto (CC tiene 4: user/project/local/team — los otros 2 son v2 si hay demanda).
  - AUTO-DREAM (fuente: CC doc 05 §3, confirmada por qwen — extracción de memoria es planner separado): job asíncrono al CERRAR sesión que destila aprendizajes a MEMORY.md. NUNCA en turno caliente. v1 = simple (1 llamada a modelo barato con el transcript); el hook del ledger B5 da el transcript gratis.
  - Reglas-semilla Osmani (fuente: doc 05 §1, builder de CC offset 11,666,006): rutas absolutas, no recapitular, no emojis — van como texto inicial de MEMORY.md.
  - Estabilidad de prefijo: metadata dinámica viaja fuera del prompt (header HTTP / mensaje), jamás muta el prefijo byte a byte (fuente: doc 05, CC attribution header).
C3. `memory/skills/`: SKILL.md (frontmatter YAML + cuerpo), inyección por escaneo de nombres (trigger = descripción en system prompt, carga por tool `skill_view`). Formato 100% compatible con hermes (~/.hermes/skills leíbles directo = migración de librería con 1 flag). Salida de skill_view microcompact-whitelisted (re-obtenible del disco, igual que CC con search_memory).
C4. AGENTS.md loader: merge repo→global→override; versionado en prefijo (hash de contenido) para estabilidad de cache.

## FASE C+ — Plan-mode + routing (PRD F1 MUST + F6b SHOULD, sin fase hasta 16-nov)
C5. Plan-mode: tool `enter_plan_mode`/`exit_plan_mode` — explorar→aprobar→ejecutar (fuentes: qwen enter/exitPlanMode, gemini enter/exit-plan-mode; research/02 hallazgo #5 "primitivas de arnés bueno"). En plan-mode: tools de escritura/terminal → deny por policy (B4 ya da el mecanismo, 0 código nuevo de permisos). `ask_user` + `complete_task` como primitivas (gemini/qwen).
C6. Workspaces+routing.md (F6b): agentes-como-carpetas, routing de 3 capas (fuente: research/03).

## FASE D — Subagentes + plugins + MCP (F9+F11+F8). ~1.5 jornadas
D1. `subagent/spawn.py`: task aislada, toolset reducido READ-ONLY default, max_turns + max_cost, resultado = resumen (patrón delegate de hermes; límites = patrón Raschka #6).
D2. `plugins/`: entry-point `tlamati.plugins` + descubrimiento `~/.config/tlamati/plugins/*.py` (patrón Reasonix "everything is a plugin" + hook registry de gemini: before_tool/after_tool/on_error; SOLO hooks con consumidor concreto — regla anti-speculative hermes).
D3. MCP client stdio mínimo: initialize → tools/list → mapear a Tool registry con permission="ask" default (no confiar en MCP: treat as untrusted). Servidores locales de tu ecosistema (REA como MCP server ya lo soporta).

## FASE E — Superficies + eval completo + pulido OSS (F7+F10). ~1 jornada
E1. TUI Textual: input multilínea, stream con markdown, diff viewer con approve/reject, barra de costo/tokens por turno (context_breakdown visible), panel de sesiones.
E2. Headless: `tlamati -p "..." --json` (JSONL events) para CI; exit codes honestos.
E3. Suite eval: ≥20 tareas (terminal/file/git/reasoning/latencia), 3 modelos objetivo (sonnet-4 vía OR, coder80B en GPU alquilada, qwen3-ollama). Matriz ARNÉS×modelo documentada en EVALS.md — nuestro argumento del Paso 1: muestra el delta de arnés.
E4. Docs: README (por qué/qué NO es), ARCHITECTURE.md (narrow waist + invariantes), CONTRIBUTING.md, SECURITY.md (trifecta + reporting), CHANGELOG + release-please.
E5. Publicar: `gh repo create tlamati --public`, tag v0.1.0, post HN/foros.

---
## FASE F — REA sobre privativos (transversal, al final de cada fase)
REA (morluto/rea, MIT, `npx rea-agents`) sobre objetivos LOCALES (solo bundles que YA instalaste legalmente):
- F-a. `rea analyze-javascript-application` contra ~/.nvm/…/@anthropic-ai/claude-code/cli.js: mapear (a) su system prompt/cache breakpoint strategy, (b) su tool catalog real, (c) qué envía ANTES de tu primer prompt (la métrica 33k). Salida: research/rea/claude-code-*.md. PROHIBIDO copar código: solo arquitectura/behavior → checklist de PRD.
- F-b. Cursor: sin bundle → análisis conductual (docs + foros) → research/rea/cursor-conductual.md.
- F-c. Contra código FUENTE abierto (sí reutilizable con licencia): opencode compaction.ts, codex compact_token_budget.rs, qwen bwrap-execution.ts, reasonix plancontract — leer → `docs/anatomia/<tema>.md` con referencia exacta (repo:path). REA se usa para confirmar que el comportamiento compilado coincide con la fuente.
- F-d. harness2: ejecutar 1 benchmark jb con 1 config (necesita sus runners; pip -e '.[render]') para entender el ciclo Propose–Probe–Compose ANTES de prometer "modo v2".

## Orden de trabajo y dependencias
A→B→C→D→E con F intercalado. B y C pueden paralelizar (subagentes por fase, spec-review primero). No saltar A7: si una fase rompe el eval baseline, se detiene y se revisa (ratchet de Osmani: cada fix nace de un fallo observado).

## Decisiones abiertas (necesitan TU elección, no urgente)
1. ¿Tlamati se come a Hermes como arnés personal, o coexisten (Hermes plataforma, Tlamati laboratorio OSS)? Afecta cuanto reutilizamos de hermes-agent vs re-escribimos limpio.
2. ¿Go/No-Go con Reasonix (MIT, fork bienvenido pero Muerto Oficial 12-nov): usarlo como esqueleto Go o Python desde cero? (mi recomendación: Python desde cero ~core, Reasonix como referencia de arquitectura plugin; razón: tu toolchain y la de hermes es Python, y WSL+Rust/Go añade friction de builds).
3. Nombre final del paquete PyPI (tlamati puede estar tomado; verificar `pip index versions tlamati`).
