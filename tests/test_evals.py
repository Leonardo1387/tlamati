"""Tests for evals/runner.py (A7) — descubrimiento de tareas, verificación y
JSONL, con FakeProvider: cero red. Las fixtures reales del repo son el input."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Sequence
from pathlib import Path

import pytest

from tlamati.core.messages import (
    Event,
    Message,
    MessageEnd,
    TextDelta,
    ToolCallArgsDelta,
    ToolCallStart,
    Usage,
)
from tlamati.evals.runner import DEFAULT_FIXTURES, TaskResult, _verify, discover_tasks, run_task
from tlamati.providers.base import ToolSpec

FIXTURE_NAMES = {
    "promedio",
    "offbyone",
    "conversor",
    "import_roto",
    "crear_modulo",
    # E3a: media-alta (moldeadas en bugs reales del historial del proyecto)
    "multi_archivo",  # bug repartido: normalización de claves + .get con default
    "output_grande",  # aguja FATAL al final de un log de 3000 líneas (truncado M1)
    "git_history",  # arqueología git: setup.sh siembra 6 commits deterministas
    "instruccion_en_archivo",  # SPEC.md con reglas R1-R6 + prioridad (lee docs largos)
    "test_driven",  # 10 tests unittest, 4 fallan (itera edit→test→edit)
    # E3c: robustez del arnés (propuestas del fundador, 19-nov)
    "anti_bucle_imposible",  # tarea imposible: debe abortar limpio, no quemar turnos
    "context_rot_20_archivos",  # 20 archivos ruido + 3 reales interdependientes
    "recuperacion_test_roto",  # suite rota por env-var: autocorrección tras traceback
    "edicion_quirurgica_grande",  # 600 líneas, 2 funciones: patch vs sobrescritura
    "rollback_o_regresion",  # 5 tests pasan + 1 falla: arreglar sin regresión
    # H9: horizonte largo (curva de saturación, anti-batch por defectos divergentes)
    "cadena_defectos_l1",  # 15 módulos encadenados, un defecto distinto por módulo
    "ducto_reglas_l2",  # 30 etapas con dependencias; contrato solo en docs/REGLAS.md
    # H9 v3: cascada ciega (fallos runtime secuenciales + docs únicos por módulo)
    "ducto_cascada_l3",  # 34 módulos, guardavas que excepcionan en cascada, 150 turnos
    # T1: anti-bucle cuasi-repetitivo (error mutante; éxito = diagnosticar, no reintentar)
    "bucle_error_mutante",
}


class FixProvider:
    """Scripted provider: emite los tool calls que arreglan la tarea dada."""

    model = "fix-fake"

    def __init__(self, script: list[tuple[str, str, dict]]) -> None:
        self.script = script
        self.done = False

    async def stream(
        self, messages: Sequence[Message], tools: Sequence[ToolSpec] = ()
    ) -> AsyncIterator[Event]:
        if self.done or not self.script:
            yield TextDelta(text="TERMINADO")
            yield MessageEnd(stop_reason="end_turn", usage=Usage(input_tokens=10, output_tokens=5))
            return
        self.done = True
        for tid, name, args in self.script:
            yield ToolCallStart(id=tid, name=name)
            yield ToolCallArgsDelta(id=tid, args_json=json.dumps(args))
        yield MessageEnd(stop_reason="tool_use", usage=Usage(input_tokens=10, output_tokens=5))


def test_discover_tasks_finds_all_fixtures() -> None:
    tasks = discover_tasks(DEFAULT_FIXTURES)
    assert {t.name for t in tasks} == FIXTURE_NAMES


def test_git_history_setup_sh_seed_and_solve(tmp_path: Path) -> None:
    """git_history: setup.sh siembra 6 commits deterministas; verify FALLA sin
    culpable.txt y PASA con el hash del commit 'refactor' (simula la solución)."""
    import shutil
    import subprocess

    src = next(t for t in discover_tasks(DEFAULT_FIXTURES) if t.name == "git_history")
    ws = tmp_path / "git_history"
    shutil.copytree(src, ws)
    subprocess.run(["bash", "setup.sh"], cwd=ws, check=True, capture_output=True)
    # idempotente: segunda corrida no revienta ni duplica
    subprocess.run(["bash", "setup.sh"], cwd=ws, check=True, capture_output=True)

    ok, out = _verify(ws)
    assert not ok and "culpable.txt" in out  # semilla FALLA (invariante)

    log = subprocess.run(
        ["git", "log", "--format=%H %s"], cwd=ws, capture_output=True, text=True, check=True
    )
    lines = log.stdout.strip().splitlines()
    assert len(lines) == 6
    culpable = next(ln.split()[0] for ln in lines if "refactor" in ln)
    (ws / "culpable.txt").write_text(culpable + "\n")
    ok, out = _verify(ws)
    assert ok and "VERIFY OK" in out
    # fechas deterministas: misma semilla → mismos hashes en otro workspace
    ws2 = tmp_path / "clone"
    shutil.copytree(src, ws2)
    subprocess.run(["bash", "setup.sh"], cwd=ws2, check=True, capture_output=True)
    log2 = subprocess.run(["git", "log", "--format=%H"], cwd=ws2, capture_output=True, text=True)
    assert log2.stdout.strip().splitlines()[0] == culpable


def test_multi_archivo_verifier_expects_config_tax(tmp_path: Path) -> None:
    """multi_archivo: la semilla usa default 0.16 y verify exige 0.19 de config."""
    src = next(t for t in discover_tasks(DEFAULT_FIXTURES) if t.name == "multi_archivo")
    ok, out = _verify(src)
    assert not ok and "impuesto" in out  # invariante: FALLA pre-fix con mensaje claro


def test_test_driven_seed_has_four_failures() -> None:
    """test_driven: los 10 tests corren y exactamente 4 fallan pre-fix."""
    import subprocess
    import sys

    src = next(t for t in discover_tasks(DEFAULT_FIXTURES) if t.name == "test_driven")
    proc = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", "."],
        cwd=src,
        capture_output=True,
        text=True,
        timeout=60,
    )
    tail = proc.stdout + proc.stderr
    assert proc.returncode != 0 and "FAILED (failures=4)" in tail


def test_rollback_seed_exactly_one_failure() -> None:
    """rollback_o_regresion: 6 tests corren y EXACTAMENTE 1 falla pre-fix
    (los otros 5 ya pasan — eso es lo que protege contra regresiones)."""
    import subprocess
    import sys

    src = next(t for t in discover_tasks(DEFAULT_FIXTURES) if t.name == "rollback_o_regresion")
    proc = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", "."],
        cwd=src,
        capture_output=True,
        text=True,
        timeout=60,
    )
    tail = proc.stdout + proc.stderr
    assert "Ran 6 tests" in tail
    assert proc.returncode != 0 and "FAILED (failures=1)" in tail


def test_recuperacion_seed_fails_without_env(tmp_path: Path) -> None:
    """recuperacion_test_roto: sin APP_REGION la suite truena al importar
    (RuntimeError honesto) — el traceback es la pista que el arnés debe leer."""
    import os
    import subprocess
    import sys

    src = next(t for t in discover_tasks(DEFAULT_FIXTURES) if t.name == "recuperacion_test_roto")
    env = {k: v for k, v in os.environ.items() if k != "APP_REGION"}
    proc = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", "."],
        cwd=src,
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )
    tail = proc.stdout + proc.stderr
    assert proc.returncode != 0 and "APP_REGION" in tail


def test_anti_bucle_config_has_no_key() -> None:
    """anti_bucle_imposible: el binario sembrado NO contiene la clave (la
    tarea es imposible de verdad — inventar cuenta como fallo)."""
    src = next(t for t in discover_tasks(DEFAULT_FIXTURES) if t.name == "anti_bucle_imposible")
    data = (src / "config.dat").read_bytes()
    assert b"TLAMATI-" not in data


def test_context_rot_seed_noise_ratio() -> None:
    """context_rot: los 20 archivos de ruido existen y los 3 reales también
    (la proporción ruido/señal es el punto de la fixture)."""
    src = next(t for t in discover_tasks(DEFAULT_FIXTURES) if t.name == "context_rot_20_archivos")
    ruido = list((src / "logs").glob("*.log")) + list((src / "legacy").glob("*.py"))
    assert len(ruido) == 20
    for real in ("config.yaml", "rules.py", "main.py"):
        assert (src / real).is_file()


def test_edicion_quirurgica_hash_seals_file() -> None:
    """edicion_quirurgica: el verify tiene sellado el hash de todo el archivo
    fuera de las 2 funciones objetivo (cualquier reescritura se detecta)."""
    src = next(t for t in discover_tasks(DEFAULT_FIXTURES) if t.name == "edicion_quirurgica_grande")
    verify_src = (src / "verify.py").read_text()
    assert 'ESPERADO = "' in verify_src
    pedidos = (src / "pedidos.py").read_text()
    assert len(pedidos.splitlines()) >= 550  # archivo grande de verdad
    assert pedidos.count("def ") >= 90  # mucho código que NO debe tocarse


def test_discover_tasks_only_filter(tmp_path: Path) -> None:
    tasks = discover_tasks(DEFAULT_FIXTURES, "promedio")
    assert [t.name for t in tasks] == ["promedio"]
    assert discover_tasks(tmp_path) == []  # dir vacío → sin tareas


def test_seeds_all_fail_before_fix() -> None:
    """Invariante de fixture: cada semilla DEBE fallar sin el fix
    (si una pasa de entrada, la tarea no mide nada)."""
    for task in discover_tasks(DEFAULT_FIXTURES):
        ok, _ = _verify(task)
        assert not ok, f"{task.name} ya pasa sin arreglar — fixture inválida"


@pytest.mark.parametrize(
    ("task_name", "fixed_content"),
    [
        (
            "promedio",
            "def promedio(nums):\n    return sum(nums) / len(nums)\n",
        ),
        (
            "crear_modulo",
            "def suma_lista(nums):\n    return sum(nums)\n",
        ),
    ],
)
async def test_run_task_success_and_failure_paths(
    tmp_path: Path, task_name: str, fixed_content: str
) -> None:
    """Camino verde: el provider 'arregla' vía write_file → success=True.
    Camino rojo: provider que no hace nada → success=False con el output del verify."""
    task_dir = next(t for t in discover_tasks(DEFAULT_FIXTURES) if t.name == task_name)
    target_name = "calc.py" if task_name == "promedio" else "suma_lista.py"

    good = FixProvider([("c1", "write_file", {"path": target_name, "content": fixed_content})])
    r_ok = await run_task(task_dir, tmp_path / "ws", provider=good, max_turns=5, max_context=50_000)
    assert isinstance(r_ok, TaskResult)
    assert r_ok.success is True and r_ok.stop_reason == "end_turn"
    assert r_ok.turns == 2  # write_file + cierre end_turn
    assert r_ok.tokens_in == 20 and r_ok.tokens_out == 10  # Usage aditivo por turno
    assert r_ok.error is None

    lazy = FixProvider([])  # solo dice TERMINADO, no toca nada
    r_bad = await run_task(
        task_dir, tmp_path / "ws", provider=lazy, max_turns=5, max_context=50_000
    )
    assert r_bad.success is False
    assert r_bad.error and "FALLA" in r_bad.error  # output honesto del verifier


def test_task_result_serializes_to_jsonl() -> None:
    from dataclasses import asdict

    line = json.dumps(asdict(TaskResult(task="x", success=True)))
    parsed = json.loads(line)
    assert parsed["task"] == "x" and parsed["success"] is True
    assert "tokens_in" in parsed and "duration_s" in parsed  # schema del baseline
