#!/usr/bin/env bash
# Lanzador desacoplado: arranca campaign_e3c.sh con setsid+nohup para que
# SOBREVIVA a la muerte de la sesión Hermes (el bench dura horas).
cd "$(dirname "$0")/.." || exit 1
bash -n bench/campaign_e3c.sh || { echo "SINTAXIS MALA"; exit 1; }
setsid nohup bash bench/campaign_e3c.sh >> evals/campaign_run.log 2>&1 < /dev/null &
sleep 2
pgrep -f campaign_e3c.sh >/dev/null && echo "ORQUESTADOR VIVO pid=$(pgrep -f campaign_e3c.sh | head -1)" || echo "NO ARRANCÓ"
