#!/usr/bin/env bash
# CAMPAÑA H9 v4 RÉPLICAS — confirmación estadística (media + desviación).
# Decisión del fundador 20-nov (opción 3): gpt+opus ×3, qwen ×2 → ~$6.4.
# qwen ×2 porque su brazo tlamati n=1 costó $0.70 (74 turnos; modelo caro
# en OpenRouter) — ×3 empujaría el total sobre el techo de $6.
# MISMO protocolo hostil que campaign_h9_v4.sh: --reveal simétrico en ambos
# brazos (33 reveals), --no-memory, purge de workdir entre runs, canary.
# Output en evals/h9v4r3_* para NO pisar la data n=1 (h9v4_*).
#
# PITFALL s26/s27: el gate de abajo usa "campaign_h9_v4[.]sh" — este script
# se llama campaign_h9_v4_runs3.sh y NO matchea ese regex (después de h9_v4
# viene "_runs3", no ".sh"), así que no hay auto-deadlock. Pero NO agregar
# "h9_v4_runs3" al patrón: se auto-matchearía.
set -u
cd "$(dirname "$0")/.." || exit 1
export PATH="$PWD/.venv/bin:$PATH"

TASKS="ducto_cascada_l3"
MODELS=("openai/gpt-6.2-sol" "anthropic/claude-opus-5.5" "qwen/qwen3.8-max-0902")
runs_for() { case "$1" in qwen/*) echo 2 ;; *) echo 3 ;; esac; }

log() { echo "[$(date '+%F %T')] $*"; }

command -v tlamati | grep -q "$PWD/.venv" || {
  log "FATAL: tlamati en PATH no es el del .venv editable (fix cache ausente)"
  exit 1
}

# ── PASO 0a: PREFLIGHT (debe correr SIN runner vivo: revisa workdirs)
bash bench/preflight_h9.sh || {
  log "FATAL: preflight en rojo — NO se lanza (corregir y relanzar)"
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
  log "CORRIENDO ×$RUNS: $model × $harness (v4 réplicas) → $out/"
  python3 bench/runner.py --harnesses "$harness" --runs "$RUNS" \
    --tasks "$TASKS" --model "$model" --out "$out/" 2>>"$out/run.log"
  local rc=$?
  log "TERMINADO: $model × $harness ×$RUNS rc=$rc"
  return $rc
}

# ── PASO 0b: NUNCA dos runners simultáneos contra OpenRouter.
while pgrep -f "campaign_(e3c|ext|fr|h9|h9_runs3|h9_v3|h9_v4)[.]sh" >/dev/null 2>&1 \
   || pgrep -f "bench/runner[.]py" >/dev/null 2>&1; do
  sleep 60
done
log "sin runners vivos — arrancando campaña H9 v4 ×3 réplicas"

# ── PASO 1: UN combo a la vez (RUNS internos por combo según modelo) ──
for model in "${MODELS[@]}"; do
  slug=$(echo "$model" | tr '/.' '__')
  out="evals/h9v4r3_2026-11_${slug}"
  RUNS=$(runs_for "$model")
  EXPECTED=$RUNS
  for h in tlamati codex; do
    if complete "$out/$h.jsonl"; then
      log "SALTO (ya completo): $h × $model ×$RUNS"
      continue
    fi
    run_combo "$model" "$h" "$out" || log "AVISO: $h × $model incompleto — seguir"
  done
done

log "CAMPAÑA H9 v4 RÉPLICAS COMPLETA. Resumen:"
for f in evals/h9v4r3_2026-11_*/*.jsonl; do
  [ -f "$f" ] && echo "  $f: $(wc -l < "$f") líneas"
done
