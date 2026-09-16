"""Factory for a genre's ``Scene Entity`` node.

The optional layer node: one entity described across the pack's full field set,
emitted as a ``SCENE_ENTITY`` payload that a Scene Weaver slot can consume. The
pack is a *parameter*, never an import -- see ``nodes/__init__.py``.

Nothing requires this node. The Scene Weaver is complete on its own and carries
a full slot 1 of its own; this exists for the two things that node cannot do:
describe a *supporting* entity in depth, and reuse one entity across several
scenes. Wiring one in is the user's explicit request for detail, which is why a
wired slot is exempt from the detail budget and why a wire outranks a locked
widget on that slot.
"""
from __future__ import annotations

from typing import Any

from comfy_api.latest import io  # type: ignore[import-not-found]

try:
    from ..data.genre import ENTITY_NODE_SLOTS, GenrePack
    from ..engine.scene import generate_entity
    from .readout import entity_readout
    from .widgets import build_inputs, read_controls, read_widgets
except ImportError:  # pragma: no cover -- standalone/test context
    from data.genre import ENTITY_NODE_SLOTS, GenrePack
    from engine.scene import generate_entity
    from nodes.readout import entity_readout
    from nodes.widgets import build_inputs, read_controls, read_widgets

#: Socket type shared by *every* genre, so any genre's entity node wires into
#: any genre's scene node -- a crashed starship in an enchanted forest is a
#: supported feature, not an accident. A dedicated type (rather than STRING)
#: also stops a silent miswiring into a text input.
SCENE_ENTITY_TYPE = "SCENE_ENTITY"

#: ``io.Custom`` mints a fresh class per call, so bind it once. ComfyUI matches
#: sockets on the ``io_type`` string, so one shared object keeps the identity
#: obvious rather than merely equivalent.
SceneEntitySocket = io.Custom(SCENE_ENTITY_TYPE)

#: Category both node classes register under, so a genre's pair sorts together.
NODE_CATEGORY = "conditioning/sceneweaver"


def build_entity_node(pack: GenrePack) -> type:
    """Generate the ``Scene Entity`` node class for ``pack``."""

    class SceneEntity(io.ComfyNode):  # type: ignore[misc, valid-type]
        """Describe one entity in depth and hand it to a Scene Weaver slot."""

        @classmethod
        def define_schema(cls) -> "io.Schema":
            return io.Schema(
                node_id=f"SceneEntity{pack.class_suffix}",
                display_name=f"Scene Entity - {pack.display}",
                category=NODE_CATEGORY,
                description=(
                    f"Describe one {pack.display} entity across every morphology "
                    "field and emit it as a SCENE_ENTITY payload. The entity_text "
                    "output is the entity as it will read inside a scene: no setting "
                    "and no action, both of which the Scene Weaver owns. Optional: "
                    "wire it into a Scene Weaver slot to give that slot the top "
                    "allowance -- though a kind a model builds from a silhouette "
                    "still speaks fewer details than one it builds from parts."
                ),
                inputs=build_inputs(pack, ENTITY_NODE_SLOTS),
                outputs=[
                    io.String.Output(display_name="entity_text"),
                    SceneEntitySocket.Output(display_name="entity"),
                ],
            )

        @classmethod
        def fingerprint_inputs(cls, **kwargs: Any) -> float:
            # Force a fresh roll on every queue. ComfyUI can serve a stale cached
            # result when control_after_generate auto-advances the seed (ComfyUI
            # #11905); a never-equal value makes this node's cache signature always
            # differ, so it re-executes and reads the new seed. Pure cache control --
            # no RNG here, so a fixed seed still reproduces exactly.
            return float("nan")

        @classmethod
        def execute(cls, **kwargs: Any) -> "io.NodeOutput":
            # No scene_filter on this node: the filter is a property of the scene
            # the entity ends up in, not of the entity itself. The entity is
            # budgeted as a wired slot at the top level and capped by its own
            # archetype, so what this node shows is exactly what it will
            # contribute to a one-entity scene -- a station speaks fewer details
            # than a creature, and the preview says so.
            controls = read_controls(pack, ENTITY_NODE_SLOTS, kwargs)
            text, payload = generate_entity(
                int(controls["seed"]),
                pack,
                widgets=read_widgets(pack, ENTITY_NODE_SLOTS, kwargs),
            )
            # `ui` is what puts the two-line readout on the node face. It
            # describes the entity that was actually generated, which the
            # frontend cannot work out from the widgets: most of them say
            # "Random", and "Random" is not a description.
            return io.NodeOutput(text, payload, ui={"text": entity_readout(payload)})

    SceneEntity.__name__ = f"SceneEntity{pack.class_suffix}"
    SceneEntity.__qualname__ = SceneEntity.__name__
    return SceneEntity
