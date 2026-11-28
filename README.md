# tlamati

Local-first, provider-agnostic **agentic harness**. The model is a plugin.

Tlamati is the scaffolding around an LLM: the loop, the tools, the sandbox, the
permissions, the audit trail, the context budget. Evidence says the harness
matters as much as the model — removing weak tools lifted Vercel's agent from
80% to 100% on the same model; Terminal-Bench showed +17pts from harness
changes alone. Tlamati is that idea, built in ~5k lines of dependency-light
Python (stdlib + httpx), Apache-2.0.

```
pip install "git+https://github.com/Leonardo1387/tlamati"          # core (headless)
pip install "git+https://github.com/Leonardo1387/tlamati[tui]"     # + interactive terminal UI (textual)
```

Requires Python 3.12+. Optional system deps: `bwrap` (bubblewrap sandbox) and
`rg` (ripgrep, for search_files) — both degrade honestly when missing.

> **Measured, not marketed:** on long-horizon tasks, the reference harness cost
> **8.6× more** (`gpt-6.2-sol`) and **1.9× more** (`claude-opus-5.5`) than
> tlamati for the same verified work — [Evals](#evals).

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
  outside the workdir. Network is ON by default (Hermes parity, SEC.1) — the
  real defense against exfiltration is review, not a blind cage: untrusted
  web/MCP content escalates egress to ASK (see Security). Use
  `--no-sandbox-net` or `sandbox: {net: false}` in config to deny network.
  `[sin sandbox]` warning when bwrap is missing — never silent.
- **Permissions that never relax.** Escalade `deny > ask > auto`; the "lethal
  trifecta" (untrusted content + egress tool) auto-escalates to ASK. In the
  TUI the approval modal offers **once / always / reject** — "always" lasts
  for the current run and that tool only (it never touches the Policy).
  Headless equivalent: `--approve-tool terminal` (or `'*'`; default: never
  auto-approve).
- **Append-only audit ledger.** Every tool call, decision and per-turn cost in
  SQLite (`tlamati audit`). Non-disableable by design.
- **Context budget + cache-safe compaction.** Prompt caching is sacred: history
  edits happen behind the last cache breakpoint. Benchmarks show 92-95%
  cache_read on real runs.
- **Durable memory + sessions.** MEMORY.md/USER.md with hard caps, auto-dream
  consolidation at close (`--dream`), resumable sessions (`--continue`).
- **Skills, hermes-compatible.** `tlamati --skills-dir ~/.hermes/skills` reads
  an existing library with zero conversion. `~/.hermes/skills` is auto-added
  last if present. tlamati also reads any
  [agentskills.io](https://agentskills.io)-compatible skill — verified in CI
  against the real
  [obsidian-skills](https://github.com/obsidianmd/obsidian-skills)
  (fixture in `fixtures/agentskills_compat/`).
- **AGENTS.md / CLAUDE.md** project instructions (cross-agent standard).
- **Subagents** (`delegate_task`) — child is read-only by construction, depth 1,
  hard token/turn caps that block BEFORE spending.
- **Everything-plugin hooks** (`before_tool` can only veto) + **MCP client**
  over **stdio and Streamable HTTP** — remote tools are ASK + untrusted
  always. Three meta-tools per server (`list_toolsets` / `describe_toolset` /
  `call_tool`) keep hundreds of upstream tools out of the context window
  until needed. Verified live against **Unreal Engine 5.8's official MCP
  server** (HTTP, 53 toolsets) and **Blender** (stdio, ~4,200 operators):
  one harness, any creative app that speaks MCP.
- **`web_fetch`.** The model can read a URL (GET, text only, 200 KB cap at
  the source) — always ASK, always `produces_untrusted`, outside the jail
  (the network gate is the permission, not bwrap).
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

stall:                        # quasi-stall detector (near-identical tool calls)
  quasi_similarity: 0.85      # SequenceMatcher ratio; 0 disables
  quasi_window: 15            # sliding window of turn signatures
  quasi_warn_count: 5         # >=N near-identical: soft warning injected
  quasi_ask_count: 8          # >=N: ask the user (TUI modal; headless stops)

sandbox:
  enabled: true               # bwrap jail for the terminal tool
  net: true                   # network inside the jail (default ON, SEC.1;
                              # flags --sandbox-net/--no-sandbox-net override)

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
  servers:                    # LISTA (no mapa); cada entrada: name + command O url
    - name: my_server
      command: ["npx", "-y", "@some/mcp-server"]   # stdio
    - name: unreal
      url: "http://127.0.0.1:8000/mcp"             # Streamable HTTP (Unreal 5.8 official MCP)
```

Key flags: `--max-turns N`, `--stall-repeats N`, `--plan-mode` (explore →
approve → execute), `--json` (JSONL events for CI), `--no-sandbox`,
`--sandbox-net/--no-sandbox-net`, `--approve-tool NAME` (headless pre-approval
for ASK permissions, e.g. `--approve-tool terminal` = the TUI's "always"
button), `--no-memory`, `--no-audit`, `--continue`, `--resume ID`.

When the turn wall is hit in the TUI, tlamati offers **"continúa"** (resume
with history intact) or **"resumen"** (model-summarized compaction, cost
counted) — never a dead stop.

## Evals

**Frontier numbers (H9 v4 — long-horizon cascade task, 36-110 turns, ×3
replicas):** for the same verified work, the reference harness (codex) cost
**8.6× more** on `gpt-6.2-sol` and **1.9× more** on `claude-opus-5.5` than
tlamati. The mechanism is measured, not claimed: codex re-sends history and
re-reads files between reveals (3-4× input tokens); tlamati keeps the active
window bounded. The advantage is model-dependent — `qwen3.8-max` inverts it —
and the full protocol, raw costs and anti-cheat audit live in
[EVALS.md](EVALS.md) ([EN](EVALS.en.md)).

`tlamati-eval` runs the fixture suite (terminal-bench-lite style: seeded bug →
agent → `verify.py` decides, never assumed). Numbers with real costs, cache
rates and honest failure attribution (upstream provider errors are NOT counted
as harness failures) live in [EVALS.md](EVALS.md) ([EN](EVALS.en.md)).

## The skillopt experiment (self-improvement, honestly measured)

We asked whether a harness can improve its own skills — propose a better
SKILL.md from observed failures, benchmark it, keep it only if it wins — and we
measured the answer instead of assuming it.

Three rounds, one fixture, two models (qwen3.8-flash, qwen3-coder), 190 total
runs, $2.85 total spend:

| Round | n per arm | What it said |
|---|---|---|
| S1.0 | 3 | "+67 points!" — a story small samples tell |
| S1.1 | 10/5 | baseline was really ~80%, not 33%; effect shrank, p=0.24, not significant |
| S1.2 | 35/30 | **mutated skill 97-100% vs baseline 83-90%, pooled Fisher p=0.0085** |

What the numbers mean:

- The propose→bench→keep cycle works, and the effect is real but modest
  (+12-14 points), with fewer turns per task (11.8 vs 14.4) — cheaper, not
  just better.
- One mutation made things *worse* (74-80%). The "keep only if the bench
  improves" gate is not optional: without a statistical judge, a
  self-improving harness degrades itself.
- The n=3 round was wrong and we say so. Benchmarks with tiny n are
  storytelling. The eval rig here (resumable, isolated HOME, Fisher's exact
  test from the stdlib) costs cents and tells the truth.

skillopt is **not a v0.1 feature** — it lives on the `spike/skillopt` branch
with full appendices (`dev/SPIKE_SKILLOPT.md`). It is the validated pilot for
v2's evidence-gated self-improvement (proposer + statistical judge + ledger).
Replication caveat: one fixture, two models; broader tasks before shipping.

## Security

Read [SECURITY.md](SECURITY.md) ([EN](SECURITY.en.md)): trust model, sandbox
guarantees, plugin/MCP
threat surface, audit ledger. Report vulnerabilities privately — see the
reporting section there.

## Project docs

- `PRD_TLAMATI.md` — product requirements, MoSCoW features, no-goals
  ([EN](PRD_TLAMATI.en.md))
- `research/` — harness anatomy studies (8 vendor harnesses), token-saving
  mechanisms, benchmarks landscape
- `edu/` — the "class of the day" series: each development session explained
  as a textbook chapter for a non-technical learner (Spanish)
- English translations (`*.en.md`) exist for CHANGELOG, SECURITY, STABILITY,
  NOTICE, EVALS, PRD, GUIA_IMPLEMENTACION, AUDITORIA_E4 and the eval/bench
  reports; the Spanish originals are authoritative

## License

Apache-2.0. Donors acknowledged: hermes-agent (MIT), qwen-code (Apache-2.0),
codex (Apache-2.0), opencode (MIT), gemini-cli (Apache-2.0) — semantics and
architecture learned, code written from scratch.
