> English translation of EVALS.md. The Spanish original is authoritative.

# EVALS — harness benchmark (E3b)

We measure what the PRD promises: **the harness matters**. Same model, same corpus,
different harness → different result. Anti-cheating rule (donor:
debugml.github.io/cheating-agents): single instruction (contents of
`instruction.md`, no added hints), `verify.py` decides success (exit 0 +
`VERIFY OK`), identical timeouts per harness (600 s), zero special configuration.

## Corpus

The 10 fixtures in `fixtures/` (terminal-bench-lite): 5 easy/medium
(`promedio`, `offbyone`, `conversor`, `import_roto`, `crear_modulo`) + 5 hard
(`multi_archivo`, `output_grande`, `git_history`, `instruccion_en_archivo`,
`test_driven`). Synthetic, modeled on real bugs, no personal data.
`git_history` is seeded with a `setup.sh` using fixed dates → deterministic
hashes across machines.

## HARNESS table (2026-11-18)

- Model: `qwen/qwen3-coder` via OpenRouter for ALL harnesses.
- Machine: WSL2, same session, same time window.
- Runner: `bench/runner.py` (external to the package; does not touch tlamati's code).
- Raw JSONL: `evals/benchmark_2026-11-18/<harness>.jsonl`.
- Schema: `{task, harness, success, turns, tokens_in, tokens_out, cache_read, duration_s, error}` — fields a harness does not expose = honest `null`.

<!-- TABLE: REAL results from the 2026-11-18 run (~23:45-00:10 CST, upstream healthy, 40/40 runs completed) -->

| harness | version | solved | easy (5) | hard (5) | tokens_in (sum) | tokens_out (sum) | cache % | total duration |
|---|---|---|---|---|---|---|---|---|
| codex | 0.133.0 | **10/10** | 5/5 | 5/5 | 1,536,586 | 19,100 | 95% | 302.6 s |
| hermes | (installed) | **10/10** | 5/5 | 5/5 | null | null | n/a | 206.3 s |
| opencode | 1.19.6 | 9/10 | 4/5 | 5/5 | 693,658 | 10,133 | 90% | 154.2 s |
| tlamati | 0.0.1 (main db0b7a1+) | 7/10 | 5/5 | 2/5 | **485,894** | 8,538 | 92% | **137.4 s** |

Failures (all legitimate, no upstream errors — every run completed its loop):

- `tlamati/instruccion_en_archivo` and `tlamati/test_driven`: stop=max_turns (20).
  The task requires more turns than budgeted; in the internal baseline
  (e3a_check, same fixture) test_driven PASSED with 9 turns — model variance
  on long tasks, not a harness bug.
- `tlamati/multi_archivo`: the model did not apply the 0.19 tax from the config
  (used the default) — a model reasoning failure, verify.py caught it.
- `opencode/promedio`: gave up in 1 turn without editing (the easiest one) — model
  variance; its internal suite still ended 9/10.

Honest reading (what this table DOES and DOES NOT say):

- codex and hermes solved everything; tlamati landed at 7/10 in this window. NO
  window-dressing: that's the data. tlamati's 3 failures were 2× turn ceiling +
  1× model reasoning on the hardest fixture.
- On EFFICIENCY, tlamati spent ~3.2× FEWER input tokens than codex
  (486k vs 1.54M) and was the fastest overall (137 s vs 303 s) — the PRD's
  minimal overhead (<8k) holds: it is the harness that drags the least context.
- One run per cell = model variance present (see the "easy" failures).
  The publishable figure must say "single run, <date>" — NEVER average
  silently. Future replicas: same runner, new dated dir.
- tlamati was the ONLY harness with a turn cap (--max-turns 20, session-16
  decision); codex/opencode/hermes ran without an explicit cap. Documented
  asymmetry: the 2 max_turns failures occurred UNDER that ceiling. Suggested
  future replica: raise the cap (e.g. 50) or remove it for strict equality.

### Post-table diagnosis (same night): tlamati's 3 failures are NOT systematic

Immediate re-run of the 3 failed tasks (`tlamati-eval --task X --max-turns 30`,
same harness, same model, same lightweight prompt):

| task | bench (1st run) | diagnosis (2nd run) |
|---|---|---|
| instruccion_en_archivo | exhausted 20 turns | PASSED end_turn, 12 turns |
| multi_archivo | incorrect default tax | PASSED end_turn, 8 turns |
| test_driven | exhausted 20 turns | PASSED end_turn, 9 turns |

Reading: the 3 failures were model VARIANCE (qwen3-coder is not deterministic
on long tasks), not a consequence of the minimal prefix. The hypothesis "cheap
harness → solves less" did NOT hold: the same lightweight context solved all 3 on
the second attempt. Methodological lesson: with N=1 a 7/10 and a 10/10 can be the
same harness with different luck — serious benchmarks run replicas and average;
here we publish a single dated run + this non-systematicity diagnosis.

Semantics notes (honesty of the comparison):

- `tokens_in` for tlamati and codex INCLUDES cache_read (OpenRouter convention);
  in opencode the event's `input` EXCLUDES `cache.read` → the runner sums
  `input+cache.read` to compare apples with apples.
- hermes `-z` (one-shot) only prints final text: it does not expose tokens → `null`.
  Its results measure ONLY % solved and duration.
- codex does not expose comparable agent turns → `turns: null`.
- Exact configuration per harness:
  - tlamati: `tlamati -p "$INSTR" --json --approve-tool '*' --max-turns 50 --no-session`
    (bwrap sandbox ON by default, network OFF). In the 1st run (benchmark_2026-11-18/)
    the cap was 20 — asymmetry corrected for the replica (benchmark_2026-11-18_run2/):
    the other harnesses run without a turn cap, so tlamati carries a loose ceiling
    (50 ≫ max observed 23) to equalize circumstances.
  - opencode: `opencode run "$INSTR" --dir WS --auto --format json -m openrouter/qwen/qwen3-coder`.
  - codex: `codex exec -C WS -s workspace-write --skip-git-repo-check --ephemeral --json "$INSTR"`
    with a separate `CODEX_HOME` (`~/.cache/tlamati-bench-codex-home`, generated by
    `bench/runner.py`; NOTE: NOT under /tmp — codex rejects helper binaries in
    temporary dirs) and `config.toml`:
    `model_provider="openrouter"`, `base_url="https://openrouter.ai/api/v1"`,
    `env_key="OPENROUTER_API_KEY"`, `wire_api="responses"`, `approval_policy="never"`.
  - hermes: `hermes -z "$INSTR" --safe-mode --yolo -m qwen/qwen3-coder --provider openrouter`
    (`--safe-mode` = bare default harness: no user config/memory/skills/plugins/MCP).

## REPLICA run2 table (2026-11-19) — same circumstances + tlamati --max-turns 50

- Same runner, same model (`qwen/qwen3-coder` OR), same 10 fixtures,
  upstream healthy start to finish (watchdog: 2 probes OK before starting;
  0 429/504 errors in the JSONL, verified with grep).
- Raw JSONL: `evals/benchmark_2026-11-18_run2/<harness>.jsonl`.
- Only change vs run1: tlamati `--max-turns 50` (founder's equality-of-
  circumstances principle: the other harnesses run without a turn cap).

| harness | solved run1 | solved run2 | tokens_in run2 | cache run2 | duration run2 |
|---|---|---|---|---|---|
| codex | 10/10 | **10/10** | 1,088,716 | 87% | 475.6 s |
| hermes | 10/10 | **10/10** | null | n/a | 1245.4 s |
| opencode | 9/10 | 7/10 | 383,201 | 84% | 129.2 s |
| tlamati | 7/10 | 8/10 | 735,322 | **98%** | 239.3 s |

Run2 failures (autopsy with the audit ledger, not speculation):

- `tlamati/instruccion_en_archivo`: EVAL-HARNESS ASYMMETRY diagnosed with the
  ledger (audit.db session 20261119-120939): the model calls `enter_plan_mode`
  on its own; in headless there is NO human approver and `exit_plan_mode` is
  fail-closed by design (golden rule C5: only real human approval leaves
  plan-mode). The model got locked in: 4 failed exit attempts (turns 6/9/15/22),
  write tools denied, 50 turns burned. In the real TUI
  (E1) the approver exists → this is NOT a product bug, it is the eval running
  without the human piece the feature assumes. Pending fix (one line): the
  headless runner must pass `--no-plan-mode` to equalize circumstances — the
  other harnesses do not offer plan-mode to the model in benchmark mode.
- `tlamati/multi_archivo`: the model used tax 0.16 (default) instead of
  the 0.19 from the config — SAME failure as run1, even though the diagnostic
  re-test on Nov 18 passed it. 2 identical failures out of 3 runs → hardest
  fixture in the set for qwen3-coder with the minimal prefix. Model variance,
  verify.py caught it with exact values.
- `opencode`: crear_modulo (did not create the module), import_roto (did not fix
  the import), instruccion_en_archivo (violated 2 SPEC rules) — model
  variance; run1 had failed ONLY promedio. N=1 per cell: the per-cell figure
  moves ±3 between runs with the same harness.

Run1-vs-run2 reading (rule: never average silently; both runs dated and
separate):

- codex and hermes: stable at 10/10 in both runs.
- opencode: 9→7. tlamati: 7→8. The % solved ordering is NOT stable with
  N=1; what DOES repeat: tlamati keeps the highest cache_read of all
  (92% run1 → 98% run2, the only harness that rises with the warm prefix) and
  codex is the most expensive in tokens (1.1-1.5M per run).
- The turn cap stopped being a factor: with 50, test_driven passed (11 turns)
  and no tlamati task died on the ceiling except the plan-mode lock-in
  (which is an asymmetry, not a ceiling: 50 turns trapped unable to write).
- hermes run2 duration (1245 s) vs run1 (206 s): hermes without token
  visibility runs at its own pace with its own heuristics (multi_archivo 356 s,
  output_grande 294 s); hermes's duration is NOT comparable between runs
  and is reported as raw data, without narrative.

## E3c table (2026-11-19) — EXPANDED corpus: 15 fixtures × 3 replicas (45 runs per harness)

- Corpus: the previous 10 fixtures + 5 robustness ones (`anti_bucle_imposible`,
  `context_rot_20_archivos`, `recuperacion_test_roto`,
  `edicion_quirurgica_grande`, `rollback_o_regresion`) seeded and validated
  (seed FAILS, reference solution PASSES, anti-corruption guard).
- Same model `qwen/qwen3-coder` OR for all harnesses; runner with
  `--runs 3` (replicas) and real `cost_usd` (OR prices verified live).
- Raw JSONL: `evals/benchmark_2026-11-19_e3c/<harness>.jsonl` (45 lines each).
- hermes: CUT before starting by founder decision (it is the slowest);
  it will run at the end of the campaign, with qwen3-coder only.

| harness | runs | all-replicas | at-least-one | cost USD | tokens_in | cache % | duration |
|---|---|---|---|---|---|---|---|
| tlamati | 37/45 | 11/15 | 14/15 | **$0.18** | **1.39M** | 92.1% | **16.9 min** |
| opencode | 42/45 | 13/15 | 15/15 | $0.49 | 4.05M | 95.6% | 17.3 min |
| codex | 43/45 | 14/15 | 15/15 | $0.86 | 7.35M | 96.1% | 38.0 min |

HONESTY RULE applied to tlamati 37/45: its 8 failures are ALL upstream
provider errors (rc=4 "Provider returned error" — OpenRouter indigestion
in that window), NOT harness errors. A failure whose `error` field is a
provider issue does not count against the harness (inherited rule B1/B5).
At-least-one replica: 14/15 — wherever the model could work, it solved;
`anti_bucle_imposible` 3/3.

Reading: tlamati solved with **5.3× fewer tokens than codex** and **2.9× fewer
than opencode**, and was **2.2× faster than codex** at the lowest cost ($0.18 vs
$0.86). The PRD's promise (minimal overhead, "the harness that drags the least
context") holds on the expanded corpus with replicas.

### Model campaign IN PROGRESS (Nov 19, as of publishing this table)

Harness×model matrix extended with `qwen/qwen3.8-flash`, `deepseek/deepseek-v3.2`
and `moonshotai/kimi-k2.7-code` (orchestrators `bench/campaign_e3c.sh` +
`bench/campaign_ext.sh`; dirs `evals/campaign_2026-11_<slug>/`). First
complete result: **flash × tlamati = 45/45 runs, 15/15 all-replicas,
15/15 at-least-one, $0.13, 1.75M tok_in, zero upstream errors** —
first perfect combo of the campaign. The full table will be added when it
finishes (same honesty rule per cell).

## H9 — frontier: does the codex/tlamati ratio grow with a long horizon?

Three campaigns with frontier models (gpt-6.2-sol, claude-opus-5.5,
qwen3.8-max-0902) via OpenRouter, harnesses tlamati vs codex. Raw details:
`evals/H9_RESULTS_2026-11-20.md` (v2) and `evals/H9_V4_RESULTS.md` (v4).

- **v2 ×1 + ×3** (short fixtures L1/L2, cadena_defectos_l1 + ducto_reglas_l2,
  4-10 turns): the frontier collapses short tasks — the turn ceiling is
  never approached. codex/tlamati cost ratios: gpt ×3.8-5.4, qwen ×1.9-3.0,
  opus ×0.6-1.8 (parity, confirmed with ×3: it was not noise). $2.03 + $4.70.
- **v3 INVALIDATED**: tlamati's persistent memory leaked the fixes to opus
  (accordion, 7 turns) and the docstrings contained the spec → illegitimate
  batch. Data archived in evals/_abortado_v3/ (encrypted), not usable for the
  thesis.
- **v4 clean cascade** (ducto_cascada_l3, 34 modules, staggered reveal ×33,
  forced horizon 36-110 turns; hostile environment fixes A-F; n=1 + replicas
  gpt/opus ×3, qwen ×2; 22/22 success; $9.31):

| model | dur codex/tlamati | COST codex/tlamati | v2 (L1/L2) cost |
|---|---|---|---|
| gpt-6.2-sol | ×2.30 | **×8.58** | ×5.4 / ×3.9 |
| opus-5.5 | ×1.10 | ×1.89 | ×1.8 / ×0.8 |
| qwen3.8-max | ×1.03 | **×0.98 (inverted)** | ×1.9 / ×3.0 |

**H9 verdict**: with a forced long horizon, the COST ratio grows on gpt
(→×8.6) and holds on opus (×1.9) — the cost-pivoted thesis holds at the
frontier. Measured mechanism: codex consumes 3-4x tokens_in on the same task
(context snowball: it re-sends history and re-reads files between
reveals; tlamati keeps a bounded active window). qwen3.8-max INVERTS the
ratio: it wanders inside the cascade (75±33 turns in tlamati) and loses the
advantage — the harness benefit depends on the model, it is not universal.

Protocol symmetry (shielding): both arms with the same 33 reveals and
comparable horizon — what is measured is what each harness does with the
accumulated history between reveals, not who sees more. Anti-cheat audit on the
11 tlamati arms (fuera_workdir=0, memory=0, canary intact): 2 flags investigated
and resolved as auditor false positives (gpt r3: indirect reveals via the
`.next` helper; qwen: "vacio" was the m07 bug corrected to "vacío").

## Outside the table (and why)

- **claude code / grok**: tied to proprietary brains — the delta would measure
  the model, not the harness (founder decision, Nov 16).
- **gemini-cli**: verified in its installed bundle (0.68.0) — it has no
  OpenAI-compatible path (zero `OPENAI_API_KEY`/`chat/completions`); its only
  custom mode is `GOOGLE_GEMINI_BASE_URL` (Gemini API). It cannot run
  qwen3-coder via OpenRouter.

## Reproduction

```bash
uv tool install --from . tlamati --reinstall
python3 bench/runner.py --probe          # upstream health (1 task × harness)
python3 bench/runner.py --out evals/benchmark_$(date +%F)/
```

The API key is taken from `OPENROUTER_API_KEY` (env or `~/.hermes/.env`).

## Public context (another lead, not directly comparable)

Terminal-Bench 4.1 (tbench.ai, captured 2026-11-17): the official table is
already a harness×model matrix. Anchors: Qwen3.8-Max-0902+Claude Code = 27.0% (max
variant, NOT qwen3-coder); Grok 4.7+Grok Build = 38.8%; Opus 5.5+CC = 65.8% (~$4.7k
per run). Dirac case (HN 47920787): OSS agent 65.2% vs Google's official agent
47.8% with the SAME Gemini-3-flash = **+17 pts harness-only**. Detail and
sources: `research/08_BENCHMARKS_EXISTENTES.md`. The Terminal-Bench lead is
OSS (harbor-framework); what costs money is the frontier brain — that's why this
benchmark fixes the brain and varies the harness.
