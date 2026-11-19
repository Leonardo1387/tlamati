#!/usr/bin/env bash
# E3c-EXT — extensión de campaña (decisión fundador 19-nov sesión 22, verbatim:
# "también haz pruebas con hermes con qwen flash y los modelos de deep seek...
# y también con open code... la mayor cantidad de referencia posible, por unos
# dolares, lo vale").
#
# Añade {hermes, opencode} × {flash, deepseek-v3.2, kimi} para completar la
# matriz 4 arneses × 3 modelos. NO toca la campaña original (campaign_e3c.sh
# sigue con tlamati+codex y cierra con hermes × qwen3-coder).
#
# SECUENCIADO: espera a que el orquestador original MUERA (fin natural) antes
# de lanzar nada — dos runners simultáneos contra OpenRouter = saturación
# garantizada (pitfall verificado sesión 20).
#
# IDEMPOTENTE: salta combos con JSONL completo (45 líneas). Reiniciable:
#   nohup setsid bash bench/campaign_ext.sh >> evals/campaign_ext.log 2>&1 &
set -u
cd "$(dirname "$0")/.." || exit 1

RUNS=3
EXPECTED=$((15 * RUNS))
MODELS=("qwen/qwen3.8-flash" "deepseek/deepseek-v3.2" "moonshotai/kimi-k2.7-code")

log() { echo "[$(date '+%F %T')] $*"; }

complete() { [ -f "$1" ] && [ "$(wc -l < "$1")" -ge "$EXPECTED" ]; }

run_combo() {  # run_combo <model> <harness> <out_dir>
  local model="$1" harness="$2" out="$3"
  mkdir -p "$out"
  python3 bench/runner.py --probe --model "$model" >/dev/null 2>&1
  if [ $? -ne 0 ]; then
    log "AVISO: sonda falló para $model — reintentando en 120s"
    sleep 120
    python3 bench/runner.py --probe --model "$model" >/dev/null 2>&1 || {
      log "SONDA SIGUE FALLANDO ($model) — combo pospuesto"
      return 1
    }
  fi
  log "CORRIENDO: $model × $harness → $out/"
  python3 bench/runner.py --harnesses "$harness" --runs "$RUNS" \
    --model "$model" --out "$out/" 2>>"$out/run.log"
  local rc=$?
  log "TERMINADO: $model × $harness rc=$rc"
  return $rc
}

# ── PASO 0: esperar fin natural de la campaña original ──
while pgrep -f "campaign_e3c.sh" >/dev/null 2>&1; do
  sleep 60
done
log "campaña original terminada — arrancando extensión hermes+opencode"

# ── PASO 1: UN arnés a la vez (nunca dos runners simultáneos) ──
for model in "${MODELS[@]}"; do
  slug=$(echo "$model" | tr '/.' '__')
  out="evals/campaign_2026-11_${slug}"
  for h in opencode hermes; do
    if complete "$out/$h.jsonl"; then
      log "SALTO (ya completo): $h × $model"
      continue
    fi
    run_combo "$model" "$h" "$out" || log "AVISO: $h × $model incompleto — seguir"
  done
done

log "CAMPAÑA EXT COMPLETA. Resultados:"
for f in evals/campaign_2026-11_*/*.jsonl; do
  [ -f "$f" ] && echo "  $f: $(wc -l < "$f")/$EXPECTED líneas"
done
