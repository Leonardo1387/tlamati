import json
import sys

sys.path.insert(0, "dev")
from spike_v2 import MODELS, run_once

rec = run_once(MODELS["flash"], None, "smoke")
out = {k: v for k, v in rec.items() if k != "final_text"}
out["final_text_len"] = len(rec.get("final_text", ""))
print(json.dumps(out, indent=1, default=str))
