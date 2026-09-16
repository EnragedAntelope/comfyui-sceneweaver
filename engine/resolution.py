"""What a resolved scene looks like once every field has a value or a ``None``.

The handoff between generation (Todo 16) and everything that reads a scene: the
prose renderer, the ``prompt_json`` builder, and the tests. Frozen dataclasses
rather than raw dicts, so a typo in a field name is an ``AttributeError`` at the
call site instead of a silent ``None`` three layers down.

One invariant runs through the whole file and is the reason it exists:

    **A field is ``None`` here if and only if it is unspoken.**

There is no third state. A value that was drawn and then dropped by the detail
budget is written back to ``None`` before it ever reaches this structure, so
``prompt_json`` and ``prompt_text`` can never disagree about what the scene
contains. "Resolved but not voiced" is the bug class
``identity-forge-dead-widget-check`` names, and this type is where it is made
unrepresentable rather than merely avoided.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping

__all__ = ["ResolvedEntity", "ResolvedRelation", "ResolvedScene"]


@dataclass(frozen=True)
class ResolvedEntity:
    """One occupied slot.

    An unoccupied slot is simply absent from ``ResolvedScene.entities`` -- it is
    not a ``ResolvedEntity`` whose fields are all ``None``. Omitting a slot and
    describing an empty one are different scenes, and only the first is a thing
    a user can ask for.
    """

    #: 1-based slot number, kept so ``prompt_json`` and the relations can name it.
    index: int
    #: ``"widgets"`` or ``"wired"`` -- whether the description came from this
    #: node's own widgets or from a Scene Entity plugged into the slot.
    source: str
    #: Slug of the pack the *description* came from. Usually the scene's own, but
    #: a foreign-genre entity wired into a slot keeps its own: a crashed
    #: starship in an enchanted forest stays traceable to the pack that built it.
    genre: str
    #: Every entity field of the scene's pack, each a value or ``None``.
    fields: Mapping[str, str | None] = field(default_factory=dict)
    #: What it is doing. Scene-owned even for a wired entity -- the Scene Weaver
    #: decides what happens, the Scene Entity only decides what a thing is.
    situation: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "fields", MappingProxyType(dict(self.fields)))

    @property
    def kind(self) -> str | None:
        """The control value every other pool and label on this slot is scoped by."""
        return self.fields.get("kind")

    def get(self, name: str) -> str | None:
        """The value of one field, or ``None`` when it is unspoken."""
        return self.fields.get(name)


@dataclass(frozen=True)
class ResolvedRelation:
    """A rendered relationship between two occupied slots.

    A relation only reaches this type when **both** endpoints are occupied, so
    the renderer never has to guard against half a relation. A relation whose
    partner slot was set to None is dropped during resolution, not here.
    """

    endpoints: tuple[int, int]
    value: str
    #: Spatial framing of the relation, or ``None``. Never rendered without a
    #: ``value`` -- a bare position ("from behind") with no action names nothing.
    position: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "endpoints", tuple(self.endpoints))


@dataclass(frozen=True)
class ResolvedScene:
    """A whole scene, ready to render or serialize."""

    environment: str | None = None
    #: What else is in the shot -- a secondary, architectural detail drawn once
    #: per scene and spoken after the entities. ``None`` emits nothing.
    context: str | None = None
    #: Which context sentence pattern the scene drew, or ``None``. The choice is
    #: made where the RNG lives (``engine.scene``) because the renderer is pure.
    context_sentence_index: int | None = None
    #: Occupied slots only, in slot order.
    entities: tuple[ResolvedEntity, ...] = ()
    relations: tuple[ResolvedRelation, ...] = ()
    #: Provenance for ``prompt_json._meta``: seed, genre, filter, warnings. Not
    #: description -- nothing here is ever rendered into ``prompt_text``, which
    #: is what keeps a constraint's ``reason`` string (the pack's one deliberate
    #: exemption from never-negate) out of the prompt.
    meta: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "entities", tuple(self.entities))
        object.__setattr__(self, "relations", tuple(self.relations))
        object.__setattr__(self, "meta", MappingProxyType(dict(self.meta)))

    def entity(self, index: int) -> ResolvedEntity | None:
        """The entity in slot ``index``, or ``None`` if the slot is empty."""
        for candidate in self.entities:
            if candidate.index == index:
                return candidate
        return None
