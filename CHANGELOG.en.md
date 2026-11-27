> English translation of CHANGELOG.md. The Spanish original is authoritative.

# CHANGELOG

Format: one section per release; unreleased changes live under "Unreleased".
Changes that break the stable surface (STABILITY.md) are labeled `BREAKING`
and follow the deprecation rule documented there.

## Unreleased

(empty)

## v2.1.0 (2026-11-26)

### Added

- **Native vision v2.1** — `ImageBlock` at the loop's waist: `read_file`
  sees images, `--image` on the CLI attaches them to the first message.
  Adapters serialize them to each provider's native format (OpenAI content
  blocks / Anthropic image blocks).

### Fixed

- **Retry with backoff on transient provider errors** — an upstream rate
  limit (e.g. Alibaba via OpenRouter) killed the run with an empty response
  (`stop=error`, `in=0 out=0`): the loop never consulted
  `ProviderError.retryable`. Now `_stream_one_turn` retries up to 4 times
  with exponential backoff 4s·2^n + jitter on 429/5xx/transport errors or
  transient messages inside `MessageEnd(error)` ("rate limit", "overloaded",
  "upstream error", in-flight credits). Deterministic errors are not
  retried. New `retry` event {attempt, delay_s, error} for TUI/JSON.

## v2.0.0 (2026-11-26)

Creative-specialization release: the harness now talks to creative
applications (Blender, Unreal Engine) INSIDE the loop, not around it.

### Added

- **MCP Streamable HTTP** (`mcp.servers[].url`) — the transport Epic's
  official MCP was missing (HTTP/SSE-only). Automatic `Mcp-Session-Id`
  handshake with renegotiation if the editor restarts, serialized calls
  (measured restriction of Unreal's server), `Origin` header. Verified
  against a live Unreal Engine 5.8.4: 53 toolsets navigable through 3
  meta-tools (`list_toolsets`/`describe_toolset`/`call_tool`). Full
  dogfooding: a level built from an imported DXF, scene cleanup and actor
  spawning, all through the harness.
- **web_fetch** — URL reading (GET, text only, 200 KB cap cut at the source
  with an honest marker). ASK + `produces_untrusted` ALWAYS; runs outside
  the bwrap jail (the network gate is the permission).
- **ctrl+c stops the agent** without killing the app + mid-turn **steering**
  (out-of-band messages while the model works).
- **ctrl+c copies the selection** when idle (no longer exits the TUI; ctrl+q
  exits).
- (Already included in the remapped v0.1.0 tag: sandbox hardening
  `bwrap --clearenv` + fail-closed whitelist — the parent process's API
  keys are NO LONGER visible inside the jail.)
- `tlamati audit`: MCP events recorded in the append-only ledger like any
  other tool (decision + args + result hash).

### Changed

- README: installation via `pip install git+https://...` (PyPI not yet);
  documentation for `web_fetch` and `mcp.servers` with `url:`; corrected
  MCP config example (list of servers, not a map).
- Full sanitization of the public history (filter-repo) + pruning of
  pre-sanitization development branches from the remote.

### Release notes

- Version jump 0.1.0 → 2.0.0 by maintainer product convention (the SEC.1
  breaking change to sandbox networking, documented in STABILITY.md, plus
  the new v2 surface: networking + MCP HTTP).
- Suite: 690 tests, ruff + mypy strict green, GitHub Actions CI.

## v0.1.0

- First tagged release (tag `v0.1.0`).
