"""The sci-fi ``GenrePack``.

The only module in the repo that knows what "sci-fi" means. Nothing under
``nodes/`` or ``engine/`` imports it; the repo-root ``__init__.py`` does, and
hands the pack to the node factories.

**Pools are empty here by design.** Todo 3 declares the *schema* -- the 21
entity fields in widget order, the three scene fields, the count pairings and
the clause order. Todos 4-12 fill ``pools``, ``labels``, ``tags`` and
``constraints``. Every such gap is marked below with the todo that closes it, so
a later session can find its work without re-reading the plan.

Authoring rules for whoever fills those pools:

* Values are **bare, article-less noun phrases**, singular where a count field
  partners them. The engine composes articles, counts and plurals.
* **Never negate.** An eyeless alien is "a smooth sensory dome where a face
  would be", never "no eyes".
* Subject-intrinsic colour is allowed and wanted (hull colour, engine glow);
  *rendering* colour is not (palettes, grades, "lit by", time of day).
"""
from __future__ import annotations

from collections import OrderedDict

try:
    from .genre import (
        NONE,
        CONTEXT_FIELD,
        ConstraintRule,
        ENVIRONMENT_FIELD,
        FieldSpec,
        GenrePack,
        HeadPhrase,
        KIND_FIELD,
        POOL_DEFAULT_KEY,
        Archetype,
        ProseSpec,
        Sentence,
        RELATION_FIELD,
        RELATION_POSITION_FIELD,
        RELATION_ANY,
        RELATION_ANY_POSITION,
        RULE_EXCLUDE,
        SITUATION_FIELD,
        TAG_CONFLICT_ONLY,
        TAG_NEUTRAL,
        TAG_PEACEFUL_ONLY,
    )
except ImportError:  # pragma: no cover -- standalone/test context
    from data.genre import (
        NONE,
        CONTEXT_FIELD,
        ConstraintRule,
        ENVIRONMENT_FIELD,
        FieldSpec,
        GenrePack,
        HeadPhrase,
        KIND_FIELD,
        POOL_DEFAULT_KEY,
        Archetype,
        ProseSpec,
        Sentence,
        RELATION_FIELD,
        RELATION_POSITION_FIELD,
        RELATION_ANY,
        RELATION_ANY_POSITION,
        RULE_EXCLUDE,
        SITUATION_FIELD,
        TAG_CONFLICT_ONLY,
        TAG_NEUTRAL,
        TAG_PEACEFUL_ONLY,
    )

# Group names. These order the node face and key the ``prompt_json`` grouping,
# so they are part of the contract with the frontend, not free text.
_IDENTITY = "Identity"
_FORM = "Form & Material"
_SURFACE = "Surface & Colour"
_COMPONENTS = "Components"
_SCENE = "Scene"
_RELATIONS = "Relations"


# ---------------------------------------------------------------------------
# Todo 9 -- scale weighting
# ---------------------------------------------------------------------------
#
# Declared up here because ``ENTITY_FIELDS`` below carries it on the ``scale``
# spec. A flat draw over a seven-value ladder makes "colossal" or "planetary"
# the size of nearly a third of all entities, and a scene where everything is
# enormous has no sense of scale at all -- scale reads by *contrast*. These
# weights are relative, not probabilities; the engine normalizes them.
#
# ``identity-forge-family-weight-rule`` is the reason this is a weight map and
# not a shortened list: culling the extremes would concentrate the weight that
# was on them onto whatever survived, which is the same bug wearing a hat.

SCALE_WEIGHTS: dict[str, float] = {
    "tiny": 1.0,
    "small": 2.0,
    "large": 2.0,
    "massive": 1.2,
    "colossal": 0.6,
    "planetary": 0.3,
}

#: Small counts are the common case and the readable one. Without weights a
#: third of every count was a collective, and an entity read as an inventory.
#: The numerals are not weighted against each other -- engine count and eye
#: count being visibly different across seeds is a thing the pack is measured
#: on, and a distribution that favours "a pair of" works against it.
COUNT_WEIGHTS: dict[str, float] = {
    "a dozen": 0.35,
    "rows of": 0.35,
    "banks of": 0.35,
    "a constellation of": 0.35,
    "a ring of": 0.6,
    "a cluster of": 0.6,
    "a fan of": 0.6,
}

#: Which subjects a scene is most often about. Measured, not guessed: stations
#: and artifacts were 32% of a 225-image batch and produced most of its dull
#: frames, while creatures -- the strongest output the pack has -- were 7%.
KIND_WEIGHTS: dict[str, float] = {
    "alien creature": 1.25, "starship": 1.5, "spacefarer": 1.3,
    "robot or mech": 1.2, "surface vehicle": 1.1, "wreck": 1.0,
    "celestial body": 1.0, "space station": 0.7, "alien artifact": 0.6,
}

# ---------------------------------------------------------------------------
# The 21 entity fields -- IN WIDGET ORDER. Never reorder; only ever append.
# ---------------------------------------------------------------------------
#
# Field names are generic so the schema stays genre-portable; the readable name
# comes from ``labels`` per kind ("Engines" on a vessel, "Bioluminescence" on a
# creature), which the frontend swaps in when ``kind`` changes.
#
# The five ``renders_with`` fields head no clause of their own -- a count is
# composed into the noun it counts, a glow colour into the emitter it belongs
# to -- which is why ``entity_clause_order`` below lists sixteen, not twenty-one.

ENTITY_FIELDS: "OrderedDict[str, FieldSpec]" = OrderedDict([
    ("kind", FieldSpec(
        group=_IDENTITY,
        label="Kind",
        tooltip="What this entity fundamentally is. Scopes every other field on "
                "this slot -- its options and its labels. Set to None to leave "
                "the slot empty.",
        brief=True,
        scope=(ENVIRONMENT_FIELD,),
        weights=KIND_WEIGHTS,
    )),
    ("subkind", FieldSpec(
        group=_IDENTITY,
        label="Type",
        tooltip="The specific type within the kind -- a ship class, a creature type.",
        kind_scoped=True,
        tag_scoped=True,
        brief=True,
    )),
    ("scale", FieldSpec(
        group=_IDENTITY,
        label="Scale",
        tooltip="How big it is relative to a person.",
        brief=True,
        scope=(KIND_FIELD,),
        weights=SCALE_WEIGHTS,
        #: A size word on every entity stops meaning anything; scale is absent
        #: about half the time (calibrated so no more than ~45% of entities
        #: carry one).
        omission_weight=8.7,
    )),
    ("condition", FieldSpec(
        group=_IDENTITY,
        label="Condition",
        tooltip="What shape it is in -- pristine, battle-scarred, derelict.",
        brief=True,
        scope=(KIND_FIELD,),
        #: Condition stays most of the time; it is only occasionally the
        #: absence of information.
        omission_weight=0.6,
    )),
    ("form", FieldSpec(
        group=_FORM,
        label="Form",
        tooltip="The silhouette: a hull shape, or a body plan. This is the field "
                "that makes two ships actually look different.",
        scope=("subkind", "kind"),
    )),
    ("material", FieldSpec(
        group=_FORM,
        label="Material",
        tooltip="What it is made of, or covered in.",
        scope=("subkind", "kind"),
    )),
    ("primary_color", FieldSpec(
        group=_SURFACE,
        label="Primary colour",
        tooltip="The colour of the thing itself -- hull, skin, integument. This "
                "describes the subject, not the lighting or the grade.",
        scope=("subkind", KIND_FIELD),
    )),
    ("accent_color", FieldSpec(
        group=_SURFACE,
        label="Accent colour",
        tooltip="A secondary colour: trim, panelling, banding. On a built subject "
                "this competes for a rotating detail slot; lock it to always speak it.",
    )),
    ("markings", FieldSpec(
        group=_SURFACE,
        label="Markings",
        tooltip="Livery, insignia, patterning. Carries no readable lettering or "
                "numerals -- models garble text. On a built subject this competes for a "
                "rotating detail slot; lock it to always speak it.",
        scope=("subkind", KIND_FIELD),
    )),
    ("surface_detail", FieldSpec(
        group=_SURFACE,
        label="Surface detail",
        tooltip="Finish and wear at close range -- pitting, seams, scaling. On a "
                "built subject this competes for a rotating detail slot; lock it to "
                "always speak it.",
        scope=("subkind", "kind"),
    )),
    ("appendages", FieldSpec(
        group=_COMPONENTS,
        label="Appendages",
        tooltip="What sticks out: pylons and fins, or limbs and tentacles. On a "
                "built subject this competes for a rotating detail slot; lock it to "
                "always speak it.",
        scope=("subkind", KIND_FIELD),
        count_partner="appendage_count",
    )),
    ("appendage_count", FieldSpec(
        group=_COMPONENTS,
        label="Appendage count",
        tooltip="How many. Composed into the appendage phrase, so it is only "
                "voiced when there are appendages to count.",
        scope=("appendages", KIND_FIELD),
        weights=COUNT_WEIGHTS,
        count_partner="appendages",
        renders_with="appendages",
    )),
    ("emitters", FieldSpec(
        group=_COMPONENTS,
        label="Emitters",
        tooltip="What glows or thrusts: engines, vents, bioluminescent organs.",
        scope=("subkind", KIND_FIELD),
        count_partner="emitter_count",
    )),
    ("emitter_count", FieldSpec(
        group=_COMPONENTS,
        label="Emitter count",
        tooltip="How many emitters.",
        scope=("emitters", KIND_FIELD),
        weights=COUNT_WEIGHTS,
        count_partner="emitters",
        renders_with="emitters",
    )),
    ("emitter_color", FieldSpec(
        group=_COMPONENTS,
        label="Emitter colour",
        tooltip="The colour of the glow itself. Emissive colour belongs to the "
                "subject; it is not a lighting instruction.",
        renders_with="emitters",
        scope=("subkind", KIND_FIELD),
    )),
    ("armament", FieldSpec(
        group=_COMPONENTS,
        label="Armament",
        tooltip="Weapons, mounted or grown. A Peaceful scene simply leaves this "
                "out rather than saying the thing is unarmed.",
        scope=("subkind", KIND_FIELD),
        tag_scoped=True,
        count_partner="armament_count",
    )),
    ("armament_count", FieldSpec(
        group=_COMPONENTS,
        label="Armament count",
        tooltip="How many weapons.",
        scope=("armament", KIND_FIELD),
        weights=COUNT_WEIGHTS,
        count_partner="armament",
        renders_with="armament",
    )),
    ("sensors", FieldSpec(
        group=_COMPONENTS,
        label="Sensors",
        tooltip="How it perceives: arrays and dishes, or eyes and sensory pits.",
        scope=("subkind", KIND_FIELD),
        count_partner="sensor_count",
    )),
    ("sensor_count", FieldSpec(
        group=_COMPONENTS,
        label="Sensor count",
        tooltip="How many. Four eyes and one eye are different creatures.",
        scope=("sensors", KIND_FIELD),
        weights=COUNT_WEIGHTS,
        count_partner="sensors",
        renders_with="sensors",
    )),
    ("aperture", FieldSpec(
        group=_COMPONENTS,
        label="Aperture",
        tooltip="The opening: a launch bay or viewport, or a mouth and its teeth. "
                "On a built subject this competes for a rotating detail slot; lock it "
                "to always speak it.",
        scope=("subkind", "kind"),
        tag_scoped=True,
    )),
    ("extras", FieldSpec(
        group=_COMPONENTS,
        label="Extras",
        tooltip="One more distinguishing component -- a cargo pod, a dorsal crest. "
                "On a built subject this competes for a rotating detail slot; lock it "
                "to always speak it.",
        scope=("subkind", KIND_FIELD),
    )),
])


# ---------------------------------------------------------------------------
# Scene fields -- owned by the Scene Weaver node, not by an entity
# ---------------------------------------------------------------------------

SCENE_FIELDS: "OrderedDict[str, FieldSpec]" = OrderedDict([
    (ENVIRONMENT_FIELD, FieldSpec(
        group=_SCENE,
        label="Environment",
        tooltip="Where the scene is: deep space through orbit and atmosphere to a "
                "planetary surface or an interior.",
    )),
    (SITUATION_FIELD, FieldSpec(
        group=_SCENE,
        label="Situation",
        tooltip="What this entity is doing -- an event in progress, not a pose.",
        scope=("subkind", KIND_FIELD),
        tag_scoped=True,
    )),
    (RELATION_FIELD, FieldSpec(
        group=_RELATIONS,
        label="Relation",
        tooltip="How two slots relate. Rendered only when both of its entities "
                "exist. Defaults to None: six random relations between four "
                "random entities reads as noise, so this is opt-in.",
        kind_scoped=False,
        tag_scoped=True,
        default=NONE,
    )),
    (RELATION_POSITION_FIELD, FieldSpec(
        group=_RELATIONS,
        label="Position",
        tooltip="Where the first entity sits relative to the second: the spatial "
                "framing of the relation. Rendered only when the relation itself "
                "exists. Not tag-scoped: position is neutral, the action carries "
                "the peace/conflict meaning.",
        kind_scoped=False,
        tag_scoped=False,
        default=NONE,
    )),
    (CONTEXT_FIELD, FieldSpec(
        group=_SCENE,
        label="Context",
        tooltip="What else is in the shot besides the subject -- a secondary, "
                "architectural detail for scale and story. Drawn once per scene "
                "and spoken after the entities. Always a thing in the world, "
                "never a lighting or framing instruction.",
        scope=(ENVIRONMENT_FIELD,),
        # Roughly half of scenes should have no context sentence at all: a
        # device in every single prompt stops being a device. The weight
        # competes with the sum of the pool's value weights, so it is set to a
        # typical pool size, not to 1.0 (which omits only about one scene in
        # ten).
        omission_weight=10.0,
    )),
])


# ---------------------------------------------------------------------------
# Count pairings -- the four fields whose noun the engine pluralizes
# ---------------------------------------------------------------------------

COUNTS: dict[str, str] = {
    "appendages": "appendage_count",
    "emitters": "emitter_count",
    "armament": "armament_count",
    "sensors": "sensor_count",
}


# ===========================================================================
# POOLS
# ===========================================================================
#
# ``{field: {kind or "_default": (values, ...)}}``. ``_default`` is the
# documented fall-through for a kind-scoped field that needs no override; a
# field that is not kind-scoped carries ``_default`` alone.
#
# Authoring rules, enforced by ``tests/validate_data.py`` (Todo 21):
#
# * Bare, article-less noun phrases. Singular wherever a count field partners
#   the pool -- the engine composes "a pair of ion thrusters" from "ion
#   thruster", so an authored plural would double-pluralize.
# * Subject-intrinsic description only. Hull colour, emissive colour, material,
#   finish, shape, scale and count are the subject; palettes, grades, lighting
#   colour and direction, time of day, atmosphere, medium, film stock, framing,
#   shot type, lens and depth of field are the *rendering* and belong to a style
#   pack, never to this one.
# * Never negate. An eyeless alien is "smooth sensory dome", never "no eyes".

#: A deliberately empty pool: this kind has no analogue of this feature at all.
#: Spelled as a named marker so the source says "decided", not "forgotten"; the
#: engine then resolves the field to ``None`` and the prose simply omits it,
#: which is omission, never negation.
_OMITTED: tuple[str, ...] = ()

#: Every ``(field, kind)`` whose pool is ``_OMITTED``, and why. A test asserts
#: this set and the actual empties match exactly in both directions, so neither
#: an undeclared hole nor a stale declaration can survive.
OMITTED_POOLS: frozenset[tuple[str, str]] = frozenset({
    # A planet has no organ of perception. Every other kind-scoped field has
    # something true to say about a celestial body; this one does not, and a
    # ``_default`` fall-through would bolt an antenna dish onto a gas giant.
    ("sensors", "celestial body"),
    # A black hole has no hull colour; the empty pool is how the field
    # resolves to ``None`` for the singularity subkind group.
    ("primary_color", "singularity"),
})

#: Field groups that draw from **one** vocabulary on purpose, so a value
#: appearing in two of them is authoring, not an accident.
#:
#: ``tests/validate_data.py`` otherwise reports a value shared by two
#: clause-heading fields, because a shared value lets one entity draw the same
#: string twice ("carved concentric grooves, marked with carved concentric
#: grooves") and the engine then has to silence a clause the pool paid for. The
#: three colour fields are the one place where that sharing is the point: a hull,
#: its trim and its exhaust are three *roles* over a single palette of pigment
#: words, and forcing them apart would mean inventing a second word for copper.
#: The engine's own repeat guard still stops "an oxide red hull, oxide red
#: accents" reaching a prompt; this only says the pools may overlap.
#: The four counts must differ within one entity. They share one vocabulary by
#: design, and without this an entity draws "a dozen exhaust plumes, a dozen
#: spinal railguns, a constellation of mast-mounted arrays" -- a quantifier used
#: as a verbal tic rather than as a count, which is one of the first things
#: reported about the output. The engine's own repeat guard skips composed
#: companions on purpose ("six thrusters ... six eyes" is how English counts two
#: things), so this is declared rather than inferred.
DISTINCT_COUNTS: tuple[frozenset[str], ...] = (
    frozenset({"appendage_count", "emitter_count", "armament_count", "sensor_count"}),
)

SHARED_VOCABULARY: tuple[frozenset[str], ...] = (
    frozenset({"primary_color", "accent_color", "emitter_color"}),
)


# ---------------------------------------------------------------------------
# Todo 4 -- environment: the viewpoint ladder
# ---------------------------------------------------------------------------
#
# Five bands, coarse to close: deep space, orbit, cloud layer (the "upper
# atmosphere" rung, named without the banned word), planetary surface, and
# interior. Randomizing across the ladder is what stops every scene being a
# ship against a starfield.
#
# **The dual-role decision, carried forward from the previous plan and kept
# deliberately:** a spacecraft, an alien world and a space station each appear
# here as *backdrop* as well as in ``kind`` as *subject*. That is what lets the
# same node express a pure-setting scene (every entity slot None), a
# single-subject scene (one entity, a matching backdrop) and a mixed one (a
# creature aboard a derelict) without a mode switch. Values below marked with a
# trailing comment are the load-bearing half of that pairing.

_ENVIRONMENT_DEEP_SPACE = (
    "deep interstellar void",
    "dense star field",
    "emission nebula",
    "absorption dust nebula",
    "globular star cluster",
    "asteroid field",
    "cometary debris stream",
    "accretion disc of a black hole",
    "binary star system",
    "supernova remnant shell",
    "galactic core star swarm",
    "interstellar dust lane",
    "derelict fleet drift",
    "collapsing molecular cloud",
    "emission shell remnant",
    "twin sun binary",
    "protostar nursery",
    "scattered asteroid cluster",
    "frozen comet belt",
)

_ENVIRONMENT_ORBIT = (
    "low orbit above a blue world",
    "high orbit above a gas giant",
    "gas giant ring system",
    "planetary ring shepherd gap",
    "geosynchronous orbital lane",
    "orbital shipyard scaffold",
    "orbital debris belt",
    "lagrange point station cluster",
    "orbital elevator tether",
    "polar orbit above an ice world",
    "ring station docking approach",
    "derelict shipyard orbit",
    "high polar orbit",
    "derelict disposal orbit",
    "equatorial transfer lane",
    "lunar far-side orbit",
    "station approach corridor",
)

_ENVIRONMENT_CLOUD_LAYER = (
    "upper cloud deck of a gas giant",
    "stratospheric cloud canyon",
    "storm band of a gas giant",
    "ammonia cloud layer",
    "floating cloud city platform",
    "ash plume above a volcanic world",
    "ionospheric charge layer",
    "dense vapour deck",
    "acid cloud deck",
    "thunderhead band",
    "dust storm front",
)

_ENVIRONMENT_SURFACE = (
    "barren alien wilderness",
    "red dust plain of a dead world",
    "orange sand dune sea",
    "black igneous lava field",
    "glacier plain of an ice world",
    "frozen methane flats",
    "crystalline flora spires",
    "bioluminescent fungal floor",
    "alien fungal growth",
    "deep ocean trench of a water world",
    "subglacial ocean of an ice moon",
    "hydrothermal vent field of a water world",
    "rocky extraterrestrial shore",
    "cracked salt flat",
    "basalt mesa badlands",
    "terraforming processor field",
    "asteroid mining pit",
    "subsurface ice cavern",
    "toxic seep basin",
    "overgrown ruin field of an abandoned colony",
    "domed colony concourse",
    "hollowed geode cavern",
    "glass plain",
    "geyser field",
    "floating-rock plateau",
    "methane sea shore",
    "crater basin",
    "obsidian canyon",
    "spore basin",
    "frozen sea ice",
    "black sand tidal flat",
    "fossil megafauna ridge",
    "grove of glass-bladed spires",
    "spore basin of a fungal world",
    "plain of luminous gas-vent flora",
    "crust field of lithophyte mats",
)

_ENVIRONMENT_INTERIOR = (
    "spacecraft interior",  # dual role: also a subject, as a vessel
    "space station interior",  # dual role: also a subject, as a station
    "spacecraft bridge",
    "spacecraft corridor",
    "spacecraft engine room",
    "spacecraft hangar deck",
    "cockpit interior",
    "airlock chamber",
    "cryogenic stasis bay",
    "hydroponics bay",
    "medical bay",
    "observation cupola",
    "station docking ring interior",
    "rotating habitat ring with curving ground",
    "alien hive resin chamber",
    "reactor hall",
    "subterranean moon base corridor",
    "crew commons",
    "brig",
    "cargo hold",
    "armoury",
    "chapel",
    "data vault",
    "maintenance crawlway",
    "crew quarters",
    "cargo airlock",
)

ENVIRONMENT_POOL: tuple[str, ...] = (
    _ENVIRONMENT_DEEP_SPACE
    + _ENVIRONMENT_ORBIT
    + _ENVIRONMENT_CLOUD_LAYER
    + _ENVIRONMENT_SURFACE
    + _ENVIRONMENT_INTERIOR
)

#: Band membership, so a validator (and a later distribution sweep) can assert
#: the ladder still has every rung rather than trusting the comment above.
ENVIRONMENT_BANDS: dict[str, tuple[str, ...]] = {
    "deep space": _ENVIRONMENT_DEEP_SPACE,
    "orbit": _ENVIRONMENT_ORBIT,
    "cloud layer": _ENVIRONMENT_CLOUD_LAYER,
    "planetary surface": _ENVIRONMENT_SURFACE,
    "interior": _ENVIRONMENT_INTERIOR,
}

#: ``{band: (context values,)}`` -- what else is in the shot, per place. Always
#: secondary and plural or architectural, never a second described subject: it
#: is given no form, material or components of its own, and the same affordance
#: machinery excludes it from a place that cannot hold it.
CONTEXT_POOLS: dict[str, tuple[str, ...]] = {
    "subsurface ice cavern": (
        "column of blue ice pillars", "frozen cascade of methane ice",
        "scatter of survey beacons across the cavern wall",
        "scatter of survey drones over the ice ledges",
        "wall of blue glacial ice",
    ),
    "hollowed geode cavern": (
        "wall of giant violet crystals", "scatter of survey drones among the crystal ledges",
        "field of shattered crystal columns", "scatter of survey beacons across the cavern wall",
    ),
    "deep ocean trench of a water world": (
        "field of mineral vent chimneys", "drifting veil of luminous ribbon-drifters",
        "fossil shell of something enormous", "trench wall dropping away into the dark",
    ),
    "subglacial ocean of an ice moon": (
        "sheet of dark ice far overhead", "field of mineral vent chimneys",
        "drifting veil of luminous ribbon-drifters",
        "scatter of survey beacons across the ice wall",
    ),
    "hydrothermal vent field of a water world": (
        "field of mineral vent chimneys", "column of rising vent bubbles",
        "fossil shell of something enormous", "drifting veil of luminous ribbon-drifters",
    ),
    "domed colony concourse": (
        "row of pressurised habitat blocks", "curve of the dome lattice overhead",
        "row of pressurised colony airlocks", "line of parked cargo hover-haulers",
    ),
    "deep space": (
        "scatter of dead hulls",
        "field of slow-tumbling debris",
        "distant station with a row of lights",
        "swarm of escort drones at a safe distance",
        "split hull of a vast derelict",
        "scatter of navigation beacons",
        "distant formation holding station",
        "curtain of dust across the stars",
        "single derelict turning end over end",
        "faint smear of a distant galaxy",
    ),
    "orbit": (
        "distant orbital refinery",
        "half-built orbital ring segment",
        "scatter of landers holding near a docking arm",
        "drifting cloud of hull fragments",
        "row of docking lights along a station arm",
        "curve of navigation lights",
        "distant planet's terminator",
        "distant shipyard hub",
        "column of cargo starships moving out",
        "field of spent boosters",
    ),
    "cloud layer": (
        "bank of cloud stacked to the horizon",
        "lightning front below",
        "spire of a distant cloud city",
        "line of drifting survey aerostats",
        "drift of luminous aerial filter-organisms",
        "distant platform on the horizon",
        "towering wall of storm cloud",
        "cloud of drifting spores",
    ),
    "planetary surface": (
        "row of pressurised habitat domes",
        "wreck of something larger",
        "pressurised skybridge between habitat domes",
        "landing pad ringed with blast shields",
        "low ridge of broken rock",
        "column of dust on the horizon",
        "ring of landing beacons around a pad",
        "column of tracked ore crawlers on the horizon",
        "terraforming processor tower on the horizon",
        "frame of a fallen structure",
        "stand of glass-bladed spires",
        "thicket of glassy spore-towers",
        "slope of lithophyte crusts",
        "swarm of drifting luminous spore-motes",
        "grove of bulbous tube-flora",
        "stand of tall luminous crystal spires",
        "grove of chitin-plated fan-spires",
        "field of light-drinking crystal fronds",
    ),
    "interior": (
        "bay door standing open on the dark",
        "row of suit lockers along one wall",
        "maintenance drone working at the far end",
        "service gantry above the deck",
        "stack of sealed cargo pods",
        "bank of status displays along the wall",
        "lattice of coolant conduits overhead",
        "ladder rising into the dark",
        "line of parked maintenance frames",
        "hatch standing open at the far end",
    ),
}


# ---------------------------------------------------------------------------
# Todo 5 -- kinds and subkinds
# ---------------------------------------------------------------------------
#
# ``kind`` is the control token: it scopes every other pool on the slot *and*
# every widget label. The nine below are deliberately broad and mutually
# exclusive, because a slot picks exactly one and every kind-scoped pool has to
# have something sensible to say for each.
#
# Two of them pair with an ``environment`` value of the same thing -- a vessel
# and "spacecraft interior", and a station and "space station interior". That
# pairing is the dual-role decision: the same concept can be the subject or
# the backdrop, so a scene can be about a ship, set inside one, or both. A
# world used to pair the same way with "barren alien wilderness"; it no longer
# does, because an entity is described but never *placed*, so a world in a
# ground-level scene was put on the sand (see docs/architecture.md).
#
# Subkinds are authored as **noun phrases**, not as the bare adjectives the plan
# sketched ("insectoid", "fungal", "energy-based"). "an energy-based" cannot head
# a clause and "a fungal" is not English; the renderer would have to bolt a kind
# noun onto every one of them, and "an energy-based creature or being" is not a
# sentence anybody wants. Authoring "energy being" and "fungal colony" keeps the
# flavour and lets a bare ``{subkind}`` template already read correctly.

KINDS: tuple[str, ...] = (
    "starship",
    "celestial body",
    "space station",
    "alien creature",
    "spacefarer",
    "robot or mech",
    "alien artifact",
    "surface vehicle",
    "wreck",
)

#: Which kinds a place can hold. The environment is drawn before every slot, so
#: ``kind`` scopes on it: a room cannot hold a starship, deep space cannot hold
#: a rover. The tight interiors are written out longhand rather than spread
#: from ``_TIGHT_INTERIORS`` so ``scripts/builtin_options.py``'s literal-only
#: evaluator can read the pool; a raw environment key beats its band.
KIND_POOLS: dict[str, tuple[str, ...]] = {
    POOL_DEFAULT_KEY: KINDS,
    "deep space": ("starship", "space station", "wreck", "celestial body",
                    "alien artifact", "alien creature", "robot or mech"),
    # A world is no longer the subject while the camera is already at a world --
    # the "planet plopped on the ground" report. Worlds stay in deep space.
    "orbit": ("starship", "space station", "wreck",
              "alien artifact", "spacefarer", "robot or mech", "alien creature"),
    "cloud layer": ("starship", "space station", "wreck", "alien artifact",
                    "alien creature", "robot or mech", "surface vehicle"),
    "planetary surface": ("starship", "alien creature", "spacefarer",
                          "robot or mech", "alien artifact", "surface vehicle", "wreck"),
    # A colony street is a place with ground, a roof overhead and no room for a
    # ship: it holds the same kinds as an interior, not the whole surface band.
    "domed colony concourse": ("spacefarer", "alien creature", "robot or mech",
                            "alien artifact", "surface vehicle", "wreck"),
    # A tight interior holds people, creatures, machines and artifacts. A
    # vehicle or a wreck appears only where the place is built to hold one.
    "interior": ("spacefarer", "alien creature", "robot or mech", "alien artifact"),
    "spacecraft hangar deck": ("spacefarer", "alien creature", "robot or mech",
                               "alien artifact", "surface vehicle", "wreck"),
    "station docking ring interior": ("spacefarer", "alien creature", "robot or mech",
                                      "alien artifact", "surface vehicle", "wreck"),
    "cargo airlock": ("spacefarer", "alien creature", "robot or mech",
                      "alien artifact", "surface vehicle", "wreck"),
    "spacecraft bridge": ("spacefarer", "alien creature", "robot or mech", "alien artifact"),
    "spacecraft corridor": ("spacefarer", "alien creature", "robot or mech", "alien artifact"),
    "spacecraft engine room": ("spacefarer", "alien creature", "robot or mech", "alien artifact"),
    # A cockpit holds a pilot; an alien creature filled it wall to wall.
    "cockpit interior": ("spacefarer", "robot or mech", "alien artifact"),
    "airlock chamber": ("spacefarer", "alien creature", "robot or mech", "alien artifact"),
    "cryogenic stasis bay": ("spacefarer", "alien creature", "robot or mech", "alien artifact"),
    "hydroponics bay": ("spacefarer", "alien creature", "robot or mech", "alien artifact"),
    "medical bay": ("spacefarer", "alien creature", "robot or mech", "alien artifact"),
    "observation cupola": ("spacefarer", "alien creature", "robot or mech", "alien artifact"),
    "alien hive resin chamber": ("spacefarer", "alien creature", "robot or mech", "alien artifact"),
    "reactor hall": ("spacefarer", "alien creature", "robot or mech", "alien artifact"),
    "subterranean moon base corridor": ("spacefarer", "alien creature", "robot or mech", "alien artifact"),
    "subsurface ice cavern": (
        "alien creature", "spacefarer", "robot or mech", "alien artifact", "surface vehicle", "wreck"
    ),
    "hollowed geode cavern": (
        "alien creature", "spacefarer", "robot or mech", "alien artifact", "surface vehicle", "wreck"
    ),
    "deep ocean trench of a water world": (
        "alien creature", "spacefarer", "robot or mech", "alien artifact", "surface vehicle", "wreck"
    ),
    "subglacial ocean of an ice moon": (
        "alien creature", "spacefarer", "robot or mech", "alien artifact", "surface vehicle", "wreck"
    ),
    "hydrothermal vent field of a water world": (
        "alien creature", "spacefarer", "robot or mech", "alien artifact", "surface vehicle", "wreck"
    ),
}

SUBKIND_POOLS: dict[str, tuple[str, ...]] = {
    "starship": (
        "scout ship", "heavy freighter", "warship", "bioship", "salvage hauler",
        "colony ship", "courier", "dreadnought", "strike carrier",
        "survey vessel", "ore hauler", "troop transport", "starliner",
        "interceptor", "generation ship", "hospital ship", "smuggler runner",
        "supply ship",
        "corvette", "survey cutter", "prison transport",
    ),
    "celestial body": (
        "rocky planet", "gas giant", "ice moon", "ringed world", "asteroid",
        "comet", "dwarf planet", "star", "neutron star", "black hole",
        "nebula cloud", "rogue planet", "volcanic moon", "ocean world",
        "binary star pair", "ring system",
        "ice giant", "lava world", "carbon planet",
    ),
    "space station": (
        "ring station", "torus habitat", "orbital shipyard", "mining platform",
        "listening post", "trade hub", "defence platform",
        "space elevator anchor", "research outpost", "refuelling depot",
        "prison station", "void monastery", "terraforming tower",
        "arcology tower", "drydock cradle", "relay array",
        "refinery platform", "observation station", "salvage yard",
    ),
    "alien creature": (
        "insectoid", "arachnoid", "cephalopod", "avian analogue",
        "aquatic swimmer", "fungal colony", "crystalline growth",
        "energy being", "colonial swarm", "reptilian grazer",
        "gelatinous mass", "plant-form", "silicate browser",
        "parasitic brood", "marauder", "gaseous drifter", "burrowing worm-form",
        "void grazer", "lithovore", "hive caste", "spore-caste drone",
        "mimic form", "radial hunter", "filter-swarm", "symbiont pair",
        "sessile brooder", "vacuum drifter",
        "crystal grazer", "plasma drifter", "burrowing horror",
    ),
    "spacefarer": (
        "pilot", "engineer", "captain", "marine", "scientist", "medic",
        "smuggler", "colonist", "navigator", "salvager", "diplomat",
        "mercenary", "raider", "xenobiologist", "crew technician", "prospector",
        "void order priest",
        "quartermaster", "archaeologist", "cartographer", "cyborg operative",
        "amphibian admiral", "mandibled envoy", "reptilian bounty hunter",
        "grey-skinned archivist", "tusked mercenary", "tendril-faced navigator",
        "crested pilot", "four-armed quartermaster", "horned warlord",
        "translucent medic",
    ),
    "robot or mech": (
        "labour droid", "combat mech", "repair drone", "survey drone",
        "android", "exosuit walker", "mining loader", "cargo hauler unit",
        "security automaton", "medical automaton", "swarm drone",
        "sentry unit", "terraforming walker", "courier drone",
        "welding drone", "siege mech", "scout walker",
    ),
    "alien artifact": (
        "monolith", "obelisk", "beacon", "data core", "containment vault",
        "alien engine", "relic sphere", "gate ring", "sarcophagus pod",
        "resonant lattice spire", "drifting cargo pod", "sealed reliquary",
        "power cell array", "navigation marker pylon",
        "memory shard", "gravity anchor", "sealed gateway",
    ),
    "surface vehicle": (
        "rover", "hovercraft", "crawler", "skimmer", "ground transport",
        "walker", "submersible", "high-altitude glider", "tracked hauler",
        "hover bike", "landing shuttlecraft", "drop pod", "sand crawler", "ice cutter",
        "amphibious crawler", "cargo sled", "survey glider",
    ),
    "wreck": (
        "crashed hull", "burnt-out star cruiser", "drifting hulk",
        "stripped void freighter", "ghost starliner", "collapsed station spar",
        "shattered interceptor", "abandoned mining rig", "half-salvaged star carrier",
        "buried lander", "torn-open habitat module", "gutted engine section",
        "sunken submersible", "fossilised bioship",
        "beached hulk", "buried frigate",
    ),
}


#: Subkind groups -- the second control token. ``kind`` says which dropdown a
#: subject came from; a subkind group says what shape of thing it is, which is
#: what ``form``, ``material``, ``aperture`` and ``surface_detail`` actually
#: depend on. Authored as a dict literal so scripts/builtin_options.py's
#: literal-only evaluator can read it, same as _COUNT_BY_KIND.
SUBKIND_GROUPS: dict[str, tuple[str, ...]] = {
    # celestial body
    "solid world":   ("rocky planet", "ice moon", "ringed world", "dwarf planet",
                      "ocean world", "rogue planet", "volcanic moon",
                      "lava world", "carbon planet"),
    "gas world":     ("gas giant", "ice giant"),
    "small body":    ("asteroid", "comet"),
    "star body":     ("star", "neutron star"),
    "singularity":   ("black hole",),
    "diffuse cloud": ("nebula cloud",),
    "binary system": ("binary star pair",),
    "disc system":   ("ring system",),

    # alien artifact
    "slab relic":     ("monolith", "obelisk"),
    "ring relic":     ("gate ring", "sealed gateway"),
    "vessel relic":   ("containment vault", "sarcophagus pod", "sealed reliquary",
                       "drifting cargo pod"),
    "core relic":     ("data core", "alien engine", "power cell array",
                       "memory shard", "gravity anchor"),
    "sphere relic":   ("relic sphere",),
    "antenna relic":  ("beacon", "navigation marker pylon", "resonant lattice spire"),

    # alien creature -- the body-plan classes
    "tentacular":     ("cephalopod",),
    "segmented":      ("insectoid", "arachnoid", "parasitic brood"),
    "vermiform":      ("burrowing worm-form", "burrowing horror"),
    "winged":         ("avian analogue",),
    "aquatic":        ("aquatic swimmer",),
    "amorphous":      ("gelatinous mass", "colonial swarm"),
    "sessile growth": ("fungal colony", "crystalline growth", "plant-form"),
    "quadrupedal":    ("reptilian grazer", "silicate browser", "crystal grazer"),
    "upright hunter": ("marauder",),
    "diffuse being":  ("energy being", "gaseous drifter", "plasma drifter"),
    # alien creature -- the non-analogue body plans. The Earth clades above are
    # kept; these give the draw somewhere else to go.
    "void dweller":    ("void grazer", "vacuum drifter"),
    "radial form":     ("radial hunter",),
    "stone feeder":    ("lithovore",),
    "caste swarm":     ("hive caste", "spore-caste drone"),
    "mimic body":      ("mimic form",),
    "filter swarm":    ("filter-swarm",),
    "symbiotic body":  ("symbiont pair",),
    "brooding colony": ("sessile brooder",),

    # robot or mech
    "humanoid unit":  ("android", "exosuit walker", "medical automaton"),
    "small drone":    ("swarm drone", "courier drone", "repair drone", "survey drone",
                       "welding drone"),
    "heavy chassis":  ("labour droid", "combat mech", "mining loader",
                       "cargo hauler unit", "terraforming walker", "siege mech",
                       "scout walker"),
    "static unit":    ("security automaton", "sentry unit"),

    # wreck -- what the wreck used to be
    "hull wreck":     ("crashed hull", "burnt-out star cruiser", "drifting hulk",
                       "stripped void freighter", "ghost starliner", "shattered interceptor",
                       "half-salvaged star carrier", "buried lander", "fossilised bioship",
                       "beached hulk", "buried frigate"),
    "structure wreck":("collapsed station spar", "abandoned mining rig",
                       "torn-open habitat module"),
    "fragment wreck": ("gutted engine section", "sunken submersible"),

    # surface vehicle
    "wheeled/tracked":("rover", "crawler", "sand crawler", "tracked hauler",
                       "ground transport", "ice cutter", "amphibious crawler"),
    "hovering":       ("hovercraft", "skimmer", "hover bike", "cargo sled"),
    "flying":         ("high-altitude glider", "survey glider"),
    "lander":         ("landing shuttlecraft", "drop pod"),
    "underwater":     ("submersible",),
    "legged":         ("walker",),

    # spacefarer
    "alien people":   ("amphibian admiral", "mandibled envoy", "reptilian bounty hunter",
                       "grey-skinned archivist", "tusked mercenary", "tendril-faced navigator",
                       "crested pilot", "four-armed quartermaster", "horned warlord",
                       "translucent medic"),
}


# ---------------------------------------------------------------------------
# Todo 6 -- form and material
# ---------------------------------------------------------------------------
#
# ``form`` is the load-bearing field of the whole pack. Everything else --
# colour, count, weapon type -- decorates a shape; this *is* the shape. Two
# ships that differ only in hull colour are the same ship, so every value here
# is a **silhouette noun**: something you could pick out as a black cutout
# against a star field. Adjective-only values ("sleek", "angular") are what a
# weak pool looks like and are excluded on purpose.
#
# Every value is a noun phrase, including the body plans, because a creature's
# ``form`` clause is the *subject* of its sentence (see ``subject_leading_kinds``
# below): "a segmented worm body, chitinous ..." works; a bare adjective cannot
# head a sentence and would force the renderer to bolt a noun on afterwards.
#
# Every one of the nine kinds carries its own override -- no ``_default``
# fall-through for ``form``, because a fall-through here is exactly the weak-pool
# failure this todo exists to prevent.

FORM_POOLS: dict[str, tuple[str, ...]] = {
    "starship": (
        "needle hull", "saucer hull", "torus-braced hull", "asymmetric spar frame",
        "arrowhead hull", "tall tiered spire hull", "modular boxy cargo hull",
        "segmented carapace hull", "twin-hulled frame", "disc-and-boom hull",
        "wedge hull", "delta-wing hull", "cylindrical pressure hull",
        "spindle hull", "forked twin-prow hull", "crescent hull",
        "flat wide-winged hull", "lattice truss frame", "sphere-and-spar hull",
        "T-shaped prow hull", "stacked-deck tower hull", "broad blunt-nosed hull",
        "dart hull", "crescent-wing hull", "layered terrace hull",
        "tri-nacelle gravlift hull", "vertical spire lander hull",
        "armoured teardrop hull", "hexagonal gravlift hull", "twin-pylon thruster hull",
    ),
    "celestial body": (
        "oblate sphere", "cratered sphere", "banded sphere", "belted sphere",
        "irregular lumpy mass", "elongated ovoid",
        "shattered fragment cluster", "twin-lobed asteroid",
        "disc of dust and rock", "spiral coil of gas",
        "expanding gas shell", "jagged shard",
        "ridged ellipsoid", "fractured shell", "banded disc",
        "rift-scarred sphere", "storm-streaked sphere", "roiling plasma sphere",
        "flare-wreathed sphere", "accretion disc around a dark core",
        "warped ring of infalling gas", "towering pillar of dust and gas",
        "plasma-bridged double star", "broad sheet of banded rings",
        "tilted ring disc parted by a dark gap", "narrow clumped ring set",
    ),
    "space station": (
        "torus", "spindle", "cluster of docked modules", "hollowed asteroid",
        "stacked disc tiers", "cross-braced cruciform", "geodesic sphere",
        "paired modules on a long truss boom", "radial truss framework",
        "cylinder with radiator fins", "long spindle with a domed cap",
        "spoke-and-hub wheel", "tapered module cluster", "counter-rotating habitat cylinders",
        "trussed wheel", "stacked torus spindle", "spindle with outriggers",
    ),
    "alien creature": (
        "hexapodal frame", "serpentine coil", "radially symmetric body",
        "amorphous mass", "elongated bipedal torso", "arachnoid body",
        "sprawling colonial body", "quivering gel body", "low-slung quadrupedal body", "tentacled bell-body",
        "segmented worm body", "hollow-boned winged frame",
        "branching crystalline lattice", "flattened ray-body",
        "coiled spiral shell", "four-armed bilateral body", "tripodal frame",
        "stalked polyp column", "broad-backed grazer frame",
        "counter-rotating disc body", "vertically stacked disc segments",
        "helical ribbon body", "inverted funnel body",
        "tessellated plate column", "nested shell cluster",
        "bilaterally folded sheet body", "many-jointed membrane frame",
        "crystalline spoke cluster", "wheel-shaped rolling body",
        "translucent bell-shaped body", "long translucent streamer body",
        "plated serpent body", "feathered raptor frame", "segmented burrower body",
        "fused twin-bodied frame", "fan-gilled drifting body",
    ),
    "spacefarer": (
        "tall and lean frame", "broad heavyset frame", "compact wiry frame",
        "armoured bulk", "long-limbed frame", "stooped frame",
        "squat powerful frame", "slight narrow frame",
        "augmented frame with one heavy limb", "hard-suited silhouette",
        "barrel-chested frame", "rangy loose-jointed frame",
        "compact athletic frame", "tall angular frame", "heavy-set armoured frame",
    ),
    # D15: humanoid alien people -- a person whose body says it is not from here.
    "alien people": (
        "tall gaunt bipedal frame", "hunched broad-shouldered frame",
        "slender long-necked frame", "stocky scaled frame",
        "lanky four-armed frame", "heavy horned frame", "narrow crested frame",
    ),
    "robot or mech": (
        "bipedal walker chassis", "quadrupedal walker chassis",
        "tracked chassis", "spherical drone body", "insectile six-legged chassis",
        "humanoid android frame", "twin-armed hauler frame",
        "serpentine segmented chassis", "hovering disc chassis",
        "tripod strider chassis", "boxy utility chassis",
        "eight-legged crawler chassis",
        "wheeled drone body", "multi-legged strider chassis", "armoured humanoid frame",
    ),
    "alien artifact": (
        "monolithic slab", "tapering obelisk", "faceted polyhedron",
        "smooth torus", "nested concentric shells", "radial finned orb",
        "spiral helix column", "smooth ovoid", "fluted spindle",
        "branching antenna lattice", "stacked disc column", "hollow open hoop",
        "faceted shard", "sheared polyhedral shard", "spiralling column",
        "folded geometric ribbon", "looped torque ring", "woven lattice orb",
        "shattered obelisk fragment", "harmonic resonator array",
        "fluted spindle", "split ovoid shell", "twisted triangular prism",
        "hollow tetrahedral frame", "biconvex disc", "helical double spire",
        "floating circle of shards",
    ),
    "surface vehicle": (
        "boxy tracked hull", "six-wheeled rover chassis", "low skimmer hull",
        "bulbous pressurised cabin", "articulated two-section body",
        "walker leg frame", "teardrop hover hull", "articulated cargo crawler chassis",
        "blunt gravlift wedge", "cylindrical submersible hull",
        "open-frame six-wheeled rover chassis", "articulated segmented crawler",
        "twin-hull hauler frame", "low wedge chassis", "six-legged walker frame",
        "blunt re-entry capsule", "squat lander with splayed legs", "flat lifting-body gravlift hull",
    ),
    "wreck": (
        "snapped hull section", "collapsed spar frame", "half-buried hull section",
        "split-open pressure hull", "flattened impact hull", "exposed girder frame",
        "torn saucer section", "crumpled nose cone", "sheared drive-core housing",
        "peeled-back plating shell", "stripped girder frame",
        "burst pressure sphere",
        "torn truss section", "bent frame lattice", "scattered plate cluster",
    ),
    # Group keys -- a subkind's shape class, added alongside the kind keys so a
    # subkind set to None still falls through to its kind.
    "solid world":   ("oblate sphere", "cratered sphere", "ridged ellipsoid", "rift-scarred sphere"),
    "gas world":     ("banded sphere", "belted sphere", "storm-streaked sphere"),
    "small body":    ("irregular lumpy mass", "elongated ovoid", "jagged shard",
                      "twin-lobed rubble pile", "cratered sphere", "shattered fragment cluster",
                      "twin-lobed asteroid", "fractured shell"),
    "star body":     ("roiling plasma sphere", "flare-wreathed sphere"),
    "singularity":   ("accretion disc around a dark core", "warped ring of infalling gas"),
    "diffuse cloud": ("spiral coil of gas", "expanding gas shell", "towering pillar of dust and gas"),
    "binary system": ("close-orbiting star core", "plasma-bridged double star"),
    "disc system":   ("broad sheet of banded rings", "tilted ring disc parted by a dark gap",
                      "narrow clumped ring set", "disc of dust and rock", "banded disc"),

    "slab relic":    ("monolithic slab", "tapering obelisk", "fluted spindle",
                      "shattered obelisk fragment"),
    "ring relic":    ("smooth torus", "hollow open hoop", "floating circle of shards",
                      "looped torque ring"),
    "vessel relic":  ("smooth ovoid", "split ovoid shell", "radial finned orb",
                      "nested concentric shells", "monolithic slab"),
    "core relic":    ("faceted polyhedron", "hollow tetrahedral frame",
                      "nested concentric shells", "stacked disc column", "spiral helix column",
                      "faceted shard", "sheared polyhedral shard", "twisted triangular prism"),
    "sphere relic":  ("smooth ovoid", "nested concentric shells", "biconvex disc",
                      "woven lattice orb"),
    "antenna relic": ("branching antenna lattice", "spiral helix column", "stacked disc column",
                      "helical double spire",
                      "tapering obelisk", "smooth ovoid", "folded geometric ribbon",
                      "harmonic resonator array", "spiralling column"),

    # alien creature -- the body-plan classes
    "tentacular":     ("tentacled bell-body", "radially symmetric body"),
    "segmented":      ("hexapodal frame", "arachnoid body"),
    "vermiform":      ("serpentine coil", "segmented worm body", "plated serpent body",
                       "segmented burrower body"),
    "winged":         ("hollow-boned winged frame",),
    "aquatic":        ("flattened ray-body", "coiled spiral shell"),
    "amorphous":      ("quivering gel body", "sprawling colonial body"),
    "sessile growth": ("branching crystalline lattice", "stalked polyp column"),
    "quadrupedal":    ("low-slung quadrupedal body", "broad-backed grazer frame"),
    "upright hunter": ("elongated bipedal torso", "four-armed bilateral body", "tripodal frame",
                       "feathered raptor frame"),
    "diffuse being":  ("amorphous mass",),
    "void dweller":    ("many-jointed membrane frame", "helical ribbon body",
                        "translucent bell-shaped body", "long translucent streamer body"),
    "radial form":     ("counter-rotating disc body", "inverted funnel body",
                        "wheel-shaped rolling body"),
    "stone feeder":    ("tessellated plate column", "nested shell cluster"),
    "caste swarm":     ("vertically stacked disc segments", "bilaterally folded sheet body"),
    "mimic body":      ("bilaterally folded sheet body", "nested shell cluster"),
    "filter swarm":    ("inverted funnel body", "fan-gilled drifting body"),
    "symbiotic body":  ("crystalline spoke cluster", "fused twin-bodied frame"),
    "brooding colony": ("nested shell cluster", "counter-rotating disc body"),

    # robot or mech
    "humanoid unit":  ("humanoid android frame", "bipedal walker chassis",
                       "armoured humanoid frame"),
    "small drone":    ("spherical drone body", "hovering disc chassis"),
    "heavy chassis":  ("quadrupedal walker chassis", "tracked chassis",
                       "twin-armed hauler frame", "tripod strider chassis",
                       "eight-legged crawler chassis", "boxy utility chassis",
                       "insectile six-legged chassis", "serpentine segmented chassis",
                       "multi-legged strider chassis"),
    "static unit":    ("boxy utility chassis", "tracked chassis", "wheeled drone body"),

    # wreck -- what the wreck used to be
    "hull wreck":     ("snapped hull section", "split-open pressure hull", "flattened impact hull",
                       "torn saucer section", "crumpled nose cone",
                       "peeled-back plating shell", "half-buried hull section"),
    "structure wreck":("collapsed spar frame", "exposed girder frame", "stripped girder frame",
                       "burst pressure sphere", "bent frame lattice", "torn truss section"),
    "fragment wreck": ("sheared drive-core housing", "scattered plate cluster"),

    # surface vehicle
    "wheeled/tracked":("boxy tracked hull", "six-wheeled rover chassis",
                       "articulated cargo crawler chassis", "open-frame six-wheeled rover chassis",
                       "articulated segmented crawler", "articulated two-section body",
                       "low wedge chassis", "twin-hull hauler frame"),
    # Round XVI: only two of these read as unambiguously futuristic (skimmer,
    # gravlift/re-entry forms), so the ground-vehicle silhouette leaned
    # present-day. Three more repulsor forms added here and to "flying" --
    # not to "wheeled/tracked", since a tracked vehicle is not itself an
    # anachronism, only the automotive *parts* elsewhere in the pool were.
    "hovering":       ("low skimmer hull", "teardrop hover hull", "twin-pod repulsor hull",
                       "articulated repulsor-skirt hull", "plated hover-pallet chassis"),
    "flying":         ("blunt gravlift wedge", "flat lifting-body gravlift hull",
                       "faceted anti-grav wedge"),
    "lander":         ("blunt re-entry capsule", "squat lander with splayed legs",
                       "bulbous pressurised cabin"),
    "underwater":     ("cylindrical submersible hull",),
    "legged":         ("walker leg frame", "six-legged walker frame"),
}


# ``material`` is what that silhouette is made of, at arm's length: substance
# and finish, both subject-intrinsic. ``_default`` is the industrial baseline a
# kind with nothing distinctive to say falls through to; every kind whose
# substance genuinely differs from fabricated hull plate overrides it. All nine
# override it today, so the fall-through exists for a *future* kind rather than
# for a current gap -- it is the documented safety net, not a shortcut.

_MATERIAL_DEFAULT = (
    "titanium alloy", "carbon composite", "ceramic ablative shell",
    "brushed aluminium", "rolled alloy plate", "polymer panelling",
    "sintered regolith", "cast iron-nickel", "woven fibre laminate",
    "anodised alloy",
)

MATERIAL_POOLS: dict[str, tuple[str, ...]] = {
    POOL_DEFAULT_KEY: _MATERIAL_DEFAULT,
    "starship": (
        "titanium alloy", "carbon composite", "bioorganic hull plate",
        "ceramic ablative shell", "layered ablative tile",
        "cold-forged alloy plate", "polished chrome plate",
        "matte polymer panelling", "obsidian-black composite",
        "gold foil thermal blanket", "woven ceramic laminate",
        "salvaged mismatched plate", "crystalline lattice hull",
        "ferro-ceramic sheathed plate",
        "ceramic-matrix composite", "reactive armour plate", "woven carbon weave",
    ),
    "celestial body": (
        "basalt crust", "iron-nickel rock", "water ice", "methane ice",
        "silicate regolith", "hydrogen and helium cloud",
        "sulphur-crusted rock", "carbonaceous chondrite", "molten rock",
        "ammonia ice", "dust and gravel", "glass-slag crust",
        "ice-and-dust mantle", "iron sulphide crust", "crystal-veined rock",
    ),
    "space station": (
        "rolled alloy plate", "ferro-ceramic hull panel", "sintered regolith shell",
        "carbon composite truss", "aluminium honeycomb panel",
        "glazed alloy hull panel", "salvaged hull plate",
        "cast basalt armour tile", "ceramic radiator plate", "woven carbon lattice",
        "modular truss panel", "printed regolith panel", "layered ceramic shell",
    ),
    "alien creature": (
        "chitinous carapace", "translucent flesh", "crystalline lattice",
        "mineral hide", "leathery hide", "plated bone", "waxy cuticle",
        "fibrous bark-skin", "gelatinous membrane", 
        "scaled hide", "silicate shell", "resinous secretion",
        "fungal tissue",
        "photonic scale", "ferrofluid skin", "calcified lace",
        "spun silicate floss", "self-annealing resin", "iridescent film",
        "keratinous plate", "gel-sheathed membrane", "silicate fibre mat",
        "crystallised shell",
    ),
    "spacefarer": (
        "canvas-weave vac suit", "woven thermal-weave suit", "mail-weave undersuit",
        "armour-composite hardsuit", "cracked polymer flight suit",
        "reinforced flight suit", "quilted insulation suit", "ceramic hardsuit",
        "polymer soft-suit", "much-repaired vac suit",
        "thermal-lined pressure suit", "impact-gel armour suit", "woven meta-aramid suit",
    ),
    # D15: a soft-suit keeps a bubble helmet, so an alien face stays visible.
    "alien people": (
        "polymer soft-suit", "woven thermal-weave suit", "mail-weave undersuit",
        "reinforced flight suit", "woven meta-aramid suit", "ceremonial command uniform",
        "layered envoy robes", "scaled flight harness",
    ),
    "robot or mech": (
        "brushed alloy plate", "matte polymer shell",
        "ceramic armour plate",
        "chrome-finished casing", "carbon fibre shell", "welded scrap plate",
        "anodised alloy panel", "rubberised sheath",
        "segmented alloy plating", "armoured ceramic plating", "composite armour shell",
    ),
    "alien artifact": (
        "black stone", "unknown dense alloy", "faceted crystal", "fused glass",
        "polished obsidian", "corroded bronze", "self-repairing ceramic",
        "gold-veined stone", "resin-cast composite", "meteoric iron",
        "vitrified glass", "engineered crystal", "carbon-weave composite",
    ),
    "surface vehicle": (
        "rolled alloy plate", "dust-caked composite",
        "ceramic underbelly plate", "moulded polymer shell",
        "sealed ceramic-alloy plate", "sealed pressure alloy",
        "mismatched salvaged panelling", "anodised alloy shell",
        "impact-resistant composite plate",
        "reinforced composite hull", "abrasion-resistant plate", "sealed alloy shell",
    ),
    "wreck": (
        "oxidised steel plate", "delaminated composite",
        "scorched ceramic tile", "corroded alloy", "salt-crusted plate",
        "sand-scoured panel", "fungus-grown plating",
        "bleached brittle polymer", "frost-shattered hull plate",
        "slag-fused metal",
        "corroded frame alloy", "cracked ceramic plate", "rusted composite panel",
    ),
    # Celestial subkind groups -- what a world is made of depends on what kind
    # of world it is. A solid world keeps the whole celestial pool; the diffuse
    # subkinds are omitted by the phenomenon archetype and need no key here.
    "gas world":  ("hydrogen and helium cloud bands", "ammonia ice clouds",
                   "water vapour cloud decks"),
    "small body": ("iron-nickel rock", "carbonaceous chondrite", "dust and gravel",
                   "silicate regolith", "water ice", "glass-slag crust"),
    "disc system": ("water ice and dust", "dark carbon rubble",
                    "ice-coated boulders"),
    "star body":  ("molten rock",),
    "solid world": (
        "basalt crust", "iron-nickel rock", "water ice", "methane ice",
        "silicate regolith",
        "sulphur-crusted rock", "carbonaceous chondrite", "molten rock",
        "ammonia ice", "dust and gravel", "glass-slag crust",
    ),
    # A gelatinous mass has no hide, pelt or shell.
    "amorphous": ("translucent flesh", "gelatinous membrane", "resinous secretion", "waxy cuticle"),
    "tentacular": ("gelatinous membrane", "translucent flesh"),
    # Round XIV: an Earth body plan in an Earth integument is the Earth animal.
    # A chitin-plated arachnoid rendered as a tarantula and a leathery serpent as
    # a snake; the plan stays, the skin is what makes it alien.
    "segmented": ("crystallised shell", "silicate shell", "photonic scale", "calcified lace"),
    "vermiform": ("ferrofluid skin", "gelatinous membrane", "gel-sheathed membrane"),
    "winged": ("photonic scale", "iridescent film", "plated bone"),
    "aquatic": ("scaled hide", "gel-sheathed membrane"),
    "sessile growth": ("fungal tissue", "fibrous bark-skin", "waxy cuticle"),
    "quadrupedal": ("scaled hide", "leathery hide", "mineral hide", "plated bone"),
    "upright hunter": ("leathery hide", "scaled hide"),
    "diffuse being": ("photonic scale", "ferrofluid skin", "iridescent film"),
    "void dweller": ("crystallised shell", "iridescent film"),
    "radial form": ("silicate shell", "calcified lace"),
    "stone feeder": ("mineral hide", "silicate shell", "calcified lace",
                     "crystalline lattice"),
    "caste swarm": ("chitinous carapace", "keratinous plate"),
    "mimic body": ("gelatinous membrane", "photonic scale", "self-annealing resin"),
    "filter swarm": ("gel-sheathed membrane", "translucent flesh"),
    "symbiotic body": ("translucent flesh", "fungal tissue", "resinous secretion",
                       "spun silicate floss"),
    "brooding colony": ("chitinous carapace", "silicate shell", "silicate fibre mat"),
    # A grown hull is organic all the way through. A metal word on one is the
    # render trap the batch showed, so the subkind keys are declared rather than
    # left to the starship pool.
    "bioship": (
        "bioorganic hull plate", "chitin-plated hull", "resin-grown hull shell",
        "veined membrane sheath", "calcified shell plating", "crystalline lattice hull",
    ),
    "fossilised bioship": (
        "calcified shell plating", "petrified chitin plate", "fossil resin shell",
    ),
}

# ---------------------------------------------------------------------------
# Todo 7 -- colour and markings: the split-colour rule
# ---------------------------------------------------------------------------
#
# **The rule, stated once.** A style pack owns how a picture is *rendered*: its
# palette, its grade, the colour and direction of its light, the time of day,
# the atmosphere, the film stock. This pack owns what the subject *is*, and a
# hull is red the way it is titanium -- a property of the object, true before
# anyone points a light at it. So "oxide red" is a legal value and "teal-and-
# orange grade" is not; "cyan" as the colour a thruster emits is legal and "lit
# by cyan light" is not. Both halves are enforced, in both directions: a planted
# "cinematic lighting" must fail the boundary test and a planted "crimson hull"
# must pass it, or the rule has collapsed into a blanket ban on colour and the
# pack can no longer describe a ship.
#
# The three colour fields are **not** kind-scoped. A colour is a colour whether
# it is on a hull, a hide or a moon, and nine near-identical copies of the same
# list would be nine places for the pools to drift apart. ``markings`` *is*
# kind-scoped -- squadron insignia and moulted banding have nothing in common.

#: What the thing itself is: hull, skin, integument, crust. Muted and material
#: first, because a random draw over saturated primaries makes every scene look
#: like a toy shelf; the accent pool below is where the bright colours live.
_PRIMARY_COLOR_DEFAULT: tuple[str, ...] = (
    "gunmetal grey", "oxide red", "off-white", "matte black",
    "brushed silver", "dull bronze", "olive drab", "sand beige",
    "rust brown", "deep navy", "hull grey", "ochre yellow", "slate blue",
    "charcoal", "zinc white", "copper", "pewter", "burnt orange", "viridian green",
    "matte white", "umber", "cobalt blue", "manganese violet", "cadmium yellow",
    "pale teal", "obsidian black", "titanium white", "brass gold",
    "carmine red", "ash grey", "verdigris", "pale sand", "deep teal",
    "warm taupe", "cool grey", "chromium green", "burnt sienna", "deep indigo",
    "dusty pink", "platinum grey",
)

#: The colour of a thing's own body. Scoped on ``subkind`` because a star's
#: colour is not a hull's: a stellar body takes stellar colours, a black hole
#: takes none at all (its entry is empty and the field resolves to ``None``),
#: and a nebula takes emission hues. ``_default`` is the hull palette.
PRIMARY_COLOR_POOLS: dict[str, tuple[str, ...]] = {
    POOL_DEFAULT_KEY: _PRIMARY_COLOR_DEFAULT,
    "star body": ("blue-white", "white", "golden yellow", "deep orange", "dull red"),
    "binary system": ("blue-white", "white", "golden yellow", "deep orange", "dull red"),
    "singularity": (),
    "diffuse cloud": ("red-violet", "teal", "amber", "crimson", "electric blue"),
    "diffuse being": ("emissive violet", "radiant gold", "electric blue", "pale green", "hot white"),
}

#: The union, for the trait map and the spoken forms.
PRIMARY_COLOR_POOL: tuple[str, ...] = tuple(
    dict.fromkeys(v for values in PRIMARY_COLOR_POOLS.values() for v in values)
)

#: Trim, banding, panel edges and piping -- the second colour, in small areas,
#: which is where a strong colour reads as livery instead of as a paint job.
ACCENT_COLOR_POOL: tuple[str, ...] = (
    "hazard yellow", "warning orange", "signal red", "arctic white",
    "obsidian black", "chrome silver", "brass gold", "cobalt blue", "lime green",
    "magenta", "deep purple", "turquoise", "carmine red", "copper", "gunmetal",
    "cream", "pale grey", "safety orange", "electric blue", "bronze",
    "verdigris green", "pink gold", "sulphur yellow", "ink blue", "oxide red",
    "vermilion orange", "pale viridian", "royal blue", "pale vermilion", "acid yellow",
    "safety green", "copper pink",
)

#: The colour of what the subject *emits* -- exhaust, bioluminescence, a reactor
#: seam. Emissive colour belongs to the object, not to the lighting rig, and it
#: is the single field that most changes how a ship reads at a glance.
EMITTER_COLOR_POOL: tuple[str, ...] = (
    "cyan", "deep blue", "violet", "magenta", "emerald green", "amber",
    "sodium orange", "crimson", "ultraviolet white", "pale cyan", "acid green",
    "deep gold", "soft magenta", "deep orange", "pale lilac", "arc white",
    "aquamarine", "sulphur yellow", "plasma pink", "indigo",
    "scarlet", "hot pink", "signal green", "reactor blue", "amber gold",
    "violet blue", "pale gold", "deep violet",
)
EMITTER_COLOR_POOLS: dict[str, tuple[str, ...]] = {
    POOL_DEFAULT_KEY: EMITTER_COLOR_POOL,
    "star body": ("blue-white", "golden yellow", "deep orange", "dull red", "arc white"),
    "binary system": ("blue-white", "golden yellow", "deep orange", "dull red", "arc white"),
    "singularity": ("violet", "ultraviolet white", "pale cyan", "amber gold"),
    "diffuse cloud": ("soft magenta", "aquamarine", "crimson", "deep violet", "emerald green"),
    "gas world": ("pale gold", "pale cyan", "aquamarine", "violet blue"),
    "solid world": ("deep orange", "deep gold", "pale cyan", "sulphur yellow", "crimson"),
    "small body": ("pale cyan", "pale gold", "arc white"),
}


# ``markings`` carries **no readable text in v1** -- no lettering, numerals,
# registry codes, callsigns, glyphs or runes. Diffusion models garble text and
# the usual base negative fights it, so a value naming any of those trades a
# reliable shape for an unreliable smear. Insignia, chevrons, discs and stencil
# *blocks* are shapes and stay. Recorded in ``docs/architecture.md`` as a
# decision, not as a gap; ``tests/validate_data.py`` enforces it.

_MARKINGS_DEFAULT = (
    "hazard chevrons", "weathered stencil blocks", "dazzle patterning",
    "banded striping", "painted hexagonal faction emblem", "contrasting panel blocking",
    "blast scoring streaks", "chipped hazard striping",
    "etched fractal panelling",
)

MARKINGS_POOLS: dict[str, tuple[str, ...]] = {
    POOL_DEFAULT_KEY: _MARKINGS_DEFAULT,
    "starship": (
        "hazard chevrons", "angular faction emblem", "weathered stencil blocks",
        "dazzle patterning", "prow sigils", "banded stern markings",
        "painted hexagonal faction emblem", "contrasting panel blocking",
        "blast scoring streaks", "chipped hazard striping",
        "etched fractal panelling", "faded house livery",
        "chequered docking bands", "stern flash striping",
        "worn docking scars", "faded warning bands", "scored panel edges",
    ),
    "celestial body": (
        "cloud belt banding", "swirling storm ovals", "crater ray splashes",
        "dust streak lanes", "polar cap contrast", "fracture line tracery",
        "mottled ice sheeting", "sulphur staining", "gap banding",
        "lava vein tracery", "impact scar clustering",
        "cloud band striping", "frost patch mottling", "crater floor contrast",
    ),
    # Round XII (D12): a world-scale marking, keyed by the body it belongs to.
    "gas world": ("cloud belt banding", "swirling storm ovals", "cloud band striping",
                  "polar cap contrast"),
    "solid world": ("crater ray splashes", "dust streak lanes", "polar cap contrast",
                    "fracture line tracery", "mottled ice sheeting", "sulphur staining",
                    "lava vein tracery", "impact scar clustering", "frost patch mottling",
                    "crater floor contrast"),
    "small body": ("crater ray splashes", "impact scar clustering", "dust streak lanes"),
    "disc system": ("gap banding", "dust streak lanes"),
    "space station": (
        "hazard chevrons", "docking guide striping", "sectional colour blocking",
        "house sigils", "radiation trefoil markings",
        "weathered stencil blocks", "dazzle patterning",
        "panel-line contrast", "rust bleed streaks", "bay-mouth outline striping",
        "sectional paint blocking", "worn hazard banding", "stained panel edges",
    ),
    "alien creature": (
        "moulted banding", "spotted dappling", "countershaded gradient",
        # "eyespot" (a camouflage marking, like a moth wing's false eye) reads
        # as a literal extra eye on the creature -- render-trap-word class.
        "warning chevron patterning", "concentric-ring rosettes", "ripple striping",
        "mottled camouflage blotching", "iridescent scale sheen",
        "veined tracery", "brindled patterning", "rosette clustering",
        "chevron-scaled flanks",
        "banded dorsal striping", "spotted flank dappling", "iridescent banding",
    ),
    "spacefarer": (
        "colony sigil emblems", "rank chevrons", "shoulder hazard striping",
        "painted helmet stripes", "scorch-marked chest plates",
        "ceremonial suit striping", "luminous seam piping",
        "sectional colour blocking", "worn guild sigil emblems",
        "luminous hazard piping",
        "faded crew sigil emblems", "worn rank chevrons", "contrast seam piping",
    ),
    "robot or mech": (
        "hazard chevrons", "unit sigils", "sectional colour blocking",
        "weathered stencil blocks", "radiation trefoil markings",
        "panel-line contrast", "scuffed paint chipping", "dazzle patterning",
        "warning striping", "oil-streak staining",
        "faded unit sigils", "scuffed warning bands", "contrast joint striping",
    ),
    "alien artifact": (
        "banded relief collars", "inlaid metal tracery",
        "spiral relief carvings", "faceted lattice reliefs",
        "polished and matte contrast banding", "verdigris staining",
        "radial fluting", "chevron relief bands", "wind-scour mottling",
        "inlaid crystal studding",
        "relief spiral carvings", "inlaid geometric tracery", "contrast relief banding",
    ),
    "surface vehicle": (
        "hazard chevrons", "dust-caked striping", "contrasting panel blocking",
        "dust-splashed mottling", "warning striping", "frame colour banding",
        "weathered stencil blocks", "painted hexagonal faction emblem",
        "reflective corner tape banding", "scorch streaks",
        "faded route stripes", "dust-scoured livery", "contrast panel edging",
    ),
    "wreck": (
        "faded livery remnants", "patchy oxidation", "blast scoring",
        "torn paint flaking", "salt-crust blooming", "fungal growth mottling",
        "scorched banding", "sand-scour polishing", "ice-rime crusting",
        "mismatched repair panels",
        "faded hull banding", "oxidation streak tracery", "stripped livery outlines",
    ),
    # A phenomenon has no crust to crater or scar: its markings are banding and
    # filament, so the celestial pool's crater rays and lava veins must not reach it.
    "star body":     ("granulation mottling", "sunspot clustering", "spectral banding"),
    "singularity":   ("accretion banding", "tidal stream striping", "jet knotting"),
    "diffuse cloud": ("filamentary banding", "dust lane striping", "ionisation front contrast"),
    "binary system": ("tidal stream striping", "accretion banding", "spectral banding"),
    "diffuse being": ("shimmer banding", "energy veining", "luminous mottling"),
}

# ---------------------------------------------------------------------------
# Todo 8 -- the six component pools
# ---------------------------------------------------------------------------
#
# These are the fields that make an entity a *specific* one rather than a class:
# how many engines, what they are, what is bolted to the hull, how it perceives,
# what opening it has. Four of the six take a count partner.
#
# **Singular, always.** ``appendages``, ``emitters``, ``armament`` and
# ``sensors`` are pluralized by the engine ("a pair of ion thrusters" from "ion
# thruster"), so an authored plural double-pluralizes. ``aperture`` and
# ``extras`` take no count and are still authored singular for consistency.
#
# ``armament`` deliberately has *no* override for ``celestial body`` or
# ``artifact or object``: both fall through to ``_default`` so that Todo 12's
# "a celestial body carries no armament" rule has a real value to exclude and
# therefore actually fires. A rule that can never fire is a rule to delete.

_APPENDAGES_DEFAULT = (
    "strut", "spar", "boom arm", "folding vane", "fin",
)

APPENDAGE_POOLS: dict[str, tuple[str, ...]] = {
    POOL_DEFAULT_KEY: _APPENDAGES_DEFAULT,
    # Round XV: every part that stood off the hull on a boom, a spar or an arm
    # left this pool -- solar vanes drew detached solar panels, outrigger pods
    # drew airliner turbofans, grapple arms and towed arrays drew cranes and
    # cables. A starship's parts are integrated into its silhouette.
    "starship": (
        "nacelle pylon", "swept fin", "sponson pod", "canard fin", "dorsal armour ridge",
        "ventral stabiliser fin", "stepped command tower", "ventral armour blade",
        "hull-flush turret blister", "stern stabiliser blade", "angled heat-sink fin",
        "armoured sensor prow",
    ),
    # No moonlets here. ``appendages`` is the counted "it bears N of them" slot,
    # and a model draws "four orbiting moonlets" as four spheres stuck to the
    # planet's surface -- the "moons attached to another planet" report, and the
    # single most common complaint about world subjects. A world keeps its moon
    # through ``extras``, which has no count partner and so is always singular:
    # "a shepherd moon" reads as a moon, "six shepherd moonlets" never does.
    "solid world": (
        "debris streamer", "tidal tail", "cryovolcanic plume", "tidal ridge",
    ),
    "small body": (
        "dust tail", "ion tail", "debris streamer",
        "ejecta ray", "rock spire", "ice plume",
    ),
    "disc system": (
        "clumped ringlet", "dust spoke",
    ),
    "celestial body": (
        "sweeping arc", "debris streamer", "tidal tail",
        "ejecta ray", "dust lane", "ice plume", "rock spire",
        "cryovolcanic plume", "tidal ridge",
    ),
    "space station": (
        "docking spar", "mooring boom",
        "antenna mast", "rotating spoke", "gantry arm", "docking boom",
        "pressurised connector tube", "service gantry arm",
        "drydock cradle arm", "spin counterweight module",
        "pressurised observation blister", "docking collar ring",
    ),
    "alien creature": (
        "jointed limb", "prehensile tentacle", "hooked claw arm",
        "membranous wing", "chitinous scythe arm", "grasping pincer",
        "feathered wing", "muscular flipper", "spindly leg",
        "gripping foot pad", "whip tail", "sucker-lined arm",
        "swivelling sensory stalk", "ciliated ribbon", "folding fin membrane",
        "articulated arm",
        "prehensile tongue", "spined tail club", "barbed tentacle",
        "paddle fin",
        "spore vent frond",
        "rooted frond cluster",
        "filter stalk",
    ),
    "spacefarer": (
        "prosthetic arm", "articulated exo-limb", "gauntleted hand", "cybernetic arm",
        "magnetic boot", "utility manipulator arm", "backpack thruster pod",
        "magnetic safety clamp", "shoulder optic boom",
        "tool harness arm", "grapple line spool", "marker pouch",
    ),
    "robot or mech": (
        "hydraulic limb", "articulated manipulator arm", "telescoping manipulator",
        "stabiliser outrigger", "tool turret arm", "folding tool arm",
        "sampling probe arm", "welding torch arm", "shield mount arm",
        "rock-cutting claw arm", "plasma welding head",
    ),
    "small drone": (
        "articulated manipulator arm", "sampling probe arm", "telescoping manipulator",
        "tool turret arm", "plasma welding head",
    ),
    "heavy chassis": (
        "hydraulic limb", "articulated manipulator arm", "stabiliser outrigger",
        "telescoping manipulator", "welding torch arm", "jointed crawler leg",
        "rock-cutting claw arm", "folding tool arm", "plasma welding head",
    ),
    "humanoid unit": (
        "hydraulic limb", "articulated manipulator arm", "shield mount arm",
        "tool turret arm",
    ),
    "static unit": (
        "telescoping manipulator", "tool turret arm", "shield mount arm",
        "stabiliser outrigger",
    ),
    "alien artifact": (
        "projecting spar", "radial fin", "hinged panel wing",
        "suspended orbiting shell", "spiral fluke", "jutting crystal fin",
        "folded petal plate", "anchoring base flange",
        "hovering fragment", "orbiting shell segment", "projecting vane",
    ),
    "surface vehicle": (
        "articulated arm", "folding ramp", "roof sensor pod",
        "heavy drill arm", "stabiliser fin", "hinged fin panel",
        "regolith scraper plate", "sample drill arm", "angled deflector plate",
        "rear engine cowling", "repulsor stabiliser vane",
    ),
    "wheeled/tracked": (
        "articulated arm", "folding ramp", "heavy drill arm",
        "regolith scraper plate", "angled deflector plate", "rear engine cowling",
        "sample drill arm", "roof sensor pod",
    ),
    "hovering": ("stabiliser fin", "hinged fin panel", "rear engine cowling",
                 "roof sensor pod", "repulsor stabiliser vane"),
    "flying": ("stabiliser fin", "hinged fin panel", "roof sensor pod",
               "repulsor stabiliser vane"),
    "lander": ("folding ramp", "angled deflector plate", "articulated arm",
               "roof sensor pod"),
    "underwater": ("articulated arm", "stabiliser fin", "sample drill arm",
                   "ballast tank blister"),
    "legged": ("articulated arm", "heavy drill arm", "roof sensor pod",
               "angled deflector plate", "sample drill arm"),
    "wreck": (
        "snapped spar", "peeled hull-skin strip", "torn hull flap",
        "torn engine mount", "sheared fin", "exposed hull frame",
        "drifting debris cluster", "twisted hull girder",
        "bent frame spar", "peeled-back armour plate", "collapsed hull girder",
    ),
    # A body without limbs must not grow legs or wings.
    "amorphous":      ("prehensile tentacle", "sucker-lined arm", "whip tail"),
    "sessile growth": ("spore vent frond", "rooted frond cluster", "filter stalk"),
    # A body without a solid surface has arcs, tails and filaments -- never rock
    # spires, ejecta rays or orbiting moonlets. The phenomenon archetype keeps
    # ``appendages``, so these subkinds need their own vocabulary.
    "star body":     ("coronal streamer", "prominence loop", "flare ribbon",
                      "solar wind tail"),
    "singularity":   ("sweeping arc", "tidal tail", "dust lane", "accretion spiral arm"),
    "binary system": ("tidal stream", "accretion arc", "dust lane"),
    "diffuse cloud": ("filamentary tendril", "dust lane", "ionisation front"),
    "diffuse being": ("trailing plasma tendril", "drifting filament", "energy wisp"),
    "gas world":     ("sweeping arc", "equatorial band", "storm band filament"),
    "tentacular": ("prehensile tentacle", "sucker-lined arm", "barbed tentacle", "prehensile tongue"),
    "segmented": ("chitinous scythe arm", "grasping pincer", "jointed limb", "hooked claw arm", "articulated arm"),
    "vermiform": ("ciliated ribbon", "gripping foot pad", "whip tail"),
    "winged": ("membranous wing", "feathered wing", "folding fin membrane"),
    "aquatic": ("muscular flipper", "paddle fin"),
    "quadrupedal": ("spindly leg", "gripping foot pad", "articulated arm",
                    "spined tail club"),
    "upright hunter": ("articulated arm", "prehensile tongue", "jointed limb"),
    "void dweller": ("trailing plasma tendril", "drifting filament", "folding fin membrane"),
    "radial form": ("ciliated ribbon", "swivelling sensory stalk", "barbed tentacle"),
    "stone feeder": ("gripping foot pad", "spindly leg", "swivelling sensory stalk"),
    "caste swarm": ("jointed limb", "spindly leg", "hooked claw arm"),
    "mimic body": ("prehensile tentacle", "ciliated ribbon", "gripping foot pad"),
    "filter swarm": ("ciliated ribbon", "muscular flipper", "swivelling sensory stalk"),
    "symbiotic body": ("prehensile tentacle", "sucker-lined arm", "jointed limb"),
    "brooding colony": ("swivelling sensory stalk", "ciliated ribbon", "prehensile tentacle"),
}


# ``emitters`` are what the thing thrusts, vents or shines *with*. The emissive
# colour is a separate field composed into this clause, so the values here name
# the fitting and never its colour or its brightness.

_EMITTERS_DEFAULT = (
    "vent port", "exhaust nozzle", "seam strip", "discharge coil",
    "radiator panel",
)

EMITTER_POOLS: dict[str, tuple[str, ...]] = {
    POOL_DEFAULT_KEY: _EMITTERS_DEFAULT,
    "starship": (
        "ion thruster", "fusion torch nozzle", "plasma vent",
        "manoeuvring thruster", "reactor exhaust port", "drive nacelle",
        "luminous hull seam", "beacon strip", "heat radiator panel",
        "arc discharge coil", "warp coil bank", "exhaust nozzle",
        "manoeuvring vent", "radiator seam", "drive plume nozzle",
    ),
    "solid world": (
        "volcanic vent", "lava fissure", "geyser vent", "cryovolcanic plume vent",
        "auroral band", "auroral curtain", "dust plume vent",
    ),
    # A bare asteroid/comet is not volcanically active -- it fell through to
    # "celestial body"'s planet-scale vocabulary below and grew "volcanic
    # vent"/"lava fissure"/"geyser vent", which read as engine ports punched
    # in a rock. This is its own pool now: outgassing and sublimation only,
    # and "vent" itself is dropped from the plain dust plume, which is the one
    # value most often mistaken for a drive exhaust.
    "small body": (
        "dust plume", "sublimating ice fissure", "outgassing plume", "sunward tail streamer",
    ),
    "celestial body": (
        "volcanic vent", "plasma jet", "auroral band", "lava fissure",
        "geyser vent", "storm discharge arc", "accretion streamer",
        "radiant polar jet",
        "cryovolcanic plume vent", "dust plume vent", "auroral curtain",
    ),
    # Round XIV: lights only. A station's heat vents, welding bay lights and
    # station-keeping thrusters rendered as glowing eyes, a red plume and a
    # purple exhaust fan on a thing that should read as parked in space.
    "space station": (
        "docking beacon", "luminous window band",
        "signal mast beacon", "beacon strobe",
        "navigation light", "docking guide light", "antenna tip beacon",
        "hangar mouth light bar", "observation deck window strip", "running light string",
    ),
    "alien creature": (
        "bioluminescent organ", "vent pore", "photophore", "luminous sac",
        "luminous stripe", "radiant frill", "incandescent eye-spot",
        "phosphorescent tendril", "spiracle vent", "ember-hot fissure",
        "luminous flank slit", "luminous ventral patch", "heat-pit organ",
    ),
    "spacefarer": (
        "helmet visor strip", "suit seam piping", "chest indicator panel",
        "shoulder beacon", "tool torch emitter", "backpack thruster vent",
        "wrist console panel", "collar light strip",
        "suit status strip", "glove beacon", "helmet beacon",
    ),
    "robot or mech": (
        "optic emitter", "joint seam strip", "heat sink grille",
        "reactor core window", "status indicator band",
        "arc welding emitter", "cooling vent slot",
        "joint seam beacon", "power core window", "running beacon",
    ),
    "small drone": ("optic emitter", "joint seam strip", "thruster nozzle",
                    "status indicator band", "cooling vent slot",
                    "power core window"),
    "alien artifact": (
        "luminous inlay vein", "radiant core aperture", "emissive fracture line",
        "pulsing node", "discharge spire", "halo ring", "resonance filament",
        "seam beacon", "pulsing aura", "emissive glyph band",
    ),
    # "front/tail beacon bar" read as a headlight/tail-light light bar -- the
    # single most literal automotive tell in the pool. Renamed to an energy
    # trace rather than a lamp.
    "surface vehicle": (
        "forward ion-trace strip", "aft ion-trace strip", "beacon strip",
        "battery cell window", "reactor vent", "arc discharge coil",
        "arc welding port", "hover skirt emitter",
    ),
    "wheeled/tracked": ("forward ion-trace strip", "aft ion-trace strip", "beacon strip",
                        "battery cell window", "reactor vent",
                        "arc discharge coil", "arc welding port"),
    "legged": ("forward ion-trace strip", "beacon strip", "battery cell window",
               "reactor vent", "arc discharge coil"),
    "hovering": ("hover skirt emitter", "thruster vent", "forward ion-trace strip",
                 "beacon strip", "battery cell window"),
    "flying": ("drive thruster nozzle", "thruster vent", "drive plume vent",
               "beacon strip", "reactor vent"),
    "lander": ("drive thruster nozzle", "drive plume vent", "thruster vent",
               "beacon strip", "battery cell window"),
    "underwater": ("forward ion-trace strip", "beacon strip", "battery cell window",
                   "propulsor ring vent"),
    # Same five bodies: plasma jets and auroral bands, never volcanic vents, lava
    # fissures or geyser vents.
    "star body":     ("plasma jet", "radiant polar jet", "auroral band",
                      "coronal discharge arc"),
    "singularity":   ("accretion streamer", "plasma jet", "radiant polar jet"),
    "binary system": ("tidal stream arc", "accretion streamer", "plasma jet"),
    "diffuse cloud": ("ionisation front", "embedded star cluster",
                      "radiant gas filament"),
    "diffuse being": ("radiant core", "pulsing energy halo", "emissive wisp"),
    "gas world":     ("storm discharge arc", "auroral band", "lightning band"),
    "disc system":   ("accretion streamer", "dust plume vent"),
}


# ``armament`` -- see the note above about the two kinds with no override. Under
# a Peaceful ``scene_filter`` this whole field simply resolves to nothing and
# the prose says nothing about weapons; it never says the thing is *unarmed*.

_ARMAMENT_DEFAULT = (
    "mounted cannon", "missile rack", "defence turret", "beam emitter",
    "kinetic launcher", "blade mount", "projectile battery",
    "energy projector",
)

ARMAMENT_POOLS: dict[str, tuple[str, ...]] = {
    POOL_DEFAULT_KEY: _ARMAMENT_DEFAULT,
    "starship": (
        "spinal railgun", "turreted beam cannon", "missile cell",
        "point-defence turret", "missile pod", "particle beam cannon",
        "mass driver", "plasma cannon", "weapon pod", "mine dispenser",
        "kinetic gatling mount", "boarding tube launcher",
    ),
    "space station": (
        "defence turret", "missile battery", "railgun emplacement",
        "beam projector", "mine field launcher", "point-defence cluster",
        "missile array", "shield pylon",
    ),
    "alien creature": (
        "serrated mandible", "venom spine", "barbed stinger", "raking talon",
        "crushing pincer", "acid spray gland", "bone club tail",
        "quilled ridge", "gripping fang", "whip lash tendril",
        "acid spore burst",
        "irritant spore burst",
        "energy discharge",
        "hooked beak", "venom barb",
        "mineral shard burst",
        "stinging filament",
    ),
    # Every head noun here is a device, not a firearm. "sidearm", "carbine",
    # "rifle", "launcher" and "bandolier" each name a present-day weapon, and a
    # model draws the present-day weapon: the reported symptom was astronauts on
    # a moon pointing what read as service pistols at each other. The pack's own
    # rule -- the qualifier has to be in the head noun, not in front of it --
    # says "energy carbine" cannot work, because the head is still a carbine.
    "spacefarer": (
        "holstered plasma caster", "shoulder-braced arc lance",
        "magnetic slug thrower", "vibro-blade",
        "shoulder-mounted missile tube", "neural stun rod",
        "plasma charge harness", "wrist-mounted arc emitter",
    ),
    "robot or mech": (
        "shoulder cannon", "arm-mounted repeater", "missile pod",
        "gauss rifle mount", "flame projector", "vibro-saw blade",
    ),
    "small drone": ("stun emitter", "micro-missile cell", "needle gun mount"),
    "humanoid unit": ("arm-mounted repeater", "shoulder cannon", "stun emitter", "wrist blade"),
    "heavy chassis": ("shoulder cannon", "missile pod", "gauss rifle mount",
                      "flame projector", "vibro-saw blade"),
    "static unit": ("arm-mounted repeater", "shoulder cannon", "stun emitter",
                    "needle gun mount", "wrist blade"),
    # "particle repeater mount" names a specific real mounting hardware with no
    # futuristic reading at all; the pool otherwise had no energy weapon.
    "surface vehicle": (
        "particle repeater mount", "roof turret", "rocket rack",
        "forward autocannon", "mine-clearing roller", "armoured ram plate",
        "hull-mounted repeater", "grenade launcher", "rail-driver turret",
        "plasma coil cannon",
    ),
    "hovering": ("particle repeater mount", "hull-mounted repeater", "grenade launcher",
                 "rocket rack"),
    "legged": ("roof turret", "rocket rack", "forward autocannon",
               "hull-mounted repeater", "grenade launcher"),
    "wreck": (
        "burst cannon muzzle", "empty missile cradle", "fused weapon blister",
        "jammed turret mount", "sheared cannon mount",
        "cracked missile cell", "warped railgun housing",
    ),
    "tentacular": ("hooked beak", "venom barb", "whip lash tendril"),
    "segmented": ("serrated mandible", "crushing pincer"),
    "vermiform": ("venom spine", "barbed stinger"),
    "winged": ("raking talon", "gripping fang"),
    "aquatic": ("venom spine", "barbed stinger"),
    "amorphous": ("acid spray gland", "venom spine"),
    "sessile growth": ("acid spore burst", "irritant spore burst"),
    "quadrupedal": ("raking talon", "quilled ridge", "bone club tail"),
    "upright hunter": ("raking talon", "gripping fang"),
    "diffuse being": ("energy discharge",),
    "void dweller": ("energy discharge", "stinging filament"),
    "radial form": ("quilled ridge", "venom spine"),
    "stone feeder": ("mineral shard burst", "quilled ridge"),
    "caste swarm": ("barbed stinger", "gripping fang"),
    "mimic body": ("venom spine", "acid spray gland"),
    "filter swarm": ("stinging filament", "venom spine"),
    "symbiotic body": ("acid spray gland", "gripping fang"),
    "brooding colony": ("irritant spore burst", "quilled ridge"),
}


# ``sensors`` -- how it perceives. ``celestial body`` is the one kind with no
# analogue at all: a planet does not look back. Its pool is ``_OMITTED`` rather
# than a fall-through, so the field resolves to nothing and the prose omits it.
# That is omission, not negation -- nothing anywhere says a world "has no eyes".

_SENSORS_DEFAULT = (
    "sensor blister", "antenna dish", "array panel", "scanner dome",
    "antenna mast",
)

SENSOR_POOLS: dict[str, tuple[str, ...]] = {
    POOL_DEFAULT_KEY: _SENSORS_DEFAULT,
    "starship": (
        "phased array panel", "antenna dish", "sensor blister",
        "forward scanner dome", "mast-mounted array", "lidar pod",
        "optical telescope tube", "sensor fin",
        "passive sensor pod", "gravimetric detector", "telescope array panel",
    ),
    "celestial body": _OMITTED,
    "space station": (
        "phased array panel", "antenna dish", "telescope tube", "sensor mast",
        "radar plate", "observation blister", "interferometer boom",
        "listening horn",
        "gravimetric detector", "deep-field array", "signal decoder dish",
    ),
    "alien creature": (
        "compound eye", "stalked eye", "sensory pit", "feathered feeler",
        "whisker filament", "tympanic membrane", "chemoreceptor frond",
        "pinhole eye", "slit pupil eye", "smooth sensory dome",
        "polarisation vane", "magnetite node", "echo dish",
        "lateral line groove", "pit membrane array",
        "heat-pit eye", "vibration-sensing pad", "chemical probe frond",
        "light-sensing patch",
        "field-sensing node",
    ),
    "spacefarer": (
        "wrist scanner", "optical implant", "optic goggle", "shoulder optic pod",
        "hand scanner", "targeting monocle", "cybernetic eye", "neural-link eyepiece",
        "sensor gauntlet",
        "range-finder optic", "bioscanner cuff", "signal locator",
    ),
    "robot or mech": (
        "optic dome", "optic stalk", "sensor crown", "antenna whisker",
        "thermal pickup plate", "acoustic pickup grille", "targeting monocle",
        "scanning bar",
        "multispectral optic", "proximity sensor fin", "audio pickup horn",
    ),
    "alien artifact": (
        "recessed optic", "scanning aperture", "receiver dish",
        "antenna vane", "watching facet", "listening slot",
        "surveying prism", "resonance detector", "glyph-reading facet",
    ),
    "surface vehicle": (
        "roof scanner dome", "antenna dish", "forward lidar blister", "lidar pod",
        "periscope tube", "roof optic turret",
        "forward radar plate",
        "gas-detection intake", "seismic probe plate",
    ),
    "wreck": (
        "shattered antenna dish", "dead sensor blister", "bent array mast",
        "cracked scanner dome", "stripped antenna stub", "fouled lidar pod",
        "snapped periscope tube",
        "crushed sensor fairing", "fouled sensor pod", "split detector fairing",
    ),
    "tentacular": ("chemoreceptor frond", "sensory pit"),
    "segmented": ("compound eye", "stalked eye"),
    "vermiform": ("sensory pit", "vibration-sensing pad", "pit membrane array"),
    "winged": ("slit pupil eye", "heat-pit eye", "echo dish"),
    "aquatic": ("lateral line groove", "chemoreceptor frond"),
    "amorphous": ("chemical probe frond", "smooth sensory dome"),
    "sessile growth": ("light-sensing patch", "chemoreceptor frond"),
    "quadrupedal": ("compound eye", "whisker filament"),
    "upright hunter": ("slit pupil eye", "compound eye"),
    "diffuse being": ("field-sensing node", "polarisation vane"),
    "void dweller": ("field-sensing node", "magnetite node"),
    "radial form": ("compound eye", "polarisation vane"),
    "stone feeder": ("vibration-sensing pad", "magnetite node"),
    "caste swarm": ("compound eye", "feathered feeler"),
    "mimic body": ("smooth sensory dome", "pinhole eye"),
    "filter swarm": ("lateral line groove", "chemical probe frond"),
    "symbiotic body": ("chemoreceptor frond", "tympanic membrane"),
    "brooding colony": ("chemoreceptor frond", "sensory pit"),
}


# ``aperture`` -- the opening. A bay or viewport on a made thing, a mouth and
# its dentition on a grown one. No count partner: one mouth is the interesting
# case and four are the interesting *creature*, which ``form`` already says.

_APERTURE_DEFAULT = (
    "access hatch", "open portal", "viewport", "intake mouth", "service port",
)

APERTURE_POOLS: dict[str, tuple[str, ...]] = {
    POOL_DEFAULT_KEY: _APERTURE_DEFAULT,
    "starship": (
        "launch bay", "armoured viewport", "cargo maw", "docking collar",
        "forward canopy", "missile hatch", "boarding ramp mouth",
        "engine intake mouth", "blast door portal", "observation cupola",
        "docking port iris", "escape pod hatch", "sensor bay door",
    ),
    "celestial body": (
        "caldera mouth", "rift canyon", "impact crater basin",
        "storm eye", "chasm",
        "equatorial rift valley", "vast impact basin",
    ),
    "space station": (
        "docking bay mouth", "airlock portal", "observation window band",
        "cargo maw", "hangar door", "service hatch", "viewport gallery",
        "launch tube mouth",
        "lander bay mouth", "maintenance airlock", "observation portal",
    ),
    "alien creature": (
        "circular toothed maw", "beaked mouth", "sieve-plated feeding slit",
        "distensible gullet", "mandibled jaw", "proboscis",
        "vertical slit mouth", "suckered mouth", "fanged jaw",
        "filter-frond mouth",
        "iris of interlocking plates", "radial feeding rosette", "sphincter vent",
        "segmented maw", "pharyngeal slit", "gullet opening",
        "energy intake vent",
        "mineral grinding maw",
    ),
    "spacefarer": (
        "helmet faceplate", "respirator grille", "open visor",
        "breathing mask vent", "hood opening", "sealed collar",
        "collar gasket", "faceplate seam", "neck seal port",
    ),
    # D15: an alien face is the point, so the aperture names the mouth or a seal.
    "alien people": (
        "tusked jaw", "beaked mouth", "tendril-fringed mouth", "wide lipless mouth",
        "mandibled mouth", "sealed collar",
    ),
    "robot or mech": (
        "vocal grille", "intake vent maw",
        "chest access panel", "optic shutter", "service port",
        "ammunition port",
        "coolant port", "tool socket", "hatch cover",
    ),
    # Round XIV: only a piloted frame has a cockpit; an android bore one in its
    # chest. ``PART_KEYWORDS["cockpit"]`` keeps it here.
    "heavy chassis": (
        "cockpit hatch", "vocal grille", "intake vent maw",
        "chest access panel", "optic shutter", "service port",
        "ammunition port",
        "coolant port", "tool socket", "hatch cover",
    ),
    "alien artifact": (
        "recessed portal", "open gate", "iris valve",
        "slotted vent mouth", "hollow core opening", "keyed socket",
        "yawning fissure",
        "keyed opening", "radial vent slot", "hollow aperture",
    ),
    # "driver hatch" (a person named "driver" is an automotive role), "intake
    # grille" (a car radiator grille) and "rear cargo door" (a delivery-van
    # part) read as present-day; renamed without changing what they mean.
    "surface vehicle": (
        "cabin canopy", "rear ramp", "pilot hatch", "cargo maw",
        "intake vane", "gun port", "glazed viewport band", "side hull hatch",
        "roof hatch", "engine intake port", "aft cargo hatch",
    ),
    "wreck": (
        "torn hull breach", "gaping bay door", "shattered viewport",
        "split seam gap", "blown airlock", "peeled hull rent",
        "exposed engine throat",
        "torn hull mouth", "opened cargo bay", "cracked access port",
    ),
    # A gas giant has no lava tube and no crater; the solid groups fall through
    # to the kind pool, declared in scope_fallthrough.
    "gas world": ("storm eye", "chasm"),
    "tentacular": ("beaked mouth", "suckered mouth"),
    "segmented": ("mandibled jaw", "segmented maw"),
    "vermiform": ("circular toothed maw", "pharyngeal slit"),
    "winged": ("beaked mouth", "fanged jaw"),
    "aquatic": ("filter-frond mouth", "gullet opening"),
    "amorphous": ("distensible gullet", "sphincter vent"),
    "sessile growth": ("filter-frond mouth", "sieve-plated feeding slit"),
    "quadrupedal": ("fanged jaw", "vertical slit mouth"),
    "upright hunter": ("fanged jaw", "mandibled jaw"),
    "diffuse being": ("energy intake vent",),
    "void dweller": ("energy intake vent", "sphincter vent"),
    "radial form": ("radial feeding rosette", "circular toothed maw",
                    "iris of interlocking plates"),
    "stone feeder": ("mineral grinding maw", "sieve-plated feeding slit"),
    "caste swarm": ("mandibled jaw", "proboscis"),
    "mimic body": ("suckered mouth", "distensible gullet"),
    "filter swarm": ("filter-frond mouth", "sieve-plated feeding slit"),
    "symbiotic body": ("proboscis", "suckered mouth"),
    "brooding colony": ("sieve-plated feeding slit", "sphincter vent"),
}


# ``extras`` -- one more distinguishing component, the thing a viewer notices
# second. No count partner and no tag: an extra is never a weapon.

_EXTRAS_DEFAULT = (
    "cargo pod", "antenna mast", "access ladder", "mounting cradle",
    "magnetic grapple clamp",
)
# Round XV: the native pools below lost every boxed-cargo, clamp, mast and arm
# extra. A model hung a cargo pod or a cradle off the hull on cables, and bolted
# a mast or a grapple well clear of the body. ``_default`` keeps its words: it
# is only the stranger's vocabulary (validator check 32).

EXTRAS_POOLS: dict[str, tuple[str, ...]] = {
    POOL_DEFAULT_KEY: _EXTRAS_DEFAULT,
    "starship": (
        "escape pod cluster", "ablative shield plate", "fuel scoop", "recessed hangar bay",
        "armoured bridge dome", "hull-flush sensor blister", "point-defence blister",
        "ventral drone launch bay", "reinforced ram prow", "dorsal comms spine",
    ),
    "celestial body": (
        "shepherd arc", "moonlet", "storm oval", "ice cap", "dust halo",
        "orbital debris belt", "tidal bulge", "canyon network",
        "shepherd moon", "crater row", "polar vortex",
    ),
    # Round XII (D12): a world-scale feature, keyed by the body it belongs to.
    "gas world": ("storm oval", "polar vortex", "dust halo", "shepherd moon",
                  "moonlet", "orbital debris belt"),
    "small body": ("moonlet", "crater row", "dust halo"),
    "solid world": ("ice cap", "canyon network", "crater row", "polar vortex",
                    "moonlet", "shepherd moon", "orbital debris belt", "dust halo",
                    "tidal bulge"),
    "space station": (
        "escape pod cluster", "antenna array cluster",
        "drone cradle", "greenhouse blister", "observation pod", "docking collar",
        "shielded reactor sphere", "hydroponics dome",
    ),
    "alien creature": (
        "dorsal crest", "tail", "luminous brood cyst", "mane of filaments",
        "symbiont growth", "spore vent", "barbed hide ridge", "gill ruff",
        "brood pouch", "dewlap", "root-like foot mass",
        "twin crest", "lure stalk", "scent gland",
    ),
    "void dweller": ("trailing light filament", "drifting spore sac", "gliding membrane"),
    "spacefarer": (
        "tool harness", "oxygen tank", "magnetic anchor piton", "holstered scanner",
        "sealed sample case", "insulated thermal shroud", "data slate", "rebreather pack",
        "magnetic grapple", "power cell belt",
        "ration pack", "climbing harness", "signal beacon", "neural interface jack",
    ),
    "robot or mech": (
        "tool rack", "cooling fin bank",
        "antenna whip", "spare limb mount", "drone bay",
        "welding rig", "armoured shoulder cowl", "back-mounted power cell",
    ),
    "alien artifact": (
        "floating attendant sphere", "mounting cradle",
        "containment field shell", "embedded crystal", "floating mooring pylon",
        "dust shroud", "worn pedestal", "orbiting fragment",
        "hovering plinth", "engraved band", "orbiting shell",
    ),
    "surface vehicle": (
        "roof sensor dome", "cargo pallet mount", "dust filter intake", "fuel cell pack",
        "armoured crew cab", "sample collection hatch", "external air scrubber",
        "rooftop antenna fin", "sonar dome", "drill rig",
    ),
    "wheeled/tracked": ("roof sensor dome", "cargo pallet mount", "fuel cell pack",
                        "dust filter intake", "armoured crew cab", "drill rig",
                        "sample collection hatch", "external air scrubber"),
    "hovering": ("roof sensor dome", "cargo pallet mount", "fuel cell pack",
                 "rooftop antenna fin", "armoured crew cab"),
    "flying": ("roof sensor dome", "fuel cell pack", "rooftop antenna fin",
               "dust filter intake", "armoured crew cab"),
    "lander": ("fuel cell pack", "roof sensor dome", "cargo pallet mount",
               "sample collection hatch", "external air scrubber"),
    "underwater": ("sample collection hatch", "fuel cell pack", "sonar dome",
                   "external air scrubber"),
    "legged": ("drill rig", "cargo pallet mount", "roof sensor dome", "fuel cell pack",
               "sample collection hatch"),
    "wreck": (
        "spilled cargo scatter", "torn bulkhead section", "half-buried engine bell",
        "collapsed antenna mast", "salvage cutting scar",
        "opened escape pod bay", "drifting debris cloud",
        "buckled hull plating",
        "scattered debris trail", "torn cargo bay door", "bent frame section",
    ),
}

# ---------------------------------------------------------------------------
# Todo 9 -- condition, scale, surface detail and the shared count vocabulary
# ---------------------------------------------------------------------------

# ``condition`` and ``scale`` are the two fields with no per-kind override at
# all. A derelict is derelict whether it is a ship, a station or a mech, and a
# thing is large in exactly one sense; nine copies of one list would only be
# nine chances to drift.

CONDITION_POOL: tuple[str, ...] = (
    "pristine", "battle-scarred", "overgrown", "unfinished", "corroded",
    "half-built", "weathered", "freshly commissioned", "hastily repaired",
    "mothballed", "scorched", "ice-encrusted", "dust-caked", "immaculate",
    "well-worn", "rebuilt", "sun-bleached", "soot-blackened", "vacuum-pitted",
    "field-repaired", "newly repainted", "radiation-stained", "half-disassembled",
    "dust-streaked", "frost-rimed", "sunburnt",
)

#: A made thing is never drawn mid-construction or freshly out of a yard.
_CONDITION_MADE: tuple[str, ...] = (
    "pristine", "battle-scarred", "overgrown", "corroded",
    "weathered", "freshly commissioned", "hastily repaired",
    "scorched", "ice-encrusted", "dust-caked", "immaculate",
    "well-worn", "rebuilt", "sun-bleached", "soot-blackened", "vacuum-pitted",
    "field-repaired", "newly repainted", "radiation-stained",
    "heavily modified", "tarnished",
    # Round XIV: "abandoned", "derelict", "breached" and "crashed" left this
    # pool. Round XII had added them so a noun that states no condition could
    # still be dead, and the 0916 batch showed what that bought: a crashed colony
    # ship riding a re-entry sheath in orbit, an abandoned troop carrier holding
    # station, a derelict walker crouching to inspect wreckage. A dead ship is
    # the ``wreck`` kind, whose every situation is dormant by construction.
    "dust-streaked", "frost-rimed",
)

#: Ordered smallest to largest. ``tiny`` is load-bearing: Todo 12's rule that a
#: celestial body is never tiny needs a real option to exclude.
SCALE_POOL: tuple[str, ...] = (
    "tiny", "small", "large", "massive", "colossal", "planetary",
)


#: ``condition`` is kind-scoped: what is a plausible state of being differs
#: by what the thing is. A wreck is derelict or breached; a living thing is
#: weathered or scorched but never mothballed or decommissioned; a celestial
#: body is never under construction. ``_default`` serves craft, structure,
#: machine and vehicle. The wreck states (crashed, derelict, abandoned,
#: breached) live only on the ``wreck`` kind -- a crashed strike carrier is a
#: wreck pretending to be a ship.
CONDITION_POOLS: dict[str, tuple[str, ...]] = {
    POOL_DEFAULT_KEY: _CONDITION_MADE,
    # Declared rather than fallen through to: ``_default`` is also what a
    # foreign-genre entity is spoken with (validator check 32).
    "starship": _CONDITION_MADE,
    "robot or mech": _CONDITION_MADE,
    "surface vehicle": _CONDITION_MADE,
    "space station": _CONDITION_MADE + ("unfinished", "half-built", "mothballed"),
    "wreck": (
        "corroded",
        "weathered", "scorched", "ice-encrusted", "dust-caked", "overgrown",
        "battle-scarred", "sun-bleached", "soot-blackened", "vacuum-pitted",
        "field-repaired", "radiation-stained", "half-disassembled", "crushed",
    ),
    "celestial body": (
        "pristine", "weathered", "scorched", "ice-encrusted",
        "dust-caked", "sun-bleached",
        "vacuum-pitted", "radiation-stained", "cratered", "tectonic-scarred",
        "cloud-banded", "eroded",
    ),
    "alien artifact": (
        "pristine", "immaculate", "weathered", "corroded", "overgrown",
        "dust-caked", "ice-encrusted", "scorched", "battle-scarred",
        "sun-bleached", "soot-blackened", "vacuum-pitted", "radiation-stained",
        "half-disassembled", "inscribed", "fractured",
    ),
    "spacefarer": (
        "battle-weary", "grime-streaked", "freshly outfitted", "travel-worn",
        "exhausted", "soot-smudged", "veteran", "frost-rimed", "dust-streaked",
        "sunburnt", "scarred", "alert", "cybernetically augmented",
    ),
    "alien creature": (
        "battle-scarred", "weathered", "scorched", "sleek", "glossy", "gaunt",
        "heavily scarred", "ancient", "juvenile", "dust-caked", "frost-rimed",
        "overgrown", "sun-bleached", "moulting", "cybernetically grafted",
    ),
}


#: ``scale`` is kind-scoped for the same reason: a celestial body is never tiny
#: (the smallest is still an asteroid), a person is never colossal, and a tiny
#: starship is a toy. ``tiny`` is removed from every made thing larger than a
#: person.
SCALE_POOLS: dict[str, tuple[str, ...]] = {
    POOL_DEFAULT_KEY:  ("tiny", "small", "large", "massive"),
    "celestial body":  ("small", "large", "massive", "colossal", "planetary"),
    "space station":   ("small", "large", "massive", "colossal"),
    "starship":        ("small", "large", "massive", "colossal"),
    "wreck":           ("small", "large", "massive", "colossal"),
    "alien creature":  ("tiny", "small", "large", "massive", "colossal"),
    "alien artifact":  ("tiny", "small", "large", "massive"),
    "robot or mech":   ("tiny", "small", "large", "massive"),
    "surface vehicle": ("small", "large", "massive"),
    "spacefarer":      ("small", "large", "massive"),
}


# ``surface_detail`` is what you see at arm's length once ``material`` has said
# what the thing is made of: wear, seams, texture. Kind-scoped, because pitting
# on a hull and moulting on a hide are different observations.

_SURFACE_DETAIL_DEFAULT = (
    "pitted and scarred", "hairline seam tracery", "flaking plate",
    "panel-line grid", "welded repair seam", "dust-caked film",
)

SURFACE_DETAIL_POOLS: dict[str, tuple[str, ...]] = {
    POOL_DEFAULT_KEY: _SURFACE_DETAIL_DEFAULT,
    "starship": (
        "pitted and scarred", "radiant hairline seams", "flaking ablative plate",
        "panel-line grid", "micrometeorite cratering", "welded repair plating",
        "heat-bloom staining", "riveted plate overlap", "exposed frame ribs",
        "sun-bleached plating", "layered greeble clutter",
        "polished mirror finish",
        "scored ablation streaks", "cracked ceramic seams", "fouled sensor lattice",
    ),
    "celestial body": (
        "crater pocking", "continent-wide dune seas", "fracture crazing",
        "banded strata layering", "glassy impact melt sheets",
        "sulphur crust flaking", "ice fissure networks",
        "dark basalt plains",
        "wind-scoured ridges", "layered ash bands", "fractured ice sheets",
    ),
    "space station": (
        "panel-line grid", "welded repair plating", "radiator fin ribbing",
        "micrometeorite cratering", "exposed frame ribs", "dust-caked film",
        "greeble clutter", "rust bleed streaking", "sun-bleached plating",
        "modular seam banding",
        "scuffed dock plating", "scored radiator fins", "stained panel joints",
    ),
    "alien creature": (
        "iridescent scaling", "fine bristled fuzz", "waxy sheen",
        "pebbled hide texture", "translucent veining", "moulting flake patches",
        "ridged chitin plating", "damp mucous film", "cracked mineral crust",
        "downy filament pelt", "barbed micro-spines", "honeycomb pore texture",
        "tessellated plating", "prismatic banding", "fractal branching veins",
        "oil-slick iridescence",
        "chitinous ridging", "mottled scale banding", "damp pore texture",
    ),
    "spacefarer": (
        "scuffed suit fabric",
        "dust-ingrained creasing", "worn glove leather",
        "scratched visor coating", "quilted padding ribbing",
        "frayed harness straps", "oil-stained cuffs",
        "scuffed knee panels", "cracked seal seams", "visible cybernetic implants",
    ),
    "robot or mech": (
        "brushed alloy grain", "chipped paint edges", "exposed hydraulic lines",
        "oil-weeping joints", "panel-line grid", "dented armour plating",
        "raised panel ribbing", "scuffed contact surfaces",
        "scored armour edges", "grease-streaked joints", "dented panel corners",
    ),
    "alien artifact": (
        "mirror-smooth finish", "carved concentric grooves", "pitted erosion",
        "crystalline inclusions", "verdigris patina", "fine fractal etching",
        "worn-soft edges", "hairline fracture crazing",
        "weathered relief banding", "chipped inlay edges", "fractal vein tracery",
    ),
    "surface vehicle": (
        "mud-caked underbody", "chipped paint edges", "dented panel work",
        "scratched canopy", "grit-worn surfaces", "welded repair plating",
        "dust film", "exposed frame tubing",
        "scored underbody plating", "mud-packed undercarriage seams", "chipped edge trim",
    ),
    "wreck": (
        "flaking ablative plate", "corrosion blooming",
        "overgrown with alien flora", "torn plate curling", "soot scoring",
        "salt crust encrustation", "fungal mat growth", "sand-scoured polish",
        "ice fracture crazing", "stripped frame exposure",
        "corroded seam lines", "flaking paint layers", "fractured panel edges",
    ),
    # A gas giant has no crater pocking; the solid groups fall through to the
    # kind pool, declared in scope_fallthrough.
    "gas world": ("banded strata layering",),
}


# ``COUNT_POOL`` is the one vocabulary all four count fields share -- appendages,
# emitters, armament and sensors. It is the only pool whose values carry a
# leading article, and deliberately so: these are not noun phrases, they are the
# engine's **composition** vocabulary, the left-hand half of "a pair of ion
# thrusters". Every validator that rejects a leading article must exempt the
# count fields, which it can detect from ``FieldSpec.renders_with``.
#
# Word tokens, never digits: "6 engines" is a caption, "six engines" is a
# description, and only one of those gets drawn.
#
# Uniform weights on purpose. Engine count and eye count are two of the five
# things the F5 gate wants visibly different across twenty seeds, so a
# distribution that favours "a pair of" is working against the point of the pack.

COUNT_POOL: tuple[str, ...] = (
    "a single",
    "a pair of",
    "three",
    "four",
    "six",
    "eight",
    "a dozen",
    "rows of",
    "banks of",
    "a ring of",
    "a cluster of",
    "a fan of",
    "a constellation of",
)

# ``COUNT_POOL`` above is the full vocabulary. It is not what any single field
# draws from, and treating it as one flat pool for all four count fields was a
# real defect rather than a simplification. The reported symptoms:
#
#   "banks of targeting monocles"    -- a person, wearing banks of anything
#   "a dozen spinal railguns"        -- spinal means there is one spine
#   "a fan of energy carbines"       -- a person holding a fan of rifles
#   "a dozen ..., a dozen ..., a constellation of ..."  -- all in one entity
#
# Two things were wrong. The **collective** quantifiers ("banks of", "rows of",
# "a constellation of") describe an industrial array and are false of anything
# person-sized, whatever is being counted. And **weapons** are counted small in
# every register: a warship has four spinal railguns or it has a battery, never
# a dozen of an item whose name says there is one.
#
# So the vocabulary is split by what is being counted *and* by what is carrying
# it. Nothing is added to the pools; the values are the same words, allotted.
# The last symptom -- the same quantifier twice in one entity -- is
# ``distinct_within_entity`` below, not a pool question.

#: Plain numerals. True of anything, at any scale.
_COUNT_FEW: tuple[str, ...] = ("a single", "a pair of", "three", "four", "six")

#: The numerals plus the shapes a *body* makes: a ring of eyes, a cluster of
#: spines, a fan of fronds. No "banks of" or "rows of" -- those are racking.
_COUNT_ORGANIC: tuple[str, ...] = _COUNT_FEW + (
    "eight", "a cluster of", "a fan of",
)

#: The organic count vocabulary plus a ring, which is a real and good image on
#: an emitter ("a ring of ion thrusters") and a tic on an eye or a limb.
_COUNT_EMITTER_ORGANIC: tuple[str, ...] = _COUNT_ORGANIC + ("a ring of",)

#: Everything, including the industrial arrays. For hulls, stations and worlds:
#: things big enough that a constellation of anything is plausible.
_COUNT_ARRAY: tuple[str, ...] = COUNT_POOL

#: ``_COUNT_ARRAY`` without the ring. A ring of thrusters is a real image; a
#: ring of limbs or eyes is the tic the ring motif measures.
_COUNT_ARRAY_NO_RING: tuple[str, ...] = (
    "a single", "a pair of", "three", "four", "six", "eight",
    "a dozen", "rows of", "banks of", "a cluster of", "a fan of",
    "a constellation of",
)

#: What a weapons fit is counted in, for every kind. A battery is expressed by
#: naming the battery, never by putting a dozen in front of a spinal mount.
_COUNT_WEAPONS: tuple[str, ...] = ("a single", "a pair of", "three", "four", "six", "eight")

#: Which vocabulary each kind counts in. A **dict literal, not a comprehension
#: or a helper call**: ``scripts/builtin_options.py`` reads these pools by
#: parsing this file rather than importing it -- which is what keeps a
#: maintainer's private local additions out of any committed document -- and
#: its evaluator understands literals and earlier names and deliberately
#: nothing else. A tidier helper here is unreadable there, and that script's
#: own error message says to widen the evaluator only as a last resort.
_COUNT_BY_KIND: dict[str, tuple[str, ...]] = {
    POOL_DEFAULT_KEY: _COUNT_FEW,
    "starship": _COUNT_ARRAY,
    "space station": _COUNT_ARRAY,
    "celestial body": _COUNT_ORGANIC,
    "wreck": _COUNT_ARRAY,
    "alien creature": _COUNT_ORGANIC,
    "spacefarer": _COUNT_FEW,
    "robot or mech": _COUNT_FEW,
    "alien artifact": _COUNT_FEW,
    "surface vehicle": _COUNT_FEW,
}

#: How a *count* is spoken depends on what is being counted. A matched pair of
#: boots is never "eight"; a worn fitting is never "six". The kind keys below
#: survive as the **stranger path** only: every noun this pack authors carries a
#: cardinality class, so its own group always wins the scope chain, and a kind
#: key is reached only by a foreign-genre noun this pack has never heard of.
_COUNT_PAIR = ("a single", "a pair of")
_COUNT_WORN = ("a single", "a pair of")

#: What each cardinality class may draw. Spread into all four count pools below,
#: and named by ``value_cardinality`` on the noun side, so the class exists in
#: both tables or in neither. Declared here rather than derived at construction
#: because ``scripts/builtin_options.py`` reads these pools by *parsing* this
#: file: a key that only appears once the pack is built is a key it cannot see,
#: and the reader has to agree with the pack field for field.
#:
#: Each class is a statement about the world, not a size band:
#:
#:   a lone part      -- there is one. A prow, a tail, an ion tail, a halo.
#:   a matched pair   -- bilateral. Wings, hands, boots, flippers, sponsons.
#:   a worn fitting   -- carried on a suit; a person wears one or two of anything.
#:   a drive unit     -- propulsion, and therefore directional: above four, the
#:                       thrust ends up on more than one face of the hull.
#:   a small set      -- a handful, bolted on where there is room.
#:   a limb set       -- limbs, which is where a high count is the point.
#:   a body row       -- repeated down a body: photophores, spines, eye-spots.
#:   an array fitting -- panelling, seams, strips, windows. Genuinely many.
#:   a ringed array   -- an array fitting that also reads well as a ring.
#:   a satellite      -- in orbit around the subject. Past two it stops reading
#:                       as orbit and starts reading as decoration stuck on.
CARDINALITY_COUNTS: dict[str, tuple[str, ...]] = {
    "a lone part": ("a single",),
    "a matched pair": _COUNT_PAIR,
    "a worn fitting": _COUNT_WORN,
    "a drive unit": ("a single", "a pair of", "three", "four"),
    "a small set": ("a single", "a pair of", "three", "four", "six"),
    "a limb set": ("a single", "a pair of", "three", "four", "six", "eight"),
    "a body row": ("a single", "a pair of", "three", "four", "six", "eight",
                   "a cluster of", "a fan of"),
    "an array fitting": ("a single", "a pair of", "three", "four", "six", "eight",
                         "a dozen", "rows of", "banks of", "a cluster of", "a fan of",
                         "a constellation of"),
    "a ringed array": ("a single", "a pair of", "three", "four", "six", "eight",
                       "a dozen", "rows of", "banks of", "a ring of", "a cluster of",
                       "a fan of", "a constellation of"),
    "a satellite": ("a single", "a pair of"),
    "a long arm": ("a single",),
    "a hand weapon": ("a single",),
    "a spinal mount": ("a single",),
}

APPENDAGE_COUNT_POOLS: dict[str, tuple[str, ...]] = {
    **_COUNT_BY_KIND,
    **CARDINALITY_COUNTS,
    "starship": _COUNT_ARRAY_NO_RING,
    "space station": _COUNT_ARRAY_NO_RING,
    "celestial body": _COUNT_ORGANIC,
    "wreck": _COUNT_ARRAY_NO_RING,
}
SENSOR_COUNT_POOLS: dict[str, tuple[str, ...]] = {
    **_COUNT_BY_KIND,
    **CARDINALITY_COUNTS,
    # A figure has two hands: armament and sensors each cap at one, so the
    # pair together can never put more than two objects in them.
    "spacefarer": ("a single",),
    "starship": _COUNT_ARRAY_NO_RING,
    "space station": _COUNT_ARRAY_NO_RING,
    "celestial body": _COUNT_ORGANIC,
    "wreck": _COUNT_ARRAY_NO_RING,
}
EMITTER_COUNT_POOLS: dict[str, tuple[str, ...]] = {
    **_COUNT_BY_KIND,
    **CARDINALITY_COUNTS,
    "alien creature": _COUNT_EMITTER_ORGANIC,
    "wreck": ("a single", "a pair of", "three"),
}
#: Weapons are counted small everywhere, so one pool serves every kind; the
#: kind keys stop a mech carrying eight of anything.
ARMAMENT_COUNT_POOLS: dict[str, tuple[str, ...]] = {
    POOL_DEFAULT_KEY: _COUNT_WEAPONS,
    **CARDINALITY_COUNTS,
    "robot or mech": ("a single", "a pair of"),
    "surface vehicle": ("a single", "a pair of"),
    "alien creature": ("a single", "a pair of", "three", "four"),
    "spacefarer": ("a single",),
}


# ---------------------------------------------------------------------------
# Cardinality -- how many of a thing there can be, decided by the thing
# ---------------------------------------------------------------------------
#
# A count field's scope chain asks its noun before it asks the kind, so the
# machinery to let a noun answer this has always been here. What was missing was
# the answer: with the nouns unclassified the question fell through to the kind,
# and a kind cannot answer it. "drive nacelle" and "luminous hull seam" are both
# ``emitters`` on a ``starship``, so both could draw "a dozen" -- and a model
# draws a dozen nacelles as engine bells at *both ends* of the hull, which is the
# "it would fly backwards" report. "six shepherd moonlets" is drawn as six balls
# stuck to the planet; "six halo crowns" as a shrub of rings.
#
# Every class is a real statement about the world, not a size band:
#
#   a lone part      -- there is one. A prow, a tail, an ion tail, a halo.
#   a matched pair   -- bilateral. Wings, hands, boots, flippers, sponsons.
#   a worn fitting   -- carried on a suit; a person wears one or two of anything.
#   a drive unit     -- propulsion. Directional, so a count above four puts
#                       thrust on more than one face of the hull.
#   a small set      -- a handful, bolted on where there is room.
#   a limb set       -- limbs, which is where a high count is the *point*.
#   a body row       -- repeated down a body: photophores, spines, eye-spots.
#   an array fitting -- panelling, seams, strips, windows. Genuinely many.
#   a ringed array   -- an array fitting that also reads well as a ring.
#   a satellite      -- something in orbit around the subject. At most two read
#                       as moons; more read as decoration stuck to the surface.
#
# ``a long arm``/``a hand weapon``/``a spinal mount`` are the weapon classes: a
# figure has two hands and a spine is singular by definition.


def _cardinality(*groups: tuple[str, tuple[str, ...]]) -> dict[str, str]:
    """Invert ``(class, values)`` pairs into the ``{value: class}`` map.

    Authored by class because that is how the judgement is actually made -- you
    decide "these are all bilateral" once -- and stored by value because that is
    what the expansion and the validator both need to look up.
    """
    out: dict[str, str] = {}
    for class_name, values in groups:
        for value in values:
            if value in out:
                raise ValueError(
                    f"{value!r} is in two cardinality classes "
                    f"({out[value]!r} and {class_name!r}); a value has one"
                )
            out[value] = class_name
    return out


_CARDINALITY_APPENDAGES = _cardinality(
    ("a lone part", (
        "stepped command tower", "ventral armour blade", "armoured sensor prow",
        "angled deflector plate", "rear engine cowling", "docking collar ring",
        "accretion arc", "anchoring base flange", "dorsal armour ridge",
        "drifting debris cluster", "dust lane", "dust tail", "equatorial band",
        "filter stalk", "folding ramp", "grapple line spool", "ion tail",
        "ionisation front", "prehensile tongue", "regolith scraper plate",
        "rooted frond cluster", "solar wind tail", "spined tail club",
        "storm band filament", "sweeping arc", "tidal ridge", "tidal stream",
        "tidal tail", "torn engine mount", "torn hull flap", "whip tail",
    )),
    ("a matched pair", (
        "stern stabiliser blade", "ballast tank blister",
        "accretion spiral arm", "canard fin", "spin counterweight module", "heavy drill arm",
        "feathered wing", "folding fin membrane", "gauntleted hand", "grasping pincer",
        "hinged fin panel", "hinged panel wing", "rock-cutting claw arm",
        "magnetic boot", "membranous wing", "muscular flipper", "nacelle pylon", "paddle fin",
        "plasma welding head", "sample drill arm", "sampling probe arm", "shield mount arm",
        "spiral fluke",
        "repulsor stabiliser vane",
        "sponson pod", "stabiliser fin", "stabiliser outrigger", "swept fin",
        "telescoping manipulator", "tool harness arm", "tool turret arm",
        "ventral stabiliser fin", "welding torch arm",
    )),
    ("a worn fitting", (
        "cybernetic arm",
        "articulated exo-limb", "backpack thruster pod", "magnetic safety clamp",
        "marker pouch", "prosthetic arm", "shoulder optic boom",
        "utility manipulator arm",
    )),
    ("a small set", (
        "hull-flush turret blister", "angled heat-sink fin", "pressurised observation blister",
        "antenna mast", "boom arm",
        "cryovolcanic plume", "debris streamer", "docking boom", "drydock cradle arm",
        "fin", "folding tool arm", "folding vane", "gantry arm", "ice plume", "mooring boom",
        "pressurised connector tube",
        "prominence loop", "rock spire", "roof sensor pod",
        "service gantry arm", "sheared fin",
    )),
    ("a limb set", (
        "articulated arm", "articulated manipulator arm", "barbed tentacle",
        "chitinous scythe arm", "swivelling sensory stalk", "gripping foot pad",
        "hooked claw arm", "hydraulic limb", "jointed crawler leg", "jointed limb",
        "prehensile tentacle", "spindly leg", "sucker-lined arm",
    )),
    ("a body row", (
        "ciliated ribbon", "coronal streamer", "drifting filament", "dust spoke",
        "ejecta ray", "energy wisp", "filamentary tendril", "flare ribbon",
        "folded petal plate", "jutting crystal fin", "radial fin", "rotating spoke",
        "spore vent frond", "trailing plasma tendril",
    )),
    ("an array fitting", (
        "bent frame spar", "collapsed hull girder", "peeled hull-skin strip",
        "docking spar", "exposed hull frame", "projecting spar", "projecting vane",
        "snapped spar", "spar",
        "strut", "peeled-back armour plate", "twisted hull girder",
    )),
    ("a satellite", (
        "clumped ringlet", "hovering fragment",
        "orbiting shell segment", "suspended orbiting shell",
    )),
)

_CARDINALITY_EMITTERS = _cardinality(
    ("a lone part", (
        "embedded star cluster", "halo ring", "ionisation front", "pulsing aura",
        "pulsing energy halo", "radiant core", "radiant core aperture",
    )),
    ("a matched pair", (
        "auroral band", "auroral curtain", "forward ion-trace strip", "lightning band",
        "plasma jet", "radiant polar jet", "aft ion-trace strip",
    )),
    ("a worn fitting", (
        "backpack thruster vent", "collar light strip", "chest indicator panel",
        "glove beacon", "helmet beacon", "helmet visor strip", "shoulder beacon",
        "suit seam piping", "suit status strip", "tool torch emitter",
        "wrist console panel",
    )),
    ("a drive unit", (
        "drive nacelle", "drive plume nozzle", "drive plume vent",
        "drive thruster nozzle", "exhaust nozzle", "fusion torch nozzle",
        "propulsor ring vent", "reactor exhaust port", "thruster nozzle",
        "thruster vent", "warp coil bank",
    )),
    ("a small set", (
        "accretion streamer", "arc welding emitter", "arc welding port",
        "beacon strobe", "coronal discharge arc",
        "cryovolcanic plume vent", "discharge spire",
        "dust plume vent", "geyser vent",
        "optic emitter", "plasma vent", "power core window",
        "reactor core window",
        "reactor vent",
        "signal mast beacon", "docking guide light", "antenna tip beacon",
        "hangar mouth light bar",
        "storm discharge arc", "sublimating ice fissure", "tidal stream arc",
        "volcanic vent", "dust plume", "outgassing plume", "sunward tail streamer",
    )),
    ("a body row", (
        "bioluminescent organ", "ember-hot fissure",
        "emissive fracture line", "emissive glyph band", "emissive wisp",
        "heat-pit organ", "incandescent eye-spot", "lava fissure",
        "luminous flank slit", "luminous inlay vein", "luminous sac",
        "luminous stripe", "luminous ventral patch", "phosphorescent tendril",
        "photophore", "pulsing node", "radiant frill", "radiant gas filament",
        "resonance filament", "spiracle vent", "vent pore",
    )),
    ("an array fitting", (
        "arc discharge coil",
        "battery cell window", "beacon strip", "cooling vent slot", "discharge coil",
        "docking beacon", "heat radiator panel",
        "heat sink grille", "joint seam beacon", "joint seam strip",
        "luminous hull seam", "luminous window band", "navigation light",
        "observation deck window strip", "running light string",
        "radiator panel", "radiator seam",
        "running beacon", "seam beacon", "seam strip",
        "status indicator band", "vent port",
    )),
    ("a ringed array", (
        "hover skirt emitter", "ion thruster", "manoeuvring thruster",
        "manoeuvring vent",
    )),
)

_CARDINALITY_ARMAMENT = _cardinality(
    ("a lone part", (
        "armoured ram plate", "barbed stinger", "bone club tail", "hooked beak",
        "mine-clearing roller", "roof turret", "venom barb", "warped railgun housing",
    )),
    ("a matched pair", (
        "acid spray gland", "arm-mounted repeater", "blade mount", "crushing pincer",
        "flame projector", "forward autocannon", "gauss rifle mount",
        "grenade launcher", "hull-mounted repeater", "micro-missile cell",
        "mine dispenser", "missile pod",
        "missile rack", "mounted cannon", "needle gun mount", "particle beam cannon",
        "particle repeater mount", "plasma cannon", "plasma coil cannon",
        "rail-driver turret", "raking talon", "rocket rack",
        "serrated mandible", "shoulder cannon", "stun emitter", "vibro-saw blade",
        "weapon pod", "whip lash tendril", "wrist blade",
    )),
    ("a small set", (
        "fused weapon blister",
        "acid spore burst", "beam emitter", "beam projector", "boarding tube launcher",
        "burst cannon muzzle", "cracked missile cell", "defence turret",
        "empty missile cradle", "energy discharge", "energy projector",
        "irritant spore burst", "jammed turret mount", "kinetic gatling mount",
        "kinetic launcher",
        "mine field launcher", "mineral shard burst", "missile array",
        "missile battery", "missile cell", "point-defence cluster",
        "point-defence turret", "projectile battery", "railgun emplacement",
        "sheared cannon mount", "shield pylon",
        "turreted beam cannon",
    )),
    ("a body row", (
        "gripping fang", "quilled ridge", "stinging filament", "venom spine",
    )),
    ("a long arm", (
        "shoulder-braced arc lance", "plasma charge harness",
        "magnetic slug thrower", "shoulder-mounted missile tube",
    )),
    ("a hand weapon", (
        "holstered plasma caster", "neural stun rod", "vibro-blade",
        "wrist-mounted arc emitter",
    )),
    ("a spinal mount", ("mass driver", "spinal railgun")),
)

_CARDINALITY_SENSORS = _cardinality(
    ("a lone part", (
        "forward lidar blister", "roof optic turret",
        "bent array mast", "split detector fairing", "cracked scanner dome",
        "crushed sensor fairing", "forward radar plate", "forward scanner dome",
        "fouled lidar pod", "fouled sensor pod", "optic dome",
        "optical telescope tube", "periscope tube", "roof scanner dome",
        "scanner dome", "sensor crown", "sensor mast", "shattered antenna dish",
        "smooth sensory dome", "snapped periscope tube", "telescope tube",
    )),
    ("a matched pair", (
        "antenna whisker", "audio pickup horn", "compound eye", "cybernetic eye",
        "echo dish", "feathered feeler", "gas-detection intake", "heat-pit eye",
        "interferometer boom", "lateral line groove", "lidar pod", "listening horn",
        "multispectral optic", "optic stalk", "optical implant", "sensor fin",
        "slit pupil eye", "tympanic membrane",
    )),
    ("a worn fitting", (
        "neural-link eyepiece",
        "bioscanner cuff", "hand scanner", "optic goggle", "range-finder optic",
        "sensor gauntlet", "shoulder optic pod", "signal locator", "targeting monocle",
        "wrist scanner",
    )),
    ("a small set", (
        "acoustic pickup grille", "antenna dish", "antenna mast", "antenna vane",
        "dead sensor blister", "deep-field array", "gravimetric detector", "mast-mounted array",
        "observation blister",
        "passive sensor pod", "proximity sensor fin", "radar plate", "receiver dish",
        "resonance detector", "scanning bar", "seismic probe plate", "sensor blister",
        "signal decoder dish", "stripped antenna stub", "telescope array panel",
        "thermal pickup plate",
    )),
    ("a body row", (
        "chemical probe frond", "chemoreceptor frond", "field-sensing node",
        "glyph-reading facet", "light-sensing patch", "listening slot",
        "magnetite node", "pinhole eye", "pit membrane array", "polarisation vane",
        "recessed optic", "scanning aperture", "sensory pit", "stalked eye",
        "surveying prism", "vibration-sensing pad", "watching facet",
        "whisker filament",
    )),
    ("an array fitting", ("array panel", "phased array panel")),
)

CARDINALITY: dict[str, dict[str, str]] = {
    "appendages": _CARDINALITY_APPENDAGES,
    "emitters": _CARDINALITY_EMITTERS,
    "armament": _CARDINALITY_ARMAMENT,
    "sensors": _CARDINALITY_SENSORS,
}


#: Every control field's groups. The four count-noun fields are absent on
#: purpose: their groups ARE their cardinality classes, and ``GenrePack``
#: expands ``value_cardinality`` into them. Declaring a count noun's group here
#: as well would put a value in two groups, which the scope validator rejects --
#: which is the point, because two tables of the same fact drift.
POOL_GROUPS: dict[str, dict[str, tuple[str, ...]]] = {
    "subkind": SUBKIND_GROUPS,
    "environment": ENVIRONMENT_BANDS,
}


# ---------------------------------------------------------------------------
# Todo 10 -- situations and relations: the action layer
# ---------------------------------------------------------------------------
#
# ``situation`` is what an entity is *doing*. Every value is an **action in
# progress**, authored as a participial phrase that can be appended to the
# entity's clause: not "docked" and not
# "damaged". A static state is already covered twice over by ``condition`` and
# ``surface_detail``; what neither of those can do is make a picture look like a
# moment rather than a museum exhibit.
#
# **Every value opens with a gerund**, without exception, and a test enforces
# it. That is both the authoring rule that keeps a state from being smuggled in
# as an action ("under boarding assault" became "repelling a boarding assault")
# and the renderer's guarantee: one comma and the phrase attaches to any entity
# reference, in any slot, with no per-value special casing.
#
# Kind-scoped, because the verb has to fit the noun: a station cannot flee and a
# planet cannot board anything. A ``_default`` fall-through is authored as well,
# and it is not decoration -- it is the **cross-genre path**. The scene node owns
# situations, so a fantasy entity wired into a sci-fi scene gets its situation
# from this pack under a kind this pack has never heard of; ``pool_for`` reads
# through to ``_default`` and the entity acts instead of standing still.
#
# Two wording traps, both hit while authoring:
#
# * "venting atmosphere from a torn flank" is the plan's own example and it
#   cannot be authored as written -- ``atmosphere`` is on the rendering denylist
#   (it bans atmospheric haze, but a substring scan cannot tell the two apart).
#   The ship vents *vapour*, which is also what actually gets drawn.
# * Negation slips in through the back door in an action phrase: "with no lights
#   showing", "seams that were not there". Both were caught and rewritten to
#   name what *is* there. See ``prompt-data-never-negate``.
#
# **A situation must be legible in one still frame, from outside the subject,
# without an actor the scene has not described.** Three tests, all of which must
# pass:
#
# 1. *Camera* -- is there something to see? Sound, radio, temperature, intent and
#    elapsed process are not visible. "humming at a pitch that carries through the
#    deck" is a sentence about a deck nobody can see.
# 2. *Actor* -- does it need someone the prompt has not described? A small,
#    plural, incidental actor is fine, because a model draws it as background:
#    "being mined by a swarm of salvage drones" renders. A large, singular,
#    off-frame one is not: "being bombarded from orbit" renders as nothing, or as
#    an invented fleet.
# 3. *Frame* -- does it fit in one shot? "running a supply line between domes" is
#    a journey; "pulling up beside a supply dome" is a shot.
#
# The gerund rule still holds and is still tested; this is the rule about *what*
# the gerund may be. Only the frame-meta half is mechanical --
# ``tests/validate_data.py`` rejects a value naming its own invisibility, and the
# other two tests are enforced by review.

_SITUATION_DEFAULT = (
    # The cross-genre fall-through: true of anything that can be in a scene at
    # all, so a foreign-genre entity still acts.
    "drifting slowly through the void",
    "coming apart along one long seam",
    "advancing across open ground",
    "ducking low and backing away",
    "crossing the open ground",
    "being examined by a survey drone",
    "standing over the wreckage of something else",
    "rising from a low crouch",
    "unfolding from a resting pose",
    "leaning into the wind",
    "hanging motionless in the open",
    "waiting at the edge of the clearing",
    "breaking apart in a spreading cloud of debris",
    "shattering into a spray of fragments",
    "fleeing in a hard turn",
    "flaring in a single hard pulse",
    "tearing loose from a docking clamp",
    "moving out into the open",
)

#: The **needs-free core** of a kind's action pool. Every value here is true in
#: any place, so a subkind-group key that points at the core survives the band
#: floor in every environment the group can be drawn in. A value that names a
#: place it needs belongs in the specific tail instead, where ``value_needs``
#: can gate it.
_SITUATION_STARSHIP_COMMON = (
    "running dark past a derelict",
    "matching course with a slower cargo starship",
    "sweeping a searchlight across a hull",
    "rolling to present its armoured flank",
    "opening its forward launch bay doors",
    "passing in front of a banded amber moon",
    "crossing a star field in silhouette",
    "holding formation with two escorts",
    "drifting with its engines cold",
    "flashing a signal beacon in a slow pattern",
    "trailing a thin wake of particles",
    "turning its flank to a banded world",
    "sweeping the terrain below with a scanning beam",
    "settling into a parking orbit",
    "extending a dorsal sensor spine",
    "launching a probe from a nose bay",
    "decelerating on a long plume",
    "running a course through a debris field",
    "holding position over a landing pad",
    "breaking up under a barrage along its central hull",
    "slewing hard as a hull section tears away",
    "punching through a debris curtain at speed",
    "cracking open along a seam in the hull",
    "spinning out with a thruster stuck open",
    "dumping fuel in a spreading cloud",
    "breaking in half across a failing frame",
    "shuddering under a direct hit",
)

_SITUATION_CELESTIAL_CORE = (
    "drifting across a star field",
    "hanging at a steep angle against the stars",
    "wearing a faint halo",
    "dimming behind a dust lane",
    # Round XII: needs-free world actions, so a rare world still has a pool to
    # draw from and the group floor holds.
    "swelling in slow pulses across its face",
    "settling into a slower spin",
    "rotating through a slow cycle",
    "tilting slowly on its axis",
    "settling into a calm band",
    "paling along one flank",
    "flickering across its whole disc",
    "shedding a thin veil of gas",
    "thinning into a pale band",
)
_SITUATION_WORLD_SHARED = (
    "eclipsing a smaller companion",
    "breaking apart under tidal stress",
    "casting a curved terminator across its face",
    "towing a tiny moonlet",
    "standing in silhouette against a nebula",
    "trailing a captured asteroid in a long arc",
    "drawing debris into a slow orbit around itself",
    "shimmering faintly at its poles",
)
_SITUATION_SOLID = (
    "erupting a plume from a polar rift",
    "cracking open along a widening rift",
    "capping its poles in frost",
    "splitting into two drifting halves",
    "hurling a debris plume into orbit",
    "splitting along a molten rift that runs across its whole face",
    "losing a vast plume of vapour into space",
    "erupting a column of lava that arcs out into space",
    "being struck by a moon-sized impactor",
    "throwing a ring of ejecta into orbit after a giant impact",
    "cracking apart as a rust-red companion moon grazes it",
    "shedding its outer crust in a spreading debris ring",
    "being torn into a stream of debris by a passing star",
)
_SITUATION_GAS = (
    "flaring an aurora over the pole",
    "crossing its disc with a dark band",
    "being mined by a swarm of salvage drones",
    "flickering with lightning across a whole hemisphere",
    "swallowing a small ochre moon in a single pass",
    "trailing an infalling comet across its face",
    "churning a storm oval wider than a moon",
    "swallowing a comet in a flash across its cloud tops",
    "shedding a ring of ice from its equator",
    "bursting a new storm up through its cloud bands",
    "crackling with lightning storms along its cloud bands",
    "venting a plume of ice crystals from a polar storm",
    "rippling with spiral storms after a comet strike",
    "drawing a pale-violet moon apart into a new ring",
    "flaring vast auroras over both poles",
    "shedding a long tail of gas toward a nearby star",
    "herding a scatter of small moons across its face",
    "carrying the dark disc of a transiting moon across its cloud bands",
)
_SITUATION_SMALL = (
    "splitting along a deep fissure system",
    "venting geysers along a fracture line",
    "trailing a band of debris",
    "trailing an ion tail across the void",
    "drifting through a debris field",
    "shedding plates into a slow debris trail",
    "trailing a sharp-edged band of debris",
    "splitting open as it spins too fast",
    "spraying chunks of ice from a fresh impact",
    "breaking into a string of fragments along its orbit",
    "shattering under a mining charge",
    "tumbling end over end past a larger world",
    "outgassing plumes of vapour from a sunward crack",
    "trailing a long twin tail of dust and gas",
    "flaring into a coma of dust as it warms",
    "being bored into by automated drill rigs",
)
_SITUATION_STELLAR = (
    "shedding its outer shell in a slow detonation",
    "collapsing into a spreading shock front",
    "detonating in a shell of expanding gas",
    "brightening along one hemisphere",
    "throwing off a corona of charged particles",
    "trailing a veil of ionised gas",
    "hurling a looping prominence far off its surface",
    "tearing a stream of plasma from a companion star",
    "swelling as its outer layers boil away",
    "blasting a coronal mass ejection toward a nearby world",
    "flaring hard enough to scour a nearby ochre moon",
    "consuming an orbiting planet in a long streamer of fire",
    "sweeping a pulsar beam across the dust around it",
    "shedding a ring of gas from its equator",
    "erupting in a storm of sunspots across its face",
)
_SITUATION_STELLAR_POLAR = (
    "pulsing in a slow rhythm",
    "projecting a beam from its pole",
    "flinging a jet from its poles",
)
_SITUATION_SINGULARITY = (
    "drawing a spiral of infalling dust",
    "warping the star field around its rim",
    "projecting a beam from its pole",
    "flinging a jet from its poles",
    "tearing a passing star into a long spiral stream",
    "swallowing a starship caught in its accretion disc",
    "shredding a wandering planet into its disc",
    "firing twin plasma beams from its poles",
    "flaring as a cloud of debris spirals in",
    "flickering as a shattered moon crosses its event horizon",
    "wrapping a torn nebula into its disc",
    "capturing a comet into a tightening spiral",
)
_SITUATION_BINARY = (
    "flaring as its two cores spiral closer",
    "merging its two cores in a single detonation",
    "trading a bridge of plasma between its two stars",
)
_SITUATION_NEBULA = (
    "collapsing into a spreading shock front",
    "trailing a veil of ionised gas",
    "collapsing into a ring of newborn stars",
    "igniting a cluster of new stars along its edge",
    "flaring as a star detonates inside it",
    "rippling as a shock wave crosses it",
    "being torn apart by a supernova shock front",
    "being scattered by a passing black hole",
    "streaming a long filament toward another cloud",
    # Round XII: the reach floor needs one more event worth looking at.
    "collapsing into a dense knot of newborn stars",
)
_SITUATION_DISC = (
    "drawing a spiral of infalling dust",
    "being mined by a swarm of salvage drones",
    "trailing a sharp-edged band of debris",
    "scattering into a spray of ice after an impact",
    "being gouged by a rust-brown moon plunging through its rings",
    "tearing a starship apart in a spray of ring ice",
    "raining ring debris down onto a nearby blue-green moon",
    "shedding a spray of ice fragments into space",
    "colliding two ring bands in a shower of ice",
    "splitting its rings around a shepherd moon",
    "spiralling ring particles into a gap",
    "sparkling with ice crystals where a comet crossed it",
    "twisting into a kinked ringlet",
    "rippling with spiral waves from a passing moon",
)

#: What any body can do, whatever it is made of.
_CREATURE_ANY = (
    "signalling with waves of colour along its flank",
    "tracking something overhead",
    "feeding on a wreck's power core",
    "brooding over a clutch of luminous cysts",
)
#: What a body does with its own substance: moult, uncurl, shake something off.
_CREATURE_BODILY = (
    "flaring its body wide in a threat display",
    "flexing a freshly moulted outer skin",
    "extending a cluster of feelers",
    "flattening itself against a rock",
    "shaking flakes of hardened resin from its back",
    "slamming its whole bulk down",
    "shaking off a cloud of stinging motes",
    "grazing on radiant foliage",
    "guarding a nest",
    "unfolding from a resting pose",
    "stretching after a long rest",
    "shivering along its length",
    "twitching in its sleep",
)
#: What a body does by moving through a place. A rooted or diffuse body cannot.
_CREATURE_MOBILE = (
    "breaking out of a containment field with a single lunge",
    "stalking prey through the corridors",
    "watching from inside a ceiling vent",
    "striking at a fleeing shuttlecraft",
    "weaving through a stand of stalks",
    "bursting through a sealed door",
    "ducking low and backing away",
    "fleeing in a hard turn",
)
#: What a body does with limbs it actually has.
_CREATURE_LIMBED = (
    "spinning a resin nest between girders",
    "rearing up on its hind limbs",
    "lashing out with a hooked limb",
    "crawling up a vertical face",
)

_SITUATION_ROBOT_COMMON = (
    "extending a tool turret",
    "hoisting a beam into place",
    "spraying sealant on a seam",
    "cutting a panel free",
    "scanning a doorway",
    "climbing over a low wall",
    "prying open a hatch",
    "raising a heavy rock drill",
    "steadying a load with an outrigger",
    "sweeping a sensor beam down a shaft",
    "crouching to inspect wreckage",
    "dodging a falling slab of rock",
    "grinding to a halt with a seized joint",
    "going down under a mass of smaller units",
)

_SITUATION_VEHICLE_COMMON = (
    "cresting a rise in a cloud of dust",
    "grinding up a rocky slope",
    "sliding sideways on loose gravel",
    "parking beside a rock outcrop",
    "lowering a ramp onto sand",
    "raising a cloud of grit",
    "crawling along a canyon floor",
    "crossing a dry riverbed",
    "nosing into a cave mouth",
    "circling a landing site",
    "idling with its lights on",
    "rocking over a boulder",
    "spraying mud from its tracks",
    "braking hard at a cliff edge",
    "following a set of wheel ruts",
    "backing up to a cargo pod",
    "extending a sampling boom",
    "turning to face a dust storm",
    "churning up a spray of grit",
    "flipping onto its back on a hard turn",
    "throwing a track at speed",
    "bursting a hub against an obstacle",
    "losing a wheel at full throttle",
    "spinning out at full throttle",
    "snapping an axle on a hard landing",
    "shearing a tread on a jagged edge",
)

_SITUATION_STARSHIP = _SITUATION_STARSHIP_COMMON + (
    "emerging from a nebula",
    "fleeing through an asteroid field",
    "venting white vapour from a torn flank",
    "firing a full weapons array at a closing formation",
    "unloading cargo onto a docking arm",
    "taking on fuel from a refuelling starship's boom",
    "breaking orbit on a long burn",
    "hauling a stripped hulk in a tractor beam",
    "deploying survey drones in a spreading fan",
    "trailing smoke from one dead engine nacelle",
    "launching interceptors from an open bay",
    "holding station beside a survey beacon",
    "standing guard over a column of civilian starships",
    "driving through a blockade line",
    "flaring its drive coils for a jump",
    "landing hard with its gear folding",
    "ploughing a trench through the ground on impact",
    "settling onto the water on its belly",
    "scraping along a canyon wall",
    # Shared-core actions a starship takes anywhere.
    "fleeing in a hard turn",
    "breaking apart in a spreading cloud of debris",
    "drifting slowly through the void",
)


_SITUATION_STATION = (
    "swinging a cargo cradle out over open space",
    "spraying a fan of glittering coolant crystals from a ruptured line",
    "extending a new module on assembly arms",
    "repelling a boarding assault at the main lock",
    "venting vapour from a ruptured central truss",
    "strobing a red beacon from its mast",
    "being stripped by a swarm of salvage drones",
    "shuttering its docks against an incoming barrage",
    "berthing rows of small spacecraft along its central truss",
    "firing point-defence into a swarm",
    "lowering a cargo cradle onto a waiting hull",
    "carrying a cage of refit scaffolding",
    "listing badly with half its hull gone",
    "turning its long truss against the light",
    "unfolding a solar array wing",
    "extending a docking arm",
    "cycling a lock with a burst of vapour",
    "welding a new spar in place",
    "passing across the face of a planet",
    "rotating slowly with its radiators aglow",
    "opening a bank of bay doors",
    "retracting a docking boom",
    "printing a slow plume from a vent",
    "holding a small starship in a docking cradle",
    "angling its mirrors toward a star",
    "running a cargo gantry along a rail",
    "extending a docking boom between modules",
    "drifting with its bays sealed",
    "swinging a beacon through the dark",
    "unfolding a radiator fin bank",
    "lowering a maintenance platform",
    "flaring a docking guide light",
    "turning a cupola toward a nebula",
    "shearing in half along its central truss",
    "being swarmed by small starships at every docking arm",
    "tumbling out of its rotation",
    "cracking open along a docking arm",
    "collapsing into a trailing field of wreckage",
    "spilling a white plume from a ruptured hull",
    "breaking apart in a spreading cloud of debris",
)

_CREATURE_SWARMING = (
    "swarming across a hull in a moving carpet",
    "flowing across a hull as one body",
    "swarming up a docking spar",
)
_CREATURE_BURROWING = (
    "burrowing up through fractured rock",
)
_CREATURE_SOARING = (
    "drifting on thermals above a canyon",
)

_SITUATION_SPACEFARER = (
    "making first contact with open hands",
    "sealing a hull breach with a foam sprayer",
    "waving a straggler toward the airlock",
    "running a diagnostic on an open panel",
    "hauling a stretcher through a smoking corridor",
    "levelling a weapon at something off to one side",
    "projecting a holographic star map from one palm",
    "climbing a hull on magnetic boots",
    "taking cover behind a buckled bulkhead",
    "planting a survey marker in red dust",
    "sealing a cracked visor with tape",
    "arguing over a projected chart",
    "leading a boarding party through a cut hatch",
    "waking from cryo with frost still on the suit",
    "signalling a descending lander with a flare",
    "kneeling to read a bootprint",
    "clamping a magnetic beacon to a deck plate",
    "welding a seam with a torch",
    "planting a beacon on a ridge",
    "hauling a cargo pod up a ramp",
    "keying a sequence into a console",
    "scanning a wall with a handheld",
    "strapping into a seat",
    "pushing a cart of supplies",
    "tightening a coupling with a wrench",
    "crouching behind a cargo pod",
    "chalking a mark on a wall",
    "passing a tool to a colleague",
    "hosing dust off a panel",
    "tying a bandage around their own forearm",
    "steadying a ladder for a colleague",
    "reaching down to help someone up",
    "cutting through a jammed airlock with a torch",
    "shouldering a buckling bulkhead back into place",
    "severing a snarl of cabling",
    "carrying a child through a smoke-filled corridor",
    "sealing a breach as the air thins",
    "running through a collapsing gantry",
    "diving clear of a falling beam",
    "fighting off a boarder at the airlock",
    "catching a falling colleague by the wrist",
    "fighting a flooding compartment",
    "holding a door against a rush of pressure",
    # Round XXI: the interior acts above now need a built place, so the open
    # surface and the deep water each get acts of their own.
    "stumbling as the ground gives way underfoot",
    "skidding down a loose slope on their heels",
    "diving flat as something streaks low overhead",
    "throwing an arm up against a sudden flare of light",
    "being dragged sideways by a surging current",
    "kicking back from a sudden eruption of silt",
    "losing their grip on a guideline in the current",
    "shining a helmet light into the murk",
    "hauling themselves along a guideline",
    "clipping a sample bag to their belt",
    "checking a depth readout on their wrist",
    # Shared-core actions a person takes anywhere.
    "ducking low and backing away",
    "advancing across open ground",
    "standing over the wreckage of something else",
    "leaning into the wind",
)

_SITUATION_ROBOT = _SITUATION_ROBOT_COMMON + (
    "welding a seam along a hull plate",
    "striding through waist-deep drifts",
    "powering down into a maintenance cradle",
    "sweeping a corridor with its optics",
    "boring into rock with a heavy rock drill",
    "trading shots across an open bay",
    "planting sensor stakes in a grid",
    "rising from a half-buried crouch",
    "clearing debris from a blocked hatch",
    "hunting through the rubble for movement",
    "drilling into a wall",
    "crossing cracked ground",
    "righting itself after a fall",
    "falling from a gantry",
    # Shared-core actions a machine takes anywhere, so a limbless unit in a
    # trench still has a pool to draw from.
    "ducking low and backing away",
    "advancing across open ground",
    "unfolding from a resting pose",
    "moving out into the open",
    # Round XII: the actions below need a limb or a leg. They live in the kind
    # pool so a combat machine can take them; the stance check keeps them off a
    # tracked chassis, and the role conflicts keep them off a civil one.
    "levelling its shoulder cannon",
    "pulling a damaged unit to cover",
)

_SITUATION_ARTIFACT = (
    "shedding a crust of dust as it moves",
    "projecting a chart of unmapped space",
    "drawing debris into a slow orbit around itself",
    "splitting open along freshly-formed seams",
    "pulsing light through its veins",
    "being lifted onto a recovery cradle",
    "spilling light from a widening crack",
    "hanging unsupported above the ground",
    "drifting through a debris field",
    "being circled by scanning drones",
    "discharging arcs across its surface",
    "bending a nearby survey mast toward itself",
    "cracking under a cutting beam",
    "sinking into the dust it rests on",
    "being guarded by a flight of sentry drones",
    "hovering just above a plinth",
    "humming as a seam brightens",
    "unfolding a panel of lattices",
    "rotating slowly on its axis",
    "drawing a spiral of dust into orbit",
    "pulsing in a slow rhythm",
    "floating above a ruined floor",
    "projecting a column of light",
    "cracking open along a seam",
    "humming with a low tone",
    "hovering above a fallen plinth",
    "shedding flakes of light",
    "standing amid a circle of stones",
    "unfolding a set of fins",
    "spinning up a cloud of fragments",
    "settling onto a stone plinth",
    "rising slowly from the ground",
    "tearing open along a line of light",
    "pulling a spiral of loose rubble toward its base",
    "lifting a spread of rubble off the ground",
    "going dark all at once",
    "bursting in a wave of light",
    "collapsing into a singularity",
    "drawing loose debris off the deck toward itself",
    "swallowing a survey drone whole",
    "cracking the ground beneath it",
    "pulling a descending lander out of the sky",
    # Shared-core actions an artifact takes anywhere.
    "flaring in a single hard pulse",
    "shattering into a spray of fragments",
    "hanging motionless in the open",
)

_SITUATION_VEHICLE = _SITUATION_VEHICLE_COMMON + (
    "towing a string of cargo pods across a salt flat",
    "pulling up beside a supply dome",
    "fording a shallow methane channel",
    "unloading cargo pods onto a landing pad",
    "spinning a track in loose scree",
    "racing a storm front toward shelter",
    "charging across open ground with its ramp raised",
    "nosing through a cloud of stirred-up silt",
    "edging down a crater wall at a steep angle",
    "drilling a core sample from the bedrock",
    "hovering low over broken ground",
    "waiting with its ramp down and cabin open",
    "climbing a dune ridge at full throttle",
    "kicking up a long dust plume",
    "taking hits from a ridge line",
    "churning through a muddy flat",
    "sliding down a scree slope",
    "nosing over a sharp crest",
    "reversing out of a gully",
    "dropping toward a landing pad on its belly thrusters",
    "cutting through a dust storm at low altitude",
    "plunging through a sheet of thin ice",
    "rolling down a slope out of control",
    "ramming a barricade at full speed",
    "skimming low over a cloud bank at full speed",
    # Shared-core actions a vehicle takes anywhere.
    "advancing across open ground",
    "ducking low and backing away",
    "moving out into the open",
    "crossing the open ground",
)

_SITUATION_WRECK = (
    "settling deeper into the sand",
    "breaking up as it falls",
    "being stripped by a swarm of salvage drones",
    "hanging at a steep angle against the stars",
    "sheltering a nest of hull-borers",
    "grinding against the rock it landed on",
    "shedding plates into a slow debris trail",
    "being cut open by salvage drones",
    "disappearing under a creeping fungal mat",
    "being surveyed by a drifting inspection drone",
    "leaking a slick across the water",
    "collapsing under its own weight",
    "spilling its contents across the ground",
    "spilling a fan of debris down a slope",
    "catching the light along a torn edge",
    "slumping as a spar gives way",
    "breaking apart in a slow avalanche",
    "shedding a slab of plating as it settles",
    "spilling a wave of debris across the ground",
    "collapsing into the pit it made",
    "tearing open along a rusted seam",
    "pinning a salvage drone beneath a buckled plate",
    "giving way under a salvage drone's cutting beam",
    "burying a salvage crawler in a slide",
    "buckling as its main girder gives way",
    "shedding a cascade of plate fragments",
    "tearing open along a frost-welded seam",
    "crumbling into a field of drifting debris",
    # Shared-core actions a wreck takes anywhere.
    "coming apart along one long seam",
    "shattering into a spray of fragments",
    "being examined by a survey drone",
)

# --- Task 4 situation families ---
_SITUATION_EVA = (
    "tumbling away from a hull after a suit-thruster failure",
    "firing suit thrusters toward a crewmate in a sealed suit",
    "clinging to a spinning hull plate",
    "shoving a tumbling hull plate out of their path",
    "shielding a cracked visor from a spray of debris",
    "manoeuvring through a debris field on suit thrusters",
    "tumbling end over end with a thruster pack jammed open",
    "carrying an unconscious crewmate in a sealed suit",
    "being struck by a tumbling fragment of hull",
    "grappling with a boarder in open vacuum",
    "clinging to the outside of a tumbling escape pod",
    "sealing a hull breach from the outside",
    "planting a magnetic beacon on a drifting asteroid",
    "pushing off from a hull toward a drifting cargo pod",
    "reeling in a drifting survey probe",
    "sweeping a helmet beam across a derelict hull",
    "signalling a distant rescue lander with a flare",
    "grabbing a spinning toolkit before it drifts away",
    "bracing against the kick of a rivet driver",
    "watching a starship burn past at close range",
    "releasing a damaged survey probe into a slow tumble",
    "drifting beside a shattered viewport",
)
_SITUATION_DRONE_SPACE = (
    "dodging a tumbling hull fragment",
    "tumbling into a debris cloud after a glancing collision",
    "wrenching loose from a magnetic clamp",
    "shielding a suited crewmate from a spray of debris",
    "spinning up a cutting beam against a derelict hull",
    "scanning a drifting wreck with a fan of sensor beams",
    "guiding a cargo pod in a tractor beam",
    "latching onto a hull with magnetic grapples",
    "welding a plate over a hull breach",
    "deploying a spread of smaller sensor drones",
    "shepherding a drifting survey probe back to its bay",
    "sweeping a sensor beam across a field of debris",
    "sealing a cracked viewport with a foam spray",
    "chasing a spinning fragment through the debris",
    "firing a short thruster burst to hold position",
)
_SITUATION_WRECK_FALL = (
    "breaking up as it falls through the cloud tops",
    "shedding burning plates as it falls",
    "spinning down through a lightning front",
    "dropping through the cloud tops in two pieces",
    "trailing smoke as it drops through a storm band",
    "tumbling end over end through the clouds",
)
_SITUATION_VEHICLE_SKY = (
    "punching through the top of a storm band",
    "weaving through towering cloud columns at speed",
    "diving through a break in the cloud tops",
    "racing a lightning front across the cloud tops",
    "fighting a crosswind above the cloud tops",
    "punching through a curtain of rain",
    "skimming the top of a storm band",
)
_SITUATION_VEHICLE_FLOOR = (
    "settling onto a landing pad on its thrusters",
    "lowering its ramp onto a deck",
    "rolling to a stop in a hangar bay",
    "idling beside a cargo stack",
    "parking between two cargo containers",
    "resting on a maintenance cradle",
)
_SITUATION_DRONE_SKY = (
    "sweeping a sensor beam through a storm band",
    "riding a thermal column above the cloud tops",
    "losing altitude in a downdraft",
    "being struck by a lightning discharge",
    "sheltering in the lee of a cloud bank",
)
_SITUATION_DRONE_GROUND = (
    "driving a survey stake into the ground",
    "crawling across a cracked plain",
    "scanning a fresh borehole over broken ground",
    "anchoring itself against a dust storm",
)


_SITUATION_DRONE_TRENCH = (
    "passing a vent chimney",
    "running a sonar sweep along the trench floor",
    "collecting samples from a mineral chimney",
)
_SITUATION_WRECK_SPACE = (
    "drifting end over end through the void",
    "trailing a slow cloud of hull fragments",
)



_CREATURE_JAWED = (
    "clamping its jaws shut with a crack",
    "snapping at a passing spark",
    "spitting a stream of caustic bile",
    "lowering its jaws to drink",
    "pressing its jaws to the ground",
    "dragging a kill toward its burrow",
    "hauling a carcass into the shade",
    "snapping at the air in a sudden strike",
    "lunging with its jaws flung wide",
    "dragging a survivor into the dark",
    "spreading a hood of skin",
    "tearing into a fallen hull",
)
_CREATURE_SPINED = (
    "spreading a fan of spines",
    "raising a crest of quills",
)
_CREATURE_GILLED = (
    "fanning a set of gill frills",
)
_CREATURE_SPORING = (
    "shedding spores in a slow cloud",
    "releasing a slow drift of spores",
    "shaking loose a cloud of spores",
)
_CREATURE_COILED = (
    "coiling its body into a tight spiral",
    "curling into a defensive coil",
)
#: A body with no jaw still engulfs, splits and surges: the event floor for the
#: jawless creature groups, which cannot take the jawed actions.
_CREATURE_ENGULFING = (
    "swelling to twice its size",
    "writhing in a tight coil",
    "surging over a barricade in one wave",
    "spreading its membranes wide in a flat fan",
    "spreading across a landing platform",
)


#: A diffuse or void body drifts, streams and pulses; it has no limb to reach with.
_CREATURE_DRIFTING = (
    "curling into a tight knot of light",
    "streaming away in a long luminous ribbon",
    "enveloping a drifting hull plate",
    "pulsing in slow waves of light",
    "spreading into a thin luminous veil",
    "drawing a thread of light out of a passing comet",
    "shifting through a spectrum of colours",
    "folding its body inward in a slow pulse",
    "seeping through a bulkhead in slow tendrils",
    "trailing a long ribbon of ionised gas",
    "paling to a soft sheen",
    "gathering itself out of a drifting veil",
    "sweeping a wide arc of light across a hull",
    "sinking into a still pool of light",
    "wrapping around a derelict's hull",
    "flickering across a whole hull",
)
#: A rooted body reaches, snaps and engulfs; it cannot stalk, burrow or flee.
_CREATURE_ROOTED = (
    "unfurling a ring of luminous fronds",
    "snapping shut in a sudden spasm",
    "lashing out with stinging fronds",
    "curling its fronds inward around its prey",
    "reaching out a ring of tendrils",
    "closing on its prey in a sudden rush",
    "unfurling into a broad fan",
    "wrapping its fronds tight around its own stalk",
    "spreading into a broad mat",
    "unfurling a snare of sticky filaments",
    "settling into a slow pulse",
)
_SITUATION_ROBOT_LIMBED = (
    "holding a collapsing wall up with its shoulders",
    "burying its fist in a bulkhead",
    "tearing a hatch off its hinges",
    "carrying an injured crewmember",
    "lifting a cargo container overhead",
    "rising from a low crouch",
)


_SITUATION_DRONE_SKY2 = (
    "tumbling out of control after a lightning strike",
    "being flung into a cloud bank by a gust",
    "sweeping a sensor beam across the cloud tops",
    "riding a thermal updraft over a storm band",
    "holding station against a crosswind",
)
_SITUATION_DRONE_TRENCH2 = (
    "losing buoyancy and settling into the silt",
    "drifting between vent chimneys",
    "sweeping a searchlight across the murk",
    "hovering to draw a sample with a probe",
)
_SITUATION_DRONE_EVENT2 = (
    "being crushed in a rockfall",
    "digging itself out of a drift",
)
_SITUATION_VEHICLE_SKY2 = (
    "stalling in a crosswind above a canyon",
    "pulling up hard out of a canyon dive",
    "burning through re-entry in a sheath of plasma",
)
_SITUATION_VEHICLE_FLOOR2 = (
    "settling onto a landing platform",
    "rolling to a stop inside a hangar",
    "extending a boarding ramp onto a deck",
    "opening its cargo bay onto a loading pad",
    "waiting on a launch platform",
    "holding position beside a docking cradle",
)


_SITUATION_VEHICLE_FLYING = (
    "losing a lift-pod panel in a violent gust",
    "breaking up in a violent gust",
    "crash-landing on its belly in a spray of dust",
    "soaring above a canyon on its gravlift pods",
    "releasing a spread of survey probes over the plain",
    "tipping one lift pod over a volcanic vent",
    "shaking in the turbulence above a storm",
    "sweeping a sampling scoop through an ash plume",
    "gliding in to land beside a supply dome",
    "riding a rising thermal in a slow spiral",
)
_SITUATION_DRONE_INDOOR = (
    "rolling along a corridor on a maintenance run",
    "ascending a maintenance shaft",
    "waiting beside a sealed hatch",
    "sweeping a corridor with its optics",
    "docking at a charging cradle",
)
_SITUATION_ROBOT_TRENCH = (
    "rolling along a trench floor",
)
_SITUATION_VEHICLE_SUBMERGED = (
    "cracking its hull under crushing pressure",
    "trailing a stream of bubbles from a breach",
    "being gripped by a tentacled creature",
    "surfacing through a sheet of ice",
    "recovering a probe from the seabed",
    # Round XIII: the aqueous/combustion rule took a burning situation out of
    # every submerged place, which dropped this pool under the event floor.
    # Replaced with events that belong down here rather than by relaxing it.
    "blowing ballast in a rush of silt",
    "cutting a snarl of cable away with a manipulator",
    "tilting hard as a vent plume slams into its flank",
    "punching through a curtain of rising bubbles",
)


_SITUATION_DRONE_INDOOR2 = (
    "being crushed by a closing hatch",
    "being knocked from its cradle by a swinging cargo arm",
)
_SITUATION_VEHICLE_FLOOR3 = (
    "slamming into a landing platform in a burst of dust",
    "folding its landing struts on contact",
    "grinding to a halt against a bulkhead",
    "tearing loose from a tie-down clamp",
)


_SITUATION_SINGULARITY_EXTRA = (
    "pulling a stream of gas into a tight knot",
    "spitting a stream of particles from its poles",
    # Round XII: the reach floor needs one more event worth looking at.
    "swallowing a nearby star in a single gulp",
)
_SITUATION_DISC_EXTRA = (
    "sweeping a gap clean of ring particles",
    # Round XII: the reach floor needs one more event worth looking at.
    "rippling in slow waves across its bands",
)


# Round XIV additions. Declared as named tuples ahead of the literal below,
# never appended to the dict afterwards: ``scripts/builtin_options.py`` reads
# pools with ``ast`` and cannot see a later subscript assignment.
#: Replacements for the acts this round deleted. A machine that "loses a tool
#: arm in a hard strike" or "collapses in a shower of parts" had no cause in the
#: frame and read as a droid falling apart on its own; a wreck that was
#: "sparking" or "burning" read as live. These keep each pool above its floor
#: with events a single frame can show.
_MACHINE_EVENTS = (
    "swerving hard around a sudden obstacle",
    "slipping through a closing gap at full speed",
    "recoiling from a sudden burst of light",
)
_DRONE_ACTS = _MACHINE_EVENTS + ("turning a slow circle to map its surroundings",)
_ROBOT_ACTS = (
    "shouldering through a cascade of loose debris",
    "turning to follow a sudden movement",
)
_WRECK_ACTS = (
    "rolling slowly to show a torn-open flank",
    "turning slowly inside a halo of its own debris",
    "being latched onto by a salvage grapple drone",
    "resting on its side against a ridge",
    "being picked over by a pair of salvage drones",
    "lying half-buried under drifted dust",
    "turning slowly to show its gutted interior",
    "lying in two pieces across a shallow valley",
)
#: Variety kept by adding: the deletions above cost the station, starship and
#: wreck pools measurable entropy against ``main``, so each gets legible acts
#: with a cause in the frame and no second plume.
_STATION_ACTS = (
    "extending a boarding bridge to a docked starship",
    "releasing a string of cargo pods on a slow drift",
    "rotating a sensor array toward the far stars",
    "guiding a small starship into an open docking bay",
    "spreading a swarm of repair drones across its hull",
    "spinning its habitat ring up to speed",
    "catching a drifting cargo pod in a docking cradle",
)
_STARSHIP_ACTS = (
    "towing a disabled shuttlecraft in a tractor beam",
    "recovering a probe into a side bay",
    "passing close along a derelict's flank",
    "arriving out of a jump in a ripple of distortion",
    "swinging hard around a tumbling asteroid",
)
#: A rooted creature and a diffuse being indoors lost their drone-snaring and
#: hull-crossing acts to the rules below, so each gets acts it can have in any
#: room -- variety is kept by adding, never by relaxing a floor.
_ROOTED_ACTS = ("snapping every frond open at once",)
_DIFFUSE_ACTS = (
    "scattering into a swarm of drifting motes",
    "reforming out of a scatter of drifting motes",
    "pouring through a narrow gap like a liquid",
    "wrapping itself around a flickering light fitting",
    "swelling to twice its size in a single pulse",
)

#: Round XV: what a starship does at a planet's surface. The fleet manoeuvres
#: below need open space, so these keep a grounded ship something to be doing.
_STARSHIP_SURFACE_ACTS = (
    "lifting off in a blast of kicked-up grit",
    "skimming low over broken ground at speed",
    "descending onto a cleared landing site",
    "idling on the ground with its ramp lowered",
    "kicking up a wake of dust on a low pass",
    "firing its braking thrusters above a landing site",
    "waiting on a scorched landing apron",
    "powering up on a cracked landing apron",
    "taking fire from a ground battery as it lifts off",
    "venting coolant steam onto the ground after landing",
    "rising slowly on vertical thrusters",
)

SITUATION_POOLS: dict[str, tuple[str, ...]] = {
    POOL_DEFAULT_KEY: _SITUATION_DEFAULT,
    "starship": _SITUATION_STARSHIP + _STARSHIP_ACTS + _STARSHIP_SURFACE_ACTS,
    "celestial body": _SITUATION_CELESTIAL_CORE + _SITUATION_WORLD_SHARED + _SITUATION_STELLAR,
    "space station": _SITUATION_STATION + _STATION_ACTS,
    "alien creature": _CREATURE_ANY + _CREATURE_BODILY + _CREATURE_MOBILE + _CREATURE_LIMBED + _CREATURE_JAWED,
    "spacefarer": _SITUATION_SPACEFARER + _SITUATION_EVA,
    "robot or mech": _SITUATION_ROBOT + _SITUATION_ROBOT_TRENCH + _ROBOT_ACTS,
    "humanoid unit": _SITUATION_ROBOT + _SITUATION_ROBOT_LIMBED + _SITUATION_ROBOT_TRENCH + _ROBOT_ACTS,
    "alien artifact": _SITUATION_ARTIFACT,
    "surface vehicle": _SITUATION_VEHICLE + _SITUATION_VEHICLE_SKY + _SITUATION_VEHICLE_FLOOR + _SITUATION_VEHICLE_SKY2 + _SITUATION_VEHICLE_FLOOR2 + _SITUATION_VEHICLE_SUBMERGED + _SITUATION_VEHICLE_FLOOR3,
    "wreck": _SITUATION_WRECK + _SITUATION_WRECK_FALL + _SITUATION_WRECK_SPACE + _WRECK_ACTS,
    # A subkind-group key points at the needs-free core, so it survives the band
    # floor in every place the group can be drawn. Group-specific actions that
    # need a place belong in ``value_needs`` and a specific tail, not here.
    "solid world": _SITUATION_CELESTIAL_CORE + _SITUATION_WORLD_SHARED + _SITUATION_SOLID,
    "gas world": _SITUATION_CELESTIAL_CORE + _SITUATION_WORLD_SHARED + _SITUATION_GAS,
    "small body": _SITUATION_CELESTIAL_CORE + _SITUATION_SMALL,
    "star body": _SITUATION_CELESTIAL_CORE + _SITUATION_STELLAR + _SITUATION_STELLAR_POLAR,
    "binary system": _SITUATION_CELESTIAL_CORE + _SITUATION_STELLAR + _SITUATION_BINARY,
    "singularity": _SITUATION_CELESTIAL_CORE + _SITUATION_SINGULARITY + _SITUATION_SINGULARITY_EXTRA,
    "diffuse cloud": _SITUATION_CELESTIAL_CORE + _SITUATION_NEBULA,
    "disc system": _SITUATION_CELESTIAL_CORE + _SITUATION_DISC + _SITUATION_DISC_EXTRA,
    "diffuse being": _CREATURE_ANY + _CREATURE_DRIFTING + _CREATURE_ENGULFING + _DIFFUSE_ACTS,
    "tentacular": _CREATURE_ANY + _CREATURE_BODILY + _CREATURE_MOBILE + _CREATURE_LIMBED + _CREATURE_JAWED,
    "segmented": _CREATURE_ANY + _CREATURE_BODILY + _CREATURE_MOBILE + _CREATURE_LIMBED + _CREATURE_JAWED + _CREATURE_SPINED,
    "vermiform": _CREATURE_ANY + _CREATURE_BODILY + _CREATURE_MOBILE + _CREATURE_BURROWING + _CREATURE_JAWED + _CREATURE_COILED,
    "winged": _CREATURE_ANY + _CREATURE_BODILY + _CREATURE_MOBILE + _CREATURE_SOARING + _CREATURE_JAWED,
    "aquatic": _CREATURE_ANY + _CREATURE_BODILY + _CREATURE_MOBILE + _CREATURE_JAWED + _CREATURE_GILLED,
    "amorphous": _CREATURE_ANY + _CREATURE_BODILY + _CREATURE_MOBILE + _CREATURE_SWARMING + _CREATURE_ENGULFING,
    "sessile growth": _CREATURE_ANY + _CREATURE_BODILY + _CREATURE_ROOTED + _CREATURE_SPORING + _ROOTED_ACTS,
    "quadrupedal": _CREATURE_ANY + _CREATURE_BODILY + _CREATURE_MOBILE + _CREATURE_LIMBED + _CREATURE_JAWED + _CREATURE_SPINED,
    "upright hunter": _CREATURE_ANY + _CREATURE_BODILY + _CREATURE_MOBILE + _CREATURE_LIMBED + _CREATURE_JAWED,
    "void dweller": _CREATURE_ANY + _CREATURE_DRIFTING + _CREATURE_SOARING + _CREATURE_ENGULFING,
    "radial form": _CREATURE_ANY + _CREATURE_BODILY + _CREATURE_MOBILE + _CREATURE_JAWED + _CREATURE_SPINED,
    "stone feeder": _CREATURE_ANY + _CREATURE_BODILY + _CREATURE_MOBILE + _CREATURE_LIMBED + _CREATURE_JAWED + _CREATURE_SPINED + _CREATURE_BURROWING,
    "caste swarm": _CREATURE_ANY + _CREATURE_BODILY + _CREATURE_MOBILE + _CREATURE_LIMBED + _CREATURE_JAWED + _CREATURE_SWARMING,
    "mimic body": _CREATURE_ANY + _CREATURE_BODILY + _CREATURE_MOBILE + _CREATURE_ENGULFING,
    "filter swarm": _CREATURE_ANY + _CREATURE_BODILY + _CREATURE_MOBILE + _CREATURE_SWARMING + _CREATURE_ENGULFING + _CREATURE_GILLED,
    "symbiotic body": _CREATURE_ANY + _CREATURE_BODILY + _CREATURE_ROOTED + _CREATURE_SPORING + _ROOTED_ACTS,
    "brooding colony": _CREATURE_ANY + _CREATURE_BODILY + _CREATURE_ROOTED + _CREATURE_SPORING + _CREATURE_SPINED + _ROOTED_ACTS,
    "flying": _SITUATION_VEHICLE_COMMON + _SITUATION_VEHICLE_SKY + _SITUATION_VEHICLE_FLOOR + _SITUATION_VEHICLE_SKY2 + _SITUATION_VEHICLE_FLOOR2 + _SITUATION_VEHICLE_FLYING + _SITUATION_VEHICLE_FLOOR3,
    "small drone": _SITUATION_ROBOT_COMMON + _SITUATION_DRONE_SPACE + _SITUATION_DRONE_SKY + _SITUATION_DRONE_GROUND + _SITUATION_DRONE_TRENCH + _SITUATION_DRONE_SKY2 + _SITUATION_DRONE_TRENCH2 + _SITUATION_DRONE_EVENT2 + _SITUATION_DRONE_INDOOR + _SITUATION_DRONE_INDOOR2 + _DRONE_ACTS,
    "courier": _SITUATION_STARSHIP_COMMON + _STARSHIP_SURFACE_ACTS,
}

#: How much a situation is worth looking at.
#:
#: "event"    -- something is happening with stakes or a change of state:
#:               firing, breaking apart, launching, fleeing, venting, cracking
#:               open, being boarded, erupting, going down.
#: "activity" -- purposeful work with visible motion: welding, hauling,
#:               drilling, docking, unloading, dragging something clear.
#: "idle"     -- a pose or a micro-gesture: pivoting at the waist, showing its
#:               windows in a grid, glinting as it turns. Real, occasionally
#:               wanted, and never what a scene should mostly be.
SITUATION_TIERS: dict[str, str] = {
    'drifting slowly through the void': 'activity',
    'coming apart along one long seam': 'activity',
    'advancing across open ground': 'event',
    'ducking low and backing away': 'event',
    'crossing the open ground': 'activity',
    'being examined by a survey drone': 'idle',
    'standing over the wreckage of something else': 'event',
    'rising from a low crouch': 'activity',
    'unfolding from a resting pose': 'activity',
    'leaning into the wind': 'idle',
    'hanging motionless in the open': 'idle',
    'waiting at the edge of the clearing': 'idle',
    'breaking apart in a spreading cloud of debris': 'event',
    'shattering into a spray of fragments': 'event',
    'fleeing in a hard turn': 'event',
    'flaring in a single hard pulse': 'event',
    'tearing loose from a docking clamp': 'event',
    'moving out into the open': 'activity',
    'running dark past a derelict': 'activity',
    'matching course with a slower cargo starship': 'activity',
    'sweeping a searchlight across a hull': 'activity',
    'rolling to present its armoured flank': 'activity',
    'opening its forward launch bay doors': 'activity',
    'passing in front of a banded amber moon': 'activity',
    'crossing a star field in silhouette': 'activity',
    'holding formation with two escorts': 'activity',
    'drifting with its engines cold': 'idle',
    'flashing a signal beacon in a slow pattern': 'activity',
    'trailing a thin wake of particles': 'activity',
    'turning its flank to a banded world': 'activity',
    'sweeping the terrain below with a scanning beam': 'activity',
    'settling into a parking orbit': 'activity',
    'extending a dorsal sensor spine': 'activity',
    'launching a probe from a nose bay': 'activity',
    'decelerating on a long plume': 'activity',
    'running a course through a debris field': 'activity',
    'holding position over a landing pad': 'idle',
    'breaking up under a barrage along its central hull': 'event',
    'slewing hard as a hull section tears away': 'event',
    'punching through a debris curtain at speed': 'event',
    'cracking open along a seam in the hull': 'event',
    'spinning out with a thruster stuck open': 'event',
    'dumping fuel in a spreading cloud': 'event',
    'breaking in half across a failing frame': 'event',
    'shuddering under a direct hit': 'event',
    'emerging from a nebula': 'activity',
    'fleeing through an asteroid field': 'event',
    'venting white vapour from a torn flank': 'event',
    'firing a full weapons array at a closing formation': 'event',
    'unloading cargo onto a docking arm': 'activity',
    "taking on fuel from a refuelling starship's boom": 'activity',
    'breaking orbit on a long burn': 'event',
    'hauling a stripped hulk in a tractor beam': 'activity',
    'deploying survey drones in a spreading fan': 'activity',
    'trailing smoke from one dead engine nacelle': 'activity',
    'launching interceptors from an open bay': 'event',
    'holding station beside a survey beacon': 'activity',
    'standing guard over a column of civilian starships': 'activity',
    'driving through a blockade line': 'event',
    'flaring its drive coils for a jump': 'event',
    'landing hard with its gear folding': 'event',
    'ploughing a trench through the ground on impact': 'event',
    'settling onto the water on its belly': 'activity',
    'scraping along a canyon wall': 'event',
    'eclipsing a smaller companion': 'activity',
    'erupting a plume from a polar rift': 'event',
    'breaking apart under tidal stress': 'event',
    'cracking open along a widening rift': 'event',
    'drawing a spiral of infalling dust': 'activity',
    'flaring an aurora over the pole': 'event',
    'trailing a sharp-edged band of debris': 'activity',
    'venting geysers along a fracture line': 'event',
    'being mined by a swarm of salvage drones': 'activity',
    'shedding its outer shell in a slow detonation': 'event',
    'casting a curved terminator across its face': 'activity',
    'capping its poles in frost': 'idle',
    'splitting along a deep fissure system': 'event',
    'wearing a faint halo': 'idle',
    'towing a tiny moonlet': 'activity',
    'trailing a band of debris': 'activity',
    'standing in silhouette against a nebula': 'idle',
    'splitting into two drifting halves': 'event',
    'hurling a debris plume into orbit': 'event',
    'collapsing into a spreading shock front': 'event',
    'flickering with lightning across a whole hemisphere': 'event',
    'swallowing a small ochre moon in a single pass': 'event',
    'detonating in a shell of expanding gas': 'event',
    'trailing an ion tail across the void': 'activity',
    'trailing a captured asteroid in a long arc': 'activity',
    'trailing an infalling comet across its face': 'activity',
    'drawing debris into a slow orbit around itself': 'activity',
    'drifting through a debris field': 'idle',
    'shedding plates into a slow debris trail': 'event',
    'hanging at a steep angle against the stars': 'idle',
    'crossing its disc with a dark band': 'activity',
    'dimming behind a dust lane': 'idle',
    'shimmering faintly at its poles': 'idle',
    'brightening along one hemisphere': 'activity',
    'trailing a veil of ionised gas': 'activity',
    'pulsing in a slow rhythm': 'idle',
    'throwing off a corona of charged particles': 'activity',
    'projecting a beam from its pole': 'activity',
    'warping the star field around its rim': 'activity',
    'flinging a jet from its poles': 'activity',
    'drifting across a star field': 'idle',
    'swinging a cargo cradle out over open space': 'activity',
    'spraying a fan of glittering coolant crystals from a ruptured line': 'activity',
    'extending a new module on assembly arms': 'activity',
    'repelling a boarding assault at the main lock': 'event',
    'venting vapour from a ruptured central truss': 'activity',
    'strobing a red beacon from its mast': 'activity',
    'being stripped by a swarm of salvage drones': 'idle',
    'shuttering its docks against an incoming barrage': 'event',
    'berthing rows of small spacecraft along its central truss': 'activity',
    'firing point-defence into a swarm': 'event',
    'lowering a cargo cradle onto a waiting hull': 'activity',
    'carrying a cage of refit scaffolding': 'activity',
    'listing badly with half its hull gone': 'activity',
    'turning its long truss against the light': 'idle',
    'unfolding a solar array wing': 'activity',
    'extending a docking arm': 'activity',
    'cycling a lock with a burst of vapour': 'activity',
    'welding a new spar in place': 'activity',
    'passing across the face of a planet': 'activity',
    'rotating slowly with its radiators aglow': 'idle',
    'opening a bank of bay doors': 'activity',
    'retracting a docking boom': 'activity',
    'printing a slow plume from a vent': 'activity',
    'holding a small starship in a docking cradle': 'activity',
    'angling its mirrors toward a star': 'idle',
    'running a cargo gantry along a rail': 'activity',
    'extending a docking boom between modules': 'activity',
    'drifting with its bays sealed': 'idle',
    'swinging a beacon through the dark': 'activity',
    'unfolding a radiator fin bank': 'activity',
    'lowering a maintenance platform': 'activity',
    'flaring a docking guide light': 'activity',
    'turning a cupola toward a nebula': 'idle',
    'shearing in half along its central truss': 'event',
    'being swarmed by small starships at every docking arm': 'event',
    'tumbling out of its rotation': 'event',
    'cracking open along a docking arm': 'event',
    'collapsing into a trailing field of wreckage': 'event',
    'spilling a white plume from a ruptured hull': 'event',
    'flaring its body wide in a threat display': 'event',
    'flexing a freshly moulted outer skin': 'activity',
    'signalling with waves of colour along its flank': 'activity',
    'shedding spores in a slow cloud': 'event',
    'spreading a hood of skin': 'activity',
    'extending a cluster of feelers': 'activity',
    'snapping at a passing spark': 'activity',
    'spreading a fan of spines': 'activity',
    'flattening itself against a rock': 'activity',
    'raising a crest of quills': 'activity',
    'fanning a set of gill frills': 'activity',
    'curling into a defensive coil': 'activity',
    'tracking something overhead': 'activity',
    'shaking flakes of hardened resin from its back': 'event',
    'tearing into a fallen hull': 'event',
    'spitting a stream of caustic bile': 'event',
    'clamping its jaws shut with a crack': 'event',
    'slamming its whole bulk down': 'event',
    'breaking out of a containment field with a single lunge': 'event',
    'shaking off a cloud of stinging motes': 'event',
    "feeding on a wreck's power core": 'activity',
    'stalking prey through the corridors': 'event',
    'watching from inside a ceiling vent': 'event',
    'brooding over a clutch of luminous cysts': 'activity',
    'grazing on radiant foliage': 'activity',
    'guarding a nest': 'activity',
    'swarming across a hull in a moving carpet': 'activity',
    'striking at a fleeing shuttlecraft': 'event',
    'spinning a resin nest between girders': 'activity',
    'drifting on thermals above a canyon': 'activity',
    'burrowing up through fractured rock': 'activity',
    'dragging a kill toward its burrow': 'event',
    'coiling its body into a tight spiral': 'event',
    'rearing up on its hind limbs': 'activity',
    'hauling a carcass into the shade': 'activity',
    'lashing out with a hooked limb': 'event',
    'lowering its jaws to drink': 'activity',
    'weaving through a stand of stalks': 'activity',
    'pressing its jaws to the ground': 'activity',
    'crawling up a vertical face': 'activity',
    'bursting through a sealed door': 'event',
    'snapping at the air in a sudden strike': 'event',
    'lunging with its jaws flung wide': 'event',
    'dragging a survivor into the dark': 'event',
    'making first contact with open hands': 'activity',
    'sealing a hull breach with a foam sprayer': 'event',
    'waving a straggler toward the airlock': 'activity',
    'running a diagnostic on an open panel': 'activity',
    'hauling a stretcher through a smoking corridor': 'event',
    'levelling a weapon at something off to one side': 'event',
    'projecting a holographic star map from one palm': 'activity',
    'climbing a hull on magnetic boots': 'activity',
    'taking cover behind a buckled bulkhead': 'event',
    'planting a survey marker in red dust': 'activity',
    'sealing a cracked visor with tape': 'activity',
    'arguing over a projected chart': 'activity',
    'leading a boarding party through a cut hatch': 'event',
    'waking from cryo with frost still on the suit': 'event',
    'signalling a descending lander with a flare': 'activity',
    'kneeling to read a bootprint': 'activity',
    'clamping a magnetic beacon to a deck plate': 'activity',
    'welding a seam with a torch': 'activity',
    'planting a beacon on a ridge': 'activity',
    'hauling a cargo pod up a ramp': 'activity',
    'keying a sequence into a console': 'activity',
    'scanning a wall with a handheld': 'activity',
    'strapping into a seat': 'activity',
    'pushing a cart of supplies': 'activity',
    'tightening a coupling with a wrench': 'activity',
    'crouching behind a cargo pod': 'activity',
    'chalking a mark on a wall': 'activity',
    'passing a tool to a colleague': 'activity',
    'hosing dust off a panel': 'activity',
    'tying a bandage around their own forearm': 'activity',
    'steadying a ladder for a colleague': 'activity',
    'reaching down to help someone up': 'activity',
    'cutting through a jammed airlock with a torch': 'event',
    'shouldering a buckling bulkhead back into place': 'event',
    'severing a snarl of cabling': 'event',
    'carrying a child through a smoke-filled corridor': 'event',
    'sealing a breach as the air thins': 'event',
    'running through a collapsing gantry': 'event',
    'diving clear of a falling beam': 'event',
    'fighting off a boarder at the airlock': 'event',
    'catching a falling colleague by the wrist': 'event',
    'holding a door against a rush of pressure': 'event',
    'extending a tool turret': 'activity',
    'hoisting a beam into place': 'activity',
    'spraying sealant on a seam': 'activity',
    'cutting a panel free': 'activity',
    'scanning a doorway': 'activity',
    'climbing over a low wall': 'activity',
    'prying open a hatch': 'activity',
    'raising a heavy rock drill': 'activity',
    'steadying a load with an outrigger': 'activity',
    'sweeping a sensor beam down a shaft': 'activity',
    'crouching to inspect wreckage': 'activity',
    'dodging a falling slab of rock': 'event',
    'grinding to a halt with a seized joint': 'event',
    'going down under a mass of smaller units': 'event',
    'welding a seam along a hull plate': 'activity',
    'striding through waist-deep drifts': 'activity',
    'levelling its shoulder cannon': 'event',
    'powering down into a maintenance cradle': 'activity',
    'sweeping a corridor with its optics': 'activity',
    'pulling a damaged unit to cover': 'event',
    'boring into rock with a heavy rock drill': 'activity',
    'trading shots across an open bay': 'event',
    'carrying an injured crewmember': 'activity',
    'planting sensor stakes in a grid': 'activity',
    'rising from a half-buried crouch': 'activity',
    'clearing debris from a blocked hatch': 'activity',
    'hunting through the rubble for movement': 'event',
    'lifting a cargo container overhead': 'activity',
    'drilling into a wall': 'activity',
    'crossing cracked ground': 'activity',
    'righting itself after a fall': 'activity',
    'tearing a hatch off its hinges': 'event',
    'falling from a gantry': 'event',
    'holding a collapsing wall up with its shoulders': 'event',
    'burying its fist in a bulkhead': 'event',
    'shedding a crust of dust as it moves': 'activity',
    'projecting a chart of unmapped space': 'activity',
    'splitting open along freshly-formed seams': 'event',
    'pulsing light through its veins': 'activity',
    'being lifted onto a recovery cradle': 'idle',
    'spilling light from a widening crack': 'event',
    'hanging unsupported above the ground': 'activity',
    'being circled by scanning drones': 'idle',
    'discharging arcs across its surface': 'event',
    'bending a nearby survey mast toward itself': 'event',
    'cracking under a cutting beam': 'event',
    'sinking into the dust it rests on': 'activity',
    'being guarded by a flight of sentry drones': 'event',
    'hovering just above a plinth': 'idle',
    'humming as a seam brightens': 'idle',
    'unfolding a panel of lattices': 'activity',
    'rotating slowly on its axis': 'idle',
    'drawing a spiral of dust into orbit': 'activity',
    'floating above a ruined floor': 'idle',
    'projecting a column of light': 'activity',
    'cracking open along a seam': 'activity',
    'humming with a low tone': 'idle',
    'hovering above a fallen plinth': 'idle',
    'shedding flakes of light': 'activity',
    'standing amid a circle of stones': 'idle',
    'unfolding a set of fins': 'activity',
    'spinning up a cloud of fragments': 'activity',
    'settling onto a stone plinth': 'idle',
    'rising slowly from the ground': 'idle',
    'tearing open along a line of light': 'event',
    'pulling a spiral of loose rubble toward its base': 'event',
    'lifting a spread of rubble off the ground': 'event',
    'going dark all at once': 'event',
    'bursting in a wave of light': 'event',
    'collapsing into a singularity': 'event',
    'drawing loose debris off the deck toward itself': 'event',
    'swallowing a survey drone whole': 'event',
    'cracking the ground beneath it': 'event',
    'pulling a descending lander out of the sky': 'event',
    'cresting a rise in a cloud of dust': 'activity',
    'grinding up a rocky slope': 'activity',
    'sliding sideways on loose gravel': 'activity',
    'parking beside a rock outcrop': 'idle',
    'lowering a ramp onto sand': 'activity',
    'raising a cloud of grit': 'activity',
    'crawling along a canyon floor': 'activity',
    'crossing a dry riverbed': 'activity',
    'nosing into a cave mouth': 'activity',
    'circling a landing site': 'activity',
    'idling with its lights on': 'idle',
    'rocking over a boulder': 'activity',
    'spraying mud from its tracks': 'activity',
    'braking hard at a cliff edge': 'activity',
    'following a set of wheel ruts': 'activity',
    'backing up to a cargo pod': 'activity',
    'extending a sampling boom': 'activity',
    'turning to face a dust storm': 'idle',
    'churning up a spray of grit': 'activity',
    'flipping onto its back on a hard turn': 'event',
    'throwing a track at speed': 'event',
    'bursting a hub against an obstacle': 'event',
    'losing a wheel at full throttle': 'event',
    'spinning out at full throttle': 'event',
    'snapping an axle on a hard landing': 'event',
    'shearing a tread on a jagged edge': 'event',
    'towing a string of cargo pods across a salt flat': 'activity',
    'pulling up beside a supply dome': 'activity',
    'fording a shallow methane channel': 'activity',
    'unloading cargo pods onto a landing pad': 'activity',
    'spinning a track in loose scree': 'activity',
    'racing a storm front toward shelter': 'activity',
    'charging across open ground with its ramp raised': 'event',
    'nosing through a cloud of stirred-up silt': 'activity',
    'edging down a crater wall at a steep angle': 'activity',
    'drilling a core sample from the bedrock': 'activity',
    'hovering low over broken ground': 'activity',
    'waiting with its ramp down and cabin open': 'idle',
    'climbing a dune ridge at full throttle': 'activity',
    'kicking up a long dust plume': 'activity',
    'taking hits from a ridge line': 'event',
    'churning through a muddy flat': 'activity',
    'sliding down a scree slope': 'activity',
    'nosing over a sharp crest': 'activity',
    'reversing out of a gully': 'activity',
    'dropping toward a landing pad on its belly thrusters': 'activity',
    'cutting through a dust storm at low altitude': 'activity',
    'plunging through a sheet of thin ice': 'event',
    'rolling down a slope out of control': 'event',
    'ramming a barricade at full speed': 'event',
    'settling deeper into the sand': 'activity',
    'breaking up as it falls': 'event',
    'sheltering a nest of hull-borers': 'activity',
    'grinding against the rock it landed on': 'activity',
    'being cut open by salvage drones': 'event',
    'disappearing under a creeping fungal mat': 'idle',
    'being surveyed by a drifting inspection drone': 'idle',
    'leaking a slick across the water': 'activity',
    'collapsing under its own weight': 'event',
    'spilling its contents across the ground': 'event',
    'spilling a fan of debris down a slope': 'activity',
    'catching the light along a torn edge': 'idle',
    'slumping as a spar gives way': 'event',
    'breaking apart in a slow avalanche': 'event',
    'shedding a slab of plating as it settles': 'event',
    'spilling a wave of debris across the ground': 'event',
    'collapsing into the pit it made': 'event',
    'tearing open along a rusted seam': 'event',
    'pinning a salvage drone beneath a buckled plate': 'event',
    "giving way under a salvage drone's cutting beam": "event",
    'burying a salvage crawler in a slide': 'event',
    "buckling as its main girder gives way": "event",
    "shedding a cascade of plate fragments": "event",
    "tearing open along a frost-welded seam": "event",
    "crumbling into a field of drifting debris": "event",
}

#: ``{tier: relative draw weight}``. Multiplied into the pool's own weights.
TIER_WEIGHTS: dict[str, float] = {"event": 3.0, "activity": 1.0, "idle": 0.25}


# ``relation`` is the other half of the action layer: what one slot is doing
# *about* another. Exactly the nine the plan names, and deliberately no more --
# six relation widgets over four slots is already the busiest part of the node,
# and a longer list would push the user toward reading a menu instead of a
# scene.
#
# These are the one pool that is **not** a noun phrase: each is a preposition-
# shaped fragment the renderer sets between two entity references ("the scout
# ship, docked at the ring station"). They are not kind-scoped -- "orbiting"
# means the same thing whichever pair it joins -- and the renderer only voices
# one when *both* endpoints exist.

RELATION_POOL: tuple[str, ...] = (
    "attacking",
    "pursuing",
    "fleeing from",
    "orbiting",
    "docked at",
    "facing",
    "observing",
    "ignoring",
    "escorting",
    "creeping toward",
    "looming over",
    "towering over",
    "drifting beside",
    "dwarfing",
    "half-hidden behind",
    "lying in the path of",
    "flanking",
    "trailing",
    "shadowing",
    "closing on",
    "hailing",
    "signalling",
    "towing",
    "holding station near",
)


RELATION_POSITION_POOL: tuple[str, ...] = (
    "from behind",
    "from above",
    "from below",
    "in the background",
    "in the foreground",
    "at a distance",
    "directly ahead",
    "alongside",
    "to one side",
    "dead ahead",
    "directly above",
    "directly below",
    "in the middle distance",
    "close alongside",
)


# ---------------------------------------------------------------------------
# Per-kind widget labels
# ---------------------------------------------------------------------------
#
# ``{field: {kind: label}}``. The field *names* stay generic so the schema is
# genre-portable; these make them readable, and the frontend (Todo 19) rewrites
# a widget's label when its slot's ``kind`` changes. It rewrites labels and
# values only -- **never widget order**, which is positional in a saved
# workflow. A field with no entry here keeps its generic ``FieldSpec.label``.
#
# Each field's labels are authored next to that field's pool, in the todo that
# owns it, so the two cannot drift apart.

LABELS: dict[str, dict[str, str]] = {
    "subkind": {
        "starship": "Ship class",
        "celestial body": "Body type",
        "space station": "Structure type",
        "alien creature": "Creature type",
        "spacefarer": "Role",
        "robot or mech": "Unit type",
        "alien artifact": "Object type",
        "surface vehicle": "Vehicle type",
        "wreck": "Wreck type",
    },
    "scale": {
        "alien creature": "Size",
        "spacefarer": "Size",
        "robot or mech": "Size",
        "celestial body": "Size class",
    },
    "form": {
        "starship": "Hull silhouette",
        "celestial body": "Body shape",
        "space station": "Structure silhouette",
        "alien creature": "Body plan",
        "spacefarer": "Build",
        "robot or mech": "Chassis",
        "alien artifact": "Object shape",
        "surface vehicle": "Chassis silhouette",
        "wreck": "Wreck shape",
    },
    "material": {
        "starship": "Hull material",
        "celestial body": "Composition",
        "space station": "Structure material",
        "alien creature": "Integument",
        "spacefarer": "Suit material",
        "robot or mech": "Casing",
        "alien artifact": "Substance",
        "surface vehicle": "Body material",
        "wreck": "Hull material",
    },
    "primary_color": {
        "starship": "Hull colour",
        "celestial body": "Surface colour",
        "space station": "Hull colour",
        "alien creature": "Skin colour",
        "spacefarer": "Suit colour",
        "robot or mech": "Casing colour",
        "alien artifact": "Body colour",
        "surface vehicle": "Body colour",
        "wreck": "Hull colour",
    },
    "accent_color": {
        "starship": "Trim colour",
        "celestial body": "Banding colour",
        "space station": "Trim colour",
        "alien creature": "Accent colour",
        "spacefarer": "Trim colour",
        "robot or mech": "Trim colour",
        "alien artifact": "Inlay colour",
        "surface vehicle": "Trim colour",
        "wreck": "Trim colour",
    },
    "markings": {
        "starship": "Livery",
        "celestial body": "Surface patterning",
        "space station": "Livery",
        "alien creature": "Patterning",
        "spacefarer": "Insignia",
        "robot or mech": "Livery",
        "alien artifact": "Relief patterning",
        "surface vehicle": "Livery",
        "wreck": "Remaining livery",
    },
    "appendages": {
        "starship": "Hull appendages",
        "celestial body": "Attendant features",
        "space station": "Structure appendages",
        "alien creature": "Limbs",
        "spacefarer": "Worn appendages",
        "robot or mech": "Manipulators",
        "alien artifact": "Projections",
        "surface vehicle": "Attachments",
        "wreck": "Remaining appendages",
    },
    "appendage_count": {
        "starship": "Appendage count",
        "alien creature": "Limb count",
        "robot or mech": "Manipulator count",
    },
    "emitters": {
        "starship": "Engines",
        "celestial body": "Vents and jets",
        "space station": "Emitters",
        "alien creature": "Bioluminescence",
        "spacefarer": "Suit emitters",
        "robot or mech": "Emitters",
        "alien artifact": "Emissive features",
        "surface vehicle": "Drive emitters",
        "wreck": "Surviving emitters",
    },
    "emitter_count": {
        "starship": "Engine count",
        "celestial body": "Vent count",
        "alien creature": "Organ count",
    },
    "emitter_color": {
        "starship": "Engine glow",
        "celestial body": "Emission colour",
        "alien creature": "Glow colour",
        "robot or mech": "Emitter glow",
        "alien artifact": "Emission colour",
        "surface vehicle": "Drive glow",
    },
    "armament": {
        "starship": "Weapons",
        "space station": "Weapons",
        "alien creature": "Natural weapons",
        "spacefarer": "Carried weapons",
        "robot or mech": "Weapons",
        "surface vehicle": "Weapons",
        "wreck": "Wrecked weapons",
    },
    "armament_count": {
        "starship": "Weapon count",
        "alien creature": "Natural weapon count",
    },
    "sensors": {
        "starship": "Sensor arrays",
        "space station": "Sensor arrays",
        "alien creature": "Eyes",
        "spacefarer": "Optics",
        "robot or mech": "Optics",
        "alien artifact": "Sensory features",
        "surface vehicle": "Sensors",
        "wreck": "Wrecked sensors",
    },
    "sensor_count": {
        "starship": "Array count",
        "space station": "Array count",
        "alien creature": "Eye count",
        "robot or mech": "Optic count",
    },
    "aperture": {
        "starship": "Bay or viewport",
        "celestial body": "Opening",
        "space station": "Bay or viewport",
        "alien creature": "Mouth and dentition",
        "spacefarer": "Face opening",
        "robot or mech": "Hatch or grille",
        "alien artifact": "Opening",
        "surface vehicle": "Canopy or hatch",
        "wreck": "Breach",
    },
    "extras": {
        "starship": "Other components",
        "celestial body": "Other features",
        "space station": "Other components",
        "alien creature": "Other features",
        "spacefarer": "Carried gear",
        "robot or mech": "Other components",
        "alien artifact": "Other features",
        "surface vehicle": "Other components",
        "wreck": "Other remains",
    },
    "surface_detail": {
        "starship": "Hull detail",
        "celestial body": "Terrain detail",
        "space station": "Hull detail",
        "alien creature": "Surface detail",
        "spacefarer": "Suit detail",
        "robot or mech": "Casing detail",
        "alien artifact": "Surface detail",
        "surface vehicle": "Body detail",
        "wreck": "Hull detail",
    },
    "condition": {
        "alien creature": "Condition",
        "spacefarer": "Condition",
    },
    # ``situation`` and ``relation`` carry no per-kind label. "Situation" reads
    # correctly for a ship, a moon and a person alike, and a relation belongs to
    # a *pair* of slots -- there is no single kind to scope its label by, which
    # is also why the relation widgets sit in their own group.
}


POOLS: dict[str, dict[str, tuple[str, ...]]] = {
    ENVIRONMENT_FIELD: {POOL_DEFAULT_KEY: ENVIRONMENT_POOL},
    CONTEXT_FIELD: CONTEXT_POOLS,
    "kind": KIND_POOLS,
    "subkind": SUBKIND_POOLS,
    "form": FORM_POOLS,
    "material": MATERIAL_POOLS,
    "primary_color": PRIMARY_COLOR_POOLS,
    "accent_color": {POOL_DEFAULT_KEY: ACCENT_COLOR_POOL},
    "emitter_color": EMITTER_COLOR_POOLS,
    "markings": MARKINGS_POOLS,
    "appendages": APPENDAGE_POOLS,
    "emitters": EMITTER_POOLS,
    "armament": ARMAMENT_POOLS,
    "sensors": SENSOR_POOLS,
    "aperture": APERTURE_POOLS,
    "extras": EXTRAS_POOLS,
    "condition": CONDITION_POOLS,
    "scale": SCALE_POOLS,
    "surface_detail": SURFACE_DETAIL_POOLS,
    # The count fields draw from allotments of ``COUNT_POOL``, not from all of
    # it: see the note there on "banks of targeting monocles".
    "appendage_count": APPENDAGE_COUNT_POOLS,
    "emitter_count": EMITTER_COUNT_POOLS,
    "armament_count": ARMAMENT_COUNT_POOLS,
    "sensor_count": SENSOR_COUNT_POOLS,
    # The action layer. ``situation`` keeps a ``_default`` on purpose: it is the
    # pool a wired foreign-genre entity resolves through.
    SITUATION_FIELD: SITUATION_POOLS,
    RELATION_FIELD: {POOL_DEFAULT_KEY: RELATION_POOL},
    RELATION_POSITION_FIELD: {POOL_DEFAULT_KEY: RELATION_POSITION_POOL},
}

# ---------------------------------------------------------------------------
# Todo 12 -- constraint rules
# ---------------------------------------------------------------------------
#
# A rule removes *values* from a field's pool when another field holds a given
# value. It never adds anything and it never writes prose, so a constraint can
# only ever make a scene quieter, never make it say what is missing.
#
# ``reason`` is the exception to the never-negate rule, and the only one in the
# pack: it is the text of the warning a user sees when a value they locked wins
# over a rule, it never reaches the prompt, and a warning forbidden from saying
# "a star is not made of rock" is a worse warning. Pool values are where the
# rule bites.
#
# Addresses are ``environment`` or ``entity{N}.{field}``, with ``entity*.`` for
# "any slot". A wildcarded rule runs once per slot and a wildcard on the other
# side binds to the *same* slot -- see ``genre.bind_address``, which is the one
# place that semantics is defined.
#
# **Rules that cannot fire are deleted, not kept.** Two from the plan's starter
# set were dropped after checking them against the authored data, and both were
# dropped for the same reason -- the kind-scoped pools had already done the job,
# and a scope is stronger than a rule because it cannot be out-iterated:
#
# * *"creature or being excludes metallic hull materials"* -- the creature
#   ``material`` pool is chitin, hide, flesh and bone. There is no metal in it to
#   exclude, so the rule would have been a comment pretending to be code.
# * *"a celestial body requires an exterior environment"*, written as a
#   ``require`` rule -- ``requires_value`` is single-valued and "exterior" is
#   fifty-odd values. It is expressed below as one exclusion of the interior
#   band instead, which is the same statement and actually fires.
#
# That second substitution leaves this pack with **no ``require`` rule at all**.
# The rule type stays in the contract (a genre with a single-valued requirement
# will want it) and Todo 26's fixture pack is where it should be exercised.

#: Interior environments and the two scales that cannot be inside one. The list
#: is read from the viewpoint ladder rather than restated, so an interior added
#: to Todo 4's pool is covered by these rules the moment it is authored.
_INTERIOR_ENVIRONMENTS: tuple[str, ...] = ENVIRONMENT_BANDS["interior"]
_SCALES_THAT_DO_NOT_FIT_INDOORS: tuple[str, ...] = ("colossal", "planetary")

#: A generated ``reason`` quotes the triggering value rather than composing an
#: article in front of it: the a/an helper is Todo 13's, and "a energy being" in
#: a warning is exactly the kind of small wrongness that makes a user distrust
#: the rest of the message.
#:
#: Kinds whose armament pool exists only through the ``_default`` fall-through,
#: and which should not have one. Session 2 kept that fall-through deliberately
#: so these rules have real values to remove: a rule with nothing to exclude is
#: a rule that never fires.
_KINDS_WITH_NO_ARMAMENT: tuple[str, ...] = ("celestial body", "alien artifact")

#: Bodies with no solid surface. A star, a nebula and an energy being all draw
#: badly with "cracked mineral crust" bolted on, and the incoherence survives
#: into the image far more often than a subtler one would.
_DIFFUSE_CREATURE_SUBKINDS: tuple[str, ...] = SUBKIND_GROUPS["diffuse being"]
#: The diffuse celestial subkinds, written as their groups so the membership
#: has one source of truth rather than two tables.
_DIFFUSE_CELESTIAL_SUBKINDS: tuple[str, ...] = (
    SUBKIND_GROUPS["star body"] + SUBKIND_GROUPS["singularity"] + SUBKIND_GROUPS["diffuse cloud"]
    + SUBKIND_GROUPS["binary system"]
)


def _exclude(
    field: str, value: str, excludes_field: str, excludes_values: tuple[str, ...], reason: str
) -> ConstraintRule:
    return ConstraintRule(
        type=RULE_EXCLUDE,
        field=field,
        value=value,
        excludes_field=excludes_field,
        excludes_values=excludes_values,
        reason=reason,
    )


#: Scale coherence -- the highest-value rules in the set, and the ones the
#: previous plan missed entirely. Scale reads by *contrast*, so it is only
#: meaningful next to something that frames it; a colossal subject in a corridor
#: has nothing to be colossal against and the image loses both readings at once.
_SCALE_RULES: tuple[ConstraintRule, ...] = tuple(
    _exclude(
        ENVIRONMENT_FIELD, environment,
        "entity*.scale", _SCALES_THAT_DO_NOT_FIT_INDOORS,
        "an interior cannot contain something bigger than the structure around it",
    )
    for environment in _INTERIOR_ENVIRONMENTS
)

#: There is no ``_ARMAMENT_RULES`` any more, for the same reason there is no
#: ``_DIFFUSE_RULES``: the ``world`` and ``object`` archetypes omit ``armament``
#: outright, and the budget's orphan pass takes the count with it. The rules
#: also had to name the count pool explicitly, which made them a second place
#: that had to agree with what ``armament_count`` can draw -- and the first
#: time that pool was narrowed, they stopped matching. One declaration.


#: There is no ``_DIFFUSE_RULES`` any more, and its absence is the point.
#:
#: A star, a black hole, a nebula, an energy being and a gaseous drifter used to
#: be handled by a block of exclusion rules that stripped solid materials and
#: surface details from their pools. It half-worked: it covered two of the eight
#: fields that assume a surface, so a black hole still drew an impact crater
#: basin and an ice cap, and the two materials that survived the cull -- "molten
#: rock" and "hydrogen and helium cloud" -- were then fed through "clad in".
#:
#: The same subkinds are now the ``phenomenon`` archetype, which omits every
#: field that presumes a surface rather than pruning two of their pools. One
#: declaration, complete coverage, and the grammar moves with it. The subkind
#: tuples above are still the single source of the membership -- see
#: ``ARCHETYPE_OF_SUBKIND``.

#: What a kind of thing can do, read by ``relation_roles``. A capability is a
#: role or an ability, not a trait: it is what makes an endpoint fit for a
#: relation, and the engine only ever tests set membership.
KIND_CAPABILITIES: dict[str, frozenset[str]] = {
    "starship": frozenset({"agent", "mobile", "vessel"}),
    "surface vehicle": frozenset({"agent", "mobile"}),
    "robot or mech": frozenset({"agent", "mobile"}),
    "alien creature": frozenset({"agent", "mobile"}),
    "spacefarer": frozenset({"agent", "mobile"}),
    "space station": frozenset({"agent", "dockable", "massive"}),
    "celestial body": frozenset({"massive"}),
    "alien artifact": frozenset(),
    "wreck": frozenset({"massive"}),
}

#: ``{relation value: (first endpoint needs, second endpoint needs)}``. The
#: expander keeps only the kinds whose capabilities cover a non-empty need set,
#: so "orbiting" needs a first endpoint that is mobile and says nothing about
#: the second. The two position exclusions below are not role rules -- they are
#: about a bearing that reads as absolute, not about what an endpoint can do.
RELATION_ROLES: dict[str, tuple[frozenset[str], frozenset[str]]] = {
    "attacking": (frozenset({"agent"}), frozenset()),
    "observing": (frozenset({"agent"}), frozenset()),
    "facing": (frozenset({"agent"}), frozenset()),
    "pursuing": (frozenset({"mobile"}), frozenset({"mobile"})),
    "escorting": (frozenset({"mobile"}), frozenset({"mobile"})),
    "fleeing from": (frozenset({"mobile"}), frozenset({"agent"})),
    "creeping toward": (frozenset({"mobile"}), frozenset()),
    "ignoring": (frozenset({"agent"}), frozenset({"agent"})),
    "orbiting": (frozenset({"mobile"}), frozenset({"massive"})),
    "docked at": (frozenset({"vessel"}), frozenset({"dockable"})),
    "looming over": (frozenset({"massive"}), frozenset()),
    "towering over": (frozenset({"massive"}), frozenset()),
    "drifting beside": (frozenset(), frozenset()),
    "dwarfing": (frozenset({"massive"}), frozenset()),
    "half-hidden behind": (frozenset(), frozenset({"massive"})),
    "lying in the path of": (frozenset(), frozenset({"mobile"})),
    "flanking": (frozenset({"mobile"}), frozenset({"mobile"})),
    "trailing": (frozenset({"mobile"}), frozenset({"mobile"})),
    "shadowing": (frozenset({"mobile"}), frozenset({"mobile"})),
    "closing on": (frozenset({"mobile"}), frozenset({"mobile"})),
    "hailing": (frozenset({"agent"}), frozenset({"agent"})),
    "signalling": (frozenset({"agent"}), frozenset({"agent"})),
    "towing": (frozenset({"vessel"}), frozenset({"mobile"})),
    "holding station near": (frozenset({"mobile"}), frozenset()),
}

_RELATION_RULES: tuple[ConstraintRule, ...] = (
    ConstraintRule(
        type=RULE_EXCLUDE,
        field=RELATION_ANY,
        value="orbiting",
        excludes_field=RELATION_ANY_POSITION,
        excludes_values=("from behind",),
        reason="an orbiting body has no behind",
    ),
    ConstraintRule(
        type=RULE_EXCLUDE,
        field=RELATION_ANY,
        value="docked at",
        excludes_field=RELATION_ANY_POSITION,
        excludes_values=("from behind",),
        reason="a docked ship faces its dock",
    ),
)

# ---------------------------------------------------------------------------
# Environment bands -- tying the subject and the action to the place
# ---------------------------------------------------------------------------
#
# ``ENVIRONMENT_BANDS`` above has existed since the environment pool was
# authored and, until now, nothing read it. Every scene drew its environment,
# its entities and their situations independently, and the results said so:
#
#   "...set in a domed colony concourse. A massive corroded submersible ...
#    It is taking hits from a ridge line."
#   "...set in an upper cloud deck of a gas giant. A collapsed station spar..."
#   "...set in a globular star cluster ... It is burrowing up through
#    fractured rock."
#
# Each of those is three independently legal draws that cannot all be true at
# once. Nothing in the pack was wrong; nothing connected them either.
#
# **Only exceptions are authored.** A situation that is plausible anywhere --
# most of them -- appears in no list here. That is what keeps this maintainable:
# adding a situation costs nothing unless it needs ground under it or vacuum
# around it, and the validator reports a name that stops matching a real value.
#
# Written as a handful of multi-value rules rather than one rule per
# environment. The same idea as twenty rules is twenty chances to edit
# nineteen of them.

#: The place table: what each place *affords*. A raw environment value's entry
#: REPLACES its band's; a value with no entry takes its band's. The engine
#: compares these sets against each value's needs and never learns what any of
#: the words mean.
#:
#: ``ground`` natural terrain underfoot; ``floor`` anything to stand or nest
#: on, ground or deck; ``shoreline`` water present with air above it (a shore, a
#: lake, a marsh); ``submerged`` the camera and subject underwater, which grants
#: no sky, no sunlight and no room for something vast; ``sky`` an atmosphere to
#: fly in; ``open-space`` vacuum to drift and orbit; ``deep-space`` stellar
#: surroundings, where a star or a black hole is the subject; ``structure`` built
#: surroundings; ``dock`` somewhere to berth; ``vast`` room for something much
#: bigger than a building; ``vista`` a clear view with no field of rubble to set a
#: world on; ``gravity`` anything to stand on, fly in or sink
#: through; ``air`` an atmosphere a bare face or an open garment can meet, which is a
#: render claim and not chemistry, and which vacuum and open water are the two places
#: that cannot grant; ``cloud-deck`` a cloud layer with open sky above it, which a
#: surface place has not; ``sunlight``; ``cold``; ``dust``; ``life``.
PLACE_AFFORDANCES: dict[str, frozenset[str]] = {
    # --- bands ---
    "deep space": frozenset({"open-space", "deep-space", "vast", "vista"}),
    "orbit": frozenset({"open-space", "vast", "sunlight"}),
    "cloud layer": frozenset({"sky", "vast", "sunlight"}),
    "planetary surface": frozenset({"ground", "floor", "sky", "vast", "sunlight"}),
    "interior": frozenset({"floor", "structure"}),
    # --- deep space, place by place ---
    "binary star system": frozenset({"open-space", "deep-space", "vast", "sunlight", "vista"}),
    "globular star cluster": frozenset({"open-space", "deep-space", "vast", "sunlight", "vista"}),
    "galactic core star swarm": frozenset({"open-space", "deep-space", "vast", "sunlight", "vista"}),
    "interstellar dust lane": frozenset({"open-space", "deep-space", "vast", "dust", "vista"}),
    "absorption dust nebula": frozenset({"open-space", "deep-space", "vast", "dust", "vista"}),
    "asteroid field": frozenset({"open-space", "deep-space", "vast", "dust"}),
    "derelict fleet drift": frozenset({"open-space", "deep-space", "vast", "dust"}),
    "cometary debris stream": frozenset({"open-space", "deep-space", "vast", "cold", "dust"}),
    "deep interstellar void": frozenset({"open-space", "deep-space", "vast", "cold", "vista"}),
    # --- orbit ---
    "orbital shipyard scaffold": frozenset({"open-space", "vast", "sunlight", "dock", "structure"}),
    "lagrange point station cluster": frozenset({"open-space", "vast", "sunlight", "dock", "structure"}),
    "ring station docking approach": frozenset({"open-space", "vast", "sunlight", "dock", "structure"}),
    "orbital elevator tether": frozenset({"open-space", "vast", "sunlight", "dock", "structure"}),
    "polar orbit above an ice world": frozenset({"open-space", "vast", "sunlight", "cold"}),
    "orbital debris belt": frozenset({"open-space", "vast", "sunlight", "dust"}),
    # --- cloud layer ---
    "floating cloud city platform": frozenset({"sky", "vast", "sunlight", "floor", "structure", "dock"}),
    "ammonia cloud layer": frozenset({"sky", "vast", "sunlight", "cold"}),
    # --- planetary surface ---
    "deep ocean trench of a water world": frozenset({"submerged", "floor", "cold"}),
    "subglacial ocean of an ice moon": frozenset({"submerged", "floor", "cold"}),
    "hydrothermal vent field of a water world": frozenset({"submerged", "floor"}),
    "rocky extraterrestrial shore": frozenset({"ground", "floor", "sky", "vast", "sunlight", "shoreline"}),
    "toxic seep basin": frozenset({"ground", "floor", "sky", "vast", "sunlight", "shoreline", "life"}),
    "glacier plain of an ice world": frozenset({"ground", "floor", "sky", "vast", "sunlight", "cold"}),
    "frozen methane flats": frozenset({"ground", "floor", "sky", "vast", "sunlight", "cold"}),
    "subsurface ice cavern": frozenset({"ground", "floor", "cold"}),
    "hollowed geode cavern": frozenset({"ground", "floor"}),
    "red dust plain of a dead world": frozenset({"ground", "floor", "sky", "vast", "sunlight", "dust"}),
    "orange sand dune sea": frozenset({"ground", "floor", "sky", "vast", "sunlight", "dust"}),
    "basalt mesa badlands": frozenset({"ground", "floor", "sky", "vast", "sunlight", "dust"}),
    "cracked salt flat": frozenset({"ground", "floor", "sky", "vast", "sunlight", "dust"}),
    "asteroid mining pit": frozenset({"ground", "floor", "sky", "vast", "sunlight", "dust"}),
    "barren alien wilderness": frozenset({"ground", "floor", "sky", "vast", "sunlight", "dust"}),
    "terraforming processor field": frozenset({"ground", "floor", "sky", "vast", "sunlight", "dust"}),
    "bioluminescent fungal floor": frozenset({"ground", "floor", "sky", "vast", "sunlight", "life"}),
    "alien fungal growth": frozenset({"ground", "floor", "sky", "vast", "sunlight", "life"}),
    "overgrown ruin field of an abandoned colony": frozenset({"ground", "floor", "sky", "vast", "sunlight", "life"}),
    "crystalline flora spires": frozenset({"ground", "floor", "sky", "vast", "sunlight", "life"}),
    "domed colony concourse": frozenset({"floor", "structure", "sunlight"}),
    # --- interior ---
    "spacecraft hangar deck": frozenset({"floor", "structure", "dock"}),
    "station docking ring interior": frozenset({"floor", "structure", "dock"}),
    "hydroponics bay": frozenset({"floor", "structure", "life"}),
    "alien hive resin chamber": frozenset({"floor", "structure", "life"}),
    "cryogenic stasis bay": frozenset({"floor", "structure", "cold"}),
    "cargo airlock": frozenset({"floor", "structure", "dock"}),
    # --- the widened places, where they differ from their band ---
    "frozen comet belt": frozenset({"open-space", "deep-space", "vast", "cold"}),
    "derelict shipyard orbit": frozenset({"open-space", "vast", "sunlight", "dock", "structure"}),
    "station approach corridor": frozenset({"open-space", "vast", "sunlight", "dock", "structure"}),
    "methane sea shore": frozenset({"ground", "floor", "sky", "vast", "sunlight", "shoreline", "cold"}),
    "crater basin": frozenset({"ground", "floor", "sky", "vast", "sunlight", "shoreline"}),
    "black sand tidal flat": frozenset({"ground", "floor", "sky", "vast", "sunlight", "shoreline"}),
    "spore basin": frozenset({"ground", "floor", "sky", "vast", "sunlight", "shoreline", "life"}),
    "frozen sea ice": frozenset({"ground", "floor", "sky", "vast", "sunlight", "cold"}),
    "scattered asteroid cluster": frozenset({"open-space", "deep-space", "vast", "dust"}),
}

#: Anything to stand on, fly in or sink through has gravity; open space does not.
_GRAVITY_SOURCES = frozenset({"ground", "floor", "sky", "shoreline", "submerged"})
#: A bare face or an open garment can meet this place; a render claim, not chemistry.
_AIR_EXCLUDED = frozenset({"open-space", "submerged"})
#: ``aloft``: no surface under the camera -- open space, or above the cloud tops.
#: What a fleet manoeuvre needs; a planetary surface affords ``sky`` but is not aloft.
#: Open water at a shore or all around: what a body that only swims needs, since
#: needs are all-of and a swimmer is at home in either.
_WATER_SOURCES = frozenset({"shoreline", "submerged"})
#: Above the cloud tops; a surface has sky but no cloud deck below it.
_CLOUD_DECK_PLACES = frozenset({
    "cloud layer", "floating cloud city platform", "ammonia cloud layer",
})
PLACE_AFFORDANCES = {
    place: (
        affordances
        | ({"gravity"} if affordances & _GRAVITY_SOURCES else set())
        | ({"air"} if not affordances & _AIR_EXCLUDED else set())
        | ({"cloud-deck"} if place in _CLOUD_DECK_PLACES else set())
        | ({"water"} if affordances & _WATER_SOURCES else set())
        | ({"aloft"} if affordances & {"open-space"} or place in _CLOUD_DECK_PLACES else set())
    )
    for place, affordances in PLACE_AFFORDANCES.items()
}

#: Actions that need something underneath them. A nest is built on a surface
#: or a deck; in open space there is nothing under it to guard.
_FLOOR_BOUND: tuple[str, ...] = (
    "guarding a nest",
    "brooding over a clutch of luminous cysts",
    "lifting a cargo container overhead",
    "carrying an injured crewmember",
    "pulling a damaged unit to cover",
)


#: Actions that need something solid underfoot.
_SURFACE_BOUND: tuple[str, ...] = (
    # spacefarer
    "planting a survey marker in red dust",
    "signalling a descending lander with a flare",
    # robot or mech
    "boring into rock with a heavy rock drill",
    "striding through waist-deep drifts",
    "planting sensor stakes in a grid",
    "rising from a half-buried crouch",
    # alien creature
    "burrowing up through fractured rock",
    "dragging a kill toward its burrow",
    "grazing on radiant foliage",
    # wreck
    "settling deeper into the sand",
    "grinding against the rock it landed on",
    "disappearing under a creeping fungal mat",
    # alien artifact
    "sinking into the dust it rests on",
    # surface vehicle -- kept even though the kind is already excluded off the
    # surface, because a wired foreign entity can occupy a slot this pack never
    # gave a kind to.
    "climbing a dune ridge at full throttle",
    "kicking up a long dust plume",
    "taking hits from a ridge line",
    "fording a shallow methane channel",
    "spinning a track in loose scree",
    "racing a storm front toward shelter",
    "edging down a crater wall at a steep angle",
    "hovering low over broken ground",
)

#: Actions that need liquid to wade, float or sink in.
_WATER_BOUND: tuple[str, ...] = (
    "leaking a slick across the water",
)

#: Actions that need open air *and* ground under them.
_SKY_BOUND: tuple[str, ...] = (
    "drifting on thermals above a canyon",
)

#: Actions that need open space around them. Indoors and inside a gas giant
#: there is neither the room nor the vacuum.
_OPEN_SPACE_BOUND: tuple[str, ...] = (
    "drifting slowly through the void",
    "emerging from a nebula",
    "fleeing through an asteroid field",
    "breaking orbit on a long burn",
    "trailing an ion tail across the void",
    "trailing a captured asteroid in a long arc",
    "trailing an infalling comet across its face",
    "drawing debris into a slow orbit around itself",
    "drifting through a debris field",
    "shedding plates into a slow debris trail",
    "hanging at a steep angle against the stars",
    "deploying survey drones in a spreading fan",
)

#: Actions that only happen inside something. Voiced anywhere else they read as
#: a scene the viewer cannot see.
_INDOOR_BOUND: tuple[str, ...] = (
    "hauling a stretcher through a smoking corridor",
    "taking cover behind a buckled bulkhead",
    "stalking prey through the corridors",
    "watching from inside a ceiling vent",
    "sweeping a corridor with its optics",
    "spinning a resin nest between girders",
    "clearing debris from a blocked hatch",
    "powering down into a maintenance cradle",
    "waving a straggler toward the airlock",
    "leading a boarding party through a cut hatch",
)

#: Actions that need a dock to happen at. A ship unloading cargo onto a docking
#: arm on a dune sea is the same class of mismatch as one settling into sand in
#: orbit -- the action names a structure the setting does not have.
_DOCK_BOUND: tuple[str, ...] = (
    "unloading cargo onto a docking arm",
    "repelling a boarding assault at the main lock",
    "shuttering its docks against an incoming barrage",
    "taking on fuel from a refuelling starship's boom",
)


#: ``{field: {value: needs}}`` -- what each value requires of the place. The
#: engine excludes a value from every environment whose affordances lack ANY
#: of its needs. Built from the classes above so the membership has one source;
#: a new value declares its own need here, and the affordance lint fails the
#: one that forgets.
#: one that forgets.
_CONTEXT_NEEDS: dict[str, frozenset[str]] = {
    **{value: frozenset({"open-space"}) for value in CONTEXT_POOLS["deep space"]},
    **{value: frozenset({"open-space"}) for value in CONTEXT_POOLS["orbit"]},
    **{value: frozenset({"sky"}) for value in CONTEXT_POOLS["cloud layer"]},
    **{value: frozenset({"ground"}) for value in CONTEXT_POOLS["planetary surface"]},
    **{value: frozenset({"floor"}) for value in CONTEXT_POOLS["interior"]},    **{value: frozenset({"ground"}) for value in CONTEXT_POOLS["subsurface ice cavern"]},
    **{value: frozenset({"ground"}) for value in CONTEXT_POOLS["hollowed geode cavern"]},
    **{value: frozenset({"submerged"}) for value in CONTEXT_POOLS["deep ocean trench of a water world"]},
    **{value: frozenset({"submerged"}) for value in CONTEXT_POOLS["subglacial ocean of an ice moon"]},
    **{value: frozenset({"submerged"})
       for value in CONTEXT_POOLS["hydrothermal vent field of a water world"]},
    **{value: frozenset({"floor", "structure"}) for value in CONTEXT_POOLS["domed colony concourse"]},
}
VALUE_NEEDS: dict[str, dict[str, frozenset[str]]] = {
    CONTEXT_FIELD: _CONTEXT_NEEDS,
    "situation": {
        **{value: frozenset({"ground"}) for value in _SURFACE_BOUND},
        **{value: frozenset({"shoreline"}) for value in _WATER_BOUND},
        **{value: frozenset({"sky", "ground"}) for value in _SKY_BOUND},
        **{value: frozenset({"open-space"}) for value in _OPEN_SPACE_BOUND},
        **{value: frozenset({"structure"}) for value in _INDOOR_BOUND},
        **{value: frozenset({"dock"}) for value in _DOCK_BOUND},
        **{value: frozenset({"floor"}) for value in _FLOOR_BOUND},
    },
    # What a kind of subkind needs of the place. A submersible needs water, a
    # glider needs sky, a walker needs a floor, a star needs stellar
    # surroundings.
    "subkind": {
        "submersible": frozenset({"submerged"}),
        "sunken submersible": frozenset({"submerged"}),
        "aquatic swimmer": frozenset({"submerged"}),
        "high-altitude glider": frozenset({"sky"}),
        # Its twin in the "flying" group, and it was missing this entry: with no
        # need of its own a glider was feasible at the bottom of an ocean trench,
        # which is also why the event floor was being asked about it there.
        "survey glider": frozenset({"sky"}),
        "avian analogue": frozenset({"sky"}),
        "rover": frozenset({"floor"}),
        "crawler": frozenset({"floor"}),
        "sand crawler": frozenset({"floor"}),
        "tracked hauler": frozenset({"floor"}),
        "ground transport": frozenset({"floor"}),
        "ice cutter": frozenset({"floor", "cold"}),
        "walker": frozenset({"floor"}),
        "labour droid": frozenset({"floor"}),
        "combat mech": frozenset({"floor"}),
        "mining loader": frozenset({"floor"}),
        "cargo hauler unit": frozenset({"floor"}),
        "terraforming walker": frozenset({"floor"}),
        "sentry unit": frozenset({"floor"}),
        "security automaton": frozenset({"floor"}),
        "exosuit walker": frozenset({"floor"}),
        "reptilian grazer": frozenset({"floor"}),
        "silicate browser": frozenset({"floor"}),
        "burrowing worm-form": frozenset({"floor"}),
        "marauder": frozenset({"floor"}),
        "insectoid": frozenset({"floor"}),
        "arachnoid": frozenset({"floor"}),
        "parasitic brood": frozenset({"floor"}),
        # Round XV: ``ground``, not ``floor`` -- a fungal colony in a colony
        # concourse was drawn growing out of the metal deck.
        "plant-form": frozenset({"ground"}),
        "fungal colony": frozenset({"ground"}),
        "crystalline growth": frozenset({"ground"}),
        # A tentacled bell-body on a dry mining pit drew an Earth octopus.
        "cephalopod": frozenset({"water"}),
        "buried lander": frozenset({"ground"}),
        "gate ring": frozenset({"vast"}),
        "alien engine": frozenset({"vast"}),
        "star": frozenset({"deep-space"}),
        "neutron star": frozenset({"deep-space"}),
        "black hole": frozenset({"deep-space"}),
        "nebula cloud": frozenset({"deep-space"}),
        "binary star pair": frozenset({"deep-space"}),
    },
    # A relation that needs open space around it.
    "relation": {
        "orbiting": frozenset({"open-space"}),
        "drifting beside": frozenset({"open-space"}),
    },
    # A condition that names an environmental *deposit* needs a place that
    # could deposit it. ``ice-encrusted`` in a lava field is the class of
    # defect a per-field check cannot see. A face condition also needs air: a
    # sunburnt or exhausted face is a bare face, and vacuum holds none.
    "condition": {
        "ice-encrusted": frozenset({"cold"}),
        "frost-rimed": frozenset({"cold"}),
        "dust-caked": frozenset({"dust"}),
        "dust-streaked": frozenset({"dust"}),
        "overgrown": frozenset({"life"}),
        "sun-bleached": frozenset({"sunlight"}),
        "sunburnt": frozenset({"sunlight", "air"}),
        "exhausted": frozenset({"air"}),
        "scarred": frozenset({"air"}),
    },
    # A garment that leaves a face or a throat open needs air to meet. A sealed
    # suit says so in its spoken form instead (``SPOKEN["material"]``), so a
    # person in vacuum or underwater is never drawn with a bare face.
    "material": {
        "woven thermal-weave suit": frozenset({"air"}),
        "mail-weave undersuit": frozenset({"air"}),
        "cracked polymer flight suit": frozenset({"air"}),
        "reinforced flight suit": frozenset({"air"}),
        "quilted insulation suit": frozenset({"air"}),
        "woven meta-aramid suit": frozenset({"air"}),
        "ceremonial command uniform": frozenset({"air"}),
        "layered envoy robes": frozenset({"air"}),
        "scaled flight harness": frozenset({"air"}),
    },
    # An aperture that opens the face to the air needs air around it.
    "aperture": {
        "open visor": frozenset({"air"}),
        "hood opening": frozenset({"air"}),
        "respirator grille": frozenset({"air"}),
        "breathing mask vent": frozenset({"air"}),
    },
}


#: A form a model reads as an Earth craft rather than as a starship. A crescent
#: wing in a blue sky is an airliner whatever the qualifier says, so the shape
#: stays in open space, where nothing it could be mistaken for is around.
VALUE_NEEDS["form"] = {
    value: frozenset({"open-space"})
    for value in (
        "delta-wing hull", "flat wide-winged hull", "crescent-wing hull",
        "crescent hull", "stacked-deck tower hull", "layered terrace hull",
        "T-shaped prow hull", "forked twin-prow hull", "broad blunt-nosed hull",
        "twin-hulled frame", "modular boxy cargo hull",
    )
}


#: Repairs the affordance lint named: each value names a place in its own text,
#: so the need is declared rather than the keyword weakened. Kept as an update
#: so the value card lives beside the lint that found it.
VALUE_NEEDS["situation"].update({
    "settling onto the water on its belly": frozenset({"shoreline"}),
    "kneeling to read a bootprint": frozenset({"floor"}),
    "crouching behind a cargo pod": frozenset({"floor", "structure"}),
    "cutting through a jammed airlock with a torch": frozenset({"structure"}),
    "shouldering a buckling bulkhead back into place": frozenset({"structure"}),
    "carrying a child through a smoke-filled corridor": frozenset({"structure"}),
    "running through a collapsing gantry": frozenset({"structure"}),
    "fighting off a boarder at the airlock": frozenset({"structure"}),
    "rising from a half-buried crouch": frozenset({"ground", "floor"}),
    "tearing a hatch off its hinges": frozenset({"structure"}),
    "falling from a gantry": frozenset({"structure"}),
    "burying its fist in a bulkhead": frozenset({"structure"}),
    "spinning a resin nest between girders": frozenset({"floor", "structure"}),
    "hovering just above a plinth": frozenset({"floor"}),
    "hovering above a fallen plinth": frozenset({"floor"}),
    "settling onto a stone plinth": frozenset({"floor"}),
    "drawing a spiral of dust into orbit": frozenset({"open-space"}),
    "turning a cupola toward a nebula": frozenset({"open-space"}),
    "towing a string of cargo pods across a salt flat": frozenset({"ground"}),
    "charging across open ground with its ramp raised": frozenset({"ground"}),
    "churning through a muddy flat": frozenset({"ground"}),
    "sliding down a scree slope": frozenset({"ground"}),
    "cutting through a dust storm at low altitude": frozenset({"sky"}),
    "sheltering a nest of hull-borers": frozenset({"floor"}),
})


#: The places a value names when it names one. These are the situations the lint
#: exposes once the blanket allowlist is narrowed: a shared pool key cannot carry
#: the need (the union rule would demand every place its groups are drawn in), so
#: the need is declared on the value. A declared empty set is deliberate -- the
#: action reads anywhere, and saying so is what keeps the coverage gate at 100%.
VALUE_NEEDS["situation"].update({
    # the cross-genre core: an action true of any subject still names its ground
    "advancing across open ground": frozenset({"ground"}),
    "crossing the open ground": frozenset({"ground"}),
    "rising from a low crouch": frozenset({"floor"}),
    # a starship's own manoeuvre names the orbit it holds
    "settling into a parking orbit": frozenset({"open-space"}),
    # a surface vehicle's actions name the ground under the wheels or tracks
    "sliding sideways on loose gravel": frozenset({"ground"}),
    "parking beside a rock outcrop": frozenset({"ground"}),
    "lowering a ramp onto sand": frozenset({"ground"}),
    "crawling along a canyon floor": frozenset({"ground"}),
    "crossing a dry riverbed": frozenset({"ground"}),
    "rocking over a boulder": frozenset({"ground"}),
    "spraying mud from its tracks": frozenset({"ground"}),
    # a creature action can still name the medium: a shuttle flees through open
    # space, a captured drone can be coiled anywhere, a sled is towed over ground
    "striking at a fleeing shuttlecraft": frozenset({"open-space"}),
    "coiling its body into a tight spiral": frozenset(),
})
VALUE_NEEDS["subkind"].update({
    "asteroid": frozenset({"open-space"}),
    "nebula cloud": frozenset({"open-space"}),
    "orbital shipyard": frozenset({"open-space"}),
    "void monastery": frozenset({"open-space"}),
    "void grazer": frozenset({"open-space"}),
    "vacuum drifter": frozenset({"open-space"}),
    "stripped void freighter": frozenset({"open-space"}),
    "beached hulk": frozenset({"shoreline"}),
    "sand crawler": frozenset({"floor", "ground"}),
    "buried frigate": frozenset({"ground"}),
    "crashed hull": frozenset({"ground"}),
    "fossilised bioship": frozenset({"ground"}),
    "drifting hulk": frozenset({"open-space"}),
    "comet": frozenset({"open-space"}),
})

#: A type that can exist anywhere its kind is offered says so.
_TYPES_NEEDING_NOTHING: tuple[str, ...] = (
    "rocky planet", "gas giant", "ice moon", "ringed world", "dwarf planet", "rogue planet",
    "volcanic moon", "ocean world", "ring system", "ice giant", "lava world", "carbon planet",
    "energy being", "colonial swarm", "gelatinous mass",
    "gaseous drifter", "lithovore", "hive caste", "spore-caste drone", "mimic form",
    "radial hunter", "filter-swarm", "symbiont pair", "sessile brooder", "crystal grazer",
    "plasma drifter", "burrowing horror", "pilot", "engineer", "captain", "marine", "scientist",
    "medic", "smuggler", "colonist", "navigator", "salvager", "diplomat", "mercenary", "raider",
    "xenobiologist", "crew technician", "prospector", "void order priest", "quartermaster",
    "cyborg operative",
    "archaeologist", "cartographer", "repair drone", "survey drone", "android",
    "medical automaton", "swarm drone", "courier drone", "welding drone", "siege mech",
    "scout walker", "monolith", "obelisk", "beacon", "data core", "containment vault",
    "relic sphere", "sarcophagus pod", "resonant lattice spire", "drifting cargo pod",
    "sealed reliquary", "power cell array", "navigation marker pylon", "memory shard",
    "gravity anchor", "sealed gateway", "hovercraft", "skimmer", "hover bike",
    # "survey glider" was here and is not any more: this table is applied after
    # the per-value needs above and overwrote its own entry, so a glider needed
    # nothing of a place and was feasible at the bottom of an ocean trench. Its
    # twin "high-altitude glider" has always declared {"sky"}.
    "landing shuttlecraft", "drop pod", "amphibious crawler", "cargo sled",
    "burnt-out star cruiser", "ghost starliner", "collapsed station spar",
    "shattered interceptor", "abandoned mining rig", "half-salvaged star carrier",
    "torn-open habitat module", "gutted engine section",
)
VALUE_NEEDS["subkind"].update({value: frozenset() for value in _TYPES_NEEDING_NOTHING})
_WORLD_TYPE_NEEDS = frozenset({"deep-space", "vista"})
VALUE_NEEDS["subkind"].update({
    value: _WORLD_TYPE_NEEDS
    for group in ("solid world", "gas world", "disc system")
    for value in SUBKIND_GROUPS[group]
})
# D15: an alien person can stand anywhere a spacefarer can.
VALUE_NEEDS["subkind"].update({
    value: frozenset()
    for value in SUBKIND_GROUPS["alien people"]
})
VALUE_NEEDS[CONTEXT_FIELD].update({
    "stand of glass-bladed spires": frozenset({"ground"}),
    "thicket of glassy spore-towers": frozenset({"ground"}),
    "slope of lithophyte crusts": frozenset({"ground"}),
    "swarm of drifting luminous spore-motes": frozenset({"ground", "life"}),
    "grove of bulbous tube-flora": frozenset({"ground"}),
    "stand of tall luminous crystal spires": frozenset({"ground"}),
    "grove of chitin-plated fan-spires": frozenset({"ground"}),
    "field of light-drinking crystal fronds": frozenset({"ground"}),
    "service gantry above the deck": frozenset({"floor", "structure"}),
    "hatch standing open at the far end": frozenset({"floor", "structure"}),
})


# ---------------------------------------------------------------------------
# The affordance lint, and the defaults that make a huge pool safe
# ---------------------------------------------------------------------------
#
# A value that names a place-affordance in its own text must declare the need,
# or the lint in ``tests/validate_data.py`` fails it. The keyword list is
# deliberately narrow: a broad word matches half the corpus and the allowlist
# then grows without bound. ``AFFORDANCE_ALLOWLIST`` holds the needs-free cores,
# whose whole design is to be place-neutral.

#: ``{affordance: (keyword, ...)}`` -- the words that name a place in a value.
AFFORDANCE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "ground": (
        "sand", "dune", "scree", "gravel", "regolith", "salt flat", "canyon floor", "canyon wall",
        "riverbed", "mud", "soil", "boulder", "ridge", "ridge line", "broken ground",
        "open ground", "the ground", "rock outcrop", "slope", "cliff", "grit", "ruts",
        "cave mouth", "landing site", "crater wall", "crater floor",
    ),
    "floor": (
        "nest", "clutch of", "deck", "plinth", "kneel", "kneeling", "crouch", "crouching",
        "prone", "stretcher", "cart",
    ),
    "structure": (
        "airlock", "corridor", "hatch", "bulkhead", "girder", "girders", "gantry", "catwalk",
        "doorway", "door", "the hold", "cargo hold", "console", "seat", "cockpit", "ladder",
        "shaft", "cryo", "ceiling", "vents", "a wall", "low wall", "collapsing wall",
        # Round XXI: acts that presume a built interior around the actor. They
        # had no declared need, so a medic "sealed a hull breach with a foam
        # sprayer" on a fungal floor and a robot "cut a panel free" on a lava
        # field -- and the same acts reached fantasy and horror places whole.
        "hull breach", "breach", "panel", "cabling", "strut", "compartment",
        "falling beam", "cargo pod", "closing gap", "containment field", "the air thins",
    ),
    "gravity": (
        "falling", "falls", "under its own weight", "slide", "avalanche", "slumping", "burying",
        "down a slope", "mid-air", "out of the air", "off their feet", "toppling", "rockslide",
    ),
    "shoreline": (
        "shore", "lake", "marsh", "beach", "tide", "surf", "swamp", "riverbank", "coast",
        "water", "shallows",
    ),
    "submerged": (
        "underwater", "seabed", "abyssal", "sunken", "trench floor", "sonar", "ballast", "bubbles",
    ),
    "open-space": (
        "orbit", "void", "vacuum", "asteroid", "nebula", "deep space", "the stars", "debris field",
        "for a jump",
    ),
    "sky": (
        "thermals", "banking", "altitude", "cloud layer", "cloud deck", "storm band", "crosswind",
        "gust", "turbulence", "sky",
    ),
    "air": (
        "mid-air", "out of the air", "the wind", "into the wind",
    ),
    "cloud-deck": (
        "cloud tops", "storm band", "cloud bank", "cloud columns", "lightning front",
        "thermal column", "updraft", "downdraft", "the clouds",
    ),
    "dock": ("dock", "berth", "mooring", "drydock"),
}

#: The fields the lint and the coverage gate read. ``form`` is deliberately not
#: here: a shape does not need a place, it needs a *stance*, and the stance axis
#: is what keeps a ring out of a gravity well. Scanning a shape for the word
#: "deck" only ever finds a substring of "stacked-deck".
#: Task 4 Step 5 -- every situation declares the place it needs. The needs below are
#: the union of the affordance keywords its own text names, plus the place a shared
#: action is drawn in; a value that reads anywhere the subject can exist says so with
#: an explicit empty set. Grouped by the pool key it is authored under.
VALUE_NEEDS["situation"].update({
    "sweeping a sensor beam down a shaft": frozenset({"structure"}),  # robot or mech,small drone
    "angling its mirrors toward a star": frozenset({}),  # space station
    "arguing over a projected chart": frozenset({"floor"}),  # spacefarer
    "backing up to a cargo pod": frozenset({"structure"}),  # flying,hovering,legged,surface vehicle,underwater,wheeled/tracked
    "being circled by scanning drones": frozenset({}),  # alien artifact
    "being cut open by salvage drones": frozenset({}),  # wreck
    "being examined by a survey drone": frozenset({"floor"}),  # _default
    "being guarded by a flight of sentry drones": frozenset({"floor"}),  # alien artifact
    "being lifted onto a recovery cradle": frozenset({}),  # alien artifact
    "being stripped by a swarm of salvage drones": frozenset({}),  # space station,wreck
    "being surveyed by a drifting inspection drone": frozenset({}),  # wreck
    "being swarmed by small starships at every docking arm": frozenset({"dock"}),  # space station
    "bending a nearby survey mast toward itself": frozenset({"ground"}),  # alien artifact
    "berthing rows of small spacecraft along its central truss": frozenset({}),  # space station
    "braking hard at a cliff edge": frozenset({"ground"}),  # flying,hovering,legged,surface vehicle,underwater,wheeled/tracked
    "breaking apart in a slow avalanche": frozenset({"gravity"}),  # wreck
    "breaking apart in a spreading cloud of debris": frozenset({}),  # _default
    "breaking in half across a failing frame": frozenset({}),  # courier,starship
    "breaking out of a containment field with a single lunge": frozenset({"structure"}),  # alien creature,diffuse being
    "breaking up as it falls": frozenset({"gravity"}),  # wreck
    "breaking up under a barrage along its central hull": frozenset({}),  # courier,starship
    "buckling as its main girder gives way": frozenset({"structure"}),  # wreck
    "bursting a hub against an obstacle": frozenset({}),  # flying,hovering,legged,surface vehicle,underwater,wheeled/tracked
    "shaking flakes of hardened resin from its back": frozenset({}),  # alien creature,diffuse being
    "bursting in a wave of light": frozenset({}),  # alien artifact
    "bursting through a sealed door": frozenset({"structure"}),  # alien creature
    "burying a salvage crawler in a slide": frozenset({"gravity", "ground"}),  # wreck
    "burying its fist in a bulkhead": frozenset({"gravity", "structure"}),  # robot or mech
    "carrying a cage of refit scaffolding": frozenset({}),  # space station
    "dodging a falling slab of rock": frozenset({"gravity", "air"}),  # robot or mech,small drone
    "catching a falling colleague by the wrist": frozenset({"gravity", "air"}),  # spacefarer
    "catching the light along a torn edge": frozenset({}),  # wreck
    "chalking a mark on a wall": frozenset({"structure"}),  # spacefarer
    "churning up a spray of grit": frozenset({"ground"}),  # flying,hovering,legged,surface vehicle,underwater,wheeled/tracked
    "circling a landing site": frozenset({"ground"}),  # flying,hovering,legged,surface vehicle,underwater,wheeled/tracked
    "climbing a hull on magnetic boots": frozenset({"floor"}),  # spacefarer
    "climbing over a low wall": frozenset({"structure"}),  # robot or mech,small drone
    "collapsing into a singularity": frozenset({}),  # alien artifact
    "collapsing into a trailing field of wreckage": frozenset({}),  # space station
    "collapsing into the pit it made": frozenset({}),  # wreck
    "collapsing under its own weight": frozenset({"gravity"}),  # wreck
    "coming apart along one long seam": frozenset({}),  # _default
    "cracking open along a docking arm": frozenset({}),  # space station
    "cracking open along a seam": frozenset({}),  # alien artifact
    "cracking open along a seam in the hull": frozenset({}),  # courier,starship
    "cracking the ground beneath it": frozenset({"ground"}),  # alien artifact
    "cracking under a cutting beam": frozenset({}),  # alien artifact
    "crawling up a vertical face": frozenset({}),  # alien creature
    "cresting a rise in a cloud of dust": frozenset({"ground"}),  # flying,hovering,legged,surface vehicle,underwater,wheeled/tracked
    "crossing a star field in silhouette": frozenset({}),  # courier,starship
    "crouching to inspect wreckage": frozenset({"floor"}),  # robot or mech,small drone
    "crumbling into a field of drifting debris": frozenset({}),  # wreck
    "slamming its whole bulk down": frozenset({}),  # alien creature,diffuse being
    "shedding a slab of plating as it settles": frozenset({"gravity"}),  # wreck
    "curling into a defensive coil": frozenset({}),  # alien creature,diffuse being
    "cutting a panel free": frozenset({"structure"}),  # robot or mech,small drone
    "cycling a lock with a burst of vapour": frozenset({}),  # space station
    "decelerating on a long plume": frozenset({}),  # courier,starship
    "discharging arcs across its surface": frozenset({}),  # alien artifact
    "diving clear of a falling beam": frozenset({"gravity"}),  # spacefarer
    "pinning a salvage drone beneath a buckled plate": frozenset({}),  # wreck
    "dragging a survivor into the dark": frozenset({}),  # alien creature
    "pulling a spiral of loose rubble toward its base": frozenset({}),  # alien artifact
    "drawing loose debris off the deck toward itself": frozenset({"floor", "gravity"}),  # alien artifact
    "drifting with its bays sealed": frozenset({}),  # space station
    "drifting with its engines cold": frozenset({}),  # courier,starship
    "drilling a core sample from the bedrock": frozenset({"ground"}),  # surface vehicle
    "drilling into a wall": frozenset({"structure"}),  # robot or mech
    "driving through a blockade line": frozenset({}),  # starship
    "launching a probe from a nose bay": frozenset({}),  # courier,starship
    "dropping toward a landing pad on its belly thrusters": frozenset({}),  # surface vehicle
    "dumping fuel in a spreading cloud": frozenset({}),  # courier,starship
    "extending a cluster of feelers": frozenset({}),  # alien creature,diffuse being
    "extending a docking arm": frozenset({}),  # space station
    "extending a new module on assembly arms": frozenset({}),  # space station
    "extending a sampling boom": frozenset({}),  # flying,hovering,legged,surface vehicle,underwater,wheeled/tracked
    "extending a tool turret": frozenset({}),  # robot or mech,small drone
    "falling from a gantry": frozenset({"gravity", "structure"}),  # robot or mech
    "fanning a set of gill frills": frozenset({}),  # alien creature,diffuse being
    "feeding on a wreck's power core": frozenset({}),  # alien creature
    "sealing a hull breach with a foam sprayer": frozenset({"floor", "structure"}),  # spacefarer
    "firing a full weapons array at a closing formation": frozenset({}),  # starship
    "firing point-defence into a swarm": frozenset({}),  # space station
    "flaring a docking guide light": frozenset({}),  # space station
    "flaring in a single hard pulse": frozenset({}),  # _default
    "flaring its drive coils for a jump": frozenset({"open-space"}),  # starship
    "flashing a signal beacon in a slow pattern": frozenset({}),  # courier,starship
    "strobing a red beacon from its mast": frozenset({}),  # space station
    # Named a rock with no need for one -- a burrowing horror flattened
    # against a literal boulder in open space, in a "derelict shipyard
    # orbit" with nothing solid to press against.
    "flattening itself against a rock": frozenset({"ground"}),  # alien creature,diffuse being
    "fleeing in a hard turn": frozenset({}),  # _default
    "flipping onto its back on a hard turn": frozenset({}),  # flying,hovering,legged,surface vehicle,underwater,wheeled/tracked
    "floating above a ruined floor": frozenset({"structure"}),  # alien artifact
    "following a set of wheel ruts": frozenset({"ground"}),  # flying,hovering,legged,surface vehicle,underwater,wheeled/tracked
    "giving way under a salvage drone's cutting beam": frozenset({}),  # wreck
    "going dark all at once": frozenset({"floor"}),  # alien artifact
    "going down under a mass of smaller units": frozenset({}),  # robot or mech,small drone
    "grinding to a halt with a seized joint": frozenset({}),  # robot or mech,small drone
    "grinding up a rocky slope": frozenset({"ground"}),  # flying,hovering,legged,surface vehicle,underwater,wheeled/tracked
    "hanging motionless in the open": frozenset({}),  # _default
    "hanging unsupported above the ground": frozenset({"ground"}),  # alien artifact
    "hauling a carcass into the shade": frozenset({}),  # alien creature
    "hauling a cargo pod up a ramp": frozenset({"floor", "structure"}),  # spacefarer
    "hauling a stretcher through a smoking corridor": frozenset({"floor", "structure"}),  # spacefarer
    "hoisting a beam into place": frozenset({}),  # robot or mech,small drone
    "holding a collapsing wall up with its shoulders": frozenset({"structure"}),  # robot or mech
    "holding a door against a rush of pressure": frozenset({"structure"}),  # spacefarer
    "holding a small starship in a docking cradle": frozenset({}),  # space station
    "holding formation with two escorts": frozenset({}),  # courier,starship
    "holding position over a landing pad": frozenset({"ground"}),  # courier,starship
    "holding station beside a survey beacon": frozenset({}),  # starship
    "hosing dust off a panel": frozenset({"floor", "structure"}),  # spacefarer
    "humming as a seam brightens": frozenset({}),  # alien artifact
    "humming with a low tone": frozenset({}),  # alien artifact
    "hunting through the rubble for movement": frozenset({}),  # robot or mech
    "idling with its lights on": frozenset({}),  # flying,hovering,legged,surface vehicle,underwater,wheeled/tracked
    "landing hard with its gear folding": frozenset({"ground"}),  # starship
    "lashing out with a hooked limb": frozenset({}),  # alien creature
    "launching interceptors from an open bay": frozenset({}),  # starship
    "leaning into the wind": frozenset({"air", "ground"}),  # _default
    "levelling a weapon at something off to one side": frozenset({"floor"}),  # spacefarer
    "levelling its shoulder cannon": frozenset({}),  # robot or mech
    "lifting a spread of rubble off the ground": frozenset({"ground"}),  # alien artifact
    "listing badly with half its hull gone": frozenset({}),  # space station
    # A full-throttle mishap needs room to have built up speed in -- reached
    # a "station docking ring interior" (a tight, walled place) as readily
    # as open ground, and rendered a ground vehicle racing indoors.
    "losing a wheel at full throttle": frozenset({"vast"}),  # flying,hovering,legged,surface vehicle,underwater,wheeled/tracked
    "lowering a cargo cradle onto a waiting hull": frozenset({}),  # space station
    "lowering a maintenance platform": frozenset({}),  # space station
    "sweeping the terrain below with a scanning beam": frozenset({}),  # courier,starship
    "lowering its jaws to drink": frozenset({}),  # alien creature
    "making first contact with open hands": frozenset({"floor"}),  # spacefarer
    "matching course with a slower cargo starship": frozenset({}),  # courier,starship
    "flexing a freshly moulted outer skin": frozenset({}),  # alien creature,diffuse being
    "moving out into the open": frozenset({}),  # _default
    "nosing into a cave mouth": frozenset({"ground"}),  # flying,hovering,legged,surface vehicle,underwater,wheeled/tracked
    "nosing over a sharp crest": frozenset({}),  # surface vehicle
    "opening a bank of bay doors": frozenset({}),  # space station
    "passing a tool to a colleague": frozenset({"floor"}),  # spacefarer
    "passing across the face of a planet": frozenset({}),  # space station
    "passing in front of a banded amber moon": frozenset({}),  # courier,starship
    "planting a beacon on a ridge": frozenset({"ground"}),  # spacefarer
    "ploughing a trench through the ground on impact": frozenset({"ground"}),  # starship
    "plunging through a sheet of thin ice": frozenset({"cold"}),  # surface vehicle
    "pressing its jaws to the ground": frozenset({"ground"}),  # alien creature
    "printing a slow plume from a vent": frozenset({}),  # space station
    "projecting a chart of unmapped space": frozenset({}),  # alien artifact
    "projecting a column of light": frozenset({}),  # alien artifact
    "prying open a hatch": frozenset({"structure"}),  # robot or mech,small drone
    "pulling a descending lander out of the sky": frozenset({"sky"}),  # alien artifact
    "pulling up beside a supply dome": frozenset({}),  # surface vehicle
    "pulsing light through its veins": frozenset({}),  # alien artifact
    "punching through a debris curtain at speed": frozenset({}),  # courier,starship
    "pushing a cart of supplies": frozenset({"floor"}),  # spacefarer
    "raising a cloud of grit": frozenset({"ground"}),  # flying,hovering,legged,surface vehicle,underwater,wheeled/tracked
    "raising a crest of quills": frozenset({}),  # alien creature,diffuse being
    "raising a heavy rock drill": frozenset({}),  # robot or mech,small drone
    "ramming a barricade at full speed": frozenset({"vast", "ground"}),  # surface vehicle
    "reaching down to help someone up": frozenset({"floor"}),  # spacefarer
    "keying a sequence into a console": frozenset({"floor", "structure"}),  # spacefarer
    "rearing up on its hind limbs": frozenset({}),  # alien creature
    "retracting a docking boom": frozenset({}),  # space station
    "ducking low and backing away": frozenset({"floor"}),  # _default
    "reversing out of a gully": frozenset({"floor"}),  # surface vehicle
    "righting itself after a fall": frozenset({}),  # robot or mech
    "rising slowly from the ground": frozenset({"ground"}),  # alien artifact
    "rolling down a slope out of control": frozenset({"gravity", "ground"}),  # surface vehicle
    "rolling to present its armoured flank": frozenset({}),  # courier,starship
    "rotating slowly on its axis": frozenset({}),  # alien artifact
    "rotating slowly with its radiators aglow": frozenset({}),  # space station
    "running a course through a debris field": frozenset({"open-space"}),  # courier,starship
    "running a diagnostic on an open panel": frozenset({"floor", "structure"}),  # spacefarer
    "running a cargo gantry along a rail": frozenset({"structure"}),  # space station
    "running dark past a derelict": frozenset({}),  # courier,starship
    "scanning a doorway": frozenset({"structure"}),  # robot or mech,small drone
    "scanning a wall with a handheld": frozenset({"structure"}),  # spacefarer
    "scraping along a canyon wall": frozenset({"ground"}),  # starship
    "sealing a breach as the air thins": frozenset({"floor"}),  # spacefarer
    "sealing a cracked visor with tape": frozenset({"floor"}),  # spacefarer
    "clamping its jaws shut with a crack": frozenset({"gravity"}),  # alien creature,diffuse being
    "severing a snarl of cabling": frozenset({"floor", "structure"}),  # spacefarer
    "shaking off a cloud of stinging motes": frozenset({}),  # alien creature,diffuse being
    "projecting a holographic star map from one palm": frozenset({"floor"}),  # spacefarer
    "shattering into a spray of fragments": frozenset({}),  # _default
    "shearing a tread on a jagged edge": frozenset({}),  # flying,hovering,legged,surface vehicle,underwater,wheeled/tracked
    "shearing in half along its central truss": frozenset({}),  # space station
    "shedding a cascade of plate fragments": frozenset({}),  # wreck
    "shedding a crust of dust as it moves": frozenset({}),  # alien artifact
    "shedding flakes of light": frozenset({}),  # alien artifact
    "shedding spores in a slow cloud": frozenset({}),  # alien creature,diffuse being
    "shuddering under a direct hit": frozenset({}),  # courier,starship
    "signalling with waves of colour along its flank": frozenset({}),  # alien creature,diffuse being
    "slewing hard as a hull section tears away": frozenset({}),  # courier,starship
    "slumping as a spar gives way": frozenset({"gravity"}),  # wreck
    "snapping an axle on a hard landing": frozenset({}),  # flying,hovering,legged,surface vehicle,underwater,wheeled/tracked
    "snapping at a passing spark": frozenset({}),  # alien creature,diffuse being
    "spilling a fan of debris down a slope": frozenset({"gravity", "ground"}),  # wreck
    "spilling a wave of debris across the ground": frozenset({"ground"}),  # wreck
    "spilling a white plume from a ruptured hull": frozenset({}),  # space station
    "spilling its contents across the ground": frozenset({"ground"}),  # wreck
    "spilling light from a widening crack": frozenset({}),  # alien artifact
    "spinning out at full throttle": frozenset({"vast"}),  # flying,hovering,legged,surface vehicle,underwater,wheeled/tracked
    "spinning out with a thruster stuck open": frozenset({}),  # courier,starship
    "spinning up a cloud of fragments": frozenset({}),  # alien artifact
    "spitting a stream of caustic bile": frozenset({}),  # alien creature,diffuse being
    "splitting open along freshly-formed seams": frozenset({}),  # alien artifact
    "extending a docking boom between modules": frozenset({}),  # space station
    "spraying a fan of glittering coolant crystals from a ruptured line": frozenset({}),  # space station
    "spraying sealant on a seam": frozenset({}),  # robot or mech,small drone
    "spreading a fan of spines": frozenset({}),  # alien creature,diffuse being
    "spreading a hood of skin": frozenset({}),  # alien creature,diffuse being
    "crossing cracked ground": frozenset({"ground"}),  # robot or mech
    "standing amid a circle of stones": frozenset({}),  # alien artifact
    "standing guard over a column of civilian starships": frozenset({}),  # starship
    "standing over the wreckage of something else": frozenset({"floor"}),  # _default
    "steadying a ladder for a colleague": frozenset({"structure"}),  # spacefarer
    "steadying a load with an outrigger": frozenset({}),  # robot or mech,small drone
    "strapping into a seat": frozenset({"structure"}),  # spacefarer
    "lunging with its jaws flung wide": frozenset({}),  # alien creature
    "swallowing a survey drone whole": frozenset({}),  # alien artifact
    "swarming across a hull in a moving carpet": frozenset({}),  # alien creature
    "sweeping a searchlight across a hull": frozenset({}),  # courier,starship
    "swinging a beacon through the dark": frozenset({}),  # space station
    "swinging a cargo cradle out over open space": frozenset({}),  # space station
    "snapping at the air in a sudden strike": frozenset({"gravity", "air"}),  # alien creature
    "tearing loose from a docking clamp": frozenset({}),  # _default
    "tearing into a fallen hull": frozenset({}),  # alien creature,diffuse being
    "tearing open along a frost-welded seam": frozenset({"cold"}),  # wreck
    "tearing open along a line of light": frozenset({}),  # alien artifact
    "tearing open along a rusted seam": frozenset({}),  # wreck
    "throwing a track at speed": frozenset({"vast"}),  # flying,hovering,legged,surface vehicle,underwater,wheeled/tracked
    "climbing a dune ridge at full throttle": frozenset({"vast", "ground"}),  # surface vehicle
    "racing a storm front toward shelter": frozenset({"vast"}),  # flying,hovering,legged,surface vehicle,wheeled/tracked
    "tightening a coupling with a wrench": frozenset({"floor"}),  # spacefarer
    "hauling a stripped hulk in a tractor beam": frozenset({}),  # starship
    "tracking something overhead": frozenset({}),  # alien creature,diffuse being
    "trading shots across an open bay": frozenset({}),  # robot or mech
    "trailing a thin wake of particles": frozenset({}),  # courier,starship
    "trailing smoke from one dead engine nacelle": frozenset({}),  # starship
    "tumbling out of its rotation": frozenset({}),  # space station
    "turning its flank to a banded world": frozenset({}),  # courier,starship
    "turning its long truss against the light": frozenset({}),  # space station
    "turning to face a dust storm": frozenset({}),  # flying,hovering,legged,surface vehicle,underwater,wheeled/tracked
    "tying a bandage around their own forearm": frozenset({"floor"}),  # spacefarer
    "flaring its body wide in a threat display": frozenset({}),  # alien creature,diffuse being
    "unfolding a panel of lattices": frozenset({}),  # alien artifact
    "unfolding a radiator fin bank": frozenset({}),  # space station
    "opening its forward launch bay doors": frozenset({}),  # courier,starship
    "unfolding a set of fins": frozenset({}),  # alien artifact
    "unfolding a solar array wing": frozenset({}),  # space station
    "extending a dorsal sensor spine": frozenset({}),  # courier,starship
    "unfolding from a resting pose": frozenset({}),  # _default
    "unloading cargo pods onto a landing pad": frozenset({}),  # surface vehicle
    "clamping a magnetic beacon to a deck plate": frozenset({"floor"}),  # spacefarer
    "venting vapour from a ruptured central truss": frozenset({}),  # space station
    "venting white vapour from a torn flank": frozenset({}),  # starship
    "waiting at the edge of the clearing": frozenset({}),  # _default
    "waiting with its ramp down and cabin open": frozenset({}),  # surface vehicle
    "waking from cryo with frost still on the suit": frozenset({"structure"}),  # spacefarer
    "weaving through a stand of stalks": frozenset({}),  # alien creature
    "welding a new spar in place": frozenset({}),  # space station
    "welding a seam along a hull plate": frozenset({}),  # robot or mech
    "welding a seam with a torch": frozenset({"floor"}),  # spacefarer
    "nosing through a cloud of stirred-up silt": frozenset({}),  # surface vehicle
})

AFFORDANCE_LINT_FIELDS: tuple[str, ...] = ("situation", "context", "subkind")

#: Values the keyword scan skips, each because a place need would be false for a
#: place the value must still reach. The shared robot core is the one case the
#: union rule cannot classify: ``scanning a doorway`` and ``prying open a hatch``
#: are drawn by both ``robot or mech`` and the ``small drone`` subkind group, and
#: that group's situation pool sits exactly on the band floor, so any place need on
#: them drops it below the floor in every place that is not the need's own. The
#: words name a fitting the drone inspects, not a place it has to be. Every other
#: shared value that names a place declares it in ``value_needs`` instead.
AFFORDANCE_ALLOWLIST: frozenset[str] = frozenset({
    "scanning a doorway",
    # The subject's own fittings, not the place's: a station's docking cradle, a
    # vehicle's own hull breach or lift panel, an artifact's own lattice panel,
    # a drone towing a pod through open space.
    "catching a drifting cargo pod in a docking cradle",
    "unfolding a panel of lattices",
    "trailing a stream of bubbles from a breach",
    "losing a lift-pod panel in a violent gust",
    "guiding a cargo pod in a tractor beam",
    "drifting cargo pod",
    # A gas world seen from space names its own cloud tops; that is the body's
    # surface, not a place the scene stands in.
    "swallowing a comet in a flash across its cloud tops",
    "prying open a hatch",
    # A station's own fittings are not the place's affordances: a station
    # berthing a craft *is* the dock, so the dock word in its own actions is not
    # a place need. Same for a drydock-cradle station and a void-order priest.
    "berthing rows of small spacecraft along its central truss",
    "extending a docking arm",
    "holding a small starship in a docking cradle",
    "flaring a docking guide light",
    "being swarmed by small starships at every docking arm",
    "cracking open along a docking arm",
    "running a cargo gantry along a rail",
    "scatter of landers holding near a docking arm",
    "drydock cradle",
    "void order priest",
})

#: ``{field: {pool key: needs}}`` -- the need every value authored under that
#: key has unless it declares its own. Only a key whose values are drawn by one
#: subkind group can carry a place need; a shared core stays neutral on purpose,
#: because the same value would otherwise need two different places at once.
DEFAULT_NEEDS: dict[str, dict[str, frozenset[str]]] = {
    CONTEXT_FIELD: {
        "deep space": frozenset({"open-space"}),
        "orbit": frozenset({"open-space"}),
        "cloud layer": frozenset({"sky"}),
        "planetary surface": frozenset({"ground"}),
        "interior": frozenset({"floor"}),
    },
    "situation": {
        "celestial body": frozenset({"open-space"}),
        "solid world": frozenset({"open-space"}),
        "star body": frozenset({"open-space"}),
        "singularity": frozenset({"open-space"}),
        "diffuse cloud": frozenset({"open-space"}),
        "gas world": frozenset({"open-space"}),
        "small body": frozenset({"open-space"}),
        "binary system": frozenset({"open-space"}),
        "disc system": frozenset({"open-space"}),
    },
    #: A starship or a station needs room larger than a building around it.
    "subkind": {
        "starship": frozenset({"vast"}),
        "space station": frozenset({"vast"}),
    },
}

#: ``{affordance: stances the place supports}``.
PLACE_STANCES: dict[str, frozenset[str]] = {
    "ground": frozenset({"rests", "walks", "rolls"}),
    "floor": frozenset({"rests", "walks", "rolls", "hovers"}),
    "structure": frozenset({"rests", "walks", "rolls", "hovers"}),
    "sky": frozenset({"flies", "hovers", "falls"}),
    "open-space": frozenset({"floats", "orbits"}),
    "deep-space": frozenset({"floats", "orbits"}),
    "submerged": frozenset({"swims", "rests"}),
    "shoreline": frozenset({"rests", "walks", "rolls", "swims", "hovers"}),
    "dock": frozenset({"rests", "hovers"}),
}

#: Round XV: a seabed still has a floor to rest and walk on, but no wheel or
#: track rolls under water (a wheeled security robot crossed a vent field).
PLACE_STANCE_BLOCKS: dict[str, frozenset[str]] = {
    "submerged": frozenset({"rolls"}),
}


_STANCE_ORBIT = frozenset({"orbits"})
_STANCE_RING = frozenset({"floats", "orbits"})
_STANCE_SHIP = frozenset({"floats", "rests", "hovers"})
#: A station hovers too: a cloud-city platform holds itself up on lift, not on a floor.
_STANCE_STATION = frozenset({"floats", "orbits", "rests", "hovers"})
_STANCE_ARTIFACT = frozenset({"rests", "floats", "hovers"})
#: A wreck lies where it fell, drifts in vacuum, or is still falling through air.
_STANCE_WRECK = frozenset({"rests", "floats", "falls"})
_STANCE_WING = frozenset({"flies", "hovers", "rests"})
_STANCE_WALK = frozenset({"rests", "walks"})
#: A suited person drifts in vacuum as readily as they stand on a deck.
_STANCE_PERSON = frozenset({"rests", "walks", "floats"})
#: A drone flies on thrusters, so it holds position in vacuum as well as over a floor.
_STANCE_DRONE = frozenset({"hovers", "floats", "rests"})
_STANCE_WHEEL = frozenset({"rolls", "rests"})
_STANCE_HOVER = frozenset({"hovers", "rests"})
_STANCE_SWIM = frozenset({"swims", "rests"})
_STANCE_FLOAT = frozenset({"floats"})
_STANCE_STATIC = frozenset({"rests"})

#: Ring and disc silhouettes never rest. A ring standing on its ring is the
#: defect the stance axis exists to kill.
_RING_FORMS: frozenset[str] = frozenset({
    "torus-braced hull", "disc-and-boom hull", "torus", "stacked disc tiers",
    "spoke-and-hub wheel", "trussed wheel", "smooth torus", "hollow open hoop",
    "counter-rotating disc body", "vertically stacked disc segments",
    "counter-rotating habitat cylinders", "disc of dust and rock", "banded disc",
    "stacked disc column", "floating circle of shards",
    "looped torque ring",
})


#: Robot and vehicle bodies say how they move one form at a time: a kind-wide default
#: let a tracked chassis "walk" and a hover disc stand in vacuum.
_ROBOT_FORM_STANCES: dict[str, frozenset[str]] = {
    "bipedal walker chassis": _STANCE_WALK,
    "humanoid android frame": _STANCE_WALK,
    "armoured humanoid frame": _STANCE_WALK,
    "quadrupedal walker chassis": _STANCE_WALK,
    "insectile six-legged chassis": _STANCE_WALK,
    "tripod strider chassis": _STANCE_WALK,
    "multi-legged strider chassis": _STANCE_WALK,
    "eight-legged crawler chassis": _STANCE_WALK,
    "serpentine segmented chassis": _STANCE_WALK,
    "tracked chassis": _STANCE_WHEEL,
    "boxy utility chassis": _STANCE_WHEEL,
    "twin-armed hauler frame": _STANCE_WHEEL,
    "wheeled drone body": _STANCE_WHEEL,
    "spherical drone body": _STANCE_DRONE,
    "hovering disc chassis": _STANCE_DRONE,
}
_VEHICLE_FORM_STANCES: dict[str, frozenset[str]] = {
    "boxy tracked hull": _STANCE_WHEEL,
    "six-wheeled rover chassis": _STANCE_WHEEL,
    "articulated cargo crawler chassis": _STANCE_WHEEL,
    "open-frame six-wheeled rover chassis": _STANCE_WHEEL,
    "articulated segmented crawler": _STANCE_WHEEL,
    "articulated two-section body": _STANCE_WHEEL,
    "twin-hull hauler frame": _STANCE_WHEEL,
    "low wedge chassis": _STANCE_WHEEL,
    "low skimmer hull": _STANCE_HOVER,
    "teardrop hover hull": _STANCE_HOVER,
    "twin-pod repulsor hull": _STANCE_HOVER,
    "articulated repulsor-skirt hull": _STANCE_HOVER,
    "plated hover-pallet chassis": _STANCE_HOVER,
    "walker leg frame": _STANCE_WALK,
    "six-legged walker frame": _STANCE_WALK,
    "blunt gravlift wedge": _STANCE_WING,
    "faceted anti-grav wedge": _STANCE_WING,
    "bulbous pressurised cabin": _STANCE_WING,
    "cylindrical submersible hull": _STANCE_SWIM,
    "blunt re-entry capsule": _STANCE_WING,
    "squat lander with splayed legs": _STANCE_WING,
    "flat lifting-body gravlift hull": _STANCE_WING,
}


def _form_stances() -> dict[str, frozenset[str]]:
    """How each shape holds itself up. Rings first and never overridden; made things by
    kind; robots and vehicles form by form; creatures by body plan."""
    stances: dict[str, frozenset[str]] = {value: _STANCE_RING for value in _RING_FORMS}
    for value in FORM_POOLS["celestial body"]:
        stances.setdefault(value, _STANCE_ORBIT)
    for value in FORM_POOLS["starship"]:
        stances.setdefault(value, _STANCE_SHIP)
    for value in FORM_POOLS["space station"]:
        stances.setdefault(value, _STANCE_STATION)
    for value in FORM_POOLS["alien artifact"]:
        stances.setdefault(value, _STANCE_ARTIFACT)
    for value in FORM_POOLS["wreck"]:
        stances.setdefault(value, _STANCE_WRECK)
    for value in FORM_POOLS["spacefarer"]:
        stances.setdefault(value, _STANCE_PERSON)
    for value in FORM_POOLS["alien people"]:
        stances.setdefault(value, _STANCE_PERSON)
    stances.update(_ROBOT_FORM_STANCES)
    stances.update(_VEHICLE_FORM_STANCES)
    for value in FORM_POOLS["alien creature"]:
        stances.setdefault(value, _STANCE_WALK)
    for value in FORM_POOLS["winged"]:
        stances[value] = _STANCE_WING
    for value in FORM_POOLS["aquatic"]:
        stances[value] = _STANCE_SWIM
    for value in FORM_POOLS["diffuse being"] + FORM_POOLS["void dweller"]:
        stances[value] = _STANCE_FLOAT
    for group in (
        "solid world", "gas world", "small body", "star body", "singularity",
        "diffuse cloud", "binary system", "disc system",
    ):
        for value in FORM_POOLS[group]:
            stances.setdefault(value, _STANCE_ORBIT)
    stances["wheel-shaped rolling body"] = _STANCE_WHEEL
    #: An energy being drifts in vacuum and hangs in the air of a hangar.
    stances["amorphous mass"] = frozenset({"floats", "hovers"})
    stances["quivering gel body"] = _STANCE_WALK
    stances["sprawling colonial body"] = _STANCE_WALK
    #: A bell-bodied swimmer needs water, not vacuum.
    stances["tentacled bell-body"] = _STANCE_SWIM
    stances["inverted funnel body"] = _STANCE_HOVER
    stances["fan-gilled drifting body"] = frozenset({"swims", "hovers"})
    #: A disc-bodied colony rests on what it grew on; only a void dweller drifts.
    stances["counter-rotating disc body"] = _STANCE_HOVER
    stances["vertically stacked disc segments"] = _STANCE_HOVER
    stances["branching crystalline lattice"] = _STANCE_STATIC
    stances["tessellated plate column"] = _STANCE_STATIC
    stances["stalked polyp column"] = _STANCE_STATIC
    stances["nested shell cluster"] = _STANCE_STATIC
    stances["spiral coil of gas"] = _STANCE_FLOAT
    stances["expanding gas shell"] = _STANCE_FLOAT
    stances["close-orbiting star core"] = _STANCE_ORBIT
    return stances


VALUE_STANCES: dict[str, dict[str, frozenset[str]]] = {
    "form": _form_stances(),
    # Only the actions whose own wording implies a stance; the rest are
    # neutral and constrain nothing.
    "situation": {
        "lowering a ramp onto sand": frozenset({"rests"}),
        "settling deeper into the sand": frozenset({"rests"}),
        "sinking into the dust it rests on": frozenset({"rests"}),
        "guarding a nest": frozenset({"rests"}),
        "brooding over a clutch of luminous cysts": frozenset({"rests"}),
        "planting a survey marker in red dust": frozenset({"walks", "rests"}),
        "boring into rock with a heavy rock drill": frozenset({"rests", "walks"}),
        "grazing on radiant foliage": frozenset({"rests", "walks"}),
        "striding through waist-deep drifts": frozenset({"walks"}),
        "climbing a dune ridge at full throttle": frozenset({"rolls", "walks"}),
        "crawling along a canyon floor": frozenset({"rolls", "walks"}),
        "spinning a track in loose scree": frozenset({"rolls"}),
        "racing a storm front toward shelter": frozenset({"rolls", "walks"}),
        "hovering low over broken ground": frozenset({"hovers"}),
        "drifting on thermals above a canyon": frozenset({"flies", "hovers"}),
        "drifting slowly through the void": frozenset({"floats"}),
        "breaking orbit on a long burn": frozenset({"floats", "orbits"}),
        "settling onto the water on its belly": frozenset({"swims", "rests"}),
        "fording a shallow methane channel": frozenset({"swims", "rests"}),
        "leaking a slick across the water": frozenset({"floats", "rests"}),
    },
}


#: A collective quantifier needs something large enough to array things across.
#: ``scale`` is entity field index 2 and the count nouns are 11/13/17/19, so it
#: is already resolved when they draw, and the constraint pass re-draws the count
#: from a pool that still holds "a single" through "eight".
_QUANTIFIER_ARRAYS: tuple[str, ...] = ("a dozen", "rows of", "banks of", "a constellation of")
_QUANTIFIER_SMALL_SCALES: tuple[str, ...] = ("tiny", "small")
_QUANTIFIER_RULES: tuple[ConstraintRule, ...] = tuple(
    ConstraintRule(
        type=RULE_EXCLUDE,
        field="entity*.scale",
        values=_QUANTIFIER_SMALL_SCALES,
        excludes_field=f"entity*.{count_field}",
        excludes_values=_QUANTIFIER_ARRAYS,
        reason="a collective quantifier describes an industrial array, which needs "
               "something large enough to array things across",
    )
    # ``armament_count`` is counted small in every register -- its pool holds no
    # collective quantifier at all -- so it needs no rule; a rule with nothing to
    # exclude never fires.
    for count_field in ("appendage_count", "emitter_count", "sensor_count")
)


#: Traits a value asserts about the thing it is on, and the pairs that cannot
#: both be true of one entity. Authored as traits rather than as pairs of
#: values because the alternative is thirty colours times ten materials of
#: near-identical rules -- unreadable, and unmaintainable the first time a pool
#: grows. The engine never learns what a trait is: this table is expanded into
#: ordinary multi-value exclusion rules below.
#:
#: Direction matters and is chosen deliberately: the trigger stands and the
#: target gives way. A material outranks a colour (the substance is the stronger
#: visual claim); a subkind outranks a condition (the noun was drawn first and
#: scopes half the entity). A foreign-genre value carries no trait, so no rule
#: fires on it -- correct and intended, so nobody "fixes" this into a crash.
def _traits(*groups: tuple[str, tuple[str, ...]]) -> dict[str, tuple[str, ...]]:
    """Merge ``(trait, values)`` pairs into one ``{value: (trait, ...)}`` map.

    A value can carry several traits -- a firing situation is both a hostile
    act and a powered one -- so the groups are unioned rather than overwritten.
    """
    merged: dict[str, list[str]] = {}
    for trait, values in groups:
        for value in values:
            merged.setdefault(value, []).append(trait)
    return {value: tuple(traits) for value, traits in merged.items()}


VALUE_TRAITS: dict[str, dict[str, tuple[str, ...]]] = {
    "material": {
        # A material whose own name fixes its colour cannot also be given one.
        "polished chrome plate": ("self-coloured",),
        "obsidian-black composite": ("self-coloured",),
        "gold foil thermal blanket": ("self-coloured",),
        "chrome-finished casing": ("self-coloured",),
        "brushed alloy plate": ("self-coloured",),
        "brushed aluminium": ("self-coloured",),
        "black stone": ("self-coloured",),
        "gold-veined stone": ("self-coloured",),
        "polished obsidian": ("self-coloured",),
        "corroded bronze": ("self-coloured",),
        "meteoric iron": ("self-coloured",),
        "bleached brittle polymer": ("self-coloured",),
        "oxidised steel plate": ("self-coloured",),
        "slag-fused metal": ("self-coloured", "heat-scarred"),
        # A frozen surface cannot also be heat-scarred or overgrown.
        "frost-shattered hull plate": ("frost-bound",),
        "water ice": ("frost-bound",),
        "methane ice": ("frost-bound",),
        "ammonia ice": ("frost-bound",),
        "scorched ceramic tile": ("heat-scarred",),
        "molten rock": ("heat-scarred",),
        "fungus-grown plating": ("biological-overgrowth",),
        # An integument is dry or wet, never both.
        "fibrous bark-skin": ("dry-integument",),
        "scaled hide": ("dry-integument",),
        "leathery hide": ("dry-integument",),
        "mineral hide": ("dry-integument",),
        "translucent flesh": ("wet-integument",),
        "gelatinous membrane": ("wet-integument",),
        "resinous secretion": ("wet-integument",),
        "waxy cuticle": ("wet-integument",),
    },
    "primary_color": {
        value: ("states-a-colour",) for value in PRIMARY_COLOR_POOL
    },
    "surface_detail": {
        "ice fracture crazing": ("frost-bound",),
        "ice fissure networks": ("frost-bound",),
        "heat-bloom staining": ("heat-scarred",),
        "soot scoring": ("heat-scarred",),
        "sulphur crust flaking": ("heat-scarred",),
        "fungal mat growth": ("biological-overgrowth",),
        "overgrown with alien flora": ("biological-overgrowth",),
        "corrosion blooming": ("biological-overgrowth",),
        "damp mucous film": ("wet-integument",),
        "waxy sheen": ("wet-integument",),
        "translucent veining": ("wet-integument",),
        "fine bristled fuzz": ("dry-integument",),
        "pebbled hide texture": ("dry-integument",),
        "ridged chitin plating": ("dry-integument",),
    },
    # A wreck has no power, crew or intent, whatever its condition says.
    "subkind": {
        **{
            subkind: ("inactive",)
            for subkind in (
                SUBKIND_GROUPS["hull wreck"]
                + SUBKIND_GROUPS["structure wreck"]
                + SUBKIND_GROUPS["fragment wreck"]
            )
        },
        # Roles. A raider does not guide refugees; a combat mech does not haul
        # cargo; a mothballed hull does not stand guard.
        "raider": ("hostile-role",),
        "mercenary": ("hostile-role",),
        "smuggler": ("hostile-role",),
        "marauder": ("hostile-role",),
        "diplomat": ("pacifist-role",),
        "void order priest": ("pacifist-role",),
        "medic": ("pacifist-role", "medical-role"),
        "xenobiologist": ("pacifist-role",),
        "combat mech": ("combat-role",),
        "security automaton": ("combat-role",),
        "sentry unit": ("combat-role",),
        "warship": ("combat-role",),
        "dreadnought": ("combat-role", "inherently-vast"),
        "strike carrier": ("combat-role", "inherently-vast"),
        "interceptor": ("combat-role", "inherently-small"),
        "defence platform": ("combat-role",),
        "marine": ("combat-role",),
        "labour droid": ("labour-role",),
        "mining loader": ("labour-role",),
        "cargo hauler unit": ("labour-role",),
        "repair drone": ("labour-role", "inherently-small"),
        "terraforming walker": ("labour-role",),
        "salvage hauler": ("labour-role",),
        "ore hauler": ("labour-role",),
        "mining platform": ("labour-role",),
        "drydock cradle": ("labour-role",),
        "refuelling depot": ("labour-role",),
        "medical automaton": ("medical-role",),
        "hospital ship": ("medical-role",),
        "generation ship": ("inherently-vast",),
        "colony ship": ("inherently-vast",),
        "ring station": ("inherently-vast",),
        "arcology tower": ("inherently-vast",),
        "space elevator anchor": ("inherently-vast",),
        "orbital shipyard": ("inherently-vast",),
        "gate ring": ("inherently-vast",),
        "gas giant": ("inherently-vast",),
        "star": ("inherently-vast",),
        "courier drone": ("inherently-small",),
        "swarm drone": ("inherently-small",),
        "survey drone": ("inherently-small",),
        "hover bike": ("inherently-small",),
        "drop pod": ("inherently-small",),
        "data core": ("inherently-small",),
        "relic sphere": ("inherently-small",),
    },
    "scale": {
        "tiny": ("small-scale",),
        "small": ("small-scale",),
        "massive": ("large-scale",),
        "colossal": ("large-scale",),
        "planetary": ("large-scale",),
    },
    "condition": {
        # A thing in an ``inactive`` state has no crew and no power, whatever
        # noun is in front of it. Every wreck subkind carries it as well (see
        # ``DORMANT_ACTS`` at the end of the module).
        # The other end of the same axis: a thing that has just left the yard is
        # not simultaneously coming apart.
        "pristine": ("pristine-state",),
        "immaculate": ("pristine-state",),
        "freshly commissioned": ("pristine-state",),
        "newly repainted": ("pristine-state",),
        "freshly outfitted": ("pristine-state",),
        "mothballed": ("inactive",),
        "unfinished": ("inactive",),
        "half-built": ("inactive",),
        "half-disassembled": ("inactive",),
    },
    "situation": _traits(
        ("humanitarian", (
            "waving a straggler toward the airlock",
            "hauling a stretcher through a smoking corridor",
            "carrying an injured crewmember",
            "projecting a holographic star map from one palm",
            "making first contact with open hands",
        )),
        ("hostile-act", (
            "fleeing through an asteroid field",
            "firing a full weapons array at a closing formation",
            "launching interceptors from an open bay",
            "driving through a blockade line",
            "breaking apart under tidal stress",
            "repelling a boarding assault at the main lock",
            "shuttering its docks against an incoming barrage",
            "firing point-defence into a swarm",
            "stalking prey through the corridors",
            "watching from inside a ceiling vent",
            "striking at a fleeing shuttlecraft",
            "dragging a kill toward its burrow",
            "coiling its body into a tight spiral",
            "levelling a weapon at something off to one side",
            "taking cover behind a buckled bulkhead",
            "leading a boarding party through a cut hatch",
            "levelling its shoulder cannon",
            "pulling a damaged unit to cover",
            "trading shots across an open bay",
            "hunting through the rubble for movement",
            "cracking under a cutting beam",
            "being guarded by a flight of sentry drones",
            "taking hits from a ridge line",
            "charging across open ground with its ramp raised",
            "advancing across open ground",
            "ducking low and backing away",
            "standing over the wreckage of something else",
        )),
        ("labour-act", (
            "lifting a cargo container overhead",
            "welding a seam along a hull plate",
            "boring into rock with a heavy rock drill",
            "drilling a core sample from the bedrock",
            "unloading cargo onto a docking arm",
            "hauling a stripped hulk in a tractor beam",
            "nosing through a cloud of stirred-up silt",
            "swinging a cargo cradle out over open space",
            "planting sensor stakes in a grid",
            "lowering a cargo cradle onto a waiting hull",
        )),
        # ``powered-act`` is derived at the end of the module from
        # ``DORMANT_ACTS``: every situation not declared dormant carries it.
        # The subject is coming apart. Paired with ``pristine-state``: "a
        # freshly commissioned corvette is breaking up under a barrage" and "a
        # pristine terraforming station is bursting module after module".
        ("destruction-act", (
            "breaking up under a barrage along its central hull",
            "slewing hard as a hull section tears away",
            "cracking open along a seam in the hull",
            "spinning out with a thruster stuck open",
            "dumping fuel in a spreading cloud",
            "breaking in half across a failing frame",
            "shuddering under a direct hit",
            "breaking apart in a spreading cloud of debris",
            "shattering into a spray of fragments",
            "coming apart along one long seam",
            "breaking apart under tidal stress",
            "shearing in half along its central truss",
        )),
    ),
    "armament": {
        # Every weapon in a machine, vessel or crew pool is military, so a civilian
        # hull (``civilian-hull``) or a civil role (``civil-role``) excludes the
        # whole pool and the field resolves to nothing. The prose never says
        # "unarmed"; it simply says nothing about weapons.
        **{
            value: ("military-weapon",)
            for key in (
                "starship", "space station", "surface vehicle", "hovering", "legged",
                "robot or mech", "small drone", "heavy chassis", "humanoid unit",
                "static unit", "spacefarer",
            )
            for value in ARMAMENT_POOLS[key]
        },
        "flame projector": ("military-weapon", "heat-weapon"),
        "plasma cannon": ("military-weapon", "heat-weapon"),
    },
    "form": {
        "elongated bipedal torso": ("bipedal-plan",),
        "humanoid android frame": ("bipedal-plan",),
        "bipedal walker chassis": ("bipedal-plan",),
        "tripodal frame": ("bipedal-plan",),
        "four-armed bilateral body": ("bipedal-plan",),
    },
    "appendages": {
        "gripping foot pad": ("leg-appendage",),
        "spindly leg": ("leg-appendage",),
        "jointed limb": ("leg-appendage",),
        "jointed crawler leg": ("leg-appendage",),
    },
}

#: ``(trigger trait, target trait)`` pairs that cannot both hold of one entity.
VALUE_TRAITS["kind"] = {"celestial body": ("world-scale-subject",)}
VALUE_TRAITS[CONTEXT_FIELD] = {
    value: ("built-scenery",)
    for value in (
        "scatter of dead hulls", "distant station with a row of lights",
        "swarm of escort drones at a safe distance", "scatter of navigation beacons",
        "distant formation holding station", "single derelict turning end over end",
        "split hull of a vast derelict", "row of docking lights along a station arm",
        "distant orbital refinery", "field of slow-tumbling debris",
        "drifting cloud of hull fragments",
    )
}

#: A name that says "walker" is drawn walking on its legs; a chassis with no
#: legs cannot be one. The pair is a conflict, not a filter, so a locked value
#: still wins and says why.
VALUE_TRAITS["subkind"].update({
    "walker": ("legged-name",),
    "scout walker": ("legged-name",),
    "terraforming walker": ("legged-name", "labour-role"),
    "exosuit walker": ("legged-name",),
})
VALUE_TRAITS["form"].update({
    "serpentine segmented chassis": ("legless-plan",),
    "tracked chassis": ("legless-plan",),
    "boxy utility chassis": ("legless-plan",),
    "twin-armed hauler frame": ("legless-plan",),
    "hovering disc chassis": ("legless-plan",),
    "spherical drone body": ("legless-plan",),
    "wheeled drone body": ("legless-plan",),
})
#: A civilian hull carries no military weapon, and a civilian crew keeps only a
#: sidearm. The starship civilians carry ``civilian-hull`` so the broad weapon
#: pool is the thing that gives way, not the sidearm a scientist may keep.
VALUE_TRAITS["subkind"].update({
    "starliner": ("civilian-role", "civilian-hull"),
    "colony ship": ("civilian-role", "civilian-hull", "inherently-vast"),
    "generation ship": ("civilian-role", "civilian-hull", "inherently-vast"),
    "survey vessel": ("civilian-role", "civilian-hull"),
    "survey cutter": ("civilian-role", "civilian-hull"),
    "supply ship": ("civilian-role", "civilian-hull"),
    "scientist": ("civilian-role",),
    "colonist": ("civilian-role",),
    "archaeologist": ("civilian-role",),
    "cartographer": ("civilian-role",),
    "crew technician": ("civilian-role",),
})
# D13: a civilian machine carries no weapon and a civilian crew no heavy one.
for _value in (
    "rover", "hovercraft", "crawler", "skimmer", "submersible", "high-altitude glider",
    "tracked hauler", "landing shuttlecraft", "drop pod", "sand crawler", "ice cutter",
    "amphibious crawler", "cargo sled", "survey glider", "survey drone", "courier drone",
    "welding drone",
):
    VALUE_TRAITS["subkind"][_value] = tuple(
        VALUE_TRAITS["subkind"].get(_value, ())
    ) + ("civilian-hull",)
for _value in ("salvager", "prospector", "engineer", "navigator", "quartermaster"):
    VALUE_TRAITS["subkind"][_value] = tuple(
        VALUE_TRAITS["subkind"].get(_value, ())
    ) + ("civilian-role",)
# D15: the humanoid alien people carry a role like any other person.
VALUE_TRAITS["subkind"].update({
    "amphibian admiral": ("combat-role",),
    "horned warlord": ("combat-role",),
    "mandibled envoy": ("pacifist-role",),
    "reptilian bounty hunter": ("hostile-role",),
    "tusked mercenary": ("hostile-role",),
    "grey-skinned archivist": ("civilian-role",),
    "four-armed quartermaster": ("civilian-role",),
    "translucent medic": ("pacifist-role", "medical-role"),
})
VALUE_TRAITS["armament"].update({
    "shoulder-mounted missile tube": ("military-weapon", "heavy-weapon"),
    "plasma charge harness": ("military-weapon", "heavy-weapon"),
    "magnetic slug thrower": ("military-weapon", "heavy-weapon"),
    "shoulder-braced arc lance": ("military-weapon", "heavy-weapon"),
})
VALUE_TRAITS[SITUATION_FIELD].update({
    "firing a full weapons array at a closing formation": ("hostile-act", "attack-act"),
    "launching interceptors from an open bay": ("hostile-act", "attack-act"),
    "firing point-defence into a swarm": ("hostile-act", "attack-act"),
    "standing guard over a column of civilian starships": ("attack-act",),
})
#: A room with furniture in it is a tabletop for anything small.
VALUE_TRAITS[ENVIRONMENT_FIELD] = {
    value: ("furnished-room",)
    for value in ("crew commons", "crew quarters", "medical bay", "chapel", "brig")
}
# A heavy frame fills a cramped room; a massive thing reads as a tabletop there.
for _value in (
    "cockpit interior", "maintenance crawlway", "airlock chamber", "observation cupola",
    "crew quarters", "brig", "spacecraft corridor", "subterranean moon base corridor",
    "cryogenic stasis bay", "data vault", "medical bay", "chapel", "crew commons",
    # Round XIII: the rooms the first pass missed. An armoury is a corridor with
    # racks on the walls -- "an alien creature in a starship weapons armoury"
    # was reported twice -- and a bridge, an engine room and a hydroponics bay
    # are all rooms you can touch both walls of.
    "armoury", "cargo hold", "hydroponics bay", "spacecraft bridge",
    "spacecraft engine room", "reactor hall", "alien hive resin chamber",
):
    VALUE_TRAITS[ENVIRONMENT_FIELD][_value] = tuple(
        VALUE_TRAITS[ENVIRONMENT_FIELD].get(_value, ())
    ) + ("cramped-room",)
for _value in (
    "exosuit walker", "siege mech", "terraforming walker", "mining loader", "combat mech",
    "scout walker", "cargo hauler unit",
):
    VALUE_TRAITS["subkind"][_value] = tuple(
        VALUE_TRAITS["subkind"].get(_value, ())
    ) + ("heavy-frame",)
# A sealed garment and an open face cannot be drawn on the same person.
VALUE_TRAITS.setdefault("material", {})
for _value in (
    "canvas-weave vac suit", "armour-composite hardsuit", "ceramic hardsuit",
    "much-repaired vac suit", "thermal-lined pressure suit", "impact-gel armour suit",
    "polymer soft-suit",
):
    VALUE_TRAITS["material"][_value] = tuple(
        VALUE_TRAITS["material"].get(_value, ())
    ) + ("sealed-helmet",)
VALUE_TRAITS.setdefault("aperture", {})
for _value in ("open visor", "hood opening", "respirator grille", "breathing mask vent"):
    VALUE_TRAITS["aperture"][_value] = ("open-face",)
# Anything else that asserts a helmet on a person carries the same trait, so the
# conflict reaches the markings, the fittings and the action as well as the suit.
for _field, _value in (
    ("markings", "painted helmet stripes"),
    ("emitters", "helmet visor strip"),
    ("emitters", "helmet beacon"),
    (SITUATION_FIELD, "sweeping a helmet beam across a derelict hull"),
):
    VALUE_TRAITS.setdefault(_field, {})
    VALUE_TRAITS[_field][_value] = tuple(
        VALUE_TRAITS[_field].get(_value, ())
    ) + ("sealed-helmet",)

TRAIT_CONFLICTS: tuple[tuple[str, str], ...] = (
    ("self-coloured", "states-a-colour"),
    ("frost-bound", "heat-scarred"),
    ("frost-bound", "biological-overgrowth"),
    ("heat-scarred", "biological-overgrowth"),
    ("dry-integument", "wet-integument"),
    ("hostile-role", "humanitarian"),
    ("pacifist-role", "hostile-act"),
    ("pacifist-role", "military-weapon"),
    ("combat-role", "labour-act"),
    ("labour-role", "hostile-act"),
    ("labour-role", "military-weapon"),
    ("medical-role", "hostile-act"),
    ("medical-role", "military-weapon"),
    ("medical-role", "heat-weapon"),
    ("world-scale-subject", "built-scenery"),
    ("inactive", "powered-act"),
    ("heat-weapon", "frost-bound"),
    ("inherently-vast", "small-scale"),
    ("inherently-small", "large-scale"),
    ("bipedal-plan", "leg-appendage"),
    ("legged-name", "legless-plan"),
    ("civilian-role", "attack-act"),
    ("civilian-role", "heavy-weapon"),
    ("civilian-hull", "military-weapon"),
    ("furnished-room", "small-scale"),
    ("sealed-helmet", "open-face"),
    ("cramped-room", "heavy-frame"),
    ("cramped-room", "large-scale"),
)

#: One sentence per conflict, in the pack's own voice. A reason may negate --
#: it is the pack's one deliberate exemption -- but it never quotes a pool value.
_TRAIT_REASONS: dict[str, str] = {
    "world-scale-subject|built-scenery":
        "a world shrinks built scenery beside it to a toy",
    "self-coloured|states-a-colour":
        "a material that already names its own colour fixes it, so a separate "
        "primary colour would contradict the substance",
    "frost-bound|heat-scarred":
        "a surface cannot be frozen and heat-scarred at once",
    "frost-bound|biological-overgrowth":
        "a surface cannot be frozen and overgrown at once",
    "heat-scarred|biological-overgrowth":
        "a surface cannot be heat-scarred and overgrown at once",
    "dry-integument|wet-integument":
        "an integument cannot be dry and wet at once",
    "hostile-role|humanitarian":
        "a raider does not guide refugees",
    "pacifist-role|hostile-act":
        "a diplomat does not fire on anything",
    "pacifist-role|military-weapon":
        "a medic does not carry a weapon",
    "combat-role|labour-act":
        "a combat machine does not haul cargo",
    "labour-role|hostile-act":
        "a labour machine does not fight",
    "labour-role|military-weapon":
        "a labour machine does not carry a weapon",
    "medical-role|hostile-act":
        "a medical machine does not fight",
    "medical-role|military-weapon":
        "a medical machine does not carry a weapon",
    "medical-role|heat-weapon":
        "a medical machine does not carry a flame projector",
    "inactive|powered-act":
        "a wreck or a mothballed thing has no power, crew or intent to act",
    "inactive|emissive":
        "a wreck or a mothballed thing has no power to light anything",
    "heat-weapon|frost-bound":
        "a frozen surface cannot carry a heat weapon",
    "inherently-vast|small-scale":
        "a vast thing is never drawn at a small scale",
    "inherently-small|large-scale":
        "a small thing is never drawn at a large scale",
    "bipedal-plan|leg-appendage":
        "a biped does not grow a set of extra legs",
    "legged-name|legless-plan":
        "a thing named for its legs walks on them",
    "civilian-role|attack-act":
        "a civilian crew does not fight",
    "civilian-role|heavy-weapon":
        "a civilian does not carry a heavy weapon",
    "civilian-hull|military-weapon":
        "a civilian hull carries no military weapon",
    "furnished-room|small-scale":
        "a small thing in a furnished room is drawn on the furniture",
    "sealed-helmet|open-face":
        "a sealed helmet leaves the face closed",
    "cramped-room|heavy-frame":
        "a heavy frame does not fit a cramped room",
    "cramped-room|large-scale":
        "a massive thing does not fit a cramped room",
}




CONSTRAINTS: tuple[ConstraintRule, ...] = (
    _SCALE_RULES
    + _RELATION_RULES
    + _QUANTIFIER_RULES
)


# ---------------------------------------------------------------------------
# Prose shape
# ---------------------------------------------------------------------------

PROSE = ProseSpec(
    scene_order=("environment", "entities", "relations"),
    # Narrative mode: the renderer composes the scene into connected prose
    # instead of a sentence per section -- the environment is its own setting
    # sentence ("Set in ..."), each entity is a subject + conjugated predicate,
    # and each relation is a standalone sentence naming both endpoints and an
    # optional spatial position ("the scout ship is attacking the heavy
    # freighter, from behind").
    narrative_mode=True,
    # The genre frame. Every noun in "a large battle-scarred warship with a
    # T-shaped prow hull" is also a naval noun, and a prompt that never says
    # what kind of world it is gets drawn as whatever its nouns most commonly
    # mean. Naming the genre once, in the sentence that was already establishing
    # the setting, costs three tokens.
    #
    # It is a **frame**, not appended scenery. A genre described as a trailing
    # noun phrase reads as one more thing in the scene -- the failure recorded
    # in ``t2i-prose-needs-a-rendering-frame`` -- so it is a connective in the
    # opening sentence rather than a clause bolted to the end.
    environment_sentence="A science fiction scene set in {a_value}",
    # A model grounds whatever it is not told floats. A station in a debris belt
    # is drawn standing on the debris; a submersible in a trench is drawn on a
    # beach. The first affordance the place has stages the sentence.
    environment_staging=(
        ("open-space", ", out in open space"),
        ("submerged", ", deep underwater"),
        ("cloud-deck", ", far above the planet's surface"),
    ),
    # A framing that needs distance says so. "In the distance, a stack of sealed
    # cargo pods is visible" inside a cockpit was the report: the context value
    # was right for the place and the *framing* was not, so this is a property of
    # the sentence rather than of the pool. The neutral patterns below carry no
    # need and are what a room draws from.
    #
    # Round XIV: a framing names *where* the context is, never how it holds
    # itself up. "A ladder crowds in close", "a trail of vapour stands further
    # back" and "a derelict stands" in open space were each a stance the template
    # imposed on a value that has its own; the validator's context-sentence check
    # fails a template that brings a stance verb back.
    context_sentences=(
        Sentence(text="Beyond {pronoun_object}, {a_context} is visible."),
        Sentence(text="Behind {pronoun_object} is {a_context}."),
        Sentence(text="{a_context} is visible behind {pronoun_object}."),
        Sentence(text="Past {pronoun_object}, {a_context} catches the light."),
        Sentence(text="The background shows {a_context}."),
        Sentence(text="In the distance, {a_context} is visible.",
                 needs=frozenset({"vast"})),
        Sentence(text="Further back, {a_context} is visible.", needs=frozenset({"vast"})),
        Sentence(text="Far behind {pronoun_object} is {a_context}.",
                 needs=frozenset({"vast"})),
    ),
    scene_frame="A science fiction scene",
    copula="is",
    copula_plural="are",
    pronoun="it",
    pronoun_plural="they",
    # ``descriptor_lead`` is only reached by the single-sentence fallback below
    # (a pack with no ``entity_sentences``, or an entity whose head noun was
    # cut). The shipped shape is the four-sentence plan.
    descriptor_lead="with",
    # ------------------------------------------------------------------
    # The sentence plan
    # ------------------------------------------------------------------
    #
    # Every entity is spoken by its archetype's patterns; a pattern is a whole
    # English sentence with holes (see ``Sentence``). The pack declares none of
    # its own because every kind reaches an archetype, and the archetype is
    # where the grammar belongs -- a hull is not "covered in" its plating and a
    # creature is. The empty tuple here is the fallback for an entity that
    # reaches no archetype at all: it renders through the single-sentence shape,
    # which is what keeps a pack with no prose authoring renderable.
    entity_sentences=(),
    # Sixteen clause heads: the 21 fields minus the five composed into another
    # (the four counts and the emitter colour). Identity first, then the body,
    # then its surface, then what is attached to it -- so an entity reads the
    # way you would describe one out loud.
    entity_clause_order=(
        "kind",
        "subkind",
        "scale",
        "condition",
        "form",
        "material",
        "primary_color",
        "accent_color",
        "surface_detail",
        "markings",
        "appendages",
        "emitters",
        "armament",
        "sensors",
        "aperture",
        "extras",
    ),
    subject_leading_kinds=frozenset({"alien creature"}),
    # ------------------------------------------------------------------
    # The opening noun phrase
    # ------------------------------------------------------------------
    #
    # Default: the subkind is the noun and the kind gives way to it -- "a large
    # battle-scarred heavy freighter" says "starship" already, so voicing the kind
    # as well would only spend tokens. ``kind`` stays in the chain as the
    # fallback for an entity whose subkind is set to None.
    #
    # Creature: the body plan is *promoted* to the head noun and nothing is
    # spoken in front of it. "a creature with a segmented worm body" reliably
    # draws a human holding a worm; "a segmented worm body, insectoid, massive"
    # draws the animal. The creature type and its scale and condition follow as
    # clauses instead of leading as adjectives, which is why the creature clause
    # order below opens with ``form``; ``ProseSpec`` cross-checks the two
    # declarations against each other, so this cannot quietly stop being true.
    #
    # The ladder underneath is the same as every other kind's, and it is what a
    # brief supporting slot falls back on: slots 2-4 never draw a ``form``, so a
    # background creature reads "a large parasitic brood" rather than losing its
    # head noun to the generic kind.
    head_phrase={
        POOL_DEFAULT_KEY: HeadPhrase(
            noun=("subkind", "kind"),
            modifiers=("scale", "condition"),
        ),
        "alien creature": HeadPhrase(
            noun=("subkind", "kind"),
            modifiers=("scale", "condition"),
            subject="form",
        ),
    },
    # ------------------------------------------------------------------
    # What a tight budget keeps
    # ------------------------------------------------------------------
    #
    # Deliberately NOT the clause order. Clause order is what reads well; this is
    # what survives when only three fields fit, and the two want different
    # things. The F5 gate asks whether twenty seeds produce visibly different
    # ship silhouettes, engine counts, glow colours, weapon loadouts and alien
    # anatomies -- so the five fields that answer it (``form``, ``emitters``
    # with its count and colour, ``armament``, ``sensors``, plus the type that
    # names the thing) are priced above the fields that only tint it. Pricing by
    # clause order instead would keep ``subkind``, ``scale`` and ``condition``
    # at Sparse and drop every one of the five, which is the default level
    # failing the point of the pack.
    #
    # ``kind`` is absent on purpose: it is the spine, never cut. It scopes every
    # other pool and it is the fallback head noun, so an entity without it is
    # not a leaner entity, it is a nameless one.
    # ``condition`` and ``scale`` sit above the component fields, which is a
    # change from the first ordering and was forced by measurement rather than
    # taste. They used to sit at index 9 and 6, which was survivable while a
    # supporting slot only had four fields to choose between -- they were the
    # only candidates, so they always won. Once a supporting slot drew its whole
    # morphology they lost every contest and stopped reaching any slot but the
    # hero: "no large creature was drawn in 400 seeds" is what that looked like
    # from the kaiju test, and a sweep showed `condition` reaching nothing.
    #
    # They earn the place on their own merits too. Both are single words with
    # outsized effect -- "derelict", "colossal" re-frame a whole image -- and
    # both are what makes a *supporting* slot read as a particular thing rather
    # than a generic one. The five fields the F5 gate measures all still land
    # inside the hero's allowance, which is what that gate actually asks.
    detail_priority=(
        "form",
        "subkind",
        "emitters",
        "primary_color",
        "condition",
        "scale",
        "armament",
        "sensors",
        "material",
        "appendages",
        "aperture",
        "markings",
        "surface_detail",
        "accent_color",
        "extras",
    ),
    # Hull colour belongs to a surface, not to the air. Folded onto the material
    # it is painted on ("gunmetal grey titanium alloy"), or onto the silhouette
    # when no material is standing ("a gunmetal grey needle hull"), and only
    # spoken alone when neither survived the budget.
    adjective_of={"primary_color": ("material", "form")},
    # ------------------------------------------------------------------
    # Clause templates
    # ------------------------------------------------------------------
    #
    # Article-less pool values in, English out. ``{a_value}`` articles a value
    # only when its head noun is singular, so one template covers "a cargo pod"
    # and "hazard chevrons" alike.
    #
    # Wording constraints these had to satisfy, both of which cost a first
    # draft: nothing here may contain a rendering term (no "glowing", no "lit
    # by" -- an emitter's colour is voiced as a plain adjective on the emitter,
    # "six cyan ion thrusters"), and nothing may negate.
    templates={
        # Scene
        ENVIRONMENT_FIELD: "{a_value}",
        SITUATION_FIELD: "{value}",
        RELATION_FIELD: "{first} is {value} {second}",
        # Entity -- the fields the head phrase does not consume
        "kind": "{a_value}",
        "subkind": "{a_value}",
        "scale": "{value}",
        "condition": "{value}",
        "form": "{a_value}",
        "primary_color": "{value}",
        "accent_color": "{value} accents",
        "surface_detail": "{value}",
        "markings": "{value}",
        "appendages": "{value}",
        "emitters": "{value}",
        "armament": "{value}",
        "sensors": "{value}",
        "aperture": "{a_value}",
        "extras": "{a_value}",
    },
)


# ---------------------------------------------------------------------------
# Todo 11 -- content-filter tags
# ---------------------------------------------------------------------------
#
# Exactly one tag on every value of the five ``tag_scoped`` fields -- ``subkind``,
# ``armament``, ``aperture``, ``situation``, ``relation`` -- and on nothing else.
# ``environment``, ``condition``, ``scale``, ``material``, ``form`` and the
# colours are untagged on purpose: a red hull is not more or less peaceful, and
# tagging them would only make the filter quietly shrink pools it has no opinion
# about.
#
# What each tag means, stated once so a later author does not have to infer it
# from the entries:
#
# ``conflict_only``  the value asserts violence, threat, or its immediate
#                    aftermath. Dropped when the user asks for Peaceful.
# ``peaceful_only``  the value asserts calm, care, trade or routine that a
#                    Conflict scene would contradict. Dropped when the user asks
#                    for Conflict.
# ``neutral``        true in either kind of scene. Most of the pack.
#
# **Peaceful means no weapons are described, never that the subject is
# "unarmed".** Every ``armament`` value is ``conflict_only``, so under Peaceful
# that pool masks to empty, the field resolves to ``None``, and the prose simply
# says nothing about weapons. Its count partner is composed into its clause and
# so is not voiced either. That is the whole mechanism, and it is why the tag
# generator below tags armament wholesale rather than value by value: a weapon
# added later must inherit the rule, not wait to be noticed.
#
# ``subkind`` carries no ``peaceful_only`` value, and that is a decision rather
# than an oversight: what a thing *is* does not forbid a fight happening around
# it -- a passenger liner, a hospital ship and a monastery are all better subjects in a
# battle, not worse. What a thing *does* (``situation``) and what it *carries*
# (``armament``) is where peacefulness actually lives.


def _tag_map(
    *pools: tuple[str, ...] | dict[str, tuple[str, ...]],
    conflict: tuple[str, ...] = (),
    peaceful: tuple[str, ...] = (),
) -> dict[str, str]:
    """Tag every value of a field, defaulting to ``neutral``.

    Raises on a name in ``conflict``/``peaceful`` that is not a real value of
    the field. A typo would otherwise be silently ignored and the value it meant
    to tag would keep drawing under the wrong filter -- an authoring bug that
    only ever shows up as "the Peaceful scenes look violent sometimes".
    """
    values: dict[str, None] = {}
    for pool in pools:
        for group in (pool.values() if isinstance(pool, dict) else (pool,)):
            for value in group:
                values.setdefault(value, None)
    unknown = sorted((set(conflict) | set(peaceful)) - set(values))
    if unknown:
        raise ValueError(f"tagged values that are not in the pool: {unknown}")
    overlap = sorted(set(conflict) & set(peaceful))
    if overlap:
        raise ValueError(f"values tagged both conflict_only and peaceful_only: {overlap}")
    return {
        value: (
            TAG_CONFLICT_ONLY if value in conflict
            else TAG_PEACEFUL_ONLY if value in peaceful
            else TAG_NEUTRAL
        )
        for value in values
    }


_SITUATION_CONFLICT = (
    # vessel
    "fleeing through an asteroid field",
    "firing a full weapons array at a closing formation",
    "launching interceptors from an open bay",
    "driving through a blockade line",
    "breaking up under a barrage along its central hull",
    "slewing hard as a hull section tears away",
    "cracking open along a seam in the hull",
    "spinning out with a thruster stuck open",
    "dumping fuel in a spreading cloud",
    "breaking in half across a failing frame",
    "shuddering under a direct hit",
    "landing hard with its gear folding",
    "ploughing a trench through the ground on impact",
    "scraping along a canyon wall",
    # celestial body
    "breaking apart under tidal stress",
    "swallowing a small ochre moon in a single pass",
    "detonating in a shell of expanding gas",
    # station or structure
    "repelling a boarding assault at the main lock",
    "shuttering its docks against an incoming barrage",
    "firing point-defence into a swarm",
    "shearing in half along its central truss",
    "being swarmed by small starships at every docking arm",
    "tumbling out of its rotation",
    "cracking open along a docking arm",
    "collapsing into a trailing field of wreckage",
    "spilling a white plume from a ruptured hull",
    # creature or being
    "stalking prey through the corridors",
    "watching from inside a ceiling vent",
    "striking at a fleeing shuttlecraft",
    "dragging a kill toward its burrow",
    "coiling its body into a tight spiral",
    "tearing into a fallen hull",
    "spitting a stream of caustic bile",
    "clamping its jaws shut with a crack",
    "slamming its whole bulk down",
    "breaking out of a containment field with a single lunge",
    "bursting through a sealed door",
    "snapping at the air in a sudden strike",
    "lunging with its jaws flung wide",
    "dragging a survivor into the dark",
    # person or spacefarer
    "levelling a weapon at something off to one side",
    "taking cover behind a buckled bulkhead",
    "leading a boarding party through a cut hatch",
    "fighting off a boarder at the airlock",
    "severing a snarl of cabling",
    "carrying a child through a smoke-filled corridor",
    "sealing a breach as the air thins",
    "running through a collapsing gantry",
    "diving clear of a falling beam",
    "cutting through a jammed airlock with a torch",
    "shouldering a buckling bulkhead back into place",
    "catching a falling colleague by the wrist",
    "holding a door against a rush of pressure",
    # robot or mech
    "levelling its shoulder cannon",
    "pulling a damaged unit to cover",
    "trading shots across an open bay",
    "hunting through the rubble for movement",
    "going down under a mass of smaller units",
    "tearing a hatch off its hinges",
    "falling from a gantry",
    "holding a collapsing wall up with its shoulders",
    # artifact or object
    "cracking under a cutting beam",
    "being guarded by a flight of sentry drones",
    "tearing open along a line of light",
    "pulling a spiral of loose rubble toward its base",
    "going dark all at once",
    "bursting in a wave of light",
    "collapsing into a singularity",
    "drawing loose debris off the deck toward itself",
    "swallowing a survey drone whole",
    "cracking the ground beneath it",
    "pulling a descending lander out of the sky",
    # vehicle
    "taking hits from a ridge line",
    "charging across open ground with its ramp raised",
    "bursting a hub against an obstacle",
    "snapping an axle on a hard landing",
    "ramming a barricade at full speed",
    "rolling down a slope out of control",
    # wreck or derelict
    "being cut open by salvage drones",
    "collapsing under its own weight",
    "slumping as a spar gives way",
    "breaking apart in a slow avalanche",
    "shedding a slab of plating as it settles",
    "tearing open along a rusted seam",
    "pinning a salvage drone beneath a buckled plate",
    "giving way under a salvage drone's cutting beam",
    "burying a salvage crawler in a slide",
    # _default
    "advancing across open ground",
    "ducking low and backing away",
    "standing over the wreckage of something else",
    "breaking apart in a spreading cloud of debris",
    "shattering into a spray of fragments",
    "fleeing in a hard turn",
    "flaring in a single hard pulse",
    "tearing loose from a docking clamp",
)
# Round XII: a rooted body reaches and engulfs, and the engulfing is a threat.
_SITUATION_CONFLICT = _SITUATION_CONFLICT + (
    "snapping shut in a sudden spasm",
    "lashing out with stinging fronds",
    "curling its fronds inward around its prey",
    "closing on its prey in a sudden rush",
    "wrapping its fronds tight around its own stalk",
    "unfurling a snare of sticky filaments",
)

#: The creature body-plan split, as cards. A drifting or rooted body has no
#: limb, so these values are the whole vocabulary those bodies can draw from
#: beside the shared core.
SITUATION_TIERS.update({
    "stretching after a long rest": "activity",
    "shivering along its length": "activity",
    "twitching in its sleep": "idle",
    "flowing across a hull as one body": "activity",
    "swarming up a docking spar": "event",
    "releasing a slow drift of spores": "activity",
    "shaking loose a cloud of spores": "event",
    "spreading its membranes wide in a flat fan": "event",
    "spreading across a landing platform": "activity",
    "curling into a tight knot of light": "activity",
    "streaming away in a long luminous ribbon": "event",
    "enveloping a drifting hull plate": "event",
    "pulsing in slow waves of light": "idle",
    "spreading into a thin luminous veil": "activity",
    "drawing a thread of light out of a passing comet": "event",
    "shifting through a spectrum of colours": "idle",
    "folding its body inward in a slow pulse": "event",
    "seeping through a bulkhead in slow tendrils": "activity",
    "trailing a long ribbon of ionised gas": "event",
    "paling to a soft sheen": "idle",
    "gathering itself out of a drifting veil": "event",
    "sweeping a wide arc of light across a hull": "event",
    "sinking into a still pool of light": "activity",
    "wrapping around a derelict's hull": "event",
    "flickering across a whole hull": "idle",
    "unfurling a ring of luminous fronds": "activity",
    "snapping shut in a sudden spasm": "event",
    "lashing out with stinging fronds": "event",
    "curling its fronds inward around its prey": "event",
    "reaching out a ring of tendrils": "activity",
    "closing on its prey in a sudden rush": "event",
    "unfurling into a broad fan": "activity",
    "wrapping its fronds tight around its own stalk": "event",
    "spreading into a broad mat": "activity",
    "unfurling a snare of sticky filaments": "event",
    "settling into a slow pulse": "idle",
})
VALUE_NEEDS["situation"].update({
    "stretching after a long rest": frozenset(),
    "shivering along its length": frozenset(),
    "twitching in its sleep": frozenset(),
    "flowing across a hull as one body": frozenset(),
    "swarming up a docking spar": frozenset(),
    "releasing a slow drift of spores": frozenset(),
    "shaking loose a cloud of spores": frozenset(),
    "spreading its membranes wide in a flat fan": frozenset(),
    "spreading across a landing platform": frozenset(),
    "curling into a tight knot of light": frozenset(),
    "streaming away in a long luminous ribbon": frozenset(),
    "enveloping a drifting hull plate": frozenset(),
    "pulsing in slow waves of light": frozenset(),
    "spreading into a thin luminous veil": frozenset(),
    "drawing a thread of light out of a passing comet": frozenset(),
    "shifting through a spectrum of colours": frozenset(),
    "folding its body inward in a slow pulse": frozenset(),
    "seeping through a bulkhead in slow tendrils": frozenset(),
    "trailing a long ribbon of ionised gas": frozenset(),
    "paling to a soft sheen": frozenset(),
    "gathering itself out of a drifting veil": frozenset(),
    "sweeping a wide arc of light across a hull": frozenset(),
    "sinking into a still pool of light": frozenset(),
    "wrapping around a derelict's hull": frozenset(),
    "flickering across a whole hull": frozenset(),
    "unfurling a ring of luminous fronds": frozenset(),
    "snapping shut in a sudden spasm": frozenset(),
    "lashing out with stinging fronds": frozenset(),
    "curling its fronds inward around its prey": frozenset(),
    "reaching out a ring of tendrils": frozenset(),
    "closing on its prey in a sudden rush": frozenset(),
    "unfurling into a broad fan": frozenset(),
    "wrapping its fronds tight around its own stalk": frozenset(),
    "spreading into a broad mat": frozenset(),
    "unfurling a snare of sticky filaments": frozenset(),
    "settling into a slow pulse": frozenset(),
    "crawling up a vertical face": frozenset({"gravity"}),
    "swelling in slow pulses across its face": frozenset(),
    "settling into a slower spin": frozenset(),
    "rotating through a slow cycle": frozenset(),
    "tilting slowly on its axis": frozenset(),
    "settling into a calm band": frozenset(),
    "paling along one flank": frozenset(),
    "flickering across its whole disc": frozenset(),
    "shedding a thin veil of gas": frozenset(),
    "thinning into a pale band": frozenset(),
    "swallowing a nearby star in a single gulp": frozenset(),
    "rippling in slow waves across its bands": frozenset(),
    "collapsing into a dense knot of newborn stars": frozenset(),
})
# Round XII: the three reach-floor additions.
SITUATION_TIERS.update({
    "swelling in slow pulses across its face": "activity",
    "settling into a slower spin": "activity",
    "rotating through a slow cycle": "activity",
    "tilting slowly on its axis": "activity",
    "settling into a calm band": "activity",
    "paling along one flank": "activity",
    "flickering across its whole disc": "activity",
    "shedding a thin veil of gas": "activity",
    "thinning into a pale band": "activity",
    "swallowing a nearby star in a single gulp": "event",
    "rippling in slow waves across its bands": "event",
    "collapsing into a dense knot of newborn stars": "event",
})
VALUE_NEEDS["situation"].update({
    "swallowing a nearby star in a single gulp": frozenset(),
    "rippling in slow waves across its bands": frozenset(),
    "collapsing into a dense knot of newborn stars": frozenset(),
})

_SITUATION_PEACEFUL = (
    # vessel
    "unloading cargo onto a docking arm",
    "taking on fuel from a refuelling starship's boom",
    "deploying survey drones in a spreading fan",
    "holding station beside a survey beacon",
    "standing guard over a column of civilian starships",
    # celestial body
    "being mined by a swarm of salvage drones",
    # station or structure
    "swinging a cargo cradle out over open space",
    "extending a new module on assembly arms",
    "berthing rows of small spacecraft along its central truss",
    "lowering a cargo cradle onto a waiting hull",
    "carrying a cage of refit scaffolding",
    # creature or being
    "flexing a freshly moulted outer skin",
    "brooding over a clutch of luminous cysts",
    "guarding a nest",
    "grazing on radiant foliage",
    "spinning a resin nest between girders",
    "drifting on thermals above a canyon",
    # person or spacefarer
    "making first contact with open hands",
    "running a diagnostic on an open panel",
    "projecting a holographic star map from one palm",
    "planting a survey marker in red dust",
    # robot or mech
    "welding a seam along a hull plate",
    "lifting a cargo container overhead",
    "powering down into a maintenance cradle",
    "boring into rock with a heavy rock drill",
    "planting sensor stakes in a grid",
    "clearing debris from a blocked hatch",
    # artifact or object
    "projecting a chart of unmapped space",
    "being lifted onto a recovery cradle",
    "being circled by scanning drones",
    "bending a nearby survey mast toward itself",
    # vehicle
    "towing a string of cargo pods across a salt flat",
    "pulling up beside a supply dome",
    "unloading cargo pods onto a landing pad",
    "nosing through a cloud of stirred-up silt",
    "drilling a core sample from the bedrock",
    "waiting with its ramp down and cabin open",
    # wreck or derelict
    "being stripped by a swarm of salvage drones",
    "being surveyed by a drifting inspection drone",
    # _default
    "being examined by a survey drone",
)

#: A type that exists to fight. Dropped under Peaceful -- and note that leaving
#: one in would be worse than dropping it, because Peaceful also strips its
#: weapons: a dreadnought with no armament described is a duller image than no
#: dreadnought at all.
_SUBKIND_CONFLICT = (
    "warship", "dreadnought", "strike carrier", "interceptor", "troop transport",
    "defence platform", "prison station", "parasitic brood", "marine",
    "mercenary", "raider", "marauder", "combat mech", "security automaton", "sentry unit", "drop pod",
    "burnt-out star cruiser", "shattered interceptor",
)

#: An opening that is a weapon port, or a mouth whose whole design is predation.
#: A beak, a filter slit and a proboscis stay neutral: eating is not violence.
_APERTURE_CONFLICT = (
    "missile hatch", "gun port", "ammunition port",
    "circular toothed maw", "fanged jaw", "mandibled jaw",
)

_RELATION_CONFLICT = ("attacking", "fleeing from", "pursuing", "creeping toward",
                     "looming over", "towering over", "dwarfing", "shadowing", "closing on")


TAGS: dict[str, dict[str, str]] = {
    "subkind": _tag_map(SUBKIND_POOLS, conflict=_SUBKIND_CONFLICT),
    # Wholesale, by construction: every weapon is conflict-tagged, so a weapon
    # added in a later session inherits the Peaceful rule instead of quietly
    # surviving it.
    "armament": _tag_map(ARMAMENT_POOLS, conflict=tuple(
        value for pool in ARMAMENT_POOLS.values() for value in pool
    )),
    "aperture": _tag_map(APERTURE_POOLS, conflict=_APERTURE_CONFLICT),
    SITUATION_FIELD: _tag_map(
        SITUATION_POOLS,
        conflict=_SITUATION_CONFLICT,
        peaceful=_SITUATION_PEACEFUL,
    ),
    RELATION_FIELD: _tag_map(RELATION_POOL, conflict=_RELATION_CONFLICT),
}



# ---------------------------------------------------------------------------
# Archetypes -- how each category of thing is spoken
# ---------------------------------------------------------------------------
#
# ``kind`` decides what an entity is drawn *from*. An archetype decides how the
# result is *said*, and the two turned out not to be the same axis.
#
# The symptom was everywhere in the output: a nebula "clad in hydrogen and
# helium cloud", a black hole with an impact crater basin, a spacefarer "clad
# in" their own suit. ``ProseSpec.templates`` had no kind dimension at all, so
# "clad in {value}" was the only thing the contract could say about a material,
# whether that material was armour plate, a hide, a suit or a gas.
#
# The pack already knew the missing categories. It had them five times over as
# module-private tuples -- ``_LIVING_KINDS``, ``_MOVABLE_KINDS``,
# ``_DIFFUSE_CELESTIAL_SUBKINDS`` and friends -- each able only to delete values
# from a pool. Those tuples are still here and still generate their constraint
# rules; what is new is that the same categories can now change a word.
#
# Nine archetypes for nine kinds is nearly one-to-one, and that is a fact about
# this genre rather than the shape of the idea. The two places it is *not*
# one-to-one are the two that mattered:
#
#   * ``celestial body`` splits. A moon is a ``world`` with a crust; a nebula is
#     a ``phenomenon`` with no surface to describe at all.
#   * ``alien creature`` splits the same way and for the same reason -- an
#     energy being has no integument either.
#
# That split is what ``archetype_override_field`` exists for, and it is why the
# override is keyed on ``subkind`` rather than on a tenth kind: a black hole and
# a rocky planet belong in the same dropdown, just not in the same sentence.

#: The head phrase every *made* thing shares: the specific type is the noun and
#: the category follows it as an apposition.
#:
#: The apposition is the fix for the single most-reported defect. The noun
#: ladder suppresses the generic ``kind`` whenever a ``subkind`` was drawn,
#: which is right almost everywhere and was catastrophic here: "a large
#: battle-scarred warship with a T-shaped prow hull" contains no word that is
#: not also a naval word, and got drawn as a ship at sea every time. ", a
#: starship" settles it for two tokens.
_MADE_HEAD = HeadPhrase(
    noun=("subkind", "kind"),
    modifiers=("scale", "condition"),
    apposition="kind",
)

#: The same head phrase without the apposition, for archetypes whose ``subkind``
#: already names the category. "A neutron star, a celestial body" spends four
#: tokens restating what "neutron star" said, and the apposition exists to add
#: information rather than to be applied uniformly.
_SELF_NAMING_HEAD = HeadPhrase(
    noun=("subkind", "kind"), modifiers=("scale", "condition")
)

# The archetype's own detail shape. Every priority list opens
# ``form, subkind, material, primary_color`` -- the silhouette, the name, the
# substance and the colour, the four things a t2i model can actually place and
# the four the reference corpus's GOOD bucket always carries. ``primary_color``
# costs a budget slot but usually costs no clause: ``adjective_of`` folds it onto
# ``material`` (or onto ``form`` when material was cut), so pricing it high is
# what keeps a colour on the thing rather than on nothing. What differs after
# those four is what that class of thing *is*: a creature spends the rest on
# anatomy (appendages, sensors, aperture); a world on appendages (ring arcs,
# tidal tails -- a world's silhouette) and one emitter; a station and a craft on
# scale and one emitter; a wreck on condition; an artifact on surface_detail.
# ``armament``, ``markings``, ``accent_color`` and ``extras`` sit below the core
# for the built and inert archetypes deliberately: they are the greebles the
# corpus shows a model cannot place in every frame. They are not dead, though --
# ``detail_rotation`` reserves one or two of the cap's slots and fills them by a
# weighted draw, so a batch shows all of them and one frame stays coherent.
# The caps only ever *lower* the caller's allowance; a four-entity scene's
# supporting slots are still tapered by ALLOWANCE_BY_COUNT first.
#
# Every pattern here is a whole English sentence with holes. The connector, the
# verb and the possessive are written next to the noun they agree with, and a
# field spoken by one pattern is consumed so the next cannot repeat it -- which
# is what lets the ``is clad in``/``is clad in``/``has`` ladder stand down to
# exactly one rung. ``kind`` is exempt from the coverage check: it is the
# spine, not a description.
ARCHETYPES: dict[str, Archetype] = {
    # A gas giant has no crust: what the eye meets is its cloud deck.
    "giant": Archetype(
        head_phrase=_SELF_NAMING_HEAD,
        omits=frozenset({"armament"}),
        detail_cap=9,
        detail_priority=(
            "form", "subkind", "material", "primary_color", "scale", "condition",
            "appendages", "emitters",
        ),
        # Round XII (D12): a world's world-scale features -- a storm oval, an
        # ice cap, a crater row -- are drawn from the tail, never from the cap.
        # The cap is 9 so the emitters stay in the fixed order as well.
        # Round XII (D12): a world's world-scale features -- a storm oval, an
        # ice cap, a crater row -- are drawn from the tail, never from the cap.
        detail_rotation_slots=1,
        detail_rotation={
            "extras": 1.0, "markings": 0.8, "aperture": 0.8, "surface_detail": 0.5,
        },
        sentences=(
            Sentence(text="{subject} {copula} {situation}."),
            Sentence(text="{subject}."),
            Sentence(text="{pronoun} {pronoun_copula} {form} seen from space[, wrapped in {material}]."),
            Sentence(text="{pronoun} {pronoun_copula} wrapped in {material}."),
            Sentence(text="{pronoun} {pronoun_copula} {primary_color}."),
            Sentence(text="{pronoun} bears {appendages, emitters, aperture, sensors, extras}."),
            Sentence(text="{pronoun} shows {surface_detail}."),
            Sentence(text="{pronoun} {pronoun_copula} marked with {markings, accent_color}."),
        ),
    ),
    # A ring system is a plane of rubble: no surface, no opening, nothing that glows.
    "ring": Archetype(
        head_phrase=_SELF_NAMING_HEAD,
        omits=frozenset({
            "armament", "aperture", "sensors", "extras", "surface_detail", "emitters", "condition",
        }),
        detail_cap=7,
        detail_priority=("form", "subkind", "material", "primary_color", "appendages", "scale"),
        # Round XII (D12): a ring is seen whole, but its banding is worth a draw.
        detail_rotation_slots=1,
        detail_rotation={"markings": 1.0},
        sentences=(
            Sentence(text="{subject} {copula} {situation}."),
            Sentence(text="{subject}."),
            Sentence(text="{pronoun} {pronoun_copula} {form} seen from space[, made of {material}]."),
            Sentence(text="{pronoun} {pronoun_copula} made of {material}."),
            Sentence(text="{pronoun} {pronoun_copula} {primary_color}."),
            Sentence(text="{pronoun} bears {appendages}."),
            Sentence(text="{pronoun} {pronoun_copula} marked with {markings, accent_color}."),
        ),
    ),
    # A hull: plated, powered, and carrying things bolted to it.
    "craft": Archetype(
        head_phrase=_SELF_NAMING_HEAD,
        detail_cap=8,
        detail_priority=(
            "form", "subkind", "material", "primary_color", "emitters", "scale",
            "condition",
        ),
        detail_rotation_slots=1,
        detail_rotation={
            "appendages": 1.0, "armament": 1.0, "extras": 1.0, "aperture": 0.8,
            "sensors": 0.6, "markings": 0.6, "surface_detail": 0.5, "accent_color": 0.3,
        },
        sentences=(
            Sentence(text="{subject} {copula} {situation}."),
            Sentence(text="{subject}."),
            Sentence(text="{pronoun} has {form}, clad in {material}."),
            Sentence(text="{pronoun} is clad in {material}."),
            Sentence(text="{pronoun} has {form}."),
            Sentence(text="{pronoun} shows {surface_detail}."),
            Sentence(text="{pronoun} {pronoun_copula} {primary_color}."),
            Sentence(text="{pronoun} {pronoun_copula} marked with {markings, accent_color}."),
            Sentence(text="{pronoun} features {appendages, armament, sensors, extras}."),
            Sentence(text="{pronoun} bears {emitters, aperture}."),
        ),
    ),
    # Built, and standing still. Same grammar as a hull today; kept separate
    # because a station's sentence plan is the obvious next thing to diverge.
    "structure": Archetype(
        head_phrase=_SELF_NAMING_HEAD,
        # Round XVI: ``surface_detail``/``markings``/``accent_color`` moved out
        # of rotation and into the fixed head (see "object" below for why),
        # which added three fields to what the fixed head always tries to
        # speak. The cap rises by the same three, so a station keeps
        # everything it always used to say -- this was never about a station
        # saying *more*, only about which single field a solitary rotation
        # slot was allowed to spend itself on.
        detail_cap=11,
        detail_priority=(
            "form", "subkind", "material", "primary_color", "scale", "emitters",
            "condition", "surface_detail", "markings", "accent_color",
        ),
        detail_rotation_slots=1,
        detail_rotation={
            "appendages": 1.0, "extras": 1.0, "aperture": 0.8, "sensors": 0.6,
            "armament": 0.4,
        },
        sentences=(
            Sentence(text="{subject} {copula} {situation}."),
            Sentence(text="{subject}."),
            Sentence(text="{pronoun} is built as {form}[, clad in {material}]."),
            Sentence(text="{pronoun} is clad in {material}."),
            Sentence(text="{pronoun} shows {surface_detail}."),
            Sentence(text="{pronoun} {pronoun_copula} {primary_color}."),
            Sentence(text="{pronoun} {pronoun_copula} marked with {markings, accent_color}."),
            Sentence(text="{pronoun} features {appendages, armament, sensors, extras}."),
            Sentence(text="{pronoun} bears {emitters, aperture}."),
        ),
    ),
    # Was a hull. Still described as one -- a wreck is legible precisely
    # because you can still see what it used to be. A wreck spends its short
    # budget on what state it is in.
    "wreck": Archetype(
        head_phrase=_SELF_NAMING_HEAD,
        # Round XIV: a wreck has no power, so nothing on it glows. A lit port or
        # a sparking junction box drew a dead hull with its engines still firing.
        omits=frozenset({"emitters"}),
        detail_cap=9,
        detail_priority=(
            "form", "subkind", "material", "primary_color", "appendages",
            "condition",
        ),
        detail_rotation_slots=1,
        detail_rotation={
            "extras": 1.0, "surface_detail": 0.8, "aperture": 0.8, "armament": 0.6,
            "markings": 0.4, "sensors": 0.3, "accent_color": 0.2,
        },
        sentences=(
            Sentence(text="{subject} {copula} {situation}."),
            Sentence(text="{subject}."),
            Sentence(text="{pronoun} {pronoun_copula} reduced to {form}[, clad in {material}]."),
            Sentence(text="{pronoun} is clad in {material}."),
            Sentence(text="{pronoun} has {form}."),
            Sentence(text="{pronoun} shows {surface_detail}."),
            Sentence(text="{pronoun} {pronoun_copula} {primary_color}."),
            Sentence(text="{pronoun} {pronoun_copula} marked with {markings, accent_color}."),
            Sentence(text="{pronoun} shows {appendages, armament, sensors, extras}."),
            Sentence(text="{pronoun} bears {emitters, aperture}."),
        ),
    ),
    # No apposition: "a combat mech, a robot or mech" restates the noun, and
    # the kind reads as a dropdown label rather than as English.
    "machine": Archetype(
        head_phrase=_SELF_NAMING_HEAD,
        detail_cap=9,
        detail_priority=(
            "form", "subkind", "material", "primary_color", "scale", "sensors",
            "armament",
        ),
        detail_rotation_slots=1,
        detail_rotation={
            "emitters": 1.2, "appendages": 1.0, "extras": 0.8, "aperture": 0.6,
            "markings": 0.6, "surface_detail": 0.5, "accent_color": 0.3,
        },
        sentences=(
            Sentence(text="{subject} {copula} {situation}."),
            Sentence(text="{subject}."),
            Sentence(text="{pronoun} has {form}, plated in {material}."),
            Sentence(text="{pronoun} is plated in {material}."),
            Sentence(text="{pronoun} has {form}."),
            Sentence(text="{pronoun} shows {surface_detail}."),
            Sentence(text="{pronoun} {pronoun_copula} {primary_color}."),
            Sentence(text="{pronoun} {pronoun_copula} marked with {markings, accent_color}."),
            Sentence(text="{pronoun} features {appendages, armament, sensors, extras}."),
            Sentence(text="{pronoun} bears {emitters, aperture}."),
        ),
    ),
    # A person *wears* their material, and is spoken as "they" -- the pack never
    # knows a spacefarer's gender and must not guess one.
    "figure": Archetype(
        head_phrase=_SELF_NAMING_HEAD,
        # A person is person-sized; their build is already in ``form``.
        omits=frozenset({"scale"}),
        pronoun="they",
        pronoun_plural="they",
        possessive="their",
        possessive_plural="their",
        pronoun_copula="are",
        pronoun_object="them",
        pronoun_object_plural="them",
        detail_cap=9,
        # The material is a garment, so it takes an article: "an aged canvas
        # coverall", not "wear aged canvas coverall".
        templates={"material": "{a_value}"},
        # A spacefarer is a person, so livery reads on them: a uniform's
        # insignia and its trim are part of the subject, not a greeble. That is
        # what keeps ``markings`` and ``accent_color`` alive -- every built and
        # inert archetype leaves both in the tail.
        # Round XII: a person's livery is part of the subject, not a tail draw, so
        # ``markings`` moved into the fixed order and out of the rotation.
        detail_priority=(
            "form", "subkind", "material", "primary_color", "markings", "armament",
            "sensors", "condition", "scale",
        ),
        detail_rotation_slots=2,
        detail_rotation={
            "extras": 1.0, "accent_color": 0.6, "surface_detail": 0.5,
            "appendages": 0.4, "aperture": 0.4, "emitters": 0.4,
        },
        sentences=(
            Sentence(text="{subject} {copula} {situation}."),
            Sentence(text="{subject}."),
            Sentence(text="{pronoun} have {form} and wear {material}."),
            Sentence(text="{pronoun} wear {material}."),
            Sentence(text="{pronoun} have {form}."),
            Sentence(text="{pronoun} show {surface_detail}."),
            Sentence(text="{pronoun} {pronoun_copula} {primary_color}."),
            Sentence(text="{possessive} gear bears {markings, accent_color}."),
            # A person does not *carry* their own hands, their boots or the pod
            # strapped to their back. "They carry a pair of gauntleted hands"
            # and "They carry a single magnetic boot" were both reported, and
            # both are this one clause putting worn kit behind a carrying verb.
            # Weapons and loose gear are carried; limbs and fitted optics are worn.
            Sentence(text="{pronoun} carry {armament, extras}."),
            Sentence(text="{pronoun} wear {appendages, sensors}."),
            Sentence(text="{pronoun} show {emitters, aperture}."),
        ),
    ),
    # A body plan is the *subject*: "a creature with a segmented worm body"
    # reliably draws a human holding a worm. Four Identity Forge render bugs
    # traced to getting this backwards, which is why the pack declares it and
    # ``ProseSpec`` cross-checks the declaration against the first pattern.
    "creature": Archetype(
        head_phrase=HeadPhrase(
            noun=("subkind", "kind"),
            modifiers=("scale", "condition"),
            subject="form",
            apposition="kind",
        ),
        detail_cap=12,
        # ``extras`` is the one greeble a creature can carry and still read as
        # one organism, so it is the archetype's last promotion rather than a
        # dead widget: every other archetype leaves it in the tail.
        # ``extras`` moved to the rotation in round XII: at the end of a ten-field
        # core order it was under the allowance, so it was a dead widget.
        detail_priority=(
            "form", "subkind", "material", "primary_color", "appendages",
            "sensors", "aperture", "scale", "armament",
        ),
        detail_rotation_slots=1,
        # Round XII: a creature's bioluminescence is a thing a model draws, so
        # ``emitters`` is in the tail rather than dead under the cap.
        detail_rotation={
            "markings": 1.0, "emitters": 1.0, "extras": 0.5, "surface_detail": 0.6,
            "accent_color": 0.3,
        },
        sentences=(
            Sentence(text="{subject} {copula} {situation}."),
            Sentence(text="{subject}."),
            Sentence(text="{pronoun} {pronoun_copula} {subkind}[, covered in {material}]."),
            Sentence(text="{pronoun} {pronoun_copula} covered in {material}."),
            Sentence(text="{pronoun} {pronoun_copula} {primary_color}."),
            Sentence(text="{pronoun} shows {surface_detail}."),
            Sentence(text="{pronoun} has {appendages, armament, sensors, extras}."),
            Sentence(text="{pronoun} bears {emitters, aperture}."),
            Sentence(text="{pronoun} {pronoun_copula} marked with {markings, accent_color}."),
        ),
    ),
    # A world has a surface but no maker. "Clad in basalt crust" says somebody
    # put it there; "a crust of basalt" says it is what the thing is.
    "world": Archetype(
        head_phrase=_SELF_NAMING_HEAD,
        omits=frozenset({"armament"}),
        detail_cap=9,
        detail_priority=(
            "form", "subkind", "material", "primary_color", "scale", "condition",
            "appendages", "emitters",
        ),
        # Round XII (D12): a world's world-scale features -- a storm oval, an
        # ice cap, a crater row -- are drawn from the tail, never from the cap.
        # The cap is 9 so the emitters stay in the fixed order as well.
        # Round XII (D12): a world's world-scale features -- a storm oval, an
        # ice cap, a crater row -- are drawn from the tail, never from the cap.
        detail_rotation_slots=1,
        detail_rotation={
            "extras": 1.0, "markings": 0.8, "aperture": 0.8, "surface_detail": 0.5,
        },
        sentences=(
            Sentence(text="{subject} {copula} {situation}."),
            Sentence(text="{subject}."),
            Sentence(text="{pronoun} {pronoun_copula} {form} seen from space[, its crust {material}]."),
            Sentence(text="{pronoun} {pronoun_copula} a world of {material}."),
            Sentence(text="{pronoun} {pronoun_copula} {primary_color}."),
            Sentence(text="{pronoun} bears {appendages, emitters, aperture, sensors, extras}."),
            Sentence(text="{pronoun} shows {surface_detail}."),
            Sentence(text="{pronoun} {pronoun_copula} marked with {markings, accent_color}."),
        ),
    ),
    # No surface at all. Everything a surface implies is omitted rather than
    # reworded -- absence by omission, never negation. This is the archetype the
    # whole mechanism was built for: a black hole was being described as
    # ice-encrusted, clad in molten rock, with an impact crater basin.
    "phenomenon": Archetype(
        # Subject-leading, like a creature and for the same reason, and the
        # apposition is the *subkind* ("a rust brown oblate sphere, a star")
        # because a star names itself and "a celestial body" does not.
        head_phrase=HeadPhrase(
            noun=("subkind", "kind"),
            modifiers=("scale", "condition"),
            subject="form",
            apposition="subkind",
        ),
        omits=frozenset(
            {
                "material", "surface_detail", "armament", "aperture", "extras",
                "sensors", "condition", "scale",
            }
        ),
        detail_cap=6,
        detail_priority=("form", "subkind", "primary_color", "emitters", "appendages"),
        # Round XII: the pattern already voices markings and accent, so the tail
        # reserves a slot for them -- otherwise both are dead widgets.
        detail_rotation_slots=1,
        detail_rotation={"markings": 1.0, "accent_color": 0.4},
        sentences=(
            Sentence(text="{subject} {copula} {situation}."),
            Sentence(text="{subject}."),
            Sentence(text="{pronoun} {pronoun_copula} {primary_color}."),
            Sentence(text="{pronoun} bears {appendages, emitters}."),
            Sentence(text="{pronoun} {pronoun_copula} marked with {markings, accent_color}."),
        ),
    ),
    # Inert, old, and made of one substance. It carries nothing and shoots
    # nothing; what it has is what it was cut from. The short budget goes on
    # the finish -- what it was cut from is the whole subject.
    "object": Archetype(
        head_phrase=_SELF_NAMING_HEAD,
        omits=frozenset({"armament", "sensors"}),
        detail_cap=9,
        # Round XVI: ``markings``/``accent_color`` moved out of rotation and
        # into the fixed head, for the same reason as the "structure"
        # archetype above -- they used to be able to win the single rotation
        # slot outright and leave an alien artifact with no component spoken.
        detail_priority=(
            "form", "subkind", "material", "primary_color", "emitters",
            "surface_detail", "markings", "accent_color",
        ),
        detail_rotation_slots=1,
        detail_rotation={
            "aperture": 1.0, "extras": 1.0, "appendages": 0.6,
        },
        sentences=(
            Sentence(text="{subject} {copula} {situation}."),
            Sentence(text="{subject}."),
            Sentence(text="{pronoun} takes the form of {form}, cut from {material}."),
            Sentence(text="{pronoun} {pronoun_copula} made of {material}."),
            Sentence(text="{pronoun} takes the form of {form}."),
            Sentence(text="{pronoun} {pronoun_copula} {primary_color}."),
            Sentence(text="{pronoun} shows {surface_detail}."),
            Sentence(text="{pronoun} {pronoun_copula} marked with {markings, accent_color}."),
            Sentence(text="{pronoun} bears {emitters, aperture, appendages, extras}."),
        ),
    ),
    # The stranger's grammar. A foreign-genre entity wired into a sci-fi scene has
    # a kind this pack has never heard of, so it reaches no archetype of its own.
    # Without an entry here it falls through to the bare ``ProseSpec``. Neutral
    # wording that is true of anything with a surface, a head phrase that names
    # the foreign category once, and a modest cap.
    POOL_DEFAULT_KEY: Archetype(
        head_phrase=_MADE_HEAD,
        detail_cap=8,
        detail_priority=("form", "subkind", "material", "primary_color", "scale"),
        sentences=(
            Sentence(text="{subject} {copula} {situation}."),
            Sentence(text="{subject}."),
            Sentence(text="{pronoun} {pronoun_copula} {form}[, covered in {material}]."),
            Sentence(text="{pronoun} {pronoun_copula} covered in {material}."),
            Sentence(text="{pronoun} has {form}."),
            Sentence(text="{pronoun} {pronoun_copula} {primary_color}."),
            Sentence(text="{pronoun} shows {surface_detail}."),
            Sentence(text="{pronoun} {pronoun_copula} marked with {markings, accent_color}."),
            Sentence(text="{pronoun} features {appendages, armament, sensors, extras}."),
            Sentence(text="{pronoun} bears {emitters, aperture}."),
        ),
    ),
}

ARCHETYPE_OF_KIND: dict[str, str] = {
    "starship": "craft",
    "surface vehicle": "craft",
    "space station": "structure",
    "wreck": "wreck",
    "robot or mech": "machine",
    "spacefarer": "figure",
    "alien creature": "creature",
    "celestial body": "world",
    "alien artifact": "object",
}

#: The subkinds that leave their kind's archetype. Built from the *same* tuples
#: the diffuse constraint rules are generated from, deliberately: a thing with
#: no surface should neither draw surface values nor be given surface grammar,
#: and naming the set once is how those two halves stay in step.
ARCHETYPE_OF_SUBKIND: dict[str, str] = {
    **{subkind: "phenomenon"
       for subkind in _DIFFUSE_CELESTIAL_SUBKINDS + _DIFFUSE_CREATURE_SUBKINDS},
    **{subkind: "giant" for subkind in SUBKIND_GROUPS["gas world"]},
    **{subkind: "ring" for subkind in SUBKIND_GROUPS["disc system"]},
}


#: (field, subkind group) pairs that are allowed to fall through to the kind
#: pool instead of having a group key of their own. The solid celestial groups
#: genuinely share the celestial aperture/surface-detail vocabulary; the
#: diffuse groups are omitted by the phenomenon archetype and need no entry.
SCOPE_FALLTHROUGH: frozenset[tuple[str, str]] = frozenset({
    ("aperture", "solid world"),
    ("aperture", "small body"),
    ("aperture", "disc system"),
    ("surface_detail", "solid world"),
    ("surface_detail", "small body"),
    ("surface_detail", "disc system"),
    # The six component fields scope on subkind now. Every group with no key of
    # its own shares its kind's vocabulary by design -- a body plan, a robot
    # class, a wreck class or a vehicle class says nothing about which engines or
    # weapons it carries -- and the groups that DO need their own key are keyed in
    # APPENDAGE_POOLS / EMITTER_POOLS / MARKINGS_POOLS. The celestial entries
    # below are the ones worth naming: a solid world keeps the celestial pool,
    # while a phenomenon has no armament, sensors or extras to fall through at
    # all (its archetype omits them).
    ("emitters", "disc system"),
    ("sensors", "solid world"),
    ("sensors", "gas world"),
    ("sensors", "small body"),
    ("sensors", "disc system"),
    ("extras", "solid world"),
    ("extras", "gas world"),
    ("extras", "small body"),
    ("extras", "disc system"),
    ("markings", "solid world"),
    ("markings", "gas world"),
    ("markings", "small body"),
    ("markings", "disc system"),
    # starship and space station have no subkind groups -- any hull class can be
    # any silhouette -- so their form falls through to the kind pool by design.
    ("form", "starship"),
    ("form", "space station"),
    # Only a small drone keeps its own situation key; the other robot groups
    # deliberately share the kind's actions, which are true of a walker or a
    # sentry unit alike.
    ("situation", "heavy chassis"),
    ("situation", "static unit"),
    ("situation", "hovering"),
    ("situation", "underwater"),
    ("situation", "legged"),
    ("situation", "wheeled/tracked"),
})


#: Cross-field word families. The engine never reads this; the distribution
#: sweep reports each one's share of the whole prompt, which is the only way a
#: bias spread across five fields becomes visible (see ``GenrePack.motifs``).
MOTIFS: dict[str, tuple[str, ...]] = {
    "ice": ("ice", "frost", "glacier", "cryo", "rime", "polar", "arctic"),
    "heat": ("scorch", "molten", "lava", "ember", "flame", "soot", "burn"),
    "rust": ("rust", "oxidis", "corrod", "verdigris", "patina"),
    "growth": ("fungal", "fungus", "overgrown", "spore", "flora", "moss", "bark"),
    "dust": ("dust", "sand", "regolith", "grit", "ash"),
    "ring": ("ring",),
}


def _hyphenated(tokens: tuple[str, ...]) -> dict[str, str]:
    """Spoken form for compound colour tokens: hyphenate the multi-word ones.

    "bone-white armour" is correct English for a compound modifier and stops
    "bone" being read as a noun; single-word tokens fall through to themselves.
    """
    return {token: token.replace(" ", "-") for token in tokens if " " in token}


#: ``{field: {token: spoken form}}`` -- how a value is said in a sentence when
#: that differs from how it reads in a dropdown. A subkind of an apposition-free
#: kind carries the category in its head noun here, so the category is said once
#: rather than twice.
_SPOKEN_SUBKIND: dict[str, str] = {
    # Starship
    "scout ship": "scout starship",
    "heavy freighter": "heavy cargo starship",
    "warship": "battle starship",
    "bioship": "grown organic starship",
    "salvage hauler": "salvage starship",
    "colony ship": "colony starship",
    "courier": "courier starship",
    "dreadnought": "dreadnought-class starship",
    "strike carrier": "carrier starship",
    "survey vessel": "survey starship",
    "ore hauler": "ore-hauling starship",
    "troop transport": "troop-carrier starship",
    # "passenger" reads as a present-day commercial airliner, especially
    # paired with a tube-and-windows hull -- a starliner wreck in a desert
    # rendered as a crashed jet fuselage.
    "starliner": "interstellar liner starship",
    "interceptor": "interceptor starfighter",
    "generation ship": "generation starship",
    "hospital ship": "hospital starship",
    "smuggler runner": "smuggling starship",
    "supply ship": "supply starship",
    # Space station
    "ring station": "ring-shaped space station",
    "torus habitat": "torus habitat station",
    "orbital shipyard": "orbital shipyard station",
    "mining platform": "mining platform station",
    "listening post": "listening-post space station",
    "trade hub": "trade-hub space station",
    "defence platform": "defence platform station",
    "space elevator anchor": "space elevator anchor station",
    "research outpost": "research space station",
    "refuelling depot": "refuelling depot station",
    "prison station": "prison space station",
    "void monastery": "void monastery station",
    "terraforming tower": "terraforming space station",
    "arcology tower": "arcology space station",
    "drydock cradle": "drydock space station",
    "relay array": "relay-array space station",
    # Wreck
    "crashed hull": "crashed starship hull",
    "burnt-out star cruiser": "burnt-out star cruiser wreck",
    "drifting hulk": "drifting starship hulk",
    "stripped void freighter": "stripped cargo starship wreck",
    "ghost starliner": "ghost liner-starship wreck",
    "collapsed station spar": "collapsed space-station spar",
    "shattered interceptor": "shattered starfighter wreck",
    "abandoned mining rig": "abandoned asteroid-mining rig",
    "half-salvaged star carrier": "half-salvaged star carrier wreck",
    "buried lander": "buried planetary lander",
    "torn-open habitat module": "torn-open space habitat module",
    "gutted engine section": "gutted starship engine section",
    "sunken submersible": "sunken submersible wreck",
    "fossilised bioship": "fossilised bioship wreck",
    # Surface vehicle
    "rover": "planetary rover",
    "hovercraft": "hover transport",
    "crawler": "tracked planetary crawler",
    "skimmer": "hover skimmer",
    "ground transport": "armoured ground transport",
    "walker": "legged walker vehicle",
    "submersible": "deep-water submersible",
    "high-altitude glider": "high-altitude gravlift flyer",
    "tracked hauler": "tracked cargo hauler",
    "landing shuttlecraft": "landing shuttlecraft",
    "drop pod": "orbital drop pod",
    "sand crawler": "armoured sand crawler",
    "ice cutter": "ice-cutting crawler",
    "hover bike": "scout hover bike",
    # Spacefarer
    "pilot": "starship pilot",
    "engineer": "starship engineer",
    "captain": "starship captain",
    "marine": "space marine",
    "scientist": "research scientist",
    "medic": "starship medic",
    "smuggler": "space smuggler",
    "colonist": "off-world colonist",
    "navigator": "starship navigator",
    "salvager": "space salvager",
    # "diplomat" alone drew a second figure to shake hands with.
    "diplomat": "lone interstellar diplomat",
    "mercenary": "space mercenary",
    "raider": "space raider",
    "xenobiologist": "xeno-biologist",
    "crew technician": "starship crew technician",
    "prospector": "asteroid prospector",
    "void order priest": "void-order priest",
    "cyborg operative": "cyborg operative",
    # D15: humanoid alien people. The word "alien" is in the spoken form, so a
    # model draws the face and the frame, not a human in a suit.
    "amphibian admiral": "bulbous-eyed amphibian alien admiral",
    "mandibled envoy": "mandibled alien envoy",
    "reptilian bounty hunter": "scaled reptilian alien bounty hunter",
    "grey-skinned archivist": "tall grey-skinned alien archivist",
    "tusked mercenary": "tusked alien mercenary",
    "tendril-faced navigator": "tendril-faced alien navigator",
    "crested pilot": "crest-headed alien pilot",
    "four-armed quartermaster": "four-armed alien quartermaster",
    "horned warlord": "horned alien warlord",
    "translucent medic": "translucent-skinned alien medic",
    # Robot or mech
    "labour droid": "labour robot",
    "combat mech": "combat mech",
    "repair drone": "repair drone",
    "survey drone": "survey drone",
    "android": "android unit",
    "exosuit walker": "exosuit walker mech",
    "mining loader": "ore-cutting mech",
    "cargo hauler unit": "cargo-hauling robot",
    "security automaton": "security robot",
    "medical automaton": "medical robot",
    "swarm drone": "swarm drone",
    "sentry unit": "sentry robot",
    "terraforming walker": "terraforming walker mech",
    "courier drone": "courier drone",
    # Alien artifact -- the apposition that said "alien" is gone, so the word
    # joins the head noun.
    "monolith": "alien monolith",
    "obelisk": "alien obelisk",
    "beacon": "alien beacon",
    "data core": "alien data core",
    "containment vault": "alien containment vault",
    "alien engine": "alien engine",
    "relic sphere": "alien relic sphere",
    "gate ring": "alien gate ring",
    "sarcophagus pod": "alien sarcophagus pod",
    "resonant lattice spire": "alien resonant lattice spire",
    "drifting cargo pod": "alien drifting cargo pod",
    "sealed reliquary": "alien sealed reliquary",
    "power cell array": "alien power cell array",
    "navigation marker pylon": "alien navigation marker pylon",
    # Celestial body
    "rocky planet": "rocky planet",
    "gas giant": "gas giant",
    "ice moon": "ice moon",
    "ringed world": "ringed world",
    "asteroid": "asteroid",
    "comet": "comet",
    "dwarf planet": "dwarf planet",
    "star": "star",
    "neutron star": "neutron star",
    "black hole": "black hole",
    "nebula cloud": "nebula",
    "rogue planet": "rogue planet",
    "volcanic moon": "volcanic moon",
    "ocean world": "ocean world",
    "binary star pair": "binary star pair",
    "ring system": "ring system",
    # The widened subkinds, where a sentence says them differently.
    "corvette": "corvette starship",
    "survey cutter": "survey starship",
    "prison transport": "prison-transport starship",
    "ice giant": "ice giant",
    "lava world": "lava world",
    "carbon planet": "carbon planet",
    "refinery platform": "refinery platform station",
    "observation station": "observation space station",
    "salvage yard": "orbital salvage yard station",
    "quartermaster": "starship quartermaster",
    "archaeologist": "xeno-archaeologist",
    "cartographer": "starship cartographer",
    "welding drone": "welding drone",
    "siege mech": "siege mech",
    "scout walker": "scout walker mech",
    "memory shard": "alien memory shard",
    "gravity anchor": "alien gravity anchor",
    "sealed gateway": "alien sealed gateway",
    "amphibious crawler": "amphibious crawler",
    "cargo sled": "cargo hover-hauler",
    "survey glider": "survey gravlift flyer",
    "beached hulk": "beached starship hulk",
    "buried frigate": "half-buried battle starship wreck",
}

_SPOKEN_ENVIRONMENT: dict[str, str] = {
    # An interior says whose interior it is, or it is drawn as a room on Earth.
    "crew commons": "starship crew commons deck",
    "crew quarters": "starship crew quarters",
    "brig": "starship brig cell block",
    "chapel": "void chapel aboard a space station",
    "armoury": "starship weapons armoury",
    "cargo hold": "starship cargo hold",
    "medical bay": "starship medical bay",
    "data vault": "orbital station data vault",
    "reactor hall": "fusion reactor hall of a space station",
    "maintenance crawlway": "starship maintenance crawlway",
    "hydroponics bay": "space station hydroponics bay",
    # A surface says which world it is on, with something no Earth sky holds.
    "orange sand dune sea": "orange dune sea beneath a banded gas giant",
    # Round XV: a bare or "cratered" moon is drawn as Earth's own. Each moon
    # carries a colour or a ring, and the tidal flat got a gas giant instead of
    # a second pair of Earth moons over an Earth beach.
    "black sand tidal flat": "black sand tidal flat beneath a vast ringed gas giant",
    "barren alien wilderness": "barren alien wilderness beneath a rust-red moon",
    "cracked salt flat": "cracked salt flat of an alien world",
    "basalt mesa badlands": "basalt mesa badlands beneath two pale-green moons",
    "glass plain": "fused glass plain of a scorched world",
    "geyser field": "geyser field of an ice moon",
    "crater basin": "flooded crater basin of an alien moon",
    "obsidian canyon": "obsidian canyon of a volcanic world",
    "frozen sea ice": "frozen sea ice of a methane world",
    "domed colony concourse":
        "pressurised colony concourse under a lattice dome",
}

#: A sealed garment says so in its spoken form, because a model draws "vac suit"
#: as an open suit with a bare face. The helmet is the render claim; it is not a
#: separate widget, and nothing carries it as a gadget.
_SPOKEN_MATERIAL: dict[str, str] = {
    "canvas-weave vac suit": "canvas-weave vac suit with a sealed domed helmet",
    "armour-composite hardsuit":
        "armour-composite hardsuit with a sealed full-face helmet",
    "ceramic hardsuit": "ceramic hardsuit with a mirrored full-face helmet",
    "much-repaired vac suit": "much-repaired vac suit with a scuffed domed helmet",
    "thermal-lined pressure suit":
        "thermal-lined pressure suit with a sealed faceplate helmet",
    "impact-gel armour suit": "impact-gel armour suit with a closed combat helmet",
    "polymer soft-suit": "polymer soft-suit with a clear bubble helmet",
}

SPOKEN: dict[str, dict[str, str]] = {
    "subkind": _SPOKEN_SUBKIND,
    "material": _SPOKEN_MATERIAL,
    "primary_color": _hyphenated(PRIMARY_COLOR_POOL),
    "accent_color": _hyphenated(ACCENT_COLOR_POOL),
    "emitter_color": _hyphenated(sorted({
        value for pool in EMITTER_COLOR_POOLS.values() for value in pool
    })),
}


#: Words a model will draw as the Earth object rather than as the subject.
#: Genre-blind: a fantasy pack lists modern ones.
SPOKEN[ENVIRONMENT_FIELD] = _SPOKEN_ENVIRONMENT


FOREIGN_NOUNS: tuple[str, ...] = (
    "whale", "manta", "catamaran", "hammerhead", "cathedral", "mushroom",
    "ziggurat", "spider", "tree", "harp", "buoy", "barge", "tug", "potato",
    "tanker", "convoy", "shuttle", "trailer", "truck", "car", "boat",
    "aircraft", "jet", "bone", "blood", "craft",
    # A model draws each of these as the Earth thing rather than as the subject.
    "balloon", "graveyard", "cemetery", "monitor", "crate", "catwalk",
    "ship", "freighter", "frigate", "lamp", "lantern", "derrick", "crane",
    "galley", "sled", "overall", "vest", "jacket", "baton", "tribal",
    "hitch", "cube", "satellite",
    "warehouse", "plane", "helicopter", "sailboat", "lighthouse", "windmill",
    # An Earth place is drawn as the Earth place; the alien qualifier has to be
    # in the head noun, not only in front of it.
    "desert", "beach", "lake", "marsh", "tundra", "jungle", "forest", "swamp",
    # A shape a model draws as the Earth craft: a fuselage is an aircraft's body,
    # a starliner and an airliner are passenger aircraft, a roundel is a national
    # marking.
    "fuselage", "starliner", "airliner", "roundel",
    # A container, a tether or a bone is drawn as the Earth object however the
    # subject is qualified: a chain is a chain, a bladder is a balloon.
    "egg", "bladder", "drum", "barrel", "canister", "bucket", "pail",
    "chain", "rope", "net", "web", "skeleton", "fish", "shoal", "tether",
    "chain", "rope", "net", "web", "skeleton", "fish", "shoal", "tether",
)
# Round XII: a colour that is also an object, and the last Earth room and animal words.
FOREIGN_NOUNS = FOREIGN_NOUNS + (
    "rose", "brick", "moss", "mustard", "plum", "pearl", "jade", "ivory", "chalk",
    "seafoam", "salmon", "coral", "mint", "mites", "street", "mess", "headlamp",
)
FOREIGN_NOUN_FIELDS: tuple[str, ...] = (
    "kind", "subkind", "scale", "condition", "form", "material", "primary_color",
    "accent_color", "markings", "surface_detail", "appendages", "emitters",
    "armament", "sensors", "aperture", "extras", "situation", "relation",
    "relation_position", "context", "environment",
)
FOREIGN_NOUN_ALLOWLIST: frozenset[str] = frozenset({
    # An astrophysical jet, not an aircraft.
    "plasma jet",
    "radiant polar jet",
    "jet knotting",
    # A tether that is part of a named structure, and a body plan whose head noun
    # is the human frame.
    "orbital elevator tether",
    "barrel-chested frame",
    "radiant polar jet",
    "jet knotting",
    "tentacled bell-body",
    "inverted funnel body",
    "wheel-shaped rolling body",
    "spoke-and-hub wheel",
    "six-wheeled rover chassis",
    "plated bone",
    "bone club tail",
    "hollow-boned winged frame",
    "landing shuttlecraft",
    "sample trailer",
    "flinging a jet from its poles",
    "radiant polar jet",
})


SITUATION_TIERS.update({
    "anchoring itself against a dust storm": "activity",
    "tumbling into a debris cloud after a glancing collision": "event",
    "being struck by a lightning discharge": "event",
    "being struck by a tumbling fragment of hull": "event",
    "bracing against the kick of a rivet driver": "activity",
    "breaking up as it falls through the cloud tops": "event",
    "chasing a spinning fragment through the debris": "activity",
    "clinging to a spinning hull plate": "event",
    "clinging to the outside of a tumbling escape pod": "event",
    "crawling across a cracked plain": "activity",
    "deploying a spread of smaller sensor drones": "activity",
    "diving through a break in the cloud tops": "event",
    "dodging a tumbling hull fragment": "event",
    "drifting beside a shattered viewport": "idle",
    "driving a survey stake into the ground": "activity",
    "fighting a crosswind above the cloud tops": "event",
    "firing a short thruster burst to hold position": "idle",
    "firing suit thrusters toward a crewmate in a sealed suit": "event",
    "grabbing a spinning toolkit before it drifts away": "activity",
    "grappling with a boarder in open vacuum": "event",
    "scanning a fresh borehole over broken ground": "activity",
    "carrying an unconscious crewmate in a sealed suit": "event",
    "idling beside a cargo stack": "idle",
    "latching onto a hull with magnetic grapples": "activity",
    "losing altitude in a downdraft": "event",
    "lowering its ramp onto a deck": "activity",
    "parking between two cargo containers": "idle",
    "sealing a hull breach from the outside": "activity",
    "planting a magnetic beacon on a drifting asteroid": "activity",
    "dropping through the cloud tops in two pieces": "event",
    "punching through a curtain of rain": "event",
    "pushing off from a hull toward a drifting cargo pod": "activity",
    "racing a lightning front across the cloud tops": "event",
    "reeling in a drifting survey probe": "activity",
    "releasing a damaged survey probe into a slow tumble": "activity",
    "resting on a maintenance cradle": "idle",
    "manoeuvring through a debris field on suit thrusters": "event",
    "riding a thermal column above the cloud tops": "idle",
    "rolling to a stop in a hangar bay": "activity",
    "scanning a drifting wreck with a fan of sensor beams": "activity",
    "sealing a cracked viewport with a foam spray": "activity",
    "settling onto a landing pad on its thrusters": "activity",
    "shaking in the turbulence above a storm": "activity",
    "shedding burning plates as it falls": "event",
    "sheltering in the lee of a cloud bank": "idle",
    "shepherding a drifting survey probe back to its bay": "activity",
    "shielding a cracked visor from a spray of debris": "event",
    "shielding a suited crewmate from a spray of debris": "event",
    "signalling a distant rescue lander with a flare": "activity",
    "skimming the top of a storm band": "activity",
    "shoving a tumbling hull plate out of their path": "event",
    "spinning down through a lightning front": "event",
    "spinning up a cutting beam against a derelict hull": "activity",
    "sweeping a helmet beam across a derelict hull": "activity",
    "sweeping a sensor beam across a field of debris": "activity",
    "sweeping a sensor beam through a storm band": "activity",
    "guiding a cargo pod in a tractor beam": "activity",
    "trailing smoke as it drops through a storm band": "event",
    "tumbling away from a hull after a suit-thruster failure": "event",
    "tumbling end over end through the clouds": "event",
    "tumbling end over end with a thruster pack jammed open": "event",
    "waiting on a launch platform": "idle",
    "watching a starship burn past at close range": "activity",
    "weaving through towering cloud columns at speed": "event",
    "welding a plate over a hull breach": "activity",
    "wrenching loose from a magnetic clamp": "event",
})
TAGS[SITUATION_FIELD].update({
    "tumbling into a debris cloud after a glancing collision": "conflict_only",
    "being struck by a lightning discharge": "conflict_only",
    "being struck by a tumbling fragment of hull": "conflict_only",
    "breaking up as it falls through the cloud tops": "conflict_only",
    "clinging to a spinning hull plate": "conflict_only",
    "clinging to the outside of a tumbling escape pod": "conflict_only",
    "dodging a tumbling hull fragment": "conflict_only",
    "firing suit thrusters toward a crewmate in a sealed suit": "conflict_only",
    "grappling with a boarder in open vacuum": "conflict_only",
    "carrying an unconscious crewmate in a sealed suit": "conflict_only",
    "losing altitude in a downdraft": "conflict_only",
    "dropping through the cloud tops in two pieces": "conflict_only",
    "reeling in a drifting survey probe": "peaceful_only",
    "shedding burning plates as it falls": "conflict_only",
    "shepherding a drifting survey probe back to its bay": "peaceful_only",
    "shielding a cracked visor from a spray of debris": "conflict_only",
    "shielding a suited crewmate from a spray of debris": "conflict_only",
    "shoving a tumbling hull plate out of their path": "conflict_only",
    "spinning down through a lightning front": "conflict_only",
    "guiding a cargo pod in a tractor beam": "peaceful_only",
    "tumbling away from a hull after a suit-thruster failure": "conflict_only",
    "tumbling end over end with a thruster pack jammed open": "conflict_only",
})
VALUE_NEEDS["situation"].update({
    "anchoring itself against a dust storm": frozenset({"ground"}),
    "tumbling into a debris cloud after a glancing collision": frozenset({"open-space"}),
    "being struck by a lightning discharge": frozenset({"sky"}),
    "being struck by a tumbling fragment of hull": frozenset({"open-space"}),
    "bracing against the kick of a rivet driver": frozenset({"open-space"}),
    "breaking up as it falls through the cloud tops": frozenset({"gravity", "sky", "cloud-deck"}),
    "chasing a spinning fragment through the debris": frozenset({"open-space"}),
    "clinging to a spinning hull plate": frozenset({"open-space"}),
    "clinging to the outside of a tumbling escape pod": frozenset({"open-space"}),
    "crawling across a cracked plain": frozenset({"ground"}),
    "deploying a spread of smaller sensor drones": frozenset({"open-space"}),
    "diving through a break in the cloud tops": frozenset({"sky", "cloud-deck"}),
    "dodging a tumbling hull fragment": frozenset({"open-space"}),
    "drifting beside a shattered viewport": frozenset({"open-space"}),
    "driving a survey stake into the ground": frozenset({"ground"}),
    "fighting a crosswind above the cloud tops": frozenset({"sky", "cloud-deck"}),
    "firing a short thruster burst to hold position": frozenset({"open-space"}),
    "firing suit thrusters toward a crewmate in a sealed suit": frozenset({"open-space"}),
    "grabbing a spinning toolkit before it drifts away": frozenset({"open-space"}),
    "grappling with a boarder in open vacuum": frozenset({"open-space"}),
    "scanning a fresh borehole over broken ground": frozenset({"ground"}),
    "carrying an unconscious crewmate in a sealed suit": frozenset({"open-space"}),
    "idling beside a cargo stack": frozenset({"floor"}),
    "latching onto a hull with magnetic grapples": frozenset({"open-space"}),
    "losing altitude in a downdraft": frozenset({"sky", "cloud-deck"}),
    "lowering its ramp onto a deck": frozenset({"floor"}),
    "parking between two cargo containers": frozenset({"floor"}),
    "sealing a hull breach from the outside": frozenset({"open-space", "structure"}),
    "planting a magnetic beacon on a drifting asteroid": frozenset({"open-space"}),
    "dropping through the cloud tops in two pieces": frozenset({"gravity", "sky", "cloud-deck"}),
    "punching through a curtain of rain": frozenset({"sky"}),
    "pushing off from a hull toward a drifting cargo pod": frozenset({"open-space", "structure"}),
    "racing a lightning front across the cloud tops": frozenset({"sky", "cloud-deck"}),
    "reeling in a drifting survey probe": frozenset({"open-space"}),
    "releasing a damaged survey probe into a slow tumble": frozenset({"open-space"}),
    "resting on a maintenance cradle": frozenset({"floor"}),
    "manoeuvring through a debris field on suit thrusters": frozenset({"open-space"}),
    "riding a thermal column above the cloud tops": frozenset({"sky", "cloud-deck"}),
    "rolling to a stop in a hangar bay": frozenset({"floor"}),
    "scanning a drifting wreck with a fan of sensor beams": frozenset({"open-space"}),
    "sealing a cracked viewport with a foam spray": frozenset({"open-space"}),
    "settling onto a landing pad on its thrusters": frozenset({"floor"}),
    "shaking in the turbulence above a storm": frozenset({"sky"}),
    "shedding burning plates as it falls": frozenset({"gravity", "sky", "cloud-deck"}),
    "sheltering in the lee of a cloud bank": frozenset({"sky", "cloud-deck"}),
    "shepherding a drifting survey probe back to its bay": frozenset({"open-space"}),
    "shielding a cracked visor from a spray of debris": frozenset({"open-space"}),
    "shielding a suited crewmate from a spray of debris": frozenset({"open-space"}),
    "signalling a distant rescue lander with a flare": frozenset({"open-space"}),
    "skimming the top of a storm band": frozenset({"sky", "cloud-deck"}),
    "shoving a tumbling hull plate out of their path": frozenset({"open-space"}),
    "spinning down through a lightning front": frozenset({"gravity", "sky", "cloud-deck"}),
    "spinning up a cutting beam against a derelict hull": frozenset({"open-space"}),
    "sweeping a helmet beam across a derelict hull": frozenset({"open-space"}),
    "sweeping a sensor beam across a field of debris": frozenset({"open-space"}),
    "sweeping a sensor beam through a storm band": frozenset({"sky", "cloud-deck"}),
    "guiding a cargo pod in a tractor beam": frozenset({"open-space"}),
    "trailing smoke as it drops through a storm band": frozenset({"gravity", "sky", "cloud-deck"}),
    "tumbling away from a hull after a suit-thruster failure": frozenset({"open-space"}),
    "tumbling end over end through the clouds": frozenset({"gravity", "sky", "cloud-deck"}),
    "tumbling end over end with a thruster pack jammed open": frozenset({"open-space"}),
    "waiting on a launch platform": frozenset({"floor"}),
    "watching a starship burn past at close range": frozenset({"open-space"}),
    "weaving through towering cloud columns at speed": frozenset({"sky", "cloud-deck"}),
    "welding a plate over a hull breach": frozenset({"open-space", "structure"}),
    "wrenching loose from a magnetic clamp": frozenset({"open-space"}),
})
VALUE_STANCES[SITUATION_FIELD].update({
    "tumbling into a debris cloud after a glancing collision": frozenset({"floats"}),
    "being struck by a tumbling fragment of hull": frozenset({"floats"}),
    "bracing against the kick of a rivet driver": frozenset({"floats"}),
    "breaking up as it falls through the cloud tops": frozenset({"falls"}),
    "chasing a spinning fragment through the debris": frozenset({"floats"}),
    "clinging to a spinning hull plate": frozenset({"floats"}),
    "clinging to the outside of a tumbling escape pod": frozenset({"floats"}),
    "deploying a spread of smaller sensor drones": frozenset({"floats"}),
    "diving through a break in the cloud tops": frozenset({"flies", "hovers"}),
    "dodging a tumbling hull fragment": frozenset({"floats"}),
    "drifting beside a shattered viewport": frozenset({"floats"}),
    "fighting a crosswind above the cloud tops": frozenset({"flies", "hovers"}),
    "firing a short thruster burst to hold position": frozenset({"floats"}),
    "firing suit thrusters toward a crewmate in a sealed suit": frozenset({"floats"}),
    "grabbing a spinning toolkit before it drifts away": frozenset({"floats"}),
    "grappling with a boarder in open vacuum": frozenset({"floats"}),
    "carrying an unconscious crewmate in a sealed suit": frozenset({"floats"}),
    "latching onto a hull with magnetic grapples": frozenset({"floats"}),
    "sealing a hull breach from the outside": frozenset({"floats"}),
    "planting a magnetic beacon on a drifting asteroid": frozenset({"floats"}),
    "dropping through the cloud tops in two pieces": frozenset({"falls"}),
    "punching through a curtain of rain": frozenset({"flies", "hovers"}),
    "pushing off from a hull toward a drifting cargo pod": frozenset({"floats"}),
    "racing a lightning front across the cloud tops": frozenset({"flies", "hovers"}),
    "reeling in a drifting survey probe": frozenset({"floats"}),
    "releasing a damaged survey probe into a slow tumble": frozenset({"floats"}),
    "manoeuvring through a debris field on suit thrusters": frozenset({"floats"}),
    "scanning a drifting wreck with a fan of sensor beams": frozenset({"floats"}),
    "sealing a cracked viewport with a foam spray": frozenset({"floats"}),
    "shaking in the turbulence above a storm": frozenset({"flies", "hovers"}),
    "shedding burning plates as it falls": frozenset({"falls"}),
    "shepherding a drifting survey probe back to its bay": frozenset({"floats"}),
    "shielding a cracked visor from a spray of debris": frozenset({"floats"}),
    "shielding a suited crewmate from a spray of debris": frozenset({"floats"}),
    "signalling a distant rescue lander with a flare": frozenset({"floats"}),
    "skimming the top of a storm band": frozenset({"flies", "hovers"}),
    "shoving a tumbling hull plate out of their path": frozenset({"floats"}),
    "spinning down through a lightning front": frozenset({"falls"}),
    "spinning up a cutting beam against a derelict hull": frozenset({"floats"}),
    "sweeping a helmet beam across a derelict hull": frozenset({"floats"}),
    "sweeping a sensor beam across a field of debris": frozenset({"floats"}),
    "guiding a cargo pod in a tractor beam": frozenset({"floats"}),
    "trailing smoke as it drops through a storm band": frozenset({"falls"}),
    "tumbling away from a hull after a suit-thruster failure": frozenset({"floats"}),
    "tumbling end over end through the clouds": frozenset({"falls"}),
    "tumbling end over end with a thruster pack jammed open": frozenset({"floats"}),
    "watching a starship burn past at close range": frozenset({"floats"}),
    "weaving through towering cloud columns at speed": frozenset({"flies", "hovers"}),
    "welding a plate over a hull breach": frozenset({"floats"}),
    "wrenching loose from a magnetic clamp": frozenset({"floats"}),
})
VALUE_NEEDS[CONTEXT_FIELD].update({
    "lightning front below": frozenset({"sky", "cloud-deck"}),
    "terraforming processor tower on the horizon": frozenset({"ground", "structure"}),
    "bay door standing open on the dark": frozenset({"floor", "structure"}),
    "ladder rising into the dark": frozenset({"floor", "structure"}),
})


SITUATION_TIERS.update({
    "swelling to twice its size": "event",
    "writhing in a tight coil": "event",
    "surging over a barricade in one wave": "event",
})
VALUE_NEEDS["situation"].update({
    "swelling to twice its size": frozenset(),
    "writhing in a tight coil": frozenset(),
    "surging over a barricade in one wave": frozenset(),
})
VALUE_NEEDS["appendages"] = {
    "peeled hull-skin strip": frozenset({"gravity"}),
    "drifting debris cluster": frozenset({"open-space"}),
}
SITUATION_TIERS.update({
    "passing a vent chimney": "activity",
    "running a sonar sweep along the trench floor": "activity",
    "fighting a flooding compartment": "event",
    "collecting samples from a mineral chimney": "activity",
    "drifting end over end through the void": "activity",
    "trailing a slow cloud of hull fragments": "activity",
})
VALUE_NEEDS["situation"].update({
    "passing a vent chimney": frozenset({"submerged"}),
    "running a sonar sweep along the trench floor": frozenset({"submerged"}),
    "fighting a flooding compartment": frozenset({"structure"}),
    "collecting samples from a mineral chimney": frozenset({"submerged"}),
    "drifting end over end through the void": frozenset({"open-space"}),
    "trailing a slow cloud of hull fragments": frozenset({"open-space"}),
})


SITUATION_TIERS.update({
    "punching through the top of a storm band": "activity",
})
VALUE_NEEDS["situation"].update({
    "diving clear of a falling beam": frozenset({"gravity", "structure"}),
    "unloading cargo pods onto a landing pad": frozenset({"ground"}),
    "crossing a star field in silhouette": frozenset({"open-space"}),
    "punching through the top of a storm band": frozenset({"sky", "cloud-deck"}),
})


VALUE_NEEDS["situation"].update({
})


# ---------------------------------------------------------------------------
# Stance and body vocabularies -- read only by tests/validate_data.py
# ---------------------------------------------------------------------------

#: ``{stance: (keyword, ...)}`` -- words that say how a body moves. A situation naming
#: one must declare that stance, or it is drawn by a form that cannot move that way.
STANCE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "rolls": ("wheel", "wheels", "hub", "axle", "tread", "treads", "track", "tracks", "ruts"),
    "walks": ("hip", "knee", "leg", "legs", "stride", "striding", "stamping", "stumbling"),
    "flies": ("banking", "thermals", "wingtip", "glide", "gliding", "stalling", "soaring"),
    "swims": ("swimming", "surfacing", "ballast"),
    "hovers": ("hovering", "skimming", "lift fan", "lift fans", "hover skirt"),
    "floats": ("thruster pack", "drifts away", "tumbling away"),
    "falls": ("as it falls", "falls through", "drops through", "plunging toward"),
}

#: ``{type, type group or kind: features}`` -- what a body has.
BODY_FEATURES: dict[str, frozenset[str]] = {
    "starship": frozenset({"wings", "arms", "jets"}),
    "space station": frozenset({"wings", "arms", "jets"}),
    "wreck": frozenset(),
    "alien artifact": frozenset({"crust"}),
    "spacefarer": frozenset({"arms", "hands", "head", "jets"}),
    "alien people": frozenset({"arms", "hands", "head", "jets"}),
    "robot or mech": frozenset(),
    "humanoid unit": frozenset({"arms", "hands", "head", "legs"}),
    "small drone": frozenset({"jets"}),
    "heavy chassis": frozenset({"legs", "tracks"}),
    "static unit": frozenset({"tracks"}),
    "surface vehicle": frozenset({"arms"}),
    "wheeled/tracked": frozenset({"arms", "tracks"}),
    "hovering": frozenset({"jets"}),
    "flying": frozenset({"wings", "jets"}),
    "lander": frozenset({"jets"}),
    "underwater": frozenset(),
    "celestial body": frozenset({"jets"}),
    "solid world": frozenset({"crust", "poles"}),
    "gas world": frozenset({"poles", "cloud-bands", "tail"}),
    "small body": frozenset({"crust", "tail"}),
    "star body": frozenset({"poles", "corona", "jets"}),
    "binary system": frozenset({"corona", "jets"}),
    "singularity": frozenset({"poles", "accretion", "jets"}),
    "diffuse cloud": frozenset(),
    "disc system": frozenset({"rings"}),
    "alien creature": frozenset({"jaws", "head", "legs", "limbs"}),
    "tentacular": frozenset({"jaws", "head", "arms", "limbs"}),
    "segmented": frozenset({"jaws", "head", "spines", "legs", "limbs"}),
    "vermiform": frozenset({"jaws", "head", "coils"}),
    "winged": frozenset({"jaws", "head", "wings", "tail"}),
    "aquatic": frozenset({"jaws", "head", "gills", "tail"}),
    "amorphous": frozenset(),
    "sessile growth": frozenset({"spores"}),
    "quadrupedal": frozenset({"jaws", "head", "spines", "tail", "legs", "limbs"}),
    "upright hunter": frozenset({"jaws", "head", "arms", "tail", "legs", "limbs"}),
    "diffuse being": frozenset(),
    "void dweller": frozenset(),
    "radial form": frozenset({"jaws", "spines"}),
    "stone feeder": frozenset({"jaws", "spines", "legs", "limbs"}),
    "caste swarm": frozenset({"jaws", "head", "legs", "limbs"}),
    "mimic body": frozenset(),
    "filter swarm": frozenset({"gills"}),
    "symbiotic body": frozenset({"spores"}),
    "brooding colony": frozenset({"spores", "spines"}),
}

#: Phrases that name the subject's own part. A word that more often names the place or
#: another object ("canyon", "hull") is deliberately absent.
BODY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "arms": ("tool arm", "severed arm", "sampling arm", "drill arm", "its shoulders", "its fist",
             "docking arm", "assembly arms"),
    "hands": ("open hands", "by the wrist"),
    "head": ("its head", "its snout"),
    "jaws": ("its jaws", "snapping at", "caustic bile"),
    "spines": ("spines", "quills"),
    "gills": ("gill", "gills"),
    "spores": ("spores", "spore"),
    "wings": ("wing", "wings", "wingtip"),
    "coils": ("coiling", "defensive coil"),
    "tail": ("tail",),
    "crust": ("crust", "continent", "fracture", "geysers"),
    "poles": ("pole", "poles", "polar"),
    "cloud-bands": ("cloud bands", "cloud belts", "storm oval", "aurora", "auroras"),
    "corona": ("corona", "coronal", "prominence", "sunspots"),
    "accretion": ("accretion", "event horizon"),
    "rings": ("rings", "ringlet", "ring ice", "ring particles", "ring bands"),
    "limbs": ("limb", "limbs"),
}
BODY_LINT_FIELDS: tuple[str, ...] = ("situation",)

#: ``{feature: (keyword, ...)}`` -- the words that name a body structure in a *part*.
#: Separate from ``BODY_KEYWORDS`` because a situation that names a track ("throwing a
#: track at speed") is legal for a tracked body and excluded at runtime by the stance
#: check, while a *part* is bolted on with no such escape.
PART_KEYWORDS: dict[str, tuple[str, ...]] = {
    "tracks": ("track", "tracks", "tread", "treads", "axle", "wheel", "wheels"),
    "legs": ("leg", "legs", "strut", "struts", "stilt", "stilts"),
    "jets": ("thruster", "thrusters", "nozzle", "nozzles", "exhaust", "nacelle",
             "jet", "jets", "drive plume"),
}
PART_LINT_FIELDS: tuple[str, ...] = (
    "appendages", "armament", "extras", "emitters", "sensors", "aperture",
)



VALUE_STANCES[SITUATION_FIELD].update({
    "breaking up as it falls": frozenset({"falls"}),
    "bursting a hub against an obstacle": frozenset({"rolls"}),
    "circling a landing site": frozenset({"flies", "hovers"}),
    "flipping onto its back on a hard turn": frozenset({"hovers", "rolls", "walks"}),
    "following a set of wheel ruts": frozenset({"rolls"}),
    "passing a vent chimney": frozenset(),
    "hovering above a fallen plinth": frozenset({"hovers"}),
    "hovering just above a plinth": frozenset({"hovers"}),
    "losing a wheel at full throttle": frozenset({"rolls"}),
    "racing a storm front toward shelter": frozenset({"hovers", "rolls", "walks"}),
    "ramming a barricade at full speed": frozenset({"hovers", "rolls", "walks"}),
    "shearing a tread on a jagged edge": frozenset({"rolls"}),
    "snapping an axle on a hard landing": frozenset({"rolls"}),
    "spinning out at full throttle": frozenset({"hovers", "rolls", "walks"}),
    "spraying mud from its tracks": frozenset({"rolls"}),
    "crossing cracked ground": frozenset({"walks"}),
    "throwing a track at speed": frozenset({"rolls"}),
})


SITUATION_TIERS.update({
    "being crushed in a rockfall": "event",
    "being flung into a cloud bank by a gust": "event",
    "burning through re-entry in a sheath of plasma": "event",
    "digging itself out of a drift": "event",
    "drifting between vent chimneys": "activity",
    "extending a boarding ramp onto a deck": "activity",
    "gliding in to land beside a supply dome": "activity",
    "holding position beside a docking cradle": "idle",
    "holding station against a crosswind": "idle",
    "losing a lift-pod panel in a violent gust": "event",
    "losing buoyancy and settling into the silt": "event",
    "opening its cargo bay onto a loading pad": "activity",
    "pulling up hard out of a canyon dive": "event",
    "recovering a probe from the seabed": "activity",
    "riding a thermal updraft over a storm band": "idle",
    "rolling to a stop inside a hangar": "activity",
    "settling onto a landing platform": "activity",
    "stalling in a crosswind above a canyon": "event",
    "surfacing through a sheet of ice": "event",
    "sweeping a sensor beam across the cloud tops": "activity",
    "tumbling out of control after a lightning strike": "event",
    "waiting on a launch platform": "idle",
})
TAGS[SITUATION_FIELD].update({
    "being crushed in a rockfall": "conflict_only",
    "being flung into a cloud bank by a gust": "conflict_only",
    "gliding in to land beside a supply dome": "peaceful_only",
    "losing a lift-pod panel in a violent gust": "conflict_only",
    "tumbling out of control after a lightning strike": "conflict_only",
})
VALUE_NEEDS["situation"].update({
    "being crushed in a rockfall": frozenset({"ground"}),
    "being flung into a cloud bank by a gust": frozenset({"sky", "cloud-deck"}),
    "burning through re-entry in a sheath of plasma": frozenset({"sky"}),
    "digging itself out of a drift": frozenset({"ground"}),
    "drifting between vent chimneys": frozenset({"submerged"}),
    "extending a boarding ramp onto a deck": frozenset({"floor"}),
    "gliding in to land beside a supply dome": frozenset({"sky"}),
    "holding position beside a docking cradle": frozenset({"floor"}),
    "holding station against a crosswind": frozenset({"sky"}),
    "losing a lift-pod panel in a violent gust": frozenset({"sky"}),
    "losing buoyancy and settling into the silt": frozenset({"submerged"}),
    "opening its cargo bay onto a loading pad": frozenset({"floor"}),
    "pulling up hard out of a canyon dive": frozenset({"sky"}),
    "recovering a probe from the seabed": frozenset({"submerged"}),
    "riding a thermal updraft over a storm band": frozenset({"sky", "cloud-deck"}),
    "rolling to a stop inside a hangar": frozenset({"floor"}),
    "settling onto a landing platform": frozenset({"floor"}),
    "stalling in a crosswind above a canyon": frozenset({"sky"}),
    "surfacing through a sheet of ice": frozenset({"submerged", "cold"}),
    "sweeping a sensor beam across the cloud tops": frozenset({"sky", "cloud-deck"}),
    "tumbling out of control after a lightning strike": frozenset({"sky"}),
    "waiting on a launch platform": frozenset({"floor"}),
})



SITUATION_TIERS.update({
    "ascending a maintenance shaft": "activity",
    "being gripped by a tentacled creature": "event",
    "breaking up in a violent gust": "event",
    "cracking its hull under crushing pressure": "event",
    "crash-landing on its belly in a spray of dust": "event",
    "docking at a charging cradle": "idle",
    "gliding in to land beside a supply dome": "activity",
    "losing a lift-pod panel in a violent gust": "event",
    "releasing a spread of survey probes over the plain": "activity",
    "rolling along a corridor on a maintenance run": "activity",
    "rolling along a trench floor": "activity",
    "shaking in the turbulence above a storm": "activity",
    "soaring above a canyon on its gravlift pods": "activity",
    "sweeping a corridor with its optics": "activity",
    "tipping one lift pod over a volcanic vent": "activity",
    "sweeping a sampling scoop through an ash plume": "activity",
    "trailing a stream of bubbles from a breach": "event",
    "waiting beside a sealed hatch": "idle",
})
TAGS[SITUATION_FIELD].update({
    "being gripped by a tentacled creature": "conflict_only",
    "breaking up in a violent gust": "conflict_only",
    "cracking its hull under crushing pressure": "conflict_only",
    "crash-landing on its belly in a spray of dust": "conflict_only",
    "gliding in to land beside a supply dome": "peaceful_only",
    "losing a lift-pod panel in a violent gust": "conflict_only",
})
VALUE_NEEDS["situation"].update({
    "ascending a maintenance shaft": frozenset({"structure"}),
    "being gripped by a tentacled creature": frozenset({"submerged"}),
    "breaking up in a violent gust": frozenset({"sky"}),
    "cracking its hull under crushing pressure": frozenset({"submerged"}),
    "crash-landing on its belly in a spray of dust": frozenset({"ground"}),
    "docking at a charging cradle": frozenset({"floor"}),
    "gliding in to land beside a supply dome": frozenset({"ground"}),
    "losing a lift-pod panel in a violent gust": frozenset({"sky"}),
    "releasing a spread of survey probes over the plain": frozenset({"sky"}),
    "rolling along a corridor on a maintenance run": frozenset({"floor", "structure"}),
    "rolling along a trench floor": frozenset({"submerged"}),
    "shaking in the turbulence above a storm": frozenset({"sky"}),
    "soaring above a canyon on its gravlift pods": frozenset({"ground", "sky"}),
    "sweeping a corridor with its optics": frozenset({"structure"}),
    "tipping one lift pod over a volcanic vent": frozenset({"sky"}),
    "sweeping a sampling scoop through an ash plume": frozenset({"sky"}),
    "trailing a stream of bubbles from a breach": frozenset({"submerged"}),
    "waiting beside a sealed hatch": frozenset({"structure"}),
})
VALUE_STANCES[SITUATION_FIELD].update({
    "gliding in to land beside a supply dome": frozenset({"flies"}),
    "stalling in a crosswind above a canyon": frozenset({"flies"}),
    "surfacing through a sheet of ice": frozenset({"swims"}),
})


SITUATION_TIERS.update({
    "being crushed by a closing hatch": "event",
    "being knocked from its cradle by a swinging cargo arm": "event",
    "folding its landing struts on contact": "event",
    "grinding to a halt against a bulkhead": "event",
    "slamming into a landing platform in a burst of dust": "event",
    "tearing loose from a tie-down clamp": "event",
})
TAGS[SITUATION_FIELD].update({
    "being crushed by a closing hatch": "conflict_only",
    "being knocked from its cradle by a swinging cargo arm": "conflict_only",
    "folding its landing struts on contact": "conflict_only",
    "grinding to a halt against a bulkhead": "conflict_only",
    "slamming into a landing platform in a burst of dust": "conflict_only",
    "tearing loose from a tie-down clamp": "conflict_only",
})
VALUE_NEEDS["situation"].update({
    "being crushed by a closing hatch": frozenset({"structure"}),
    "being knocked from its cradle by a swinging cargo arm": frozenset({"floor"}),
    "folding its landing struts on contact": frozenset({"floor"}),
    "grinding to a halt against a bulkhead": frozenset({"structure"}),
    "slamming into a landing platform in a burst of dust": frozenset({"floor"}),
    "tearing loose from a tie-down clamp": frozenset({"floor"}),
})
VALUE_STANCES[SITUATION_FIELD].update({
    "soaring above a canyon on its gravlift pods": {'flies'},
})


VALUE_STANCES[SITUATION_FIELD].update({
    "churning up a spray of grit": frozenset({"rolls", "walks"}),
    "raising a cloud of grit": frozenset({"rolls", "walks"}),
    "sliding sideways on loose gravel": frozenset({"rolls"}),
})


SITUATION_TIERS.update({
    "being bored into by automated drill rigs": "activity",
    "being gouged by a rust-brown moon plunging through its rings": "event",
    "being scattered by a passing black hole": "event",
    "being struck by a moon-sized impactor": "event",
    "being torn apart by a supernova shock front": "event",
    "being torn into a stream of debris by a passing star": "event",
    "blasting a coronal mass ejection toward a nearby world": "event",
    "breaking into a string of fragments along its orbit": "event",
    "bursting a new storm up through its cloud bands": "event",
    "capturing a comet into a tightening spiral": "activity",
    "carrying the dark disc of a transiting moon across its cloud bands": "idle",
    "churning a storm oval wider than a moon": "event",
    "collapsing into a ring of newborn stars": "event",
    "colliding two ring bands in a shower of ice": "event",
    "consuming an orbiting planet in a long streamer of fire": "event",
    "cracking apart as a rust-red companion moon grazes it": "event",
    "crackling with lightning storms along its cloud bands": "event",
    "drawing a pale-violet moon apart into a new ring": "event",
    "erupting a column of lava that arcs out into space": "event",
    "erupting in a storm of sunspots across its face": "activity",
    "firing twin plasma beams from its poles": "event",
    "flaring as a cloud of debris spirals in": "event",
    "flaring as a star detonates inside it": "event",
    "flaring as its two cores spiral closer": "event",
    "flaring hard enough to scour a nearby ochre moon": "event",
    "flaring into a coma of dust as it warms": "activity",
    "flaring vast auroras over both poles": "activity",
    "flickering as a shattered moon crosses its event horizon": "event",
    "hurling a looping prominence far off its surface": "event",
    "igniting a cluster of new stars along its edge": "event",
    "losing a vast plume of vapour into space": "event",
    "merging its two cores in a single detonation": "event",
    "outgassing plumes of vapour from a sunward crack": "activity",
    "raining ring debris down onto a nearby blue-green moon": "event",
    "rippling as a shock wave crosses it": "event",
    "rippling with spiral storms after a comet strike": "event",
    "rippling with spiral waves from a passing moon": "activity",
    "scattering into a spray of ice after an impact": "event",
    "shattering under a mining charge": "event",
    "shedding a long tail of gas toward a nearby star": "activity",
    "shedding a ring of gas from its equator": "activity",
    "shedding a ring of ice from its equator": "event",
    "shedding a spray of ice fragments into space": "event",
    "shedding its outer crust in a spreading debris ring": "event",
    "shredding a wandering planet into its disc": "event",
    "sparkling with ice crystals where a comet crossed it": "activity",
    "spiralling ring particles into a gap": "activity",
    "splitting along a molten rift that runs across its whole face": "event",
    "splitting its rings around a shepherd moon": "activity",
    "splitting open as it spins too fast": "event",
    "spraying chunks of ice from a fresh impact": "event",
    "streaming a long filament toward another cloud": "activity",
    "swallowing a comet in a flash across its cloud tops": "event",
    "swallowing a starship caught in its accretion disc": "event",
    "sweeping a pulsar beam across the dust around it": "activity",
    "swelling as its outer layers boil away": "event",
    "tearing a passing star into a long spiral stream": "event",
    "tearing a starship apart in a spray of ring ice": "event",
    "tearing a stream of plasma from a companion star": "event",
    "throwing a ring of ejecta into orbit after a giant impact": "event",
    "herding a scatter of small moons across its face": "idle",
    "trading a bridge of plasma between its two stars": "activity",
    "trailing a long twin tail of dust and gas": "activity",
    "tumbling end over end past a larger world": "activity",
    "twisting into a kinked ringlet": "activity",
    "venting a plume of ice crystals from a polar storm": "event",
    "wrapping a torn nebula into its disc": "event",
})
TAGS[SITUATION_FIELD].update({
    "being bored into by automated drill rigs": "peaceful_only",
    "being gouged by a rust-brown moon plunging through its rings": "conflict_only",
    "being scattered by a passing black hole": "conflict_only",
    "being struck by a moon-sized impactor": "conflict_only",
    "being torn apart by a supernova shock front": "conflict_only",
    "being torn into a stream of debris by a passing star": "conflict_only",
    "blasting a coronal mass ejection toward a nearby world": "conflict_only",
    "consuming an orbiting planet in a long streamer of fire": "conflict_only",
    "cracking apart as a rust-red companion moon grazes it": "conflict_only",
    "drawing a pale-violet moon apart into a new ring": "conflict_only",
    "flaring hard enough to scour a nearby ochre moon": "conflict_only",
    "merging its two cores in a single detonation": "conflict_only",
    "scattering into a spray of ice after an impact": "conflict_only",
    "shattering under a mining charge": "conflict_only",
    "shedding its outer crust in a spreading debris ring": "conflict_only",
    "shredding a wandering planet into its disc": "conflict_only",
    "swallowing a starship caught in its accretion disc": "conflict_only",
    "tearing a passing star into a long spiral stream": "conflict_only",
    "tearing a starship apart in a spray of ring ice": "conflict_only",
    "throwing a ring of ejecta into orbit after a giant impact": "conflict_only",
})


SITUATION_TIERS.update({
    "pulling a stream of gas into a tight knot": "activity",
    "spitting a stream of particles from its poles": "event",
    "sweeping a gap clean of ring particles": "activity",
})
TAGS[SITUATION_FIELD].update({
})



_TRAIT_ADDITIONS: dict[str, tuple[str, ...]] = {
    "survey drone": ("civil-role",),
    "courier drone": ("civil-role",),
    "android": ("civil-role",),
    # A crew role whose job is not fighting. Every spacefarer weapon carries
    # ``military-weapon``, so this empties the field rather than saying the
    # person is unarmed -- a scientist reading an instrument was being drawn
    # holding a pistol. The roles left armed are the ones a viewer expects armed:
    # pilot, captain, salvager, smuggler, marine, mercenary, raider, bounty
    # hunter, warlord.
    "engineer": ("civil-role",),
    "scientist": ("civil-role",),
    "colonist": ("civil-role",),
    "navigator": ("civil-role",),
    "crew technician": ("civil-role",),
    "prospector": ("civil-role",),
    "quartermaster": ("civil-role",),
    "archaeologist": ("civil-role",),
    "cartographer": ("civil-role",),
    "grey-skinned archivist": ("civil-role",),
    "tendril-faced navigator": ("civil-role",),
    "four-armed quartermaster": ("civil-role",),
    "mandibled envoy": ("civil-role", "pacifist-role"),
    "amphibian admiral": ("civil-role",),
    "translucent medic": ("civil-role", "medical-role"),
    "swarm drone": ("combat-role",),
    "scout walker": ("combat-role",),
    "siege mech": ("combat-role", "inherently-large"),
    "combat mech": ("inherently-large",),
    "terraforming walker": ("inherently-large",),
    "mining loader": ("inherently-large",),
    "heavy freighter": ("inherently-large",),
    "monolith": ("inherently-large",),
    "obelisk": ("inherently-large",),
    "sealed gateway": ("inherently-large",),
    "resonant lattice spire": ("inherently-large",),
    "alien engine": ("inherently-large",),
    "welding drone": ("labour-role", "inherently-small"),
    "exosuit walker": ("labour-role",),
    "memory shard": ("inherently-small",),
}
for _value, _added in _TRAIT_ADDITIONS.items():
    VALUE_TRAITS.setdefault("subkind", {})
    VALUE_TRAITS["subkind"][_value] = tuple(VALUE_TRAITS["subkind"].get(_value, ())) + _added
VALUE_TRAITS.setdefault("armament", {})
for _weapon in ("shoulder-mounted missile tube", "plasma charge harness",
                "magnetic slug thrower", "shoulder-braced arc lance"):
    VALUE_TRAITS["armament"][_weapon] = tuple(
        VALUE_TRAITS["armament"].get(_weapon, ())
    ) + ("heavy-weapon",)

TRAIT_CONFLICTS = TRAIT_CONFLICTS + (
    ("pristine-state", "destruction-act"),
    ("civil-role", "military-weapon"),
    ("civil-role", "hostile-act"),
    ("inherently-large", "small-scale"),
    ("legless-plan", "leg-appendage"),
)
_TRAIT_REASONS.update({
    "pristine-state|destruction-act":
        "a thing just out of the yard is not also coming apart",
    "civil-role|military-weapon": "a survey or courier machine does not carry a weapon",
    "civil-role|hostile-act": "a survey or courier machine does not fight",
    "inherently-large|small-scale": "a large machine or monument is never drawn small",
    "legless-plan|leg-appendage": "a body with no legs does not grow a leg",
})


# ---------------------------------------------------------------------------
# Round XIII -- the axes the 915 batch exposed
# ---------------------------------------------------------------------------
#
# Every table here is an ``update`` and this is the last word in the module, so
# none of it can be undone by an earlier rebinding. The pattern is additive for
# the same reason ``_TRAIT_ADDITIONS`` is: a value may already carry a trait.

def _add_traits(field: str, additions: dict) -> None:
    """Union ``{value: (trait, ...)}`` into a field's trait map."""
    VALUE_TRAITS.setdefault(field, {})
    for _v, _added in additions.items():
        VALUE_TRAITS[field][_v] = tuple(
            dict.fromkeys(tuple(VALUE_TRAITS[field].get(_v, ())) + _added)
        )


#: Water fills the place. Fire does not burn in one, and the batch had a diver
#: dragging a crewmate "clear of a fire" at the bottom of a trench and an
#: ice-cutting crawler "catching fire" in an ocean.
_add_traits(ENVIRONMENT_FIELD, {
    "deep ocean trench of a water world": ("aqueous",),
    "subglacial ocean of an ice moon": ("aqueous",),
    "hydrothermal vent field of a water world": ("aqueous",),
})

#: An open flame. Kept apart from ``fire-word-not-fire``, which is about
#: "taking fire" meaning gunfire: these are the values that really do burn.
_add_traits(SITUATION_FIELD, {
    value: ("combustion",)
    for value in (
        "shedding burning plates as it falls",
        "burning through re-entry in a sheath of plasma",
    )
})

#: The thermal axis, on the two fields that were contradicting each other: a
#: "lava world" whose crust is "methane ice", and a "volcanic moon" venting
#: "cryovolcanic plumes". ``frost-bound|heat-scarred`` already existed, but only
#: in the direction that lets a material overrule a subkind -- and the subkind is
#: drawn first and names the whole body, so it has to be the one that stands.
_add_traits("subkind", {
    "lava world": ("heat-scarred",),
    "volcanic moon": ("heat-scarred",),
    "ice moon": ("frost-bound",),
    "ice giant": ("frost-bound",),
})
_add_traits("emitters", {
    "lava fissure": ("heat-scarred",),
    "volcanic vent": ("heat-scarred",),
    "ember-hot fissure": ("heat-scarred",),
    "cryovolcanic plume vent": ("frost-bound",),
    "sublimating ice fissure": ("frost-bound",),
})
_add_traits("appendages", {
    "cryovolcanic plume": ("frost-bound",),
    "ice plume": ("frost-bound",),
})

#: More of the same act. Every value verified against the pools it is drawn
#: from -- a trait naming a value the pack does not have is a silent no-op, and
#: this table only earns its place if it fires.
_add_traits(SITUATION_FIELD, {
    value: ("destruction-act",)
    for value in (
        "venting white vapour from a torn flank",
        "splitting open along freshly-formed seams",
        "collapsing into a trailing field of wreckage",
        "giving way under a salvage drone's cutting beam",
        "tearing open along a frost-welded seam",
        "shedding its outer crust in a spreading debris ring",
        "splitting along a deep fissure system",
        "coming apart along one long seam",
        "breaking up as it falls through the cloud tops",
        "dropping through the cloud tops in two pieces",
    )
})

TRAIT_CONFLICTS = TRAIT_CONFLICTS + (
    ("aqueous", "combustion"),
    ("heat-scarred", "frost-bound"),
)
_TRAIT_REASONS.update({
    "aqueous|combustion": "nothing burns at the bottom of an ocean",
    "heat-scarred|frost-bound": "a molten body does not also wear ice",
})

#: Every value of a tiered field must carry a tier, so the four submerged
#: additions above are priced here rather than left for the validator to find.
SITUATION_TIERS.update({
    "blowing ballast in a rush of silt": "activity",
    "cutting a snarl of cable away with a manipulator": "activity",
    "tilting hard as a vent plume slams into its flank": "event",
    "punching through a curtain of rising bubbles": "event",
})

#: Each of the four is written for one place and says so, and the ballast line
#: says the body swims, so it declares that as well. Adding a value without its
#: whole card is what the affordance and stance lints exist to catch.
VALUE_NEEDS[SITUATION_FIELD].update({
    "blowing ballast in a rush of silt": frozenset({"submerged"}),
    "cutting a snarl of cable away with a manipulator": frozenset({"submerged"}),
    "tilting hard as a vent plume slams into its flank": frozenset({"submerged"}),
    "punching through a curtain of rising bubbles": frozenset({"submerged"}),
})
VALUE_STANCES[SITUATION_FIELD].update({
    "blowing ballast in a rush of silt": frozenset({"swims"}),
    "cutting a snarl of cable away with a manipulator": frozenset({"swims"}),
    "tilting hard as a vent plume slams into its flank": frozenset({"swims"}),
    "punching through a curtain of rising bubbles": frozenset({"swims"}),
})


# Task 10 residual: values the concern instrument reads as needing ground, and a
# serpentine chassis that does not walk.
VALUE_NEEDS["situation"].update({
    "pulling up hard out of a canyon dive": frozenset({"ground", "sky"}),
    "stalling in a crosswind above a canyon": frozenset({"ground", "sky"}),
    "dropping toward a landing pad on its belly thrusters": frozenset({"ground"}),
})
VALUE_STANCES[SITUATION_FIELD].update({
    # Round XII: a drone that examines a wreck is a machine, and the value says
    # nothing about how the observer holds itself up.
    "being examined by a survey drone": frozenset(),
})
VALUE_STANCES["form"].update({
    "serpentine segmented chassis": frozenset({"rests"}),
})


# ---------------------------------------------------------------------------
# Round XIV -- the 0916 batch
# ---------------------------------------------------------------------------
#
# The last word in the module, like round XIII, so nothing earlier can undo it.
# Each block declares one relationship; the conflicts it needs are appended at
# the end of the section.

_ROUND_XIV_SITUATIONS = (
    _MACHINE_EVENTS + _DIFFUSE_ACTS + (
        "turning a slow circle to map its surroundings",
        "shouldering through a cascade of loose debris",
        "turning to follow a sudden movement",
        "snapping every frond open at once",
    )
)
TAGS[SITUATION_FIELD].update({
    value: "neutral"
    for value in _ROUND_XIV_SITUATIONS + _WRECK_ACTS + _STATION_ACTS + _STARSHIP_ACTS
})
SITUATION_TIERS.update({
    "resting on its side against a ridge": "idle",
    "being picked over by a pair of salvage drones": "activity",
    "lying half-buried under drifted dust": "idle",
    "turning slowly to show its gutted interior": "activity",
    "lying in two pieces across a shallow valley": "event",
    "extending a boarding bridge to a docked starship": "activity",
    "releasing a string of cargo pods on a slow drift": "activity",
    "rotating a sensor array toward the far stars": "idle",
    "guiding a small starship into an open docking bay": "activity",
    "spreading a swarm of repair drones across its hull": "event",
    "spinning its habitat ring up to speed": "event",
    "catching a drifting cargo pod in a docking cradle": "event",
    "towing a disabled shuttlecraft in a tractor beam": "event",
    "recovering a probe into a side bay": "activity",
    "passing close along a derelict's flank": "activity",
    "arriving out of a jump in a ripple of distortion": "event",
    "swinging hard around a tumbling asteroid": "event",
})
VALUE_NEEDS[SITUATION_FIELD].update({
    "resting on its side against a ridge": frozenset({"ground"}),
    "being picked over by a pair of salvage drones": frozenset(),
    "lying half-buried under drifted dust": frozenset({"ground", "dust"}),
    "turning slowly to show its gutted interior": frozenset({"open-space"}),
    "lying in two pieces across a shallow valley": frozenset({"ground"}),
    **{value: frozenset({"open-space"}) for value in _STATION_ACTS + _STARSHIP_ACTS},
})
#: Place-neutral on purpose: each reads the same in a corridor, a trench or a
#: cloud deck.
VALUE_NEEDS[SITUATION_FIELD].update({value: frozenset() for value in _ROUND_XIV_SITUATIONS})
SITUATION_TIERS.update({
    "snapping every frond open at once": "event",
    "scattering into a swarm of drifting motes": "event",
    "reforming out of a scatter of drifting motes": "activity",
    "pouring through a narrow gap like a liquid": "event",
    "wrapping itself around a flickering light fitting": "activity",
    "swelling to twice its size in a single pulse": "event",
    "swerving hard around a sudden obstacle": "event",
    "slipping through a closing gap at full speed": "event",
    "recoiling from a sudden burst of light": "event",
    "turning a slow circle to map its surroundings": "activity",
    "shouldering through a cascade of loose debris": "event",
    "turning to follow a sudden movement": "activity",
    "rolling slowly to show a torn-open flank": "activity",
    "turning slowly inside a halo of its own debris": "idle",
    "being latched onto by a salvage grapple drone": "event",
})
VALUE_NEEDS[SITUATION_FIELD].update({
    "rolling slowly to show a torn-open flank": frozenset({"open-space"}),
    "turning slowly inside a halo of its own debris": frozenset({"open-space"}),
    "being latched onto by a salvage grapple drone": frozenset({"open-space"}),
    # A hull breach is fought from inside a hull.
    "sealing a hull breach with a foam sprayer": frozenset({"floor", "structure"}),
    # Nothing falls in open space: "a cephalopod tearing into a fallen hull" at
    # a lagrange point was drawn wrapped round a planet.
    "tearing into a fallen hull": frozenset({"ground"}),
    # A gap that closes is a door or a shutter: on a glass plain it had nothing
    # to close.
    "slipping through a closing gap at full speed": frozenset({"structure"}),
})
#: Round XXI replacements for the interior acts that now need a built place.
SITUATION_TIERS.update({
    "stumbling as the ground gives way underfoot": "event",
    "skidding down a loose slope on their heels": "event",
    "diving flat as something streaks low overhead": "event",
    "throwing an arm up against a sudden flare of light": "event",
    "being dragged sideways by a surging current": "event",
    "kicking back from a sudden eruption of silt": "event",
    "losing their grip on a guideline in the current": "event",
    "shining a helmet light into the murk": "activity",
    "hauling themselves along a guideline": "activity",
    "clipping a sample bag to their belt": "activity",
    "checking a depth readout on their wrist": "activity",
    "sweeping a searchlight across the murk": "activity",
    "hovering to draw a sample with a probe": "activity",
    "riding a rising thermal in a slow spiral": "activity",
    "skimming low over a cloud bank at full speed": "event",
})
VALUE_NEEDS[SITUATION_FIELD].update({
    "stumbling as the ground gives way underfoot": frozenset({"ground", "gravity"}),
    "skidding down a loose slope on their heels": frozenset({"ground", "gravity"}),
    "diving flat as something streaks low overhead": frozenset({"ground", "sky"}),
    "throwing an arm up against a sudden flare of light": frozenset({"floor"}),
    "being dragged sideways by a surging current": frozenset({"submerged"}),
    "kicking back from a sudden eruption of silt": frozenset({"submerged"}),
    "losing their grip on a guideline in the current": frozenset({"submerged"}),
    "shining a helmet light into the murk": frozenset({"submerged"}),
    "hauling themselves along a guideline": frozenset({"submerged"}),
    "clipping a sample bag to their belt": frozenset({"floor"}),
    "checking a depth readout on their wrist": frozenset({"submerged"}),
    "sweeping a searchlight across the murk": frozenset({"submerged"}),
    "hovering to draw a sample with a probe": frozenset({"submerged"}),
    "riding a rising thermal in a slow spiral": frozenset({"sky"}),
    # Round XXII: the barricade now needs ground; the cloud decks keep their floor.
    "skimming low over a cloud bank at full speed": frozenset({"sky", "cloud-deck"}),
})
VALUE_STANCES[SITUATION_FIELD].update({
    "stumbling as the ground gives way underfoot": frozenset({"walks"}),
    "hauling themselves along a guideline": frozenset({"floats"}),
    "hovering to draw a sample with a probe": frozenset({"hovers"}),
})

#: **Dormant acts: the closed half of the ``inactive`` axis.** What a thing
#: with no power, crew or intent can be doing -- gravity, drift, decay, and
#: being acted on by something the sentence names. Every situation *not* listed
#: here carries ``powered-act`` (derived below), so a new situation is live until
#: someone declares it dormant. The two hand-kept ``powered-act`` lists this
#: replaced missed "riding a re-entry plasma sheath", "holding station beside a
#: survey beacon" and "crouching to inspect wreckage", each drawn on a dead hull.
#: A wreck act left off this list is filtered from every wreck, and
#: ``scripts/reach_audit.py --gate`` names it as a value nobody draws.
DORMANT_ACTS: frozenset[str] = frozenset({
    # Wrecks, by place.
    "settling deeper into the sand", "breaking up as it falls",
    "being stripped by a swarm of salvage drones",
    "hanging at a steep angle against the stars", "sheltering a nest of hull-borers",
    "grinding against the rock it landed on", "shedding plates into a slow debris trail",
    "being cut open by salvage drones", "disappearing under a creeping fungal mat",
    "being surveyed by a drifting inspection drone", "leaking a slick across the water",
    "collapsing under its own weight", "spilling its contents across the ground",
    "spilling a fan of debris down a slope", "catching the light along a torn edge",
    "slumping as a spar gives way", "breaking apart in a slow avalanche",
    "shedding a slab of plating as it settles",
    "spilling a wave of debris across the ground", "collapsing into the pit it made",
    "tearing open along a rusted seam", "pinning a salvage drone beneath a buckled plate",
    "giving way under a salvage drone's cutting beam",
    "burying a salvage crawler in a slide", "buckling as its main girder gives way",
    "shedding a cascade of plate fragments", "tearing open along a frost-welded seam",
    "crumbling into a field of drifting debris", "coming apart along one long seam",
    "shattering into a spray of fragments", "being examined by a survey drone",
    "breaking up as it falls through the cloud tops",
    "shedding burning plates as it falls", "spinning down through a lightning front",
    "dropping through the cloud tops in two pieces",
    "trailing smoke as it drops through a storm band",
    "tumbling end over end through the clouds", "drifting end over end through the void",
    "trailing a slow cloud of hull fragments",
    "rolling slowly to show a torn-open flank",
    "turning slowly inside a halo of its own debris",
    "being latched onto by a salvage grapple drone",
    "resting on its side against a ridge", "being picked over by a pair of salvage drones",
    "lying half-buried under drifted dust", "turning slowly to show its gutted interior",
    "lying in two pieces across a shallow valley",
    # A mothballed, unfinished or half-built station.
    "carrying a cage of refit scaffolding", "listing badly with half its hull gone",
    "turning its long truss against the light", "passing across the face of a planet",
    "drifting with its bays sealed", "tumbling out of its rotation",
    # Drift and spin need no power, so a world, and a ship a user locked into a
    # dead state, still have something to be doing.
    "drifting across a star field", "rotating through a slow cycle",
    "drifting slowly through the void", "drifting with its engines cold",
    # A half-disassembled artifact.
    "being lifted onto a recovery cradle", "being circled by scanning drones",
    "sinking into the dust it rests on",
    "rotating slowly on its axis", "standing amid a circle of stones",
    "hanging motionless in the open", "cracking open along a seam",
})
_add_traits(SITUATION_FIELD, {
    value: ("powered-act",)
    for pool in SITUATION_POOLS.values()
    for value in pool
    if value not in DORMANT_ACTS
})

#: Every emitter is a light or an exhaust, so a thing with no power shows none.
#: The wreck archetype omits the field outright; this covers a mothballed
#: station and a half-disassembled artifact.
_add_traits("emitters", {
    value: ("emissive",) for pool in EMITTER_POOLS.values() for value in pool
})

#: **A craft is prey only for something big enough, outside.** "A tiny plant-form
#: snaring a passing drone" drew a toy drone, and "a serpent coiling around a
#: captured drone" inside a cockpit drew a creature in one ship seizing another.
_add_traits(ENVIRONMENT_FIELD, {
    value: ("interior-place",) for value in ENVIRONMENT_BANDS["interior"]
})
_add_traits(SITUATION_FIELD, {
    value: ("craft-prey",)
    for value in (
        # Round XV: the small-machine prey acts (a drone, a probe, a cargo pod)
        # left the pool. A model fused the machine to the creature -- "a weird
        # metal thing on the end of its snout" -- so only a craft big enough to
        # read as a second object stays prey.
        "striking at a fleeing shuttlecraft", "tearing into a fallen hull",
        "wrapping around a derelict's hull",
    )
})
#: A creature on the outside of a hull. Indoors the model has to invent a
#: second ship inside the room for it to cross.
_add_traits(SITUATION_FIELD, {
    value: ("outer-hull-act",)
    for value in (
        "flowing across a hull as one body", "swarming across a hull in a moving carpet",
        "seeping through a bulkhead in slow tendrils", "flickering across a whole hull",
        "sweeping a wide arc of light across a hull", "enveloping a drifting hull plate",
    )
})

#: **One thrust source.** Exhaust on the hull plus an act that describes its own
#: plume drew engines firing backwards and downwards at once. The act is the
#: scene, so the emitter gives way and draws a light instead.
_add_traits("emitters", {
    value: ("exhaust-emitter",)
    for value in (
        "ion thruster", "fusion torch nozzle", "plasma vent", "manoeuvring thruster",
        "reactor exhaust port", "drive nacelle", "exhaust nozzle", "manoeuvring vent",
        "drive plume nozzle", "thruster nozzle", "drive thruster nozzle", "thruster vent",
        "drive plume vent", "propulsor ring vent",
    )
})
_add_traits(SITUATION_FIELD, {
    value: ("plume-act",)
    for value in (
        "breaking orbit on a long burn", 
        "burning through re-entry in a sheath of plasma", "decelerating on a long plume",
        "dropping toward a landing pad on its belly thrusters",
        "firing a short thruster burst to hold position",
        "settling onto a landing pad on its thrusters",
        "spinning out with a thruster stuck open", "spilling a white plume from a ruptured hull",
    )
})

#: **A crew does not work calmly beside a monster.** "A marauder uncurling from
#: its cocoon" with "a crew working at the far end" behind it.
VALUE_TRAITS["kind"]["alien creature"] = ("creature-subject",)
_add_traits(CONTEXT_FIELD, {"maintenance drone working at the far end": ("crew-scenery",)})

#: A civil station does not fire on anything: "a terraforming station firing
#: point-defence into a swarm".
_add_traits("subkind", {
    value: ("civil-role",)
    for value in (
        "terraforming tower", "refinery platform", "research outpost", "relay array",
        "observation station", "trade hub", "void monastery", "listening post",
    )
})

#: **A cockpit hatch belongs to a piloted frame.** An android "bears a cockpit
#: hatch" in its chest. The part lint now knows the word, and only the heavy
#: chassis (walkers, loaders, mechs) has the structure.
PART_KEYWORDS["cockpit"] = ("cockpit",)
BODY_FEATURES["heavy chassis"] = BODY_FEATURES["heavy chassis"] | frozenset({"cockpit"})

TRAIT_CONFLICTS = TRAIT_CONFLICTS + (
    ("inactive", "emissive"),
    ("interior-place", "craft-prey"),
    ("interior-place", "outer-hull-act"),
    ("craft-prey", "small-scale"),
    ("outer-hull-act", "small-scale"),
    ("plume-act", "exhaust-emitter"),
    ("creature-subject", "crew-scenery"),
)
_TRAIT_REASONS.update({
    "interior-place|craft-prey": "a creature inside a hull does not seize another craft",
    "interior-place|outer-hull-act": "a creature inside a hull is not crossing its outside",
    "craft-prey|small-scale": "a small creature cannot take a craft",
    "outer-hull-act|small-scale": "a small creature cannot cover a whole hull",
    "plume-act|exhaust-emitter": "a hull that is already burning its drive shows one plume",
    "creature-subject|crew-scenery": "a crew does not work calmly beside a creature",
})

# ---------------------------------------------------------------------------
# Round XVI -- the 0917-afternoon batch
# ---------------------------------------------------------------------------

# "sensor gauntlet" (a worn sensor) and "magnetic grapple" (a carried extra)
# both localise to the hand/wrist; a spacefarer who draws both at once fused
# into one clunky mechanical claw. They are fine individually -- only their
# co-occurrence is the defect -- so this shares one trait across two fields
# rather than rewording either value.
_add_traits("sensors", {"sensor gauntlet": ("hand-mounted",)})
_add_traits("extras", {"magnetic grapple": ("hand-mounted",)})
TRAIT_CONFLICTS = TRAIT_CONFLICTS + (
    ("hand-mounted", "hand-mounted"),
)
_TRAIT_REASONS.update({
    "hand-mounted|hand-mounted": "a hand can carry a gauntlet or a grapple, not both at once",
})

# Round XXI: an act that fills both hands leaves none for held gear. "Sealing a
# hull breach with a foam sprayer" while carrying a magnetic grapple and two
# tool torches drew a figure with tools fused into every hand.
_add_traits(SITUATION_FIELD, {v: ("hands-busy",) for v in (
    "sealing a hull breach with a foam sprayer", "hauling a stretcher through a smoking corridor",
    "planting a survey marker in red dust", "sealing a cracked visor with tape",
    "signalling a descending lander with a flare", "clamping a magnetic beacon to a deck plate",
    "welding a seam with a torch", "planting a beacon on a ridge", "hauling a cargo pod up a ramp",
    "scanning a wall with a handheld", "pushing a cart of supplies",
    "tightening a coupling with a wrench", "chalking a mark on a wall", "passing a tool to a colleague",
    "hosing dust off a panel", "tying a bandage around their own forearm",
    "steadying a ladder for a colleague", "cutting through a jammed airlock with a torch",
    "shouldering a buckling bulkhead back into place", "severing a snarl of cabling",
    "carrying a child through a smoke-filled corridor", "catching a falling colleague by the wrist",
    "holding a door against a rush of pressure", "carrying an unconscious crewmate in a sealed suit",
    "grappling with a boarder in open vacuum", "sealing a hull breach from the outside",
    "planting a magnetic beacon on a drifting asteroid", "reeling in a drifting survey probe",
    "signalling a distant rescue lander with a flare", "grabbing a spinning toolkit before it drifts away",
    "bracing against the kick of a rivet driver", "welding a plate over a hull breach",
    "clipping a sample bag to their belt",
)})
_add_traits("armament", {v: ("hand-held",) for v in (
    "shoulder-braced arc lance", "magnetic slug thrower", "vibro-blade",
    "shoulder-mounted missile tube", "neural stun rod",
)})
_add_traits("extras", {v: ("hand-held",) for v in (
    "magnetic anchor piton", "sealed sample case", "data slate", "magnetic grapple", "signal beacon",
)})
_add_traits("sensors", {v: ("hand-held",) for v in ("hand scanner", "signal locator")})
_add_traits("emitters", {"tool torch emitter": ("hand-held",)})
TRAIT_CONFLICTS = TRAIT_CONFLICTS + (("hands-busy", "hand-held"),)
_TRAIT_REASONS.update({"hands-busy|hand-held": "both hands are already busy with the act"})

# Round XXII: horns and a crest do not fit inside a clear bubble helmet -- they
# were drawn piercing it.
_add_traits("subkind", {v: ("head-crest",) for v in ("crested pilot", "horned warlord")})
_add_traits("form", {v: ("head-crest",) for v in ("heavy horned frame", "narrow crested frame")})
# "immaculate" and "trailing smoke from one dead engine" on one carrier.
_add_traits(SITUATION_FIELD, {"trailing smoke from one dead engine nacelle": ("destruction-act",)})
# A "large swarm drone": a hand-sized drone keeps to tiny and small. Scoped to
# the drones, whose pool keeps two sizes; a hover bike keeps "large".
_add_traits("scale", {"large": ("big-scale",)})
_add_traits("subkind", {v: ("hand-sized",) for v in (
    "swarm drone", "courier drone", "repair drone", "survey drone",
)})
TRAIT_CONFLICTS = TRAIT_CONFLICTS + (
    ("sealed-helmet", "head-crest"),
    ("hand-sized", "big-scale"),
)
_TRAIT_REASONS.update({
    "sealed-helmet|head-crest": "horns or a crest do not fit inside a sealed helmet",
    "hand-sized|big-scale": "a hand-sized drone is never large",
})


# ---------------------------------------------------------------------------
# Round XV -- the 0916-evening batch
# ---------------------------------------------------------------------------

def _add_needs(field: str, additions: dict) -> None:
    """Union ``{value: needs}`` into a field's needs; a later table must not overwrite."""
    table = VALUE_NEEDS.setdefault(field, {})
    for _v, _needs in additions.items():
        table[_v] = frozenset(table.get(_v, frozenset())) | _needs


#: A fleet manoeuvre happens aloft. A planetary surface affords ``sky``,
#: so without the need a ship "holding formation with two escorts" or "passing in
#: front of a moon" was drawn parked on its landing gear in a ruin field, and read
#: as an airliner.
_add_needs(SITUATION_FIELD, {
    value: frozenset({"aloft"})
    for value in (
        "passing in front of a banded amber moon", "turning its flank to a banded world",
        "running dark past a derelict", "holding formation with two escorts",
        "matching course with a slower cargo starship",
        "standing guard over a column of civilian starships",
        "hauling a stripped hulk in a tractor beam", "driving through a blockade line",
        "firing a full weapons array at a closing formation",
        "launching interceptors from an open bay", "dumping fuel in a spreading cloud",
        "rolling to present its armoured flank", "extending a dorsal sensor spine",
        "opening its forward launch bay doors", "launching a probe from a nose bay",
        "holding station beside a survey beacon", "sweeping a searchlight across a hull",
        "flashing a signal beacon in a slow pattern", "trailing a thin wake of particles",
        "decelerating on a long plume", "punching through a debris curtain at speed",
    )
})

SITUATION_TIERS.update({
    "lifting off in a blast of kicked-up grit": "event",
    "skimming low over broken ground at speed": "event",
    "descending onto a cleared landing site": "activity",
    "idling on the ground with its ramp lowered": "idle",
    "kicking up a wake of dust on a low pass": "event",
    "firing its braking thrusters above a landing site": "activity",
    "waiting on a scorched landing apron": "idle",
    "powering up on a cracked landing apron": "activity",
    "taking fire from a ground battery as it lifts off": "event",
    "venting coolant steam onto the ground after landing": "activity",
    "rising slowly on vertical thrusters": "event",
})
TAGS[SITUATION_FIELD].update({
    "lifting off in a blast of kicked-up grit": "neutral",
    "skimming low over broken ground at speed": "neutral",
    "descending onto a cleared landing site": "neutral",
    "idling on the ground with its ramp lowered": "neutral",
    "kicking up a wake of dust on a low pass": "neutral",
    "firing its braking thrusters above a landing site": "neutral",
    "waiting on a scorched landing apron": "neutral",
    "powering up on a cracked landing apron": "neutral",
    "taking fire from a ground battery as it lifts off": "conflict_only",
    "venting coolant steam onto the ground after landing": "neutral",
    "rising slowly on vertical thrusters": "neutral",
})
_add_needs(SITUATION_FIELD, {
    "lifting off in a blast of kicked-up grit": frozenset({"ground", "sky"}),
    "skimming low over broken ground at speed": frozenset({"ground", "sky"}),
    "descending onto a cleared landing site": frozenset({"ground", "sky"}),
    "idling on the ground with its ramp lowered": frozenset({"ground"}),
    "kicking up a wake of dust on a low pass": frozenset({"ground", "sky"}),
    "firing its braking thrusters above a landing site": frozenset({"ground", "sky"}),
    "waiting on a scorched landing apron": frozenset({"ground"}),
    "powering up on a cracked landing apron": frozenset({"ground"}),
    "taking fire from a ground battery as it lifts off": frozenset({"ground", "sky"}),
    "venting coolant steam onto the ground after landing": frozenset({"ground"}),
    "rising slowly on vertical thrusters": frozenset({"ground", "sky"}),
    "sweeping the terrain below with a scanning beam": frozenset({"ground", "sky"}),
    "seeping through a bulkhead in slow tendrils": frozenset({"structure"}),
    # A second body in the frame needs somewhere a bare face can be, or a hull.
    "nosing through a cloud of stirred-up silt": frozenset({"submerged"}),
    "sealing a breach as the air thins": frozenset({"structure"}),
    "dragging a survivor into the dark": frozenset({"floor", "air"}),
    # A slab of rock falls where there is rock above: not in a station corridor.
    "dodging a falling slab of rock": frozenset({"ground"}),
})

#: A flight act declares a flight stance. Without one, a crawler whose only
#: stance is rolling "burned through re-entry in a sheath of plasma" while
#: parked on a floating-rock plateau: the plateau affords sky, so the need alone
#: could not see it.
VALUE_STANCES[SITUATION_FIELD].update({
    "skimming low over a cloud bank at full speed": frozenset({"hovers", "flies"}),
    "skimming low over broken ground at speed": frozenset({"hovers", "flies"}),
    "kicking up a wake of dust on a low pass": frozenset({"hovers", "flies"}),
    "rising slowly on vertical thrusters": frozenset({"hovers", "flies"}),
    "punching through the top of a storm band": frozenset({"flies", "hovers"}),
    "pulling up hard out of a canyon dive": frozenset({"flies"}),
    "burning through re-entry in a sheath of plasma": frozenset({"flies", "hovers", "falls"}),
    "losing a lift-pod panel in a violent gust": frozenset({"flies", "hovers", "falls"}),
    "breaking up in a violent gust": frozenset({"flies", "hovers", "falls"}),
    "releasing a spread of survey probes over the plain": frozenset({"flies", "hovers"}),
    "tipping one lift pod over a volcanic vent": frozenset({"flies", "hovers"}),
    "sweeping a sampling scoop through an ash plume": frozenset({"flies", "hovers"}),
    "being flung into a cloud bank by a gust": frozenset({"flies", "hovers", "falls"}),
})
#: The words that caught the acts above, so the stance lint fails the next one.
STANCE_KEYWORDS["flies"] = STANCE_KEYWORDS["flies"] + (
    "re-entry", "dive", "gust", "lift pod",
)

#: A finish belongs to a body too: "mud-packed tread gaps" was drawn as tracks
#: under a submersible, because surface detail was the one part-bearing field
#: the part lint did not read.
PART_LINT_FIELDS = PART_LINT_FIELDS + ("surface_detail",)


SCIFI_PACK = GenrePack(
    slug="scifi",
    display="Sci-Fi",
    class_suffix="SciFi",
    kinds=KINDS,
    entity_fields=ENTITY_FIELDS,
    scene_fields=SCENE_FIELDS,
    pools=POOLS,
    labels=LABELS,
    counts=COUNTS,
    tags=TAGS,
    constraints=CONSTRAINTS,
    place_affordances=PLACE_AFFORDANCES,
    default_needs=DEFAULT_NEEDS,
    value_stances=VALUE_STANCES,
    place_stances=PLACE_STANCES,
    place_stance_blocks=PLACE_STANCE_BLOCKS,
    affordance_keywords=AFFORDANCE_KEYWORDS,
    affordance_lint_fields=AFFORDANCE_LINT_FIELDS,
    affordance_allowlist=AFFORDANCE_ALLOWLIST,
    stance_keywords=STANCE_KEYWORDS,
    body_features=BODY_FEATURES,
    body_keywords=BODY_KEYWORDS,
    body_lint_fields=BODY_LINT_FIELDS,
    part_keywords=PART_KEYWORDS,
    part_lint_fields=PART_LINT_FIELDS,
    value_needs=VALUE_NEEDS,
    value_traits=VALUE_TRAITS,
    value_tiers={"situation": SITUATION_TIERS},
    tier_weights=TIER_WEIGHTS,
    trait_conflicts=TRAIT_CONFLICTS,
    trait_reasons=_TRAIT_REASONS,
    kind_capabilities=KIND_CAPABILITIES,
    relation_roles=RELATION_ROLES,
    omitted_pools=OMITTED_POOLS,
    shared_vocabulary=SHARED_VOCABULARY,
    distinct_within_entity=DISTINCT_COUNTS,
    pool_groups=POOL_GROUPS,
    value_cardinality=CARDINALITY,
    cardinality_counts=CARDINALITY_COUNTS,
    scope_fallthrough=SCOPE_FALLTHROUGH,
    environment_bands=ENVIRONMENT_BANDS,
    motifs=MOTIFS,
    spoken=SPOKEN,
    foreign_nouns=FOREIGN_NOUNS,
    foreign_noun_fields=FOREIGN_NOUN_FIELDS,
    foreign_noun_allowlist=FOREIGN_NOUN_ALLOWLIST,
    archetypes=ARCHETYPES,
    archetype_of_kind=ARCHETYPE_OF_KIND,
    archetype_override_field="subkind",
    archetype_of_override=ARCHETYPE_OF_SUBKIND,
    prose=PROSE,
)
