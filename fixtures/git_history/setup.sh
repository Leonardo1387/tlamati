#!/usr/bin/env bash
# Construye el repo semilla con 6 commits DETERMINISTAS (fechas fijas).
# El runner lo ejecuta tras copiar la fixture al workspace.
set -euo pipefail
cd "$(dirname "$0")"
[ -d .git ] && exit 0  # idempotente

export GIT_AUTHOR_NAME="Semilla" GIT_AUTHOR_EMAIL="semilla@ejemplo.test"
export GIT_COMMITTER_NAME="Semilla" GIT_COMMITTER_EMAIL="semilla@ejemplo.test"
D1="2026-10-01T09:00:00+00:00"; D2="2026-10-02T09:00:00+00:00"
D3="2026-10-03T09:00:00+00:00"; D4="2026-10-04T09:00:00+00:00"
D5="2026-10-05T09:00:00+00:00"; D6="2026-10-06T09:00:00+00:00"

git init -q -b main

printf '# Proyecto semilla\n\nEjercicio de arqueologia git.\n' > README.md
GIT_AUTHOR_DATE="$D1" GIT_COMMITTER_DATE="$D1" git add README.md
GIT_AUTHOR_DATE="$D1" GIT_COMMITTER_DATE="$D1" git commit -q -m "commit inicial: README"

cat > rutas.py <<'EOF'
"""Utilidades de rutas."""


def formatear_ruta(partes):
    """Une partes de ruta con barras '/' (formato URL)."""
    return "/".join(p.strip("/") for p in partes if p)
EOF
GIT_AUTHOR_DATE="$D2" GIT_COMMITTER_DATE="$D2" git add rutas.py
GIT_AUTHOR_DATE="$D2" GIT_COMMITTER_DATE="$D2" git commit -q -m "feat: formatear_ruta con barras POSIX"

cat > app.py <<'EOF'
from rutas import formatear_ruta


def url_documento(carpeta, nombre):
    return "https://cdn.ejemplo.test/" + formatear_ruta([carpeta, nombre])
EOF
GIT_AUTHOR_DATE="$D3" GIT_COMMITTER_DATE="$D3" git add app.py
GIT_AUTHOR_DATE="$D3" GIT_COMMITTER_DATE="$D3" git commit -q -m "feat: url_documento usa formatear_ruta"

printf 'notas internas v1\n' > notas.txt
GIT_AUTHOR_DATE="$D4" GIT_COMMITTER_DATE="$D4" git add notas.txt
GIT_AUTHOR_DATE="$D4" GIT_COMMITTER_DATE="$D4" git commit -q -m "docs: notas internas"

printf 'notas internas v1\npendiente: revisar rutas\n' > notas.txt
GIT_AUTHOR_DATE="$D5" GIT_COMMITTER_DATE="$D5" git add notas.txt
GIT_AUTHOR_DATE="$D5" GIT_COMMITTER_DATE="$D5" git commit -q -m "docs: amplia notas"

cat > rutas.py <<'EOF'
"""Utilidades de rutas."""


def formatear_ruta(partes):
    """Une partes de ruta con barras '/' (formato URL)."""
    # refactor "soporte Windows": separador con backslash
    return "\\".join(p.strip("/") for p in partes if p)
EOF
GIT_AUTHOR_DATE="$D6" GIT_COMMITTER_DATE="$D6" git add rutas.py
GIT_AUTHOR_DATE="$D6" GIT_COMMITTER_DATE="$D6" git commit -q -m "refactor: formatear_ruta con separador Windows"
