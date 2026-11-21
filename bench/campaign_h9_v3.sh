#!/usr/bin/env bash
# CAMPAÑA H9 v3 — CASCADA CIEGA (horizonte estirado de verdad, 40+ turnos).
# Tesis v3: con fallos runtime secuenciales (cascada) + semántica única por
# módulo, los frontera NO pueden resolver en 4-10 turnos → el ratio
# codex/tlamati se mide en horizonte largo real.
# Fixture: ducto_cascada_l3 (34 módulos, guardavas runtime, 150 turnos/3600s).
#
# Modelos frontera: gpt-6.2-sol + claude-opus-5.5 + qwen3.8-max-0902.
# Arneses: tlamati + codex. --runs 1 (corrida larga).
#
# IDEMPOTENTE: salta combos con JSONL completo (EXPECTED líneas).
# Relanzar con bench/launch_campaign_h9_v3.sh sin miedo.
# ANTES de lanzar: el fundador vio la calibración qwen3-coder sobre v3
# (evals/h9_calib_v3/) y dio OK — regla de reporte de gasto (S17).
set -u
cd "$(dirname "$0")/.." || exit 1
# CRÍTICO H9: el binario `tlamati` instalado (~/.local/bin) es PRE-fix de cache.
export PATH="$PWD/.venv/bin:$PATH"

RUNS=1
TASKS="ducto_cascada_l3"
EXPECTED=$((1 * RUNS))
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
  log "CORRIENDO: $model × $harness (v3 cascada) → $out/"
  python3 bench/runner.py --harnesses "$harness" --runs "$RUNS" \
    --tasks "$TASKS" --model "$model" --out "$out/" 2>>"$out/run.log"
  local rc=$?
  log "TERMINADO: $model × $harness rc=$rc"
  return $rc
}

# ── PASO 0: NUNCA dos runners simultáneos contra OpenRouter.
# Contención: Hermes mismo corre sobre qwen3.8-max vía OpenRouter.
while pgrep -f "campaign_(e3c|ext|fr|h9|h9_runs3)[.]sh" >/dev/null 2>&1 \
   || pgrep -f "bench/runner[.]py" >/dev/null 2>&1; do
  sleep 60
done
log "sin runners vivos — arrancando campaña H9 v3 (cascada ciega)"

# ── PASO 1: UN combo a la vez ──
for model in "${MODELS[@]}"; do
  slug=$(echo "$model" | tr '/.' '__')
  out="evals/h9v3_2026-11_${slug}"
  for h in tlamati codex; do
    if complete "$out/$h.jsonl"; then
      log "SALTO (ya completo): $h × $model"
      continue
    fi
    run_combo "$model" "$h" "$out" || log "AVISO: $h × $model incompleto — seguir"
  done
done

log "CAMPAÑA H9 v3 COMPLETA. Resumen:"
for f in evals/h9v3_2026-11_*/*.jsonl; do
  [ -f "$f" ] && echo "  $f: $(wc -l < "$f")/$EXPECTED líneas"
done
