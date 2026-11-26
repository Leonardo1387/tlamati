"""Vision v2.1 — image loading at the narrow waist.

Dolor real (dogfood 26-nov): el arnés no podía ENSEÑAR una imagen al modelo.
``Message.content: str`` es texto puro y web_fetch rechaza binarios honestamente
(así debe seguir: egreso acotado, un verbo). La vía tlamática NO es un VLM
local que parafrasea (eso pierde la imagen: el modelo ve un texto de segunda
mano), sino bloques de imagen nativos en el waist: ``ImageBlock`` viaja en
``Message.images`` / ``ToolResult.images`` y cada adaptador lo traduce a SU
formato (Anthropic base64 source / OpenAI data-URL). El loop y el resto del
core siguen ciegos al proveedor.

Reglas de honestidad (las mismas de M1/web_fetch):
- Magic bytes, no la extensión: un .png que es JPEG se declara JPEG; un
  binario que no es imagen → error que dice qué llegó.
- Cap en la fuente (MAX_IMAGE_BYTES): una imagen mayor se RECHAZA con su peso
  visible (no se recorta a medias: una imagen truncada es un png roto que el
  proveedor 400-ea de forma críptica).
- Dimensiones reales cuando el formato las expone barato (png/jpeg/gif);
  None cuando no (webp) — nunca inventadas.
- Costo de tokens VISIBLE (budget.py): Anthropic ≈ w*h/750; sin dimensiones,
  estimación documentada de 1600 (típica de una imagen redimensionada por la
  API). Nunca cero silencioso.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path

# Anthropic hard limit is 5 MB per image; dejamos margen para el base64 y para
# que el error llegue ANTES de gastar un request.
MAX_IMAGE_BYTES = 4_000_000

# Estimación documentada cuando el formato no expone dimensiones barato.
FALLBACK_IMAGE_TOKENS = 1600

_MAGIC: tuple[tuple[bytes, str], ...] = (
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
)


@dataclass(frozen=True)
class ImageBlock:
    """One image attached to a message or tool result.

    ``data`` is base64 (the wire form both providers need; keeps the dataclass
    hashable/serializable like the rest of the waist). ``source_path`` is
    provenance for the audit trail and the model-facing marker — None when the
    image did not come from a path (future: paste/URL).
    """

    data: str
    media_type: str
    width: int | None = None
    height: int | None = None
    source_path: str | None = None
    size_bytes: int = 0

    def token_estimate(self) -> int:
        """Anthropic's published formula (w*h/750); honest fallback otherwise."""
        if self.width and self.height:
            return max(1, (self.width * self.height) // 750)
        return FALLBACK_IMAGE_TOKENS

    def marker(self) -> str:
        """Model-facing one-liner that travels as text next to the block."""
        dims = f"{self.width}x{self.height}" if self.width and self.height else "dims n/d"
        where = f" · {self.source_path}" if self.source_path else ""
        return (
            f"[image · {self.media_type} · {dims} · {self.size_bytes} bytes{where} "
            f"· ~{self.token_estimate()} tokens — adjunta como bloque de visión]"
        )


def detect_media_type(head: bytes) -> str | None:
    """Magic-byte sniff. None = not a supported image (honest, not a guess)."""
    for magic, media in _MAGIC:
        if head.startswith(magic):
            return media
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    return None


def _dims_png(b: bytes) -> tuple[int | None, int | None]:
    if len(b) >= 24:
        return int.from_bytes(b[16:20], "big"), int.from_bytes(b[20:24], "big")
    return None, None


def _dims_gif(b: bytes) -> tuple[int | None, int | None]:
    if len(b) >= 10:
        return int.from_bytes(b[6:8], "little"), int.from_bytes(b[8:10], "little")
    return None, None


def _dims_jpeg(b: bytes) -> tuple[int | None, int | None]:
    """Walk markers to the first SOFn (frame header carries h/w)."""
    i = 2
    n = len(b)
    while i + 9 < n:
        if b[i] != 0xFF:
            i += 1
            continue
        marker = b[i + 1]
        if marker == 0xFF:
            i += 1
            continue
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        seg_len = int.from_bytes(b[i + 2 : i + 4], "big")
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            return int.from_bytes(b[i + 7 : i + 9], "big"), int.from_bytes(b[i + 5 : i + 7], "big")
        i += 2 + seg_len
    return None, None


def _dimensions(media: str, b: bytes) -> tuple[int | None, int | None]:
    if media == "image/png":
        return _dims_png(b)
    if media == "image/gif":
        return _dims_gif(b)
    if media == "image/jpeg":
        return _dims_jpeg(b)
    return None, None  # webp: barato y honesto > parser completo en v2.1


def load_image(path: Path) -> ImageBlock:
    """Read a local image file into an ImageBlock.

    Raises ValueError with a model/user-readable reason (never a crash into
    the loop; callers convert to ERROR strings).
    """
    if not path.is_file():
        raise ValueError(f"no such file: {path}")
    try:
        raw = path.read_bytes()
    except OSError as e:
        raise ValueError(f"cannot read {path}: {e}") from e
    media = detect_media_type(raw[:12])
    if media is None:
        head = raw[:8].hex() or "vacío"
        raise ValueError(
            f"{path} no es una imagen soportada (png/jpeg/gif/webp); magic bytes: {head}"
        )
    if len(raw) > MAX_IMAGE_BYTES:
        raise ValueError(
            f"{path} pesa {len(raw)} bytes y el tope es {MAX_IMAGE_BYTES} "
            "(imágenes mayores se rechazan enteras: recortarlas produciría un "
            "binario roto)"
        )
    w, h = _dimensions(media, raw)
    return ImageBlock(
        data=base64.b64encode(raw).decode("ascii"),
        media_type=media,
        width=w,
        height=h,
        source_path=str(path),
        size_bytes=len(raw),
    )
