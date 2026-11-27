> English translation of GUIA_IMPLEMENTACION.md. The Spanish original is authoritative.

# TLAMATI IMPLEMENTATION GUIDE — step by step
v0.1 · 14-Nov-2026 · Companion to PRD_TLAMATI.md
> For Hermes: execute with the writing-plans + subagent-driven-development skills, phase by phase.

## 0. Real inventory (verified on this machine, 14-Nov-2026)
### What we ALREADY have
| Resource | Status |
|---|---|
| WSL Ubuntu, 890GB free on / (1TB disk) | OK |
| Python 3.12.3 + uv 0.11.16 (creates/installs venvs and CLI apps) | OK |
| Node v22.22.2 / npm 10.9.7 | OK |
| git 2.43, gh CLI 2.95 (auth OK), tmux, gcc 13.3 | OK |
| tiktoken, pydantic v2, openai SDK already in global pip | OK |
| REA `rea@6.7.0` via `npx rea-agents` (works; capabilities: Linux OK, macOS n/a) | OK |
| Hermes Agent v0.18.2 with full source at ~/.hermes/hermes-agent (MIT, 263k★) — pattern DONOR: adapters, toolsets, compaction, approval | OK |
| Claude Code 2.1.92 installed via npm (cli.js 59MB minified) — behavioral REA target | OK |
| Codex 0.133 installed + Rust source vendor/codex (Apache-2.0) | OK |
| Clones in vendor/: codex, opencode, qwen-code, gemini-cli, grok-build, DeepSeek-Reasonix, harness2, claude-code + local hermes — 8 study substrates | OK |
| LLM access: OpenRouter (Anthropic claude-sonnet-4-6 via base_url), hourly-rented GPU (coder 80B + q35b), configurable Ollama | OK |
| Business rule: latency ≤30s, quality untouchable, $0 in paid dependencies | OK |

### Still to download (few; ALL free/open-source)
1. `sudo apt install ripgrep bubblewrap sqlite3` ← THIS REQUIRES YOUR SUDO PASSWORD (I tried: "a password is required"). 3 pkgs: ~6MB.
2. `uv venv + uv add` in tlamati/: textual (TUI), rich, jsonschema, httpx, aiosqlite, pytest, ruff, mypy. (0 paid deps)
3. Optional v2: `npm i -g @zed-industries/agent-client-protocol` no — ACP is a protocol, implemented over stdio JSON-RPC, no pkg. Tree-sitter (`pip tree-sitter + grammars`, Apache) only when semantic search comes up.
4. gh repo: create <user>/tlamati (private → public at v0.1).

### NOT needed and NOT to be used
- No additional paid Anthropic/OpenAI SDK; everything over HTTP against OpenRouter/Ollama/rented-GPU.
- Docker is not a requirement (sandbox = bwrap; docker as optional v2 backend).

---
## PHASE A — Seed (F1+F3+F10 minimum). ~1 split workday
Demo goal: `tlamati -p "fix X"` solves a real bug in a test repo with a local model and a budget.

A1. Scaffolding: `uv init --package tlamati` → PRD §7 structure. pyproject with `[project.scripts] tlamati`, ruff+mypy+pytest, GitHub Actions CI (lint+test). LICENSE Apache-2.0 + NOTICE.md.
  Verify: `uv tool install --from . tlamati && tlamati --version`.
A2. `core/messages.py`: internal types (Message, ToolCall, ToolResult, Usage). This is the NEGOLO: every adapter translates to/from here.
A3. `providers/base.py`: Protocol `stream(messages, tools) -> AsyncIterator[Event]`. Implement OpenAICompat (covers OpenRouter+Ollama+vLLM; config: base_url+api_key+model) and AnthropicMessages (native messages API format, tool_use/tool_result, cache_control breakpoints) — copy the SEMANTICS of ~/.hermes/hermes-agent/agent/anthropic_adapter.py (MIT), don't copy lines unless they add value.
  Test: against a mock `ollama` server (httpx MockTransport) validating tool_calls normalization and that weird refusal/finish_reason values map to a typed error.
A4. `core/loop.py` ≤500 LOC: while turn → stream → execute tool calls → append → repeat, until stop or budget. No weird base classes: function + state dataclass. v1 interjection: SIGINT queues a user message for the next turn.
A5. `context/budget.py`: token counting per model (tiktoken cache + approximator for models without encoding), 80/95% thresholds, `context_breakdown` per section (system/tools/history — hermes pattern).
A6. `context/compaction.py`: summary with a configurable CHEAP MODEL (fallback chain), retention of recent tool outputs, and golden rule: compaction REBUILDS the suffix, never mutates the cacheable prefix.
A7. First E2E eval: 5 own terminal-bench-lite tasks (fixtures/), runner `tlamati-eval` → JSONL with success/tokens/cost. Run with qwen3-coder via OpenRouter and local Ollama. Save baseline.

## PHASE B — Tools + permissions (F2+F5). ~1.5 workdays
B1. `tools/registry.py`: Tool(name, schema, permission, run, sandboxable). Schema via `jsonschema` validation BEFORE executing. Footprint ladder (hermes AGENTS.md rule): extension first, new core tool last.
B2. Tools: read_file (with line numbers + honest truncation), write_file, edit (hermes-patch-style fuzzy-match: 9 strategies), search_files (rg subprocess), terminal (pty-less foreground first; background+poll v1.1).
B3. `sandbox/bwrap.py`: execution jail for terminal/edit: `--ro-bind / / --bind <workdir> <workdir> --dev/dev --unshare-net by default`; `--net` flag = separate permission. Default profile: read-only fs + writable workdir. (If the apt packages from A4… I mean from §0.1 aren't installed, ask for the password here.)
B4. `policy/`: TOML-style policy in config.yaml: tool→auto|ask|deny + path/command patterns. Approval in the TUI and in headless with `--yolo/--approve-…` (default NEVER yolo). Trifecta rule: if the turn consumed a tool result with `untrusted=True`, any outbound tool (network, env-mail) escalates to ask even if it was auto.
B5. `policy/ledger.py`: append-only SQLite: turn, tool args, result hash, cost, permission decision. `tlamati audit --session <id>`.

## PHASE C — Session + memory + skills (F4+F6). ~1 workday
> Distilled Nov 16 (session 8) from research/02 + research/05: every decision carries its source.

C1. `session/store.py`: SQLite (aiosqlite): sessions, messages, summaries, usage. `tlamati resume`, `--continue`.
  - Schema PREPARED for compaction: `summaries` table (window→summary, model used) + `retention` column per tool_result (survives-window flag, source: codex `compact_retained_tool_outputs.rs`) + `content_cleared` boolean for microcompaction (source: qwen `microcompact.ts` — honest marker "[Old tool result content cleared]", anti-collision regex derived from the producing constant).
  - Cache invariant: every history edit happens BEHIND the last breakpoint or via native cache-edits (source: Anthropic's `clear_tool_uses_20250919`/`cache_edits` mechanism used by CC, doc 05). Re-obtainability rule: whatever can be re-read from disk (read_file, search, skill_view) is microcompactable; the irreproducible (terminal output, network results) gets retention=true.
C2. `memory/`: MEMORY.md (facts) + USER.md (preferences), injected in the cacheable prefix; `memory` tool (add/replace/remove) atomic batch.
  - HARD ceilings (source: CC via REA, events tengu_team_mem_sync_* and team_mem_entries_capped → there IS an entry CAP; doc 05 §2): line/char limit per file + entry cap; when full the agent CONSOLIDATES (merges/deletes) in the same batch — never accumulates.
  - Minimal v1 scopes: user + project (CC has 4: user/project/local/team — the other 2 are v2 if there's demand).
  - AUTO-DREAM (source: CC doc 05 §3, confirmed by qwen — memory extraction is a separate planner): async job on session CLOSE that distills learnings into MEMORY.md. NEVER in a hot turn. v1 = simple (1 call to a cheap model with the transcript); the B5 ledger hook provides the transcript for free.
  - Osmani seed rules (source: doc 05 §1, CC builder offset 11,666,006): absolute paths, no recapitulating, no emojis — go in as initial MEMORY.md text.
  - Prefix stability: dynamic metadata travels outside the prompt (HTTP header / message), never mutates the prefix byte by byte (source: doc 05, CC attribution header).
C3. `memory/skills/`: SKILL.md (YAML frontmatter + body), injection by name scanning (trigger = description in the system prompt, loading via the `skill_view` tool). Format 100% compatible with hermes (~/.hermes/skills directly readable = library migration with 1 flag). skill_view output is microcompact-whitelisted (re-obtainable from disk, same as CC with search_memory).
C4. AGENTS.md loader: merge repo→global→override; versioned in the prefix (content hash) for cache stability.

## PHASE C+ — Plan-mode + routing (PRD F1 MUST + F6b SHOULD, no phase until Nov 16)
C5. Plan-mode: `enter_plan_mode`/`exit_plan_mode` tools — explore→approve→execute (sources: qwen enter/exitPlanMode, gemini enter/exit-plan-mode; research/02 finding #5 "good harness primitives"). In plan-mode: write/terminal tools → deny by policy (B4 already provides the mechanism, 0 new permission code). `ask_user` + `complete_task` as primitives (gemini/qwen).
C6. Workspaces+routing.md (F6b): agents-as-folders, 3-layer routing (source: research/03).

## PHASE D — Subagents + plugins + MCP (F9+F11+F8). ~1.5 workdays
D1. `subagent/spawn.py`: isolated task, reduced READ-ONLY default toolset, max_turns + max_cost, result = summary (hermes delegate pattern; limits = Raschka pattern #6).
D2. `plugins/`: entry-point `tlamati.plugins` + discovery `~/.config/tlamati/plugins/*.py` (Reasonix "everything is a plugin" pattern + gemini's hook registry: before_tool/after_tool/on_error; ONLY hooks with a concrete consumer — hermes anti-speculative rule).
D3. Minimal stdio MCP client: initialize → tools/list → map to the Tool registry with permission="ask" by default (don't trust MCP: treat as untrusted). Local servers from your ecosystem (REA as an MCP server already supports it).

## PHASE E — Surfaces + full eval + OSS polish (F7+F10). ~1 workday
E1. Textual TUI: multiline input, stream with markdown, diff viewer with approve/reject, per-turn cost/token bar (visible context_breakdown), sessions panel.
E2. Headless: `tlamati -p "..." --json` (JSONL events) for CI; honest exit codes.
E3. Eval suite: ≥20 tasks (terminal/file/git/reasoning/latency), 3 target models (sonnet-4 via OR, coder80B on rented GPU, qwen3-ollama). HARNESS×model matrix documented in EVALS.md — our Step-1 argument: it shows the harness delta.
E4. Docs: README (why/what it is NOT), ARCHITECTURE.md (narrow waist + invariants), CONTRIBUTING.md, SECURITY.md (trifecta + reporting), CHANGELOG + release-please.
E5. Publish: `gh repo create tlamati --public`, tag v0.1.0, HN/forums post.

---
## PHASE F — REA on proprietary targets (cross-cutting, at the end of each phase)
REA (morluto/rea, MIT, `npx rea-agents`) on LOCAL targets (only bundles you ALREADY legally installed):
- F-a. `rea analyze-javascript-application` against ~/.nvm/…/@anthropic-ai/claude-code/cli.js: map (a) its system prompt/cache breakpoint strategy, (b) its real tool catalog, (c) what it sends BEFORE your first prompt (the 33k metric). Output: research/rea/claude-code-*.md. Copying code FORBIDDEN: architecture/behavior only → PRD checklist.
- F-b. Cursor: no bundle → behavioral analysis (docs + forums) → research/rea/cursor-conductual.md.
- F-c. Against open SOURCE code (reusable with license): opencode compaction.ts, codex compact_token_budget.rs, qwen bwrap-execution.ts, reasonix plancontract — read → `docs/anatomia/<topic>.md` with exact reference (repo:path). REA is used to confirm the compiled behavior matches the source.
- F-d. harness2: run 1 jb benchmark with 1 config (needs its runners; pip -e '.[render]') to understand the Propose–Probe–Compose cycle BEFORE promising "v2 mode".

## Work order and dependencies
A→B→C→D→E with F interleaved. B and C can be parallelized (subagents per phase, spec-review first). Don't skip A7: if a phase breaks the eval baseline, it stops and gets reviewed (Osmani ratchet: every fix is born from an observed failure).

## Open decisions (need YOUR choice, not urgent)
1. Does Tlamati absorb Hermes as a personal harness, or do they coexist (Hermes platform, Tlamati OSS lab)? Affects how much we reuse from hermes-agent vs rewrite clean.
2. Go/No-Go on Reasonix (MIT, forks welcome but Officially Dead Nov 12): use it as the Go skeleton or Python from scratch? (my recommendation: Python from scratch ~core, Reasonix as plugin-architecture reference; reason: your toolchain and hermes's are Python, and WSL+Rust/Go adds build friction).
3. Final PyPI package name (tlamati may be taken; verify `pip index versions tlamati`).
