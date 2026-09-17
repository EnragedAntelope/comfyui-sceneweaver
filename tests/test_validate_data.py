"""Todo 21 -- proof that ``tests/validate_data.py`` actually rejects things.

``feedback-verify-the-verifier``: a check that has never been watched fail is a
claim, not a check. A sweep reporting a scary number is suspect before the code
is, and a validator reporting *no* findings is suspect in exactly the same way.

So every check in the validator gets a planted defect here, and every planted
defect must be caught **by its own code**, not merely by "something failed" --
a rendering term that tripped the article check would leave the rendering check
unproven while the suite stayed green.

Each mutation builds a *copy* of the pack. ``GenrePack`` is frozen and shared
process-wide, so mutating pools in place would leak the planted defect into
every other test in the process.
"""
from __future__ import annotations

import dataclasses
import unittest

from data import genre as G
from data.genre import POOL_DEFAULT_KEY, ConstraintRule
from data.scifi import SCIFI_PACK
from tests.validate_data import (
    MIN_SITUATIONS_PER_KIND,
    Report,
    check_shadowed_values,
    validate,
)


def _with_pools(**changes):
    """A copy of the pack with ``field=(kind, values)`` replacements applied.

    A truncation can drop a value a vocabulary still names, so the vocabularies
    are pruned to what the mutated pools still contain -- otherwise the copy
    would fail construction on a stale declaration rather than reach the check
    under test.
    """
    pools = {name: dict(by_kind) for name, by_kind in SCIFI_PACK.pools.items()}
    for field, (kind, values) in changes.items():
        pools[field][kind] = tuple(values)
    present = {
        name: {v for values in by_kind.values() for v in values}
        for name, by_kind in pools.items()
    }
    needs = {
        field: {v: n for v, n in by_value.items() if v in present.get(field, set())}
        for field, by_value in SCIFI_PACK.value_needs.items()
    }
    traits = {
        field: {v: t for v, t in by_value.items() if v in present.get(field, set())}
        for field, by_value in SCIFI_PACK.value_traits.items()
    }
    defaults = {
        field: {key: n for key, n in by_key.items() if key in pools.get(field, {})}
        for field, by_key in SCIFI_PACK.default_needs.items()
    }
    stances = {
        field: {v: s for v, s in by_value.items() if v in present.get(field, set())}
        for field, by_value in SCIFI_PACK.value_stances.items()
    }
    return dataclasses.replace(
        SCIFI_PACK,
        pools=pools,
        value_needs=needs,
        value_traits=traits,
        default_needs=defaults,
        value_stances=stances,
    )


def _plus(field: str, value: str, kind: str = POOL_DEFAULT_KEY):
    """A copy of the pack with one extra value in one pool."""
    existing = SCIFI_PACK.pools[field].get(kind, ())
    return _with_pools(**{field: (kind, (*existing, value))})


def _without_default_need(field: str, key: str):
    """A copy of the pack with one ``default_needs`` key removed.

    A value that relied on the key for its place-need is then classified by
    nothing, which is what the coverage gate exists to catch.
    """
    defaults = {
        name: {
            pool_key: needs
            for pool_key, needs in by_key.items()
            if not (name == field and pool_key == key)
        }
        for name, by_key in SCIFI_PACK.default_needs.items()
    }
    return dataclasses.replace(SCIFI_PACK, default_needs=defaults)


def _without_stance(value: str):
    """A copy of the pack with one form's stance declaration removed."""
    stances = {
        field: dict(by_value) for field, by_value in SCIFI_PACK.value_stances.items()
    }
    del stances["form"][value]
    return dataclasses.replace(SCIFI_PACK, value_stances=stances)


def _with_added_affordances(place: str, *added: str):
    """A copy of the pack with ``added`` granted by one existing place."""
    places = {
        name: frozenset(granted)
        for name, granted in SCIFI_PACK.place_affordances.items()
    }
    places[place] = places[place] | frozenset(added)
    return dataclasses.replace(SCIFI_PACK, place_affordances=places)


def _codes(report) -> set[str]:
    """The finding codes a report carries, e.g. ``{"RENDERING"}``."""
    return {line.split(" ", 1)[0] for line in report.failures}


class TheShippedPackIsCleanTests(unittest.TestCase):
    def test_the_shipped_pack_validates(self) -> None:
        report = validate()
        self.assertEqual(
            report.failures, [], "\n".join(report.failures)
        )

    def test_the_report_carries_the_live_numbers(self) -> None:
        """The numbers no doc states, so the doc cannot go stale."""
        report = validate()
        for key in ("pool_values", "pool_fields", "constraint_rules", "count_compositions"):
            with self.subTest(key=key):
                self.assertGreater(report.numbers.get(key, 0), 0)

    def test_a_clean_report_is_ok(self) -> None:
        self.assertTrue(validate().ok)


class EveryCheckFiresTests(unittest.TestCase):
    """One planted defect per check, each caught by its own code."""

    def assertCode(self, pack, code: str) -> None:
        report = validate(pack)
        self.assertIn(
            code,
            _codes(report),
            f"the {code} check did not fire; findings were {report.failures}",
        )

    def test_an_untagged_value_in_a_tagged_pool_is_caught(self) -> None:
        self.assertCode(_plus("armament", "improvised spar", "starship"), "TAG")

    def test_a_rule_naming_a_fifth_slot_is_caught(self) -> None:
        rule = ConstraintRule(
            type="exclude",
            field="entity5.kind",
            value="starship",
            excludes_field="entity5.scale",
            excludes_values=("tiny",),
            reason="planted",
        )
        pack = dataclasses.replace(SCIFI_PACK, constraints=(*SCIFI_PACK.constraints, rule))
        self.assertCode(pack, "RULE")

    def test_a_rule_naming_a_value_that_is_not_an_option_is_caught(self) -> None:
        rule = ConstraintRule(
            type="exclude",
            field="entity*.kind",
            value="dragon",
            excludes_field="entity*.scale",
            excludes_values=("tiny",),
            reason="planted",
        )
        pack = dataclasses.replace(SCIFI_PACK, constraints=(*SCIFI_PACK.constraints, rule))
        self.assertCode(pack, "RULE")

    def test_a_reasonless_rule_is_caught(self) -> None:
        rule = ConstraintRule(
            type="exclude",
            field="entity*.kind",
            value="starship",
            excludes_field="entity*.scale",
            excludes_values=("tiny",),
        )
        pack = dataclasses.replace(SCIFI_PACK, constraints=(*SCIFI_PACK.constraints, rule))
        self.assertCode(pack, "RULE")

    def test_an_undeclared_empty_pool_is_caught(self) -> None:
        self.assertCode(_with_pools(form=("starship", ())), "COVERAGE")

    def test_a_stale_omission_declaration_is_caught(self) -> None:
        pack = dataclasses.replace(
            SCIFI_PACK,
            omitted_pools=frozenset({*SCIFI_PACK.omitted_pools, ("form", "starship")}),
        )
        self.assertCode(pack, "COVERAGE")

    def test_a_leading_article_is_caught(self) -> None:
        self.assertCode(_plus("primary_color", "a deep crimson"), "ARTICLE")

    def test_a_plural_count_noun_is_caught(self) -> None:
        self.assertCode(_plus("emitters", "ion thrusters", "starship"), "PLURAL")

    def test_a_digit_in_the_count_vocabulary_is_caught(self) -> None:
        self.assertCode(_plus("emitter_count", "4"), "DIGIT")

    def test_readable_text_in_markings_is_caught(self) -> None:
        self.assertCode(_plus("markings", "registry lettering", "starship"), "TEXT")

    def test_a_kind_below_the_situation_floor_is_caught(self) -> None:
        short = SCIFI_PACK.pools["situation"]["starship"][: MIN_SITUATIONS_PER_KIND - 1]
        self.assertCode(_with_pools(situation=("starship", short)), "SITUATION")

    def test_an_unclassified_tiered_value_is_caught(self) -> None:
        """A value with no tier would silently draw at neutral weight."""
        self.assertCode(
            _plus("situation", "drifting past a test buoy", "starship"), "TIER"
        )

    def test_a_rendering_term_is_caught(self) -> None:
        self.assertCode(_plus("primary_color", "cinematic lighting"), "RENDERING")

    def test_a_negation_is_caught(self) -> None:
        self.assertCode(_plus("condition", "missing every hull plate"), "NEGATION")

    def test_a_cross_field_duplicate_is_caught(self) -> None:
        existing = SCIFI_PACK.pools["surface_detail"]["starship"][0]
        self.assertCode(_plus("markings", existing, "starship"), "DUPLICATE")

    def test_an_unclassified_lint_value_is_caught(self) -> None:
        """A value its pool key's default no longer covers has no place-need."""
        pack = _plus("situation", "drifting past a test buoy", "starship")
        self.assertCode(pack, "UNCLASSIFIED")

    def test_a_form_without_a_stance_is_caught(self) -> None:
        value = next(iter(SCIFI_PACK.value_stances["form"]))
        self.assertCode(_without_stance(value), "STANCE")

    def test_a_place_granting_contradictory_affordances_is_caught(self) -> None:
        place = next(iter(SCIFI_PACK.place_affordances))
        self.assertCode(
            _with_added_affordances(place, "submerged", "sky"), "CONTRADICTION"
        )

    def test_a_place_granting_compatible_affordances_is_not_flagged(self) -> None:
        """``submerged`` and ``ground`` do not contradict, so neither may fire.

        Probed from an existing underwater place: ``air`` and ``submerged`` DO
        contradict, so a place that affords air cannot be the probe."""
        place = next(
            name
            for name, granted in SCIFI_PACK.place_affordances.items()
            if "submerged" in granted and "sky" not in granted
        )
        pack = _with_added_affordances(place, "ground")
        self.assertNotIn("CONTRADICTION", _codes(validate(pack)))

    def test_a_place_offering_a_kind_that_cannot_exist_there_fails(self) -> None:
        pools = {name: dict(by_key) for name, by_key in SCIFI_PACK.pools.items()}
        pools["kind"]["crew commons"] = ("spacefarer", "celestial body")
        pack = dataclasses.replace(SCIFI_PACK, pools=pools)
        codes = {line.split()[0] for line in validate(pack).failures}
        self.assertIn("DEADKIND", codes)

    def test_an_empty_need_default_fails(self) -> None:
        defaults = {name: dict(by_key) for name, by_key in SCIFI_PACK.default_needs.items()}
        defaults["situation"]["starship"] = frozenset()
        pack = dataclasses.replace(SCIFI_PACK, default_needs=defaults)
        codes = {line.split()[0] for line in validate(pack).failures}
        self.assertIn("EMPTYDEFAULT", codes)

    def test_a_type_with_too_few_situations_where_it_can_exist_fails(self) -> None:
        short = SCIFI_PACK.pools["situation"]["small drone"][:3]
        pack = _with_pools(situation=("small drone", short))
        codes = {line.split()[0] for line in validate(pack).failures}
        self.assertIn("FLOOR", codes)

    def _with_situation(self, key: str, value: str, stances=None) -> "G.GenrePack":
        pools = {name: dict(by_key) for name, by_key in SCIFI_PACK.pools.items()}
        pools["situation"][key] = (*pools["situation"][key], value)
        tags = {name: dict(values) for name, values in SCIFI_PACK.tags.items()}
        tags["situation"][value] = "neutral"
        tiers = {"situation": {**SCIFI_PACK.value_tiers["situation"], value: "event"}}
        needs = {name: dict(values) for name, values in SCIFI_PACK.value_needs.items()}
        needs["situation"][value] = frozenset()
        value_stances = {name: dict(values) for name, values in SCIFI_PACK.value_stances.items()}
        if stances is not None:
            value_stances["situation"][value] = frozenset(stances)
        return dataclasses.replace(
            SCIFI_PACK, pools=pools, tags=tags, value_tiers=tiers,
            value_needs=needs, value_stances=value_stances,
        )

    def test_a_body_part_reachable_by_a_body_without_it_fails(self) -> None:
        pack = self._with_situation("diffuse being", "snapping its jaws at a drone")
        self.assertIn("BODY", {line.split()[0] for line in validate(pack).failures})

    def test_a_movement_word_without_its_stance_fails(self) -> None:
        pack = self._with_situation("surface vehicle", "losing a wheel on a hard landing")
        self.assertIn("STANCEWORD", {line.split()[0] for line in validate(pack).failures})

    def test_a_spoken_form_naming_an_earth_object_fails(self) -> None:
        spoken = {name: dict(values) for name, values in SCIFI_PACK.spoken.items()}
        spoken["subkind"]["hospital ship"] = "hospital ship"
        pack = dataclasses.replace(SCIFI_PACK, spoken=spoken)
        self.assertIn("FOREIGN", {line.split()[0] for line in validate(pack).failures})

    def test_a_value_no_subject_can_reach_is_caught(self) -> None:
        """A form authored only under a kind key is unreachable once every subkind
        has a group key of its own -- the shadow the group keys cast. The check is
        called directly because it lands on ``CHECKS`` only with the data fix."""
        existing = SCIFI_PACK.pools["form"]["robot or mech"]
        pack = _with_pools(
            form=("robot or mech", (*existing, "planted unreachable chassis"))
        )
        report = Report()
        check_shadowed_values(pack, report)
        self.assertIn("SHADOWED", _codes(report))

    def test_a_part_a_body_cannot_have_is_caught(self) -> None:
        """A part pool is keyed by kind, so a value can be bolted to a body with no
        such structure. The situation lint cannot see it: a situation such as
        "throwing a track" relies on the runtime stance check instead."""
        pools = {name: dict(by_key) for name, by_key in SCIFI_PACK.pools.items()}
        pools["extras"]["hovering"] = ("spare track",)
        pack = dataclasses.replace(
            SCIFI_PACK,
            pools=pools,
            body_features={
                **SCIFI_PACK.body_features,
                "wheeled/tracked": frozenset({"tracks"}),
            },
            part_keywords={"tracks": ("track",)},
            part_lint_fields=("extras",),
        )
        self.assertIn("PARTFIT", {line.split()[0] for line in validate(pack).failures})

    def test_a_context_sentence_with_a_stance_verb_is_caught(self) -> None:
        """Round XIV: a framing verb is forced onto every context value."""
        prose = dataclasses.replace(
            SCIFI_PACK.prose,
            context_sentences=SCIFI_PACK.prose.context_sentences
            + (G.Sentence(text="{a_context} crowds in close behind {pronoun_object}."),),
        )
        pack = dataclasses.replace(SCIFI_PACK, prose=prose)
        self.assertIn("CONTEXTSTANCE", {line.split()[0] for line in validate(pack).failures})

    def test_the_shipped_context_sentences_carry_no_stance_verb(self) -> None:
        self.assertNotIn(
            "CONTEXTSTANCE", {line.split()[0] for line in validate(SCIFI_PACK).failures}
        )

class TheSplitRuleIsProvenBothWaysTests(unittest.TestCase):
    """The plan names both directions by name. Neither alone proves the rule."""

    def test_a_planted_cinematic_lighting_fails(self) -> None:
        report = validate(_plus("primary_color", "cinematic lighting"))
        self.assertFalse(report.ok)
        self.assertTrue(
            any("cinematic lighting" in line for line in report.failures),
            report.failures,
        )

    def test_a_planted_crimson_hull_passes(self) -> None:
        """The same pool, the same check, a subject-intrinsic value: clean.

        A denylist that banned every colour word would pass the test above and
        fail this one, which is why both are here.
        """
        report = validate(_plus("primary_color", "crimson"))
        self.assertEqual(report.failures, [], "\n".join(report.failures))

    def test_the_shared_vocabulary_exemption_is_not_a_blanket_one(self) -> None:
        """The colour fields may overlap; nothing else may.

        Without this, widening the exemption to silence a real finding would go
        unnoticed.
        """
        self.assertEqual(len(SCIFI_PACK.shared_vocabulary), 1)
        (group,) = SCIFI_PACK.shared_vocabulary
        self.assertEqual(group, frozenset({"primary_color", "accent_color", "emitter_color"}))


if __name__ == "__main__":
    unittest.main()
