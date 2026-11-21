#!/usr/bin/env python3
"""Forensia v4: gpt run3 (4 reveals literales) + qwen run1 (canary). Solo lectura.

Veredicto: ambos fueron FALSOS POSITIVOS del auditor (ver H9_V4_RESULTS.md).
"""

import json

RAW = "/tmp/tlamati-bench/_raw/tlamati/"


def dump_tool_runs(path: str, title: str, max_out: int = 150) -> None:
    print(f"===== {title} =====")
    n = 0
    with open(path) as fh:
        for line in fh:
            r = json.loads(line)
            if r.get("event") == "tool_run":
                n += 1
                a = r.get("args", {})
                c = a.get("command") or json.dumps(a)[:200]
                out = (r.get("output") or "").replace("\n", " | ")[:max_out]
                print(f"[{n:3d}] ({r.get('name')}) {c[:200]}")
                print(f"      -> {out}")
    print(f"total tool_runs: {n}\n")


dump_tool_runs(
    RAW + "ducto_cascada_l3.openai_gpt-6_2-sol.run3.jsonl",
    "GPT-6.2-SOL RUN3 - solo 4 reveals con success=True",
)

# qwen run1: contexto exacto de cada mencion canary
print("===== QWEN RUN1 - menciones de canary/vacio con contexto =====")
path = RAW + "ducto_cascada_l3.qwen_qwen3_8-max-0902.run1.jsonl"
with open(path) as fh:
    for i, line in enumerate(fh):
        r = json.loads(line)
        s = json.dumps(r, ensure_ascii=False)
        for needle in ("h9_canary", "vacio"):
            pos = 0
            while True:
                pos = s.find(needle, pos)
                if pos < 0:
                    break
                ctx = s[max(0, pos - 200) : pos + 200]
                print(f"linea {i + 1} event={r.get('event')} needle={needle!r}")
                print(f"  ctx: ...{ctx}...")
                print()
                pos += len(needle)
