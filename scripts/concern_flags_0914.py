"""Round XI concern flags -- the render-trap classes from the 2026-09-14 batch. Frozen; do not
edit to make a task pass.

The round-X instrument (``scripts/concern_flags.py``) catches structural illegality: a thing
where it cannot stand, an action its body cannot take. This one catches the classes the 914
batch actually showed, which are legal draws whose *words* a text-to-image model renders as
the wrong object -- a "tether" becomes a chain, a "bladder-pod" a balloon, a "starliner" an
airliner. Every flag here was read off a named image in that batch.

An instrument, not a gate: ``tests/`` owns the gates. The definitions are frozen once
committed and are never edited to make a task pass.
"""
from __future__ import annotations

import re

from data.genre import affordances_of, group_of

EMPTY = str()

#: Kinds whose body a drag/tow/hail needs a grip or a limb to perform.
_DRAG_CREATURE_GROUPS = frozenset({
    "diffuse being", "amorphous", "sessile growth", "void dweller", "mimic body",
    "filter swarm", "symbiotic body", "brooding colony",
})
#: Ship types that are civilian by role, so a weapon on one is a contradiction.
_CIVILIAN_SHIPS = frozenset({
    "starliner", "hospital ship", "colony ship", "generation ship", "survey vessel",
    "survey cutter", "supply ship",
})
#: People who carry no heavy weapon.
_CIVILIAN_PEOPLE = frozenset({
    "scientist", "colonist", "archaeologist", "cartographer", "crew technician",
})
_HEAVY_WEAPONS = frozenset({
    "shoulder launcher", "grenade bandolier", "mag-rifle", "energy carbine",
})
#: A room with furniture in it; a small subject reads as a tabletop ornament there.
_FURNISHED_ROOMS = frozenset({
    "crew galley", "crew quarters", "medical bay", "chapel", "brig",
})
_CIVILIAN_SHIP_ATTACKS = (
    r"(firing a full weapons array|launching interceptors|firing point-defence|"
    r"standing guard over)"
)

#: Every class this instrument reports. All are gated once the round lands.
STRUCTURAL_0914: frozenset[str] = frozenset({
    "person-open-face-hostile",
    "helmet-carried",
    "face-condition-hostile",
    "earthcraft-in-atmosphere",
    "tether-cable-chain",
    "drag-without-grip",
    "earth-container",
    "egg-bladder-balloon",
    "net-web-mesh",
    "bone-scenery",
    "fish-bird-scenery",
    "cloud-sit-at-ground",
    "jump-in-atmosphere",
    "midair-underwater",
    "article-on-plural-head",
    "walker-without-legs",
    "ice-tool-without-cold",
    "civilian-armed",
    "grown-hull-metal",
    "small-subject-furnished-room",
    "crew-without-floor",
})


def field(record, name):
    """A record's value as text, empty when unset."""
    value = record.get(name)
    return value if value else EMPTY


def flags_0914(pack, doc, text):
    """Every round-XI render-trap class the first entity of ``doc`` falls into."""
    out: list[str] = []
    if not doc["entities"]:
        return out
    e = doc["entities"][0]
    env = field(doc, "environment")
    aff = affordances_of(pack, env)
    kind, sub, form = e.get("kind"), e.get("subkind"), field(e, "form")
    grp = group_of(pack, "subkind", sub) if sub else None
    sit = field(e, "situation").lower()
    ctx = field(doc, "context").lower()
    material = field(e, "material").lower()
    low = text.lower()
    hostile = bool(aff & {"open-space", "submerged"})

    if (kind == "spacefarer" and hostile
            and not re.search(r"\bwear an? [^.]*\bhelmet\b", low)):
        out.append("person-open-face-hostile")
    if re.search(r"\bcarry [^.]*\bhelmet", low):
        out.append("helmet-carried")
    if (kind == "spacefarer" and hostile
            and e.get("condition") in ("exhausted", "scarred", "sunburnt")):
        out.append("face-condition-hostile")
    if (kind in ("starship", "wreck", "surface vehicle") and "open-space" not in aff
            and re.search(
                r"\b(wings?|winged|lifting-body|glider|fuselage|crescent hull|stacked-deck|"
                r"terrace hull|prow|blunt-nosed|twin-hulled|boxy cargo hull|starliner|"
                r"airliner|jet)\b", low)):
        out.append("earthcraft-in-atmosphere")
    if re.search(r"\b(tether\w*|cables?|chains?|ropes?)\b",
                 " ".join([sit, ctx, field(e, "extras").lower(),
                           field(e, "appendages").lower()])):
        out.append("tether-cable-chain")
    if (re.search(r"\b(dragg\w*|haul\w*|tow\w*|tugg\w*)\b", sit)
            and (kind == "wreck"
                 or (kind == "robot or mech" and grp != "humanoid unit")
                 or (kind == "alien creature" and grp in _DRAG_CREATURE_GROUPS))):
        out.append("drag-without-grip")
    if re.search(r"\b(canisters?|drums?|barrels?|buckets?|pails?|kegs?)\b",
                 low.replace("barrel-chested", "")):
        out.append("earth-container")
    if re.search(r"\b(eggs?|bladders?|bladder-\w+|balloons?)\b", low):
        out.append("egg-bladder-balloon")
    if re.search(r"\b(nets?|netting|webs?|webbing|mesh)\b", low):
        out.append("net-web-mesh")
    if (re.search(r"\b(spine|skeleton|bones?|ribs?)\b", ctx)
            or (kind != "alien creature" and re.search(r"\bspine\b", sit))):
        out.append("bone-scenery")
    if re.search(r"\b(shoal|swimmers?|fish|wings|flock)\b", ctx):
        out.append("fish-bird-scenery")
    if (kind != "celestial body"
            and re.search(
                r"\b(cloud tops|storm band|cloud bank|cloud columns|lightning front|"
                r"thermal column|updraft|downdraft|the clouds)\b", sit)
            and aff & {"ground", "floor"}
            # A place that affords a cloud deck is above the clouds on purpose:
            # a floating platform has a floor and a cloud deck at once.
            and "cloud-deck" not in aff):
        out.append("cloud-sit-at-ground")
    if re.search(r"\b(jump|breaking orbit)\b", sit) and "open-space" not in aff:
        out.append("jump-in-atmosphere")
    if re.search(r"\b(mid-air|out of the air|into the wind)\b", sit) and "submerged" in aff:
        out.append("midair-underwater")
    if re.search(r"\ban? (?:[a-z-]+ ){0,4}[a-z-]+s (?:parted|split)\b", low):
        out.append("article-on-plural-head")
    if sub and "walker" in sub and re.search(
            r"(serpentine|tracked|wheel|disc|spherical|boxy|gantry)", form):
        out.append("walker-without-legs")
    if sub == "ice cutter" and "cold" not in aff:
        out.append("ice-tool-without-cold")
    if ((sub in _CIVILIAN_SHIPS
         and (e.get("armament") or re.search(_CIVILIAN_SHIP_ATTACKS, sit)))
            or (sub in _CIVILIAN_PEOPLE and e.get("armament") in _HEAVY_WEAPONS)):
        out.append("civilian-armed")
    if sub in ("bioship", "fossilised bioship") and re.search(
            r"(steel|chrome|alloy|titanium|foil|aluminium|ferro)", material):
        out.append("grown-hull-metal")
    if env in _FURNISHED_ROOMS and e.get("scale") in ("tiny", "small"):
        out.append("small-subject-furnished-room")
    if (re.search(r"\b(the crew|survey team|armed cordon)\b", sit)
            and "sky" in aff and "floor" not in aff):
        out.append("crew-without-floor")
    return out
