> English translation of bench/README.md. The Spanish original is authoritative.

# bench/ — external harness benchmark (E3b)

EXTERNAL runner (imports nothing from the `tlamati` package; it treats it as
just another harness, same as opencode/codex/hermes). Compares terminal
harnesses with the SAME model (`qwen/qwen3-coder` via OpenRouter) on the 10
fixtures in `fixtures/`.

```bash
python3 bench/runner.py --probe                     # upstream health: 1 task × harness
python3 bench/runner.py --out evals/benchmark_DATE/  # full run (4×10)
python3 bench/runner.py --harnesses tlamati,codex --tasks promedio,offbyone
```

- Success is decided by each fixture's `verify.py` (exit 0 + VERIFY OK), NEVER by the harness.
- JSONL per harness with a frozen schema; unexposed fields = honest `null`.
- Single timeout: 600 s per task×harness; verify: 60 s.
- Results, token semantics, and public context: `EVALS.md` at the root.

Integrity (anti-cheating): single instruction, zero injected hints, timeouts
untouched per harness, the version run is the published one. If a harness does
not run on this machine, what DID run is reported — never invented numbers.
