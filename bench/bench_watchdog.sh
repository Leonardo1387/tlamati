#!/usr/bin/env bash
# bench_watchdog.sh — corre la réplica E3b cuando OpenRouter respira.
# Patrón de la sesión 16 (eval_watchdog): sonda barata cada 3 min, 2 OK
# seguidos antes de la suite; si la suite falla, distinguir upstream vs real.
set -u
cd ~/code/tlamati
OUT=evals/benchmark_2026-11-18_run2
streak=0
for i in $(seq 1 96); do
  if python3 bench/runner.py --probe --harnesses tlamati >/dev/null 2>&1; then
    streak=$((streak+1))
    echo "[probe $i] OK (racha $streak/2) $(date '+%H:%M:%S')" >&2
    [ $streak -ge 2 ] && break
  else
    streak=0
    echo "[probe $i] saturado $(date '+%H:%M:%S')" >&2
  fi
  sleep 180
done
if [ $streak -lt 2 ]; then
  echo "SUITE_NO_CORRIO: upstream nunca estabilizó"
  exit 1
fi
for intento in 1 2 3; do
  echo "[suite intento $intento] $(date '+%H:%M:%S')" >&2
  python3 bench/runner.py --out "$OUT/"
  rc=$?
  # ¿hubo errores upstream en algún JSONL de la corrida?
  if grep -l -i "rate-limit\|429\|504\|502\|temporarily" "$OUT"/*.jsonl >/dev/null 2>&1; then
    echo "[suite intento $intento] contaminada por upstream, espero 240s" >&2
    sleep 240
    continue
  fi
  echo "SUITE_TERMINADA rc=$rc intento=$intento limpia-de-upstream"
  exit $rc
done
echo "SUITE_TERMINADA rc=1 tras 3 intentos con contaminación upstream"
exit 1
