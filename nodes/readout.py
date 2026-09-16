"""The lines a node draws in its own footer after it runs.

Built here, in Python, rather than in the frontend, for one reason: this is the
only place the *resolved* scene exists. The frontend can see what the widgets
say, which is not the same thing -- a widget saying "Random" tells you nothing
about what was drawn, and a slot promoted by a wire is not described by its
widgets at all. A readout assembled from widget values would be a plausible
summary of the wrong scene.

Deliberately short. It is drawn **inside** the node, in a reserved footer strip:
what is in the scene on the first line, how it was generated on the second. It
used to be painted on the canvas below the node, where it floated over whatever
happened to be there and read as a stray label rather than as part of the node.

It is a summary, not the prompt. The prompt goes to ``prompt_text`` and belongs
in a Show Text node, which is where a ComfyUI user already looks for generated
text; a node face is for the controls and for enough feedback to tell whether
the last run did what you wanted.
"""
from __future__ import annotations

from typing import Any, Mapping

try:
    from ..data.genre import SITUATION_FIELD
    from ..engine.budget import count_tokens
except ImportError:  # pragma: no cover -- standalone/test context
    from data.genre import SITUATION_FIELD
    from engine.budget import count_tokens

__all__ = ["LINE_LIMIT", "entity_readout", "scene_readout"]

#: Characters per line before eliding. Sized for a default-width node at 100%
#: zoom; the frontend clips rather than wrapping, so a longer line would simply
#: run off into the canvas.
LINE_LIMIT = 72


def _clip(text: str, limit: int = LINE_LIMIT) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "..."


def _plural(count: int, noun: str, plural: str | None = None) -> str:
    return f"{count} {noun if count == 1 else (plural or noun + 's')}"


def scene_readout(document: Mapping[str, Any], prompt: str = "") -> list[str]:
    """Two lines, plus a third when there is a warning, summarising a document.

    ``prompt`` is the rendered ``prompt_text``. Its approximate token count is
    the one number a user cannot get by looking at the node, and the one that
    tells them whether the scene they just built is going to render as a
    picture or as a mush -- so it goes on the face rather than in the JSON.
    """
    meta = document.get("_meta") or {}
    entities = document.get("entities") or []

    parts = [document.get("environment") or "no setting"]
    parts.extend(
        entity.get("subkind") or entity.get("kind") or "?" for entity in entities
    )
    first = _clip(" | ".join(parts))

    stats = [
        str(meta.get("filter_applied", "")),
        _plural(len(entities), "entity", "entities"),
        _plural(len(document.get("relations") or []), "relation"),
    ]
    wired = sum(1 for entity in entities if entity.get("source") == "wired")
    if wired:
        stats.append(f"{wired} wired")
    if prompt:
        stats.append(f"{count_tokens(prompt)} tok")
    warnings = list(meta.get("warnings") or ())
    if warnings:
        # Surfaced on the face because every warning this pack raises is a
        # precedence decision the user did not explicitly make -- a wire beating
        # a locked widget, or a lock beating a rule. Silent is the wrong default
        # for "something you asked for was overruled".
        stats.append(_plural(len(warnings), "warning"))
    lines = [first, _clip(" | ".join(part for part in stats if part))]
    redrawn = meta.get("redrawn_fields") or {}
    if warnings:
        # The first warning's own words, on a line of their own: a count says a
        # decision happened, the sentence says which one.
        more = f" (+{len(warnings) - 1} more)" if len(warnings) > 1 else ""
        lines.append(_clip(f"{warnings[0]}{more}"))
    elif redrawn:
        # Not a warning: nobody chose the value. But the Entity node showed it, so
        # the user learns why the image differs from that node's preview.
        slot, names = sorted(redrawn.items())[0]
        lines.append(_clip(f"slot {slot} re-drawn to fit: {', '.join(names)}"))
    return lines


def entity_readout(payload: Mapping[str, Any]) -> list[str]:
    """Two lines summarising a ``SCENE_ENTITY`` payload."""
    fields = payload.get("fields") or {}
    named = [
        value
        for value in (fields.get("subkind"), fields.get("kind"), fields.get("form"))
        if value
    ]
    first = _clip(" | ".join(named)) if named else "omitted"

    described = sum(
        1 for name, value in fields.items() if name != SITUATION_FIELD and value
    )
    return [first, f"{described} of {len(fields)} fields described"]
