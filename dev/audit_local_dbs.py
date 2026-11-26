"""One-off audit: what the local runtime DBs show about dream/compaction/skills."""

import sqlite3

BASE = "/home/usuario/.local/share/tlamati"


def dump(path: str) -> None:
    print(f"===== {path} =====")
    try:
        db = sqlite3.connect(path)
    except sqlite3.Error as e:
        print(f"  cannot open: {e}")
        return
    try:
        tabs = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        print("  tables:", tabs)
        for t in tabs:
            n = db.execute(f"SELECT COUNT(*) FROM [{t}]").fetchone()[0]
            cols = [c[1] for c in db.execute(f"PRAGMA table_info([{t}])")]
            print(f"  {t}: {n} rows, cols={cols}")
            if n and n <= 2_000_000:
                pass
    except sqlite3.Error as e:
        print(f"  error: {e}")
    finally:
        db.close()


def q(path: str, sql: str, label: str) -> None:
    try:
        db = sqlite3.connect(path)
        rows = db.execute(sql).fetchall()
        db.close()
        print(f"-- {label}: {rows[:40]}")
    except sqlite3.Error as e:
        print(f"-- {label}: ERR {e}")


audit = f"{BASE}/audit.db"
sess = f"{BASE}/sessions.db"

dump(audit)
dump(sess)

# guess common schemas then aggregate
for path in (audit, sess):
    try:
        db = sqlite3.connect(path)
        tabs = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        for t in tabs:
            cols = [c[1] for c in db.execute(f"PRAGMA table_info([{t}])")]
            ev_col = next((c for c in cols if c in ("event", "kind", "type", "name")), None)
            ts_col = next((c for c in cols if c in ("ts", "created_at", "at", "time")), None)
            if ev_col:
                print(f"-- {path.split('/')[-1]}.{t} by {ev_col}:")
                for ev, n in db.execute(
                    f"SELECT {ev_col}, COUNT(*) FROM [{t}]"
                    f" GROUP BY {ev_col} ORDER BY 2 DESC LIMIT 15"
                ):
                    print(f"     {ev}: {n}")
            if ts_col:
                rng = db.execute(f"SELECT MIN({ts_col}), MAX({ts_col}) FROM [{t}]").fetchone()
                print(f"-- {t} time range ({ts_col}): {rng}")
        db.close()
    except sqlite3.Error as e:
        print(f"ERR {path}: {e}")

# sessions: count + which had dream/compaction markers in payload
try:
    db = sqlite3.connect(sess)
    tabs = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    for t in tabs:
        cols = [c[1] for c in db.execute(f"PRAGMA table_info([{t}])")]
        for c in cols:
            try:
                dreams = db.execute(
                    f"SELECT COUNT(*) FROM [{t}] WHERE [{c}] LIKE '%dream%'"
                ).fetchone()[0]
                comp = db.execute(
                    f"SELECT COUNT(*) FROM [{t}] WHERE [{c}] LIKE '%compact%'"
                ).fetchone()[0]
                if dreams or comp:
                    print(f"-- {t}.{c}: rows mentioning dream={dreams} compact={comp}")
            except sqlite3.Error:
                pass
    db.close()
except sqlite3.Error as e:
    print("ERR sessions scan:", e)
