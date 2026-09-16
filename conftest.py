"""Registers the comfy_api stub before pytest collects any test module.

``python -m unittest discover -s tests -t .`` gets this ordering from
``tests/__init__.py``, because ``-t .`` makes ``tests`` a genuine subpackage
whose ``__init__`` Python must run first. pytest has no equivalent guarantee,
so it could import a node module before the stub is registered -- a contributor
running the natural-feeling command would get a silently different suite. A
rootdir ``conftest.py`` is imported before collection begins, which is the same
guarantee by a different route.

**Real-first, stub-fallback**, identical to ``tests/__init__.py``: with ComfyUI
installed the real ``comfy_api`` wins and the stub is never touched. Both files
are kept because they cover different runners, not because either is redundant.

``python -m unittest discover -s tests -t . -v`` remains the documented command
and the CI entry point -- it is what guarantees the pack stays dependency-free.
This file makes ``pytest`` *correct*; it does not make it *the* command.

**One known limitation, and it is structural.** pytest resolves this file's
module name through the package chain: it walks up from ``conftest.py`` for as
long as it finds an ``__init__.py``. The repo root has one -- it is a ComfyUI
pack, so it must -- which means that if the *directory* is also a legal Python
identifier, pytest imports the root package (running the entrypoint, and its
``from comfy_api.latest import ...``) **before** it imports this file, and the
stub registration below never gets its turn::

    git clone <url> comfyui-sceneweaver && pytest tests   # exits 0
    git clone <url> sceneweaver         && pytest tests   # exits 4

``--import-mode=importlib`` does not change it: pytest still resolves the
package chain. ``pythonpath = ["tests/comfy_stub"]`` in pyproject.toml does fix
it, because that runs before collection -- but it puts the stub *ahead* of a
real installed ``comfy_api``, which throws away the real-first property this
whole file exists to preserve, on exactly the machines that have ComfyUI.

It is left as a documented constraint rather than engineered around, because the
supported name is the only one anything produces: ``git clone`` uses the repo
name, and ComfyUI installs a custom node under it. Clone or install this pack as
``comfyui-sceneweaver``. ``python -m unittest discover -s tests -t . -v`` works
under any directory name.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent

# The repo root must be importable for `data.*` / `nodes.*` / `engine.*` to
# resolve, and for pytest's own import of the root package -- which is what
# surfaced the missing `ComfyExtension` export on Identity Forge's stub.
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:  # pragma: no cover -- taken on a machine with ComfyUI installed
    import comfy_api.latest.io  # noqa: F401
except ImportError:
    sys.path.insert(0, str(_ROOT / "tests" / "comfy_stub"))
