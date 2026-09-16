"""Todo 17 -- the ``Scene Entity`` node class.

Two things are being pinned here and they pull in different directions, so they
are worth naming apart.

*The schema is a compatibility surface.* Widget count, widget order and the
option list on each combo are what a saved workflow's positional
``widgets_values`` is restored against. A test that only checked "22 inputs"
would pass while every value in every saved graph landed on the wrong widget, so
the order is asserted against ``data.genre.widget_order`` -- the single
declaration both the node and the frontend read.

*The node itself is a thin adapter.* Everything it does is delegated to
``engine.scene.generate_entity``, which has its own suite; what is checked here
is that the adapter passes the right things through and hands back the two
outputs in the right shape.
"""
from __future__ import annotations

import unittest

from data import genre
from data.genre import ENTITY_NODE_SLOTS, NONE, RANDOM
from data.scifi import SCIFI_PACK
from nodes.scene_entity import SCENE_ENTITY_TYPE, build_entity_node
from engine.scene import ENTITY_PAYLOAD_VERSION

NODE = build_entity_node(SCIFI_PACK)


class SchemaShapeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.schema = NODE.define_schema()
        self.by_id = {inp.id: inp for inp in self.schema.inputs}

    def test_input_count_is_the_seed_plus_the_whole_morphology(self) -> None:
        """22 = one seed + the pack's entity fields. Derived from the pack, not
        typed in, so a genre with a different field count still passes."""
        self.assertEqual(len(self.schema.inputs), 1 + len(SCIFI_PACK.entity_fields))
        self.assertEqual(len(self.schema.inputs), 22)

    def test_widget_order_matches_the_contract_exactly(self) -> None:
        """The invariant that protects every saved workflow: ``widgets_values``
        is positional, so this order may be appended to and never rearranged."""
        self.assertEqual(
            [inp.id for inp in self.schema.inputs],
            list(genre.widget_order(SCIFI_PACK, ENTITY_NODE_SLOTS)),
        )

    def test_the_entity_node_carries_no_scene_controls(self) -> None:
        """No scene_filter and no set_all_fields. The filter is a property of
        the scene an entity ends up in; the depth is answered by the fact that
        the user reached for this node at all."""
        for absent in ("scene_filter", genre.SET_ALL_FIELDS_KEY):
            with self.subTest(widget=absent):
                self.assertNotIn(absent, self.by_id)

    def test_seed_is_an_int_that_advances_every_queue(self) -> None:
        seed = self.by_id["seed"]
        self.assertIsInstance(seed, genre_io_int())
        self.assertEqual(seed.control_after_generate, genre.SEED_CONTROL_AFTER_GENERATE)
        self.assertEqual((seed.min, seed.max), (genre.SEED_MIN, genre.SEED_MAX))

    def test_every_field_offers_random_then_options_then_none(self) -> None:
        for name in SCIFI_PACK.entity_fields:
            with self.subTest(field=name):
                options = self.by_id[name].options
                self.assertEqual(options[0], RANDOM)
                self.assertEqual(options[-1], NONE)
                self.assertEqual(
                    tuple(options[1:-1]), genre.pool_options(SCIFI_PACK, name)
                )

    def test_every_field_defaults_to_random(self) -> None:
        """Full random with no configuration is the pack's headline behaviour."""
        for name in SCIFI_PACK.entity_fields:
            with self.subTest(field=name):
                self.assertEqual(self.by_id[name].default, RANDOM)

    def test_every_field_tooltip_states_the_three_choices(self) -> None:
        for name in SCIFI_PACK.entity_fields:
            with self.subTest(field=name):
                # Help sentence first, then one shared mechanic line last, so
                # the three choices always read in the same place on every
                # widget however long the field's own help gets.
                mechanic = self.by_id[name].tooltip.splitlines()[-1]
                self.assertEqual(
                    mechanic,
                    f"{SCIFI_PACK.entity_fields[name].group} | {RANDOM}=randomize, "
                    f"value=lock, {NONE}=omit",
                )

    def test_labels_are_the_packs_generic_ones(self) -> None:
        """Per-kind labels are the frontend's job: a widget's label is fixed at
        registration and the kind is not, so the schema carries the generic
        name and ``js/sceneweaver.js`` rewrites it."""
        for name, spec in SCIFI_PACK.entity_fields.items():
            with self.subTest(field=name):
                self.assertEqual(self.by_id[name].display_name, spec.label)

    def test_outputs(self) -> None:
        outputs = self.schema.outputs
        self.assertEqual([o.display_name for o in outputs], ["entity_text", "entity"])
        self.assertEqual(outputs[1].io_type, SCENE_ENTITY_TYPE)


class EntityNodeHonestyTests(unittest.TestCase):
    """The Scene Entity node's preview must match what it contributes.

    Before this round the node passed ``budget=None`` and spoke every clause
    head, while the same entity wired into a scene was cut to the caller's
    allowance -- so the node's face disagreed with the wired result on every
    render. The cap is now the archetype's, applied identically on both paths.
    """

    _HEADS = tuple(
        name
        for name, spec in SCIFI_PACK.entity_fields.items()
        if spec.renders_with is None
    )

    def test_the_node_preview_speaks_what_the_wire_contributes(self) -> None:
        """The preview is what the entity contributes -- except where the host
        scene's coherence pass re-draws a value the node drew at random. A
        difference is always reported, never silent.

        Before this round a wired value was force-locked, so the preview and
        the wired result agreed exactly and a walker could still be drawn in
        vacuum. Now the two may differ, and that difference is the fix."""
        from engine.scene import generate_entity, generate_scene

        checked = 0
        for seed in range(60):
            _, payload = generate_entity(seed, SCIFI_PACK)
            if payload["fields"].get("kind") is None:
                continue
            _, document = generate_scene(
                1000 + seed, SCIFI_PACK,
                wired_entities={1: payload}, entity_count=1,
            )
            record = next(e for e in document["entities"] if e["index"] == 1)
            preview = {
                n for n in self._HEADS if payload["fields"].get(n) is not None
            }
            wired = {n for n in self._HEADS if record.get(n) is not None}
            with self.subTest(seed=seed):
                # The scene never invents a field the node did not speak...
                self.assertLessEqual(wired, preview)
                # ...and a field it drops is named in a warning, not silent.
                if preview - wired:
                    self.assertTrue(
                        any(
                            "a rule dropped" in w
                            for w in document["_meta"]["warnings"]
                        ),
                        f"{preview - wired} dropped with no warning",
                    )
            checked += 1
        self.assertGreater(checked, 0)


def genre_io_int() -> type:
    """The ``io.Int.Input`` class actually in play (real ComfyUI or the stub)."""
    from comfy_api.latest import io

    return io.Int.Input


class ExecuteTests(unittest.TestCase):
    def test_execute_returns_prose_and_a_tagged_payload(self) -> None:
        text, payload = NODE.execute(seed=42).args
        self.assertIsInstance(text, str)
        self.assertTrue(text)
        self.assertEqual(payload["genre"], "scifi")
        self.assertEqual(payload["schema_version"], ENTITY_PAYLOAD_VERSION)

    def test_the_payload_carries_every_field_of_the_pack(self) -> None:
        """A consumer has to be able to tell "not asked for" from "not in this
        genre", and only an explicit key with a null does that."""
        _, payload = NODE.execute(seed=7).args
        self.assertEqual(set(payload["fields"]), set(SCIFI_PACK.entity_fields))

    def test_execute_with_no_widgets_at_all_still_generates(self) -> None:
        """A workflow saved before a widget existed sends fewer kwargs than the
        node now declares. Falling back to each widget's registered default
        keeps that graph generating instead of raising."""
        text, payload = NODE.execute(seed=3).args
        self.assertTrue(text)
        self.assertIsNotNone(payload["fields"]["kind"])

    def test_same_seed_reproduces_and_a_different_seed_does_not(self) -> None:
        first = NODE.execute(seed=11).args[0]
        self.assertEqual(first, NODE.execute(seed=11).args[0])
        self.assertNotEqual(first, NODE.execute(seed=12).args[0])

    def test_a_locked_field_is_honoured_verbatim(self) -> None:
        _, payload = NODE.execute(seed=5, kind="starship", scale="colossal").args
        self.assertEqual(payload["fields"]["kind"], "starship")
        self.assertEqual(payload["fields"]["scale"], "colossal")

    def test_a_field_set_to_none_is_null_in_the_payload(self) -> None:
        _, payload = NODE.execute(seed=5, kind="starship", markings=NONE).args
        self.assertIsNone(payload["fields"]["markings"])

    def test_kind_set_to_none_omits_the_entity_entirely(self) -> None:
        """An omitted entity is not an entity described as empty. Nothing is
        drawn, nothing is said -- absence by omission, never by negation."""
        text, payload = NODE.execute(seed=5, kind=NONE).args
        self.assertEqual(text, "")
        self.assertEqual(set(payload["fields"].values()), {None})

    def test_the_kind_scopes_what_the_other_fields_can_draw(self) -> None:
        for seed in range(6):
            with self.subTest(seed=seed):
                _, payload = NODE.execute(seed=seed, kind="alien creature").args
                form = payload["fields"]["form"]
                if form is not None:
                    self.assertIn(
                        form, genre.pool_for(SCIFI_PACK, "form", "alien creature")
                    )

    def test_a_count_never_survives_the_noun_it_counts(self) -> None:
        """A quantity of nothing in the payload would be believed by every
        consumer downstream. ``celestial body`` has no sensors at all, so its
        sensor count must be null on every seed."""
        for seed in range(20):
            with self.subTest(seed=seed):
                _, payload = NODE.execute(seed=seed, kind="celestial body").args
                fields = payload["fields"]
                for name, spec in SCIFI_PACK.entity_fields.items():
                    if spec.renders_with and fields[spec.renders_with] is None:
                        self.assertIsNone(fields[name])


class WiringContractTests(unittest.TestCase):
    """The payload is only useful if a Scene Weaver slot can actually read it.

    The two nodes are built and tested separately, so the shape they agree on is
    exactly the kind of thing that drifts. This crosses the boundary on purpose.
    """

    def test_the_payload_promotes_a_scene_slot(self) -> None:
        from engine.scene import generate_scene

        _, payload = NODE.execute(seed=99, kind="starship", form="needle hull").args
        _, document = generate_scene(
            1, SCIFI_PACK, wired_entities={2: payload},         )
        slot2 = next(e for e in document["entities"] if e["index"] == 2)
        self.assertEqual(slot2["source"], "wired")
        self.assertEqual(slot2["genre"], "scifi")
        # Slot 2 carries only the brief fields as widgets; the wire promoted it
        # to the full morphology, and Sparse did not cut it back.
        self.assertEqual(slot2["form"], "needle hull")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
