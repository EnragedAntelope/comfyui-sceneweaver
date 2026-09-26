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
from typing import Any, Iterable, Mapping

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

#: Place words that say what a place is *shaped* like rather than what it is
#: like to be in. A home whose shape word the host has no word for is a shape
#: the host cannot build: a hovercraft's hangar is a ``dock``, and read without
#: it as a floor under a roof it put the skimmer in a horror hallway (#1318).
#: Every other word a host lacks -- sunlight, dust, a grave -- is only dropped.
_SHAPE_WORDS: frozenset[str] = frozenset({
    "floor", "ground", "structure", "room", "water", "submerged", "shoreline",
    "sky", "dock", "cloud-deck", "navigable", "open-ground",
    "open-space", "void", "deep-space", "aloft",
})

#: Place words that cannot both hold. A sunlit colony dome was one guest rover's
#: home, and a host with no word for sunlight still says its morgue is dark:
#: read without the pair, the rover was parked in the morgue.
_OPPOSITES: Mapping[str, str] = {"sunlight": "dark", "dark": "sunlight"}

#: A need every place of a genre meets when the genre has no emptiness at all:
#: horror has no word for gravity because nothing in it is ever weightless, and
#: the unknown word failed every flying ship's strict placement.
_UNIVERSAL_WITHOUT_EMPTINESS: frozenset[str] = frozenset({"gravity"})
_EMPTINESS: frozenset[str] = frozenset({"open-space", "void"})
_SPACE_WORDS: frozenset[str] = frozenset({"open-space", "void", "deep-space"})

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


def _alternatives(need: str, vocabulary: "frozenset[str]") -> "frozenset[str] | None":
    """The host words any one of which meets ``need``; empty when every place does.

    ``None`` when the host has no word for it at all.
    """
    if need in vocabulary:
        return frozenset({need})
    if need in _UNIVERSAL_WITHOUT_EMPTINESS and not vocabulary & _EMPTINESS:
        return frozenset()
    known = [word for word in AFFORDANCE_EQUIVALENTS.get(need, ()) if word in vocabulary]
    return frozenset(known[:1]) if known else None


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
        alternatives = _alternatives(need, vocabulary)
        if alternatives is None:
            if not unknown_ok:
                return False
        elif alternatives and not alternatives & here:
            return False
    return True


def _home_met(
    home: "frozenset[str]", vocabulary: "frozenset[str]", here: "frozenset[str]",
    guest_vocabulary: "frozenset[str]", *, lenient: bool = False,
) -> float:
    """The share of a home's words the host place meets.

    A condition word the host lacks says nothing; a shape word it lacks makes
    the home one the host cannot build (0), unless ``lenient``. Nor may the
    place have a shape both genres can name that the home lacks: a sewer's
    water is no hover-car concourse's. A home in space read as a host's sky
    asks nothing of the ground under that sky.
    """
    checked = []
    said: set[str] = set()
    for word in home:
        alternatives = _alternatives(word, vocabulary)
        if alternatives is None:
            if word in _SHAPE_WORDS and not lenient:
                return 0.0
        elif alternatives:
            checked.append(alternatives)
            said |= alternatives
    if not lenient and any(_OPPOSITES.get(word) in here for word in home):
        return 0.0
    overhead = bool(home & _SPACE_WORDS) and not vocabulary & _EMPTINESS
    if not lenient and not overhead and any(
        word in _SHAPE_WORDS and word in guest_vocabulary and word not in said
        for word in here
    ):
        return 0.0
    if not checked:
        return 1.0
    return sum(1 for alt in checked if alt & here) / len(checked)


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


_HOMES_CACHE: dict[tuple, tuple] = {}


def homes(guest: GenrePack, fields: Mapping[str, "str | None"]) -> "tuple[frozenset[str], ...]":
    """Every distinct place shape the guest's own genre puts this body in.

    The guest pack's kind pools already know where its kind belongs: a space
    station is only ever in open space, an ogre only ever breathes air. A host
    place must be shaped like *one* of those homes -- an ogre was placed on a
    space-station approach lane, a station in a sea of clouds. Their common
    ground alone was too little: a starship lands on plains and flies in space
    and cloud, so all three shared only "vast", and it was drawn resting in a
    dwarven great hall (#1256).
    """
    key = (guest.slug, tuple(sorted((k, v) for k, v in fields.items() if v)))
    if key not in _HOMES_CACHE:
        kind = fields.get(KIND_FIELD)
        _HOMES_CACHE[key] = tuple(dict.fromkeys(
            affordances_of(guest, place) for place in _places(guest)
            if (not kind or kind in pool_for(guest, KIND_FIELD, {ENVIRONMENT_FIELD: place}))
            and guest_fits_place(guest, guest, fields, place)
        ))
    return _HOMES_CACHE[key]


def habitat_score(
    guest: GenrePack, host: GenrePack, fields: Mapping[str, "str | None"], environment: str,
    *, lenient: bool = False,
) -> float:
    """How nearly a host place is shaped like the guest's best-matching home, 0 to 1."""
    shapes = homes(guest, fields)
    if not shapes:
        return 1.0
    vocabulary = _host_affordance_words(host)
    here = affordances_of(host, environment)
    known = _host_affordance_words(guest)
    return max(_home_met(home, vocabulary, here, known, lenient=lenient) for home in shapes)


def best_habitat(
    guest: GenrePack, host: GenrePack, fields: Mapping[str, "str | None"], places: "Iterable[str]"
) -> "set[str]":
    """The places most like a guest home, for a guest no placement rung could hold.

    A family mausoleum's homes are all walled graveyards and no place of that
    host is one, so it was put anywhere -- a starship medical bay (#1206). An open
    plain is nearer a graveyard than a ward is.
    """
    scored = {
        place: habitat_score(guest, host, fields, place, lenient=True) for place in places
    }
    if not scored:
        return set()
    best = max(scored.values())
    return {place for place, score in scored.items() if score == best}


def skyborne(
    guest: GenrePack, host: GenrePack, fields: Mapping[str, "str | None"], environment: "str | None"
) -> bool:
    """Whether a guest that only ever exists in space stands under this host's open sky.

    A genre with no emptiness hangs a station or a world in its sky, and the
    model draws it standing in the place unless the prose says it is overhead:
    a space station sheared in half on a carnival midway (#1321).
    """
    vocabulary = _host_affordance_words(host)
    if environment is None or vocabulary & _EMPTINESS:
        return False
    here = affordances_of(host, environment)
    if "sky" not in here:
        return False
    shapes = homes(guest, fields)
    if not shapes:
        return False
    # The homes that put it here: a listening post's cloud-city home is one the
    # host cannot build, and counting it left the station standing in a cemetery.
    known = _host_affordance_words(guest)
    scores = {home: _home_met(home, vocabulary, here, known) for home in shapes}
    if not max(scores.values()):
        scores = {home: _home_met(home, vocabulary, here, known, lenient=True) for home in shapes}
    best = max(scores.values())
    return all(home & _SPACE_WORDS for home, score in scores.items() if score == best)


def _traits_of(pack: GenrePack, name: str, value: "str | None") -> "set[str]":
    return set(pack.value_traits.get(name, {}).get(value, ())) if value else set()


#: The fields that say what a body is, and so where it can be.
_IDENTITY_FIELDS: frozenset[str] = frozenset({KIND_FIELD, STANCE_FIELD, "scale"})


def _conflicting(place: "set[str]", value: "set[str]", conflicts) -> bool:
    return any((a in place and b in value) or (b in place and a in value) for a, b in conflicts)


def _place_refuses_body(
    guest: GenrePack, host: GenrePack, fields: Mapping[str, "str | None"], environment: str
) -> bool:
    """Whether a host place trait conflicts with a guest body trait of the same name.

    Trait words are shared vocabulary the way stances are: one genre's crawlway
    is ``cramped-room`` and another's "towering" elemental is ``large-scale``.
    Only what the body *is* decides where it goes; a drawn condition does not:
    a "scorched" bathyscaphe refused every sea and was put in a furnished void
    (#1318 replay). ``mask_for_place`` drops such a value afterwards.
    """
    place = _traits_of(host, ENVIRONMENT_FIELD, environment)
    if not place:
        return False
    body: set[str] = set()
    for name in _IDENTITY_FIELDS | {type_field(guest)}:
        body |= _traits_of(guest, name, fields.get(name))
    # Either genre's rule counts: the host may never pair the two words itself
    # (a drowned church is ``aqueous`` in a genre with no fire creature).
    conflicts = set(host.trait_conflicts) | set(guest.trait_conflicts)
    # Either way round: a pair's order is the rule's direction inside one genre,
    # not a statement about which side is the place (#1275).
    return _conflicting(place, body, conflicts)


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
    if host is not guest and not by_type_only and habitat_score(
        guest, host, fields, environment
    ) < 1.0:
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
    place = _traits_of(host, ENVIRONMENT_FIELD, environment)
    conflicts = set(host.trait_conflicts) | set(guest.trait_conflicts)
    for name in guest.entity_fields:
        value = fields.get(name)
        if value is None or name in chosen or name in identity:
            continue
        if _needs_met(
            resolved_needs(guest, name, value), host, environment, unknown_ok=False
        ) and not _conflicting(place, _traits_of(guest, name, value), conflicts):
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
