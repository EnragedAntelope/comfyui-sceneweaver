"""Loads the repo-root ``__init__.py`` (the ComfyUI entrypoint) for testing.

The repo directory is ``comfyui-sceneweaver`` -- hyphenated, per the ComfyUI
Registry naming convention -- so it is not a legal Python package name and
``import comfyui_sceneweaver`` cannot work by directory name alone. ComfyUI does
not rely on one either: ``load_custom_node`` builds a spec straight from
``<pack>/__init__.py`` under a name of its own choosing. Both loaders here do
the same thing, in the two shapes the entrypoint's try/except was written for.

* ``load_entrypoint`` -- **package mode**, what ComfyUI actually does.
  ``spec_from_file_location`` on an ``__init__.py`` marks the module a package,
  so the entrypoint's ``from .data.scifi import ...`` resolves and the ``try``
  branch is what runs.
* ``load_entrypoint_flat`` -- **flat mode**. Suppressing
  ``submodule_search_locations`` makes the module a plain module with no parent
  package, so every package-relative import fails and the ``except ImportError``
  fallback is what supplies the pack. That branch exists for flatter layouts and
  would otherwise never be executed by anything, which is how a fallback rots.

Package mode binds a *second* copy of ``data`` / ``nodes`` under the entrypoint
package name, so classes loaded through it are not identical to the ones a
plain ``import data.scifi`` yields. Use flat mode for any assertion that turns
on object identity.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

#: The name the entrypoint module is bound to. The underscored form of the
#: distribution name, so the module reads naturally in test output.
PACKAGE_NAME = "comfyui_sceneweaver"

REPO_ROOT = Path(__file__).resolve().parent.parent

_ENTRYPOINT = REPO_ROOT / "__init__.py"


def _load(name: str, *, as_package: bool) -> ModuleType:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    sys.modules.pop(name, None)
    if as_package:
        spec = importlib.util.spec_from_file_location(name, _ENTRYPOINT)
    else:
        # Explicit None suppresses the "this file is called __init__.py, so it
        # must be a package" inference -- which is exactly what makes the
        # package-relative imports fail and the fallback fire.
        spec = importlib.util.spec_from_file_location(
            name, _ENTRYPOINT, submodule_search_locations=None
        )
    if spec is None or spec.loader is None:  # pragma: no cover -- unreachable
        raise ImportError(f"cannot build a spec for {_ENTRYPOINT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


def load_entrypoint(name: str = PACKAGE_NAME) -> ModuleType:
    """Load the entrypoint the way ComfyUI does (package mode).

    Always loads fresh: the node classes are generated at import time, so a
    cached module would hide a regression in the factories.
    """
    return _load(name, as_package=True)


def load_entrypoint_flat(name: str = f"{PACKAGE_NAME}_flat") -> ModuleType:
    """Load the entrypoint with no parent package, exercising the fallback."""
    return _load(name, as_package=False)
