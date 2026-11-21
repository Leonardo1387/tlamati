#!/usr/bin/env python3
"""Auditoria pre-publicacion: escanea ARBOL (tracked) e HISTORIA git completa
buscando cualquier cosa que comprometa privacidad, integridad del trabajo o
credenciales. Salida: hallazgos por severidad con archivo:linea (arbol) o
commit:blob (historia).

Uso: python3 scripts/audit_publicacion.py [--historia]
"""
import re
import subprocess
import sys
from collections import defaultdict

# --- Patrones: (nombre, severidad, regex) -----------------------------------
PATTERNS = [
    # Credenciales / secretos
    ("API key OpenRouter", "CRITICO", r"sk-or-[A-Za-z0-9\-_]{16,}"),
    ("API key Anthropic", "CRITICO", r"sk-ant-[A-Za-z0-9\-_]{16,}"),
    ("API key OpenAI", "CRITICO", r"sk-[A-Za-z0-9\-_]{20,}"),
    ("GitHub token", "CRITICO", r"(ghp_|gho_|github_pat_)[A-Za-z0-9_]{16,}"),
    ("HuggingFace token", "CRITICO", r"hf_[A-Za-z0-9]{20,}"),
    ("Slack/Discord token", "CRITICO", r"xox[baprs]-[A-Za-z0-9\-]{10,}"),
    ("AWS key", "CRITICO", r"AKIA[0-9A-Z]{16}"),
    ("Stripe key", "CRITICO", r"sk_(live|test)_[A-Za-z0-9]{16,}"),
    ("Clave privada", "CRITICO", r"BEGIN (RSA |OPENSSH |EC |DSA )?PRIVATE KEY"),
    ("Supabase/anon-like JWT", "ALTO", r"eyJ[A-Za-z0-9_\-]{20,}\.eyJ[A-Za-z0-9_\-]{20,}"),
    ("Password inline", "ALTO", r"(?i)(password|passwd|secret)\s*[:=]\s*['\"][^'\"]{6,}['\"]"),
    # Identidad del fundador / maquina
    ("Usuario WSL", "CRITICO", r"usuario"),
    ("Ruta Windows usuario", "ALTO", r"[A-Za-z]:[\\\\/](Users|users)[\\\\/](?!Admin\b)[A-Za-z0-9_.\-]+"),
    ("GitHub handle", "ALTO", r"leonardoGH|leonardo1387"),
    ("OpenRouter user id", "ALTO", r"\buser_[A-Za-z0-9]{16,}"),
    ("Email personal", "ALTO", r"[A-Za-z0-9._%+\-]+@(?!example\.(com|org)|gmail\.com|users\.noreply\.github\.com|convrsations\.ai)[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"),
    ("Telefono MX/US", "MEDIO", r"(?<!\d)(?:\+?52[\s\-]?)?(?:1[\s\-]?)?\(?\d{2,3}\)?[\s\-]?\d{4}[\s\-]?\d{4}(?!\d)"),
    ("IP publica", "MEDIO", r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"),
    # Negocios / proyectos del fundador que no deben vincularse
    ("Negocio: Producto A", "ALTO", r"(?i)escudo\s+legal"),
    ("Negocio: App Vial", "ALTO", r"(?i)abogado[\s\-_]vial"),
    ("Proyecto: [REDACTED_PROYECTO]", "ALTO", r"(?i)paso[\s\-_]cero|proyectolegal"),
    ("Proyecto: PlataformaEdtech/edtech-plat", "ALTO", r"(?i)edtech_int_int_int_int_int_int_int|edtech-plat"),
    ("Proyecto: consult", "ALTO", r"(?i)consult"),
    ("Proveedor nube: Enverge", "MEDIO", r"(?i)enverge"),
    ("Correo negocio", "ALTO", r"convrsations"),
    # Binarios sensibles
    ("Archivo de voz/mp3 referenciado", "MEDIO", r"(?i)\.mp3\b"),
]

TEXT_EXT = re.compile(
    r"\.(py|md|txt|json|jsonl|toml|yml|yaml|cfg|ini|sh|bash|log|csv|tsv|"
    r"html|css|js|ts|lock|rst|tex|svg|xml|env|diff|patch)$", re.I)
SKIP_DIR = re.compile(r"(^|/)(\.git|node_modules|vendor|\.venv|venv)(/|$)")


def tracked_files():
    out = subprocess.run(["git", "ls-files", "-z"], capture_output=True,
                         text=True, check=True).stdout
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
            # binario: solo registrar nombre si parece sensible
            for name, sev, rx in [("Archivo binario desconocido", "REVISAR",
                                   re.compile(r"\.(mp3|wav|png|jpg|zip|tar|db)$", re.I))]:
                if rx.search(path):
                    findings[f"{name} [{sev}]"].append(f"ARBOL {path}")
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if len(line) > 2000:
                line = line[:2000]
            for name, sev, pat in PATTERNS:
                if re.search(pat, line):
                    findings[f"{name} [{sev}]"].append(
                        f"ARBOL {path}:{i}: {line.strip()[:160]}")


def scan_history(findings):
    """Todos los blobs que EXISTIERON en cualquier commit."""
    out = subprocess.run(
        ["git", "rev-list", "--objects", "--all"],
        capture_output=True, text=True, check=True).stdout
    blobs = []
    for ln in out.splitlines():
        sha, _, rest = ln.partition(" ")
        if rest:
            blobs.append((sha, rest))
    # dedupe por path, mantener primer sha encontrado
    seen = {}
    for sha, path in blobs:
        if path not in seen and not SKIP_DIR.search(path):
            seen[path] = sha
    n = 0
    for path, sha in seen.items():
        try:
            r = subprocess.run(["git", "cat-file", "-p", sha],
                               capture_output=True, timeout=20)
        except subprocess.TimeoutExpired:
            continue
        if r.returncode != 0:
            continue
        data = r.stdout
        if b"\0" in data[:4096]:
            n += 1
            continue
        text = data.decode("utf-8", errors="replace")
        for name, sev, pat in PATTERNS:
            hits = sum(1 for m in re.findall(pat, text))
            if hits:
                findings[f"{name} [{sev}]"].append(
                    f"HISTORIA {path} ({hits}x en {sha[:8]})")
        n += 1
    print(f"# historia escaneada: {n} objetos", file=sys.stderr)


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
                print(f"  ... y {len(items)-15} más")
    print(f"\nTOTAL: {total} hallazgos")
    sys.exit(0)


if __name__ == "__main__":
    main()
