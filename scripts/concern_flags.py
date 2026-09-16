"""Concern audit flags -- the defect classes users reported, checked on one scene.

An instrument, not a gate: ``tests/`` owns the gates. The definitions are frozen at
the 2026-09-13 baseline (see docs/architecture.md) and were checked against a batch
the user labelled by eye. A name starting ``info-`` is reported and never gated.
"""
from __future__ import annotations

import re

from data.genre import _supported_stances, affordances_of, group_of, pool_for, resolved_needs

EMPTY = str()
ENCLOSED = frozenset({"subsurface ice cavern", "hollowed geode cavern",
                      "deep ocean trench of a water world", "domed colony street"})
NONCOMBAT_ROBOTS = frozenset({"labour droid", "repair drone", "survey drone", "mining loader",
                              "cargo hauler unit", "medical automaton", "terraforming walker",
                              "courier drone", "welding drone"})
ROBOT_WEAPONS = frozenset({"shoulder cannon", "arm-mounted repeater", "missile pod",
                           "gauss rifle mount", "flame projector", "chain blade", "stun emitter",
                           "micro-missile cell", "needle gun mount"})
CLAWLESS_ROBOTS = frozenset({"medical automaton", "courier drone", "survey drone", "android",
                             "swarm drone"})
BIG = frozenset({"siege mech", "combat mech", "terraforming walker", "mining loader", "monolith",
                 "obelisk", "gate ring", "sealed gateway", "resonant lattice spire", "alien engine",
                 "dreadnought", "strike carrier", "generation ship", "colony ship",
                 "heavy freighter"})
SMALL = frozenset({"courier drone", "swarm drone", "survey drone", "repair drone", "welding drone",
                   "hover bike", "drop pod", "data core", "relic sphere", "memory shard"})
INACTIVE = frozenset({"mothballed", "unfinished", "half-built", "half-disassembled"})
ARRAY_COUNTS = frozenset({"a ring of", "a dozen", "rows of", "banks of", "a constellation of",
                          "eight", "six"})
SELF_POWERED = (
    r"\b(full throttle|at speed|circling|cresting|climbing|grinding up|racing|banking|towing|"
    r"extending|raising|lowering|backing up|reversing|turning to face|braking|spinning out|nosing|"
    r"following a set|crawling along|crossing|parking|idling|rolling to present|flaring its drive|"
    r"decelerating|holding formation|holding position|matching course|running a course|running dark|"
    r"sweeping|firing|launching|deploying|docking|breaking orbit|signalling|projecting|scanning|"
    r"spraying|welding|drilling|hoisting|cutting|prying|striding|stamping|carrying|lifting|catching|"
    r"levelling|unloading|dropping toward|ramming|punching through|driving through)\b"
)
LEGGED_FORM = (r"(walker|leg|bipedal|quadrupedal|hexapod|strider|tripod|crawler chassis|android|"
               r"humanoid|arachnoid|grazer frame|raptor|winged frame|four-armed)")
WHEELED_FORM = r"(wheel|tracked|rover|buggy|crawler train|hauler frame|two-section)"
COILER_FORM = r"(serpent|worm|tentacle|helical|coil|ribbon)"
GROUND_WORDS = (r"\b(ground|sand|grit|mud|gravel|scree|soil|ridge|canyon|dune|slope|cliff|boulder|"
                r"ruts|riverbed|cave mouth|rock outcrop|salt flat|a rise|landing site|landing pad|"
                r"landing hard)\b")
STRUCT_WORDS = (r"\b(door|doorway|hatch|airlock|corridor|bulkhead|ceiling|vents|console|seat|"
                r"cockpit|the hold|gantry|catwalk|ladder|shaft|cryo|girders|falling beam)\b")
GRAVITY_WORDS = (r"\b(falling|falls|under its own weight|slide|avalanche|slumping|burying|"
                 r"down a slope|mid-air|out of the air|off their feet)\b")
WATER_WORDS = r"\b(water|surf|shore|wake through)\b"
SPACE_WORDS = r"\b(orbit|the void|vacuum|the stars|star field|debris field|asteroid field)\b"
EARTH_WORDS = (r"\b(ships?|freighters?|frigates?|lamps?|lanterns?|derricks?|cranes?|trucks?|"
               r"trailers?|sleds?|galley|overalls?|vests?|jackets?|batons?|tribal|hitch|"
               r"exhaust pipes?|desert|beach|lakes?|forest|jungle|swamp|boats?|planes?|convoys?|"
               r"tankers?|barges?|tugs?|buoys?|crates?|catwalks?|satellites?)\b")
PART_MATERIAL = r"\b(canopy|rubber|overall|vest|jacket|padding)\b"
STELLAR_WRONG = (r"\b(auroras?|frost|canyon|continent|crater|geysers|crust|storm oval|cloud belts|"
                 r"cloud bands|terminator|halves|moonlet|rift)\b")
POLAR = r"\b(poles?|polar)\b"


def field(record, name):
    """A record's value as text, empty when unset."""
    value = record.get(name)
    return value if value else EMPTY


def flags(pack, doc, text):
    """Every concern class the first entity of ``doc`` falls into, as short names."""
    out: list[str] = []
    if not doc["entities"]:
        return out
    e = doc["entities"][0]
    env = field(doc, "environment")
    aff = affordances_of(pack, env)
    support = _supported_stances(pack, env)
    kind, sub, form = e.get("kind"), e.get("subkind"), field(e, "form")
    grp = group_of(pack, "subkind", sub) if sub else None
    raw_sit = e.get("situation")
    sit = field(e, "situation").lower()
    ctx = field(doc, "context").lower()
    stances = pack.value_stances.get("form", {}).get(form) if form else None
    gravity = bool(aff & {"ground", "floor", "sky", "shoreline", "submerged"})
    open_only = "open-space" in aff and not (aff & {"structure", "dock", "floor", "ground"})
    if kind and not form and sub and pool_for(pack, "form", {"kind": kind, "subkind": sub}):
        out.append("noform")
    if stances and not (stances & support):
        out.append("subject-cannot-stand")
    if (kind == "spacefarer" and open_only
            and "open-space" not in resolved_needs(pack, "situation", raw_sit or EMPTY)):
        out.append("person-in-void")
    if kind == "alien creature" and open_only and grp not in ("diffuse being", "void dweller"):
        out.append("creature-in-void")
    if kind == "robot or mech" and open_only and grp != "small drone":
        out.append("mech-in-void")
    if (kind == "surface vehicle" and not (aff & {"ground", "floor", "shoreline", "submerged"})
            and not (stances and stances & {"hovers", "flies"})):
        out.append("ground-vehicle-in-sky")
    if kind == "starship" and env in ENCLOSED:
        out.append("ship-enclosed")
    if sit and kind != "celestial body":
        if re.search(GROUND_WORDS, sit) and not (aff & {"ground", "floor"}):
            out.append("sit-needs-ground")
        if (re.search(STRUCT_WORDS, sit) and not (aff & {"structure", "dock"})
                and not ("cockpit" in sit and aff & {"ground"})):
            out.append("sit-needs-structure")
        if re.search(GRAVITY_WORDS, sit) and not gravity:
            out.append("sit-needs-gravity")
        if re.search(WATER_WORDS, sit) and not (aff & {"shoreline", "submerged"}):
            out.append("sit-needs-water")
        if re.search(SPACE_WORDS, sit) and "open-space" not in aff:
            out.append("sit-needs-space")
    if sit:
        if (re.search(r"\b(wheels?|hub|axle|treads?|tracks?)\b", sit)
                and kind in ("surface vehicle", "robot or mech")
                and not (grp == "wheeled/tracked" or re.search(WHEELED_FORM, form))):
            out.append("body-no-wheels")
        if (re.search(r"\b(hip|knee|legs?|feet|stamping|striding)\b", sit)
                and kind in ("robot or mech", "alien creature")
                and not re.search(LEGGED_FORM, form)):
            out.append("body-no-legs")
        if (re.search(r"\b(arm|fist|shoulders)\b", sit) and kind == "robot or mech"
                and not re.search(r"(android|humanoid|bipedal|loader|gantry)", form)
                and "arm" not in field(e, "appendages")):
            out.append("body-no-arms")
        if re.search(r"\bscales\b", sit) and "scal" not in field(e, "material") + field(e, "surface_detail"):
            out.append("body-no-scales")
        if (re.search(r"\b(jaws|snout|head to drink)\b", sit)
                and grp in ("diffuse being", "sessile growth", "void dweller", "amorphous")):
            out.append("body-no-jaws")
        if (re.search(r"\bcoil", sit) and kind == "alien creature"
                and not re.search(COILER_FORM, form + " " + field(e, "appendages"))):
            out.append("body-cannot-coil")
    if kind == "celestial body":
        if (grp in ("solid world", "gas world")
                and re.search(r"\b(canyon|continent|slide|crater|fracture lines|geysers)\b", sit)):
            out.append("celestial-surface-scale")
        if (grp in ("star body", "singularity", "binary system", "diffuse cloud", "disc system")
                and re.search(STELLAR_WRONG, sit)):
            out.append("celestial-wrong-body")
        elif grp in ("diffuse cloud", "disc system") and re.search(POLAR, sit):
            out.append("celestial-wrong-body")
        if grp == "solid world" and form in ("banded sphere", "belted sphere"):
            out.append("celestial-gas-form-on-rock")
        if re.search(r"\b(station|landers|beacons|formation|walkway|gantries|figures|freighter)\b", ctx):
            out.append("celestial-scale-context")
    if re.search(EARTH_WORDS, text.lower()):
        out.append("earth-noun")
    if re.search(PART_MATERIAL, field(e, "material")):
        out.append("material-is-a-part")
    if re.search(r"\bcube\b", form):
        out.append("cube")
    if kind == "robot or mech" and sub in NONCOMBAT_ROBOTS and e.get("armament") in ROBOT_WEAPONS:
        out.append("role-weapon")
    if sub in CLAWLESS_ROBOTS and re.search(r"\bclaw", field(e, "armament") + " " + field(e, "appendages")):
        out.append("role-claw")
    if ((e.get("scale") in ("tiny", "small") and sub in BIG)
            or (e.get("scale") in ("massive", "colossal") and sub in SMALL)):
        out.append("scale-contradiction")
    if (kind in ("starship", "robot or mech", "surface vehicle")
            and e.get("condition") in INACTIVE and re.search(SELF_POWERED, sit)):
        out.append("inactive-acting")
    if kind == "wreck" and e.get("emitter_count") in ARRAY_COUNTS:
        out.append("wreck-emitter-array")
    if env in ENCLOSED and re.search(
        r"\b(horizon|landing field|sky|column of dust|freighter column|derrick|survey markers)\b", ctx
    ):
        out.append("context-enclosed")
    for name in ("appendages", "armament", "extras"):
        if re.search(r"\b(claw|pincer)", field(e, name)):
            out.append(f"info-claw-{kind}-{name}")
    return out
