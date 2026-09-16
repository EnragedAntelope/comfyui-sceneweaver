"""ASCII-only gate: every tracked text file must be pure ASCII.

Wave 1 of the sceneweaver overhaul. Kept as a permanent regression test so a
non-ASCII byte (em-dash, middle dot, smart quote, ...) cannot silently return.
"""
from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: Extensions treated as text. Everything else (images, binaries) is ignored.
TEXT_EXTENSIONS = {".py", ".js", ".mjs", ".css", ".md", ".json", ".toml", ".txt"}

#: Path fragments that are never scanned: generated, cached, or vendored.
EXCLUDED_FRAGMENTS = (
    "node_modules",
    "__pycache__",
    ".ruff_cache",
    ".pytest_cache",
    ".git",
    ".omo",
)


def _tracked_text_files() -> list[Path]:
    """All git-tracked files under the repo root with a text extension."""
    listing = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout
    files: list[Path] = []
    for rel in listing.splitlines():
        path = ROOT / rel
        if path.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        if any(fragment in path.parts for fragment in EXCLUDED_FRAGMENTS):
            continue
        files.append(path)
    return files


class TestAsciiOnly(unittest.TestCase):
    def test_all_tracked_text_files_are_ascii(self) -> None:
        offenders: list[str] = []
        for path in _tracked_text_files():
            try:
                data = path.read_bytes()
            except OSError:
                continue
            line = 1
            start = 0
            for i, byte in enumerate(data):
                if byte == 0x0A:
                    line += 1
                    start = i + 1
                elif byte > 0x7F:
                    col = i - start + 1
                    run = data[i : i + 4]
                    try:
                        char = run.decode("utf-8", errors="ignore")[:1]
                    except Exception:
                        char = ""
                    offenders.append(
                        f"{path.relative_to(ROOT)}:{line}:{col}: byte 0x{byte:02X} ({char!r})"
                    )
        if offenders:
            self.fail(
                "Non-ASCII bytes found (repo must be ASCII-only):\n"
                + "\n".join(offenders)
            )


if __name__ == "__main__":
    unittest.main()
