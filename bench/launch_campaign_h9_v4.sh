#!/usr/bin/env bash
# Lanzador desacoplado de la campaña H9 v4 (cascada limpia, entorno hostil).
# Mismo patrón que launch_campaign_h9_v3.sh: setsid+nohup DENTRO del script.
# OJO pgrep anti-self-match (pitfall s26): el patrón "campaign_h9_v4[.]sh"
# NO matchea el cmdline propio de ESTE launcher (bash bench/launch_campaign_h9_v4.sh).
cd "$(dirname "$0")/.." || exit 1
bash -n bench/campaign_h9_v4.sh || { echo "SINTAXIS MALA"; exit 1; }
setsid nohup bash bench/campaign_h9_v4.sh >> evals/campaign_h9_v4.log 2>&1 < /dev/null &
sleep 2
pgrep -f "bench/campaign_h9_v4[.]sh" >/dev/null \
  && echo "H9v4 VIVA pid=$(pgrep -f 'bench/campaign_h9_v4[.]sh' | head -1)" \
  || echo "NO ARRANCÓ"
