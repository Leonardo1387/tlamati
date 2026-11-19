#!/usr/bin/env bash
# Lanzador desacoplado de la extensión de campaña (hermes+opencode × 3 modelos).
# Mismo patrón que launch_campaign.sh: setsid+nohup DENTRO del script para que
# sobreviva a la muerte de la sesión Hermes.
cd "$(dirname "$0")/.." || exit 1
bash -n bench/campaign_ext.sh || { echo "SINTAXIS MALA"; exit 1; }
setsid nohup bash bench/campaign_ext.sh >> evals/campaign_ext.log 2>&1 < /dev/null &
sleep 2
pgrep -f campaign_ext.sh >/dev/null && echo "EXT VIVA pid=$(pgrep -f campaign_ext.sh | head -1)" || echo "NO ARRANCÓ"
