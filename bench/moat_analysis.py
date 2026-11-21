# ruff: noqa: RUF001  (informe en espanol con signos intencionales)
"""bench/moat_analysis.py — responde las 5 hipótesis del MOAT de contexto.

Tesis del fundador (19-nov sesión 25): "una arquitectura cuya ventaja económica
se acumula a medida que aumenta el trabajo que realiza. Eso es lo que hay que
medir."

HIPÓTESIS (cada una con su número):
  H1 COMPOUNDING: codex re-envía historia → su costo POR LLAMADA crece más
     rápido que el de tlamati (pendiente de la curva, no solo arranque).
  H2 ESCALA: el ratio codex/tlamati CRECE con la longitud de la tarea
     (cortas vs medias vs largas). Si no crece, la tesis se debilita — hay
     que saberlo nosotros antes que un cliente.
  H3 GENERALIZACIÓN: el ratio se mantiene entre modelos (propiedad del arnés,
     no del cerebro).
  H4 NEGOCIO: costo por tarea RESUELTA ($) y % de ahorro — la métrica que una
     empresa que corre agentes a escala entiende sin traducción.
  H5 PREFIJO MAGRO: tokens del primer request/turno (el piso fijo por tarea).

Fuentes (todo real, nada estimado salvo $ que usa la tabla PRICES del runner):
  - evals/campaign_*/{tlamati,codex}.jsonl — totales por corrida
  - /tmp/tlamati-bench/_raw/<harness>/*.jsonl — eventos crudos por corrida
    (tlamati: turn_end con usage por turno; codex: turn.completed final)
  - *.stderr TRACE de codex (si la corrida se lanzó con RUST_LOG=codex_client=trace):
    tamaños de POST por request → curva real de codex (proxy bytes/4 validado
    con error 0.43% contra usage oficial, 19-nov).

Uso:  python3 bench/moat_analysis.py [--evals-dir evals/] [--md SALIDA.md]
Reglas de honestidad: null = null; corrida única se fecha; LO ESTIMADO se declara.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import statistics
from pathlib import Path
from typing import Any

BYTES_PER_TOKEN = 4  # proxy validado 19-nov: suma POSTs vs usage oficial, error 0.43%


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text().splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


# ---------------------------------------------------------------- curvas


def curva_tlamati(raw: Path) -> list[int] | None:
    """input_tokens POR TURNO desde eventos turn_end (usage es por-turno:
    audit.db turn_costs se alimenta de lo mismo y su suma cuadra con el total)."""
    per_turn = []
    for ev in load_jsonl(raw):
        if ev.get("event") == "turn_end":
            usage = ev.get("usage") or {}
            tin = usage.get("input_tokens")
            if tin:
                per_turn.append(int(tin))
    return per_turn or None


def curva_codex(raw_stderr: Path) -> list[int] | None:
    """≈tokens POR REQUEST desde POST bodies del TRACE (bytes/4)."""
    if not raw_stderr.is_file():
        return None
    sizes = []
    for line in raw_stderr.read_text(errors="replace").splitlines():
        if "POST to http" in line:
            m = re.search(r"POST to \S+: (\{.*)$", line)
            if m:
                sizes.append(len(m.group(1)) // BYTES_PER_TOKEN)
    return sizes or None


def slope(xs: list[int]) -> float:
    """Pendiente de regresión lineal (tokens por llamada adicional)."""
    n = len(xs)
    if n < 2:
        return 0.0
    mx = (n - 1) / 2
    my = sum(xs) / n
    num = sum((i - mx) * (y - my) for i, y in enumerate(xs))
    den = sum((i - mx) ** 2 for i in range(n))
    return num / den if den else 0.0


# ---------------------------------------------------------------- celdas


def cells(evals_dir: Path) -> dict[str, dict[str, list[dict[str, Any]]]]:
    """{modelo_slug: {harness: filas}} de todos los dirs campaign_*."""
    out: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for d in sorted(evals_dir.glob("campaign_*")):
        if not d.is_dir():
            continue
        slug = d.name.replace("campaign_2026-11_", "")
        for h in ("tlamati", "codex", "opencode", "hermes"):
            rows = load_jsonl(d / f"{h}.jsonl")
            if rows:
                out.setdefault(slug, {})[h] = rows
    return out


def agg(rows: list[dict[str, Any]]) -> dict[str, Any]:
    tin = [r["tokens_in"] for r in rows if r.get("tokens_in")]
    tout = [r["tokens_out"] for r in rows if r.get("tokens_out")]
    cost = [r["cost_usd"] for r in rows if r.get("cost_usd")]
    cache = [
        r["cache_read"] / r["tokens_in"]
        for r in rows
        if r.get("tokens_in") and r.get("cache_read") is not None
    ]
    solved = [r for r in rows if r["success"]]
    cost_solved = [r["cost_usd"] for r in solved if r.get("cost_usd")]
    return {
        "n": len(rows),
        "ok": len(solved),
        "tin_mu": statistics.mean(tin) if tin else None,
        "tout_mu": statistics.mean(tout) if tout else None,
        "cache_mu": statistics.mean(cache) if cache else None,
        "cost_total": sum(cost) if cost else None,
        "cost_per_solved": statistics.mean(cost_solved) if cost_solved else None,
        "nulls": sum(1 for r in rows if r.get("tokens_in") is None),
    }


# ---------------------------------------------------------------- informe


def main() -> int:
    ap = argparse.ArgumentParser(description="Análisis del moat de contexto (H1-H5)")
    ap.add_argument("--evals-dir", default="evals")
    ap.add_argument("--raw-root", default="/tmp/tlamati-bench/_raw")
    ap.add_argument("--md", help="escribir informe markdown aquí")
    args = ap.parse_args()

    evals = Path(args.evals_dir)
    raw_root = Path(args.raw_root)
    data = cells(evals)
    if not data:
        print(f"sin campañas en {evals}")
        return 1

    L: list[str] = []

    def say(s: str = "") -> None:
        print(s)
        L.append(s)

    say("# MOAT DE CONTEXTO — análisis de campaña")
    say(
        f"fuente: {evals} + curvas {raw_root} · proxy codex bytes/{BYTES_PER_TOKEN}"
        " (validado 0.43% vs usage oficial)"
    )
    say("costos = tabla PRICES estimada, NO factura OpenRouter (honestidad EVALS).")
    say()

    # ── H3 + H4: tabla general (ratios por modelo + negocio) ──
    say("## H3 GENERALIZACIÓN + H4 NEGOCIO (totales por celda)")
    say(
        f"{'modelo':30} {'arnés':8} {'ok/n':>6} {'tin μ':>9} {'cache%':>7} "
        f"{'$/tarea OK':>10} {'ratio':>6}"
    )
    ratios: dict[str, float | None] = {}
    for slug, hs in data.items():
        aggs = {h: agg(rows) for h, rows in hs.items()}
        t, c = aggs.get("tlamati"), aggs.get("codex")
        ratio = (c["tin_mu"] / t["tin_mu"]) if (t and c and t["tin_mu"] and c["tin_mu"]) else None
        ratios[slug] = ratio
        for h, a in sorted(aggs.items()):
            cps = f"${a['cost_per_solved']:.4f}" if a["cost_per_solved"] else "null"
            cache = f"{a['cache_mu'] * 100:.1f}" if a["cache_mu"] is not None else "-"
            tin = f"{a['tin_mu']:,.0f}" if a["tin_mu"] else "null"
            r = f"{ratio:.2f}×" if (ratio and h == "codex" and t) else ""
            nulls = f" *{a['nulls']} nulls" if a["nulls"] else ""
            say(
                f"{slug:30} {h:8} {a['ok']:>3}/{a['n']:<2} {tin:>9} {cache:>7} "
                f"{cps:>10} {r:>6}{nulls}"
            )
    say()
    if ratios:
        vals = [r for r in ratios.values() if r]
        say(
            "ratio codex/tlamati entre modelos: "
            + " · ".join(f"{s}={r:.2f}×" for s, r in ratios.items() if r)
        )
        if len(vals) >= 2:
            say(
                f"rango: {min(vals):.2f}×–{max(vals):.2f}× "
                f"(mediana {statistics.median(vals):.2f}×) → "
                + (
                    "SE GENERALIZA (mismo orden)"
                    if min(vals) > 1.2
                    else "NO uniforme — reportar desviación honesta"
                )
            )
    say()

    # ── H2 ESCALA: ratio por longitud de tarea ──
    say("## H2 ESCALA — ¿el ratio crece con la longitud de la tarea?")
    say("longitud = turnos de tlamati en esa tarea (proxy comparable entre arneses)")
    buckets = {"corta (≤5 turnos)": (0, 5), "media (6-12)": (6, 12), "larga (>12)": (13, 10**6)}
    per_task: dict[str, dict[str, dict[Any, list[int]]]] = {}
    for slug, hs in data.items():
        tl_by_task: dict[Any, list[int]] = {}
        cx_by_task: dict[Any, list[int]] = {}
        turns_by_task: dict[Any, list[int]] = {}
        for r in hs.get("tlamati", []):
            if r.get("tokens_in"):
                tl_by_task.setdefault(r["task"], []).append(r["tokens_in"])
            if r.get("turns"):
                turns_by_task.setdefault(r["task"], []).append(r["turns"])
        for r in hs.get("codex", []):
            if r.get("tokens_in"):
                cx_by_task.setdefault(r["task"], []).append(r["tokens_in"])
        per_task[slug] = {"tl": tl_by_task, "cx": cx_by_task, "turns": turns_by_task}

    say(f"{'bucket':20} {'tareas':>6} {'tin μ tlamati':>14} {'tin μ codex':>12} {'ratio':>7}")
    for name, (lo, hi) in buckets.items():
        tls, cxs, ntasks = [], [], 0
        for _slug, d in per_task.items():
            for task, turns in d["turns"].items():
                mu_t = statistics.mean(turns)
                if lo <= mu_t <= hi and task in d["tl"] and task in d["cx"]:
                    tls.append(statistics.mean(d["tl"][task]))
                    cxs.append(statistics.mean(d["cx"][task]))
                    ntasks += 1
        if tls:
            t_mu, c_mu = statistics.mean(tls), statistics.mean(cxs)
            say(f"{name:20} {ntasks:>6} {t_mu:>14,.0f} {c_mu:>12,.0f} {c_mu / t_mu:>6.2f}×")
        else:
            say(f"{name:20} {0:>6} {'—':>14} {'—':>12} {'n/d':>7}")
    say("(si el ratio SUBE de corta→larga, la ventaja es compuesta y escala;")
    say(" si es plano, la ventaja viene del prefijo+llamadas, no del crecimiento)")
    say()

    # ── H1 + H5: curvas por llamada (requiere _raw con turn_end / TRACE stderr) ──
    say("## H1 COMPOUNDING + H5 PREFIJO — curvas por llamada (evidencia _raw)")
    say(f"{'celda':45} {'arranque':>9} {'pendiente':>10} {'n':>4}")
    any_curve = False
    for raw_h in sorted(raw_root.glob("*")) if raw_root.is_dir() else []:
        h = raw_h.name
        for f in sorted(raw_h.glob("*.jsonl")):
            curva = curva_tlamati(f) if h == "tlamati" else None
            if curva is None and h == "codex":
                curva = curva_codex(f.with_suffix(".stderr"))
            if curva and len(curva) >= 3:
                any_curve = True
                say(f"{h + '/' + f.name:45} {curva[0]:>9,} {slope(curva):>10,.0f} {len(curva):>4}")
    if not any_curve:
        say("sin curvas capturadas aún (el runner guarda _raw desde el fix del 19-nov;")
        say(" codex necesita RUST_LOG=codex_client=trace para la curva por request).")
        say("Las curvas de referencia medidas a mano el 19-nov (instruccion_en_archivo, flash):")
        say("  tlamati: arranque 7,649 · pendiente +717 tok/turno · 7 turnos · total 69,344")
        say("  codex:   arranque 11,258 · pendiente +1,212 tok/request · 14 req · total 264,729")
        say("  → H1 sostenida: pendiente 1.69× más empinada + prefijo 1.47× más gordo")
        say("  → H5 sostenida; ratio de la tarea 3.80× (usage oficial codex)")
    say()

    # ── H7 VARIANZA: ¿predecible, no solo barato? ──
    say("## H7 VARIANZA — ¿la ventaja es predecible o suerte de una corrida?")
    say(
        f"{'celda':40} {'tin med':>9} {'tin stdev':>10} "
        f"{'$P50':>8} {'$P90':>8} {'$P95':>8} {'ok%[IC95 Wilson]':>18} {'TO':>3}"
    )

    def pct(xs: list[float], p: float) -> float:
        s = sorted(xs)
        k = (len(s) - 1) * p
        lo, hi = int(k), min(int(k) + 1, len(s) - 1)
        return s[lo] + (s[hi] - s[lo]) * (k - lo)

    def wilson(k: int, n: int) -> tuple[float, float]:
        if n == 0:
            return (0.0, 0.0)
        z = 1.959964
        ph = k / n
        den = 1 + z * z / n
        c = ph + z * z / (2 * n)
        m = z * ((ph * (1 - ph) / n + z * z / (4 * n * n)) ** 0.5)
        return ((c - m) / den, (c + m) / den)

    boot_cells: dict[str, dict[str, dict[Any, list[int]]]] = {}
    for slug, hs in data.items():
        for h, rows in sorted(hs.items()):
            tin = [r["tokens_in"] for r in rows if r.get("tokens_in")]
            cost = [r["cost_usd"] for r in rows if r.get("cost_usd") is not None]
            ok = sum(1 for r in rows if r["success"])
            lo, hi = wilson(ok, len(rows))
            tos = sum(1 for r in rows if (r.get("error") or "").startswith("harness timeout"))
            med = f"{statistics.median(tin):,.0f}" if tin else "null"
            sd = f"{statistics.stdev(tin):,.0f}" if len(tin) > 1 else "-"
            p50 = f"${pct(cost, 0.5):.4f}" if cost else "null"
            p90 = f"${pct(cost, 0.9):.4f}" if cost else "null"
            p95 = f"${pct(cost, 0.95):.4f}" if cost else "null"
            say(
                f"{slug + ' × ' + h:40} {med:>9} {sd:>10} {p50:>8} {p90:>8} {p95:>8} "
                f"{ok * 100 // max(len(rows), 1):>3}% [{lo * 100:.0f}-{hi * 100:.0f}%]".ljust(118)
                + f" {tos:>3}"
            )
            if h in ("tlamati", "codex"):
                by_task: dict[Any, list[int]] = {}
                for r in rows:
                    if r.get("tokens_in"):
                        by_task.setdefault(r["task"], []).append(r["tokens_in"])
                boot_cells.setdefault(slug, {})[h] = by_task
    say()

    # Bootstrap AGRUPADO POR TAREA: las 3 réplicas de una tarea NO son
    # independientes → la unidad de remuestreo es la TAREA (media de sus réplicas).
    rng = random.Random(20261119)  # semilla fija = reproducible
    B = 10_000
    say("### Bootstrap del ratio codex/tlamati (unidad = tarea, B=10,000, semilla fija)")
    say(f"{'modelo':32} {'ratio puntual':>13} {'IC95':>16} {'P(ratio>1.5)':>12}")
    for slug, d in boot_cells.items():
        tl, cx = d.get("tlamati"), d.get("codex")
        if not tl or not cx:
            continue
        tasks = sorted(set(tl) & set(cx))
        if len(tasks) < 3:
            say(f"{slug:32} {'n/d':>13} (solo {len(tasks)} tareas comunes)")
            continue
        t_mu = {t: statistics.mean(tl[t]) for t in tasks}
        c_mu = {t: statistics.mean(cx[t]) for t in tasks}
        point = sum(c_mu.values()) / sum(t_mu.values())
        boots: list[float] = []
        for _ in range(B):
            samp = [tasks[rng.randrange(len(tasks))] for _ in tasks]
            den = sum(t_mu[t] for t in samp)
            if den:
                boots.append(sum(c_mu[t] for t in samp) / den)
        boots.sort()
        lo = boots[int(0.025 * len(boots))]
        hi = boots[int(0.975 * len(boots))]
        p15 = sum(1 for b in boots if b > 1.5) / len(boots)
        say(f"{slug:32} {point:>12.2f}× [{lo:.2f}–{hi:.2f}]×".ljust(66) + f" {p15 * 100:>10.1f}%")
    say("(frase del pitch = 'la ventaja es X× [IC95 a–b]'; P(ratio>1.5) es la")
    say(" probabilidad bootstrap de que la ventaja sea al menos 1.5×)")
    say()

    # ── H8 DESCOMPOSICIÓN: ¿de dónde sale el 3x? ──
    say("## H8 DESCOMPOSICIÓN — ¿de dónde sale la ventaja? (prefijo × pendiente × llamadas)")
    say("modelo: total ≈ arranque + pendiente·(n-1) por llamada; se descompone el ratio")
    curves: list[tuple[str, str, list[int]]] = []
    if Path("/tmp/curva_tlamati.jsonl").is_file():
        c = curva_tlamati(Path("/tmp/curva_tlamati.jsonl"))
        if c:
            curves.append(("referencia 19-nov instruccion_en_archivo (flash)", "tlamati", c))
    if Path("/tmp/curva_codex.stderr").is_file():
        c = curva_codex(Path("/tmp/curva_codex.stderr"))
        if c:
            curves.append(("referencia 19-nov instruccion_en_archivo (flash)", "codex", c))
    if raw_root.is_dir():
        for raw_h in sorted(raw_root.glob("*")):
            h = raw_h.name
            for f in sorted(raw_h.glob("*.jsonl")):
                c = curva_tlamati(f) if h == "tlamati" else None
                if c is None and h == "codex":
                    c = curva_codex(f.with_suffix(".stderr"))
                if c and len(c) >= 3:
                    curves.append((f"{h}/{f.stem}", h, c))
    seen: set[tuple[str, str]] = set()
    for label, h, c in curves:
        if (label, h) in seen:
            continue
        seen.add((label, h))
        total = sum(c)
        arranque = c[0]
        pend = slope(c)
        say(
            f"- {label} [{h}]: n={len(c)} llamadas · arranque {arranque:,} · "
            f"pendiente +{pend:,.0f}/llamada · total {total:,}"
        )
    pairs: dict[str, dict[str, tuple[list[int], int, float, int]]] = {}
    for label, h, c in curves:
        pairs.setdefault(label, {})[h] = (c, c[0], slope(c), len(c))
    for plabel, pd in pairs.items():
        if "tlamati" in pd and "codex" in pd:
            (ct, at, pt, nt), (cc, ac, pc, nc) = pd["tlamati"], pd["codex"]
            tt, tc = sum(ct), sum(cc)
            if not tt or not at or not pt:
                continue
            say(f"  → {plabel}: ratio total {tc / tt:.2f}× descompuesto:")
            say(f"     prefijo: tlamati {at:,} vs codex {ac:,} = {ac / at:.2f}×")
            say(f"     pendiente: tlamati +{pt:,.0f} vs codex +{pc:,.0f} = {pc / pt:.2f}×")
            say(f"     llamadas: tlamati {nt} vs codex {nc} = {nc / nt:.2f}×")
            comp = (ac / at) * (pc / pt) * (nc / nt)
            say(f"     producto de factores ≈ {comp:.2f}× (aprox: los términos se solapan)")
    say()

    # ── veredicto ──
    say("## VEREDICTO (se rellena con los números de arriba)")
    if ratios:
        vals = [r for r in ratios.values() if r]
        say(f"- H3: ratio mediano {statistics.median(vals):.2f}× en {len(vals)} modelos")
    say("- H1/H5: ver sección de curvas (referencia 19-nov si no hay _raw)")
    say("- H2: ver buckets — es LA prueba del compounding en el corpus actual")

    if args.md:
        Path(args.md).write_text("\n".join(L) + "\n")
        print(f"\ninforme escrito en {args.md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
