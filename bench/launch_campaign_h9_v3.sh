#!/usr/bin/env bash
# Lanzador desacoplado de la campaña H9 v3 (cascada ciega).
# Mismo patrón que launch_campaign_h9.sh: setsid+nohup DENTRO del script.
# OJO pgrep anti-self-match (pitfall s26): el patrón "campaign_h9_v3[.]sh"
# NO matchea el cmdline propio de ESTE launcher (bash bench/launch_campaign_h9_v3.sh).
cd "$(dirname "$0")/.." || exit 1
bash -n bench/campaign_h9_v3.sh || { echo "SINTAXIS MALA"; exit 1; }
setsid nohup bash bench/campaign_h9_v3.sh >> evals/campaign_h9_v3.log 2>&1 < /dev/null &
sleep 2
pgrep -f "bench/campaign_h9_v3[.]sh" >/dev/null \
  && echo "H9v3 VIVA pid=$(pgrep -f 'bench/campaign_h9_v3[.]sh' | head -1)" \
  || echo "NO ARRANCÓ"
