"""Todo 21 -- the data validator. Run it directly:

.. code-block:: console

    python tests/validate_data.py

Exits 0 when the shipped pack is sound and 1 with a named finding when it is
not. It is the check an authoring session runs after touching a pool, and it is
a CI step, because a data defect is invisible in a diff: adding "no weapons" to
a pool looks exactly like adding "spinal railgun".

**It also reports the live numbers.** No document in this repo states how many
values a pool holds (``readme-count-claims-assert-truth-not-tightness``): a
count in prose turns every content addition into a doc chore and goes stale
silently, so the README names this command instead and the command answers.

What it checks, in the order the plan lists them:

1. tag coverage -- exactly one content tag on every value of every tag-scoped
   field, and nothing else tagged;
2. constraint resolution -- every rule's addresses and values are real;
3. per-kind pool coverage -- an override, a documented ``_default``
   fall-through, or a declared deliberate omission; never a silent hole;
4. no leading articles (the count vocabulary excepted, by construction);
5. count-partner pluralization, over the whole corpus and every count token;
6. no readable text in ``markings``;
7. every kind clears the situation floor, and its event floor;
8. the two denylists and the never-negate rule over every value;
9. no two clause-heading fields of one kind offer the identical value;
10. no situation names its own invisibility (the mechanical half of the three-
    test situation rule; see the comment above ``SITUATION_POOLS``).

Nine is not in the plan's list and is here because a sweep found it: pools
overlap by design, so two fields could hand one entity the same string twice and
produce "an oxide red hull, oxide red accents". ``engine.scene`` drops the
repeat at run time, but data that needs the runtime guard to look right has
already lost the variety it was authored for, so it is a finding here too.

**This module imports the pack; it never imports the pack through the
entrypoint.** ``data.scifi`` is the built-ins and only the built-ins -- the
``user_options.json`` merge happens in the repo-root ``__init__.py``, after the
import. See ``data/user_options.py``.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from data import genre as G  # noqa: E402
from data.scifi import SCIFI_PACK  # noqa: E402
from engine.grammar import (  # noqa: E402
    count_phrase,
    head_is_plural,
    head_noun,
    pluralize,
    with_article,
)
from tests.boundary import (  # noqa: E402
    leading_article,
    negation_findings,
    readable_text_findings,
    rendering_findings,
)

#: The plan's floor for the action layer. Below it a kind's situations start
#: visibly repeating across a handful of seeds.
MIN_SITUATIONS_PER_KIND = 12

#: Words that are singular despite ending in "s". Without this the plural check
#: reads "chassis" as a plural noun and asks an author to fix a correct value.
SINGULAR_S = frozenset({
    "bass", "gas", "glass", "truss", "mass", "cross", "press", "chassis",
    "apparatus", "harness", "brass", "canvas", "lattice",
})


@dataclass
class Report:
    """What one validation run found.

    ``failures`` is the exit code; ``notes`` and ``numbers`` are the report a
    doc would otherwise have had to state and go stale.
    """

    failures: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    numbers: dict[str, int] = field(default_factory=dict)

    def fail(self, code: str, message: str) -> None:
        self.failures.append(f"{code:<10} {message}")

    @property
    def ok(self) -> bool:
        return not self.failures


def _clause_heads(pack: G.GenrePack) -> tuple[str, ...]:
    return tuple(n for n, s in pack.entity_fields.items() if s.renders_with is None)


def _count_fields(pack: G.GenrePack) -> tuple[str, ...]:
    return tuple(
        n
        for n, s in pack.entity_fields.items()
        if s.renders_with is not None and s.count_partner is not None
    )


# ---------------------------------------------------------------------------
# The checks
# ---------------------------------------------------------------------------


def check_tags(pack: G.GenrePack, report: Report) -> None:
    """1. Exactly one tag on every value of a tag-scoped field, and no other."""
    tag_scoped = {
        name
        for name, spec in (dict(pack.entity_fields) | dict(pack.scene_fields)).items()
        if spec.tag_scoped
    }
    tagged = set(pack.tags)
    for extra in sorted(tagged - tag_scoped):
        report.fail(
            "TAG",
            f"{extra!r} carries content tags but is not declared tag_scoped, so the "
            "filter never reads them",
        )
    for missing in sorted(tag_scoped - tagged):
        report.fail("TAG", f"{missing!r} is tag_scoped but carries no tag map")

    for name in sorted(tag_scoped & tagged):
        values = set()
        for group in (pack.pools.get(name) or {}).values():
            values.update(group)
        table = pack.tags[name]
        for value in sorted(values - set(table)):
            report.fail("TAG", f"{name}: {value!r} carries no tag")
        for value in sorted(set(table) - values):
            report.fail("TAG", f"{name}: {value!r} is tagged but is not in the pool")
        for value, tag in sorted(table.items()):
            if tag not in G.CONTENT_TAGS:
                report.fail("TAG", f"{name}: {value!r} carries unknown tag {tag!r}")
    report.numbers["tag_scoped_fields"] = len(tag_scoped)


def check_constraints(pack: G.GenrePack, report: Report) -> None:
    """2. Every rule addresses a real field of a real slot, at a real value."""
    space = G.constraint_address_space(pack, G.SCENE_NODE_SLOTS)
    for index, rule in enumerate(pack.all_constraints):
        triggers = rule.triggers
        shown = triggers[0] if len(triggers) == 1 else f"{len(triggers)} values"
        where = f"rule {index} ({rule.field}={shown!r})"
        for address in (rule.field, rule.excludes_field, rule.requires_field):
            if address is None:
                continue
            bound = G.bind_address(address, G.LONE_ENTITY_SLOT, (1, 2))
            if bound not in space:
                report.fail("RULE", f"{where}: {address!r} is not an address this pack has")
        trigger_base = G.address_field(rule.field)
        options = G.pool_options(pack, trigger_base)
        for trigger in triggers:
            if trigger not in options:
                report.fail(
                    "RULE", f"{where}: {trigger!r} is not an option of {trigger_base!r}"
                )
        target = G.address_field(rule.excludes_field or rule.requires_field or "")
        wanted = (
            rule.excludes_values
            or rule.requires_values
            or ((rule.requires_value,) if rule.requires_value else ())
        )
        options = set(G.pool_options(pack, target))
        for value in wanted:
            if value not in options:
                report.fail("RULE", f"{where}: {value!r} is not an option of {target!r}")
        if not rule.reason:
            report.fail("RULE", f"{where}: carries no reason, so its warning would say nothing")
    report.numbers["constraint_rules"] = len(pack.all_constraints)


def check_pool_coverage(pack: G.GenrePack, report: Report) -> None:
    """3. Every kind resolves every kind-scoped field, by a declared route."""
    kind_scoped = [
        name
        for name, spec in (dict(pack.entity_fields) | dict(pack.scene_fields)).items()
        if spec.kind_scoped
    ]
    declared_empty = set(pack.omitted_pools)
    seen_empty: set[tuple[str, str]] = set()
    for kind in pack.kinds:
        for name in kind_scoped:
            by_kind = pack.pools.get(name) or {}
            if kind in by_kind:
                route = "override"
                values = by_kind[kind]
            elif G.POOL_DEFAULT_KEY in by_kind:
                route = "_default fall-through"
                values = by_kind[G.POOL_DEFAULT_KEY]
            else:
                report.fail(
                    "COVERAGE",
                    f"{name}[{kind}]: no override and no {G.POOL_DEFAULT_KEY!r}; this kind "
                    "would resolve to nothing for no recorded reason",
                )
                continue
            if not values:
                seen_empty.add((name, kind))
                if (name, kind) not in declared_empty:
                    report.fail(
                        "COVERAGE",
                        f"{name}[{kind}]: empty pool that pack.omitted_pools does not declare",
                    )
                route = "declared omission"
            report.notes.append(f"  {kind:<22} {name:<16} {route:<22} {len(values):>3} values")
    # A subkind-group pool may be empty on purpose too (a black hole has no
    # hull colour); the same declaration covers it.
    for name in kind_scoped:
        for key, values in (pack.pools.get(name) or {}).items():
            if not values:
                seen_empty.add((name, key))
    for stale in sorted(declared_empty - seen_empty):
        report.fail(
            "COVERAGE",
            f"pack.omitted_pools declares {stale} empty, but it is not; delete the declaration",
        )
    report.numbers["kind_scoped_fields"] = len(kind_scoped)


def check_values(pack: G.GenrePack, report: Report) -> None:
    """4, 6, 8. Articles, readable text, the denylists and never-negate."""
    counts = set(_count_fields(pack))
    total = 0
    for name, by_kind in pack.pools.items():
        for kind, values in by_kind.items():
            for value in values:
                total += 1
                where = f"{name}[{kind}]"
                for finding in rendering_findings(value):
                    report.fail("RENDERING", f"{where}: {value!r} contains {finding}")
                for finding in negation_findings(value):
                    report.fail("NEGATION", f"{where}: {value!r} contains {finding}")
                if name not in counts and leading_article(value):
                    report.fail("ARTICLE", f"{where}: {value!r} opens with an article")
                if name in counts and re.search(r"\d", value):
                    report.fail(
                        "DIGIT",
                        f"{where}: {value!r} is a numeral; a digit gets drawn as a caption, "
                        "not as a quantity",
                    )
                if name == "markings":
                    for finding in readable_text_findings(value):
                        report.fail("TEXT", f"{where}: {value!r} names {finding}")
    report.numbers["pool_values"] = total
    report.numbers["pool_fields"] = len(pack.pools)


def check_plurals(pack: G.GenrePack, report: Report) -> None:
    """5. Every count-partnered noun pluralizes over every count token.

    The whole corpus, not a sample: a value that needs a manual exception is a
    data bug, and the point of running it over everything is that the fix lands
    in the pool rather than in a lookup table nobody maintains.
    """
    tokens = G.pool_for(pack, next(iter(_count_fields(pack)), ""))
    checked = 0
    for noun_field, count_field in pack.counts.items():
        for by_kind in ((pack.pools.get(noun_field) or {}),):
            for kind, values in by_kind.items():
                for value in values:
                    where = f"{noun_field}[{kind}]"
                    head = head_noun(value)
                    if head.lower().endswith("s") and head.lower() not in SINGULAR_S:
                        report.fail(
                            "PLURAL",
                            f"{where}: {value!r} is authored plural; the engine pluralizes",
                        )
                    plural = pluralize(value)
                    if plural == value or not plural:
                        report.fail("PLURAL", f"{where}: {value!r} does not pluralize")
                    for token in tokens:
                        phrase = count_phrase(token, value)
                        checked += 1
                        if not phrase or "  " in phrase:
                            report.fail(
                                "PLURAL",
                                f"{where}: {token!r} x {value!r} composes to {phrase!r}",
                            )
                    articled = with_article(value)
                    if articled.split(" ", 1)[0].lower() not in ("a", "an"):
                        report.fail("ARTICLE", f"{where}: {value!r} takes no article")
        report.notes.append(f"  count pair {noun_field} / {count_field}")
    report.numbers["count_compositions"] = checked


def check_situations(pack: G.GenrePack, report: Report) -> None:
    """7. Every kind clears the action-layer floor."""
    for kind in pack.kinds:
        values = G.pool_for(pack, G.SITUATION_FIELD, kind)
        if len(values) < MIN_SITUATIONS_PER_KIND:
            report.fail(
                "SITUATION",
                f"{kind!r} has {len(values)} situations, below the floor of "
                f"{MIN_SITUATIONS_PER_KIND}; its actions will visibly repeat",
            )
        report.notes.append(f"  situations {kind:<22} {len(values):>3}")


#: Frame-meta markers that name a thing's own invisibility. Only the frame half of
#: the authoring rule is mechanical -- a regex cannot judge whether a still frame
#: can show an action -- so this rejects the one class that is unambiguous.
_FRAME_META_MARKERS: tuple[str, ...] = (
    "out of view", "off-screen", "off screen", "unseen", "the scene", "the frame",
)


def check_situation_visibility(pack: G.GenrePack, report: Report) -> None:
    """10. No situation names its own invisibility.

    The situation authoring rule is three tests -- is there something to see,
    does it need an actor the scene has not described, does it fit in one shot.
    Only the first has a mechanical half: a value that says it is "out of view"
    or "unseen" has told the reader there is nothing to see. The actor and frame
    tests are enforced by review, not by this check; do not pretend a substring
    scan can judge visibility.
    """
    for kind, values in (pack.pools.get(G.SITUATION_FIELD) or {}).items():
        for value in values:
            lowered = value.lower()
            for marker in _FRAME_META_MARKERS:
                if marker in lowered:
                    report.fail(
                        "VISIBILITY",
                        f"situation[{kind}]: {value!r} names its own invisibility "
                        f"({marker!r}); a situation must be legible in one still frame",
                    )


def check_cross_field_duplicates(pack: G.GenrePack, report: Report) -> None:
    """9. Two clause heads of one kind must not offer the identical value.

    Except where the pack declares that they share one vocabulary on purpose --
    the three colour fields are three roles over a single palette of pigment
    words, and pulling them apart would mean inventing a second word for copper.
    """
    heads = _clause_heads(pack)
    shared = pack.shared_vocabulary

    def declared_together(one: str, other: str) -> bool:
        return any({one, other} <= group for group in shared)

    for kind in pack.kinds:
        owner: dict[str, str] = {}
        for name in heads:
            for value in G.pool_for(pack, name, kind):
                held = owner.setdefault(value, name)
                if held != name and not declared_together(held, name):
                    report.fail(
                        "DUPLICATE",
                        f"{kind!r}: {value!r} is in both {held!r} and {name!r}; one entity "
                        "can draw it twice, and the engine then has to silence a clause "
                        "the pool paid for",
                    )


def check_situation_groups(pack: G.GenrePack, report: Report) -> None:
    """Every situation-pool key is a kind, a subkind, a subkind group, or the
    default. A typo would silently shadow the kind pool it was meant to override."""
    pools = pack.pools.get(G.SITUATION_FIELD) or {}
    kinds = set(pack.kinds)
    subkinds = set(G.pool_options(pack, "subkind"))
    groups = set(pack.pool_groups.get("subkind") or {})
    for key in pools:
        if key in kinds or key == G.POOL_DEFAULT_KEY or key in subkinds or key in groups:
            continue
        report.fail(
            "SITUATION_GROUP",
            f"situation pool key {key!r} is not a kind, a subkind, a subkind group, "
            f"nor {G.POOL_DEFAULT_KEY!r}",
        )


#: The plan's floor for the action layer *after* coherence filtering. Below it
#: a kind's situations start visibly repeating across a handful of seeds.
SITUATION_FLOOR = 20

#: How many of those situations must be worth looking at. A place that cannot
#: hold a dramatic action for a kind should not hold that kind.
EVENT_FLOOR = 6

#: A value that can stand before a noun: one word, a hyphenated compound, or an
#: -ly adverb plus one participle ("freshly commissioned").
_ATTRIBUTIVE_RE = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")


def _archetype_for_kind(pack: G.GenrePack, kind: str):
    """The archetype governing a kind, or ``None``."""
    name = pack.archetype_of_kind.get(kind)
    return pack.archetypes.get(name) if name else None


def _head_phrase_for_kind(pack: G.GenrePack, kind: str):
    """The head phrase a kind is spoken with: its archetype's, else the pack's."""
    archetype = _archetype_for_kind(pack, kind)
    if archetype is not None and archetype.head_phrase is not None:
        return archetype.head_phrase
    return pack.prose.head_phrase.get(kind) or pack.prose.head_phrase.get(
        G.POOL_DEFAULT_KEY
    )


def _modifier_fields(pack: G.GenrePack) -> tuple[str, ...]:
    """Fields consumed as head-phrase modifiers, read from the pack's head phrases."""
    fields: list[str] = []
    heads = list(pack.prose.head_phrase.values())
    heads += [
        archetype.head_phrase
        for archetype in pack.archetypes.values()
        if archetype.head_phrase is not None
    ]
    for head in heads:
        for name in head.modifiers:
            if name not in fields:
                fields.append(name)
    return tuple(fields)


def _is_attributive(value: str) -> bool:
    """Whether ``value`` can stand before a noun as a modifier."""
    if _ATTRIBUTIVE_RE.match(value):
        return True
    words = value.split()
    return len(words) == 2 and words[0].endswith("ly")


def _env_excludes(pack: G.GenrePack, environment: str, field: str) -> set[str]:
    """Values ``field`` may not take in ``environment``, from every derived rule."""
    target = f"entity*.{field}"
    banned: set[str] = set()
    for rule in pack.all_constraints:
        if rule.type != G.RULE_EXCLUDE or rule.field != G.ENVIRONMENT_FIELD:
            continue
        if environment not in rule.triggers or rule.excludes_field != target:
            continue
        banned |= set(rule.excludes_values)
    return banned



def check_foreign_nouns(pack: G.GenrePack, report: Report) -> None:
    """11. Nothing the prompt says names an Earth object a model draws instead of the subject.

    Scans what is *said*: a value's spoken form when it has one, and every sentence a genre
    authored -- "hospital ship" is never spoken, while "ship's engineer" always was.
    """
    if not pack.foreign_nouns:
        return
    patterns = [
        (noun, re.compile(rf"\b{re.escape(noun)}s?\b", re.IGNORECASE))
        for noun in pack.foreign_nouns
    ]
    reported: set[tuple[str, str]] = set()

    def scan(where: str, token: str, text: str) -> None:
        if token in pack.foreign_noun_allowlist or text in pack.foreign_noun_allowlist:
            return
        for noun, pattern in patterns:
            if pattern.search(text) and (where, text) not in reported:
                reported.add((where, text))
                report.fail(
                    "FOREIGN",
                    f"{where}: {text!r} names {noun!r}, which a model draws as the Earth object",
                )

    for field_name in pack.foreign_noun_fields:
        for value in G.pool_options(pack, field_name):
            scan(field_name, value, G.spoken_value(pack, field_name, value))
    sentences = [p.text for archetype in pack.archetypes.values() for p in archetype.sentences]
    sentences += [p.text for p in pack.prose.entity_sentences]
    sentences += [p.text for p in pack.prose.context_sentences]
    sentences += [pack.prose.environment_sentence, pack.prose.scene_frame]
    for text in sentences:
        if text:
            scan("prose", text, text)


def check_affordance_keywords(pack: G.GenrePack, report: Report) -> None:
    """12. A value that names a place-affordance must declare the need."""
    if not pack.affordance_keywords:
        return
    for field_name in pack.affordance_lint_fields:
        for key, values in (pack.pools.get(field_name) or {}).items():
            for value in values:
                if value in pack.affordance_allowlist:
                    continue
                declared = G.resolved_needs(pack, field_name, value)
                low = value.lower()
                for need, keywords in pack.affordance_keywords.items():
                    if need in declared:
                        continue
                    if any(
                        re.search(rf"\b{re.escape(keyword)}\b", low)
                        for keyword in keywords
                    ):
                        report.fail(
                            "AFFORDANCE",
                            f"{field_name}[{key}]: {value!r} names {need!r} but does "
                            "not declare the need, so it can be placed anywhere",
                        )


def check_affordance_coverage(pack: G.GenrePack, report: Report) -> None:
    """18. Every value of a lint field is classified.

    A value is classified when it has its own entry in ``value_needs`` (even an
    empty one) or is authored under a pool key that ``default_needs`` covers.
    An unclassified value is one the lint cannot reason about, which is how most
    situations stayed unplaced: nothing said where they could go, so they went
    everywhere.
    """
    for field_name in pack.affordance_lint_fields:
        values = G.pool_options(pack, field_name)
        unclassified = [value for value in values if not G.is_classified(pack, field_name, value)]
        classified = len(values) - len(unclassified)
        report.numbers[f"{field_name}_values"] = len(values)
        report.numbers[f"{field_name}_classified"] = classified
        report.numbers[f"{field_name}_unclassified"] = len(unclassified)
        for value in unclassified:
            report.fail(
                "UNCLASSIFIED",
                f"{field_name}: {value!r} resolves to no need and no default key covers "
                "it; declare its need or a deliberate empty entry",
            )


def check_stance_coverage(pack: G.GenrePack, report: Report) -> None:
    """19. Every value of the stance field declares how it holds itself up.

    A form with no stance escapes the stance rule and can stand on the ground or
    hang in vacuum; the vocabulary is only a gate if every shape speaks it."""
    by_value = pack.value_stances.get(G.STANCE_FIELD, {})
    if not by_value:
        return
    values = set(G.pool_options(pack, G.STANCE_FIELD))
    for value in sorted(values - set(by_value)):
        report.fail(
            "STANCE",
            f"{G.STANCE_FIELD}: {value!r} declares no stance, so it is unconstrained by "
            "the place it stands in",
        )


def check_affordance_contradictions(pack: G.GenrePack, report: Report) -> None:
    """20. No place grants two affordances that cannot co-exist.

    A place both underwater and under open sky, or both in vacuum and with
    ground underfoot, is how the water rows drifted: the surface band was
    copied and a word added rather than the sky removed."""
    contradictions = (
        ("submerged", "sky"),
        ("open-space", "ground"),
        ("air", "open-space"),
        ("air", "submerged"),
        ("cloud-deck", "ground"),
    )
    for place, affordances in pack.place_affordances.items():
        for one, other in contradictions:
            if one in affordances and other in affordances:
                report.fail(
                    "CONTRADICTION",
                    f"place_affordances[{place!r}] grants both {one!r} and {other!r}",
                )


def check_attributive_modifiers(pack: G.GenrePack, report: Report) -> None:
    """13. A head-phrase modifier must be able to stand before a noun."""
    for field_name in _modifier_fields(pack):
        for key, values in (pack.pools.get(field_name) or {}).items():
            for value in values:
                if not _is_attributive(value):
                    report.fail(
                        "ATTRIBUTIVE",
                        f"{field_name}[{key}]: {value!r} cannot stand before a noun",
                    )


def _form_needs_singular(pack: G.GenrePack, plan, archetype) -> bool:
    """Whether a plan places ``{form}`` directly after a singular copula or verb."""
    for pattern in plan:
        segments = pattern._segments
        for index, segment in enumerate(segments):
            if not (isinstance(segment, G.Slot) and segment.name == "form"):
                continue
            if index == 0:
                continue
            prev = segments[index - 1]
            if isinstance(prev, G.Literal) and prev.text.rstrip().endswith(
                (" is", " are", " has", " have")
            ):
                return True
            if isinstance(prev, G.Slot) and prev.name in ("copula", "pronoun_copula"):
                copula = (archetype.pronoun_copula if archetype else "") or "is"
                if copula == "is":
                    return True
    return False


def check_singular_forms(pack: G.GenrePack, report: Report) -> None:
    """14. A form spoken after a singular verb must have a singular head."""
    for kind in pack.kinds:
        archetype = _archetype_for_kind(pack, kind)
        plan = (archetype.sentences if archetype else ()) or pack.prose.entity_sentences
        if not plan or not _form_needs_singular(pack, plan, archetype):
            continue
        for value in G.pool_for(pack, "form", kind):
            if head_is_plural(value):
                report.fail(
                    "SINGULAR",
                    f"form[{kind}]: {value!r} is plural but is spoken after a singular "
                    "verb; make the pattern plural-safe or rename the value",
                )


def _form_excludes(pack: G.GenrePack, form: str, field_name: str) -> set[str]:
    """Values of ``field_name`` a rule triggered by ``form`` excludes, from every rule."""
    trigger = f"entity*.{G.STANCE_FIELD}"
    target = f"entity*.{field_name}"
    banned: set[str] = set()
    for rule in pack.all_constraints:
        if rule.type != G.RULE_EXCLUDE or rule.field != trigger:
            continue
        if form in rule.triggers and rule.excludes_field == target:
            banned |= set(rule.excludes_values)
    return banned


def check_band_floor(pack: G.GenrePack, report: Report) -> None:
    """15. Every type that can exist in a place keeps the situation and event floors there.

    Asked per type, not per kind: once a type group has a situation key of its own, the
    kind pool is not what that subject draws, and a type that cannot exist in a place has
    no floor to keep there. A situation counts when the place allows it and at least one
    form the type can stand up in there allows it too.
    """
    tiers = pack.value_tiers.get(G.SITUATION_FIELD, {})
    name = G.type_field(pack)
    place_cache: dict[str, set[str]] = {}
    form_cache: dict[str, set[str]] = {}
    shortfalls: dict[tuple[str, str, object, int], list[str]] = {}
    for environment in G.pool_options(pack, G.ENVIRONMENT_FIELD):
        if environment not in place_cache:
            place_cache[environment] = _env_excludes(pack, environment, G.SITUATION_FIELD)
        for kind in G.pool_for(pack, G.KIND_FIELD, {G.ENVIRONMENT_FIELD: environment}):
            types = G.feasible_types(pack, environment, kind) if name else ()
            if name and len(types) < 3:
                shortfalls.setdefault(("SUBFLOOR", kind, None, len(types)), []).append(environment)
            for value in types or (None,):
                scope = {G.KIND_FIELD: kind}
                if name and value is not None:
                    scope[name] = value
                pool = set(G.pool_for(pack, G.SITUATION_FIELD, scope)) - place_cache[environment]
                forms = [
                    form for form in G.pool_for(pack, G.STANCE_FIELD, scope)
                    if G.form_can_stand(pack, environment, form)
                ]
                for form in forms:
                    if form not in form_cache:
                        form_cache[form] = _form_excludes(pack, form, G.SITUATION_FIELD)
                if forms:
                    pool = {v for v in pool if any(v not in form_cache[f] for f in forms)}
                events = sum(1 for v in pool if tiers.get(v) == "event")
                if len(pool) < SITUATION_FLOOR:
                    shortfalls.setdefault(("FLOOR", kind, value, len(pool)), []).append(environment)
                if events < EVENT_FLOOR:
                    shortfalls.setdefault(("EVENTFLOOR", kind, value, events), []).append(environment)
    floors = {"SUBFLOOR": 3, "FLOOR": SITUATION_FLOOR, "EVENTFLOOR": EVENT_FLOOR}
    for (code, kind, value, kept), places in sorted(shortfalls.items(), key=str):
        report.fail(
            code,
            f"{kind!r}/{value!r} keeps {kept} (floor {floors[code]}) in {len(places)} "
            f"place(s), e.g. {places[:3]}",
        )


def check_kind_feasibility(pack: G.GenrePack, report: Report) -> None:
    """23. Every kind a place offers can exist there.

    A kind in a place's kind pool with no type that affords the place and stands up in
    it is drawn, then excluded by a derived rule, then re-drawn -- wasted draws that skew
    the kind distribution and hide a data lie. Remove the kind from the place, or give
    one of its types a stance the place supports.
    """
    for environment in G.pool_options(pack, G.ENVIRONMENT_FIELD):
        for kind in G.pool_for(pack, G.KIND_FIELD, {G.ENVIRONMENT_FIELD: environment}):
            if not G.kind_feasible(pack, environment, kind):
                report.fail(
                    "DEADKIND",
                    f"{environment!r} offers {kind!r}, but no type of it can exist there",
                )


def check_empty_defaults(pack: G.GenrePack, report: Report) -> None:
    """24. A key default that declares nothing classifies nothing.

    An empty ``default_needs`` entry satisfied the coverage gate for every value under
    its key while saying nothing about where those values can happen -- which is how
    two thirds of the situations stayed placeable everywhere. A value that truly needs
    nothing says so on its own ``value_needs`` entry, where a reviewer can see it.
    """
    for field_name in pack.affordance_lint_fields:
        for key, needs in (pack.default_needs.get(field_name) or {}).items():
            if not needs:
                report.fail(
                    "EMPTYDEFAULT",
                    f"default_needs[{field_name!r}][{key!r}] is empty; declare needs per value",
                )


def _subjects(pack: G.GenrePack):
    """Every ``(kind, type)`` a scene can hold; ``(kind, None)`` for a kind with no types."""
    name = G.type_field(pack)
    for kind in pack.kinds:
        values = G.pool_for(pack, name, {G.KIND_FIELD: kind}) if name else ()
        for value in values or (None,):
            yield kind, value


def _reach(pack: G.GenrePack, field_name: str) -> "dict[str, list[tuple[str, str | None]]]":
    """``{value: [(kind, type), ...]}`` -- every subject whose resolved pool holds the value."""
    name = G.type_field(pack)
    reach: dict[str, list[tuple[str, str | None]]] = {}
    for kind, value in _subjects(pack):
        scope = {G.KIND_FIELD: kind}
        if name and value is not None:
            scope[name] = value
        for option in G.pool_for(pack, field_name, scope):
            reach.setdefault(option, []).append((kind, value))
    return reach


def _named(words_by_key, text: str) -> set[str]:
    low = text.lower()
    return {
        key for key, words in words_by_key.items()
        if any(re.search(rf"\b{re.escape(word)}\b", low) for word in words)
    }


def check_stance_keywords(pack: G.GenrePack, report: Report) -> None:
    """25. A situation that says how a body moves declares that stance."""
    if not pack.stance_keywords:
        return
    declared = pack.value_stances.get(G.SITUATION_FIELD, {})
    for value in G.pool_options(pack, G.SITUATION_FIELD):
        for stance in sorted(_named(pack.stance_keywords, value)):
            if stance not in declared.get(value, frozenset()):
                report.fail(
                    "STANCEWORD", f"situation: {value!r} says {stance!r} but does not declare it"
                )


def check_body_keywords(pack: G.GenrePack, report: Report) -> None:
    """26. A value that names a body part is drawn only by bodies that have it."""
    if not pack.body_keywords:
        return
    for field_name in pack.body_lint_fields:
        for option, subjects in sorted(_reach(pack, field_name).items()):
            named = _named(pack.body_keywords, option)
            if not named:
                continue
            lacking = sorted({
                f"{value or kind} lacks {'/'.join(sorted(named - G.body_features_of(pack, kind, value)))}"
                for kind, value in subjects
                if named - G.body_features_of(pack, kind, value)
            })
            if lacking:
                report.fail(
                    "BODY",
                    f"{field_name}: {option!r} is drawn by {len(lacking)} body(ies) without it, "
                    f"e.g. {lacking[:3]}",
                )


def check_body_coverage(pack: G.GenrePack, report: Report) -> None:
    """27. Every subject resolves to a declared body, even an empty one."""
    if not pack.body_keywords:
        return
    for kind, value in _subjects(pack):
        if not G.has_body_declaration(pack, kind, value):
            report.fail("BODYCOVER", f"{value or kind!r} ({kind}) declares no body at any level")


def check_part_keywords(pack: G.GenrePack, report: Report) -> None:
    """29. A part that names a body structure is drawn only by bodies that have it."""
    if not pack.part_keywords:
        return
    for field_name in pack.part_lint_fields:
        for option, subjects in sorted(_reach(pack, field_name).items()):
            named = _named(pack.part_keywords, option)
            if not named:
                continue
            lacking = sorted({
                f"{value or kind} lacks "
                f"{'/'.join(sorted(named - G.body_features_of(pack, kind, value)))}"
                for kind, value in subjects
                if named - G.body_features_of(pack, kind, value)
            })
            if lacking:
                report.fail(
                    "PARTFIT",
                    f"{field_name}: {option!r} is drawn by {len(lacking)} body(ies) "
                    f"without it, e.g. {lacking[:3]}",
                )


def check_cardinality_coverage(pack: G.GenrePack, report: Report) -> None:
    """30. Every count noun says how many of it there can be.

    A count field's scope asks its noun first and its kind second, so a noun
    with no class of its own is counted by its kind -- and a kind is far too
    coarse to ask: "a dozen drive nacelles" and "a dozen luminous hull seams"
    are the same draw on the same field, and only one of them is a picture. The
    first renders as engines at both ends of the hull.

    Both directions, for the reason ``check_tier_coverage`` checks both: a
    class naming a value the pools no longer hold is a declaration that stopped
    being true, and it is invisible until something draws it.
    """
    if not pack.value_cardinality:
        return
    for noun_field in pack.counts:
        values = set(G.pool_options(pack, noun_field))
        classified = set(pack.value_cardinality.get(noun_field, {}))
        for value in sorted(values - classified):
            report.fail(
                "CARD",
                f"{noun_field}: {value!r} carries no cardinality class, so how many "
                "of it there are is decided by the kind",
            )
        for value in sorted(classified - values):
            report.fail(
                "CARD",
                f"value_cardinality[{noun_field!r}] names {value!r}, which is not a "
                f"value of {noun_field!r}",
            )


def check_shadowed_values(pack: G.GenrePack, report: Report) -> None:
    """28. A value authored only under a key no subject resolves is unreachable."""
    type_name = G.type_field(pack)
    if type_name is None:
        return
    fields = [
        name for name, spec in pack.entity_fields.items() if type_name in spec.scope
    ]
    if G.SITUATION_FIELD not in fields:
        fields.append(G.SITUATION_FIELD)
    for field_name in fields:
        reach = _reach(pack, field_name)
        for value in G.pool_options(pack, field_name):
            if value in reach:
                continue
            keys = G.pool_keys_for_value(pack, field_name, value)
            if keys == (G.POOL_DEFAULT_KEY,):
                key = f"{field_name}_stranger_only"
                report.numbers[key] = report.numbers.get(key, 0) + 1
                continue
            report.fail(
                "SHADOWED",
                f"{field_name}: {value!r} is authored under {keys} but no subject "
                "resolves any of them",
            )

def check_spoken_completeness(pack: G.GenrePack, report: Report) -> None:
    """16. A subkind of an apposition-free kind must carry a spoken form."""
    spoken = pack.spoken.get("subkind", {})
    for kind in pack.kinds:
        head = _head_phrase_for_kind(pack, kind)
        if head is None or head.apposition is not None:
            continue
        for subkind in G.pool_for(pack, "subkind", kind):
            if subkind not in spoken:
                report.fail(
                    "SPOKEN",
                    f"subkind[{kind}]: {subkind!r} has no spoken form and its "
                    "archetype has no apposition, so its category is never said",
                )

def check_tier_coverage(pack: G.GenrePack, report: Report) -> None:
    """17. Every value of a tiered field carries a tier, and no tier is stale.

    A content check rather than a construction one: a user's
    ``user_options.json`` may add an untiered value at merge time and must not
    crash the pack, so the maintainer's gate lives here where the user's file
    can never trip it."""
    for field_name, tiers in pack.value_tiers.items():
        values = set(G.pool_options(pack, field_name))
        for value in sorted(values - set(tiers)):
            report.fail(
                "TIER",
                f"value_tiers[{field_name!r}] leaves {value!r} unclassified; every "
                "value of a tiered field must carry a tier",
            )
        for value in sorted(set(tiers) - values):
            report.fail(
                "TIER",
                f"value_tiers[{field_name!r}] names {value!r}, which is not a "
                f"value of {field_name!r}",
            )


CHECKS = (
    check_tags,
    check_constraints,
    check_pool_coverage,
    check_values,
    check_plurals,
    check_situations,
    check_situation_visibility,
    check_cross_field_duplicates,
    check_situation_groups,
    check_foreign_nouns,
    check_affordance_keywords,
    check_affordance_coverage,
    check_stance_coverage,
    check_affordance_contradictions,
    check_attributive_modifiers,
    check_singular_forms,
    check_band_floor,
    check_kind_feasibility,
    check_empty_defaults,
    check_stance_keywords,
    check_body_keywords,
    check_body_coverage,
    check_part_keywords,
    check_cardinality_coverage,
    check_spoken_completeness,
    check_tier_coverage,
    check_shadowed_values,
)


def validate(pack: G.GenrePack = SCIFI_PACK) -> Report:
    """Run every check over ``pack`` and return the report.

    Takes a pack so ``tests/test_validate_data.py`` can plant a defect in a copy
    and require this to catch it. A validator nobody has watched reject anything
    is a claim, not a check.
    """
    report = Report()
    for check in CHECKS:
        check(pack, report)
    return report


def main(argv: "list[str] | None" = None) -> int:
    report = validate()
    print(f"validate_data -- {SCIFI_PACK.display} pack ({SCIFI_PACK.slug})")
    for key in sorted(report.numbers):
        print(f"  {key:<22} {report.numbers[key]}")
    total = report.numbers.get("situation_values", 0)
    classified = report.numbers.get("situation_classified", 0)
    percent = 100.0 * classified / total if total else 100.0
    print(f"  {'situation_needs':<22} {percent:.1f}%")
    print()
    for line in report.notes:
        print(line)
    print()
    if report.failures:
        print(f"FAILED with {len(report.failures)} finding(s):")
        for line in report.failures:
            print(f"  {line}")
        return 1
    print("OK -- tags, constraints, pools, articles, plurals and both denylists are sound.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
