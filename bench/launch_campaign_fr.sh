#!/usr/bin/env bash
# Lanzador desacoplado de la campaña frontera (escenario C).
# Mismo patrón que launch_campaign_ext.sh: setsid+nohup DENTRO del script.
cd "$(dirname "$0")/.." || exit 1
bash -n bench/campaign_fr.sh || { echo "SINTAXIS MALA"; exit 1; }
setsid nohup bash bench/campaign_fr.sh >> evals/campaign_fr.log 2>&1 < /dev/null &
sleep 2
pgrep -f campaign_fr.sh >/dev/null && echo "FR VIVA pid=$(pgrep -f campaign_fr.sh | head -1)" || echo "NO ARRANCÓ"
