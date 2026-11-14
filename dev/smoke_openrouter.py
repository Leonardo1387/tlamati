"""Smoke real (no es test unitario): OpenAICompat contra OpenRouter de verdad.

Correr manual: uv run python dev/smoke_openrouter.py
Requiere OPENROUTER_API_KEY en entorno. Gasta <1 centavo.
"""

import asyncio
import os

from tlamati.core.messages import Message, MessageEnd, TextDelta, ToolCallArgsDelta, ToolCallStart
from tlamati.providers.base import ToolSpec
from tlamati.providers.openai_compat import OpenAICompat


async def main() -> None:
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        # fallback: leer de ~/.hermes/.env sin exponer la key en el proceso shell
        env_path = os.path.expanduser("~/.hermes/.env")
        prefix = "OPENROUTER" + "_API_KEY" + "="
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    if line.startswith(prefix):
                        key = line.split("=", 1)[1].strip().strip('"').strip("'")
    if not key:
        raise SystemExit("OPENROUTER_API_KEY no está en el entorno ni en ~/.hermes/.env")
    p = OpenAICompat(
        model="qwen/qwen3-coder",
        base_url="https://openrouter.ai/api/v1",
        api_key=key,
        max_tokens=200,
    )
    tools = [
        ToolSpec(
            name="read_file",
            description="Read a text file",
            input_schema={
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        )
    ]
    msgs = [
        Message(role="system", content="Eres un asistente. Usa herramientas si ayudan."),
        Message(role="user", content="Lee el archivo main.py y dime qué hace. Responde breve."),
    ]
    text = ""
    args = ""
    tool_name = ""
    end = None
    async for ev in p.stream(msgs, tools):
        if isinstance(ev, TextDelta):
            text += ev.text
        elif isinstance(ev, ToolCallStart):
            tool_name = ev.name
        elif isinstance(ev, ToolCallArgsDelta):
            args += ev.args_json
        elif isinstance(ev, MessageEnd):
            end = ev
    print("== TRANSCRIPT REAL OpenRouter ==")
    print("tool llamado:", tool_name or "(ninguno)")
    if args:
        print("args:", args)
    if text:
        print("texto:", text[:200])
    assert end is not None
    print("stop_reason:", end.stop_reason)
    print("usage:", end.usage)
    if end.error:
        print("ERROR:", end.error)


if __name__ == "__main__":
    asyncio.run(main())
