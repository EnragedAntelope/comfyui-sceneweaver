"""The prose renderer: a ``ResolvedScene`` in, one prompt string out.

Pure. No RNG, no pack mutation, no ComfyUI. Given the same scene and the same
pack this returns the same string, which is half of the "same seed reproduces
the same prompt" guarantee (the other half is the resolver).

**Nothing about a genre is decided here.** The renderer knows four moves:

1. build the phrase map from the head phrase and the surviving fields --
   folding composed companions into their host (hard ones from
   ``FieldSpec.renders_with``, a count or a glow colour; soft ones from
   ``pack.prose.adjective_of``, a hull colour onto its material);
2. build the subject, the head phrase articled;
3. fill the genre's sentence patterns: a pattern is spoken only when every
   slot outside a bracketed segment resolves, and a field spoken once is
   consumed;
4. drop whatever did not resolve.

The connector, the verb and the possessive are **genre data**, written by the
genre next to the noun they agree with. A clause list can only ever attach a
detail with a comma, which is why every field used to arrive in the same
grammatical relationship to the subject whatever its real one was. If you find
yourself wanting to join two clauses here, the pattern is the place.

**Two rules that are not stylistic.** Nothing is negated -- a field with no
value produces no clause at all, never a clause about its absence. And nothing
about *rendering* is emitted: an emitter's colour is voiced as a plain adjective
on the emitter ("six cyan ion thrusters"), never as a light it casts.
"""
from __future__ import annotations

import re
from typing import Mapping

try:
    from ..data.genre import (
        CONTEXT_FIELD,
        ENVIRONMENT_FIELD,
        GRAMMAR_SLOTS,
        POOL_DEFAULT_KEY,
        RELATION_FIELD,
        RELATION_POSITION_FIELD,
        SITUATION_FIELD,
        Archetype,
        GenrePack,
        HeadPhrase,
        ListSlot,
        Literal,
        Slot,
        affordances_of,
        archetype_for,
        spoken_value,
    )
except ImportError:  # pragma: no cover -- standalone/test context
    from data.genre import (
        CONTEXT_FIELD,
        ENVIRONMENT_FIELD,
        GRAMMAR_SLOTS,
        POOL_DEFAULT_KEY,
        RELATION_FIELD,
        RELATION_POSITION_FIELD,
        SITUATION_FIELD,
        Archetype,
        GenrePack,
        HeadPhrase,
        ListSlot,
        Literal,
        Slot,
        affordances_of,
        archetype_for,
        spoken_value,
    )

from .grammar import article_for, count_phrase, head_is_plural, with_article_if_singular
from .resolution import ResolvedEntity, ResolvedRelation, ResolvedScene

__all__ = ["DEFAULT_TEMPLATE", "compose_scene", "entity_reference", "render_entity", "render_prose"]

#: What a field with no authored template renders as. A bare value keeps a
#: minimal pack -- a fixture, a genre in progress -- renderable with no prose
#: authoring at all.
DEFAULT_TEMPLATE = "{value}"

#: Section keys ``pack.prose.scene_order`` may name.
_ENTITIES_SECTION = "entities"
_RELATIONS_SECTION = "relations"


# ---------------------------------------------------------------------------
# Template formatting
# ---------------------------------------------------------------------------


def _format(template: str, value: str, **extra: str) -> str:
    """Fill one template. ``ProseSpec`` has already vetted the placeholders."""
    return template.format(
        value=value,
        a_value=with_article_if_singular(value),
        a=article_for(value),
        **extra,
    ).strip()


def _template(pack: GenrePack, name: str, archetype: "Archetype | None" = None) -> str:
    """One field's clause wording.

    Archetype first, then the pack. This lookup is the whole reason ``Archetype``
    exists: with a single pack-wide table, ``"material": "clad in {value}"``
    applied to a nebula as readily as to a warship, and there was no place in
    the contract to say otherwise.
    """
    if archetype is not None and name in archetype.templates:
        return archetype.templates[name]
    return pack.prose.templates.get(name, DEFAULT_TEMPLATE)


# ---------------------------------------------------------------------------
# Entity composition
# ---------------------------------------------------------------------------




def _head_phrase_spec(
    pack: GenrePack, kind: str | None, archetype: "Archetype | None" = None
) -> HeadPhrase | None:
    """The opening noun phrase: the archetype's, else the pack's for this kind.

    The archetype is consulted first because it is the more specific statement
    -- a phenomenon leads with what it *is* whatever kind bucket it sits in.
    """
    if archetype is not None and archetype.head_phrase is not None:
        return archetype.head_phrase
    if kind is not None and kind in pack.prose.head_phrase:
        return pack.prose.head_phrase[kind]
    return pack.prose.head_phrase.get(POOL_DEFAULT_KEY)


def _sentence_plan(pack: GenrePack, archetype: "Archetype | None") -> tuple:
    """The sentence plan: the archetype's, else the pack's."""
    if archetype is not None and archetype.sentences:
        return archetype.sentences
    return pack.prose.entity_sentences




def _companions(pack: GenrePack) -> Mapping[str, tuple[str, ...]]:
    """``{host_field: (companion, ...)}`` from ``FieldSpec.renders_with``.

    In pack field order, so an emitter's count precedes its colour without the
    renderer holding an opinion about either.
    """
    hosts: dict[str, list[str]] = {}
    for name, spec in pack.entity_fields.items():
        if spec.renders_with is not None:
            hosts.setdefault(spec.renders_with, []).append(name)
    return {host: tuple(names) for host, names in hosts.items()}


def _compose_host(
    pack: GenrePack,
    entity: ResolvedEntity,
    name: str,
    adjectives: "list[str]",
) -> str:
    """The text of one clause-heading field, with everything folded into it.

    A count partner becomes the phrase's quantity and drives its plural; every
    other companion, plus any soft adjective anchored here, becomes an adjective
    in front of the noun. The head noun stays last either way, which is what
    lets ``count_phrase`` inflect it.
    """
    raw = entity.get(name)
    if raw is None:
        return ""
    value = spoken_value(pack, name, raw)
    spec = pack.entity_fields[name]
    extra = list(adjectives)
    count_token: str | None = None
    for companion in _companions(pack).get(name, ()):
        companion_raw = entity.get(companion)
        if companion_raw is None:
            continue
        companion_value = spoken_value(pack, companion, companion_raw)
        if companion == spec.count_partner:
            count_token = companion_value
        else:
            extra.append(companion_value)
    if spec.count_partner is not None:
        return count_phrase(count_token, value, " ".join(extra))
    return " ".join([*extra, value]) if extra else value


def entity_reference(entity: ResolvedEntity, pack: GenrePack) -> str:
    """How a relation names this entity: "the heavy freighter".

    Uses the head-phrase noun chain, so an entity is referred to by the same
    word it was introduced with. Falls back through the chain and finally to the
    entity's kind, so a slot always has a name to be related by.
    """
    head = _head_phrase_spec(pack, entity.kind, archetype_for(pack, entity.fields))
    candidates = head.noun if head is not None else ()
    if head is not None and head.subject is not None:
        # Named by what it was introduced as: a creature enters the scene as its
        # body plan, so that is what a relation must call it.
        candidates = (head.subject, *candidates)
    for name in (*candidates, "kind"):
        value = entity.get(name)
        if value:
            return f"the {spoken_value(pack, name, value)}"
    return f"the {pack.display.lower()} subject"


def _entity_sentence(
    subject: str,
    descriptors: "list[str]",
    situation: str | None,
    pack: GenrePack,
) -> str:
    """One entity as a single sentence body -- lower-case, no trailing period.

    The shape a pack gets when it declares no ``entity_sentences``: subject,
    every surviving clause behind one ``descriptor_lead``, then the situation.
    Kept because it is what makes a pack with no prose authoring at all
    renderable -- the genre-seam fixture depends on it -- and because a genre
    may legitimately want it. A shipped genre should not: five clauses in this
    shape put thirty tokens between the subject and its verb, which is what
    ``entity_sentences`` exists to cut up.
    """
    parts: list[str] = [subject] if subject else []
    if descriptors:
        if subject:
            parts.append(f"{pack.prose.descriptor_lead} {', '.join(descriptors)}")
        else:
            parts.append(", ".join(descriptors))
    if situation:
        copula = pack.prose.copula_plural if head_is_plural(subject) else pack.prose.copula
        parts.append(f"{copula} {situation}")
    return " ".join(p for p in parts if p)


def _grammar(
    pack: GenrePack, archetype: "Archetype | None", subject: str
) -> dict[str, str]:
    """The grammar-slot values for one entity, agreeing with its subject.

    ``{pronoun}``, ``{possessive}`` and ``{pronoun_copula}`` describe how the
    entity is spoken, not what it is, so they are never consumed. They come
    from the archetype when it declares one and the pack otherwise; the plural
    form is chosen by the subject's number, and ``{pronoun_copula}`` follows
    the *pronoun* rather than the subject -- a person is "they are" whether
    the head noun reads singular or plural.
    """
    plural = head_is_plural(subject)
    singular_pronoun = (archetype.pronoun if archetype else "") or pack.prose.pronoun
    plural_pronoun = (
        archetype.pronoun_plural if archetype else ""
    ) or pack.prose.pronoun_plural
    singular_possessive = (
        archetype.possessive if archetype else ""
    ) or pack.prose.possessive
    plural_possessive = (
        archetype.possessive_plural if archetype else ""
    ) or pack.prose.possessive_plural
    singular_object = (
        archetype.pronoun_object if archetype else ""
    ) or pack.prose.pronoun_object
    plural_object = (
        archetype.pronoun_object_plural if archetype else ""
    ) or pack.prose.pronoun_object_plural
    declared_copula = (archetype.pronoun_copula if archetype else "") or ""
    grammar = {
        "pronoun": plural_pronoun if plural else singular_pronoun,
        "pronoun_object": plural_object if plural else singular_object,
        "possessive": plural_possessive if plural else singular_possessive,
        "copula": pack.prose.copula_plural if plural else pack.prose.copula,
        "pronoun_copula": declared_copula
        or (pack.prose.copula_plural if plural else pack.prose.pronoun_copula),
    }
    if subject:
        grammar["subject"] = subject
    return grammar


def _slot_text(
    name: str,
    available: Mapping[str, str],
    grammar: Mapping[str, str],
    consumed: "set[str] | frozenset[str]",
) -> "str | None":
    """One slot's text, or ``None`` when the field has nothing to say."""
    if name in GRAMMAR_SLOTS:
        if name == "subject" and name in consumed:
            return None
        return grammar.get(name)
    return available.get(name)


def _join_list(members: "list[str]") -> str:
    """English list: ", "-joined with " and " before the last member."""
    if len(members) == 1:
        return members[0]
    return ", ".join(members[:-1]) + " and " + members[-1]


_REUSABLE_GRAMMAR = frozenset(
    {"pronoun", "pronoun_object", "possessive", "copula", "pronoun_copula"}
)


_DOUBLED_SPACE_RE = re.compile(r" {2,}")
_SPACE_BEFORE_PUNCT_RE = re.compile(r" +([.,])")
#: An apposition now closes with a comma of its own, so a pattern that ends the
#: sentence on the subject leaves ``,.`` and one that follows it with an authored
#: ``[, ...]`` segment leaves ``,,``. Both are the head phrase's comma meeting the
#: pattern's own punctuation; closing them here spares every pattern author from
#: having to know the apposition appends a comma at all.
_COMMA_BEFORE_STOP_RE = re.compile(r",\s*\.")
_DOUBLED_COMMA_RE = re.compile(r",\s*,")


def _tidy(text: str) -> str:
    """Close the gaps an optional segment -- or an apposition -- leaves behind.

    A pattern with an optional in the middle can otherwise assemble a double
    space or a space before its full stop -- the same hole, once, for every
    author who forgets it.

    It also closes the punctuation an **apposition** leaves. The head phrase
    voices the category noun as an apposition and closes it with a comma,
    because an English apposition is set off on both sides; a pattern that then
    ends the sentence on the subject would render a comma before its full stop,
    and one that follows the subject with an authored ``[, ...]`` segment would
    render a doubled comma. Both are fixed here rather than in every pattern,
    for the same reason the space rules are: it is one hole, once, for the pack.
    """
    text = _DOUBLED_SPACE_RE.sub(" ", text)
    text = _SPACE_BEFORE_PUNCT_RE.sub(r"\1", text)
    text = _COMMA_BEFORE_STOP_RE.sub(".", text)
    text = _DOUBLED_COMMA_RE.sub(",", text)
    return _DOUBLED_SPACE_RE.sub(" ", text).strip()


def _render_segments(
    segments,
    available: Mapping[str, str],
    grammar: Mapping[str, str],
    consumed: "set[str] | frozenset[str]",
) -> "tuple[str, tuple[str, ...]] | None":
    """Render one pattern's segments, or ``None`` when it cannot fire.

    Returns the text and the field names it actually spoke. A list slot speaks
    only the members that resolved; an optional segment that stands down speaks
    nothing. Both matter, because consumption is derived from what was said and
    not from what the pattern mentions.
    """
    parts: list[str] = []
    spoken: list[str] = []
    for segment in segments:
        if isinstance(segment, Literal):
            parts.append(segment.text)
        elif isinstance(segment, Slot):
            text = _slot_text(segment.name, available, grammar, consumed)
            if text is None:
                return None
            parts.append(text)
            if segment.name not in _REUSABLE_GRAMMAR:
                spoken.append(segment.name)
        elif isinstance(segment, ListSlot):
            members = [
                (name, _slot_text(name, available, grammar, consumed))
                for name in segment.names
            ]
            resolved = [(name, text) for name, text in members if text is not None]
            if not resolved:
                return None
            parts.append(_join_list([text for _, text in resolved]))
            spoken.extend(name for name, _ in resolved)
        else:  # Optional
            inner = _render_segments(segment.segments, available, grammar, consumed)
            if inner is not None:
                text, inner_spoken = inner
                parts.append(text)
                spoken.extend(inner_spoken)
    return "".join(parts), tuple(spoken)


def _render_patterns(
    subject: str,
    clauses: "Mapping[str, str]",
    situation: str | None,
    pack: GenrePack,
    archetype: "Archetype | None",
) -> "list[str]":
    """One entity as its genre-authored sentences.

    The whole control flow is two rules: a pattern is spoken only when every
    slot outside a bracketed segment resolves, and a field spoken once is
    consumed -- so the first pattern that can fire wins and the rest stand
    down, which is what a fallback ladder is.
    """
    available = dict(clauses)
    if situation is not None:
        available[SITUATION_FIELD] = situation
    grammar = _grammar(pack, archetype, subject)
    consumed: set[str] = set()
    sentences: list[str] = []
    for pattern in _sentence_plan(pack, archetype):
        live = {name: text for name, text in available.items() if name not in consumed}
        rendered = _render_segments(pattern._segments, live, grammar, consumed)
        if rendered is None:
            continue
        body = _tidy(rendered[0])
        if not body:
            continue
        sentences.append(_sentence(body))
        consumed.update(rendered[1])
    return sentences


def _entity_parts(
    entity: ResolvedEntity, pack: GenrePack
) -> "tuple[str, dict[str, str], str | None]":
    """One entity as ``(subject, clauses, situation)``.

    The subject is the head phrase; ``clauses`` maps each surviving
    clause-heading field to its formatted text, in the pack's clause order; the
    situation is the predicate. A *mapping* rather than a list because a
    sentence pattern claims fields by name -- the pack's clause order is only
    the fallback ordering, and the per-sentence order is what a shipped genre
    actually declares.

    Empty subject + no clauses + no situation means the entity has nothing to
    say, which callers drop.
    """
    archetype = archetype_for(pack, entity.fields)
    order = pack.prose.entity_clause_order
    head = _head_phrase_spec(pack, entity.kind, archetype)

    # 1. Soft adjectives: fold each onto the first anchor that has a value.
    attached: dict[str, list[str]] = {}
    consumed: set[str] = set()
    for name, anchors in pack.prose.adjective_of.items():
        value = entity.get(name)
        if value is None:
            continue
        for anchor in anchors:
            if entity.get(anchor) is not None:
                attached.setdefault(anchor, []).append(spoken_value(pack, name, value))
                consumed.add(name)
                break

    # 2. Hard companions never head a clause of their own.
    for companions in _companions(pack).values():
        consumed.update(companions)

    # 3. The head phrase (subject).
    head_text = ""
    if head is not None:
        subject = head.subject if head.subject and entity.get(head.subject) else None
        winner = next((n for n in head.noun if entity.get(n) is not None), None)
        noun_field = subject or winner
        if subject is not None:
            consumed.add(subject)
            consumed.update(n for n in head.noun if n != winner)
            consumed.update(head.modifiers)
            modifier_fields: tuple[str, ...] = head.modifiers
        else:
            consumed.update(head.noun)
            consumed.update(head.modifiers)
            modifier_fields = head.modifiers
        if noun_field is not None:
            words = [
                spoken_value(pack, f, m)
                for f in modifier_fields
                if (m := entity.get(f))
            ]
            words.extend(attached.get(noun_field, ()))
            words.append(_compose_host(pack, entity, noun_field, []))
            phrase = " ".join(w for w in words if w)
            head_text = with_article_if_singular(phrase)
            # The apposition names the category the specific head noun already
            # suppressed. Silent when it *is* the head noun, so an entity whose
            # subkind was never drawn does not read "a starship, a starship".
            # It is set off on both sides, so it carries a trailing comma;
            # ``_tidy`` closes that against whatever punctuation follows.
            if head.apposition is not None and head.apposition != noun_field:
                category = entity.get(head.apposition)
                if category:
                    consumed.add(head.apposition)
                    head_text = (
                        f"{head_text}, "
                        f"{with_article_if_singular(spoken_value(pack, head.apposition, category))},"
                    )

    # 4. Everything else, in the pack's declared order.
    clauses: dict[str, str] = {}
    for name in order:
        if name in consumed or entity.get(name) is None:
            continue
        text = _compose_host(pack, entity, name, attached.get(name, []))
        if text:
            clauses[name] = _format(_template(pack, name, archetype), text)

    situation = (
        _format(
            _template(pack, SITUATION_FIELD, archetype),
            spoken_value(pack, SITUATION_FIELD, entity.situation),
        )
        if entity.situation
        else None
    )
    return head_text, clauses, situation


def _render_entity_sentences(entity: ResolvedEntity, pack: GenrePack) -> "list[str]":
    """Every sentence one entity contributes, capitalized and closed.

    The sentence plan is used when the pack declares one **and** the entity
    actually has a subject to hang pronouns off. Without a subject a plan whose
    later leads say "It carries" would be talking about nothing, so such an
    entity falls back to the single-sentence shape -- which is exactly the case
    a minimal pack, or a slot whose head noun was cut, is in.
    """
    archetype = archetype_for(pack, entity.fields)
    subject, clauses, situation = _entity_parts(entity, pack)
    if not subject and not clauses and not situation:
        return []
    if _sentence_plan(pack, archetype) and subject:
        return _render_patterns(subject, clauses, situation, pack, archetype)
    body = _entity_sentence(subject, list(clauses.values()), situation, pack)
    return [_sentence(body)] if body else []


def render_entity(entity: ResolvedEntity, pack: GenrePack) -> str:
    """One entity as its own sentences, already capitalized and closed.

    Returns "" for an entity with nothing to say, which the caller drops rather
    than emitting an empty sentence.
    """
    return " ".join(_render_entity_sentences(entity, pack))


# ---------------------------------------------------------------------------
# Scene composition
# ---------------------------------------------------------------------------


def _sentence(text: str) -> str:
    """Capitalize a fragment and close it. Entity clauses arrive lower-case.

    ``_tidy`` runs on the *closed* sentence as well as in the pattern path, so
    the clause fallback (a pack with no ``entity_sentences``) also absorbs an
    apposition's trailing comma - which only exists once the stop is appended
    (``a wreck,`` + ``.`` is ``a wreck,.``). It is idempotent, so the already
    tidied pattern path is unaffected.
    """
    if not text:
        return ""
    body = text[0].upper() + text[1:]
    return _tidy(body if body.endswith(".") else f"{body}.")


def _environment_sentence(pack: GenrePack, environment: str) -> str:
    """The setting sentence, staged with the first affordance suffix that applies.

    A text-to-image model grounds anything it is not told floats: a station in a
    debris belt is drawn standing on the debris. So a place that affords open
    space says so -- \"Set in an orbital debris belt, out in open space.\"
    """
    template = pack.prose.environment_sentence or _template(pack, ENVIRONMENT_FIELD)
    text = _format(template, spoken_value(pack, ENVIRONMENT_FIELD, environment))
    afforded = affordances_of(pack, environment)
    for affordance, suffix in pack.prose.environment_staging:
        if affordance in afforded:
            text += suffix
            break
    return _sentence(text)


def _references(scene: ResolvedScene, pack: GenrePack) -> Mapping[int, str]:
    """A distinct reference per entity.

    Two freighters in one scene would otherwise both be "the heavy freighter"
    and every relation between them would read as a thing relating to itself.
    Numbered only where a collision actually happens, so the common case stays
    plain.
    """
    base = {e.index: entity_reference(e, pack) for e in scene.entities}
    counts: dict[str, int] = {}
    for reference in base.values():
        counts[reference] = counts.get(reference, 0) + 1
    ordinals = ("first", "second", "third", "fourth", "fifth")
    seen: dict[str, int] = {}
    resolved: dict[int, str] = {}
    for index, reference in base.items():
        if counts[reference] == 1:
            resolved[index] = reference
            continue
        position = seen.get(reference, 0)
        seen[reference] = position + 1
        ordinal = ordinals[position] if position < len(ordinals) else str(position + 1)
        resolved[index] = reference.replace("the ", f"the {ordinal} ", 1)
    return resolved


def _relation_sentence(
    relation: ResolvedRelation, references: Mapping[int, str], pack: GenrePack
) -> str:
    """One relation as a lower-case sentence body, no trailing period.

    "{first} is {action} {second}" through the relation template, plus the
    pack's ``relation_position_template`` when the relation carries a position
    ("... the heavy freighter, from behind").
    """
    first, second = relation.endpoints
    text = _format(
        _template(pack, RELATION_FIELD),
        spoken_value(pack, RELATION_FIELD, relation.value),
        first=references[first],
        second=references[second],
    )
    if relation.position and pack.prose.relation_position_template:
        text += _format(
            pack.prose.relation_position_template,
            spoken_value(pack, RELATION_POSITION_FIELD, relation.position),
        )
    return text


def _context_sentence(scene: ResolvedScene, pack: GenrePack) -> str:
    """The scene's context as its own sentence, or "" for none.

    Drawn once per scene and spoken after the entities: what else is in the
    shot, never a second described subject. The patterns are pack data and one
    is chosen at random per scene -- the index was drawn where the RNG lives
    (``engine.scene``), because this module is pure. The subject's object
    pronoun lets a person be "them" and a ship "it".
    """
    patterns = pack.prose.context_sentences
    if not scene.entities or not scene.context or not patterns:
        return ""
    index = scene.context_sentence_index
    pattern = patterns[(index if index is not None else 0) % len(patterns)]
    subject, _clauses, _situation = _entity_parts(scene.entities[0], pack)
    grammar = _grammar(pack, archetype_for(pack, scene.entities[0].fields), subject)
    spoken = spoken_value(pack, CONTEXT_FIELD, scene.context)
    available = {
        CONTEXT_FIELD: spoken,
        f"a_{CONTEXT_FIELD}": with_article_if_singular(spoken),
    }
    rendered = _render_segments(pattern._segments, available, grammar, frozenset())
    if rendered is None:
        return ""
    body = _tidy(rendered[0])
    return _sentence(body) if body else ""


def compose_scene(
    scene: ResolvedScene,
    pack: GenrePack,
    references: Mapping[int, str],
) -> list[str]:
    """Assemble a scene as connected prose: a list of sentence strings.

    Each move is driven by pack data:

    1. the environment opens the scene as its own setting sentence through
       ``pack.prose.environment_sentence`` ("Set in an asteroid field.");
    2. each entity is a subject + conjugated predicate;
    3. each relation is a standalone sentence naming both endpoints
       ("the scout ship is attacking the heavy freighter") plus its spatial
       position when present (", from behind").

    A relation to an empty slot is dropped, not half-voiced.
    """
    sentences: list[str] = []
    for entity in scene.entities:
        sentences.extend(_render_entity_sentences(entity, pack))
    context = _context_sentence(scene, pack)
    if context:
        sentences.append(context)

    if scene.environment:
        sentences.insert(0, _environment_sentence(pack, scene.environment))
    elif pack.prose.scene_frame and sentences:
        # No environment to carry the genre, so it is stated on its own. A
        # prompt that never names its genre gets drawn as whatever its nouns
        # most commonly mean, which is rarely the world the pack is about.
        #
        # ``and sentences`` because an empty scene must stay empty. A user who
        # set every field to None asked for nothing, and answering that with a
        # bare genre label is a prompt they did not write.
        sentences.insert(0, _sentence(pack.prose.scene_frame))

    for relation in scene.relations:
        first, second = relation.endpoints
        if first not in references or second not in references:
            continue
        sentences.append(_sentence(_relation_sentence(relation, references, pack)))
    return sentences


def render_prose(scene: ResolvedScene, pack: GenrePack) -> str:
    """Render a whole scene.

    The budget has already written every cut field back to ``None`` by the
    time a scene reaches here (see ``engine.budget``), so taking a budget here
    would give two places that decide whether a field is voiced -- and one of
    them would eventually be wrong. What is in the scene is what is spoken.

    A pack with ``prose.narrative_mode`` is composed into connected prose via
    ``compose_scene``; anything else keeps one sentence per section.
    """
    references = _references(scene, pack)
    if pack.prose.narrative_mode:
        return " ".join(s for s in compose_scene(scene, pack, references) if s)

    sections: list[str] = []

    for section in pack.prose.scene_order:
        if section == ENVIRONMENT_FIELD:
            if scene.environment:
                sections.append(_environment_sentence(pack, scene.environment))
        elif section == _ENTITIES_SECTION:
            for entity in scene.entities:
                sections.extend(_render_entity_sentences(entity, pack))
            context = _context_sentence(scene, pack)
            if context:
                sections.append(context)
        elif section == _RELATIONS_SECTION:
            for relation in scene.relations:
                first, second = relation.endpoints
                if first not in references or second not in references:
                    # Both endpoints must be occupied. Resolution drops a
                    # half-relation before it gets here; this is the belt to
                    # that braces, and it omits rather than inventing a subject.
                    continue
                sections.append(_sentence(_relation_sentence(relation, references, pack)))

    return " ".join(s for s in sections if s)
