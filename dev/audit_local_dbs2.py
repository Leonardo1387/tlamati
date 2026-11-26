"""Audit pass 2: runtime evidence for self-improvement loops (dream/compaction) + spend."""

import sqlite3
from datetime import UTC, datetime

BASE = "/home/usuario/.local/share/tlamati"


def d(ts: float) -> str:
    return datetime.fromtimestamp(ts, UTC).astimezone().strftime("%d-%b %H:%M")


sb = sqlite3.connect(f"{BASE}/sessions.db")
ab = sqlite3.connect(f"{BASE}/audit.db")

print("== SESSIONS ==")
rows = sb.execute(
    "SELECT id, created_at, last_active, model, first_prompt, stop_reason, turns"
    " FROM sessions ORDER BY created_at"
).fetchall()
print(f"total sessions: {len(rows)}")
by_day: dict[str, int] = {}
for r in rows:
    by_day.setdefault(datetime.fromtimestamp(r[1]).strftime("%d-%b"), 0)
    by_day[datetime.fromtimestamp(r[1]).strftime("%d-%b")] += 1
print("sessions per day:", by_day)
print("stop_reason histogram:")
h: dict[str, int] = {}
for r in rows:
    h[r[5] or "?"] = h.get(r[5] or "?", 0) + 1
print("  ", h)
print("last 6 sessions:")
for r in rows[-6:]:
    print(
        f"  {d(r[1])} turns={r[6]} model={(r[3] or '?')[:28]} stop={r[5]} :: {(r[4] or '')[:60]!r}"
    )

print("\n== DREAM evidence (messages mentioning dream) ==")
for sid, seq, role in sb.execute(
    "SELECT session_id, seq, role FROM messages WHERE body_json LIKE '%dream%'"
    " ORDER BY session_id, seq"
):
    print(f"  session={sid[:16]} seq={seq} role={role}")

print("\n== COMPACTION evidence ==")
n_cleared = sb.execute("SELECT COUNT(*) FROM messages WHERE content_cleared=1").fetchone()[0]
n_sum = sb.execute(
    "SELECT COUNT(*) FROM messages WHERE body_json LIKE '%CONTEXTO COMPACTADO%'"
).fetchone()[0]
n_emerg = sb.execute(
    "SELECT COUNT(*) FROM messages WHERE body_json LIKE '%EMERGENCIA%'"
).fetchone()[0]
print(
    f"  content_cleared msgs: {n_cleared}; summarized-marker: {n_sum}; emergency drops: {n_emerg}"
)
print(f"  summaries table rows: {sb.execute('SELECT COUNT(*) FROM summaries').fetchone()[0]}")
per_sess = sb.execute(
    "SELECT session_id, COUNT(*) FROM messages"
    " WHERE body_json LIKE '%CONTEXTO COMPACTADO%'"
    " GROUP BY session_id ORDER BY 2 DESC LIMIT 8"
).fetchall()
print("  top sessions by summary markers:", per_sess)

print("\n== SPEND / CACHE ==")
tot = ab.execute(
    "SELECT COUNT(DISTINCT session_id), SUM(cost_usd), SUM(input_tokens),"
    " SUM(cache_read) FROM turn_costs"
).fetchone()
print(
    f"  sessions with cost rows: {tot[0]}; total spend ${tot[1]:.4f};"
    f" in_tok={tot[2]:,}; cache_read={tot[3]:,}"
)
if tot[2]:
    print(f"  cache hit ratio: {100 * tot[3] / (tot[2] + tot[3]):.1f}%")
top = ab.execute(
    "SELECT session_id, SUM(cost_usd), COUNT(*) FROM turn_costs"
    " GROUP BY session_id ORDER BY 2 DESC LIMIT 6"
).fetchall()
print("  priciest sessions:")
for s, c, t in top:
    print(f"    {s[:16]} ${c:.4f} turns={t}")

print("\n== TOOL DECISIONS (permissions) ==")
h2: dict[str, int] = {}
for dec, n in ab.execute("SELECT decision, COUNT(*) FROM tool_events GROUP BY decision"):
    h2[dec] = n
print("  ", h2)
errs = ab.execute("SELECT COUNT(*) FROM tool_events WHERE is_error=1").fetchone()[0]
print(f"  tool errors: {errs} / 5443 ({100 * errs / 5443:.1f}%)")
