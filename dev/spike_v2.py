"""S1.3 — skillopt spike REBUILT (25-nov-2026).

The original spike branch (spike/skillopt, 6a50338) was lost in the pre-
publication filter-repo: only README + CLASE_18/19 survived. The founder's
call: rebuild it, re-run it, and point the README at real, reproducible
artifacts this time.

Design (faithful to the original, distilled from CLASE_18/19):
  fixture:  fixtures/instruccion_en_archivo (broken validador.py vs SPEC.md)
  arms:     v0 (NO skill) vs mut1/mut2 (SKILL.md injected via
            <workdir>/.tlamati/skills/) — mutations PROPOSED by the model
            from observed v0 failures (one cheap OpenRouter call each)
  harness:  .venv/bin/tlamati -p ... --json headless, isolated HOME,
            --no-memory, --approve-tool '*' (fixture is trusted, self-owned)
  judge:    python3 verify.py inside the fresh workdir (exit 0 = success)
  stats:    Fisher exact one-sided (stdlib math.comb) per model + pooled
  resume:   every run appended to dev/spike_v2_progress.json (skip if done)
  budget:   HARD cap $8 — aborts proposing/benching before exceeding.

Run:  cd ~/code/tlamati && .venv/bin/python dev/spike_v2.py \
        [--phase collect|propose|bench|report|all]
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib import error as urlerror
from urllib import request as urlrequest

REPO = Path(__file__).resolve().parent.parent
FIXTURE = REPO / "fixtures" / "instruccion_en_archivo"
TLAMATI = REPO / ".venv" / "bin" / "tlamati"
PROGRESS = REPO / "dev" / "spike_v2_progress.json"
PROPOSALS = REPO / "dev" / "spike_v2_skill_mut1.md", REPO / "dev" / "spike_v2_skill_mut2.md"
RESULTS = REPO / "dev" / "spike_v2_results.json"
LOG = REPO / "dev" / "spike_v2_run.log"
SPEND_PATH = REPO / "dev" / "spike_v2_spend.json"

MODELS = {"flash": "qwen/qwen3.8-flash", "coder": "qwen/qwen3-coder"}
SEED_N = {"flash": 6, "coder": 4}  # v0 failures to gather for the proposer
BENCH_N = {"flash": 25, "coder": 20}  # per arm (S1.2: 35/30; 25/20 + prior = enough to replicate)
MAX_TURNS = 40
RUN_TIMEOUT = 420  # seconds per headless run
HARD_CAP_USD = 8.0
CONCURRENCY = 3
API_URL = "https://openrouter.ai/api/v1/chat/completions"

PROMPT = (
    "validador.py en este directorio NO cumple SPEC.md. Lee SPEC.md completo "
    "(reglas R1-R6, orden de prioridad y tabla de códigos), arregla "
    "validador.py y verifica con `python3 verify.py` hasta que imprima "
    "VERIFY OK. No modifiques SPEC.md, datos/comunes.txt ni verify.py."
)

# RLock, NO Lock: run_once llama a _add_spend YA teniendo el lock (deadlock si no
# es reentrante — el humo colgado real del 25-nov).
_lock = threading.RLock()


def _api_key() -> str:
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if key:
        return key
    env = Path.home() / ".hermes" / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("OPENROUTER_API_KEY="):
                return line.split("=", 1)[1].strip().strip("'\"")
    raise SystemExit("no OPENROUTER_API_KEY in env nor ~/.hermes/.env")


def _spend() -> float:
    if SPEND_PATH.exists():
        return json.loads(SPEND_PATH.read_text())["spent_usd"]
    return 0.0


def _add_spend(amount: float, label: str) -> None:
    with _lock:
        if SPEND_PATH.exists():
            data = json.loads(SPEND_PATH.read_text())
        else:
            data = {"spent_usd": 0.0, "items": []}
        data["spent_usd"] = round(data["spent_usd"] + amount, 5)
        data["items"].append(
            {"label": label, "usd": round(amount, 5), "ts": time.strftime("%H:%M:%S")}
        )
        SPEND_PATH.write_text(json.dumps(data, indent=1))


# ---------------------------------------------------------------- runs


def fresh_workdir(tag: str) -> tuple[Path, Path]:
    """Isolated HOME + fresh fixture copy (no __pycache__, no stray edits)."""
    rnd = f"{int(time.time())}-{random.randint(0, 9999)}"
    wd = Path(f"/tmp/skillopt-v2/work-{tag}-{rnd}")
    home = Path(f"/tmp/skillopt-v2/home-{tag}-{rnd}")
    if wd.exists():
        shutil.rmtree(wd)
    shutil.copytree(FIXTURE, wd, ignore=shutil.ignore_patterns("__pycache__"))
    home.mkdir(parents=True, exist_ok=True)
    return wd, home


def run_once(model: str, skill_text: str | None, tag: str) -> dict:
    Path("/tmp/skillopt-v2").mkdir(exist_ok=True)
    wd, home = fresh_workdir(tag)
    if skill_text is not None:
        sdir = wd / ".tlamati" / "skills" / "spec-fix"
        sdir.mkdir(parents=True)
        (sdir / "SKILL.md").write_text(skill_text, encoding="utf-8")
    env = dict(os.environ)
    env["HOME"] = str(home)
    env["OPENROUTER_API_KEY"] = _api_key()
    cmd = [
        str(TLAMATI),
        "-p",
        PROMPT,
        "--model",
        model,
        "--max-turns",
        str(MAX_TURNS),
        "--json",
        "--no-memory",
        "--approve-tool",
        "*",
        "--no-subagents",
        "--quiet",
    ]
    t0 = time.time()
    rec: dict = {
        "tag": tag,
        "model": model,
        "ok": False,
        "turns": None,
        "cost_usd": None,
        "stop_reason": None,
        "dur_s": None,
        "final_text": "",
        "error": None,
    }
    # FIX 25-nov: NUNCA capture_output=True con timeout. subprocess.run mata al
    # hijo pero luego DRENA los pipes; si un nieto (bwrap) hereda el PIPE, el
    # drenaje bloquea para siempre (el smoke colgado de 500s). Solución:
    # stdout/stderr a archivos + start_new_session + killpg en timeout.
    out_f = tempfile.NamedTemporaryFile(  # noqa: SIM115 — vida gestionada por el finally
        mode="w+", suffix=".out", prefix=f"spike-{tag}-", dir="/tmp/skillopt-v2", delete=False
    )
    err_f = tempfile.NamedTemporaryFile(  # noqa: SIM115
        mode="w+", suffix=".err", prefix=f"spike-{tag}-", dir="/tmp/skillopt-v2", delete=False
    )
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=wd,
            env=env,
            stdout=out_f,
            stderr=err_f,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
            text=True,
        )
        timed_out = False
        try:
            proc.wait(timeout=RUN_TIMEOUT)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(proc.pid, signal.SIGTERM)
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait(timeout=5)
        out_f.seek(0)
        stdout = out_f.read()
        err_f.seek(0)
        stderr = err_f.read()
        rec["dur_s"] = round(time.time() - t0, 1)
        if timed_out:
            rec["error"] = "timeout"
        result_ev = None
        for line in stdout.splitlines():
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if ev.get("event") == "result":
                result_ev = ev
        if result_ev is None:
            if not rec["error"]:
                rec["error"] = f"no result event (exit {proc.returncode}): {stderr[-300:]}"
        else:
            rec["stop_reason"] = result_ev.get("stop_reason")
            rec["turns"] = result_ev.get("turns")
            rec["cost_usd"] = (result_ev.get("usage") or {}).get("cost_usd")
            rec["final_text"] = (result_ev.get("final_text") or "")[:2500]
    finally:
        out_f.close()
        err_f.close()
        os.unlink(out_f.name)
        os.unlink(err_f.name)
    # THE judge: verify.py, not the agent's self-report.
    ver = subprocess.run(
        [sys.executable, "verify.py"], cwd=wd, capture_output=True, text=True, timeout=60
    )
    rec["ok"] = ver.returncode == 0 and "VERIFY OK" in ver.stdout
    rec["verify_out"] = (ver.stdout + ver.stderr)[-400:]
    # keep a failure excerpt for the proposer, then free the workdir
    if not rec["ok"] and not rec["error"]:
        rec["fail_excerpt"] = rec["verify_out"]
    shutil.rmtree(wd, ignore_errors=True)
    shutil.rmtree(home, ignore_errors=True)
    with _lock:
        if rec["cost_usd"]:
            _add_spend(float(rec["cost_usd"]), f"run {tag}")
    return rec


def load_progress() -> list[dict]:
    if PROGRESS.exists():
        return json.loads(PROGRESS.read_text())
    return []


def save_run(rec: dict) -> None:
    with _lock:
        prog = load_progress()
        prog.append(rec)
        PROGRESS.write_text(json.dumps(prog, indent=1))
    line = (
        f"{rec['tag']} model={rec['model']} ok={rec['ok']} turns={rec['turns']} "
        f"cost={rec['cost_usd']} stop={rec['stop_reason']} dur={rec['dur_s']}s "
        f"err={rec['error']}\n"
    )
    with LOG.open("a") as f:
        f.write(line)
    print(line.strip(), flush=True)


# ---------------------------------------------------------------- propose

PROPOSE_SYSTEM = (
    "Eres un optimizador de skills para un agente de terminal. Un agente falló "
    "una tarea porque no priorizó bien las reglas de un SPEC. Recibirás: el "
    "prompt de la tarea, el SPEC completo, la implementación rota y transcripciones "
    "de fallos. Escribe UNA SKILL.md (YAML frontmatter con name+description, cuerpo "
    "markdown) que, si el agente la consulta ANTES de codificar, maximiza el éxito. "
    "El cuerpo debe ser denso, accionable, <=250 palabras, en español o inglés. "
    "Responde SOLO con el contenido del archivo, sin cercas de código."
)


def propose_skill(variant: int, failures: list[dict], spec_text: str) -> str | None:
    body = {
        "model": MODELS["flash"],
        "messages": [
            {"role": "system", "content": PROPOSE_SYSTEM},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "variante": variant,
                        "consigna": (
                            "variante A: checklist por regla condición→fuente→código→prioridad"
                            if variant == 1
                            else "variante B: énfasis en leer el SPEC COMPLETO y verificar contra "
                            "los casos de verify.py antes de declarar éxito"
                        ),
                        "prompt_tarea": PROMPT,
                        "spec": spec_text,
                        "codigo_roto": (FIXTURE / "validador.py").read_text(),
                        "fallos": [
                            {
                                "final_text": f["final_text"][:600],
                                "verify": f.get("verify_out", "")[:400],
                                "stop": f["stop_reason"],
                            }
                            for f in failures[:6]
                        ],
                    },
                    ensure_ascii=False,
                ),
            },
        ],
        "max_tokens": 3000,  # el flash es reasoning: 1200 se iba TODO en pensar (content=None)
        "temperature": 0.7,
    }
    req = urlrequest.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {_api_key()}", "Content-Type": "application/json"},
    )
    try:
        with urlrequest.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
        choice = data["choices"][0]
        txt = (choice["message"].get("content") or "").strip()
        if not txt:
            print(
                f"propose mut{variant}: content vacío (finish={choice.get('finish_reason')})",
                flush=True,
            )
            return None
        if txt.startswith("```"):
            txt = txt.split("\n", 1)[1].rsplit("```", 1)[0]
        usage = data.get("usage") or {}
        cost = (usage.get("prompt_tokens", 0) * 1.5e-7) + (
            usage.get("completion_tokens", 0) * 4.7e-7
        )
        _add_spend(cost, f"propose mut{variant}")
        if "name:" not in txt[:120] or len(txt) < 300:
            # content=None (reasoning sin respuesta) o truncado por max_tokens: reintentar
            print(f"propose mut{variant}: propuesta inválida ({len(txt)} chars)", flush=True)
            return None
        return txt
    except (urlerror.URLError, KeyError, json.JSONDecodeError) as e:
        print(f"propose variant {variant} failed: {e}", flush=True)
        return None


# ---------------------------------------------------------------- stats


def fisher_p_better(a_ok: int, a_n: int, b_ok: int, b_n: int) -> float:
    """One-sided Fisher: P(arm B at least this much better than arm A)."""
    na, nb = a_n, b_n
    tot_ok = a_ok + b_ok
    n = na + nb
    lo = max(0, tot_ok - nb)

    def pmf(k: int) -> float:
        return math.comb(na, k) * math.comb(nb, tot_ok - k) / math.comb(n, tot_ok)

    return sum(pmf(k) for k in range(lo, a_ok + 1))


def rate(prog: list[dict], arm: str, mkey: str) -> tuple[int, int]:
    # OJO: r["model"] guarda el nombre COMPLETO ("qwen/qwen3.8-flash"), no la clave.
    rs = [r for r in prog if r["arm"] == arm and r["model"] == MODELS[mkey]]
    return sum(1 for r in rs if r["ok"]), len(rs)


# ---------------------------------------------------------------- phases


def phase_collect() -> list[dict]:
    prog = load_progress()
    failures = [r for r in prog if r["tag"].startswith("seed") and not r["ok"]]
    done = {r["tag"] for r in prog if r["tag"].startswith("seed")}
    jobs = [
        (mkey, i) for mkey, n in SEED_N.items() for i in range(n) if f"seed-{mkey}-{i}" not in done
    ]
    print(f"collect: {len(jobs)} new seed runs", flush=True)

    def job(mk_i):
        mkey, i = mk_i
        rec = run_once(MODELS[mkey], None, f"seed-{mkey}-{i}")
        rec["arm"] = "v0"
        save_run(rec)
        return rec

    with ThreadPoolExecutor(CONCURRENCY) as ex:
        list(ex.map(job, jobs))
    prog = load_progress()
    failures = [r for r in prog if r["tag"].startswith("seed") and not r["ok"]]
    if len(failures) < 2:  # baseline too strong this round — more seeds for material
        extra = [r for r in prog if r["tag"].startswith("seed") and not r["ok"]]
        n_seeds = len([r for r in prog if r["tag"].startswith("seed")])
        print(
            f"WARNING: only {len(failures)} failures in {n_seeds} seeds; "
            f"proposing from {len(extra)} transcripts anyway",
            flush=True,
        )
    return failures


def phase_propose(failures: list[dict]) -> None:
    spec_text = (FIXTURE / "SPEC.md").read_text()
    for variant, path in ((1, PROPOSALS[0]), (2, PROPOSALS[1])):
        if path.exists():
            print(f"mut{variant}: proposal exists, reusing", flush=True)
            continue
        txt = None
        for attempt in (1, 2, 3):
            txt = propose_skill(variant, failures, spec_text)
            if txt:
                break
            print(f"mut{variant}: intento {attempt} sin propuesta, reintentando", flush=True)
        if txt:
            path.write_text(txt, encoding="utf-8")
            print(f"mut{variant}: proposed ({len(txt)} chars)", flush=True)
        else:
            raise SystemExit(f"proposer failed for mut{variant} — no transcript-only fallback")


def phase_bench() -> None:
    prog = load_progress()
    skills = {1: PROPOSALS[0].read_text(), 2: PROPOSALS[1].read_text()}
    jobs = []
    for mkey, n in BENCH_N.items():
        for arm in ("v0", "mut1", "mut2"):
            done = sum(
                1
                for r in prog
                if r["arm"] == arm and r["model"] == mkey and not r["tag"].startswith("seed")
            )
            # seed runs already count toward v0 for this model
            if arm == "v0":
                done += sum(1 for r in prog if r["tag"].startswith(f"seed-{mkey}-"))
            for i in range(done, n):
                jobs.append((mkey, arm, i))
    print(
        f"bench: {len(jobs)} runs pending (cap ${HARD_CAP_USD}, spent ${_spend():.3f})",
        flush=True,
    )

    def job(ma_i):
        mkey, arm, i = ma_i
        if _spend() > HARD_CAP_USD:
            print(f"ABORT {arm}-{mkey}-{i}: over cap", flush=True)
            return
        skill = None if arm == "v0" else skills[int(arm[-1])]
        rec = run_once(MODELS[mkey], skill, f"bench-{arm}-{mkey}-{i}")
        rec["arm"] = arm
        save_run(rec)

    with ThreadPoolExecutor(CONCURRENCY) as ex:
        list(ex.map(job, jobs))


def phase_report() -> dict:
    prog = load_progress()
    out: dict = {"generated": time.strftime("%Y-%m-%d %H:%M"), "spend_usd": _spend(), "arms": {}}
    for mkey in MODELS:
        out["arms"][mkey] = {}
        for arm in ("v0", "mut1", "mut2"):
            ok, n = rate(prog, arm, mkey)
            turns = [
                r["turns"]
                for r in prog
                if r["arm"] in (arm, "v0")
                and r["model"] == MODELS[mkey]
                and r["turns"] is not None
                and (r["arm"] == arm or not r["tag"].startswith("seed"))
            ]
            out["arms"][mkey][arm] = {
                "ok": ok,
                "n": n,
                "rate": round(ok / n, 3) if n else None,
                "mean_turns": round(sum(turns) / len(turns), 1) if turns else None,
            }
    out["fisher"] = {}
    for arm in ("mut1", "mut2"):
        per_model = {}
        pool = [0, 0, 0, 0]  # v0ok v0n armok armn
        for mkey in MODELS:
            a_ok, a_n = rate(prog, "v0", mkey)
            b_ok, b_n = rate(prog, arm, mkey)
            per_model[mkey] = {
                "p": round(fisher_p_better(a_ok, a_n, b_ok, b_n), 4),
                "v0": f"{a_ok}/{a_n}",
                "arm": f"{b_ok}/{b_n}",
            }
            pool = [pool[0] + a_ok, pool[1] + a_n, pool[2] + b_ok, pool[3] + b_n]
        out["fisher"][arm] = {
            **per_model,
            "pooled": {
                "p": round(fisher_p_better(*pool), 4),
                "v0": f"{pool[0]}/{pool[1]}",
                "arm": f"{pool[2]}/{pool[3]}",
            },
        }
    gate = {}
    for arm in ("mut1", "mut2"):
        p = out["fisher"][arm]["pooled"]["p"]
        gate[arm] = "KEEP" if p < 0.05 and _arm_better(out, arm) else "DROP"
    out["gate"] = gate
    RESULTS.write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1), flush=True)
    return out


def _arm_better(out: dict, arm: str) -> bool:
    return all(
        (out["arms"][m][arm]["rate"] or 0) >= (out["arms"][m]["v0"]["rate"] or 0)
        for m in MODELS
        if out["arms"][m][arm]["n"]
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--phase", default="all", choices=["collect", "propose", "bench", "report", "all"]
    )
    args = ap.parse_args()
    LOG.parent.mkdir(exist_ok=True)
    Path("/tmp/skillopt-v2").mkdir(exist_ok=True)
    if args.phase in ("collect", "all"):
        failures = phase_collect()
        if args.phase == "all":
            phase_propose(failures)
            phase_bench()
    if args.phase == "propose":
        phase_propose([r for r in load_progress() if r["tag"].startswith("seed") and not r["ok"]])
    if args.phase == "bench":
        phase_bench()
    if args.phase in ("report", "all"):
        phase_report()
    print(f"DONE spend=${_spend():.4f}", flush=True)


if __name__ == "__main__":
    main()
