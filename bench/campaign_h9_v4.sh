#!/usr/bin/env bash
# CAMPAÑA H9 v4 — CASCADA ESCALONADA CON ENTORNO HOSTIL (lecciones de v3).
# v3 fue INVALIDADA: la memoria persistente de tlamati filtró las respuestas
# a opus (7 turnos con acordeón) y los docstring filtraban las specs. v4:
# fixture con docstring neutro + runner --no-memory + purge de workdir
# cross-harness + respuestas cifradas fuera de /tmp + canary trap.
# Ver sección "CAMPAÑA v3 INVALIDADA + FIXES v4" en skill tlamati-harness-project.
#
# Modelos frontera: gpt-6.2-sol + claude-opus-5.5 + qwen3.8-max-0902.
# Harnesses: tlamati + codex. --runs 1 (ejecuciones largas, 40-110 turnos esperados).
#
# IDEMPOTENTE: omite combos con JSONL completo (EXPECTED líneas).
# Relanzar con bench/launch_campaign_h9_v4.sh sin miedo.
# ANTES de lanzar: calibración v4 limpia (evals/h9_calib_v4/: 104 turnos,
# $0.1525, trayectoria auditada sin trampas) + OK del fundador — regla S17.
set -u
cd "$(dirname "$0")/.." || exit 1
# CRÍTICO H9: el binario `tlamati` instalado (~/.local/bin) es PRE-fix de caché.
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

# ── PASO 0a: PREFLIGHT v4 (FIX-F): entorno hostil verificado antes de gastar.
# Ojo: el chequeo de workdirs residuales falla si HAY un runner vivo; por eso
# el preflight corre ANTES del gate de runners y la purga es tarea del runner.
bash bench/preflight_h9.sh || {
  log "FATAL: preflight en rojo — NO se lanza la campaña (corregir y relanzar)"
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
  log "CORRIENDO: $model × $harness (v4 cascada limpia) → $out/"
  python3 bench/runner.py --harnesses "$harness" --runs "$RUNS" \
    --tasks "$TASKS" --model "$model" --out "$out/" 2>>"$out/run.log"
  local rc=$?
  log "TERMINADO: $model × $harness rc=$rc"
  return $rc
}

# ── PASO 0b: NUNCA dos runners simultáneos contra OpenRouter.
# Contención: Hermes mismo corre sobre qwen3.8-max vía OpenRouter.
# OJO (pitfall s26): el patrón NO debe incluir h9_v4 — este script se llama
# campaign_h9_v4.sh y se auto-matchearía → deadlock (pasó en el 1er intento
# de lanzamiento, 20-nov 17:12).
while pgrep -f "campaign_(e3c|ext|fr|h9|h9_runs3|h9_v3)[.]sh" >/dev/null 2>&1 \
   || pgrep -f "bench/runner[.]py" >/dev/null 2>&1; do
  sleep 60
done
log "sin runners vivos — arrancando campaña H9 v4 (cascada limpia)"

# ── PASO 1: UN combo a la vez ──
for model in "${MODELS[@]}"; do
  slug=$(echo "$model" | tr '/.' '__')
  out="evals/h9v4_2026-11_${slug}"
  for h in tlamati codex; do
    if complete "$out/$h.jsonl"; then
      log "SALTO (ya completo): $h × $model"
      continue
    fi
    run_combo "$model" "$h" "$out" || log "AVISO: $h × $model incompleto — seguir"
  done
done

log "CAMPAÑA H9 v4 COMPLETA. Resumen:"
for f in evals/h9v4_2026-11_*/*.jsonl; do
  [ -f "$f" ] && echo "  $f: $(wc -l < "$f")/$EXPECTED líneas"
done
