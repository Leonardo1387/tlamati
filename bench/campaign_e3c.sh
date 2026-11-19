#!/usr/bin/env bash
# E3c — orquestador de campaña de modelos (decisión fundador 19-nov sesión 21):
#   1. El bench en curso (tlamati/opencode/codex/hermes × qwen3-coder) se CORTA
#      justo cuando va a empezar hermes (orden del runner: hermes es el último).
#      Los JSONL por arnés se escriben al terminar cada arnés → no se pierde nada.
#   2. Campaña: tlamati + codex × {qwen3.8-flash, deepseek-v3.2, kimi-k2.7-code}.
#   3. Cierre: hermes × qwen3-coder (solo ese modelo, decisión del fundador).
# IDEMPOTENTE: cada combo se salta si su JSONL ya existe con N líneas esperadas.
# Reiniciable tras muerte de sesión: relanzar con nohup (ver cabecera de uso).
# Uso:  nohup bash bench/campaign_e3c.sh >> evals/campaign_run.log 2>&1 &
set -u
cd "$(dirname "$0")/.." || exit 1

BENCH_DIR="evals/benchmark_2026-11-19_e3c"
RUNS=3
EXPECTED=$((15 * RUNS))  # 15 fixtures × 3 réplicas = 45 líneas por JSONL
MODELS=("qwen/qwen3.8-flash" "deepseek/deepseek-v3.2" "moonshotai/kimi-k2.7-code")
# La API key la resuelve bench/runner.py solo (env o ~/.hermes/.env) — no hace
# falta exportarla aquí.

log() { echo "[$(date '+%F %T')] $*"; }

complete() {  # complete <jsonl> → 0 si tiene las 45 líneas
  [ -f "$1" ] && [ "$(wc -l < "$1")" -ge "$EXPECTED" ]
}

run_combo() {  # run_combo <model> <harnesses> <out_dir>
  local model="$1" harnesses="$2" out="$3"
  mkdir -p "$out"
  # Sonda de salud upstream antes de gastar (patrón eval_watchdog)
  python3 bench/runner.py --probe --model "$model" >/dev/null 2>&1
  if [ $? -ne 0 ]; then
    log "AVISO: sonda falló para $model — reintentando en 120s (1 intento)"
    sleep 120
    python3 bench/runner.py --probe --model "$model" >/dev/null 2>&1 || {
      log "SONDA SIGUE FALLANDO ($model) — combo pospuesto, seguir con el resto"
      return 1
    }
  fi
  log "CORRIENDO: $model × $harnesses → $out/"
  python3 bench/runner.py --harnesses "$harnesses" --runs "$RUNS" \
    --model "$model" --out "$out/" 2>>"$out/run.log"
  local rc=$?
  log "TERMINADO: $model × $harnesses rc=$rc"
  return $rc
}

# ── PASO 1: esperar a que el bench actual llegue a hermes y cortarlo ──
if ! complete "$BENCH_DIR/codex.jsonl"; then
  log "Esperando a que el bench actual termine codex (corte antes de hermes)…"
  while true; do
    if complete "$BENCH_DIR/codex.jsonl"; then
      log "codex.jsonl completo — cortando el runner antes de hermes"
      pkill -f "bench/runner.py --runs" 2>/dev/null
      # matar también cualquier hijo huérfano del runner (codex/hermes en vuelo)
      pkill -f "hermes -z" 2>/dev/null
      sleep 5
      break
    fi
    if ! pgrep -f "bench/runner.py --runs" >/dev/null 2>&1; then
      if complete "$BENCH_DIR/codex.jsonl"; then break; fi
      log "ERROR: el runner murió antes de terminar codex — revisar $BENCH_DIR/run.log"
      exit 1
    fi
    sleep 30
  done
else
  log "codex.jsonl ya completo — nada que esperar"
  pkill -f "bench/runner.py --runs" 2>/dev/null  # por si acaso sigue vivo
fi

# ── PASO 2: campaña tlamati + codex × 3 modelos ──
for model in "${MODELS[@]}"; do
  slug=$(echo "$model" | tr '/.' '__')
  out="evals/campaign_2026-11_${slug}"
  ok=1
  for h in tlamati codex; do
    if complete "$out/$h.jsonl"; then
      log "SALTO (ya completo): $h × $model"
      continue
    fi
    ok=0
  done
  [ "$ok" -eq 1 ] && continue
  run_combo "$model" "tlamati,codex" "$out" || log "AVISO: $model incompleto — seguir"
done

# ── PASO 3: hermes × qwen-coder al FINAL (decisión fundador) ──
if complete "$BENCH_DIR/hermes.jsonl"; then
  log "SALTO: hermes × qwen3-coder ya completo"
else
  run_combo "qwen/qwen3-coder" "hermes" "$BENCH_DIR" || log "AVISO: hermes incompleto"
fi

log "CAMPAÑA E3c COMPLETA. Resultados:"
for f in "$BENCH_DIR"/*.jsonl evals/campaign_2026-11_*/*.jsonl; do
  [ -f "$f" ] && echo "  $f: $(wc -l < "$f")/$EXPECTED líneas"
done
