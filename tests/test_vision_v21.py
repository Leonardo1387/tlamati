"""Vision v2.1 — native image blocks at the waist.

Cubre el camino completo sin red y sin modelos: magic bytes → ImageBlock →
Message/ToolResult → payload de cada adaptador → budget → compaction. Los
binarios de prueba se SINTETIZAN con headers mínimos válidos (nada de
fixtures opacas): png/gif/jpeg/webp con dimensiones conocidas, y un binario
que NO es imagen para el rechazo honesto.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tlamati.context.budget import Budget
from tlamati.context.compaction import CompactionConfig, microcompact, render_for_summary
from tlamati.core.images import (
    FALLBACK_IMAGE_TOKENS,
    MAX_IMAGE_BYTES,
    ImageBlock,
    detect_media_type,
    load_image,
)
from tlamati.core.messages import Message, ToolCall, ToolResult
from tlamati.tools.files import make_file_tools
from tlamati.tools.registry import Registry, Tool, ToolOutput


# ---------------------------------------------------------------- fixtures
def _png(w: int, h: int) -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n"
        + (13).to_bytes(4, "big")
        + b"IHDR"
        + w.to_bytes(4, "big")
        + h.to_bytes(4, "big")
        + b"\x08\x06\x00\x00\x00"
    )


def _gif(w: int, h: int) -> bytes:
    return b"GIF89a" + w.to_bytes(2, "little") + h.to_bytes(2, "little") + b"\x00" * 8


def _jpeg(w: int, h: int) -> bytes:
    sof = (
        b"\xff\xc0"
        + (11).to_bytes(2, "big")
        + b"\x08"
        + h.to_bytes(2, "big")
        + w.to_bytes(2, "big")
        + b"\x03\x01\x11\x00"
    )
    return b"\xff\xd8\xff" + sof + b"\xff\xd9"


def _webp() -> bytes:
    return b"RIFF" + (12).to_bytes(4, "little") + b"WEBP" + b"VP8 " + b"\x00" * 4


@pytest.fixture()
def png_file(tmp_path: Path) -> Path:
    p = tmp_path / "foto.png"
    p.write_bytes(_png(300, 200))
    return p


# ---------------------------------------------------------------- images.py
class TestLoadImage:
    def test_magic_bytes_not_extension(self, tmp_path: Path) -> None:
        p = tmp_path / "mentira.txt"  # extensión textual, alma de png
        p.write_bytes(_png(10, 20))
        block = load_image(p)
        assert block.media_type == "image/png"
        assert (block.width, block.height) == (10, 20)

    @pytest.mark.parametrize(
        ("raw", "media"),
        [(_png(1, 1), "image/png"), (_gif(2, 3), "image/gif"), (_jpeg(4, 5), "image/jpeg")],
    )
    def test_formats_and_dims(self, tmp_path: Path, raw: bytes, media: str) -> None:
        p = tmp_path / "x"
        p.write_bytes(raw)
        block = load_image(p)
        assert block.media_type == media

    def test_jpeg_dims_from_sof(self, tmp_path: Path) -> None:
        p = tmp_path / "x.jpg"
        p.write_bytes(_jpeg(640, 480))
        block = load_image(p)
        assert (block.width, block.height) == (640, 480)

    def test_webp_dims_honest_none(self, tmp_path: Path) -> None:
        p = tmp_path / "x.webp"
        p.write_bytes(_webp())
        block = load_image(p)
        assert block.media_type == "image/webp"
        assert block.width is None
        assert block.token_estimate() == FALLBACK_IMAGE_TOKENS

    def test_non_image_rejected_with_magic(self, tmp_path: Path) -> None:
        p = tmp_path / "bin.dat"
        p.write_bytes(b"\x00\x01\x02\x03NO-IMG")
        with pytest.raises(ValueError, match="magic bytes"):
            load_image(p)

    def test_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="no such file"):
            load_image(tmp_path / "nope.png")

    def test_over_cap_rejected_whole(self, tmp_path: Path, monkeypatch: Any) -> None:
        import tlamati.core.images as imgs

        monkeypatch.setattr(imgs, "MAX_IMAGE_BYTES", 16)
        p = tmp_path / "gorda.png"
        p.write_bytes(_png(1, 1) + b"\x00" * 64)
        with pytest.raises(ValueError, match="tope"):
            load_image(p)
        assert MAX_IMAGE_BYTES > 0  # el real sigue sano

    def test_token_estimate_formula(self) -> None:
        block = ImageBlock(data="", media_type="image/png", width=1500, height=1500)
        assert block.token_estimate() == 3000  # 1500*1500/750

    def test_detect_media_type_none(self) -> None:
        assert detect_media_type(b"plain text") is None


# ---------------------------------------------------------------- waist
class TestMessageWaist:
    def test_only_user_and_tool_carry_images(self, png_file: Path) -> None:
        im = load_image(png_file)
        Message(role="user", content="mira", images=(im,))
        tr = ToolResult(tool_call_id="t", content="m", images=(im,))
        Message(role="tool", content="", tool_result=tr)
        with pytest.raises(ValueError, match="only user"):
            Message(role="assistant", content="x", images=(im,))
        with pytest.raises(ValueError, match="only user"):
            Message(role="system", content="x", images=(im,))

    def test_persistence_is_metadata_not_pixels(self, png_file: Path) -> None:
        im = load_image(png_file)
        d = Message(role="user", content="mira", images=(im,)).as_dict()
        blob = json.dumps(d)
        assert im.data not in blob  # cero base64 en la sesión
        assert d["images"][0]["source_path"] == str(png_file)

    def test_roundtrip_reloads_live_pixels(self, png_file: Path) -> None:
        im = load_image(png_file)
        m2 = Message.from_dict(Message(role="user", content="mira", images=(im,)).as_dict())
        assert len(m2.images) == 1
        assert m2.images[0].data == im.data

    def test_roundtrip_drops_dead_file(self, png_file: Path) -> None:
        im = load_image(png_file)
        d = Message(role="user", content="mira", images=(im,)).as_dict()
        png_file.unlink()
        m2 = Message.from_dict(d)
        assert m2.images == ()  # y el marker de texto queda como registro


# ---------------------------------------------------------------- registry + tools
class TestRegistryVision:
    @pytest.mark.asyncio()
    async def test_tool_output_carries_images(self, png_file: Path) -> None:
        im = load_image(png_file)

        async def run(args: dict[str, Any]) -> ToolOutput:
            return ToolOutput(content=im.marker(), images=(im,))

        reg = Registry(
            [Tool(name="viso", description="d", input_schema={"type": "object"}, run=run)]
        )
        result = await reg.execute("viso", {}, "call1")
        assert result.images == (im,)
        assert not result.is_error

    @pytest.mark.asyncio()
    async def test_error_strips_images(self, png_file: Path) -> None:
        im = load_image(png_file)

        async def run(args: dict[str, Any]) -> ToolOutput:
            return ToolOutput(content="ERROR: no pude", images=(im,))

        tool = Tool(name="viso", description="d", input_schema={"type": "object"}, run=run)
        reg = Registry([tool])
        result = await reg.execute("viso", {}, "call1")
        assert result.is_error
        assert result.images == ()

    @pytest.mark.asyncio()
    async def test_read_file_returns_native_block(self, png_file: Path) -> None:
        tool = next(t for t in make_file_tools(png_file.parent) if t.name == "read_file")
        out = await tool.run({"path": png_file.name})
        assert isinstance(out, ToolOutput)
        assert out.images and out.images[0].media_type == "image/png"
        assert "300x200" in out.content  # marker honesto

    @pytest.mark.asyncio()
    async def test_read_file_text_unchanged(self, tmp_path: Path) -> None:
        (tmp_path / "a.txt").write_text("hola\n")
        tool = next(t for t in make_file_tools(tmp_path) if t.name == "read_file")
        out = await tool.run({"path": "a.txt"})
        assert isinstance(out, str)
        assert "hola" in out


# ---------------------------------------------------------------- adapters
class TestAdapters:
    def _im(self, png_file: Path) -> ImageBlock:
        return load_image(png_file)

    def test_anthropic_user_and_tool_result(self, png_file: Path) -> None:
        from tlamati.providers.anthropic_messages import AnthropicMessages

        im = self._im(png_file)
        prov = AnthropicMessages(model="claude-x")
        user = Message(role="user", content="mira", images=(im,))
        call = ToolCall(id="c1", name="read_file", arguments={}, raw_arguments="{}")
        assistant = Message(role="assistant", content="veo", tool_calls=(call,))
        tool_msg = Message(
            role="tool",
            content="",
            tool_result=ToolResult(tool_call_id="c1", content="marker", images=(im,)),
        )
        hist = prov._build_history([user, assistant, tool_msg])
        u_blocks = hist[0]["content"]
        assert u_blocks[1]["type"] == "image"
        assert u_blocks[1]["source"]["type"] == "base64"
        assert u_blocks[1]["source"]["data"] == im.data
        tr_block = hist[2]["content"][0]
        assert tr_block["type"] == "tool_result"
        inner = tr_block["content"]
        assert isinstance(inner, list)
        assert inner[0] == {"type": "text", "text": "marker"}
        assert inner[1]["type"] == "image"

    def test_anthropic_merge_keeps_images(self, png_file: Path) -> None:
        """Consecutive user roles merge (donor rule); pixels must survive.

        Shape real: assistant(tool_use) → tool(result con imagen) → user(con
        imagen). El tool_result se emite como role user, así que el siguiente
        user message se MERGEA con él: los bloques de imagen de ambos lados
        deben quedar en el mensaje fusionado.
        """
        from tlamati.providers.anthropic_messages import AnthropicMessages

        im = self._im(png_file)
        prov = AnthropicMessages(model="claude-x")
        call = ToolCall(id="c1", name="read_file", arguments={}, raw_arguments="{}")
        assistant = Message(role="assistant", content="veo", tool_calls=(call,))
        tool_msg = Message(
            role="tool",
            content="",
            tool_result=ToolResult(tool_call_id="c1", content="marker", images=(im,)),
        )
        user2 = Message(role="user", content="y ahora esta", images=(im,))
        hist = prov._build_history([assistant, tool_msg, user2])
        assert len(hist) == 2  # assistant + un solo user fusionado
        types = [b.get("type") for b in hist[1]["content"]]
        assert types == ["tool_result", "text", "image"]

    def test_openai_data_urls_and_cache_breakpoint(self, png_file: Path) -> None:
        from tlamati.providers.openai_compat import OpenAICompat

        im = self._im(png_file)
        prov = OpenAICompat(model="anthropic/claude-x")  # fuerza markers de cache
        user = Message(role="user", content="mira", images=(im,))
        tool_msg = Message(
            role="tool",
            content="",
            tool_result=ToolResult(tool_call_id="c1", content="marker", images=(im,)),
        )
        converted = [prov._convert_message(user), prov._convert_message(tool_msg)]
        u_content = converted[0]["content"]
        assert u_content[0]["type"] == "text"
        assert u_content[1]["image_url"]["url"].startswith("data:image/png;base64,")
        prov._mark_anthropic_cache(converted)
        t_content = converted[1]["content"]
        assert isinstance(t_content, list)
        assert t_content[-1].get("cache_control") == {"type": "ephemeral"}
        # el texto del tool result sigue ahí (marker honesto)
        assert t_content[0]["text"] == "marker"


# ---------------------------------------------------------------- budget + compaction
class TestBudgetAndCompaction:
    def test_budget_counts_pixels(self, png_file: Path) -> None:
        im = load_image(png_file)
        plain = Message(role="user", content="mira")
        with_img = Message(role="user", content="mira", images=(im,))
        from tlamati.context.budget import _message_tokens

        assert _message_tokens(with_img) - _message_tokens(plain) == im.token_estimate()

    def test_microcompact_clears_pixels_too(self, png_file: Path) -> None:
        im = load_image(png_file)
        cfg = CompactionConfig(retain_first=0, retain_recent=0)
        call = ToolCall(
            id="c1", name="read_file", arguments={"path": "foto.png"}, raw_arguments="{}"
        )
        assistant = Message(role="assistant", content="voy", tool_calls=(call,))
        tool_msg = Message(
            role="tool",
            content="",
            tool_result=ToolResult(tool_call_id="c1", content=im.marker(), images=(im,)),
        )
        history = [assistant, tool_msg]
        out, cleared = microcompact(history, cfg)
        assert cleared == 1
        assert out[1].tool_result is not None
        assert out[1].tool_result.images == ()  # píxeles evictados, no a medias
        assert out[1].tool_result.microcompacted is True

    def test_summary_transcript_keeps_markers(self, png_file: Path) -> None:
        im = load_image(png_file)
        text = render_for_summary([Message(role="user", content="mira", images=(im,))])
        assert "image" in text and "300x200" in text


def test_budget_class_still_constructs() -> None:
    b = Budget(max_context_tokens=1000)
    assert b.max_context_tokens == 1000
