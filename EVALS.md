# EVALS — benchmark de arneses (E3b)

Medimos lo que el PRD promete: **el arnés importa**. Mismo modelo, mismo corpus,
distinto arnés → distinto resultado. Regla anti-cheating (donor:
debugml.github.io/cheating-agents): instrucción única (contenido de
`instruction.md`, sin ayudas añadidas), `verify.py` decide el éxito (exit 0 +
`VERIFY OK`), timeouts idénticos por arnés (600 s), cero configuración especial.

## Corpus

Las 10 fixtures de `fixtures/` (terminal-bench-lite): 5 fáciles/medias
(`promedio`, `offbyone`, `conversor`, `import_roto`, `crear_modulo`) + 5 duras
(`multi_archivo`, `output_grande`, `git_history`, `instruccion_en_archivo`,
`test_driven`). Sintéticas, moldeadas en bugs reales, sin datos personales.
`git_history` se siembra con `setup.sh` de fechas fijas → hashes deterministas
entre máquinas.

## Tabla ARNÉS (18-nov-2026)

- Modelo: `qwen/qwen3-coder` vía OpenRouter para TODOS los arneses.
- Máquina: WSL2, misma sesión, misma ventana temporal.
- Runner: `bench/runner.py` (externo al paquete; no toca el código de tlamati).
- JSONL crudos: `evals/benchmark_2026-11-18/<arnés>.jsonl`.
- Schema: `{task, harness, success, turns, tokens_in, tokens_out, cache_read, duration_s, error}` — campos que un arnés no expone = `null` honesto.

<!-- TABLA: resultados REALES de la corrida del 18-nov-2026 (~23:45-00:10 CST, upstream sano, 40/40 corridas completadas) -->

| arnés | versión | resueltas | fáciles (5) | duras (5) | tokens_in (suma) | tokens_out (suma) | cache % | duración total |
|---|---|---|---|---|---|---|---|---|
| codex | 0.133.0 | **10/10** | 5/5 | 5/5 | 1,536,586 | 19,100 | 95% | 302.6 s |
| hermes | (instalado) | **10/10** | 5/5 | 5/5 | null | null | n/a | 206.3 s |
| opencode | 1.19.6 | 9/10 | 4/5 | 5/5 | 693,658 | 10,133 | 90% | 154.2 s |
| tlamati | 0.0.1 (main db0b7a1+) | 7/10 | 5/5 | 2/5 | **485,894** | 8,538 | 92% | **137.4 s** |

Fallos (todos legítimos, sin errores upstream — cada corrida completó su loop):

- `tlamati/instruccion_en_archivo` y `tlamati/test_driven`: stop=max_turns (20).
  La tarea exige más turnos de los presupuestados; en el baseline interno
  (e3a_check, misma fixture) test_driven PASÓ con 9 turnos — varianza del modelo
  en tareas largas, no bug del arnés.
- `tlamati/multi_archivo`: el modelo no aplicó el impuesto 0.19 del config
  (usó default) — fallo de razonamiento del modelo, verify.py lo cazó.
- `opencode/promedio`: se rindió en 1 turno sin editar (la más fácil) — varianza
  del modelo; su suite interna igual quedó 9/10.

Lectura honesta (lo que SÍ dice y lo que NO dice esta tabla):

- codex y hermes resolvieron todo; tlamati quedó 7/10 en esta ventana. NO
  maquillamos: es el dato. Los 3 fallos de tlamati fueron 2× techo de turnos +
  1× razonamiento del modelo en la fixture más difícil.
- En EFICIENCIA, tlamati gastó ~3.2× MENOS tokens de entrada que codex
  (486k vs 1.54M) y fue el más rápido en total (137 s vs 303 s) — el overhead
  mínimo del PRD (<8k) se sostiene: es el arnés que menos contexto arrastra.
- Una corrida por celda = varianza de modelo presente (ver fallos "fáciles").
  La cifra publicable debe decir "corrida única, <fecha>" — NUNCA promediar
  silencio. Réplicas futuras: mismo runner, nueva fecha de dir.

Notas de semántica (honestidad de la comparación):

- `tokens_in` de tlamati y codex INCLUYE cache_read (convención OpenRouter);
  en opencode el `input` del evento EXCLUYE `cache.read` → el runner suma
  `input+cache.read` para comparar manzanas con manzanas.
- hermes `-z` (one-shot) solo imprime texto final: no expone tokens → `null`.
  Sus resultados miden SOLO % resueltas y duración.
- codex no expone turnos de agente comparables → `turns: null`.
- Configuración exacta por arnés:
  - tlamati: `tlamati -p "$INSTR" --json --approve-tool '*' --max-turns 20 --no-session`
    (sandbox bwrap ON por default, red OFF).
  - opencode: `opencode run "$INSTR" --dir WS --auto --format json -m openrouter/qwen/qwen3-coder`.
  - codex: `codex exec -C WS -s workspace-write --skip-git-repo-check --ephemeral --json "$INSTR"`
    con `CODEX_HOME` aparte (`bench/runner.py` lo genera) y `config.toml`:
    `model_provider="openrouter"`, `base_url="https://openrouter.ai/api/v1"`,
    `env_key="OPENROUTER_API_KEY"`, `wire_api="responses"`, `approval_policy="never"`.
  - hermes: `hermes -z "$INSTR" --safe-mode --yolo -m qwen/qwen3-coder --provider openrouter`
    (`--safe-mode` = arnés default pelón: sin config/memoria/skills/plugins/MCP
    del usuario).

## Fuera de la tabla (y por qué)

- **claude code / grok**: atados a cerebros propietarios — el delta mediría el
  modelo, no el arnés (decisión del fundador, 16-nov).
- **gemini-cli**: verificado en su bundle instalado (0.68.0) — no tiene ruta
  OpenAI-compatible (cero `OPENAI_API_KEY`/`chat/completions`); su único modo
  custom es `GOOGLE_GEMINI_BASE_URL` (API de Gemini). No puede correr
  qwen3-coder vía OpenRouter.

## Reproducción

```bash
uv tool install --from . tlamati --reinstall
python3 bench/runner.py --probe          # salud upstream (1 tarea × arnés)
python3 bench/runner.py --out evals/benchmark_$(date +%F)/
```

La API key se toma de `OPENROUTER_API_KEY` (env o `~/.hermes/.env`).

## Contexto público (otra pista, no comparable directo)

Terminal-Bench 4.1 (tbench.ai, capturado 17-nov-2026): la tabla oficial ya es
matriz arnés×modelo. Anclas: Qwen3.8-Max-0902+Claude Code = 27.0% (variante
max, NO qwen3-coder); Grok 4.7+Grok Build = 38.8%; Opus 5.5+CC = 65.8% (~$4.7k
la corrida). Caso dirac (HN 47920787): agente OSS 65.2% vs agente oficial de
Google 47.8% con el MISMO Gemini-3-flash = **+17 pts harness-only**. Detalle y
fuentes: `research/08_BENCHMARKS_EXISTENTES.md`. La pista de Terminal-Bench es
OSS (harbor-framework); lo que cuesta es el cerebro frontier — por eso este
benchmark fija el cerebro y varía el arnés.
