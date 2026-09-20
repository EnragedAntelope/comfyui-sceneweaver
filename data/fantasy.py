"""The fantasy ``GenrePack``.

The second genre, built on the seam the sci-fi pack proved. Nothing under
``nodes/`` or ``engine/`` imports it; the repo-root ``__init__.py`` does.

**Same field keys as sci-fi, fantasy labels.** A ``SCENE_ENTITY`` payload is
matched to its host scene by field key, so a gorgon wired into a sci-fi station
keeps its serpent hair and its bronze scales. Only ``LABELS`` differ.

**What this pack carries over from thirteen sci-fi rounds, by construction:**

* Coherence is declared, not listed: a place affords, a value needs, a form says
  how it holds itself up, and two facts that cannot both hold are a trait
  conflict. ``engine/`` never learns what a troll is.
* Liveness is a **closed list**. ``DORMANT_ACTS`` is what a petrified, ruined or
  dormant thing can be doing and ``SLEEP_ACTS`` what a slumbering one can; every
  other situation is derived as live. A new situation is live until declared
  otherwise, so the safe default needs no memory.
* A dead or petrified thing shows no light: every emitter is ``emissive``.
* A small body does not carry off a big one, and an interior holds nothing huge.
* **Pools are literals** (``scripts/builtin_options.py`` reads them with
  ``ast``). Situations are authored in *buckets* -- one tuple per (tier, tag,
  needs) -- and the pool literals concatenate the buckets, so a value's tier, tag
  and needs are declared once, by the bucket it sits in.
* Never negate. Never name rendering: "glow", "shadow", "mist", "dawn",
  "moonlight" are the style pack's words, not the subject's.

Authoring rules are the sci-fi pack's: bare article-less noun phrases, singular
where a count partners the pool, every situation opens with a gerund and is
legible in one still frame without an actor the scene has not described.
"""
from __future__ import annotations

from collections import OrderedDict

try:
    from .genre import (
        CONTEXT_FIELD,
        ENVIRONMENT_FIELD,
        KIND_FIELD,
        NONE,
        POOL_DEFAULT_KEY,
        RELATION_ANY,
        RELATION_ANY_POSITION,
        RELATION_FIELD,
        RELATION_POSITION_FIELD,
        RULE_EXCLUDE,
        RULE_REQUIRE,
        SITUATION_FIELD,
        TAG_CONFLICT_ONLY,
        TAG_NEUTRAL,
        TAG_PEACEFUL_ONLY,
        Archetype,
        ConstraintRule,
        FieldSpec,
        GenrePack,
        HeadPhrase,
        ProseSpec,
        Sentence,
    )
except ImportError:  # pragma: no cover -- standalone/test context
    from data.genre import (
        CONTEXT_FIELD,
        ENVIRONMENT_FIELD,
        KIND_FIELD,
        NONE,
        POOL_DEFAULT_KEY,
        RELATION_ANY,
        RELATION_ANY_POSITION,
        RELATION_FIELD,
        RELATION_POSITION_FIELD,
        RULE_EXCLUDE,
        RULE_REQUIRE,
        SITUATION_FIELD,
        TAG_CONFLICT_ONLY,
        TAG_NEUTRAL,
        TAG_PEACEFUL_ONLY,
        Archetype,
        ConstraintRule,
        FieldSpec,
        GenrePack,
        HeadPhrase,
        ProseSpec,
        Sentence,
    )

_IDENTITY = "Identity"
_FORM = "Form & Material"
_SURFACE = "Surface & Colour"
_COMPONENTS = "Components"
_SCENE = "Scene"
_RELATIONS = "Relations"


# ---------------------------------------------------------------------------
# Weights
# ---------------------------------------------------------------------------

#: Scale reads by contrast; a flat draw makes a third of everything enormous.
#:
#: The measured sizes belong to the bodies whose size *is* the subject -- a
#: giant, a troll, a goblin, a pixie -- and are weighted to be voiced far more
#: often than ``omission_weight`` leaves them out. "A large hill giant" reads
#: as a tall man; a measurement is what a model draws as a change of scale. No
#: comparison object ("the size of a house") -- a model draws the house.
SCALE_WEIGHTS: dict[str, float] = {
    "tiny": 1.0, "small": 2.0, "large": 2.0, "huge": 1.2, "colossal": 0.6, "titanic": 0.3,
    "nine-foot-tall": 12.0, "twelve-foot-tall": 12.0,
    "ten-foot-tall": 12.0, "fourteen-foot-tall": 12.0,
    "twenty-foot-tall": 12.0, "forty-foot-tall": 10.0,
    "three-foot-tall": 10.0, "two-foot-tall": 10.0,
    "six-inch-tall": 12.0, "ten-inch-tall": 12.0,
}

#: Small counts are the readable case; a collective on every part reads as an inventory.
COUNT_WEIGHTS: dict[str, float] = {
    "a dozen": 0.35, "a crown of": 0.5, "a ring of": 0.6, "a cluster of": 0.6,
    "a fan of": 0.6,
}

#: A slumbering, petrified or ruined subject can only rest, so it is a quiet
#: frame; weighted down so it stays an occasional one.
CONDITION_WEIGHTS: dict[str, float] = {
    "slumbering": 0.35, "petrified": 0.35, "dormant": 0.4, "ruined": 0.6, "abandoned": 0.5,
    "wrecked": 0.5,
}

#: What a fantasy scene is most often about. Beasts, dragons and people carry a
#: frame on their own; a building or an object is best as an occasional subject.
KIND_WEIGHTS: dict[str, float] = {
    "dragon": 1.3, "mythic beast": 1.4, "folk": 1.4, "hybrid folk": 1.0, "giant-kin": 1.0,
    "small folk": 0.9, "spirit or elemental": 0.9, "undead": 0.9, "construct": 0.8,
    "vessel": 0.8, "structure": 0.6, "artifact": 0.6,
}


# ---------------------------------------------------------------------------
# The entity fields -- IN WIDGET ORDER. Never reorder; only ever append.
# ---------------------------------------------------------------------------
#
# The keys and their order match the sci-fi pack exactly, which is what lets an
# entity from either genre fill a slot in the other.

ENTITY_FIELDS: "OrderedDict[str, FieldSpec]" = OrderedDict([
    ("kind", FieldSpec(
        group=_IDENTITY, label="Kind",
        tooltip="What this entity fundamentally is. Scopes every other field on this slot -- "
                "its options and its labels. Set to None to leave the slot empty.",
        brief=True, scope=(ENVIRONMENT_FIELD,), weights=KIND_WEIGHTS,
    )),
    ("subkind", FieldSpec(
        group=_IDENTITY, label="Type",
        tooltip="The specific type within the kind -- a unicorn, a frost troll, a galleon.",
        kind_scoped=True, tag_scoped=True, brief=True,
    )),
    ("scale", FieldSpec(
        group=_IDENTITY, label="Scale",
        tooltip="How big it is relative to a person.",
        brief=True, scope=("subkind", KIND_FIELD), weights=SCALE_WEIGHTS, omission_weight=6.5,
    )),
    ("condition", FieldSpec(
        group=_IDENTITY, label="Condition",
        tooltip="Age and state -- ancient, battle-scarred, slumbering, petrified.",
        brief=True, scope=(KIND_FIELD,), omission_weight=0.6, weights=CONDITION_WEIGHTS,
    )),
    ("form", FieldSpec(
        group=_FORM, label="Form",
        tooltip="The silhouette: a body plan, a build, a hull or a tower's shape. The field "
                "that makes two dragons actually look different.",
        scope=("subkind", "kind"),
    )),
    ("material", FieldSpec(
        group=_FORM, label="Material",
        tooltip="What it is covered in, made of, or wearing.",
        scope=("subkind", "kind"),
    )),
    ("primary_color", FieldSpec(
        group=_SURFACE, label="Primary colour",
        tooltip="The colour of the thing itself -- scales, coat, robes, stone. Describes the "
                "subject, never the lighting.",
        scope=("subkind", KIND_FIELD),
    )),
    ("accent_color", FieldSpec(
        group=_SURFACE, label="Accent colour",
        tooltip="A secondary colour: trim, banding, the underside of a wing.",
    )),
    ("markings", FieldSpec(
        group=_SURFACE, label="Markings",
        tooltip="Heraldry, war paint, patterning. Carries no readable lettering.",
        scope=("subkind", KIND_FIELD),
    )),
    ("surface_detail", FieldSpec(
        group=_SURFACE, label="Surface detail",
        tooltip="Finish and wear at close range -- scars, moss, weathering, stitching of hide.",
        scope=("subkind", "kind"),
    )),
    ("appendages", FieldSpec(
        group=_COMPONENTS, label="Appendages",
        tooltip="What sticks out: horns, wings, tails, tusks, towers and masts.",
        scope=("subkind", KIND_FIELD), count_partner="appendage_count",
    )),
    ("appendage_count", FieldSpec(
        group=_COMPONENTS, label="Appendage count",
        tooltip="How many. Composed into the appendage phrase.",
        scope=("appendages", KIND_FIELD), weights=COUNT_WEIGHTS,
        count_partner="appendages", renders_with="appendages",
    )),
    ("emitters", FieldSpec(
        group=_COMPONENTS, label="Emitters",
        tooltip="What shines with its own light: enchanted gems, rune tracery, ember eyes, "
                "a spell held in the hand.",
        scope=("subkind", KIND_FIELD), count_partner="emitter_count",
    )),
    ("emitter_count", FieldSpec(
        group=_COMPONENTS, label="Emitter count",
        tooltip="How many.",
        scope=("emitters", KIND_FIELD), weights=COUNT_WEIGHTS,
        count_partner="emitters", renders_with="emitters",
    )),
    ("emitter_color", FieldSpec(
        group=_COMPONENTS, label="Emitter colour",
        tooltip="The colour of the magic itself. Belongs to the subject, not the lighting.",
        renders_with="emitters", scope=("subkind", KIND_FIELD),
    )),
    ("armament", FieldSpec(
        group=_COMPONENTS, label="Armament",
        tooltip="Weapons, carried or grown: a longsword, a war maul, horns and talons.",
        scope=("subkind", KIND_FIELD), tag_scoped=True, count_partner="armament_count",
    )),
    ("armament_count", FieldSpec(
        group=_COMPONENTS, label="Armament count",
        tooltip="How many weapons.",
        scope=("armament", KIND_FIELD), weights=COUNT_WEIGHTS,
        count_partner="armament", renders_with="armament",
    )),
    ("sensors", FieldSpec(
        group=_COMPONENTS, label="Sensors",
        tooltip="How it sees: eyes, many eyes, a lantern-bearing gaze.",
        scope=("subkind", KIND_FIELD), count_partner="sensor_count",
    )),
    ("sensor_count", FieldSpec(
        group=_COMPONENTS, label="Sensor count",
        tooltip="How many. A cyclops and a many-eyed horror are different things.",
        scope=("sensors", KIND_FIELD), weights=COUNT_WEIGHTS,
        count_partner="sensors", renders_with="sensors",
    )),
    ("aperture", FieldSpec(
        group=_COMPONENTS, label="Aperture",
        tooltip="The opening: a fanged maw, a visor, a gatehouse arch.",
        scope=("subkind", "kind"), tag_scoped=True,
    )),
    ("extras", FieldSpec(
        group=_COMPONENTS, label="Extras",
        tooltip="One more distinguishing thing -- a saddle, a satchel, a hanging banner.",
        scope=("subkind", KIND_FIELD),
    )),
])

SCENE_FIELDS: "OrderedDict[str, FieldSpec]" = OrderedDict([
    (ENVIRONMENT_FIELD, FieldSpec(
        group=_SCENE, label="Environment",
        tooltip="Where the scene is: wild lands, the water, the sky, underground, a town, "
                "a hall, or a realm beyond the world.",
    )),
    (SITUATION_FIELD, FieldSpec(
        group=_SCENE, label="Situation",
        tooltip="What this entity is doing -- an event in progress, not a pose.",
        scope=("subkind", KIND_FIELD), tag_scoped=True,
    )),
    (RELATION_FIELD, FieldSpec(
        group=_RELATIONS, label="Relation",
        tooltip="How two slots relate. Rendered only when both entities exist. Opt-in.",
        kind_scoped=False, tag_scoped=True, default=NONE,
    )),
    (RELATION_POSITION_FIELD, FieldSpec(
        group=_RELATIONS, label="Position",
        tooltip="Where the first entity sits relative to the second.",
        kind_scoped=False, tag_scoped=False, default=NONE,
    )),
    (CONTEXT_FIELD, FieldSpec(
        group=_SCENE, label="Context",
        tooltip="What else is in the shot besides the subject -- a secondary detail for "
                "scale and story. Always a thing in the world, never a lighting instruction.",
        scope=(ENVIRONMENT_FIELD,), omission_weight=5.0,
    )),
])

COUNTS: dict[str, str] = {
    "appendages": "appendage_count",
    "emitters": "emitter_count",
    "armament": "armament_count",
    "sensors": "sensor_count",
}

DISTINCT_COUNTS: tuple[frozenset[str], ...] = (
    frozenset({"appendage_count", "emitter_count", "armament_count", "sensor_count"}),
)
SHARED_VOCABULARY: tuple[frozenset[str], ...] = (
    frozenset({"primary_color", "accent_color", "emitter_color"}),
)


# ---------------------------------------------------------------------------
# Environments -- seven bands
# ---------------------------------------------------------------------------
#
# Wild lands, waterside, underwater, the sky, underground, settlement, interior
# and the otherworld. A place states only what it *is*; the time of day and the
# weather's look belong to a style.

_ENV_WILDS = (
    "ancient oak forest",
    "enchanted forest glade",
    "windswept moorland",
    "rolling highland hills",
    "high mountain pass",
    "snowbound mountain peak",
    "glacier valley",
    "red sandstone canyon",
    "desert of shifting dunes",
    "salt-crusted wasteland",
    "volcanic ashlands",
    "petrified forest",
    "wildflower meadow",
    "bramble-choked valley",
    "forest of giant mushrooms",
    "crystal-studded plateau",
    "overgrown elven ruins",
    "field of standing stones",
    "old battlefield of rusted banners",
    "thorn-wrapped hillside of barrow mounds",
)
_ENV_WATERSIDE = (
    "storm-lashed sea cliffs",
    "black sand beach",
    "lake shore below a waterfall",
    "shallow river ford",
    "reed marsh",
    "mangrove fen",
    "frozen lake shore",
    "rocky coast of a stormy sea",
)
_ENV_UNDERWATER = (
    "sunken temple ruins",
    "kelp forest depths",
    "coral reef grotto",
    "abyssal sea trench",
    "drowned city streets",
)
_ENV_SKY = (
    "sea of clouds",
    "floating island archipelago",
    "stormy sky above a mountain range",
    "open sky above a great forest",
)
_ENV_UNDERGROUND = (
    "dwarven great hall",
    "crystal cavern",
    "dragon's hoard cavern",
    "magma cavern",
    "catacomb crypt",
    "abandoned mine tunnels",
    "underground river cavern",
    "fungal grotto",
)
_ENV_SETTLEMENT = (
    "cobbled market square",
    "walled city gate",
    "harbour town quay",
    "village green",
    "castle courtyard",
    "elven treetop village",
    "dwarven mountain stronghold gate",
    "ruined city plaza",
)
_ENV_INTERIOR = (
    "royal throne room",
    "castle great hall",
    "wizard's tower study",
    "apothecary's workshop",
    "temple sanctum",
    "vaulted library",
    "dungeon cell block",
    "tavern common room",
    "blacksmith's forge",
    "treasure vault",
)
_ENV_OTHERWORLD = (
    "fairy ring glade",
    "astral void between worlds",
    "blazing elemental plane",
    "realm of endless night",
    "frozen realm of the frost giants",
)

ENVIRONMENT_POOL: tuple[str, ...] = (
    _ENV_WILDS + _ENV_WATERSIDE + _ENV_UNDERWATER + _ENV_SKY + _ENV_UNDERGROUND
    + _ENV_SETTLEMENT + _ENV_INTERIOR + _ENV_OTHERWORLD
)

ENVIRONMENT_BANDS: dict[str, tuple[str, ...]] = {
    "wilds": _ENV_WILDS,
    "waterside": _ENV_WATERSIDE,
    "underwater": _ENV_UNDERWATER,
    "sky": _ENV_SKY,
    "underground": _ENV_UNDERGROUND,
    "settlement": _ENV_SETTLEMENT,
    "interior": _ENV_INTERIOR,
    "otherworld": _ENV_OTHERWORLD,
}

#: What else is in the shot. Always secondary, plural or architectural, never a
#: second described subject.
#:
#: Round XV: a place key wins over its band, so each place draws from its own
#: tuple plus the shared tuple of its kind of place. A band-wide list put a wall
#: of library books into a blacksmith's forge and a feasting table into a temple,
#: and made ravens, gulls, herons and a lighthouse most of what stood behind an
#: outdoor subject.
_CTX_OPEN = (
    "ring of weathered standing stones", "ruined arch wrapped in creepers",
    "abandoned campsite of charred logs", "moss-covered statue of a forgotten king",
    "column of pilgrims on a far road", "lone ancient oak on a rise",
    "carved boundary stone beside the path", "burned-out wagon beside the road",
)
_CTX_FOREST = (
    "hollow fallen trunk furred with moss", "ring of pale toadstools",
    "overgrown shrine among the roots", "moss-covered statue of a forgotten king",
    "hunter's hide high in the branches", "stream winding between the roots",
)
_CTX_PEAKS = (
    "distant range of jagged peaks", "valley winding far below", "stone cairn marking the pass",
    "dwarven waystone carved into the rock",
)
_CTX_BARRENS = (
    "half-buried colossal statue", "bleached bones of a great beast",
    "abandoned caravan tents", "wind-carved rock arch", "toppled obelisk half-sunk in the ground",
)
_CTX_SEA = (
    "wrecked longship on the rocks", "lighthouse on a distant headland",
    "sea stacks rising from the surf", "overturned rowing boat on the shingle",
)
_CTX_FRESH = (
    "fishing village of stilted huts", "line of weathered pilings",
    "willow trees trailing into the water", "ruined watermill on the far bank",
    "stepping stones across the water",
)
CONTEXT_POOLS: dict[str, tuple[str, ...]] = {
    "wilds": _CTX_OPEN,
    "ancient oak forest": _CTX_FOREST,
    "enchanted forest glade": _CTX_FOREST,
    "forest of giant mushrooms": _CTX_FOREST,
    "bramble-choked valley": _CTX_FOREST + _CTX_OPEN,
    "high mountain pass": _CTX_PEAKS,
    "snowbound mountain peak": _CTX_PEAKS + ("frozen waterfall on a cliff face",),
    "glacier valley": _CTX_PEAKS + ("frozen waterfall on a cliff face",),
    "red sandstone canyon": _CTX_BARRENS,
    "desert of shifting dunes": _CTX_BARRENS,
    "salt-crusted wasteland": _CTX_BARRENS,
    "petrified forest": _CTX_BARRENS,
    "volcanic ashlands": _CTX_BARRENS + ("distant volcano trailing a plume of ash",),
    "waterside": _CTX_FRESH,
    "storm-lashed sea cliffs": _CTX_SEA,
    "black sand beach": _CTX_SEA,
    "rocky coast of a stormy sea": _CTX_SEA,
    "underwater": (
        "cluster of toppled marble columns", "shoal of silver fish", "swaying forest of kelp",
        "barnacle-crusted anchor", "sunken statue of a sea god", "scatter of old coins in the sand",
    ),
    "sky": (
        "floating island trailing waterfalls", "distant airship under full sail",
        "towering cloud bank", "scatter of drifting rock islets", "distant floating castle",
    ),
    "underground": (
        "cluster of pale cave crystals", "flight of stone steps descending into the deep",
        "rope bridge over a deep chasm", "forest of dripping stalactites",
    ),
    "dwarven great hall": (
        "row of rune-carved stone pillars", "long stone feasting table",
        "row of carved ancestor statues", "great forge hearth set into the wall",
    ),
    "crystal cavern": (
        "cluster of pale cave crystals", "mirror-still underground lake", "ceiling of glittering crystal",
    ),
    "dragon's hoard cavern": (
        "heap of spilled gold coins", "scatter of bones of past challengers",
        "toppled suit of armour half-buried in gold",
    ),
    "magma cavern": (
        "flow of slow-moving lava", "field of black basalt columns", "bubbling basin of molten rock",
    ),
    "catacomb crypt": (
        "wall of niches stacked with skulls", "row of stone sarcophagi",
        "carved burial effigy on a tomb lid",
    ),
    "abandoned mine tunnels": (
        "abandoned mine cart on rusted rails", "sagging timber shoring beams",
        "rusted pickaxe left against the wall",
    ),
    "underground river cavern": (
        "rope bridge over a deep chasm", "flight of stone steps descending into the deep",
        "glistening curtain of flowstone",
    ),
    "fungal grotto": (
        "cluster of luminous toadstools", "spore-dusted stalagmites", "towering pale mushroom stalk",
    ),
    "settlement": (
        "row of timber-framed shops", "crowd of townsfolk at a distance",
        "stone well at the square's centre", "row of market stalls under striped awnings",
    ),
    "walled city gate": (
        "banner-hung stretch of castle wall", "line of guards on the battlements",
        "cluster of wagons waiting at the gate",
    ),
    "harbour town quay": (
        "moored fishing boat at the quay", "stack of barrels and crates", "tall ship at the dock",
    ),
    "village green": (
        "row of thatched cottages", "stone well at the green's edge", "ribbon-hung maypole",
    ),
    "castle courtyard": (
        "banner-hung stretch of castle wall", "row of stable doors", "rack of practice spears",
    ),
    "elven treetop village": (
        "graceful bridge between two great trees", "lantern-hung platform among the branches",
        "spiral stair winding around a trunk",
    ),
    "dwarven mountain stronghold gate": (
        "pair of carved guardian statues", "great stone stair cut into the mountain",
    ),
    "ruined city plaza": (
        "toppled statue of a forgotten ruler", "broken fountain choked with weeds",
        "collapsed colonnade",
    ),
    "royal throne room": (
        "row of tall stained-glass windows", "row of hanging battle banners",
        "raised dais under a carved canopy",
    ),
    "castle great hall": (
        "long feasting table", "stone hearth with a banked fire", "row of hanging battle tapestries",
    ),
    "wizard's tower study": (
        "shelf of arcane curiosities", "desk buried under unrolled scrolls", "brass orrery",
    ),
    "apothecary's workshop": (
        "shelf of stoppered jars", "bundle of drying roots hung from a beam", "bubbling alembic",
    ),
    "temple sanctum": (
        "carved stone altar", "towering statue of a deity", "row of stone pews",
    ),
    "vaulted library": (
        "wall of leather-bound books", "reading lectern", "tall rolling ladder",
    ),
    "dungeon cell block": (
        "row of iron-barred cells", "set of rusted manacles on the wall", "iron candelabra",
    ),
    "tavern common room": (
        "crowded bar counter", "stack of ale barrels behind the bar", "stone hearth with a banked fire",
    ),
    "blacksmith's forge": (
        "anvil beside the hearth", "rack of tongs and hammers", "quenching trough",
        "rack of polished weapons along one wall",
    ),
    "treasure vault": (
        "heap of spilled gold coins", "row of iron-bound chests", "suit of armour on a stand",
    ),
    "fairy ring glade": ("ring of tall pale mushrooms", "circle of dancing fey lights"),
    "astral void between worlds": (
        "field of floating crystal shards", "distant silhouette of a vast palace",
        "cloud of drifting silver motes",
    ),
    "blazing elemental plane": ("flow of slow-moving lava", "field of black basalt columns"),
    "realm of endless night": ("toppled idol of black iron", "circle of pale standing stones"),
    "frozen realm of the frost giants": ("towering ice-carved statue", "field of frozen warriors"),
}


# ---------------------------------------------------------------------------
# Kinds and types
# ---------------------------------------------------------------------------

KINDS: tuple[str, ...] = (
    "dragon",
    "mythic beast",
    "giant-kin",
    "small folk",
    "hybrid folk",
    "folk",
    "spirit or elemental",
    "undead",
    "construct",
    "structure",
    "vessel",
    "artifact",
)

#: Which kinds a place can hold. A band key covers its places; a place key wins.
KIND_POOLS: dict[str, tuple[str, ...]] = {
    POOL_DEFAULT_KEY: KINDS,
    "wilds": ("dragon", "mythic beast", "giant-kin", "small folk", "hybrid folk", "folk",
              "spirit or elemental", "undead", "construct", "structure", "vessel", "artifact"),
    "waterside": ("dragon", "mythic beast", "giant-kin", "small folk", "hybrid folk", "folk",
                  "spirit or elemental", "undead", "structure", "vessel", "artifact"),
    "underwater": ("dragon", "mythic beast", "hybrid folk", "spirit or elemental", "undead",
                   "artifact"),
    "sky": ("dragon", "mythic beast", "spirit or elemental", "vessel"),
    "floating island archipelago": ("dragon", "mythic beast", "spirit or elemental", "vessel",
                                    "structure", "artifact", "folk"),
    "astral void between worlds": ("dragon", "mythic beast", "spirit or elemental", "undead",
                                   "artifact"),
    "underground": ("dragon", "mythic beast", "giant-kin", "small folk", "folk",
                    "spirit or elemental", "undead", "construct", "artifact"),
    "settlement": ("dragon", "mythic beast", "giant-kin", "small folk", "hybrid folk", "folk",
                   "undead", "construct", "structure", "vessel", "artifact"),
    "interior": ("small folk", "hybrid folk", "folk", "spirit or elemental", "undead",
                 "construct", "artifact"),
    "otherworld": ("dragon", "mythic beast", "hybrid folk", "folk", "spirit or elemental",
                   "undead", "construct", "structure", "artifact"),
}

SUBKIND_GROUPS: dict[str, tuple[str, ...]] = {
    # dragon
    "winged dragon": ("true dragon", "elder dragon", "drake", "wyvern", "fire drake"),
    "serpent wyrm": ("wyrm", "lindworm", "cave wyrm"),
    "sea wyrm": ("sea serpent", "leviathan", "abyssal wyrm"),
    "many-headed dragon": ("hydra", "marsh hydra"),
    # mythic beast
    "hoofed beast": ("unicorn", "nightmare steed", "kelpie", "silver stag"),
    "winged beast": ("pegasus", "hippogriff", "griffin", "roc", "phoenix", "thunderbird",
                     "cockatrice"),
    "chimeric beast": ("manticore", "chimera", "sphinx"),
    "great beast": ("dire wolf", "cave bear", "great tusked boar", "basilisk", "behemoth",
                    "giant cave spider", "hellhound", "treant"),
    "sea beast": ("kraken", "hippocamp", "giant sea turtle"),
    # giant-kin
    "troll": ("cave troll", "bridge troll", "frost troll", "moss troll", "river troll"),
    "ogre-kin": ("ogre", "ogre brute", "ogre shaman"),
    "giant": ("hill giant", "frost giant", "fire giant", "stone giant", "cyclops", "ettin"),
    # small folk
    "goblinoid": ("goblin", "goblin shaman", "kobold", "redcap"),
    "gnome-kin": ("gnome tinkerer", "forest gnome", "brownie"),
    "winged fey": ("pixie", "sprite", "imp"),
    # hybrid folk
    "hoofed folk": ("centaur", "satyr", "faun", "minotaur"),
    "serpent folk": ("gorgon", "naga"),
    "winged folk": ("harpy",),
    "sea folk": ("merfolk", "selkie"),
    "tree folk": ("dryad",),
    # folk
    "adventurer": ("knight", "paladin", "ranger", "cleric", "bard", "rogue", "sorcerer",
                   "hedge witch", "druid", "monk", "necromancer", "warlord", "blacksmith",
                   "herbalist", "travelling merchant", "archer", "beastmaster", "potion-brewer",
                   "wandering scholar"),
    "elf": ("wood elf archer", "high elf mage", "elven bladedancer", "dark elf assassin"),
    "dwarf": ("mountain dwarf smith", "dwarf axe-warden", "dwarf runesmith", "dwarf miner"),
    "orc": ("orc warchief", "orc shaman", "orc raider"),
    "halfling": ("halfling burglar", "halfling scout"),
    # spirit or elemental
    "elemental": ("fire elemental", "water elemental", "air elemental", "storm elemental",
                  "ice elemental", "earth elemental", "magma elemental"),
    "fey spirit": ("will-o'-wisp", "sylph", "undine", "forest spirit"),
    # undead
    "walking dead": ("skeleton warrior", "ghoul", "death knight", "lich", "mummy", "revenant",
                     "drowned revenant"),
    "restless spirit": ("wraith", "banshee", "spectral knight"),
    # construct
    "golem": ("stone golem", "clay golem", "iron golem", "bronze colossus", "crystal golem"),
    "animated": ("animated armour", "clockwork guardian", "living statue", "gargoyle"),
    # structure
    "fortification": ("castle", "watchtower", "ruined keep", "city gate", "fortified bridge"),
    "sacred site": ("shrine", "temple", "standing stone circle", "mountain monastery",
                    "wayside shrine"),
    "arcane tower": ("wizard's tower", "floating citadel", "crystal spire"),
    "dwelling": ("elven tree palace", "dwarven stronghold gate", "windmill", "lighthouse",
                 "witch's hut"),
    # vessel
    "sailing ship": ("galleon", "longship", "war galley", "river barge", "pirate sloop"),
    "flying ship": ("airship", "sky galleon", "cloud skiff"),
    "land vehicle": ("war chariot", "merchant caravan wagon", "royal carriage", "siege tower",
                     "painted travelling wagon"),
    # artifact
    # An object a hand could lift, which rests on something; and a set piece that
    # stands in the scene. A war horn left the pool: a carried object with nothing
    # to rest on was drawn hanging in the middle of a forest.
    "relic": ("crystal orb", "enchanted tome", "reliquary", "magic mirror", "jewelled crown",
              "staff of power", "jewelled chalice", "dragon egg", "ancient hourglass"),
    "monument": ("sword in the stone", "runestone", "cursed idol", "portal arch",
                 "rune-carved anvil", "dragon-skull totem"),
}

SUBKIND_POOLS: dict[str, tuple[str, ...]] = {
    "dragon": SUBKIND_GROUPS["winged dragon"] + SUBKIND_GROUPS["serpent wyrm"]
    + SUBKIND_GROUPS["sea wyrm"] + SUBKIND_GROUPS["many-headed dragon"],
    "mythic beast": SUBKIND_GROUPS["hoofed beast"] + SUBKIND_GROUPS["winged beast"]
    + SUBKIND_GROUPS["chimeric beast"] + SUBKIND_GROUPS["great beast"]
    + SUBKIND_GROUPS["sea beast"],
    "giant-kin": SUBKIND_GROUPS["troll"] + SUBKIND_GROUPS["ogre-kin"] + SUBKIND_GROUPS["giant"],
    "small folk": SUBKIND_GROUPS["goblinoid"] + SUBKIND_GROUPS["gnome-kin"]
    + SUBKIND_GROUPS["winged fey"],
    "hybrid folk": SUBKIND_GROUPS["hoofed folk"] + SUBKIND_GROUPS["serpent folk"]
    + SUBKIND_GROUPS["winged folk"] + SUBKIND_GROUPS["sea folk"] + SUBKIND_GROUPS["tree folk"],
    "folk": SUBKIND_GROUPS["adventurer"] + SUBKIND_GROUPS["elf"] + SUBKIND_GROUPS["dwarf"]
    + SUBKIND_GROUPS["orc"] + SUBKIND_GROUPS["halfling"],
    "spirit or elemental": SUBKIND_GROUPS["elemental"] + SUBKIND_GROUPS["fey spirit"],
    "undead": SUBKIND_GROUPS["walking dead"] + SUBKIND_GROUPS["restless spirit"],
    "construct": SUBKIND_GROUPS["golem"] + SUBKIND_GROUPS["animated"],
    "structure": SUBKIND_GROUPS["fortification"] + SUBKIND_GROUPS["sacred site"]
    + SUBKIND_GROUPS["arcane tower"] + SUBKIND_GROUPS["dwelling"],
    "vessel": SUBKIND_GROUPS["sailing ship"] + SUBKIND_GROUPS["flying ship"]
    + SUBKIND_GROUPS["land vehicle"],
    "artifact": SUBKIND_GROUPS["relic"] + SUBKIND_GROUPS["monument"],
}

# ---------------------------------------------------------------------------
# Form -- the silhouette, keyed where the body differs
# ---------------------------------------------------------------------------
#
# An iconic creature is keyed by its own type, so a unicorn never draws a
# griffin's body; a group shares forms only where every member fits them.

_FORM_WINGED_DRAGON = (
    "long-necked four-legged winged body", "heavy-shouldered four-legged winged body",
    "lean whip-tailed winged body", "serpentine winged body on four short legs",
    "two-legged body with wing-arms", "barrel-chested horned winged body",
    "sleek crested winged body",
)
_FORM_SERPENT_WYRM = (
    "long serpentine body", "coiled serpentine body with two clawed forelegs",
    "armoured burrowing serpentine body", "ridged serpentine body with a spiked tail",
)
_FORM_SEA_SERPENT = (
    "finned serpentine body", "vast eel-like body with a crested spine",
    "ridged sea-serpent body with paddle fins",
)
_FORM_HYDRA = (
    "many-necked heavy body", "squat many-headed body", "long-necked many-headed body",
)
_FORM_HORSE = ("slender horse body", "powerful warhorse body", "long-maned horse body")
_FORM_WINGED_HORSE = ("feather-winged horse body", "broad-winged warhorse body")
_FORM_GIANT = ("towering muscular body", "rangy weathered body", "massive broad-chested body")
_FORM_FOLK = (
    "tall lean build", "broad powerful build", "wiry agile build", "stocky solid build",
    "weathered rangy build", "slight nimble build",
)
_FORM_ELEMENTAL = (
    "towering humanoid shape", "swirling vortex shape", "crouching bestial shape",
    "tall serpentine shape",
)
_FORM_WALKING_DEAD = (
    "gaunt skeletal frame", "hunched emaciated frame", "tall armoured frame",
    "withered robed frame",
)
_FORM_RESTLESS = ("tattered translucent shape", "hooded drifting shape", "armoured translucent shape")
_FORM_GOLEM = ("hulking humanoid body", "towering blocky body", "broad-shouldered squat body")

FORM_POOLS: dict[str, tuple[str, ...]] = {
    #: The stranger's forms: only a foreign-genre kind reaches these.
    POOL_DEFAULT_KEY: ("hulking body", "slender body", "sprawling body"),
    # dragon
    "winged dragon": _FORM_WINGED_DRAGON,
    "serpent wyrm": _FORM_SERPENT_WYRM,
    "sea wyrm": _FORM_SEA_SERPENT,
    "many-headed dragon": _FORM_HYDRA,
    # mythic beast
    "unicorn": _FORM_HORSE + ("goat-legged horse body",),
    "nightmare steed": ("gaunt horse body", "powerful warhorse body"),
    "kelpie": ("sleek dripping horse body", "long-maned horse body"),
    "silver stag": ("long-legged stag body", "heavy-antlered stag body"),
    "pegasus": _FORM_WINGED_HORSE,
    "hippogriff": ("eagle-fronted horse body with broad wings", "long-winged eagle-headed horse body"),
    "griffin": ("lion body with an eagle's head and wings", "lean eagle-fronted lion body"),
    "roc": ("vast eagle body", "long-tailed raptor body"),
    "phoenix": ("long-tailed firebird body", "slender crested bird body"),
    "thunderbird": ("vast storm-feathered bird body", "broad-winged raptor body"),
    "cockatrice": ("serpent-tailed fowl body", "long-necked wattled fowl body"),
    "manticore": ("lion body with a scorpion tail", "bat-winged lion body"),
    "chimera": ("lion body with a goat's head on its back", "three-headed lion body"),
    "sphinx": ("lion body with a human face", "winged lion body with a human face"),
    # Round XV: a plain bear, wolf, boar, turtle or spider body is drawn as the Earth
    # animal; the silhouette itself has to say it is not one.
    "dire wolf": ("rangy wolf body with a bristling bony spine",
                  "heavy-shouldered wolf body with curling brow horns"),
    "cave bear": ("hulking bear body with a ridge of stony plates",
                  "long-clawed bear body with bony forearm spurs"),
    "great tusked boar": ("boar body with an armoured bony crest",
                          "hump-shouldered boar body with iron-dark tusks"),
    "basilisk": ("eight-legged lizard body", "low serpentine lizard body"),
    "behemoth": ("vast horned quadruped body", "elephantine armoured body"),
    "giant cave spider": ("long-legged spider body with a crystal-studded abdomen",
                          "bloated spider body with a spined abdomen"),
    "hellhound": ("lean hound body", "broad-chested hound body"),
    "treant": ("towering tree body on root legs", "gnarled oak body with branch arms"),
    "kraken": ("vast many-armed body", "long-armed cephalopod body"),
    "hippocamp": ("horse-fronted fish-tailed body",),
    "giant sea turtle": ("vast domed-shell turtle body with a mossy island on its back",
                         "ridge-shelled turtle body crusted with coral spires"),
    # giant-kin
    "troll": ("hunched long-armed body", "towering gaunt body", "stooped knuckle-dragging body"),
    "ogre-kin": ("pot-bellied brawny body", "broad-shouldered hulking body"),
    "giant": _FORM_GIANT,
    "ettin": ("two-headed hulking body", "two-headed towering body"),
    # small folk
    "goblinoid": ("wiry stooped build", "scrawny long-eared build", "squat muscular build"),
    "kobold": ("small scaled lizard build", "wiry scaled build"),
    "gnome-kin": ("stout short build", "spry wiry build", "round-bellied short build"),
    "pixie": ("slender dragonfly-winged build", "moth-winged slight build"),
    "sprite": ("slender dragonfly-winged build", "moth-winged slight build"),
    "imp": ("bat-winged wiry build", "horned bat-winged build"),
    # hybrid folk
    "centaur": ("horse body below a human torso", "draught-horse body below a broad human torso"),
    "satyr": ("goat-legged human build", "shaggy goat-legged build"),
    "faun": ("goat-legged human build", "slender goat-legged build"),
    "minotaur": ("bull-headed towering build", "bull-headed brawny build"),
    "gorgon": ("human torso and arms above a coiled serpent tail", "two-legged scaled body"),
    "naga": ("human torso and arms above a long serpent tail",),
    "harpy": ("feather-armed taloned build",),
    "merfolk": ("long fish tail below a human torso",),
    "selkie": ("sleek seal-like build", "lithe seal-skinned build"),
    "dryad": ("slender bark-skinned build", "willowy bark-skinned build"),
    # folk
    "adventurer": _FORM_FOLK,
    "elf": ("tall willowy build", "lithe graceful build", "slender poised build"),
    "dwarf": ("stocky broad build", "barrel-chested short build", "thickset powerful build"),
    "orc": ("hulking muscled build", "lean scarred build", "broad tusked build"),
    "halfling": ("small nimble build", "round-cheeked small build"),
    # spirit or elemental
    "elemental": _FORM_ELEMENTAL,
    "earth elemental": ("hulking boulder-limbed shape", "towering rock-slab shape"),
    "magma elemental": ("hulking humanoid shape", "towering humanoid shape"),
    "will-o'-wisp": ("small drifting orb shape", "wavering teardrop shape"),
    "sylph": ("slender winged humanoid shape", "willowy drifting humanoid shape"),
    "undine": ("flowing humanoid shape", "slender rising column shape"),
    "forest spirit": ("antlered humanoid shape", "tall stag-headed shape"),
    # undead
    "walking dead": _FORM_WALKING_DEAD,
    "mummy": ("bandage-wrapped withered frame", "tall bandage-wrapped frame"),
    "drowned revenant": ("weed-draped swollen frame", "gaunt weed-draped frame"),
    "restless spirit": _FORM_RESTLESS,
    # construct
    "golem": _FORM_GOLEM,
    "bronze colossus": ("towering statuesque body", "vast armoured statuesque body"),
    "animated armour": ("hollow plate-armoured body", "towering plate-armoured body"),
    "clockwork guardian": ("clockwork humanoid body", "clockwork lion body"),
    "living statue": ("statuesque humanoid body", "robed statuesque body"),
    "gargoyle": ("winged crouching stone body", "horned winged stone body"),
    # structure
    "castle": ("high-walled keep with round towers", "square stone keep with corner turrets",
               "sprawling hilltop fortress"),
    "watchtower": ("tall narrow tower", "squat round tower"),
    "ruined keep": ("square stronghold with broken walls", "roofless round fortress"),
    "city gate": ("twin-towered gatehouse", "arched gatehouse in a high wall"),
    "fortified bridge": ("arched stone span with a gate tower", "long many-arched causeway"),
    "shrine": ("domed stone rotunda", "open-sided pillared pavilion"),
    "temple": ("columned stone sanctuary", "stepped pyramid"),
    "standing stone circle": ("ring of tall rough-hewn stones", "double ring of leaning stones"),
    "mountain monastery": ("cluster of terraced cliffside halls", "walled compound on a crag"),
    "wayside shrine": ("small roofed niche on a post", "carved stone wayside pillar"),
    "wizard's tower": ("tall spiralling spire", "crooked leaning spire"),
    "floating citadel": ("fortress-crowned floating rock", "spire-crowned floating crag"),
    "crystal spire": ("tall faceted pinnacle", "cluster of faceted pinnacles"),
    "elven tree palace": ("halls woven into a giant tree", "tiered halls among giant boughs"),
    "dwarven stronghold gate": ("vast carved portal in a cliff face",),
    "windmill": ("tall timber mill with lattice arms", "stone mill tower with lattice arms"),
    "lighthouse": ("tall stone beacon tower", "squat headland beacon tower"),
    "witch's hut": ("crooked cottage on stilts", "moss-roofed crooked cottage"),
    # vessel
    "galleon": ("three-masted high-sterned hull",),
    "longship": ("long low dragon-prowed hull",),
    "war galley": ("long oared hull with a bronze ram",),
    "river barge": ("broad flat-bottomed hull",),
    "pirate sloop": ("sleek single-masted hull",),
    "airship": ("gasbag above a wooden hull", "twin gasbags above a long hull"),
    "sky galleon": ("winged wooden hull under full sail",),
    "cloud skiff": ("slim skiff hull under a canvas wing",),
    "war chariot": ("light two-wheeled frame", "heavy scythe-wheeled frame"),
    "merchant caravan wagon": ("canvas-covered four-wheeled cart",),
    "royal carriage": ("gilded enclosed coach body",),
    "siege tower": ("tall wheeled timber frame",),
    "painted travelling wagon": ("barrel-roofed wooden caravan",),
    # artifact
    "sword in the stone": ("longsword thrust into a boulder",),
    "crystal orb": ("perfect sphere on a claw-footed stand", "floating sphere"),
    "runestone": ("tall carved standing stone", "squat rune-cut boulder"),
    "cursed idol": ("squat many-armed figure", "tall grimacing effigy"),
    "portal arch": ("freestanding carved stone gateway", "ring of carved stone"),
    "enchanted tome": ("thick iron-bound book", "floating open book"),
    "reliquary": ("ornate gabled casket", "tall spired casket"),
    "magic mirror": ("tall oval glass in a carved frame", "round hand glass"),
    "jewelled crown": ("high-spired circlet", "simple circlet"),
    "staff of power": ("tall gnarled rod", "long rod crowned with a claw"),
    "jewelled chalice": ("tall footed goblet",),
    "dragon egg": ("large scaled ovoid", "cluster of scaled ovoids"),
    "ancient hourglass": ("tall sand-timer in a carved frame",),
    "rune-carved anvil": ("squat block of rune-cut iron", "horned block of blackened iron"),
    "dragon-skull totem": ("vast horned skull set on a stone slab",
                           "skull half-sunk in a heap of bones"),
}


# ---------------------------------------------------------------------------
# Material -- hide, coat, garb, stone, timber
# ---------------------------------------------------------------------------

_MAT_DRAGON = (
    "overlapping armoured scales", "iridescent scales", "rough ridged scales",
    "smooth glossy scales", "bronze-edged scales", "heavy plated scales",
    "crystal-flecked scales",
)
_MAT_ADVENTURER = (
    "suit of polished plate armour", "chainmail hauberk", "hooded leather jerkin",
    "travel-worn cloak and tunic", "quilted gambeson", "fur-trimmed coat",
)
_MAT_GOLEM = ("rough-hewn granite", "carved basalt", "cracked river clay", "riveted cast iron")

MATERIAL_POOLS: dict[str, tuple[str, ...]] = {
    POOL_DEFAULT_KEY: ("weathered stone", "carved oak", "hammered bronze", "woven cloth"),
    # dragon
    "winged dragon": _MAT_DRAGON,
    "serpent wyrm": _MAT_DRAGON,
    "many-headed dragon": _MAT_DRAGON,
    "sea wyrm": ("slick finned scales", "barnacle-crusted scales", "pearlescent scales"),
    # mythic beast
    "hoofed beast": ("silky coat", "dappled coat", "shaggy winter coat", "short sleek coat"),
    "winged beast": ("dense plumage", "fur and feathers", "iridescent plumage", "ember-tipped plumage"),
    "chimeric beast": ("short lion fur", "matted mane and hide", "leathery hide"),
    "great beast": ("thick shaggy fur", "coarse heavy fur", "bristly hide", "armoured hide"),
    "basilisk": ("stony scales", "rough ridged scales"),
    "giant cave spider": ("bristled chitin", "glossy chitin"),
    "hellhound": ("sooty scorched hide", "short cinder-flecked fur"),
    "treant": ("gnarled bark", "moss-draped bark"),
    "sea beast": ("rubbery mottled skin", "sleek scales", "barnacled shell"),
    # giant-kin
    "troll": ("warty hide", "moss-grown hide", "rough stony skin"),
    "ogre-kin": ("coarse warty skin and hide wraps", "thick hide wraps"),
    "giant": ("rough furs and hides", "stitched hide tunic", "iron-studded leather hauberk"),
    "frost giant": ("frost-rimed furs", "rough furs and hides"),
    "fire giant": ("suit of soot-blackened iron armour", "iron-studded leather hauberk"),
    # small folk
    "goblinoid": ("ragged leathers", "scavenged chainmail scraps", "oversized hooded cloak"),
    "gnome-kin": ("leather tinker's apron", "hooded wool tunic", "embroidered waistcoat"),
    "winged fey": ("leaf-woven tunic", "spider-silk wrap", "petal-layered wrap"),
    "imp": ("tattered loincloth", "scorched rag wrap"),
    # hybrid folk
    "hoofed folk": ("leather war harness", "woven wool cloak", "simple linen wrap"),
    "minotaur": ("iron-studded leather kilt", "chain-hung war harness"),
    "serpent folk": ("bronze scale hauberk", "draped linen robes", "gilded scale hauberk"),
    "winged folk": ("torn linen wrap", "feather-trimmed leather harness"),
    "sea folk": ("woven kelp sash", "shell-studded harness"),
    "selkie": ("sealskin cloak", "woven kelp sash"),
    "tree folk": ("woven leaf wrap", "living ivy gown"),
    # folk
    "adventurer": _MAT_ADVENTURER,
    "knight": ("suit of polished plate armour", "suit of dented plate armour", "chainmail and surcoat"),
    "paladin": ("suit of polished plate armour", "suit of gilded plate armour", "chainmail and surcoat"),
    "sorcerer": ("flowing embroidered robes", "high-collared silk robes"),
    "necromancer": ("tattered hooded robes", "bone-trimmed dark robes"),
    "monk": ("rope-belted wool robe", "wrapped training tunic"),
    "cleric": ("chainmail and surcoat", "hooded vestments"),
    "druid": ("fur-trimmed hooded robe", "leaf-woven mantle"),
    "hedge witch": ("hooded wool shawl and skirts", "herb-hung layered robes"),
    "blacksmith": ("leather smithing apron", "soot-stained work shirt"),
    "herbalist": ("herb-hung layered robes", "linen smock"),
    "travelling merchant": ("fur-trimmed coat", "layered silk robes"),
    "wandering scholar": ("ink-stained scholar's robe", "travel-worn cloak and tunic"),
    "elf": ("suit of leaf-patterned silk armour", "silver-thread robes", "fitted dark leathers"),
    "dwarf": ("suit of rune-etched plate armour", "fur-lined mail coat", "leather smithing apron"),
    "orc": ("suit of spiked iron armour", "bone-studded leathers", "heavy fur mantle"),
    "halfling": ("snug wool waistcoat", "soft leather jerkin", "hooded travelling cloak"),
    # spirit or elemental
    "fire elemental": ("living flame", "roaring white-hot flame"),
    "water elemental": ("churning seawater", "glassy flowing water"),
    "air elemental": ("whirling wind and dust", "spiralling storm vapour"),
    "storm elemental": ("crackling storm cloud", "rain-lashed storm vapour"),
    "ice elemental": ("jagged ice shards", "frost crystal"),
    "earth elemental": ("boulders and packed earth", "cracked granite"),
    "magma elemental": ("molten rock and cinders", "cooling black magma crust"),
    "will-o'-wisp": ("pale drifting light", "flickering cold fire"),
    "sylph": ("swirling air and silk", "translucent wind-woven veils"),
    "undine": ("flowing clear water", "rippling seawater"),
    "forest spirit": ("moss and woven branches", "bark and living leaves"),
    # undead
    "walking dead": ("yellowed bone", "rotting rags", "rusted chainmail", "grave-stained robes"),
    "mummy": ("linen burial wrappings", "resin-stiffened wrappings"),
    "drowned revenant": ("sodden rags and weed", "barnacle-crusted rags"),
    "restless spirit": ("tattered spectral cloth", "translucent grave shroud"),
    # construct
    "golem": _MAT_GOLEM,
    "iron golem": ("riveted cast iron", "blackened wrought iron"),
    "crystal golem": ("faceted quartz crystal", "cloudy crystal"),
    "bronze colossus": ("verdigris bronze", "polished bronze"),
    "animated armour": ("dented steel plate", "blackened steel plate"),
    "clockwork guardian": ("brass gears and plating", "copper plating and cogs"),
    "living statue": ("polished marble", "weathered limestone"),
    "gargoyle": ("weathered stone", "lichen-spotted stone"),
    # structure
    "fortification": ("rough fieldstone", "dressed limestone blocks", "basalt blocks"),
    "sacred site": ("white marble", "dressed limestone blocks", "moss-covered stone"),
    "standing stone circle": ("lichen-spotted granite", "weathered sandstone"),
    "arcane tower": ("basalt blocks", "carved living wood", "enchanted crystal"),
    "crystal spire": ("enchanted crystal", "clear faceted quartz"),
    "dwelling": ("timber and whitewashed plaster", "carved living wood", "rough fieldstone"),
    # vessel
    "sailing ship": ("tarred oak planking", "clinker-built pine planks", "gilded carved timber"),
    "flying ship": ("varnished oak planking", "brass-banded timber", "weathered canvas and timber"),
    "land vehicle": ("iron-banded oak", "gilded carved timber", "weathered canvas and timber"),
    # artifact
    "relic": ("hammered gold", "tarnished silver", "polished obsidian", "rough-cut stone",
              "clear crystal", "ancient bronze", "carved bone", "dragonscale leather",
              "enchanted glass"),
    "monument": ("rough-cut stone", "polished obsidian", "ancient bronze", "carved bone",
                 "blackened iron", "weathered granite"),
}


# ---------------------------------------------------------------------------
# Colour -- the subject's own, never the light's
# ---------------------------------------------------------------------------

_COLOR_SCALE = (
    "crimson", "emerald green", "cobalt blue", "gold", "bronze", "copper", "coal black",
    "bone white", "silver", "violet", "ash grey", "deep teal", "burnt orange", "blood red",
)
_COLOR_COAT = (
    "pure white", "raven black", "dappled grey", "chestnut", "tawny gold", "silver grey",
    "russet", "cream", "earth brown", "slate grey",
)
_COLOR_SKIN = (
    "grey-green", "mottled brown", "slate grey", "moss green", "clay red", "pale blue-grey",
    "ochre", "ashen",
)
_COLOR_GARB = (
    "deep crimson", "forest green", "royal blue", "black", "pale beige", "ochre", "burgundy",
    "silver-grey", "earth brown", "sky blue", "violet",
)
_COLOR_STONE = ("granite grey", "sandstone", "black", "white", "weathered bronze", "lichen grey")
_COLOR_SPIRIT = ("pale blue", "ember orange", "sea green", "silver-white", "violet", "storm grey")

PRIMARY_COLOR_POOLS: dict[str, tuple[str, ...]] = {
    POOL_DEFAULT_KEY: _COLOR_GARB,
    "dragon": _COLOR_SCALE,
    "mythic beast": _COLOR_COAT,
    "giant-kin": _COLOR_SKIN,
    "small folk": _COLOR_GARB,
    "hybrid folk": _COLOR_GARB,
    "folk": _COLOR_GARB,
    "spirit or elemental": _COLOR_SPIRIT,
    "fire elemental": ("ember orange", "white-gold", "blood red"),
    "magma elemental": ("ember orange", "coal black", "blood red"),
    "water elemental": ("sea green", "pale blue", "deep teal"),
    "undine": ("sea green", "pale blue", "deep teal"),
    "ice elemental": ("pale blue", "silver-white"),
    "air elemental": ("storm grey", "pale blue", "silver-white"),
    "storm elemental": ("storm grey", "violet", "silver-white"),
    "undead": ("bone white", "ashen", "grave-soil brown", "black", "pale grey"),
    "construct": _COLOR_STONE,
    "structure": _COLOR_STONE,
    "vessel": ("black", "earth brown", "crimson", "royal blue", "gold", "weathered grey"),
    "artifact": ("gold", "silver", "black", "blood red", "deep violet", "bone white"),
}
PRIMARY_COLOR_POOL: tuple[str, ...] = tuple(
    dict.fromkeys(v for pool in PRIMARY_COLOR_POOLS.values() for v in pool)
)
ACCENT_COLOR_POOL: tuple[str, ...] = (
    "gold", "silver", "crimson", "black", "bone white", "bronze", "deep blue", "emerald green",
    "violet", "copper", "burgundy", "teal", "ochre", "pewter", "rust red", "forest green",
)
EMITTER_COLOR_POOL: tuple[str, ...] = (
    "arcane violet", "fey green", "ember orange", "frost blue", "golden", "pale silver",
    "blood red", "sea green", "white-gold", "amber", "hellfire red", "wisp blue", "spectral teal",
    "verdant green", "royal purple", "copper orange",
)
EMITTER_COLOR_POOLS: dict[str, tuple[str, ...]] = {
    POOL_DEFAULT_KEY: EMITTER_COLOR_POOL,
    "fire elemental": ("ember orange", "white-gold", "amber"),
    "magma elemental": ("ember orange", "amber", "blood red"),
    "water elemental": ("sea green", "frost blue", "pale silver"),
    "undine": ("sea green", "frost blue", "pale silver"),
    "ice elemental": ("frost blue", "pale silver"),
    "phoenix": ("ember orange", "golden", "white-gold"),
    "hellhound": ("ember orange", "blood red", "amber"),
}


# ---------------------------------------------------------------------------
# Markings and surface detail
# ---------------------------------------------------------------------------
#
# ``markings`` carries no readable text: a model garbles lettering, and a rune
# is a shape here only outside this field.

MARKINGS_POOLS: dict[str, tuple[str, ...]] = {
    POOL_DEFAULT_KEY: ("painted heraldry", "carved spiral patterning", "banded trim"),
    "dragon": ("tiger-striped scale banding", "spotted flank patterning", "pale underbelly banding",
               "darker dorsal banding", "old battle scars in parallel rows"),
    "mythic beast": ("dappled flank spots", "pale facial markings", "striped flank banding",
                     "silver-tipped fur"),
    "winged beast": ("barred wing feathers", "pale facial markings", "dappled flank spots"),
    "giant cave spider": ("pale banded leg rings", "jagged back patterning"),
    "sea beast": ("mottled shell patterning", "pale ridge banding"),
    "giant-kin": ("ochre war paint", "ritual scarification", "blue woad swirls", "tribal bone charms"),
    "small folk": ("smeared war paint", "stolen heraldic badges", "bead-and-feather charms"),
    "hybrid folk": ("painted spiral tattoos", "gold arm bands", "braided hair beads"),
    "folk": ("embroidered heraldry", "painted shield heraldry", "woven clan tartan",
             "tooled leather patterning", "silver clan jewellery"),
    "spirit or elemental": ("slowly shifting spiral patterning", "rippling bands of colour"),
    "undead": ("faded heraldry", "tarnished funeral jewellery", "grave-dirt streaking"),
    "construct": ("carved spiral patterning", "inlaid gold lines", "chiselled geometric banding"),
    "structure": ("hanging heraldic banners", "carved relief friezes", "painted crests above the gate"),
    "sailing ship": ("painted serpent designs", "striped sails", "heraldic pennants",
                     "gilded stern carvings"),
    "flying ship": ("painted serpent designs", "striped sails", "heraldic pennants",
                    "gilded stern carvings"),
    "land vehicle": ("painted scrollwork panels", "heraldic pennants", "painted flower garlands"),
    "artifact": ("filigree scrollwork", "carved dragon motifs", "inlaid star pattern"),
}

SURFACE_DETAIL_POOLS: dict[str, tuple[str, ...]] = {
    POOL_DEFAULT_KEY: ("weathered wear", "fine carved detail", "chipped edges"),
    "dragon": ("battle scarring", "cracked plating along one flank", "moss grown into old scars",
               "gleaming unmarked plating", "barnacle crusting", "cracked claw tips"),
    "mythic beast": ("old claw scars", "fresh battle wounds", "mud-caked flanks",
                     "healed arrow scars", "sleek well-fed flanks"),
    "hoofed beast": ("burrs matted into the coat", "groomed gleaming hair", "mud-caked legs"),
    "winged beast": ("singed feather tips", "ruffled feathers", "old claw scars"),
    "giant-kin": ("lichen growing on the skin", "old axe scars", "caked river mud", "cracked knuckles"),
    "small folk": ("dirt-smudged cheeks", "soot-blackened fingers", "torn hems"),
    "hybrid folk": ("sun-weathered skin", "braided hair", "old battle scars"),
    "folk": ("travel dust", "battle-dented armour", "mud-spattered boots", "weathered skin",
             "neatly mended seams", "rain-soaked clothing"),
    "spirit or elemental": ("constantly shifting ripples", "trailing sparks and motes"),
    "undead": ("exposed ribs", "peeling grave-worn skin", "rusted buckles", "cobwebbed joints"),
    "restless spirit": ("frayed translucent edges", "slowly rippling folds"),
    "construct": ("cracks sealed with gold", "moss in the seams", "chipped carving", "rust streaks"),
    "structure": ("ivy climbing the walls", "crumbling battlements", "weathered stonework",
                  "fresh whitewash", "arrow-scarred walls"),
    "sailing ship": ("salt-stained timbers", "fresh paint along the hull", "barnacled waterline",
                     "rain-darkened canvas"),
    "flying ship": ("fresh paint along the hull", "rain-darkened canvas", "wind-scoured timbers"),
    "land vehicle": ("mud-caked wheels", "fresh paint along the sides", "rain-darkened canvas",
                     "dust-coated panels"),
    "artifact": ("worn smooth by hands", "chipped gilding", "dust in the carvings", "hairline cracks"),
}

# ---------------------------------------------------------------------------
# Components -- appendages, emitters, armament, sensors, aperture, extras
# ---------------------------------------------------------------------------
#
# A count noun is singular with its head last ("spiral horn"), and every one of
# them is classified in ``CARDINALITY`` below: a unicorn has one horn whatever
# the count dropdown would have liked.

APPENDAGE_POOLS: dict[str, tuple[str, ...]] = {
    POOL_DEFAULT_KEY: ("carved finial", "hanging chain"),
    # dragon
    "winged dragon": ("curved horn", "swept-back horn", "leathery wing", "tattered wing",
                      "spiked tail", "dorsal spine", "neck frill", "cheek spike"),
    "serpent wyrm": ("curved horn", "dorsal spine", "neck frill", "spiked tail", "whisker barbel"),
    "sea wyrm": ("dorsal fin", "fin crest", "spiked tail", "whisker barbel"),
    "many-headed dragon": ("serpent-headed neck", "dorsal spine", "spiked tail"),
    # mythic beast
    "unicorn": ("spiral horn", "feathered fetlock", "flowing tail"),
    "nightmare steed": ("flowing mane", "feathered fetlock"),
    "kelpie": ("weed-tangled mane", "webbed hoof"),
    "silver stag": ("branching antler", "short tail"),
    "pegasus": ("feathered wing", "flowing tail"),
    "hippogriff": ("feathered wing", "taloned foreleg"),
    "winged beast": ("broad wing", "tail plume", "feather crest", "taloned foot"),
    "manticore": ("scorpion tail", "bat wing", "shaggy mane"),
    "chimera": ("goat head", "serpent tail", "shaggy mane"),
    "sphinx": ("feathered wing", "braided mane"),
    "great beast": ("hackled mane", "long tail", "clawed forepaw"),
    "great tusked boar": ("curved tusk", "bristle crest"),
    "basilisk": ("crested spine", "clawed forepaw"),
    "behemoth": ("curved horn", "curved tusk", "armoured tail"),
    "giant cave spider": ("long leg", "hooked pedipalp"),
    "treant": ("branch arm", "root leg", "leafy crown"),
    "kraken": ("sucker-lined tentacle", "long hooked tentacle"),
    "hippocamp": ("finned tail", "webbed foreleg"),
    "giant sea turtle": ("broad flipper", "ridged tail"),
    # giant-kin
    "troll": ("long tusk", "pointed ear", "matted hair tangle"),
    "ogre-kin": ("jutting tusk", "heavy brow ridge"),
    "giant": ("braided beard", "iron arm band", "heavy chain belt"),
    "cyclops": ("heavy brow ridge", "iron arm band"),
    # small folk
    "goblinoid": ("large pointed ear", "long hooked nose"),
    "kobold": ("short horn", "whip tail"),
    "gnome-kin": ("long braided beard", "tall pointed cap"),
    "pixie": ("dragonfly wing", "feathery antenna"),
    "sprite": ("moth wing", "feathery antenna"),
    "imp": ("bat wing", "curved horn", "barbed tail"),
    # hybrid folk
    "centaur": ("braided horse tail", "braided mane"),
    "satyr": ("curling ram horn", "tufted tail"),
    "faun": ("curling ram horn", "tufted tail"),
    "minotaur": ("bull horn", "tufted tail"),
    "gorgon": ("hissing viper",),
    # A cobra hood and a braided tail made the naga a snake holding a sword.
    "naga": ("long braided hair", "jewelled arm band"),
    "harpy": ("feathered arm", "taloned foot"),
    "sea folk": ("fin-edged ear", "webbed hand"),
    "dryad": ("leafy hair tendril", "twig antler"),
    # folk -- what is worn over the body
    "adventurer": ("fur-trimmed pauldron", "tattered cape", "steel gauntlet", "leather bracer",
                   "winged helm", "hooded mantle", "feathered hat"),
    "elf": ("leaf-shaped pauldron", "flowing cape", "silver circlet", "leather bracer"),
    "dwarf": ("horned helm", "braided beard clasp", "steel gauntlet"),
    "orc": ("bone pauldron", "spiked collar", "fur mantle"),
    "halfling": ("hooded mantle", "feathered hat"),
    # spirit or elemental
    "elemental": ("trailing tendril", "whirling arm", "streaming tail"),
    "earth elemental": ("boulder fist", "jagged stone shoulder"),
    "magma elemental": ("boulder fist", "jagged stone shoulder"),
    "fey spirit": ("trailing tendril", "streaming tail", "branching antler"),
    # undead
    "walking dead": ("tattered cape", "rusted pauldron", "dangling chain"),
    "lich": ("iron crown", "tattered cape"),
    "restless spirit": ("trailing tatter", "spectral chain"),
    # construct
    "golem": ("boulder fist", "carved shoulder plate", "moss-grown shoulder"),
    "animated armour": ("plumed helm crest", "tattered surcoat"),
    "clockwork guardian": ("spinning gear crest", "piston arm"),
    "living statue": ("carved laurel crown", "draped stone cloak"),
    "gargoyle": ("stone wing", "curled horn"),
    # structure
    "fortification": ("round tower", "square turret", "drawbridge", "curtain wall"),
    "sacred site": ("carved stone pinnacle", "slender spire", "colonnade", "domed roof"),
    "standing stone circle": ("capstone lintel", "fallen outlier stone"),
    "arcane tower": ("slender spire", "floating stone ring", "open balcony"),
    "dwelling": ("stone chimney", "open balcony", "turf roof"),
    "windmill": ("lattice sail", "stone chimney"),
    "lighthouse": ("lantern gallery", "stone chimney"),
    # vessel
    "sailing ship": ("tall mast", "square sail", "carved figurehead", "long oar", "lateen sail"),
    "flying ship": ("canvas wing", "rudder fin", "tall mast"),
    "land vehicle": ("banner pole", "canvas canopy", "iron-rimmed wheel"),
    # artifact
    "relic": ("carved claw", "jewelled finial", "bird-shaped handle"),
    "monument": ("carved capstone", "worn stone base"),
}

EMITTER_POOLS: dict[str, tuple[str, ...]] = {
    POOL_DEFAULT_KEY: ("enchanted gem", "luminous rune tracery"),
    "dragon": ("ember-hot throat", "smouldering nostril", "molten scale seam", "luminous eye"),
    "sea wyrm": ("luminous eye", "luminous gill slit", "luminous spot"),
    "mythic beast": ("luminous eye", "faint luminous marking"),
    "unicorn": ("luminous horn", "star-flecked mane"),
    "phoenix": ("burning plume", "ember tail feather"),
    "hellhound": ("ember eye", "smouldering paw"),
    "thunderbird": ("crackling feather", "luminous eye"),
    "giant-kin": ("luminous runic tattoo", "ember eye"),
    "fire giant": ("smouldering brand", "ember eye"),
    "small folk": ("luminous eye", "enchanted gem"),
    "winged fey": ("luminous wing vein", "enchanted gem"),
    "imp": ("ember eye", "smouldering horn tip"),
    "hybrid folk": ("luminous eye", "enchanted gem"),
    "dryad": ("luminous blossom", "luminous eye"),
    "folk": ("enchanted gem", "luminous rune tracery", "crackling spell orb"),
    "spirit or elemental": ("luminous core", "drifting mote"),
    "fire elemental": ("white-hot core", "crackling spark"),
    "magma elemental": ("white-hot core", "molten crack"),
    "undead": ("ember eye socket", "cold luminous eye", "spectral flame"),
    "construct": ("luminous rune seam", "enchanted gem core", "ember eye"),
    "structure": ("lantern-hung window", "enchanted beacon", "luminous crystal"),
    "sailing ship": ("stern lantern", "enchanted gem", "luminous rune tracery"),
    "flying ship": ("stern lantern", "enchanted gem", "luminous rune tracery"),
    "land vehicle": ("hanging lantern", "enchanted gem"),
    "artifact": ("enchanted gem", "luminous rune tracery", "luminous core"),
}

ARMAMENT_POOLS: dict[str, tuple[str, ...]] = {
    POOL_DEFAULT_KEY: ("longsword", "spear"),
    "dragon": ("raking claw", "barbed tail spike", "curved fang"),
    "mythic beast": ("raking claw", "curved fang"),
    "hoofed beast": ("iron-shod hoof",),
    "pegasus": ("iron-shod hoof",),
    "winged beast": ("hooked talon", "tearing beak"),
    "griffin": ("hooked talon", "tearing beak"),
    "roc": ("hooked talon", "tearing beak"),
    "great tusked boar": ("goring tusk",),
    "giant cave spider": ("venomous fang",),
    "kraken": ("crushing beak",),
    "giant-kin": ("tree-trunk club", "iron-banded war maul", "great throwing stone", "stone-headed axe",
                  "rusted cleaver"),
    "small folk": ("notched short blade", "crude spear", "sling", "rusty dagger"),
    "winged fey": ("thorn spear", "tiny bow"),
    "imp": ("barbed pitchfork",),
    "hybrid folk": ("longbow", "hunting spear", "curved sword"),
    "minotaur": ("double-bladed axe", "iron-bound club"),
    "sea folk": ("coral trident", "bone spear"),
    # A harpy's talons are her feet ("taloned foot"); in a carry sentence they
    # read as a talon held in the hand.
    "winged folk": (),
    "folk": ("longsword", "war hammer", "longbow", "dagger", "quarterstaff", "battle axe",
             "crossbow", "flanged mace", "rapier", "kite shield", "gnarled staff", "flail"),
    "elf": ("longbow", "rapier", "slender curved blade"),
    "wood elf archer": ("longbow",),
    "dwarf": ("battle axe", "war hammer", "crossbow"),
    "orc": ("flail", "battle axe", "heavy cleaver"),
    "halfling": ("dagger", "sling"),
    "knight": ("longsword", "kite shield", "war hammer"),
    "paladin": ("longsword", "flanged mace", "kite shield"),
    "cleric": ("flanged mace", "war hammer"),
    "archer": ("longbow", "crossbow"),
    "ranger": ("longbow", "dagger"),
    "rogue": ("dagger", "rapier", "crossbow"),
    "bard": ("rapier", "dagger"),
    "monk": ("quarterstaff",),
    "sorcerer": ("gnarled staff", "dagger"),
    "necromancer": ("gnarled staff", "dagger"),
    "hedge witch": ("gnarled staff", "dagger"),
    "druid": ("gnarled staff", "quarterstaff"),
    "wandering scholar": ("quarterstaff", "dagger"),
    "herbalist": ("dagger",),
    "travelling merchant": ("dagger", "crossbow"),
    "undead": ("rusted longsword", "notched axe", "cracked shield", "reaping scythe", "bone staff"),
    "construct": ("rune-etched greatsword", "halberd", "war hammer", "great stone maul"),
    "fortification": ("ballista", "trebuchet", "mounted crossbow"),
    # A shrine, a tower or a mill has no defences of its own. Without these a
    # native subject fell through to the stranger's longsword and spear, and a
    # wizard's tower "had a single spear" (validator check 32).
    "sacred site": (), "arcane tower": (), "dwelling": (),
    # Round XV: scoped by what the vessel is. A kind-wide pool bolted stern lanterns
    # and bolt throwers onto a siege tower, and anchors onto wagons.
    "sailing ship": ("bronze ballista", "boarding ram"),
    "flying ship": ("bronze ballista", "mounted crossbow"),
    "land vehicle": (),
    "war chariot": ("scythed wheel hub",),
    "siege tower": ("iron-capped battering ram", "mounted crossbow"),
}

SENSOR_POOLS: dict[str, tuple[str, ...]] = {
    POOL_DEFAULT_KEY: ("keen eye",),
    "dragon": ("slit-pupiled eye", "hooded eye", "heat-sensing pit"),
    "mythic beast": ("keen eye", "large dark eye", "golden eye"),
    "giant cave spider": ("many-faceted eye",),
    "giant-kin": ("small sunken eye", "bloodshot eye"),
    "cyclops": ("single great eye",),
    "small folk": ("beady eye", "large yellow eye"),
    "hybrid folk": ("keen eye", "dark heavy-lidded eye"),
    "serpent folk": ("unblinking serpent eye", "keen eye"),
    "folk": ("keen eye", "scarred eye", "looking glass"),
    "undead": ("dark eye socket", "pinpoint luminous eye"),
    "construct": ("gem-set eye", "carved stone eye"),
    "sailing ship": ("crow's nest",),
    "flying ship": ("crow's nest",),
    "land vehicle": (),
}

APERTURE_POOLS: dict[str, tuple[str, ...]] = {
    POOL_DEFAULT_KEY: ("hinged lid", "arched opening"),
    "dragon": ("fanged maw", "long toothed jaw", "hissing maw"),
    "mythic beast": ("snarling muzzle", "fanged maw"),
    "hoofed beast": ("soft muzzle", "flaring nostrils"),
    "pegasus": ("soft muzzle", "flaring nostrils"),
    "winged beast": ("hooked beak", "curved beak"),
    "sphinx": ("serene human mouth",),
    "sea beast": ("wide beaked mouth",),
    "giant-kin": ("gap-toothed mouth", "tusked underbite"),
    "small folk": ("needle-toothed grin", "gap-toothed grin"),
    "hybrid folk": ("grim-set mouth", "sharp-toothed smile"),
    "minotaur": ("flared bull nostrils", "ringed bull muzzle"),
    "serpent folk": ("forked-tongued mouth", "lipless serpent smile"),
    "folk": ("open-faced helm", "closed visor", "hooded face", "raised visor", "scarf-wrapped face"),
    "undead": ("grinning skull jaw", "rusted visor", "gaping jaw"),
    "construct": ("carved grille mouth", "open visor slit"),
    "structure": ("arched gateway", "portcullis gate", "great oak door", "round stained-glass window"),
    "sailing ship": ("stern cabin window", "open cargo hatch", "boarding gangway"),
    "flying ship": ("stern cabin window", "open cargo hatch"),
    "land vehicle": ("curtained side window", "open rear door"),
    "artifact": ("hinged lid", "keyhole", "gem socket"),
}

EXTRAS_POOLS: dict[str, tuple[str, ...]] = {
    POOL_DEFAULT_KEY: ("iron chain", "carved pedestal"),
    "dragon": ("broken chain collar", "old arrow shafts in its hide", "war saddle", "clinging coins"),
    "mythic beast": ("war saddle", "jewelled bridle", "broken chain collar", "rider's harness"),
    "giant-kin": ("bone necklace", "bundle of logs", "iron chain belt", "sack slung over one shoulder"),
    "small folk": ("stolen coin purse", "sack of loot", "bone necklace", "tinker's tool belt"),
    "winged fey": ("tiny woven satchel", "thistledown cloak", "stolen silver thimble"),
    # Carried, never worn: this slot is spoken "they carry ...".
    "hybrid folk": ("quiver of arrows", "leather satchel", "waterskin", "bone-carved talisman"),
    # Panpipes are a satyr's and a faun's; a minotaur and a harpy carrying reed
    # pipes into a fight were drawn holding two bamboo flutes.
    "satyr": ("set of panpipes", "wineskin", "leather satchel"),
    "faun": ("set of panpipes", "wineskin", "leather satchel"),
    "folk": ("leather satchel", "rolled map", "quiver of arrows", "coin purse", "hooded lantern",
             "chained spellbook", "herb pouch", "lute", "hunting horn", "bedroll"),
    "undead": ("rusted manacle", "tattered banner", "clinging grave dirt"),
    "construct": ("chain leash", "moss mantle", "carved rune plate"),
    "structure": ("hanging banner", "courtyard well", "row of stone gargoyles"),
    # "furled" (rolled up) rendered as literal fur fringe on the banners --
    # the same substance-word-collision class as "forked" tongue -> fork.
    "sailing ship": ("rolled banner", "cargo of barrels", "ship's boat", "iron anchor"),
    "flying ship": ("rolled banner", "cargo of barrels", "hanging sandbag ballast"),
    "land vehicle": ("rolled banner", "cargo of barrels", "lashed-down travel trunks"),
    # What the object rests on or stands among, spoken as such: "bears a carved
    # pedestal" left a small relic floating in the air. "velvet cushion" and
    # "silk-draped table" are indoor/furnished surfaces -- gated below
    # (VALUE_NEEDS) so an hourglass no longer rests on a velvet cushion in a
    # reed marsh; the stone/plinth surfaces stay place-neutral.
    "relic": ("velvet cushion", "carved stone pedestal", "moss-covered altar stone",
              "iron-bound plinth", "silk-draped table", "flat standing stone"),
    "monument": ("ring of old offerings", "carpet of thick moss", "scatter of melted candle stubs",
                 "circle of trampled earth"),
}

OMITTED_POOLS: frozenset[tuple[str, str]] = frozenset({
    ("armament", "sacred site"), ("armament", "arcane tower"), ("armament", "dwelling"),
    ("armament", "land vehicle"), ("sensors", "land vehicle"), ("armament", "winged folk"),
})


# ---------------------------------------------------------------------------
# Condition and scale
# ---------------------------------------------------------------------------

CONDITION_POOLS: dict[str, tuple[str, ...]] = {
    POOL_DEFAULT_KEY: ("ancient", "weathered", "battle-scarred", "gleaming"),
    "dragon": ("ancient", "young", "battle-scarred", "slumbering", "petrified", "gaunt",
               "venerable", "moss-crusted", "gleaming"),
    "mythic beast": ("young", "ancient", "battle-scarred", "slumbering", "petrified", "wild-eyed",
                     "sleek", "gaunt", "grizzled", "untamed"),
    "giant-kin": ("ancient", "battle-scarred", "slumbering", "petrified", "gaunt", "grizzled",
                  "moss-covered", "hulking"),
    "small folk": ("young", "battle-scarred", "ragged", "sly", "mischievous", "grizzled"),
    "hybrid folk": ("young", "ancient", "battle-scarred", "weathered", "proud", "wild-eyed"),
    "folk": ("young", "grizzled", "battle-weary", "travel-worn", "veteran", "weathered", "noble",
             "exiled"),
    "spirit or elemental": ("raging", "calm", "ancient", "newly summoned", "flickering", "towering"),
    "undead": ("ancient", "freshly risen", "crumbling", "battle-worn", "dormant", "grave-worn"),
    "construct": ("ancient", "dormant", "cracked", "battle-worn", "moss-covered", "newly forged",
                  "rune-scarred", "gleaming"),
    "structure": ("ruined", "abandoned", "ancient", "newly built", "moss-covered", "fortified",
                  "weathered", "overgrown", "frost-rimed"),
    "vessel": ("weathered", "battle-scarred", "newly launched", "gilded", "wrecked", "abandoned",
               "storm-battered"),
    "artifact": ("ancient", "cursed", "tarnished", "gleaming", "cracked", "dormant", "pristine",
                 "dust-covered"),
}

SCALE_POOLS: dict[str, tuple[str, ...]] = {
    POOL_DEFAULT_KEY: ("small", "large"),
    "dragon": ("small", "large", "huge", "colossal", "titanic"),
    "mythic beast": ("tiny", "small", "large", "huge", "colossal"),
    "troll": ("nine-foot-tall", "twelve-foot-tall"),
    "ogre-kin": ("ten-foot-tall", "fourteen-foot-tall"),
    "giant": ("twenty-foot-tall", "forty-foot-tall"),
    "goblinoid": ("three-foot-tall", "two-foot-tall"),
    "gnome-kin": ("three-foot-tall", "two-foot-tall"),
    "winged fey": ("six-inch-tall", "ten-inch-tall"),
    "hybrid folk": ("small", "large"),
    "folk": ("small", "large"),
    "spirit or elemental": ("tiny", "small", "large", "huge", "colossal"),
    "undead": ("small", "large", "huge"),
    "construct": ("small", "large", "huge", "colossal", "titanic"),
    "structure": ("small", "large", "huge", "colossal"),
    "vessel": ("small", "large", "huge", "colossal"),
    "artifact": ("tiny", "small", "large", "huge"),
}


# ---------------------------------------------------------------------------
# Counts and cardinality
# ---------------------------------------------------------------------------
#
# A count field asks its noun before its kind, so every count noun declares how
# many of it there can be. The classes are statements about bodies:
#
#   a lone part    -- there is one: a unicorn's horn, a figurehead, a crown
#   a matched pair -- bilateral: wings, eyes, fetlocks, pauldrons
#   a small set    -- a handful: towers, masts, gems
#   a limb set     -- limbs and heads, where a high count is the point
#   a body row     -- repeated down a body: spines, runic tattoos, spots
#   an array       -- genuinely many: windows, rune seams, lanterns
#   a crown        -- three at the least: a hydra's necks, a gorgon's vipers
#   a hand weapon  -- one in the hand
#   a paired arm   -- one or two: daggers, claws of a fist

COUNT_POOL: tuple[str, ...] = (
    "a single", "a pair of", "three", "four", "six", "eight", "a dozen", "a ring of",
    "a cluster of", "a fan of", "a crown of",
)

CARDINALITY_COUNTS: dict[str, tuple[str, ...]] = {
    "a lone part": ("a single",),
    "a matched pair": ("a pair of",),
    "a small set": ("a single", "a pair of", "three", "four"),
    "a limb set": ("a single", "a pair of", "three", "four", "six", "eight"),
    "a body row": ("a single", "a pair of", "three", "four", "six", "a cluster of", "a fan of"),
    "an array": ("a pair of", "three", "four", "six", "eight", "a dozen", "a ring of",
                 "a cluster of"),
    "a crown": ("three", "six", "eight", "a crown of"),
    "a hand weapon": ("a single",),
    "a paired arm": ("a single", "a pair of"),
}

APPENDAGE_COUNT_POOLS: dict[str, tuple[str, ...]] = {
    POOL_DEFAULT_KEY: ("a single", "a pair of", "three"), **CARDINALITY_COUNTS,
}
EMITTER_COUNT_POOLS: dict[str, tuple[str, ...]] = {
    POOL_DEFAULT_KEY: ("a single", "a pair of", "three"), **CARDINALITY_COUNTS,
}
ARMAMENT_COUNT_POOLS: dict[str, tuple[str, ...]] = {
    POOL_DEFAULT_KEY: ("a single", "a pair of"), **CARDINALITY_COUNTS,
}
SENSOR_COUNT_POOLS: dict[str, tuple[str, ...]] = {
    POOL_DEFAULT_KEY: ("a single", "a pair of"), **CARDINALITY_COUNTS,
}


def _cardinality(*groups: tuple[str, tuple[str, ...]]) -> dict[str, str]:
    """Invert ``(class, values)`` pairs into ``{value: class}``; a value has one class."""
    out: dict[str, str] = {}
    for class_name, values in groups:
        for value in values:
            if value in out:
                raise ValueError(f"{value!r} is in two cardinality classes")
            out[value] = class_name
    return out


CARDINALITY: dict[str, dict[str, str]] = {
    "appendages": _cardinality(
        ("a lone part", (
            "long braided hair", "carved capstone", "worn stone base", "tall mast",
            "carved finial", "spiral horn", "flowing tail", "flowing mane", "weed-tangled mane",
            "short tail", "tail plume", "feather crest", "scorpion tail", "shaggy mane",
            "goat head", "serpent tail", "braided mane", "hackled mane", "long tail",
            "bristle crest", "crested spine", "armoured tail", "leafy crown", "finned tail",
            "ridged tail", "matted hair tangle", "heavy brow ridge", "braided beard",
            "heavy chain belt", "long hooked nose", "whip tail", "long braided beard",
            "tall pointed cap", "barbed tail", "braided horse tail", "tufted tail",
            "tattered cape", "winged helm", "hooded mantle", "feathered hat",
            "flowing cape", "silver circlet", "horned helm", "braided beard clasp", "spiked collar",
            "fur mantle", "streaming tail", "iron crown", "plumed helm crest", "tattered surcoat",
            "spinning gear crest", "carved laurel crown", "draped stone cloak", "drawbridge",
            "curtain wall", "domed roof", "colonnade", "capstone lintel", "turf roof",
            "lantern gallery", "carved figurehead", "rudder fin", "canvas canopy", "spiked tail",
            "dorsal spine", "neck frill", "dorsal fin", "fin crest", "jewelled finial",
            "bird-shaped handle", "leafy hair tendril", "moss-grown shoulder",
        )),
        ("a matched pair", (
            "jewelled arm band",
            "curved horn", "swept-back horn", "leathery wing", "tattered wing", "cheek spike",
            "whisker barbel", "branching antler", "feathered wing", "bat wing", "broad wing",
            "taloned foreleg", "webbed hoof", "clawed forepaw", "curved tusk", "hooked pedipalp",
            "webbed foreleg", "broad flipper", "long tusk", "pointed ear", "jutting tusk",
            "iron arm band", "large pointed ear", "short horn", "dragonfly wing",
            "feathery antenna", "moth wing", "curling ram horn", "bull horn", "feathered arm",
            "fin-edged ear", "webbed hand", "twig antler", "fur-trimmed pauldron", "steel gauntlet",
            "leather bracer", "leaf-shaped pauldron", "bone pauldron", "rusted pauldron",
            "boulder fist", "jagged stone shoulder", "carved shoulder plate", "piston arm",
            "stone wing", "curled horn", "canvas wing", "taloned foot", "feathered fetlock",
        )),
        ("a small set", (
            "banner pole",
            "iron-rimmed wheel",
            "hanging chain", "round tower", "square turret", "carved stone pinnacle",
            "slender spire",
            "floating stone ring", "open balcony", "stone chimney", "square sail",
            "lateen sail", "carved claw", "fallen outlier stone", "lattice sail",
            "dangling chain", "spectral chain", "trailing tatter",
        )),
        ("a limb set", (
            "long leg", "branch arm", "root leg", "sucker-lined tentacle", "long hooked tentacle",
            "trailing tendril", "whirling arm", "long oar",
        )),
        ("a crown", ("serpent-headed neck", "hissing viper")),
    ),
    "emitters": _cardinality(
        ("a lone part", (
            "ember-hot throat", "luminous horn", "star-flecked mane",
            "crackling spell orb", "luminous core", "white-hot core", "spectral flame",
            "enchanted gem core", "enchanted beacon", "smouldering brand",
        )),
        ("a matched pair", (
            "smouldering nostril", "luminous eye", "ember eye", "cold luminous eye",
            "ember eye socket", "smouldering horn tip",
        )),
        ("a small set", (
            "hanging lantern",
            "enchanted gem", "luminous crystal", "stern lantern", "luminous blossom",
            "smouldering paw", "ember tail feather",
        )),
        ("a body row", (
            "luminous gill slit",
            "molten scale seam", "luminous spot", "faint luminous marking", "burning plume",
            "crackling feather", "luminous runic tattoo", "luminous wing vein", "drifting mote",
            "crackling spark", "molten crack",
        )),
        ("an array", ("luminous rune tracery", "luminous rune seam", "lantern-hung window")),
    ),
    "armament": _cardinality(
        ("a hand weapon", (
            "rune-etched greatsword", "great stone maul", "iron-capped battering ram",
            "longsword", "spear", "tree-trunk club", "iron-banded war maul", "great throwing stone",
            "stone-headed axe", "rusted cleaver", "notched short blade", "crude spear", "sling",
            "thorn spear", "tiny bow", "barbed pitchfork", "longbow", "hunting spear",
            "curved sword", "double-bladed axe", "iron-bound club", "coral trident", "bone spear",
            "war hammer", "quarterstaff", "battle axe", "crossbow", "flanged mace", "rapier",
            "kite shield", "gnarled staff", "flail", "rusted longsword", "notched axe",
            "slender curved blade", "heavy cleaver",
            "cracked shield", "reaping scythe", "bone staff", "halberd", "barbed tail spike",
            "crushing beak", "tearing beak", "goring tusk", "boarding ram",
        )),
        ("a paired arm", (
            "scythed wheel hub",
            "raking claw", "curved fang", "iron-shod hoof", "hooked talon", "venomous fang",
            "rusty dagger", "dagger",
        )),
        ("a small set", ("ballista", "trebuchet", "mounted crossbow", "bronze ballista")),
    ),
    "sensors": _cardinality(
        ("a lone part", ("single great eye", "looking glass", "crow's nest", "heat-sensing pit")),
        ("a matched pair", (
            "keen eye", "slit-pupiled eye", "hooded eye", "large dark eye", "golden eye",
            "small sunken eye", "bloodshot eye", "beady eye", "large yellow eye",
            "unblinking serpent eye", "scarred eye", "dark eye socket", "pinpoint luminous eye",
            "gem-set eye", "carved stone eye", "dark heavy-lidded eye",
        )),
        ("a limb set", ("many-faceted eye",)),
    ),
}

#: Count pools per group: ``GenrePack`` expands ``value_cardinality`` into the
#: count fields' groups, so only the control fields are declared here.
POOL_GROUPS: dict[str, dict[str, tuple[str, ...]]] = {
    "subkind": SUBKIND_GROUPS,
    "environment": ENVIRONMENT_BANDS,
}

# ---------------------------------------------------------------------------
# Situations -- authored in buckets
# ---------------------------------------------------------------------------
#
# Every value opens with a gerund, is legible in one still frame, and needs no
# actor the scene has not described beyond a small plural one. A bucket is one
# tuple whose values share a tier, a filter tag, the place they need, the stance
# they take and whether a dormant or sleeping thing can be doing them; the
# registry ``_BUCKETS`` below derives ``SITUATION_TIERS``, the tags, the needs,
# the stances and the two liveness lists from it. Pools concatenate buckets.

# --- dragon ---
_S_DRAGON_EV_WAR = (
    "rearing up to strike", "lashing out with a snapping bite", "coiling to strike",
    "thrashing in fury", "raking the air with a clawed swipe", "snapping at a hurled spear",
)
_S_DRAGON_EV_BREATH = (
    "spewing a torrent of flame", "unleashing a gout of roaring fire",
)
_S_DRAGON_EV_AIR = (
    "shaking off a volley of arrows", "breathing a stream of crackling lightning",
)
#: Freezing breath where the place is cold; in a warm place it iced everything over.
_S_DRAGON_EV_COLD = ("exhaling a blast of freezing breath",)
_S_DRAGON_EV = ("roaring with its jaws flung wide", "rising to its full height")
_S_DRAGON_ACT = (
    "stretching its long neck", "sniffing the air with flared nostrils", "flicking a cloven tongue",
    "trailing a curl of smoke from its nostrils", "baring a row of long teeth",
    "staring down at something far below", "swinging its head slowly from side to side",
    "shifting its great weight",
)
_S_DRAGON_IDLE = ("resting with its head lowered", "blinking slowly", "watching with narrowed eyes")
_S_DRAGON_CALM = ("guarding a clutch of eggs", "grooming its scales with a long tongue")
_S_WINGED_EV = ("unfurling its wings to their full span", "sweeping its tail in a wide arc")
_S_WINGED_EV_SKY = (
    "beating its wings to climb into the air", "banking hard between two peaks",
)
_S_WINGED_EV_SKY_WAR = ("diving with its wings folded back",)
_S_WINGED_ACT_SKY = ("circling overhead on broad wings",)
_S_WINGED_EV_LAND = ("landing hard in a spray of earth",)
_S_WINGED_EV_LAND_WAR = ("snatching a bleating goat from a hillside",)
_S_WINGED_ACT = ("folding its wings along its flanks",)
_S_WINGED_IDLE_CRAG = ("perched on a jagged crag",)
_S_WINGED_EV_WALLS = ("tearing the roof from a stone tower", "raking a castle rampart with its claws")
_S_WYRM_EV_GROUND = ("burrowing up through broken earth", "rising out of a deep crevasse")
_S_WYRM_EV_GROUND_WAR = ("crushing a wagon in its coils",)
_S_WYRM_ACT_GROUND = ("slithering across the ground in wide loops", "wrapping its coils around a boulder")
_S_WYRM_ACT_WALLS = ("coiling around a toppled pillar",)
_S_SEA_EV_SHORE = ("surging up out of the waves", "breaking the surface in a spray of foam")
_S_SEA_EV_SHORE_WAR = ("crushing a longship in its coils",)
_S_SEA_ACT_SHORE = ("circling just below the surface",)
_S_SEA_ACT_DEEP = ("gliding through the depths", "sliding past a sunken column")
_S_SEA_EV_DEEP = ("rising from a bed of kelp",)
_S_SEA_IDLE_DEEP = ("coiling among the rocks of the seabed",)
_S_HYDRA_EV_WAR = ("striking with several heads at once", "lunging with its longest neck",
                   "tangling its necks in fury")
_S_HYDRA_ACT = ("hissing from every head",)
_S_HYDRA_ACT_SHORE = ("wading through the shallows",)
_S_HYDRA_EV_SHORE = ("rising from a stagnant pool",)

# --- beasts, giants and anything that can be petrified or put to sleep ---
_S_STONE_DORMANT = (
    "standing locked mid-roar", "streaked with lichen and weather",
    "standing with a cracked stony flank", "crumbling at one edge",
)
_S_STONE_DORMANT_LIFE = ("wreathed in creeping ivy", "sprouting a young tree from one cracked flank")
_S_STONE_DORMANT_DEEP = ("crusted with sea growth on the seabed",)
_S_SLEEP = (
    "sleeping curled in a loose heap", "sleeping with one eye half open",
    "dozing with its eyes shut",
)
_S_SLEEP_DRAGON = ("dozing with a curl of smoke above its nostrils", "sleeping on a mound of spilled coins")
_S_SLEEP_LIFE = ("snoring beneath a drift of fallen leaves",)

# --- mythic beast ---
_S_BEAST_EV_WAR = (
    "charging headlong", "rearing up in fury", "lunging with a savage snarl",
    "turning at bay with its hackles raised",
)
_S_BEAST_EV_WAR_LIFE = ("thrashing through tangled undergrowth",)
_S_BEAST_EV_AIR_WAR = ("shaking off a volley of arrows",)
_S_BEAST_EV = ("bolting in sudden alarm", "bellowing a warning")
_S_BEAST_EV_AIR = ("leaping clear over a fallen log",)
_S_BEAST_ACT = (
    "standing alert with its head raised", "shaking its head", "stalking slowly forward",
    "sniffing the air", "circling warily", "turning to look back", "freezing mid-step",
    "limping from an old wound", "scenting something on the wind", "baring its teeth in warning",
    "turning in a slow circle",
)
_S_BEAST_IDLE = ("resting with its eyes half closed", "watching with unblinking eyes")
_S_BEAST_CALM_LIFE = ("grazing quietly",)
_S_BEAST_CALM_SHORE = ("drinking from a still pool",)
_S_HOOF_EV_GROUND = ("galloping across open ground",)
_S_HOOF_EV = ("rearing high on its hind legs",)
_S_HOOF_ACT_GROUND = ("striking the ground with a hoof",)
_S_WINGBEAST_EV_SKY = ("taking wing in a burst of feathers",)
_S_WINGBEAST_EV_SKY_WAR = ("diving on prey with talons spread",)
_S_WINGBEAST_ACT_SKY = ("soaring on outstretched wings",)
_S_WINGBEAST_EV_LAND = ("landing on a high crag",)
_S_WINGBEAST_IDLE = ("preening a feathered wing",)
_S_CHIMERA_ACT = ("lashing its tail", "pacing back and forth")
_S_CHIMERA_EV_WAR = ("crouching to spring",)
_S_GREAT_ACT_GROUND = ("tearing at a fallen log", "digging into the ground with its claws")
_S_GREAT_EV_LIFE = ("crashing through thick undergrowth",)
_S_GREAT_ACT = ("raising its hackles",)
_S_SEABEAST_EV_DEEP = ("rising from the depths",)
_S_SEABEAST_ACT_DEEP = ("gliding along the seabed", "trailing a cloud of silt")
_S_SEABEAST_EV_SHORE = ("surfacing beside a rocky shore",)
_S_SEABEAST_EV_SHORE_WAR = ("dragging a fishing boat beneath the waves",)

# --- giant-kin ---
_S_GIANT_EV_WAR = (
    "swinging a massive weapon in a wide arc", "grabbing for a fleeing adventurer", "hurling a great stone",
    "smashing a wooden cart to splinters", "roaring a challenge", "stamping forward in a rage",
)
_S_GIANT_EV_AIR_WAR = ("shrugging off a volley of arrows",)
_S_GIANT_EV = ("heaving a fallen log aside", "tripping over its own feet")
_S_GIANT_ACT = (
    "scratching its head in slow confusion", "gnawing on a huge bone", "sniffing the air",
    "squinting down at something small", "hefting a great stone onto one shoulder",
    "counting stolen coins on thick fingers", "picking its teeth with a splinter",
    "bellowing with laughter", "stirring a huge iron cauldron",
)
_S_GIANT_IDLE = ("sitting slumped against a rock", "resting its chin on one fist")
_S_GIANT_EV_LIFE = ("tearing a sapling out by the roots",)
_S_GIANT_ACT_SHORE = ("wading knee-deep into a river",)
_S_GIANT_ACT_WALLS = ("ducking beneath a low archway",)
_S_GIANT_ACT_COLD = ("brushing snow from its shoulders",)

# --- small folk ---
_S_SMALL_EV_WAR = (
    "springing an ambush", "hurling a rusty dagger", "slashing wildly with a short blade",
    "shrieking a war cry",
)
_S_SMALL_EV = ("fleeing with a stolen trinket", "scrambling away in panic", "tumbling head over heels",
              "diving for cover")
_S_SMALL_ACT = (
    "counting stolen coins", "sharpening a crooked blade", "juggling three pebbles",
    "sniffing a strange root", "grinning with too many teeth",
    "tinkering with a tiny contraption", "stirring a bubbling potion", "peering out from a hiding place",
    "tying a clumsy knot", "rummaging through a sack of loot",
)
_S_SMALL_IDLE = ("sitting cross-legged on a stone", "yawning hugely")
_S_SMALL_EV2 = (
    "tumbling out of a toppled barrel", "setting off its own clumsy trap", "bursting out of a hollow log",
    "leaping onto a traveller's pack",
)
_S_SMALL_ACT2 = (
    "sneaking along with a stolen chicken", "drawing crude pictures in the dirt",
    "fitting a stolen ring onto a finger", "arguing with its own reflection",
)
_S_SMALL_ACT_LIFE = ("hiding behind a giant mushroom", "whispering into a knothole")
_S_SMALL_ACT_WALLS = ("picking a lock", "peering around a corner")
_S_FEY_ACT_AIR = ("hovering on buzzing wings",)
_S_FEY_EV_AIR = ("darting away in a zigzag",)
_S_FEY_CALM = ("sprinkling a trail of sparkling dust",)

# --- hybrid folk ---
_S_HYBRID_EV_WAR = (
    "brandishing a weapon high", "charging with a lowered weapon", "lunging forward with a snarl",
    "shielding their face from a blow",
)
_S_HYBRID_EV = ("recoiling in alarm", "leaping back into cover", "spinning to face a sudden threat")
_S_HYBRID_ACT = (
    "turning to face an intruder", "standing guard with folded arms", "calling out a warning",
    "tracing a pattern in the air with one hand", "glaring with narrowed eyes",
    "raising a hand in warning", "sharpening a blade", "whispering a spell",
)
_S_HYBRID_CALM = (
    "offering a gift with open hands", "laughing with their head thrown back",
    "weaving a garland", "bowing low in greeting",
)
_S_FAUN_CALM = ("playing a haunting tune on a set of panpipes",)
_S_HYBRID_IDLE = ("resting with their eyes closed", "sitting on a mossy stone lost in thought")
_S_HYBRID_EV2 = ("vaulting over a fallen log", "snatching a thrown dagger from the air")
_S_HYBRID_EV2_WAR = ("rising from a crouch to strike", "shouting a war cry")
_S_HYBRID_ACT2 = ("braiding flowers into their hair", "carving a small wooden totem",
                  "tracing the stars with an outstretched finger")
_S_GORGON_EV_WAR = ("turning a charging warrior to stone with a glance",)
_S_MINOTAUR_EV_WAR = ("charging with horns lowered",)
_S_NAGA_EV = ("rising up on coiled tail",)
_S_CENTAUR_EV_GROUND = ("galloping across a meadow",)
_S_SEAFOLK_EV_SHORE = ("surfacing with a flick of the tail",)
_S_SEAFOLK_ACT_DEEP = ("gliding through a kelp forest",)
_S_HARPY_EV_SKY_WAR = ("swooping down with talons outstretched",)
_S_SELKIE_ACT_SHORE = ("shedding a sealskin at the water's edge",)
_S_DRYAD_EV_LIFE = ("stepping out from the bark of an oak",)

# --- folk ---
_S_FOLK_EV_WAR = (
    "drawing a weapon with a flourish", "loosing an arrow at full draw", "parrying a heavy blow",
    "charging forward with a battle cry", "diving into a forward roll", "casting a crackling spell",
    "rallying defenders with a raised blade", "leaping into a desperate lunge",
)
_S_FOLK_EV_FIRE = ("diving aside from a blast of flame",)
_S_FOLK_EV = ("leaping across a gap", "catching a thrown satchel", "stumbling back in shock",
             "unleashing a burst of arcane power")
_S_FOLK_ACT = (
    "studying a weathered map", "sharpening a blade on a whetstone", "stringing a longbow",
    "counting coins into a pouch", "whispering an incantation", "mixing a potion in a glass flask",
    "bandaging a wounded arm", "scanning the horizon with a spyglass", "leading a horse by the reins",
    "poring over an ancient tome", "shouldering a heavy pack", "testing the edge of a blade",
)
_S_FOLK_CALM = ("strumming a lute", "kneeling in prayer", "sharing a laugh with a companion")
_S_FOLK_IDLE = ("pausing to catch their breath", "resting with their arms folded")
_S_FOLK_EV_FIRE_CAMP = ("stamping out a campfire",)
_S_FOLK_ACT_GROUND = ("tracking footprints in the mud", "planting a banner in the earth")
_S_FOLK_ACT_WALLS = ("vaulting over a low wall", "sitting on a stone stair")
_S_FOLK_IDLE_LIFE = ("resting against a tree",)
_S_DWARF_ACT = ("hefting a heavy weapon onto one shoulder", "hammering at a rock face")
_S_ELF_ACT_LIFE = ("loosing arrows from a high branch",)
_S_ORC_EV_WAR = ("beating a war drum",)
_S_HALFLING_ACT = ("tiptoeing past a sleeping hound",)
_S_SMITH_ACT = ("hammering a red-hot blade on an anvil", "quenching a blade in a hissing trough")
_S_BARD_CALM = ("singing to a gathered crowd",)
_S_DRUID_CALM_LIFE = ("coaxing vines from a withered stump",)
_S_NECRO_EV_WAR = ("raising skeletons from the earth",)
_S_HERBALIST_CALM_LIFE = ("gathering herbs into a basket",)

# --- spirit or elemental ---
_S_SPIRIT_EV = (
    "swelling to twice its size", "rising into a towering column", "spinning into a howling vortex",
    "twisting into a tight spiral", "reforming from scattered fragments",
    "seeping through a narrow crack", "bursting apart and reforming", "flaring up in a sudden surge",
)
_S_SPIRIT_EV_WAR = (
    "lashing out at an intruder", "crashing down in a spray of fragments",
    "gathering itself before a strike", "raging in a tight whirl",
)
_S_SPIRIT_ACT = (
    "drifting in a slow spiral", "flickering in and out of sight", "trailing sparks and motes",
    "circling an intruder", "shrinking to a faint flicker", "pulsing slowly", "swirling around a fallen banner",
    "stretching into a thin ribbon", "curling around a toppled statue", "rippling like disturbed water",
)
_S_SPIRIT_IDLE = ("hanging motionless in the air",)
_S_SPIRIT_EV2 = (
    "erupting in a sudden flare", "shattering a toppled statue with a crack of force",
    "drawing loose stones into its body", "lashing a nearby banner to shreds",
)
_S_SPIRIT_ACT2 = (
    "sending ripples through the air around it", "coiling around a toppled column",
    "resting in a slow swirl",
)
_S_SPIRIT_EV_LIFE = ("whipping up a spiral of leaves",)
_S_SPIRIT_ACT_LIFE = ("parting a curtain of hanging moss",)
_S_SPIRIT_ACT_SHORE = ("hovering over a still pool",)
_S_SPIRIT_ACT_GROUND = ("hovering just above the ground",)

# --- undead ---
_S_UNDEAD_EV_WAR = (
    "raising a rusted weapon high", "lurching forward with grasping hands",
    "swinging its weapon in a wide arc",
)
#: A barricade that is not in the frame was drawn as a tombstone being hacked at.
_S_UNDEAD_EV_WAR_WALLS = ("hacking at a barricade",)
_S_UNDEAD_EV = ("gaping its jaw wide", "shuddering as it rises", "flickering between two places at once")
_S_UNDEAD_ACT = (
    "dragging a rusted chain", "gathering a swirl of dust", "standing sentinel",
    "clutching a tarnished locket", "tilting its head at a sound", "straightening a rusted helm",
    "trailing tattered burial cloth", "weeping with its face in its hands",
    "reaching for a guttering candle",
)
_S_BONES_EV = ("collapsing into a heap of bones and rising again", "turning its skull with a jerk")
_S_BONES_ACT = ("pointing a bony finger", "shuffling in a slow circle")
_S_UNDEAD_EV_GROUND = ("rising from a shallow grave",)
_S_UNDEAD_EV_WALLS = ("clawing out of a stone coffin", "reaching through iron bars")
_S_UNDEAD_ACT_WALLS = ("kneeling before a toppled throne",)
_S_WALKDEAD_EV = ("shambling forward with arms outstretched", "tearing loose from a tangle of roots")
_S_UNDEAD_ACT2 = ("raising a tarnished crown in salute", "brushing old dust from its shoulders")
_S_RESTLESS_EV = ("wailing with its mouth stretched wide", "reaching out with translucent hands",
                  "fading into a curl of vapour")
_S_RESTLESS_ACT_WALLS = ("drifting through a stone wall",)
_S_UNDEAD_DORMANT = ("resting beneath a layer of dust",)
_S_BONES_DORMANT = ("lying in a heap of bones",)
_S_UNDEAD_DORMANT_WALLS = ("lying still in an open sarcophagus", "standing motionless in an alcove")

# --- construct ---
_S_CONSTRUCT_EV_WAR = (
    "smashing a stone fist down", "sweeping a heavy arm in a wide arc",
    "cracking under a heavy blow", "shrugging off a hail of arrows",
)
_S_CONSTRUCT_EV = (
    "marching forward in heavy steps", "raising both fists high", "shedding a spray of rock chips",
    "grinding to a halt mid-stride", "reassembling from scattered pieces",
)
_S_CONSTRUCT_ACT = (
    "turning its head in slow jerks", "kneeling to lift a fallen stone", "pointing the way with an outstretched arm",
    "carrying a heavy stone block", "flexing stiff fingers", "standing guard", "stepping over a fallen column",
    "brushing dust from its shoulders", "shifting its weight with a grinding lurch",
    "tilting its head to study an intruder",
)
_S_CONSTRUCT_IDLE = ("standing sentinel on a plinth", "kneeling in a posture of prayer")
_S_CONSTRUCT_EV2 = ("crumbling a stone block in its grip", "flaring into motion with a surge of runes")
_S_CONSTRUCT_EV2_WAR = ("punching through a wooden barricade",)  # needs built walls
_S_CONSTRUCT_ACT2 = ("sweeping rubble aside with one arm", "holding a lantern aloft")
_S_CONSTRUCT_EV_WALLS = ("stepping out of a wall niche", "stepping through a shattered doorway")
_S_CONSTRUCT_ACT_WALLS = ("patrolling a long corridor",)
_S_GARGOYLE_EV_SKY = ("launching from a rooftop",)
_S_CONSTRUCT_DORMANT = ("standing motionless under a coat of dust", "half-buried in rubble")
_S_CONSTRUCT_DORMANT_LIFE = ("covered in climbing ivy",)

# --- structure ---
_S_STRUCTURE_EV = (
    "weathering a lashing storm", "being struck by a fork of lightning", "standing firm in a driving rainstorm",
)
_S_STRUCTURE_ACT = (
    "being repaired under wooden scaffolding", "being decked out with festival garlands",
    "flying a long prayer pennant", "welcoming a procession at its entrance",
    "drawing a trickle of travellers", "sheltering a flock of sheep in its lee",
)
_S_STRUCTURE_IDLE = ("standing tall against the sky", "standing firm in a stiff wind")
_S_STRUCTURE_DORMANT = ("crumbling at one corner", "shedding stones into the grass", "standing roofless and silent")
_S_STRUCTURE_DORMANT_LIFE = ("half-swallowed by the forest",)
_S_STRUCTURE_IDLE_CRAG = ("perched on a high crag",)
_S_STRUCTURE_IDLE_SHORE = ("reflected in a still lake",)
_S_FORT_EV = ("raising its drawbridge", "throwing open its gates", "sending up a signal fire")
_S_FORT_EV_WAR = (
    "lowering its portcullis with a crash", "bristling with archers along its battlements",
    "holding firm against a siege ladder assault",
)
_S_FORT_ACT = ("flying banners from every tower", "hosting a bustling market at its foot")
_S_FORT_IDLE = ("towering over a cluster of cottages", "rising above a sea of rooftops")
_S_SACRED_EV = (
    "raising the great banner of its order", "trembling as its sealed crypt grinds open", "blazing with a column of holy fire",
)
_S_SACRED_ACT = (
    "housing a line of patient pilgrims", "gathering a crowd of kneeling worshippers",
    "trailing incense smoke from its roof",
)
_S_ARCANE_EV = (
    "crackling with arcs of stray magic", "venting a plume of coloured smoke from its peak",
    "drawing a storm into a spiral above it",
)
_S_ARCANE_EV_WAR = ("hurling a bolt of lightning from its peak",)
_S_ARCANE_ACT = ("spinning a ring of floating stones around its peak", "throbbing with slow surges of power")
_S_DWELLING_EV = (
    "catching a sudden gust across its roof", "sheltering a crowd from a sudden downpour",
    "shedding loose shingles in a squall",
)
_S_DWELLING_ACT = ("trailing smoke from its chimneys", "drying a line of washing in the breeze",
                   "hanging lanterns along its eaves")
_S_WINDMILL_ACT = ("turning its sails in a steady wind",)
_S_LIGHTHOUSE_ACT_SHORE = ("sweeping a lantern beam across the waves",)
_S_CITADEL_ACT_SKY = ("drifting slowly among the clouds",)
_S_CITADEL_EV_SKY = ("trailing waterfalls from its floating rock",)

# --- vessel ---
_S_VESSEL_EV = (
    "ploughing ahead at full speed", "turning sharply to avoid a collision",
    "shedding cargo as it lurches", "lurching onto one side", "swaying under a sudden gust",
    "shuddering to a sudden stop",
)
_S_VESSEL_EV_WAR = ("bristling with armed defenders", "taking a volley of flaming arrows",
                    "breaking apart under a heavy blow")
_S_VESSEL_ACT = (
    "flying a long pennant", "riding low under a heavy load", "carrying a crowd of cheering passengers",
    "being loaded by a line of porters", "flying the colours of a distant kingdom", "trailing a long banner",
    "dropping a rope ladder over the side", "packed with sacks and crates",
)
_S_VESSEL_IDLE = ("gleaming with fresh gilding",)
_S_SHIP_EV_SHORE = (
    "cutting through heavy seas under full sail", "tacking hard into the wind",
    "running before a storm", "rowing hard with every oar", "listing heavily with a torn sail",
)
_S_SHIP_EV_SHORE_WAR = ("being boarded by pirates", "loosing a ballista at a pursuing ship")
_S_SHIP_ACT_SHORE = ("lowering a boat over the side", "gliding into a sheltered cove")
_S_SHIP_IDLE_DOCK = ("riding at anchor in a sheltered harbour",)
_S_AIRSHIP_EV_SKY = ("rising through the clouds", "fighting a buffeting wind")
_S_AIRSHIP_ACT_SKY = ("gliding low over the treetops", "dropping ballast in a stream of sand")
_S_CART_ACT_GROUND = ("rumbling along a rutted road", "rolling to a stop at a crossroads")
_S_CART_EV_GROUND = ("bouncing over rough ground", "stuck axle-deep in mud")
_S_CART_EV_GROUND_WAR = ("charging headlong across a battlefield",)
_S_CART_ACT_WALLS = ("rolling through a city gate",)
_S_CART_ACT_FLOOR = ("rolling across worn cobbles",)
_S_CART_IDLE_FLOOR = ("waiting beside a busy stall",)
_S_VESSEL_DORMANT = ("standing abandoned with its paint peeling",)
_S_VESSEL_DORMANT_SHORE = ("lying beached on its side", "rotting in the shallows")
_S_VESSEL_DORMANT_LIFE = ("overgrown by creeping vines",)
_S_VESSEL_DORMANT_GROUND = ("lying broken on a hillside",)

# --- artifact ---
_S_ARTIFACT_EV = (
    "cracking open along a seam", "drawing loose objects toward itself", "throwing off a shower of sparks",
    "flaring as someone reaches for it", "calling a swirl of embers around itself",
)
#: Rime only where the place is cold: in a forest it was drawn as ice on everything.
_S_ARTIFACT_EV_COLD = ("coating everything near it in rime",)
_S_ARTIFACT_ACT_COLD = ("trailing a thin ribbon of rime",)
_S_MONUMENT_ACT = (
    "humming as its carvings wake one by one", "drawing a slow spiral of dust around its base",
    "pulsing with slow surges of power", "wreathed in drifting sparks",
)
_S_MONUMENT_IDLE = ("standing silent in a ring of trampled grass", "sitting among withered offerings")
_S_ARTIFACT_EV_WAR = ("unleashing a burst of raw power", "hurling back a would-be thief")
_S_ARTIFACT_ACT = (
    "floating just above its resting place", "pulsing with slow surges of power",
    "lifting dust into a slow spiral", "spinning slowly in the air", "wreathed in drifting sparks",
    "whispering to anyone who comes near", "humming as its gems shift colour",
)
_S_ARTIFACT_IDLE = ("lying wrapped in a moth-eaten cloth", "sitting among withered offerings",
                    "gathering dust on a forgotten shelf")
_S_ARTIFACT_EV2 = (
    "splitting the air with a thin crack of force", "raising a ring of floating stones around itself",
    "pulling a thread of lightning down from above", "shifting its gems into a new pattern",
)
_S_ARTIFACT_ACT2 = (
    "turning slowly on its pedestal", "drawing wisps of smoke into itself",
    "casting a slow-moving pattern of sparks",
)
_S_ARTIFACT_EV_GROUND = ("sinking slowly into the ground beneath it",)
_S_ARTIFACT_IDLE_WALLS = ("embedded in a stone altar",)
_S_ARTIFACT_EV_SHORE = ("rising from a pool of still water",)
_S_ARTIFACT_DORMANT = ("resting under a thick layer of dust", "lying forgotten among old bones",
                       "wrapped in cobwebs")


#: The registry. ``(values, tier, tag, needs, stances, life)``: tag is ``c``
#: conflict, ``p`` peaceful, ``n`` neutral; life is ``d`` for what a dormant,
#: petrified or ruined thing can do, ``s`` for what a sleeping one can, and
#: empty for everything alive and awake.
_A = frozenset()
_AIR = frozenset({"air"})
_GROUND = frozenset({"ground"})
_SKY = frozenset({"sky"})
_SHORE = frozenset({"shoreline"})
_DEEP = frozenset({"submerged"})
_WALLS = frozenset({"structure"})
_LIFE = frozenset({"life"})
_COLD = frozenset({"cold"})
_DOCK = frozenset({"dock"})
_FLY = frozenset({"flies"})
_SWIM = frozenset({"swims"})
_WALK = frozenset({"walks"})
_SLITHER = frozenset({"slithers"})
_SAIL = frozenset({"sails"})
_ROLL = frozenset({"rolls"})
_FLOAT = frozenset({"floats", "hovers", "flies"})

_BUCKETS = (
    (_S_DRAGON_EV_WAR, "event", "c", _A, _A, ""),
    (_S_DRAGON_EV_BREATH, "event", "c", _AIR, _A, ""),
    (_S_DRAGON_EV_AIR, "event", "c", _AIR, _A, ""),
    (_S_DRAGON_EV_COLD, "event", "c", _AIR | _COLD, _A, ""),
    (_S_DRAGON_EV, "event", "n", _A, _A, ""),
    (_S_DRAGON_ACT, "activity", "n", _A, _A, ""),
    (_S_DRAGON_IDLE, "idle", "n", _A, _A, ""),
    (_S_DRAGON_CALM, "activity", "p", _A, _A, ""),
    (_S_WINGED_EV, "event", "n", _AIR, _A, ""),
    (_S_WINGED_EV_SKY, "event", "n", _SKY, _FLY, ""),
    (_S_WINGED_EV_SKY_WAR, "event", "c", _SKY, _FLY, ""),
    (_S_WINGED_ACT_SKY, "activity", "n", _SKY, _FLY, ""),
    (_S_WINGED_EV_LAND, "event", "n", _GROUND | _SKY, _FLY, ""),
    (_S_WINGED_EV_LAND_WAR, "event", "c", _GROUND | _SKY, _FLY, ""),
    (_S_WINGED_ACT, "activity", "n", _A, _A, ""),
    (_S_WINGED_IDLE_CRAG, "idle", "n", _GROUND, _A, ""),
    (_S_WINGED_EV_WALLS, "event", "c", _WALLS | _SKY, _A, ""),
    (_S_WYRM_EV_GROUND, "event", "n", _GROUND, _SLITHER, ""),
    (_S_WYRM_EV_GROUND_WAR, "event", "c", _GROUND, _SLITHER, ""),
    (_S_WYRM_ACT_GROUND, "activity", "n", _GROUND, _SLITHER, ""),
    (_S_WYRM_ACT_WALLS, "activity", "n", _WALLS, _SLITHER, ""),
    (_S_SEA_EV_SHORE, "event", "n", _SHORE, _SWIM, ""),
    (_S_SEA_EV_SHORE_WAR, "event", "c", _SHORE, _SWIM, ""),
    (_S_SEA_ACT_SHORE, "activity", "n", _SHORE, _SWIM, ""),
    (_S_SEA_ACT_DEEP, "activity", "n", _DEEP, _SWIM, ""),
    (_S_SEA_EV_DEEP, "event", "n", _DEEP, _SWIM, ""),
    (_S_SEA_IDLE_DEEP, "idle", "n", _DEEP, _A, ""),
    (_S_HYDRA_EV_WAR, "event", "c", _A, _A, ""),
    (_S_HYDRA_ACT, "activity", "n", _A, _A, ""),
    (_S_HYDRA_ACT_SHORE, "activity", "n", _SHORE, _WALK, ""),
    (_S_HYDRA_EV_SHORE, "event", "n", _SHORE, _A, ""),
    (_S_STONE_DORMANT, "idle", "n", _A, _A, "d"),
    (_S_STONE_DORMANT_LIFE, "idle", "n", _LIFE, _A, "d"),
    (_S_STONE_DORMANT_DEEP, "idle", "n", _DEEP, _A, "d"),
    (_S_SLEEP, "idle", "n", _A, _A, "s"),
    (_S_SLEEP_DRAGON, "idle", "n", _A, _A, "s"),
    (_S_SLEEP_LIFE, "idle", "n", _LIFE, _A, "s"),
    (_S_BEAST_EV_WAR, "event", "c", _A, _A, ""),
    (_S_BEAST_EV_WAR_LIFE, "event", "c", _LIFE, _A, ""),
    (_S_BEAST_EV_AIR_WAR, "event", "c", _AIR, _A, ""),
    (_S_BEAST_EV, "event", "n", _A, _A, ""),
    (_S_BEAST_EV_AIR, "event", "n", _AIR, _A, ""),
    (_S_BEAST_ACT, "activity", "n", _A, _A, ""),
    (_S_BEAST_IDLE, "idle", "n", _A, _A, ""),
    (_S_BEAST_CALM_LIFE, "activity", "p", _LIFE, _A, ""),
    (_S_BEAST_CALM_SHORE, "activity", "p", _SHORE, _A, ""),
    (_S_HOOF_EV_GROUND, "event", "n", _GROUND, _WALK, ""),
    (_S_HOOF_EV, "event", "n", _AIR, _A, ""),
    (_S_HOOF_ACT_GROUND, "activity", "n", _GROUND, _A, ""),
    (_S_WINGBEAST_EV_SKY, "event", "n", _SKY, _FLY, ""),
    (_S_WINGBEAST_EV_SKY_WAR, "event", "c", _SKY, _FLY, ""),
    (_S_WINGBEAST_ACT_SKY, "activity", "n", _SKY, _FLY, ""),
    (_S_WINGBEAST_EV_LAND, "event", "n", _GROUND | _SKY, _FLY, ""),
    (_S_WINGBEAST_IDLE, "idle", "n", _A, _A, ""),
    (_S_CHIMERA_ACT, "activity", "n", _A, _A, ""),
    (_S_CHIMERA_EV_WAR, "event", "c", _A, _A, ""),
    (_S_GREAT_ACT_GROUND, "activity", "n", _GROUND, _A, ""),
    (_S_GREAT_EV_LIFE, "event", "n", _LIFE, _A, ""),
    (_S_GREAT_ACT, "activity", "n", _A, _A, ""),
    (_S_SEABEAST_EV_DEEP, "event", "n", _DEEP, _SWIM, ""),
    (_S_SEABEAST_ACT_DEEP, "activity", "n", _DEEP, _SWIM, ""),
    (_S_SEABEAST_EV_SHORE, "event", "n", _SHORE, _SWIM, ""),
    (_S_SEABEAST_EV_SHORE_WAR, "event", "c", _SHORE, _SWIM, ""),
    (_S_GIANT_EV_WAR, "event", "c", _A, _A, ""),
    (_S_GIANT_EV_AIR_WAR, "event", "c", _AIR, _A, ""),
    (_S_GIANT_EV, "event", "n", _A, _A, ""),
    (_S_GIANT_ACT, "activity", "n", _A, _A, ""),
    (_S_GIANT_IDLE, "idle", "n", _A, _A, ""),
    (_S_GIANT_EV_LIFE, "event", "n", _LIFE, _A, ""),
    (_S_GIANT_ACT_SHORE, "activity", "n", _SHORE, _WALK, ""),
    (_S_GIANT_ACT_WALLS, "activity", "n", _WALLS, _A, ""),
    (_S_GIANT_ACT_COLD, "activity", "n", _COLD, _A, ""),
    (_S_SMALL_EV_WAR, "event", "c", _A, _A, ""),
    (_S_SMALL_EV, "event", "n", _A, _A, ""),
    (_S_SMALL_ACT, "activity", "n", _A, _A, ""),
    (_S_SMALL_IDLE, "idle", "n", _A, _A, ""),
    (_S_SMALL_EV2, "event", "n", _A, _A, ""),
    (_S_SMALL_ACT2, "activity", "n", _A, _A, ""),
    (_S_SMALL_ACT_LIFE, "activity", "n", _LIFE, _A, ""),
    (_S_SMALL_ACT_WALLS, "activity", "n", _WALLS, _A, ""),
    (_S_FEY_ACT_AIR, "activity", "n", _AIR, _FLOAT, ""),
    (_S_FEY_EV_AIR, "event", "n", _AIR, _FLOAT, ""),
    (_S_FEY_CALM, "activity", "p", _A, _A, ""),
    (_S_HYBRID_EV_WAR, "event", "c", _A, _A, ""),
    (_S_HYBRID_EV, "event", "n", _A, _A, ""),
    (_S_HYBRID_ACT, "activity", "n", _A, _A, ""),
    (_S_HYBRID_CALM, "activity", "p", _A, _A, ""),
    (_S_FAUN_CALM, "activity", "p", _A, _A, ""),
    (_S_HYBRID_IDLE, "idle", "n", _A, _A, ""),
    (_S_HYBRID_EV2, "event", "n", _AIR, _A, ""),
    (_S_HYBRID_EV2_WAR, "event", "c", _A, _A, ""),
    (_S_HYBRID_ACT2, "activity", "p", _A, _A, ""),
    (_S_GORGON_EV_WAR, "event", "c", _A, _A, ""),
    (_S_MINOTAUR_EV_WAR, "event", "c", _A, _A, ""),
    (_S_NAGA_EV, "event", "n", _A, _A, ""),
    (_S_CENTAUR_EV_GROUND, "event", "n", _GROUND | _LIFE, _WALK, ""),
    (_S_SEAFOLK_EV_SHORE, "event", "n", _SHORE, _SWIM, ""),
    (_S_SEAFOLK_ACT_DEEP, "activity", "n", _DEEP, _SWIM, ""),
    (_S_HARPY_EV_SKY_WAR, "event", "c", _SKY, _FLY, ""),
    (_S_SELKIE_ACT_SHORE, "activity", "n", _SHORE, _A, ""),
    (_S_DRYAD_EV_LIFE, "event", "n", _LIFE, _A, ""),
    (_S_FOLK_EV_WAR, "event", "c", _A, _A, ""),
    (_S_FOLK_EV_FIRE, "event", "c", _AIR, _A, ""),
    (_S_FOLK_EV, "event", "n", _A, _A, ""),
    (_S_FOLK_ACT, "activity", "n", _A, _A, ""),
    (_S_FOLK_CALM, "activity", "p", _A, _A, ""),
    (_S_FOLK_IDLE, "idle", "n", _A, _A, ""),
    (_S_FOLK_EV_FIRE_CAMP, "event", "n", _GROUND | _AIR, _A, ""),
    (_S_FOLK_ACT_GROUND, "activity", "n", _GROUND, _A, ""),
    (_S_FOLK_ACT_WALLS, "activity", "n", _WALLS, _A, ""),
    (_S_FOLK_IDLE_LIFE, "idle", "n", _LIFE, _A, ""),
    (_S_DWARF_ACT, "activity", "n", _A, _A, ""),
    (_S_ELF_ACT_LIFE, "activity", "c", _LIFE, _A, ""),
    (_S_ORC_EV_WAR, "event", "c", _A, _A, ""),
    (_S_HALFLING_ACT, "activity", "n", _A, _A, ""),
    (_S_SMITH_ACT, "activity", "n", _AIR, _A, ""),
    (_S_BARD_CALM, "activity", "p", _A, _A, ""),
    (_S_DRUID_CALM_LIFE, "activity", "p", _LIFE, _A, ""),
    (_S_NECRO_EV_WAR, "event", "c", _GROUND, _A, ""),
    (_S_HERBALIST_CALM_LIFE, "activity", "p", _LIFE, _A, ""),
    (_S_SPIRIT_EV, "event", "n", _A, _A, ""),
    (_S_SPIRIT_EV_WAR, "event", "c", _A, _A, ""),
    (_S_SPIRIT_ACT, "activity", "n", _A, _A, ""),
    (_S_SPIRIT_IDLE, "idle", "n", _A, _FLOAT, ""),
    (_S_SPIRIT_ACT_GROUND, "activity", "n", _GROUND, _FLOAT, ""),
    (_S_SPIRIT_EV2, "event", "n", _A, _A, ""),
    (_S_SPIRIT_ACT2, "activity", "n", _A, _A, ""),
    (_S_SPIRIT_EV_LIFE, "event", "n", _LIFE, _A, ""),
    (_S_SPIRIT_ACT_LIFE, "activity", "n", _LIFE, _A, ""),
    (_S_SPIRIT_ACT_SHORE, "activity", "n", _SHORE, _FLOAT, ""),
    (_S_UNDEAD_EV_WAR, "event", "c", _A, _A, ""),
    (_S_UNDEAD_EV_WAR_WALLS, "event", "c", _WALLS, _A, ""),
    (_S_UNDEAD_EV, "event", "n", _A, _A, ""),
    (_S_UNDEAD_ACT, "activity", "n", _A, _A, ""),
    (_S_UNDEAD_EV_GROUND, "event", "n", _GROUND, _A, ""),
    (_S_BONES_EV, "event", "n", _A, _A, ""),
    (_S_BONES_ACT, "activity", "n", _A, _A, ""),
    (_S_BONES_DORMANT, "idle", "n", _A, _A, "d"),
    (_S_UNDEAD_EV_WALLS, "event", "n", _WALLS, _A, ""),
    (_S_UNDEAD_ACT_WALLS, "activity", "n", _WALLS, _A, ""),
    (_S_UNDEAD_ACT2, "activity", "n", _A, _A, ""),
    (_S_WALKDEAD_EV, "event", "c", _A, _WALK, ""),
    (_S_RESTLESS_EV, "event", "n", _A, _A, ""),
    (_S_RESTLESS_ACT_WALLS, "activity", "n", _WALLS, _FLOAT, ""),
    (_S_UNDEAD_DORMANT, "idle", "n", _A, _A, "d"),
    (_S_UNDEAD_DORMANT_WALLS, "idle", "n", _WALLS, _A, "d"),
    (_S_CONSTRUCT_EV_WAR, "event", "c", _A, _A, ""),
    (_S_CONSTRUCT_EV, "event", "n", _A, _A, ""),
    (_S_CONSTRUCT_ACT, "activity", "n", _A, _A, ""),
    (_S_CONSTRUCT_IDLE, "idle", "n", _A, _A, ""),
    (_S_CONSTRUCT_EV2, "event", "n", _A, _A, ""),
    (_S_CONSTRUCT_EV2_WAR, "event", "c", _WALLS, _A, ""),
    (_S_CONSTRUCT_ACT2, "activity", "n", _A, _A, ""),
    (_S_CONSTRUCT_EV_WALLS, "event", "n", _WALLS, _A, ""),
    (_S_CONSTRUCT_ACT_WALLS, "activity", "n", _WALLS, _A, ""),
    (_S_GARGOYLE_EV_SKY, "event", "n", _SKY | _WALLS, _FLY, ""),
    (_S_CONSTRUCT_DORMANT, "idle", "n", _A, _A, "d"),
    (_S_CONSTRUCT_DORMANT_LIFE, "idle", "n", _LIFE, _A, "d"),
    (_S_STRUCTURE_EV, "event", "n", _AIR, _A, ""),
    (_S_STRUCTURE_ACT, "activity", "p", _AIR, _A, ""),
    (_S_FORT_EV, "event", "n", _AIR, _A, ""),
    (_S_FORT_EV_WAR, "event", "c", _AIR, _A, ""),
    (_S_FORT_ACT, "activity", "n", _AIR, _A, ""),
    (_S_FORT_IDLE, "idle", "n", _AIR, _A, ""),
    (_S_SACRED_EV, "event", "n", _AIR, _A, ""),
    (_S_SACRED_ACT, "activity", "p", _AIR, _A, ""),
    (_S_ARCANE_EV, "event", "n", _AIR, _A, ""),
    (_S_ARCANE_EV_WAR, "event", "c", _AIR, _A, ""),
    (_S_ARCANE_ACT, "activity", "n", _AIR, _A, ""),
    (_S_DWELLING_EV, "event", "n", _AIR, _A, ""),
    (_S_DWELLING_ACT, "activity", "n", _AIR, _A, ""),
    (_S_WINDMILL_ACT, "activity", "n", _AIR, _A, ""),
    (_S_LIGHTHOUSE_ACT_SHORE, "activity", "n", _SHORE, _A, ""),
    (_S_STRUCTURE_IDLE, "idle", "n", _AIR, _A, ""),
    (_S_STRUCTURE_DORMANT, "idle", "n", _A, _A, "d"),
    (_S_STRUCTURE_DORMANT_LIFE, "idle", "n", _LIFE, _A, "d"),
    (_S_STRUCTURE_IDLE_CRAG, "idle", "n", _GROUND, _A, ""),
    (_S_STRUCTURE_IDLE_SHORE, "idle", "n", _SHORE, _A, ""),
    (_S_CITADEL_ACT_SKY, "activity", "n", _SKY, _A, ""),
    (_S_CITADEL_EV_SKY, "event", "n", _SKY, _A, ""),
    (_S_VESSEL_EV, "event", "n", _A, _A, ""),
    (_S_VESSEL_EV_WAR, "event", "c", _AIR, _A, ""),
    (_S_VESSEL_ACT, "activity", "n", _A, _A, ""),
    (_S_VESSEL_IDLE, "idle", "n", _A, _A, ""),
    (_S_SHIP_EV_SHORE, "event", "n", _SHORE, _SAIL, ""),
    (_S_SHIP_EV_SHORE_WAR, "event", "c", _SHORE, _SAIL, ""),
    (_S_SHIP_ACT_SHORE, "activity", "n", _SHORE, _SAIL, ""),
    (_S_SHIP_IDLE_DOCK, "idle", "n", _SHORE, _SAIL, ""),
    (_S_AIRSHIP_EV_SKY, "event", "n", _SKY, _FLY, ""),
    (_S_AIRSHIP_ACT_SKY, "activity", "n", _SKY, _FLY, ""),
    (_S_CART_ACT_GROUND, "activity", "n", _GROUND, _ROLL, ""),
    (_S_CART_EV_GROUND, "event", "n", _GROUND, _ROLL, ""),
    (_S_CART_EV_GROUND_WAR, "event", "c", _GROUND, _ROLL, ""),
    (_S_CART_ACT_WALLS, "activity", "n", _WALLS, _ROLL, ""),
    (_S_CART_ACT_FLOOR, "activity", "n", frozenset({"floor"}), _ROLL, ""),
    (_S_CART_IDLE_FLOOR, "idle", "n", frozenset({"floor"}), _A, ""),
    (_S_VESSEL_DORMANT, "idle", "n", _A, _A, "d"),
    (_S_VESSEL_DORMANT_SHORE, "idle", "n", _SHORE, _A, "d"),
    (_S_VESSEL_DORMANT_LIFE, "idle", "n", _LIFE, _A, "d"),
    (_S_VESSEL_DORMANT_GROUND, "idle", "n", _GROUND, _A, "d"),
    (_S_ARTIFACT_EV, "event", "n", _A, _A, ""),
    (_S_ARTIFACT_EV_WAR, "event", "c", _A, _A, ""),
    (_S_ARTIFACT_ACT, "activity", "n", _A, _A, ""),
    (_S_ARTIFACT_IDLE, "idle", "n", _A, _A, ""),
    (_S_ARTIFACT_EV2, "event", "n", _A, _A, ""),
    (_S_ARTIFACT_ACT2, "activity", "n", _A, _A, ""),
    (_S_ARTIFACT_EV_GROUND, "event", "n", _GROUND, _A, ""),
    (_S_ARTIFACT_IDLE_WALLS, "idle", "n", _WALLS, _A, ""),
    (_S_ARTIFACT_EV_SHORE, "event", "n", _SHORE, _A, ""),
    (_S_ARTIFACT_DORMANT, "idle", "n", _A, _A, "d"),
    (_S_ARTIFACT_EV_COLD, "event", "n", _COLD, _A, ""),
    (_S_ARTIFACT_ACT_COLD, "activity", "n", _COLD, _A, ""),
    (_S_MONUMENT_ACT, "activity", "n", _A, _A, ""),
    (_S_MONUMENT_IDLE, "idle", "n", _A, _A, ""),
)

# Shared compositions, as literal concatenations.
_S_DRAGON_CORE = (
    _S_DRAGON_EV_WAR + _S_DRAGON_EV_BREATH + _S_DRAGON_EV_AIR + _S_DRAGON_EV_COLD + _S_DRAGON_EV
    + _S_DRAGON_ACT
    + _S_DRAGON_IDLE + _S_DRAGON_CALM + _S_STONE_DORMANT + _S_STONE_DORMANT_LIFE + _S_SLEEP
    + _S_SLEEP_DRAGON + _S_SLEEP_LIFE
)
_S_BEAST_CORE = (
    _S_BEAST_EV_WAR + _S_BEAST_EV_WAR_LIFE + _S_BEAST_EV_AIR_WAR + _S_BEAST_EV + _S_BEAST_EV_AIR + _S_BEAST_ACT
    + _S_BEAST_IDLE + _S_BEAST_CALM_LIFE + _S_BEAST_CALM_SHORE + _S_STONE_DORMANT
    + _S_STONE_DORMANT_LIFE + _S_SLEEP + _S_SLEEP_LIFE
)
_S_GIANT_CORE = (
    _S_GIANT_EV_WAR + _S_GIANT_EV_AIR_WAR + _S_GIANT_EV + _S_GIANT_ACT + _S_GIANT_IDLE
    + _S_GIANT_EV_LIFE + _S_GIANT_ACT_SHORE + _S_GIANT_ACT_WALLS + _S_GIANT_ACT_COLD
    + _S_STONE_DORMANT + _S_STONE_DORMANT_LIFE + _S_SLEEP + _S_SLEEP_LIFE
)
_S_SMALL_CORE = (
    _S_SMALL_EV_WAR + _S_SMALL_EV + _S_SMALL_ACT + _S_SMALL_IDLE + _S_SMALL_ACT_LIFE
    + _S_SMALL_ACT_WALLS + _S_SMALL_EV2 + _S_SMALL_ACT2
)
_S_HYBRID_CORE = (
    _S_HYBRID_EV_WAR + _S_HYBRID_EV + _S_HYBRID_ACT + _S_HYBRID_CALM + _S_HYBRID_IDLE + _S_HYBRID_EV2
    + _S_HYBRID_EV2_WAR + _S_HYBRID_ACT2
)
_S_FOLK_CORE = (
    _S_FOLK_EV_WAR + _S_FOLK_EV_FIRE + _S_FOLK_EV + _S_FOLK_ACT + _S_FOLK_CALM + _S_FOLK_IDLE
    + _S_FOLK_EV_FIRE_CAMP + _S_FOLK_ACT_GROUND + _S_FOLK_ACT_WALLS + _S_FOLK_IDLE_LIFE
)
_S_UNDEAD_CORE = (
    _S_UNDEAD_EV_WAR + _S_UNDEAD_EV_WAR_WALLS + _S_UNDEAD_EV + _S_UNDEAD_ACT + _S_UNDEAD_EV_GROUND + _S_UNDEAD_EV_WALLS
    + _S_UNDEAD_ACT_WALLS + _S_UNDEAD_DORMANT + _S_UNDEAD_DORMANT_WALLS + _S_UNDEAD_ACT2
)
_S_CONSTRUCT_CORE = (
    _S_CONSTRUCT_EV_WAR + _S_CONSTRUCT_EV + _S_CONSTRUCT_ACT + _S_CONSTRUCT_IDLE + _S_CONSTRUCT_EV2
    + _S_CONSTRUCT_EV2_WAR + _S_CONSTRUCT_ACT2
    + _S_CONSTRUCT_EV_WALLS + _S_CONSTRUCT_ACT_WALLS + _S_CONSTRUCT_DORMANT
    + _S_CONSTRUCT_DORMANT_LIFE
)
_S_STRUCTURE_CORE = (
    _S_STRUCTURE_EV + _S_STRUCTURE_ACT + _S_STRUCTURE_IDLE
    + _S_STRUCTURE_DORMANT + _S_STRUCTURE_DORMANT_LIFE + _S_STRUCTURE_IDLE_CRAG
    + _S_STRUCTURE_IDLE_SHORE
)
_S_VESSEL_CORE = (
    _S_VESSEL_EV + _S_VESSEL_EV_WAR + _S_VESSEL_ACT + _S_VESSEL_IDLE + _S_VESSEL_DORMANT
    + _S_VESSEL_DORMANT_SHORE + _S_VESSEL_DORMANT_LIFE + _S_VESSEL_DORMANT_GROUND
)

SITUATION_POOLS: dict[str, tuple[str, ...]] = {
    #: The cross-genre fall-through: true of almost anything, so a foreign entity acts.
    POOL_DEFAULT_KEY: (
        "turning to look back", "standing alert with its head raised", "circling warily",
        "recoiling in alarm", "rising to its full height", "resting with its head lowered",
        "shaking off a volley of arrows", "charging headlong",
    ),
    "dragon": _S_DRAGON_CORE,
    "winged dragon": (
        _S_DRAGON_CORE + _S_WINGED_EV + _S_WINGED_EV_SKY + _S_WINGED_EV_SKY_WAR + _S_WINGED_ACT_SKY
        + _S_WINGED_EV_LAND + _S_WINGED_EV_LAND_WAR + _S_WINGED_ACT + _S_WINGED_IDLE_CRAG
        + _S_WINGED_EV_WALLS
    ),
    "serpent wyrm": (
        _S_DRAGON_CORE + _S_WYRM_EV_GROUND + _S_WYRM_EV_GROUND_WAR + _S_WYRM_ACT_GROUND
        + _S_WYRM_ACT_WALLS
    ),
    "sea wyrm": (
        _S_DRAGON_CORE + _S_SEA_EV_SHORE + _S_SEA_EV_SHORE_WAR + _S_SEA_ACT_SHORE + _S_SEA_ACT_DEEP
        + _S_SEA_EV_DEEP + _S_SEA_IDLE_DEEP + _S_STONE_DORMANT_DEEP
    ),
    "many-headed dragon": (
        _S_DRAGON_CORE + _S_HYDRA_EV_WAR + _S_HYDRA_ACT + _S_HYDRA_ACT_SHORE + _S_HYDRA_EV_SHORE
    ),
    "mythic beast": _S_BEAST_CORE,
    "hoofed beast": _S_BEAST_CORE + _S_HOOF_EV_GROUND + _S_HOOF_EV + _S_HOOF_ACT_GROUND,
    "winged beast": (
        _S_BEAST_CORE + _S_WINGBEAST_EV_SKY + _S_WINGBEAST_EV_SKY_WAR + _S_WINGBEAST_ACT_SKY
        + _S_WINGBEAST_EV_LAND + _S_WINGBEAST_IDLE
    ),
    "chimeric beast": _S_BEAST_CORE + _S_CHIMERA_ACT + _S_CHIMERA_EV_WAR,
    "great beast": _S_BEAST_CORE + _S_GREAT_ACT_GROUND + _S_GREAT_EV_LIFE + _S_GREAT_ACT,
    "sea beast": (
        _S_BEAST_CORE + _S_SEABEAST_EV_DEEP + _S_SEABEAST_ACT_DEEP + _S_SEABEAST_EV_SHORE
        + _S_SEABEAST_EV_SHORE_WAR + _S_STONE_DORMANT_DEEP
    ),
    "giant-kin": _S_GIANT_CORE,
    "small folk": _S_SMALL_CORE,
    "winged fey": _S_SMALL_CORE + _S_FEY_ACT_AIR + _S_FEY_EV_AIR + _S_FEY_CALM,
    "hybrid folk": _S_HYBRID_CORE,
    "gorgon": _S_HYBRID_CORE + _S_GORGON_EV_WAR + _S_NAGA_EV,
    "naga": _S_HYBRID_CORE + _S_NAGA_EV + _S_SEAFOLK_ACT_DEEP,
    "minotaur": _S_HYBRID_CORE + _S_MINOTAUR_EV_WAR,
    "satyr": _S_HYBRID_CORE + _S_FAUN_CALM,
    "faun": _S_HYBRID_CORE + _S_FAUN_CALM,
    "centaur": _S_HYBRID_CORE + _S_CENTAUR_EV_GROUND,
    "sea folk": _S_HYBRID_CORE + _S_SEAFOLK_EV_SHORE + _S_SEAFOLK_ACT_DEEP,
    "selkie": _S_HYBRID_CORE + _S_SEAFOLK_EV_SHORE + _S_SEAFOLK_ACT_DEEP + _S_SELKIE_ACT_SHORE,
    "winged folk": _S_HYBRID_CORE + _S_HARPY_EV_SKY_WAR,
    "tree folk": _S_HYBRID_CORE + _S_DRYAD_EV_LIFE,
    "folk": _S_FOLK_CORE,
    "dwarf": _S_FOLK_CORE + _S_DWARF_ACT,
    "elf": _S_FOLK_CORE + _S_ELF_ACT_LIFE,
    "orc": _S_FOLK_CORE + _S_ORC_EV_WAR,
    "halfling": _S_FOLK_CORE + _S_HALFLING_ACT,
    "blacksmith": _S_FOLK_CORE + _S_SMITH_ACT,
    "mountain dwarf smith": _S_FOLK_CORE + _S_DWARF_ACT + _S_SMITH_ACT,
    "bard": _S_FOLK_CORE + _S_BARD_CALM,
    "druid": _S_FOLK_CORE + _S_DRUID_CALM_LIFE,
    "necromancer": _S_FOLK_CORE + _S_NECRO_EV_WAR,
    "herbalist": _S_FOLK_CORE + _S_HERBALIST_CALM_LIFE,
    "spirit or elemental": (
        _S_SPIRIT_EV + _S_SPIRIT_EV_WAR + _S_SPIRIT_ACT + _S_SPIRIT_IDLE + _S_SPIRIT_ACT_GROUND
        + _S_SPIRIT_EV2 + _S_SPIRIT_ACT2 + _S_SPIRIT_EV_LIFE + _S_SPIRIT_ACT_LIFE + _S_SPIRIT_ACT_SHORE
    ),
    "undead": _S_UNDEAD_CORE + _S_BONES_EV + _S_BONES_ACT + _S_BONES_DORMANT,
    "walking dead": _S_UNDEAD_CORE + _S_WALKDEAD_EV + _S_BONES_EV + _S_BONES_ACT + _S_BONES_DORMANT,
    "restless spirit": _S_UNDEAD_CORE + _S_RESTLESS_EV + _S_RESTLESS_ACT_WALLS,
    "construct": _S_CONSTRUCT_CORE,
    "gargoyle": _S_CONSTRUCT_CORE + _S_GARGOYLE_EV_SKY,
    "structure": _S_STRUCTURE_CORE,
    "fortification": _S_STRUCTURE_CORE + _S_FORT_EV + _S_FORT_EV_WAR + _S_FORT_ACT + _S_FORT_IDLE,
    "sacred site": _S_STRUCTURE_CORE + _S_SACRED_EV + _S_SACRED_ACT,
    "arcane tower": _S_STRUCTURE_CORE + _S_ARCANE_EV + _S_ARCANE_EV_WAR + _S_ARCANE_ACT,
    "floating citadel": (
        _S_STRUCTURE_CORE + _S_ARCANE_EV + _S_ARCANE_EV_WAR + _S_ARCANE_ACT + _S_CITADEL_ACT_SKY
        + _S_CITADEL_EV_SKY
    ),
    "dwelling": _S_STRUCTURE_CORE + _S_DWELLING_EV + _S_DWELLING_ACT,
    "windmill": _S_STRUCTURE_CORE + _S_DWELLING_EV + _S_DWELLING_ACT + _S_WINDMILL_ACT,
    "lighthouse": _S_STRUCTURE_CORE + _S_DWELLING_EV + _S_DWELLING_ACT + _S_LIGHTHOUSE_ACT_SHORE,
    "vessel": _S_VESSEL_CORE,
    "sailing ship": (
        _S_VESSEL_CORE + _S_SHIP_EV_SHORE + _S_SHIP_EV_SHORE_WAR + _S_SHIP_ACT_SHORE + _S_SHIP_IDLE_DOCK
    ),
    "flying ship": _S_VESSEL_CORE + _S_AIRSHIP_EV_SKY + _S_AIRSHIP_ACT_SKY,
    "land vehicle": (
        _S_VESSEL_CORE + _S_CART_ACT_GROUND + _S_CART_EV_GROUND + _S_CART_EV_GROUND_WAR
        + _S_CART_ACT_WALLS + _S_CART_ACT_FLOOR + _S_CART_IDLE_FLOOR
    ),
    "artifact": (
        _S_ARTIFACT_EV + _S_ARTIFACT_EV_WAR + _S_ARTIFACT_ACT + _S_ARTIFACT_IDLE
        + _S_ARTIFACT_IDLE_WALLS + _S_ARTIFACT_EV_SHORE + _S_ARTIFACT_DORMANT + _S_ARTIFACT_EV2
        + _S_ARTIFACT_ACT2 + _S_ARTIFACT_EV_GROUND + _S_ARTIFACT_EV_COLD + _S_ARTIFACT_ACT_COLD
    ),
    "monument": (
        _S_ARTIFACT_EV + _S_ARTIFACT_EV_WAR + _S_ARTIFACT_EV2 + _S_ARTIFACT_EV_GROUND
        + _S_ARTIFACT_EV_COLD + _S_ARTIFACT_ACT_COLD + _S_MONUMENT_ACT + _S_MONUMENT_IDLE
        + _S_ARTIFACT_DORMANT
    ),
}

TIER_WEIGHTS: dict[str, float] = {"event": 3.0, "activity": 1.0, "idle": 0.25}


# ---------------------------------------------------------------------------
# Relations
# ---------------------------------------------------------------------------

RELATION_POOL: tuple[str, ...] = (
    "attacking", "hunting", "fleeing from", "facing", "watching", "ignoring", "guarding",
    "riding", "creeping toward", "looming over", "towering over", "bowing before", "duelling",
    "protecting", "stalking", "confronting", "parleying with", "following", "hiding from",
    "leading", "taming", "healing", "challenging", "charging at", "approaching",
)
RELATION_POSITION_POOL: tuple[str, ...] = (
    "from behind", "from above", "from below", "in the background", "in the foreground",
    "at a distance", "directly ahead", "alongside", "to one side", "close alongside",
    "in the middle distance",
)

# ---------------------------------------------------------------------------
# Labels
# ---------------------------------------------------------------------------

_BEASTLY = ("dragon", "mythic beast")
_PEOPLE = ("giant-kin", "small folk", "hybrid folk", "folk")


def _labels(**by_kind: str) -> dict[str, str]:
    """Expand ``beasts=`` and ``people=`` shorthands into per-kind labels."""
    out: dict[str, str] = {}
    for key, label in by_kind.items():
        if key == "beasts":
            out.update({kind: label for kind in _BEASTLY})
        elif key == "people":
            out.update({kind: label for kind in _PEOPLE})
        else:
            out[key.replace("_", " ")] = label
    return out


LABELS: dict[str, dict[str, str]] = {
    "subkind": _labels(dragon="Dragon type", mythic_beast="Beast type", people="Folk type",
                       spirit_or_elemental="Spirit type", undead="Undead type",
                       construct="Construct type", structure="Structure type",
                       vessel="Vessel type", artifact="Artifact type"),
    "scale": _labels(beasts="Size", people="Size", undead="Size"),
    "condition": _labels(beasts="Age and state", people="State", undead="Decay and state"),
    "form": _labels(beasts="Body plan", people="Build", spirit_or_elemental="Shape",
                    undead="Frame", construct="Body", structure="Silhouette", vessel="Hull",
                    artifact="Object shape"),
    "material": _labels(dragon="Scales", mythic_beast="Hide or coat", people="Garb",
                        spirit_or_elemental="Substance", undead="Remains and garb",
                        construct="Material", structure="Stonework", vessel="Timber",
                        artifact="Substance"),
    "primary_color": _labels(dragon="Scale colour", mythic_beast="Coat colour", people="Garb colour",
                             spirit_or_elemental="Colour", undead="Colour", construct="Colour",
                             structure="Stone colour", vessel="Hull colour", artifact="Colour"),
    "markings": _labels(beasts="Patterning", people="Heraldry and paint", structure="Banners and carving",
                        vessel="Livery", artifact="Ornament"),
    "appendages": _labels(beasts="Horns, wings and tails", people="Worn and grown features",
                          structure="Towers and walls", vessel="Masts and rigging",
                          artifact="Projections"),
    "emitters": _labels(beasts="Inner fire and magic", people="Magic", spirit_or_elemental="Core",
                        undead="Unnatural light", construct="Rune light", structure="Lights",
                        vessel="Lanterns", artifact="Magic"),
    "emitter_color": _labels(beasts="Magic colour", people="Magic colour", artifact="Magic colour"),
    "armament": _labels(beasts="Natural weapons", people="Weapons", undead="Weapons",
                        construct="Weapons", structure="Defences", vessel="Weapons"),
    "sensors": _labels(beasts="Eyes", people="Eyes", undead="Eyes", construct="Eyes", vessel="Lookout"),
    "aperture": _labels(beasts="Maw", people="Face", undead="Face", construct="Face",
                        structure="Gateway", vessel="Hatch", artifact="Opening"),
    "extras": _labels(beasts="Trappings", people="Carried gear", undead="Remnants",
                      structure="Other features", vessel="Cargo", artifact="Setting"),
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
    "appendage_count": APPENDAGE_COUNT_POOLS,
    "emitter_count": EMITTER_COUNT_POOLS,
    "armament_count": ARMAMENT_COUNT_POOLS,
    "sensor_count": SENSOR_COUNT_POOLS,
    SITUATION_FIELD: SITUATION_POOLS,
    RELATION_FIELD: {POOL_DEFAULT_KEY: RELATION_POOL},
    RELATION_POSITION_FIELD: {POOL_DEFAULT_KEY: RELATION_POSITION_POOL},
}


# ---------------------------------------------------------------------------
# Relations: roles and rules
# ---------------------------------------------------------------------------

KIND_CAPABILITIES: dict[str, frozenset[str]] = {
    "dragon": frozenset({"agent", "mobile", "massive", "mount"}),
    "mythic beast": frozenset({"agent", "mobile", "mount"}),
    "giant-kin": frozenset({"agent", "mobile", "massive", "sapient"}),
    "small folk": frozenset({"agent", "mobile", "sapient", "rider"}),
    "hybrid folk": frozenset({"agent", "mobile", "sapient", "rider"}),
    "folk": frozenset({"agent", "mobile", "sapient", "rider"}),
    "spirit or elemental": frozenset({"agent", "mobile"}),
    "undead": frozenset({"agent", "mobile", "rider"}),
    "construct": frozenset({"agent", "mobile"}),
    "structure": frozenset({"massive"}),
    "vessel": frozenset({"mobile", "massive"}),
    "artifact": frozenset(),
}

RELATION_ROLES: dict[str, tuple[frozenset[str], frozenset[str]]] = {
    "attacking": (frozenset({"agent"}), frozenset()),
    "hunting": (frozenset({"mobile", "agent"}), frozenset({"mobile"})),
    "fleeing from": (frozenset({"mobile"}), frozenset({"agent"})),
    "facing": (frozenset({"agent"}), frozenset()),
    "watching": (frozenset({"agent"}), frozenset()),
    "ignoring": (frozenset({"agent"}), frozenset({"agent"})),
    "guarding": (frozenset({"agent"}), frozenset()),
    "riding": (frozenset({"rider"}), frozenset({"mount"})),
    "creeping toward": (frozenset({"mobile"}), frozenset()),
    "looming over": (frozenset({"massive"}), frozenset()),
    "towering over": (frozenset({"massive"}), frozenset()),
    "bowing before": (frozenset({"sapient"}), frozenset({"agent"})),
    "duelling": (frozenset({"sapient"}), frozenset({"sapient"})),
    "protecting": (frozenset({"agent"}), frozenset()),
    "stalking": (frozenset({"mobile"}), frozenset({"mobile"})),
    "confronting": (frozenset({"agent"}), frozenset({"agent"})),
    "parleying with": (frozenset({"sapient"}), frozenset({"sapient"})),
    "following": (frozenset({"mobile"}), frozenset({"mobile"})),
    "hiding from": (frozenset({"mobile"}), frozenset({"agent"})),
    "leading": (frozenset({"sapient"}), frozenset({"mobile"})),
    "taming": (frozenset({"sapient"}), frozenset({"mount"})),
    "healing": (frozenset({"sapient"}), frozenset({"agent"})),
    "challenging": (frozenset({"agent"}), frozenset({"agent"})),
    "charging at": (frozenset({"mobile"}), frozenset()),
    "approaching": (frozenset({"mobile"}), frozenset()),
}

#: A rider sits on the mount: only a position that can be true of that reads.
_RIDING_POSITIONS: tuple[str, ...] = (
    "from behind", "from below", "in the background", "at a distance", "directly ahead",
    "to one side", "in the middle distance", "in the foreground",
)
#: What only a creature turned to stone can be doing. Stated plainly ("wreathed in
#: creeping ivy") and made true by the condition: a stone act requires the
#: petrified condition, and every other condition excludes it. Worded as its own
#: petrification, it read "a petrified boar is standing petrified"; left to chance,
#: a live ogre was "wreathed in creeping ivy".
_STONE_ACTS: tuple[str, ...] = (
    "standing locked mid-roar", "streaked with lichen and weather", "standing with a cracked stony flank",
    "crumbling at one edge", "wreathed in creeping ivy", "sprouting a young tree from one cracked flank",
    "crusted with sea growth on the seabed",
)
_LIVING_CONDITIONS: tuple[str, ...] = tuple(
    value for key in ("dragon", "mythic beast", "giant-kin") for value in CONDITION_POOLS[key]
    if value != "petrified"
)

CONSTRAINTS: tuple[ConstraintRule, ...] = (
    ConstraintRule(
        type=RULE_REQUIRE, field=f"entity*.{SITUATION_FIELD}", values=_STONE_ACTS,
        requires_field="entity*.condition", requires_values=("petrified",),
        reason="only a creature turned to stone does nothing but weather",
    ),
    ConstraintRule(
        type=RULE_EXCLUDE, field="entity*.condition", values=tuple(dict.fromkeys(_LIVING_CONDITIONS)),
        excludes_field=f"entity*.{SITUATION_FIELD}", excludes_values=_STONE_ACTS,
        reason="a living creature is not weathering like stone",
    ),
    *(
        ConstraintRule(
            type=RULE_EXCLUDE, field=RELATION_ANY, value=relation,
            excludes_field=RELATION_ANY_POSITION, excludes_values=("from below",),
            reason="a thing that towers over another is not below it",
        )
        for relation in ("towering over", "looming over")
    ),
    ConstraintRule(
        type=RULE_EXCLUDE, field=RELATION_ANY, value="riding",
        excludes_field=RELATION_ANY_POSITION, excludes_values=_RIDING_POSITIONS,
        reason="a rider sits on the mount it is riding",
    ),
)


# ---------------------------------------------------------------------------
# Places: what each one affords, and how a body can stand in it
# ---------------------------------------------------------------------------
#
# ``ground`` natural footing; ``floor`` anything to stand on; ``structure`` built
# surroundings; ``shoreline`` water with air above it; ``submerged`` under water;
# ``sky`` room to fly; ``cloud-deck`` above the clouds; ``void`` the starry void
# between worlds; ``dock`` a berth for a ship; ``vast`` room for something huge;
# ``sunlight``, ``cold``, ``heat``, ``dust``, ``life``, ``dark``. ``gravity`` and
# ``air`` are derived below.

PLACE_AFFORDANCES: dict[str, frozenset[str]] = {
    # --- bands ---
    "wilds": frozenset({"ground", "floor", "sky", "vast", "sunlight"}),
    "waterside": frozenset({"ground", "floor", "sky", "vast", "sunlight", "shoreline"}),
    "underwater": frozenset({"submerged"}),
    "sky": frozenset({"sky", "vast", "sunlight"}),
    "underground": frozenset({"ground", "floor", "dark"}),
    "settlement": frozenset({"ground", "floor", "structure", "sky", "sunlight"}),
    "interior": frozenset({"floor", "structure"}),
    "otherworld": frozenset({"ground", "floor", "sky", "vast"}),
    # --- wilds ---
    "ancient oak forest": frozenset({"ground", "floor", "sky", "vast", "sunlight", "life"}),
    "enchanted forest glade": frozenset({"ground", "floor", "sky", "vast", "sunlight", "life"}),
    "windswept moorland": frozenset({"ground", "floor", "sky", "vast", "sunlight", "life", "open-ground"}),
    "rolling highland hills": frozenset({"ground", "floor", "sky", "vast", "sunlight", "life", "open-ground"}),
    "high mountain pass": frozenset({"ground", "floor", "sky", "vast", "sunlight", "cold"}),
    "snowbound mountain peak": frozenset({"ground", "floor", "sky", "vast", "sunlight", "cold"}),
    "glacier valley": frozenset({"ground", "floor", "sky", "vast", "sunlight", "cold"}),
    "red sandstone canyon": frozenset({"ground", "floor", "sky", "vast", "sunlight", "dust"}),
    "desert of shifting dunes": frozenset({"ground", "floor", "sky", "vast", "sunlight", "dust", "open-ground"}),
    "salt-crusted wasteland": frozenset({"ground", "floor", "sky", "vast", "sunlight", "dust", "open-ground"}),
    "volcanic ashlands": frozenset({"ground", "floor", "sky", "vast", "sunlight", "dust", "heat"}),
    "petrified forest": frozenset({"ground", "floor", "sky", "vast", "sunlight", "dust"}),
    "wildflower meadow": frozenset({"ground", "floor", "sky", "vast", "sunlight", "life", "open-ground"}),
    "bramble-choked valley": frozenset({"ground", "floor", "sky", "vast", "sunlight", "life"}),
    "forest of giant mushrooms": frozenset({"ground", "floor", "sky", "vast", "life"}),
    "overgrown elven ruins": frozenset({"ground", "floor", "sky", "vast", "sunlight", "life", "structure"}),
    "thorn-wrapped hillside of barrow mounds": frozenset({"ground", "floor", "sky", "vast", "life"}),
    "field of standing stones": frozenset({"ground", "floor", "sky", "vast", "sunlight", "open-ground"}),
    "old battlefield of rusted banners": frozenset({"ground", "floor", "sky", "vast", "sunlight",
                                                    "open-ground"}),
    # --- waterside ---
    # ``navigable``: water deep and open enough for a ship; a longship in a
    # shallow river ford was a boat in a creek.
    "storm-lashed sea cliffs": frozenset({"ground", "floor", "sky", "vast", "sunlight", "shoreline",
                                          "navigable"}),
    "black sand beach": frozenset({"ground", "floor", "sky", "vast", "sunlight", "shoreline",
                                   "navigable"}),
    "lake shore below a waterfall": frozenset({"ground", "floor", "sky", "vast", "sunlight",
                                               "shoreline", "navigable"}),
    "rocky coast of a stormy sea": frozenset({"ground", "floor", "sky", "vast", "sunlight",
                                              "shoreline", "navigable"}),
    # ``open-ground``: flat, open land a wheel can cross.
    "shallow river ford": frozenset({"ground", "floor", "sky", "vast", "sunlight", "shoreline",
                                     "open-ground"}),
    "frozen lake shore": frozenset({"ground", "floor", "sky", "vast", "sunlight", "shoreline", "cold"}),
    "reed marsh": frozenset({"ground", "floor", "sky", "vast", "sunlight", "shoreline", "life"}),
    "mangrove fen": frozenset({"ground", "floor", "sky", "vast", "shoreline", "life"}),
    # --- underwater ---
    "kelp forest depths": frozenset({"submerged", "life"}),
    "coral reef grotto": frozenset({"submerged", "life"}),
    "sunken temple ruins": frozenset({"submerged"}),
    "drowned city streets": frozenset({"submerged"}),
    # --- sky ---
    "sea of clouds": frozenset({"sky", "vast", "sunlight", "cloud-deck"}),
    "floating island archipelago": frozenset({"sky", "vast", "sunlight", "ground", "floor", "life"}),
    "stormy sky above a mountain range": frozenset({"sky", "vast", "cloud-deck"}),
    # --- underground ---
    "dwarven great hall": frozenset({"floor", "structure", "dark", "vast"}),
    "dragon's hoard cavern": frozenset({"ground", "floor", "dark", "vast"}),
    "magma cavern": frozenset({"ground", "floor", "dark", "heat"}),
    "catacomb crypt": frozenset({"floor", "structure", "dark"}),
    "abandoned mine tunnels": frozenset({"ground", "floor", "structure", "dark"}),
    "underground river cavern": frozenset({"ground", "floor", "dark", "shoreline"}),
    "fungal grotto": frozenset({"ground", "floor", "dark", "life"}),
    # --- settlement ---
    "cobbled market square": frozenset({"floor", "structure", "sky", "sunlight", "open-ground"}),
    "harbour town quay": frozenset({"floor", "structure", "sky", "sunlight", "shoreline", "dock",
                                    "navigable", "open-ground"}),
    "walled city gate": frozenset({"ground", "floor", "structure", "sky", "sunlight", "open-ground"}),
    "village green": frozenset({"ground", "floor", "structure", "sky", "sunlight", "life", "open-ground"}),
    "castle courtyard": frozenset({"floor", "structure", "sky", "sunlight", "open-ground"}),
    "elven treetop village": frozenset({"floor", "structure", "sky", "sunlight", "life"}),
    "dwarven mountain stronghold gate": frozenset({"ground", "floor", "structure", "sky", "cold"}),
    "ruined city plaza": frozenset({"ground", "floor", "structure", "sky", "sunlight", "life", "open-ground"}),
    # --- interior ---
    "blacksmith's forge": frozenset({"floor", "structure", "heat"}),
    "dungeon cell block": frozenset({"floor", "structure", "dark"}),
    "treasure vault": frozenset({"floor", "structure", "dark"}),
    # --- otherworld ---
    "fairy ring glade": frozenset({"ground", "floor", "sky", "sunlight", "life"}),
    "astral void between worlds": frozenset({"void", "vast"}),
    "blazing elemental plane": frozenset({"ground", "floor", "vast", "heat"}),
    "realm of endless night": frozenset({"ground", "floor", "sky", "vast", "dark"}),
    "frozen realm of the frost giants": frozenset({"ground", "floor", "sky", "vast", "cold"}),
}
_GRAVITY_SOURCES = frozenset({"ground", "floor", "sky", "shoreline", "submerged"})
_AIR_EXCLUDED = frozenset({"submerged", "void"})
#: Open water at a shore or all around: a water spirit is at home in either.
_WATER_SOURCES = frozenset({"shoreline", "submerged"})
PLACE_AFFORDANCES = {
    place: (
        affordances
        | ({"gravity"} if affordances & _GRAVITY_SOURCES else set())
        | ({"air"} if not affordances & _AIR_EXCLUDED else set())
        | ({"water"} if affordances & _WATER_SOURCES else set())
    )
    for place, affordances in PLACE_AFFORDANCES.items()
}

#: ``{affordance: stances the place supports}``.
PLACE_STANCES: dict[str, frozenset[str]] = {
    "ground": frozenset({"rests", "walks", "rolls", "slithers"}),
    "floor": frozenset({"rests", "walks", "rolls", "slithers", "hovers", "floats"}),
    "structure": frozenset({"rests", "walks", "rolls", "slithers", "hovers", "floats"}),
    "sky": frozenset({"flies", "hovers", "floats", "falls"}),
    "submerged": frozenset({"swims", "floats", "rests"}),
    "shoreline": frozenset({"rests", "walks", "rolls", "swims", "slithers", "sails", "hovers"}),
    "dock": frozenset({"sails", "rests"}),
    "void": frozenset({"floats", "flies"}),
}

_WALK_FLY = frozenset({"walks", "flies"})
_WALK_SWIM = frozenset({"walks", "swims"})
_FEY = frozenset({"flies", "hovers", "walks"})
_SPIRIT = frozenset({"floats", "hovers", "flies"})
_STILL = frozenset({"rests"})
_OBJECT = frozenset({"rests", "floats", "hovers"})

#: How each form holds itself up, by the pool key that authors it. A form listed
#: under two keys takes the union.
_FORM_KEY_STANCES: dict[str, frozenset[str]] = {
    "winged dragon": _WALK_FLY, "serpent wyrm": _SLITHER, "sea wyrm": _SWIM,
    "many-headed dragon": _WALK_SWIM,
    "unicorn": _WALK, "nightmare steed": _WALK, "kelpie": _WALK_SWIM, "silver stag": _WALK,
    "pegasus": _WALK_FLY, "hippogriff": _WALK_FLY, "griffin": _WALK_FLY, "roc": _WALK_FLY,
    "phoenix": _WALK_FLY, "thunderbird": _WALK_FLY, "cockatrice": _WALK_FLY,
    "manticore": _WALK, "chimera": _WALK, "sphinx": _WALK, "dire wolf": _WALK, "cave bear": _WALK,
    "great tusked boar": _WALK, "basilisk": frozenset({"walks", "slithers"}), "behemoth": _WALK,
    "giant cave spider": _WALK, "hellhound": _WALK, "treant": _WALK,
    "kraken": _SWIM, "hippocamp": _SWIM, "giant sea turtle": _SWIM,
    "troll": _WALK, "ogre-kin": _WALK, "giant": _WALK, "ettin": _WALK,
    "goblinoid": _WALK, "kobold": _WALK, "gnome-kin": _WALK, "pixie": _FEY, "sprite": _FEY, "imp": _FEY,
    "centaur": _WALK, "satyr": _WALK, "faun": _WALK, "minotaur": _WALK,
    "gorgon": frozenset({"walks", "slithers"}), "naga": frozenset({"slithers", "swims"}),
    "harpy": _WALK_FLY, "merfolk": _SWIM, "selkie": _WALK_SWIM, "dryad": _WALK,
    "adventurer": _WALK, "elf": _WALK, "dwarf": _WALK, "orc": _WALK, "halfling": _WALK,
    "elemental": frozenset({"floats", "hovers", "walks"}), "earth elemental": _WALK,
    "magma elemental": _WALK, "will-o'-wisp": frozenset({"floats", "hovers"}), "sylph": _SPIRIT,
    "undine": frozenset({"floats", "swims"}), "forest spirit": frozenset({"walks", "floats"}),
    "walking dead": _WALK, "mummy": _WALK, "drowned revenant": _WALK_SWIM,
    "restless spirit": frozenset({"floats", "hovers"}),
    "golem": _WALK, "bronze colossus": _WALK, "animated armour": _WALK, "clockwork guardian": _WALK,
    "living statue": frozenset({"walks", "rests"}), "gargoyle": frozenset({"walks", "flies", "rests"}),
    "floating citadel": frozenset({"floats", "hovers"}),
    "galleon": _SAIL, "longship": _SAIL, "war galley": _SAIL, "river barge": _SAIL, "pirate sloop": _SAIL,
    "airship": frozenset({"flies", "hovers"}), "sky galleon": frozenset({"flies", "hovers"}),
    "cloud skiff": frozenset({"flies", "hovers"}),
    "war chariot": _ROLL, "merchant caravan wagon": _ROLL, "royal carriage": _ROLL,
    "siege tower": _ROLL, "painted travelling wagon": _ROLL,
}
#: Two forms that fly where their siblings only walk.
_FORM_STANCE_OVERRIDES: dict[str, frozenset[str]] = {
    "bat-winged lion body": _WALK_FLY,
    "winged lion body with a human face": _WALK_FLY,
}


def _form_stances() -> dict[str, frozenset[str]]:
    out: dict[str, frozenset[str]] = {}
    structures = set(SUBKIND_POOLS["structure"]) - {"floating citadel"}
    artifacts = set(SUBKIND_POOLS["artifact"])
    for key, forms in FORM_POOLS.items():
        if key == POOL_DEFAULT_KEY:
            stances = frozenset()
        elif key in _FORM_KEY_STANCES:
            stances = _FORM_KEY_STANCES[key]
        elif key in structures:
            stances = _STILL
        elif key in artifacts:
            stances = _OBJECT
        else:
            raise ValueError(f"form pool {key!r} declares no stance")
        for form in forms:
            out[form] = out.get(form, frozenset()) | stances
    out.update(_FORM_STANCE_OVERRIDES)
    return out


# ---------------------------------------------------------------------------
# Needs, stances, tiers and tags, derived from the situation buckets
# ---------------------------------------------------------------------------

def _bucket_table(index: int) -> dict[str, object]:
    out: dict[str, object] = {}
    for bucket in _BUCKETS:
        for value in bucket[0]:
            if value in out and out[value] != bucket[index]:
                raise ValueError(f"situation {value!r} is in two buckets that disagree")
            out[value] = bucket[index]
    return out


SITUATION_TIERS: dict[str, str] = _bucket_table(1)  # type: ignore[assignment]
_SITUATION_TAG_CODES: dict[str, str] = _bucket_table(2)  # type: ignore[assignment]
_SITUATION_NEEDS: dict[str, frozenset[str]] = _bucket_table(3)  # type: ignore[assignment]
_SITUATION_STANCES: dict[str, frozenset[str]] = _bucket_table(4)  # type: ignore[assignment]
_SITUATION_LIFE: dict[str, str] = _bucket_table(5)  # type: ignore[assignment]

_ALL_SITUATIONS: frozenset[str] = frozenset(
    value for pool in SITUATION_POOLS.values() for value in pool
)
_unbucketed = sorted(_ALL_SITUATIONS - set(SITUATION_TIERS))
if _unbucketed:
    raise ValueError(f"situations with no bucket: {_unbucketed}")

#: What a petrified, dormant, ruined or wrecked thing can be doing. Closed:
#: every other situation is derived ``powered-act``.
DORMANT_ACTS: frozenset[str] = frozenset(v for v, life in _SITUATION_LIFE.items() if life == "d")
#: What a slumbering thing can be doing, beyond the dormant list.
SLEEP_ACTS: frozenset[str] = frozenset(v for v, life in _SITUATION_LIFE.items() if life == "s")

_SUBKIND_NEEDS: dict[str, frozenset[str]] = {
    **{value: frozenset() for pool in SUBKIND_POOLS.values() for value in pool},
    "river troll": _SHORE,
    "earth elemental": _GROUND,
    "longship": _SHORE | frozenset({"navigable"}),
    "galleon": _SHORE | frozenset({"navigable"}),
    "war galley": _SHORE | frozenset({"navigable"}),
    "pirate sloop": _SHORE | frozenset({"navigable"}),
    "river barge": _SHORE,
    **{value: frozenset({"open-ground"}) for value in SUBKIND_GROUPS["land vehicle"]},
    "frost troll": _COLD,
    "frost giant": _COLD | frozenset({"vast"}),
    "hill giant": frozenset({"vast"}),
    "fire giant": frozenset({"vast"}),
    "stone giant": frozenset({"vast"}),
    "cyclops": frozenset({"vast"}),
    "ettin": frozenset({"vast"}),
    "ice elemental": _COLD,
    "magma elemental": frozenset({"heat"}),
    # A spirit of a place is drawn in that place: a forest spirit in a crypt and a
    # wisp in an empty void read as nothing at all.
    "forest spirit": _LIFE,
    "will-o'-wisp": _LIFE,
    "dryad": _LIFE,
    "treant": _LIFE,
    "sylph": _SKY,
    "undine": frozenset({"water"}),
    "water elemental": frozenset({"water"}),
    "city gate": _WALLS,
    "dwarven stronghold gate": _WALLS,
    "elven tree palace": _LIFE,
    "lighthouse": _SHORE,
    "windmill": _GROUND,
}

VALUE_NEEDS: dict[str, dict[str, frozenset[str]]] = {
    SITUATION_FIELD: dict(_SITUATION_NEEDS),
    "subkind": _SUBKIND_NEEDS,
    "condition": {"frost-rimed": _COLD, "overgrown": _LIFE},
    # A relic's furnished resting surfaces presume an indoor, dry room; a reed
    # marsh and a flooded temple are neither. The stone/altar surfaces stay
    # ungated on purpose -- they already read fine outdoors and underwater.
    "extras": {
        "velvet cushion": _WALLS | _AIR,
        "silk-draped table": _WALLS | _AIR,
    },
    # A context shared by places of different kinds takes the union of their key
    # defaults, which no single place may afford; these say what they really need.
    CONTEXT_FIELD: {
        "heap of spilled gold coins": frozenset({"floor"}),
        "great forge hearth set into the wall": frozenset({"floor", "structure"}),
        "wall of niches stacked with skulls": frozenset({"floor", "structure"}),
        "rusted pickaxe left against the wall": frozenset({"floor", "structure"}),
        "moored fishing boat at the quay": _WALLS | _SHORE | _DOCK,
        "moss-covered statue of a forgotten king": _GROUND,
        "lone ancient oak on a rise": _GROUND | _LIFE,
    },
}

DEFAULT_NEEDS: dict[str, dict[str, frozenset[str]]] = {
    CONTEXT_FIELD: {
        "wilds": _GROUND, "waterside": _SHORE, "underwater": _DEEP, "sky": _SKY,
        "underground": frozenset({"floor"}), "settlement": _WALLS,
        **{place: _GROUND for place in _ENV_WILDS if place in CONTEXT_POOLS},
        **{place: _SHORE for place in _ENV_WATERSIDE if place in CONTEXT_POOLS},
        **{place: frozenset({"floor"}) for place in _ENV_UNDERGROUND if place in CONTEXT_POOLS},
        **{place: _WALLS for place in _ENV_SETTLEMENT + _ENV_INTERIOR if place in CONTEXT_POOLS},
        **{place: _GROUND | _LIFE for place in (
            "ancient oak forest", "enchanted forest glade", "forest of giant mushrooms",
            "bramble-choked valley",
        )},
        **{place: _GROUND | _COLD for place in (
            "high mountain pass", "snowbound mountain peak", "glacier valley",
        )},
        "fungal grotto": frozenset({"floor", "life"}),
        "elven treetop village": _WALLS | _LIFE,
        "fairy ring glade": _LIFE, "astral void between worlds": frozenset({"void"}),
        "blazing elemental plane": frozenset({"heat"}), "realm of endless night": frozenset({"dark"}),
        "frozen realm of the frost giants": _COLD,
    },
}

VALUE_STANCES: dict[str, dict[str, frozenset[str]]] = {
    "form": _form_stances(),
    SITUATION_FIELD: {v: s for v, s in _SITUATION_STANCES.items() if s},
}


# ---------------------------------------------------------------------------
# Traits and conflicts
# ---------------------------------------------------------------------------

_INHERENTLY_VAST = (
    "elder dragon", "leviathan", "kraken", "roc", "behemoth", "bronze colossus",
    # A type named "giant" is never small ("a small gaunt giant sea turtle").
    "giant sea turtle", "giant cave spider",
)
_INHERENTLY_SMALL = (
    "pixie", "sprite", "imp", "brownie", "will-o'-wisp", "cockatrice", "crystal orb",
    "jewelled crown", "jewelled chalice", "magic mirror", "enchanted tome", "ancient hourglass",
    "dragon egg",
)
_HUGE_DEEDS = (
    "tearing the roof from a stone tower", "raking a castle rampart with its claws",
    "sweeping its tail in a wide arc", "crushing a wagon in its coils",
    "crushing a longship in its coils", "dragging a fishing boat beneath the waves",
)
_COMBUSTION = (
    "spewing a torrent of flame", "unleashing a gout of roaring fire",
    "diving aside from a blast of flame", "stamping out a campfire", "sending up a signal fire",
    "taking a volley of flaming arrows", "blazing with a column of holy fire",
)
_CIVIL_ROLES = ("blacksmith", "herbalist", "travelling merchant", "wandering scholar", "bard", "potion-brewer")

_SELF_COLOURED = (
    "hammered gold", "tarnished silver", "polished obsidian", "ancient bronze", "verdigris bronze",
    "polished bronze", "white marble", "polished marble", "brass gears and plating",
    "copper plating and cogs", "enchanted crystal", "clear faceted quartz", "clear crystal",
    "faceted quartz crystal", "living flame", "roaring white-hot flame", "molten rock and cinders",
    "cooling black magma crust", "blackened steel plate", "blackened wrought iron",
)

VALUE_TRAITS: dict[str, dict[str, tuple[str, ...]]] = {
    "material": {v: ("self-coloured",) for v in _SELF_COLOURED},
    "primary_color": {v: ("states-a-colour",) for pool in PRIMARY_COLOR_POOLS.values() for v in pool},
    "condition": {
        "petrified": ("inactive",), "ruined": ("inactive",), "abandoned": ("inactive",),
        "wrecked": ("inactive",), "dormant": ("inactive",), "slumbering": ("asleep",),
    },
    "scale": {
        "tiny": ("small-scale",), "small": ("small-scale",),
        "huge": ("large-scale",), "colossal": ("large-scale",), "titanic": ("large-scale",),
        "twelve-foot-tall": ("large-scale",), "fourteen-foot-tall": ("large-scale",),
        "twenty-foot-tall": ("large-scale",), "forty-foot-tall": ("large-scale",),
        "three-foot-tall": ("small-scale",), "two-foot-tall": ("small-scale",),
        "six-inch-tall": ("small-scale",), "ten-inch-tall": ("small-scale",),
    },
    "subkind": {
        **{v: ("inherently-vast",) for v in _INHERENTLY_VAST},
        **{v: ("inherently-small",) for v in _INHERENTLY_SMALL},
        "frost troll": ("frost-bound",), "frost giant": ("frost-bound",),
        "ice elemental": ("frost-bound",),
        "fire giant": ("heat-bound",), "hellhound": ("heat-bound",), "phoenix": ("heat-bound",),
        "fire elemental": ("heat-bound", "combustion"),
        "magma elemental": ("heat-bound", "combustion"),
        **{v: ("civil-role",) for v in _CIVIL_ROLES},
    },
    ENVIRONMENT_FIELD: {
        **{v: ("aqueous",) for v in _ENV_UNDERWATER},
        **{v: ("interior-place",) for v in _ENV_INTERIOR},
        "volcanic ashlands": ("hot-place",), "magma cavern": ("hot-place",),
        "blazing elemental plane": ("hot-place",),
        "blacksmith's forge": ("hot-place",),
        "snowbound mountain peak": ("cold-place",), "glacier valley": ("cold-place",),
        "frozen lake shore": ("cold-place",), "frozen realm of the frost giants": ("cold-place",),
        "high mountain pass": ("cold-place",),
    },
    SITUATION_FIELD: {},
    "emitters": {
        value: ("emissive",) for pool in EMITTER_POOLS.values() for value in pool
    },
}


def _add_traits(field: str, additions: dict[str, tuple[str, ...]]) -> None:
    table = VALUE_TRAITS.setdefault(field, {})
    for value, added in additions.items():
        table[value] = tuple(dict.fromkeys(tuple(table.get(value, ())) + added))


#: Added, not merged into the literal above: a later ``**{...}`` entry for the same
#: key replaced the earlier one, and the kraken, the leviathan and the giant sea
#: turtle silently lost ``inherently-vast`` -- a "small giant sea turtle" was legal.
_add_traits("subkind", {v: ("water-bound",) for v in (
    "selkie", "merfolk", "undine", "water elemental", "kelpie", "hippocamp", "kraken",
    "giant sea turtle", "sea serpent", "leviathan", "abyssal wyrm", "drowned revenant",
)})
_add_traits(SITUATION_FIELD, {v: ("powered-act",) for v in _ALL_SITUATIONS - DORMANT_ACTS})
_add_traits(SITUATION_FIELD, {v: ("waking-act",) for v in _ALL_SITUATIONS - SLEEP_ACTS})
_add_traits(SITUATION_FIELD, {v: ("huge-deed",) for v in _HUGE_DEEDS})
_add_traits(SITUATION_FIELD, {v: ("combustion",) for v in _COMBUSTION})
_add_traits(SITUATION_FIELD, {
    v: ("violent-act",) for v, code in _SITUATION_TAG_CODES.items() if code == "c"
})

#: Round XV -- an act that names a weapon class needs a weapon of that class.
#: "Charging with a shield raised" was drawn for a druid carrying a quarterstaff,
#: who grew a shield to match. Most acts were reworded to be weapon-neutral; the
#: bow and blade acts are worth keeping and declare what they hold. An entity
#: with no armament described is free to hold whatever the act names.
_BOW_ACTS = ("loosing an arrow at full draw", "stringing a longbow", "loosing arrows from a high branch")
_BLADE_ACTS = (
    "sharpening a blade on a whetstone", "testing the edge of a blade", "sharpening a blade",
    "sharpening a crooked blade", "slashing wildly with a short blade",
    "rallying defenders with a raised blade",
)
_add_traits(SITUATION_FIELD, {v: ("bow-act",) for v in _BOW_ACTS})
_add_traits(SITUATION_FIELD, {v: ("blade-act",) for v in _BLADE_ACTS})
_add_traits("armament", {
    **{v: ("bow-weapon",) for v in ("longbow", "tiny bow")},
    **{v: ("edged-weapon",) for v in (
        "longsword", "dagger", "battle axe", "rapier", "slender curved blade", "heavy cleaver",
        "curved sword", "double-bladed axe", "notched short blade", "rusty dagger",
        "hunting spear", "crude spear", "thorn spear", "bone spear", "coral trident", "spear",
        "rusted longsword", "notched axe", "reaping scythe", "stone-headed axe", "rusted cleaver",
        "rune-etched greatsword", "halberd",
    )},
    **{v: ("unbladed-weapon",) for v in (
        "war hammer", "quarterstaff", "flanged mace", "kite shield", "gnarled staff", "flail",
        "crossbow", "iron-bound club", "sling", "barbed pitchfork", "tree-trunk club",
        "iron-banded war maul", "great throwing stone", "cracked shield", "bone staff",
        "great stone maul",
    )},
})

#: A new or gleaming thing is not decaying: "a newly launched cloud skiff standing
#: abandoned with its paint peeling".
_PRISTINE_CONDITIONS = (
    "newly launched", "newly built", "newly forged", "gleaming", "pristine", "newly summoned",
)
_NEGLECT_ACTS = (
    "standing abandoned with its paint peeling", "rotting in the shallows",
    "overgrown by creeping vines", "lying broken on a hillside", "lying beached on its side",
    "crumbling at one corner", "shedding stones into the grass", "standing roofless and silent",
    "half-swallowed by the forest", "gathering dust on a forgotten shelf",
    "resting under a thick layer of dust", "wrapped in cobwebs", "lying forgotten among old bones",
    "standing motionless under a coat of dust", "half-buried in rubble", "covered in climbing ivy",
    "resting beneath a layer of dust", "streaked with lichen and weather",
    "crumbling at one edge", "wreathed in creeping ivy",
    "sprouting a young tree from one cracked flank",
)
_add_traits("condition", {v: ("pristine-state",) for v in _PRISTINE_CONDITIONS})
_add_traits(SITUATION_FIELD, {v: ("neglect-act",) for v in _NEGLECT_ACTS})

TRAIT_CONFLICTS: tuple[tuple[str, str], ...] = (
    ("self-coloured", "states-a-colour"),
    ("inactive", "powered-act"),
    ("asleep", "waking-act"),
    ("inactive", "emissive"),
    ("aqueous", "combustion"),
    ("hot-place", "frost-bound"),
    ("cold-place", "heat-bound"),
    ("hot-place", "water-bound"),
    ("huge-deed", "small-scale"),
    ("inherently-vast", "small-scale"),
    ("inherently-small", "large-scale"),
    ("interior-place", "large-scale"),
    ("civil-role", "violent-act"),
    ("bow-act", "edged-weapon"),
    ("bow-act", "unbladed-weapon"),
    ("blade-act", "bow-weapon"),
    ("blade-act", "unbladed-weapon"),
    ("pristine-state", "neglect-act"),
)
TRAIT_REASONS: dict[str, str] = {
    "self-coloured|states-a-colour": "a material that names its own colour fixes it",
    "inactive|powered-act": "a petrified, ruined or dormant thing does not act",
    "asleep|waking-act": "a slumbering thing is asleep",
    "inactive|emissive": "a petrified, ruined or dormant thing shows no light of its own",
    "aqueous|combustion": "nothing burns under water",
    "hot-place|frost-bound": "a creature of frost does not stand in fire",
    "cold-place|heat-bound": "a creature of fire does not stand in ice",
    "hot-place|water-bound": "a creature of the water does not stand in fire",
    "huge-deed|small-scale": "a small body cannot do a giant's deed",
    "inherently-vast|small-scale": "a vast creature is never small",
    "inherently-small|large-scale": "a small thing is never huge",
    "interior-place|large-scale": "a room cannot hold something huge",
    "civil-role|violent-act": "a smith, a scholar or a bard does not fight",
    "bow-act|edged-weapon": "an archer's act needs the bow the entity carries",
    "bow-act|unbladed-weapon": "an archer's act needs the bow the entity carries",
    "blade-act|bow-weapon": "a blade act needs a blade",
    "blade-act|unbladed-weapon": "a blade act needs a blade",
    "pristine-state|neglect-act": "a new or gleaming thing is not decaying",
}


def _tag_code(code: str) -> str:
    return {"c": TAG_CONFLICT_ONLY, "p": TAG_PEACEFUL_ONLY}.get(code, TAG_NEUTRAL)


_RELATION_CONFLICT = frozenset({
    "attacking", "hunting", "fleeing from", "creeping toward", "duelling", "stalking",
    "confronting", "challenging", "charging at", "hiding from",
})
_RELATION_PEACEFUL = frozenset({"bowing before", "parleying with", "healing", "taming", "leading"})

#: Weapons are carried, not wielded, so they are neutral: a knight keeps a sword
#: in a Peaceful scene. What is *done* with it is what the filter reads.
TAGS: dict[str, dict[str, str]] = {
    "subkind": {v: TAG_NEUTRAL for pool in SUBKIND_POOLS.values() for v in pool},
    "armament": {v: TAG_NEUTRAL for pool in ARMAMENT_POOLS.values() for v in pool},
    "aperture": {v: TAG_NEUTRAL for pool in APERTURE_POOLS.values() for v in pool},
    SITUATION_FIELD: {v: _tag_code(code) for v, code in _SITUATION_TAG_CODES.items()},
    RELATION_FIELD: {
        v: (TAG_CONFLICT_ONLY if v in _RELATION_CONFLICT
            else TAG_PEACEFUL_ONLY if v in _RELATION_PEACEFUL else TAG_NEUTRAL)
        for v in RELATION_POOL
    },
}


# ---------------------------------------------------------------------------
# Lint tables -- place words, stance words, body words, part words, anachronisms
# ---------------------------------------------------------------------------

AFFORDANCE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "ground": ("ground", "earth", "soil", "hillside", "crag", "mud", "crevasse", "boulder", "grave",
               "road", "crossroads", "battlefield"),
    "structure": ("wall", "walls", "door", "gate", "pillar", "archway", "alcove", "coffin",
                  "sarcophagus", "iron bars", "throne", "corridor", "rooftop", "rampart",
                  "stone tower", "altar", "stair", "tower mooring"),
    "shoreline": ("shore", "shallows", "waves", "river", "pool", "cove", "water's edge", "surface",
                  "boat", "longship", "seas"),
    "submerged": ("depths", "seabed", "kelp", "sunken"),
    "sky": ("overhead", "clouds"),
    "life": ("undergrowth", "tree", "sapling", "ivy", "vines", "meadow", "herbs", "leaves", "oak",
             "branch", "mushroom"),
    "cold": ("snow", "frost", "frozen", "ice"),
    "heat": ("lava", "magma"),
    "dock": ("quay", "moored", "mooring"),
}
AFFORDANCE_LINT_FIELDS: tuple[str, ...] = ("situation", "context", "subkind")
AFFORDANCE_ALLOWLIST: frozenset[str] = frozenset({
    # A frost troll and a frost giant need cold, and say so in value_needs; the
    # frozen realm names itself.
    "frozen realm of the frost giants",
})

STANCE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "flies": ("overhead", "soaring", "diving on", "taking wing", "swooping", "launching from",
              "banking", "climb into the air"),
    "swims": ("surfacing", "through the depths", "through a kelp", "along the seabed"),
    "slithers": ("slithering", "burrowing"),
    "walks": ("galloping", "wading", "shambling"),
    "rolls": ("rumbling along", "bouncing over", "rolling"),
    "sails": ("under full sail", "tacking", "rowing"),
    "hovers": ("hovering",),
}

BODY_FEATURES: dict[str, frozenset[str]] = {
    "dragon": frozenset({"jaws", "tail"}),
    "winged dragon": frozenset({"jaws", "tail", "wings"}),
    "serpent wyrm": frozenset({"jaws", "tail"}),
    "sea wyrm": frozenset({"jaws", "tail"}),
    "many-headed dragon": frozenset({"jaws", "tail", "heads"}),
    "mythic beast": frozenset({"jaws"}),
    "hoofed beast": frozenset({"jaws", "hooves", "tail"}),
    "pegasus": frozenset({"jaws", "hooves", "tail", "wings"}),
    "hippogriff": frozenset({"jaws", "hooves", "tail", "wings"}),
    "winged beast": frozenset({"jaws", "tail", "wings"}),
    "chimeric beast": frozenset({"jaws", "tail"}),
    "manticore": frozenset({"jaws", "tail", "wings"}),
    "sphinx": frozenset({"jaws", "tail", "wings"}),
    "great beast": frozenset({"jaws", "tail"}),
    "sea beast": frozenset({"jaws", "tentacles"}),
    "giant-kin": frozenset({"hands", "jaws"}),
    "small folk": frozenset({"hands", "jaws"}),
    "winged fey": frozenset({"hands", "jaws", "wings"}),
    "imp": frozenset({"hands", "jaws", "wings", "tail"}),
    "hybrid folk": frozenset({"hands", "jaws"}),
    "serpent folk": frozenset({"hands", "jaws", "tail"}),
    "minotaur": frozenset({"hands", "jaws", "horns", "tail"}),
    "sea folk": frozenset({"hands", "jaws", "tail"}),
    "winged folk": frozenset({"hands", "jaws", "wings"}),
    "folk": frozenset({"hands", "jaws"}),
    "spirit or elemental": frozenset(),
    "undead": frozenset({"hands", "jaws"}),
    "restless spirit": frozenset({"hands", "jaws"}),
    "construct": frozenset({"hands"}),
    "gargoyle": frozenset({"hands", "wings"}),
    "structure": frozenset(),
    "vessel": frozenset(),
    "sailing ship": frozenset({"keel", "stern", "sails"}),
    "flying ship": frozenset({"wings", "stern", "sails"}),
    "land vehicle": frozenset({"wheels"}),
    "windmill": frozenset({"sails"}),
    "artifact": frozenset(),
}
BODY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "wings": ("wings", "wing"),
    "tail": ("tail",),
    "heads": ("every head", "several heads", "necks", "longest neck"),
    "horns": ("horns",),
    "hooves": ("hoof", "hooves", "hind legs"),
    "hands": ("hands", "hand", "fist", "fists", "fingers", "finger"),
    "jaws": ("jaws", "jaw", "teeth", "bite"),
}
BODY_LINT_FIELDS: tuple[str, ...] = ("situation",)
PART_KEYWORDS: dict[str, tuple[str, ...]] = {
    "wings": ("wing",),
    "hooves": ("hoof",),
    "tentacles": ("tentacle",),
    "wheels": ("wheel", "wheels"),
    # Round XV: what only a hull that floats has, what only a ship has at its back,
    # and what only a rigged hull (or a windmill) carries.
    "keel": ("waterline", "anchor", "barnacled", "oar", "ship's boat", "gangway"),
    "stern": ("stern",),
    "sails": ("mast", "sail", "sails"),
}
PART_LINT_FIELDS: tuple[str, ...] = (
    "appendages", "armament", "extras", "emitters", "sensors", "aperture", "surface_detail",
    "markings",
)

#: Anachronisms: a model draws each of these as the modern thing, and none of them
#: belongs in a fantasy frame.
FOREIGN_NOUNS: tuple[str, ...] = (
    "gun", "guns", "rifle", "pistol", "bullet", "engine", "motor", "neon", "plastic", "laser",
    "robot", "car", "truck", "phone", "screen", "computer", "electric", "chrome", "concrete",
    "asphalt", "jet", "rocket", "satellite", "spaceship", "starship", "cyber", "digital",
    "battery", "radio", "radar", "helicopter", "airplane", "aircraft", "tank", "grenade",
    "missile", "drone", "bicycle", "jeans", "sneakers", "sunglasses", "headphones", "hoodie",
    "zipper", "skyscraper", "factory", "propeller",
)
FOREIGN_NOUN_FIELDS: tuple[str, ...] = (
    "kind", "subkind", "scale", "condition", "form", "material", "primary_color",
    "accent_color", "markings", "surface_detail", "appendages", "emitters",
    "armament", "sensors", "aperture", "extras", "situation", "relation",
    "relation_position", "context", "environment",
)


# ---------------------------------------------------------------------------
# Archetypes -- how each category of thing is spoken
# ---------------------------------------------------------------------------

_SELF_NAMING_HEAD = HeadPhrase(noun=("subkind", "kind"), modifiers=("scale", "condition"))
_MADE_HEAD = HeadPhrase(noun=("subkind", "kind"), modifiers=("scale", "condition"), apposition="kind")

_THEY = dict(
    pronoun="they", pronoun_plural="they", possessive="their", possessive_plural="their",
    pronoun_copula="are", pronoun_object="them", pronoun_object_plural="them",
)

#: A cap counts the head modifiers (scale, condition) as well, and they never spend
#: the allowance, so every cap below is the clause count it speaks plus two.
ARCHETYPES: dict[str, Archetype] = {
    # A dragon or a beast: the type is iconic, so it leads; the body follows.
    "creature": Archetype(
        head_phrase=_SELF_NAMING_HEAD,
        detail_cap=12,
        detail_priority=("form", "subkind", "material", "primary_color", "appendages", "sensors",
                         "aperture", "scale"),
        detail_rotation_slots=1,
        detail_rotation={"armament": 1.0, "markings": 1.0, "emitters": 1.0, "extras": 0.5,
                         "surface_detail": 0.6, "accent_color": 0.3},
        sentences=(
            Sentence(text="{subject} {copula} {situation}."),
            Sentence(text="{subject}."),
            Sentence(text="{pronoun} has {form}[, covered in {material}]."),
            Sentence(text="{pronoun} {pronoun_copula} covered in {material}."),
            Sentence(text="{pronoun} {pronoun_copula} {primary_color}."),
            Sentence(text="{pronoun} shows {surface_detail}."),
            Sentence(text="{pronoun} features {appendages, armament, sensors, extras}."),
            Sentence(text="{pronoun} bears {emitters, aperture}."),
            Sentence(text="{pronoun} {pronoun_copula} marked with {markings, accent_color}."),
        ),
    ),
    # A troll or an ogre: a body in its own hide, spoken as a person-like "they".
    "brute": Archetype(
        head_phrase=_SELF_NAMING_HEAD,
        detail_cap=11,
        detail_priority=("form", "subkind", "material", "primary_color", "armament", "appendages",
                         "sensors", "scale"),
        detail_rotation_slots=1,
        detail_rotation={"extras": 1.0, "markings": 0.8, "aperture": 0.8, "surface_detail": 0.6,
                         "emitters": 0.4, "accent_color": 0.3},
        sentences=(
            Sentence(text="{subject} {copula} {situation}."),
            Sentence(text="{subject}."),
            Sentence(text="{pronoun} have {form}[, covered in {material}]."),
            Sentence(text="{pronoun} {pronoun_copula} covered in {material}."),
            Sentence(text="{pronoun} {pronoun_copula} {primary_color}."),
            Sentence(text="{pronoun} show {surface_detail}."),
            Sentence(text="{pronoun} carry {armament, extras}."),
            Sentence(text="{possessive} features include {appendages, sensors}."),
            Sentence(text="{pronoun} show {emitters, aperture}."),
            Sentence(text="{possessive} hide bears {markings, accent_color}."),
        ),
        **_THEY,
    ),
    # A giant, a goblin, a centaur: a body that wears garb and carries gear.
    "being": Archetype(
        head_phrase=_SELF_NAMING_HEAD,
        detail_cap=11,
        templates={"material": "{a_value}"},
        detail_priority=("form", "subkind", "material", "primary_color", "appendages", "sensors",
                         "armament"),
        detail_rotation_slots=2,
        detail_rotation={"markings": 1.0, "extras": 1.0, "aperture": 0.8, "surface_detail": 0.6,
                         "emitters": 0.6, "scale": 0.6, "accent_color": 0.4},
        sentences=(
            Sentence(text="{subject} {copula} {situation}."),
            Sentence(text="{subject}."),
            Sentence(text="{pronoun} have {form} and wear {material}."),
            Sentence(text="{pronoun} wear {material}."),
            Sentence(text="{pronoun} have {form}."),
            Sentence(text="{possessive} garb is {primary_color}."),
            Sentence(text="{pronoun} show {surface_detail}."),
            Sentence(text="{possessive} gear bears {markings, accent_color}."),
            Sentence(text="{pronoun} carry {armament, extras}."),
            Sentence(text="{possessive} features include {appendages, sensors}."),
            Sentence(text="{pronoun} show {emitters, aperture}."),
        ),
        **_THEY,
    ),
    # A person. Build is in the form, so scale is omitted, like sci-fi's figure.
    "figure": Archetype(
        head_phrase=_SELF_NAMING_HEAD,
        omits=frozenset({"scale"}),
        detail_cap=10,
        templates={"material": "{a_value}"},
        detail_priority=("form", "subkind", "material", "primary_color", "armament", "appendages",
                         "markings"),
        detail_rotation_slots=2,
        detail_rotation={"extras": 1.0, "emitters": 0.8, "accent_color": 0.6, "surface_detail": 0.5,
                         "aperture": 0.5, "sensors": 0.5},
        sentences=(
            Sentence(text="{subject} {copula} {situation}."),
            Sentence(text="{subject}."),
            Sentence(text="{pronoun} have {form} and wear {material}."),
            Sentence(text="{pronoun} wear {material}."),
            Sentence(text="{pronoun} have {form}."),
            Sentence(text="{possessive} garb is {primary_color}."),
            Sentence(text="{pronoun} show {surface_detail}."),
            Sentence(text="{possessive} gear bears {markings, accent_color}."),
            Sentence(text="{pronoun} carry {armament, extras}."),
            Sentence(text="{pronoun} wear {appendages}."),
            Sentence(text="{possessive} features include {sensors}."),
            Sentence(text="{pronoun} show {emitters, aperture}."),
        ),
        **_THEY,
    ),
    # An elemental, a wisp, a wraith: a shape made of a substance, nothing carried.
    "spirit": Archetype(
        head_phrase=_SELF_NAMING_HEAD,
        omits=frozenset({"armament", "sensors", "aperture", "extras"}),
        detail_cap=10,
        detail_priority=("form", "subkind", "material", "primary_color", "emitters", "appendages"),
        detail_rotation_slots=1,
        detail_rotation={"markings": 1.0, "surface_detail": 0.8, "accent_color": 0.3},
        sentences=(
            Sentence(text="{subject} {copula} {situation}."),
            Sentence(text="{subject}."),
            Sentence(text="{pronoun} takes {form}[, made of {material}]."),
            Sentence(text="{pronoun} {pronoun_copula} made of {material}."),
            Sentence(text="{pronoun} {pronoun_copula} {primary_color}."),
            Sentence(text="{pronoun} shows {surface_detail}."),
            Sentence(text="{pronoun} bears {appendages, emitters}."),
            Sentence(text="{pronoun} {pronoun_copula} marked with {markings, accent_color}."),
        ),
    ),
    # A walking corpse: a frame clad in what it was buried in.
    "undead": Archetype(
        head_phrase=_SELF_NAMING_HEAD,
        detail_cap=11,
        detail_priority=("form", "subkind", "material", "primary_color", "armament", "sensors",
                         "condition", "appendages"),
        detail_rotation_slots=1,
        detail_rotation={"extras": 1.0, "emitters": 1.0, "aperture": 0.8, "markings": 0.6,
                         "surface_detail": 0.6, "accent_color": 0.3},
        sentences=(
            Sentence(text="{subject} {copula} {situation}."),
            Sentence(text="{subject}."),
            Sentence(text="{pronoun} has {form}[, clad in {material}]."),
            Sentence(text="{pronoun} {pronoun_copula} clad in {material}."),
            Sentence(text="{pronoun} {pronoun_copula} {primary_color}."),
            Sentence(text="{pronoun} shows {surface_detail}."),
            Sentence(text="{pronoun} carries {armament, extras}."),
            Sentence(text="{pronoun} features {appendages, sensors}."),
            Sentence(text="{pronoun} bears {emitters, aperture}."),
            Sentence(text="{pronoun} {pronoun_copula} marked with {markings, accent_color}."),
        ),
    ),
    # A golem or a gargoyle: made, not born.
    "construct": Archetype(
        head_phrase=_SELF_NAMING_HEAD,
        detail_cap=11,
        detail_priority=("form", "subkind", "material", "primary_color", "scale", "emitters",
                         "armament", "appendages"),
        detail_rotation_slots=1,
        detail_rotation={"surface_detail": 1.0, "markings": 0.8, "sensors": 0.8, "extras": 0.6,
                         "aperture": 0.5, "accent_color": 0.3},
        sentences=(
            Sentence(text="{subject} {copula} {situation}."),
            Sentence(text="{subject}."),
            Sentence(text="{pronoun} has {form}[, made of {material}]."),
            Sentence(text="{pronoun} {pronoun_copula} made of {material}."),
            Sentence(text="{pronoun} {pronoun_copula} {primary_color}."),
            Sentence(text="{pronoun} shows {surface_detail}."),
            Sentence(text="{pronoun} carries {armament, extras}."),
            Sentence(text="{pronoun} features {appendages, sensors}."),
            Sentence(text="{pronoun} bears {emitters, aperture}."),
            Sentence(text="{pronoun} {pronoun_copula} marked with {markings, accent_color}."),
        ),
    ),
    # A castle or a shrine: a silhouette, built of one stone, and little else.
    "structure": Archetype(
        head_phrase=_SELF_NAMING_HEAD,
        omits=frozenset({"sensors"}),
        detail_cap=8,
        detail_priority=("form", "subkind", "material", "primary_color", "scale", "condition",
                         "appendages"),
        detail_rotation_slots=1,
        detail_rotation={"markings": 1.0, "aperture": 1.0, "surface_detail": 0.8, "extras": 0.6,
                         "emitters": 0.6, "armament": 0.4, "accent_color": 0.3},
        sentences=(
            Sentence(text="{subject} {copula} {situation}."),
            Sentence(text="{subject}."),
            Sentence(text="{pronoun} is built as {form}[, made of {material}]."),
            Sentence(text="{pronoun} is built of {material}."),
            Sentence(text="{possessive} stone is {primary_color}."),
            Sentence(text="{pronoun} shows {surface_detail}."),
            Sentence(text="{pronoun} features {appendages, armament, extras}."),
            Sentence(text="{pronoun} bears {emitters, aperture}."),
            Sentence(text="{pronoun} {pronoun_copula} marked with {markings, accent_color}."),
        ),
    ),
    # A ship, an airship, a wagon.
    "vessel": Archetype(
        head_phrase=_SELF_NAMING_HEAD,
        detail_cap=9,
        detail_priority=("form", "subkind", "material", "primary_color", "appendages", "scale",
                         "condition"),
        detail_rotation_slots=1,
        detail_rotation={"markings": 1.0, "armament": 0.8, "extras": 0.8, "emitters": 0.6,
                         "aperture": 0.5, "sensors": 0.5, "surface_detail": 0.5, "accent_color": 0.3},
        sentences=(
            Sentence(text="{subject} {copula} {situation}."),
            Sentence(text="{subject}."),
            Sentence(text="{pronoun} has {form}[, built of {material}]."),
            Sentence(text="{pronoun} is built of {material}."),
            Sentence(text="{possessive} hull is {primary_color}."),
            Sentence(text="{pronoun} shows {surface_detail}."),
            Sentence(text="{pronoun} features {appendages, sensors}."),
            Sentence(text="{pronoun} carries {armament, extras}."),
            Sentence(text="{pronoun} bears {emitters, aperture}."),
            Sentence(text="{pronoun} {pronoun_copula} marked with {markings, accent_color}."),
        ),
    ),
    # An enchanted object: what it was made from is the subject, and what it rests
    # on keeps it out of the air.
    "object": Archetype(
        head_phrase=_SELF_NAMING_HEAD,
        omits=frozenset({"armament", "sensors"}),
        detail_cap=8,
        detail_priority=("form", "subkind", "material", "extras", "primary_color", "emitters"),
        detail_rotation_slots=1,
        detail_rotation={"surface_detail": 1.0, "markings": 1.0, "aperture": 0.8,
                         "appendages": 0.6, "accent_color": 0.3},
        sentences=(
            Sentence(text="{subject} {copula} {situation}."),
            Sentence(text="{subject}."),
            Sentence(text="{pronoun} takes the form of {form}, made of {material}."),
            Sentence(text="{pronoun} {pronoun_copula} made of {material}."),
            Sentence(text="{pronoun} takes the form of {form}."),
            Sentence(text="{pronoun} rests on {extras}."),
            Sentence(text="{pronoun} {pronoun_copula} {primary_color}."),
            Sentence(text="{pronoun} shows {surface_detail}."),
            Sentence(text="{pronoun} {pronoun_copula} marked with {markings, accent_color}."),
            Sentence(text="{pronoun} bears {emitters, aperture, appendages}."),
        ),
    ),
    # A standing stone, an altar, a portal: a set piece that stands in the scene.
    "monument": Archetype(
        head_phrase=_SELF_NAMING_HEAD,
        omits=frozenset({"armament", "sensors"}),
        detail_cap=8,
        detail_priority=("form", "subkind", "material", "extras", "primary_color", "emitters"),
        detail_rotation_slots=1,
        detail_rotation={"surface_detail": 1.0, "markings": 1.0, "aperture": 0.8,
                         "appendages": 0.6, "accent_color": 0.3},
        sentences=(
            Sentence(text="{subject} {copula} {situation}."),
            Sentence(text="{subject}."),
            Sentence(text="{pronoun} takes the form of {form}, made of {material}."),
            Sentence(text="{pronoun} {pronoun_copula} made of {material}."),
            Sentence(text="{pronoun} takes the form of {form}."),
            Sentence(text="{pronoun} is set amid {extras}."),
            Sentence(text="{pronoun} {pronoun_copula} {primary_color}."),
            Sentence(text="{pronoun} shows {surface_detail}."),
            Sentence(text="{pronoun} {pronoun_copula} marked with {markings, accent_color}."),
            Sentence(text="{pronoun} bears {emitters, aperture, appendages}."),
        ),
    ),
    # The stranger's grammar, for a foreign-genre entity wired into a fantasy scene.
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
    "dragon": "creature", "mythic beast": "creature", "giant-kin": "being", "small folk": "being",
    "hybrid folk": "being", "folk": "figure", "spirit or elemental": "spirit", "undead": "undead",
    "construct": "construct", "structure": "structure", "vessel": "vessel", "artifact": "object",
}
ARCHETYPE_OF_SUBKIND: dict[str, str] = {
    **{v: "brute" for v in SUBKIND_GROUPS["troll"] + SUBKIND_GROUPS["ogre-kin"]},
    **{v: "spirit" for v in SUBKIND_GROUPS["restless spirit"]},
    **{v: "monument" for v in SUBKIND_GROUPS["monument"]},
}


# ---------------------------------------------------------------------------
# Spoken forms, motifs
# ---------------------------------------------------------------------------

def _hyphenated(tokens) -> dict[str, str]:
    return {token: token.replace(" ", "-") for token in tokens if " " in token}


#: A type whose bare name a model draws as something else.
_SPOKEN_SUBKIND: dict[str, str] = {
    "drake": "dragon drake",
    "kelpie": "kelpie water horse",
    "roc": "giant roc bird",
    "phoenix": "phoenix firebird",
    "thunderbird": "giant storm thunderbird",
    "behemoth": "horned behemoth",
    "kraken": "kraken sea monster",
    "hippocamp": "hippocamp sea steed",
    "ettin": "two-headed ettin giant",
    "redcap": "redcap goblin",
    "brownie": "brownie hearth sprite",
    "sprite": "fey sprite",
    "faun": "goat-legged faun",
    "harpy": "winged harpy",
    "selkie": "selkie seal-folk",
    "cloud skiff": "flying cloud skiff",
    "forest gnome": "bearded forest gnome",
}

#: In a fantasy frame a type almost always names its own category ("frost troll",
#: "stone golem"), so the pack says each one as itself unless it is overridden
#: above. Declared for every type, because a type that is never declared is one
#: nobody decided about.
_SPOKEN_SUBKIND = {
    **{value: value for pool in SUBKIND_POOLS.values() for value in pool},
    **_SPOKEN_SUBKIND,
}

SPOKEN: dict[str, dict[str, str]] = {
    "subkind": _SPOKEN_SUBKIND,
    "primary_color": _hyphenated(PRIMARY_COLOR_POOL),
    "accent_color": _hyphenated(ACCENT_COLOR_POOL),
    "emitter_color": _hyphenated(EMITTER_COLOR_POOL),
}

MOTIFS: dict[str, tuple[str, ...]] = {
    "fire": ("flame", "ember", "smoulder", "fire", "molten", "burn"),
    "ice": ("frost", "ice", "snow", "frozen", "rime"),
    "gold": ("gold", "gilded", "jewel"),
    "bone": ("bone", "skull", "grave"),
    "growth": ("moss", "ivy", "vine", "leaf", "bark", "root"),
    "stone": ("stone", "granite", "marble", "basalt"),
}


# ---------------------------------------------------------------------------
# Prose
# ---------------------------------------------------------------------------

PROSE = ProseSpec(
    scene_order=("environment", "entities", "relations"),
    narrative_mode=True,
    environment_sentence="A fantasy scene set in {a_value}",
    environment_staging=(
        ("submerged", ", deep underwater"),
        ("cloud-deck", ", high above the clouds"),
        ("void", ", adrift among the stars"),
    ),
    context_sentences=(
        Sentence(text="Beyond {pronoun_object}, {a_context} is visible."),
        Sentence(text="Behind {pronoun_object} is {a_context}."),
        Sentence(text="{a_context} is visible behind {pronoun_object}."),
        Sentence(text="Past {pronoun_object}, {a_context} catches the light."),
        Sentence(text="The background shows {a_context}."),
        Sentence(text="In the distance, {a_context} is visible.", needs=frozenset({"vast"})),
        Sentence(text="Further back, {a_context} is visible.", needs=frozenset({"vast"})),
        Sentence(text="Far behind {pronoun_object} is {a_context}.", needs=frozenset({"vast"})),
    ),
    scene_frame="A fantasy scene",
    copula="is",
    copula_plural="are",
    pronoun="it",
    pronoun_plural="they",
    descriptor_lead="with",
    entity_sentences=(),
    entity_clause_order=(
        "kind", "subkind", "scale", "condition", "form", "material", "primary_color",
        "accent_color", "surface_detail", "markings", "appendages", "emitters", "armament",
        "sensors", "aperture", "extras",
    ),
    head_phrase={
        POOL_DEFAULT_KEY: HeadPhrase(noun=("subkind", "kind"), modifiers=("scale", "condition")),
    },
    detail_priority=(
        "form", "subkind", "emitters", "primary_color", "condition", "scale", "armament",
        "sensors", "material", "appendages", "aperture", "markings", "surface_detail",
        "accent_color", "extras",
    ),
    adjective_of={"primary_color": ("material", "form")},
    templates={
        ENVIRONMENT_FIELD: "{a_value}",
        SITUATION_FIELD: "{value}",
        RELATION_FIELD: "{first} is {value} {second}",
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


FANTASY_PACK = GenrePack(
    slug="fantasy",
    display="Fantasy",
    class_suffix="Fantasy",
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
    value_tiers={SITUATION_FIELD: SITUATION_TIERS},
    tier_weights=TIER_WEIGHTS,
    trait_conflicts=TRAIT_CONFLICTS,
    trait_reasons=TRAIT_REASONS,
    kind_capabilities=KIND_CAPABILITIES,
    relation_roles=RELATION_ROLES,
    omitted_pools=OMITTED_POOLS,
    shared_vocabulary=SHARED_VOCABULARY,
    distinct_within_entity=DISTINCT_COUNTS,
    pool_groups=POOL_GROUPS,
    value_cardinality=CARDINALITY,
    cardinality_counts=CARDINALITY_COUNTS,
    environment_bands=ENVIRONMENT_BANDS,
    motifs=MOTIFS,
    spoken=SPOKEN,
    foreign_nouns=FOREIGN_NOUNS,
    foreign_noun_fields=FOREIGN_NOUN_FIELDS,
    archetypes=ARCHETYPES,
    archetype_of_kind=ARCHETYPE_OF_KIND,
    archetype_override_field="subkind",
    archetype_of_override=ARCHETYPE_OF_SUBKIND,
    prose=PROSE,
)
