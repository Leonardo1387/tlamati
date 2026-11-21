#!/usr/bin/env bash
# FASE 1 del moat — ablaciones H8 causal. SECUENCIADO detrás de las campañas
# vivas (regla dura: NUNCA dos runners contra OpenRouter a la vez). Idempotente:
# ablations.jsonl es append y el script para en honesto si upstream enferma.
# Relanzar con:  bash bench/launch_ablations.sh
set -u
cd "$(dirname "$0")/.." || exit 1

OUT="evals/ablations_$(date '+%Y-%m-%d')"
LOG="evals/ablations.log"
MODEL="qwen/qwen3-coder"

log() { echo "[$(date '+%F %T')] $*"; }

# ── PASO 0: esperar fin natural de TODAS las campañas (ext + frontera) ──
while pgrep -f "campaign_e3c.sh|campaign_ext.sh|campaign_fr.sh" >/dev/null 2>&1; do
  sleep 60
done
log "campañas terminadas — arrancando ablaciones"

# ── PASO 1: sonda upstream (1 corrida barata A0×promedio) ──
if ! python3 bench/ablations.py --probe --model "$MODEL" >>"$LOG" 2>&1; then
  log "SONDA FALLÓ (upstream enfermo) — reintentando en 180s"
  sleep 180
  python3 bench/ablations.py --probe --model "$MODEL" >>"$LOG" 2>&1 || {
    log "SONDA SIGUE FALLANDO — ablaciones pospuestas; relanzar launcher"
    exit 1
  }
fi
log "sonda OK — lanzando matriz 3 configs × 5 tareas"

# ── PASO 2: matriz completa ──
python3 bench/ablations.py --model "$MODEL" >>"$LOG" 2>&1
rc=$?
log "ablaciones terminadas rc=$rc → $OUT/ablations.jsonl"
exit $rc
