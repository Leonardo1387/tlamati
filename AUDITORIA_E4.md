# AUDITORÍA E4 — Cobertura de features (última puerta antes de v0.1.0 público)

Generada 19-nov-2026 (sesión 22, PASO E4). Método: inventario del código en
`src/tlamati/`, cruzado con el PRD (MoSCoW), el arnés donor de cada semántica
(regla de copia: aprender semántica de OSS/donors, escribir Python propio) y
el test que lo prueba. Suite en la auditoría: 427 tests verdes, ruff check +
ruff format --check + mypy --strict limpios.

## Tabla de cobertura

| Feature (PRD) | Donor de semántica | Archivo(s) | Test(s) |
|---|---|---|---|
| F1 Loop + adapters [MUST] | hermes-agent (MIT), qwen-code format fallback | core/loop.py, core/messages.py, providers/openai_compat.py, providers/anthropic_messages.py | test_loop.py, test_messages.py, test_providers.py |
| F2 Tools core + permisos [MUST] | hermes (patch fuzzy, read_file caps), opencode permission.ts | tools/registry.py, tools/files.py, tools/search.py, tools/terminal.py, policy/config.py | test_registry.py, test_tools_b2.py, test_policy_b4.py |
| F3 Presupuesto + compaction + cache [MUST] | codex compact_token_budget.rs, qwen microcompaction, CC clear_tool_uses (nativo), hermes iteration_budget | context/budget.py, context/compaction.py | test_budget.py, test_compaction.py |
| F4 Sesiones + memoria [MUST] | Claude Code MEMORY.md scopes + tengu caps + auto-dream (vía REA/research 05), hermes memory | session/store.py, memory/store.py, memory/dream.py, memory/tools.py | test_session_store.py, test_memory.py |
| F5 Sandbox bwrap [MUST] | codex sandbox (concepto; no sus 33k LOC), gemini-cli | sandbox/bwrap.py, tools/terminal.py | test_sandbox_b3.py |
| F6 Skills + AGENTS.md [MUST] | hermes SKILL.md (formato 100% compatible), codex AGENTS.md | memory/skills.py, context/instructions.py | test_skills.py, test_instructions.py |
| F6b Workspaces + routing.md [SHOULD] | video "agents as folders" (research/03), qwen worktrees (concepto) | context/routing.py | test_routing.py |
| F7 TUI/headless [SHOULD] | opencode (ApproveScreen diff), hermes TUI | tui/app.py, cli.py | test_tui_e1.py, test_cli.py |
| F8 MCP client [SHOULD] | gemini-cli mcp, hermes MCP | mcp/client.py | test_mcp_d3.py, fake_mcp_server.py |
| F9 Sub-agentes [SHOULD] | hermes delegate_task (límites propios: read-only por construcción, profundidad 1) | subagent/spawn.py | test_subagent_d1.py |
| F10 Evals + trazas [MUST] | terminal-bench (concepto verify-decides), codex rollout | evals/runner.py, core/json_events.py, policy/ledger.py, bench/runner.py | test_evals.py, test_headless_json_e2.py, test_ledger_b5.py |
| F11 Plugins todo-plugin [SHOULD] | hermes plugins, Reasonix everything-plugin (reference-only, DEAD) | plugins/__init__.py, plugins/internal/ledger_plugin.py | test_plugins_d2.py |
| F15 Clase del día [SHOULD v1] | invención propia del proyecto (edu/) | edu/PROMPT_CLASE_DIARIA.md (mecanismo manual; hook automático NO construido — ver "huecos") | n/a (documento) |
| Plan-mode (F1 MUST, fase C5) | qwen explicit-plan-exit-approval.md (4 reglas oro fail-closed), gemini planning.md | plan/mode.py, plan/tools.py | test_plan_mode.py, test_plan_mode_headless_e3c.py |
| Muro de turnos + detector de estancamiento (E3d) | hermes (ofrecer resumen ~ donor CC 90-turnos forzado, aquí OFRECIDO) | core/loop.py, cli.py, tui/app.py | test_stall_e3d.py, test_loop.py |
| Ojos Windows (E3e PASO C) | Hermes WSL /mnt/<letra> de facto | tools/winpath.py + integración files/search/terminal | test_winpath_e3e.py |
| F16 Onboarding por nivel [COULD v2] | visión fundador sesión 20 | PRD_TLAMATI.md §6 (documentada, NO implementada — decidido) | n/a |
| F12 harness2 auto-mejora [COULD v2] | arxiv harness2 Propose-Probe-Compose | research/02 (documentado como v2 explícita, NO olvido) | n/a |
| F13 ACP server [COULD v2] | zed ACP | PRD §6 (no implementada) | n/a |
| F14 Web/browser [COULD v2] | — | PRD §6 (no implementada) | n/a |

## Huecos honestos (no bloquean v0.1, documentados)

1. **anthropic_messages.py existe pero el CLI no lo cablea** — solo
   openai_compat está integrado end-to-end. El README lo dice explícitamente.
2. **F15 "Clase del día" es un proceso manual** (prompt + Hermes), no un hook
   automático del arnés. El PRD la lista SHOULD v1; el mecanismo real es el
   documento edu/. Decisión: se publica como está (proceso), no como código.
3. **Content guard (revisor LLM de descargas)** — Fase C+ pospuesta, anotado
   en fase-b-state. La trifecta B4 cubre el caso letal básico.
4. **Env heredado a la jaula bwrap** (API keys visibles al comando enjaulado) —
   RESUELTO 25-nov: `--clearenv` + whitelist fail-closed en sandbox/bwrap.py
   (test de jaula real incluido). Era "post-v0.1"; se adelantó porque el repo
   ya es público.
5. **MCP url: (Streamable HTTP)** — documentado como puerta abierta, NO
   construido (solo stdio).
6. **Windows nativo fuera de WSL** — WON'T explícito del PRD §4.

## Puertas restantes ANTES de hacer público el repo

- [ ] **REESCRIBIR HISTORIA GIT**: el user_id de OpenRouter
      (el user_id de OpenRouter) vive en el commit 81c5235 (evals/b5_check.jsonl
      original). El working tree ya está sanitizado (commit 83e734e) pero la
      historia NO. Antes de `gh repo edit --visibility public`:
      `pip install git-filter-repo` + filtro de cadena + force-push. El repo
      es privado hoy = sin fuga actual.
- [ ] Verificar .gitignore cubre: evals/campaign_*/ en curso, __pycache__,
      vendor/, rea-out/, tmp.
- [ ] SECURITY.md: el fundador debe poner un correo REAL de contacto
      (marcador [PENDIENTE] puesto a propósito — Hermes no inventa datos de
      contacto).
- [ ] pyproject version 0.0.1 → 0.1.0 + tag + release notes.
- [ ] PyPI: re-verificar nombre libre (`tlamati` era 404 el 14-nov) + build
      hatchling + upload.
- [ ] EVALS.md: tabla §E3c completa cuando termine la campaña de modelos
      (regla de honestidad: fallo con campo error de proveedor NO es fallo
      del arnés; corrida única = decirlo, nunca promediar en silencio).
