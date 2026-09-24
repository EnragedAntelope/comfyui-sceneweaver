"""The ``GenrePack`` contract -- the seam every genre plugs into.

A pack is pure data. The engine and both node classes are written against this
module and never against a concrete genre, so adding one costs a single
``data/<genre>.py`` plus two registration lines in the repo-root ``__init__.py``.
``tests/test_genre_contract.py`` pins that: it asserts this module imports
without pulling in any pack, and greps ``nodes/`` and ``engine/`` for genre
slugs. If something here ever needs to know what "sci-fi" means, the contract is
wrong -- widen the contract, never special-case the genre.

Three layers, in the order a value travels:

``FieldSpec``  what a genre *declares* about one field (group, label, whether
               its pool is kind-scoped, whether the content filter touches it,
               which field is its count partner, ...). Authored by hand.
``FieldDef``   what ``build_field_definitions`` *builds* for one widget on one
               node: a FieldSpec with its options resolved, its slot bound and
               its widget key and constraint address computed. Machine-made.
``widget``     what a node class emits from a FieldDef.

Two key spaces, deliberately distinct:

* **Widget key** -- ``entity2_kind``. A legal Python identifier, because it
  arrives at ``execute()`` as a keyword argument.
* **Constraint address** -- ``entity2.kind``. Dotted, and shared by both node
  classes: the Scene Entity node's single entity uses slot 1's addresses, so one
  rule set governs both nodes rather than two that can drift apart.

**Widget order is a compatibility surface.** ``widgets_values`` in a saved
workflow is positional, so ``widget_order`` below is the single declaration of
it. Never reorder it; only ever append.
"""
from __future__ import annotations

import re
from collections import OrderedDict
from dataclasses import MISSING, dataclass, field, fields as dataclass_fields, replace
from itertools import combinations
from string import Formatter
from types import MappingProxyType
from typing import Any, Mapping

# ---------------------------------------------------------------------------
# Widget vocabulary
# ---------------------------------------------------------------------------

#: Draw this field at random from its (kind-scoped, filter-masked) pool.
RANDOM = "Random"
#: Omit this field entirely. Absence is expressed by saying nothing about it --
#: never by naming what is missing. See the never-negate rule in AGENTS.md.
NONE = "None"

#: ``scene_filter``: a tag-based pre-pass that masks pools before any draw.
#: "Peaceful" yields a ship with no weapons *described*, not "an unarmed ship".
SCENE_FILTERS: tuple[str, ...] = ("Any", "Peaceful", "Conflict")
#: The control widget that carries the filter.
SCENE_FILTER_KEY = "scene_filter"
DEFAULT_SCENE_FILTER = "Any"


#: ``set_all_fields``: a bulk edit of the *other* widgets, performed by the
#: frontend, which then snaps this back to "Off".
SET_ALL_OFF = "Off"
SET_ALL_CLEAR = "Clear all"
SET_ALL_RANDOMIZE = "Randomize all"
SET_ALL_OPTIONS: tuple[str, ...] = (SET_ALL_OFF, SET_ALL_RANDOMIZE, SET_ALL_CLEAR)
SET_ALL_FIELDS_KEY = "set_all_fields"
SET_ALL_FIELDS_LABEL = "Bulk edit widgets"
SET_ALL_FIELDS_TOOLTIP = (
    "Bulk-edit every descriptive widget below. 'Randomize all' turns each one "
    "that says 'None' into 'Random'; 'Clear all' does the reverse. A field you "
    "locked to a value is never touched, and the control snaps back to 'Off' as "
    "soon as it has run, so it stays a one-shot action rather than a mode."
)

#: Bounds for the ``seed`` widget. They live on the contract rather than in a
#: node module because both node classes register the same widget and a
#: divergence between them would be invisible until a saved workflow clamped a
#: seed differently on one node than on the other. 64-bit, matching ComfyUI's
#: own seed widgets.
SEED_MIN = 0
SEED_MAX = 0xFFFFFFFFFFFFFFFF
#: A *string* here sets the auto-added control_after_generate widget's default
#: mode. "randomize" is what makes every queue produce a new scene; a bare True
#: would default that control to "fixed" instead.
SEED_CONTROL_AFTER_GENERATE = "randomize"

#: Content-filter tag vocabulary. Frozen at three: exactly one tag on every
#: value in every ``tag_scoped`` pool.
TAG_NEUTRAL = "neutral"
TAG_PEACEFUL_ONLY = "peaceful_only"
TAG_CONFLICT_ONLY = "conflict_only"
CONTENT_TAGS: frozenset[str] = frozenset({TAG_NEUTRAL, TAG_PEACEFUL_ONLY, TAG_CONFLICT_ONLY})

# ---------------------------------------------------------------------------
# Structural constants
# ---------------------------------------------------------------------------

#: The control field every other pool and every widget label is scoped by.
KIND_FIELD = "kind"
#: Scene-owned fields. ``situation`` is emitted once per slot; ``relation`` once
#: per unordered slot pair.
ENVIRONMENT_FIELD = "environment"
#: What else is in the shot, drawn once per scene. Optional: a pack that
#: declares no ``context`` field simply renders no context sentence.
CONTEXT_FIELD = "context"
SITUATION_FIELD = "situation"
RELATION_FIELD = "relation"
RELATION_POSITION_FIELD = "relation_position"

#: The entity field a shape's stance lives on. Affordances describe a *place*;
#: a stance describes a *body*. The rule that pairs them names this field.
STANCE_FIELD = "form"

#: Relation-pair and endpoint constraint addresses (todo 8). ``relation_*``
#: matches any pair; ``first``/``second`` name the pair's endpoints.
RELATION_ANY = "relation_*"
RELATION_ANY_POSITION = "relation_*_position"
FIRST_ENDPOINT = "first"
SECOND_ENDPOINT = "second"
SCENE_FIELD_NAMES: tuple[str, ...] = (
    ENVIRONMENT_FIELD, SITUATION_FIELD, RELATION_FIELD, RELATION_POSITION_FIELD
)

#: Pool key used when a field has no per-kind override. Reading through to it is
#: a *documented fallback*, not an accident -- see ``pool_for``.
POOL_DEFAULT_KEY = "_default"

#: ``build_field_definitions(pack, slots)`` argument for each node.
ENTITY_NODE_SLOTS = 0
SCENE_NODE_SLOTS = 4

#: Slot whose constraint addresses the single-entity node borrows, so one rule
#: set governs both node classes.
LONE_ENTITY_SLOT = 1

#: The control that says how many entity slots a scene occupies.
ENTITY_COUNT_KEY = "entity_count"

#: Its options, as strings, because it is a combo. A combo rather than an int
#: spinner on purpose: an int input on this node would need a min, a max and a
#: suppressed ``control_after_generate``, none of which the field contract
#: carries -- three new plumbed attributes to save one click.
def entity_count_options(slots: int) -> tuple[str, ...]:
    return tuple(str(n) for n in range(1, max(1, slots) + 1))

_IDENTIFIER_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_CLASS_SUFFIX_RE = re.compile(r"^[A-Z][A-Za-z0-9]*$")
#: A constraint address: ``environment``, ``relation_1_2``, ``entity3.kind`` or
#: the any-slot wildcard ``entity*.kind``.
ADDRESS_RE = re.compile(
    r"^(?:[a-z][a-z0-9_]*|"
    r"entity(?:\*|[1-9][0-9]*)\.[a-z][a-z0-9_]*|"
    r"relation_\*|relation_\*_position|"
    r"(?:first|second)\.[a-z][a-z0-9_]*)$"
)

#: Rule kinds. Kept as strings rather than an Enum so a pack module stays plain
#: readable data.
RULE_EXCLUDE = "exclude"
RULE_REQUIRE = "require"
RULE_TYPES: frozenset[str] = frozenset({RULE_EXCLUDE, RULE_REQUIRE})

_EMPTY_MAP: Mapping[str, Any] = MappingProxyType({})


def _freeze(mapping: Mapping[str, Any] | None) -> Mapping[str, Any]:
    """Return a read-only view of ``mapping``, one level deep.

    A pack is shared process-wide, so an accidental in-place edit -- a user
    options merge that appends to a pool instead of building a new pack -- would
    leak one user's private entries into everything else that reads it.
    """
    if not mapping:
        return _EMPTY_MAP
    return MappingProxyType(dict(mapping))


def _freeze_nested(mapping: Mapping[str, Mapping[str, Any]] | None) -> Mapping[str, Mapping[str, Any]]:
    """``_freeze`` for the ``{field: {key: value}}`` maps (pools, labels, tags)."""
    if not mapping:
        return _EMPTY_MAP
    return MappingProxyType({key: _freeze(value) for key, value in mapping.items()})


def _freeze_sets(mapping: Mapping[str, Any] | None) -> Mapping[str, frozenset[str]]:
    """``_freeze`` for a ``{key: frozenset}`` map (affordances, capabilities)."""
    if not mapping:
        return _EMPTY_MAP
    return MappingProxyType({key: frozenset(value) for key, value in mapping.items()})


def _freeze_nested_sets(
    mapping: Mapping[str, Mapping[str, Any]] | None,
) -> Mapping[str, Mapping[str, frozenset[str]]]:
    """``_freeze`` for the ``{field: {value: frozenset}}`` maps (needs, traits)."""
    if not mapping:
        return _EMPTY_MAP
    return MappingProxyType({key: _freeze_sets(value) for key, value in mapping.items()})


# ---------------------------------------------------------------------------
# What a genre declares
# ---------------------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class FieldSpec:
    """One field, as a genre author writes it.

    Everything a pack states about a field *except* its values -- those live in
    ``GenrePack.pools`` so a pool can be kind-scoped and filter-masked without
    duplicating the metadata per kind.
    """

    #: UI grouping and the key the prompt_json groups by.
    group: str
    #: Generic, genre-portable label. ``GenrePack.labels`` overrides it per kind
    #: ("Engine count" on a vessel, "Eye count" on a creature) and the frontend
    #: rewrites the widget label when ``kind`` changes -- labels only, never the
    #: widget order.
    label: str
    #: Sentence of help shown above the mechanic line in the widget tooltip.
    tooltip: str = ""
    #: Whether ``None`` (omit this field) is offered. False only for controls.
    optional: bool = True
    #: Read straight from its widget: never randomized, never described, never
    #: in ``prompt_json`` outside ``_meta``.
    control: bool = False
    #: Pool is ``{kind: [...]}`` rather than a single list. See ``pool_for``.
    kind_scoped: bool = False
    #: The ordered chain of CONTROL FIELDS whose current values key this field's
    #: pool, most specific first. ("subkind", "kind") means: try the subkind's own
    #: pool, then the subkind's declared group, then the kind's, then the kind's
    #: group, then POOL_DEFAULT_KEY.
    #:
    #: ``kind_scoped=True`` is the one-element case and stays the spelling for it;
    #: the two are reconciled in __post_init__ so every existing reader of
    #: ``kind_scoped`` -- the frontend payload, the validator, the lock-narrowing
    #: pass -- keeps working unchanged.
    scope: tuple[str, ...] = ()
    #: The ``scene_filter`` pre-pass masks this field's pool by content tag.
    tag_scoped: bool = False
    #: The other half of a count pair -- on a noun field, its count field; on a
    #: count field, the noun it counts. Bidirectional so either side can find
    #: the other without a second lookup table.
    count_partner: str | None = None
    #: Per-value draw weights. Absent means uniform. Used to stop a small pool's
    #: extremes ("colossal", "planetary") dominating a flat draw.
    weights: Mapping[str, float] | None = None
    #: Relative weight of drawing NO value at all, against the pool's own
    #: weights. A field exempt from the budget -- a head-phrase modifier -- is
    #: otherwise spoken on every entity, and a describing word on every entity
    #: stops meaning anything. Honoured only by a ``Random`` draw; a locked
    #: value never reaches the draw.
    omission_weight: float = 0.0
    #: Part of the brief five a supporting slot gets when nothing is wired in.
    brief: bool = False
    #: This field has no clause of its own; it is composed into the named
    #: field's clause (a count into its noun, a glow colour into its emitter).
    #: Such fields are absent from ``prose.entity_clause_order`` by construction.
    renders_with: str | None = None
    #: "combo" or "int". Only ``seed`` is an int, but the contract carries the
    #: distinction rather than special-casing one field name in the node code.
    widget: str = "combo"
    #: Widget default. Descriptive fields default to ``RANDOM`` -- full random
    #: with no configuration is the pack's headline behaviour.
    default: Any = RANDOM

    def __post_init__(self) -> None:
        if self.widget not in ("combo", "int"):
            raise ValueError(f"FieldSpec.widget must be 'combo' or 'int', got {self.widget!r}")
        if self.control and self.optional:
            raise ValueError(
                f"control field {self.label!r} cannot be optional: a control is read "
                "from its widget, so 'None' would be a value the engine must interpret"
            )
        object.__setattr__(self, "weights", _freeze(self.weights) if self.weights else None)
        if self.omission_weight < 0:
            raise ValueError(
                f"FieldSpec.omission_weight must be >= 0, got {self.omission_weight}"
            )
        scope = tuple(self.scope)
        if not scope and self.kind_scoped:
            scope = (KIND_FIELD,)
        object.__setattr__(self, "scope", scope)
        object.__setattr__(self, "kind_scoped", KIND_FIELD in scope)


@dataclass(frozen=True, kw_only=True)
class ConstraintRule:
    """One exclusion or requirement, addressed at a field/value pair.

    ``field`` and ``excludes_field`` / ``requires_field`` are constraint
    addresses (see the module docstring): ``environment``, ``entity2.scale``, or
    ``entity*.kind`` for "any slot". ``reason`` is not decoration -- it is what
    the warning says when a locked value wins over a rule.
    """

    type: str
    field: str
    #: The trigger value. Exactly one of ``value`` / ``values`` is set.
    value: str = ""
    #: Trigger values, for a rule that fires on any of a set.
    #:
    #: "A submersible does not appear indoors" is one idea about twenty
    #: environments, and writing it as twenty near-identical rules makes the
    #: rule table twenty times harder to read and twenty times easier to leave
    #: half-edited. It also multiplies the work of the fixed-point pass, which
    #: runs every rule on every slot on every one of its passes.
    values: tuple[str, ...] = ()
    excludes_field: str | None = None
    excludes_values: tuple[str, ...] = ()
    requires_field: str | None = None
    requires_value: str | None = None
    requires_values: tuple[str, ...] = ()
    reason: str = ""

    def __post_init__(self) -> None:
        if self.type not in RULE_TYPES:
            raise ValueError(f"unknown rule type {self.type!r}; expected one of {sorted(RULE_TYPES)}")
        for address in (self.field, self.excludes_field, self.requires_field):
            if address is not None and not ADDRESS_RE.match(address):
                raise ValueError(f"{address!r} is not a valid constraint address")
        if self.type == RULE_EXCLUDE:
            if not self.excludes_field or not self.excludes_values:
                raise ValueError("an exclude rule needs excludes_field and excludes_values")
            if self.requires_field or self.requires_value or self.requires_values:
                raise ValueError("an exclude rule must not carry requires_*")
        else:
            if not self.requires_field:
                raise ValueError("a require rule needs requires_field")
            if self.requires_value is None and not self.requires_values:
                raise ValueError("a require rule needs requires_value or requires_values")
            if self.excludes_field or self.excludes_values:
                raise ValueError("a require rule must not carry excludes_*")
        object.__setattr__(self, "values", tuple(self.values))
        if bool(self.value) == bool(self.values):
            raise ValueError(
                "a rule needs exactly one of value or values; both or neither leaves "
                "it ambiguous which one the trigger is"
            )
        if self.value == NONE or NONE in self.values:
            # A rule keyed on absence would fire on every unfilled field and is
            # unfixable once shipped: absence is not a value in this pack.
            raise ValueError("a rule may not be written against NONE")
        object.__setattr__(self, "excludes_values", tuple(self.excludes_values))
        object.__setattr__(self, "requires_values", tuple(self.requires_values))

    @property
    def triggers(self) -> tuple[str, ...]:
        """Every value that fires this rule, however it was declared."""
        return self.values or (self.value,)


@dataclass(frozen=True, kw_only=True)
class HeadPhrase:
    """How an entity's opening noun phrase is assembled, for one kind.

    Every field named here is **consumed** -- it is spoken (or deliberately not
    spoken) by the head phrase and never renders again as its own clause. That
    is what stops "a heavy freighter" being followed by a redundant "vessel".
    """

    #: A **generality ladder**: candidates from most to least specific. The first
    #: with a value becomes the head noun and the rest stay silent, which is how
    #: a specific ``subkind`` ("heavy freighter") suppresses the generic ``kind``
    #: it already implies.
    noun: tuple[str, ...]
    #: Fields voiced as bare adjectives in front of the noun, in this order.
    modifiers: tuple[str, ...] = ()
    #: A field on a *different* axis that takes the head-noun position whenever
    #: it has a value -- a creature's body plan, which must be the subject of its
    #: sentence rather than a trailing modifier.
    #:
    #: It does not silence the ladder: when the subject leads, the ladder's
    #: winner falls back to its own clause ("a segmented worm body, an
    #: insectoid"). The **modifiers ride with the subject** -- they fold in as
    #: leading adjectives on it ("a large battle-scarred segmented worm body"),
    #: because a pattern grammar has somewhere better to put them than a
    #: sentence of their own. That was not true of the clause grammar, where a
    #: promoted subject dropped its modifiers and they had to fall back to their
    #: own clause; it is true of the sentence grammar, and the coverage
    #: validator relies on it. With no value it does not fire at all, and the
    #: head phrase is assembled exactly as it would have been -- which is what
    #: keeps a brief supporting slot, where the subject was never drawn, reading
    #: as "a large parasitic brood" rather than "a creature or being, a
    #: parasitic brood".
    subject: str | None = None
    #: A field voiced as an apposition immediately after the head noun ("a
    #: large warship, a starship"), even though the noun ladder consumed it.
    #:
    #: This exists for one specific failure. The ladder is a *generality*
    #: ladder: a specific ``subkind`` suppresses the generic ``kind`` it
    #: implies, which is usually right and here was catastrophic -- the word
    #: "vessel" was the only thing in the whole prompt saying the subject was a
    #: spacecraft, and it was never spoken. "A large battle-scarred warship
    #: with a hammerhead prow hull" drew an ocean-going warship, reliably,
    #: because every word in it is also a naval word. Naming the category once
    #: costs two tokens and settles it.
    #:
    #: An apposition is set off on both sides in English, so the rendered phrase
    #: carries a trailing comma (", a wreck,"). ``engine.prose._tidy`` closes it
    #: against whatever punctuation the pattern adds, which is why no pattern has
    #: to know the comma is there.
    #:
    #: Silent when it names the field that won the ladder, so it never says the
    #: same noun twice.
    apposition: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "noun", tuple(self.noun))
        object.__setattr__(self, "modifiers", tuple(self.modifiers))
        overlap = set(self.noun) & set(self.modifiers)
        if overlap:
            raise ValueError(
                f"{sorted(overlap)} is both a head noun and a head modifier; a field is "
                "voiced once or not at all"
            )
        if self.subject is not None and self.subject in set(self.noun) | set(self.modifiers):
            raise ValueError(
                f"{self.subject!r} is the head subject and also on the noun ladder or in "
                "the modifiers; the subject is a promotion, not a duplicate"
            )


#: Placeholders a clause template may use. ``a_value`` articles the value only
#: when its head noun is singular, so one template serves "a cargo pod" and
#: "hazard chevrons"; ``first``/``second`` are the two entity references a
#: relation joins.
TEMPLATE_PLACEHOLDERS: frozenset[str] = frozenset({"value", "a_value", "a", "first", "second"})

# ---------------------------------------------------------------------------
# The sentence grammar
# ---------------------------------------------------------------------------
#
# A genre writes whole English sentences with named holes in them and the
# renderer fills the holes; it never learns what any of them mean. Four
# constructs, no more:
#
#   ``{field}``      a slot -- that field's rendered phrase.
#   ``{a, b, c}``    a list slot -- whichever members resolved, in order.
#   ``[ ... ]``      an optional segment, emitted only when every slot inside
#                    it resolves. Never nested.
#   anything else    literal text.
#
# Two rules decide the render, and they are the whole control flow. A pattern
# is spoken only when every slot *outside* a bracketed segment resolves, and a
# field spoken once is **consumed**. The second rule is what lets a genre write
# a ladder of fallbacks -- the first pattern that can fire wins and the rest
# quietly stand down -- without a ``requires`` list for the two to drift apart.
#
# The point of the whole mechanism: a clause list can only ever attach a detail
# with a comma, so every field arrived in the same grammatical relationship to
# the subject whatever its real one was. Here the connector, the verb and the
# possessive are written by the genre, next to the noun they agree with.

#: Slots the renderer fills from grammar rather than from a resolved field.
#: Never consumed: they describe how the entity is spoken, not a detail about
#: it, so a later pattern may reach for them again.
GRAMMAR_SLOTS: frozenset[str] = frozenset(
    {"subject", "pronoun", "pronoun_object", "possessive", "copula", "pronoun_copula"}
)


#: Slot names a context sentence may use beyond the grammar slots: the context
#: value bare, and its articled form. A context sentence is a ``Sentence`` but
#: has no entity, so its legal-slot set is its own.
CONTEXT_SLOTS: frozenset[str] = frozenset({CONTEXT_FIELD, "a_context"})


@dataclass(frozen=True, kw_only=True)
class Literal:
    """Fixed text between a pattern's holes."""

    text: str


@dataclass(frozen=True, kw_only=True)
class Slot:
    """One ``{field}`` hole."""

    name: str


@dataclass(frozen=True, kw_only=True)
class ListSlot:
    """One ``{a, b, c}`` hole: the members that resolved, joined as English."""

    names: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "names", tuple(self.names))


@dataclass(frozen=True, kw_only=True)
class Optional:
    """One ``[ ... ]`` segment: emitted only when every slot inside resolves."""

    segments: tuple["Literal | Slot | ListSlot", ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "segments", tuple(self.segments))


#: One parsed piece of a sentence pattern.
Segment = Literal | Slot | ListSlot | Optional


def _sentence_error(text: str, reason: str) -> ValueError:
    return ValueError(f"sentence pattern {text!r} {reason}")


def _parse_slot(text: str, content: str) -> "Slot | ListSlot":
    """Parse one ``{...}`` body into a slot or a list slot."""
    parts = [part.strip() for part in content.split(",")]
    if len(parts) == 1:
        if not parts[0]:
            raise _sentence_error(text, "has an empty slot")
        return Slot(name=parts[0])
    for part in parts:
        if not part:
            raise _sentence_error(text, "has an empty member in a list slot")
    if len(set(parts)) != len(parts):
        raise _sentence_error(text, "names the same field twice in one list slot")
    return ListSlot(names=tuple(parts))


def _parse_sentence(text: str) -> tuple[Segment, ...]:
    """Parse one pattern into its ordered segments.

    Raises ``ValueError`` naming the pattern for anything the mini-language
    cannot mean. Parsed once, at construction, and cached on the ``Sentence``,
    so the renderer never re-reads the text.
    """
    stack: "list[list[Segment]]" = [[]]
    literal: "list[str]" = []

    def flush() -> None:
        if literal:
            stack[-1].append(Literal(text="".join(literal)))
            literal.clear()

    index = 0
    while index < len(text):
        char = text[index]
        if char == "[":
            flush()
            if len(stack) > 1:
                raise _sentence_error(
                    text,
                    "nests a bracketed segment inside another; optionals do not nest",
                )
            stack.append([])
        elif char == "]":
            flush()
            if len(stack) == 1:
                raise _sentence_error(
                    text, "closes a bracketed segment that was never opened"
                )
            inner = stack.pop()
            if not any(isinstance(seg, (Slot, ListSlot)) for seg in inner):
                raise _sentence_error(
                    text,
                    "has a bracketed segment with no slot in it, so it would "
                    "either always be spoken or contribute only a gap",
                )
            stack[-1].append(Optional(segments=tuple(inner)))
        elif char == "{":
            flush()
            close = text.find("}", index + 1)
            if close < 0:
                raise _sentence_error(text, "opens a slot that is never closed")
            stack[-1].append(_parse_slot(text, text[index + 1 : close]))
            index = close
        else:
            literal.append(char)
        index += 1

    if len(stack) > 1:
        raise _sentence_error(text, "opens a bracketed segment that is never closed")
    flush()
    if not any(isinstance(seg, (Slot, ListSlot)) for seg in stack[0]):
        raise _sentence_error(
            text,
            "has no slot outside a bracketed segment, so it would fire for every "
            "entity and could never stand down",
        )
    return tuple(stack[0])


def pattern_slots(pattern: "Sentence") -> tuple[str, ...]:
    """Every field name a pattern can speak, optionals included."""
    names: list[str] = []
    for segment in pattern._segments:
        if isinstance(segment, Slot):
            names.append(segment.name)
        elif isinstance(segment, ListSlot):
            names.extend(segment.names)
        elif isinstance(segment, Optional):
            for inner in segment.segments:
                if isinstance(inner, Slot):
                    names.append(inner.name)
                elif isinstance(inner, ListSlot):
                    names.extend(inner.names)
    return tuple(names)


def pattern_covers(pattern: "Sentence", field: str) -> bool:
    """Whether ``pattern`` voices ``field`` unconditionally.

    Unconditionally means the pattern fires whenever ``field`` has a value and
    actually speaks it: every slot outside a bracket is either ``field`` itself,
    a grammar slot (which always resolves), or a list slot that contains it. A
    field that appears only inside an optional segment, or only in a pattern
    gated on another required slot, is not covered -- that pattern can stand
    down while the field is still drawn.
    """
    spoken = False
    for segment in pattern._segments:
        if isinstance(segment, Optional):
            continue
        if isinstance(segment, Slot):
            if segment.name == field:
                spoken = True
            elif segment.name not in GRAMMAR_SLOTS:
                return False
        elif isinstance(segment, ListSlot):
            if field in segment.names:
                spoken = True
            else:
                return False
        else:
            continue
    return spoken


def _always_consumed(head: "HeadPhrase | None") -> frozenset[str]:
    """Clause heads a head phrase voices on every render where they have a value.

    Mirrors ``engine.prose._entity_parts``. A head phrase that promotes a
    ``subject`` consumes that subject always, but the noun ladder's *winner*
    stays a clause -- so no noun field is guaranteed. The modifiers are
    consumed either way: they fold in as leading adjectives on the head noun,
    promoted or not. A head phrase with no subject consumes its whole ladder.
    """
    if head is None:
        return frozenset()
    consumed: set[str] = set()
    consumed.update(head.modifiers)
    if head.subject is None:
        consumed.update(head.noun)
        if head.apposition is not None:
            consumed.add(head.apposition)
    else:
        consumed.add(head.subject)
        if head.apposition is not None and head.apposition != head.subject:
            consumed.add(head.apposition)
    return frozenset(consumed)


@dataclass(frozen=True, kw_only=True)
class Sentence:
    """One sentence of an entity's description, written as English with holes.

    A genre author writes the sentence they want and marks the holes; the
    renderer fills them and never learns what any of them mean. That is the
    whole difference from the clause list this replaces -- a clause list can
    only ever attach a detail with a comma, so every field arrived in the same
    grammatical relationship to the subject whatever its real one was, and the
    output read as a pile rather than as prose.

    ``_segments`` caches the parse so the renderer never re-reads ``text``.
    """

    text: str
    #: Affordances the place must have before this sentence may be drawn.
    #:
    #: A sentence can be true of the scene and wrong about the room it is in.
    #: "In the distance, a stack of sealed cargo pods is visible" is a fine
    #: sentence in orbit and nonsense in a cockpit, and nothing about the
    #: *context value* is wrong -- it is the framing that needs depth. Empty
    #: means the sentence fits anywhere, which is every sentence a pack writes
    #: until it has a reason to say otherwise. Genre-blind: the engine only
    #: checks that one set of words contains another.
    needs: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        object.__setattr__(self, "needs", frozenset(self.needs))
        object.__setattr__(self, "_segments", _parse_sentence(self.text))


@dataclass(frozen=True, kw_only=True)
class Archetype:
    """A category of thing that shares a grammar.

    ``kind`` says what pools an entity draws from. An archetype says how the
    result is **spoken** -- and the two are not the same axis, which is the
    defect this type exists to fix.

    Before it, every kind shared one clause-template table, so a nebula was
    "clad in hydrogen and helium cloud" and a person was "clad in" their
    clothes, because ``templates`` had no kind dimension at all. The pack had
    the missing concept five times over as module-private tuples -- the living
    kinds, the movable kinds, the diffuse subkinds -- but they could only delete
    values from pools, never change a word of grammar. An archetype is those
    tuples promoted to the contract and given the power they were reaching for.

    A genre declares its own set. The names are the genre's business; a fantasy
    pack that declares ``figure``, ``beast``, ``structure`` and ``phenomenon``
    gets the same machinery with none of the sci-fi vocabulary, which is what
    makes a second genre a data module.

    Every field is an *override*. Anything left unset falls through to the
    ``ProseSpec``, so an archetype that only needs different wording for one
    field says only that.
    """

    #: Entity fields this archetype never voices. A phenomenon has no
    #: integument, so ``material`` and ``surface_detail`` are omitted rather
    #: than drawn and talked around -- absence by omission, the pack's rule.
    #:
    #: Applied in the detail budget, which is the one place allowed to decide a
    #: field is unspoken **and** writes it back to ``None``. Suppressing it in
    #: the renderer instead would leave the value standing in ``prompt_json``,
    #: promising the image a detail it was never asked for.
    omits: frozenset[str] = frozenset()
    #: The most optional clause heads this archetype ever speaks, or ``None``
    #: for "whatever the caller's allowance says".
    #:
    #: A creature's component clauses ARE its anatomy -- six of them build one
    #: organism. A station's are six micro-greebles at a scale a model cannot
    #: place, and they outweigh the silhouette. One allowance for both was the
    #: defect: the GOOD bucket of the reference corpus was creatures and people,
    #: the BAD bucket stations, artifacts, wrecks and worlds, with identical
    #: grammar and only the clause count differing.
    #:
    #: Applied as a floor on the caller's allowance (``min``), never as a raise:
    #: a four-entity scene must not get *more* detail because one slot holds a
    #: creature.
    detail_cap: int | None = None
    #: Fields promoted to the front of this archetype's spend order. Fields not
    #: named here follow in ``ProseSpec.detail_priority`` order, so an archetype
    #: states only what it wants differently.
    detail_priority: tuple[str, ...] = ()
    #: Fields filled by a weighted draw instead of a fixed order. A fixed
    #: ``detail_priority`` spends the allowance in the same order on every render,
    #: so every field below the cap is a dead widget -- drawn, resolved, written
    #: into the JSON and never spoken. A rotation turns the tail into a draw: the
    #: core fields still speak in order and the reserved slots are filled by one
    #: of these fields, weighted, so a batch shows all of them.
    #:
    #: Applied only on a slot that speaks at full depth (the hero slot, a wired
    #: slot, the Scene Entity node). A brief supporting slot keeps the fixed order:
    #: its allowance is small and belongs to the silhouette, not to a random detail.
    detail_rotation: Mapping[str, float] = field(default_factory=dict)
    #: Allowance slots reserved for ``detail_rotation``. Zero disables the draw even
    #: when the map is populated.
    detail_rotation_slots: int = 0
    #: Per-field clause wording, overriding ``ProseSpec.templates``.
    templates: Mapping[str, str] = field(default_factory=dict)
    #: The opening noun phrase, overriding ``ProseSpec.head_phrase``.
    head_phrase: "HeadPhrase | None" = None
    #: This archetype's sentence patterns, overriding
    #: ``ProseSpec.entity_sentences``. Empty inherits the pack's, and a pack
    #: with none renders through the single-sentence fallback.
    sentences: tuple[Sentence, ...] = ()
    #: Third-person grammar. Empty inherits the ``ProseSpec``'s.
    pronoun: str = ""
    pronoun_plural: str = ""
    possessive: str = ""
    possessive_plural: str = ""
    pronoun_copula: str = ""
    pronoun_object: str = ""
    pronoun_object_plural: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "omits", frozenset(self.omits))
        object.__setattr__(self, "detail_priority", tuple(self.detail_priority))
        object.__setattr__(self, "detail_rotation", _freeze(self.detail_rotation))
        object.__setattr__(self, "templates", _freeze(self.templates))
        object.__setattr__(self, "sentences", tuple(self.sentences))


@dataclass(frozen=True, kw_only=True)
class ProseSpec:
    """How a genre's clauses are ordered and worded.

    Clause order lives here rather than in the renderer because it is genre
    knowledge: a creature leads its sentence with its body plan (a non-human
    body must be the *subject*, not a trailing modifier), while a vessel leads
    with its class. Hardcoding either in the engine would break the seam.

    The renderer knows five things and no more: consume the head phrase, fold in
    any composed companions, walk the clause order, format each template, and
    compose the scene into connected prose when narrative mode is declared.
    Every genre-specific choice above is a field on this dataclass.
    """

    #: Top-level section order, e.g. ("environment", "entities", "relations").
    scene_order: tuple[str, ...]
    #: Default within-entity clause order. Contains only fields that head a
    #: clause -- a field with ``renders_with`` set is composed into another.
    entity_clause_order: tuple[str, ...]
    #: Per-kind overrides of the above.
    kind_clause_order: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    #: Kinds whose ``form`` clause is the subject of the entity sentence.
    subject_leading_kinds: frozenset[str] = frozenset()
    #: Clause templates keyed by field name, using ``TEMPLATE_PLACEHOLDERS``. A
    #: field with no entry renders as a bare "{value}".
    templates: Mapping[str, str] = field(default_factory=dict)
    #: ``{kind_or_POOL_DEFAULT_KEY: HeadPhrase}``. Empty means no head phrase at
    #: all: every field renders as its own clause, which is what a minimal
    #: fixture pack wants and what keeps the seam cheap to exercise.
    head_phrase: Mapping[str, HeadPhrase] = field(default_factory=dict)
    #: ``{field: (anchor, ...)}`` -- the *soft* composition. The field is folded
    #: in as a leading adjective on the first anchor that has a value ("gunmetal
    #: grey titanium alloy"); with no anchor standing it falls back to its own
    #: clause. Distinct from ``FieldSpec.renders_with``, which is the hard form:
    #: a count never stands alone, but a hull colour usefully can.
    adjective_of: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    #: Scene-composition mode. False renders one sentence per section -- the
    #: environment, then each entity, then each relation, in ``scene_order`` --
    #: which is the backward-compatible default. True composes the scene into
    #: connected prose: the environment is its own setting sentence, and a
    #: relation is woven into its first endpoint's sentence as a relative
    #: clause.
    narrative_mode: bool = False
    #: The environment's setting-sentence template ("Set in {a_value}"). Empty
    #: falls back to the ``templates`` entry for the environment field.
    environment_sentence: str = ""
    #: Ordered ``(affordance, suffix)`` pairs. The first pair whose affordance the
    #: environment affords appends its suffix to the setting sentence. A
    #: text-to-image model grounds anything it is not told floats: a station in a
    #: debris belt is drawn standing on the debris.
    environment_staging: tuple[tuple[str, str], ...] = ()
    #: The context sentence plan, emitted once per scene after the entities when
    #: the pack declares a ``context`` field. One pattern is drawn at random per
    #: scene; ``{context}`` is the value bare, ``{a_context}`` its articled form,
    #: and ``{pronoun_object}`` the subject's object pronoun. Empty emits nothing.
    context_sentences: tuple[Sentence, ...] = ()
    #: A sentence naming the genre, emitted when there is no environment to
    #: carry it. Empty emits nothing.
    #:
    #: A prompt has to say what kind of world it is somewhere. Every individual
    #: noun in "a large battle-scarred warship with a hammerhead prow hull" is
    #: also a naval noun, and with no genre anywhere in the sentence a model
    #: draws the reading it has seen most. This is a *frame*, not appended
    #: scenery -- see the note in ``environment_sentence``'s pack value.
    scene_frame: str = ""
    #: The copula that conjugates a singular subject to its situation.
    copula: str = "is"
    #: The copula for a plural subject.
    copula_plural: str = "are"
    #: The lead word that introduces the grouped trailing-descriptor clause.
    descriptor_lead: str = "with"
    #: Template that appends a relation's spatial position to its standalone
    #: sentence: ", {value}" turns "the scout ship is attacking the freighter"
    #: into "... the freighter, from behind". Empty omits the position.
    relation_position_template: str = ", {value}"
    #: How an entity is cut into sentences. **Empty means one sentence per
    #: entity** -- subject, every surviving clause behind ``descriptor_lead``,
    #: then the situation -- which is the shape a minimal pack gets for free and
    #: what keeps the genre-seam fixture renderable with no prose authoring at
    #: all. A shipped genre declares real cuts: five clauses in one sentence put
    #: thirty tokens between a subject and its verb.
    entity_sentences: tuple[Sentence, ...] = ()
    #: Third-person grammar for an entity, used by a pattern's grammar slots.
    #: A person is ``they/their/are``; the pack never knows a spacefarer's
    #: gender and must not guess one.
    pronoun: str = "it"
    pronoun_plural: str = "they"
    possessive: str = "its"
    possessive_plural: str = "their"
    pronoun_copula: str = "is"
    #: The object pronoun, for a context sentence that names the subject
    #: obliquely ("Beyond them, ..."). A person is "them" in both numbers.
    pronoun_object: str = "it"
    pronoun_object_plural: str = "them"
    detail_priority: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "scene_order", tuple(self.scene_order))
        object.__setattr__(self, "entity_clause_order", tuple(self.entity_clause_order))
        object.__setattr__(
            self,
            "kind_clause_order",
            MappingProxyType({k: tuple(v) for k, v in dict(self.kind_clause_order).items()})
            if self.kind_clause_order
            else _EMPTY_MAP,
        )
        object.__setattr__(self, "subject_leading_kinds", frozenset(self.subject_leading_kinds))
        object.__setattr__(self, "templates", _freeze(self.templates))
        object.__setattr__(self, "detail_priority", tuple(self.detail_priority))
        object.__setattr__(self, "head_phrase", _freeze(self.head_phrase))
        object.__setattr__(
            self,
            "adjective_of",
            MappingProxyType({k: tuple(v) for k, v in dict(self.adjective_of).items()})
            if self.adjective_of
            else _EMPTY_MAP,
        )
        object.__setattr__(self, "entity_sentences", tuple(self.entity_sentences))
        object.__setattr__(self, "context_sentences", tuple(self.context_sentences))
        object.__setattr__(
            self, "environment_staging",
            tuple((affordance, suffix) for affordance, suffix in self.environment_staging),
        )
        self._validate_templates()

    def _check_template(self, name: str, template: str) -> None:
        """Reject a malformed template at pack construction, not at render time.

        A typo in a template is otherwise invisible until the seed that first
        draws that field -- which may be days after the change, in a user's
        queue rather than in a test. Shared by the clause templates and the
        setting ``environment_sentence``.
        """
        for _, placeholder, _, _ in Formatter().parse(template):
            if placeholder is None:
                continue
            if placeholder == "":
                raise ValueError(
                    f"template for {name!r} uses a positional placeholder; templates "
                    "are keyword-only so a genre author can reorder them freely"
                )
            if placeholder not in TEMPLATE_PLACEHOLDERS:
                raise ValueError(
                    f"template for {name!r} uses unknown placeholder {placeholder!r}; "
                    f"expected one of {sorted(TEMPLATE_PLACEHOLDERS)}"
                )

    def _validate_templates(self) -> None:
        for name, template in self.templates.items():
            self._check_template(name, template)
        if self.environment_sentence:
            self._check_template("environment_sentence", self.environment_sentence)
        if self.scene_frame:
            self._check_template("scene_frame", self.scene_frame)
        if self.relation_position_template:
            self._check_template("relation_position_template", self.relation_position_template)
        self._validate_context_sentences()

    def _validate_context_sentences(self) -> None:
        """A context sentence is a ``Sentence`` whose slots are the context value
        (bare or articled) and the grammar slots. It must name the context, or it
        would say nothing about the scene; it must not name a field, because a
        context sentence has no entity to take one from."""
        legal = CONTEXT_SLOTS | GRAMMAR_SLOTS
        for index, pattern in enumerate(self.context_sentences):
            names: list[str] = []
            for segment in pattern._segments:
                inner = segment.segments if isinstance(segment, Optional) else (segment,)
                for piece in inner:
                    if isinstance(piece, Slot):
                        names.append(piece.name)
                        if piece.name not in legal:
                            raise ValueError(
                                f"context_sentences[{index}] names {piece.name!r}, which is "
                                "neither the context value, its articled form, nor a grammar slot"
                            )
                    elif isinstance(piece, ListSlot):
                        raise ValueError(
                            f"context_sentences[{index}] uses a list slot; a context sentence "
                            "names the context once and has no entity to list fields from"
                        )
            if CONTEXT_FIELD not in names and "a_context" not in names:
                raise ValueError(
                    f"context_sentences[{index}] does not name {CONTEXT_FIELD!r}, so it says "
                    "nothing about the scene"
                )


@dataclass(frozen=True, kw_only=True)
class GenrePack:
    """One genre's complete data contract.

    ``class_suffix`` is declared rather than derived from ``slug``: a genre's
    class name is part of a saved workflow's node id, so it must be stated
    exactly ("SciFi", not the "Scifi" a naive title-case of "scifi" produces).
    Getting it wrong later would orphan every saved graph.
    """

    #: Lowercase, identifier-safe genre key. Appears in ``prompt_json`` as the
    #: per-entity ``genre`` tag, so a foreign-genre entity stays traceable.
    slug: str
    #: Human-readable genre name, used in node display names ("Sci-Fi").
    display: str
    #: PascalCase fragment for the generated class and node ids ("SciFi").
    class_suffix: str
    #: The control tokens every kind-scoped pool and label map is keyed by.
    kinds: tuple[str, ...]
    #: The entity morphology, in widget order. Ordered mapping; do not reorder.
    entity_fields: Mapping[str, FieldSpec]
    #: ``environment``, ``situation`` and ``relation``.
    scene_fields: Mapping[str, FieldSpec]
    #: ``{field: {kind_or_POOL_DEFAULT_KEY: (values, ...)}}``.
    pools: Mapping[str, Mapping[str, tuple[str, ...]]] = field(default_factory=dict)
    #: ``{field: {kind: label}}`` -- what the frontend rewrites widget labels to.
    labels: Mapping[str, Mapping[str, str]] = field(default_factory=dict)
    #: ``{noun_field: count_field}``. Derived-checkable against the specs'
    #: ``count_partner``, and kept as its own map so a validator can iterate the
    #: pairs without walking every field.
    counts: Mapping[str, str] = field(default_factory=dict)
    #: ``{field: {value: tag}}``. Field-scoped rather than a flat value map:
    #: two pools may legitimately share a word, and a flat map would silently
    #: give both the same tag.
    tags: Mapping[str, Mapping[str, str]] = field(default_factory=dict)
    constraints: tuple[ConstraintRule, ...] = ()
    #: ``{(field, kind)}`` whose pool is deliberately empty. A pack declares
    #: these so ``tests/validate_data.py`` can tell a decision from a hole, and
    #: so a declaration that stopped being true is reported as stale rather than
    #: quietly outliving the pool it described.
    omitted_pools: frozenset[tuple[str, str]] = frozenset()
    #: Groups of fields that draw from **one** vocabulary on purpose, so a value
    #: shared between two of them is authoring rather than an accident (the
    #: colour fields: a hull, its trim and its exhaust are three roles over one
    #: palette of pigment words). Everywhere else a shared value lets one entity
    #: draw the same string twice and the engine has to silence a clause the
    #: pool paid for, which the validator reports.
    shared_vocabulary: tuple[frozenset[str], ...] = ()
    #: Groups of fields whose values must **differ** within one entity -- the
    #: inverse of ``shared_vocabulary``, and needed for the same reason that one
    #: is: a pool shared by several fields will land the same string in two of
    #: them.
    #:
    #: The engine's own repeat guard covers clause heads and deliberately skips
    #: composed companions, because "six thrusters ... six eyes" is how English
    #: counts two things. That reasoning holds for numerals and fails for the
    #: collective quantifiers in the same pool: "a dozen exhaust plumes, a dozen
    #: railguns, a constellation of arrays" reads as a tic rather than as a
    #: count, and it was one of the first things reported about the output.
    #: A pack that wants its counts visibly different says so here.
    distinct_within_entity: tuple[frozenset[str], ...] = ()
    #: ``{band: (environment value, ...)}`` -- the environment pool grouped into
    #: the coarse places a scene can be. Declared so a pack can write one rule
    #: about "anywhere indoors" instead of one rule per interior.
    #:
    #: It is *not* consulted by the engine. It is a vocabulary for the pack's
    #: own constraint rules, which is why the engine stays unable to tell an
    #: orbit from a corridor.
    environment_bands: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    #: {control_field: {group_name: (control values, ...)}}.
    #:
    #: A pool may be keyed by a group name as well as by a raw control value, so a
    #: genre says "every solid world has one of these shapes" once instead of once
    #: per world. Lookup is raw value first, then group, then the fall-through --
    #: so a single subkind that needs its own pool still overrides its group.
    pool_groups: Mapping[str, Mapping[str, tuple[str, ...]]] = field(default_factory=dict)
    #: {(field, scope key)} that are ALLOWED to resolve through the fall-through
    #: instead of through a key of their own. Declared, so "I forgot to classify
    #: 'sarcophagus pod'" is a validator failure rather than a silent bad render.
    scope_fallthrough: frozenset[tuple[str, str]] = frozenset()
    #: ``{motif: (substring, ...)}`` -- word families whose share is measured across
    #: the WHOLE prompt rather than within one field.
    #:
    #: A per-value check cannot see a bias that is spread out: "ice-encrusted" in
    #: the conditions, three ices in the materials, frost in the surface details,
    #: five cold environments and four white colours are each unremarkable, and
    #: together they put ice in a quarter of all output. A motif is the declaration
    #: that those words are one idea, so a sweep can report the idea's share.
    #:
    #: Not consulted by the engine -- it is an instrument for the maintainer's
    #: sweep, in the same way ``environment_bands`` is a vocabulary for the pack's
    #: own rules.
    motifs: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    #: ``{field: {token: spoken form}}`` -- how a value is said in a sentence when
    #: that differs from how it reads in a dropdown.
    #:
    #: A dropdown token has to be short and scannable ("hospital ship") and is
    #: also a control token that pools, groups, tags and rules are keyed by, so
    #: renaming it cascades through the whole pack. What a sentence needs is
    #: different: ONE noun phrase whose head names what the thing is, in-genre
    #: ("hospital starship"). Before this field the only way to get the category
    #: into the sentence was an apposition ("a hospital ship, a starship"), which
    #: a text encoder reads as two objects.
    #:
    #: Also where a compound colour gets its hyphen: "bone-white armour" is
    #: correct English for a compound modifier and stops "bone" being read as a
    #: noun.
    spoken: Mapping[str, Mapping[str, str]] = field(default_factory=dict)
    #: ``{environment value or band name: affordances}``. A raw environment
    #: value's entry REPLACES its band's entry; a value with no entry takes its
    #: band's.
    #:
    #: Affordances are what a *place* provides -- ground, floor, water, sky,
    #: open space, a dock, built structure, room for something vast, sunlight,
    #: cold, dust, life. A value declares what it *needs* in ``value_needs`` and
    #: is excluded from every place whose affordances lack any of them. Genre-
    #: blind: the engine only compares two sets of words.
    place_affordances: Mapping[str, frozenset[str]] = field(default_factory=dict)
    #: ``{field: {value: needs}}`` -- what a value requires of the place. A value
    #: is excluded from every environment whose affordances lack ANY of its
    #: needs.
    value_needs: Mapping[str, Mapping[str, frozenset[str]]] = field(default_factory=dict)
    #: ``{field: {pool key: needs}}`` -- the need every value authored under that
    #: key has unless it declares its own. A value under several keys resolves to
    #: the union of their defaults; an explicit entry in ``value_needs`` (even an
    #: empty frozenset) replaces that entirely. This is how a whole pool key is
    #: classified once instead of once per value.
    default_needs: Mapping[str, Mapping[str, frozenset[str]]] = field(default_factory=dict)
    #: ``{field: {value: frozenset(trait)}}`` -- what a value *is* (a role, a size
    #: class, a state). Expanded with ``trait_conflicts`` into ordinary exclusion
    #: rules by genre-blind code; the engine never learns what a trait means.
    value_traits: Mapping[str, Mapping[str, frozenset[str]]] = field(default_factory=dict)
    #: ``{field: {value: stances}}`` -- how a shape can hold itself up. A torus
    #: cannot stand on the ground; a walker chassis cannot hang in vacuum doing
    #: something that needs footing; a world only orbits. Place affordances
    #: cannot express this, because the failure is not the place -- it is the
    #: pairing of a silhouette with a place and an action.
    value_stances: Mapping[str, Mapping[str, frozenset[str]]] = field(default_factory=dict)
    #: ``{affordance: stances the place supports}``.
    place_stances: Mapping[str, frozenset[str]] = field(default_factory=dict)
    #: ``{affordance: stances a place that affords it can never support}``,
    #: whatever its other affordances grant. A body that *has* a blocked stance
    #: is kept out of the place entirely: a wheeled robot at rest is still a
    #: wheeled robot on the sea floor.
    #:
    #: Support is a union, so a seabed that affords ``floor`` (a diver walks it,
    #: a wreck rests on it) also supported rolling, and a wheeled security robot
    #: was drawn across a hydrothermal vent field. Water does not stop a body
    #: resting or walking on the bottom; it stops a wheel. Removing ``floor``
    #: instead cost every legitimate seabed act at once. A block is subtracted
    #: after the union, so it reaches the stance rules and type feasibility alike.
    place_stance_blocks: Mapping[str, frozenset[str]] = field(default_factory=dict)
    #: ``{field: {value: tier}}`` -- how much a value is worth looking at.
    #:
    #: Every other mechanism in this pack can only *remove* a value. None of
    #: them can say that a thing happening is worth a picture, so widening a
    #: pool raises coverage and lowers the mean interest: the situation tests
    #: select for small, safe, literal actions, and a pool of four hundred of
    #: those is four hundred ways to be dull. A tier is the pack stating which
    #: end of its own vocabulary it wants to spend its draws on.
    value_tiers: Mapping[str, Mapping[str, str]] = field(default_factory=dict)
    #: ``{tier: relative draw weight}``. Multiplied into ``FieldSpec.weights``.
    tier_weights: Mapping[str, float] = field(default_factory=dict)
    #: ``(trigger trait, target trait)`` pairs that cannot both hold of one
    #: entity. The trigger stands and the target gives way.
    trait_conflicts: tuple[tuple[str, str], ...] = ()
    #: ``{"trigger|target": reason}`` -- the warning text a trait conflict shows
    #: when a locked value wins over it. A reason may negate; it never reaches
    #: the prompt.
    trait_reasons: Mapping[str, str] = field(default_factory=dict)
    #: ``{kind: capabilities}`` -- what a kind of thing can do (agent, mobile,
    #: vessel, dockable, massive). Read by ``relation_roles``.
    kind_capabilities: Mapping[str, frozenset[str]] = field(default_factory=dict)
    #: ``{relation value: (first endpoint needs, second endpoint needs)}``.
    #: Expanded into require rules on ``first.kind`` / ``second.kind``.
    relation_roles: Mapping[str, tuple[frozenset[str], frozenset[str]]] = field(
        default_factory=dict
    )
    #: Lint vocabularies, read only by ``tests/validate_data.py``. Genre-blind:
    #: sci-fi lists Earth objects a model will draw instead of the subject; a
    #: fantasy pack lists modern ones.
    foreign_nouns: tuple[str, ...] = ()
    foreign_noun_fields: tuple[str, ...] = ()
    foreign_noun_allowlist: frozenset[str] = frozenset()
    #: ``{affordance: (keyword, ...)}`` -- a value in ``affordance_lint_fields``
    #: whose text contains a keyword must declare that need (or be allowlisted).
    affordance_keywords: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    affordance_lint_fields: tuple[str, ...] = ()
    affordance_allowlist: frozenset[str] = frozenset()
    #: ``{stance: (keyword, ...)}`` -- words that say how a body moves. A situation naming
    #: one must list that stance in ``value_stances``, so ``_expand_stances`` keeps it from
    #: every form that cannot move that way. Read only by ``tests/validate_data.py``.
    stance_keywords: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    #: ``{type, type group or kind: features}`` -- what a body has (arms, jaws, a crust).
    #: The most specific entry wins. Read only by ``tests/validate_data.py``.
    body_features: Mapping[str, frozenset[str]] = field(default_factory=dict)
    #: ``{feature: (keyword, ...)}`` -- the words that name a feature in a value.
    body_keywords: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    #: The fields the body lint reads.
    body_lint_fields: tuple[str, ...] = ()
    #: ``{feature: (keyword, ...)}`` -- the words that name a body feature in a *part*.
    #: A part pool is keyed by kind, so a value can be bolted to a body that has no
    #: such feature -- a spare track on a drop pod. The situation lint cannot catch
    #: that, because a situation such as "throwing a track" relies on the stance check.
    #: Read only by ``tests/validate_data.py``.
    part_keywords: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    #: The entity fields the part lint reads.
    part_lint_fields: tuple[str, ...] = ()
    #: ``{name: Archetype}`` -- the genre's grammar categories. Empty means the
    #: pack speaks every kind the same way, which is what a minimal pack and the
    #: seam fixture want.
    archetypes: Mapping[str, Archetype] = field(default_factory=dict)
    #: ``{kind: archetype name}``. A kind with no entry falls through to
    #: ``archetypes[POOL_DEFAULT_KEY]`` if the pack declares one, and otherwise
    #: to the ``ProseSpec`` alone.
    archetype_of_kind: Mapping[str, str] = field(default_factory=dict)
    #: The field whose value may override the kind's archetype, or empty for
    #: none. Declared rather than hardcoded because the *existence* of a second,
    #: finer axis is a contract idea while its name is a genre's business:
    #: sci-fi points this at ``subkind`` so a nebula and a moon can be different
    #: kinds of thing to talk about while sharing one ``celestial body`` kind.
    archetype_override_field: str = ""
    #: ``{value of archetype_override_field: archetype name}``. Consulted first,
    #: so a black hole leaves the ``world`` archetype for ``phenomenon`` without
    #: needing a kind of its own.
    archetype_of_override: Mapping[str, str] = field(default_factory=dict)
    #: ``{count noun field: {value: cardinality class}}`` -- how many of a thing
    #: there can be, decided by the noun rather than by what is carrying it.
    #:
    #: A count field's scope chain already asks its noun before it asks the kind
    #: (``scope=("emitters", KIND_FIELD)``), so the machinery to answer this has
    #: always been there; what was missing was the answer. With the noun
    #: unclassified the question fell through to the kind, and a kind is far too
    #: coarse to ask: a starship has one prow and a dozen hull seams, and both
    #: are ``emitters`` on a ``starship``. That is how "a dozen drive nacelles"
    #: became legal, and a model draws it as engines at both ends of the hull --
    #: the ship appears to thrust in the direction its cockpit is facing.
    #:
    #: Declared per value rather than as two hand-written tables because the
    #: alternative drifts: ``GenrePack`` expands this into the noun field's
    #: ``pool_groups`` *and* the partner count field's pool, so a class can never
    #: exist in one and not the other. Genre-blind -- the engine only ever reads
    #: the resulting pools, and a fantasy pack naming its classes "a paired
    #: greave" and "a rank of pennants" gets the same machinery.
    value_cardinality: Mapping[str, Mapping[str, str]] = field(default_factory=dict)
    #: ``{cardinality class: the quantifiers it may draw}``. Every class named in
    #: ``value_cardinality`` needs an entry here or the pack refuses to build.
    cardinality_counts: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    prose: ProseSpec = field(
        default_factory=lambda: ProseSpec(scene_order=(), entity_clause_order=())
    )
    #: ``{label shown on the node: the filter it applies}``, in dropdown order.
    #:
    #: The filter is one tag axis, and a genre may say what its ends mean: horror
    #: shows "No gore" / "Any" / "Gore only" over the same Peaceful / Any /
    #: Conflict masking, so a gore value is tagged ``conflict_only`` exactly as a
    #: weapon act is. A saved workflow stores the label, so a label, once shipped,
    #: is a compatibility surface like a dropdown value.
    scene_filter_labels: Mapping[str, str] = field(
        default_factory=lambda: OrderedDict((name, name) for name in SCENE_FILTERS)
    )
    #: The label a freshly dropped node starts on.
    scene_filter_default: str = DEFAULT_SCENE_FILTER
    #: The filter widget's tooltip when the labels are the genre's own.
    scene_filter_tooltip: str = ""

    def __post_init__(self) -> None:
        if not _IDENTIFIER_RE.match(self.slug):
            raise ValueError(f"slug {self.slug!r} must be lowercase and identifier-safe")
        if not _CLASS_SUFFIX_RE.match(self.class_suffix):
            raise ValueError(f"class_suffix {self.class_suffix!r} must be PascalCase")
        object.__setattr__(self, "kinds", tuple(self.kinds))
        # Before the pools are frozen: the cardinality classes become ordinary
        # pool groups and ordinary count pools, so everything downstream -- the
        # scope chain, the validator, the frontend payload -- sees one kind of
        # table and never learns that a cardinality class is special.
        object.__setattr__(self, "value_cardinality", _freeze_nested(self.value_cardinality))
        object.__setattr__(self, "cardinality_counts", _freeze(self.cardinality_counts))
        self._expand_cardinality()
        object.__setattr__(self, "entity_fields", _freeze(OrderedDict(self.entity_fields)))
        object.__setattr__(self, "scene_fields", _freeze(OrderedDict(self.scene_fields)))
        object.__setattr__(self, "pools", _freeze_nested(self.pools))
        object.__setattr__(self, "labels", _freeze_nested(self.labels))
        object.__setattr__(self, "counts", _freeze(self.counts))
        object.__setattr__(self, "tags", _freeze_nested(self.tags))
        object.__setattr__(self, "constraints", tuple(self.constraints))
        object.__setattr__(self, "omitted_pools", frozenset(self.omitted_pools))
        object.__setattr__(
            self, "shared_vocabulary", tuple(frozenset(g) for g in self.shared_vocabulary)
        )
        object.__setattr__(
            self,
            "distinct_within_entity",
            tuple(frozenset(g) for g in self.distinct_within_entity),
        )
        object.__setattr__(
            self,
            "environment_bands",
            MappingProxyType({k: tuple(v) for k, v in dict(self.environment_bands).items()})
            if self.environment_bands
            else _EMPTY_MAP,
        )
        object.__setattr__(
            self,
            "motifs",
            MappingProxyType({k: tuple(v) for k, v in dict(self.motifs).items()})
            if self.motifs
            else _EMPTY_MAP,
        )
        object.__setattr__(self, "spoken", _freeze_nested(self.spoken))
        object.__setattr__(self, "place_affordances", _freeze_sets(self.place_affordances))
        object.__setattr__(self, "value_needs", _freeze_nested_sets(self.value_needs))
        object.__setattr__(self, "default_needs", _freeze_nested_sets(self.default_needs))
        object.__setattr__(self, "value_traits", _freeze_nested_sets(self.value_traits))
        object.__setattr__(self, "value_stances", _freeze_nested_sets(self.value_stances))
        object.__setattr__(self, "place_stances", _freeze_sets(self.place_stances))
        object.__setattr__(
            self, "place_stance_blocks", _freeze_sets(self.place_stance_blocks)
        )
        object.__setattr__(self, "value_tiers", _freeze_nested(self.value_tiers))
        object.__setattr__(self, "tier_weights", _freeze(self.tier_weights))
        object.__setattr__(
            self,
            "trait_conflicts",
            tuple((str(a), str(b)) for a, b in self.trait_conflicts),
        )
        object.__setattr__(self, "trait_reasons", _freeze(self.trait_reasons))
        object.__setattr__(self, "kind_capabilities", _freeze_sets(self.kind_capabilities))
        object.__setattr__(
            self,
            "relation_roles",
            MappingProxyType(
                {k: (frozenset(a), frozenset(b)) for k, (a, b) in dict(self.relation_roles).items()}
            )
            if self.relation_roles
            else _EMPTY_MAP,
        )
        object.__setattr__(self, "foreign_nouns", tuple(self.foreign_nouns))
        object.__setattr__(self, "foreign_noun_fields", tuple(self.foreign_noun_fields))
        object.__setattr__(self, "foreign_noun_allowlist", frozenset(self.foreign_noun_allowlist))
        object.__setattr__(
            self,
            "affordance_keywords",
            MappingProxyType({k: tuple(v) for k, v in dict(self.affordance_keywords).items()})
            if self.affordance_keywords
            else _EMPTY_MAP,
        )
        object.__setattr__(self, "affordance_lint_fields", tuple(self.affordance_lint_fields))
        object.__setattr__(self, "affordance_allowlist", frozenset(self.affordance_allowlist))
        object.__setattr__(self, "pool_groups", _freeze_nested(self.pool_groups))
        object.__setattr__(self, "scope_fallthrough", frozenset(self.scope_fallthrough))
        object.__setattr__(self, "archetypes", _freeze(self.archetypes))
        object.__setattr__(self, "archetype_of_kind", _freeze(self.archetype_of_kind))
        object.__setattr__(
            self, "archetype_of_override", _freeze(self.archetype_of_override)
        )
        object.__setattr__(
            self, "stance_keywords",
            MappingProxyType({k: tuple(v) for k, v in dict(self.stance_keywords).items()})
            if self.stance_keywords else _EMPTY_MAP,
        )
        object.__setattr__(self, "body_features", _freeze_sets(self.body_features))
        object.__setattr__(
            self, "body_keywords",
            MappingProxyType({k: tuple(v) for k, v in dict(self.body_keywords).items()})
            if self.body_keywords else _EMPTY_MAP,
        )
        object.__setattr__(self, "body_lint_fields", tuple(self.body_lint_fields))
        object.__setattr__(
            self, "part_keywords",
            MappingProxyType({k: tuple(v) for k, v in dict(self.part_keywords).items()})
            if self.part_keywords else _EMPTY_MAP,
        )
        object.__setattr__(self, "part_lint_fields", tuple(self.part_lint_fields))
        self._validate_scene_filter()
        self._validate_structure()
        self._validate_archetypes()
        self._validate_scopes()
        object.__setattr__(self, "_derived_rules", self._derive_rules())
        object.__setattr__(self, "_effective_weights", self._derive_weights())

    def _expand_cardinality(self) -> None:
        """Turn ``value_cardinality`` into ordinary pool groups on the noun field.

        A count field's scope chain asks its noun before it asks the kind, so
        the machinery to let a noun decide its own count has always been here;
        what was missing was the answer. Unclassified, a noun fell through to
        the kind -- and a kind cannot answer it, because "prow" and "hull seam"
        are both ``emitters`` on a ``starship``.

        Only the **groups** are derived. The count pools themselves are authored
        statically, because ``scripts/builtin_options.py`` reads the pools by
        parsing the source rather than importing it, and a pool key that only
        exists after construction is a key that reader can never see. The class
        names are shared between the two by ``cardinality_counts``, so they
        cannot drift apart.

        Idempotent: ``dataclasses.replace`` re-runs ``__post_init__`` on an
        already-expanded pack -- which is how the validator plants a defect and
        how the user-options merge works -- so re-deriving the same group must
        be a no-op rather than a collision.
        """
        if not self.value_cardinality:
            return
        groups = {key: dict(value) for key, value in dict(self.pool_groups).items()}
        for noun_field in dict(self.counts):
            classes = self.value_cardinality.get(noun_field)
            if not classes:
                continue
            members: dict[str, list[str]] = {}
            for value, class_name in classes.items():
                if class_name not in self.cardinality_counts:
                    raise ValueError(
                        f"value_cardinality[{noun_field!r}][{value!r}] names "
                        f"{class_name!r}, which has no cardinality_counts entry"
                    )
                members.setdefault(class_name, []).append(value)
            field_groups = groups.setdefault(noun_field, {})
            for class_name, values in members.items():
                derived = tuple(values)
                existing = field_groups.get(class_name)
                if existing is not None and tuple(existing) != derived:
                    raise ValueError(
                        f"pool_groups[{noun_field!r}][{class_name!r}] disagrees with "
                        "value_cardinality; the cardinality table is the single "
                        "declaration of a count noun's group"
                    )
                field_groups[class_name] = derived
        object.__setattr__(self, "pool_groups", groups)

    def _validate_scene_filter(self) -> None:
        object.__setattr__(
            self, "scene_filter_labels", OrderedDict(self.scene_filter_labels)
        )
        applied = list(self.scene_filter_labels.values())
        if sorted(applied) != sorted(SCENE_FILTERS):
            raise ValueError(
                f"scene_filter_labels must map one label to each of {list(SCENE_FILTERS)}, "
                f"got {applied}"
            )
        if self.scene_filter_default not in self.scene_filter_labels:
            raise ValueError(
                f"scene_filter_default {self.scene_filter_default!r} is not one of the "
                f"labels {list(self.scene_filter_labels)}"
            )

    def _validate_structure(self) -> None:
        """Shape checks only -- never pool *contents*.

        Pools are empty until Todos 4-12 fill them, and a pack that refused to
        construct without them could not be built incrementally. Content
        validation is ``tests/validate_data.py`` (Todo 21).
        """
        if KIND_FIELD not in self.entity_fields:
            raise ValueError(f"a pack must declare a {KIND_FIELD!r} entity field")
        for name in SCENE_FIELD_NAMES:
            if name not in self.scene_fields:
                raise ValueError(f"a pack must declare the {name!r} scene field")
        overlap = set(self.entity_fields) & set(self.scene_fields)
        if overlap:
            raise ValueError(f"fields declared as both entity and scene: {sorted(overlap)}")

        for noun, counter in self.counts.items():
            if noun not in self.entity_fields:
                raise ValueError(f"counts names {noun!r}, which is not an entity field")
            if counter not in self.entity_fields:
                raise ValueError(f"counts names {counter!r}, which is not an entity field")
            if self.entity_fields[noun].count_partner != counter:
                raise ValueError(f"{noun!r} does not name {counter!r} as its count_partner")
            if self.entity_fields[counter].count_partner != noun:
                raise ValueError(f"{counter!r} does not name {noun!r} as its count_partner")

        clause_order = set(self.prose.entity_clause_order)
        heads = {n for n, s in self.entity_fields.items() if s.renders_with is None}
        if clause_order and clause_order != heads:
            missing = sorted(heads - clause_order)
            extra = sorted(clause_order - heads)
            raise ValueError(
                "prose.entity_clause_order must list exactly the clause-heading fields "
                f"(missing {missing}, unexpected {extra}). A field that heads no clause "
                "and is composed into none is drawn every render and never voiced."
            )
        for name, spec in self.entity_fields.items():
            if spec.renders_with is not None and spec.renders_with not in self.entity_fields:
                raise ValueError(f"{name!r} renders_with {spec.renders_with!r}, which is not a field")

        self._validate_declarations()
        self._validate_tiers()
        self._validate_vocabularies()
        self._validate_prose_addresses()

    def _validate_declarations(self) -> None:
        """The two exemption declarations must name things this pack has.

        A typo here is worse than no declaration: ``omitted_pools`` would keep a
        real empty pool undeclared *and* report a stale entry, and
        ``shared_vocabulary`` would silently stop exempting the pair it meant to.
        """
        known_fields = set(self.entity_fields) | set(self.scene_fields)
        known_pool_keys = set(self.kinds) | {POOL_DEFAULT_KEY}
        for groups in self.pool_groups.values():
            known_pool_keys |= set(groups)
        for name, kind in sorted(self.omitted_pools):
            if name not in known_fields:
                raise ValueError(f"omitted_pools names {name!r}, which is not a field")
            if kind not in known_pool_keys:
                raise ValueError(
                    f"omitted_pools names {kind!r}, which is neither a kind nor a pool group"
                )
        for group in self.shared_vocabulary:
            if len(group) < 2:
                raise ValueError(
                    "a shared_vocabulary group needs at least two fields; one field cannot "
                    "share a vocabulary with itself"
                )
            for name in sorted(group):
                if name not in self.entity_fields:
                    raise ValueError(
                        f"shared_vocabulary names {name!r}, which is not an entity field"
                    )

    def _validate_tiers(self) -> None:
        """Structural checks only -- never pool contents.

        A user's ``user_options.json`` may add a value to a tiered field at
        merge time, and construction must not crash on it: an untiered value
        draws at neutral weight. The completeness rule -- every value of a
        tiered field carries a tier -- is a *content* check and lives in
        ``tests/validate_data.py``, where a user's own file can never trip it.
        """
        all_fields = set(self.entity_fields) | set(self.scene_fields)
        for field_name, tiers in self.value_tiers.items():
            if field_name not in all_fields:
                raise ValueError(f"value_tiers names {field_name!r}, which is not a field")
            for value, tier in tiers.items():
                if tier not in self.tier_weights:
                    raise ValueError(
                        f"value_tiers[{field_name!r}][{value!r}] names tier {tier!r}, "
                        "which has no entry in tier_weights"
                    )
        for tier, weight in self.tier_weights.items():
            if weight <= 0:
                raise ValueError(
                    f"tier_weights[{tier!r}] is {weight}; a non-positive weight "
                    "would remove every value of that tier"
                )

    def _validate_vocabularies(self) -> None:
        """Every declared vocabulary names things this pack actually has.

        A typo in a need or a trait is worse than no declaration at all: the
        value it was meant to describe would silently escape the rule the
        vocabulary exists to build, and nothing else would report it.
        """
        all_fields = set(self.entity_fields) | set(self.scene_fields)
        for field_name, table in self.spoken.items():
            if field_name not in all_fields:
                raise ValueError(f"spoken names {field_name!r}, which is not a field")
            options = set(pool_options(self, field_name))
            for token, form in table.items():
                if token not in options:
                    raise ValueError(
                        f"spoken[{field_name!r}] names {token!r}, which is not a value "
                        f"of {field_name!r}"
                    )
                if not form.strip():
                    raise ValueError(
                        f"spoken[{field_name!r}][{token!r}] is an empty spoken form"
                    )

        known_places = set(pool_options(self, ENVIRONMENT_FIELD))
        band_names = set(self.pool_groups.get(ENVIRONMENT_FIELD, {})) | set(self.environment_bands)
        for place in self.place_affordances:
            if place not in known_places and place not in band_names:
                raise ValueError(
                    f"place_affordances names {place!r}, which is neither an environment "
                    "nor a band of this pack"
                )
        provided: set[str] = set()
        for affordances in self.place_affordances.values():
            provided |= set(affordances)
        for field_name, by_value in self.value_needs.items():
            if field_name not in all_fields:
                raise ValueError(f"value_needs names {field_name!r}, which is not a field")
            options = set(pool_options(self, field_name))
            for value, needs in by_value.items():
                if value not in options:
                    raise ValueError(
                        f"value_needs[{field_name!r}] names {value!r}, which is not a "
                        f"value of {field_name!r}"
                    )
                for need in needs:
                    if need not in provided:
                        raise ValueError(
                            f"value_needs[{field_name!r}][{value!r}] needs {need!r}, "
                            "which no place affords; a need no place satisfies would "
                            "exclude the value everywhere"
                        )

        for field_name, by_key in self.default_needs.items():
            if field_name not in all_fields:
                raise ValueError(f"default_needs names {field_name!r}, which is not a field")
            known_keys = set(self.pools.get(field_name, {}))
            if not known_keys:
                raise ValueError(
                    f"default_needs names {field_name!r}, which has no pool keys"
                )
            for key, needs in by_key.items():
                if key not in known_keys:
                    raise ValueError(
                        f"default_needs[{field_name!r}] names {key!r}, which is not a "
                        f"pool key of {field_name!r}"
                    )
                for need in needs:
                    if need not in provided:
                        raise ValueError(
                            f"default_needs[{field_name!r}][{key!r}] needs {need!r}, "
                            "which no place affords; a need no place satisfies would "
                            "exclude every value under that key"
                        )

        for field_name, by_value in self.value_traits.items():
            if field_name not in all_fields:
                raise ValueError(f"value_traits names {field_name!r}, which is not a field")
            options = set(pool_options(self, field_name))
            for value in by_value:
                if value not in options:
                    raise ValueError(
                        f"value_traits[{field_name!r}] names {value!r}, which is not a "
                        f"value of {field_name!r}"
                    )

        supported: set[str] = set()
        for stances in self.place_stances.values():
            supported |= set(stances)
        for field_name, by_value in self.value_stances.items():
            if field_name not in all_fields:
                raise ValueError(f"value_stances names {field_name!r}, which is not a field")
            options = set(pool_options(self, field_name))
            for value, stances in by_value.items():
                if value not in options:
                    raise ValueError(
                        f"value_stances[{field_name!r}] names {value!r}, which is not a "
                        f"value of {field_name!r}"
                    )
                for stance in stances:
                    if stance not in supported:
                        raise ValueError(
                            f"value_stances[{field_name!r}][{value!r}] names {stance!r}, "
                            "which no place supports; the value would be excluded "
                            "everywhere"
                        )
        for affordance in self.place_stances:
            if affordance not in provided:
                raise ValueError(
                    f"place_stances names {affordance!r}, which no place affords"
                )
        for affordance, blocked in self.place_stance_blocks.items():
            if affordance not in provided:
                raise ValueError(
                    f"place_stance_blocks names {affordance!r}, which no place affords"
                )
            for stance in blocked:
                if stance not in supported:
                    raise ValueError(
                        f"place_stance_blocks[{affordance!r}] names {stance!r}, which no "
                        "place supports"
                    )
        for trigger, target in self.trait_conflicts:
            if not trigger or not target:
                raise ValueError("a trait conflict names an empty trait")

        capabilities: set[str] = set()
        for kind, caps in self.kind_capabilities.items():
            if kind not in self.kinds:
                raise ValueError(f"kind_capabilities names {kind!r}, which is not a kind")
            capabilities |= set(caps)
        relations = set(pool_options(self, RELATION_FIELD))
        for relation, (first, second) in self.relation_roles.items():
            if relation not in relations:
                raise ValueError(
                    f"relation_roles names {relation!r}, which is not a relation of this pack"
                )
            for needs in (first, second):
                for need in needs:
                    if need not in capabilities:
                        raise ValueError(
                            f"relation_roles[{relation!r}] needs {need!r}, which no kind has"
                        )

        for field_name in self.foreign_noun_fields:
            if field_name not in all_fields:
                raise ValueError(
                    f"foreign_noun_fields names {field_name!r}, which is not a field"
                )
        for field_name in self.affordance_lint_fields:
            if field_name not in all_fields:
                raise ValueError(
                    f"affordance_lint_fields names {field_name!r}, which is not a field"
                )

        stance_words: set[str] = set()
        for stances in self.place_stances.values():
            stance_words |= set(stances)
        for stance in self.stance_keywords:
            if stance not in stance_words:
                raise ValueError(f"stance_keywords names {stance!r}, which no place supports")
        type_name = type_field(self)
        bodies = set(self.kinds)
        if type_name is not None:
            bodies |= set(pool_options(self, type_name)) | set(self.pool_groups.get(type_name, {}))
        declared: set[str] = set()
        for key, features in self.body_features.items():
            if key not in bodies:
                raise ValueError(
                    f"body_features names {key!r}, which is neither a kind, a type nor a type group"
                )
            declared |= set(features)
        for feature in self.body_keywords:
            if feature not in declared:
                raise ValueError(f"body_keywords names {feature!r}, which no body declares")
        for field_name in self.body_lint_fields:
            if field_name not in all_fields:
                raise ValueError(f"body_lint_fields names {field_name!r}, which is not a field")
        for feature in self.part_keywords:
            if feature not in declared:
                raise ValueError(f"part_keywords names {feature!r}, which no body declares")
        for field_name in self.part_lint_fields:
            if field_name not in self.entity_fields:
                raise ValueError(
                    f"part_lint_fields names {field_name!r}, which is not an entity field"
                )
        affordances: set[str] = set()
        for place_affordances in self.place_affordances.values():
            affordances |= set(place_affordances)
        for affordance, suffix in self.prose.environment_staging:
            if affordance not in affordances:
                raise ValueError(
                    f"environment_staging pairs {affordance!r} with {suffix!r}, which no "
                    "place affords"
                )
            if not suffix.startswith(", ") or "{" in suffix or "}" in suffix:
                raise ValueError(
                    f"environment_staging suffix {suffix!r} must start with ', ' and "
                    "carry no template hole"
                )

    def _validate_archetypes(self) -> None:
        """Every archetype reference resolves, and every archetype speaks.

        An unresolvable name would silently fall through to the ``ProseSpec``,
        which is the exact behaviour the archetype was added to stop -- a nebula
        quietly borrowing a warship's grammar again, with nothing failing.
        """
        heads = {n for n, s in self.entity_fields.items() if s.renders_with is None}
        for name, archetype in self.archetypes.items():
            for omitted in sorted(archetype.omits):
                if omitted not in self.entity_fields:
                    raise ValueError(
                        f"archetype {name!r} omits {omitted!r}, which is not an entity field"
                    )
            if archetype.detail_cap is not None and archetype.detail_cap < 1:
                raise ValueError(
                    f"archetype {name!r} has detail_cap {archetype.detail_cap}; a cap of 0 "
                    "means the archetype is never described, which is what omitting the "
                    "kind means"
                )
            priority = archetype.detail_priority
            if len(set(priority)) != len(priority):
                raise ValueError(
                    f"archetype {name!r} lists a field twice in detail_priority"
                )
            for field_name in priority:
                if field_name == KIND_FIELD:
                    raise ValueError(
                        f"archetype {name!r} prices {KIND_FIELD!r} in detail_priority; "
                        "the kind is the spine and is never budgeted"
                    )
                if field_name not in heads:
                    raise ValueError(
                        f"archetype {name!r} prices {field_name!r} in detail_priority, "
                        "which heads no clause"
                    )
            self._validate_rotation(name, archetype, priority, heads)
            for field_name in archetype.templates:
                if field_name not in self.entity_fields and field_name not in self.scene_fields:
                    raise ValueError(
                        f"archetype {name!r} templates {field_name!r}, which is not a field"
                    )
            self._validate_sentence_set(f"archetype {name!r}", archetype.sentences, heads)
        # A pattern may name a field the archetype omits, and deliberately so.
        # The component pattern lists every component field, and each archetype
        # subtracts what it does not have -- which is what lets one pattern be
        # shared by nine archetypes instead of nine hand-maintained copies that
        # would drift the first time a field is added. An omitted field is
        # simply never in the mapping the renderer walks, so the slot costs
        # nothing.

        self._validate_coverage(heads)
        self._validate_subject_leading(heads)

        for name, substrings in sorted(self.motifs.items()):
            if not substrings:
                raise ValueError(
                    f"motif {name!r} declares no substrings, so its share would "
                    "always be zero and it could never report anything"
                )
            for substring in substrings:
                if not substring:
                    raise ValueError(f"motif {name!r} declares an empty substring")

        if self.environment_bands:
            pool = set(pool_for(self, ENVIRONMENT_FIELD))
            banded: set[str] = set()
            for band, values in sorted(self.environment_bands.items()):
                for value in values:
                    if value not in pool:
                        raise ValueError(
                            f"environment_bands[{band!r}] names {value!r}, which is not an "
                            "environment of this pack"
                        )
                    if value in banded:
                        raise ValueError(
                            f"{value!r} is in two environment bands; a place is in one band "
                            "or the rules written against them contradict each other"
                        )
                    banded.add(value)
            missing = sorted(pool - banded)
            if missing:
                raise ValueError(
                    f"environment_bands does not cover {missing}; an unbanded environment "
                    "silently escapes every rule written against a band"
                )

        for group in self.distinct_within_entity:
            if len(group) < 2:
                raise ValueError(
                    "a distinct_within_entity group needs at least two fields; one field "
                    "cannot collide with itself"
                )
            for name in sorted(group):
                if name not in self.entity_fields:
                    raise ValueError(
                        f"distinct_within_entity names {name!r}, which is not an entity field"
                    )

        known = set(self.archetypes)
        for kind, name in sorted(self.archetype_of_kind.items()):
            if kind not in set(self.kinds):
                raise ValueError(
                    f"archetype_of_kind is keyed on {kind!r}, which is not a kind of this pack"
                )
            if name not in known:
                raise ValueError(f"kind {kind!r} names archetype {name!r}, which is not declared")

        if self.archetype_of_override and not self.archetype_override_field:
            raise ValueError(
                "archetype_of_override is populated but archetype_override_field names no "
                "field, so nothing would ever be looked up in it"
            )
        if self.archetype_override_field:
            if self.archetype_override_field not in self.entity_fields:
                raise ValueError(
                    f"archetype_override_field is {self.archetype_override_field!r}, which is "
                    "not an entity field"
                )
            for value, name in sorted(self.archetype_of_override.items()):
                if name not in known:
                    raise ValueError(
                        f"{value!r} names archetype {name!r}, which is not declared"
                    )

    def _validate_rotation(
        self, name: str, archetype: Archetype, priority: tuple[str, ...], heads: set[str]
    ) -> None:
        """The rotating tail names real, speakable, non-core fields."""
        rotation = archetype.detail_rotation
        slots = archetype.detail_rotation_slots
        if slots < 0:
            raise ValueError(
                f"archetype {name!r} reserves {slots} rotation slot(s); a negative count "
                "reserves nothing"
            )
        if slots and not rotation:
            raise ValueError(
                f"archetype {name!r} reserves {slots} rotation slot(s) but declares no "
                "detail_rotation; the slot would always go unused"
            )
        if archetype.detail_cap is not None and slots >= archetype.detail_cap:
            raise ValueError(
                f"archetype {name!r} reserves {slots} rotation slot(s) of a detail_cap of "
                f"{archetype.detail_cap}; the core order would be empty"
            )
        for field_name, weight in rotation.items():
            if field_name not in self.entity_fields:
                raise ValueError(
                    f"archetype {name!r} rotates {field_name!r}, which is not an entity field"
                )
            if self.entity_fields[field_name].renders_with is not None:
                raise ValueError(
                    f"archetype {name!r} rotates {field_name!r}, which heads no clause"
                )
            if field_name == KIND_FIELD:
                raise ValueError(
                    f"archetype {name!r} rotates {KIND_FIELD!r}; the kind is the spine and "
                    "is never budgeted"
                )
            if field_name in archetype.omits:
                raise ValueError(
                    f"archetype {name!r} rotates {field_name!r} but also omits it; a field "
                    "it never speaks cannot fill a slot"
                )
            if field_name in priority:
                raise ValueError(
                    f"archetype {name!r} lists {field_name!r} in both detail_priority and "
                    "detail_rotation; the core order and the draw would compete for one field"
                )
            if weight <= 0:
                raise ValueError(
                    f"archetype {name!r} gives {field_name!r} rotation weight {weight}; a "
                    "non-positive weight removes it from the draw"
                )

    def _validate_sentence_set(
        self, where: str, patterns: "tuple[Sentence, ...]", heads: set[str]
    ) -> None:
        """Every slot a pattern names is real, and the set introduces its subject."""
        legal = heads | {SITUATION_FIELD} | GRAMMAR_SLOTS
        for index, pattern in enumerate(patterns):
            for segment in pattern._segments:
                inner = segment.segments if isinstance(segment, Optional) else (segment,)
                for piece in inner:
                    if isinstance(piece, Slot):
                        if piece.name not in legal:
                            raise ValueError(
                                f"{where} sentence {index} names {piece.name!r}, which is "
                                "neither a clause-heading entity field, the situation, nor "
                                "one of the grammar slots"
                            )
                    elif isinstance(piece, ListSlot):
                        for member in piece.names:
                            if member not in heads:
                                raise ValueError(
                                    f"{where} sentence {index} lists {member!r}, which is "
                                    "not a clause-heading entity field"
                                )
        if patterns and not any("subject" in pattern_slots(p) for p in patterns):
            raise ValueError(
                f"{where} declares patterns but none names the subject, so the entity "
                "would never be introduced"
            )

    def _validate_coverage(self, heads: set[str]) -> None:
        """Every field an archetype draws must be voiced by a pattern of its plan.

        The plan is the archetype's own patterns, else the pack's. A field that
        is drawn every render and never spoken is the dead-widget bug this whole
        check exists to make impossible.
        """
        for name, archetype in self.archetypes.items():
            plan = archetype.sentences or self.prose.entity_sentences
            if not plan:
                continue
            head = archetype.head_phrase
            if head is None:
                head = self.prose.head_phrase.get(POOL_DEFAULT_KEY)
            # ``kind`` is the spine, not a description: it scopes every pool and is
            # the one field a document may hold unspoken (see the coherence suite).
            required = (
                heads
                - {KIND_FIELD}
                - set(archetype.omits)
                - set(_always_consumed(head))
            ) | {SITUATION_FIELD}
            for clause_head in sorted(required):
                if not any(pattern_covers(pattern, clause_head) for pattern in plan):
                    raise ValueError(
                        f"archetype {name!r} draws {clause_head!r} but no pattern speaks it "
                        "unconditionally, so it would be drawn every render and never "
                        "voiced; give it a pattern of its own or fold it into the head "
                        "phrase"
                    )

    def _validate_subject_leading(self, heads: set[str]) -> None:
        """A kind declared subject-leading must actually lead with its subject.

        The declaration is the claim; the head phrase and the first pattern are
        what the renderer obeys. Checking them against each other is what stops
        the claim quietly becoming false -- the exact failure mode behind four
        Identity Forge render bugs, where a non-human body ended up a trailing
        modifier and the model drew a human holding it.
        """
        for kind in sorted(self.prose.subject_leading_kinds):
            name = self.archetype_of_kind.get(kind)
            archetype = self.archetypes.get(name) if name else None
            head = archetype.head_phrase if archetype is not None else None
            if head is None:
                head = self.prose.head_phrase.get(kind) or self.prose.head_phrase.get(
                    POOL_DEFAULT_KEY
                )
            if head is None:
                continue
            if head.subject is None:
                raise ValueError(
                    f"kind {kind!r} is declared subject-leading but its head phrase "
                    "names no subject, so nothing would be promoted to the front of "
                    "its sentence"
                )
            plan = archetype.sentences if archetype is not None else ()
            if not plan:
                plan = self.prose.entity_sentences
            if not plan:
                continue
            first = plan[0]._segments[0]
            if not (isinstance(first, Slot) and first.name == "subject"):
                raise ValueError(
                    f"kind {kind!r} is declared subject-leading, but its first pattern "
                    f"{plan[0].text!r} does not open with the subject. The body plan has "
                    "to be the subject of its own sentence or the model draws a person "
                    "holding it"
                )

    def _validate_scopes(self) -> None:
        """The scope chain must resolve in one forward pass, and every declared
        group, band and fall-through entry must name something this pack has.

        A scope that names an unknown field, or an entity control that has not
        resolved yet, would surface as a silent wrong draw at render time --
        the same reason the other ``_validate_*`` methods fail construction
        rather than generation.
        """
        entity_fields = self.entity_fields
        scene_fields = self.scene_fields
        entity_names = set(entity_fields)
        scene_names = set(scene_fields)
        all_fields = entity_names | scene_names
        entity_order = tuple(entity_fields)

        declared_controls = (
            {c for spec in entity_fields.values() for c in spec.scope}
            | {c for spec in scene_fields.values() for c in spec.scope}
        )

        for name, spec in entity_fields.items():
            for control in spec.scope:
                if control not in all_fields:
                    raise ValueError(
                        f"field {name!r} scopes on {control!r}, which is neither an "
                        "entity field nor a scene field"
                    )
                if control == name:
                    raise ValueError(
                        f"field {name!r} scopes on itself; a field cannot scope itself"
                    )
                if control in entity_names and entity_order.index(control) >= entity_order.index(name):
                    raise ValueError(
                        f"field {name!r} scopes on {control!r}, which resolves after it in "
                        "entity_fields order; a scope chain must be resolvable in one forward pass"
                    )
        for name, spec in scene_fields.items():
            for control in spec.scope:
                if control not in all_fields:
                    raise ValueError(
                        f"field {name!r} scopes on {control!r}, which is neither an "
                        "entity field nor a scene field"
                    )
                if control == name:
                    raise ValueError(
                        f"field {name!r} scopes on itself; a field cannot scope itself"
                    )

        for control in self.pool_groups:
            if control not in declared_controls:
                raise ValueError(
                    f"pool_groups names control field {control!r}, which this pack does "
                    "not declare; every pool_groups key must appear in some field's scope"
                )

        for control, groups in self.pool_groups.items():
            legal = set(pool_options(self, control))
            value_group: dict[str, str] = {}
            for group_name, members in groups.items():
                if group_name == POOL_DEFAULT_KEY:
                    raise ValueError(
                        f"pool_groups[{control!r}] names a group {POOL_DEFAULT_KEY!r}, which "
                        "collides with the default pool key"
                    )
                if group_name in legal:
                    raise ValueError(
                        f"pool_groups[{control!r}] names group {group_name!r}, which collides "
                        "with a raw value of that control field"
                    )
                for value in members:
                    if value not in legal:
                        raise ValueError(
                            f"pool_groups[{control!r}][{group_name!r}] lists {value!r}, which "
                            f"is not a value of {control!r}"
                        )
                    if value in value_group:
                        raise ValueError(
                            f"{value!r} is in two pool_groups of {control!r} "
                            f"({value_group[value]!r} and {group_name!r}); a value is in one group"
                        )
                    value_group[value] = group_name

        env_groups = self.pool_groups.get(ENVIRONMENT_FIELD)
        if self.environment_bands and env_groups:
            if dict(self.environment_bands) != dict(env_groups):
                raise ValueError(
                    "environment_bands and pool_groups['environment'] disagree; they must "
                    "name the same bands with the same values"
                )

        if self.scope_fallthrough:
            control_values: set[str] = set()
            for control in declared_controls:
                control_values.update(pool_options(self, control))
            group_names = {g for groups in self.pool_groups.values() for g in groups}
            valid_keys = control_values | group_names | {POOL_DEFAULT_KEY}
            for field, key in self.scope_fallthrough:
                if field not in all_fields:
                    raise ValueError(f"scope_fallthrough names {field!r}, which is not a field")
                if key not in valid_keys:
                    raise ValueError(
                        f"scope_fallthrough names {key!r} for {field!r}, which is not a value "
                        "or group of this pack"
                    )

    def _validate_prose_addresses(self) -> None:
        """Every field a ``ProseSpec`` names must exist, and be one that speaks.

        A head phrase or an adjective anchor pointing at a field that heads no
        clause is silently unreachable -- the renderer would never fold it in and
        the widget would be drawn every render and never voiced, which is the
        dead-widget bug ``identity-forge-dead-widget-check`` names.
        """
        heads = {n for n, s in self.entity_fields.items() if s.renders_with is None}
        known_kinds = set(self.kinds) | {POOL_DEFAULT_KEY}

        for kind, head in self.prose.head_phrase.items():
            if kind not in known_kinds:
                raise ValueError(
                    f"prose.head_phrase is keyed on {kind!r}, which is not a kind of this "
                    f"pack (nor {POOL_DEFAULT_KEY!r})"
                )
            named = (*head.noun, *head.modifiers)
            if head.subject is not None:
                named = (*named, head.subject)
            for name in named:
                if name not in heads:
                    raise ValueError(
                        f"prose.head_phrase[{kind!r}] names {name!r}, which is not a "
                        "clause-heading entity field"
                    )

        priority = self.prose.detail_priority
        if priority:
            if len(set(priority)) != len(priority):
                raise ValueError("prose.detail_priority lists a field twice")
            expected = heads - {KIND_FIELD}
            if set(priority) != expected:
                missing = sorted(expected - set(priority))
                extra = sorted(set(priority) - expected)
                raise ValueError(
                    "prose.detail_priority must price every clause head except "
                    f"{KIND_FIELD!r} (missing {missing}, unexpected {extra}). An unpriced "
                    "field would be cut in an order nobody chose"
                )

        for name, anchors in self.prose.adjective_of.items():
            if name not in heads:
                raise ValueError(
                    f"prose.adjective_of names {name!r}, which is not a clause-heading "
                    "entity field"
                )
            for anchor in anchors:
                if anchor not in heads:
                    raise ValueError(
                        f"prose.adjective_of[{name!r}] anchors on {anchor!r}, which is not "
                        "a clause-heading entity field"
                    )
                if anchor == name:
                    raise ValueError(f"prose.adjective_of[{name!r}] anchors on itself")

        self._validate_sentence_set(
            "prose.entity_sentences", self.prose.entity_sentences, heads
        )

    def _derive_rules(self) -> tuple[ConstraintRule, ...]:
        """The declared rules plus every rule derived from the vocabularies."""
        return (
            tuple(self.constraints)
            + _expand_traits(self)
            + _expand_affordances(self)
            # Feasibility before stances: a kind excluded from a place must be
            # re-drawn before the rules that scope its subkind and form, or those
            # fields are nulled by the stance rule and never revived.
            + _expand_feasibility(self)
            + _expand_stances(self)
            + _expand_relation_roles(self)
        )

    def _derive_weights(self) -> Mapping[str, Mapping[str, float]]:
        """The effective draw weights of every tiered field, computed once.

        ``FieldSpec.weights`` states a value's own weight; ``tier_weights``
        states what its *tier* is worth. The two multiply, so a pack can price
        a value twice -- rare *and* expensive -- without either declaration
        knowing about the other. A field with no tiers keeps its plain weights
        and is absent from this map; ``weights_for`` falls through to them.
        """
        if not self.value_tiers:
            return _EMPTY_MAP
        derived: dict[str, Mapping[str, float]] = {}
        for field_name, tiers in self.value_tiers.items():
            spec = self.entity_fields.get(field_name) or self.scene_fields.get(field_name)
            base = spec.weights if spec is not None and spec.weights else {}
            derived[field_name] = MappingProxyType(
                {
                    value: base.get(value, 1.0)
                    * self.tier_weights.get(tiers.get(value, ""), 1.0)
                    for value in pool_options(self, field_name)
                }
            )
        return MappingProxyType(derived)

    @property
    def all_constraints(self) -> tuple[ConstraintRule, ...]:
        """The declared rules plus every rule derived from the vocabularies above.

        Computed once at construction: a pack is shared process-wide and frozen,
        so the expansion cannot change under a render.
        """
        return self._derived_rules

    def weights_for(self, field: str) -> Mapping[str, float] | None:
        """Effective per-value draw weights for ``field``, or ``None``.

        The engine reads this instead of ``FieldSpec.weights`` so a genre can
        price a value by its tier without the engine learning what a tier is.
        A tiered field's map is the product of its own weights and its tier
        weights; an untiered field keeps its plain weights, so a pack that
        declares no tiers behaves exactly as before.
        """
        derived = self._effective_weights.get(field)
        if derived is not None:
            return derived
        spec = self.entity_fields.get(field) or self.scene_fields.get(field)
        return spec.weights if spec is not None else None


# ---------------------------------------------------------------------------
# What the builder produces
# ---------------------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class FieldDef:
    """One widget on one node, resolved against a pack.

    Every attribute below is required -- there are no defaults -- because a
    FieldDef is machine-built and a silently-defaulted key would be a hole the
    engine only discovers at render time. ``FieldSpec`` is where the convenient
    defaults live; this is the fully-determined result.
    """

    #: Widget key: a legal identifier, because it arrives as an ``execute``
    #: keyword argument. ``entity2_kind``.
    key: str
    #: Constraint / resolution address. ``entity2.kind``.
    path: str
    #: The pack field this came from. ``kind``.
    base: str
    #: 1-based entity slot, or ``None`` for a scene-wide field.
    slot: int | None
    #: The two slots a relation joins, or ``None``.
    endpoints: tuple[int, int] | None
    group: str
    label: str
    tooltip: str
    #: Bare pool values, article-less. For a kind-scoped field this is the union
    #: across kinds, because ComfyUI fixes a combo's options at registration and
    #: a locked value must stay selectable when the kind changes; the frontend
    #: narrows what is *shown*. Empty until Todos 4-12.
    options: tuple[str, ...]
    optional: bool
    control: bool
    kind_scoped: bool
    scope: tuple[str, ...]
    tag_scoped: bool
    count_partner: str | None
    weights: Mapping[str, float] | None
    #: Relative weight of drawing no value, or 0.0 for "never omit".
    omission_weight: float
    widget: str
    default: Any

    def __post_init__(self) -> None:
        object.__setattr__(self, "options", tuple(self.options))


#: The keys the plan names as the FieldDef contract. Asserted to be a subset of
#: the dataclass's own required keys, so the two can never drift apart.
REQUIRED_FIELD_DEF_KEYS: frozenset[str] = frozenset(
    {"group", "options", "optional", "control", "weights", "count_partner", "tag_scoped"}
)


def field_def_required_keys() -> frozenset[str]:
    """Every ``FieldDef`` attribute that has no default (i.e. all of them)."""
    return frozenset(
        f.name
        for f in dataclass_fields(FieldDef)
        if f.default is MISSING and f.default_factory is MISSING
    )


# ---------------------------------------------------------------------------
# Key and address helpers
# ---------------------------------------------------------------------------


def slot_key(slot: int, name: str) -> str:
    """Widget key for a slot's field: ``entity2_kind``."""
    return f"entity{slot}_{name}"


def slot_path(slot: int, name: str) -> str:
    """Constraint address for a slot's field: ``entity2.kind``."""
    return f"entity{slot}.{name}"


def relation_key(first: int, second: int) -> str:
    """Widget key *and* constraint address for a relation: ``relation_1_2``."""
    return f"relation_{first}_{second}"


def relation_position_key(first: int, second: int) -> str:
    """Widget key *and* constraint address for a relation's position."""
    return f"relation_{first}_{second}_position"


def relation_pairs(slots: int) -> tuple[tuple[int, int], ...]:
    """Every unordered slot pair, in a stable order. Four slots give six."""
    return tuple(combinations(range(1, slots + 1), 2))


def constraint_address_space(pack: GenrePack, slots: int = SCENE_NODE_SLOTS) -> frozenset[str]:
    """Every address a constraint rule may legally name.

    Deliberately **wider than any one node's widget list**. Slots 2..N carry only
    the brief fields as widgets, but wiring a Scene Entity into one promotes it
    to the whole morphology at run time, so a rule keyed on ``entity*.material``
    must still reach slot 3. The address space is therefore the pack's schema
    crossed with the slot count -- what a scene *can* hold -- while
    ``build_field_definitions`` stays the authority on what is drawn on the node
    face. Validating rules against the narrower set would reject a rule that is
    correct precisely in the case the entity node exists for.

    ``entity5.kind`` is outside the space, because ``slots`` is what a scene has.
    """
    space = {ENVIRONMENT_FIELD}
    space.add(CONTEXT_FIELD)
    for slot in range(1, slots + 1):
        space.add(slot_path(slot, SITUATION_FIELD))
        for name in pack.entity_fields:
            space.add(slot_path(slot, name))
    for first, second in relation_pairs(slots):
        space.add(relation_key(first, second))
        space.add(relation_position_key(first, second))
    return frozenset(space)


def is_slot_wildcard(address: str) -> bool:
    """Whether ``address`` is the any-slot form ``entity*.kind``."""
    return address.startswith("entity*.")


def bind_address(
    address: str, slot: int | None = None, pair: tuple[int, int] | None = None
) -> str:
    """Resolve a constraint address against a concrete slot and relation pair.

    **The wildcard rule, stated once** because the engine, the validator and
    every genre author have to agree on it: a constraint whose ``field`` is
    wildcarded is evaluated **once per slot**, and a wildcard on the *other*
    side of that same rule binds to the *same* slot. "A celestial body carries
    no armament" is about that body's own armament, never about slot 3's.

    ``relation_*`` / ``relation_*_position`` bind to the pair; ``first.name``
    and ``second.name`` name the pair's endpoints (todo 8).

    A non-wildcarded address is scene-global and comes back unchanged, which is
    what lets one rule pair a per-slot trigger with a scene-wide consequence
    ("a celestial body is not indoors" excludes ``environment`` values).
    """
    if address == RELATION_ANY:
        if pair is None:
            raise ValueError(f"{address!r} needs a relation pair to bind to")
        return relation_key(*pair)
    if address == RELATION_ANY_POSITION:
        if pair is None:
            raise ValueError(f"{address!r} needs a relation pair to bind to")
        return relation_position_key(*pair)
    if address.startswith((FIRST_ENDPOINT + ".", SECOND_ENDPOINT + ".")):
        if pair is None:
            raise ValueError(f"{address!r} needs a relation pair to bind to")
        endpoint = pair[0] if address.startswith(FIRST_ENDPOINT + ".") else pair[1]
        _, _, name = address.partition(".")
        return slot_path(endpoint, name)
    if not is_slot_wildcard(address):
        return address
    if slot is None:
        raise ValueError(f"{address!r} is slot-wildcarded and needs a slot to bind to")
    _, _, name = address.partition(".")
    return slot_path(slot, name)


def address_field(address: str) -> str:
    """The pack field an address names, resolving wildcards and endpoints.

    ``entity2.scale`` -> ``scale``; ``relation_*`` -> ``relation``; ``first.kind``
    -> ``kind``. Used by the validator and the tests to look an address up in
    ``pack.pools``."""
    if address == RELATION_ANY:
        return RELATION_FIELD
    if address == RELATION_ANY_POSITION:
        return RELATION_POSITION_FIELD
    if address.startswith((FIRST_ENDPOINT + ".", SECOND_ENDPOINT + ".")):
        return address.partition(".")[2]
    if "." in address:
        return address.partition(".")[2]
    if address.startswith("relation_"):
        return RELATION_POSITION_FIELD if address.endswith("_position") else RELATION_FIELD
    return address

def address_matches(address: str, path: str) -> bool:
    """Whether a rule ``address`` (possibly slot-wildcarded) selects ``path``."""
    if address == path:
        return True
    if not address.startswith("entity*."):
        return False
    _, _, name = address.partition(".")
    entity, dot, target = path.partition(".")
    return bool(dot) and entity.startswith("entity") and target == name


# ---------------------------------------------------------------------------
# Pool and label access
# ---------------------------------------------------------------------------


def group_of(pack: GenrePack, control_field: str, value: str) -> str | None:
    """The declared group ``value`` belongs to for ``control_field``, or None."""
    for group_name, members in pack.pool_groups.get(control_field, {}).items():
        if value in members:
            return group_name
    return None


def scope_keys(
    pack: GenrePack, spec: FieldSpec, values: Mapping[str, str | None]
) -> tuple[str, ...]:
    """Every pool key this field's scope resolves to, in precedence order,
    ending with POOL_DEFAULT_KEY. Exposed so the validator, the engine and the
    frontend payload all answer the question the same way."""
    keys: list[str] = []
    seen: set[str] = set()
    for control in spec.scope:
        value = values.get(control)
        if value is None:
            continue
        if value not in seen:
            seen.add(value)
            keys.append(value)
        group = group_of(pack, control, value)
        if group is not None and group not in seen:
            seen.add(group)
            keys.append(group)
    if POOL_DEFAULT_KEY not in seen:
        keys.append(POOL_DEFAULT_KEY)
    return tuple(keys)


def pool_for(
    pack: GenrePack, name: str, scope: Mapping[str, str | None] | str | None = None
) -> tuple[str, ...]:
    """Values available for ``name`` under ``scope``.

    ``scope`` is a mapping of control field -> current value. A bare string is
    accepted and read as the value of ``KIND_FIELD``, which is what every
    pre-scope-chain caller passes. Resolution walks the field's declared scope
    chain -- raw value first, then the value's group, then the fall-through --
    and never raises: a missing pool is a data defect that
    ``tests/validate_data.py`` reports by name, not a crash the user meets.
    """
    if isinstance(scope, str):
        scope = {KIND_FIELD: scope}
    elif scope is None:
        scope = {}
    by_kind = pack.pools.get(name)
    if not by_kind:
        return ()
    spec = pack.entity_fields.get(name) or pack.scene_fields.get(name)
    if spec is None:
        return ()
    for key in scope_keys(pack, spec, scope):
        if key in by_kind:
            return tuple(by_kind[key])
    return ()


def pool_keys_for_value(pack: GenrePack, field: str, value: str) -> tuple[str, ...]:
    """Every pool key of ``field`` whose values contain ``value``, in pool order."""
    return tuple(
        key for key, values in (pack.pools.get(field) or {}).items() if value in values
    )


def resolved_needs(pack: GenrePack, field: str, value: str) -> frozenset[str]:
    """The needs of one value: its own entry, else the union of its keys' defaults.

    An explicit entry in ``value_needs`` replaces the defaults entirely -- an
    empty frozenset there means "deliberately needs nothing", which is why the
    test is ``in`` and not a truthiness check. A value authored under several
    pool keys takes the union of their defaults, because which key a draw
    resolves to depends on the slot's scope while the value is the same value.
    """
    by_value = pack.value_needs.get(field, {})
    if value in by_value:
        return frozenset(by_value[value])
    defaults = pack.default_needs.get(field, {})
    needs: set[str] = set()
    for key in pool_keys_for_value(pack, field, value):
        needs |= set(defaults.get(key, ()))
    return frozenset(needs)


def is_classified(pack: GenrePack, field: str, value: str) -> bool:
    """Whether a value's place-need is declared: by its own entry, or by a key it
    is authored under carrying a default. A default entry that is empty is a
    declaration too -- "this value needs nothing of the place" -- so this is the
    one question the coverage gate asks."""
    if value in pack.value_needs.get(field, {}):
        return True
    defaults = pack.default_needs.get(field, {})
    return any(key in defaults for key in pool_keys_for_value(pack, field, value))


def archetype_name_for(
    pack: GenrePack, values: Mapping[str, str | None]
) -> str | None:
    """The *name* of the archetype governing one entity, or ``None``.

    ``archetype_for`` returns the object because the engine only needs its
    grammar; this returns the name so ``prompt_json`` can report which category
    the pack put the entity in -- the one piece of information that explains
    every length decision the pack makes.

    Resolution order, most specific first: the override field (a black hole
    leaving ``world`` for ``phenomenon``), then the kind, then the pack's
    ``_default`` archetype if it declares one. ``None`` means the entity is
    spoken by the ``ProseSpec`` alone, which is what a pack that declares no
    archetypes gets.

    Takes the whole field mapping rather than a kind and a subkind, so the
    engine can ask this question without knowing which fields a genre uses to
    answer it.
    """
    if not pack.archetypes:
        return None
    if pack.archetype_override_field:
        override = values.get(pack.archetype_override_field)
        if override is not None:
            name = pack.archetype_of_override.get(override)
            if name is not None:
                return name
    kind = values.get(KIND_FIELD)
    if kind is not None:
        name = pack.archetype_of_kind.get(kind)
        if name is not None:
            return name
    if POOL_DEFAULT_KEY in pack.archetypes:
        return POOL_DEFAULT_KEY
    return None


def archetype_for(
    pack: GenrePack, values: Mapping[str, str | None]
) -> "Archetype | None":
    """The archetype governing one entity's grammar, or ``None``.

    A thin wrapper over ``archetype_name_for``: one resolution order, so the
    object the engine renders with and the name ``prompt_json`` reports can
    never disagree.
    """
    name = archetype_name_for(pack, values)
    return pack.archetypes[name] if name is not None else None


def pool_options(pack: GenrePack, name: str) -> tuple[str, ...]:
    """Union of every value ``name`` can take, in first-seen order.

    This is what goes on the widget: ComfyUI fixes a combo's options at
    registration, so a value that is legal under *some* kind must stay
    selectable, or locking it and then switching kind would silently drop it.
    """
    seen: dict[str, None] = {}
    by_kind = pack.pools.get(name) or {}
    for key in (POOL_DEFAULT_KEY, *by_kind):
        for value in by_kind.get(key, ()):
            seen.setdefault(value, None)
    return tuple(seen)


def spoken_value(pack: GenrePack, field: str, value: str) -> str:
    """How ``value`` of ``field`` is said in a sentence. Falls back to the token."""
    return pack.spoken.get(field, {}).get(value, value)


def affordances_of(pack: GenrePack, environment: str) -> frozenset[str]:
    """What ``environment`` affords: its own entry, else its band's, else nothing."""
    if environment in pack.place_affordances:
        return frozenset(pack.place_affordances[environment])
    band = group_of(pack, ENVIRONMENT_FIELD, environment)
    if band is None:
        for name, members in pack.environment_bands.items():
            if environment in members:
                band = name
                break
    if band is not None and band in pack.place_affordances:
        return frozenset(pack.place_affordances[band])
    return frozenset()


def type_field(pack: GenrePack) -> str | None:
    """The control between ``kind`` and the stance field -- sci-fi's ``subkind`` -- or None.

    Read from the stance field's own scope rather than named, so a genre that calls the
    level something else, or has no such level, needs nothing from the contract.
    """
    spec = pack.entity_fields.get(STANCE_FIELD)
    if spec is None:
        return None
    for control in spec.scope:
        if control != KIND_FIELD and control in pack.entity_fields:
            return control
    return None


def _stance_scope(pack: GenrePack, kind: str, value: str | None) -> dict[str, str]:
    scope = {KIND_FIELD: kind}
    name = type_field(pack)
    if name is not None and value is not None:
        scope[name] = value
    return scope


def form_can_stand(pack: GenrePack, environment: str, form: str) -> bool:
    """Whether ``form`` can be in ``environment``; a form with no stances is unconstrained."""
    stances = pack.value_stances.get(STANCE_FIELD, {}).get(form)
    return not stances or stances_fit(
        stances, supported_stances(pack, environment), blocked_stances(pack, environment)
    )


def type_can_stand(pack: GenrePack, environment: str, kind: str, value: str | None) -> bool:
    """Whether at least one form this kind and type can take stands up in ``environment``."""
    forms = pool_for(pack, STANCE_FIELD, _stance_scope(pack, kind, value))
    return not forms or any(form_can_stand(pack, environment, form) for form in forms)


def type_feasible(pack: GenrePack, environment: str, kind: str, value: str) -> bool:
    """A type exists in a place that affords its needs and holds one of its forms up."""
    name = type_field(pack)
    if name is not None and not resolved_needs(pack, name, value) <= affordances_of(pack, environment):
        return False
    return type_can_stand(pack, environment, kind, value)


def feasible_types(pack: GenrePack, environment: str, kind: str) -> tuple[str, ...]:
    """The types of ``kind`` that can exist in ``environment``, in pool order."""
    name = type_field(pack)
    if name is None:
        return ()
    return tuple(
        value
        for value in pool_for(pack, name, {KIND_FIELD: kind})
        if type_feasible(pack, environment, kind, value)
    )


def kind_feasible(pack: GenrePack, environment: str, kind: str) -> bool:
    """A kind exists where one of its types does -- or, with no type level, where one of its forms stands."""
    name = type_field(pack)
    if name is None or not pool_for(pack, name, {KIND_FIELD: kind}):
        return type_can_stand(pack, environment, kind, None)
    return bool(feasible_types(pack, environment, kind))


def _body_key(pack: GenrePack, kind: str, value: str | None) -> str | None:
    """The most specific ``body_features`` key for a subject: type, type group, kind."""
    if value is not None and value in pack.body_features:
        return value
    name = type_field(pack)
    if value is not None and name is not None:
        group = group_of(pack, name, value)
        if group is not None and group in pack.body_features:
            return group
    return kind if kind in pack.body_features else None


def body_features_of(pack: GenrePack, kind: str, value: str | None) -> frozenset[str]:
    """What a body has; empty when the pack declares nothing for it."""
    key = _body_key(pack, kind, value)
    return frozenset(pack.body_features[key]) if key is not None else frozenset()


def has_body_declaration(pack: GenrePack, kind: str, value: str | None) -> bool:
    """Whether the pack declares a body for this subject at any level, even an empty one."""
    return _body_key(pack, kind, value) is not None


def _trait_fields(pack: GenrePack, trait: str) -> tuple[str, ...]:
    """The fields that carry ``trait`` on at least one value."""
    return tuple(
        field
        for field, values in pack.value_traits.items()
        if any(trait in traits for traits in values.values())
    )


def _values_with_trait(pack: GenrePack, field: str, trait: str) -> tuple[str, ...]:
    """The values of ``field`` that carry ``trait``, in pool order."""
    return tuple(
        value for value, traits in pack.value_traits[field].items() if trait in traits
    )

def _trait_address(pack: GenrePack, field_name: str) -> str:
    """Where a trait's field sits in a rule: bare for a scene-global field, per slot otherwise.

    ``context`` is drawn once per scene, so ``entity*.context`` is no address at all; the
    situation and the relations are scene fields that still belong to a slot or a pair.
    """
    if field_name in pack.scene_fields and field_name not in (
        SITUATION_FIELD, RELATION_FIELD, RELATION_POSITION_FIELD,
    ):
        return field_name
    return f"entity*.{field_name}"

def _expand_traits(pack: GenrePack) -> tuple[ConstraintRule, ...]:
    """Expand ``trait_conflicts`` into ordinary multi-value exclusion rules.

    The trigger stands and the target gives way. The field a trait lives on is
    inferred from the table rather than declared twice, so a trait added to a
    second field is covered the moment it is authored. A field addressed here
    is ``entity*.``-prefixed, which the engine binds per slot -- so a scene
    field like ``situation`` is handled the same way as an entity field.
    """
    rules: list[ConstraintRule] = []
    for trigger_trait, target_trait in pack.trait_conflicts:
        for trigger_field in _trait_fields(pack, trigger_trait):
            triggers = _values_with_trait(pack, trigger_field, trigger_trait)
            if not triggers:
                continue
            for target_field in _trait_fields(pack, target_trait):
                if target_field == trigger_field:
                    continue
                targets = _values_with_trait(pack, target_field, target_trait)
                if not targets:
                    continue
                rules.append(
                    ConstraintRule(
                        type=RULE_EXCLUDE,
                        field=_trait_address(pack, trigger_field),
                        values=triggers,
                        excludes_field=_trait_address(pack, target_field),
                        excludes_values=targets,
                        reason=pack.trait_reasons.get(
                            f"{trigger_trait}|{target_trait}",
                            f"a thing cannot be both {trigger_trait} and {target_trait}",
                        ),
                    )
                )
    return tuple(rules)


def _expand_affordances(pack: GenrePack) -> tuple[ConstraintRule, ...]:
    """Exclude each value from every place that lacks one of its needs.

    A value's needs are its own entry in ``value_needs``, else the union of the
    ``default_needs`` of every pool key it is authored under. Values are grouped
    by identical need-set so a field with many values that need the same thing
    produces one rule, not one rule per value. A group whose need-set is empty
    (the value is at home anywhere) produces nothing.
    """
    rules: list[ConstraintRule] = []
    environments = pool_options(pack, ENVIRONMENT_FIELD)
    fields = list(pack.value_needs)
    fields += [name for name in pack.default_needs if name not in pack.value_needs]
    for field_name in fields:
        groups: dict[frozenset[str], list[str]] = {}
        for value in pool_options(pack, field_name):
            needs = resolved_needs(pack, field_name, value)
            if needs:
                groups.setdefault(needs, []).append(value)
        if not groups:
            continue
        if field_name == RELATION_FIELD:
            target_field = RELATION_ANY
        elif field_name in pack.scene_fields and field_name not in SCENE_FIELD_NAMES:
            # A scene-global field (``context``) is addressed bare, not per slot.
            # ``situation`` is a scene field too but is addressed per slot.
            target_field = field_name
        else:
            target_field = f"entity*.{field_name}"
        for needs, values in groups.items():
            lacking = tuple(
                environment
                for environment in environments
                if not needs <= affordances_of(pack, environment)
            )
            if not lacking:
                continue
            rules.append(
                ConstraintRule(
                    type=RULE_EXCLUDE,
                    field=ENVIRONMENT_FIELD,
                    values=lacking,
                    excludes_field=target_field,
                    excludes_values=tuple(values),
                    reason=f"needs {', '.join(sorted(needs))}, which this place lacks",
                )
            )
    return tuple(rules)


def supported_stances(pack: GenrePack, environment: str) -> frozenset[str]:
    """Every stance the affordances of ``environment`` support, less any it blocks."""
    affordances = affordances_of(pack, environment)
    supported: set[str] = set()
    for affordance in affordances:
        supported |= set(pack.place_stances.get(affordance, ()))
    for affordance in affordances:
        supported -= set(pack.place_stance_blocks.get(affordance, ()))
    return frozenset(supported)


#: The earlier private name, kept so existing callers do not churn.
_supported_stances = supported_stances


def blocked_stances(pack: GenrePack, environment: str) -> frozenset[str]:
    """Every stance a body may not have at all in ``environment`` (``place_stance_blocks``)."""
    blocked: set[str] = set()
    for affordance in affordances_of(pack, environment):
        blocked |= set(pack.place_stance_blocks.get(affordance, ()))
    return frozenset(blocked)


def stances_fit(
    stances: "frozenset[str] | set[str]", support: frozenset[str], blocked: frozenset[str]
) -> bool:
    """Whether a body with ``stances`` can be in a place: one supported, none blocked."""
    return bool(stances & support) and not (stances & blocked)


def _expand_stances(pack: GenrePack) -> tuple[ConstraintRule, ...]:
    """Exclude a shape from every place that cannot hold it, and an action the
    subject's shape cannot take.

    A place says what it *affords*; a form says what it can *do*. Neither alone
    can see the failure: a ring standing on its ring was a legal place and a
    legal shape, and the defect was the pairing. Two rule families, both
    ordinary exclusions:

    * a form is excluded from every environment whose affordances support none
      of its stances -- the environment is the trigger, so the shape gives way
      and the place (which scopes the kind and the context) is never re-drawn;
    * a situation is excluded from a form whose stances it cannot share, on the
      same slot -- the silhouette stands and the action gives way.
    """
    form_stances = pack.value_stances.get(STANCE_FIELD, {})
    if not pack.place_stances or not form_stances:
        return ()
    rules: list[ConstraintRule] = []
    environments = pool_options(pack, ENVIRONMENT_FIELD)
    support = {
        environment: _supported_stances(pack, environment)
        for environment in environments
    }
    blocks = {environment: blocked_stances(pack, environment) for environment in environments}
    blocked: dict[frozenset[str], list[str]] = {}
    for environment in environments:
        disallowed = tuple(
            value
            for value, stances in form_stances.items()
            if stances and not stances_fit(stances, support[environment], blocks[environment])
        )
        if disallowed:
            blocked.setdefault(frozenset(disallowed), []).append(environment)
    for disallowed, places in blocked.items():
        rules.append(
            ConstraintRule(
                type=RULE_EXCLUDE,
                field=ENVIRONMENT_FIELD,
                values=tuple(places),
                excludes_field=f"entity*.{STANCE_FIELD}",
                excludes_values=tuple(sorted(disallowed)),
                reason="this shape cannot hold itself up here",
            )
        )
    situation_stances = pack.value_stances.get(SITUATION_FIELD, {})
    if not situation_stances:
        return tuple(rules)
    form_groups: dict[frozenset[str], list[str]] = {}
    for value, stances in form_stances.items():
        if stances:
            form_groups.setdefault(frozenset(stances), []).append(value)
    situation_groups: dict[frozenset[str], list[str]] = {}
    for value, stances in situation_stances.items():
        if stances:
            situation_groups.setdefault(frozenset(stances), []).append(value)
    for form_set, forms in form_groups.items():
        for situation_set, situations in situation_groups.items():
            if form_set & situation_set:
                continue
            rules.append(
                ConstraintRule(
                    type=RULE_EXCLUDE,
                    field=f"entity*.{STANCE_FIELD}",
                    values=tuple(forms),
                    excludes_field=f"entity*.{SITUATION_FIELD}",
                    excludes_values=tuple(situations),
                    reason="this shape cannot take that action",
                )
            )
    return tuple(rules)


def _expand_feasibility(pack: GenrePack) -> tuple[ConstraintRule, ...]:
    """Exclude a type from every place none of its forms can stand in, and a kind from
    every place none of its types can exist in.

    The stance rule removes a *form*. When it removes every form a type can take, the
    pool empties, the form resolves to None and the subject is described with no
    silhouette in a place it cannot occupy. These rules move the exclusion up the chain,
    so the constraint pass re-draws the type -- and ``_rescope_slot`` its dependents --
    instead. Type needs are not re-emitted: ``_expand_affordances`` already covers them.
    Kind rules cover every kind, not only a place's own kind pool, because a wired or
    locked kind can reach any place.
    """
    stances = pack.value_stances.get(STANCE_FIELD, {})
    if not pack.place_stances or not stances:
        return ()
    name = type_field(pack)
    types_by_kind = {
        kind: pool_for(pack, name, {KIND_FIELD: kind}) if name is not None else ()
        for kind in pack.kinds
    }
    forms_by_type = {
        (kind, value): pool_for(pack, STANCE_FIELD, _stance_scope(pack, kind, value))
        for kind in pack.kinds
        for value in (types_by_kind[kind] or (None,))
    }
    blocked_types: dict[frozenset[str], list[str]] = {}
    blocked_kinds: dict[str, list[str]] = {}
    for environment in pool_options(pack, ENVIRONMENT_FIELD):
        support = supported_stances(pack, environment)
        blocks = blocked_stances(pack, environment)
        affords = affordances_of(pack, environment)
        stuck: set[str] = set()
        for kind in pack.kinds:
            alive = False
            for value in types_by_kind[kind] or (None,):
                forms = forms_by_type[(kind, value)]
                stands = not forms or any(
                    not stances.get(form) or stances_fit(stances[form], support, blocks)
                    for form in forms
                )
                if value is not None and not stands:
                    stuck.add(value)
                needs_met = value is None or resolved_needs(pack, name, value) <= affords
                alive = alive or (stands and needs_met)
            if not alive:
                blocked_kinds.setdefault(kind, []).append(environment)
        if stuck:
            blocked_types.setdefault(frozenset(stuck), []).append(environment)
    rules = [
        ConstraintRule(
            type=RULE_EXCLUDE,
            field=ENVIRONMENT_FIELD,
            values=tuple(places),
            excludes_field=f"entity*.{name}",
            excludes_values=tuple(sorted(values)),
            reason="nothing of this type can hold itself up here",
        )
        for values, places in blocked_types.items()
    ]
    rules += [
        ConstraintRule(
            type=RULE_EXCLUDE,
            field=ENVIRONMENT_FIELD,
            values=tuple(places),
            excludes_field=f"entity*.{KIND_FIELD}",
            excludes_values=(kind,),
            reason="nothing of this kind can exist here",
        )
        for kind, places in blocked_kinds.items()
    ]
    return tuple(rules)


def _expand_relation_roles(pack: GenrePack) -> tuple[ConstraintRule, ...]:
    """Drop a relation whose endpoint kind cannot do its part."""
    if not pack.kind_capabilities:
        return ()
    kinds = tuple(pack.kinds)
    rules: list[ConstraintRule] = []
    for relation, (first_needs, second_needs) in pack.relation_roles.items():
        for needs, endpoint in (
            (frozenset(first_needs), FIRST_ENDPOINT),
            (frozenset(second_needs), SECOND_ENDPOINT),
        ):
            if not needs:
                continue
            # The relation is the target, not the kind: when an endpoint cannot
            # do its part the relation is re-drawn, so an inert subject draws an
            # inert-safe relation rather than the kind being re-drawn to None.
            disallowed = tuple(
                kind
                for kind in kinds
                if not needs <= pack.kind_capabilities.get(kind, frozenset())
            )
            if not disallowed:
                continue
            rules.append(
                ConstraintRule(
                    type=RULE_EXCLUDE,
                    field=f"{endpoint}.kind",
                    values=disallowed,
                    excludes_field=RELATION_ANY,
                    excludes_values=(relation,),
                    reason=f"this relation needs a {endpoint} endpoint that can "
                           f"{', '.join(sorted(needs))}",
                )
            )
    return tuple(rules)


#: Which content tags survive each ``scene_filter``. "Peaceful" drops the
#: conflict-tagged values and "Conflict" drops the peaceful-tagged ones; neutral
#: values are drawn under all three, which is why most of a pack is neutral.
_FILTER_ALLOWS: Mapping[str, frozenset[str]] = MappingProxyType({
    "Any": CONTENT_TAGS,
    "Peaceful": frozenset({TAG_NEUTRAL, TAG_PEACEFUL_ONLY}),
    "Conflict": frozenset({TAG_NEUTRAL, TAG_CONFLICT_ONLY}),
})


def canonical_scene_filter(pack: GenrePack, value: str) -> str:
    """The filter a node's label applies: ``"No gore"`` -> ``"Peaceful"``.

    A canonical name is accepted as itself, so a script, a test or an older
    saved graph that passes ``"Peaceful"`` keeps working on any genre.
    """
    if value in SCENE_FILTERS:
        return value
    try:
        return pack.scene_filter_labels[value]
    except KeyError:
        raise ValueError(
            f"unknown scene_filter {value!r}; expected one of "
            f"{[*pack.scene_filter_labels, *SCENE_FILTERS]}"
        ) from None


def allowed_tags(scene_filter: str) -> frozenset[str]:
    """The content tags a given ``scene_filter`` may draw."""
    try:
        return _FILTER_ALLOWS[scene_filter]
    except KeyError:
        raise ValueError(
            f"unknown scene_filter {scene_filter!r}; expected one of {list(SCENE_FILTERS)}"
        ) from None


def tag_for(pack: GenrePack, name: str, value: str) -> str:
    """The content tag on one value of one field.

    Untagged values read as ``neutral``. That is deliberate: an authoring gap
    should cost a value its *filtering*, not its existence -- a pack that
    dropped every untagged value would empty a pool mid-render, where the user
    meets it, instead of failing in ``tests/test_content_tags.py``, where the
    author does.
    """
    return pack.tags.get(name, {}).get(value, TAG_NEUTRAL)


def filtered_pool(
    pack: GenrePack,
    name: str,
    scope: Mapping[str, str | None] | str | None = None,
    scene_filter: str = DEFAULT_SCENE_FILTER,
) -> tuple[str, ...]:
    """``pool_for`` with the content filter applied -- the ``scene_filter`` pre-pass.

    Masking happens **before** any draw, so "Peaceful" produces a subject with no
    weapons *described* rather than a subject described as unarmed. The pool
    going empty is a legitimate, intended outcome (it is exactly what happens to
    ``armament`` under "Peaceful"); the caller resolves the field to ``None`` and
    the prose says nothing about it. Absence by omission, never by negation.

    A field the filter does not touch (``tag_scoped`` is False) is returned
    whole, whatever tags it might carry -- one place decides what the filter
    reaches, and it is the field's own declaration.
    """
    values = pool_for(pack, name, scope)
    spec = pack.entity_fields.get(name) or pack.scene_fields.get(name)
    if spec is None or not spec.tag_scoped:
        return values
    permitted = allowed_tags(scene_filter)
    return tuple(v for v in values if tag_for(pack, name, v) in permitted)


def label_for(pack: GenrePack, name: str, kind: str | None = None) -> str:
    """The widget label for ``name`` under ``kind``, falling back to generic."""
    spec = pack.entity_fields.get(name) or pack.scene_fields.get(name)
    generic = spec.label if spec else name
    if kind is None:
        return generic
    return pack.labels.get(name, {}).get(kind, generic)


def label_qualifier(definition: FieldDef, slots: int) -> str:
    """What distinguishes one copy of a repeated widget from the next.

    A scene node carries four ``Kind`` widgets and six ``Relation`` widgets. Left
    alone they would all read the same, which on a 48-widget node face is not a
    cosmetic problem -- it is not knowing which slot you are editing. The
    qualifier is kept *separate* from the label rather than baked into it because
    the frontend swaps the label per kind ("Engine count" / "Eye count") and
    would otherwise have to parse the suffix back off to do it.

    Empty for a single-entity node, so the Scene Entity's widgets read plainly.
    """
    if definition.endpoints is not None:
        first, second = definition.endpoints
        return f" {first}-{second}"
    if slots > 1 and definition.slot is not None:
        return f" {definition.slot}"
    return ""


def widget_label(definition: FieldDef, slots: int, label: str | None = None) -> str:
    """The label a widget displays: a generic or per-kind label, qualified."""
    return f"{label or definition.label}{label_qualifier(definition, slots)}"


def widget_choices(definition: FieldDef) -> tuple[str, ...]:
    """The literal option list a combo widget is registered with.

    ``["Random"] + options + ["None"]`` for a descriptive field; a control's own
    fixed options, untouched. ``None`` sits last so it reads as "and otherwise,
    leave this out" rather than as the first thing the eye lands on.
    """
    if definition.control or definition.widget != "combo":
        return definition.options
    tail = (NONE,) if definition.optional else ()
    return (RANDOM, *definition.options, *tail)


def field_tooltip(definition: FieldDef) -> str:
    """Help text plus the one mechanic line every descriptive widget shares."""
    if definition.control:
        return definition.tooltip
    mechanic = f"{definition.group} | {RANDOM}=randomize, value=lock, {NONE}=omit"
    return f"{definition.tooltip}\n{mechanic}" if definition.tooltip else mechanic


# ---------------------------------------------------------------------------
# The builder both node classes call
# ---------------------------------------------------------------------------

#: Controls that parameterize generation. ``set_all_fields`` is deliberately
#: NOT here: it is a bulk edit of the other widgets performed by the frontend,
#: with no pool, no group, no tag scope and no presence in ``prompt_json``. Six
#: of a FieldDef's seven contract keys would be meaningless for it. Its widget
#: position is still pinned, by ``widget_order`` below.
_SEED_SPEC = FieldSpec(
    group="Controls",
    label="Seed",
    tooltip=(
        "Seed for reproducible scenes. The control below defaults to 'randomize' "
        "so every run differs; set it to 'fixed' to reproduce a scene."
    ),
    optional=False,
    control=True,
    widget="int",
    default=0,
)

_SCENE_FILTER_SPEC = FieldSpec(
    group="Controls",
    label="Scene filter",
    tooltip=(
        "Restrict what random draws may pick. 'Peaceful' leaves weapons and "
        "hostile actions out of the description entirely; 'Conflict' favours "
        "them. A value you lock yourself is always kept."
    ),
    optional=False,
    control=True,
    default=DEFAULT_SCENE_FILTER,
)


_ENTITY_COUNT_SPEC = FieldSpec(
    group="Controls",
    label="Entities",
    tooltip=(
        "How many subjects the scene has. Slot 1 is described most fully and "
        "later slots a little less, because an image has one subject's worth of "
        "attention to share out however many things are in it. Raising this "
        "reveals that slot's widgets on the node; every slot it reveals is "
        "described, never just named. Two is the sweet spot -- three and four "
        "work, and read as a crowd. A Scene Entity wired into a slot occupies "
        "it whatever this says. How much a slot actually speaks is also capped "
        "by what kind of thing it is: a creature or a person carries its whole "
        "component list, a station or a wreck only its silhouette, so a slot "
        "full of locked widgets can still read shorter than you expect."
    ),
    optional=False,
    control=True,
    default="1",  # DEFAULT_ENTITY_COUNT, as a combo value
)

_CONTROL_SPECS: "OrderedDict[str, tuple[FieldSpec, tuple[str, ...]]]" = OrderedDict(
    [
        ("seed", (_SEED_SPEC, ())),
        (ENTITY_COUNT_KEY, (_ENTITY_COUNT_SPEC, ())),
        (SCENE_FILTER_KEY, (_SCENE_FILTER_SPEC, SCENE_FILTERS)),
    ]
)

#: The one control the entity node shares with the scene node.
_ENTITY_NODE_CONTROLS: tuple[str, ...] = ("seed",)


def _definition(
    *,
    key: str,
    path: str,
    base: str,
    spec: FieldSpec,
    options: tuple[str, ...],
    slot: int | None = None,
    endpoints: tuple[int, int] | None = None,
    default: Any = None,
) -> FieldDef:
    return FieldDef(
        key=key,
        path=path,
        base=base,
        slot=slot,
        endpoints=endpoints,
        group=spec.group,
        label=spec.label,
        tooltip=spec.tooltip,
        options=options,
        optional=spec.optional,
        control=spec.control,
        kind_scoped=spec.kind_scoped,
        scope=spec.scope,
        tag_scoped=spec.tag_scoped,
        count_partner=spec.count_partner,
        weights=spec.weights,
        omission_weight=spec.omission_weight,
        widget=spec.widget,
        default=spec.default if default is None else default,
    )


def _brief_field_names(pack: GenrePack) -> tuple[str, ...]:
    """What a supporting slot carries when nothing is wired into it.

    ``KIND_FIELD`` is always included, whether or not the pack marked it brief:
    a slot's kind is what decides whether the slot is occupied at all, so a
    supporting slot without that widget could never be filled and slots 2-N
    would be dead on every node built from that pack. A pack that already marks
    it brief -- which any pack should -- is unaffected, so this changes no
    widget count and no widget order.
    """
    brief = [name for name, spec in pack.entity_fields.items() if spec.brief]
    if KIND_FIELD not in brief and KIND_FIELD in pack.entity_fields:
        brief.insert(0, KIND_FIELD)
    return tuple(brief)


def build_field_definitions(pack: GenrePack, slots: int) -> "OrderedDict[str, FieldDef]":
    """Every widget both node classes need, keyed by widget key, in widget order.

    ``slots == ENTITY_NODE_SLOTS`` (0) builds the Scene Entity layout: a seed
    plus the pack's whole entity morphology, keyed bare (``kind``) but addressed
    at slot 1 (``entity1.kind``) so one constraint rule set governs both nodes.

    ``slots >= 1`` builds the Scene Weaver layout: the generation controls, the
    environment, a fully-described slot 1, brief slots 2..N, a situation per
    slot and a relation per slot pair.

    The returned order **is** the widget order, minus ``set_all_fields`` --
    see ``widget_order``. It is a compatibility surface: appending is safe,
    reordering silently rewrites every saved workflow.
    """
    if slots < 0:
        raise ValueError(f"slots must be >= 0, got {slots}")

    definitions: "OrderedDict[str, FieldDef]" = OrderedDict()

    control_names = _ENTITY_NODE_CONTROLS if slots == ENTITY_NODE_SLOTS else tuple(_CONTROL_SPECS)
    for name in control_names:
        spec, options = _CONTROL_SPECS[name]
        if name == ENTITY_COUNT_KEY:
            # Options depend on how many slots this node has, which the spec
            # cannot know: the same contract serves a pack with two.
            options = entity_count_options(slots)
        if name == SCENE_FILTER_KEY:
            # A genre names the ends of its own filter axis.
            options = tuple(pack.scene_filter_labels)
            spec = replace(
                spec,
                default=pack.scene_filter_default,
                tooltip=pack.scene_filter_tooltip or spec.tooltip,
            )
        definitions[name] = _definition(
            key=name, path=name, base=name, spec=spec, options=options
        )

    if slots == ENTITY_NODE_SLOTS:
        for name, spec in pack.entity_fields.items():
            definitions[name] = _definition(
                key=name,
                path=slot_path(LONE_ENTITY_SLOT, name),
                base=name,
                spec=spec,
                options=pool_options(pack, name),
                slot=LONE_ENTITY_SLOT,
            )
        return definitions

    environment_spec = pack.scene_fields[ENVIRONMENT_FIELD]
    definitions[ENVIRONMENT_FIELD] = _definition(
        key=ENVIRONMENT_FIELD,
        path=ENVIRONMENT_FIELD,
        base=ENVIRONMENT_FIELD,
        spec=environment_spec,
        options=pool_options(pack, ENVIRONMENT_FIELD),
    )

    brief = _brief_field_names(pack)
    situation_spec = pack.scene_fields[SITUATION_FIELD]
    for slot in range(1, slots + 1):
        # Slot 1 carries the whole morphology so the core node is never a stub;
        # supporting slots stay brief until a Scene Entity is wired into them.
        names = tuple(pack.entity_fields) if slot == 1 else brief
        for name in names:
            # Every slot's kind defaults to "Random". An untouched node is still
            # one entity, because ``entity_count`` defaults to 1 and slots past
            # it are emptied before anything is drawn -- so the *control* says
            # how many subjects there are, and the widget says what they are.
            #
            # These defaults used to be "None", which made the count control a
            # lie the moment it was raised: slot 2 would be revealed, and stay
            # empty, because its hidden widget still said None. Coercing None to
            # Random inside the engine fixed that and broke something worse --
            # a slot the user had deliberately emptied came back.
            definitions[slot_key(slot, name)] = _definition(
                key=slot_key(slot, name),
                path=slot_path(slot, name),
                base=name,
                spec=pack.entity_fields[name],
                options=pool_options(pack, name),
                slot=slot,
            )
        definitions[slot_key(slot, SITUATION_FIELD)] = _definition(
            key=slot_key(slot, SITUATION_FIELD),
            path=slot_path(slot, SITUATION_FIELD),
            base=SITUATION_FIELD,
            spec=situation_spec,
            options=pool_options(pack, SITUATION_FIELD),
            slot=slot,
        )

    relation_spec = pack.scene_fields[RELATION_FIELD]
    for first, second in relation_pairs(slots):
        key = relation_key(first, second)
        definitions[key] = _definition(
            key=key,
            path=key,
            base=RELATION_FIELD,
            spec=relation_spec,
            options=pool_options(pack, RELATION_FIELD),
            endpoints=(first, second),
        )

    relation_position_spec = pack.scene_fields[RELATION_POSITION_FIELD]
    for first, second in relation_pairs(slots):
        key = relation_position_key(first, second)
        definitions[key] = _definition(
            key=key,
            path=key,
            base=RELATION_POSITION_FIELD,
            spec=relation_position_spec,
            options=pool_options(pack, RELATION_POSITION_FIELD),
            endpoints=(first, second),
        )

    context_spec = pack.scene_fields.get(CONTEXT_FIELD)
    if context_spec is not None:
        definitions[CONTEXT_FIELD] = _definition(
            key=CONTEXT_FIELD,
            path=CONTEXT_FIELD,
            base=CONTEXT_FIELD,
            spec=context_spec,
            options=pool_options(pack, CONTEXT_FIELD),
        )

    return definitions


def build_resolution_definitions(
    pack: GenrePack, slots: int
) -> "OrderedDict[str, FieldDef]":
    """Every field the *engine* resolves, keyed by widget key -- the whole
    address space, not just the widget list.

    ``build_field_definitions`` answers "what is drawn on the node face".
    This answers "what does a scene contain", and the two deliberately differ:
    a supporting slot carries four widgets but a whole morphology, because
    twenty-one dropdowns times four slots is not a usable node face while a
    four-word entity is not a described one.

    A field with a widget keeps that widget's definition -- its default, its
    options, its lock behaviour. A field without one is synthesized with a
    default of ``RANDOM``, which is what "the user gave no instruction" means
    everywhere else in this pack.

    Two things depend on this being the wider set. Resolution draws these
    fields, so a supporting slot is described rather than merely named. And the
    constraint pass addresses fields through it, so a rule keyed on
    ``entity*.armament`` reaches slot 3 -- which is exactly the case
    ``constraint_address_space`` was widened for. Building the constraint map
    from the widget list instead let a data core carry missile racks, because
    no rule could see a field no widget backed.
    """
    definitions = build_field_definitions(pack, slots)
    if slots == ENTITY_NODE_SLOTS:
        return definitions
    for slot in range(1, slots + 1):
        for name, spec in pack.entity_fields.items():
            key = slot_key(slot, name)
            if key in definitions:
                continue
            definitions[key] = _definition(
                key=key,
                path=slot_path(slot, name),
                base=name,
                spec=spec,
                options=pool_options(pack, name),
                slot=slot,
                default=RANDOM,
            )
    return definitions


def widget_order(pack: GenrePack, slots: int) -> tuple[str, ...]:
    """The full widget order for a node, ``set_all_fields`` included.

    A saved workflow's ``widgets_values`` is positional, so this single
    declaration is what stops the bulk-edit control drifting one slot left or
    right between releases and silently reassigning every value after it. Node
    classes must emit their widgets in exactly this order.

    ``set_all_fields`` sits last among the controls -- immediately before
    ``environment`` -- so the controls read as one block at the top of the
    node face and every descriptive widget keeps a stable index behind them.
    """
    keys = list(build_field_definitions(pack, slots))
    if slots == ENTITY_NODE_SLOTS:
        return tuple(keys)
    keys.insert(keys.index(ENVIRONMENT_FIELD), SET_ALL_FIELDS_KEY)
    return tuple(keys)
