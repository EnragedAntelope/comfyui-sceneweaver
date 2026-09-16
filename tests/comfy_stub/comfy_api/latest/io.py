"""A record-only stand-in for ``comfy_api.latest.io``, used only when the real
package is not importable (i.e. this process has no ComfyUI install).

Without this, both node factories in ``nodes/*.py`` -- which import ``io`` at
module scope -- would be unimportable outside a running ComfyUI, so nothing here
could ever be schema-tested and a CI runner would have nothing to read.

**This must never become the only thing anything sees.** Registration happens in
``tests/__init__.py`` and the rootdir ``conftest.py``, both of which import the
*real* package first and fall back to this one only on ``ImportError`` -- so on
a machine with ComfyUI installed everything runs against the genuine API, and
this stub exists purely to cover the gap on a runner that has neither.

Scope is deliberately narrow: only the surface this pack actually calls --
``Schema``, ``ComfyNode``, ``NodeOutput``, ``Combo.Input``,
``String.Input``/``String.Output``, ``Int.Input`` and ``Custom`` (for the
``SCENE_ENTITY`` socket). No ``Float``, ``Image``, ``Hidden`` or
``NumberDisplay`` -- this pack does not use them. Widen it only alongside a real
call site.

Structural fidelity that matters, mirrored from the real ``_io.py``:

* ``Input`` carries **no** ``default``; only ``WidgetInput`` adds one. A
  socket-only type (``Custom(...).Input``) extends ``Input`` directly, so
  ``hasattr(inp, "default")`` distinguishes a real widget from a link-only
  socket without maintaining a name list. Todo 18 input-count assertions rely
  on that.
* ``ComfyNode.fingerprint_inputs`` is declared here whether or not a node
  overrides it, exactly as the real base class does -- so a test asking whether
  a node overrides caching must check ``"fingerprint_inputs" in vars(cls)``,
  never ``hasattr``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class Input:
    """Base for every ``*.Input`` below: id/display/optional/tooltip only."""

    def __init__(
        self,
        id: str,
        display_name: str | None = None,
        optional: bool = False,
        tooltip: str | None = None,
        **extra: Any,
    ) -> None:
        self.id = id
        self.display_name = display_name
        self.optional = optional
        self.tooltip = tooltip
        for key, value in extra.items():
            setattr(self, key, value)


class WidgetInput(Input):
    """Base for an Input that has a widget on the node face, and so contributes
    an entry to a saved workflow's positional ``widgets_values``."""

    def __init__(
        self,
        id: str,
        display_name: str | None = None,
        optional: bool = False,
        tooltip: str | None = None,
        default: Any = None,
        **extra: Any,
    ) -> None:
        super().__init__(id, display_name, optional, tooltip, **extra)
        self.default = default


class Output:
    """Base for every ``*.Output`` below."""

    def __init__(
        self,
        id: str | None = None,
        display_name: str | None = None,
        tooltip: str | None = None,
        is_output_list: bool = False,
        **extra: Any,
    ) -> None:
        self.id = id
        self.display_name = display_name if display_name else id
        self.tooltip = tooltip
        self.is_output_list = is_output_list
        for key, value in extra.items():
            setattr(self, key, value)


class Int:
    class Input(WidgetInput):
        def __init__(
            self,
            id: str,
            display_name: str | None = None,
            default: int | None = None,
            min: int | None = None,
            max: int | None = None,
            control_after_generate: str | bool | None = None,
            tooltip: str | None = None,
            optional: bool = False,
            **extra: Any,
        ) -> None:
            super().__init__(id, display_name, optional, tooltip, default, **extra)
            self.min = min
            self.max = max
            self.control_after_generate = control_after_generate

    class Output(Output):
        pass


class String:
    class Input(WidgetInput):
        def __init__(
            self,
            id: str,
            display_name: str | None = None,
            multiline: bool = False,
            optional: bool = False,
            default: str | None = None,
            force_input: bool = False,
            tooltip: str | None = None,
            **extra: Any,
        ) -> None:
            super().__init__(id, display_name, optional, tooltip, default, **extra)
            self.multiline = multiline
            self.force_input = force_input

    class Output(Output):
        pass


class Combo:
    class Input(WidgetInput):
        def __init__(
            self,
            id: str,
            options: list[str] | None = None,
            display_name: str | None = None,
            default: str | None = None,
            control_after_generate: str | bool | None = None,
            tooltip: str | None = None,
            optional: bool = False,
            **extra: Any,
        ) -> None:
            super().__init__(id, display_name, optional, tooltip, default, **extra)
            # Real ComfyUI stores the raw list here; the options-object shape
            # (``.values``) shows up on the *frontend* widget, not this schema
            # Input. Fixture generators read this list directly.
            self.options = options if options is not None else []
            self.control_after_generate = control_after_generate


# Bound before ``Custom`` so its nested classes can name the module-level bases
# without the name lookup resolving to the nested definitions themselves.
_InputBase = Input
_OutputBase = Output


def Custom(io_type: str) -> type:  # noqa: N802 -- mirrors the real API name
    """Mint a socket-only ComfyType for ``io_type``.

    Matches the real ``io.Custom``: a fresh class per call, carrying the type
    string that ComfyUI matches sockets on. ``Input`` extends the socket-only
    ``Input`` base (no ``default``), which is exactly what a wire-only input is.
    """

    class CustomComfyType:
        io_type: str = ""

        class Input(_InputBase):
            pass

        class Output(_OutputBase):
            pass

    CustomComfyType.io_type = io_type
    CustomComfyType.Input.io_type = io_type
    CustomComfyType.Output.io_type = io_type
    return CustomComfyType


@dataclass
class Schema:
    """Definition of a V3 node inputs/outputs. Subset of the real fields --
    exactly what ``nodes/*.py`` passes to ``io.Schema(...)``."""

    node_id: str
    display_name: str | None = None
    category: str = "sd"
    inputs: list[Input] = field(default_factory=list)
    outputs: list[Output] = field(default_factory=list)
    description: str = ""
    is_output_node: bool = False


class ComfyNode:
    """Common base every node class here inherits from.

    No execution-time behaviour: nothing in this repo's Python suite drives
    ``execute()`` through the real ComfyUI queue plumbing -- the engine
    functions it delegates to are tested directly instead.
    """

    @classmethod
    def fingerprint_inputs(cls, **kwargs: Any) -> Any:
        """Declared solely so the stub matches the real base class -- see the
        module docstring."""
        raise NotImplementedError


class NodeOutput:
    """Positional output bundle plus the optional UI payload.

    ``ui`` mirrors the real signature (``ui: _UIOutput | dict``). A plain dict is
    what both node classes pass -- the real ComfyUI accepts one and forwards it
    to the frontend's ``onExecuted`` untouched -- so no ``_UIOutput`` class is
    needed here. ``expand`` and ``block_execution`` are omitted: this pack calls
    neither, and a stub wider than its call sites is a stub that can drift.
    """

    def __init__(self, *args: Any, ui: Any = None) -> None:
        self.args = args
        self.ui = ui
