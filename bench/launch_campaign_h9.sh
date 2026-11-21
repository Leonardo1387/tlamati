#!/usr/bin/env bash
# Lanzador desacoplado de la campaña H9 (horizonte largo).
# Mismo patrón que launch_campaign_fr.sh: setsid+nohup DENTRO del script.
# OJO pgrep anti-self-match (pitfall s26): el patrón "bench/campaign_h9[.]sh"
# NO matchea el cmdline propio de ESTE launcher (bash bench/launch_campaign_h9.sh).
cd "$(dirname "$0")/.." || exit 1
bash -n bench/campaign_h9.sh || { echo "SINTAXIS MALA"; exit 1; }
setsid nohup bash bench/campaign_h9.sh >> evals/campaign_h9.log 2>&1 < /dev/null &
sleep 2
pgrep -f "bench/campaign_h9[.]sh" >/dev/null \
  && echo "H9 VIVA pid=$(pgrep -f 'bench/campaign_h9[.]sh' | head -1)" \
  || echo "NO ARRANCÓ"
