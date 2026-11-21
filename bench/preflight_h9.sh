#!/usr/bin/env bash
# FIX-F (H9-v4): preflight OBLIGATORIO antes de lanzar cualquier campaña de bench.
# Nació de la campaña v3 INVALIDADA: memoria persistente con respuestas (opus las
# recibió en el prompt), docstrings que filtraban specs, y respuestas de referencia
# legibles en /tmp (el jail bwrap es --ro-bind / / → TODO el filesystem es legible).
# Uso: bash bench/preflight_h9.sh  (rc=0 → se puede lanzar; rc=1 → NO lanzar)
set -u
FAIL=0
ok()   { echo "  OK   $1"; }
malo() { echo "  MALO $1"; FAIL=1; }

echo "== PREFLIGHT campaña H9 =="

# 1. Memoria tlamati sin notas de fixtures (acordeones)
if grep -qi "tlamati-bench\|ducto_cascada\|VERIFY OK" ~/.local/share/tlamati/memory/MEMORY.md 2>/dev/null; then
  malo "MEMORY.md de tlamati tiene notas de fixtures — purgar antes de lanzar"
else
  ok "memoria tlamati limpia"
fi

# 2. Respuestas de referencia NO legibles en /tmp (deben estar cifradas en el repo)
LEAK=$(find /tmp -maxdepth 2 \( -name "h9_ref*" -o -name "h9_expected*" -o -name "gen_h9*" -o -name "*build_fixture*" \) -not -path "*/tlamati-bench/*" 2>/dev/null | head -5)
if [ -n "$LEAK" ]; then
  malo "respuestas/generadores legibles en /tmp: $LEAK"
else
  ok "sin respuestas en claro bajo /tmp"
fi

# 3. Workdirs de campañas previas purgados (ataque A6: leer solución del otro arnés)
STALE=$(find /tmp/tlamati-bench -maxdepth 2 -name "ducto_cascada_l3" -type d 2>/dev/null | head -5)
if [ -n "$STALE" ]; then
  malo "workdirs viejos presentes (el runner los purga al correr, pero lanzar con ellos = riesgo): $STALE"
else
  ok "sin workdirs residuales"
fi

# 4. Canary trap intacto (FIX-E)
if [ -f /tmp/h9_canary/cascada/m07.py ] && grep -q '"vacio"' /tmp/h9_canary/cascada/m07.py; then
  ok "canary presente (/tmp/h9_canary — valor trampa 'vacio' sin acento)"
else
  malo "canary ausente o alterado — regenerar /tmp/h9_canary"
fi

# 5. Fixture: semilla DEBE fallar (rc=1) y sello intacto
cd ~/code/tlamati/fixtures/ducto_cascada_l3 2>/dev/null || { malo "fixture no encontrada"; exit 1; }
python3 verify.py >/dev/null 2>&1
RC=$?
if [ "$RC" = "1" ]; then ok "semilla falla (rc=1)"; else malo "semilla rc=$RC (esperado 1) — fixture corrupta o resuelta"; fi

# 6. binario tlamati del .venv (NO el pre-fix de ~/.local/bin)
TLAMATI_BIN=$(command -v tlamati 2>/dev/null || echo "AUSENTE")
case "$TLAMATI_BIN" in
  */code/tlamati/.venv/bin/tlamati) ok "tlamati del venv editable: $TLAMATI_BIN" ;;
  *) malo "tlamati en PATH es $TLAMATI_BIN — exportar PATH=\$PWD/.venv/bin:\$PATH" ;;
esac

echo "== preflight: $([ $FAIL = 0 ] && echo 'PUEDE LANZARSE' || echo 'NO LANZAR — corregir lo MALO') =="
exit $FAIL
