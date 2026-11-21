#!/usr/bin/env python3
"""Forensia: gpt x codex run2 outlier (48s/$0.111 vs 116-133s/$0.54-0.58).

Veredicto: legitimo (turn.completed real, 66/66 tests, VERIFY OK, 97% cache).
"""

import glob
import json
import os

RAW = "/tmp/tlamati-bench/_raw/codex/"
cands = sorted(glob.glob(RAW + "ducto_cascada_l3.*.jsonl"))
print("raws codex presentes:", [os.path.basename(c) for c in cands])

for path in cands:
    if "openai_gpt" not in path:
        continue
    print(f"\n===== {os.path.basename(path)} =====")
    with open(path) as fh:
        lines = fh.readlines()
    print(f"lineas: {len(lines)}")
    evs: dict[str, int] = {}
    for line in lines:
        r = json.loads(line)
        evs[r.get("event")] = evs.get(r.get("event"), 0) + 1
    print("eventos:", evs)
    for line in lines[:2]:
        r = json.loads(line)
        print("HEAD:", json.dumps(r, ensure_ascii=False)[:300])
    for line in lines[-2:]:
        r = json.loads(line)
        print("TAIL:", json.dumps(r, ensure_ascii=False)[:300])
