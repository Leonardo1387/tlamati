#!/usr/bin/env bash
# CAMPAÑA H9 — CURVA DE SATURACIÓN (horizonte largo, 100+ turnos).
# Tesis: el ratio codex/tlamati CRECE con la longitud real de la tarea.
# Fixtures L1 (refactor 15 módulos) + L2 (migración 30 módulos con
# descubrimiento en docs/API-NUEVA.md), límites por fixture vía
# bench_limits.json (120 turnos, timeout 1800s — MISMO techo ambos arneses).
#
# Modelos frontera: gpt-6.2-sol + claude-opus-5.5 (tlamati CON fix de cache
# 20-nov) + qwen3.8-max-0902. Arneses: tlamati + codex. --runs 1 (corrida
# larga; la varianza ya está medida en la batería corta con B=10k).
#
# IDEMPOTENTE: salta combos con JSONL completo (EXPECTED líneas).
# Relanzar con bench/launch_campaign_h9.sh sin miedo.
# ANTES de lanzar: el fundador debe haber visto la calibración qwen3-coder
# (costo/duración reales) y dado OK — regla de reporte de gasto.
set -u
cd "$(dirname "$0")/.." || exit 1
# CRÍTICO H9: el binario `tlamati` instalado (~/.local/bin) es PRE-fix de cache.
# La campaña DEBE usar el tlamati del .venv editable (src/ con el fix
# cache_control anthropic del 20-nov) — si no, opus vuelve a medir cache=0.
export PATH="$PWD/.venv/bin:$PATH"

RUNS=1
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
  log "CORRIENDO: $model × $harness (L1+L2) → $out/"
  python3 bench/runner.py --harnesses "$harness" --runs "$RUNS" \
    --tasks "$TASKS" --model "$model" --out "$out/" 2>>"$out/run.log"
  local rc=$?
  log "TERMINADO: $model × $harness rc=$rc"
  return $rc
}

# ── PASO 0: NUNCA dos runners simultáneos contra OpenRouter.
# Patrones con bracket anti-self-match (pitfall deadlock s26): el cmdline
# propio contiene "campaign_h9" — ningún patrón de abajo lo matchea.
while pgrep -f "campaign_(e3c|ext|fr)[.]sh" >/dev/null 2>&1 \
   || pgrep -f "bench/runner[.]py" >/dev/null 2>&1; do
  sleep 60
done
log "sin runners vivos — arrancando campaña H9 (horizonte largo)"

# ── PASO 1: UN combo a la vez ──
for model in "${MODELS[@]}"; do
  slug=$(echo "$model" | tr '/.' '__')
  out="evals/h9_2026-11_${slug}"
  for h in tlamati codex; do
    if complete "$out/$h.jsonl"; then
      log "SALTO (ya completo): $h × $model"
      continue
    fi
    run_combo "$model" "$h" "$out" || log "AVISO: $h × $model incompleto — seguir"
  done
done

log "CAMPAÑA H9 COMPLETA. Resumen:"
for f in evals/h9_2026-11_*/*.jsonl; do
  [ -f "$f" ] && echo "  $f: $(wc -l < "$f")/$EXPECTED líneas"
done
