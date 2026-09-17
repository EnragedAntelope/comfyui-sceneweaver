"""Todo 21 -- does the scene hold together, over a sweep rather than a fixture?

``tests/test_prose.py`` pins the renderer against hand-built entities: it proves
each rule in isolation. This file asks the different question -- whether the
rules still hold on scenes the *generator* actually produces, across every
detail level and every filter. A rule that is correct on a fixture and wrong on
seed 317 is still wrong.

Five things are checked, and each is a way the output can be internally
inconsistent rather than merely ugly:

1. **prompt_json and prompt_text describe the same scene.** Every occupied slot
   gets a sentence; an omitted slot never appears; every non-``None`` value is
   spoken. The inverse -- a field resolved and then silently dropped -- is the
   dead-widget bug class (``identity-forge-dead-widget-check``).
2. **A relation has two real ends.** Half a relation would have to invent a
   partner, and inventing one is the never-negate rule in another costume.
3. **Articles agree with the words after them**, checked against an *independent*
   implementation of the a/an rule. Using ``engine.grammar.article_for`` as the
   oracle for prose that ``article_for`` produced would assert only that the
   function is consistent with itself.
4. **A non-human body is the subject of its sentence.** Four Identity Forge
   render bugs traced to getting this backwards; a model given a body plan as a
   trailing modifier draws a human holding one.
5. **Nothing is said twice.** Pools overlap by design, so an entity could draw
   the same string into two clauses ("an oxide red hull, oxide red accents").

The never-negate rule is listed under this todo too; the wide sweep for it lives
in ``tests/test_boundary.py``, next to the denylist it shares a scanner with,
and the assertion here is the pointer that stops it being looked for in only one
of the two places.
"""
from __future__ import annotations

import dataclasses
from collections import Counter
import re
import unittest

from data.genre import (
    KIND_FIELD,
    Literal,
    Optional,
    affordances_of,
    archetype_for,
    filtered_pool,
    is_classified,
    pool_for,
    pool_options,
    spoken_value,
)
from data.scifi import SCIFI_PACK, _FLOOR_BOUND
from engine.grammar import head_is_plural, head_noun, pluralize
from engine.prose import _references, compose_scene, render_entity, render_prose
from engine.resolution import ResolvedEntity, ResolvedRelation, ResolvedScene
from engine.scene import generate_entity, generate_scene
from tests.boundary import negation_findings

SWEEP_SEEDS = 300

#: Keys of a ``prompt_json`` entity record that are provenance, not description.
_META_KEYS = frozenset({"index", "source", "genre", "situation", "archetype"})

#: The one field a document may carry that the prose does not say. The head
#: phrase's noun ladder consumes ``kind`` whenever a ``subkind`` outranks it, so
#: "a heavy freighter" is not followed by a redundant "starship". Anything else
#: appearing here would be a field resolved and discarded.
_CONSUMED_UNSPOKEN = frozenset({"kind"})

#: Words whose spelling and whose sound disagree. Empty of matches over the
#: shipped pack -- measured, not assumed -- but present because the first
#: authored "universal joint" or "hour-glass hull" would otherwise turn a
#: correct article into a failure here.
_YOO_GLIDE = ("uni", "use", "usu", "utili", "eu", "one", "once")
_SILENT_H = ("hour", "honest", "honour", "honor", "heir")


def _expected_article(word: str) -> str:
    """The a/an rule, implemented independently of ``engine.grammar``."""
    low = word.lower()
    if low.startswith(_SILENT_H):
        return "an"
    if low.startswith(_YOO_GLIDE):
        return "a"
    return "an" if low[:1] in "aeiou" else "a"


def _entities(document) -> list[ResolvedEntity]:
    """Rebuild the resolved entities from ``prompt_json``.

    Through the public document rather than by reaching into the generator, so
    what is asserted is what a downstream node would read.
    """
    return [
        ResolvedEntity(
            index=record["index"],
            source=record["source"],
            genre=record["genre"],
            fields={k: v for k, v in record.items() if k not in _META_KEYS},
            situation=record["situation"],
        )
        for record in document["entities"]
    ]

def _sweep(seeds=SWEEP_SEEDS, **kwargs):
    for seed in range(seeds):
        text, document = generate_scene(seed, SCIFI_PACK, **kwargs)
        yield seed, None, text, document


def _sentences(text: str) -> list[str]:
    """Sentences of a rendered scene, split the way ``render_prose`` joins them."""
    return [s for s in text.split(". ") if s]


def _scene(document) -> ResolvedScene:
    """Rebuild the resolved scene from ``prompt_json``.

    Through the public document rather than by reaching into the generator, so
    what is asserted is what a downstream node would read.
    """
    return ResolvedScene(
        environment=document["environment"],
        context=document.get("context"),
        context_sentence_index=document["_meta"].get("context_sentence_index"),
        entities=tuple(_entities(document)),
        relations=tuple(
            ResolvedRelation(endpoints=tuple(record["endpoints"]), value=record["value"], position=record.get("position"))
            for record in document["relations"]
        ),
    )

def _is_spoken(pack, field: str, value: str, text: str) -> bool:
    """Whether a document value reached the prose, allowing for inflection.

    A value may reach the sentence as its declared **spoken form** ("hospital
    starship" for the token "hospital ship") or as an inflected form of either
    ("missile batteries"), so both are accepted. ``prompt_json`` keeps the
    token; the prose speaks the spoken form.
    """
    low = text.lower()
    candidates = (value, spoken_value(pack, field, value))
    return any(
        candidate.lower() in low or pluralize(candidate).lower() in low
        for candidate in candidates
    )


class DocumentAgreesWithProseTests(unittest.TestCase):
    def test_the_text_is_exactly_the_scene_render_output(self) -> None:
        """``prompt_text`` IS ``render_prose`` of the resolved scene.

        In narrative mode that means the composed output -- the environment
        frame, the woven relative clauses, the split possessive predicates --
        and not some sentence-per-section shadow of it.
        """
        for seed, level, text, document in _sweep(seeds=100):
            with self.subTest(seed=seed, level=level):
                self.assertEqual(render_prose(_scene(document), SCIFI_PACK), text)
    def test_an_omitted_slot_is_absent_from_both(self) -> None:
        """A slot with no kind is left out of the scene, not described empty."""
        widgets = {f"entity{slot}_kind": "None" for slot in (2, 3, 4)}
        for seed, level, text, document in _sweep(seeds=100, widgets=widgets):
            with self.subTest(seed=seed, level=level):
                self.assertEqual([e["index"] for e in document["entities"]], [1])
                self.assertEqual(document["relations"], [])

    def test_every_document_value_is_spoken(self) -> None:
        """``None`` if and only if unspoken -- checked in the hard direction.

        ``kind`` is the one exemption, and it is a design decision rather than a
        hole: the head-phrase noun ladder gives way to a more specific
        ``subkind``, because "a heavy freighter" already says "starship". The test
        below pins that it is the *only* exemption, so the list cannot quietly
        grow into the dead-widget bug it is one instance away from.
        """
        for seed, level, text, document in _sweep(seeds=100):
            for record in document["entities"]:
                for name, value in record.items():
                    if name in _META_KEYS or name in _CONSUMED_UNSPOKEN or value is None:
                        continue
                    with self.subTest(seed=seed, level=level, field=name):
                        self.assertTrue(
                            _is_spoken(SCIFI_PACK, name, value, text),
                            f"{value!r} in {text!r}",
                        )

    def test_kind_is_the_only_field_a_document_may_hold_unspoken(self) -> None:
        """Swept at every level, not only at ``Everything``.

        ``Everything`` cuts nothing, so a budget that stopped writing its cut
        fields back to ``None`` would leave this green while ``prompt_json``
        quietly claimed values the prompt never said. Planted and confirmed.
        """
        unspoken = set()
        for _seed, _level, text, document in _sweep(seeds=200):
            for record in document["entities"]:
                for name, value in record.items():
                    if name in _META_KEYS or value is None:
                        continue
                    if not _is_spoken(SCIFI_PACK, name, value, text):
                        unspoken.add(name)
        self.assertEqual(unspoken, set(_CONSUMED_UNSPOKEN))



#: The six relation widgets default to ``None``, so a default sweep produces no
#: relations at all and every assertion about them would pass vacuously. Turning
#: them on is what makes this file's relation tests test anything -- a planted
#: defect that emitted a relation to an unoccupied slot went unnoticed until
#: they did.
ALL_RELATIONS = {
    f"relation_{first}_{second}": "Random"
    for first in range(1, 5)
    for second in range(first + 1, 5)
}

ALL_ENTITIES = {f"entity{n}_kind": "Random" for n in range(1, 5)}


class RelationTests(unittest.TestCase):
    def test_the_sweep_actually_produces_relations(self) -> None:
        """Guards against every assertion below passing vacuously."""
        seen = sum(
            len(document["relations"])
            for _s, _l, _t, document in _sweep(seeds=50, widgets=ALL_RELATIONS, entity_count=4)
        )
        self.assertGreater(seen, 0)

    def test_both_endpoints_of_every_relation_are_occupied(self) -> None:
        for seed, level, _text, document in _sweep(widgets=ALL_RELATIONS, entity_count=4):
            occupied = {e["index"] for e in document["entities"]}
            for relation in document["relations"]:
                with self.subTest(seed=seed, level=level):
                    self.assertLessEqual(set(relation["endpoints"]), occupied)

    def test_every_relation_in_the_document_is_in_the_prose(self) -> None:
        for seed, level, text, document in _sweep(seeds=100, widgets=ALL_RELATIONS, entity_count=4):
            for relation in document["relations"]:
                with self.subTest(seed=seed, level=level):
                    self.assertIn(relation["value"].lower(), text.lower())

    def test_a_relation_never_joins_a_slot_to_itself(self) -> None:
        for _seed, _level, _text, document in _sweep(seeds=100, widgets=ALL_RELATIONS, entity_count=4):
            for relation in document["relations"]:
                first, second = relation["endpoints"]
                self.assertNotEqual(first, second)

    def test_a_scene_with_one_entity_has_no_relations(self) -> None:
        widgets = {
            **ALL_RELATIONS,
            **{f"entity{slot}_kind": "None" for slot in (2, 3, 4)},
        }
        for _seed, _level, _text, document in _sweep(seeds=100, widgets=widgets):
            self.assertEqual(document["relations"], [])


class ArticleTests(unittest.TestCase):
    def test_every_article_agrees_with_the_word_after_it(self) -> None:
        pattern = re.compile(r"\b(an?) ([A-Za-z][A-Za-z'-]*)")
        for seed, level, text, _document in _sweep():
            for article, word in pattern.findall(text):
                with self.subTest(seed=seed, level=level, phrase=f"{article} {word}"):
                    self.assertEqual(article.lower(), _expected_article(word))

    def test_a_sentence_never_opens_with_a_bare_article(self) -> None:
        for seed, level, text, _document in _sweep(seeds=100):
            with self.subTest(seed=seed, level=level):
                self.assertNotRegex(text, r"\b[Aa]n? \.")
                self.assertNotRegex(text, r"\b[Aa]n? ,")


class SubjectLeadingTests(unittest.TestCase):
    """A non-human body is the subject of its sentence, not a trailing modifier."""

    def test_a_creature_with_a_body_plan_leads_with_it(self) -> None:
        kinds = SCIFI_PACK.prose.subject_leading_kinds
        self.assertTrue(kinds, "no kind is declared subject-leading")
        seen = 0
        widgets = {"entity1_kind": next(iter(kinds))}
        for _seed, _level, _text, document in _sweep(seeds=200, widgets=widgets):
            for entity in _entities(document):
                form = entity.get("form")
                if entity.kind not in kinds or form is None:
                    continue
                seen += 1
                text = render_entity(entity, SCIFI_PACK)
                # Leading adjectives are allowed -- a hull colour folds onto the
                # body plan when no material is standing ("a cobalt blue
                # hexapodal frame"), and that is still the body plan leading.
                # What must never happen is the body plan arriving *after* the
                # creature type: "a creature with a segmented worm body" draws a
                # human holding a worm.
                head, _, _ = text.partition(".")
                # The sentence is capitalized, so the head's first word may be
                # the form itself ("Vertically stacked disc segments, ..."); the
                # comparison is about position, not case.
                lowered = head.lower()
                self.assertIn(
                    form.lower(), lowered, f"slot {entity.index}: {text!r}"
                )
                # Only an article and folded adjectives may precede the body
                # plan. A comma before it would mean another clause got there
                # first, which is the failure this test exists for.
                self.assertNotIn(
                    ",",
                    lowered[: lowered.index(form.lower())],
                    f"slot {entity.index}: {text!r}",
                )
        self.assertGreater(seen, 0, "no creature with a body plan was ever generated")


class RepetitionTests(unittest.TestCase):
    def test_no_entity_says_the_same_thing_twice(self) -> None:
        heads = [n for n, s in SCIFI_PACK.entity_fields.items() if s.renders_with is None]
        for seed, level, _text, document in _sweep():
            for record in document["entities"]:
                spoken = [record[name] for name in heads if record.get(name)]
                with self.subTest(seed=seed, level=level, slot=record["index"]):
                    self.assertEqual(len(spoken), len(set(spoken)), spoken)

    def test_a_user_who_locks_two_fields_to_one_value_still_gets_both(self) -> None:
        """The repeat guard yields to an explicit lock, like every other rule
        in this engine."""
        widgets = {
            "entity1_kind": "starship",
            "entity1_primary_color": "oxide red",
            "entity1_accent_color": "oxide red",
        }
        _text, document = generate_scene(
            7, SCIFI_PACK, widgets=widgets,         )
        record = document["entities"][0]
        self.assertEqual(record["primary_color"], "oxide red")
        self.assertEqual(record["accent_color"], "oxide red")

    def test_an_unlocked_repeat_yields_to_a_locked_one(self) -> None:
        """Forced rather than hoped for: the random field's pool is narrowed to
        the single value that collides, so the draw *must* repeat the lock and
        the guard is the only thing that can stop it reaching the prose."""
        collision = "verdigris staining"
        pools = {name: dict(by_kind) for name, by_kind in SCIFI_PACK.pools.items()}
        pools["surface_detail"]["alien artifact"] = (collision,)
        pack = dataclasses.replace(SCIFI_PACK, pools=pools)
        widgets = {
            "entity1_kind": "alien artifact",
            "entity1_markings": collision,
        }
        for seed in range(20):
            text, document = generate_scene(
                seed, pack, widgets=widgets,             )
            record = document["entities"][0]
            with self.subTest(seed=seed):
                self.assertEqual(record["markings"], collision)
                self.assertIsNone(record["surface_detail"])
                self.assertEqual(text.lower().count(collision), 1)


class PredicateTests(unittest.TestCase):
    """Every entity is a subject + conjugated predicate across the real sweep."""

    def test_every_entity_with_a_situation_has_a_conjugated_copula(self) -> None:
        seen = 0
        for seed, level, _text, document in _sweep(seeds=100):
            for entity in _entities(document):
                sentence = render_entity(entity, SCIFI_PACK)
                with self.subTest(seed=seed, level=level, slot=entity.index):
                    self.assertTrue(sentence.endswith("."), sentence)
                    if entity.situation is not None:
                        self.assertRegex(sentence, r"\b(is|are)\b", sentence)
                        seen += 1
        self.assertGreater(seen, 0, "no entity with a situation was ever rendered")


class NeverNegateTests(unittest.TestCase):
    """Listed under this todo; the wide sweep is in ``tests/test_boundary.py``."""

    def test_no_generated_scene_negates(self) -> None:
        for seed, level, text, _document in _sweep(seeds=100):
            findings = negation_findings(text)
            if findings:
                self.fail(f"seed {seed} at {level}: {', '.join(findings)} in {text!r}")


#: Two independent clauses joined by a comma. The entity shape groups its
#: descriptors -- bare, article-less noun phrases -- under one ``with`` clause,
#: so a comma before a pronoun, possessive or definite-article clause is the
#: splice signal that survives: a re-introduced "its hull is ..." or "it is
#: marked with ..." predicate would be comma-spliced exactly this way.
_COMMA_SPLICE_RE = re.compile(
    r",\s+(?:it|its|this|that|the)\s+(?:[a-z]+\s+)?(?:is|are|was|were)\b"
)


class NarrativeTests(unittest.TestCase):
    """A scene reads as connected prose, not a sentence-per-section catalog:
    the environment is its own setting sentence, each entity is a subject +
    conjugated predicate, and relations are woven in as relative clauses."""

    def test_the_environment_is_its_own_setting_sentence(self) -> None:
        for seed, level, text, document in _sweep(seeds=100):
            environment = document["environment"]
            if not environment or not document["entities"]:
                continue
            with self.subTest(seed=seed, level=level):
                first = _sentences(text)[0].lower()
                self.assertIn(spoken_value(SCIFI_PACK, "environment", environment).lower(), first)
                # The setting sentence also carries the genre frame. Every
                # noun in this pack's ship vocabulary is also a naval noun, so
                # a prompt that never names its genre gets drawn at sea; the
                # frame is a connective in the opening sentence rather than a
                # noun phrase appended at the end, which would read as one more
                # thing in the scene.
                self.assertTrue(
                    first.startswith(SCIFI_PACK.prose.environment_sentence.split("{")[0].lower()),
                    first,
                )

    def test_the_environment_stands_alone_without_entities(self) -> None:
        """With no entity sentence to carry it, the environment keeps its own."""
        widgets = {f"entity{slot}_kind": "None" for slot in (1, 2, 3, 4)}
        for seed, _level, text, document in _sweep(seeds=50, widgets=widgets):
            environment = document["environment"]
            if not environment:
                continue
            with self.subTest(seed=seed):
                self.assertIn(spoken_value(SCIFI_PACK, "environment", environment).lower(), text.lower())
                self.assertNotIn(". ", text)
                self.assertTrue(text.endswith("."))

    def test_every_relation_is_a_standalone_sentence(self) -> None:
        widgets = {
            **ALL_ENTITIES,
            **ALL_RELATIONS,
            **{f"relation_{f}_{s}_position": "Random" for f in range(1, 5) for s in range(f + 1, 5)},
        }
        for seed, level, text, document in _sweep(seeds=100, widgets=widgets):
            scene = _scene(document)
            references = _references(scene, SCIFI_PACK)
            sentences = compose_scene(scene, SCIFI_PACK, references)
            for relation in scene.relations:
                first, second = relation.endpoints
                with self.subTest(seed=seed, level=level, relation=relation.value):
                    self.assertTrue(
                        any(
                            relation.value in s
                            and references[first].lower() in s.lower()
                            and references[second].lower() in s.lower()
                            for s in sentences
                        ),
                        text,
                    )
                    if relation.position:
                        self.assertTrue(
                            any(relation.position in s for s in sentences), text
                        )

    def test_no_comma_splices(self) -> None:
        for seed, level, text, _document in _sweep(
            seeds=100, widgets=ALL_RELATIONS, entity_count=4
        ):
            with self.subTest(seed=seed, level=level):
                self.assertIsNone(_COMMA_SPLICE_RE.search(text), text)

    def test_a_non_narrative_pack_keeps_sentence_per_section(self) -> None:
        """``narrative_mode=False`` keeps the catalog layout -- the backward
        compatibility the flag exists for."""
        pack = dataclasses.replace(
            SCIFI_PACK, prose=dataclasses.replace(SCIFI_PACK.prose, narrative_mode=False)
        )
        text, document = generate_scene(
            7, pack,  widgets=ALL_RELATIONS
        )
        self.assertNotIn(", that is ", text)
        self.assertIn(" is ", text)

class ArchetypeTests(unittest.TestCase):
    """An archetype decides how a category of thing is *spoken*.

    ``kind`` says what an entity is drawn from; an archetype says how the result
    is worded. Before the split there was no kind dimension in the template
    table at all, and every one of these assertions was false: a nebula was
    "clad in hydrogen and helium cloud", a spacefarer was clad in their own
    suit, a black hole had an impact crater basin and an ice cap.
    """

    #: Fields that presume a surface. A thing with none of them declared should
    #: have all of them absent, in the document as well as in the prose.
    SURFACE_FIELDS = ("material", "surface_detail", "aperture", "extras")

    def _slots(self, seeds: int = 300):
        for seed, _level, text, document in _sweep(seeds=seeds, entity_count=4):
            for entity in _entities(document):
                yield seed, text, entity

    def test_a_body_with_no_surface_is_never_given_one(self) -> None:
        """The defect the whole mechanism was built for.

        Checked on the *document*, not the prose: a field suppressed only at
        render time would still sit in prompt_json promising the image an
        integument the thing does not have.
        """
        diffuse = {s for s, name in SCIFI_PACK.archetype_of_override.items()
                   if name == "phenomenon"}
        self.assertTrue(diffuse, "the pack declares no subkind archetype overrides")
        seen = 0
        for seed, _text, entity in self._slots():
            if entity.get("subkind") not in diffuse:
                continue
            seen += 1
            for name in self.SURFACE_FIELDS:
                with self.subTest(seed=seed, subkind=entity.get("subkind"), field=name):
                    self.assertIsNone(entity.get(name))
        self.assertGreater(seen, 0, "no diffuse body was ever generated")

    def test_every_archetype_omission_holds_end_to_end(self) -> None:
        """Every declared omission, checked against what actually resolved."""
        for seed, _text, entity in self._slots():
            archetype = archetype_for(SCIFI_PACK, entity.fields)
            if archetype is None:
                continue
            for name in sorted(archetype.omits):
                with self.subTest(seed=seed, kind=entity.kind, field=name):
                    self.assertIsNone(entity.get(name))

    def test_a_material_is_worded_for_what_it_is_on(self) -> None:
        """One template served a hull, a hide and a suit, and it read as a hull.

        The connector now lives in the sentence pattern rather than in a
        per-archetype template, so the wording is read from there. A test naming
        the strings would keep passing if every archetype quietly went back to
        sharing one, so this asserts they differ.
        """
        leads = {
            pattern.text.split("{material}")[0]
            for archetype in SCIFI_PACK.archetypes.values()
            for pattern in archetype.sentences
            if "{material}" in pattern.text
        }
        self.assertGreater(
            len(leads), 1,
            "every archetype words a material identically, so the split does nothing",
        )
        for name, archetype in SCIFI_PACK.archetypes.items():
            if "material" in archetype.omits:
                continue
            with self.subTest(archetype=name):
                self.assertTrue(
                    any("{material}" in p.text for p in archetype.sentences),
                    f"{name} can draw a material but has no pattern that says it",
                )

    def test_the_generic_kind_reaches_the_prompt_where_it_is_declared(self) -> None:
        """The naval-ship fix, asserted end to end.

        Nothing in "a large battle-scarred warship with a hammerhead prow hull"
        says the subject is a spacecraft, and every word in it is also a naval
        word. Where an archetype declares an apposition, that category noun must
        actually arrive in the prompt.
        """
        seen = 0
        for seed, text, entity in self._slots(seeds=200):
            archetype = archetype_for(SCIFI_PACK, entity.fields)
            head = archetype.head_phrase if archetype else None
            if head is None or head.apposition is None:
                continue
            category = entity.get(head.apposition)
            if not category or entity.get("subkind") is None:
                continue
            seen += 1
            with self.subTest(seed=seed, kind=entity.kind):
                self.assertIn(spoken_value(SCIFI_PACK, head.apposition, category), text)
        self.assertGreater(seen, 0, "no entity with a declared apposition was generated")


class ScopeChainTests(unittest.TestCase):
    """The scope chain: every field resolves through its controls, and two
    clauses never inflect one noun."""

    @staticmethod
    def _normalized_head(value: str) -> str:
        return head_noun(value).lower().rstrip("s")

    def test_no_entity_repeats_a_head_noun(self) -> None:
        """Two clauses never share a head noun outside a shared vocabulary."""
        for seed, _level, _text, document in _sweep(seeds=400):
            for record in document["entities"]:
                owner: dict[str, str] = {}
                for name in SCIFI_PACK.entity_fields:
                    if name == KIND_FIELD:
                        continue
                    if SCIFI_PACK.entity_fields[name].renders_with is not None:
                        continue
                    value = record.get(name)
                    if value is None:
                        continue
                    head = self._normalized_head(value)
                    held_by = owner.get(head)
                    if held_by is None:
                        owner[head] = name
                        continue
                    if any(
                        name in group and held_by in group
                        for group in SCIFI_PACK.shared_vocabulary
                    ):
                        continue
                    with self.subTest(seed=seed, field=name):
                        self.fail(
                            f"{name}={value!r} repeats head {head!r} held by {held_by}"
                        )

    def test_every_scoped_field_resolves_through_its_chain(self) -> None:
        """A resolved value is always in its field's scope-keyed, filtered pool."""
        for seed, _level, _text, document in _sweep(seeds=300):
            for record in document["entities"]:
                values = {k: v for k, v in record.items() if k not in _META_KEYS}
                for name, spec in SCIFI_PACK.entity_fields.items():
                    if not spec.scope:
                        continue
                    value = values.get(name)
                    if value is None:
                        continue
                    scope = {
                        control: (
                            values.get(control)
                            if control in SCIFI_PACK.entity_fields
                            else document["environment"]
                        )
                        for control in spec.scope
                    }
                    pool = filtered_pool(SCIFI_PACK, name, scope)
                    with self.subTest(seed=seed, field=name, value=value):
                        self.assertIn(value, pool)

    def test_no_person_scale_item_is_counted_in_bulk(self) -> None:
        """A matched pair of boots is never "eight"; a worn fitting is never "six".

        The count is scoped on the noun it counts, so a noun in a cardinality
        group draws from that group's count pool rather than the kind's bulk one.
        """
        allowed = {"a single", "a pair of", "three"}
        pairs = (
            ("appendage_count", "appendages"),
            ("emitter_count", "emitters"),
            ("armament_count", "armament"),
            ("sensor_count", "sensors"),
        )
        seen = 0
        widgets = {"entity1_kind": "spacefarer"}
        for seed, _level, _text, document in _sweep(seeds=400, widgets=widgets):
            for record in document["entities"]:
                if record.get("kind") != "spacefarer":
                    continue
                seen += 1
                for count_field, noun_field in pairs:
                    noun = record.get(noun_field)
                    count = record.get(count_field)
                    if noun is None or count is None:
                        continue
                    groups = SCIFI_PACK.pool_groups.get(noun_field, {})
                    if any(noun in members for members in groups.values()):
                        with self.subTest(seed=seed, noun=noun):
                            self.assertIn(count, allowed, f"{noun!r} counted {count!r}")
        self.assertGreater(seen, 0, "no spacefarer was generated")


class ArchetypeShapeTests(unittest.TestCase):
    """The archetype owns how much an entity speaks and in what shape."""

    _HEADS = tuple(
        name
        for name, spec in SCIFI_PACK.entity_fields.items()
        if spec.renders_with is None
    )

    def test_no_entity_repeats_a_sentence_lead(self) -> None:
        """``It carries ... It carries ...`` was in the corpus; the caps make
        it unreachable, and this is what keeps it unreachable."""
        for seed in range(150):
            _text, document = generate_scene(seed, SCIFI_PACK, entity_count=1)
            for record in document["entities"]:
                entity = ResolvedEntity(
                    index=record["index"],
                    source=record["source"],
                    genre=record["genre"],
                    fields={n: record.get(n) for n in SCIFI_PACK.entity_fields},
                    situation=record.get("situation"),
                )
                rendered = render_entity(entity, SCIFI_PACK)
                leads = [
                    " ".join(sentence.split()[:3])
                    for sentence in rendered.split(". ")
                    if sentence.strip()
                ]
                with self.subTest(seed=seed, index=record["index"]):
                    self.assertEqual(len(leads), len(set(leads)), rendered)

    def test_a_phenomenon_never_wears_a_solid_surface_part(self) -> None:
        from data.genre import pool_for as genre_pool_for
        from data.scifi import ARCHETYPE_OF_SUBKIND

        phenomenon = {
            subkind
            for subkind, name in ARCHETYPE_OF_SUBKIND.items()
            if name == "phenomenon"
        }
        for seed in range(300):
            _text, document = generate_scene(seed, SCIFI_PACK, entity_count=1)
            for record in document["entities"]:
                subkind = record.get("subkind")
                if subkind not in phenomenon:
                    continue
                for field in ("appendages", "emitters"):
                    value = record.get(field)
                    if value is None:
                        continue
                    allowed = set(
                        genre_pool_for(SCIFI_PACK, field, {"subkind": subkind})
                    )
                    with self.subTest(seed=seed, subkind=subkind, field=field):
                        self.assertIn(value, allowed)

    def test_no_entity_speaks_more_than_its_archetypes_cap(self) -> None:
        from data.genre import archetype_name_for

        for seed in range(300):
            _text, document = generate_scene(seed, SCIFI_PACK, entity_count=1)
            for record in document["entities"]:
                name = archetype_name_for(
                    SCIFI_PACK,
                    {n: record.get(n) for n in SCIFI_PACK.entity_fields},
                )
                archetype = SCIFI_PACK.archetypes.get(name) if name else None
                if archetype is None or archetype.detail_cap is None:
                    continue
                spoken = [
                    n
                    for n in self._HEADS
                    if n != KIND_FIELD and record.get(n) is not None
                ]
                with self.subTest(seed=seed, archetype=name):
                    self.assertLessEqual(len(spoken), archetype.detail_cap)



class SentenceGrammarTests(unittest.TestCase):
    """Every emitted sentence is one the genre authored.

    The regression guard for the whole overhaul: a sentence that matches no
    pattern is one the renderer invented -- a verbless appositive pile, or a
    connector that leaked back into ``engine/prose.py``.
    """

    @staticmethod
    def _regex(pattern):
        def render(segment):
            if isinstance(segment, Literal):
                return re.escape(segment.text)
            if isinstance(segment, Optional):
                return "(?:" + "".join(render(s) for s in segment.segments) + ")?"
            return ".+?"

        return re.compile("^" + "".join(render(s) for s in pattern._segments) + "$")

    def _plan(self, entity):
        archetype = archetype_for(SCIFI_PACK, entity.fields)
        if archetype is not None and archetype.sentences:
            return archetype.sentences
        return SCIFI_PACK.prose.entity_sentences

    def test_every_sentence_matches_an_authored_pattern(self) -> None:
        checked = 0
        for seed, _level, _text, document in _sweep(seeds=200, entity_count=2):
            for entity in _entities(document):
                plan = self._plan(entity)
                if not plan:
                    continue
                patterns = [self._regex(p) for p in plan]
                for sentence in _sentences(render_entity(entity, SCIFI_PACK)):
                    if not sentence.endswith("."):
                        sentence += "."
                    checked += 1
                    with self.subTest(seed=seed, sentence=sentence):
                        self.assertTrue(
                            any(rx.match(sentence) for rx in patterns),
                            f"{sentence!r} matches no pattern of its archetype",
                        )
        self.assertGreater(checked, 0)

    def test_a_person_is_never_spoken_as_it(self) -> None:
        seen = 0
        for seed, _level, _text, document in _sweep(seeds=200, entity_count=1):
            for entity in _entities(document):
                if entity.kind != "spacefarer":
                    continue
                seen += 1
                text = render_entity(entity, SCIFI_PACK)
                with self.subTest(seed=seed):
                    self.assertNotRegex(text, r"\bIt\b")
                    self.assertNotRegex(text, r"\bits\b")
        self.assertGreater(seen, 0)


class PunctuationTests(unittest.TestCase):
    """A1 -- an apposition closes itself.

    The old apposition opened with a comma and never closed it, so a rendered
    prompt could carry ``,.`` (the subject ended the sentence), ``, .`` (an
    optional segment stood down) or ``,,`` (a pattern's own comma followed it).
    None of those is English, and every one of them is a pattern-independent
    defect, so the sweep is where it is checked."""

    def test_no_prompt_carries_stray_punctuation(self) -> None:
        for seed, level, text, _document in _sweep(seeds=150):
            with self.subTest(seed=seed, level=level):
                self.assertNotIn(",.", text)
                self.assertNotIn(", .", text)
                self.assertNotIn(",,", text)
                self.assertNotIn("  ", text)


class BareModifierTests(unittest.TestCase):
    """A5 -- a promoted subject keeps its modifiers.

    Before the fix a creature dropped ``scale`` and ``condition`` from its head
    phrase and had to carry ``{pronoun} {pronoun_copula} {scale}.`` and
    ``{...} {condition}.`` patterns instead, which rendered as two filler
    sentences per creature. The sweep asserts no entity ever says only a scale
    or a condition again."""

    @staticmethod
    def _modifier_values() -> set[str]:
        values: set[str] = set()
        for field in ("scale", "condition"):
            values |= set(pool_for(SCIFI_PACK, field, None))
            for kind in SCIFI_PACK.kinds:
                values |= set(pool_for(SCIFI_PACK, field, kind))
        return values

    def test_no_entity_says_only_its_scale_or_condition(self) -> None:
        values = self._modifier_values()
        checked = 0
        for seed, level, _text, document in _sweep(seeds=150):
            for entity in _entities(document):
                for sentence in _sentences(render_entity(entity, SCIFI_PACK)):
                    body = sentence.rstrip(".").strip()
                    checked += 1
                    for prefix in ("It is ", "They are "):
                        if body.startswith(prefix) and body[len(prefix):] in values:
                            with self.subTest(seed=seed, level=level):
                                self.fail(f"bare modifier sentence: {sentence!r}")
        self.assertGreater(checked, 0)


class FloorBoundTests(unittest.TestCase):
    """B3 -- a nest needs a floor.

    ``guarding a nest`` and ``brooding over a clutch of eggs`` were in no band
    list, so a creature brooded over eggs in open orbit. The action set is read
    off the pack's own ``_FLOOR_BOUND`` rather than restated, so it cannot
    drift from the rule it guards."""

    def test_no_nest_situation_happens_without_a_floor(self) -> None:
        self.assertTrue(_FLOOR_BOUND)
        band_of = {
            value: band
            for band, values in SCIFI_PACK.environment_bands.items()
            for value in values
        }
        # Read off the pack's own place table: a band with no floor affordance
        # is where a nest cannot be built, so the test cannot drift from the rule.
        no_floor = {
            band
            for band, values in SCIFI_PACK.environment_bands.items()
            if all("floor" not in affordances_of(SCIFI_PACK, value) for value in values)
        }
        seen = 0
        for seed, _level, _text, document in _sweep(
            seeds=250, widgets={"entity1_kind": "alien creature"}, entity_count=4
        ):
            environment = document["environment"]
            if not environment or band_of[environment] not in no_floor:
                continue
            for entity in document["entities"]:
                situation = entity.get("situation")
                if situation is None:
                    continue
                seen += 1
                with self.subTest(seed=seed, situation=situation):
                    self.assertNotIn(situation, _FLOOR_BOUND)
        self.assertGreater(seen, 0)


class PlanetSurfaceTests(unittest.TestCase):
    """B5 -- a world seen from the ground has no sky to hang in.

    The pack describes an entity but never *places* it, so ``celestial body``
    is removed from the ``planetary surface`` kind pool: otherwise a moon is
    generated as the subject of a ground-level scene and the model puts it on
    the sand. The gap is recorded in ``docs/architecture.md``."""

    def test_no_celestial_body_appears_on_a_planetary_surface(self) -> None:
        band_of = {
            value: band
            for band, values in SCIFI_PACK.environment_bands.items()
            for value in values
        }
        seen = 0
        for seed, _level, _text, document in _sweep(seeds=250, entity_count=4):
            environment = document["environment"]
            if not environment or band_of[environment] != "planetary surface":
                continue
            for entity in document["entities"]:
                seen += 1
                with self.subTest(seed=seed):
                    self.assertNotEqual(entity["kind"], "celestial body")
        self.assertGreater(seen, 0)


class SurfaceVehicleSituationTests(unittest.TestCase):
    """B2 -- a vehicle's action is in the pool its subkind group resolves to."""

    def test_every_surface_vehicle_situation_matches_its_group(self) -> None:
        groups = SCIFI_PACK.pool_groups["subkind"]
        checked = 0
        for seed, _level, _text, document in _sweep(seeds=250, entity_count=4):
            for record in document["entities"]:
                if record.get("kind") != "surface vehicle":
                    continue
                subkind = record.get("subkind")
                situation = record.get("situation")
                if subkind is None or situation is None:
                    continue
                checked += 1
                allowed = pool_for(
                    SCIFI_PACK, "situation", {"subkind": subkind, "kind": "surface vehicle"}
                )
                with self.subTest(seed=seed, subkind=subkind):
                    self.assertIn(situation, allowed)
                self.assertIsNotNone(
                    next((g for g, members in groups.items() if subkind in members), None),
                    subkind,
                )
        self.assertGreater(checked, 0)

    def test_every_vehicle_action_fits_how_the_vehicle_moves(self) -> None:
        form_stances = SCIFI_PACK.value_stances["form"]
        situation_stances = SCIFI_PACK.value_stances["situation"]
        seen = 0
        for seed, _level, _text, document in _sweep(seeds=250, entity_count=4):
            for record in document["entities"]:
                if record.get("kind") != "surface vehicle" or not record.get("situation"):
                    continue
                needed = situation_stances.get(record["situation"])
                moves = form_stances.get(record.get("form"))
                if not needed or not moves:
                    continue
                seen += 1
                with self.subTest(seed=seed, situation=record["situation"], form=record.get("form")):
                    self.assertTrue(needed & moves)
        self.assertGreater(seen, 0)



class RoleTests(unittest.TestCase):
    """A robot is built for one job, and its job decides what it may carry."""

    ROLES = frozenset({"combat-role", "labour-role", "medical-role", "civil-role"})

    def test_every_robot_type_has_exactly_one_role(self) -> None:
        traits = SCIFI_PACK.value_traits.get("subkind", {})
        for subkind in pool_for(SCIFI_PACK, "subkind", {"kind": "robot or mech"}):
            with self.subTest(subkind=subkind):
                self.assertEqual(len(set(traits.get(subkind, ())) & self.ROLES), 1)
class FigureScaleTests(unittest.TestCase):
    """A person is person-sized; the figure archetype omits ``scale``."""

    def test_no_figure_entity_speaks_a_scale(self) -> None:
        widgets = {"entity1_kind": "spacefarer"}
        seen = 0
        for seed, _level, text, document in _sweep(seeds=150, widgets=widgets):
            for record in document["entities"]:
                if record.get("kind") != "spacefarer":
                    continue
                seen += 1
                with self.subTest(seed=seed):
                    self.assertIsNone(record.get("scale"))
                    for scale in ("tiny", "small", "mid-sized", "large", "massive"):
                        self.assertNotIn(f" {scale} ", f" {text} ")
        self.assertGreater(seen, 0, "no spacefarer was generated")




class ComponentClauseTests(unittest.TestCase):
    """W4 -- no entity renders as a bare shape.

    The product-shot failure was `{subject} is {situation}. It takes the form
    of {form}, cut from {material}.` and nothing else: one shape, one
    substance, no features. Every rendered entity must speak at least one
    component clause, or its archetype cap or priority is wrong."""

    COMPONENTS = (
        "appendages", "emitters", "armament", "sensors", "aperture", "extras",
    )

    def test_every_entity_speaks_a_component_clause(self) -> None:
        missing: list[tuple[int, str]] = []
        for seed in range(SWEEP_SEEDS):
            _text, document = generate_scene(seed, SCIFI_PACK, entity_count=1)
            for record in document["entities"]:
                if not any(
                    record.get(name) is not None for name in self.COMPONENTS
                ):
                    missing.append((seed, record["kind"]))
        self.assertEqual(
            missing, [], f"{len(missing)} entities had no component clause"
        )




class ContextTests(unittest.TestCase):
    """W7 -- a scene names what else is in the shot.

    The context is drawn once per scene, scoped on the environment band, and
    spoken as its own sentence after the entities. It is secondary scenery,
    never a second described subject: it has no form, material or components."""

    def test_the_context_reaches_the_prose_and_the_document(self) -> None:
        seen = 0
        for seed in range(SWEEP_SEEDS):
            text, document = generate_scene(seed, SCIFI_PACK, entity_count=1)
            context = document.get("context")
            if context is None:
                continue
            seen += 1
            with self.subTest(seed=seed):
                self.assertIn(
                    spoken_value(SCIFI_PACK, "context", context).lower(), text.lower()
                )
        self.assertGreater(seen, 0, "no scene ever drew a context")

    def test_the_context_comes_from_its_environment_band(self) -> None:
        for seed in range(SWEEP_SEEDS):
            _text, document = generate_scene(seed, SCIFI_PACK, entity_count=1)
            context = document.get("context")
            environment = document["environment"]
            if context is None or not environment:
                continue
            with self.subTest(seed=seed, environment=environment):
                self.assertIn(context, pool_for(SCIFI_PACK, "context", {"environment": environment}))

    def test_every_context_value_has_a_singular_head(self) -> None:
        """Every context sentence conjugates for one thing: "rows of stalks holds" was drawn."""
        for value in pool_options(SCIFI_PACK, "context"):
            with self.subTest(value=value):
                self.assertFalse(head_is_plural(value))


def _supported_stances(environment: str) -> frozenset[str]:
    """Every stance the place's affordances support, read off the pack."""
    supported: set[str] = set()
    for affordance in affordances_of(SCIFI_PACK, environment):
        supported |= set(SCIFI_PACK.place_stances.get(affordance, ()))
    return frozenset(supported)


class StanceTests(unittest.TestCase):
    """A shape is never drawn in a place that cannot hold it up."""

    def test_no_form_is_drawn_where_its_stance_is_unsupported(self) -> None:
        form_stances = SCIFI_PACK.value_stances.get("form", {})
        self.assertTrue(form_stances, "the stance vocabulary is empty")
        seen = 0
        for seed, level, text, document in _sweep(seeds=250, entity_count=4):
            environment = document["environment"]
            if environment is None:
                continue
            supported = _supported_stances(environment)
            for entity in _entities(document):
                stances = form_stances.get(entity.get("form"))
                if not stances:
                    continue
                seen += 1
                with self.subTest(seed=seed, level=level, form=entity.get("form")):
                    self.assertTrue(
                        stances & supported,
                        f"{entity.get('form')!r} cannot hold itself up in {environment!r}",
                    )
            for record in document["entities"]:
                if record["index"] != 1 and record["source"] != "wired":
                    continue
                kind, subkind = record.get("kind"), record.get("subkind")
                if (kind and subkind and record.get("form") is None
                        and pool_for(SCIFI_PACK, "form", {"kind": kind, "subkind": subkind})):
                    with self.subTest(seed=seed, level=level, kind=kind, subkind=subkind):
                        self.fail(f"{kind}/{subkind} has no silhouette in {environment!r}")
        self.assertGreater(seen, 0)


class FigureHeldItemsTests(unittest.TestCase):
    """A person has two hands."""

    _MAGNITUDE = {
        "a single": 1, "a pair of": 2, "three": 3, "four": 4,
        "six": 6, "eight": 8, "a dozen": 12,
    }

    def test_a_figure_never_speaks_more_than_two_held_items(self) -> None:
        seen = 0
        for seed, level, text, document in _sweep(
            seeds=250, widgets={"entity1_kind": "spacefarer"}
        ):
            for entity in _entities(document):
                if entity.kind != "spacefarer":
                    continue
                total = sum(
                    self._MAGNITUDE.get(entity.get(name), 0)
                    for name in ("armament_count", "sensor_count")
                )
                seen += 1
                with self.subTest(seed=seed, level=level):
                    self.assertLessEqual(total, 2)
        self.assertGreater(seen, 0)


class ContextSentenceTests(unittest.TestCase):
    """The context sentence is a set of openers, not one tic."""

    _OPENERS = (
        "Beyond it,", "Beyond them,", "Behind it is", "Behind them is",
        "is visible behind", "catches the light", "The background shows",
        "In the distance,", "Further back,", "Far behind",
    )

    def test_the_context_sentence_varies_across_openers(self) -> None:
        openers: Counter = Counter()
        spoken = 0
        for seed, level, text, document in _sweep(seeds=300):
            if not document.get("context"):
                continue
            spoken += 1
            for opener in self._OPENERS:
                if opener in text:
                    openers[opener] += 1
        self.assertGreaterEqual(len(openers), 6, f"only saw {openers}")
        beyond = openers.get("Beyond it,", 0) + openers.get("Beyond them,", 0)
        self.assertLessEqual(
            beyond / max(spoken, 1), 0.5, f"Beyond opener share: {openers}"
        )

    def test_a_figure_is_never_spoken_of_as_it(self) -> None:
        for seed, level, text, document in _sweep(
            seeds=200, widgets={"entity1_kind": "spacefarer"}
        ):
            if not document.get("context"):
                continue
            with self.subTest(seed=seed):
                self.assertNotIn("Beyond it,", text)


class SituationClassificationTests(unittest.TestCase):
    """Every situation declares where it can happen."""

    def test_every_situation_is_classified(self) -> None:
        values = pool_options(SCIFI_PACK, "situation")
        self.assertGreater(len(values), 0)
        for value in values:
            with self.subTest(value=value):
                self.assertTrue(is_classified(SCIFI_PACK, "situation", value))

class WiredPathCoherenceTests(unittest.TestCase):
    """The path the user actually uses: a Scene Entity wired into a slot.

    Every coherence rule in this pack measured 0 violations with the Scene
    Weaver alone and 10.5% with a Scene Entity wired in, because a wired value
    was treated as the user's choice when it was only a random draw. A gate
    exercised on one path is a gate for one path, so this sweeps all three."""

    _SEEDS = SWEEP_SEEDS

    def _violations(self, document, environment, form_stances):
        """Every entity whose form cannot hold itself up in ``environment``."""
        supported = _supported_stances(environment)
        found: list[str] = []
        for entity in _entities(document):
            stances = form_stances.get(entity.get("form"))
            if stances and not (stances & supported):
                found.append(
                    f"{entity.get('form')!r} cannot hold itself up in "
                    f"{environment!r}"
                )
        for record in document["entities"]:
            if record["index"] != 1 and record["source"] != "wired":
                continue
            kind, subkind = record.get("kind"), record.get("subkind")
            if (kind and subkind and record.get("form") is None
                    and pool_for(SCIFI_PACK, "form", {"kind": kind, "subkind": subkind})):
                found.append(f"{kind}/{subkind} has no silhouette in {environment!r}")
        return found

    def _lacks(self, document):
        """Locked-value warnings that a rule's reason had to overrule."""
        return sum(
            "which this place lacks" in w or "cannot hold itself up" in w
            for w in document["_meta"]["warnings"]
        )

    def _sweep_unwired(self, entity_count):
        form_stances = SCIFI_PACK.value_stances.get("form", {})
        seen = 0
        violations: list[str] = []
        for seed in range(self._SEEDS):
            _text, document = generate_scene(
                seed, SCIFI_PACK, entity_count=entity_count
            )
            environment = document["environment"]
            if environment is None:
                continue
            seen += sum(
                1 for e in _entities(document)
                if form_stances.get(e.get("form"))
            )
            violations.extend(self._violations(document, environment, form_stances))
        return seen, violations

    def test_the_unwired_single_entity_path_holds_every_form(self):
        seen, violations = self._sweep_unwired(1)
        self.assertGreater(seen, 0)
        self.assertFalse(violations, violations[:5])

    def test_the_unwired_three_entity_path_holds_every_form(self):
        seen, violations = self._sweep_unwired(3)
        self.assertGreater(seen, 0)
        self.assertFalse(violations, violations[:5])

    def test_the_wired_path_holds_every_form_and_raises_no_locked_warning(self):
        """The regression that hid for five rounds: a wired entity's *drawn*
        form was force-locked, so the place could not re-draw it and merely
        warned. Now the drawn value is a draw and is re-drawn to fit."""
        form_stances = SCIFI_PACK.value_stances.get("form", {})
        seen = 0
        violations: list[str] = []
        lacks = 0
        for seed in range(self._SEEDS):
            _text, payload = generate_entity(seed, SCIFI_PACK)
            if payload["fields"].get(KIND_FIELD) is None:
                continue
            _text, document = generate_scene(
                seed + 100000, SCIFI_PACK,
                wired_entities={1: payload}, entity_count=1,
            )
            environment = document["environment"]
            if environment is None:
                continue
            seen += sum(
                1 for e in _entities(document)
                if form_stances.get(e.get("form"))
            )
            violations.extend(self._violations(document, environment, form_stances))
            lacks += self._lacks(document)
        self.assertGreater(seen, 0)
        self.assertFalse(violations, violations[:5])
        # Only a value the user locked may keep a rule's reason. A drawn wired
        # value is re-drawn silently, so the wired path raises almost none.
        self.assertLess(lacks, 20, f"{lacks} locked-value warnings on the wired path")


if __name__ == "__main__":
    unittest.main()
