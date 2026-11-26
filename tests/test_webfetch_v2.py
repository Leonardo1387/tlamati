"""v2 — web_fetch tests: httpx.MockTransport, cero red real.

Cubren el contrato completo: éxito textual, HTTP >= 400 honesto, binario
rechazado, truncado en la fuente con marcador, timeout, DNS/conexión,
validación de URL, y los innegociables de policy (ASK + produces_untrusted).
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from tlamati.tools.registry import Permission
from tlamati.tools.webfetch import MAX_DOWNLOAD_BYTES, make_web_fetch_tools


def _mock(handler: Any) -> httpx.MockTransport:
    return httpx.MockTransport(handler)


def _tool(transport: httpx.MockTransport) -> Any:
    tools = make_web_fetch_tools(transport=transport)
    assert len(tools) == 1
    return tools[0]


class TestPolicyContract:
    def test_ask_and_untrusted_are_non_negotiable(self) -> None:
        tool = make_web_fetch_tools()[0]
        assert tool.name == "web_fetch"
        assert tool.permission is Permission.ASK
        assert tool.produces_untrusted is True

    def test_schema_requires_url(self) -> None:
        tool = make_web_fetch_tools()[0]
        assert tool.input_schema["required"] == ["url"]


class TestHappyPath:
    async def test_text_response_with_status_header(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="hola mundo", headers={"content-type": "text/plain"})

        tool = _tool(_mock(handler))
        out = await tool.run({"url": "https://example.com/x.txt"})
        assert "HTTP 200" in out
        assert "hola mundo" in out

    async def test_html_content_type_accepted(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                text="<html><body>hi</body></html>",
                headers={"content-type": "text/html; charset=utf-8"},
            )

        tool = _tool(_mock(handler))
        out = await tool.run({"url": "https://example.com/"})
        assert "<body>hi</body>" in out

    async def test_json_content_type_accepted(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"ok": True})

        tool = _tool(_mock(handler))
        out = await tool.run({"url": "https://api.example.com/v1"})
        assert '"ok"' in out


class TestHonestErrors:
    async def test_http_error_reported(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, text="nope")

        tool = _tool(_mock(handler))
        out = await tool.run({"url": "https://example.com/missing"})
        assert out.startswith("ERROR: HTTP 404")

    async def test_binary_content_rejected_with_content_type(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200, content=b"\x89PNG\x00\x01", headers={"content-type": "image/png"}
            )

        tool = _tool(_mock(handler))
        out = await tool.run({"url": "https://example.com/i.png"})
        assert out.startswith("ERROR: content-type no textual")
        assert "image/png" in out

    async def test_timeout_is_error_string_not_exception(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectTimeout("slow")

        tool = _tool(_mock(handler))
        out = await tool.run({"url": "https://slow.example.com"})
        assert out.startswith("ERROR: timeout")

    async def test_connection_error_is_error_string(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("dns fail")

        tool = _tool(_mock(handler))
        out = await tool.run({"url": "https://bad.example.com"})
        assert out.startswith("ERROR: fetch failed")

    async def test_non_http_scheme_rejected(self) -> None:
        tool = _tool(_mock(lambda r: httpx.Response(200, text="x")))
        out = await tool.run({"url": "file:///etc/passwd"})
        assert out.startswith("ERROR: only http")

    async def test_missing_url_rejected(self) -> None:
        tool = _tool(_mock(lambda r: httpx.Response(200, text="x")))
        out = await tool.run({})
        assert out.startswith("ERROR: url is required")


class TestSourceTruncation:
    async def test_large_body_cut_at_cap_with_visible_marker(self) -> None:
        big = b"a" * (MAX_DOWNLOAD_BYTES + 10_000)

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=big, headers={"content-type": "text/plain"})

        tool = _tool(_mock(handler))
        out = await tool.run({"url": "https://example.com/huge.txt"})
        assert "TRUNCADO EN LA FUENTE" in out
        # header + cuerpo truncado no debe exceder el cap por mucho
        assert len(out) <= MAX_DOWNLOAD_BYTES + 500


class TestRedirects:
    async def test_redirect_followed(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/old":
                return httpx.Response(301, headers={"location": "https://example.com/new"})
            return httpx.Response(200, text="destino", headers={"content-type": "text/plain"})

        tool = _tool(_mock(handler))
        out = await tool.run({"url": "https://example.com/old"})
        assert "destino" in out


class TestRegistryIntegration:
    def test_webfetch_registers_and_spec_is_stable(self) -> None:
        """Entra al Registry sin colisión y su spec (prefijo cacheable) es estable."""
        from tlamati.tools.registry import Registry

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="x", headers={"content-type": "text/plain"})

        tool = _tool(_mock(handler))
        reg = Registry()
        reg.register(tool)
        specs = reg.specs()
        assert [s.name for s in specs] == ["web_fetch"]
        assert "url" in tool.input_schema["properties"]


class TestBuiltinComposition:
    def test_webfetch_included_in_make_tools(self) -> None:
        from pathlib import Path

        from tlamati.tools.builtin import make_tools

        names = [t.name for t in make_tools(Path("/tmp"), sandbox=False)]
        assert "web_fetch" in names

    def test_environment_block_mentions_web_fetch(self) -> None:
        from pathlib import Path

        from tlamati.env_info import environment_block

        block = environment_block(Path("/tmp"), net=False)
        assert "web_fetch" in block


@pytest.mark.parametrize(
    "ct",
    [
        "text/plain",
        "text/html; charset=utf-8",
        "application/json",
        "application/xml",
        "application/ld+json",
        "text/markdown",
        "application/x-yaml",
    ],
)
async def test_textual_content_types(ct: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"cuerpo", headers={"content-type": ct})

    tool = _tool(_mock(handler))
    out = await tool.run({"url": "https://example.com/f"})
    assert not out.startswith("ERROR")
    assert "cuerpo" in out


@pytest.mark.parametrize("ct", ["image/png", "application/pdf", "application/zip"])
async def test_binary_content_types_rejected(ct: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"\x00\x01", headers={"content-type": ct})

    tool = _tool(_mock(handler))
    out = await tool.run({"url": "https://example.com/f"})
    assert out.startswith("ERROR: content-type no textual")
