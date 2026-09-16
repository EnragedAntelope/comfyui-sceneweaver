"""A subject is never described without a silhouette because its place could not hold one."""
from __future__ import annotations

import random
import re
import unittest

from data.genre import (
    KIND_FIELD,
    STANCE_FIELD,
    feasible_types,
    kind_feasible,
    pool_for,
    pool_options,
    type_field,
)
from data.scifi import SCIFI_PACK
from engine.scene import generate_entity, generate_scene

SEEDS = 400


def missing_silhouettes(document) -> list[str]:
    """Slot-1 and wired entities whose type has forms but whose form resolved to None."""
    name = type_field(SCIFI_PACK)
    found = []
    for record in document["entities"]:
        if record["index"] != 1 and record["source"] != "wired":
            continue
        kind, value = record.get(KIND_FIELD), record.get(name)
        if kind is None or value is None or record.get(STANCE_FIELD) is not None:
            continue
        if pool_for(SCIFI_PACK, STANCE_FIELD, {KIND_FIELD: kind, name: value}):
            found.append(f"{kind}/{value} in {document['environment']!r}")
    return found


class FeasibilityTests(unittest.TestCase):
    def test_the_unwired_path_never_drops_a_silhouette(self) -> None:
        missing: list[str] = []
        for seed in range(SEEDS):
            _text, document = generate_scene(seed, SCIFI_PACK, entity_count=1)
            missing += missing_silhouettes(document)
        self.assertEqual(missing, [], missing[:5])

    def test_the_wired_path_never_drops_a_silhouette(self) -> None:
        rng = random.Random(20260913)
        missing: list[str] = []
        for _ in range(SEEDS):
            _text, payload = generate_entity(rng.randrange(2**48), SCIFI_PACK)
            _text, document = generate_scene(
                rng.randrange(2**48), SCIFI_PACK, wired_entities={1: payload}, entity_count=1
            )
            missing += missing_silhouettes(document)
        self.assertEqual(missing, [], missing[:5])

    def test_every_drawn_type_can_exist_where_it_was_drawn(self) -> None:
        name = type_field(SCIFI_PACK)
        for seed in range(SEEDS):
            _text, document = generate_scene(seed, SCIFI_PACK, entity_count=1)
            environment = document["environment"]
            for record in document["entities"]:
                kind, value = record.get(KIND_FIELD), record.get(name)
                if kind is None or value is None:
                    continue
                with self.subTest(seed=seed, kind=kind, value=value, environment=environment):
                    self.assertIn(value, feasible_types(SCIFI_PACK, environment, kind))

    def test_every_kind_a_place_offers_can_exist_there(self) -> None:
        for environment in pool_options(SCIFI_PACK, "environment"):
            for kind in pool_for(SCIFI_PACK, KIND_FIELD, {"environment": environment}):
                with self.subTest(environment=environment, kind=kind):
                    self.assertTrue(kind_feasible(SCIFI_PACK, environment, kind))

    def test_a_form_named_for_its_locomotion_moves_that_way(self) -> None:
        rules = (
            (re.compile(r"\b(legged|leg|walker|strider|bipedal|quadrupedal|hexapod|tripod|humanoid|android)\b"), "walks"),
            (re.compile(r"\b(wheeled|tracked|rover)\b"), "rolls"),
            (re.compile(r"\b(hover|hovering|skimmer)\b"), "hovers"),
        )
        for form, declared in SCIFI_PACK.value_stances["form"].items():
            for pattern, stance in rules:
                if pattern.search(form):
                    with self.subTest(form=form, stance=stance):
                        self.assertIn(stance, declared)
