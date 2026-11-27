> English translation of PRD_TLAMATI.md. The Spanish original is authoritative.

# PRD — TLAMATI: open-source agentic harness, local-first
Version 0.1 · 14-Nov-2026 · Owner: Leonardo Gutiérrez · Name: tlamati ("the wise one", Nahuatl)
Chosen license: **Apache-2.0** (includes patent grant; MIT acceptable, Apache preferred for a project aiming at corporate adoption).

---

## 1. Problem and opportunity
Step-1 research (research/01_HALLAZGOS_PASO1.md) showed that, with models of similar capability, **the harness — not the model — decides performance**: Vercel +20 pts of success by removing tools (same model), LangChain 52.8→66.5% by changing only the harness, Letta 59.1% vs Claude Code 41.6% on the SAME Claude Opus 4.5. And Han Lee warns half the harness work is throwaway when the model improves — except the PERMANENT parts: sandbox, permissions, spend limits, auditing, memory, traceability.

Opportunity: the best open harnesses (opencode 226k★, hermes 263k★, codex, gemini-cli, qwen-code) converge on a known recipe. None of them is *ours*: Tlamati is the harness that runs on the developer's machine with their models (OpenRouter/Anthropic via OpenRouter, hourly-rented GPU for open weights, local Ollama), with no data leaks for convenience (OpenCode anti-pattern: session-titling with a hosted model), inheriting the proven decisions and avoiding the unproven costs (don't reinvent Windows' 24k-LOC sandbox).

## 2. Users
- **Primary:** Leonardo Gutiérrez, power user on WSL/Ubuntu; CLI + TUI; a human approves dangerous actions.
- **Secondary:** OSS community devs who run open models on their own hardware (the niche winder.ai identifies: "running a harness against open-weight models on your own hardware").

## 3. Value proposition
1. **Guaranteed local-first:** no network call that the user or the model did not explicitly request. No titling, no analytics, no "outward convenience". Offline mode with Ollama.
2. **Truly provider-agnostic:** normal adapters (Anthropic messages, OpenAI-compatible, OpenRouter, Ollama, vLLM, Enverge) with **tool-calling format fallbacks** (anti-pattern "formats one agent emits another won't parse"). The model is a plug-in.
3. **The harness is not throwaway:** engineering concentrated on the permanent parts (permissions, sandbox, budget, auditing, memory) and context heuristics marked as temporary/replaceable.
4. **All-Plugin with a minimal core:** ~500 LOC of loop; everything else is tools, policies, and markdown skills ("Markdown is now code"). Inherits from Reasonix (MIT — reusable with attribution; its official death makes it seed material, not a dependency).
5. **Evaluable from day 1:** versioned eval suite and append-only traces (anti-pattern: "appears to work in controlled conditions, fails under production load").

## 4. Goals (v1) / Non-goals
### Yes in v1
- Turn-by-turn agentic loop with streaming, mid-turn user interjection (xai-interjection-core pattern), and plan-mode (explore→approve→execute).
- Core tools: terminal (with approval), filesystem (read/write/edit with diff and per-path access control), search (ripgrep-first, optional semantic Tree-sitter/lsp later), web (opt-in), scoped sub-agent.
- Context management: token budget (tiktoken/native counters), compaction with a cheap fallback model, **stable cacheable prefix** (cache-first, Hermes invariant: "per-conversation prompt caching is sacred"). M1-M5 savings hierarchy (research/04): truncation at the tool → budget check → microcompaction of reproducible tool outputs with placeholder+pointer (qwen microcompact.ts pattern + Anthropic context_management/cache_edits API, always behind the last cache breakpoint) → compaction with a cheap model → fresh window.
- Sessions: SQLite, transcript + structured summary kept separate; resume session. Long-term memory as markdown files + editable persistent memory.
- Permissions: declarative policy per tool/pattern/path; network allowlists; "lethal trifecta" rule (untrusted content crossing toward external communication requires explicit approval).
- Sandbox: bubblewrap on Linux/WSL (read-only by default, declared writable paths); v1 on macOS = strict approvals; Windows host = via WSL.
- Markdown skills + AGENTS.md (OpenAI format) + MCP client (local stdio servers; catalog).
- Workspaces with declarative routing ("agents as folders" pattern, research/03): `routing.md` in the cacheable prefix — "task → files to load/omit/skills" table; per-workspace context on demand; naming conventions as index (no DB). Loader `context/routing.py` ~100 LOC.
- Simple TUI (Textual) and headless mode `tlamati -p "..."` for scripts/CI.
- Evals: 20 own tasks + Terminal-Bench-lite runner; metrics: success, tokens/turn, cost, latency, system-prompt overhang.
- Packaged CLI (`uv tool install tlamati`), single config.yaml (no .env except secrets).

### Not in v1 (explicit, avoids YAGNI)
- Orchestrated multi-agent fleet/governance (layer 4 of the stack).
- IDE editor (vscode/zed/acp server), desktop app, messaging (gateway).
- Recursive harness self-improvement (harness2) — kept as optional **v2 mode**: proposer/probe/compose.
- Reimplementing a 24k-LOC sandbox for native Windows; supporting Windows outside WSL.
- Embedded code RAG (Step-1 evidence favors cheap deterministic search first).

## 5. Measurable success (target vs current reference state)
- Pre-first-prompt overhead < 8k tokens (ref: OpenCode 7k vs Claude Code 33k).
- ≥95% of sessions without a tool-call format error on the 3 target backends.
- Internal eval: ≥ the same success % as Qwen-Coder running under opencode with the same model, and document the harness delta (our "change the harness, not the model" experiment).
- Visible cost: every turn reports tokens/cost; compaction reduces ≥40% of tokens in 50-turn sessions without losing the task.
- OSS adoption: Apache-2.0 repo with CONTRIBUTING, CI, v0.1 release in ≤6 weeks of focused work.

## 6. Requirements by feature (MoSCoW priority)
F1 Loop+adapters [MUST] · F2 Core tools+permissions [MUST] · F3 Context: budget+compaction+cache [MUST] · F4 SQLite sessions+memory [MUST] · F5 bwrap sandbox [MUST] · F6 Markdown skills+AGENTS.md [MUST] · F6b Workspaces+routing.md [SHOULD v1, MUST v1.1] · F7 TUI/headless [SHOULD] · F8 MCP client [SHOULD] · F9 Sub-agents [SHOULD] · F10 Evals+traces [MUST] · F11 All-plugin plugins [SHOULD] · F15 Educational "class of the day": post-session hook that generates 1-3 pages of text for a non-technical student (edu/PROMPT_CLASE_DIARIA.md; shares the mechanism with auto-dream/consolidation) [SHOULD v1] · F16 Level-guided onboarding: first run detects missing config → asks level (beginner/technical) → step-by-step setup checklist (provider+key, recommended tools like ripgrep/bwrap, optional REA for closed apps, 1-flag skills migration). Founder's vision (session 20, verbatim in HANDOFF_E3d §2): "the agent walks you through the setup step by step" — the harness is for first-timers, the entry ceremony must be zero-friction. Zero-ceremony with Hermes (~/.hermes/skills auto-discovered, STEP A) and Windows eyes (STEP C) already solve part of it; F16 unifies the first-time experience. [COULD v2 — documented, NOT implemented in v0.1] · F12 harness2-mode self-improvement [COULD v2] · F13 ACP server [COULD v2] · F14 Web/browser [COULD v2] · WON'T: desktop/gateway/multi-agent v1.

## 7. Architecture (narrow waist)
```
tlamati/
  core/        loop, messages, turns (≈500 LOC, stable)
  providers/   adapters: anthropic, openai_compat, ollama (+ OpenRouter/rented-GPU as configs)
  tools/       declarative registry: name, schema, permission, sandbox_policy, run()
  policy/      permissions, approvals, trifecta rules, network allowlists
  context/     budget, compaction, stable prompt-cache, snippets
  session/     SQLite (transcript, summary, ledger), resume
  memory/      markdown files (memory + skills), AGENTS.md loader
  sandbox/     bwrap profile, paths, network
  subagent/    bounded scope, read-only default, recursion limit
  evals/       tasks, runner, traces
  ui/          textual TUI + headless
  plugins/     entry-points (Reasonix-style all-plugin)
```
Invariants: (1) system-prompt prefix byte-stable per conversation; (2) every provider call goes through a provider adapter that normalizes tool_calls to the internal format and degrades with a declared fallback; (3) no tool without a declared permission; (4) every model action is written to an append-only ledger with cost; (5) the loop never mutates past context except via explicit compaction.

## 8. Risks and mitigation
- **Model→harness gets rewritten every generation:** mitigate with narrow interfaces and heuristics tagged `provisional` (Lee's test: would a better model void this?).
- **Security (lethal trifecta):** web-reading + private filesystem + external communication = exfiltration → default policy: external content marked untrusted, outbound tools (network/send) require approval when the turn included untrusted content.
- **License:** REA on Claude Code/Cursor (proprietary): **behavioral study** allowed; copying code/bundle forbidden. Reusable material comes from MIT/Apache (Reasonix, hermes-agent, opencode, codex, gemini-cli, qwen-code) with NOTICE attribution.
- **Scope creep:** WON'T list + monthly review "ratchet rule" (Osmani): no new rule/prompt without a real failure justifying it.

## 9. Competition and why Tlamati exists
| | opencode | hermes | qwen-code | codex | **tlamati** |
|---|---|---|---|---|---|
| Strict local-first | partial | yes | partial | no | yes |
| Model-agnostic | 75+ | yes | multi-model bugs | OpenAI only | yes + format fallbacks |
| All-plugin | plugins | skills+plugins | partial | no | yes (Reasonix seed) |
| Harness2 self-improvement | no | no | no | no | v2 mode |
| Personal/own machine | general | yes | Qwen-first | OpenAI-first | own, auditable |

## 10. Glossary
harness = everything around the model that lets it act; capability = plugin unit (tools+hooks+instructions+settings, Pydantic v2 sense); ACP = Agent Client Protocol (Zed); MCP = Model Context Protocol (Anthropic); AGENTS.md = instructions format (OpenAI).
