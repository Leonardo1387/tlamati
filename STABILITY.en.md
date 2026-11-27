> English translation of STABILITY.md. The Spanish original is authoritative.

# STABILITY.md — what tlamati promises (and what it doesn't)

No marketing, same philosophy as SECURITY.md: explicit limits are a feature.
This document states what a script, an agent, or an integration built on
tlamati can rely on, how breaking changes are announced, and what falls
outside the promise.

Donor: gbrain `docs/STABILITY.md` (adapted, not copied — tlamati is smaller
and its promise is proportional).

## Channels

- **alpha (`main`)**: continuous development. Anything may change between
  one commit and the next, with one exception: breaking changes to the
  stable surface are recorded in `CHANGELOG.md` ("Unreleased" section)
  before or in the same commit that introduces them.
- **releases (tags `v*`)**: the promise below applies from tag to tag. The
  current release is `v0.1.0`; whatever lives on `main` after the tag is
  alpha until the next one.

## What is stable since v0.1

1. **Memory file format**: `MEMORY.md` and `USER.md` — markdown entries
   separated by `§`. They are the ONLY source of truth for memory.
   A file written by an old version of tlamati is always readable by a new
   one.
2. **SKILL.md format**: YAML frontmatter (`name`, `description`) + markdown
   body, compatible with agentskills.io. Unknown fields from the spec are
   ignored without crashing.
3. **The documented CLI**: commands and flags that appear in `tlamati --help`
   and in the README. Undocumented flags are not part of the promise.
4. **Exit codes** (headless; contract E2):

   | code | meaning |
   |---|---|
   | 0 | `end_turn` — the agent finished its work |
   | 1 | `max_turns` — turns exhausted (task incomplete, not an error) |
   | 2 | misuse / failed startup (no api key, invalid config, argparse) |
   | 3 | `budget_exceeded` — context budget exceeded |
   | 4 | `error` — provider or loop failure (unknown stop_reason = fail-closed here) |
   | 5 | `aborted` — aborted by the user |
   | 6 | `refusal` — the model refused |
   | 7 | `max_tokens` — output token cap |
   | 8 | `stall` — loop detected |

5. **`--json` contract (JSONL)**: stdout is EXCLUSIVE to the stream (one
   JSON object per line with `ts`, `event`, and a flat payload); stderr stays
   human; the final event is ALWAYS `result` with `stop_reason`, `usage`, and
   `exit_code`. A CI consumer needs to parse nothing else to decide.
6. **Byte-identical `render_for_prompt()`**: the memory/instructions block
   that enters the system prompt does not change bytes between releases if
   the content does not change (sacred cacheable prefix — rule of commit
   `7751663`). No new metadata (sidecar, tiers) is rendered into the prompt.
7. **Memory caps**: 100 entries / 24,000 chars per target. Raising them is a
   compatible change; lowering them is breaking.
8. **Advisory never mutates**: dream gaps (G2), cold entries from
   `memory status` (M8b), and `memory lint` findings (M8c) are informative.
   They do not write, delete, or reorder memory files.
   `memory lint` always returns exit 0. Nothing is deleted silently.

## What is NOT promised

- **Internal APIs of `src/tlamati/**`**: importable, but not a contract.
  The stable surface is the CLI and the file formats.
- **`.meta.json` sidecar fields**: it is DERIVED from MEMORY.md/USER.md,
  rebuildable, fail-soft (memory rules; the sidecar never blocks a write).
  It may migrate with a version key in any release.
- **Human message wording** (everything that is not `--json`),
  internal/undocumented flags.
- **Search ranking, speed, and exact results of model-dependent features**
  (consolidation/dream, routing): non-deterministic by nature.
- **The TUI**: interactive and evolving; its layout and keybindings are not
  a contract.

## How breaking changes are announced

- Every change that breaks the stable surface is recorded in
  `CHANGELOG.md`, "Unreleased" section, with the `BREAKING` label.
- **gbrain rule: removals require deprecation.** A documented command, flag,
  or behavior is announced first, keeps working for at least 1 minor release
  with a warning, and only then is removed.
- **Sole exception: security and data loss.** A fix for a security hole or
  for something that loses data may change behavior immediately; its
  changelog entry states which of the two it is and what to do.
- A default change counts as breaking (see the log below).

## Breaking change log

- **2026-11-21 (Unreleased, post-v0.1.0) — SEC.1: network default OFF→ON.**
  The sandbox no longer blocks network by default (`config.yaml` governs;
  precedence: CLI flag > config > default `net=True`). An agent that
  previously said "I have no network" now has it, with the lethal trifecta as
  compensation (egress AUTO→ASK after consuming untrusted content — see
  SECURITY.md). Commit `b25745e`. It is a deliberate, documented default
  change, not an accident: network OFF by default made the harness lie about
  its capabilities.
