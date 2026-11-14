#!/usr/bin/env python3
"""Analyze a REA cc-analyze JSON evidence bundle: endpoints, storage, workers,
findings families. Usage: python3 analyze_cc.py <cc-analyze-vN.json>"""

import json
import re
import sys
from collections import Counter

path = sys.argv[1] if len(sys.argv) > 1 else "cc-analyze-v3.json"
d = json.load(open(path))
nr = d.get("normalized_result") or {}
print("== evidence_id:", d.get("evidence_id"))
print("== stats:", json.dumps(nr.get("statistics")))


def walk(o):
    if isinstance(o, dict):
        yield o
        for v in o.values():
            yield from walk(v)
    elif isinstance(o, list):
        for i in o:
            yield from walk(i)


nodes = [x for x in walk(nr) if "node_id" in x and "kind" in x]
seen, uniq = set(), []
for n in nodes:
    if n["node_id"] not in seen:
        seen.add(n["node_id"])
        uniq.append(n)

print("== node kinds:", Counter(n["kind"] for n in uniq).most_common())

for kind in ("endpoint", "storage", "worker"):
    ks = [n for n in uniq if n["kind"] == kind]
    print(f"\n== {kind}s ({len(ks)}):")
    for n in ks[:8]:
        ident = n.get("identity") or {}
        attrs = n.get("attributes") or {}
        blob = json.dumps(
            {
                k: v
                for k, v in list(n.items())
                if k in ("identity", "attributes", "url", "name", "location", "target")
            }
        )[:220]
        print("  ", blob)

# find endpoint URL strings anywhere
urls = Counter()
for n in uniq:
    if n["kind"] == "endpoint":
        s = json.dumps(n)
        for m in re.findall(r"https?://[a-zA-Z0-9._:/-]+", s):
            urls[m[:80]] += 1
print("\n== endpoint URL literals:", urls.most_common(15) or "none as literals (dynamic)")

f = [x for x in walk(nr) if x.get("finding_id") or x.get("type") == "finding"]
print("\n== findings objects:", len(f))
for x in f[:4]:
    print("  ", json.dumps(x)[:200])
