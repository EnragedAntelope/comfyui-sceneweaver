"""scripts/pngmeta.py reads the text chunks ComfyUI writes, with the standard library."""
from __future__ import annotations

import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from pngmeta import PNG_SIGNATURE, png_text_chunks  # noqa: E402


def _chunk(kind: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(kind + data)
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", crc)


class PngTextChunkTests(unittest.TestCase):
    def test_reads_text_ztxt_and_itxt_chunks(self) -> None:
        header = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
        body = (
            PNG_SIGNATURE
            + _chunk(b"IHDR", header)
            + _chunk(b"tEXt", b'prompt\x00{"a": 1}')
            + _chunk(b"zTXt", b"workflow\x00\x00" + zlib.compress(b'{"nodes": []}'))
            + _chunk(b"iTXt", b"parameters\x00\x00\x00\x00\x00caf\xc3\xa9")
            + _chunk(b"IDAT", zlib.compress(b"\x00\x00\x00\x00"))
            + _chunk(b"IEND", b"")
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "image.png"
            path.write_bytes(body)
            chunks = png_text_chunks(path)
        self.assertEqual(chunks["prompt"], '{"a": 1}')
        self.assertEqual(chunks["workflow"], '{"nodes": []}')
        self.assertEqual(chunks["parameters"], "caf" + chr(233))  # keeps the source ASCII

    def test_a_file_that_is_not_a_png_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "image.png"
            path.write_bytes(b"not a png")
            with self.assertRaises(ValueError):
                png_text_chunks(path)
