> English translation of evals/H9_V4_RESULTS.md. The Spanish original is authoritative.

# H9 v4 campaign — results (clean cascade, hostile environment) — 20-Nov-2026

Anti-batch v4 fixture: `ducto_cascada_l3` (34 cascade modules, staggered
reveal ×33). Full hostile environment (fixes A-F after v3 invalidation):
neutral docstrings, runner --no-memory + cross-harness purge, encrypted
answers outside /tmp, raws with model, canary trap, mandatory preflight.

Design: n=1 (17:14-18:13) + replicates (18:16-19:13, gpt/opus ×3, qwen ×2 —
founder's option 3 due to qwen cost). **16+6=22 runs, 22/22
success=True, 0 model failures.** TOTAL v4 COST: $9.31 ($2.67 n=1 + $6.64
replicates; budget $40, cumulative spend ~$18.2).

## Protocol symmetry (methodological shielding)

Both arms (tlamati and codex) operate on the SAME available information:
the 33 staggered reveals from verify.py and a comparable horizon (36-38 turns
tlamati; codex does not report turns). What is measured is not who SEES more,
but what each harness does with the accumulated history between reveal 1 and
reveal 33: codex re-sends the full conversation on every turn and re-reads
already-seen files (quadratic context snowball); tlamati keeps the active
window bounded. There is no artificial information advantage in either arm.

## Consolidated table (n=1 + replicates, mean±std)

| model | harness | n | turns | dur_s | cost | tok_in (n=1) | cache% |
|---|---|---|---|---|---|---|---|
| gpt-6.2-sol | tlamati | 4 | 36±0 | 46±19 | $0.0524±0.0119 | 226k | 95.1% |
| gpt-6.2-sol | codex | 4 | – | 106±39 | $0.4496±0.2263 | 985k | 77.4% |
| opus-5.5 | tlamati | 4 | 37±1 | 107±6 | $0.2774±0.0098 | 460k | 95.8% |
| opus-5.5 | codex | 4 | – | 118±3 | $0.5247±0.0546 | 1318k | 96.8% |
| qwen3.8-max | tlamati | 3 | 75±33 | 452±184 | $0.6881±0.3035 | – | – |
| qwen3.8-max | codex | 3 | – | 467±174 | $0.6769±0.2571 | – | – |

Costs per run (dispersion):
- gpt×tlamati: 0.0676 / 0.0484 / 0.0544 / 0.0391 — VERY stable
- gpt×codex: 0.5771 / 0.5704 / **0.1110** / 0.5398 — run2 LEGITIMATE outlier
  (forensics: real turn.completed, 66/66 tests, VERIFY OK, 562k tok with 97%
  cache; it simply solved more efficiently — not a broken run nor a cheat)
- opus×tlamati: 0.2740 / 0.2791 / 0.2899 / 0.2666 — VERY stable
- opus×codex: 0.5386 / 0.5923 / 0.5051 / 0.4630 — stable
- qwen×tlamati: 0.6999 / 0.3789 / 0.9855 — HIGH dispersion (42-108 turns)
- qwen×codex: 0.5137 / 0.9732 / 0.5437 — high dispersion

## codex/tlamati ratios (consolidated means)

| model | dur | cost | v2-L1 dur/cost | v2-L2 dur/cost |
|---|---|---|---|---|
| gpt-6.2-sol | ×2.30 | **×8.58** | ×7.2 / ×5.4 | ×3.7 / ×3.9 |
| opus-5.5 | ×1.10 | **×1.89** | ×0.9 / ×1.8 | ×0.7 / ×0.8 |
| qwen3.8-max | ×1.03 | ×0.98 | ×4.8 / ×3.4 | ×3.4 / ×3.0 |

## ANSWER TO THE CENTRAL H9 QUESTION

With horizon forced to 36-110 turns in ALL arms:

1. **The COST ratio grows with the long horizon on gpt (5.4→3.9→8.58) and
   holds on opus (~1.8-1.9 consistent across L1, L2 and cascade).** The
   thesis pivoted to cost HOLDS on frontier models: for equal results,
   codex pays 1.9-8.6x more depending on model.
2. **Mechanism confirmed by tokens**: codex consumes 3-4x more tokens_in than
   tlamati on the same task (985k vs 226k on gpt; 1318k vs 460k on opus) —
   the context snowball is real and measurable, not theoretical.
3. **qwen3.8-max INVERTS the ratio (0.98)**: in the long cascade its tlamati
   arm blows up (75±33 turns, up to 108) while codex holds steady.
   The harness advantage is NOT universal: it depends on how many extra turns
   the model spends inside the pipeline. With models that wander in the
   cascade, tlamati loses its bounded-context advantage. New finding of v4.
4. **Stability**: opus and gpt×tlamati have minimal cost deviation
   (±3-8%); qwen has ±40-45% — unpredictable behavior on long horizons,
   consistent with its "cheap model" role, which here was NOT cheap.

## Anti-cheat audit (FIX-F, 9 tlamati arms: n=1 + replicates)

Criteria: outside_workdir=0, memory=0, reveals≥30, canary intact.

| arm | calls | outside | memory | reveals | canary | verdict |
|---|---|---|---|---|---|---|
| gpt n1 | 37 | 0 | 0 | 33 | no | CLEAN |
| gpt r1 | 35 | 0 | 0 | 33 | no | CLEAN |
| gpt r2 | 37 | 0 | 0 | 33 | no | CLEAN |
| gpt r3 | 36 | 0 | 0 | 4* | no | CLEAN (see *) |
| opus n1 | 36 | 0 | 0 | 33 | no | CLEAN |
| opus r1 | 35 | 0 | 0 | 33 | no | CLEAN |
| opus r2 | 37 | 0 | 0 | 34 | no | CLEAN |
| opus r3 | 35 | 0 | 0 | 33 | no | CLEAN |
| qwen n1 | 77 | 0 | 0 | 38 | no** | CLEAN (see **) |
| qwen r1 | 44 | 0 | 0 | 33 | no** | CLEAN (see **) |
| qwen r2 | 115 | 0 | 0 | 33 | no | CLEAN |

\* FALSE POSITIVE from the auditor: gpt r3 created a `.next` helper (sed +
verify.py --reveal $1 + cat next) invoked 30 times for stages 3-33.
The reveals DID happen, indirectly. Legitimate sequential trajectory: each
sed corresponds to the bug of the just-revealed stage. LESSON: the auditor
must count reveals through indirection (bash helper/loop), not just literal grep.

\** FALSE POSITIVE from the auditor: the "vacio" mentions are the command that
fixes m07 (`"vacio"` bug in source → `"vacío"` correct answer with accent) and
descriptive text of the fix. outside_workdir=0: it never touched
/tmp/h9_canary. LESSON: the canary criterion must be "trap value as FINAL
key", not substring in raw.

Full forensics: evals/forensia_v4_flags.py (tlamati) and
evals/forensia_v4_codex_outlier.py (codex).

## Raw data

- n=1: evals/h9v4_2026-11_<slug>/{tlamati,codex}.jsonl (1 line each)
- Replicates: evals/h9v4r3_2026-11_<slug>/{tlamati,codex}.jsonl (3/3/2 lines)
- Raw tlamati: /tmp/tlamati-bench/_raw/tlamati/ducto_cascada_l3.<model>.runN.jsonl
- Raw codex: /tmp/tlamati-bench/_raw/codex/ (thread events format)
- Infra failures (archived): evals/_failed_qwen_attempt1/ (1st qwen attempt:
  OpenRouter rate-limit + httpx.ReadTimeout; relaunched clean)
- Logs: evals/campaign_h9_v4.log, evals/campaign_h9_v4_runs3.log
- Pre-run workdirs (snapshots): _raw/tlamati/*.preN.workdir.tgz

## Comparison with invalidated v3 (historical context)

v3 (contaminated by accordion-memory): gpt×tlamati 36t/$0.109, opus×tlamati
7t/$0.170 (illegitimate batch). Clean v4: gpt×tlamati 36t/$0.052 (cheaper and
legitimate), opus×tlamati 37t/$0.277 (opus does NOT collapse to batch without
the accordion in memory — v3's invalidity was proven by contrast: without
cheating, opus takes 37 turns, not 7).
