#!/usr/bin/env bash
# Vigilante de saturación OpenRouter durante la campaña (sesión 24, modo yolo).
# Cada 5 min revisa los JSONL/log de campaña activos por errores upstream
# (429/504/rate-limit) y por orquestadores muertos. Alertas → stdout (log).
# Muere solo cuando ya no hay orquestadores vivos.
cd ~/code/tlamati || exit 1
LOG=evals/saturation_watch.log
echo "[$(date '+%F %T')] vigilante iniciado" >> "$LOG"
while pgrep -f "campaign_e3c.sh|campaign_ext.sh|bench/runner.py" > /dev/null; do
  # errores upstream recientes en los JSONL de campaña (últimas 40 líneas c/u)
  ALERTS=$(for f in evals/campaign_2026-11_*/*.jsonl; do
    [ -f "$f" ] || continue
    tail -n 40 "$f" | grep -oE '"error": "[^"]*(429|504|rate.?limit|upstream)[^"]*"' | head -n 3
  done)
  if [ -n "$ALERTS" ]; then
    echo "[$(date '+%F %T')] ALERTA SATURACION: $ALERTS" >> "$LOG"
  fi
  # runner muerto pero orquestador vivo = posible atasco
  if ! pgrep -f "bench/runner.py" > /dev/null && pgrep -f "campaign_e3c.sh|campaign_ext.sh" > /dev/null; then
    echo "[$(date '+%F %T')] aviso: orquestador vivo sin runner (entre fases o atasco — revisar campaign_run.log)" >> "$LOG"
  fi
  sleep 300
done
echo "[$(date '+%F %T')] campaña terminada — vigilante cierra" >> "$LOG"
