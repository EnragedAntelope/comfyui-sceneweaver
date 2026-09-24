"""The fantasy pack: sound data, coherent scenes on both paths, and wiring across genres.

The coherence classes here are written against the *output* and the pack's own closed
lists, so a new situation that forgets its bucket, or a place that grants a stance it
should not, shows up as a named class rather than as a vague bad render.
"""
from __future__ import annotations

import json
import logging
import random
import re
import tempfile
import unittest
from pathlib import Path

import data.genre as G
from data import fantasy as F
from data.fantasy import FANTASY_PACK
from data.scifi import SCIFI_PACK
from data.user_options import apply_user_options, merge_user_options
from engine.scene import generate_entity, generate_scene
from scripts.builtin_options import builtin_pools
from tests.boundary import negation_findings, rendering_findings
from tests.validate_data import validate

_FIRE = re.compile(r"\b(fire|flame|burning|blaze|blazing|campfire)\b")
_ANACHRONISM = re.compile(r"\b(" + "|".join(FANTASY_PACK.foreign_nouns) + r")\b")
_STANCE_VERB = re.compile(r"\b(stands|lies|crowds in)\b")
_DEAD = {"petrified", "ruined", "abandoned", "wrecked", "dormant"}
_WATER_BORN = {"selkie", "merfolk", "undine", "water elemental", "kelpie"}


def _classes(text: str, document: dict) -> set[str]:
    """Every incoherence class one scene falls into."""
    found: set[str] = set()
    place = document["environment"]
    affords = G.affordances_of(FANTASY_PACK, place)
    conflict = {v for v, code in F._SITUATION_TAG_CODES.items() if code == "c"}
    for entity in document["entities"]:
        situation = entity.get("situation") or ""
        condition = entity.get("condition") or ""
        subkind = entity.get("subkind") or ""
        if not situation:
            found.add("no-situation")
        if condition in _DEAD and (situation not in F.DORMANT_ACTS or entity.get("emitters")):
            found.add("dead-but-live")
        if condition == "slumbering" and situation not in F.SLEEP_ACTS:
            found.add("sleeper-awake")
        if entity.get("form") and not G.form_can_stand(FANTASY_PACK, place, entity["form"]):
            found.add("body-cannot-stand")
        if "submerged" in affords and _FIRE.search(f"{situation} {subkind}"):
            found.add("fire-underwater")
        if place in F.ENVIRONMENT_BANDS["interior"] and entity.get("scale") in (
                "huge", "colossal", "titanic"):
            found.add("huge-indoors")
        if place in F.VALUE_TRAITS[G.ENVIRONMENT_FIELD] and subkind in _WATER_BORN and (
                "hot-place" in F.VALUE_TRAITS[G.ENVIRONMENT_FIELD][place]):
            found.add("water-creature-in-fire")
        if subkind in F._CIVIL_ROLES and situation in conflict:
            found.add("civil-role-fighting")
    low = text.lower()
    if _ANACHRONISM.search(low):
        found.add("anachronism")
    if _STANCE_VERB.search(low):
        found.add("context-stance-verb")
    if rendering_findings(text) or negation_findings(text):
        found.add("rendering-or-negation")
    return found


class FantasyDataTests(unittest.TestCase):
    def test_the_validator_finds_nothing(self) -> None:
        self.assertEqual(validate(FANTASY_PACK).failures, [])

    def test_the_ast_reader_agrees_with_the_pack_field_for_field(self) -> None:
        read = builtin_pools(pack="fantasy")
        for field_name, by_key in FANTASY_PACK.pools.items():
            with self.subTest(field=field_name):
                self.assertEqual(
                    {key: tuple(values) for key, values in by_key.items()}, read.get(field_name)
                )

    def test_every_situation_is_in_exactly_one_kind_of_bucket(self) -> None:
        values = {v for pool in F.SITUATION_POOLS.values() for v in pool}
        self.assertEqual(values - set(F.SITUATION_TIERS), set())
        self.assertEqual(F.DORMANT_ACTS & F.SLEEP_ACTS, frozenset())


class FantasyCoherenceTests(unittest.TestCase):
    """A seeded sweep over both paths; every class must read zero."""

    def test_no_class_fires_on_either_path(self) -> None:
        logging.disable(logging.CRITICAL)
        try:
            rng = random.Random(916)
            hits: dict[str, list[str]] = {}
            for index in range(500):
                entity_seed, scene_seed = rng.randrange(2**48), rng.randrange(2**48)
                wired = {1: generate_entity(entity_seed, FANTASY_PACK)[1]} if index % 2 else {}
                text, document = generate_scene(
                    scene_seed, FANTASY_PACK, wired_entities=wired, entity_count=1 + index % 2
                )
                self.assertTrue(text.startswith("A fantasy scene"), text[:40])
                for name in _classes(text, document):
                    hits.setdefault(name, []).append(text[:160])
        finally:
            logging.disable(logging.NOTSET)
        self.assertEqual(hits, {}, hits)

    def test_a_planted_dead_act_is_caught(self) -> None:
        document = {
            "environment": "wildflower meadow",
            "entities": [{"condition": "petrified", "situation": "charging headlong",
                          "subkind": "unicorn", "form": "slender horse body"}],
        }
        self.assertIn("dead-but-live", _classes("A fantasy scene.", document))

    def test_a_planted_anachronism_is_caught(self) -> None:
        document = {"environment": "wildflower meadow", "entities": []}
        self.assertIn("anachronism", _classes("A knight holding a laser rifle.", document))


class CrossGenreTests(unittest.TestCase):
    """An entity of either genre fills a slot in a scene of the other."""

    def test_a_fantasy_entity_in_a_scifi_scene(self) -> None:
        for seed in range(20):
            _text, payload = generate_entity(seed, FANTASY_PACK)
            text, document = generate_scene(seed, SCIFI_PACK, wired_entities={1: payload},
                                            entity_count=1)
            with self.subTest(seed=seed):
                self.assertTrue(text.startswith("A science fiction scene"))
                self.assertEqual(document["entities"][0]["genre"], "fantasy")

    def test_a_scifi_entity_in_a_fantasy_scene(self) -> None:
        for seed in range(20):
            _text, payload = generate_entity(seed, SCIFI_PACK)
            text, document = generate_scene(seed, FANTASY_PACK, wired_entities={1: payload},
                                            entity_count=1)
            with self.subTest(seed=seed):
                self.assertTrue(text.startswith("A fantasy scene"))
                self.assertEqual(document["entities"][0]["genre"], "scifi")


class UserOptionsSectionTests(unittest.TestCase):
    """One ``user_options.json``: top-level for sci-fi, a named section per other genre."""

    DOCUMENT = {
        "pools": {"primary_color": {"_default": ["hunter green"]}},
        "fantasy": {"pools": {"subkind": {"mythic beast": ["moon hare"]}}},
    }

    def _file(self) -> Path:
        folder = Path(tempfile.mkdtemp())
        path = folder / "user_options.json"
        path.write_text(json.dumps(self.DOCUMENT), encoding="utf-8")
        return path

    def test_the_fantasy_section_reaches_the_fantasy_pack_only(self) -> None:
        path = self._file()
        fantasy = apply_user_options(FANTASY_PACK, path, section="fantasy")
        scifi = apply_user_options(SCIFI_PACK, path, sections=("fantasy",))
        self.assertIn("moon hare", fantasy.pools["subkind"]["mythic beast"])
        self.assertNotIn("hunter green", fantasy.pools["primary_color"].get("_default", ()))
        self.assertIn("hunter green", scifi.pools["primary_color"]["_default"])

    def test_a_declared_genre_section_is_not_an_unknown_key(self) -> None:
        with self.assertNoLogs("data.user_options", level="WARNING"):
            merge_user_options(SCIFI_PACK, {"fantasy": {}}, sections=("fantasy",))


if __name__ == "__main__":
    unittest.main()
