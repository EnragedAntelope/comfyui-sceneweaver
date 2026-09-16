"""Round XII concern flags -- the classes from the 2026-09-15 batch. Frozen; do not edit to
make a task pass.

The round-X instrument (``scripts/concern_flags.py``) catches structural illegality and the
round-XI one (``scripts/concern_flags_0914.py``) catches words a model draws as the wrong
Earth object. This one catches the 915 batch's own classes, and they are a different shape:
the subject is legal, the place is legal, and the *part* does not fit the body it is bolted
to -- a drop pod with a spare track, a submersible with mine ploughs, a survey drone with
three plasma cutters. It also catches a made thing drawn as a building, a body that floats
with nothing saying so, and a still body taking a mobile action.

An instrument, not a gate: ``tests/`` owns the gates. The definitions are frozen once
committed and are never edited to make a task pass.
"""
from __future__ import annotations

import re

from data.genre import affordances_of, group_of

EMPTY = str()

#: Subkinds that are fighting machines; a weapon on one of these is its job.
_COMBAT_SUBKINDS = {
    "combat mech", "siege mech", "security automaton", "sentry unit", "swarm drone",
    "android", "exosuit walker", "scout walker", "ground transport", "walker", "hover bike",
}
#: Subkinds that are working machines; a weapon on one of these is a contradiction.
_CIVIL_MACHINES = {
    "repair drone", "survey drone", "courier drone", "welding drone", "medical automaton",
    "labour droid", "mining loader", "cargo hauler unit", "terraforming walker", "rover",
    "hovercraft", "crawler", "skimmer", "submersible", "high-altitude glider",
    "tracked hauler", "landing shuttlecraft", "drop pod", "sand crawler", "ice cutter",
    "amphibious crawler", "cargo sled", "survey glider",
}
#: Creature groups whose body cannot take a mobile action.
_STILL_CREATURE_GROUPS = {
    "sessile growth", "brooding colony", "symbiotic body", "diffuse being", "void dweller",
}
#: Robot forms with no legs, so a leg appendage on one is bolted to nothing.
_LEGLESS_ROBOT_FORMS = {
    "serpentine segmented chassis", "tracked chassis", "boxy utility chassis",
    "gantry-armed loader frame", "hovering disc chassis", "spherical drone body",
    "wheeled drone body",
}
#: Rooms too small for a heavy frame; a large subject reads as a tabletop ornament there.
_CRAMPED = {
    "cockpit interior", "maintenance crawlway", "airlock chamber", "observation cupola",
    "crew quarters", "brig", "spacecraft corridor", "subterranean moon base corridor",
    "cryogenic stasis bay", "data vault", "medical bay", "chapel", "crew galley",
    "crew commons",
}
#: Frames whose bulk fills a cramped room.
_HEAVY_FRAMES = {
    "exosuit walker", "siege mech", "terraforming walker", "mining loader", "combat mech",
    "scout walker", "cargo hauler unit",
}
#: Apertures that leave a face open; a sealed helmet beside one of these contradicts itself.
_OPEN_FACE = {
    "open visor", "hood opening", "respirator grille", "breathing mask vent",
}
#: Terrain features read at a person's scale, not from space.
_SMALL_WORLD_FEATURES = {
    "lava tube opening", "polar sink hole", "collapsed cave mouth", "sinkhole throat",
    "geothermal vent mouth", "wind-carved dune ripples", "boulder-strewn regolith",
}

#: Every class this instrument reports. All but ``info-fire-situation`` are gated.
STRUCTURAL_0915: frozenset[str] = frozenset({
    "civil-machine-armed",
    "blade-part-on-noncombat",
    "machine-weapon-swarm",
    "jets-on-grounded-body",
    "tracks-on-trackless",
    "legs-on-legless",
    "station-as-building",
    "space-without-float-cue",
    "underwater-without-cue",
    "cloud-deck-without-cue",
    "crowd-actor",
    "fire-word-not-fire",
    "colour-object-word",
    "earth-creature-or-flora",
    "earth-room-word",
    "rain-in-dry-sky",
    "still-body-mobile-action",
    "sealed-helmet-open-face",
    "heavy-body-cramped-room",
    "readable-sign-word",
    "world-small-feature",
})


def flags_0915(pack, doc, text):
    """Every round-XII concern class the first entity of ``doc`` falls into."""
    out: list[str] = []
    if not doc["entities"]:
        return out
    e = doc["entities"][0]
    env = doc.get("environment") or ""
    aff = affordances_of(pack, env)
    kind = e.get("kind")
    sub = e.get("subkind") or ""
    grp = group_of(pack, "subkind", sub) if sub else None
    low = text.lower()
    body = low.split(". ", 1)[1] if ". " in low else low

    def f(name):
        return (e.get(name) or EMPTY).lower()

    parts = " ".join(f(n) for n in ("appendages", "armament", "extras", "emitters"))
    sit = f("situation")
    ctx = (doc.get("context") or EMPTY).lower()

    if sub in _CIVIL_MACHINES and e.get("armament"):
        out.append("civil-machine-armed")
    if (kind in {"robot or mech", "surface vehicle", "starship", "space station", "wreck",
                 "alien artifact"}
            and sub not in _COMBAT_SUBKINDS
            and re.search(r"\b(cutters?|blades?|saws?|rams?|spikes?|prongs?|lances?|scythes?)\b",
                          parts)):
        out.append("blade-part-on-noncombat")
    if (kind in {"robot or mech", "surface vehicle"}
            and e.get("armament_count") in {"three", "four", "six", "eight"}):
        out.append("machine-weapon-swarm")
    if ((kind == "robot or mech" and grp != "small drone")
            or (kind == "surface vehicle"
                and grp in {"wheeled/tracked", "legged", "underwater"})) and re.search(
            r"\b(thrusters?|nozzles?|exhaust|drive plume|jets?|nacelles?)\b", f("emitters")):
        out.append("jets-on-grounded-body")
    if (kind == "surface vehicle"
            and grp in {"hovering", "flying", "lander", "underwater", "legged"}
            and re.search(r"\b(tracks?|treads?|wheels?|axles?)\b", parts)):
        out.append("tracks-on-trackless")
    if ((kind == "robot or mech" and f("form") in _LEGLESS_ROBOT_FORMS
         and re.search(r"\blegs?\b", f("appendages")))
            or (kind in {"starship", "wreck", "space station"}
                and re.search(r"\b(struts?|stubs?|legs?|stilts?)\b", parts))):
        out.append("legs-on-legless")
    if kind == "space station" and re.search(
            r"\b(tower|pyramidal|curtain wall|vent stacks?|smokestacks?)\b", body):
        out.append("station-as-building")
    if "open-space" in aff and kind != "celestial body" and "open space" not in low:
        out.append("space-without-float-cue")
    if "submerged" in aff and "underwater" not in low:
        out.append("underwater-without-cue")
    if "cloud-deck" in aff and "far above the planet" not in low:
        out.append("cloud-deck-without-cue")
    if ((kind != "spacefarer"
         and re.search(
             r"\b(crew|crews|team|colonists|refugees|party|cordon|troops|delegation|"
             r"intruders|crowd)\b", sit))
            or (env not in pack.environment_bands.get("interior", ())
                and re.search(r"\b(crew|team|colonists|crowd|crowded)\b", ctx))):
        out.append("crowd-actor")
    if re.search(r"\b(taking fire|incoming fire|trading fire|under fire)\b", sit):
        out.append("fire-word-not-fire")
    if re.search(r"\b(rose|brick|moss|mustard|plum|pearl|jade|ivory|chalk|seafoam|salmon|"
                 r"coral|mint)\b", body):
        out.append("colour-object-word")
    if re.search(r"\b(mites?|spiders?|insects?|beetles?|moths?|snakes?|rats?|sail-creatures?|"
                 r"chitin-barked fans|coiled sporing stalks|filament fronds)\b", low):
        out.append("earth-creature-or-flora")
    if re.search(r"\b(mess deck|galley|street|kitchen|headlamps?|windscreen)\b", low):
        out.append("earth-room-word")
    if "rain" in ctx and re.search(r"(dust|ash)", env):
        out.append("rain-in-dry-sky")
    if (kind == "alien creature" and grp in _STILL_CREATURE_GROUPS
            and re.search(
                r"(limb|fleeing|retreating|stalking|crawling|rearing|burrowing|"
                r"bursting through|lunge|swarming|weaving)", sit)):
        out.append("still-body-mobile-action")
    if kind == "spacefarer" and "helmet" in body and f("aperture") in _OPEN_FACE:
        out.append("sealed-helmet-open-face")
    if env in _CRAMPED and (sub in _HEAVY_FRAMES
                            or e.get("scale") in {"massive", "colossal", "planetary"}):
        out.append("heavy-body-cramped-room")
    if re.search(r"\b(warning beacon|warning sign|signage|lettering)\b", sit + " " + ctx):
        out.append("readable-sign-word")
    if kind == "celestial body" and (f("aperture") in _SMALL_WORLD_FEATURES
                                     or f("surface_detail") in _SMALL_WORLD_FEATURES):
        out.append("world-small-feature")
    if re.search(r"\b(fire|burning|flames?|ablaze)\b", sit):
        out.append("info-fire-situation")
    return out
