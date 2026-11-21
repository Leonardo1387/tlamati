#!/usr/bin/env bash
# CAMPAÑA FRONTERA — escenario C (autorizado fundador 19-nov sesión 25, verbatim:
# "autorizo el C, pero opino que primero hagamos un script específico para lo que
# queremos descubrir con esos evals").
#
# Modelos: qwen3.8-max-0902 (frontera Qwen) + gpt-6.2-sol (frontera OpenAI gen-6)
# + claude-opus-5.5 (frontera Anthropic). Cota estimada $25.31 (techo ×1.5 = $38).
# Arneses: tlamati + codex (comparación moat; opencode/hermes ya cubren la
# generalización entre arneses en campaign_ext).
#
# SECUENCIADO tras campaign_ext.sh (fin natural, NUNCA dos runners simultáneos).
# IDEMPOTENTE: salta combos con JSONL de 45 líneas. Relanzar con
# bench/launch_campaign_fr.sh sin miedo.
set -u
cd "$(dirname "$0")/.." || exit 1

RUNS=3
EXPECTED=$((15 * RUNS))
MODELS=("qwen/qwen3.8-max-0902" "openai/gpt-6.2-sol" "anthropic/claude-opus-5.5")

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

# ── PASO 0: esperar fin natural de TODA campaña previa ──
while pgrep -f "campaign_e3c.sh|campaign_ext.sh" >/dev/null 2>&1; do
  sleep 60
done
log "campañas previas terminadas — arrancando campaña FRONTERA (escenario C)"

# ── PASO 1: UN combo a la vez ──
for model in "${MODELS[@]}"; do
  slug=$(echo "$model" | tr '/.' '__')
  out="evals/campaign_2026-11_${slug}"
  for h in tlamati codex; do
    if complete "$out/$h.jsonl"; then
      log "SALTO (ya completo): $h × $model"
      continue
    fi
    run_combo "$model" "$h" "$out" || log "AVISO: $h × $model incompleto — seguir"
  done
done

log "CAMPAÑA FRONTERA COMPLETA. Análisis:"
python3 bench/moat_analysis.py --md evals/MOAT_ANALYSIS.md || true
for f in evals/campaign_2026-11_*/*.jsonl; do
  [ -f "$f" ] && echo "  $f: $(wc -l < "$f")/$EXPECTED líneas"
done
