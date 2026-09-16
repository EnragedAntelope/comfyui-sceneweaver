"""Todo 2 -- the test harness itself.

These assertions exist so a *harness* regression fails loudly here instead of
showing up as a hundred confusing failures elsewhere. The one that matters most
is ``test_stub_exports_comfy_extension``: Identity Forge shipped a stub without
that export for several releases, which broke ``pytest`` on every single test
while ``unittest discover`` stayed green, and the cause was misrecorded as a
stub *ordering* problem for months.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

from comfy_api.latest import ComfyExtension, io

_ROOT = Path(__file__).resolve().parent.parent


class ComfyApiAvailabilityTests(unittest.TestCase):
    """The bootstrap put *some* ``comfy_api`` in reach before any node import."""

    def test_comfy_api_is_importable(self) -> None:
        self.assertIn("comfy_api.latest.io", sys.modules)

    def test_stub_exports_comfy_extension(self) -> None:
        # The repo-root __init__.py does `from comfy_api.latest import
        # ComfyExtension, io`. Without this export the entrypoint is
        # unimportable and pytest -- which reaches the root package -- fails
        # everywhere while unittest discover stays green. Do not delete.
        self.assertTrue(callable(getattr(ComfyExtension, "get_node_list", None)))

    def test_real_comfy_api_wins_when_installed(self) -> None:
        """Real-first, stub-fallback: the stub is only on the path as a
        fallback, and never ahead of a real install."""
        stub_root = str(_ROOT / "tests" / "comfy_stub")
        module_file = getattr(sys.modules["comfy_api.latest.io"], "__file__", "") or ""
        if stub_root in sys.path:
            # No real ComfyUI here, so the loaded module must be the stub.
            self.assertTrue(module_file.startswith(stub_root))
        else:
            # A real install was found; the stub must not have been registered.
            self.assertFalse(module_file.startswith(stub_root))


class StubSurfaceTests(unittest.TestCase):
    """Every ``io`` name the pack constructs must exist and behave.

    Narrow on purpose: widening the stub without a matching call site is how a
    stub drifts into fiction.
    """

    def test_schema_accepts_the_fields_the_nodes_pass(self) -> None:
        schema = io.Schema(
            node_id="X",
            display_name="X",
            category="conditioning/sceneweaver",
            description="d",
            inputs=[],
            outputs=[io.String.Output(display_name="prompt_text")],
        )
        self.assertEqual(schema.node_id, "X")
        self.assertEqual(schema.outputs[0].display_name, "prompt_text")

    def test_widget_inputs_carry_a_default(self) -> None:
        self.assertTrue(hasattr(io.Combo.Input("f", options=["a"], default="a"), "default"))
        self.assertTrue(hasattr(io.String.Input("f", default=""), "default"))
        self.assertTrue(hasattr(io.Int.Input("seed", default=0), "default"))

    def test_combo_input_records_its_options(self) -> None:
        widget = io.Combo.Input("f", options=["Random", "a", "None"], default="Random")
        self.assertEqual(widget.options, ["Random", "a", "None"])

    def test_custom_socket_carries_its_io_type(self) -> None:
        socket = io.Custom("SCENE_ENTITY")
        self.assertEqual(socket.io_type, "SCENE_ENTITY")
        self.assertEqual(socket.Output(display_name="entity").io_type, "SCENE_ENTITY")
        self.assertEqual(socket.Input("entity_1_in", optional=True).io_type, "SCENE_ENTITY")

    def test_custom_socket_input_has_no_default(self) -> None:
        """A wire-only socket is structurally distinct from a widget.

        The real API gives ``default`` to ``WidgetInput`` only, so
        ``hasattr(inp, "default")`` separates the widgets that occupy a saved
        workflow's positional ``widgets_values`` from the sockets that do not.
        Todo 18 counts on that distinction; if the stub blurred it, the count
        assertion would pass here and be wrong in ComfyUI.
        """
        self.assertFalse(hasattr(io.Custom("SCENE_ENTITY").Input("entity_1_in"), "default"))

    def test_comfy_node_declares_fingerprint_inputs_on_the_base(self) -> None:
        """So a test for "does this node override caching?" must inspect
        ``vars(cls)``, exactly as it must against the real API."""
        self.assertIn("fingerprint_inputs", vars(io.ComfyNode))

    def test_node_output_stores_positionally(self) -> None:
        self.assertEqual(io.NodeOutput("a", "b").args, ("a", "b"))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
