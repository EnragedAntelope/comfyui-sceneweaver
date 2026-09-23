"""Factory for a genre's ``Scene Weaver`` node.

The core node: complete on its own. One click yields an environment, up to four
entities and the relations between them. Four optional ``SCENE_ENTITY`` sockets
let a Scene Entity node promote any slot to full depth, but nothing is required
to be wired. The pack is a *parameter*, never an import.

**Why the sockets come last in the schema.** Only widgets contribute to a saved
workflow's positional ``widgets_values``, so a link-only socket cannot disturb
it wherever it sits. Appending them keeps the node face reading top-down as the
generation controls, then the scene, then the wires that override parts of it --
and keeps "append, never insert" true of the whole input list, not just the
widget half of it.
"""
from __future__ import annotations

from typing import Any, Mapping

from comfy_api.latest import io  # type: ignore[import-not-found]

try:
    from ..data.genre import (
        ENTITY_COUNT_KEY,
        SCENE_NODE_SLOTS,
        SET_ALL_FIELDS_KEY,
        GenrePack,
    )
    from ..engine.scene import generate_scene, scene_json_text
    from .readout import scene_readout
    from .scene_entity import NODE_CATEGORY, SceneEntitySocket
    from .widgets import build_inputs, read_controls, read_widgets
except ImportError:  # pragma: no cover -- standalone/test context
    from data.genre import (
        ENTITY_COUNT_KEY,
        SCENE_NODE_SLOTS,
        SET_ALL_FIELDS_KEY,
        GenrePack,
    )
    from engine.scene import generate_scene, scene_json_text
    from nodes.readout import scene_readout
    from nodes.scene_entity import NODE_CATEGORY, SceneEntitySocket
    from nodes.widgets import build_inputs, read_controls, read_widgets

#: How many entity slots a scene carries. Slot 1 is described in full; slots
#: 2-4 are brief unless a Scene Entity is wired into them. Taken from the
#: contract so the sockets, the widgets and the constraint address space can
#: never disagree about how many slots exist.
SCENE_SLOTS = SCENE_NODE_SLOTS


def entity_socket_key(slot: int) -> str:
    """The optional ``SCENE_ENTITY`` input for a slot: ``entity_2_in``."""
    return f"entity_{slot}_in"


def _entity_sockets() -> list[Any]:
    return [
        SceneEntitySocket.Input(
            entity_socket_key(slot),
            display_name=entity_socket_key(slot),
            optional=True,
            tooltip=(
                f"Optional. A Scene Entity wired here describes slot {slot}, "
                "replacing that slot's own descriptive widgets and giving it the top "
                "allowance for the scene. It is a promotion, not an exemption: how "
                "much the slot speaks is still capped by what kind of thing it is, "
                "so a station reads shorter than a creature. A field you locked on "
                "the Scene Entity is a choice: it wins over these widgets and over a "
                "coherence rule, and the rule's reason is reported in "
                "prompt_json._meta. A field the Scene Entity drew at random is a draw: "
                "this scene first picks a place that can hold the whole wired subject, "
                "and re-draws a drawn field only when no place can -- the node face then "
                "names what was re-drawn. What the entity is *doing* stays "
                "this node's: situation and relations are never taken from a wired "
                "entity."
            ),
        )
        for slot in range(1, SCENE_SLOTS + 1)
    ]


def build_scene_node(pack: GenrePack) -> type:
    """Generate the ``Scene Weaver`` node class for ``pack``."""

    class SceneWeaver(io.ComfyNode):  # type: ignore[misc, valid-type]
        """Randomize a whole scene: setting, entities and how they relate."""

        @classmethod
        def define_schema(cls) -> "io.Schema":
            return io.Schema(
                node_id=f"SceneWeaver{pack.class_suffix}",
                display_name=f"Scene Weaver - {pack.display}",
                category=NODE_CATEGORY,
                description=(
                    f"Randomize a whole {pack.display} scene in one click: an "
                    f"environment, up to {SCENE_SLOTS} entities and the relationships "
                    "between them, as natural-language prose plus structured JSON. "
                    "Set 'Entities' to reveal and fill more subject slots. Every "
                    "field can be locked to a value or set to None. Wire prompt_text "
                    "into a Show Text node to read the prompt."
                ),
                inputs=[*build_inputs(pack, SCENE_SLOTS), *_entity_sockets()],
                outputs=[
                    io.String.Output(
                        display_name="prompt_text",
                        tooltip="The prompt. Wire this into the text encoder.",
                    ),
                    # A prompt_json wired into the encoder rendered the JSON
                    # itself as the prompt; the tooltip says what it is for.
                    io.String.Output(
                        display_name="prompt_json",
                        tooltip="Structured scene data for other nodes or logs. "
                        "Not a prompt: do not wire it into a text encoder.",
                    ),
                ],
            )

        @classmethod
        def fingerprint_inputs(cls, **kwargs: Any) -> float:
            # See the identical note on the Scene Entity node: ComfyUI #11905.
            return float("nan")

        @classmethod
        def execute(cls, **kwargs: Any) -> "io.NodeOutput":
            controls = read_controls(pack, SCENE_SLOTS, kwargs)
            text, document = generate_scene(
                int(controls["seed"]),
                pack,
                widgets=read_widgets(pack, SCENE_SLOTS, kwargs),
                wired_entities=_wired_entities(kwargs),
                scene_filter=controls["scene_filter"],
                set_all_fields=controls[SET_ALL_FIELDS_KEY],
                entity_count=int(controls[ENTITY_COUNT_KEY]),
                slots=SCENE_SLOTS,
            )
            # See the note on the Scene Entity node: the readout describes the
            # scene that was generated, not the widgets that asked for it.
            return io.NodeOutput(
                text,
                scene_json_text(document),
                ui={"text": scene_readout(document, text)},
            )

    SceneWeaver.__name__ = f"SceneWeaver{pack.class_suffix}"
    SceneWeaver.__qualname__ = SceneWeaver.__name__
    return SceneWeaver


def _wired_entities(kwargs: Mapping[str, Any]) -> dict[int, Mapping[str, Any]]:
    """Collect the connected ``SCENE_ENTITY`` payloads, keyed by slot.

    Raises rather than skipping on a payload of the wrong shape. The socket type
    already makes a miswire hard, so anything that reaches here is a genuine
    defect somewhere upstream, and quietly generating a scene with that slot
    unwired would hide it behind a plausible-looking result.
    """
    wired: dict[int, Mapping[str, Any]] = {}
    for slot in range(1, SCENE_SLOTS + 1):
        payload = kwargs.get(entity_socket_key(slot))
        if payload is None:
            continue
        if not isinstance(payload, Mapping):
            raise ValueError(
                f"{entity_socket_key(slot)} expects a SCENE_ENTITY payload "
                f"(a mapping), got {type(payload).__name__}"
            )
        wired[slot] = payload
    return wired
