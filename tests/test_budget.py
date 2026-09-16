"""Todo 15 -- the detail budget.

The assertion this file exists for is ``test_a_cut_field_is_none_not_hidden``:
a budget-cut field must be ``None`` in the data, not merely absent from the
prose. Everything else here is the arithmetic around it.

The allowance is a **whole-scene** quantity: ``ALLOWANCE_BY_COUNT`` says how
much each occupied slot gets given how many are occupied, so a scene does not
gain total description by gaining subjects.
"""
from __future__ import annotations

import random
import unittest

from data.genre import (
    SITUATION_FIELD,
    Archetype,
    FieldSpec,
    GenrePack,
    ProseSpec,
    pattern_covers,
    pattern_slots,
)
from data.scifi import SCIFI_PACK
from engine.budget import (
    ALLOWANCE_BY_COUNT,
    allowance_for,
    apply_budget,
    count_tokens,
)

#: The single-entity hero allowance -- what most of the arithmetic below is
#: written against. Read from the table rather than restated, so a change to
#: the table cannot leave these tests asserting a number nothing uses.
HERO = ALLOWANCE_BY_COUNT[1][0]
#: The head-phrase modifier fields. They are two words in front of the noun,
#: not clauses, so they never spend the allowance and are always spoken.
HEAD_MODIFIERS = frozenset({"scale", "condition"})
from engine.prose import render_entity
from engine.resolution import ResolvedEntity

FULL = {
    "kind": "starship",
    "subkind": "heavy freighter",
    "scale": "large",
    "condition": "battle-scarred",
    "form": "needle hull",
    "material": "titanium alloy",
    "primary_color": "gunmetal grey",
    "accent_color": "oxide red",
    "markings": "hazard chevrons",
    "surface_detail": "pitted and scarred",
    "appendages": "docking spar",
    "appendage_count": "four",
    "emitters": "ion thruster",
    "emitter_count": "six",
    "emitter_color": "cyan",
    "armament": "point-defence turret",
    "armament_count": "a pair of",
    "sensors": "phased array panel",
    "sensor_count": "three",
    "aperture": "launch bay",
    "extras": "cargo pod",
}


def spoken(values: dict) -> set[str]:
    """The clause-heading fields that still have a value."""
    return {
        name
        for name, spec in SCIFI_PACK.entity_fields.items()
        if spec.renders_with is None and values.get(name) is not None
    }


class AllowanceTests(unittest.TestCase):
    def test_the_first_slot_takes_the_head_of_its_row(self) -> None:
        for occupied, row in ALLOWANCE_BY_COUNT.items():
            with self.subTest(occupied=occupied):
                self.assertEqual(allowance_for(occupied, 1), row[0])

    def test_a_later_slot_never_gets_more_than_an_earlier_one(self) -> None:
        for occupied, row in ALLOWANCE_BY_COUNT.items():
            with self.subTest(occupied=occupied):
                self.assertEqual(list(row), sorted(row, reverse=True))

    def test_a_fuller_scene_describes_each_subject_less(self) -> None:
        """Detail is spent per scene, not per slot. A four-entity scene that
        described each subject as fully as a one-entity scene would be four
        half-drawn things, which is the mush the module exists to prevent."""
        heads = [ALLOWANCE_BY_COUNT[n][0] for n in sorted(ALLOWANCE_BY_COUNT)]
        self.assertEqual(heads, sorted(heads, reverse=True))

    def test_no_slot_is_reduced_to_a_bare_name(self) -> None:
        """Three details is still a described thing. A slot dropped to zero
        would make wiring a Scene Entity into it pointless."""
        for occupied, row in ALLOWANCE_BY_COUNT.items():
            for position, allowance in enumerate(row, start=1):
                with self.subTest(occupied=occupied, position=position):
                    self.assertGreaterEqual(allowance, 3)

    def test_an_out_of_range_scene_still_budgets(self) -> None:
        """A pack with more slots than the table anticipates must budget rather
        than raise -- the slot count is a pack decision, this table is not."""
        largest = ALLOWANCE_BY_COUNT[max(ALLOWANCE_BY_COUNT)]
        self.assertEqual(allowance_for(99, 1), largest[0])
        self.assertEqual(allowance_for(99, 99), largest[-1])

    def test_every_archetype_can_name_and_act_on_its_entity(self) -> None:
        """The guard the old ``max_clauses`` capacity check played.

        A plan that could not voice the situation would leave the entity
        standing still, and one that could not name the subject would describe
        it entirely by pronoun. The coverage validator enforces the stronger
        form at construction; this is the budget-side reminder."""
        for name, archetype in SCIFI_PACK.archetypes.items():
            plan = archetype.sentences or SCIFI_PACK.prose.entity_sentences
            with self.subTest(archetype=name):
                self.assertTrue(plan)
                self.assertTrue(any("subject" in pattern_slots(p) for p in plan))
                self.assertTrue(any(pattern_covers(p, SITUATION_FIELD) for p in plan))



class CutTests(unittest.TestCase):
    def test_a_cut_field_is_none_not_hidden(self) -> None:
        """The rule the module exists for. A drawn-then-discarded value in the
        JSON promises the image a detail it was never asked for."""
        result = apply_budget(SCIFI_PACK, FULL, budget=HERO)
        cut = {n for n in spoken(FULL) if n not in spoken(result)}
        self.assertTrue(cut)
        for name in cut:
            with self.subTest(name=name):
                self.assertIsNone(result[name])
                self.assertIn(name, result)

    def test_head_phrase_modifiers_are_never_priced(self) -> None:
        """``scale`` and ``condition`` are two words in front of the noun, not
        clauses of their own, so they are drawn every render whatever the
        allowance is -- which is what stops them vanishing at random."""
        result = apply_budget(SCIFI_PACK, FULL, budget=1)
        self.assertIsNotNone(result["scale"])
        self.assertIsNotNone(result["condition"])

    def test_the_budget_is_the_hero_allowance_of_optional_fields(self) -> None:
        result = apply_budget(SCIFI_PACK, FULL, budget=HERO)
        self.assertEqual(len(spoken(result) - {"kind"} - HEAD_MODIFIERS), HERO)

    def test_the_kind_is_never_cut(self) -> None:
        result = apply_budget(SCIFI_PACK, FULL, budget=HERO)
        self.assertEqual(result["kind"], "starship")

    def test_no_cap_renders_everything(self) -> None:
        result = apply_budget(SCIFI_PACK, FULL)
        self.assertEqual(result, dict(FULL))

    def test_a_cut_host_takes_its_companions_with_it(self) -> None:
        """A count and a glow colour ride their noun. Left behind they would be
        resolved-but-unvoiced -- the same bug from the other side."""
        result = apply_budget(SCIFI_PACK, FULL, budget=HERO)
        for host, companion in (("emitters", "emitter_count"),
                                ("emitters", "emitter_color"),
                                ("armament", "armament_count"),
                                ("sensors", "sensor_count"),
                                ("appendages", "appendage_count")):
            with self.subTest(host=host, companion=companion):
                if result[host] is None:
                    self.assertIsNone(result[companion])

    def test_a_field_that_was_already_none_stays_none(self) -> None:
        values = dict(FULL, armament=None, armament_count=None)
        result = apply_budget(SCIFI_PACK, values, budget=HERO)
        self.assertIsNone(result["armament"])


class PriorityTests(unittest.TestCase):
    def test_the_pack_priority_decides_what_survives(self) -> None:
        result = apply_budget(SCIFI_PACK, FULL, budget=HERO)
        priority = [
            name for name in SCIFI_PACK.prose.detail_priority if name not in HEAD_MODIFIERS
        ]
        priority = [
            name for name in SCIFI_PACK.prose.detail_priority if name not in HEAD_MODIFIERS
        ]
        expected = set(priority[:HERO]) | HEAD_MODIFIERS
        self.assertEqual(spoken(result) - {"kind"}, expected)

    def test_the_fixed_budget_keeps_the_fields_the_f5_gate_measures(self) -> None:
        """Silhouette and emitters are what make two seeds look different. A
        budget that dropped them would fail the point of the pack."""
        result = apply_budget(SCIFI_PACK, FULL, budget=HERO)
        for name in ("form", "emitters", "armament", "sensors"):
            with self.subTest(name=name):
                self.assertIsNotNone(result[name])

    def test_a_pack_with_no_priority_falls_back_to_clause_order(self) -> None:
        pack = GenrePack(
            slug="fixture",
            display="Fixture",
            class_suffix="Fixture",
            kinds=("thing",),
            entity_fields={
                "kind": FieldSpec(group="I", label="Kind"),
                "a_field": FieldSpec(group="I", label="A"),
                "b_field": FieldSpec(group="I", label="B"),
            },
            scene_fields={
                "environment": FieldSpec(group="S", label="E"),
                "situation": FieldSpec(group="S", label="S"),
                "relation": FieldSpec(group="R", label="R"),
                "relation_position": FieldSpec(group="R", label="Position"),
            },
            prose=ProseSpec(
                scene_order=(), entity_clause_order=("kind", "a_field", "b_field")
            ),
        )
        values = {"kind": "thing", "a_field": "one", "b_field": "two"}
        result = apply_budget(pack, values, budget=HERO)
        self.assertEqual(result, values)


class LockTests(unittest.TestCase):
    def test_a_locked_field_survives_the_budget(self) -> None:
        locked = {"extras", "markings", "accent_color"}
        result = apply_budget(
            SCIFI_PACK, FULL, budget=HERO, locked=locked
        )
        for name in locked:
            with self.subTest(name=name):
                self.assertIsNotNone(result[name])

    def test_locked_fields_spend_the_allowance(self) -> None:
        """"Remaining budget is filled by random draws" -- so a lock costs one."""
        result = apply_budget(
            SCIFI_PACK, FULL, budget=HERO, locked={"extras"}
        )
        self.assertEqual(len(spoken(result) - {"kind"} - HEAD_MODIFIERS), HERO)
        self.assertIsNotNone(result["extras"])

    def test_locking_more_than_the_budget_keeps_every_lock(self) -> None:
        locked = set(SCIFI_PACK.prose.detail_priority)
        result = apply_budget(
            SCIFI_PACK, FULL, budget=HERO, locked=locked
        )
        self.assertEqual(spoken(result) - {"kind"}, locked)

    def test_a_locked_count_protects_the_noun_it_counts(self) -> None:
        """A quantity of nothing cannot be spoken, so the lock has to reach the
        host or it silently buys nothing."""
        result = apply_budget(
            SCIFI_PACK, FULL, budget=HERO, locked={"sensor_count"}
        )
        self.assertIsNotNone(result["sensors"])
        self.assertEqual(result["sensor_count"], "three")


class WiredSlotTests(unittest.TestCase):
    def test_a_wired_slot_gets_the_same_allowance_as_slot_one(self) -> None:
        """Wiring a Scene Entity *is* the request for detail: the slot is
        promoted to the top allowance, so it reads as richly as the hero slot.
        ``engine.scene`` is what chooses that allowance; this asserts the two
        end up with the same budget rather than that ``apply_budget`` knows."""
        wired = apply_budget(SCIFI_PACK, FULL, budget=HERO, wired=True)
        hero = apply_budget(SCIFI_PACK, FULL, budget=HERO)
        self.assertEqual(spoken(wired), spoken(hero))

    def test_a_wired_slot_still_respects_the_cap(self) -> None:
        """A promotion, not an exemption. Four uncapped wired entities measure
        ~320 tokens, which is exactly the mush the control prevents."""
        result = apply_budget(SCIFI_PACK, FULL, budget=HERO, wired=True)
        self.assertEqual(len(spoken(result) - {"kind"} - HEAD_MODIFIERS), HERO)

    def test_an_unwired_supporting_slot_stays_brief(self) -> None:
        result = apply_budget(SCIFI_PACK, FULL, budget=allowance_for(4, 3))
        self.assertEqual(
            len(spoken(result) - {"kind"} - HEAD_MODIFIERS), allowance_for(4, 3)
        )


class TokenCountTests(unittest.TestCase):
    def test_a_short_phrase_counts_its_words(self) -> None:
        self.assertEqual(count_tokens("a saucer hull"), 3)

    def test_punctuation_counts(self) -> None:
        self.assertGreater(count_tokens("a saucer hull, gunmetal grey"),
                           count_tokens("a saucer hull gunmetal grey"))

    def test_a_long_word_counts_twice(self) -> None:
        """CLIP's BPE splits long words, and this approximation must not
        under-count -- a ceiling test that under-counts passes while the real
        prompt overruns."""
        self.assertGreater(count_tokens("bioluminescent"), 1)

    def test_an_empty_string_is_zero(self) -> None:
        self.assertEqual(count_tokens(""), 0)


class RenderedBudgetTests(unittest.TestCase):
    """The budget and the renderer agree: what is cut is not spoken."""

    def _render(self, slot: int = 1, budget: int | None = HERO) -> str:
        values = apply_budget(SCIFI_PACK, FULL, budget=budget)
        return render_entity(
            ResolvedEntity(index=slot, source="widgets", genre="scifi", fields=values),
            SCIFI_PACK,
        )

    def test_a_budgeted_render_is_shorter_than_no_cap(self) -> None:
        self.assertLess(
            count_tokens(self._render(budget=HERO)),
            count_tokens(self._render(budget=None)),
        )

    def test_a_cut_value_never_reaches_the_prose(self) -> None:
        values = apply_budget(SCIFI_PACK, FULL, budget=HERO)
        text = self._render()
        for name, original in FULL.items():
            if values.get(name) is None and original is not None:
                with self.subTest(name=name):
                    self.assertNotIn(original, text)


class ArchetypeBudgetTests(unittest.TestCase):
    """An archetype owns how much detail it speaks and in what order.

    A station is not a creature: the same allowance that reads as anatomy on a
    body reads as unplaceable greebles on a hull, so ``detail_cap`` lowers the
    caller's allowance and never raises it, and ``detail_priority`` states only
    what the archetype wants differently.
    """

    def _capped(self, cap: int | None) -> Archetype:
        return Archetype(head_phrase=None, detail_cap=cap)

    def test_a_cap_lowers_a_callers_allowance(self) -> None:
        values = apply_budget(SCIFI_PACK, FULL, budget=HERO, archetype=self._capped(4))
        self.assertLessEqual(len(spoken(values) - {"kind"}), 4)

    def test_a_cap_never_raises_a_callers_allowance(self) -> None:
        values = apply_budget(SCIFI_PACK, FULL, budget=3, archetype=self._capped(9))
        self.assertLessEqual(len(spoken(values) - {"kind"} - HEAD_MODIFIERS), 3)

    def test_a_cap_bounds_an_uncapped_call(self) -> None:
        """``budget=None`` means \"whatever this kind of thing speaks\", not
        \"everything\" -- which is what keeps the Scene Entity node honest."""
        values = apply_budget(SCIFI_PACK, FULL, budget=None, archetype=self._capped(5))
        self.assertLessEqual(len(spoken(values) - {"kind"}), 5)

    def test_an_archetypes_priority_is_spent_first(self) -> None:
        archetype = Archetype(head_phrase=None, detail_priority=("markings", "extras"))
        values = apply_budget(SCIFI_PACK, FULL, budget=2, archetype=archetype)
        self.assertEqual(spoken(values) - {"kind"} - HEAD_MODIFIERS, {"markings", "extras"})

    def test_unlisted_fields_still_follow_pack_order(self) -> None:
        archetype = Archetype(head_phrase=None, detail_priority=("markings",))
        values = apply_budget(SCIFI_PACK, FULL, budget=2, archetype=archetype)
        self.assertIn("markings", spoken(values))
        self.assertIn(SCIFI_PACK.prose.detail_priority[0], spoken(values))

    def test_a_locked_field_survives_a_cap(self) -> None:
        values = apply_budget(
            SCIFI_PACK, FULL, budget=1, locked={"extras"},
            archetype=self._capped(1),
        )
        self.assertIn("extras", spoken(values))

        self.assertIn("extras", spoken(values))


class RotationTests(unittest.TestCase):
    """The rotating tail: a fixed priority is a dead widget below the cap."""

    #: A shape whose core fits inside the cap with one slot left over.
    ROTATING = Archetype(
        head_phrase=None,
        detail_cap=8,
        detail_priority=("form", "material", "primary_color", "emitters"),
        detail_rotation={"extras": 1.0, "markings": 1.0, "accent_color": 1.0},
        detail_rotation_slots=1,
    )
    #: The same shape with no rotation declared.
    FIXED = Archetype(
        head_phrase=None,
        detail_cap=8,
        detail_priority=("form", "material", "primary_color", "emitters"),
    )

    def test_rng_none_keeps_the_legacy_order(self) -> None:
        """The seam fixture and every pre-round-XI caller pass no rng, so a
        declared rotation must change nothing without one."""
        self.assertEqual(
            apply_budget(SCIFI_PACK, FULL, budget=HERO, archetype=self.ROTATING),
            apply_budget(SCIFI_PACK, FULL, budget=HERO, archetype=self.FIXED),
        )

    def test_a_rotation_stays_within_the_cap_and_reaches_every_key(self) -> None:
        seen: set[str] = set()
        for seed in range(200):
            result = apply_budget(
                SCIFI_PACK, FULL, budget=HERO, archetype=self.ROTATING,
                rng=random.Random(seed),
            )
            kept = spoken(result) - {"kind"} - HEAD_MODIFIERS
            self.assertLessEqual(len(kept), self.ROTATING.detail_cap)
            seen |= kept & set(self.ROTATING.detail_rotation)
        self.assertEqual(seen, set(self.ROTATING.detail_rotation))

    def test_a_locked_rotation_field_is_always_kept(self) -> None:
        for seed in range(50):
            result = apply_budget(
                SCIFI_PACK, FULL, budget=HERO, archetype=self.ROTATING,
                locked={"extras"}, rng=random.Random(seed),
            )
            with self.subTest(seed=seed):
                self.assertIsNotNone(result["extras"])

    def test_the_core_still_precedes_the_draw(self) -> None:
        """The rotation fills the reserved slot, not the core ones."""
        for seed in range(20):
            result = apply_budget(
                SCIFI_PACK, FULL, budget=HERO, archetype=self.ROTATING,
                rng=random.Random(seed),
            )
            with self.subTest(seed=seed):
                for name in ("form", "material", "primary_color"):
                    self.assertIsNotNone(result[name])
if __name__ == "__main__":  # pragma: no cover
    unittest.main()
