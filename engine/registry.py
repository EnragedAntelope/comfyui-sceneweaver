"""The packs this process has seen, by slug.

A ``SCENE_ENTITY`` payload names the genre that built it. When a scene of one
genre receives an entity of another, the scene needs the *guest* pack to speak
the entity, place it and give it something to do -- the host pack has never
heard of a harpy. Every ``generate_scene``/``generate_entity`` call registers
the pack it was given, so whichever pack built a payload is known to whichever
pack receives it, without the engine ever naming a genre.
"""
from __future__ import annotations

try:
    from ..data.genre import GenrePack
except ImportError:  # pragma: no cover -- standalone/test context
    from data.genre import GenrePack

_PACKS: dict[str, GenrePack] = {}


def register_pack(pack: GenrePack) -> None:
    """Remember ``pack`` under its slug; the most recent registration wins."""
    _PACKS[pack.slug] = pack


def registered_pack(slug: "str | None") -> "GenrePack | None":
    """The pack registered under ``slug``, or ``None``."""
    return _PACKS.get(slug) if slug else None
