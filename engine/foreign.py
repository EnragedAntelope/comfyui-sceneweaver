"""A wired entity from another genre: place it, mask it, give it something to do.

The host pack has never heard of a harpy, so everything it knows about one is
wrong: it spoke a spacefarer through its stranger grammar ("It is a hard-suited
silhouette, covered in ... suit"), drew a drop pod "charging headlong" and a
skeleton "drifting in open space" out of its own default acts, and left the
guest's colours unhyphenated. The *guest* pack knows all of it, so this module
asks the guest -- through the registry, never by name -- and translates only
what the two genres share: stances, place affordances and content tags.

Genre-blind throughout. A guest whose pack was never registered falls back to
the host's own handling, which is what every foreign entity got before.
"""
from __future__ import annotations

import random
from typing import Any, Mapping

try:
    from ..data.genre import (
        ENVIRONMENT_FIELD,
        KIND_FIELD,
        RULE_EXCLUDE,
        SITUATION_FIELD,
        STANCE_FIELD,
        GenrePack,
        affordances_of,
        allowed_tags,
        bind_address,
        blocked_stances,
        pool_for,
        resolved_needs,
        slot_path,
        stances_fit,
        supported_stances,
        tag_for,
        type_field,
    )
except ImportError:  # pragma: no cover -- standalone/test context
    from data.genre import (
        ENVIRONMENT_FIELD,
        KIND_FIELD,
        RULE_EXCLUDE,
        SITUATION_FIELD,
        STANCE_FIELD,
        GenrePack,
        affordances_of,
        allowed_tags,
        bind_address,
        blocked_stances,
        pool_for,
        resolved_needs,
        slot_path,
        stances_fit,
        supported_stances,
        tag_for,
        type_field,
    )

from .registry import registered_pack

#: A stance one genre has and another does not, said in the nearest shared word.
#: English, not genre data: a serpent that slithers walks the same ground, and a
#: ship under sail floats on the water it needs.
STANCE_EQUIVALENTS: Mapping[str, str] = {
    "slithers": "walks",
    "climbs": "walks",
    "sails": "floats",
    "orbits": "floats",
    "falls": "flies",
}

#: A place word one genre has and another does not, said in the nearest shared
#: word, first match wins: open space and a void between worlds are the same
#: emptiness, and a thing built to hang above a world belongs in that emptiness
#: too -- a space station read wrong in a sea of clouds. A genre with neither
#: has only the sky to hang it in: a rogue planet was put in a manor ballroom.
AFFORDANCE_EQUIVALENTS: Mapping[str, tuple[str, ...]] = {
    "open-space": ("void", "sky"),
    "void": ("open-space", "sky"),
    "aloft": ("void", "sky"),
    "deep-space": ("void", "sky"),
}

#: A need every place of a genre meets when the genre has no emptiness at all:
#: horror has no word for gravity because nothing in it is ever weightless, and
#: the unknown word failed every flying ship's strict placement.
_UNIVERSAL_WITHOUT_EMPTINESS: frozenset[str] = frozenset({"gravity"})
_EMPTINESS: frozenset[str] = frozenset({"open-space", "void"})

_GUEST_SLOT = 1


def guest_pack(host: GenrePack, payload: "Mapping[str, Any] | None") -> "GenrePack | None":
    """The registered pack that built ``payload``, when it is not the host's own."""
    if not payload:
        return None
    genre = payload.get("genre")
    if not genre or genre == host.slug:
        return None
    return registered_pack(genre)


def voice_of(entity_genre: "str | None", host: GenrePack) -> GenrePack:
    """The pack an entity is spoken with: its own when it is foreign and known."""
    if entity_genre and entity_genre != host.slug:
        guest = registered_pack(entity_genre)
        if guest is not None:
            return guest
    return host


def _host_stance_words(host: GenrePack) -> "frozenset[str]":
    words: set[str] = set()
    for stances in host.place_stances.values():
        words |= set(stances)
    return frozenset(words)


def translate_stances(stances: "frozenset[str] | set[str]", host: GenrePack) -> "frozenset[str]":
    """Guest stances in the host's vocabulary; a stance the host lacks becomes its equivalent."""
    known = _host_stance_words(host)
    out: set[str] = set()
    for stance in stances:
        if stance in known:
            out.add(stance)
        elif STANCE_EQUIVALENTS.get(stance) in known:
            out.add(STANCE_EQUIVALENTS[stance])
    return frozenset(out)


def _host_affordance_words(host: GenrePack) -> "frozenset[str]":
    words: set[str] = set()
    for affordances in host.place_affordances.values():
        words |= set(affordances)
    return frozenset(words)


def _guest_scope(guest: GenrePack, fields: Mapping[str, "str | None"]) -> dict[str, "str | None"]:
    scope: dict[str, str | None] = {KIND_FIELD: fields.get(KIND_FIELD)}
    name = type_field(guest)
    if name is not None:
        scope[name] = fields.get(name)
    if STANCE_FIELD in guest.entity_fields:
        scope[STANCE_FIELD] = fields.get(STANCE_FIELD)
    return scope


def guest_body_stances(guest: GenrePack, fields: Mapping[str, "str | None"]) -> "frozenset[str]":
    """What the guest's body can do: its form's stances, else any form its type can take."""
    by_form = guest.value_stances.get(STANCE_FIELD, {})
    form = fields.get(STANCE_FIELD)
    if form and by_form.get(form):
        return frozenset(by_form[form])
    stances: set[str] = set()
    for candidate in pool_for(guest, STANCE_FIELD, _guest_scope(guest, fields)):
        stances |= set(by_form.get(candidate, ()))
    return frozenset(stances)


def _needs_met(
    needs: "frozenset[str]", host: GenrePack, environment: str, *, unknown_ok: bool
) -> bool:
    """Whether the host place meets a guest need set, read through shared words only.

    A need the host vocabulary never uses cannot be checked; ``unknown_ok``
    decides whether that passes (placing a body) or fails (choosing an act --
    an act that needs "open-space" has nowhere to happen in a genre without it).
    """
    vocabulary = _host_affordance_words(host)
    here = affordances_of(host, environment)
    for need in needs:
        if need not in vocabulary:
            if need in _UNIVERSAL_WITHOUT_EMPTINESS and not vocabulary & _EMPTINESS:
                continue
            need = next(
                (word for word in AFFORDANCE_EQUIVALENTS.get(need, ()) if word in vocabulary), need
            )
        if need in vocabulary:
            if need not in here:
                return False
        elif not unknown_ok:
            return False
    return True


#: The stance a body is placed by, most grounded first. A body that walks is put
#: where it can walk even if it can also float: a spacefarer's zero-g drift is
#: "floats" too, and translated into a genre with no open space it put a man in
#: a spacesuit in a sea of clouds.
PRIMARY_STANCE_ORDER: tuple[str, ...] = (
    "walks", "rolls", "swims", "flies", "hovers", "floats", "rests",
)


def primary_stance(guest: GenrePack, host: GenrePack, fields: Mapping[str, "str | None"]) -> "str | None":
    """The body's first stance in ``PRIMARY_STANCE_ORDER``, in the host's words."""
    stances = translate_stances(guest_body_stances(guest, fields), host)
    return next((s for s in PRIMARY_STANCE_ORDER if s in stances), None)


def _places(pack: GenrePack) -> "tuple[str, ...]":
    return tuple(dict.fromkeys(
        v for values in pack.pools.get(ENVIRONMENT_FIELD, {}).values() for v in values
    ))


_HABITAT_CACHE: dict[tuple, frozenset] = {}


def habitat(guest: GenrePack, fields: Mapping[str, "str | None"]) -> "frozenset[str]":
    """What every place the guest's own genre puts this body in has in common.

    The guest pack's kind pools already know where its kind belongs: a space
    station is only ever in open space, an ogre only ever breathes air. That
    common ground is what a host place must also afford -- an ogre was
    placed on a space-station approach lane, a station in a sea of clouds.
    """
    key = (guest.slug, tuple(sorted((k, v) for k, v in fields.items() if v)))
    if key not in _HABITAT_CACHE:
        kind = fields.get(KIND_FIELD)
        homes = [
            affordances_of(guest, place) for place in _places(guest)
            if (not kind or kind in pool_for(guest, KIND_FIELD, {ENVIRONMENT_FIELD: place}))
            and guest_fits_place(guest, guest, fields, place)
        ]
        _HABITAT_CACHE[key] = frozenset.intersection(*homes) if homes else frozenset()
    return _HABITAT_CACHE[key]


def _traits_of(pack: GenrePack, name: str, value: "str | None") -> "set[str]":
    return set(pack.value_traits.get(name, {}).get(value, ())) if value else set()


def _place_refuses_body(
    guest: GenrePack, host: GenrePack, fields: Mapping[str, "str | None"], environment: str
) -> bool:
    """Whether a host place trait conflicts with a guest body trait of the same name.

    Trait words are shared vocabulary the way stances are: one genre's crawlway
    is ``cramped-room`` and another's "towering" elemental is ``large-scale``.
    """
    place = _traits_of(host, ENVIRONMENT_FIELD, environment)
    if not place:
        return False
    body: set[str] = set()
    for name, value in fields.items():
        body |= _traits_of(guest, name, value)
    # Either genre's rule counts: the host may never pair the two words itself
    # (a drowned church is ``aqueous`` in a genre with no fire creature).
    conflicts = set(host.trait_conflicts) | set(guest.trait_conflicts)
    return any(a in place and b in body for a, b in conflicts)


def guest_fits_place(
    guest: GenrePack,
    host: GenrePack,
    fields: Mapping[str, "str | None"],
    environment: str,
    *,
    primary_only: bool = False,
    strict: bool = False,
    any_stance: bool = False,
    by_type_only: bool = False,
) -> bool:
    """Whether a host place can hold this guest body: its stances and its type's needs.

    ``primary_only`` asks the stricter question -- can it stand the way it
    mostly stands -- which the placement tries first. ``strict`` fails a need
    the host has no word for (a space station has nowhere to be in a genre
    with no open space), and the placement relaxes it last. ``any_stance`` is
    the last resort, a place that meets the needs whatever the body's stances:
    a war galley no host shore let float was put in a cloud deck instead.
    ``by_type_only`` drops the habitat inference and keeps only what the type
    itself needs: a sunken submersible's seabed floor is a word fantasy's water
    never grants, and without it the wreck went into an apothecary's workshop.
    """
    stances = translate_stances(guest_body_stances(guest, fields), host)
    if primary_only:
        first = primary_stance(guest, host, fields)
        if first is not None:
            stances = frozenset({first})
    if stances and not any_stance and not stances_fit(
        stances, supported_stances(host, environment), blocked_stances(host, environment)
    ):
        return False
    if host is not guest and not by_type_only and not _needs_met(
        habitat(guest, fields), host, environment, unknown_ok=not strict
    ):
        return False
    # Asked of the guest's own places too, so its habitat is drawn from the
    # places its own genre would really put it.
    if _place_refuses_body(guest, host, fields, environment):
        return False
    name = type_field(guest)
    value = fields.get(name) if name is not None else None
    if name is not None and value:
        return _needs_met(
            resolved_needs(guest, name, value), host, environment, unknown_ok=not strict
        )
    return True


def mask_for_filter(
    guest: GenrePack,
    fields: "dict[str, str | None]",
    chosen: "frozenset[str]",
    scene_filter: str,
) -> None:
    """Drop the guest values the host's content filter excludes, read by the guest's tags.

    Omitted rather than re-drawn: the host has no pool of the guest's genre to
    draw a replacement from, and absence says nothing where a wrong-genre
    substitute would say something false.
    """
    permitted = allowed_tags(scene_filter)
    identity = {KIND_FIELD, type_field(guest)}
    for name, spec in guest.entity_fields.items():
        value = fields.get(name)
        if value is None or name in chosen or name in identity or not spec.tag_scoped:
            continue
        if tag_for(guest, name, value) in permitted:
            continue
        fields[name] = None
        partner = guest.counts.get(name)
        if partner and partner not in chosen:
            fields[partner] = None


def mask_for_place(
    guest: GenrePack,
    host: GenrePack,
    fields: "dict[str, str | None]",
    chosen: "frozenset[str]",
    environment: "str | None",
) -> None:
    """Drop the guest values whose needs the host place fails, read through shared words.

    The guest drew its coat and its gear without knowing where it would stand: a
    "rain-soaked trench coat" brought rain into a habitat ring. Omitted, with its
    count and colour, for the reason ``mask_for_filter`` omits. A need the host
    has no word for fails: a horror chair set against "a wall of warped
    panelling" stood in a fantasy stone crypt, because fantasy has no ``room``.
    """
    if environment is None:
        return
    identity = {KIND_FIELD, type_field(guest), STANCE_FIELD}
    for name in guest.entity_fields:
        value = fields.get(name)
        if value is None or name in chosen or name in identity:
            continue
        if _needs_met(resolved_needs(guest, name, value), host, environment, unknown_ok=False):
            continue
        fields[name] = None
        for other, other_spec in guest.entity_fields.items():
            if other_spec.renders_with == name and other not in chosen:
                fields[other] = None


def _entity_state(guest: GenrePack, fields: Mapping[str, "str | None"]) -> dict[str, "str | None"]:
    return {slot_path(_GUEST_SLOT, name): value for name, value in fields.items()}


def _entity_rules(guest: GenrePack) -> tuple:
    """The guest's rules that bind to one slot -- relation-pair rules have no pair here."""
    rules = []
    for rule in guest.all_constraints:
        try:
            for address in (rule.field, rule.excludes_field, rule.requires_field):
                if address:
                    bind_address(address, _GUEST_SLOT, None)
        except ValueError:
            continue
        rules.append(rule)
    return tuple(rules)


def _act_allowed_by_entity(
    guest: GenrePack, state: Mapping[str, "str | None"], act: str
) -> bool:
    """Whether the guest's own rules let this entity do ``act``, either way round.

    Both directions matter: the entity's values can exclude the act (a petrified
    thing does not act), and the act can exclude or require an entity value (a
    stone act requires "petrified"). Rules keyed on the environment never fire
    here -- the environment is the host's -- and are handled by the place check.
    """
    situation = slot_path(_GUEST_SLOT, SITUATION_FIELD)
    for rule in _entity_rules(guest):
        trigger = bind_address(rule.field, _GUEST_SLOT, None)
        if rule.type == RULE_EXCLUDE:
            target = bind_address(rule.excludes_field or "", _GUEST_SLOT, None)
            if target == situation and act in rule.excludes_values:
                if trigger != situation and state.get(trigger) in rule.triggers:
                    return False
            if trigger == situation and act in rule.triggers:
                if state.get(target) in rule.excludes_values:
                    return False
        elif trigger == situation and act in rule.triggers and rule.requires_field:
            target = bind_address(rule.requires_field, _GUEST_SLOT, None)
            if target.startswith(ENVIRONMENT_FIELD):
                return False
            allowed = set(rule.requires_values) if rule.requires_values else {rule.requires_value}
            if state.get(target) not in allowed:
                return False
    return True


def guest_situation(
    rng: random.Random,
    guest: GenrePack,
    host: GenrePack,
    fields: Mapping[str, "str | None"],
    environment: "str | None",
    scene_filter: str,
) -> "str | None":
    """An act from the guest's own repertoire that this host place can stage, or None.

    The guest's acts were written for this body -- a spirit beckons, a drop pod
    burns in -- so they are asked first; each is kept only if the host place
    meets its needs, supports one of its stances, and the host filter allows its
    tag. ``None`` sends the caller back to the host's own draw.
    """
    if environment is None:
        return None
    state = _entity_state(guest, fields)
    permitted = allowed_tags(scene_filter)
    support = supported_stances(host, environment)
    tiers = guest.value_tiers.get(SITUATION_FIELD, {})
    # Two tiers. An act that needs nothing of the place was written to work
    # anywhere; one that needs something was written for the guest's own world
    # ("bracing a failing bulkhead" meets "structure" in a treasure vault and is
    # still a spaceship's wall). The place-neutral tier is preferred.
    neutral: list[tuple[str, float]] = []
    placed: list[tuple[str, float]] = []
    for act in pool_for(guest, SITUATION_FIELD, _guest_scope(guest, fields)):
        if tag_for(guest, SITUATION_FIELD, act) not in permitted:
            continue
        needs = resolved_needs(guest, SITUATION_FIELD, act)
        if not _needs_met(needs, host, environment, unknown_ok=False):
            continue
        stances = guest.value_stances.get(SITUATION_FIELD, {}).get(act)
        if stances and not (translate_stances(stances, host) & support):
            continue
        if not _act_allowed_by_entity(guest, state, act):
            continue
        weight = float(guest.tier_weights.get(tiers.get(act, ""), 1.0))
        (placed if needs else neutral).append((act, weight))
    candidates = neutral or placed
    if not candidates:
        return None
    return rng.choices(
        [act for act, _ in candidates], weights=[w for _, w in candidates], k=1
    )[0]
