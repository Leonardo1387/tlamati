> English translation of AUDITORIA_E4.md. The Spanish original is authoritative.

# E4 AUDIT — Feature coverage (last gate before public v0.1.0)

Generated 2026-11-19 (session 22, STEP E4). Method: inventory of the code in
`src/tlamati/`, cross-checked against the PRD (MoSCoW), the donor harness of
each semantic (copy rule: learn semantics from OSS/donors, write our own
Python), and the test that proves it. Suite at audit time: 427 green tests,
ruff check + ruff format --check + mypy --strict clean.

## Coverage table

| Feature (PRD) | Semantics donor | File(s) | Test(s) |
|---|---|---|---|
| F1 Loop + adapters [MUST] | hermes-agent (MIT), qwen-code format fallback | core/loop.py, core/messages.py, providers/openai_compat.py, providers/anthropic_messages.py | test_loop.py, test_messages.py, test_providers.py |
| F2 Core tools + permissions [MUST] | hermes (patch fuzzy, read_file caps), opencode permission.ts | tools/registry.py, tools/files.py, tools/search.py, tools/terminal.py, policy/config.py | test_registry.py, test_tools_b2.py, test_policy_b4.py |
| F3 Budget + compaction + cache [MUST] | codex compact_token_budget.rs, qwen microcompaction, CC clear_tool_uses (native), hermes iteration_budget | context/budget.py, context/compaction.py | test_budget.py, test_compaction.py |
| F4 Sessions + memory [MUST] | Claude Code MEMORY.md scopes + tengu caps + auto-dream (via REA/research 05), hermes memory | session/store.py, memory/store.py, memory/dream.py, memory/tools.py | test_session_store.py, test_memory.py |
| F5 Sandbox bwrap [MUST] | codex sandbox (concept; not its 33k LOC), gemini-cli | sandbox/bwrap.py, tools/terminal.py | test_sandbox_b3.py |
| F6 Skills + AGENTS.md [MUST] | hermes SKILL.md (100% compatible format), codex AGENTS.md | memory/skills.py, context/instructions.py | test_skills.py, test_instructions.py |
| F6b Workspaces + routing.md [SHOULD] | video "agents as folders" (research/03), qwen worktrees (concept) | context/routing.py | test_routing.py |
| F7 TUI/headless [SHOULD] | opencode (ApproveScreen diff), hermes TUI | tui/app.py, cli.py | test_tui_e1.py, test_cli.py |
| F8 MCP client [SHOULD] | gemini-cli mcp, hermes MCP | mcp/client.py | test_mcp_d3.py, fake_mcp_server.py |
| F9 Subagents [SHOULD] | hermes delegate_task (own limits: read-only by construction, depth 1) | subagent/spawn.py | test_subagent_d1.py |
| F10 Evals + traces [MUST] | terminal-bench (verify-decides concept), codex rollout | evals/runner.py, core/json_events.py, policy/ledger.py, bench/runner.py | test_evals.py, test_headless_json_e2.py, test_ledger_b5.py |
| F11 Everything-plugin plugins [SHOULD] | hermes plugins, Reasonix everything-plugin (reference-only, DEAD) | plugins/__init__.py, plugins/internal/ledger_plugin.py | test_plugins_d2.py |
| F15 Class of the day [SHOULD v1] | project's own invention (edu/) | edu/PROMPT_CLASE_DIARIA.md (manual mechanism; automatic hook NOT built — see "gaps") | n/a (document) |
| Plan-mode (F1 MUST, phase C5) | qwen explicit-plan-exit-approval.md (4 golden fail-closed rules), gemini planning.md | plan/mode.py, plan/tools.py | test_plan_mode.py, test_plan_mode_headless_e3c.py |
| Turn wall + stall detector (E3d) | hermes (offer summary ~ donor CC forced 90-turns, here OFFERED) | core/loop.py, cli.py, tui/app.py | test_stall_e3d.py, test_loop.py |
| Windows eyes (E3e STEP C) | Hermes WSL /mnt/<letter> de facto | tools/winpath.py + files/search/terminal integration | test_winpath_e3e.py |
| F16 Onboarding by level [COULD v2] | founder vision session 20 | PRD_TLAMATI.md §6 (documented, NOT implemented — decided) | n/a |
| F12 harness2 self-improvement [COULD v2] | arxiv harness2 Propose-Probe-Compose | research/02 (documented as explicit v2, NOT an oversight) | n/a |
| F13 ACP server [COULD v2] | zed ACP | PRD §6 (not implemented) | n/a |
| F14 Web/browser [COULD v2] | — | PRD §6 (not implemented) | n/a |

## Honest gaps (do not block v0.1, documented)

1. **anthropic_messages.py exists but the CLI does not wire it** — only
   openai_compat is integrated end-to-end. The README says so explicitly.
2. **F15 "Class of the day" is a manual process** (prompt + Hermes), not an
   automatic hook of the harness. The PRD lists it SHOULD v1; the real
   mechanism is the edu/ document. Decision: it is published as-is (process),
   not as code.
3. **Content guard (LLM reviewer of downloads)** — Phase C+ postponed, noted
   in fase-b-state. The B4 trifecta covers the basic lethal case.
4. **Env inherited by the bwrap cage** (API keys visible to the caged
   command) — RESOLVED 25-nov: `--clearenv` + fail-closed whitelist in
   sandbox/bwrap.py (real-cage test included). It was "post-v0.1"; it was
   pulled forward because the repo is already public.
5. **MCP url: (Streamable HTTP)** — documented as an open door, NOT built
   (stdio only).
6. **Native Windows outside WSL** — explicit WON'T in PRD §4.

## Remaining gates BEFORE making the repo public

- [ ] **REWRITE GIT HISTORY**: the OpenRouter user_id
      (the OpenRouter user_id) lives in commit 81c5235 (original
      evals/b5_check.jsonl). The working tree is already sanitized (commit
      83e734e) but the history is NOT. Before
      `gh repo edit --visibility public`:
      `pip install git-filter-repo` + string filter + force-push. The repo
      is private today = no current leak.
- [ ] Verify .gitignore covers: in-progress evals/campaign_*/, __pycache__,
      vendor/, rea-out/, tmp.
- [ ] SECURITY.md: the founder must put a REAL contact email
      ([PENDIENTE] placeholder placed on purpose — Hermes does not invent
      contact data).
- [ ] pyproject version 0.0.1 → 0.1.0 + tag + release notes.
- [ ] PyPI: re-verify the name is free (`tlamati` was 404 on 14-nov) + build
      hatchling + upload.
- [ ] EVALS.md: complete §E3c table when the model campaign finishes
      (honesty rule: a failure with a provider error field is NOT a harness
      failure; single run = say so, never average silently).
