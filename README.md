# tlamati

Local-first, provider-agnostic **agentic harness**. The model is a plugin.

Tlamati is the scaffolding around an LLM: the loop, the tools, the sandbox, the
permissions, the audit trail, the context budget. Evidence says the harness
matters as much as the model — removing weak tools lifted Vercel's agent from
80% to 100% on the same model; Terminal-Bench showed +17pts from harness
changes alone. Tlamati is that idea, built in ~5k lines of dependency-light
Python (stdlib + httpx), Apache-2.0.

```
pip install tlamati          # core (headless)
pip install "tlamati[tui]"   # + interactive terminal UI (textual)
```

Requires Python 3.12+. Optional system deps: `bwrap` (bubblewrap sandbox) and
`rg` (ripgrep, for search_files) — both degrade honestly when missing.

## Quickstart

```bash
export OPENROUTER_API_KEY=***
tlamati                                # interactive TUI (with [tui] extra)
tlamati -p "fix the failing test in tests/test_x.py"   # headless one-shot
```

Any OpenAI-compatible provider works, not just OpenRouter (DeepInfra, Together,
Groq, Ollama, vLLM...):

```bash
tlamati -p "..." --base-url https://api.deepinfra.com/v1 --model deepseek-ai/DeepSeek-V3
```

An Anthropic-native adapter (`providers/anthropic_messages.py`) is included in
the codebase but the CLI wires OpenAI-compatible endpoints; use OpenRouter for
Claude models today.

## What you get

- **Simple loop, honest failures.** `stop_reason` and exit codes tell the truth
  (`0` end_turn, `1` max_turns, `2` usage, `3` budget, `4` error, `8` stall...).
- **Stall detector.** Same tool call (identical args) 3 turns in a row = dead
  loop → hard stop. Editing the same file with different content is NOT a loop.
- **Sandbox.** `terminal` runs inside a bubblewrap jail: read-only filesystem
  outside the workdir, network OFF by default. `[sin sandbox]` warning when
  bwrap is missing — never silent.
- **Permissions that never relax.** Escalade `deny > ask > auto`; the "lethal
  trifecta" (untrusted content + egress tool) auto-escalates to ASK.
- **Append-only audit ledger.** Every tool call, decision and per-turn cost in
  SQLite (`tlamati audit`). Non-disableable by design.
- **Context budget + cache-safe compaction.** Prompt caching is sacred: history
  edits happen behind the last cache breakpoint. Benchmarks show 92-95%
  cache_read on real runs.
- **Durable memory + sessions.** MEMORY.md/USER.md with hard caps, auto-dream
  consolidation at close (`--dream`), resumable sessions (`--continue`).
- **Skills, hermes-compatible.** `tlamati --skills-dir ~/.hermes/skills` reads
  an existing library with zero conversion. `~/.hermes/skills` is auto-added
  last if present.
- **AGENTS.md / CLAUDE.md** project instructions (cross-agent standard).
- **Subagents** (`delegate_task`) — child is read-only by construction, depth 1,
  hard token/turn caps that block BEFORE spending.
- **Everything-plugin hooks** (`before_tool` can only veto) + **MCP client**
  (stdio; remote tools are ASK + untrusted always).
- **Windows paths on WSL.** `C:\Users\me\Desktop\notes.txt` pasted as-is is
  normalized to `/mnt/c/Users/me/Desktop/notes.txt` across all path-taking
  tools. Unmounted drive = honest error, never an invented path.

## Configuration

`tlamati.yaml` (project) or `~/.config/tlamati/config.yaml` (user). Flags
override config; config overrides defaults.

```yaml
provider:                     # all keys optional; flags override
  model: qwen/qwen3-coder
  base_url: https://openrouter.ai/api/v1
  api_key_env: OPENROUTER_API_KEY   # env var holding the key (default: this one)

general:
  max_turns: 60               # turn wall; <=0 = yolo (context budget still caps)
  stall_repeats: 3            # stall detector; 0 disables

skills:
  extra_dirs:                 # additional skill roots (hermes SKILL.md format)
    - ~/shared-skills

plugins:
  extra_dirs: []              # *.py modules with register(hooks)

subagent:
  max_turns_default: 10
  max_turns_cap: 25
  max_total_tokens: 200000

mcp:
  servers:
    my_server:
      command: ["npx", "-y", "@some/mcp-server"]
```

Key flags: `--max-turns N`, `--stall-repeats N`, `--plan-mode` (explore →
approve → execute), `--json` (JSONL events for CI), `--no-sandbox`,
`--sandbox-net`, `--no-memory`, `--no-audit`, `--continue`, `--resume ID`.

When the turn wall is hit in the TUI, tlamati offers **"continúa"** (resume
with history intact) or **"resumen"** (model-summarized compaction, cost
counted) — never a dead stop.

## Evals

`tlamati-eval` runs the fixture suite (terminal-bench-lite style: seeded bug →
agent → `verify.py` decides, never assumed). Numbers with real costs, cache
rates and honest failure attribution (upstream provider errors are NOT counted
as harness failures) live in [EVALS.md](EVALS.md).

## Security

Read [SECURITY.md](SECURITY.md): trust model, sandbox guarantees, plugin/MCP
threat surface, audit ledger. Report vulnerabilities privately — see the
reporting section there.

## Project docs

- `PRD_TLAMATI.md` — product requirements, MoSCoW features, no-goals
- `research/` — harness anatomy studies (8 vendor harnesses), token-saving
  mechanisms, benchmarks landscape
- `edu/` — the "class of the day" series: each development session explained
  as a textbook chapter for a non-technical learner (Spanish)

## License

Apache-2.0. Donors acknowledged: hermes-agent (MIT), qwen-code (Apache-2.0),
codex (Apache-2.0), opencode (MIT), gemini-cli (Apache-2.0) — semantics and
architecture learned, code written from scratch.
