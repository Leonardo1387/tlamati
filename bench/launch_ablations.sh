#!/usr/bin/env bash
# Lanza bench/ablations.sh desacoplado de la sesión (setsid DENTRO del script —
# terminal() foreground bloquea nohup/setsid inline, pitfall confirmado 2×).
# Idempotente: si ya hay un ablations.sh corriendo, no duplica.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p evals
if pgrep -f "bench/ablations[.]sh" >/dev/null 2>&1; then
  echo "ablations.sh ya está corriendo — sin duplicar"
  exit 0
fi
setsid bash bench/ablations.sh >> evals/ablations_watchdog.log 2>&1 < /dev/null &
sleep 1
pgrep -af "bench/ablations[.]sh" && echo "lanzado OK — bitácora: evals/ablations.log"
