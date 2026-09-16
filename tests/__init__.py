"""Runs before every ``tests/test_*.py`` module -- but only under
``python -m unittest discover -s tests -t . -v``. The ``-t .`` is what makes
``tests`` a genuine subpackage of the repo root, and that is what makes
Python's import system guarantee this file runs before its children. Without
it, ``discover`` imports the test files as bare top-level modules and this
package ``__init__`` never runs first.

Two jobs, both order-sensitive:

1. Put the repo root on ``sys.path`` so ``data.*``, ``nodes.*`` and ``engine.*``
   resolve when the suite is run from anywhere.
2. Register the ``comfy_api`` stub **before** any test module can import a node
   module. A module runs its top-level code once per process, so if
   ``nodes.scene_weaver`` were imported first it would raise on the missing
   ``comfy_api`` and the failure would be permanent for the rest of the run --
   registering the stub afterwards could not undo it.

**Real-first, stub-fallback:** on a machine with ComfyUI installed the real
``comfy_api`` wins and the stub is never touched.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent

if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:  # pragma: no cover -- taken on a machine with ComfyUI installed
    import comfy_api.latest.io  # noqa: F401
except ImportError:
    sys.path.insert(0, str(_ROOT / "tests" / "comfy_stub"))
