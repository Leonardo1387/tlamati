> English translation of evals/INFORME_ARNES_CONSOLIDADO.md. The Spanish original is authoritative.

# CONSOLIDATED REPORT — tlamati vs codex vs hermes vs opencode

Date: 20-Nov-2026. Sources: this repo's OWN data (all runs executed on the
same WSL2 machine, same model qwen/qwen3-coder via OpenRouter except
H9-frontier). Raw JSONL in evals/. This report does NOT include external
data (see final section on that possibility).

## 1. What was measured and with what rigor

Three corpora, increasing complexity:

| corpus | fixtures | typical horizon | replicates | harnesses |
|---|---|---|---|---|
| lite (18-Nov) | 10 (5 easy + 5 hard) | 4-23 turns | ×2 runs | 4 |
| E3c (19-Nov) | 15 (+5 robustness) | 4-30 turns | ×3 | 4 |
| H9 v2 (20-Nov) | 2 anti-batch (L1/L2) | frontier collapses to 4-10t | ×1 and ×3 | 2 (tlamati/codex) × 3 frontier models |
| H9 v4 (20-Nov) | ducto_cascada_l3 (34 modules, runtime reveal) | 36-110 forced turns | n=1 + ×3/×2 | 2 × 3 frontier models |

Anti-cheating rules (donor: debugml.github.io/cheating-agents): single
instruction, verify.py decides success, identical timeouts, zero special
configuration, upstream failures filtered and reported separately.

## 2. CENTRAL RESULT — E3c corpus (15 fixtures × 3 replicates, qwen3-coder)

| harness | runs OK | out of 15 (all ×3) | cost | tokens_in | total dur |
|---|---|---|---|---|---|
| **tlamati** | 37/45* | 11/15 | **$0.18** | **1.39M** | 16.9 min |
| opencode | 42/45 | 13/15 | $0.49 | 4.05M | 17.3 min |
| codex | 43/45 | 14/15 | $0.86 | 7.35M | 38.0 min |
| hermes | 45/45 | 15/15 | n/a** | n/a** | 40.0 min |

\* All 8 tlamati failures are rc=4 "Provider returned error"
(OpenRouter indigestion in that window) — infrastructure failures, not the
harness's. At-least-one-replicate: tlamati 14/15.
\** hermes one-shot does not expose tokens/cost — only % solved and duration.

Reading: tlamati solved with **5.3x fewer tokens than codex**, **2.9x fewer
than opencode**, at the lowest cost and shortest duration. hermes solved
everything (45/45) but took 2.4x longer than tlamati. codex and hermes are
the most reliable in absolute terms; tlamati is the most efficient per unit
of work.

## 3. Long horizon with FRONTIER models (H9 — tlamati vs codex only)

hermes/opencode did NOT run in H9 (hermes by founder's cost/time decision;
opencode outside the frontier scope). With gpt-6.2-sol, opus-5.5 and
qwen3.8-max on ducto_cascada_l3 (34 modules, staggered runtime reveal,
audited hostile anti-cheat environment):

| model | cost ratio codex/tlamati | duration ratio |
|---|---|---|
| gpt-6.2-sol | **×8.58** (tlamati wins) | ×2.30 |
| opus-5.5 | **×1.89** (tlamati wins) | ×1.10 |
| qwen3.8-max | ×0.98 (INVERTED) | ×1.03 |

Mechanism verified by tokens: codex re-sends the full history and
re-reads files between stages (quadratic snowball; 985k-1.32M tok_in vs
226k-460k for tlamati for the same result). The harness advantage depends
on the model: with qwen3.8-max (which wanders, 75±33 turns) it evaporates.

22/22 runs success=True, $9.31 spent, clean anti-cheat audit across
the 11 tlamati arms (0 reads outside workdir, 0 memory, canary
intact; 2 flags investigated = auditor false positives).

## 4. Conclusion per harness

**tlamati** — The most efficient in the panel when the provider is healthy:
lowest cost, shortest time and 3-5x fewer tokens than codex in ALL corpora,
an advantage that GROWS with the long horizon on frontier models (×3.9→×8.6
on gpt). Honest weaknesses: (a) 7-8/15 in a single lite run due to model
variance with the minimal prefix (the hard fixtures demand more context than
minimalism offers — the diagnostic re-test passed all 3); (b) the headless
plan-mode corner case (eval-harness asymmetry, one-line fix pending);
(c) with wandering models (qwen3.8-max) the advantage inverts.

**codex** — The most reliable in gross rate (43-45/45) alongside hermes, and
the only one that never failed for harness reasons. But it pays the context
snowball: 4.8x tlamati's cost in E3c ($0.86 vs $0.18) and 1.9-8.6x on
frontier with long horizon. In frontier+cascade, codex NEVER wins on cost.

**hermes** — 45/45 in E3c, the only perfect score in the extended corpus.
Does not expose tokens/cost (a measurement limitation, not a virtue). It is
the slowest (40 min, 2.4x tlamati). Its profile: maximum resolution, no
efficiency data — not comparable on the axis this benchmark measures
(context/cost).

**opencode** — Consistent middle ground: 42/45 in E3c, $0.49 (2.7x tlamati),
4.05M tokens (2.9x tlamati), duration similar to tlamati. No systematic
failures of its own; its variance is the model's.

## 5. Defensible claim (one line)

With the same brain (qwen3-coder), tlamati solves the tasks at ~21% of
codex's cost and 37% of opencode's while dragging 3-5x less context;
with frontier brains on a forced long horizon, the cost advantage grows
(×8.6 on gpt-6.2-sol, ×1.9 on opus-5.5) and inverts only when the model
wanders (qwen3.8-max ×0.98). hermes solves everything but exposes no
efficiency metrics and is the slowest.

## 6. Caveats (full honesty)

- n=1 per cell in lite; E3c ×3; H9-v4 ×3/×2. Single-run cells
  move ±3 (documented in EVALS.md).
- A single non-frontier model (qwen3-coder) in the 4-harness comparison.
  The frontier extension is tlamati vs codex only.
- hermes ran with --safe-mode (bare harness): not the configuration of a
  real user with skills/memory.
- Costs = OpenRouter prices of 18-20-Nov-2026; cache_read bills ~10%.
- hermes duration not comparable across runs (its own heuristics).

## 7. External data from other harnesses (proposal, NOT included)

Founder's idea: incorporate into the report public benchmarks where OTHER
harnesses (claude code, aider, gemini-cli, grok build...) were measured
against codex, and use codex as a bridge to position tlamati indirectly —
marking every figure as EXTERNAL. Existing anchor: Terminal-Bench 4.1
(tbench.ai) is already a harness×model matrix; dirac case (HN 47920787): OSS
agent 65.2% vs official Google agent 47.8% with the same Gemini-3-flash
(+17pts harness-only). Rules to do it with rigor: (1) NEVER average external
with own data in the same table; (2) "source" column + date + distinct
fixture in every row; (3) the bridge is only valid if external-codex and
own-codex are comparable versions/dates — otherwise, present as separate
context. Detail and sources: research/08_BENCHMARKS_EXISTENTES.md.

## 8. EXTERNAL TABLE (Terminal-Bench 4.1, tbench.ai, captured 20-Nov-2026)

EXTERNAL SOURCE — NOT mixable with the own tables (different fixtures and
difficulty, runs of $200-16,500). Listed as CONTEXT and as a "codex
bridge": our 3 H9 frontier models appear here with OTHER harnesses.

| # | Model | Harness | Resolution | Tokens | Run cost |
|---|---|---|---|---|---|
| 1 | Copilot Fusion (max) | GitHub Copilot | 71.2% ±2.9 | 3.3B | $2.0k |
| 2 | Opus 5.5 (max) | Claude Code | 65.8% ±3.1 | 8.0B | $4.7k |
| 5 | Sonnet 5.5 (max) | Claude Code | 63.9% ±3.0 | 19.4B | $7.3k |
| 6 | GPT-6.2 Astra (max) | Codex | 62.1% ±2.3 | 1.1B | $1.4k |
| 7 | **GPT-6.2 Sol (max)** | **Codex** | 61.5% ±2.8 | 1.1B | $0.3k |
| 22 | Grok 4.7 (xhigh) | Grok Build | 38.8% ±3.6 | 5.5B | $3.7k |
| 29 | **Qwen3.8-Max-0902 (max)** | **Claude Code** | 27.0% ±3.9 | 3.0B | $4.6k |

Possible bridges (our H9 vs this leaderboard, SAME model):
- **GPT-6.2 Sol**: here Codex=61.5% ($0.3k). In our H9, tlamati did the
  SAME task as Codex at 1/8.6 of the cost. tlamati is not on the leaderboard.
- **Opus 5.5**: here Claude Code=65.8% ($4.7k). In H9, tlamati vs codex with
  Opus = codex 1.9x more expensive. We do not compare tlamati vs Claude Code
  (different fixtures) → it CANNOT be claimed that tlamati wins/loses vs
  Claude Code.
- **Qwen3.8-Max-0902**: here Claude Code=27.0% ($4.6k, note: "max" variant,
  NOT the qwen3-coder of our lite bench). In H9 with this model the ratio
  inverted (tlamati more expensive) — coherent: it is the hard-to-tame model.

Rules met: (1) external in a SEPARATE table; (2) source+date+harness per
row; (3) the bridge is used only where the model matches AND it is declared
that the fixtures differ (percentages from different tracks are not averaged).
tlamati/hermes/opencode do NOT appear on the public leaderboard → there is no
direct external number for them; the only anchoring is via the shared
model+codex.
