> English translation of SECURITY.md. The Spanish original is authoritative.

# SECURITY.md — Tlamati

No marketing: in an OSS harness, explicit limits are a feature. This
document states what each layer protects, what it does NOT protect, and why
that is a decision rather than an oversight.

## The honest matrix (FASE SEC audit, 2026-11-21)

Every security restriction in the harness fell into one of three categories:

### REAL — genuinely protects

- **The lethal trifecta** (`policy/` + `tools/registry.py`): when a turn
  consumes untrusted content (web result, MCP, or terminal with network —
  tools marked `produces_untrusted`), EGRESS tools escalate AUTO→ASK.
  This is the anti-exfiltration defense after reading untrusted web content:
  the model may read the web freely, but to GO OUT (curl POST, ssh, etc.)
  after consuming it, a human approves.
  - TUI: modal once / **always** / reject. "Always" lasts for the run and
    applies only to that tool; it NEVER touches the Policy (the ladder only
    hardens).
  - Headless: `--approve-tool NAME` pre-approves ASK tools (`'*'` = all;
    default: none — never silent yolo).
- **MCP is always ASK + untrusted**: MCP servers are untrusted territory by
  construction. Every remote tool is wrapped as `mcp_<server>_<tool>` with
  `permission=ASK` and `produces_untrusted=True` ALWAYS (the policy may
  harden to deny, never relax).
- **Permission ladder `deny > ask > auto`**: overrides, patterns, and
  `before_tool` plugins may only HARDEN. Nothing relaxes permissions at
  runtime.
- **The agent KNOWS its environment** (SEC.3): the system prompt declares
  whether the terminal has network or not, using the SAME formula the tool
  uses (`net_efectiva = sandbox_net or not sandbox`). Prompt and tool never
  contradict each other (an end-to-end test blocks it). An agent that does
  not know it has network lies to the user ("I can't") — that is also an
  honest-security failure.

### ILLUSORY / PARITY — does not protect, and it is a documented decision

- **The bwrap cage is NOT a filesystem boundary.** File tools
  (read_file, write_file, patch...) run FREE and on AUTO, and `_resolve`
  (files.py) resolves any absolute path — write_file bypasses the cage
  entirely. Hermes PARITY DECISION: the harness does not promise to confine
  the filesystem; it promises to AUDIT (append-only ledger) and REVIEW
  (trifecta). The terminal cage is a **shell-accident safety net** (it
  protects against accidental `rm -rf` outside the workdir, not against a
  malicious agent with file tools).
- **API keys NOT visible to the caged command** (hardened 25-nov): the cage
  starts with `--clearenv` and receives only a whitelist of innocuous
  variables (PATH/HOME/LANG/TERM/...). Fail-closed: `OPENROUTER_API_KEY` and
  any other secret in the parent env stay out of the caged command. The
  harness calls the model OUTSIDE the cage; caged commands need no
  credentials. NOTE: this applies to the *terminal* tool — file tools and
  plugins run in the harness process (next and previous points), where the
  env IS visible.
- **Plugins without sandbox**: they run in the harness process. They are
  code of the machine's OWNER (same model as hermes-agent). A plugin from a
  third-party repo (a cloned `.tlamati/plugins/`) is third-party code with
  your credentials: review it before running `tlamati` in repos you do not
  know.

### BLOCKS WITHOUT PROTECTING — removed

- **Network OFF by default** (state before SEC.1): it was a redundant second
  lock that added NO real defense (the trifecta already covers exfiltration)
  and only blocked legitimate work (pip, railway, curl, git clone).
  **BREAKING CHANGE 2026-11-21**: the network default went OFF→ON. The cage
  remains available (`--no-sandbox-net` / `sandbox: {net: false}`) for
  whoever wants the extra lock, but it is no longer imposed by default. Must
  be recorded in STABILITY.md (phase G1).

## Sandbox and flags (quick reference)

```yaml
# config.yaml (~/.config/tlamati/ or the project's tlamati.yaml)
sandbox:
  enabled: true   # bwrap cage for the terminal tool
  net: true       # network inside the cage (default ON since SEC.1)
```

Precedence: **explicit flag > config > default**. Flags are born
"opinionless" (`None`) so that config rules when the user says nothing
(`resolve_sandbox_flags` in cli.py, single shared core for headless and TUI).

| Flag | Effect |
|---|---|
| `--no-sandbox` | turns off the bwrap cage (warns `[sin sandbox]`, never silent) |
| `--sandbox-net` / `--no-sandbox-net` | network ON/OFF inside the cage |
| `--approve-tool NAME` | headless: pre-approves an ASK tool (equivalent to the TUI's "always") |
| `--plan-mode` | explore → approve plan → execute (mutually exclusive with `--approve-tool '*'`) |

Honest degradation: without the `bwrap` binary, the terminal runs WITHOUT a
cage, but the CLI warns at startup and the tool result carries the note. The
user always knows whether they are protected or not.

## Trust model (layers)

- **Subagents (D1)**: the child is NEVER more powerful than the parent —
  read-only toolset by construction (whitelist ∩ AUTO permission), maximum
  depth 1, hard turn and token caps that block BEFORE spending. The parent's
  plugin hooks are inherited by the child (hardening only).
- **MCP (D3)**: never auto-discovery (only servers declared by the owner in
  `tlamati.yaml` / `--mcp-config`). Per-call timeout (default 60s) and
  terminate→wait→kill shutdown: a hung server never hangs the run. MCP
  results do NOT enter microcompaction by default.
- **Audit (B5)**: every tool_event and turn_cost lands in an append-only
  SQLite ledger (`tlamati audit`). INTERNAL, non-disableable plugin;
  subagent events travel to the same db with the prefix `<parent>:sub-NN`.
  No invisible executions.

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
— it is documented behavior (parity decision, see ILLUSORY above).

We follow a 90-day disclosure window: we ask for a private report first and
coordinate a fix + advisory; credit to reporters who want it.
