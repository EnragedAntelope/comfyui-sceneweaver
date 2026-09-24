"""``generate_scene`` -- the seven-step pipeline that turns a seed into a scene.

Pure and genre-blind. Everything it knows about a genre it was handed in a
``GenrePack``; everything it knows about the user it was handed in a widget
mapping. Given the same arguments it returns the same two values, which is the
whole of the "same seed reproduces the same scene" guarantee.

The pipeline, in order, and why the order is the order:

1. ``rng = random.Random(seed)`` -- one generator, consumed in a fixed
   traversal, so the scene is a pure function of the seed.
2. **``set_all_fields``** -- the bulk edit. It rewrites widgets that say
   "Random" or "None"; it never touches one holding a literal value, because
   that is a lock and a bulk control must not silently undo a deliberate choice.
3. **Merge wired entities.** A Scene Entity plugged into a slot replaces that
   slot's *descriptive* fields. The slot's ``situation`` and its relations stay
   the scene's, because the scene node owns what happens and the entity node
   only owns what a thing is.
4. **The ``scene_filter`` pre-pass** masks tagged pools *before* any draw, so
   "Peaceful" yields a ship with no weapons described rather than one described
   as unarmed. Masking after the draw would mean choosing a weapon and then
   talking around it.
5. **Resolve** every field from its kind-scoped, filter-masked pool. ``kind``
   resolves first on each slot because it scopes every other pool on it.
6. **Constraints** to a fixed point, capped at ``MAX_CONSTRAINT_PASSES``. The
   pre-pass does not count toward the cap -- it is not iteration, it is a pool
   mask.
7. **The detail budget**, last, because it can only cut what has been drawn.

**Three precedence rules, written down here because each is surprising if you
meet it by accident.**

*A wired entity beats a locked slot widget.* Wiring a whole node into a slot is
a more explicit statement than choosing a value from that slot's dropdown, and
the alternative -- a widget quietly overriding the node the user visibly
connected -- is worse. Every field it overrides is named in
``_meta.overridden_fields`` and logged at WARNING, so it is reported rather than
discovered.

*A wired value the user chose beats a constraint rule; a wired value the node
drew does not.* A field locked on the Scene Entity is an explicit choice, so it
wins and the rule's ``reason`` is reported. A field the Entity node drew at
random is not a choice -- it is a draw -- so it stays an ordinary resolved
value and the scene re-draws it when the place cannot hold it. Treating every
wired field as a lock is what let a walker be drawn in vacuum and a torus rest
on its ring.

*A reason is warning text, never description.* ``prompt_text`` never negates: a
rule's ``reason`` is the pack's one deliberate exemption from that rule, and it
is spoken only to ``_meta.warnings``.
"""
from __future__ import annotations

import dataclasses
import json
import logging
import random
from typing import Any, Callable, Iterable, Mapping

try:
    from ..data.genre import (
        CONTEXT_FIELD,
        DEFAULT_SCENE_FILTER,
        ENTITY_NODE_SLOTS,
        ENVIRONMENT_FIELD,
        KIND_FIELD,
        LONE_ENTITY_SLOT,
        NONE,
        RANDOM,
        RELATION_FIELD,
        RELATION_ANY,
        RULE_EXCLUDE,
        RULE_REQUIRE,
        SCENE_NODE_SLOTS,
        SET_ALL_CLEAR,
        SET_ALL_OFF,
        SET_ALL_OPTIONS,
        SITUATION_FIELD,
        STANCE_FIELD,
        Archetype,
        FieldDef,
        GenrePack,
        bind_address,
        canonical_scene_filter,
        build_field_definitions,
        archetype_for,
        affordances_of,
        spoken_value,
        archetype_name_for,
        build_resolution_definitions,
        filtered_pool,
        form_can_stand,
        is_slot_wildcard,
        pool_for,
        pool_options,
        relation_key,
        relation_position_key,
        relation_pairs,
        RELATION_ANY_POSITION,
        SECOND_ENDPOINT,
        FIRST_ENDPOINT,
        slot_key,
        slot_path,
        type_feasible,
        type_field,
    )
except ImportError:  # pragma: no cover -- standalone/test context
    from data.genre import (
        CONTEXT_FIELD,
        DEFAULT_SCENE_FILTER,
        ENTITY_NODE_SLOTS,
        ENVIRONMENT_FIELD,
        KIND_FIELD,
        LONE_ENTITY_SLOT,
        NONE,
        RANDOM,
        RELATION_FIELD,
        RELATION_ANY,
        RULE_EXCLUDE,
        RULE_REQUIRE,
        SCENE_NODE_SLOTS,
        SET_ALL_CLEAR,
        SET_ALL_OFF,
        SET_ALL_OPTIONS,
        SITUATION_FIELD,
        STANCE_FIELD,
        Archetype,
        FieldDef,
        GenrePack,
        bind_address,
        canonical_scene_filter,
        build_field_definitions,
        archetype_for,
        affordances_of,
        spoken_value,
        archetype_name_for,
        build_resolution_definitions,
        filtered_pool,
        form_can_stand,
        is_slot_wildcard,
        pool_for,
        pool_options,
        relation_key,
        relation_position_key,
        relation_pairs,
        FIRST_ENDPOINT,
        SECOND_ENDPOINT,
        RELATION_ANY_POSITION,
        slot_key,
        slot_path,
        type_feasible,
        type_field,
    )

from .budget import allowance_for, apply_budget
from .foreign import (
    guest_fits_place,
    guest_pack,
    guest_situation,
    mask_for_filter,
    mask_for_place,
    voice_of,
)
from .prose import head_phrase_spec, render_prose
from .registry import register_pack
from .grammar import head_noun
from .resolution import ResolvedEntity, ResolvedRelation, ResolvedScene

__all__ = [
    "ENTITY_PAYLOAD_VERSION",
    "JSON_SCHEMA_VERSION",
    "DEFAULT_ENTITY_COUNT",
    "MAX_CONSTRAINT_PASSES",
    "SOURCE_WIDGETS",
    "SOURCE_WIRED",
    "entity_payload",
    "generate_entity",
    "generate_scene",
    "scene_json_text",
]

LOGGER = logging.getLogger("sceneweaver")

#: Fixed-point cap for the constraint pass. A rule set can be written so that A
#: excludes B's value and B excludes A's, which oscillates forever; the cap
#: turns that into a deterministic stop plus a warning instead of a hung queue.
#: Identity Forge's precedent, same number.
MAX_CONSTRAINT_PASSES = 12

#: How many subjects an untouched node builds. One, because a scene with one
#: subject is the one a text-to-image model draws best, and because a node that
#: quietly produced four would bury the control that says so.
DEFAULT_ENTITY_COUNT = 1

#: ``prompt_json._meta.schema_version``. Bump when the shape changes, so a
#: downstream consumer can tell. 3 added ``_meta.redrawn_fields``.
JSON_SCHEMA_VERSION = 3

#: ``SCENE_ENTITY`` payload version, independent of the JSON schema: the socket
#: is shared by every genre and outlives any one pack's field list. Bumped to 2
#: when the payload gained ``locked`` -- the base names the user chose, so a
#: receiver can tell a choice from a draw.
ENTITY_PAYLOAD_VERSION = 2

SOURCE_WIDGETS = "widgets"
SOURCE_WIRED = "wired"


# ---------------------------------------------------------------------------
# The SCENE_ENTITY payload
# ---------------------------------------------------------------------------


def entity_payload(
    genre: str,
    fields: Mapping[str, str | None],
    locked: "Iterable[str]" = (),
) -> dict[str, Any]:
    """Build the payload a Scene Entity node hands to a Scene Weaver slot.

    Deliberately a genre tag, a flat field mapping, and the base names the user
    **chose** (``locked``). The socket is shared across genres -- a starship in
    an enchanted forest is a supported feature -- so the payload cannot assume
    the receiving pack knows any particular field.

    ``locked`` is the difference between a value the user picked and one the node
    drew at random: a receiver honours the first as a statement and is free to
    re-draw the second to fit its own place. A payload without the key -- an
    older saved graph, a foreign-genre node -- locks nothing, which is the safe
    direction.
    """
    return {
        "schema_version": ENTITY_PAYLOAD_VERSION,
        "genre": genre,
        "fields": {name: value for name, value in fields.items()},
        "locked": sorted(name for name in locked if fields.get(name) is not None),
    }


def _payload_fields(pack: GenrePack, payload: Mapping[str, Any]) -> dict[str, str | None]:
    """Read a payload through the receiving pack's schema.

    A field the payload does not carry is ``None``; a field the receiving pack
    does not define is dropped. That is what makes the cross-genre path work
    without either pack knowing about the other -- and what makes a
    genre-specific constraint rule simply never fire on a foreign entity rather
    than fight it.
    """
    supplied = payload.get("fields") or {}
    return {name: supplied.get(name) for name in pack.entity_fields}

def _payload_locked(payload: Mapping[str, Any]) -> "frozenset[str]":
    """The base field names a payload reports the user locked.

    A payload with no ``locked`` key -- an older saved graph, or a foreign-genre
    node that does not supply one -- locks nothing. Rules then apply to every
    value, which is the safe direction: re-drawing a draw is never wrong, and
    keeping a value the place forbids always is.
    """
    locked = payload.get("locked")
    if not isinstance(locked, (list, tuple, set, frozenset)):
        return frozenset()
    return frozenset(name for name in locked if isinstance(name, str))


# ---------------------------------------------------------------------------
# Widget reading
# ---------------------------------------------------------------------------


def _apply_set_all(
    definitions: Mapping[str, FieldDef],
    widgets: Mapping[str, Any],
    set_all_fields: str,
) -> dict[str, Any]:
    """Apply the bulk edit, leaving every locked widget exactly as it was.

    Mirrors what the frontend does to the widget values directly, so the engine
    behaves identically when driven headless -- from a test, or from a graph
    saved before the JS shipped.
    """
    if set_all_fields not in SET_ALL_OPTIONS:
        raise ValueError(
            f"unknown set_all_fields {set_all_fields!r}; expected one of {list(SET_ALL_OPTIONS)}"
        )
    resolved = dict(widgets)
    if set_all_fields == SET_ALL_OFF:
        return resolved
    swap_from, swap_to = (
        (RANDOM, NONE) if set_all_fields == SET_ALL_CLEAR else (NONE, RANDOM)
    )
    for key, definition in definitions.items():
        if definition.control:
            continue
        if resolved.get(key, definition.default) == swap_from:
            resolved[key] = swap_to
    return resolved


def _widget_value(definition: FieldDef, widgets: Mapping[str, Any]) -> Any:
    return widgets.get(definition.key, definition.default)


def _is_locked(value: Any) -> bool:
    """A widget holding a literal is a lock; "Random" and "None" are not."""
    return value not in (RANDOM, NONE, None)


# ---------------------------------------------------------------------------
# Drawing
# ---------------------------------------------------------------------------


def _draw(
    rng: random.Random,
    pack: GenrePack,
    definition: FieldDef,
    scope: "Mapping[str, str | None]",
    scene_filter: str,
    banned: "frozenset[str] | set[str]" = frozenset(),
) -> str | None:
    """One seed-stable draw from a field's scope-keyed, filter-masked pool.

    ``scope`` maps each control field in the field's chain to its current value.
    An empty pool resolves to ``None`` and the prose simply says nothing. That
    is a legitimate outcome, not an error: it is exactly what happens to
    ``armament`` under "Peaceful", and what a constraint that excludes a whole
    pool is asking for.
    """
    pool = [
        value
        for value in filtered_pool(pack, definition.base, scope, scene_filter)
        if value not in banned
    ]
    if not pool:
        return None
    weights = pack.weights_for(definition.base)
    # ``omission_weight`` lets a head-phrase modifier -- a word spoken on every
    # entity -- say nothing at all, because a describing word on every entity is
    # a describing word that stops meaning anything. Offered only to a random
    # draw: a locked value never reaches here.
    if definition.omission_weight > 0:
        return rng.choices(
            [*pool, None],
            weights=[
                *(weights.get(value, 1.0) if weights else 1.0 for value in pool),
                definition.omission_weight,
            ],
            k=1,
        )[0]
    if weights:
        return rng.choices(pool, weights=[weights.get(v, 1.0) for v in pool], k=1)[0]
    return rng.choice(pool)


# ---------------------------------------------------------------------------
# One entity, resolved from its own widgets
# ---------------------------------------------------------------------------


def _resolve_entity_fields(
    rng: random.Random,
    pack: GenrePack,
    definitions: Mapping[str, FieldDef],
    widgets: Mapping[str, Any],
    *,
    keyer: "Callable[[str], str]",
    scene_filter: str,
    locked_paths: "set[str]",
    scene_scope: "Mapping[str, str | None]",
) -> tuple[dict[str, str | None], set[str]]:
    """Resolve one entity's whole morphology from its widgets.

    Shared by both node classes, because the *only* difference between them here
    is how a base field name reaches its widget: bare (``kind``) on the Scene
    Entity node, slot-prefixed (``entity2_kind``) on the Scene Weaver. ``keyer``
    is that difference and nothing else is.

    Fields resolve in ``entity_fields`` order -- which is also widget order --
    so every control a field's scope names is already resolved when the field
    is drawn. ``scene_scope`` carries the scene-wide controls (``environment``)
    a field may also scope on. A ``kind`` of ``None`` means the slot is
    *omitted* -- so every other field goes to ``None`` without being drawn at
    all, rather than being drawn and discarded.

    Returns ``(values keyed by base field name, locked base field names)``.
    Locked *paths* are recorded into the caller's set as usual, because the
    constraint pass addresses fields by path.
    """
    values: dict[str, str | None] = {}
    locked: set[str] = set()
    controls = _control_fields(pack)

    kind_def = definitions[keyer(KIND_FIELD)]
    kind_widget = _widget_value(kind_def, widgets)
    kind_value = _resolve_one(
        rng, pack, kind_def, kind_widget, dict(scene_scope), scene_filter, locked_paths,
        banned=_control_values_ruled_out_by_locks(pack, KIND_FIELD, definitions, widgets, keyer),
    )
    values[KIND_FIELD] = kind_value
    if _is_locked(kind_widget):
        locked.add(KIND_FIELD)

    for name in pack.entity_fields:
        if name == KIND_FIELD:
            continue
        if kind_value is None:
            # An omitted slot carries nothing: a slot whose kind is None is left
            # out of the scene, not described as empty.
            values[name] = None
            continue
        # **A supporting slot has fewer widgets, not fewer fields.** The
        # definitions handed in are the *resolution* set, which covers the whole
        # address space; a field with no widget on this slot carries a default
        # of "Random", which is what no instruction means everywhere else here.
        # See ``build_resolution_definitions``.
        definition = definitions[keyer(name)]
        widget = _widget_value(definition, widgets)
        banned = (
            _control_values_ruled_out_by_locks(pack, name, definitions, widgets, keyer)
            if name in controls
            else frozenset()
        )
        scope = {**scene_scope, **values}
        values[name] = _resolve_one(
            rng, pack, definition, widget, scope, scene_filter, locked_paths, banned
        )
        if _is_locked(widget):
            locked.add(name)
    _silence_repeats(
        pack, values, locked,
        rng=rng, definitions=definitions, keyer=keyer,
        scene_filter=scene_filter, scene_scope=scene_scope,
    )
    return values, locked


def _occupied_slots(
    slots: int,
    entity_count: int | None,
    promoted: Mapping[int, Any],
    definitions: Mapping[str, FieldDef],
    widgets: Mapping[str, Any],
) -> "set[int]":
    """The slots this scene fills.

    Three ways a slot is occupied, and they are the pack's precedence order:

    1. it is one of the first ``entity_count`` -- the control's own job;
    2. a Scene Entity is wired into it, which is a more explicit statement than
       any widget and already outranks a locked one;
    3. its ``kind`` widget holds a literal, which is a lock.

    Rule 3 is why the count clamps rather than commands. A user who named a
    subject in a slot has said what they want more precisely than the count
    does, and silently dropping it would be the same defect as a widget quietly
    overriding a wire -- the thing this engine already refuses to do.

    ``entity_count`` of ``None`` means "no opinion": every slot is left to its
    own widget. That is the pre-control behaviour, and what the Scene Entity
    node and every caller without such a control passes.
    """
    if entity_count is None:
        return set(range(1, slots + 1))

    wanted = min(max(int(entity_count), 1), slots)
    occupied = set(range(1, wanted + 1))
    occupied.update(slot for slot in promoted if 1 <= slot <= slots)
    for slot in range(1, slots + 1):
        key = key_for(slot, KIND_FIELD)
        definition = definitions.get(key)
        if definition is None:
            continue
        if _is_locked(widgets.get(key, definition.default)):
            occupied.add(slot)
    return occupied


def _archetype_for(
    pack: GenrePack, values: Mapping[str, str | None]
) -> "Archetype | None":
    """The archetype governing this entity, or ``None``.

    One lookup, so the omit set and the detail cap can never come from two
    different archetypes.
    """
    return archetype_for(pack, values)


def _visible_fields(
    pack: GenrePack, widget_defs: Mapping[str, FieldDef], slot: int
) -> "frozenset[str]":
    """Entity fields this slot draws a widget for.

    Read from the *widget* definitions, deliberately -- the resolution set
    covers every field on every slot, and the whole point of this set is the
    difference between the two.
    """
    return frozenset(
        name for name in pack.entity_fields if slot_key(slot, name) in widget_defs
    )


def _control_fields(pack: GenrePack) -> "frozenset[str]":
    """Every entity control field -- a field that appears in some field's scope."""
    return frozenset(control for spec in pack.entity_fields.values() for control in spec.scope)


def _control_values_ruled_out_by_locks(
    pack: GenrePack,
    control_field: str,
    definitions: Mapping[str, FieldDef],
    widgets: Mapping[str, Any],
    keyer: "Callable[[str], str]",
) -> "frozenset[str]":
    """Values of ``control_field`` that cannot be drawn because a scoped field is locked.

    ``control_field`` scopes some fields, so it is drawn first -- which means a
    value the user locked on one of those fields has not been consulted yet.
    Lock "Form: gas giant shape" while leaving "Subkind" on Random and the
    subkind could come back "gate ring", giving a gate ring shaped like a gas
    giant: the lock is honoured, the draw is legal, and the pair is nonsense.

    So a locked scoped value narrows the control to the values whose pool for
    that field actually contains it. Genre-blind -- it reads the pools rather
    than knowing what any of them mean -- and it only ever *narrows*: if no
    value of the control can hold the lock (a value merged in from user options,
    say), nothing is banned and the previous behaviour stands rather than the
    pool going empty.
    """
    allowed: "set[str] | None" = None
    legal = set(pool_options(pack, control_field))
    for name, spec in pack.entity_fields.items():
        if control_field not in spec.scope:
            continue
        definition = definitions.get(keyer(name))
        if definition is None:
            continue
        value = _widget_value(definition, widgets)
        if not _is_locked(value):
            continue
        holders = {v for v in legal if value in pool_for(pack, name, {control_field: v})}
        if not holders:
            # A lock no value of the control can hold -- a value merged in from
            # user options, say -- constrains nothing rather than emptying the
            # pool.
            continue
        allowed = holders if allowed is None else (allowed & holders)
    if not allowed:
        # No constraining lock, or contradictory locks whose holder sets do not
        # overlap. Ban nothing rather than empty the pool: an entity that
        # vanishes is worse than one built from two explicit, conflicting
        # choices. Mirrors ``_environments_ruled_out_by_fixed_subjects``.
        return frozenset()
    return frozenset(legal - allowed)


def _environments_ruled_out_by_fixed_subjects(
    pack: GenrePack,
    definitions: Mapping[str, FieldDef],
    widgets: Mapping[str, Any],
    promoted: Mapping[int, Mapping[str, Any]],
) -> "frozenset[str]":
    """Environments that cannot hold a subject the scene has already been handed.

    A subject is fixed two ways: a locked kind widget (with that slot's locked type and
    form, when set) and a wired payload, whose drawn values are what the Scene Entity
    node showed. **The place adapts to the subject before the subject adapts to the
    place:** each subject narrows the environments to those that hold its whole
    description, else its kind and type, else its kind. A subject no remaining place
    can hold narrows nothing, and the constraint pass re-draws whatever is not a
    choice. Genre-blind: it reads pools, needs and stances, never what a value means.
    """
    legal = tuple(pool_options(pack, ENVIRONMENT_FIELD))
    known_kinds = set(pool_options(pack, KIND_FIELD))
    name = type_field(pack)
    subjects: list[tuple[Any, Any, Any]] = []
    for definition in definitions.values():
        if definition.base != KIND_FIELD or definition.slot is None:
            continue
        kind = widgets.get(definition.key, definition.default)
        if not _is_locked(kind):
            continue
        subjects.append((
            kind,
            _locked_widget(definitions, widgets, definition.slot, name),
            _locked_widget(definitions, widgets, definition.slot, STANCE_FIELD),
        ))
    guests: list[tuple[GenrePack, dict[str, str | None]]] = []
    for slot in sorted(promoted):
        guest = guest_pack(pack, promoted[slot])
        if guest is not None:
            guests.append((guest, _payload_fields(guest, promoted[slot])))
            continue
        fields = _payload_fields(pack, promoted[slot])
        subjects.append((
            fields.get(KIND_FIELD),
            fields.get(name) if name is not None else None,
            fields.get(STANCE_FIELD),
        ))
    allowed = set(legal)
    # A foreign guest narrows by what the two genres share -- its body's stances
    # and its type's needs, read through the host's words -- since the host's
    # own kind pools have never heard of it.
    for guest, fields in guests:
        for primary_only, strict in ((True, True), (False, True), (False, False)):
            holders = {
                environment for environment in allowed
                if guest_fits_place(
                    guest, pack, fields, environment, primary_only=primary_only, strict=strict
                )
            }
            if holders:
                allowed = holders
                break
    for kind, value, form in subjects:
        if not kind or kind not in known_kinds:
            continue
        for rung_value, rung_form in dict.fromkeys(((value, form), (value, None), (None, None))):
            holders = {
                environment for environment in allowed
                if _place_holds(pack, environment, kind, rung_value, rung_form)
            }
            if holders:
                allowed = holders
                break
    if not allowed or len(allowed) == len(legal):
        return frozenset()
    return frozenset(set(legal) - allowed)


def _locked_widget(
    definitions: Mapping[str, FieldDef], widgets: Mapping[str, Any], slot: int, name: "str | None"
) -> Any:
    """A slot's widget value when it holds a lock, else None."""
    if name is None:
        return None
    definition = definitions.get(key_for(slot, name))
    if definition is None:
        return None
    value = widgets.get(definition.key, definition.default)
    return value if _is_locked(value) else None


def _place_holds(pack: GenrePack, environment: str, kind: str, value: Any, form: Any) -> bool:
    """Whether ``environment`` can hold this kind, type and form together."""
    if kind not in pool_for(pack, KIND_FIELD, {ENVIRONMENT_FIELD: environment}):
        return False
    if value is not None and not type_feasible(pack, environment, kind, value):
        return False
    return form is None or form_can_stand(pack, environment, form)


def _normalized_head(value: str) -> str:
    """The singular, lowercased head noun of a clause value, for repeat detection."""
    return head_noun(value).lower().rstrip("s")


def _share_vocabulary(pack: GenrePack, a: str, b: str) -> bool:
    """Whether two fields draw from one declared vocabulary (the colour trio)."""
    return any(a in group and b in group for group in pack.shared_vocabulary)


def _silence_repeats(
    pack: GenrePack,
    values: "dict[str, str | None]",
    locked: "set[str]",
    *,
    rng: random.Random,
    definitions: Mapping[str, FieldDef],
    keyer: "Callable[[str], str]",
    scene_filter: str,
    scene_scope: "Mapping[str, str | None]",
) -> None:
    """Silence a clause that would repeat an earlier clause's value or head noun.

    Pools overlap by design -- ``primary_color`` and ``accent_color`` draw from
    one colour vocabulary, and ``markings`` and ``surface_detail`` both describe
    a surface -- so a draw can legitimately land the same string in two fields
    of one entity and produce "an oxide red hull, oxide red accents". Measured
    at roughly one scene in a hundred over a 2000-seed sweep before this;
    ``tests/test_coherence.py`` holds it at zero.

    Genre-free, and deliberately narrow:

    * **Exact matches only.** A word-level rule was measured and rejected: 290
      distinct words repeat inside an entity sentence over the same sweep and
      almost all of them are ordinary English ("a ring of vents ... a ring
      system"). Exact repetition is the only form with no false positives.
    * **Clause heads only.** A composed companion -- a count -- never stands
      alone, and "six thrusters ... six eyes" is how English counts two things.
    * **A locked value is never dropped.** Locking is an explicit statement of
      intent and beats every other rule in this engine; a user who locks both
      colours to "oxide red" is asking for it and gets it. Where only one of the
      pair is locked, the *unlocked* one is the one that goes, whichever came
      first.

    Mutates ``values`` in place, walking ``entity_fields`` order, so which of an
    unlocked pair survives is the pack's declaration order rather than a dict
    accident.
    """
    owner: dict[str, str] = {}
    for name in pack.entity_fields:
        if pack.entity_fields[name].renders_with is not None:
            continue
        value = values.get(name)
        if value is None:
            continue
        held_by = owner.get(value)
        if held_by is None:
            owner[value] = name
            continue
        if name not in locked:
            values[name] = None
        elif held_by not in locked:
            values[held_by] = None
            owner[value] = name

    # Two distinct strings can still inflect one noun ("mooring boom" /
    # "interferometer boom"), which the exact pass cannot see. Measured at 92
    # collisions in 1000 entities. The later field is *re-drawn* rather than
    # dropped, so the detail is kept; a shared_vocabulary pair and a locked
    # field are exempt.
    head_owner: dict[str, str] = {}
    for name in pack.entity_fields:
        if name == KIND_FIELD:
            continue
        if pack.entity_fields[name].renders_with is not None:
            continue
        value = values.get(name)
        if value is None:
            continue
        head = _normalized_head(value)
        held_by = head_owner.get(head)
        if held_by is None:
            head_owner[head] = name
            continue
        if _share_vocabulary(pack, name, held_by):
            continue
        if name in locked:
            continue
        scope = {**scene_scope, **values}
        taken = set(head_owner)
        replacement = _draw(
            rng, pack, definitions[keyer(name)], scope, scene_filter,
            {
                v
                for v in filtered_pool(pack, name, scope, scene_filter)
                if _normalized_head(v) in taken
            },
        )
        # **Re-drawn, never nulled** -- the same rule the declared-group pass
        # below already keeps. Every value of this field can share a head with
        # something earlier (a courier drone has exactly two silhouettes, a
        # "spherical drone body" and a "hovering disc chassis"), and then the
        # re-draw has an empty pool and returns None. Assigning that turned an
        # inflection clash into a subject with **no silhouette at all** -- a
        # strictly worse sentence than the repeat, arrived at silently: no
        # warning, nothing in ``redrawn_fields``, and the field simply gone.
        # A repeated head noun is ordinary English; an absent body plan is a
        # defect, so when nothing else is available the original stands.
        if replacement is None:
            continue
        values[name] = replacement
        head_owner[_normalized_head(replacement)] = name
        # A count scopes on its noun, so re-drawing the noun invalidates the
        # count drawn under the old one. Re-draw it under the new noun.
        partner = pack.entity_fields[name].count_partner
        if partner is not None and partner not in locked and values.get(partner) is not None:
            values[partner] = _draw(
                rng, pack, definitions[keyer(partner)],
                {**scene_scope, **values}, scene_filter,
            )

    # Declared groups, which *do* include composed companions. A repeated count
    # is **re-drawn**, never nulled: a bare plural asserts *several*, so a nulled
    # count on a person reads as a rifle on each hip -- which is how "sidearm
    # holsters" drew guns on both hips. Re-draw from the field's own pool, minus
    # every value already taken in the group; only when nothing remains does the
    # original stand, because a repeated "a single" is ordinary English and a
    # nulled one is a false count. A count is None only when the user set its
    # widget to None or its host is absent.
    for group in pack.distinct_within_entity:
        taken: set[str] = set()
        for name in pack.entity_fields:
            if name not in group:
                continue
            value = values.get(name)
            if value is None:
                continue
            if value in taken and name not in locked:
                scope = {**scene_scope, **values}
                replacement = _draw(
                    rng, pack, definitions[keyer(name)], scope, scene_filter,
                    {
                        v
                        for v in filtered_pool(pack, name, scope, scene_filter)
                        if v in taken
                    },
                )
                if replacement is not None:
                    value = replacement
                    values[name] = replacement
            taken.add(value)


def _mask_drawn_wired_values(
    rng: random.Random,
    pack: GenrePack,
    state: dict[str, str | None],
    address_of: Mapping[str, FieldDef],
    slot: int,
    chosen: "frozenset[str]",
    scene_filter: str,
) -> None:
    """Apply the scene's content filter to a wired entity's *drawn* values.

    The Scene Entity node has no filter of its own, so a value it drew at random
    reached a "No gore" scene intact -- a blood-soaked corpse passed straight
    through. A drawn value is a draw, not a choice (the same reasoning that lets
    a rule re-draw it), so a tag-scoped field whose value the filter masks is
    re-drawn from the filtered pool, and a count partner is re-drawn with its
    noun. A value the user locked on the Entity node is kept, and the kind and
    the type are left to the constraint pass, because re-drawing either here
    would strand every field it scopes.
    """
    identity = {KIND_FIELD, type_field(pack)}
    for name in pack.entity_fields:
        path = slot_path(slot, name)
        value = state.get(path)
        definition = address_of.get(path)
        if value is None or name in chosen or definition is None:
            continue
        if not definition.tag_scoped or name in identity:
            continue
        scope = _scope_for(pack, state, path)
        if value not in pool_for(pack, name, scope):
            # A foreign or user-supplied value: the filter is not what excludes it.
            continue
        if value in filtered_pool(pack, name, scope, scene_filter):
            continue
        state[path] = _draw(rng, pack, definition, scope, scene_filter)
        partner = pack.counts.get(name)
        partner_path = slot_path(slot, partner) if partner else None
        partner_def = address_of.get(partner_path) if partner_path else None
        if partner_def is not None and partner not in chosen:
            state[partner_path] = (
                _draw(rng, pack, partner_def, _scope_for(pack, state, partner_path), scene_filter)
                if state[path] is not None else None
            )


def _warn_masked_locks(
    pack: GenrePack,
    state: Mapping[str, str | None],
    address_of: Mapping[str, FieldDef],
    locked_paths: "set[str]",
    scene_filter: str,
    warnings: list[str],
) -> None:
    """Report every locked value the content filter would otherwise have masked.

    The lock survives -- a filter masks pools, it never overrules a value the
    user named -- but silently keeping a conflict-tagged weapon under "Peaceful"
    would look like the filter had failed. Saying so is the difference.

    The value has to be in the field's *unfiltered* pool for the filter to be
    what removed it. A locked value that is in no pool at all -- a widget saved
    before a value was renamed, or one a ``user_options.json`` supplies -- is a
    different situation entirely, and blaming the filter for it would send a
    reader looking in the wrong place.
    """
    for path, value in state.items():
        definition = address_of.get(path)
        if definition is None or value is None or path not in locked_paths:
            continue
        if not definition.tag_scoped:
            continue
        scope = _scope_for(pack, state, path)
        if value in pool_for(pack, definition.base, scope) and value not in filtered_pool(
            pack, definition.base, scope, scene_filter
        ):
            message = (
                f"{path}: kept the locked value {value!r}, which the {scene_filter!r} "
                "filter would otherwise have masked"
            )
            warnings.append(message)
            LOGGER.warning("sceneweaver: %s", message)


# ---------------------------------------------------------------------------
# Constraints
# ---------------------------------------------------------------------------


def _rule_bindings(pack: GenrePack, slots: int):
    """Every ``(rule, slot, pair)`` a rule set expands to.

    A slot-wildcarded rule is evaluated once per slot, and a wildcard on the
    *other* side of that rule binds to the **same** slot -- "a celestial body
    carries no armament" is about that body's own armament, never slot 3's.
    A relation-pair rule (``relation_*``, ``first.*`` or ``second.*``) is
    evaluated once per pair (todo 8). ``bind_address`` states this rule once;
    this is where it is spent.
    """
    for rule in pack.all_constraints:
        addresses = (rule.field, rule.excludes_field or "", rule.requires_field or "")
        pair_scoped = (
            RELATION_ANY in addresses
            or RELATION_ANY_POSITION in addresses
            or any(a.startswith((FIRST_ENDPOINT + ".", SECOND_ENDPOINT + ".")) for a in addresses)
        )
        if pair_scoped:
            for first, second in relation_pairs(slots):
                yield rule, None, (first, second)
        elif any(is_slot_wildcard(a) for a in addresses):
            for slot in range(1, slots + 1):
                yield rule, slot, None
        else:
            yield rule, None, None


def _control_values_ruled_out_by_state(
    pack: GenrePack,
    control_field: str,
    state: Mapping[str, str | None],
    locked_paths: "set[str]",
    slot: int,
) -> "frozenset[str]":
    """``_control_values_ruled_out_by_locks``, asked of a resolved slot instead of widgets.

    The constraint pass works on paths and has no widget mapping, so the same
    rule is expressed twice against two different inputs. Both are narrow and
    both are genre-blind; keeping them apart is cheaper than threading the
    widget mapping through the pass for one lookup.
    """
    allowed: "set[str] | None" = None
    legal = set(pool_options(pack, control_field))
    for name, spec in pack.entity_fields.items():
        if control_field not in spec.scope:
            continue
        path = slot_path(slot, name)
        if path not in locked_paths:
            continue
        value = state.get(path)
        if value is None:
            continue
        holders = {v for v in legal if value in pool_for(pack, name, {control_field: v})}
        if not holders:
            continue
        allowed = holders if allowed is None else (allowed & holders)
    if not allowed:
        # Contradictory locks ban nothing rather than emptying the pool -- the
        # same rule as the widget-side lookup.
        return frozenset()
    return frozenset(legal - allowed)


def _rescope_slot(
    rng: random.Random,
    pack: GenrePack,
    state: dict[str, str | None],
    address_of: Mapping[str, FieldDef],
    locked_paths: "set[str]",
    scene_filter: str,
    slot: int,
    changed: "frozenset[str] | set[str]",
    revive: "set[str] | frozenset[str]" = frozenset(),
) -> None:
    """Re-draw the fields a changed control scopes, in declaration order.

    ``changed`` is the set of control fields whose values just changed. Any
    unlocked field whose scope intersects ``changed`` is re-drawn under the new
    values; a re-drawn field that is itself a control of a later field is added
    to ``changed`` so the walk continues. One re-draw therefore cannot leave a
    downstream field scoped by a stale value.

    Locked fields are left alone -- a value the user named outranks a rule,
    which is the same precedence the rest of this pass obeys, and the warning
    for it has already been raised where the lock was seen.

    A field that is ``None`` is also left alone, because a field with an empty
    pool is legitimately silent -- except for a path in ``revive``, which a rule
    nulled and which the new control value may make drawable again.
    """
    changed = set(changed)
    controls = _control_fields(pack)
    for name, spec in pack.entity_fields.items():
        if name in changed or not (set(spec.scope) & changed):
            continue
        path = slot_path(slot, name)
        if path in locked_paths or (state.get(path) is None and path not in revive):
            continue
        definition = address_of.get(path)
        if definition is None:
            continue
        state[path] = _draw(
            rng, pack, definition, _scope_for(pack, state, path), scene_filter
        )
        if name in controls:
            changed.add(name)
        revive.discard(path)

    # The situation is a scene field, not an entity one, and is scoped on the
    # slot's kind too: a station cannot flee and a planet cannot board anything.
    situation_path = slot_path(slot, SITUATION_FIELD)
    definition = address_of.get(situation_path)
    if (
        definition is not None
        and situation_path not in locked_paths
        and (state.get(situation_path) is not None or situation_path in revive)
        and set(pack.scene_fields[SITUATION_FIELD].scope) & changed
    ):
        state[situation_path] = _draw(
            rng, pack, definition, _scope_for(pack, state, situation_path), scene_filter
        )


def _banned_by_state(
    pack: GenrePack,
    state: Mapping[str, str | None],
    address_of: Mapping[str, FieldDef],
    scene_filter: str,
    slots: int,
) -> "tuple[dict[str, set[str]], dict[str, list[str]]]":
    """``(target -> forbidden values, target -> reasons)`` for the current state.

    Shared by the constraint fixed point and the head-noun guard, so a field
    the guard re-draws cannot be re-drawn back into a state a rule forbids.
    """
    banned: dict[str, set[str]] = {}
    reasons: dict[str, list[str]] = {}
    for rule, slot, pair in _rule_bindings(pack, slots):
        trigger = bind_address(rule.field, slot, pair)
        if state.get(trigger) not in rule.triggers:
            continue
        if rule.type == RULE_EXCLUDE:
            target = bind_address(rule.excludes_field, slot, pair)
            forbidden = set(rule.excludes_values)
        else:
            target = bind_address(rule.requires_field, slot, pair)
            definition = address_of.get(target)
            if definition is None:
                continue
            # A requirement is the same machinery as an exclusion with the
            # complement of the allowed set, so there is one code path to get
            # right rather than two that can disagree.
            allowed = set(rule.requires_values) if rule.requires_values else {rule.requires_value}
            forbidden = {
                value
                for value in filtered_pool(
                    pack, definition.base, _scope_for(pack, state, target), scene_filter
                )
                if value not in allowed
            }
        if not forbidden:
            continue
        banned.setdefault(target, set()).update(forbidden)
        if rule.reason:
            reasons.setdefault(target, []).append(rule.reason)
    return banned, reasons


def _required_targets(
    pack: GenrePack, state: Mapping[str, str | None], slots: int
) -> "set[str]":
    """Every address a triggered ``require`` rule names as its target.

    ``_banned_by_state`` turns a requirement into the exclusion of its
    complement, which is exactly right for a field that holds a value and says
    nothing about a field that holds none. This is the other half: the targets
    that must hold one of the required values, empty or not.
    """
    required: set[str] = set()
    for rule, slot, pair in _rule_bindings(pack, slots):
        if rule.type != RULE_REQUIRE or not rule.requires_field:
            continue
        if state.get(bind_address(rule.field, slot, pair)) in rule.triggers:
            required.add(bind_address(rule.requires_field, slot, pair))
    return required


def _apply_constraints(
    rng: random.Random,
    pack: GenrePack,
    state: dict[str, str | None],
    address_of: Mapping[str, FieldDef],
    locked_paths: "set[str]",
    scene_filter: str,
    slots: int,
    warnings: list[str],
) -> None:
    """Drive ``state`` to a constraint fixed point, in place.

    Terminates in at most ``MAX_CONSTRAINT_PASSES`` passes whatever the rule set
    says. A rule set that has not settled by then is a *data* defect, so it is
    reported as a warning rather than silently accepted or endlessly retried.
    """
    # Round XVI: the re-offer step below fills a field the main loop nulled,
    # but a freshly re-offered value can conflict with a field that settled
    # earlier in the same pass while the target was still empty -- an
    # "at rest" condition re-offered onto a place whose situation had already
    # settled to a powered act, because nothing was banned while the
    # condition read None. The outer loop below gives the main fixed point a
    # second look whenever a re-offer actually changed something, so it can
    # catch and redraw whatever the re-offered value now conflicts with,
    # using the exact same banned-value logic rather than new machinery.
    for _outer_pass in range(3):
        refilled = False
        nulled: set[str] = set()
        for _ in range(MAX_CONSTRAINT_PASSES):
            banned, reasons = _banned_by_state(pack, state, address_of, scene_filter, slots)
            required = _required_targets(pack, state, slots)

            changed = False
            # A requirement whose allowed set is the whole pool bans nothing, and
            # still has an empty target to fill. Banned targets keep their order,
            # so a scene no requirement touches draws exactly as it did.
            for target in [*banned, *sorted(required - set(banned))]:
                forbidden = banned.get(target, set())
                current = state.get(target)
                if current is None:
                    # An exclusion has nothing to remove from an empty field, but
                    # a requirement is unmet by one: a creature "wreathed in
                    # creeping ivy" with no condition drawn is a live creature
                    # standing in ivy. Fill it from the allowed values -- unless
                    # the user chose the emptiness, which a locked path records.
                    if target not in required or target in locked_paths:
                        continue
                elif current not in forbidden:
                    continue
                if target in locked_paths:
                    # The user named this value. It wins, and the rule's reason
                    # is reported -- to _meta.warnings, never to prompt_text.
                    for reason in reasons.get(target, ()):
                        message = f"{target}: kept the locked value {current!r} ({reason})"
                        if message not in warnings:
                            warnings.append(message)
                            LOGGER.warning("sceneweaver: %s", message)
                    continue
                definition = address_of.get(target)
                if definition is None:
                    continue
                is_control = (
                    definition.base in _control_fields(pack) and definition.slot is not None
                )
                if is_control:
                    # Same reasoning as the first draw: a value the user locked
                    # on a field this control scopes has to survive a rule
                    # re-drawing the control out from under it, or the rule
                    # fixes one incoherence by making another.
                    forbidden = forbidden | _control_values_ruled_out_by_state(
                        pack, definition.base, state, locked_paths, definition.slot
                    )
                if current is None:
                    # Filling a requirement: the field may not go unsaid again.
                    definition = dataclasses.replace(definition, omission_weight=0.0)
                replacement = _draw(
                    rng, pack, definition, _scope_for(pack, state, target), scene_filter,
                    forbidden,
                )
                if replacement is None and current is None:
                    # No allowed value in this scope: the requirement cannot be
                    # met, and re-drawing an empty field every pass would never
                    # settle.
                    continue
                state[target] = replacement
                if replacement is None:
                    nulled.add(target)
                changed = True
                if is_control:
                    _rescope_slot(
                        rng, pack, state, address_of, locked_paths,
                        scene_filter, definition.slot, {definition.base}, nulled,
                    )
            if not changed:
                break
        else:
            message = (
                f"constraint rules did not settle within {MAX_CONSTRAINT_PASSES} passes; "
                "the scene is the state after the last pass"
            )
            warnings.append(message)
            LOGGER.warning("sceneweaver: %s", message)

        # **Re-offer what a rule emptied, once the scope is final.**
        #
        # A rule nulls a field against the state *at that moment*, and that
        # state is not the state the scene ends in: a form is excluded while
        # its slot still holds the subkind that scopes it, and the subkind is
        # then re-drawn by the same fixed point. Seed 68 walked exactly that
        # path -- a walker chassis excluded from a cramped room, then the
        # subkind re-drawn to "courier drone", whose own pool holds two
        # silhouettes that both stand there. The field stayed None because
        # nothing went back to ask again.
        #
        # ``_rescope_slot``'s ``revive`` set covers the case where a control
        # changes *after* the null in the same pass; it cannot cover a null
        # that happens after the control has already settled. This does, and
        # it is the same rule the repeat guard keeps: a field is re-drawn,
        # never left empty, when the pool has something to give. A field
        # whose pool is genuinely empty -- every weapon under "Peaceful" --
        # draws None again here and stays silent, which is the outcome that
        # was always correct.
        if nulled:
            banned, _reasons = _banned_by_state(pack, state, address_of, scene_filter, slots)
            for target in sorted(nulled):
                if state.get(target) is not None or target in locked_paths:
                    continue
                definition = address_of.get(target)
                if definition is None:
                    continue
                state[target] = _draw(
                    rng, pack, definition, _scope_for(pack, state, target), scene_filter,
                    banned.get(target, frozenset()),
                )
                if state[target] is not None:
                    refilled = True

        # A field re-offered here holds a fresh value the fixed point above
        # never saw, so a field that settled earlier -- while this one still
        # read None and excluded nothing -- can now be in conflict with it.
        # Give the fixed point another look; it stops as soon as a pass
        # changes nothing, so this costs a whole extra round only on the rare
        # scene that actually needs it.
        if not refilled:
            break

    _silence_head_noun_repeats(
        pack, state, address_of, locked_paths, rng, scene_filter, slots
    )
    _silence_word_echoes(pack, state, locked_paths, slots)


_FUNCTION_WORDS = frozenset({"a", "an", "the", "of", "and", "in", "on", "with", "its", "their"})


def _shares_word(a: str, b: str) -> bool:
    """Whether two phrases share a content word, hyphenated parts counted apart."""
    shared = set(a.replace("-", " ").split()) & set(b.replace("-", " ").split())
    return bool(shared - _FUNCTION_WORDS)


def _silence_word_echoes(
    pack: GenrePack, state: dict[str, str | None], locked_paths: "set[str]", slots: int
) -> None:
    """Silence a word the phrase it joins already says, in the state so the JSON agrees.

    "an antique antique rocking chair" was an ``antique`` condition modifying
    that subkind; "a pale-blue pale inner light" a colour on its own emitter.
    A head modifier that shares a word with the head noun, and a colour
    companion that shares one with its host, go unsaid.
    """
    for slot in range(1, slots + 1):
        fields = {name: state.get(slot_path(slot, name)) for name in pack.entity_fields}
        if fields.get(KIND_FIELD) is None:
            continue

        def said(name: str) -> str:
            return spoken_value(pack, name, fields[name]) if fields.get(name) else ""

        def silence(name: str) -> None:
            path = slot_path(slot, name)
            if path not in locked_paths:
                state[path] = None
                fields[name] = None

        head = head_phrase_spec(pack, fields.get(KIND_FIELD), archetype_for(pack, fields))
        if head is not None:
            nouns = ((head.subject,) if head.subject else ()) + tuple(head.noun)
            noun = next((n for n in nouns if fields.get(n)), None)
            if noun is not None:
                for name in head.modifiers:
                    if name in fields and fields.get(name) and _shares_word(said(name), said(noun)):
                        silence(name)
        for name, spec in pack.entity_fields.items():
            host = spec.renders_with
            if host is None or name == pack.entity_fields[host].count_partner:
                continue
            if fields.get(name) and fields.get(host) and _shares_word(said(name), said(host)):
                silence(name)


def _silence_head_noun_repeats(
    pack: GenrePack,
    state: dict[str, str | None],
    address_of: Mapping[str, FieldDef],
    locked_paths: "set[str]",
    rng: random.Random,
    scene_filter: str,
    slots: int,
) -> None:
    """Re-run the head-noun guard after the constraint pass, over each occupied slot.

    The constraint pass can re-draw a field -- ``_rescope_slot`` and the target
    re-draw -- without consulting the head-noun guard, so a collision the resolve
    pass removed can come back. This is the same guard, asked of the resolved
    state rather than the widget values, and it runs last so the final document
    carries no repeat.
    """
    constraint_banned, _ = _banned_by_state(pack, state, address_of, scene_filter, slots)
    for slot in range(1, slots + 1):
        if state.get(slot_path(slot, KIND_FIELD)) is None:
            continue
        head_owner: dict[str, str] = {}
        for name in pack.entity_fields:
            if name == KIND_FIELD:
                continue
            if pack.entity_fields[name].renders_with is not None:
                continue
            path = slot_path(slot, name)
            value = state.get(path)
            if value is None:
                continue
            head = _normalized_head(value)
            held_by = head_owner.get(head)
            if held_by is None:
                head_owner[head] = name
                continue
            if _share_vocabulary(pack, name, held_by):
                continue
            if path in locked_paths:
                continue
            definition = address_of.get(path)
            if definition is None:
                continue
            scope = _scope_for(pack, state, path)
            taken = set(head_owner)
            forbidden = {
                v
                for v in filtered_pool(pack, name, scope, scene_filter)
                if _normalized_head(v) in taken
            } | constraint_banned.get(path, set())
            replacement = _draw(
                rng, pack, definition, scope, scene_filter, forbidden
            )
            state[path] = replacement
            if replacement is not None:
                head_owner[_normalized_head(replacement)] = name
                # A count scopes on its noun; re-draw it under the new noun.
                partner = pack.entity_fields[name].count_partner
                if partner is not None:
                    partner_path = slot_path(slot, partner)
                    if partner_path not in locked_paths and state.get(partner_path) is not None:
                        pdef = address_of.get(partner_path)
                        if pdef is not None:
                            state[partner_path] = _draw(
                                rng, pack, pdef,
                                _scope_for(pack, state, partner_path), scene_filter,
                                constraint_banned.get(partner_path, set()),
                            )

def _scope_for(
    pack: GenrePack, state: Mapping[str, str | None], address: str
) -> "dict[str, str | None]":
    """The control-field values that scope ``address``'s pool.

    An entity control is read at this address's own slot prefix
    (``entity2.subkind`` for ``entity2.form``); a scene control (``environment``)
    is read at its bare scene address. Both, because a field's scope may name
    either.
    """
    entity, dot, name = address.partition(".")
    if not dot:
        name, entity = address, ""
    spec = pack.entity_fields.get(name) or pack.scene_fields.get(name)
    if spec is None or not spec.scope:
        return {}
    scope: dict[str, str | None] = {}
    for control in spec.scope:
        if control in pack.scene_fields or not entity:
            scope[control] = state.get(control)
        else:
            scope[control] = state.get(f"{entity}.{control}")
    return scope


# ---------------------------------------------------------------------------
# The pipeline
# ---------------------------------------------------------------------------


def generate_scene(
    seed: int,
    pack: GenrePack,
    *,
    widgets: Mapping[str, Any] | None = None,
    wired_entities: Mapping[int, Mapping[str, Any]] | None = None,
    scene_filter: str = DEFAULT_SCENE_FILTER,
    set_all_fields: str = SET_ALL_OFF,
    entity_count: int | None = DEFAULT_ENTITY_COUNT,
    slots: int = SCENE_NODE_SLOTS,
) -> tuple[str, dict[str, Any]]:
    """Generate one scene. Returns ``(prompt_text, prompt_json)``.

    ``widgets`` is the node's whole widget mapping keyed by widget key
    (``entity2_kind``), each value "Random", "None" or a literal. It is named
    for what it holds rather than for the locked subset of it, because most of
    it is "Random" on a default node and calling that "locked" would mislead
    every future reader.

    ``wired_entities`` maps a 1-based slot to a ``SCENE_ENTITY`` payload.

    ``entity_count`` is how many slots the scene occupies, and it is the
    **authority** on that: slots past it are left out even if their kind widget
    holds a value, and slots within it are filled even if their kind widget
    still says "None". Anything else makes the control a lie -- a user who sets
    it to 3 and gets one entity because two hidden widgets defaulted to "None"
    has been told something untrue by the node face. A wired slot is occupied
    whatever the count says, because connecting a node is the more explicit
    statement; the count is raised to match and reported in ``_meta``.

    It defaults to ``DEFAULT_ENTITY_COUNT`` rather than to ``None`` so that a
    bare call behaves like a freshly-dropped node: one subject. Pass ``None``
    explicitly for "no opinion", where every slot is left to its own widget.
    """
    register_pack(pack)
    rng = random.Random(seed)
    widgets = dict(widgets or {})
    wired_entities = dict(wired_entities or {})
    warnings: list[str] = []
    overridden: list[str] = []
    # The node hands over the label it shows ("No gore"); every draw below reads
    # the filter it applies. ``_meta`` keeps the label, which is what was chosen.
    filter_label = scene_filter
    scene_filter = canonical_scene_filter(pack, scene_filter)

    # The *resolution* set, not the widget list: a supporting slot has fewer
    # widgets but the same fields, and a constraint rule must reach a field no
    # widget backs. See ``build_resolution_definitions``.
    definitions = build_resolution_definitions(pack, slots)
    widget_defs = build_field_definitions(pack, slots)
    address_of = {d.path: d for d in definitions.values() if not d.control}

    # 2. The bulk edit.
    widgets = _apply_set_all(definitions, widgets, set_all_fields)

    # 3. Which slots a wire has promoted to full depth.
    # A wire with no kind states nothing about the subject, so the slot draws its
    # own -- see D11. Without this the scene is environment-only and the slot is
    # described as nothing at all.
    promoted = {
        slot: payload for slot, payload in wired_entities.items() if 1 <= slot <= slots
        and _payload_fields(pack, payload).get(KIND_FIELD) is not None
    }

    # 3b. How many slots the scene occupies. The count only ever *empties* slots
    # past it: within the count a slot is whatever its own widget says, so a
    # slot the user deliberately set to None stays empty and a pure-setting
    # scene is still expressible. A wire past the count raises it -- the wire is
    # the more explicit statement -- so the widened count is what the budget
    # divides the scene's detail between.
    occupies = _occupied_slots(slots, entity_count, promoted, definitions, widgets)
    for slot in range(1, slots + 1) if entity_count is not None else ():
        key = key_for(slot, KIND_FIELD)
        if key not in definitions:
            continue
        if slot not in occupies:
            widgets[key] = NONE
    for slot in sorted(wired_entities):
        if slot not in promoted:
            if 1 <= slot <= slots:
                message = (
                    f"slot {slot}'s wired entity has no kind, so slot {slot} "
                    "draws its own subject"
                )
            else:
                message = (
                    f"ignored a wired entity for slot {slot}: this scene has {slots} slots"
                )
            warnings.append(message)
            LOGGER.warning("sceneweaver: %s", message)

    # 4-5. Resolve, with the filter already masking every pool.
    state: dict[str, str | None] = {}
    locked_paths: set[str] = set()
    sources: dict[int, str] = {}
    genres: dict[int, str] = {}
    per_slot_locked: dict[int, set[str]] = {}
    wired_supplied: dict[int, dict[str, str | None]] = {}
    wired_chosen: dict[int, "frozenset[str]"] = {}
    #: A foreign guest's own view of its fields, in its own pack's schema. The
    #: host state still carries the values (the field keys are shared), but the
    #: guest is budgeted, masked and spoken by the pack that built it.
    guests: dict[int, tuple[GenrePack, dict[str, str | None]]] = {}

    environment_def = definitions[ENVIRONMENT_FIELD]
    environment_widget = _widget_value(environment_def, widgets)
    state[ENVIRONMENT_FIELD] = _resolve_one(
        rng, pack, environment_def, environment_widget, {}, scene_filter, locked_paths,
        banned=_environments_ruled_out_by_fixed_subjects(
            pack, definitions, widgets, promoted,
        ),
    )
    scene_scope: dict[str, str | None] = {ENVIRONMENT_FIELD: state[ENVIRONMENT_FIELD]}
    context_def = definitions.get(CONTEXT_FIELD)
    if context_def is not None:
        state[CONTEXT_FIELD] = _resolve_one(
            rng, pack, context_def, _widget_value(context_def, widgets),
            {ENVIRONMENT_FIELD: state[ENVIRONMENT_FIELD]}, scene_filter, locked_paths,
        )

    for slot in range(1, slots + 1):
        payload = promoted.get(slot)
        sources[slot] = SOURCE_WIRED if payload is not None else SOURCE_WIDGETS
        genres[slot] = (payload or {}).get("genre", pack.slug) if payload else pack.slug
        locked_here: set[str] = set()
        per_slot_locked[slot] = locked_here

        guest = guest_pack(pack, payload)
        if payload is not None and guest is not None:
            guest_fields = _payload_fields(guest, payload)
            mask_for_filter(guest, guest_fields, _payload_locked(payload), scene_filter)
            mask_for_place(
                guest, pack, guest_fields, _payload_locked(payload), state.get(ENVIRONMENT_FIELD)
            )
            guests[slot] = (guest, guest_fields)
        if payload is not None:
            supplied = _payload_fields(pack, payload)
            if guest is not None:
                supplied = {name: guests[slot][1].get(name) for name in pack.entity_fields}
            chosen = _payload_locked(payload)
            wired_supplied[slot] = {name: supplied.get(name) for name in pack.entity_fields}
            wired_chosen[slot] = chosen
            lost: list[str] = []
            for name in pack.entity_fields:
                path = slot_path(slot, name)
                key = key_for(slot, name)
                if key in definitions and _is_locked(widgets.get(key, RANDOM)):
                    lost.append(key)
                state[path] = supplied.get(name)
                if supplied.get(name) is None:
                    continue
                # A wired value the user **chose** is the more explicit statement
                # and beats a rule, with the rule's reason reported. A value the
                # Entity node drew at random is not a choice -- it is a draw --
                # so it stays an ordinary resolved value and the constraint pass
                # re-draws it when this place cannot hold it. Locking every
                # supplied field instead is what let a walker be drawn in vacuum.
                #
                # ``locked_here`` is the budget's lock set, and only a genuine
                # choice belongs in it: rule 2 of the budget gives a wired slot
                # the hero allowance untapered, not an exemption from the cap, so
                # a *drawn* wired field stays cuttable. A field the user locked
                # on the Entity node is a choice and is budget-locked too.
                if name in chosen:
                    locked_paths.add(path)
                    locked_here.add(name)
            _mask_drawn_wired_values(rng, pack, state, address_of, slot, chosen, scene_filter)
            if lost:
                overridden.extend(lost)
                message = (
                    f"slot {slot}: a wired Scene Entity replaced {len(lost)} locked "
                    f"widget value(s) ({', '.join(sorted(lost))}); the wire is the more "
                    "explicit statement"
                )
                warnings.append(message)
                LOGGER.warning("sceneweaver: %s", message)
        else:
            values, resolved_locks = _resolve_entity_fields(
                rng, pack, definitions, widgets,
                keyer=lambda name, slot=slot: key_for(slot, name),
                scene_filter=scene_filter,
                locked_paths=locked_paths,
                scene_scope=scene_scope,
            )
            for name, value in values.items():
                state[slot_path(slot, name)] = value
            locked_here.update(resolved_locks)

        situation_def = definitions[key_for(slot, SITUATION_FIELD)]
        situation_widget = _widget_value(situation_def, widgets)
        situation_path = slot_path(slot, SITUATION_FIELD)
        # A foreign guest acts from its own repertoire when the host place can
        # stage one of its acts; the host's default acts were written for things
        # the host knows, which is how a drop pod came to be "charging headlong".
        # A user's locked situation still wins.
        guest_act = None
        if slot in guests and situation_widget == RANDOM:
            guest, guest_fields = guests[slot]
            guest_act = guest_situation(
                rng, guest, pack, guest_fields, state.get(ENVIRONMENT_FIELD), scene_filter,
            )
        if guest_act is not None:
            state[situation_path] = guest_act
            locked_paths.add(situation_path)
        else:
            state[situation_path] = (
                _resolve_one(
                    rng, pack, situation_def, situation_widget,
                    _scope_for(pack, state, situation_path), scene_filter, locked_paths,
                )
                if state.get(slot_path(slot, KIND_FIELD)) is not None
                else None
            )

    for first, second in relation_pairs(slots):
        key = relation_key(first, second)
        definition = definitions[key]
        state[key] = _resolve_one(
            rng, pack, definition, _widget_value(definition, widgets), {},
            scene_filter, locked_paths,
        )

    for first, second in relation_pairs(slots):
        key = relation_position_key(first, second)
        definition = definitions[key]
        state[key] = _resolve_one(
            rng, pack, definition, _widget_value(definition, widgets), {},
            scene_filter, locked_paths,
        )

    # A locked value that the filter would have masked survives, and says so.
    _warn_masked_locks(pack, state, address_of, locked_paths, scene_filter, warnings)

    # 6. Constraints.
    _apply_constraints(
        rng, pack, state, address_of, locked_paths,
        scene_filter, slots, warnings,
    )

    # A wired field the user did NOT choose can be re-drawn by a rule; when the
    # re-draw empties it, the Entity node showed a value the scene no longer
    # has, so it is reported once per slot rather than silently dropped. Budget
    # cuts happen later and are not rule decisions, so they are not counted.
    for slot, supplied_values in wired_supplied.items():
        dropped = [
            name
            for name, value in supplied_values.items()
            if value is not None
            and name not in wired_chosen[slot]
            and state.get(slot_path(slot, name)) is None
        ]
        if dropped:
            message = (
                f"slot {slot}: a rule dropped {len(dropped)} wired field(s) this "
                f"place cannot hold ({', '.join(sorted(dropped))})"
            )
            warnings.append(message)
            LOGGER.warning("sceneweaver: %s", message)

    # A drawn wired value the constraint pass replaced. Not a warning -- the place
    # could not hold it and nobody chose it -- but the Entity node showed it, so the
    # node face says what changed.
    redrawn: dict[str, list[str]] = {}
    for slot, supplied_values in wired_supplied.items():
        changed = sorted(
            name
            for name, value in supplied_values.items()
            if value is not None
            and name not in wired_chosen[slot]
            and state.get(slot_path(slot, name)) not in (None, value)
        )
        if changed:
            redrawn[str(slot)] = changed

    # 7. The detail budget, then assemble.
    #
    # The allowance depends on how many slots the scene actually *occupies*,
    # not on how many it has, so a two-entity scene budgeted for two rather
    # than for four. Counted first, before anything is cut, because cutting
    # slot 1 cannot be allowed to depend on whether slot 3 has been reached yet.
    occupied = [
        slot for slot in range(1, slots + 1)
        if state.get(slot_path(slot, KIND_FIELD)) is not None
    ]
    entities: list[ResolvedEntity] = []
    for position, slot in enumerate(occupied, start=1):
        voice = guests[slot][0] if slot in guests else pack
        values = {name: state.get(slot_path(slot, name)) for name in voice.entity_fields}
        wired = sources[slot] == SOURCE_WIRED
        archetype = _archetype_for(voice, values)
        values = apply_budget(
            voice, values,
            # A wired slot takes the top allowance for this scene -- what slot 1
            # gets -- rather than its own position's. Wiring a whole node in is
            # the request for depth; it is a promotion, never an exemption.
            budget=allowance_for(len(occupied), 1 if wired else position),
            archetype=archetype,
            locked=per_slot_locked[slot],
            # The fields this slot actually shows a dropdown for. A wired slot
            # is described by its wire, not by its widgets, so it passes none
            # and spends the whole allowance on the pack's own priority.
            visible=frozenset() if wired else _visible_fields(pack, widget_defs, slot),
            omits=archetype.omits if archetype is not None else frozenset(),
            wired=wired,
            rng=rng,
        )
        for name, value in values.items():
            state[slot_path(slot, name)] = value
        entities.append(
            ResolvedEntity(
                index=slot,
                source=sources[slot],
                genre=genres[slot],
                fields=values,
                situation=state.get(slot_path(slot, SITUATION_FIELD)),
            )
        )

    occupied = {entity.index for entity in entities}
    relations: list[ResolvedRelation] = []
    for first, second in relation_pairs(slots):
        value = state.get(relation_key(first, second))
        if value is None or first not in occupied or second not in occupied:
            # A relation needs both ends. Dropping it is the never-negate rule
            # again: say nothing rather than invent the missing partner.
            continue
        relations.append(
            ResolvedRelation(
                endpoints=(first, second),
                value=value,
                position=state.get(relation_position_key(first, second)),
            )
        )

    # The context sentence pattern is chosen here, not in the renderer: the
    # renderer is pure and owns no RNG, and this is the last draw in the
    # function, so it shifts no earlier one.
    # A framing that needs depth is only offered where the place has it: "In the
    # distance, a stack of sealed cargo pods is visible" is a fine sentence in
    # orbit and nonsense in a cockpit. The index recorded is into the WHOLE
    # tuple, not into the eligible subset, so the renderer keeps indexing the
    # pack's own list and the document still round-trips.
    context_patterns = pack.prose.context_sentences
    here = affordances_of(pack, state.get(ENVIRONMENT_FIELD) or "")
    eligible = [
        index
        for index, pattern in enumerate(context_patterns)
        if pattern.needs <= here
    ]
    context_index = (
        rng.choice(eligible) if eligible and state.get(CONTEXT_FIELD) else None
    )

    meta = {
        "seed": seed,
        "genre": pack.slug,
        "schema_version": JSON_SCHEMA_VERSION,
        "redrawn_fields": redrawn,
        "filter_applied": filter_label,
        "overridden_fields": overridden,
        "warnings": warnings,
        # Which context sentence pattern the scene drew. Recorded so the
        # document round-trips: the renderer is pure and needs the index, not
        # a fresh draw.
        "context_sentence_index": context_index,
    }
    scene = ResolvedScene(
        environment=state.get(ENVIRONMENT_FIELD),
        context=state.get(CONTEXT_FIELD),
        context_sentence_index=context_index,
        entities=tuple(entities),
        relations=tuple(relations),
        meta=meta,
    )
    return render_prose(scene, pack), _to_json(pack, scene)


def generate_entity(
    seed: int,
    pack: GenrePack,
    *,
    widgets: Mapping[str, Any] | None = None,
    scene_filter: str = DEFAULT_SCENE_FILTER,
) -> tuple[str, dict[str, Any]]:
    """Generate one entity. Returns ``(prompt_text, SCENE_ENTITY payload)``.

    The Scene Entity node's whole job: one slot's morphology, with no
    environment, no situation and no relations -- the scene node owns all three,
    so an entity that carried its own would fight whichever scene it was wired
    into.

    ``widgets`` is keyed by the entity node's **bare** widget keys (``kind``),
    while the constraint pass addresses the same fields at slot 1
    (``entity1.kind``). That is deliberate and is what lets one rule set govern
    both node classes: a rule written about an entity's material reaches this
    node too, without the pack having to say so twice.
    """
    register_pack(pack)
    rng = random.Random(seed)
    widgets = dict(widgets or {})
    warnings: list[str] = []

    definitions = build_field_definitions(pack, ENTITY_NODE_SLOTS)
    address_of = {d.path: d for d in definitions.values() if not d.control}
    locked_paths: set[str] = set()

    values, locked = _resolve_entity_fields(
        rng, pack, definitions, widgets,
        keyer=lambda name: name,
        scene_filter=scene_filter,
        locked_paths=locked_paths,
        scene_scope={},
    )

    state = {slot_path(LONE_ENTITY_SLOT, name): value for name, value in values.items()}
    _warn_masked_locks(pack, state, address_of, locked_paths, scene_filter, warnings)
    _apply_constraints(
        rng, pack, state, address_of, locked_paths, scene_filter,
        LONE_ENTITY_SLOT, warnings,
    )
    values = {
        name: state[slot_path(LONE_ENTITY_SLOT, name)] for name in pack.entity_fields
    }

    # Budgeted as a wired slot at the top level, with the archetype's own cap: the
    # node renders exactly what the entity will contribute to a one-entity scene,
    # so its own preview cannot disagree with the wired result. The archetype cap
    # is what shortens a station without shortening a creature -- an uncapped call
    # here would draw all sixteen clause heads and render a shape no scene would
    # ever produce.
    archetype = _archetype_for(pack, values)
    values = apply_budget(
        pack, values,
        budget=allowance_for(1, 1),
        archetype=archetype,
        locked=locked,
        omits=archetype.omits if archetype is not None else frozenset(),
        rng=rng,
    )

    entity = ResolvedEntity(
        index=LONE_ENTITY_SLOT,
        source=SOURCE_WIDGETS,
        genre=pack.slug,
        fields=values,
        situation=None,
    )
    # Rendered through the scene renderer rather than through ``render_entity``
    # directly, so the sentence a user reads on this node is assembled by exactly
    # the code that will assemble it once the entity is wired into a scene.
    text = render_prose(ResolvedScene(entities=(entity,)), pack)
    return text, entity_payload(pack.slug, values, locked)


def key_for(slot: int, name: str) -> str:
    """Widget key for a slot's field. Thin alias so the pipeline reads flat."""
    return f"entity{slot}_{name}"


def _resolve_one(
    rng: random.Random,
    pack: GenrePack,
    definition: FieldDef,
    widget: Any,
    scope: "Mapping[str, str | None]",
    scene_filter: str,
    locked_paths: set[str],
    banned: "frozenset[str] | set[str]" = frozenset(),
) -> str | None:
    """Turn one widget value into one resolved value.

    "Random" draws; "None" omits; anything else is a lock and is recorded as one
    so the constraint pass knows not to overrule it.
    """
    if widget == NONE or widget is None:
        return None
    if widget == RANDOM:
        return _draw(rng, pack, definition, scope, scene_filter, banned)
    locked_paths.add(definition.path)
    return widget


def _to_json(pack: GenrePack, scene: ResolvedScene) -> dict[str, Any]:
    """The ``prompt_json`` document, in the shape the plan pins.

    Every field of every entity appears, ``None`` included: a reader has to be
    able to tell "not asked for" from "not in this genre", and only an explicit
    null does that.
    """
    entities = []
    for entity in scene.entities:
        record: dict[str, Any] = {
            "index": entity.index,
            "source": entity.source,
            "genre": entity.genre,
            "archetype": archetype_name_for(
                voice_of(entity.genre, pack),
                {name: entity.get(name) for name in pack.entity_fields},
            ),
        }
        for name in pack.entity_fields:
            record[name] = entity.get(name)
        record[SITUATION_FIELD] = entity.situation
        entities.append(record)
    return {
        ENVIRONMENT_FIELD: scene.environment,
        CONTEXT_FIELD: scene.context,
        "entities": entities,
        RELATION_FIELD + "s": [
            {
                "endpoints": list(relation.endpoints),
                "value": relation.value,
                "position": relation.position,
            }
            for relation in scene.relations
        ],
        "_meta": dict(scene.meta),
    }


def scene_json_text(document: Mapping[str, Any]) -> str:
    """``prompt_json`` as the string the node outputs."""
    return json.dumps(document, indent=2, ensure_ascii=False)
