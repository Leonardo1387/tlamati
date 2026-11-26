import faulthandler
import sys

faulthandler.dump_traceback_later(20, repeat=True)  # stack cada 20s si se cuelga

sys.path.insert(0, "dev")
print("importando spike_v2...", flush=True)
from spike_v2 import MODELS, run_once  # noqa: E402

print("import OK, lanzando run_once smoke2...", flush=True)
rec = run_once(MODELS["flash"], None, "smoke2")
faulthandler.cancel_dump_traceback_later()
import json  # noqa: E402

out = {k: v for k, v in rec.items() if k != "final_text"}
out["final_text_len"] = len(rec.get("final_text", ""))
print(json.dumps(out, indent=1, default=str), flush=True)
