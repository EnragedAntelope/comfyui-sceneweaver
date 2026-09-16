"""Todo 12 -- constraint rules resolved against the real schema and pools.

A constraint rule is a string pointing at another string. Nothing in the type
system connects either end to the pack, so every way of getting one wrong is
silent:

* a **field** that is not a real address -- the rule simply never matches, and
  the scene keeps producing the incoherence it was written to remove;
* a **value** that is not a real option -- same outcome, from a typo;
* an **excluded value** that is not in the pool it names -- the rule fires and
  removes nothing, which looks identical to working;
* a rule addressing **``entity5``**, a slot no node has.

Each of those is a rule that *never fires*, and the plan is explicit that such a
rule is deleted rather than kept: a rule nobody has watched do anything is a
comment with a dataclass around it.

The firing check is the load-bearing one. It resolves each rule's excluded
values against the pool they would actually be drawn from -- under the *kind*
the trigger implies, since almost every pool is kind-scoped -- and fails if the
intersection is empty.
"""
from __future__ import annotations

import unittest

from data.genre import (
    ENVIRONMENT_FIELD,
    FIRST_ENDPOINT,
    KIND_FIELD,
    RELATION_ANY,
    RELATION_ANY_POSITION,
    RULE_EXCLUDE,
    RULE_REQUIRE,
    SCENE_NODE_SLOTS,
    SECOND_ENDPOINT,
    SITUATION_FIELD,
    ConstraintRule,
    address_field,
    bind_address,
    build_field_definitions,
    constraint_address_space,
    is_slot_wildcard,
    pool_for,
    relation_pairs,
)
from data.scifi import ENVIRONMENT_BANDS, SCIFI_PACK, TRAIT_CONFLICTS, VALUE_TRAITS
from engine.scene import generate_entity, generate_scene

#: The address space a rule may name, and the pack field behind each address.
#:
#: This is **wider than the scene node's widget list** and has to be: slots 2-4
#: carry only the brief fields as widgets, so ``entity3.material`` is not a
#: widget -- but wiring a Scene Entity into slot 3 promotes it to the full
#: morphology at run time, which is exactly when a material rule needs to reach
#: it. Validating against the widget list instead was the first thing this file
#: caught, and it would have deleted twelve correct rules.
ADDRESS_SPACE = constraint_address_space(SCIFI_PACK, SCENE_NODE_SLOTS)
PATH_TO_FIELD = {address: address_field(address) for address in ADDRESS_SPACE}
SLOTS = tuple(range(1, SCENE_NODE_SLOTS + 1))

#: What the scene node actually draws, for the narrower assertion below.
WIDGET_PATHS = {
    definition.path
    for definition in build_field_definitions(SCIFI_PACK, SCENE_NODE_SLOTS).values()
}


def _resolved_paths(address: str) -> tuple[str, ...]:
    """Every concrete widget path an address selects."""
    if is_slot_wildcard(address):
        return tuple(bind_address(address, slot) for slot in SLOTS)
    if address in (RELATION_ANY, RELATION_ANY_POSITION) or address.startswith(
        (FIRST_ENDPOINT + ".", SECOND_ENDPOINT + ".")
    ):
        return tuple(bind_address(address, None, pair) for pair in relation_pairs(SCENE_NODE_SLOTS))
    return (address,)


def _kinds_that_can_hold(field: str, *values: str) -> tuple[str, ...]:
    """Which kinds a trigger value is reachable under.

    ``kind`` is its own answer; a ``subkind`` names the kinds whose pool contains
    it; anything else is scene-wide and matches every kind. This is what lets the
    firing check look up an excluded value in the pool it is really drawn from
    rather than in the union of all of them, which would pass on a value that is
    only legal under some other kind.
    """
    if field == "kind":
        return tuple(values)
    if field == "subkind":
        return tuple(
            kind
            for kind in SCIFI_PACK.kinds
            if any(v in pool_for(SCIFI_PACK, "subkind", kind) for v in values)
        )
    return SCIFI_PACK.kinds


class AddressResolutionTests(unittest.TestCase):
    def test_every_rule_addresses_a_real_field_of_a_real_slot(self) -> None:
        for rule in SCIFI_PACK.all_constraints:
            for address in (rule.field, rule.excludes_field, rule.requires_field):
                if address is None:
                    continue
                for path in _resolved_paths(address):
                    with self.subTest(rule=rule.reason, path=path):
                        self.assertIn(path, ADDRESS_SPACE)

    def test_every_trigger_is_something_the_user_can_actually_set(self) -> None:
        """The narrower half. A rule may *act on* a promoted slot's field that
        has no widget, but nothing could ever *trigger* a rule whose own field
        is unreachable from both the node face and a wired entity -- and slot
        1's widgets plus the environment are what the scene node exposes."""
        for rule in SCIFI_PACK.all_constraints:
            trigger_paths = _resolved_paths(rule.field)
            with self.subTest(rule=rule.reason, field=rule.field):
                self.assertTrue(set(trigger_paths) & WIDGET_PATHS)

    def test_the_address_space_is_wider_than_the_widget_set(self) -> None:
        """Pins the distinction the resolution check turns on, so a later
        session cannot collapse the two and quietly delete the rules that only
        apply to a wired slot."""
        self.assertLess(len(WIDGET_PATHS), len(ADDRESS_SPACE))
        self.assertNotIn("entity3.material", WIDGET_PATHS)
        self.assertIn("entity3.material", ADDRESS_SPACE)
        self.assertIn("entity3.kind", WIDGET_PATHS)
        self.assertIn(f"entity4.{SITUATION_FIELD}", ADDRESS_SPACE)

    def test_every_trigger_value_is_a_real_option(self) -> None:
        for rule in SCIFI_PACK.all_constraints:
            field = PATH_TO_FIELD[_resolved_paths(rule.field)[0]]
            reachable = {
                option
                for key in (None, *SCIFI_PACK.pools.get(field, {}))
                for option in pool_for(SCIFI_PACK, field, key)
            }
            for trigger in rule.triggers:
                with self.subTest(rule=rule.reason, field=field, value=trigger):
                    self.assertIn(trigger, reachable)

    def test_a_rule_naming_a_fifth_slot_is_rejected(self) -> None:
        """Slot 5 is syntactically addressable -- the address regex allows any
        slot number, and Todo 3 pinned that deliberately as a separate concern.
        Resolution is where it is caught: the scene has four slots, so nothing
        in the address space begins with ``entity5``."""
        rogue = ConstraintRule(
            type=RULE_EXCLUDE,
            field="entity5.kind",
            value="starship",
            excludes_field="entity5.form",
            excludes_values=("saucer hull",),
            reason="addresses a slot no node has",
        )
        self.assertNotIn(rogue.field, ADDRESS_SPACE)
        self.assertNotIn(rogue.excludes_field, ADDRESS_SPACE)
        self.assertFalse([a for a in ADDRESS_SPACE if a.startswith("entity5")])
        for slot in SLOTS:
            self.assertIn(bind_address("entity*.kind", slot), ADDRESS_SPACE)

    def test_binding_a_wildcard_needs_a_slot(self) -> None:
        with self.assertRaises(ValueError):
            bind_address("entity*.kind")
        self.assertEqual(bind_address("entity*.scale", 3), "entity3.scale")
        self.assertEqual(bind_address("environment", 3), "environment")


def _target_field(rule) -> str:
    """The pack field a rule acts on (its exclusion or requirement target)."""
    target = rule.excludes_field if rule.type == RULE_EXCLUDE else rule.requires_field
    return PATH_TO_FIELD[_resolved_paths(target)[0]]


def _named_values(rule) -> set[str]:
    """The values a rule names: an exclude's list, or a require's allowed set."""
    if rule.type == RULE_EXCLUDE:
        return set(rule.excludes_values)
    return set(rule.requires_values) if rule.requires_values else {rule.requires_value}


def _drawable_values(field: str) -> set[str]:
    """Every value ``field`` can draw, over kinds, subkinds and environments.

    A scene field scoped on ``environment`` (``context``) draws nothing under
    a kind scope, so the environment scopes are what reach it."""
    values: set[str] = set()
    for kind in SCIFI_PACK.kinds:
        scopes = [{KIND_FIELD: kind}]
        for subkind in pool_for(SCIFI_PACK, "subkind", kind):
            scopes.append({KIND_FIELD: kind, "subkind": subkind})
        for scope in scopes:
            values.update(pool_for(SCIFI_PACK, field, scope))
    for environment in pool_for(SCIFI_PACK, ENVIRONMENT_FIELD):
        values.update(pool_for(SCIFI_PACK, field, {ENVIRONMENT_FIELD: environment}))
    # ``None`` reads the ``_default`` pool, which is drawable and not the union
    # of the per-kind ones: a wired foreign-genre entity resolves through it.
    values.update(pool_for(SCIFI_PACK, field, None))
    return values


class RuleFiringTests(unittest.TestCase):
    """A rule that removes nothing is deleted, not kept."""

    def test_every_rule_can_actually_remove_something(self) -> None:
        for rule in SCIFI_PACK.all_constraints:
            trigger_field = PATH_TO_FIELD[_resolved_paths(rule.field)[0]]
            kinds = _kinds_that_can_hold(trigger_field, *rule.triggers)
            with self.subTest(reason=rule.reason):
                self.assertTrue(kinds, "the trigger value is reachable under no kind")
                drawable = _drawable_values(_target_field(rule))
                removed = (
                    _named_values(rule) & drawable
                    if rule.type == RULE_EXCLUDE
                    else drawable - _named_values(rule)
                )
                self.assertTrue(removed, "removes nothing that can be drawn -- delete it")

    def test_no_rule_names_a_value_that_is_not_in_the_pool(self) -> None:
        # The trait vocabulary crosses kinds -- a raider's hostile-act rule
        # names situations that live on other kinds -- so the guard is the
        # global union: it catches a typo, not a value that is legal elsewhere.
        for rule in SCIFI_PACK.all_constraints:
            drawable = _drawable_values(_target_field(rule))
            for value in _named_values(rule):
                with self.subTest(reason=rule.reason, value=value):
                    self.assertIn(value, drawable)

    def test_no_rule_leaves_a_field_with_a_single_forced_value(self) -> None:
        for rule in SCIFI_PACK.all_constraints:
            if rule.type == RULE_REQUIRE and rule.requires_field in (
                FIRST_ENDPOINT + ".kind",
                SECOND_ENDPOINT + ".kind",
            ):
                # A relation role legitimately forces an endpoint kind
                # ("only a starship docks at a station"); that is the point
                # of the vocabulary, not the accident this guard catches.
                continue
            trigger_field = PATH_TO_FIELD[_resolved_paths(rule.field)[0]]
            for kind in _kinds_that_can_hold(trigger_field, *rule.triggers):
                pool = set(pool_for(SCIFI_PACK, _target_field(rule), kind))
                named = _named_values(rule)
                if rule.type == RULE_EXCLUDE and not (pool & named):
                    # The rule removes nothing here, so it cannot be what left
                    # the field with one value; a cap in the data did, and that
                    # is the data's business, not the rule's.
                    continue
                remaining = (
                    pool - named
                    if rule.type == RULE_EXCLUDE
                    else named
                )
                with self.subTest(reason=rule.reason, kind=kind):
                    self.assertNotEqual(len(remaining), 1)


class RuleShapeTests(unittest.TestCase):
    def test_every_require_rule_is_multi_valued(self) -> None:
        """A single-valued requirement cannot be expressed in this pack's data;
        a require rule must name a set of allowed values (todo 8)."""
        for rule in SCIFI_PACK.all_constraints:
            if rule.type == RULE_REQUIRE:
                with self.subTest(rule=rule.reason):
                    self.assertTrue(rule.requires_values)
                    self.assertIsNone(rule.requires_value)

    def test_every_rule_carries_a_reason(self) -> None:
        """The reason is not decoration: it is the text of the warning the user
        gets when a value they locked wins over a rule."""
        for rule in SCIFI_PACK.all_constraints:
            with self.subTest(field=rule.field, values=rule.triggers):
                self.assertTrue(rule.reason.strip())

    def test_a_reason_is_warning_text_and_may_negate(self) -> None:
        """The one deliberate exemption from the never-negate rule, pinned so
        nobody re-derives it. A reason is shown to the user when a locked value
        beats a rule; it never reaches the prompt, and a warning forbidden from
        saying "a star is not made of rock" is a worse warning. The rule bites on
        pool values, which ``test_content_tags`` checks.
        """
        reasons = [rule.reason for rule in SCIFI_PACK.all_constraints]
        self.assertTrue(any(" not " in f" {reason} " for reason in reasons))
        for name, by_kind in SCIFI_PACK.pools.items():
            for values in by_kind.values():
                for value in values:
                    with self.subTest(field=name, value=value):
                        self.assertNotIn(" not ", f" {value} ")

    def test_the_scale_rules_exist_and_cover_the_whole_interior_band(self) -> None:
        """The rules the previous plan missed. Read from the ladder rather than
        counted, so a new interior environment is covered or this fails."""
        from data.scifi import ENVIRONMENT_BANDS

        covered = {
            trigger
            for rule in SCIFI_PACK.constraints
            if rule.field == "environment" and rule.excludes_field == "entity*.scale"
            for trigger in rule.triggers
        }
        self.assertEqual(covered, set(ENVIRONMENT_BANDS["interior"]))

    def test_a_celestial_body_is_neither_indoors_nor_tiny(self) -> None:
        from data.scifi import KIND_POOLS

        # "not indoors" and "not in a cloud deck" are now the band-scoped kind
        # pool, not a rule: a world is a backdrop, so no band that puts it in a
        # room or a cloud can hold it.
        self.assertNotIn("celestial body", KIND_POOLS["interior"])
        self.assertNotIn("celestial body", KIND_POOLS["cloud layer"])
        self.assertNotIn("tiny", pool_for(SCIFI_PACK, "scale", "celestial body"))

    def test_both_halves_of_the_armament_pair_are_absent_together(self) -> None:
        """A world and a relic carry no guns -- and no count of guns.

        Asserted end to end rather than against the rule table. It used to be a
        pair of exclusion rules per kind; it is now one ``omits`` on each of the
        two archetypes, with the budget's orphan pass taking the count. Checking
        the *rules* would have gone green on a pack where they were present and
        never fired, and it would have to be rewritten again the next time the
        mechanism moves. What must stay true is that neither half reaches a
        scene, so that is what this asks.
        """
        for kind in ("celestial body", "alien artifact"):
            seen = 0
            for seed in range(120):
                _text, document = generate_scene(
                    seed, SCIFI_PACK,
                    widgets={"entity1_kind": kind},
                )
                for record in document["entities"]:
                    if record.get("kind") != kind:
                        continue
                    seen += 1
                    with self.subTest(kind=kind, seed=seed):
                        self.assertIsNone(record.get("armament"))
                        self.assertIsNone(record.get("armament_count"))
            self.assertGreater(seen, 0, f"no {kind} was ever generated")


class LivingSubjectCoherenceTests(unittest.TestCase):
    """A living subject is not a manufactured one.

    These rules exist because of a measurement, not a reading: `condition` and
    `scale` are universal pools by design, every individual draw was legal, and
    nothing failed -- while a machine-only condition was landing on more than
    half of every `person or spacefarer` slot ("a derelict captain", "a
    half-built medic"). A distribution defect has no single-scene symptom, so
    the guard has to be a sweep rather than a spot check.

    Asserted over generated scenes rather than over the rule table: a rule can
    be present and still not fire, which is the failure this suite's own
    `test_every_rule_can_actually_remove_something` was written for.
    """

    #: The exclusion is read off the pack rather than restated, so this cannot
    #: drift from the rules it is guarding.
    def _excluded(self, kind: str, field: str) -> set[str]:
        """Values ``kind`` may not draw for ``field``, as the kind-scoped pool leaves
        out. Read off the pools rather than the rules: condition and scale stopped
        being rule-constrained when they became kind-scoped pools."""
        return set(pool_for(SCIFI_PACK, field, None)) - set(pool_for(SCIFI_PACK, field, kind))

    def test_a_living_subject_never_draws_a_manufactured_condition(self) -> None:
        forbidden = {
            kind: self._excluded(kind, "condition")
            for kind in ("spacefarer", "alien creature")
        }
        for kind, values in forbidden.items():
            self.assertTrue(values, f"no condition rule for {kind!r}")
        for seed in range(400):
            _, document = generate_scene(
                seed=seed, pack=SCIFI_PACK,             )
            for entity in document["entities"]:
                banned = forbidden.get(entity["kind"])
                if banned is None:
                    continue
                with self.subTest(seed=seed, kind=entity["kind"]):
                    self.assertNotIn(entity["condition"], banned)

    def test_named_nonsense_pairs_never_appear(self) -> None:
        """Ground truth written out literally, on purpose.

        The sweep above reads its forbidden set off the pack, which keeps it
        from drifting -- but it also means an empty rule table makes it
        vacuous. This one names the pairs, so it fails whether the rules were
        deleted, stopped firing, or never reached the engine at all.
        """
        nonsense = {
            "spacefarer": ("derelict", "half-built", "mothballed",
                                     "under construction", "salvaged and rebuilt"),
            "alien creature": ("under construction", "half-built", "derelict",
                                  "freshly commissioned"),
        }
        for seed in range(400):
            _, document = generate_scene(
                seed=seed, pack=SCIFI_PACK,             )
            for entity in document["entities"]:
                for value in nonsense.get(entity["kind"], ()):
                    self.assertNotEqual(
                        entity["condition"], value,
                        f"seed {seed}: {entity['kind']!r} drew {value!r}",
                    )

    def test_a_person_is_person_sized(self) -> None:
        banned = self._excluded("spacefarer", "scale")
        self.assertTrue(banned)
        for seed in range(400):
            _, document = generate_scene(
                seed=seed, pack=SCIFI_PACK,             )
            for entity in document["entities"]:
                if entity["kind"] == "spacefarer":
                    self.assertNotIn(entity["scale"], banned, f"seed {seed}")

    def test_a_creature_may_still_be_colossal(self) -> None:
        """The counterpart assertion, and the reason the scale rule names one
        kind rather than both: a colossal creature is a kaiju, which the pack
        should be able to make. A rule that quietly banned it would pass the
        test above and make the pack worse."""
        seen = set()
        for seed in range(400):
            _, document = generate_scene(
                seed=seed, pack=SCIFI_PACK,             )
            for entity in document["entities"]:
                if entity["kind"] == "alien creature":
                    seen.add(entity["scale"])
        self.assertTrue(
            seen & {"massive", "colossal", "planetary"},
            "no large creature was drawn in 400 seeds -- the kaiju path is gone",
        )

    def test_the_condition_pool_is_not_emptied_for_a_living_kind(self) -> None:
        """A partial cull concentrates weight on the survivors; an total one
        leaves a widget that can only say None. Neither is what was intended."""
        for kind in ("spacefarer", "alien creature"):
            remaining = set(pool_for(SCIFI_PACK, "condition", kind)) - self._excluded(
                kind, "condition"
            )
            with self.subTest(kind=kind):
                self.assertGreaterEqual(len(remaining), 5, sorted(remaining))


class RelationCoherenceTests(unittest.TestCase):
    """todo 8 -- endpoint-aware relation constraints actually fire."""

    _IMMOBILE = {
        "celestial body", "space station", "spacefarer",
        "alien artifact", "wreck",
    }

    def _relation_widgets(self, with_positions: bool) -> dict[str, str]:
        widgets = {f"entity{n}_kind": "Random" for n in range(1, 5)}
        widgets.update(
            {f"relation_{f}_{s}": "Random" for f in range(1, 5) for s in range(f + 1, 5)}
        )
        if with_positions:
            widgets.update(
                {f"relation_{f}_{s}_position": "Random" for f in range(1, 5) for s in range(f + 1, 5)}
            )
        return widgets

    def test_orbiting_never_co_occurs_with_an_immobile_first_endpoint(self) -> None:
        for seed in range(200):
            _, document = generate_scene(
                seed, SCIFI_PACK, widgets=self._relation_widgets(False)
            )
            occupied = {e["index"]: e["kind"] for e in document["entities"]}
            for relation in document["relations"]:
                if relation["value"] != "orbiting":
                    continue
                first = relation["endpoints"][0]
                with self.subTest(seed=seed, endpoints=relation["endpoints"]):
                    self.assertNotIn(occupied[first], self._IMMOBILE)

    def test_from_behind_never_co_occurs_with_orbiting_or_docked(self) -> None:
        for seed in range(200):
            _, document = generate_scene(
                seed, SCIFI_PACK, widgets=self._relation_widgets(True)
            )
            for relation in document["relations"]:
                if relation["value"] in ("orbiting", "docked at"):
                    with self.subTest(seed=seed, relation=relation["value"]):
                        self.assertNotEqual(relation["position"], "from behind")

class EnvironmentBandTests(unittest.TestCase):
    """The subject and the action have to fit the place.

    Every scene used to draw its environment, its entities and their situations
    independently, and produced things like "set in a domed colony concourse ... a
    massive corroded submersible ... taking hits from a ridge line" -- three
    legal draws that cannot all be true. ``ENVIRONMENT_BANDS`` had existed the
    whole time and nothing read it.

    Read off the pack rather than restated, so this cannot drift from the rules
    it guards; the literal named pairs below are the guard against the rules
    being deleted and this going vacuously green.
    """

    def _band_of(self) -> "dict[str, str]":
        return {
            value: band
            for band, values in SCIFI_PACK.environment_bands.items()
            for value in values
        }

    def _scenes(self, seeds: int = 300):
        band_of = self._band_of()
        widgets = {f"entity{n}_kind": "Random" for n in range(1, 5)}
        for seed in range(seeds):
            _text, document = generate_scene(seed, SCIFI_PACK, widgets=widgets)
            environment = document["environment"]
            if not environment:
                continue
            yield seed, band_of[environment], document

    def test_every_environment_is_in_exactly_one_band(self) -> None:
        """The pack refuses to construct otherwise; this states why it matters.

        An unbanded environment escapes every rule written against a band --
        silently, and only on the seeds that draw it.
        """
        pool = set(pool_for(SCIFI_PACK, "environment"))
        banded = [v for values in SCIFI_PACK.environment_bands.values() for v in values]
        self.assertEqual(sorted(banded), sorted(set(banded)))
        self.assertEqual(set(banded), pool)

    def test_a_ground_vehicle_never_appears_off_the_ground(self) -> None:
        """A rover needs deep space or orbit to stand on nothing at all."""
        for seed, band, document in self._scenes():
            if band not in ("deep space", "orbit"):
                continue
            for entity in document["entities"]:
                with self.subTest(seed=seed, band=band):
                    self.assertNotEqual(entity["kind"], "surface vehicle")

    def test_a_world_is_never_indoors_or_in_a_cloud_deck(self) -> None:
        for seed, band, document in self._scenes():
            if band not in ("interior", "cloud layer"):
                continue
            for entity in document["entities"]:
                with self.subTest(seed=seed, band=band):
                    self.assertNotEqual(entity["kind"], "celestial body")

    def test_a_locked_kind_narrows_the_environment_it_can_appear_in(self) -> None:
        """Locking a kind bans every environment whose kind pool lacks it."""
        legal = pool_for(SCIFI_PACK, "environment", None)
        holders = {
            e for e in legal
            if "surface vehicle" in pool_for(SCIFI_PACK, "kind", {"environment": e})
        }
        seen = 0
        for seed in range(120):
            _, document = generate_scene(
                seed, SCIFI_PACK, widgets={"entity1_kind": "surface vehicle"}
            )
            seen += 1
            with self.subTest(seed=seed):
                self.assertIn(document["environment"], holders)
        self.assertGreater(seen, 0)

    #: Named literally so this fails whether the rules were deleted, stopped
    #: firing, or never reached the engine -- the same reasoning as
    #: ``test_named_nonsense_pairs_never_appear`` above.
    _NEEDS_GROUND = (
        "settling deeper into the sand",
        "taking hits from a ridge line",
        "burrowing up through fractured rock",
        "kicking up a long dust plume",
        "boring into rock with a heavy rock drill",
    )
    _NEEDS_OPEN_SPACE = (
        "drifting slowly through the void",
        "fleeing through an asteroid field",
        "drifting through a debris field",
    )

    def test_a_ground_action_never_happens_off_the_ground(self) -> None:
        for seed, band, document in self._scenes():
            if band not in ("deep space", "orbit", "cloud layer", "interior"):
                continue
            for entity in document["entities"]:
                with self.subTest(seed=seed, band=band):
                    self.assertNotIn(entity["situation"], self._NEEDS_GROUND)

    def test_an_open_space_action_never_happens_enclosed(self) -> None:
        for seed, band, document in self._scenes():
            if band not in ("cloud layer", "planetary surface", "interior"):
                continue
            for entity in document["entities"]:
                with self.subTest(seed=seed, band=band):
                    self.assertNotIn(entity["situation"], self._NEEDS_OPEN_SPACE)

    def test_the_bands_do_not_empty_the_situation_pool(self) -> None:
        """A band that forbade every situation would leave entities standing
        still, which is worse than the incoherence this replaced."""
        silent = 0
        total = 0
        for _seed, _band, document in self._scenes(seeds=200):
            for entity in document["entities"]:
                total += 1
                if entity["situation"] is None:
                    silent += 1
        self.assertGreater(total, 0)
        self.assertLess(silent / total, 0.05, f"{silent} of {total} slots do nothing")



class KindRescopeTests(unittest.TestCase):
    """A rule that re-draws a ``kind`` must re-draw what that kind scoped.

    ``kind`` is the control token every other pool on a slot is scoped by, so
    changing it invalidates everything already drawn under the old one. The
    constraint pass used to change it and leave the rest standing, which
    produced a celestial body whose subkind was "sand crawler" and which had a
    rear ramp -- every field individually legal, none of them legal together.

    Swept rather than spot-checked: it only happens on the seeds where a rule
    actually fires on a kind, and it produced no warning and no failure.
    """

    _SCOPED = (
        "subkind", "form", "material", "markings", "surface_detail",
        "appendages", "emitters", "armament", "sensors", "aperture", "extras",
    )

    def test_every_field_belongs_to_the_scope_chain_it_was_drawn_under(self) -> None:
        """A field resolves through its declared scope chain, so the value must
        be in the pool *that chain* selects -- not merely the kind pool. The
        component fields scope on ``subkind`` first, so a black hole's
        appendages come from the singularity pool and not the celestial one."""
        checked = 0
        for count in (1, 2, 4):
            for seed in range(150):
                _text, document = generate_scene(
                    seed, SCIFI_PACK, entity_count=count
                )
                for record in document["entities"]:
                    kind = record["kind"]
                    checked += 1
                    for name in self._SCOPED:
                        value = record.get(name)
                        if value is None:
                            continue
                        with self.subTest(seed=seed, kind=kind, field=name):
                            scope = {
                                control: record.get(control)
                                for control in SCIFI_PACK.entity_fields[name].scope
                            }
                            self.assertIn(value, pool_for(SCIFI_PACK, name, scope))
        self.assertGreater(checked, 0)

    def test_the_situation_belongs_to_the_kind_too(self) -> None:
        """``situation`` is a scene field and kind-scoped: a station cannot flee
        and a planet cannot board anything."""
        for count in (1, 4):
            for seed in range(150):
                _text, document = generate_scene(
                    seed, SCIFI_PACK, entity_count=count
                )
                for record in document["entities"]:
                    situation = record.get("situation")
                    if situation is None:
                        continue
                    scope = {"kind": record["kind"]}
                    if record.get("subkind") is not None:
                        scope["subkind"] = record["subkind"]
                    allowed = set(pool_for(SCIFI_PACK, SITUATION_FIELD, scope))
                    allowed |= set(pool_for(SCIFI_PACK, SITUATION_FIELD, None))
                    with self.subTest(seed=seed, kind=record["kind"]):
                        self.assertIn(situation, allowed)


class WiredKindEnvironmentTests(unittest.TestCase):
    """A wired entity's kind must not be contradicted by the place it is in.

    The environment is drawn first, before any slot, so a wire is the more
    explicit statement about what is in the scene and the place adapts to it."""

    def test_a_wired_kind_never_lands_in_a_band_that_excludes_it(self) -> None:
        interiors = set(ENVIRONMENT_BANDS["interior"])
        _, payload = generate_entity(7, SCIFI_PACK, widgets={"kind": "starship"})
        for seed in range(120):
            _, document = generate_scene(
                seed, SCIFI_PACK, wired_entities={1: payload}, entity_count=1
            )
            with self.subTest(seed=seed):
                self.assertNotIn(document["environment"], interiors)


class TraitConflictTests(unittest.TestCase):
    """Two traits that cannot both be true of one entity must never co-occur.

    Driven off the pack's own tables, so a trait added to a second field -- or a
    conflict added later -- is covered without editing this test."""

    def _values_with(self, field: str, trait: str) -> set[str]:
        return {
            value
            for value, traits in VALUE_TRAITS.get(field, {}).items()
            if trait in traits
        }

    def test_no_entity_carries_both_sides_of_a_trait_conflict(self) -> None:
        for trigger_trait, target_trait in TRAIT_CONFLICTS:
            for trigger_field in VALUE_TRAITS:
                triggers = self._values_with(trigger_field, trigger_trait)
                if not triggers:
                    continue
                for target_field in VALUE_TRAITS:
                    if target_field == trigger_field:
                        continue
                    targets = self._values_with(target_field, target_trait)
                    if not targets:
                        continue
                    for seed in range(50):
                        _, document = generate_scene(seed, SCIFI_PACK, entity_count=1)
                        for record in document["entities"]:
                            with self.subTest(
                                seed=seed,
                                trigger=trigger_field,
                                target=target_field,
                            ):
                                self.assertFalse(
                                    record.get(trigger_field) in triggers
                                    and record.get(target_field) in targets,
                                    f"{record.get(trigger_field)!r} and "
                                    f"{record.get(target_field)!r} cannot both hold",
                                )

    def test_a_small_entity_carries_no_collective_quantifier(self) -> None:
        arrays = {"a dozen", "rows of", "banks of", "a constellation of"}
        count_fields = (
            "appendage_count", "emitter_count", "armament_count", "sensor_count",
        )
        for seed in range(200):
            _, document = generate_scene(seed, SCIFI_PACK, entity_count=1)
            for record in document["entities"]:
                if record.get("scale") not in ("tiny", "small", "medium"):
                    continue
                for name in count_fields:
                    with self.subTest(seed=seed, field=name):
                        self.assertNotIn(record.get(name), arrays)

if __name__ == "__main__":  # pragma: no cover
    unittest.main()
