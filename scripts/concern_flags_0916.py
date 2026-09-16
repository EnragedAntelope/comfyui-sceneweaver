"""Round XIV concern flags -- the classes from the 2026-09-16 batch. Frozen; do not edit to
make a task pass.

The 916 batch was a different shape again. Every prompt was legal English about a legal
subject in a legal place, and a model still drew the wrong picture: a dead hull with its
engines lit, a droid's elbow exploding with nothing in the frame to hit it, a campfire
under a lander, a tiny creature holding a ship, a sewn cloth patch on a hull, a crane on a
mining mech, a sail on a creature. Several are words (``patch``, ``sail``, ``loader``); the
rest are relationships between two fields that each read fine alone.

An instrument, not a gate: ``tests/`` owns the gates. The definitions are frozen once
committed and are never edited to make a task pass.
"""
from __future__ import annotations

import re

from data.genre import affordances_of

EMPTY = str()


def _words(*terms: str) -> "re.Pattern[str]":
    return re.compile(r"\b(" + "|".join(terms) + r")\b")


#: The four states that made a live-noun subject dead.
_DEAD_STATES = {"abandoned", "derelict", "crashed", "breached"}
_LIVE_ON_A_WRECK = _words(r"spark\w*", "fire", r"burning", "smouldering", "firing",
                          r"thrusters?", "holding station", "riding")
_FALLING = _words("as it falls", "drops through", "falls through")
_STANCE_IN_CONTEXT = _words("stands", "lies", "crowds in close", "stands further back")
_SEWN_PATCH = _words("patch kit", "patched", r"stitching", r"patchwork", r"patch quilting")
_CABLE = _words(r"conduits?", r"cables?", "coupling", r"junction box(es)?", "power line")
_BOX = _words("battery pack", r"ammunition cassettes?", r"scanner housings?",
              r"detector housings?")
_CONSTRUCTION = _words("loader", r"breaker arms?", r"cargo booms?", r"counterweight booms?",
                       r"telescoping booms?", r"loader frames?")
_RIGGING = _words(r"sail\w*", r"gimbal\w*", r"booms?")
_FIRE = _words("fire", "burning", "igniting", "smouldering", "ablaze")
_SELF_BREAKING = _words(r"spark\w*", "severed", "shower of parts", "losing a tool arm",
                        "losing a leg", "shorting out", "hip joint", "bursting its casing")
_CRAFT = _words(r"drones?", r"pods?", r"hulls?", "shuttlecraft", r"probes?")
_MEAL = _words("meal", "food", "feast", "eating")
_ICE_EJECTION = _words("frozen vapour", "frozen gas", "cold vapour")
_CREW = _words("crew", "pressure suits")
_STATION_EXHAUST = _words(r"thrusters?", "heat vents?", "welding bay", r"grilles?")
_EXHAUST = _words(r"thrusters?", r"nozzles?", "torch", "exhaust")
_PLUME_ACT = _words("plume", "sheath", "long burn", "stuck open")
_EARTH_ARTHROPOD = {"arachnoid", "insectoid"}
_EARTH_SKIN = {"chitinous carapace", "keratinous plate"}

#: Every class this instrument reports. All are gated.
STRUCTURAL_0916: frozenset[str] = frozenset({
    "dead-state-on-live-noun",
    "wreck-lit-or-acting",
    "context-stance-verb",
    "sewn-patch-word",
    "cable-on-wreck",
    "box-part-word",
    "construction-word",
    "creature-rigging-word",
    "open-fire",
    "machine-breaks-itself",
    "craft-prey-small-or-indoors",
    "meal-word",
    "ice-ejection-context",
    "crew-beside-creature",
    "station-exhaust",
    "thrust-twice",
    "earth-arthropod-skin",
    "cockpit-on-android",
})


def flags_0916(pack, doc, text):
    """Every round-XIV concern class the first entity of ``doc`` falls into."""
    out: list[str] = []
    if not doc["entities"]:
        return out
    e = doc["entities"][0]
    env = doc.get("environment") or EMPTY
    aff = affordances_of(pack, env)
    indoors = env in (pack.environment_bands.get("interior") or ())
    kind = e.get("kind")
    low = text.lower()

    def f(name):
        return (e.get(name) or EMPTY).lower()

    sit = f("situation")
    ctx = (doc.get("context") or EMPTY).lower()
    parts = " ".join(f(n) for n in ("appendages", "extras", "sensors", "aperture", "markings",
                                     "surface_detail", "armament"))
    context_sentence = next((s for s in low.split(". ") if ctx and ctx in s), EMPTY)

    if kind != "wreck" and f("condition") in _DEAD_STATES:
        out.append("dead-state-on-live-noun")
    if kind == "wreck" and (e.get("emitters") or (
            _LIVE_ON_A_WRECK.search(sit) and not _FALLING.search(sit))):
        out.append("wreck-lit-or-acting")
    if _STANCE_IN_CONTEXT.search(context_sentence.replace(ctx, EMPTY)):
        out.append("context-stance-verb")
    if _SEWN_PATCH.search(low):
        out.append("sewn-patch-word")
    if kind == "wreck" and _CABLE.search(parts + " " + sit):
        out.append("cable-on-wreck")
    if _BOX.search(low):
        out.append("box-part-word")
    if _CONSTRUCTION.search(low):
        out.append("construction-word")
    if kind == "alien creature" and _RIGGING.search(low):
        out.append("creature-rigging-word")
    # A star's "streamer of fire" is plasma, not a campfire under a lander.
    if kind != "celestial body" and _FIRE.search(sit) and "sky" not in aff:
        out.append("open-fire")
    if kind in {"robot or mech", "surface vehicle"} and _SELF_BREAKING.search(sit):
        out.append("machine-breaks-itself")
    if kind == "alien creature" and _CRAFT.search(sit) and (
            indoors or f("scale") in {"tiny", "small"}):
        out.append("craft-prey-small-or-indoors")
    if _MEAL.search(sit):
        out.append("meal-word")
    if _ICE_EJECTION.search(ctx + " " + sit):
        out.append("ice-ejection-context")
    if kind == "alien creature" and _CREW.search(ctx):
        out.append("crew-beside-creature")
    if kind == "space station" and _STATION_EXHAUST.search(f("emitters")):
        out.append("station-exhaust")
    if kind == "starship" and _EXHAUST.search(f("emitters")) and _PLUME_ACT.search(sit):
        out.append("thrust-twice")
    if f("subkind") in _EARTH_ARTHROPOD and f("material") in _EARTH_SKIN:
        out.append("earth-arthropod-skin")
    if f("subkind") == "android" and "cockpit" in f("aperture"):
        out.append("cockpit-on-android")
    return out
