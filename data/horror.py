"""The horror ``GenrePack``.

The third genre, built on the seam sci-fi proved and fantasy reused. Nothing
under ``nodes/`` or ``engine/`` imports it; the repo-root ``__init__.py`` does.

**Same field keys as sci-fi and fantasy, horror labels.** A ``SCENE_ENTITY``
payload is matched to its host scene by field key, so a sci-fi alien wired into a
haunted chapel keeps its whole morphology.

**What this pack carries over, by construction:**

* Coherence is declared, not listed: a place affords, a value needs, a form says
  how it holds itself up, and two facts that cannot both hold are a trait
  conflict. ``engine/`` never learns what a ghoul is.
* Liveness is a **closed list**, and for horror it inverts: a walking corpse is
  live. ``DORMANT_ACTS`` is what a thing at rest can be doing -- a corpse lying
  in its coffin, a doll on its shelf, a house standing silent.
* **Dread is staging, not spectacle.** Stillness is priced higher than in the
  other genres: a figure standing motionless at the end of a hall is the frame.
* **Gore is a filter, off by default.** Graphic values are tagged
  ``conflict_only`` and the node labels the filter "No gore" / "Any" /
  "Gore only", defaulting to "No gore".
* Never negate, never name rendering: "fog", "mist", "shadow", "dim", "at
  night" are the style's words. Darkness is a place fact (``dark``).
* Content guidelines (``docs/genre-roadmap.md``): no real people or tragedies,
  no mental illness as a monster, no living religious or cultural figure as a
  monster, no trademarks, and no child in peril.

Authoring rules are the other packs': bare article-less noun phrases, situations
open with a gerund and are legible in one still frame, and are authored in
buckets that declare tier, tag, needs, stances and liveness once.
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

#: Horror reads close: most things are person-sized, and a few are vast.
SCALE_WEIGHTS: dict[str, float] = {
    "small": 1.0, "large": 1.5, "hulking": 1.0, "towering": 0.8, "gargantuan": 0.4,
}

COUNT_WEIGHTS: dict[str, float] = {
    "a dozen": 0.35, "a cluster of": 0.6,
}

#: A thing at rest is the quiet frame horror is good at; weighted so it stays an
#: occasional one rather than a still life on every seed.
CONDITION_WEIGHTS: dict[str, float] = {
    "entombed": 0.4, "dormant": 0.4, "abandoned": 0.6, "boarded-up": 0.6,
}

KIND_WEIGHTS: dict[str, float] = {
    "undead": 1.3, "spirit": 1.2, "cryptid": 1.2, "eldritch horror": 0.9, "mortal": 1.2,
    "cursed object": 0.6, "haunted place": 0.7,
}


# ---------------------------------------------------------------------------
# The entity fields -- IN WIDGET ORDER. Never reorder; only ever append.
# ---------------------------------------------------------------------------

ENTITY_FIELDS: "OrderedDict[str, FieldSpec]" = OrderedDict([
    ("kind", FieldSpec(
        group=_IDENTITY, label="Kind",
        tooltip="What this entity fundamentally is. Scopes every other field on this slot -- "
                "its options and its labels. Set to None to leave the slot empty.",
        brief=True, scope=(ENVIRONMENT_FIELD,), weights=KIND_WEIGHTS,
    )),
    ("subkind", FieldSpec(
        group=_IDENTITY, label="Type",
        tooltip="The specific type within the kind -- a ghoul, a banshee, a porcelain doll.",
        kind_scoped=True, tag_scoped=True, brief=True,
    )),
    ("scale", FieldSpec(
        group=_IDENTITY, label="Scale",
        tooltip="How big it is relative to a person.",
        brief=True, scope=("subkind", KIND_FIELD), weights=SCALE_WEIGHTS, omission_weight=6.0,
    )),
    ("condition", FieldSpec(
        group=_IDENTITY, label="Condition",
        tooltip="Age, decay and state -- rotting, freshly risen, entombed, boarded-up.",
        brief=True, scope=("subkind", KIND_FIELD), omission_weight=0.8, weights=CONDITION_WEIGHTS,
        tag_scoped=True,
    )),
    ("form", FieldSpec(
        group=_FORM, label="Form",
        tooltip="The silhouette: a gait, a build, a body plan, a building's shape.",
        scope=("subkind", "kind"),
    )),
    ("material", FieldSpec(
        group=_FORM, label="Material",
        tooltip="What it is covered in, made of, or wearing.",
        scope=("subkind", "kind"),
    )),
    ("primary_color", FieldSpec(
        group=_SURFACE, label="Primary colour",
        tooltip="The colour of the thing itself -- skin, robes, wallpaper. Never the lighting.",
        scope=("subkind", KIND_FIELD),
    )),
    ("accent_color", FieldSpec(
        group=_SURFACE, label="Accent colour",
        tooltip="A secondary colour: trim, a stain, a sash.",
    )),
    ("markings", FieldSpec(
        group=_SURFACE, label="Markings",
        tooltip="Scrawled sigils, stains, burn marks. Carries no readable lettering.",
        scope=("subkind", KIND_FIELD),
    )),
    ("surface_detail", FieldSpec(
        group=_SURFACE, label="Surface detail",
        tooltip="Finish and wear at close range -- cracked varnish, grave dirt, wet rot.",
        scope=("subkind", "kind"), tag_scoped=True,
    )),
    ("appendages", FieldSpec(
        group=_COMPONENTS, label="Appendages",
        tooltip="What sticks out: antlers, claws, tendrils, a lantern pole, a chimney.",
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
        tooltip="What shines with its own light: eyes that catch the dark, a lantern, "
                "a cold spectral flame.",
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
        tooltip="The colour of the unnatural light. Belongs to the subject, not the lighting.",
        renders_with="emitters", scope=("subkind", KIND_FIELD),
    )),
    ("armament", FieldSpec(
        group=_COMPONENTS, label="Armament",
        tooltip="Weapons and implements, carried or grown: a cleaver, a sickle, claws.",
        scope=("subkind", KIND_FIELD), tag_scoped=True, count_partner="armament_count",
    )),
    ("armament_count", FieldSpec(
        group=_COMPONENTS, label="Armament count",
        tooltip="How many.",
        scope=("armament", KIND_FIELD), weights=COUNT_WEIGHTS,
        count_partner="armament", renders_with="armament",
    )),
    ("sensors", FieldSpec(
        group=_COMPONENTS, label="Sensors",
        tooltip="How it watches: eyes, too many eyes, a blank stare.",
        scope=("subkind", KIND_FIELD), count_partner="sensor_count",
    )),
    ("sensor_count", FieldSpec(
        group=_COMPONENTS, label="Sensor count",
        tooltip="How many.",
        scope=("sensors", KIND_FIELD), weights=COUNT_WEIGHTS,
        count_partner="sensors", renders_with="sensors",
    )),
    ("aperture", FieldSpec(
        group=_COMPONENTS, label="Aperture",
        tooltip="The opening: a mouth, a mask, a door hanging open.",
        scope=("subkind", "kind"), tag_scoped=True,
    )),
    ("extras", FieldSpec(
        group=_COMPONENTS, label="Extras",
        tooltip="One more distinguishing thing -- a lantern, a satchel, a chain of keys.",
        scope=("subkind", KIND_FIELD),
    )),
])

SCENE_FIELDS: "OrderedDict[str, FieldSpec]" = OrderedDict([
    (ENVIRONMENT_FIELD, FieldSpec(
        group=_SCENE, label="Environment",
        tooltip="Where the scene is: the wilds, a graveyard, the water, a town, a room, "
                "underground, or somewhere that should not exist.",
    )),
    (SITUATION_FIELD, FieldSpec(
        group=_SCENE, label="Situation",
        tooltip="What this entity is doing -- often something very still.",
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
                "dread and story. Always a thing in the world, never a lighting instruction.",
        scope=(ENVIRONMENT_FIELD,), omission_weight=6.0,
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
# Environments -- eight bands
# ---------------------------------------------------------------------------

_ENV_WILDS = (
    "dead forest of bare black trees",
    "overgrown cornfield",
    "bayou swamp",
    "snowbound pine woods",
    "withered apple orchard",
    "windswept moor of standing stones",
    "rocky ravine",
)
_ENV_GRAVES = (
    "overgrown cemetery",
    "sunken churchyard",
    "family burial plot behind a farmhouse",
    "field of crooked grave markers",
)
_ENV_WATERSIDE = (
    "drowned village shoreline",
    "rotting fishing pier",
    "black lake shore",
    "flooded quarry edge",
)
_ENV_UNDERWATER = (
    # "flooded" reads as shallow and walkable, which fights the band's own
    # ", deep underwater" staging suffix -- a diver at knee height and a
    # diver at full submersion are two different images at once.
    "drowned church nave",
    "murky lake bottom",
    "sunken ship hold",
    "frozen lake bed",
)
_ENV_TOWN = (
    "empty small-town main street",
    "abandoned carnival fairground",
    "derelict roadside motel",
    "boarded-up village square",
    "flooded suburban street",
)
_ENV_INTERIOR = (
    "hospital corridor after closing",
    "flooded cellar",
    "attic crawlspace",
    "abandoned chapel",
    "basement boiler room",
    "hospital morgue",
    "taxidermy parlour",
    "dusty manor ballroom",
    "peeling hotel hallway",
    "farmhouse kitchen",
)
_ENV_UNDERGROUND = (
    "catacomb ossuary",
    "brick sewer tunnel",
    "collapsed mine shaft",
    "crypt beneath a chapel",
    "cave strewn with bones",
)
_ENV_OTHERWORLD = (
    "endless crimson hallway",
    "void of drifting furniture",
    "flesh-walled chamber",
)

ENVIRONMENT_POOL: tuple[str, ...] = (
    _ENV_WILDS + _ENV_GRAVES + _ENV_WATERSIDE + _ENV_UNDERWATER + _ENV_TOWN + _ENV_INTERIOR
    + _ENV_UNDERGROUND + _ENV_OTHERWORLD
)

ENVIRONMENT_BANDS: dict[str, tuple[str, ...]] = {
    "wilds": _ENV_WILDS,
    "graveyard": _ENV_GRAVES,
    "waterside": _ENV_WATERSIDE,
    "underwater": _ENV_UNDERWATER,
    "town": _ENV_TOWN,
    "interior": _ENV_INTERIOR,
    "underground": _ENV_UNDERGROUND,
    "otherworld": _ENV_OTHERWORLD,
}

#: What else is in the shot, keyed by band or by place (a place key wins).
CONTEXT_POOLS: dict[str, tuple[str, ...]] = {
    "wilds": (
        "abandoned car rusting in the weeds", "ring of stacked stones",
        "scarecrow on a leaning post", "hunting cabin with a sagging roof",
        "trail of torn clothing through the brush", "rusted barbed-wire fence",
    ),
    "graveyard": (
        "row of leaning headstones", "open grave with a spade beside it",
        "stone angel with a broken wing", "rusted iron cemetery gate",
        "crumbling family mausoleum",
    ),
    "waterside": (
        "overturned rowing boat on the bank", "line of rotting pilings",
        "church steeple jutting from the water", "tangle of drowned tree roots",
    ),
    "underwater": (
        "drifting pews", "sunken rowing boat", "tangle of drowned tree roots",
        "scatter of old bones in the silt",
    ),
    "town": (
        "row of boarded-up shopfronts", "abandoned bicycle on its side",
        "flickering motel sign", "shuttered gas station", "empty playground swing set",
    ),
    "abandoned carnival fairground": (
        "rusted carousel of wooden horses", "collapsed striped tent", "stalled ferris wheel",
    ),
    "interior": (
        "door standing ajar at the end of the room", "overturned chair",
        "wall scrawled with sigils", "row of dusty framed pictures", "cracked mirror on the wall",
    ),
    "hospital corridor after closing": (
        "abandoned gurney", "row of swinging double doors", "wheelchair facing the wall",
    ),
    "hospital morgue": (
        "row of steel cold-storage doors", "sheeted body on a steel table",
    ),
    "taxidermy parlour": (
        "wall of mounted animal heads", "workbench of glass eyes and wire",
    ),
    "farmhouse kitchen": (
        "table laid for a meal nobody finished", "row of jars on a crooked shelf",
    ),
    "underground": (
        "heap of stacked skulls", "rusted grate in the floor", "row of stone coffins",
        "trickle of black seepage",
    ),
    "brick sewer tunnel": (
        "rusted grate in the floor", "trickle of black seepage", "rusted access ladder",
    ),
    "otherworld": (
        "door standing open onto nothing", "staircase that ends in midair",
        "row of identical doors",
    ),
}


# ---------------------------------------------------------------------------
# Kinds and types
# ---------------------------------------------------------------------------

KINDS: tuple[str, ...] = (
    "undead",
    "spirit",
    "cryptid",
    "eldritch horror",
    "mortal",
    "cursed object",
    "haunted place",
)

#: A cursed object belongs in a room or a tomb, a haunted place under open sky.
KIND_POOLS: dict[str, tuple[str, ...]] = {
    POOL_DEFAULT_KEY: KINDS,
    "wilds": ("undead", "spirit", "cryptid", "eldritch horror", "mortal", "haunted place"),
    "graveyard": ("undead", "spirit", "cryptid", "mortal", "haunted place"),
    "waterside": ("undead", "spirit", "cryptid", "eldritch horror", "mortal", "haunted place"),
    "underwater": ("undead", "spirit", "eldritch horror", "cursed object"),
    "town": ("undead", "spirit", "cryptid", "mortal", "haunted place"),
    "interior": ("undead", "spirit", "cryptid", "eldritch horror", "mortal", "cursed object"),
    "underground": ("undead", "spirit", "cryptid", "eldritch horror", "mortal", "cursed object"),
    "otherworld": ("spirit", "eldritch horror", "mortal", "cursed object"),
    "rotting fishing pier": ("undead", "spirit", "cryptid", "eldritch horror", "mortal"),
}

SUBKIND_GROUPS: dict[str, tuple[str, ...]] = {
    # undead
    "rotting dead": ("zombie", "ghoul", "plague corpse", "bog body"),
    "bloodsucker": ("vampire", "vampire thrall"),
    "skeletal dead": ("walking skeleton", "bone revenant"),
    "drowned dead": ("drowned revenant", "waterlogged corpse"),
    # spirit
    "apparition": ("ghost", "spectral bride", "weeping apparition", "blank-faced apparition"),
    "wrathful spirit": ("wraith", "banshee", "poltergeist", "shade spirit"),
    # cryptid
    "cursed beast": ("werewolf", "hellish black hound", "bog lurker"),
    "watcher": ("antlered stalker", "moth-winged watcher", "hollow-eyed stag"),
    "crawler": ("pale crawler", "blind cave thing"),
    "effigy": ("living scarecrow", "stitched straw man"),
    # eldritch horror
    "tentacled horror": ("tentacled abomination", "thing beneath the ice"),
    "many-eyed horror": ("many-eyed abomination", "pulsing flesh mass"),
    "amalgam": ("flesh-knit amalgam", "bone-and-sinew colossus"),
    # mortal
    "cult": ("hooded cultist", "cult high priest", "possessed villager"),
    "stalker": ("masked stalker", "hooded executioner", "grave robber"),
    "occultist": ("plague doctor", "bog witch", "occult scholar"),
    "survivor": ("lone survivor", "paranormal investigator", "lantern-bearing warden",
                 "village priest"),
    # cursed object
    "keepsake": ("porcelain doll", "music box", "spirit board", "puzzle box",
                 "ventriloquist dummy"),
    "furnishing": ("cracked mirror", "haunted family picture", "antique rocking chair",
                   "grandfather clock"),
    # haunted place
    "dwelling": ("abandoned farmhouse", "gothic manor", "isolated cabin", "derelict motel"),
    "sacred ruin": ("ruined chapel", "family mausoleum", "boarded-up church"),
    "attraction": ("rusted carnival ride", "derelict funhouse"),
    "landmark": ("lonely lighthouse", "rotting windmill", "rusted water tower"),
}

SUBKIND_POOLS: dict[str, tuple[str, ...]] = {
    "undead": SUBKIND_GROUPS["rotting dead"] + SUBKIND_GROUPS["bloodsucker"]
    + SUBKIND_GROUPS["skeletal dead"] + SUBKIND_GROUPS["drowned dead"],
    "spirit": SUBKIND_GROUPS["apparition"] + SUBKIND_GROUPS["wrathful spirit"],
    "cryptid": SUBKIND_GROUPS["cursed beast"] + SUBKIND_GROUPS["watcher"]
    + SUBKIND_GROUPS["crawler"] + SUBKIND_GROUPS["effigy"],
    "eldritch horror": SUBKIND_GROUPS["tentacled horror"] + SUBKIND_GROUPS["many-eyed horror"]
    + SUBKIND_GROUPS["amalgam"],
    "mortal": SUBKIND_GROUPS["cult"] + SUBKIND_GROUPS["stalker"] + SUBKIND_GROUPS["occultist"]
    + SUBKIND_GROUPS["survivor"],
    "cursed object": SUBKIND_GROUPS["keepsake"] + SUBKIND_GROUPS["furnishing"],
    "haunted place": SUBKIND_GROUPS["dwelling"] + SUBKIND_GROUPS["sacred ruin"]
    + SUBKIND_GROUPS["attraction"] + SUBKIND_GROUPS["landmark"],
}


# ---------------------------------------------------------------------------
# Form, material and colour
# ---------------------------------------------------------------------------

FORM_POOLS: dict[str, tuple[str, ...]] = {
    #: The stranger's forms: only a foreign-genre kind reaches these.
    POOL_DEFAULT_KEY: ("hunched body", "gaunt body", "sprawling body"),
    # undead
    "rotting dead": ("shambling stiff-legged frame", "hunched emaciated frame",
                     "bloated lurching frame", "crawling broken frame"),
    "bog body": ("shrivelled leathery frame", "peat-stained crouching frame"),
    "bloodsucker": ("tall gaunt aristocratic frame", "lean predatory frame",
                    "hunched rat-like frame"),
    "skeletal dead": ("rattling bare-boned frame", "tall armoured bone frame"),
    "drowned dead": ("swollen dripping frame", "weed-draped stooped frame"),
    # spirit
    "apparition": ("translucent drifting figure", "veiled floating figure",
                   "half-seen translucent figure", "slender figure with long lank hair"),
    "wrathful spirit": ("tattered billowing shape", "long-limbed contorted shape",
                        "hooded drifting shape", "figure bent backwards at the waist"),
    # cryptid
    "werewolf": ("hulking wolf-headed body", "lean digitigrade wolf body"),
    "hellish black hound": ("gaunt shaggy hound body", "broad-chested hound body"),
    "bog lurker": ("long-armed hunched body", "slick crouching body"),
    "watcher": ("impossibly tall thin body", "long-limbed crouching body"),
    "moth-winged watcher": ("tall body with folded moth wings", "hunched body with vast moth wings"),
    "hollow-eyed stag": ("emaciated stag body", "towering skeletal stag body"),
    "crawler": ("pale long-limbed crawling body", "spindly backwards-bent body"),
    "effigy": ("sagging stuffed body on a post", "lanky stitched body"),
    # eldritch horror
    # "tentacle-topped" drew an octopus head on a body.
    "tentacled horror": ("writhing tentacled mass", "hunched many-limbed body trailing tentacles",
                         "vast slug-like body ringed with tentacles"),
    "many-eyed horror": ("bulging eye-studded mound", "quivering heap of eye-studded flesh"),
    # A lump with one eye doing nothing readable: the abomination has a body.
    "many-eyed abomination": ("hunched spider-limbed body studded with eyes",
                              "tall stooped body covered in blinking eyes"),
    "amalgam": ("lurching body of fused limbs", "towering knot of bone and sinew"),
    # mortal
    "mortal": ("tall lean build", "heavy-set build", "wiry build", "stooped build"),
    "possessed villager": ("rigid contorted build", "stooped twitching build"),
    # cursed object
    "porcelain doll": ("seated figure with a cracked face", "standing figure in a lace dress"),
    "music box": ("carved casket with a tiny dancer", "lacquered case with a winding key"),
    "spirit board": ("lettered panel with a heart-shaped planchette",
                     "carved plaque with a brass planchette"),
    "puzzle box": ("ornate cube of sliding panels", "brass-bound cube"),
    "ventriloquist dummy": ("slumped figure with a hinged jaw", "seated figure in a tiny suit"),
    "cracked mirror": ("tall glass in a gilded frame", "oval glass on a stand"),
    "haunted family picture": ("life-sized likeness in a heavy frame",
                               "small oval likeness in a gilt frame"),
    "antique rocking chair": ("high-backed rocker", "spindle-backed rocker"),
    "grandfather clock": ("tall narrow wooden case", "carved case with a brass pendulum"),
    # haunted place
    "abandoned farmhouse": ("two-storey clapboard house", "sagging house with a deep porch"),
    "gothic manor": ("turreted gothic mansion", "sprawling many-gabled mansion"),
    "isolated cabin": ("log house with a stone chimney", "tin-roofed shack"),
    "derelict motel": ("single-storey row of motel rooms", "two-storey block with an open walkway"),
    "ruined chapel": ("roofless stone nave", "stone shell with a collapsed roof"),
    "family mausoleum": ("squat stone tomb with iron doors", "columned marble tomb"),
    "boarded-up church": ("steepled wooden meeting house", "brick hall with a squat tower"),
    "rusted carnival ride": ("rusted swing carousel on a steel frame", "stalled ferris wheel on a steel frame"),
    "derelict funhouse": ("garish funhouse facade", "clown-faced funhouse front"),
    "lonely lighthouse": ("tall white tower on the rocks", "squat stone light tower"),
    "rotting windmill": ("timber mill tower with broken sails", "stone windmill tower"),
    "rusted water tower": ("bulbous tank on stilt legs", "tall cylindrical tank on a frame"),
}

MATERIAL_POOLS: dict[str, tuple[str, ...]] = {
    POOL_DEFAULT_KEY: ("mottled hide", "rough cloth", "weathered wood", "cold iron"),
    # undead
    "rotting dead": ("tattered burial clothes", "grave-soiled suit", "torn hospital gown",
                     "mud-caked work clothes"),
    "bog body": ("tanned leathery skin", "peat-blackened hide"),
    "bloodsucker": ("velvet frock coat", "high-collared cloak", "moth-eaten evening gown"),
    "skeletal dead": ("yellowed bone", "rusted chainmail over bone"),
    "drowned dead": ("sodden sailcloth rags", "waterlogged woollen coat"),
    # spirit
    "apparition": ("translucent wedding veil", "pale burial shroud", "grey drifting gauze",
                   "faded mourning dress"),
    "wrathful spirit": ("tattered shroud", "smoke-like drifting rags", "soot-stained wedding dress",
                        "torn mourning dress"),
    # cryptid
    "cursed beast": ("matted shaggy fur", "coarse grey pelt", "slick mottled skin"),
    "watcher": ("grey bark-like hide", "dusty moth-scaled skin", "patchy rotting hide"),
    "crawler": ("waxy pale skin", "translucent clammy skin"),
    "effigy": ("rotting burlap and straw", "stitched sackcloth"),
    # eldritch horror
    "eldritch horror": ("glistening grey flesh", "rubbery mottled hide", "pulsing raw sinew"),
    # mortal
    "cult": ("hooded ritual robe", "rough brown habit", "bloodstained work apron"),
    "stalker": ("long oilskin coat", "grimy overalls", "heavy leather apron"),
    "occultist": ("layered shawls and skirts", "worn tweed coat", "moth-eaten velvet robe"),
    "plague doctor": ("waxed leather coat", "long oilcloth robe"),
    "survivor": ("torn flannel shirt", "rain-soaked trench coat", "muddy field jacket",
                 "quilted work jacket"),
    "village priest": ("clerical collar and long coat", "rain-soaked cassock"),
    # cursed object
    "keepsake": ("chipped porcelain", "cracked lacquered wood", "tarnished brass",
                 "yellowed bone china"),
    "furnishing": ("worm-eaten oak", "cracked lacquered wood", "tarnished brass", "flaking gilt wood"),
    # haunted place
    "dwelling": ("weathered clapboard", "blackened brick", "rotting timber", "moss-streaked stone"),
    "sacred ruin": ("moss-streaked stone", "blackened brick", "weathered marble", "rotting timber"),
    "attraction": ("rust-streaked steel", "peeling painted plywood"),
    "landmark": ("weathered clapboard", "rust-streaked steel", "moss-streaked stone"),
}

_COLOR_SKIN = ("grey-green", "corpse grey", "bruised purple", "jaundiced yellow", "waxen white",
               "mottled brown")
_COLOR_GARB = ("black", "funeral grey", "faded crimson", "yellowed ivory", "drab brown",
               "bottle green", "oxblood")
_COLOR_SPIRIT = ("pale grey", "sickly green", "bone white", "cold blue", "ash grey")
_COLOR_BUILT = ("peeling white", "soot black", "faded red", "weathered grey", "rust brown")

PRIMARY_COLOR_POOLS: dict[str, tuple[str, ...]] = {
    POOL_DEFAULT_KEY: _COLOR_GARB,
    "undead": _COLOR_SKIN,
    "bog body": ("peat brown", "dark umber", "blackened brown"),
    "spirit": _COLOR_SPIRIT,
    "cryptid": ("pitch black", "ash grey", "drab brown", "waxen white", "mottled brown"),
    "crawler": ("waxen white", "corpse grey", "ash grey"),
    "eldritch horror": ("bruised purple", "slate grey", "sickly green", "raw red", "pallid pink"),
    "mortal": _COLOR_GARB,
    "cursed object": ("yellowed ivory", "black", "faded crimson", "tarnished gold", "faded rose"),
    "haunted place": _COLOR_BUILT,
}
PRIMARY_COLOR_POOL: tuple[str, ...] = tuple(
    dict.fromkeys(v for pool in PRIMARY_COLOR_POOLS.values() for v in pool)
)
ACCENT_COLOR_POOL: tuple[str, ...] = (
    "dark maroon", "tarnished silver", "black", "bone white", "rust orange", "funeral purple",
    "verdigris green", "faded gold", "sickly yellow",
)
EMITTER_COLOR_POOL: tuple[str, ...] = (
    "cold white", "sickly green", "dull red", "pale blue", "warm amber", "violet",
)
EMITTER_COLOR_POOLS: dict[str, tuple[str, ...]] = {
    POOL_DEFAULT_KEY: EMITTER_COLOR_POOL,
    # A colour and its emitter are drawn independently, so "lantern amber"
    # still collided even here: it landed on "guttering candle" as often as
    # on "hooded lantern", and a mortal figure grew a second, literal lantern
    # object instead of a candle glowing amber. "warm amber" is safe with
    # any of the three mortal emitters.
    "mortal": ("warm amber", "cold white"),
}


# ---------------------------------------------------------------------------
# Markings and surface detail
# ---------------------------------------------------------------------------

MARKINGS_POOLS: dict[str, tuple[str, ...]] = {
    POOL_DEFAULT_KEY: ("scratched sigils", "water stains", "scorch marks"),
    "undead": ("grave-dirt streaks", "blackened veins", "old stitched scars"),
    "skeletal dead": ("grave-dirt streaks", "scratched sigils", "rust stains"),
    "spirit": ("drifting ripples", "faint water stains"),
    "cryptid": ("pale scar patches", "mud-caked streaks", "patchy dark mottling"),
    "cursed beast": ("pale scar patches", "bristling ridges of fur", "mud-caked streaks"),
    "effigy": ("crude stitching", "faded paint smears"),
    "eldritch horror": ("pulsing vein patterning", "clustered warty growths"),
    "mortal": ("painted ritual sigils", "sewn-on bone charms", "mud-spattered hems"),
    "cursed object": ("scratched sigils", "faded painted flowers", "tiny bite marks"),
    "furnishing": ("scratched sigils", "scorch marks", "crazed gilding"),
    "haunted place": ("scrawled warning sigils", "water stains", "scorch marks",
                      "boarded-over windows"),
}

SURFACE_DETAIL_POOLS: dict[str, tuple[str, ...]] = {
    POOL_DEFAULT_KEY: ("cracked finish", "thick dust"),
    "undead": ("grave dirt in every crease", "split grey skin", "clumps of wet earth",
               "dripping fresh blood", "exposed ribs", "torn-open gut wound",
               "glistening exposed muscle"),
    "skeletal dead": ("cobwebbed joints", "cracked yellowed bone", "clinging grave dirt"),
    "spirit": ("frayed translucent edges", "slowly dripping water"),
    "cryptid": ("old gouged scars", "cracked peeling skin", "caked dried mud",
                "fresh claw-mark gashes"),
    "cursed beast": ("burrs matted into the fur", "old gouged scars", "blood-matted fur around the muzzle"),
    "effigy": ("straw poking through the seams", "crow-pecked burlap"),
    "eldritch horror": ("glistening slime", "weeping sores", "barnacle-like growths",
                        "raw weeping flesh"),
    "mortal": ("mud-caked boots", "rain-soaked clothing", "torn sleeves", "blood-spattered sleeves"),
    "cursed object": ("crazed varnish", "thick dust", "hairline cracks", "faded gilt edges"),
    "haunted place": ("peeling paint", "sagging gutters", "shattered windows", "creeping black mould"),
}


# ---------------------------------------------------------------------------
# Components
# ---------------------------------------------------------------------------

APPENDAGE_POOLS: dict[str, tuple[str, ...]] = {
    POOL_DEFAULT_KEY: ("twisted spike", "trailing strip of cloth"),
    # undead
    "rotting dead": ("dangling jaw", "grasping hand", "dragging foot"),
    "bloodsucker": ("long clawed hand", "high cape collar", "pointed ear"),
    "skeletal dead": ("bony hand", "rusted helm"),
    "drowned dead": ("weed-tangled hand", "trailing strand of weed"),
    # spirit
    "apparition": ("long trailing veil", "outstretched hand"),
    "wrathful spirit": ("trailing tatter", "long grasping hand"),
    # cryptid
    "werewolf": ("pointed wolf ear", "hooked claw hand", "bristling tail"),
    "hellish black hound": ("ragged ear", "whip-thin tail"),
    "bog lurker": ("webbed claw hand", "dripping fin crest"),
    "watcher": ("branching antler", "long spindly finger"),
    "moth-winged watcher": ("dusty moth wing", "feathery antenna"),
    "hollow-eyed stag": ("branching antler",),
    "crawler": ("long spindly finger", "backwards-bent knee"),
    "effigy": ("straw-stuffed arm", "tattered hat"),
    # eldritch horror
    "tentacled horror": ("sucker-lined tentacle", "barbed tentacle"),
    "many-eyed horror": ("groping tendril", "fleshy stalk"),
    "amalgam": ("fused extra arm", "jutting rib"),
    # mortal
    "mortal": ("hooded mantle", "long leather glove", "wide-brimmed hat"),
    "survivor": ("battered backpack", "knitted scarf", "wide-brimmed hat"),
    "cult": ("deep hood", "ritual stole"),
    # cursed object
    # A pendulum is a clock's, a winding key a music box's, a finial not a box's.
    "cursed object": ("tarnished brass clasp", "inlaid bone panel"),
    "music box": ("brass winding key", "tiny dancing figure"),
    "porcelain doll": ("lace bonnet", "ribbon sash"),
    "ventriloquist dummy": ("tiny bow tie", "painted wooden hand"),
    "furnishing": ("carved finial", "gilded crest"),
    "grandfather clock": ("brass pendulum", "carved finial"),
    # haunted place
    "dwelling": ("sagging porch", "crooked chimney", "broken shutter", "weathervane"),
    "sacred ruin": ("leaning stone cross", "crumbling spire", "iron-barred gate"),
    "rusted carnival ride": ("rusted arm of gondolas", "peeling painted clown face"),
    "derelict funhouse": ("peeling painted clown face", "cracked plaster clown statue"),
    # "broken sail" is a windmill part; the bare "landmark" kind key used to
    # cover all three landmark subkinds, so a lighthouse and a water tower
    # grew sails too (round-xvi's kind-level-pool-is-a-trap shape).
    "lonely lighthouse": ("rusted access ladder", "cracked lamp-room glass"),
    "rotting windmill": ("rusted access ladder", "broken sail"),
    "rusted water tower": ("rusted access ladder", "corroded support strut"),
}

EMITTER_POOLS: dict[str, tuple[str, ...]] = {
    # An unlocated glow and a mouth/aperture, spoken in their own sentences
    # since round XVIII, still read as one thing when a diffusion model
    # attends across the whole prompt rather than sentence by sentence -- a
    # flesh mass's "pulsing inner light" (meant as a body glow) kept drawing
    # as light spilling from its "ring-shaped toothed maw" instead. Anchored
    # to a place on the body other than the face so the two no longer share
    # a location for the model to merge.
    POOL_DEFAULT_KEY: ("pinprick eye", "spectral flame in its chest"),
    "undead": ("reflective eye", "sunken pinprick eye"),
    "spirit": ("inner light in its chest", "luminous shimmer", "light behind its eyes",
               "hollow burning eye"),
    "cryptid": ("reflective eye", "burning eye"),
    "eldritch horror": ("luminous vein along its flank", "luminous pustule on its flank"),
    # A hands-free light: with only hand-held ones a two-handed shotgun or
    # fire axe could never be drawn beside them.
    "mortal": ("hooded lantern", "guttering candle", "handheld torch beam", "headlamp"),
    # The warden's lantern is in the name; a second light was held awkwardly.
    "lantern-bearing warden": ("headlamp",),
    "cursed object": ("faint inner light",),
    "porcelain doll": ("faint inner light", "shining painted eye"),
    "ventriloquist dummy": ("faint inner light", "shining painted eye"),
    # A doll's or a dummy's face carries painted eyes; a chair, a clock or a
    # mirror is not a face and should not grow one by falling through to the
    # kind-level pool above.
    "furnishing": ("faint inner light",),
    "haunted place": ("lamp in an upstairs window", "flickering porch lamp"),
    "attraction": ("string of bare bulbs", "flickering marquee light"),
}

ARMAMENT_POOLS: dict[str, tuple[str, ...]] = {
    POOL_DEFAULT_KEY: ("rusted blade", "iron hook"),
    "undead": ("rusted meat hook", "broken shovel"),
    "rotting dead": (),
    "bloodsucker": ("ornate dagger",),
    "skeletal dead": ("rusted sword", "notched axe"),
    "spirit": (),
    "cryptid": ("hooked claw", "yellowed fang"),
    "effigy": ("rusted sickle", "pitchfork"),
    "hollow-eyed stag": ("jagged antler tine",),
    "eldritch horror": ("barbed stinger", "hooked talon"),
    "cult": ("ritual dagger", "curved sacrificial knife", "rusted cleaver"),
    "stalker": ("butcher's cleaver", "wood axe", "rusted machete", "iron chain whip", "sickle",
               "gore-slicked axe"),
    "occultist": ("curved skinning knife", "iron cane"),
    "survivor": ("fire axe", "shotgun", "iron crowbar", "wooden stake"),
    "village priest": ("silver crucifix", "wooden stake"),
    "cursed object": (),
    "haunted place": (),
}

SENSOR_POOLS: dict[str, tuple[str, ...]] = {
    POOL_DEFAULT_KEY: ("staring eye",),
    "undead": ("milky dead eye", "sunken eye"),
    "bloodsucker": ("unblinking red-rimmed eye", "cold pale eye"),
    "spirit": ("hollow black eye", "sorrowful eye", "clouded white eye"),
    "cryptid": ("flared sniffing nostril", "twitching tall ear"),
    # An effigy's eyes are its glowing emitter; a hare's ears were drawn on a straw man.
    "effigy": (),
    "eldritch horror": ("bulging eye", "wet black eye"),
    "mortal": ("wide staring eye", "dark-circled sleepless eye"),
    # "eye behind a mask" put a mask on an investigator.
    "stalker": ("wide staring eye", "eye behind a mask"),
    "cult": ("wide staring eye", "eye behind a mask"),
    # Eyes are a doll's and a dummy's; a puzzle box grew painted ones.
    "keepsake": (),
    "porcelain doll": ("painted glass eye", "watching painted eye"),
    "ventriloquist dummy": ("painted glass eye", "watching painted eye"),
    "furnishing": (),
    "haunted family picture": ("watching painted eye",),
    "haunted place": (),
}

APERTURE_POOLS: dict[str, tuple[str, ...]] = {
    POOL_DEFAULT_KEY: ("gaping mouth", "hinged lid"),
    "undead": ("slack gaping jaw", "lipless grin", "blood-smeared mouth", "gore-clotted maw"),
    "bloodsucker": ("fanged smile", "blood-smeared mouth"),
    # A veiled face cannot stare ("watching with an unblinking stare ... veiled face").
    "spirit": ("silently screaming mouth", "gaping black mouth", "stitched-shut mouth"),
    "cryptid": ("wide lipless mouth", "needle-toothed mouth"),
    "cursed beast": ("snarling muzzle", "wide lipless mouth"),
    "eldritch horror": ("ring-shaped toothed maw", "vertical slit mouth"),
    "mortal": ("gaunt hollow-cheeked face", "hood pulled low over the face"),
    "cult": ("hood pulled low over the face", "painted bone mask"),
    "possessed villager": ("slack twisted grin", "cracked bleeding lips"),
    # A stalker is masked; a bare face beside "masked stalker" contradicted it.
    "stalker": ("blank white mask", "burlap sack mask", "hood pulled low over the face"),
    "occultist": ("veiled face", "gaunt hollow-cheeked face"),
    "plague doctor": ("beaked plague mask",),
    "survivor": ("frightened face", "grim determined face"),
    "cursed object": ("hinged lid",),
    "porcelain doll": ("tiny painted mouth",),
    "ventriloquist dummy": ("hinged painted jaw",),
    "furnishing": ("glass door hanging open", "cracked glass front"),
    "antique rocking chair": ("worn wicker seat",),
    "haunted place": ("front door hanging open", "cellar door", "gaping broken window"),
    "attraction": ("boarded-up entrance", "gaping clown-mouth entrance"),
}

EXTRAS_POOLS: dict[str, tuple[str, ...]] = {
    POOL_DEFAULT_KEY: ("iron key", "tattered ribbon"),
    # "hospital identity band" used to sit here and reach every undead -- a
    # medieval catacomb dweller, a bog body, a drowned sailor -- asserting a
    # specific modern-hospital backstory none of those places support. No
    # context/era token exists to re-scope it safely, so it is dropped and
    # replaced in kind, not merely removed.
    "undead": ("tarnished signet ring", "scrap of burial linen", "tangle of grave roots",
               "rusted shackle"),
    "spirit": ("wilted bouquet", "tarnished locket"),
    "cryptid": ("tangle of snagged cloth", "trail of muddy prints"),
    "cursed beast": ("broken chain collar", "tangle of snagged cloth"),
    "eldritch horror": ("trail of glistening slime", "cluster of clinging barnacles"),
    "mortal": ("ring of old iron keys", "coil of wire", "leather satchel", "burlap sack"),
    "survivor": ("flashlight", "bolt-action hunting rifle", "first aid kit", "crumpled map"),
    "occultist": ("leather-bound grimoire", "bundle of dried herbs", "bird skull charm"),
    # "velvet-lined case" and its furnished siblings used to reach an object
    # in a reed marsh or on the floor of a drowned church -- gated below to
    # an indoor, dry place (VALUE_NEEDS). "dusty ledge" is the outdoor
    # place-neutral surface, gated to air only -- dust does not settle
    # underwater, and a spirit board on a "dusty ledge" in a drowned nave
    # rendered as a bone-dry room with no water in it at all. "silt-caked
    # ledge" is the submerged equivalent.
    "cursed object": ("velvet-lined case", "dusty shelf", "carved side table", "child-sized chair",
                      "dusty ledge", "silt-caked ledge"),
    "furnishing": ("peeling floral wallpaper", "wall of stained plaster", "wall of warped panelling"),
    "haunted place": ("overgrown garden gate", "crooked picket fence", "tangle of dead rose bushes"),
    "dwelling": ("rusted swing on the porch", "overgrown garden gate", "crooked picket fence"),
}

OMITTED_POOLS: frozenset[tuple[str, str]] = frozenset({
    ("armament", "rotting dead"), ("armament", "spirit"), ("armament", "cursed object"),
    ("armament", "haunted place"), ("sensors", "haunted place"), ("sensors", "furnishing"),
    ("sensors", "keepsake"), ("sensors", "effigy"),
})


# ---------------------------------------------------------------------------
# Condition and scale
# ---------------------------------------------------------------------------

CONDITION_POOLS: dict[str, tuple[str, ...]] = {
    POOL_DEFAULT_KEY: ("weathered", "ancient", "filthy"),
    "undead": ("freshly risen", "rotting", "desiccated", "bloated", "grave-soiled", "entombed",
               "blood-soaked"),
    "skeletal dead": ("ancient", "cobwebbed", "grave-soiled", "entombed"),
    "bog body": ("desiccated", "grave-soiled", "entombed", "ancient"),
    "bloodsucker": ("ancient", "gaunt", "pallid", "blood-soaked", "entombed"),
    "spirit": ("sorrowful", "wrathful", "ancient", "restless"),
    "cryptid": ("starving", "wounded", "ancient", "blood-soaked", "mangy"),
    # Straw is not wounded or starving.
    "effigy": ("ancient", "weathered", "filthy"),
    "eldritch horror": ("newly awakened", "ancient", "writhing", "slumbering"),
    "mortal": ("exhausted", "wild-eyed", "wounded", "grim", "blood-soaked", "rain-soaked"),
    "survivor": ("exhausted", "wild-eyed", "wounded", "grim", "rain-soaked"),
    # "water-stained" rendered as literal water dripping off a dry chair --
    # the same substance-word-collision class as "forked"/"furled".
    "cursed object": ("antique", "cracked", "damp-blotched", "scorched", "dormant"),
    "haunted place": ("abandoned", "boarded-up", "burnt-out", "overgrown", "sagging"),
}

SCALE_POOLS: dict[str, tuple[str, ...]] = {
    POOL_DEFAULT_KEY: ("small", "large"),
    "undead": ("small", "large"),
    "spirit": ("small", "large", "towering"),
    "cryptid": ("small", "large", "hulking", "towering"),
    "eldritch horror": ("hulking", "towering", "gargantuan"),
    "mortal": ("small", "large", "hulking"),
    "cursed object": ("small", "large"),
    "haunted place": ("small", "large", "towering"),
}


# ---------------------------------------------------------------------------
# Counts and cardinality
# ---------------------------------------------------------------------------

COUNT_POOL: tuple[str, ...] = (
    "a single", "a pair of", "three", "four", "six", "eight", "a dozen", "a cluster of",
)

CARDINALITY_COUNTS: dict[str, tuple[str, ...]] = {
    "a lone part": ("a single",),
    "a matched pair": ("a pair of",),
    "a small set": ("a single", "a pair of", "three", "four"),
    "a limb set": ("a single", "a pair of", "three", "four", "six", "eight"),
    "a body row": ("a single", "a pair of", "three", "four", "six", "a cluster of"),
    "an array": ("a pair of", "three", "four", "six", "eight", "a dozen", "a cluster of"),
    # "a crown of" read as a literal jewelled headpiece (a crowned octopus),
    # the render-trap-word class -- "a cluster of" says the same arrangement
    # without the object noun.
    "a crown": ("three", "six", "eight", "a cluster of"),
    "a hand weapon": ("a single",),
    "a paired arm": ("a single", "a pair of"),
}

APPENDAGE_COUNT_POOLS: dict[str, tuple[str, ...]] = {
    POOL_DEFAULT_KEY: ("a single", "a pair of"), **CARDINALITY_COUNTS,
}
EMITTER_COUNT_POOLS: dict[str, tuple[str, ...]] = {
    POOL_DEFAULT_KEY: ("a single", "a pair of"), **CARDINALITY_COUNTS,
}
ARMAMENT_COUNT_POOLS: dict[str, tuple[str, ...]] = {
    POOL_DEFAULT_KEY: ("a single",), **CARDINALITY_COUNTS,
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
            "battered backpack", "knitted scarf",
            "crumbling spire", "iron-barred gate",
            "trailing strip of cloth", "dangling jaw", "dragging foot", "high cape collar",
            "rusted helm", "trailing strand of weed", "long trailing veil", "bristling tail",
            "whip-thin tail", "dripping fin crest", "tattered hat", "hooded mantle",
            "wide-brimmed hat", "deep hood", "ritual stole", "carved finial", "brass winding key",
            "tarnished brass clasp", "inlaid bone panel", "tiny dancing figure", "lace bonnet",
            "ribbon sash", "tiny bow tie", "gilded crest", "cracked plaster clown statue",
            "brass pendulum", "sagging porch", "crooked chimney", "weathervane",
            "rusted arm of gondolas", "peeling painted clown face", "rusted access ladder",
            "jutting rib", "cracked lamp-room glass", "corroded support strut",
        )),
        ("a matched pair", (
            "long clawed hand", "pointed ear", "bony hand", "weed-tangled hand",
            "outstretched hand", "long grasping hand", "pointed wolf ear", "painted wooden hand", "hooked claw hand",
            "ragged ear", "webbed claw hand", "branching antler", "dusty moth wing",
            "feathery antenna", "backwards-bent knee", "straw-stuffed arm", "long leather glove",
            "grasping hand",
        )),
        ("a small set", (
            "leaning stone cross", "twisted spike", "broken shutter", "broken sail",
            "trailing tatter",
                         "fused extra arm")),
        ("a limb set", ("long spindly finger", "sucker-lined tentacle", "barbed tentacle",
                        "groping tendril", "fleshy stalk")),
    ),
    "emitters": _cardinality(
        ("a lone part", ("spectral flame in its chest", "inner light in its chest",
                         "luminous shimmer",
                         "luminous vein along its flank",
                         "hooded lantern", "guttering candle", "handheld torch beam",
                         "faint inner light", "lamp in an upstairs window", "flickering porch lamp",
                         "string of bare bulbs", "flickering marquee light", "headlamp")),
        ("a matched pair", ("pinprick eye", "reflective eye", "sunken pinprick eye",
                            "hollow burning eye", "burning eye", "shining painted eye",
                            "light behind its eyes")),
        ("a body row", ("luminous pustule on its flank",)),
    ),
    "armament": _cardinality(
        ("a hand weapon", (
            "rusted blade", "iron hook", "rusted meat hook", "broken shovel", "ornate dagger",
            "rusted sword", "notched axe", "rusted sickle", "pitchfork", "barbed stinger",
            "rusted cleaver", "wood axe", "sickle", "iron crowbar", "ritual dagger",
            "curved sacrificial knife", "butcher's cleaver", "rusted machete", "iron chain whip",
            "curved skinning knife", "iron cane", "fire axe", "shotgun", "wooden stake",
            "silver crucifix", "gore-slicked axe",
        )),
        ("a paired arm", (
            "jagged antler tine", "hooked claw", "yellowed fang", "hooked talon")),
    ),
    "sensors": _cardinality(
        ("a matched pair", (
            "flared sniffing nostril", "twitching tall ear",
            "staring eye", "milky dead eye", "sunken eye", "unblinking red-rimmed eye",
            "cold pale eye", "hollow black eye", "sorrowful eye", "clouded white eye",
            "wide staring eye", "dark-circled sleepless eye", "eye behind a mask",
            "painted glass eye", "watching painted eye",
        )),
        ("an array", ("bulging eye", "wet black eye")),
    ),
}

POOL_GROUPS: dict[str, dict[str, tuple[str, ...]]] = {
    "subkind": SUBKIND_GROUPS,
    "environment": ENVIRONMENT_BANDS,
}


# ---------------------------------------------------------------------------
# Situations -- authored in buckets
# ---------------------------------------------------------------------------

# --- the dead that walk ---
_S_DEAD_EV_WALK = ("shambling forward with arms outstretched",)
_S_DEAD_EV = (
    "lunging with grasping hands",
    "jerking its head toward a sound", "lurching suddenly forward", "snapping its jaws at the air",
    "reaching out with rigid fingers", "turning with a sudden jerk",
    "collapsing and dragging itself onward",
)
_S_DEAD_EV_GORE = (
    "feeding hunched over a fresh kill", "tearing into raw meat with its teeth",
    "dragging a bloodied body by one ankle", "tearing a strip of flesh loose with its teeth",
    "clawing open its own stitched-shut abdomen", "dragging a trail of spilled entrails behind it",
    # Was "...with both hands" -- the "dead" archetype keeps armament in the
    # fixed head, so an armed skeleton warrior needed a third arm to also be
    # gripping a rusted sword.
    "cracking open a ribcage",
)
_S_DEAD_ACT = (
    "swaying on its feet", "dragging one foot as it walks", "turning its head at an unnatural angle",
    "twitching where it stands", "sniffing the air like an animal",
    "moaning with its jaw hanging slack", "shuffling in a slow circle",
    "flexing its stiff grey fingers",
)
_S_DEAD_ACT_GORE = (
    "picking at a loose strip of its own skin", "worrying a flap of rotted skin with broken nails",
    "picking maggots from a gaping wound",
)
_S_DEAD_IDLE = ("standing motionless with its back turned", "staring at nothing", "swaying in place")
_S_DEAD_ACT_WALLS = (
    "clawing at a boarded-up window", "scratching slowly at a door",
    "pressing its face against a window",
)
_S_DEAD_EV_GROUND = ("stumbling out of the tree line",)
_S_DEAD_EV_GRAVE = ("clawing its way up out of a grave", "pushing aside a toppled headstone")
_S_DEAD_ACT_WATER = ("wading out of the black water", "rising dripping from the shallows")
_S_DEAD_DORMANT_GROUND = ("lying half-buried in loose earth",)
_S_DEAD_DORMANT = ("lying still under a torn shroud", "lying face-down and motionless")
_S_DEAD_DORMANT_WALLS = (
    "lying in an open coffin", "slumped against a crypt wall", "lying still on a mortuary slab",
)
_S_VAMPIRE_ACT = (
    "watching from the top of a staircase", "moving soundlessly down a hallway",
    "standing perfectly still in a doorway",
)
_S_VAMPIRE_ACT_ANY = (
    "lowering its hood with a slow smile", "beckoning with one long finger",
    "smiling to reveal long fangs", "adjusting a ruffled cuff", "sniffing the air hungrily",
    "circling slowly and watching", "tilting its head with interest", "turning a heavy signet ring",
    "standing with its cloak spread wide",
)
_S_VAMPIRE_IDLE = ("gazing with a cold unblinking stare",)
_S_VAMPIRE_EV_GORE = (
    "wiping blood from its lips", "feeding at a pale throat",
    "tearing open a throat in a spray of blood", "draining a body dry with a wet gurgling sound",
)
_S_VAMPIRE_EV_ANY = (
    "lunging with bared fangs", "sweeping its cloak aside", "vanishing in a swirl of its cloak",
    "seizing a wrist in an iron grip", "springing forward with inhuman speed",
)
_S_VAMPIRE_EV = ("unfolding from a crouch on a rooftop", "rising slowly from an open coffin")
_S_BONES_EV = ("reassembling itself from a heap of bones", "rattling forward with a rusted blade")
_S_DROWNED_DEEP = ("drifting upright through the murky water", "reaching up from the silt")

# --- spirits ---
_S_SPIRIT_EV = (
    "screaming with its mouth stretched impossibly wide", "flickering violently between two places",
    "vanishing mid-step", "bursting apart into drifting rags", "lunging forward with a silent shriek",
    "rushing forward in a sudden gust of cold air", "unravelling into strands of pale vapour",
)
_S_SPIRIT_ACT = (
    # Was "weeping with its face in its hands" -- the spirit archetype's own
    # "{pronoun} clutches {extras}" sentence (a tarnished locket, a wilted
    # bouquet) already puts something in its hands, the same conflict as
    # the undead and dead archetypes had.
    "hunched over in silent grief", "reaching out with a pale hand",
    "turning slowly to face the viewer", "drifting slowly past", "beckoning with one pale finger",
    "mouthing silent words", "rocking gently back and forth", "tilting its head to one side",
    "fading in and out of sight", "clutching a wilted bouquet",
)
_S_SPIRIT_HOVER = ("hovering motionless in the air",)
_S_SPIRIT_IDLE = ("standing motionless and staring", "watching with an unblinking stare",
                  "waiting perfectly still")
_S_SPIRIT_WALLS = (
    "standing motionless at the end of the hall", "watching from a doorway",
    "passing straight through a wall", "drifting slowly down a hallway",
    "sitting perfectly still in a rocking chair",
)
_S_SPIRIT_EV_WALLS = ("slamming every door in the room",)
_S_SPIRIT_ACT_WATER = ("standing on the surface of the black water",)
_S_SPIRIT_ACT_GRAVE = ("kneeling beside a weathered headstone",)
#: A drowned place lost its candle and dust acts to the air they need.
_S_SPIRIT_ACT_DEEP = ("drifting slowly through the murky water", "trailing a slow cloud of silt behind it")
_S_POLTERGEIST_EV = ("hurling dishes across the room", "stacking chairs into a crooked tower")

# --- cryptids ---
_S_CRYPTID_EV = (
    "lunging out of hiding", "freezing as it catches a scent", "bounding forward in long strides",
    "springing sideways at a sudden noise", "rising slowly to its full height",
    "whirling around to face the viewer",
)
_S_CRYPTID_EV_WAR = ("charging straight at the viewer",)
_S_CRYPTID_ACT = (
    "circling slowly at a distance", "sniffing at a trail", "crouching low and still",
    "watching with its head cocked", "pacing back and forth", "tilting its head as it watches",
    "stalking forward in a low crouch", "twitching at a distant sound",
    "creeping closer one step at a time", "tilting its head at an unnatural angle",
)
_S_CRYPTID_IDLE = ("standing impossibly still", "watching from a distance", "waiting half-hidden")
_S_CRYPTID_LIFE = (
    "watching from the tree line", "stepping out from behind a tree",
    "standing half-hidden among the trunks", "lunging out of the brush",
)
_S_BEAST_EV = ("rearing up with a howl", "snarling as it springs")
_S_BEAST_EV_GORE = (
    "gnawing on a bloodied bone", "dragging a torn carcass", "shaking a limp body in its jaws",
    "disembowelling a carcass with one raking claw",
    "cracking a ribcage open to get at the organs inside", "shaking a body until a limb tears free",
)
_S_BEAST_ACT = ("baring its teeth in a silent snarl", "licking its muzzle slowly")
_S_CRAWLER_ACT = ("crawling along the ceiling", "scuttling backwards on all fours")
_S_CRAWLER_EV = ("dropping from the ceiling",)
_S_EFFIGY_ACT = ("climbing down from its post", "turning its sackcloth head")
_S_EFFIGY_EV = ("lurching upright among the stalks",)
_S_WATCHER_ACT_SKY = ("spreading its wings against the sky",)

# --- eldritch horrors ---
_S_ELDRITCH_EV = (
    # "crown" reads as a literal jewelled headpiece, not "arranged in a ring" --
    # rendered as a royal crown perched on a tentacled creature.
    "unfurling a writhing mass of tentacles", "splitting open to reveal rows of teeth",
    "dragging itself forward on countless limbs", "surging forward in a wet heave",
    "opening a dozen eyes at once", "lashing out with a barbed limb",
    "bursting upward with a shriek",
)
_S_ELDRITCH_EV_GORE = (
    "swallowing a struggling victim whole", "trailing strips of torn flesh",
    "dragging a limp body along the floor", "sinking its teeth into a still-twitching torso",
    "leaving a trail of half-digested remains",
)
_S_ELDRITCH_ACT = (
    "pulsing slowly as its eyes open one by one", "reaching out with groping tendrils",
    "oozing slowly forward", "turning every eye toward the viewer",
    "shuddering as something moves inside it", "weeping thick black fluid",
    "extending a long quivering stalk", "sliding its bulk over itself",
    "tasting the air with a dozen tongues",
)
_S_ELDRITCH_IDLE = ("looming motionless", "breathing in slow heaving pulses")
_S_ELDRITCH_GROUND = ("rising out of a crack in the ground",)
_S_ELDRITCH_DEEP = ("rising from the murky depths", "coiling around a sunken wreck")
_S_ELDRITCH_DORMANT = ("lying dormant beneath a crust of ice",)
_S_ELDRITCH_SLEEP = ("lying coiled and motionless", "heaving in slow sleeping breaths")

# --- mortals ---
_S_MORTAL_EV = (
    "rearing back to strike", "bursting out of hiding", "breaking into a run",
    "spinning around at a sound", "lunging forward with a snarl", "smashing a lantern at their feet",
)
_S_MORTAL_EV_GORE = (
    "wiping a bloodied blade clean", "dragging a bloodied sack", "sharpening a stained cleaver",
    "hacking through a limb with three heavy strokes", "gutting a carcass strung up on a hook",
    "carving a symbol into bare flesh", "dragging a disembowelled body by its ankles",
)
_S_MORTAL_ACT = (
    "standing silently and watching", "tilting their head slowly", "chanting under their breath",
    "dragging a heavy sack", "sharpening a blade on a whetstone", "setting down a single candle",
    "wiping their hands on a stained apron", "turning a key in a rusted padlock",
    "counting under their breath",
)
_S_MORTAL_IDLE = ("waiting motionless", "standing perfectly still")
_S_MORTAL_WALLS = (
    "kicking in a door", "bursting through a curtain", "peering through a gap in the boards",
    "standing silently in a doorway", "waiting motionless at the top of the stairs",
)
_S_MORTAL_GROUND = ("burying something in a shallow hole",)
_S_CULT_ACT = (
    "leading a hooded procession", "chanting over a circle of candles",
    "raising a ritual dagger overhead", "kneeling before a crude altar",
)
_S_CULT_WALLS = ("carving a sigil into a door",)
_S_OCCULT_ACT = (
    "reading aloud from a crumbling grimoire", "burning herbs in an iron bowl",
    "laying out cards by candle stub", "drawing a chalk circle", "stirring a bubbling iron pot",
)
_S_SURVIVOR_EV = (
    "backing away with a flashlight raised", "running for their life", "fumbling with a ring of keys",
    "diving for cover", "swinging a fire axe at something off to one side",
    "stumbling and falling", "hiding behind an overturned table", "spinning toward a noise",
)
_S_SURVIVOR_ACT = (
    "checking a bolt-action rifle with shaking hands", "reading a torn diary page",
    "holding up a crucifix", "clutching a first aid kit to their chest",
    "bandaging a bleeding arm", "calling out into the dark", "creeping forward step by step",
    "loading shells into a shotgun", "shining a flashlight into the dark",
    "studying a crumpled map",
)
_S_SURVIVOR_IDLE = ("hiding very still", "catching their breath")
_S_SURVIVOR_PEACE = ("praying quietly by candle stub",)
_S_SURVIVOR_WALLS = (
    "barricading a door", "searching a dark room by flashlight", "listening at a closed door",
    "peering around a corner", "sitting slumped against a wall to catch their breath",
)

# --- cursed objects ---
_S_OBJECT_EV = (
    "tipping over on its own", "cracking straight down the middle", "shuddering violently",
    "spinning in place", "sliding slowly across the floor", "toppling with a crash",
)
_S_OBJECT_ACT = (
    "turning a fraction by itself", "rocking gently by itself", "weeping dark tears",
    "dripping water onto the floor", "trembling faintly", "shedding flakes of old paint",
    "reflecting a pale figure behind the viewer", "marked by a small handprint in its dust",
    "leaning at an impossible angle", "gathering a ring of dead flies",
    "shifting when nobody looks", "beaded with cold condensation", "rattling faintly on its own",
)
_S_OBJECT_IDLE = ("standing before long scratches gouged into the wall", "facing the wall")
_S_OBJECT_DORMANT = ("gathering dust under a sheet",)
_S_OBJECT_DORMANT_ANY = ("leaking a thin trickle of black fluid",)
_S_OBJECT_DORMANT_DEEP = ("half-buried in drifting silt", "crusted with pale barnacles")
_S_KEEPSAKE_DORMANT = ("lying forgotten in a drawer",)
_S_DOLL_ACT = ("turning its head toward the viewer", "sitting up by itself")
_S_BOX_ACT = ("playing a tune nobody wound", "creaking open by itself")
#: A puzzle box has no tune to play.
_S_PUZZLE_ACT = ("sliding its panels by itself", "creaking open a crack by itself")
_S_BOARD_ACT = ("moving its planchette on its own",)
_S_CLOCK_ACT = ("striking thirteen", "swinging its pendulum faster and faster")

# --- haunted places ---
_S_PLACE_EV = (
    "banging its shutters in a gust", "shedding a shower of broken glass",
    "groaning as its frame sags", "losing a chunk of its roof", "belching dust from within",
    "shuddering as something moves inside", "collapsing at one corner",
)
_S_PLACE_ACT = (
    "standing with a candle burning behind one pane", "drawing a crooked line of crows to its roof",
    "leaning under gathering storm clouds", "swallowed by creeping ivy",
    "trailing a thin curl of chimney smoke", "creaking in a steady wind",
    "sagging under heavy rain", "hung with rotting bunting", "staring out through broken panes",
    "sinking slowly into overgrowth", "standing with its gate swinging",
    "weeping long streaks of rust",
)
_S_PLACE_IDLE = ("standing silent at the end of an overgrown drive", "looming over a dead lawn")
_S_PLACE_DORMANT = ("rotting quietly into the ground", "standing boarded-up and silent")
_S_RIDE_ACT = ("turning slowly with nobody aboard", "creaking in a gust of wind")
_S_LIGHTHOUSE_ACT = ("sweeping a beam across the black water",)


_A = frozenset()
_GROUND = frozenset({"ground"})
_FLOOR = frozenset({"floor"})
_WALLS = frozenset({"structure"})
_SHORE = frozenset({"shoreline"})
_DEEP = frozenset({"submerged"})
_GRAVE = frozenset({"grave"})
_LIFE = frozenset({"life"})
_COLD = frozenset({"cold"})
_SKY = frozenset({"sky"})
_WALK = frozenset({"walks"})
_FLOAT = frozenset({"floats", "hovers"})
_CLIMB = frozenset({"climbs"})
_STILL = frozenset({"rests"})

#: ``(values, tier, tag, needs, stances, life)``: tag ``c`` gore or killing (hidden by
#: "No gore"), ``p`` only in a gore-free scene, ``n`` either; life ``d`` for what a
#: thing at rest can be doing, empty for everything that moves.
_BUCKETS = (
    (_S_DEAD_EV, "event", "n", _A, _A, ""),
    (_S_DEAD_EV_WALK, "event", "n", _A, _WALK, ""),
    (_S_DEAD_EV_GORE, "event", "c", _A, _A, ""),
    (_S_DEAD_ACT, "activity", "n", _A, _A, ""),
    (_S_DEAD_ACT_GORE, "activity", "c", _A, _A, ""),
    (_S_DEAD_IDLE, "idle", "n", _A, _A, ""),
    (_S_DEAD_ACT_WALLS, "activity", "n", _WALLS, _A, ""),
    (_S_DEAD_EV_GROUND, "event", "n", _GROUND | _LIFE, _WALK, ""),
    (_S_DEAD_EV_GRAVE, "event", "n", _GRAVE, _A, ""),
    (_S_DEAD_ACT_WATER, "activity", "n", _SHORE, _WALK, ""),
    (_S_DEAD_DORMANT_GROUND, "idle", "n", _GROUND, _STILL, "d"),
    (_S_DEAD_DORMANT, "idle", "n", _A, _STILL, "d"),
    (_S_DEAD_DORMANT_WALLS, "idle", "n", _WALLS, _STILL, "d"),
    (_S_VAMPIRE_ACT, "activity", "n", _WALLS, _A, ""),
    (_S_VAMPIRE_ACT_ANY, "activity", "n", _A, _A, ""),
    (_S_VAMPIRE_EV_GORE, "event", "c", _A, _A, ""),
    (_S_VAMPIRE_EV, "event", "n", _WALLS, _A, ""),
    (_S_VAMPIRE_EV_ANY, "event", "n", _A, _A, ""),
    (_S_VAMPIRE_IDLE, "idle", "n", _A, _A, ""),
    (_S_BONES_EV, "event", "n", _A, _A, ""),
    (_S_DROWNED_DEEP, "activity", "n", _DEEP, frozenset({"swims"}), ""),
    (_S_SPIRIT_EV, "event", "n", _A, _A, ""),
    (_S_SPIRIT_ACT, "activity", "n", _A, _A, ""),
    (_S_SPIRIT_HOVER, "activity", "n", _A, _FLOAT, ""),
    (_S_SPIRIT_IDLE, "idle", "n", _A, _A, ""),
    (_S_SPIRIT_WALLS, "activity", "n", _WALLS, _A, ""),
    (_S_SPIRIT_EV_WALLS, "event", "n", _WALLS, _A, ""),
    (_S_SPIRIT_ACT_WATER, "activity", "n", _SHORE, _FLOAT, ""),
    (_S_SPIRIT_ACT_GRAVE, "activity", "n", _GRAVE, _A, ""),
    (_S_SPIRIT_ACT_DEEP, "activity", "n", _DEEP, _A, ""),
    (_S_POLTERGEIST_EV, "event", "n", _WALLS, _A, ""),
    (_S_CRYPTID_EV, "event", "n", _A, _A, ""),
    (_S_CRYPTID_EV_WAR, "event", "c", _A, _WALK, ""),
    (_S_CRYPTID_ACT, "activity", "n", _A, _A, ""),
    (_S_CRYPTID_IDLE, "idle", "n", _A, _A, ""),
    (_S_CRYPTID_LIFE, "activity", "n", _GROUND | _LIFE, _A, ""),
    (_S_BEAST_EV, "event", "n", _A, _A, ""),
    (_S_BEAST_EV_GORE, "event", "c", _A, _A, ""),
    (_S_BEAST_ACT, "activity", "n", _A, _A, ""),
    (_S_CRAWLER_ACT, "activity", "n", _WALLS, _CLIMB, ""),
    (_S_CRAWLER_EV, "event", "n", _WALLS, _CLIMB, ""),
    (_S_EFFIGY_ACT, "activity", "n", _GROUND, _A, ""),
    (_S_EFFIGY_EV, "event", "n", _GROUND, _A, ""),
    (_S_WATCHER_ACT_SKY, "activity", "n", _SKY, _A, ""),
    (_S_ELDRITCH_EV, "event", "n", _A, _A, ""),
    (_S_ELDRITCH_EV_GORE, "event", "c", _A, _A, ""),
    (_S_ELDRITCH_ACT, "activity", "n", _A, _A, ""),
    (_S_ELDRITCH_IDLE, "idle", "n", _A, _A, ""),
    (_S_ELDRITCH_GROUND, "event", "n", _GROUND, _A, ""),
    (_S_ELDRITCH_DEEP, "event", "n", _DEEP, _A, ""),
    (_S_ELDRITCH_DORMANT, "idle", "n", _COLD, _STILL, "d"),
    (_S_ELDRITCH_SLEEP, "idle", "n", _A, _A, "d"),
    (_S_MORTAL_EV, "event", "n", _A, _A, ""),
    (_S_MORTAL_EV_GORE, "event", "c", _A, _A, ""),
    (_S_MORTAL_ACT, "activity", "n", _A, _A, ""),
    (_S_MORTAL_IDLE, "idle", "n", _A, _A, ""),
    (_S_MORTAL_WALLS, "event", "n", _WALLS, _A, ""),
    (_S_MORTAL_GROUND, "activity", "n", _GROUND, _A, ""),
    (_S_CULT_ACT, "activity", "n", _A, _A, ""),
    (_S_CULT_WALLS, "activity", "n", _WALLS, _A, ""),
    (_S_OCCULT_ACT, "activity", "n", _A, _A, ""),
    (_S_SURVIVOR_EV, "event", "n", _A, _WALK, ""),
    (_S_SURVIVOR_ACT, "activity", "n", _A, _A, ""),
    (_S_SURVIVOR_IDLE, "idle", "n", _A, _A, ""),
    (_S_SURVIVOR_PEACE, "activity", "p", _A, _A, ""),
    (_S_SURVIVOR_WALLS, "activity", "n", _WALLS, _A, ""),
    (_S_OBJECT_EV, "event", "n", _A, _A, ""),
    (_S_OBJECT_ACT, "activity", "n", _A, _A, ""),
    (_S_OBJECT_IDLE, "idle", "n", _WALLS, _A, ""),
    (_S_OBJECT_DORMANT, "idle", "n", _WALLS, _A, "d"),
    (_S_OBJECT_DORMANT_ANY, "idle", "n", _A, _A, "d"),
    (_S_OBJECT_DORMANT_DEEP, "idle", "n", _DEEP, _A, "d"),
    (_S_KEEPSAKE_DORMANT, "idle", "n", _WALLS, _A, "d"),
    (_S_DOLL_ACT, "activity", "n", _A, _A, ""),
    (_S_BOX_ACT, "activity", "n", _A, _A, ""),
    (_S_PUZZLE_ACT, "activity", "n", _A, _A, ""),
    (_S_BOARD_ACT, "activity", "n", _A, _A, ""),
    (_S_CLOCK_ACT, "event", "n", _A, _A, ""),
    (_S_PLACE_EV, "event", "n", _A, _A, ""),
    (_S_PLACE_ACT, "activity", "n", _A, _A, ""),
    (_S_PLACE_IDLE, "idle", "n", _GROUND, _A, ""),
    (_S_PLACE_DORMANT, "idle", "n", _GROUND, _A, "d"),
    (_S_RIDE_ACT, "activity", "n", _GROUND, _A, ""),
    (_S_LIGHTHOUSE_ACT, "activity", "n", _SHORE, _A, ""),
)

_S_DEAD_CORE = (
    _S_DEAD_EV + _S_DEAD_EV_WALK + _S_DEAD_EV_GORE + _S_DEAD_ACT + _S_DEAD_ACT_GORE + _S_DEAD_IDLE
    + _S_DEAD_ACT_WALLS + _S_DEAD_EV_GROUND + _S_DEAD_EV_GRAVE + _S_DEAD_ACT_WATER
    + _S_DEAD_DORMANT_GROUND + _S_DEAD_DORMANT + _S_DEAD_DORMANT_WALLS
)
_S_SPIRIT_CORE = (
    _S_SPIRIT_EV + _S_SPIRIT_ACT + _S_SPIRIT_HOVER + _S_SPIRIT_IDLE + _S_SPIRIT_WALLS + _S_SPIRIT_EV_WALLS
    + _S_SPIRIT_ACT_WATER + _S_SPIRIT_ACT_GRAVE + _S_SPIRIT_ACT_DEEP
)
_S_CRYPTID_CORE = (
    _S_CRYPTID_EV + _S_CRYPTID_EV_WAR + _S_CRYPTID_ACT + _S_CRYPTID_IDLE + _S_CRYPTID_LIFE
)
_S_ELDRITCH_CORE = (
    _S_ELDRITCH_EV + _S_ELDRITCH_EV_GORE + _S_ELDRITCH_ACT + _S_ELDRITCH_IDLE + _S_ELDRITCH_GROUND
    + _S_ELDRITCH_DEEP + _S_ELDRITCH_DORMANT + _S_ELDRITCH_SLEEP
)
_S_MORTAL_CORE = (
    _S_MORTAL_EV + _S_MORTAL_EV_GORE + _S_MORTAL_ACT + _S_MORTAL_IDLE + _S_MORTAL_WALLS
    + _S_MORTAL_GROUND
)
_S_OBJECT_CORE = (
    _S_OBJECT_EV + _S_OBJECT_ACT + _S_OBJECT_IDLE + _S_OBJECT_DORMANT + _S_OBJECT_DORMANT_ANY
    + _S_OBJECT_DORMANT_DEEP
)
_S_PLACE_CORE = _S_PLACE_EV + _S_PLACE_ACT + _S_PLACE_IDLE + _S_PLACE_DORMANT

SITUATION_POOLS: dict[str, tuple[str, ...]] = {
    #: The cross-genre fall-through: true of almost anything, so a foreign entity acts.
    POOL_DEFAULT_KEY: (
        "standing motionless with its back turned", "staring at nothing",
        "freezing as it catches a scent", "circling slowly at a distance",
        "tilting its head as it watches", "creeping closer one step at a time",
    ),
    "undead": _S_DEAD_CORE,
    "bloodsucker": (
        _S_VAMPIRE_ACT + _S_VAMPIRE_ACT_ANY + _S_VAMPIRE_IDLE + _S_VAMPIRE_EV_GORE + _S_VAMPIRE_EV
        + _S_VAMPIRE_EV_ANY + _S_DEAD_IDLE + _S_DEAD_EV_GRAVE + _S_DEAD_DORMANT
        + _S_DEAD_DORMANT_WALLS
    ),
    "skeletal dead": _S_DEAD_CORE + _S_BONES_EV,
    "drowned dead": _S_DEAD_CORE + _S_DROWNED_DEEP,
    "spirit": _S_SPIRIT_CORE,
    "poltergeist": _S_SPIRIT_CORE + _S_POLTERGEIST_EV,
    "cryptid": _S_CRYPTID_CORE + _S_BEAST_EV + _S_BEAST_EV_GORE + _S_BEAST_ACT,
    "watcher": _S_CRYPTID_CORE,
    "moth-winged watcher": _S_CRYPTID_CORE + _S_WATCHER_ACT_SKY,
    "crawler": _S_CRYPTID_CORE + _S_CRAWLER_ACT + _S_CRAWLER_EV,
    "effigy": _S_CRYPTID_CORE + _S_EFFIGY_ACT + _S_EFFIGY_EV,
    "eldritch horror": _S_ELDRITCH_CORE,
    "mortal": _S_MORTAL_CORE,
    "cult": _S_MORTAL_CORE + _S_CULT_ACT + _S_CULT_WALLS,
    "occultist": _S_MORTAL_CORE + _S_OCCULT_ACT,
    "survivor": (
        _S_SURVIVOR_EV + _S_SURVIVOR_ACT + _S_SURVIVOR_IDLE + _S_SURVIVOR_PEACE
        + _S_SURVIVOR_WALLS
    ),
    "cursed object": _S_OBJECT_CORE,
    "porcelain doll": _S_OBJECT_CORE + _S_KEEPSAKE_DORMANT + _S_DOLL_ACT,
    "ventriloquist dummy": _S_OBJECT_CORE + _S_KEEPSAKE_DORMANT + _S_DOLL_ACT,
    "music box": _S_OBJECT_CORE + _S_KEEPSAKE_DORMANT + _S_BOX_ACT,
    "puzzle box": _S_OBJECT_CORE + _S_KEEPSAKE_DORMANT + _S_PUZZLE_ACT,
    "spirit board": _S_OBJECT_CORE + _S_KEEPSAKE_DORMANT + _S_BOARD_ACT,
    "grandfather clock": _S_OBJECT_CORE + _S_CLOCK_ACT,
    "haunted place": _S_PLACE_CORE,
    "attraction": _S_PLACE_CORE,
    "rusted carnival ride": _S_PLACE_CORE + _S_RIDE_ACT,
    "lonely lighthouse": _S_PLACE_CORE + _S_LIGHTHOUSE_ACT,
}

#: Stillness is worth more here than in the other genres.
TIER_WEIGHTS: dict[str, float] = {"event": 2.0, "activity": 1.2, "idle": 0.9}


# ---------------------------------------------------------------------------
# Relations
# ---------------------------------------------------------------------------

RELATION_POOL: tuple[str, ...] = (
    "stalking", "hunting", "fleeing from", "watching", "creeping toward", "looming over",
    "hiding from", "confronting", "following", "attacking", "protecting", "reaching for",
    "standing behind", "cornering",
)
RELATION_POSITION_POOL: tuple[str, ...] = (
    "from behind", "from above", "from below", "in the background", "in the foreground",
    "at a distance",
    "directly ahead", "to one side", "close alongside", "in the middle distance",
)

# ---------------------------------------------------------------------------
# Labels
# ---------------------------------------------------------------------------

_LIVING = ("undead", "cryptid", "eldritch horror")


def _labels(**by_kind: str) -> dict[str, str]:
    """Expand ``living=`` into per-kind labels."""
    out: dict[str, str] = {}
    for key, label in by_kind.items():
        if key == "living":
            out.update({kind: label for kind in _LIVING})
        else:
            out[key.replace("_", " ")] = label
    return out


LABELS: dict[str, dict[str, str]] = {
    "subkind": _labels(undead="Undead type", spirit="Spirit type", cryptid="Cryptid type",
                       eldritch_horror="Horror type", mortal="Person type",
                       cursed_object="Object type", haunted_place="Place type"),
    "scale": _labels(living="Size", mortal="Size", spirit="Size"),
    "condition": _labels(undead="Decay and state", living="State", mortal="State",
                         cursed_object="State", haunted_place="State"),
    "form": _labels(living="Body", spirit="Shape", mortal="Build", cursed_object="Object shape",
                    haunted_place="Silhouette"),
    "material": _labels(undead="Remains and garb", cryptid="Hide", eldritch_horror="Flesh",
                        spirit="Substance", mortal="Garb", cursed_object="Material",
                        haunted_place="Walls"),
    "primary_color": _labels(living="Colour", spirit="Colour", mortal="Garb colour",
                             haunted_place="Paint colour"),
    "surface_detail": _labels(living="Decay and wear", mortal="Wear", cursed_object="Wear",
                              haunted_place="Decay"),
    "appendages": _labels(living="Limbs and growths", spirit="Trailing parts",
                          mortal="Worn features", haunted_place="Features"),
    "emitters": _labels(living="Unnatural light", spirit="Cold light", mortal="Light carried",
                        haunted_place="Lights"),
    "armament": _labels(living="Claws and weapons", mortal="Weapons and implements"),
    "sensors": _labels(living="Eyes", spirit="Eyes", mortal="Eyes", cursed_object="Eyes"),
    "aperture": _labels(living="Mouth", spirit="Mouth", mortal="Face or mask",
                        cursed_object="Opening", haunted_place="Doorway"),
    "extras": _labels(living="Remnants", spirit="Keepsake", mortal="Carried gear",
                      cursed_object="Resting place", haunted_place="Grounds"),
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
    "undead": frozenset({"agent", "mobile"}),
    "spirit": frozenset({"agent", "mobile"}),
    "cryptid": frozenset({"agent", "mobile"}),
    "eldritch horror": frozenset({"agent", "mobile", "massive"}),
    "mortal": frozenset({"agent", "mobile", "sapient"}),
    "cursed object": frozenset(),
    "haunted place": frozenset({"massive"}),
}

RELATION_ROLES: dict[str, tuple[frozenset[str], frozenset[str]]] = {
    "stalking": (frozenset({"mobile"}), frozenset({"mobile"})),
    "hunting": (frozenset({"mobile", "agent"}), frozenset({"mobile"})),
    "fleeing from": (frozenset({"mobile"}), frozenset({"agent"})),
    "watching": (frozenset({"agent"}), frozenset()),
    "creeping toward": (frozenset({"mobile"}), frozenset()),
    "looming over": (frozenset({"massive"}), frozenset()),
    "hiding from": (frozenset({"mobile"}), frozenset({"agent"})),
    "confronting": (frozenset({"agent"}), frozenset({"agent"})),
    "following": (frozenset({"mobile"}), frozenset({"mobile"})),
    "attacking": (frozenset({"agent"}), frozenset()),
    "protecting": (frozenset({"sapient"}), frozenset()),
    "reaching for": (frozenset({"agent"}), frozenset()),
    "standing behind": (frozenset({"agent"}), frozenset({"agent"})),
    "cornering": (frozenset({"mobile", "agent"}), frozenset({"mobile"})),
}

CONSTRAINTS: tuple[ConstraintRule, ...] = (
    ConstraintRule(
        type=RULE_EXCLUDE, field=RELATION_ANY, value="looming over",
        excludes_field=RELATION_ANY_POSITION, excludes_values=("from below",),
        reason="a thing that looms over another is not below it",
    ),
)


# ---------------------------------------------------------------------------
# Places: what each one affords, and how a body can stand in it
# ---------------------------------------------------------------------------
#
# ``ground`` natural footing; ``floor`` anything to stand on; ``structure`` built
# walls around or beside; ``grave`` graves in the ground; ``shoreline`` water with
# air above it; ``submerged`` under water; ``sky`` open air above; ``dark`` a place
# with no daylight in it; ``cold``; ``life`` living growth; ``vast`` room for
# something huge. ``air`` and ``water`` are derived below.

PLACE_AFFORDANCES: dict[str, frozenset[str]] = {
    # --- bands ---
    "wilds": frozenset({"ground", "floor", "sky", "vast", "life"}),
    "graveyard": frozenset({"ground", "floor", "sky", "grave", "structure", "life"}),
    "waterside": frozenset({"ground", "floor", "sky", "shoreline", "vast"}),
    "underwater": frozenset({"submerged", "floor", "dark"}),
    "town": frozenset({"ground", "floor", "sky", "structure", "road"}),
    "interior": frozenset({"floor", "structure", "dark", "room"}),
    "underground": frozenset({"floor", "structure", "dark"}),
    "otherworld": frozenset({"floor", "structure", "dark", "vast", "room"}),
    # --- places that differ from their band ---
    "snowbound pine woods": frozenset({"ground", "floor", "sky", "vast", "life", "cold"}),
    "windswept moor of standing stones": frozenset({"ground", "floor", "sky", "vast", "life",
                                                    "structure"}),
    "rocky ravine": frozenset({"ground", "floor", "sky", "vast"}),
    "overgrown cemetery": frozenset({"ground", "floor", "sky", "grave", "structure", "life",
                                     "vast"}),
    "drowned village shoreline": frozenset({"ground", "floor", "sky", "shoreline", "structure",
                                            "vast"}),
    "rotting fishing pier": frozenset({"floor", "sky", "shoreline", "structure"}),
    "abandoned carnival fairground": frozenset({"ground", "floor", "sky", "structure", "vast",
                                                "fairground"}),
    "flooded suburban street": frozenset({"ground", "floor", "sky", "structure", "shoreline",
                                          "road"}),
    # A travelling fair sets up in the square.
    "boarded-up village square": frozenset({"ground", "floor", "sky", "structure", "road",
                                            "fairground"}),
    "flooded cellar": frozenset({"floor", "structure", "dark", "shoreline"}),
    "abandoned chapel": frozenset({"floor", "structure", "dark", "vast"}),
    "dusty manor ballroom": frozenset({"floor", "structure", "dark", "vast"}),
    "brick sewer tunnel": frozenset({"floor", "structure", "dark", "shoreline"}),
    "collapsed mine shaft": frozenset({"ground", "floor", "structure", "dark"}),
    "cave strewn with bones": frozenset({"ground", "floor", "dark"}),
    "crypt beneath a chapel": frozenset({"floor", "structure", "dark", "grave"}),
    "catacomb ossuary": frozenset({"floor", "structure", "dark", "grave"}),
    "frozen lake bed": frozenset({"submerged", "floor", "dark", "cold"}),
}
_AIR_EXCLUDED = frozenset({"submerged"})
_WATER_SOURCES = frozenset({"shoreline", "submerged"})
PLACE_AFFORDANCES = {
    place: (
        affordances
        | ({"air"} if not affordances & _AIR_EXCLUDED else set())
        | ({"water"} if affordances & _WATER_SOURCES else set())
    )
    for place, affordances in PLACE_AFFORDANCES.items()
}

PLACE_STANCES: dict[str, frozenset[str]] = {
    "ground": frozenset({"rests", "walks"}),
    "floor": frozenset({"rests", "walks", "hovers", "floats"}),
    "structure": frozenset({"rests", "walks", "hovers", "floats", "climbs"}),
    "sky": frozenset({"flies", "hovers", "floats"}),
    "submerged": frozenset({"swims", "floats", "rests", "walks"}),
    "shoreline": frozenset({"rests", "walks", "swims", "hovers", "floats"}),
}

_FLY_WALK = frozenset({"walks", "flies"})
_SPIRIT = frozenset({"floats", "hovers", "walks"})
_CRAWL = frozenset({"walks", "climbs"})

#: How each form holds itself up, by the pool key that authors it.
_FORM_KEY_STANCES: dict[str, frozenset[str]] = {
    POOL_DEFAULT_KEY: frozenset(),
    "rotting dead": _WALK | _STILL, "bog body": _WALK | _STILL,
    "bloodsucker": _CRAWL | _STILL, "skeletal dead": _WALK | _STILL,
    "drowned dead": frozenset({"walks", "swims", "rests"}),
    "apparition": _SPIRIT, "wrathful spirit": _SPIRIT,
    "werewolf": _WALK, "hellish black hound": _WALK, "bog lurker": frozenset({"walks", "swims"}),
    "watcher": _WALK, "moth-winged watcher": _FLY_WALK, "hollow-eyed stag": _WALK,
    "crawler": _CRAWL, "effigy": _WALK,
    "tentacled horror": frozenset({"walks", "swims", "rests"}), "many-eyed horror": _WALK,
    "many-eyed abomination": _CRAWL,
    "amalgam": _WALK,
    "mortal": _WALK, "possessed villager": _CRAWL,
}


def _form_stances() -> dict[str, frozenset[str]]:
    out: dict[str, frozenset[str]] = {}
    still_keys = set(SUBKIND_POOLS["cursed object"]) | set(SUBKIND_POOLS["haunted place"]) | {
        "sacred ruin", "attraction",
    }
    for key, forms in FORM_POOLS.items():
        if key in _FORM_KEY_STANCES:
            stances = _FORM_KEY_STANCES[key]
        elif key in still_keys:
            stances = _STILL
        else:
            raise ValueError(f"form pool {key!r} declares no stance")
        for form in forms:
            out[form] = out.get(form, frozenset()) | stances
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

#: What a thing at rest can be doing. Closed: every other situation is live.
DORMANT_ACTS: frozenset[str] = frozenset(v for v, life in _SITUATION_LIFE.items() if life == "d")

_SUBKIND_NEEDS: dict[str, frozenset[str]] = {
    **{value: frozenset() for pool in SUBKIND_POOLS.values() for value in pool},
    "bog body": frozenset({"ground"}),
    "drowned revenant": frozenset({"water"}),
    "waterlogged corpse": frozenset({"water"}),
    "bog lurker": frozenset({"water"}),
    # Needs an actual frozen surface to be beneath, not just a cold place --
    # "cold" alone let it draw in a snowy forest with no ice in sight.
    "thing beneath the ice": frozenset({"cold", "water"}),
    "living scarecrow": frozenset({"ground"}),
    "stitched straw man": frozenset({"ground"}),
    "hollow-eyed stag": frozenset({"ground", "life"}),
    "antlered stalker": frozenset({"ground"}),
    "bone-and-sinew colossus": frozenset({"vast"}),
    "lonely lighthouse": frozenset({"shoreline"}),
    "rotting windmill": frozenset({"ground"}),
    "rusted water tower": frozenset({"ground"}),
    # A ride or a funhouse outside a fairground was drawn on a moor and in a
    # flooded street; a motel in snowbound pine woods. Each needs its own place.
    "rusted carnival ride": frozenset({"ground", "fairground"}),
    "derelict funhouse": frozenset({"ground", "fairground"}),
    **{value: frozenset({"ground"}) for value in SUBKIND_GROUPS["dwelling"]},
    "ruined chapel": frozenset({"ground"}),
    "boarded-up church": frozenset({"ground"}),
    "family mausoleum": frozenset({"grave"}),
    # A portrait propped in a sewer tunnel: furniture belongs in a room.
    **{value: frozenset({"room"}) for value in SUBKIND_GROUPS["furnishing"]},
    "derelict motel": frozenset({"ground", "road"}),
}

VALUE_NEEDS: dict[str, dict[str, frozenset[str]]] = {
    # Condensation beads on a thing in a room (dew had formed in a morgue).
    SITUATION_FIELD: {**_SITUATION_NEEDS, "beaded with cold condensation": frozenset({"room"})},
    "subkind": _SUBKIND_NEEDS,
    # "Dripping" asserts the subject is out of the water it dripped from; a
    # spirit or a corpse already ``submerged`` should not also be dripping.
    # ``air`` is horror's own derived "not submerged" token (see
    # ``PLACE_AFFORDANCES`` below).
    "surface_detail": {
        "slowly dripping water": frozenset({"air"}),
        "dripping fresh blood": frozenset({"air"}),
    },
    # Round XIV's deposit-condition rule (scifi.py) never reached horror:
    # vegetation overtaking a place needs a place that can grow it. Horror
    # has no frost/ice *condition* value to gate (unlike scifi/fantasy) --
    # its cold-only content is already gated at the situation level
    # (``_S_ELDRITCH_DORMANT`` needs ``_COLD``).
    "condition": {
        "overgrown": _LIFE,
    },
    # A cursed object's furnished resting surfaces (velvet, a display case, a
    # dusty shelf) presume an indoor, dry room; a reed marsh and a drowned
    # church nave are neither. "dusty ledge" is the outdoor-or-underwater
    # fallback, but "dusty" itself needs air (dust does not settle
    # underwater) -- "silt-caked ledge" is submerged's own fallback so a
    # cursed object always has a surface, wet or dry.
    "extras": {
        "velvet-lined case": _WALLS | frozenset({"air"}),
        "dusty shelf": _WALLS | frozenset({"air"}),
        "carved side table": _WALLS | frozenset({"air"}),
        "child-sized chair": _WALLS | frozenset({"air"}),
        "dusty ledge": frozenset({"air"}),
        "silt-caked ledge": frozenset({"submerged"}),
        # A mirror in a mine shaft stood "against a wall of stained plaster".
        "peeling floral wallpaper": frozenset({"room"}),
        "wall of stained plaster": frozenset({"room"}),
        "wall of warped panelling": frozenset({"room"}),
    },
}

DEFAULT_NEEDS: dict[str, dict[str, frozenset[str]]] = {
    CONTEXT_FIELD: {
        "wilds": _GROUND, "graveyard": _GRAVE, "waterside": _SHORE, "underwater": _DEEP,
        "town": _WALLS, "abandoned carnival fairground": _WALLS, "interior": _WALLS,
        "hospital corridor after closing": _WALLS, "hospital morgue": _WALLS,
        "taxidermy parlour": _WALLS, "farmhouse kitchen": _WALLS,
        "underground": _FLOOR, "brick sewer tunnel": _WALLS, "otherworld": _WALLS,
    },
}

VALUE_STANCES: dict[str, dict[str, frozenset[str]]] = {
    "form": _form_stances(),
    SITUATION_FIELD: {v: s for v, s in _SITUATION_STANCES.items() if s},
}


# ---------------------------------------------------------------------------
# Traits and conflicts
# ---------------------------------------------------------------------------

_BARE_BONE = ("walking skeleton", "bone revenant")
_FLESH_CONDITIONS = ("rotting", "bloated", "freshly risen", "blood-soaked")


def _add_traits(field: str, additions: dict[str, tuple[str, ...]]) -> None:
    table = VALUE_TRAITS.setdefault(field, {})
    for value, added in additions.items():
        table[value] = tuple(dict.fromkeys(tuple(table.get(value, ())) + added))


VALUE_TRAITS: dict[str, dict[str, tuple[str, ...]]] = {
    "condition": {
        "entombed": ("inactive",), "dormant": ("inactive",), "abandoned": ("inactive",),
        "boarded-up": ("inactive",), "slumbering": ("inactive",),
    },
    "scale": {
        "small": ("small-scale",), "towering": ("large-scale",), "gargantuan": ("large-scale",),
    },
    "subkind": {},
    ENVIRONMENT_FIELD: {v: ("interior-place",) for v in _ENV_INTERIOR},
    SITUATION_FIELD: {},
    "emitters": {value: ("emissive",) for pool in EMITTER_POOLS.values() for value in pool},
}
_add_traits("subkind", {v: ("bare-bone",) for v in _BARE_BONE})
_add_traits("condition", {v: ("flesh-intact",) for v in _FLESH_CONDITIONS})
_add_traits(SITUATION_FIELD, {v: ("powered-act",) for v in _ALL_SITUATIONS - DORMANT_ACTS})
_add_traits(SITUATION_FIELD, {
    v: ("violent-act",) for v, code in _SITUATION_TAG_CODES.items() if code == "c"
})
_add_traits("subkind", {"village priest": ("pacifist-role",)})
# A windmill belongs to a farm, not a graveyard -- "rotting windmill" appeared
# in a sunken churchyard and among grave markers. Scope it out of the four
# explicitly funerary environments only; it stays free everywhere else
# (a lake shore, the wilds).
_add_traits(ENVIRONMENT_FIELD, {v: ("funerary-place",) for v in _ENV_GRAVES})
_add_traits("subkind", {"rotting windmill": ("rural-landmark",)})
# A figure already carrying a two-handed weapon has no hand left for a
# lantern, a candle or a torch -- "backing away with a flashlight raised"
# while also carrying a shotgun rendered a lantern strapped to a wrist.
_add_traits("emitters", {v: ("hand-occupying",)
                         for v in ("hooded lantern", "guttering candle", "handheld torch beam")})
_add_traits("armament", {v: ("two-handed-weapon",) for v in ("shotgun", "fire axe")})
_add_traits("extras", {"bolt-action hunting rifle": ("two-handed-weapon",)})
# A situation that already occupies both hands (working a rifle bolt,
# loading a gun, holding something two-armed to the chest) conflicts with a
# separately-drawn hand-occupying emitter the same way a two-handed weapon
# does -- "loading shells into a shotgun" rendered with a handheld torch
# beam also somehow in the same two hands.
_add_traits(SITUATION_FIELD, {v: ("two-handed-weapon",) for v in (
    "checking a bolt-action rifle with shaking hands", "loading shells into a shotgun",
    "clutching a first aid kit to their chest", "bandaging a bleeding arm",
    "barricading a door",
)})

# Round XXI -- a material that names a colour fixes it: "waxen-white yellowed
# bone", "jaundiced-yellow peat-blackened hide".
_COLOUR_WORDS = ("grey", "black", "brown", "white", "yellowed", "pale", "red", "crimson", "peat",
                 "soot", "ivory", "gold", "silver", "brass", "bone")
_add_traits("material", {
    v: ("self-coloured",) for pool in MATERIAL_POOLS.values() for v in pool
    if any(w in v.replace("-", " ").split() for w in _COLOUR_WORDS)
})
_add_traits("primary_color", {v: ("states-a-colour",) for pool in PRIMARY_COLOR_POOLS.values() for v in pool})

# Round XXII -- a face that is hidden has no mouth or eyes to show: a
# "blank-faced apparition" or "veiled floating figure" given a screaming mouth
# and lights behind its eyes was drawn as two ghosts, one for each face.
_add_traits("subkind", {"blank-faced apparition": ("face-hidden",)})
_add_traits("form", {"veiled floating figure": ("face-hidden",)})
_add_traits("aperture", {v: ("face-feature",) for v in APERTURE_POOLS["spirit"]})
_add_traits("sensors", {v: ("face-feature",) for v in SENSOR_POOLS["spirit"]})
_add_traits("emitters", {v: ("face-feature",) for v in ("light behind its eyes", "hollow burning eye")})
# #388 the warden's own lantern takes one hand, so the other stays free.
_add_traits("subkind", {"lantern-bearing warden": ("lantern-hand",)})
# #391 a crowbar in hand while both hands work a rifle.
# "loading shells into a shotgun" is left out: its weapon is the one it names.
_add_traits(SITUATION_FIELD, {v: ("both-hands-act",) for v in (
    "checking a bolt-action rifle with shaking hands",
    "clutching a first aid kit to their chest", "bandaging a bleeding arm", "barricading a door",
)})

# Round XXI -- what the hands hold. A priest carried a wooden stake and a
# hunting rifle; a survivor a stake, a first aid kit and a lit candle.
_add_traits("armament", {v: ("carried-weapon",) for v in (
    ARMAMENT_POOLS["occultist"] + ARMAMENT_POOLS["survivor"] + ARMAMENT_POOLS["village priest"]
)})
_add_traits("extras", {"bolt-action hunting rifle": ("firearm",)})
_add_traits("extras", {v: ("held-item",) for v in (
    "first aid kit", "flashlight", "crumpled map", "leather-bound grimoire", "coil of wire",
)})
# A locket clutched to the chest and a flame in the chest are one place.
_add_traits("emitters", {v: ("chest-located",) for pool in EMITTER_POOLS.values() for v in pool
                         if v.endswith("in its chest")})
_add_traits("extras", {"tarnished locket": ("chest-located",)})
# A room, however strange, cannot hold a gargantuan thing.
_add_traits(ENVIRONMENT_FIELD, {v: ("interior-place",) for v in (
    "flesh-walled chamber", "endless crimson hallway",
)})
# A slumbering mass does not stare.
_add_traits("sensors", {v: ("open-eyed",) for v in ("bulging eye", "wet black eye")})

TRAIT_CONFLICTS: tuple[tuple[str, str], ...] = (
    ("inactive", "powered-act"),
    ("inactive", "emissive"),
    ("bare-bone", "flesh-intact"),
    ("interior-place", "large-scale"),
    ("pacifist-role", "violent-act"),
    ("funerary-place", "rural-landmark"),
    ("two-handed-weapon", "hand-occupying"),
    ("self-coloured", "states-a-colour"),
    ("pacifist-role", "firearm"),
    ("held-item", "hand-occupying"),
    ("held-item", "two-handed-weapon"),
    ("chest-located", "chest-located"),
    ("inactive", "open-eyed"),
    ("face-hidden", "face-feature"),
    ("both-hands-act", "carried-weapon"),
    ("lantern-hand", "carried-weapon"),
    ("lantern-hand", "held-item"),
)
TRAIT_REASONS: dict[str, str] = {
    "inactive|powered-act": "a thing at rest does not act",
    "inactive|emissive": "a thing at rest shows no light of its own",
    "bare-bone|flesh-intact": "a skeleton has no flesh to rot",
    "interior-place|large-scale": "a room cannot hold something huge",
    "pacifist-role|violent-act": "a priest does not kill",
    "funerary-place|rural-landmark": "a windmill belongs to a farm, not a graveyard",
    "two-handed-weapon|hand-occupying": "both hands are already full",
    "self-coloured|states-a-colour": "a material that names its own colour fixes it",
    "pacifist-role|firearm": "a priest does not carry a gun",
    "held-item|hand-occupying": "both hands are already full",
    "held-item|two-handed-weapon": "both hands are already full",
    "chest-located|chest-located": "a clutched locket and a light in the chest share one place",
    "inactive|open-eyed": "a slumbering thing does not stare",
    "face-hidden|face-feature": "a hidden face shows no mouth or eyes",
    "both-hands-act|carried-weapon": "both hands are busy, so the weapon is put away",
    "lantern-hand|carried-weapon": "one hand holds the lantern the warden is named for",
    "lantern-hand|held-item": "one hand holds the lantern the warden is named for",
}


def _tag_code(code: str) -> str:
    return {"c": TAG_CONFLICT_ONLY, "p": TAG_PEACEFUL_ONLY}.get(code, TAG_NEUTRAL)


#: Graphic values outside the situations. "No gore" hides every one of them.
#: Round XVI: stepped up substantially -- "Gore only" read as barely
#: different from "Any" with 9 situations and ~11 values behind it. Both are
#: now roughly tripled.
_GORE = {
    "condition": ("blood-soaked",),
    "surface_detail": ("dripping fresh blood", "exposed ribs", "blood-matted fur around the muzzle",
                       "weeping sores", "blood-spattered sleeves", "torn-open gut wound",
                       "glistening exposed muscle", "fresh claw-mark gashes", "raw weeping flesh"),
    "aperture": ("blood-smeared mouth", "cracked bleeding lips", "gore-clotted maw"),
    "armament": ("butcher's cleaver", "curved sacrificial knife", "gore-slicked axe"),
}
_RELATION_CONFLICT = frozenset({
    "stalking", "hunting", "attacking", "cornering",
})


def _tags_for(field: str, pools: dict[str, tuple[str, ...]]) -> dict[str, str]:
    gore = set(_GORE.get(field, ()))
    return {
        value: (TAG_CONFLICT_ONLY if value in gore else TAG_NEUTRAL)
        for pool in pools.values() for value in pool
    }


TAGS: dict[str, dict[str, str]] = {
    "subkind": _tags_for("subkind", SUBKIND_POOLS),
    "condition": _tags_for("condition", CONDITION_POOLS),
    "surface_detail": _tags_for("surface_detail", SURFACE_DETAIL_POOLS),
    "armament": _tags_for("armament", ARMAMENT_POOLS),
    "aperture": _tags_for("aperture", APERTURE_POOLS),
    SITUATION_FIELD: {v: _tag_code(code) for v, code in _SITUATION_TAG_CODES.items()},
    RELATION_FIELD: {
        v: (TAG_CONFLICT_ONLY if v in _RELATION_CONFLICT else TAG_NEUTRAL)
        for v in RELATION_POOL
    },
}


# ---------------------------------------------------------------------------
# Lint tables
# ---------------------------------------------------------------------------

AFFORDANCE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "ground": ("ground", "earth", "brush", "tree line", "trees", "trunks", "undergrowth",
               "lawn", "drive"),
    "structure": ("wall", "walls", "door", "doors", "doorway", "window", "hallway", "corridor",
                  "staircase", "stairs", "ceiling", "room", "rooftop", "shelf", "crypt"),
    "grave": ("grave", "headstone"),
    "shoreline": ("shallows", "surface of the", "black water"),
    "submerged": ("silt", "depths", "sunken", "murky water"),
    "sky": ("sky", "telephone pole"),
    "cold": ("ice",),
}
AFFORDANCE_LINT_FIELDS: tuple[str, ...] = ("situation", "context", "subkind")
AFFORDANCE_ALLOWLIST: frozenset[str] = frozenset({
    # A role, not a place: a grave robber is still one in a town street.
    "grave robber",
    # Named for what it is, not where it stands; its needs are declared.
    "thing beneath the ice", "boarded-up church", "boarded-up village square",
    "hospital corridor after closing", "peeling hotel hallway",
})

STANCE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "walks": ("shambling", "wading", "stumbling", "charging", "running"),
    "swims": ("drifting upright",),
    "climbs": ("crawling along the ceiling",),
    "floats": ("hovering", "gliding"),
}

BODY_FEATURES: dict[str, frozenset[str]] = {
    "undead": frozenset({"hands", "jaws"}),
    "spirit": frozenset({"hands"}),
    "cryptid": frozenset({"jaws"}),
    "werewolf": frozenset({"jaws", "hands"}),
    "watcher": frozenset({"hands", "antlers"}),
    "moth-winged watcher": frozenset({"hands", "wings"}),
    "hollow-eyed stag": frozenset({"jaws", "antlers"}),
    "crawler": frozenset({"hands", "jaws"}),
    "effigy": frozenset({"hands"}),
    "eldritch horror": frozenset({"jaws", "tentacles"}),
    "mortal": frozenset({"hands", "jaws"}),
    "cursed object": frozenset(),
    "haunted place": frozenset(),
}
BODY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "hands": ("hand", "hands", "finger", "fingers", "fist"),
    "jaws": ("jaw", "teeth", "lips"),
    "tentacles": ("tentacles",),
    "wings": ("wings",),
    "antlers": ("antler", "antlers"),
}
BODY_LINT_FIELDS: tuple[str, ...] = ("situation",)
PART_KEYWORDS: dict[str, tuple[str, ...]] = {
    "wings": ("wing",),
    "antlers": ("antler",),
    "tentacles": ("tentacle",),
}
PART_LINT_FIELDS: tuple[str, ...] = (
    "appendages", "armament", "extras", "emitters", "sensors", "aperture", "surface_detail",
)

#: Words from another genre: a model draws each as the sci-fi thing.
FOREIGN_NOUNS: tuple[str, ...] = (
    "laser", "robot", "spaceship", "starship", "cyber", "hologram", "drone", "alien",
    "plasma", "android", "mech",
)
FOREIGN_NOUN_FIELDS: tuple[str, ...] = (
    "kind", "subkind", "scale", "condition", "form", "material", "primary_color",
    "accent_color", "markings", "surface_detail", "appendages", "emitters",
    "armament", "sensors", "aperture", "extras", "situation", "relation",
    "relation_position", "context", "environment",
)


# ---------------------------------------------------------------------------
# Archetypes
# ---------------------------------------------------------------------------

_SELF_NAMING_HEAD = HeadPhrase(noun=("subkind", "kind"), modifiers=("scale", "condition"))
_MADE_HEAD = HeadPhrase(noun=("subkind", "kind"), modifiers=("scale", "condition"), apposition="kind")

_THEY = dict(
    pronoun="they", pronoun_plural="they", possessive="their", possessive_plural="their",
    pronoun_copula="are", pronoun_object="them", pronoun_object_plural="them",
)

ARCHETYPES: dict[str, Archetype] = {
    # A walking corpse, a vampire: a body in what it was buried in.
    "dead": Archetype(
        head_phrase=_SELF_NAMING_HEAD,
        detail_cap=11,
        detail_priority=("form", "subkind", "material", "primary_color", "sensors", "aperture"),
        detail_rotation_slots=2,
        detail_rotation={"surface_detail": 1.0, "appendages": 0.9, "extras": 0.7, "armament": 0.7,
                         "emitters": 0.6, "markings": 0.5, "accent_color": 0.3},
        sentences=(
            Sentence(text="{subject} {copula} {situation}."),
            Sentence(text="{subject}."),
            Sentence(text="{pronoun} has {form}[, clad in {material}]."),
            Sentence(text="{pronoun} {pronoun_copula} clad in {material}."),
            Sentence(text="{pronoun} {pronoun_copula} {primary_color}."),
            Sentence(text="{pronoun} shows {surface_detail}."),
            Sentence(text="{pronoun} features {appendages, sensors, extras}."),
            Sentence(text="{pronoun} carries {armament}."),
            # Split for the same reason as the spirit and creature archetypes
            # below: joined, an emitter read as glowing out of the aperture
            # beside it (a jaw with light spilling from it, not a lit eye).
            Sentence(text="{pronoun} glimmers with {emitters}."),
            Sentence(text="{pronoun} bears {aperture}."),
            Sentence(text="{pronoun} {pronoun_copula} marked with {markings, accent_color}."),
        ),
    ),
    # A ghost: a shape made of a substance; nothing carried.
    "spirit": Archetype(
        head_phrase=_SELF_NAMING_HEAD,
        omits=frozenset({"armament", "sensors"}),
        detail_cap=9,
        detail_priority=("form", "subkind", "material", "primary_color", "emitters", "aperture"),
        detail_rotation_slots=1,
        detail_rotation={"appendages": 1.0, "surface_detail": 0.8, "extras": 0.6, "markings": 0.5,
                         "accent_color": 0.3},
        sentences=(
            Sentence(text="{subject} {copula} {situation}."),
            Sentence(text="{subject}."),
            Sentence(text="{pronoun} takes {form}[, made of {material}]."),
            Sentence(text="{pronoun} {pronoun_copula} made of {material}."),
            Sentence(text="{pronoun} {pronoun_copula} {primary_color}."),
            Sentence(text="{pronoun} shows {surface_detail}."),
            Sentence(text="{pronoun} features {appendages}."),
            Sentence(text="{pronoun} clutches {extras}."),
            # emitters and aperture used to share one clause ("bears a flame
            # and a mouth"), which read as the light coming from the mouth --
            # a glowing maw where none was drawn. Split so a light source is
            # never grammatically anchored to an opening.
            Sentence(text="{pronoun} glimmers with {emitters}."),
            Sentence(text="{pronoun} bears {aperture}."),
            Sentence(text="{pronoun} {pronoun_copula} marked with {markings, accent_color}."),
        ),
    ),
    # A cryptid or an eldritch horror: a body built from parts.
    "creature": Archetype(
        head_phrase=_SELF_NAMING_HEAD,
        detail_cap=12,
        detail_priority=("form", "subkind", "material", "primary_color", "appendages", "sensors",
                         "aperture", "scale"),
        detail_rotation_slots=1,
        detail_rotation={"armament": 1.0, "markings": 0.8, "emitters": 1.0, "extras": 0.5,
                         "surface_detail": 0.8, "accent_color": 0.3},
        sentences=(
            Sentence(text="{subject} {copula} {situation}."),
            Sentence(text="{subject}."),
            Sentence(text="{pronoun} has {form}[, covered in {material}]."),
            Sentence(text="{pronoun} {pronoun_copula} covered in {material}."),
            Sentence(text="{pronoun} {pronoun_copula} {primary_color}."),
            Sentence(text="{pronoun} shows {surface_detail}."),
            Sentence(text="{pronoun} features {appendages, armament, sensors, extras}."),
            # Split for the same reason as the spirit archetype above: joined,
            # an inner light read as glowing out of the maw beside it.
            Sentence(text="{pronoun} glimmers with {emitters}."),
            Sentence(text="{pronoun} bears {aperture}."),
            Sentence(text="{pronoun} {pronoun_copula} marked with {markings, accent_color}."),
        ),
    ),
    # A person: a cultist, a stalker, a survivor.
    "figure": Archetype(
        head_phrase=_SELF_NAMING_HEAD,
        omits=frozenset({"scale"}),
        detail_cap=10,
        templates={"material": "{a_value}"},
        detail_priority=("form", "subkind", "material", "primary_color", "aperture", "armament"),
        # Round XVI: ``extras`` moved out of the fixed head and into rotation,
        # alongside ``emitters`` -- both used to be near-guaranteed on every
        # figure, so a survivor drew a weapon, a lantern and a first-aid kit in
        # the same clause. They now compete for the same rotation slots as
        # fantasy and sci-fi already do, and ``emitters`` gets its own
        # sentence instead of piling into "carry" -- fantasy's exact pattern.
        detail_rotation_slots=2,
        detail_rotation={"emitters": 1.0, "extras": 1.0, "appendages": 0.8, "surface_detail": 0.8,
                         "markings": 0.6, "sensors": 0.5, "accent_color": 0.4},
        sentences=(
            Sentence(text="{subject} {copula} {situation}."),
            Sentence(text="{subject}."),
            Sentence(text="{pronoun} have {form} and wear {material}."),
            Sentence(text="{pronoun} wear {material}."),
            Sentence(text="{pronoun} have {form}."),
            Sentence(text="{possessive} clothing is {primary_color}."),
            Sentence(text="{pronoun} show {surface_detail}."),
            # Joined, "mud-spattered hems and funeral-purple accents" drew
            # purple splashed on the coat; apart, the accent is a trim.
            Sentence(text="{possessive} clothing bears {markings}."),
            Sentence(text="{possessive} clothing has {accent_color}."),
            Sentence(text="{pronoun} carry {armament, extras}."),
            Sentence(text="{pronoun} wear {appendages}."),
            Sentence(text="{possessive} features include {sensors}."),
            # Split, the same reason as the other archetypes below: joined,
            # a held light (a candle, a lantern) read as glowing out of the
            # mouth beside it instead of held in the hand.
            Sentence(text="{pronoun} glimmer with {emitters}."),
            Sentence(text="{pronoun} show {aperture}."),
        ),
        **_THEY,
    ),
    # A cursed keepsake: it rests on something.
    "object": Archetype(
        head_phrase=_SELF_NAMING_HEAD,
        omits=frozenset({"armament"}),
        detail_cap=8,
        detail_priority=("form", "subkind", "material", "extras", "primary_color", "sensors"),
        detail_rotation_slots=1,
        detail_rotation={"surface_detail": 1.0, "markings": 1.0, "aperture": 0.8,
                         "appendages": 0.6, "emitters": 0.6, "accent_color": 0.3},
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
            Sentence(text="{pronoun} has {sensors, appendages}."),
            Sentence(text="{pronoun} glimmers with {emitters}."),
            Sentence(text="{pronoun} bears {aperture}."),
        ),
    ),
    # A mirror, a portrait, a clock: a furnishing in its room.
    "furnishing": Archetype(
        head_phrase=_SELF_NAMING_HEAD,
        omits=frozenset({"armament"}),
        detail_cap=8,
        detail_priority=("form", "subkind", "material", "extras", "primary_color", "sensors"),
        detail_rotation_slots=1,
        detail_rotation={"surface_detail": 1.0, "markings": 1.0, "aperture": 0.8,
                         "appendages": 0.6, "emitters": 0.6, "accent_color": 0.3},
        sentences=(
            Sentence(text="{subject} {copula} {situation}."),
            Sentence(text="{subject}."),
            Sentence(text="{pronoun} takes the form of {form}, made of {material}."),
            Sentence(text="{pronoun} {pronoun_copula} made of {material}."),
            Sentence(text="{pronoun} takes the form of {form}."),
            Sentence(text="{pronoun} is set against {extras}."),
            Sentence(text="{pronoun} {pronoun_copula} {primary_color}."),
            Sentence(text="{pronoun} shows {surface_detail}."),
            Sentence(text="{pronoun} {pronoun_copula} marked with {markings, accent_color}."),
            Sentence(text="{pronoun} has {sensors, appendages}."),
            Sentence(text="{pronoun} glimmers with {emitters}."),
            Sentence(text="{pronoun} bears {aperture}."),
        ),
    ),
    # A house, a chapel, a ride: a silhouette.
    "place": Archetype(
        head_phrase=_SELF_NAMING_HEAD,
        omits=frozenset({"sensors", "armament"}),
        detail_cap=8,
        detail_priority=("form", "subkind", "material", "primary_color", "scale", "condition",
                         "appendages"),
        detail_rotation_slots=1,
        detail_rotation={"surface_detail": 1.0, "aperture": 1.0, "emitters": 0.8, "markings": 0.6,
                         "extras": 0.6, "accent_color": 0.3},
        sentences=(
            Sentence(text="{subject} {copula} {situation}."),
            Sentence(text="{subject}."),
            Sentence(text="{pronoun} is built as {form}[, made of {material}]."),
            Sentence(text="{pronoun} is built of {material}."),
            Sentence(text="{possessive} walls are {primary_color}."),
            Sentence(text="{pronoun} shows {surface_detail}."),
            Sentence(text="{pronoun} features {appendages, extras}."),
            Sentence(text="{pronoun} glimmers with {emitters}."),
            Sentence(text="{pronoun} bears {aperture}."),
            Sentence(text="{pronoun} {pronoun_copula} marked with {markings, accent_color}."),
        ),
    ),
    # The stranger's grammar, for a foreign-genre entity wired into a horror scene.
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
            Sentence(text="{pronoun} glimmers with {emitters}."),
            Sentence(text="{pronoun} bears {aperture}."),
        ),
    ),
}

ARCHETYPE_OF_KIND: dict[str, str] = {
    "undead": "dead", "spirit": "spirit", "cryptid": "creature", "eldritch horror": "creature",
    "mortal": "figure", "cursed object": "object", "haunted place": "place",
}
ARCHETYPE_OF_SUBKIND: dict[str, str] = {
    **{v: "furnishing" for v in SUBKIND_GROUPS["furnishing"]},
}


# ---------------------------------------------------------------------------
# Spoken forms, motifs, prose
# ---------------------------------------------------------------------------

def _hyphenated(tokens) -> dict[str, str]:
    return {token: token.replace(" ", "-") for token in tokens if " " in token}


_SPOKEN_ENVIRONMENT: dict[str, str] = {
    # Said plainly it rendered as a furnished room with a picture hanging in mid-air.
    "void of drifting furniture": "endless black void with old furniture drifting in it",
}

_SPOKEN_SUBKIND: dict[str, str] = {
    **{value: value for pool in SUBKIND_POOLS.values() for value in pool},
    # A bare word a model draws as something else.
    "ghoul": "grey-skinned ghoul",
    "bog body": "risen bog body",
    "ghost": "ghost apparition",
    "poltergeist": "poltergeist spirit",
    "werewolf": "snarling werewolf",
}

SPOKEN: dict[str, dict[str, str]] = {
    "subkind": _SPOKEN_SUBKIND,
    "environment": _SPOKEN_ENVIRONMENT,
    "primary_color": _hyphenated(PRIMARY_COLOR_POOL),
    "accent_color": _hyphenated(ACCENT_COLOR_POOL),
    "emitter_color": _hyphenated(EMITTER_COLOR_POOL),
}

MOTIFS: dict[str, tuple[str, ...]] = {
    "blood": ("blood", "bloodied", "bloodstained"),
    "rot": ("rot", "rotting", "mould", "decay"),
    "bone": ("bone", "skull", "skeleton"),
    "water": ("water", "drowned", "sodden", "flooded"),
}

PROSE = ProseSpec(
    scene_order=("environment", "entities", "relations"),
    narrative_mode=True,
    environment_sentence="A horror scene set in {a_value}",
    environment_staging=(
        ("submerged", ", deep underwater"),
    ),
    context_sentences=(
        Sentence(text="Behind {pronoun_object} is {a_context}."),
        Sentence(text="{a_context} is visible behind {pronoun_object}."),
        Sentence(text="The background shows {a_context}."),
        Sentence(text="Beyond {pronoun_object}, {a_context} is visible."),
        Sentence(text="In the distance, {a_context} is visible.", needs=frozenset({"vast"})),
        Sentence(text="Further back, {a_context} is visible.", needs=frozenset({"vast"})),
    ),
    scene_frame="A horror scene",
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
        "form", "subkind", "material", "primary_color", "condition", "scale", "aperture",
        "sensors", "armament", "appendages", "emitters", "markings", "surface_detail",
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


# ---------------------------------------------------------------------------
# Round XXIII -- the 923 evening batch
# ---------------------------------------------------------------------------

# Rain came indoors with a "rain-soaked" coat (#579, #629).
_RAIN = frozenset({"sky"})
VALUE_NEEDS.setdefault("material", {}).update({
    "rain-soaked trench coat": _RAIN, "rain-soaked cassock": _RAIN,
})
VALUE_NEEDS.setdefault("condition", {})["rain-soaked"] = _RAIN
VALUE_NEEDS.setdefault("surface_detail", {})["rain-soaked clothing"] = _RAIN
# Candles, dust, ivy and wind on the floor of a drowned church: acts that take
# place in air, and said so only in their words.
for _v in (
    "sniffing the air like an animal",
    "sniffing the air hungrily",
    "rushing forward in a sudden gust of cold air",
    "hovering motionless in the air",
    "tasting the air with a dozen tongues",
    "smashing a lantern at their feet",
    "setting down a single candle",
    "burning herbs in an iron bowl",
    "laying out cards by candle stub",
    "praying quietly by candle stub",
    "marked by a small handprint in its dust",
    "belching dust from within",
    "standing with a candle burning behind one pane",
    "swallowed by creeping ivy",
    "trailing a thin curl of chimney smoke",
    "creaking in a steady wind",
    "sagging under heavy rain",
):
    VALUE_NEEDS[SITUATION_FIELD][_v] = VALUE_NEEDS[SITUATION_FIELD].get(_v, frozenset()) | frozenset({"air"})
# #636 a poltergeist hurled dishes "across the room" on a fishing pier.
VALUE_NEEDS[SITUATION_FIELD].update({
    "hurling dishes across the room": frozenset({"room", "structure"}),
    "stacking chairs into a crooked tower": frozenset({"room", "structure"}),
})
# #644 floral wallpaper in a flesh-walled chamber: its walls are flesh, and
# furniture belongs in the rooms of the otherworld that have any.
PLACE_AFFORDANCES["flesh-walled chamber"] = PLACE_AFFORDANCES["otherworld"] - {"room"}
# A drowned place is ``aqueous``, the shared trait word another genre's fire
# creature refuses: a fire elemental burned in a drowned church nave (#597).
_add_traits(ENVIRONMENT_FIELD, {v: ("aqueous",) for v in _ENV_UNDERWATER})
# #637 a stuffed body on a post stays on its post.
VALUE_STANCES["form"]["sagging stuffed body on a post"] = frozenset({"rests"})

# #579 a lantern-bearing warden with a rifle as well.
# #641 a stalker "smashing a lantern at their feet" with a lit lantern in hand.
_add_traits(SITUATION_FIELD, {"smashing a lantern at their feet": ("lantern-act",)})
_add_traits(SITUATION_FIELD, {v: ("firearm",) for v in (
    "checking a bolt-action rifle with shaking hands", "loading shells into a shotgun",
)})
_add_traits("emitters", {v: ("lantern-light",) for v in ("hooded lantern", "guttering candle")})
# #640 a slumbering amalgam screaming with its maw open.
_add_traits("aperture", {v: ("gaping",) for v in ("ring-shaped toothed maw", "gaping mouth")})

TRAIT_CONFLICTS = TRAIT_CONFLICTS + (
    ("lantern-hand", "firearm"),
    ("lantern-act", "lantern-light"),
    ("lantern-hand", "lantern-act"),
    ("inactive", "gaping"),
)
TRAIT_REASONS.update({
    "lantern-hand|firearm": "one hand holds the lantern, and a rifle needs two",
    "lantern-act|lantern-light": "the lantern being smashed is the only one",
    "lantern-hand|lantern-act": "the warden does not smash the lantern they are named for",
    "inactive|gaping": "a slumbering thing keeps its maw shut",
})


HORROR_PACK = GenrePack(
    slug="horror",
    display="Horror",
    class_suffix="Horror",
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
    scene_filter_labels=OrderedDict((
        ("No gore", "Peaceful"), ("Any", "Any"), ("Gore only", "Conflict"),
    )),
    scene_filter_default="No gore",
    scene_filter_tooltip=(
        "What random draws may pick. 'No gore' (the default) leaves graphic wounds, blood and "
        "killing out of the description entirely; 'Gore only' favours them. A value you lock "
        "yourself is always kept."
    ),
)
