"""Smoke real de A6: ModelSummarizer contra OpenRouter (modelo barato).

Uso: uv run python dev/smoke_compaction.py
Lee la key de OPENROUTER_API_KEY (env) o ~/.hermes/.env — en Python, nunca por shell.
"""

import asyncio
import os
from pathlib import Path

from tlamati.context.compaction import ModelSummarizer
from tlamati.providers.openai_compat import OpenAICompat


def resolve_key() -> str:
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        env_file = Path.home() / ".hermes" / ".env"
        name = "OPENROUTER" + "_API_KEY="
        if env_file.is_file():
            for line in env_file.read_text().splitlines():
                if line.startswith(name):
                    key = line.split("=", 1)[1].strip().strip('"').strip("'")
    if not key:
        raise SystemExit("sin OPENROUTER_API_KEY")
    return key


async def main() -> None:
    api_key = resolve_key()
    summarizer = ModelSummarizer(
        [
            OpenAICompat(
                model="qwen/qwen3-coder",
                base_url="https://openrouter.ai/api/v1",
                api_key=api_key,
                max_tokens=400,
            )
        ]
    )
    transcript = """[user] arregla el bug de calc.py: el test falla
[assistant]
[calls] read_file({"path": "calc.py"})
[tool_result c1] 1|def promedio(nums):
2|    return sum(nums)/len(nums) - 1
[assistant] El bug es el `- 1` al final.
[calls] write_file({"path": "calc.py", "content": "def promedio(nums):\\n    return sum(nums)/len(nums)\\n"})
[tool_result c2] escrito calc.py
[assistant]
[calls] terminal({"command": "python3 test_calc.py"})
[tool_result c3] TEST OK
"""
    summary, usage = await summarizer.summarize(transcript)
    print("=== RESUMEN ===")
    print(summary)
    print("=== USAGE ===")
    print(f"input={usage.input_tokens} output={usage.output_tokens} "
          f"cache_read={usage.cache_read_tokens}")


if __name__ == "__main__":
    asyncio.run(main())
