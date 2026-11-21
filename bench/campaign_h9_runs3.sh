#!/usr/bin/env bash
# CAMPAÑA H9 ×3 RUNS — evidencia estadística completa.
# Mismos combos que campaign_h9.sh pero --runs 3 y salida a evals/h9x3_*
# (el runner SOBRESCRIBE el JSONL → NUNCA apuntar al dir runs=1).
# Idempotente: salta combos con JSONL completo (EXPECTED=2*3=6 líneas).
set -u
cd "$(dirname "$0")/.." || exit 1
export PATH="$PWD/.venv/bin:$PATH"

RUNS=3
TASKS="cadena_defectos_l1,ducto_reglas_l2"
EXPECTED=$((2 * RUNS))
MODELS=("openai/gpt-6.2-sol" "anthropic/claude-opus-5.5" "qwen/qwen3.8-max-0902")

log() { echo "[$(date '+%F %T')] $*"; }

command -v tlamati | grep -q "$PWD/.venv" || {
  log "FATAL: tlamati en PATH no es el del .venv editable (fix cache ausente)"
  exit 1
}

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
  log "CORRIENDO: $model × $harness ×3 (L1+L2) → $out/"
  python3 bench/runner.py --harnesses "$harness" --runs "$RUNS" \
    --tasks "$TASKS" --model "$model" --out "$out/" 2>>"$out/run.log"
  local rc=$?
  log "TERMINADO: $model × $harness rc=$rc"
  return $rc
}

# ── PASO 0: nunca dos runners simultáneos contra OpenRouter (anti-self-match) ──
while pgrep -f "campaign_(e3c|ext|fr|h9)[.]sh" >/dev/null 2>&1 \
   || pgrep -f "bench/runner[.]py" >/dev/null 2>&1; do
  sleep 60
done
log "sin runners vivos — arrancando campaña H9 ×3"

for model in "${MODELS[@]}"; do
  slug=$(echo "$model" | tr '/.' '__')
  out="evals/h9x3_2026-11_${slug}"
  for h in tlamati codex; do
    if complete "$out/$h.jsonl"; then
      log "SALTO (ya completo): $h × $model"
      continue
    fi
    run_combo "$model" "$h" "$out" || log "AVISO: $h × $model incompleto — seguir"
  done
done

log "CAMPAÑA H9 ×3 COMPLETA. Resumen:"
for f in evals/h9x3_2026-11_*/*.jsonl; do
  [ -f "$f" ] && echo "  $f: $(wc -l < "$f")/$EXPECTED líneas"
done
