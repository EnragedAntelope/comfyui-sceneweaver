"""The 0.6.0 content additions, held to the rules they were authored under.

Each class pins what a value was *given*, not just that it exists: a place's
affordances, a subject's needs, a relation's roles and tag. A value added without
its card passes ``validate_data.py`` only when the card is checkable there, and a
card nobody asserts is a card the next edit can quietly drop.
"""
from __future__ import annotations

import unittest
from typing import Iterable

import data.genre as G
from data import fantasy as F
from data import horror as H
from data import scifi as S
from data.fantasy import FANTASY_PACK
from data.horror import HORROR_PACK
from data.scifi import SCIFI_PACK
from engine.scene import generate_scene

SEEDS = range(250)


def _scenes(pack, widgets, seeds: "Iterable[int]" = SEEDS, **kwargs):
    for seed in seeds:
        yield generate_scene(seed, pack, widgets=widgets, entity_count=1, **kwargs)


class HorrorRelationTests(unittest.TestCase):
    NEW = ("dragging", "feeding on", "luring", "worshipping", "carrying off")

    def test_every_new_relation_has_roles_and_a_tag(self) -> None:
        for value in self.NEW:
            with self.subTest(value=value):
                self.assertIn(value, HORROR_PACK.pools["relation"][G.POOL_DEFAULT_KEY])
                self.assertIn(value, HORROR_PACK.relation_roles)
                self.assertIn(value, HORROR_PACK.tags[G.RELATION_FIELD])

    def test_the_violent_ones_are_graphic_and_hidden_by_no_gore(self) -> None:
        graphic = {"dragging", "feeding on", "carrying off"}
        for value in self.NEW:
            expected = G.TAG_CONFLICT_ONLY if value in graphic else G.TAG_NEUTRAL
            self.assertEqual(HORROR_PACK.tags[G.RELATION_FIELD][value], expected, value)
        drawn = set()
        for seed in range(300):
            _text, doc = generate_scene(
                seed, HORROR_PACK, widgets={"relation_1_2": "Random"},
                scene_filter="No gore", entity_count=2,
            )
            drawn.update(r["value"] for r in doc["relations"])
        self.assertFalse(drawn & graphic, "No gore must not draw a graphic relation")

    def test_a_drawn_relation_respects_who_can_do_it_to_whom(self) -> None:
        caps = H.KIND_CAPABILITIES
        seen = set()
        for seed in range(3000):
            _text, doc = generate_scene(
                seed, HORROR_PACK, widgets={"relation_1_2": "Random"}, entity_count=2
            )
            for relation in doc["relations"]:
                value = relation["value"]
                if value not in self.NEW:
                    continue
                seen.add(value)
                first, second = (doc["entities"][i - 1]["kind"] for i in relation["endpoints"])
                need_first, need_second = H.RELATION_ROLES[value]
                self.assertLessEqual(need_first, caps[first], (value, first))
                self.assertLessEqual(need_second, caps[second], (value, second))
        self.assertEqual(seen, set(self.NEW), "a new relation that is never drawn is a dead option")


class HorrorPlaceTests(unittest.TestCase):
    PLACES = {
        "hedge maze": "wilds",
        "abandoned desert mining town": "town",
        "abandoned theatre stage": "interior",
        "overgrown greenhouse": "interior",
        "wax museum gallery": "interior",
        "lighthouse lamp room": "interior",
    }

    def test_each_place_is_banded_and_drawn(self) -> None:
        for place, band in self.PLACES.items():
            with self.subTest(place=place):
                self.assertIn(place, HORROR_PACK.environment_bands[band])
                for text, _doc in _scenes(HORROR_PACK, {"environment": place}, range(15)):
                    self.assertIn(place, text)

    def test_a_glass_room_has_daylight_and_a_hedge_has_no_room_for_a_giant(self) -> None:
        affords = lambda place: G.affordances_of(HORROR_PACK, place)  # noqa: E731
        self.assertNotIn("dark", affords("overgrown greenhouse"))
        self.assertNotIn("dark", affords("lighthouse lamp room"))
        self.assertNotIn("vast", affords("hedge maze"))
        self.assertIn("dark", affords("wax museum gallery"))

    def test_the_new_colours_are_not_banned_words(self) -> None:
        for colour in ("deep crimson", "deep orange", "pale teal", "dull gold"):
            self.assertIn(colour, HORROR_PACK.pools["emitter_color"][G.POOL_DEFAULT_KEY])
        for colour in ("faded blue", "dull ochre", "tarnished brass", "deep teal"):
            self.assertIn(colour, HORROR_PACK.pools["accent_color"][G.POOL_DEFAULT_KEY])


class HorrorSubjectTests(unittest.TestCase):
    def test_a_mummy_never_weeps_fresh_blood(self) -> None:
        graphic = {
            value for value, tag in HORROR_PACK.tags["surface_detail"].items()
            if tag == G.TAG_CONFLICT_ONLY
        } | {"blood-smeared mouth", "gore-clotted maw", "cracked bleeding lips"}
        self.assertFalse(
            graphic & set(HORROR_PACK.pools["surface_detail"]["mummy"]),
            "a desiccated wrapped body carries none of the undead pool's wounds",
        )
        self.assertFalse(graphic & set(HORROR_PACK.pools["aperture"]["mummy"]))

    def test_a_mummy_is_spoken_so_a_model_draws_wrappings_not_a_mother(self) -> None:
        text, doc = next(
            _scenes(HORROR_PACK, {"entity1_kind": "undead", "entity1_subkind": "mummy"}, [3])
        )
        self.assertEqual(doc["entities"][0]["subkind"], "mummy")
        self.assertIn("bandage-wrapped mummy", text)

    def test_a_mummy_is_never_on_a_lake_bed(self) -> None:
        for _text, doc in _scenes(
            HORROR_PACK, {"entity1_kind": "undead", "entity1_subkind": "mummy"}
        ):
            affords = G.affordances_of(HORROR_PACK, doc["environment"])
            self.assertIn("air", affords, doc["environment"])


class FantasyContentTests(unittest.TestCase):
    PLACES = {
        "jungle temple ruins": "wilds",
        "desert oasis": "wilds",
        "pirate cove": "waterside",
        "gladiatorial arena": "settlement",
        "tournament jousting field": "settlement",
        "ice palace hall": "interior",
    }

    def test_each_place_is_banded_and_drawn(self) -> None:
        for place, band in self.PLACES.items():
            with self.subTest(place=place):
                self.assertIn(place, FANTASY_PACK.environment_bands[band])
                for text, _doc in _scenes(FANTASY_PACK, {"environment": place}, range(15)):
                    self.assertIn(place, text)

    def test_a_pirate_cove_is_navigable_and_an_oasis_is_not_a_shore(self) -> None:
        self.assertIn("navigable", G.affordances_of(FANTASY_PACK, "pirate cove"))
        self.assertNotIn("shoreline", G.affordances_of(FANTASY_PACK, "desert oasis"))
        self.assertIn("cold", G.affordances_of(FANTASY_PACK, "ice palace hall"))

    def test_a_giant_scorpion_is_only_drawn_where_it_is_warm(self) -> None:
        places = set()
        for _text, doc in _scenes(
            FANTASY_PACK, {"entity1_kind": "mythic beast", "entity1_subkind": "giant scorpion"}
        ):
            places.add(doc["environment"])
        self.assertTrue(places)
        for place in places:
            self.assertIn("warm", G.affordances_of(FANTASY_PACK, place), place)

    def test_a_woolly_mammoth_needs_room_for_something_huge(self) -> None:
        places = set()
        for _text, doc in _scenes(
            FANTASY_PACK, {"entity1_kind": "mythic beast", "entity1_subkind": "woolly mammoth"}
        ):
            places.add(doc["environment"])
        self.assertTrue(places)
        for place in places:
            self.assertIn("vast", G.affordances_of(FANTASY_PACK, place), place)

    def test_each_new_role_has_its_own_clothes_and_hands(self) -> None:
        for role in ("gladiator", "pirate captain", "witch hunter"):
            with self.subTest(role=role):
                self.assertIn(role, FANTASY_PACK.pool_groups["subkind"]["adventurer"])
                for field in ("material", "armament", "appendages"):
                    self.assertTrue(FANTASY_PACK.pools[field].get(role), (role, field))

    def test_a_beast_does_not_borrow_another_animals_mouth_or_markings(self) -> None:
        self.assertNotIn("snarling muzzle", F.APERTURE_POOLS["woolly mammoth"])
        self.assertNotIn("striped flank banding", F.MARKINGS_POOLS["woolly mammoth"])
        self.assertNotIn("snarling muzzle", F.APERTURE_POOLS["giant scorpion"])
        self.assertNotIn("striped flank banding", F.MARKINGS_POOLS["giant scorpion"])


class SciFiContentTests(unittest.TestCase):
    PLACES = ("frontier spaceport landing pad", "temperate belt of a tidally locked world")

    def test_an_open_surface_place_grants_no_structure(self) -> None:
        """A granted ``structure`` would admit every corridor act on an open pad."""
        for place in self.PLACES:
            with self.subTest(place=place):
                self.assertIn(place, SCIFI_PACK.environment_bands["planetary surface"])
                affords = G.affordances_of(SCIFI_PACK, place)
                self.assertNotIn("structure", affords)
                self.assertIn("ground", affords)

    def test_a_surface_place_names_an_alien_sky_so_it_is_not_drawn_as_earth(self) -> None:
        for place in self.PLACES:
            spoken = G.spoken_value(SCIFI_PACK, "environment", place)
            self.assertTrue(
                any(word in spoken for word in ("moon", "sun", "giant")), spoken
            )

    def test_the_pad_and_the_belt_are_drawn(self) -> None:
        for place in self.PLACES:
            for text, _doc in _scenes(SCIFI_PACK, {"environment": place}, range(10)):
                self.assertIn(G.spoken_value(SCIFI_PACK, "environment", place), text)


class RenderTestFixTests(unittest.TestCase):
    """The 1002 render test: a candle in the sand, a ramp open under water, a lute on a gladiator."""

    def test_a_candle_act_needs_a_room_and_a_ramp_needs_air(self) -> None:
        self.assertIn(
            "structure",
            G.resolved_needs(FANTASY_PACK, "situation", "reaching for a guttering candle"),
        )
        self.assertIn(
            "air", G.resolved_needs(SCIFI_PACK, "situation", "lowering its ramp onto a deck")
        )

    def test_only_a_bard_carries_a_lute(self) -> None:
        holders = {
            key for key, values in FANTASY_PACK.pools["extras"].items() if "lute" in values
        }
        self.assertEqual(holders, {"bard"})
        for role in ("gladiator", "pirate captain", "witch hunter"):
            self.assertNotIn("lute", G.pool_for(FANTASY_PACK, "extras", {"subkind": role, "kind": "folk"}))

    def test_the_taxidermy_fox_is_gone(self) -> None:
        self.assertNotIn("taxidermy fox", HORROR_PACK.pools["subkind"]["cursed object"])


class RenderTest1003Tests(unittest.TestCase):
    """The 1003 render test: a manor for a hut, a desert-only scorpion, a beam to a wreck."""

    def _pool(self, pack, field: str, subkind: str, kind: str) -> tuple:
        return G.pool_for(pack, field, {"subkind": subkind, "kind": kind})

    def test_a_witchs_hut_is_not_a_manor(self) -> None:
        hut = ("witch's hut", "structure")
        for field, manorial in (
            ("markings", "painted crests above the gate"), ("aperture", "portcullis gate"),
            ("surface_detail", "crumbling battlements"), ("extras", "row of stone gargoyles"),
            ("scale", "colossal"),
        ):
            self.assertNotIn(manorial, self._pool(FANTASY_PACK, field, *hut), field)

    def test_a_scorpion_lives_wherever_it_is_warm(self) -> None:
        self.assertEqual(G.resolved_needs(FANTASY_PACK, "subkind", "giant scorpion"), {"warm"})
        warm = [
            place for place in FANTASY_PACK.pools["environment"][G.POOL_DEFAULT_KEY]
            if "warm" in G.affordances_of(FANTASY_PACK, place)
        ]
        self.assertGreaterEqual(len(warm), 8)
        self.assertIn("gladiatorial arena", warm)

    def test_a_statues_arm_sweep_needs_both_hands(self) -> None:
        self.assertIn("sweeping a heavy arm in a wide arc", F._BOTH_HANDS)

    def test_a_beam_at_a_vessel_owns_the_frames_other_ships(self) -> None:
        self.assertIn(("beams-at-a-vessel", "background-vessel"), SCIFI_PACK.trait_conflicts)
        traits = SCIFI_PACK.value_traits
        self.assertIn(
            "beams-at-a-vessel",
            traits["situation"]["towing a crippled courier starship in a tractor beam"],
        )
        self.assertIn(
            "background-vessel", traits["context"]["distant wrecked starship turning end over end"]
        )

    def test_a_sphere_hull_never_rests_on_open_ground(self) -> None:
        self.assertIn(("open-landscape", "spherical-hull"), SCIFI_PACK.trait_conflicts)

    def test_a_plural_context_takes_a_plural_verb(self) -> None:
        for seed in range(3000):
            text, doc = generate_scene(seed, FANTASY_PACK, entity_count=1)
            if doc.get("context") == "bleached bones of a great beast":
                self.assertNotRegex(text, r"great beast (is|catches) ")
                self.assertNotIn("is bleached bones", text)
                return
        self.fail("no scene drew the plural context")


class RenderTest1003bTests(unittest.TestCase):
    """The sceneweaver103 renders: Trek words, a clock-faced automaton, two cyclopes."""

    def _all(self, pack) -> set:
        return {v for pools in pack.pools.values() for vs in pools.values() for v in vs}

    def test_no_star_trek_vocabulary(self) -> None:
        import re
        trek = re.compile(r"nacelle|warp coil|saucer|shuttlecraft", re.I)
        values = self._all(SCIFI_PACK)
        values |= {v for spoken in SCIFI_PACK.spoken.values() for v in spoken.values()}
        values -= {"landing shuttlecraft"}  # the widget token; it is spoken "stubby landing craft"
        self.assertEqual(sorted(v for v in values if trek.search(v)), [])
        self.assertEqual(G.spoken_value(SCIFI_PACK, "subkind", "landing shuttlecraft"), "stubby landing craft")

    def test_singular_heads_ending_in_s(self) -> None:
        from engine.grammar import head_is_plural, with_article_if_singular
        self.assertFalse(head_is_plural("hulking cyclops"))
        self.assertEqual(with_article_if_singular("figure bent backwards at the waist"),
                         "a figure bent backwards at the waist")

    def test_no_clock_and_no_sword_forest(self) -> None:
        values = self._all(FANTASY_PACK)
        self.assertFalse([v for v in values if "clockwork" in v and v != "clockwork guardian"])
        self.assertNotIn("clockwork", G.spoken_value(FANTASY_PACK, "subkind", "clockwork guardian"))
        self.assertNotIn(
            "blades", G.spoken_value(FANTASY_PACK, "environment", "old battlefield of rusted banners")
        )

    def test_a_ghost_holds_nothing_and_a_skeleton_has_no_gut(self) -> None:
        self.assertFalse([v for v in self._all(HORROR_PACK) if "held in one hand" in v])
        conflicts = HORROR_PACK.trait_conflicts
        self.assertIn(("bare-bone", "flesh-intact"), conflicts)
        self.assertIn(
            "flesh-intact",
            HORROR_PACK.value_traits["situation"]["dragging a trail of spilled entrails behind it"],
        )

    def test_a_count_follows_a_noun_a_rule_redrew(self) -> None:
        # The warden's hand-held light is re-drawn by a rule; its count must follow.
        for seed in range(400):
            _, doc = generate_scene(
                seed, HORROR_PACK,
                widgets={"entity1_kind": "mortal", "entity1_subkind": "paranormal investigator"},
                entity_count=1,
            )
            entity = doc["entities"][0]
            if entity.get("emitters") and entity.get("emitter_count"):
                pool = G.pool_for(HORROR_PACK, "emitter_count",
                                  {"emitters": entity["emitters"], "kind": "mortal"})
                self.assertIn(entity["emitter_count"], pool, (seed, entity["emitters"]))

    def test_the_warden_carries_one_light_and_a_ghost_none(self) -> None:
        self.assertEqual(
            G.pool_for(HORROR_PACK, "emitters", {"subkind": "lantern-bearing warden", "kind": "mortal"}), ()
        )
        self.assertFalse([v for v in self._all(HORROR_PACK) if "will-o" in v])

    def test_a_singing_harp_has_its_own_acts(self) -> None:
        acts = G.pool_for(FANTASY_PACK, "situation", {"subkind": "singing harp", "kind": "artifact"})
        self.assertIn("lulling a band of armed raiders to sleep around it", acts)
        self.assertNotIn("withering the grass in a spreading circle around it", acts)

    def test_a_plague_victim_is_not_a_mummy(self) -> None:
        self.assertNotIn("stained bandage wrappings", self._all(HORROR_PACK))
        self.assertNotIn(
            "sewn-on knotted-twine charms",
            G.pool_for(HORROR_PACK, "markings", {"subkind": "pox-ridden wanderer", "kind": "mortal"}),
        )


class RoundXXIXTests(unittest.TestCase):
    """Subgenre flavour as content: post-collapse places, grown places and rites, brass beasts, weather."""

    HORROR_PLACES = {
        "barricaded farmyard": "wilds",
        "highway jammed with abandoned cars": "town",
        "military roadblock on an empty highway": "town",
        "looted supermarket aisle": "interior",
        "concrete fallout shelter": "underground",
    }
    SCIFI_PLACES = ("genetics laboratory", "living bioship corridor", "terraced arboretum dome")
    NEW_SITUATIONS = (
        (HORROR_PACK, H._S_DEAD_EV_WRECK + H._S_SPIRIT_EV_WRECK + H._S_ELDRITCH_EV_WRECK
         + H._S_BEAST_EV_WRECK + H._S_SURVIVOR_EV_WRECK + H._S_SWARM_EV_WRECK),
        (SCIFI_PACK, S._SITUATION_VOID_RITES + (
            "smashing out of a cracked specimen tank in a flood of green fluid",
            "clamping a cracked specimen tank shut as green fluid sprays out",
        )),
        (FANTASY_PACK, F.SITUATION_POOLS["brass beast"] + F.SITUATION_POOLS["brass falcon"]
         + F._S_FOLK_ACT_COLD + F._S_FOLK_ACT_DUST + F._S_BEAST_ACT_COLD + F._S_BEAST_ACT_DUST),
    )

    def test_each_place_is_banded_and_drawn(self) -> None:
        for pack, places in ((HORROR_PACK, self.HORROR_PLACES),
                             (SCIFI_PACK, dict.fromkeys(self.SCIFI_PLACES, "interior"))):
            for place, band in places.items():
                with self.subTest(place=place):
                    self.assertIn(place, pack.environment_bands[band])
                    self.assertTrue(pack.pools["context"].get(place), "a place keeps its own context")
                    for _text, doc in _scenes(pack, {"environment": place}, range(15)):
                        self.assertEqual(doc["environment"], place)

    def test_wrecks_are_where_the_cars_are_and_a_farm_holds_no_haunted_hospital(self) -> None:
        self.assertIn("wreck", G.affordances_of(HORROR_PACK, "highway jammed with abandoned cars"))
        self.assertNotIn("wreck", G.affordances_of(HORROR_PACK, "barricaded farmyard"))
        self.assertNotIn("haunted place", H.KIND_POOLS["barricaded farmyard"])

    def test_a_grown_place_is_spoken_off_world(self) -> None:
        for place in self.SCIFI_PLACES:
            spoken = G.spoken_value(SCIFI_PACK, "environment", place)
            self.assertRegex(spoken, r"aboard|inside|of an orbital habitat", place)
        self.assertIn("lab", G.affordances_of(SCIFI_PACK, "genetics laboratory"))

    def test_the_priest_keeps_the_whole_spacefarer_core_and_gains_rites(self) -> None:
        pool = set(S.SITUATION_POOLS["void order priest"])
        self.assertLessEqual(set(S._SITUATION_SPACEFARER), pool)
        self.assertLessEqual(set(S._SITUATION_VOID_RITES), pool)

    def test_a_brass_beast_is_a_made_animal_with_its_own_acts(self) -> None:
        beasts = F.SUBKIND_GROUPS["brass beast"]
        self.assertLessEqual(set(beasts), set(F.SUBKIND_POOLS["construct"]))
        for beast in beasts:
            with self.subTest(beast=beast):
                self.assertNotIn("clock", beast)
                self.assertEqual(F.ARCHETYPE_OF_SUBKIND[beast], "creature")
                spoken = G.spoken_value(FANTASY_PACK, "subkind", beast)
                self.assertRegex(spoken, r"gear-driven|cog-jointed|rivet-plated")

    def test_every_new_act_is_an_event_or_an_activity(self) -> None:
        for pack, values in self.NEW_SITUATIONS:
            tiers = pack.value_tiers["situation"]
            for value in values:
                if value in F._S_CONSTRUCT_DORMANT + F._S_CONSTRUCT_DORMANT_LIFE:
                    continue  # the dormant state reuses the construct's existing acts
                with self.subTest(value=value):
                    self.assertIn(tiers[value], ("event", "activity"))

    def test_weather_is_only_where_the_place_has_that_weather(self) -> None:
        needs = lambda field, value: G.resolved_needs(FANTASY_PACK, field, value)  # noqa: E731
        for value in F._CTX_SNOW + F._S_FOLK_ACT_COLD + F._S_BEAST_ACT_COLD:
            field = "context" if value in F._CTX_SNOW else "situation"
            self.assertIn("cold", needs(field, value), value)
        for value in F._CTX_SAND + F._S_FOLK_ACT_DUST + F._S_BEAST_ACT_DUST:
            field = "context" if value in F._CTX_SAND else "situation"
            self.assertIn("dust", needs(field, value), value)

    def test_band_weather_leaves_a_users_band_contexts_reaching_every_place(self) -> None:
        # A place key wins over its band; keying the storm or the hills would drop these.
        from data.user_options import merge_user_options
        merged = merge_user_options(
            FANTASY_PACK, {"pools": {"context": {"sky": ["test zeppelin"], "wilds": ["test cairn"]}}}
        )
        for place, value in (("stormy sky above a mountain range", "test zeppelin"),
                             ("rolling highland hills", "test cairn")):
            self.assertIn(value, G.pool_for(merged, "context", {"environment": place}), place)


if __name__ == "__main__":
    unittest.main()
