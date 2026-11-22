# NOTICE — Tlamati

Copyright 2026 Leonardo Gutiérrez. Licensed under the Apache License, Version 2.0.

This product includes SEMANTICS and architectural patterns learned from the
following projects (no verbatim code copied unless stated; all licenses OSS):

- hermes-agent (MIT) — donor: Anthropic adapter semantics, tool-call
  normalization, budget/iteration patterns, "prompt caching is sacred"
  invariant, fuzzy-edit patch strategies.
- codex (Apache-2.0, OpenAI) — reference: compaction subsystem design
  (token-budget compaction, retained tool outputs).
- qwen-code (Apache-2.0, Alibaba) — reference: microcompaction
  (COMPACTABLE_TOOLS whitelist + placeholder + anti-collision regex).
- gemini-cli (Apache-2.0, Google) — reference: tool-output truncation
  (truncate at the spout), hooks registry.
- opencode (MIT) — reference: permission model design.
- grok-build — reference: interjection-core (SIGINT → pending user message).
- DeepSeek-Reasonix (MIT, discontinued 2026-11-12) — reference: everything-is-a-plugin
  architecture; used as design seed only, not a dependency.

This product includes VENDORED FILES (verbatim copies, license preserved):

- obsidian-skills (MIT, © 2026 Steph Ango (@kepano),
  github.com/obsidianmd/obsidian-skills) — the 7 skills of the official
  Obsidian plugin, vendored into `fixtures/agentskills_compat/` as the
  agentskills.io compatibility fixture (tests/test_skills_agentskills_compat.py).
  License text: `fixtures/agentskills_compat/LICENSE-OBSIDIAN-SKILLS`.
  Cloned 21-nov-2026 (depth 1). Vendored on purpose: if upstream changes or
  disappears, the test keeps measuring against the certified spec.
- gbrain `docs/STABILITY.md` — SEMANTIC donor for the repo's own STABILITY.md
  (adapted, not copied; see its header).

Closed-source systems (Claude Code, Cursor) were studied via BEHAVIORAL and
documented-evidence analysis only (REA). No code, minified bundles, or derived
lines from proprietary sources are included in this repository.
