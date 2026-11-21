#!/usr/bin/env python3
"""Auditoria pre-publicacion: escanea ARBOL (tracked) e HISTORIA git completa
buscando cualquier cosa que comprometa privacidad, integridad del trabajo o
credenciales. Salida: hallazgos por severidad con archivo:linea (arbol) o
path (historia).

Los patrones genericos (secretos, formas de ruta, IDs) viven aqui.
Los patrones ESPECIFICOS del dueno del repo (usuario real, nombres de
negocio, correo personal) viven en scripts/audit_patterns_local.txt,
que esta en .gitignore y NUNCA se commitea — asi el propio script de
auditoria no filtra la informacion que protege.

Uso: python3 scripts/audit_publicacion.py [--historia]
"""

import os
import re
import subprocess
import sys
from collections import defaultdict

# --- Patrones genericos: (nombre, severidad, regex) --------------------------
PATTERNS_BASE = [
    # Credenciales / secretos
    ("API key OpenRouter", "CRITICO", r"sk-or-[A-Za-z0-9\-_]{16,}"),
    ("API key Anthropic", "CRITICO", r"sk-ant-[A-Za-z0-9\-_]{16,}"),
    ("API key OpenAI", "CRITICO", r"sk-[A-Za-z0-9\-_]{20,}"),
    ("GitHub token", "CRITICO", r"(ghp_|gho_|github_pat_)[A-Za-z0-9_]{16,}"),
    ("HuggingFace token", "CRITICO", r"hf_[A-Za-z0-9]{20,}"),
    ("Slack token", "CRITICO", r"xox[baprs]-[A-Za-z0-9\-]{10,}"),
    ("AWS key", "CRITICO", r"AKIA[0-9A-Z]{16}"),
    ("Stripe key", "CRITICO", r"sk_(live|test)_[A-Za-z0-9]{16,}"),
    ("Clave privada", "CRITICO", r"BEGIN (RSA |OPENSSH |EC |DSA )?PRIVATE KEY"),
    ("JWT-like", "ALTO", r"eyJ[A-Za-z0-9_\-]{20,}\.eyJ[A-Za-z0-9_\-]{20,}"),
    ("Password inline", "ALTO", r"(?i)(password|passwd|secret)\s*[:=]\s*['\"][^'\"]{6,}['\"]"),
    # Identidad de maquina (variantes concretas -> archivo local)
    ("Ruta home Linux", "CRITICO", r"/home/[a-z0-9_]{4,}/"),
    (
        "Ruta Windows usuario",
        "ALTO",
        r"[A-Za-z]:[\\\\/](?:Users|users)[\\\\/](?!Public)[A-Za-z0-9_.\-]+",
    ),
    (
        "Usuario de sistema",
        "ALTO",
        r"(?:^|[\s\"'=(/])(?:login|user(?:name)?)\s*[:=]\s*[\"']?[a-z][a-z0-9_]{4,}[\"']?",
    ),
    ("ID de plataforma tipo user_xxx", "ALTO", r"\buser_[A-Za-z0-9]{16,}"),
    (
        "Email no-test",
        "ALTO",
        r"[A-Za-z0-9._%+\-]+@(?!example\.(?:com|org|test)|dominio\.mx|gmail\.com|users\.noreply\.github\.com)[A-Za-z0-9.\-]+\.[A-Za-z]{2,}",
    ),
    (
        "Telefono MX/US (formato separado)",
        "MEDIO",
        r"(?<![\dA-Za-z])(?:\+?52[\s\-]?)?(?:1[\s\-]?)?\(?\d{2,3}\)?[\s\-]\d{4}[\s\-]\d{4}(?![\dA-Za-z])",
    ),
    ("IP publica", "MEDIO", r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"),
    # Binarios sensibles
    ("Referencia a audio personal", "MEDIO", r"(?i)\.mp3\b"),
]

_LOCAL_PATTERNS_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "audit_patterns_local.txt"
)


def _load_local_patterns():
    """Lineas: nombre|severidad|regex. Archivo local, NUNCA commiteado."""
    extra = []
    if os.path.exists(_LOCAL_PATTERNS_FILE):
        with open(_LOCAL_PATTERNS_FILE, encoding="utf-8") as fh:
            for ln in fh:
                ln = ln.strip()
                if not ln or ln.startswith("#"):
                    continue
                parts = ln.split("|", 2)
                if len(parts) == 3:
                    extra.append((parts[0], parts[1], parts[2]))
    return extra


PATTERNS = PATTERNS_BASE + _load_local_patterns()

SKIP_DIR = re.compile(r"(^|/)(\.git|node_modules|vendor|\.venv|venv)(/|$)")


def tracked_files():
    out = subprocess.run(
        ["git", "ls-files", "-z"], capture_output=True, text=True, check=True
    ).stdout
    return [f for f in out.split("\0") if f]


def scan_tree(findings):
    for path in tracked_files():
        if SKIP_DIR.search(path):
            continue
        try:
            with open(path, "rb") as fh:
                data = fh.read()
        except OSError:
            continue
        if b"\0" in data[:4096]:
            if re.search(r"\.(mp3|wav|zip|tar|db)$", path, re.I):
                findings["Archivo binario sensible [REVISAR]"].append(f"ARBOL {path}")
            continue
        text = data.decode("utf-8", errors="replace")
        for i, line in enumerate(text.splitlines(), 1):
            if len(line) > 2000:
                line = line[:2000]
            for name, sev, pat in PATTERNS:
                if re.search(pat, line):
                    findings[f"{name} [{sev}]"].append(f"ARBOL {path}:{i}: {line.strip()[:160]}")


def scan_history(findings):
    """Todos los blobs alcanzables de todos los refs: el caso real de
    'ya lo borre del arbol pero sigue en la historia'."""
    out = subprocess.run(
        ["git", "rev-list", "--objects", "--all"], capture_output=True, text=True, check=True
    ).stdout
    seen = {}
    for ln in out.splitlines():
        sha, _, rest = ln.partition(" ")
        if rest and rest not in seen:
            seen[rest] = sha
    n = 0
    for path, sha in seen.items():
        if SKIP_DIR.search(path):
            continue
        try:
            r = subprocess.run(["git", "cat-file", "-p", sha], capture_output=True, timeout=20)
        except subprocess.TimeoutExpired:
            continue
        if r.returncode != 0:
            continue
        data = r.stdout
        if b"\0" not in data[:4096]:
            text = data.decode("utf-8", errors="replace")
            for name, sev, pat in PATTERNS:
                hits = len(re.findall(pat, text))
                if hits:
                    findings[f"{name} [{sev}]"].append(
                        f"HISTORIA {path} ({hits}x en blob {sha[:8]})"
                    )
        n += 1
    print(f"# historia escaneada: {n} objetos unicos", file=sys.stderr)


def main():
    findings = defaultdict(list)
    scan_tree(findings)
    if "--historia" in sys.argv:
        scan_history(findings)
    order = ["CRITICO", "ALTO", "MEDIO", "REVISAR"]
    total = 0
    for sev in order:
        keys = sorted(k for k in findings if k.endswith(f"[{sev}]"))
        for k in keys:
            items = findings[k]
            total += len(items)
            print(f"\n=== {k} — {len(items)} hallazgos ===")
            for it in items[:15]:
                print("  " + it)
            if len(items) > 15:
                print(f"  ... y {len(items) - 15} más")
    print(f"\nTOTAL: {total} hallazgos")
    if not _load_local_patterns():
        print(
            "AVISO: no existe scripts/audit_patterns_local.txt — la auditoria "
            "corrio solo con patrones genericos. Anade ahi los nombres "
            "especificos que quieres proteger ANTES de publicar."
        )
    sys.exit(0)


if __name__ == "__main__":
    main()
