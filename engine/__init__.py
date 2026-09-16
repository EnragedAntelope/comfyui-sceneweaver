"""Pure generation logic -- no ComfyUI imports, no genre knowledge.

Four layers, bottom up:

``grammar``     articles, plurals and count phrases. Strings in, strings out.
``resolution``  the frozen ``ResolvedScene`` types. ``None`` means unspoken, and
                there is no third state.
``prose``       a resolved scene rendered through ``pack.prose``.
``budget``      how much of each entity is allowed to reach the prompt.
``scene``       ``generate_scene`` -- the seven-step pipeline that ties the rest
                together and is what both node classes call.

Everything here must stay importable without ``comfy_api`` so the engine is
testable outside a running ComfyUI, and must never name a genre --
``tests/test_genre_contract.py`` greps this package and fails if one appears.
"""
from __future__ import annotations

from .budget import (
    ALLOWANCE_BY_COUNT,
    MAX_ALLOWANCE,
    TOKEN_CEILING,
    allowance_for,
    apply_budget,
    count_tokens,
)
from .grammar import (
    article_for,
    count_phrase,
    head_noun,
    is_singular_count,
    join_clauses,
    pluralize,
    with_article,
    with_article_if_singular,
)
from .prose import entity_reference, render_entity, render_prose
from .resolution import ResolvedEntity, ResolvedRelation, ResolvedScene
from .scene import (
    ENTITY_PAYLOAD_VERSION,
    JSON_SCHEMA_VERSION,
    MAX_CONSTRAINT_PASSES,
    SOURCE_WIDGETS,
    SOURCE_WIRED,
    entity_payload,
    generate_entity,
    generate_scene,
    scene_json_text,
)

__all__ = [
    "ENTITY_PAYLOAD_VERSION",
    "ALLOWANCE_BY_COUNT",
    "MAX_ALLOWANCE",
    "allowance_for",
    "JSON_SCHEMA_VERSION",
    "MAX_CONSTRAINT_PASSES",
    "SOURCE_WIDGETS",
    "SOURCE_WIRED",
    "TOKEN_CEILING",
    "ResolvedEntity",
    "ResolvedRelation",
    "ResolvedScene",
    "apply_budget",
    "article_for",
    "count_phrase",
    "count_tokens",
    "entity_payload",
    "entity_reference",
    "generate_entity",
    "generate_scene",
    "head_noun",
    "is_singular_count",
    "join_clauses",
    "pluralize",
    "render_entity",
    "render_prose",
    "scene_json_text",
    "with_article",
    "with_article_if_singular",
]
