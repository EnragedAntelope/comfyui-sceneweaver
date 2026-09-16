"""Turning a ``GenrePack``'s ``FieldDef``s into ComfyUI V3 inputs.

Both node classes register their widgets through this module and neither
hand-writes a field list. That is the genre seam at its narrowest point: a
second genre is a data module, because nothing here knows what a genre contains
-- only that a pack has field definitions and declares the order they appear in.

**The invariant this module exists to hold.** A saved workflow's
``widgets_values`` is a positional array: ComfyUI writes widget values out in
node-widget order and reads them back the same way, by index, with no names
involved. So the order emitted here is a compatibility surface, and it is taken
from exactly one place -- ``data.genre.widget_order`` -- rather than being
rebuilt by whichever loop happens to run. Appending a widget at the end is safe;
inserting or reordering one silently reassigns every value after it in every
graph anyone has ever saved. The frontend may rewrite a widget's *label* and its
*value*; it must never touch the order.
"""
from __future__ import annotations

from typing import Any, Mapping

from comfy_api.latest import io  # type: ignore[import-not-found]

try:
    from ..data.genre import (
        SEED_CONTROL_AFTER_GENERATE,
        SEED_MAX,
        SEED_MIN,
        SET_ALL_FIELDS_KEY,
        SET_ALL_FIELDS_LABEL,
        SET_ALL_FIELDS_TOOLTIP,
        SET_ALL_OFF,
        SET_ALL_OPTIONS,
        FieldDef,
        GenrePack,
        build_field_definitions,
        field_tooltip,
        widget_choices,
        widget_label,
        widget_order,
    )
except ImportError:  # pragma: no cover -- standalone/test context
    from data.genre import (
        SEED_CONTROL_AFTER_GENERATE,
        SEED_MAX,
        SEED_MIN,
        SET_ALL_FIELDS_KEY,
        SET_ALL_FIELDS_LABEL,
        SET_ALL_FIELDS_TOOLTIP,
        SET_ALL_OFF,
        SET_ALL_OPTIONS,
        FieldDef,
        GenrePack,
        build_field_definitions,
        field_tooltip,
        widget_choices,
        widget_label,
        widget_order,
    )

__all__ = [
    "build_inputs",
    "read_controls",
    "read_widgets",
]


def _widget_input(definition: FieldDef, slots: int) -> Any:
    """One ``FieldDef`` as the input ComfyUI registers it with.

    ``display_name`` carries the pack's *generic* label, plus the slot or
    endpoint qualifier that tells four identical "Kind" widgets apart. The
    per-kind label ("Engine count" on a vessel, "Eye count" on a creature) is
    applied by the frontend, because a widget's label is fixed at registration
    while the kind is not.
    """
    if definition.widget == "int":
        return io.Int.Input(
            definition.key,
            display_name=widget_label(definition, slots),
            default=definition.default,
            min=SEED_MIN,
            max=SEED_MAX,
            control_after_generate=SEED_CONTROL_AFTER_GENERATE,
            tooltip=field_tooltip(definition),
        )
    return io.Combo.Input(
        definition.key,
        options=list(widget_choices(definition)),
        display_name=widget_label(definition, slots),
        default=definition.default,
        tooltip=field_tooltip(definition),
    )


def _set_all_input() -> Any:
    """The bulk-edit control.

    Deliberately not a ``FieldDef``: it has no pool, no group, no content tag and
    no presence in ``prompt_json``, so most of that contract would be meaningless
    for it. Its *position* is pinned all the same, by ``widget_order``.
    """
    return io.Combo.Input(
        SET_ALL_FIELDS_KEY,
        options=list(SET_ALL_OPTIONS),
        display_name=SET_ALL_FIELDS_LABEL,
        default=SET_ALL_OFF,
        tooltip=SET_ALL_FIELDS_TOOLTIP,
    )



def build_inputs(pack: GenrePack, slots: int) -> list[Any]:
    """Every widget input for a node, in ``widget_order``.

    Link-only sockets are the caller's business and are appended after these --
    they carry no widget, so they contribute nothing to ``widgets_values`` and
    cannot disturb what is here.
    """
    definitions = build_field_definitions(pack, slots)
    inputs: list[Any] = []
    for key in widget_order(pack, slots):
        if key == SET_ALL_FIELDS_KEY:
            inputs.append(_set_all_input())
            continue
        inputs.append(_widget_input(definitions[key], slots))
    return inputs


def read_widgets(
    pack: GenrePack, slots: int, kwargs: Mapping[str, Any]
) -> dict[str, Any]:
    """The descriptive widget mapping ``generate_*`` takes, pulled from kwargs.

    Controls are excluded because they are read separately and are not fields --
    a control has no pool to draw from and never appears in a description. A key
    ComfyUI did not send falls back to the widget's registered default, so an
    older saved workflow missing a later-added widget still generates rather than
    raising.
    """
    definitions = build_field_definitions(pack, slots)
    return {
        key: kwargs.get(key, definition.default)
        for key, definition in definitions.items()
        if not definition.control
    }


def read_controls(
    pack: GenrePack, slots: int, kwargs: Mapping[str, Any]
) -> dict[str, Any]:
    """The control widgets, same fallback-to-default rule as ``read_widgets``."""
    definitions = build_field_definitions(pack, slots)
    controls = {
        key: kwargs.get(key, definition.default)
        for key, definition in definitions.items()
        if definition.control
    }
    if SET_ALL_FIELDS_KEY in widget_order(pack, slots):
        controls[SET_ALL_FIELDS_KEY] = kwargs.get(SET_ALL_FIELDS_KEY, SET_ALL_OFF)
    return controls
