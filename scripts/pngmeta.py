"""Read the text chunks ComfyUI writes into a PNG -- standard library only.

ComfyUI stores the executed graph as a ``prompt`` chunk (API format) and the
editor graph as ``workflow``. ``scripts/replay_batch.py`` reads ``prompt`` to
replay a batch of images through the engine.
"""
from __future__ import annotations

import struct
import zlib
from pathlib import Path

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def png_text_chunks(path: "str | Path") -> dict[str, str]:
    """Every tEXt, zTXt and iTXt chunk of a PNG, as ``{keyword: text}``."""
    found: dict[str, str] = {}
    with open(path, "rb") as handle:
        if handle.read(8) != PNG_SIGNATURE:
            raise ValueError(f"{path} is not a PNG file")
        while True:
            head = handle.read(8)
            if len(head) < 8:
                break
            length, kind = struct.unpack(">I4s", head)
            if kind not in (b"tEXt", b"zTXt", b"iTXt"):
                if kind == b"IEND":
                    break
                handle.seek(length + 4, 1)
                continue
            data = handle.read(length)
            handle.seek(4, 1)
            key, _, rest = data.partition(b"\x00")
            name = key.decode("latin-1")
            if kind == b"tEXt":
                found[name] = rest.decode("latin-1")
            elif kind == b"zTXt":
                found[name] = zlib.decompress(rest[1:]).decode("latin-1")
            else:
                compressed = rest[0]
                rest = rest[2:]
                _language, _, rest = rest.partition(b"\x00")
                _translated, _, text = rest.partition(b"\x00")
                found[name] = (zlib.decompress(text) if compressed else text).decode("utf-8")
    return found
