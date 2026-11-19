# bench/ — benchmark externo de arneses (E3b)

Runner EXTERNO (no importa nada del paquete `tlamati`; lo trata como un arnés
más, igual que a opencode/codex/hermes). Compara arneses de terminal con el
MISMO modelo (`qwen/qwen3-coder` vía OpenRouter) sobre las 10 fixtures de
`fixtures/`.

```bash
python3 bench/runner.py --probe                     # salud upstream: 1 tarea × arnés
python3 bench/runner.py --out evals/benchmark_DATE/  # corrida completa (4×10)
python3 bench/runner.py --harnesses tlamati,codex --tasks promedio,offbyone
```

- Éxito lo decide `verify.py` de cada fixture (exit 0 + VERIFY OK), NUNCA el arnés.
- JSONL por arnés con schema congelado; campos no expuestos = `null` honesto.
- Timeout único: 600 s por tarea×arnés; verify: 60 s.
- Resultados, semántica de tokens y contexto público: `EVALS.md` en la raíz.

Integridad (anti-cheating): instrucción única, cero ayudas inyectadas, timeouts
sin tocar por arnés, la versión corrida es la publicada. Si un arnés no corre en
esta máquina, se reporta lo que SÍ corrió — nunca números inventados.
