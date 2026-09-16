"""What ``js/sceneweaver.js`` needs from a pack, and the route that serves it.

**Why a route and not a generated .js file.** The frontend has to know three
things a widget cannot carry: the per-kind label for every field, the kind-scoped
subset of every pool, and which widgets a given ``kind`` control scopes. All
three live in the pack. Baking them into a committed JavaScript file would work
until the first ``user_options.json`` merge (Todo 23), which adds pool values at
*import* time -- a generated file would then be wrong on exactly the machine that
customised it, silently, and only for the frontend. Serving the live pack cannot
drift from it.

Genre-free, like everything else under ``nodes/``: the caller supplies which
packs are registered under which node ids.

The payload is descriptive only. It never tells the frontend a widget's
*position*, because position comes from the schema ComfyUI already built, and a
second source for it is a second thing that can disagree.
"""
from __future__ import annotations

import logging
from typing import Any, Mapping

try:
    from ..data.genre import (
        ENTITY_COUNT_KEY,
        ENTITY_NODE_SLOTS,
        KIND_FIELD,
        NONE,
        POOL_DEFAULT_KEY,
        RANDOM,
        SET_ALL_FIELDS_KEY,
        SET_ALL_OFF,
        SET_ALL_CLEAR,
        SET_ALL_RANDOMIZE,
        SITUATION_FIELD,
        GenrePack,
        build_field_definitions,
        label_qualifier,
        widget_choices,
        widget_order,
    )
except ImportError:  # pragma: no cover -- standalone/test context
    from data.genre import (
        ENTITY_COUNT_KEY,
        ENTITY_NODE_SLOTS,
        KIND_FIELD,
        NONE,
        POOL_DEFAULT_KEY,
        RANDOM,
        SET_ALL_FIELDS_KEY,
        SET_ALL_OFF,
        SET_ALL_CLEAR,
        SET_ALL_RANDOMIZE,
        SITUATION_FIELD,
        GenrePack,
        build_field_definitions,
        label_qualifier,
        widget_choices,
        widget_order,
    )

__all__ = ["FRONTEND_ROUTE", "frontend_payload", "node_payload", "register_routes"]

_LOG = logging.getLogger(__name__)

#: Where ``js/sceneweaver.js`` fetches the payload from.
FRONTEND_ROUTE = "/sceneweaver/fields"

_ROLE_SCENE = "scene"
_ROLE_ENTITY = "entity"


def _pools(pack: GenrePack, names: "set[str]") -> dict[str, dict[str, list[str]]]:
    """The kind-scoped pools, as the frontend reads them.

    Shipped once per *field* rather than once per widget: four slots share one
    ``kind`` pool and repeating it four times would quadruple the payload for
    nothing.
    """
    return {
        name: {kind: list(values) for kind, values in pack.pools[name].items()}
        for name in sorted(names)
        if name in pack.pools
    }


def node_payload(pack: GenrePack, slots: int) -> dict[str, Any]:
    """Everything one node class's frontend needs, keyed by *widget* key."""
    definitions = build_field_definitions(pack, slots)
    order = widget_order(pack, slots)

    fields: dict[str, Any] = {}
    kind_widgets: dict[str, list[str]] = {}
    choices: dict[str, list[str]] = {}
    pooled: set[str] = set()

    for key, definition in definitions.items():
        if definition.control:
            continue
        fields[key] = {
            "base": definition.base,
            "slot": definition.slot,
            "endpoints": definition.endpoints,
            "group": definition.group,
            # The generic label and its qualifier travel separately: the
            # frontend swaps the label per kind and would otherwise have to
            # parse " 2" back off the end to do it.
            "label": definition.label,
            "qualifier": label_qualifier(definition, slots),
            "kind_scoped": definition.kind_scoped,
            "scope": list(definition.scope),
        }
        pooled.add(definition.base)
        # Keyed by field, not by widget: four slots register the identical
        # option list for `kind`, and shipping it four times would be four
        # chances for one copy to be read while another was meant.
        choices.setdefault(definition.base, list(widget_choices(definition)))

    # Which widgets each `kind` control scopes. Built from the slot each widget
    # belongs to rather than from a name pattern, so a pack that keys its slots
    # differently still gets this right.
    for key, definition in definitions.items():
        if definition.control or definition.base != KIND_FIELD:
            continue
        kind_widgets[key] = [
            other.key
            for other in definitions.values()
            if not other.control
            and other.slot == definition.slot
            and other.key != key
        ]

    # Which widgets each scope control narrows. Built like ``kind_widgets`` --
    # from the slot each widget belongs to, never from a name pattern -- but keyed
    # by every control (kind, subkind, the count nouns, environment), not just kind.
    scope_widgets: dict[str, list[str]] = {}
    control_bases = {c for spec in pack.entity_fields.values() for c in spec.scope}
    control_bases |= {c for spec in pack.scene_fields.values() for c in spec.scope}
    for key, definition in definitions.items():
        if definition.base not in control_bases:
            continue
        dependents = [
            other.key
            for other in definitions.values()
            if not other.control
            and other.key != key
            and definition.base in other.scope
            and (definition.slot is None or other.slot == definition.slot)
        ]
        if dependents:
            scope_widgets[key] = dependents

    payload: dict[str, Any] = {
        "genre": pack.slug,
        "display": pack.display,
        "role": _ROLE_ENTITY if slots == ENTITY_NODE_SLOTS else _ROLE_SCENE,
        "kind_field": KIND_FIELD,
        # Named, not inferred. The frontend mirrors the engine's occupancy rule
        # and needs to know which widget carries the count and which field the
        # scene keeps owning on a wired slot.
        "entity_count_key": ENTITY_COUNT_KEY if ENTITY_COUNT_KEY in order else None,
        "situation_field": SITUATION_FIELD,
        "random": RANDOM,
        "none": NONE,
        "default_key": POOL_DEFAULT_KEY,
        "order": list(order),
        "fields": fields,
        "choices": choices,
        "kind_widgets": kind_widgets,
        "scope_widgets": scope_widgets,
        "pool_groups": {
            control: {group: list(values) for group, values in groups.items()}
            for control, groups in sorted(pack.pool_groups.items())
        },
        "labels": {
            name: dict(per_kind) for name, per_kind in sorted(pack.labels.items())
        },
        "pools": _pools(pack, pooled),
    }
    if SET_ALL_FIELDS_KEY in order:
        payload["set_all"] = {
            "key": SET_ALL_FIELDS_KEY,
            "off": SET_ALL_OFF,
            # Named rather than positional, so the frontend never infers a
            # direction from an option index.
            "clear": SET_ALL_CLEAR,
            "randomize": SET_ALL_RANDOMIZE,
        }
    return payload


def frontend_payload(specs: Mapping[str, tuple[GenrePack, int]]) -> dict[str, Any]:
    """The whole route body: ``{"nodes": {node_id: <node payload>}}``.

    Keyed by node id because that is what ``beforeRegisterNodeDef`` is handed --
    the frontend never has to know a genre's name to find its data, which is the
    same seam the node classes are built on.
    """
    return {
        "nodes": {
            node_id: node_payload(pack, slots)
            for node_id, (pack, slots) in specs.items()
        }
    }


def register_routes(specs: Mapping[str, tuple[GenrePack, int]]) -> bool:
    """Register the read-only fields route, if a ComfyUI server is present.

    Returns whether it was registered. A missing server is the normal case
    outside ComfyUI (tests, a bare import) and must never stop the nodes loading,
    so the failure is logged and swallowed -- the frontend then falls back to
    generic labels and the unnarrowed option lists, which is degraded but not
    broken.
    """
    try:
        from aiohttp import web
        from server import PromptServer  # type: ignore[import-not-found]
    except Exception as exc:  # noqa: BLE001 -- never block node registration
        _LOG.info("fields route not registered (no ComfyUI server): %s", exc)
        return False

    body = frontend_payload(specs)

    @PromptServer.instance.routes.get(FRONTEND_ROUTE)
    async def _fields(_request):  # type: ignore[no-untyped-def]  # pragma: no cover
        return web.json_response(body)

    return True
