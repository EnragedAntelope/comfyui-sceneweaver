"""Todo 1 -- V3 registration for both node classes.

Lands with Todo 2 rather than Todo 1 because it needs the ``comfy_api`` stub
that Todo 2 builds; Todo 1's own acceptance gate is the standalone entrypoint
command recorded in ``.omo/evidence/task-1-sceneweaver.txt``.
"""
from __future__ import annotations

import asyncio
import importlib
import sys
import unittest

from tests._loader import (
    PACKAGE_NAME,
    REPO_ROOT,
    load_entrypoint,
    load_entrypoint_flat,
)

EXPECTED_CATEGORY = "conditioning/sceneweaver"


def _node_list(module: object) -> list[type]:
    return asyncio.run(asyncio.run(module.comfy_entrypoint()).get_node_list())


class EntrypointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_entrypoint()

    def test_entrypoint_returns_an_extension(self) -> None:
        extension = asyncio.run(self.module.comfy_entrypoint())
        self.assertIsInstance(extension, self.module.SceneWeaverExtension)

    def test_get_node_list_returns_every_genre_pair(self) -> None:
        nodes = _node_list(self.module)
        self.assertEqual(len(nodes), 4)
        self.assertEqual(
            {n.__name__ for n in nodes},
            {"SceneWeaverSciFi", "SceneEntitySciFi", "SceneWeaverFantasy", "SceneEntityFantasy"},
        )

    def test_web_directory_points_at_the_js_folder(self) -> None:
        self.assertEqual(self.module.WEB_DIRECTORY, "./js")
        self.assertTrue((REPO_ROOT / "js").is_dir())

    def test_package_mode_uses_the_relative_imports(self) -> None:
        """The branch ComfyUI itself takes: ``load_custom_node`` builds the spec
        from ``<pack>/__init__.py``, which makes the module a package and lets
        ``from .data.scifi import ...`` resolve."""
        self.assertEqual(self.module.__package__, PACKAGE_NAME)
        self.assertIn(f"{PACKAGE_NAME}.data.scifi", sys.modules)


class FlatLayoutFallbackTests(unittest.TestCase):
    """The ``except ImportError`` fallback is live code, not decoration.

    With no parent package every package-relative import in the entrypoint
    fails, so the absolute branch is what supplies the pack and the factories.
    Nothing else in the suite executes it, and an unexecuted fallback is one
    rename away from being broken without anyone noticing.
    """

    def test_flat_load_registers_both_nodes(self) -> None:
        module = load_entrypoint_flat()
        self.assertEqual(module.__package__, "")
        self.assertIn("data.scifi", sys.modules)
        self.assertEqual(len(_node_list(module)), 4)


class NodeIdentityTests(unittest.TestCase):
    """Identity only. Both classes are registration shells until Todos 17-18."""

    def setUp(self) -> None:
        self.module = load_entrypoint()
        self.nodes = {n.__name__: n for n in _node_list(self.module)}
        self.schemas = {name: n.define_schema() for name, n in self.nodes.items()}

    def test_node_ids_and_display_names(self) -> None:
        self.assertEqual(self.schemas["SceneWeaverSciFi"].node_id, "SceneWeaverSciFi")
        self.assertEqual(
            self.schemas["SceneWeaverSciFi"].display_name, "Scene Weaver - Sci-Fi"
        )
        self.assertEqual(self.schemas["SceneEntitySciFi"].node_id, "SceneEntitySciFi")
        self.assertEqual(
            self.schemas["SceneEntitySciFi"].display_name, "Scene Entity - Sci-Fi"
        )

    def test_both_register_in_one_category(self) -> None:
        for name, schema in self.schemas.items():
            with self.subTest(node=name):
                self.assertEqual(schema.category, EXPECTED_CATEGORY)

    def test_output_sockets(self) -> None:
        weaver = [o.display_name for o in self.schemas["SceneWeaverSciFi"].outputs]
        entity_outputs = self.schemas["SceneEntitySciFi"].outputs
        self.assertEqual(weaver, ["prompt_text", "prompt_json"])
        self.assertEqual([o.display_name for o in entity_outputs], ["entity_text", "entity"])
        self.assertEqual(entity_outputs[1].io_type, "SCENE_ENTITY")

    def test_both_force_a_fresh_roll_every_queue(self) -> None:
        """ComfyUI #11905: with ``control_after_generate`` advancing the seed, a
        cached result can be served for the new seed. ``vars(cls)`` rather than
        ``hasattr`` -- the base class declares the hook either way."""
        for name, node in self.nodes.items():
            with self.subTest(node=name):
                self.assertIn("fingerprint_inputs", vars(node))
                self.assertNotEqual(node.fingerprint_inputs(), node.fingerprint_inputs())

    def test_neither_node_is_a_shell_any_more(self) -> None:
        """Replaces the placeholder assertions Todos 17 and 18 retired. The
        shape of each schema is pinned by its own suite; what is checked here is
        that the classes ComfyUI is actually handed are the finished ones -- the
        registration path and the factories are two different things and only
        this test crosses both."""
        for name, node in self.nodes.items():
            with self.subTest(node=name):
                self.assertFalse(hasattr(node, "_PLACEHOLDER_SCHEMA"))
                self.assertTrue(node.define_schema().inputs)


class MissingModuleTests(unittest.TestCase):
    """A node module that cannot be found must raise, never register nothing.

    The entrypoint's try/except exists to switch between a package-relative and
    a flat layout. A bare ``except ImportError`` around a whole import block can
    just as easily swallow a genuine typo and hand ComfyUI a pack with fewer
    nodes than it should have -- silently. This pins the loud behaviour.
    """

    class _Blocker:
        """Refuses one module, under any package prefix.

        Prefix-tolerant because package mode binds the same file twice: once as
        ``data.scifi`` and once as ``<entrypoint>.data.scifi``. Matching only
        the bare name would let the relative import sail past the block and the
        test would assert nothing.
        """

        def __init__(self, blocked: str) -> None:
            self.blocked = blocked
            self._suffix = f".{blocked}"

        def find_spec(self, fullname, path=None, target=None):  # noqa: ANN001, ANN202
            if fullname == self.blocked or fullname.endswith(self._suffix):
                raise ImportError(f"blocked for test: {fullname}")
            return None

    def _load_without(self, module_name: str) -> None:
        blocker = self._Blocker(module_name)
        sys.meta_path.insert(0, blocker)
        head = module_name.split(".")[0]
        purged = {
            key: value
            for key, value in sys.modules.items()
            if key == head or f".{head}." in f".{key}."
        }
        for key in purged:
            del sys.modules[key]
        try:
            load_entrypoint(f"{PACKAGE_NAME}_missing")
        finally:
            sys.meta_path.remove(blocker)
            sys.modules.update(purged)
            sys.modules.pop(f"{PACKAGE_NAME}_missing", None)

    def test_unresolvable_node_module_raises(self) -> None:
        with self.assertRaises(ImportError):
            self._load_without("nodes.scene_weaver")

    def test_unresolvable_pack_module_raises(self) -> None:
        with self.assertRaises(ImportError):
            self._load_without("data.scifi")

    def test_the_repo_still_imports_afterwards(self) -> None:
        """The blocker teardown must leave ``sys.modules`` usable -- otherwise
        this class would poison every test that runs after it."""
        importlib.import_module("data.scifi")
        self.assertEqual(len(_node_list(load_entrypoint())), 4)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
