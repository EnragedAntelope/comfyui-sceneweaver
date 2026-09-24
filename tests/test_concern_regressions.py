"""Every concern a user reported, as a combination the generator must never produce again.

Each row locks what the report needs locked, sweeps seeds through the real engine
and asserts the reported combination never comes back. Rows are added in the same
commit as the fix that closes them, and are never removed.
"""
from __future__ import annotations

import re
import unittest
from dataclasses import dataclass, field
from typing import Callable, Mapping

from data import fantasy as FANTASY
from data.genre import GenrePack, affordances_of, group_of, pool_for, resolved_needs
from data.fantasy import FANTASY_PACK
from data.scifi import SCIFI_PACK
from engine.grammar import head_is_plural
from engine.scene import generate_entity, generate_scene

SEEDS = 120


@dataclass(frozen=True)
class Concern:
    name: str
    forbidden: Callable[[dict, dict, str], bool]
    widgets: Mapping[str, str] = field(default_factory=dict)
    #: When set, a Scene Entity with this kind *drawn* (not locked) is wired into slot 1.
    wired_kind: "str | None" = None
    #: The genre the row was reported against.
    pack: GenrePack = SCIFI_PACK


def scenes(concern: Concern):
    for seed in range(SEEDS):
        wired = {}
        if concern.wired_kind is not None:
            _text, payload = generate_entity(seed, concern.pack, widgets={"kind": concern.wired_kind})
            wired = {1: dict(payload, locked=[])}
        text, document = generate_scene(
            seed + 50_000, concern.pack, widgets=dict(concern.widgets),
            wired_entities=wired, entity_count=1,
        )
        if document["entities"]:
            yield seed, document["entities"][0], document, text


def said(record: dict, name: str) -> str:
    return (record.get(name) or "").lower()


_WORLD_TYPES = (
    "rocky planet", "ice moon", "ringed world", "dwarf planet", "ocean world", "rogue planet",
    "volcanic moon", "lava world", "carbon planet", "gas giant", "ice giant", "ring system",
)
_BUILT_SCENERY = (
    "scatter of dead hulls", "distant station with a row of lights",
    "swarm of support landers at a safe distance", "scatter of navigation beacons",
    "distant formation holding station", "single derelict turning end over end",
)
#: Robot forms with no legs, so a leg appendage on one is bolted to nothing.
_LEGLESS_FORMS = (
    "serpentine segmented chassis", "tracked chassis", "boxy utility chassis",
    "twin-armed hauler frame", "hovering disc chassis", "spherical drone body",
    "wheeled drone body",
)

#: More than two of something, and the cardinality classes whose noun cannot
#: honestly appear more than twice. Read against ``value_cardinality`` rather
#: than against a list of nouns, so the row keeps working as the pools grow.
_MANY_COUNTS = frozenset({
    "a dozen", "rows of", "banks of", "a constellation of", "a ring of",
    "a cluster of", "a fan of", "eight", "six", "four", "three",
})
_AT_MOST_TWO = frozenset({
    "a lone part", "a matched pair", "a worn fitting", "a satellite",
    "a long arm", "a hand weapon", "a spinal mount",
})
#: A person's anatomy, or kit worn on the body. None of it is *carried*.
_ANATOMY_OR_WORN = (
    "gauntleted hand", "magnetic boot", "prosthetic arm", "articulated exo-limb",
    "backpack thruster pod", "magnetic safety clamp", "shoulder optic boom",
)

#: The two places with no air to breathe: a face shown there is a render trap.
_NO_AIR = ("high polar orbit", "deep ocean trench of a water world")
_EARTH = (
    r"\b(ships?|freighters?|frigates?|lamps?|lanterns?|derricks?|cranes?|trucks?|trailers?|sleds?|"
    r"galley|overalls?|vests?|jackets?|batons?|tribal|hitch|exhaust pipes?|desert|beach|lakes?|"
    r"forest|jungle|swamp|boats?|planes?|convoys?|tankers?|barges?|tugs?|buoys?|crates?|catwalks?|"
    r"satellites?)\b"
)


CONCERNS: tuple[Concern, ...] = (
    Concern(
        "a subject drawn into deep space has no silhouette",
        lambda r, d, t: r.get("form") is None,
        widgets={"environment": "deep interstellar void"},
    ),
    Concern(
        "a subject drawn into open orbit has no silhouette",
        lambda r, d, t: r.get("form") is None,
        widgets={"environment": "polar orbit above an ice world"},
    ),
    Concern(
        "a wired gelatinous mass loses its body to the repeat guard",
        lambda r, d, t: r.get("subkind") == "gelatinous mass" and r.get("form") is None,
        wired_kind="alien creature",
    ),
    Concern(
        "a locked robot in deep space is anything but a drone",
        lambda r, d, t: r.get("form") is None or r.get("subkind") not in (
            "swarm drone", "courier drone", "repair drone", "survey drone", "welding drone"),
        widgets={"environment": "deep interstellar void", "entity1_kind": "robot or mech"},
    ),
    Concern(
        "a locked person in open orbit has no silhouette",
        lambda r, d, t: r.get("form") is None,
        widgets={"environment": "polar orbit above an ice world", "entity1_kind": "spacefarer"},
    ),
    Concern(
        "a hover vehicle in a cloud deck is replaced by a wheeled one",
        lambda r, d, t: r.get("kind") == "surface vehicle" and "rolls" in (
            SCIFI_PACK.value_stances["form"].get(r.get("form")) or ()),
        widgets={"environment": "storm band of a gas giant"},
    ),
    Concern(
        "a person in a barren wilderness straps into a seat",
        lambda r, d, t: "seat" in said(r, "situation"),
        widgets={"environment": "barren alien wilderness", "entity1_kind": "spacefarer"},
    ),
    Concern(
        "a person in open orbit wakes from cryo",
        lambda r, d, t: "cryo" in said(r, "situation"),
        widgets={"environment": "polar orbit above an ice world", "entity1_kind": "spacefarer"},
    ),
    Concern(
        "a person in open orbit does anything but an open-space action",
        lambda r, d, t: "open-space" not in resolved_needs(
            SCIFI_PACK, "situation", r.get("situation") or ""),
        widgets={"environment": "high polar orbit", "entity1_kind": "spacefarer"},
    ),
    Concern(
        "a wreck in a star cluster spills across the ground",
        lambda r, d, t: "ground" in said(r, "situation"),
        widgets={"environment": "globular star cluster", "entity1_kind": "wreck"},
    ),
    Concern(
        "a wreck in a comet belt collapses under its own weight",
        lambda r, d, t: bool(re.search(
            r"\b(under its own weight|slide|avalanche|slumping)\b", said(r, "situation"))),
        widgets={"environment": "frozen comet belt", "entity1_kind": "wreck"},
    ),
    Concern(
        "a starship is drawn inside an ice cavern",
        lambda r, d, t: r.get("kind") == "starship",
        widgets={"environment": "subsurface ice cavern"},
    ),
    Concern(
        "a robot in deep void aims into a shaft",
        lambda r, d, t: "shaft" in said(r, "situation"),
        widgets={"environment": "deep interstellar void", "entity1_kind": "robot or mech"},
    ),
    Concern(
        "a hover bike bursts a hub or loses a wheel",
        lambda r, d, t: bool(re.search(r"\b(hub|wheels?|axle|treads?|tracks?)\b", said(r, "situation"))),
        widgets={"entity1_kind": "surface vehicle", "entity1_subkind": "hover bike"},
    ),
    Concern(
        "a disc drone breaks apart at the hip",
        lambda r, d, t: bool(re.search(r"\b(hip|knee|legs?|stamping|striding)\b", said(r, "situation"))),
        widgets={"entity1_kind": "robot or mech", "entity1_subkind": "repair drone"},
    ),
    Concern(
        "an energy being sheds scales or bares jaws",
        lambda r, d, t: bool(re.search(r"\b(scales|jaws|snout|gills?|spines|quills)\b", said(r, "situation"))),
        widgets={"entity1_kind": "alien creature", "entity1_subkind": "energy being"},
    ),
    Concern(
        "an arachnoid coils",
        lambda r, d, t: "coil" in said(r, "situation"),
        widgets={"entity1_kind": "alien creature", "entity1_subkind": "arachnoid"},
    ),
    Concern(
        "a survey glider grinds through grit on wheels",
        lambda r, d, t: bool(re.search(r"\b(grit|gravel|hub|wheels?|tracks?|axle)\b", said(r, "situation"))),
        widgets={"entity1_kind": "surface vehicle", "entity1_subkind": "survey glider"},
    ),
    Concern(
        "a binary star cracks like a planet or wears an aurora",
        lambda r, d, t: bool(re.search(
            r"\b(canyon|continent|crater|crust|aurora|poles?|polar|geysers)\b", said(r, "situation"))),
        widgets={"entity1_kind": "celestial body", "entity1_subkind": "binary star pair"},
    ),
    Concern(
        "a dwarf planet sheds a continent or is banded like a gas giant",
        lambda r, d, t: bool(re.search(r"\b(continent|slide|canyon|crater)\b", said(r, "situation")))
        or r.get("form") in ("banded sphere", "belted sphere"),
        widgets={"entity1_kind": "celestial body", "entity1_subkind": "dwarf planet"},
    ),
    Concern(
        "a world is drawn inside an asteroid field",
        lambda r, d, t: r.get("subkind") in _WORLD_TYPES,
        widgets={"environment": "asteroid field", "entity1_kind": "celestial body"},
    ),
    Concern(
        "a gas giant has a crust",
        lambda r, d, t: bool(re.search(r"\bcrust\b", t.lower())),
        widgets={"entity1_kind": "celestial body", "entity1_subkind": "gas giant"},
    ),
    Concern(
        "a ring system has a pole, an aurora or a crust",
        lambda r, d, t: bool(re.search(r"\b(poles?|polar|aurora|crust|lava)\b", t.lower())),
        widgets={"entity1_kind": "celestial body", "entity1_subkind": "ring system"},
    ),
    Concern(
        "a world stands before built scenery",
        lambda r, d, t: d.get("context") in _BUILT_SCENERY,
        widgets={"entity1_kind": "celestial body"},
    ),
    Concern(
        "a celestial body is counted like an industrial array",
        lambda r, d, t: any(r.get(name) in ("rows of", "banks of", "a constellation of", "a dozen")
                            for name in ("appendage_count", "emitter_count")),
        widgets={"entity1_kind": "celestial body"},
    ),
    *(
        Concern(
            f"a {subkind} carries a weapon or a claw",
            lambda r, d, t: r.get("armament") in (
                "shoulder cannon", "arm-mounted repeater", "missile pod", "gauss rifle mount",
                "flame projector", "vibro-saw blade", "stun emitter", "micro-missile cell",
                "needle gun mount",
            ) or "claw" in said(r, "armament") + said(r, "appendages"),
            widgets={"entity1_kind": "robot or mech", "entity1_subkind": subkind},
        )
        for subkind in ("medical automaton", "courier drone", "survey drone")
    ),
    *(
        Concern(
            f"a {subkind} is drawn tiny or small",
            lambda r, d, t: r.get("scale") in ("tiny", "small"),
            widgets={"entity1_kind": kind, "entity1_subkind": subkind},
        )
        for kind, subkind in (("robot or mech", "siege mech"), ("alien artifact", "monolith"))
    ),
    *(
        Concern(
            f"a {kind} is mothballed, unfinished or half-built",
            lambda r, d, t: r.get("condition") in (
                "mothballed", "unfinished", "half-built", "half-disassembled"),
            widgets={"entity1_kind": kind},
        )
        for kind in ("starship", "robot or mech", "surface vehicle")
    ),
    Concern(
        "a station is sunburnt",
        lambda r, d, t: r.get("condition") == "sunburnt",
        widgets={"entity1_kind": "space station"},
    ),
    Concern(
        "a wreck glows with an array of neon ports",
        lambda r, d, t: r.get("emitter_count") in (
            "a ring of", "a dozen", "rows of", "banks of", "a constellation of", "eight", "six")
        or r.get("emitter_color") in ("magenta", "hot pink", "plasma pink", "signal green",
                                      "soft magenta", "acid green"),
        widgets={"entity1_kind": "wreck"},
    ),
    Concern(
        "an artifact is a cube",
        lambda r, d, t: "cube" in said(r, "form"),
        widgets={"entity1_kind": "alien artifact"},
    ),
    Concern(
        "a vehicle is clad in a part",
        lambda r, d, t: bool(re.search(r"\b(canopy|rubber|tread)\b", said(r, "material"))),
        widgets={"entity1_kind": "surface vehicle"},
    ),
    Concern(
        "a void creature grows a venom spine or a second head",
        lambda r, d, t: r.get("armament") == "venom spine" or r.get("extras") == "secondary head",
        widgets={"entity1_kind": "alien creature", "entity1_subkind": "vacuum drifter"},
    ),
    Concern(
        "a body built for ground or water drifts in a ring system",
        lambda r, d, t: group_of(SCIFI_PACK, "subkind", r.get("subkind") or "") not in (
            "diffuse being", "void dweller"),
        widgets={"environment": "gas giant ring system", "entity1_kind": "alien creature"},
    ),
    Concern(
        "an Earth object reaches the prompt",
        lambda r, d, t: bool(re.search(_EARTH, t.lower())),
    ),
    Concern(
        "an Earth object reaches a wired scene",
        lambda r, d, t: bool(re.search(_EARTH, t.lower())),
        wired_kind="surface vehicle",
    ),
    Concern(
        "a cavern shows a landing field, a horizon or a sky",
        lambda r, d, t: bool(re.search(r"\b(horizon|landing field|sky)\b", d.get("context") or "")),
        widgets={"environment": "hollowed geode cavern"},
    ),
    Concern(
        "a plural context breaks its sentence's verb",
        lambda r, d, t: bool(d.get("context")) and head_is_plural(d["context"]),
    ),
    *(
        Concern(
            f"a suited person in {place} shows a bare face",
            lambda r, d, t: not re.search(r"\bhelmet\b", t.lower()),
            widgets={"environment": place, "entity1_kind": "spacefarer"},
        )
        for place in _NO_AIR
    ),
    Concern(
        "a person carries a helmet as a gadget",
        lambda r, d, t: bool(re.search(r"\bcarry [^.]*\bhelmet", t.lower())),
        wired_kind="spacefarer",
    ),
    *(
        Concern(
            f"a starship in {place} is shaped like an Earth craft",
            lambda r, d, t: resolved_needs(
                SCIFI_PACK, "form", r.get("form") or ""
            ) >= {"open-space"},
            widgets={"environment": place, "entity1_kind": "starship"},
        )
        for place in (
            "upper cloud deck of a gas giant", "methane sea shore", "frozen methane flats",
        )
    ),
    *(
        Concern(
            f"a {kind} is drawn with a tether, cable, chain, rope, net or container",
            lambda r, d, t: bool(re.search(
                r"\b(tether\w*|cables?|chains?|ropes?|nets?|webbing|canisters?|drums?|"
                r"barrels?|eggs?|bladders?|skeleton)\b",
                # The entity's own words and the context; the environment is a
                # named structure, and ``orbital elevator tether`` is a real one.
                " ".join(
                    str(v) for name, v in r.items()
                    if name not in ("index", "source", "genre", "archetype")
                ).lower() + " " + (d.get("context") or "").lower(),
            )),
            wired_kind=kind,
        )
        for kind in ("wreck", "robot or mech", "starship")
    ),
    Concern(
        "a dust lane is drawn as a spine of something vast",
        lambda r, d, t: "spine" in (d.get("context") or ""),
        widgets={"environment": "interstellar dust lane"},
    ),
    Concern(
        "a scout walker is drawn on a serpentine or tracked chassis",
        lambda r, d, t: bool(re.search(
            r"(serpentine|tracked|wheel|disc|spherical|boxy|gantry)", r.get("form") or ""
        )),
        widgets={"entity1_kind": "robot or mech", "entity1_subkind": "scout walker"},
    ),
    Concern(
        "an ice cutter is drawn where there is no cold",
        lambda r, d, t: "cold" not in affordances_of(
            SCIFI_PACK, d.get("environment") or ""
        ),
        widgets={"entity1_kind": "surface vehicle", "entity1_subkind": "ice cutter"},
    ),
    Concern(
        "a starliner carries a weapon",
        lambda r, d, t: bool(r.get("armament")),
        widgets={"entity1_kind": "starship", "entity1_subkind": "starliner"},
    ),
    Concern(
        "a bioship is clad in metal",
        lambda r, d, t: bool(re.search(
            r"(steel|chrome|alloy|titanium|foil|aluminium|ferro)",
            (r.get("material") or "").lower(),
        )),
        widgets={"entity1_kind": "starship", "entity1_subkind": "bioship"},
    ),
    Concern(
        "a small creature is drawn on the furniture of a furnished room",
        lambda r, d, t: r.get("scale") in ("tiny", "small"),
        widgets={"environment": "crew commons", "entity1_kind": "alien creature"},
    ),
    Concern(
        "a flying or floating vehicle carries tracks or wheels",
        lambda r, d, t: bool(re.search(
            r"\b(tracks?|treads?|wheels?|axles?)\b",
            " ".join(said(r, n) for n in ("appendages", "extras", "emitters")),
        )),
        widgets={"environment": "upper cloud deck of a gas giant"},
        wired_kind="surface vehicle",
    ),
    Concern(
        "a legless robot grows a leg",
        lambda r, d, t: said(r, "form") in _LEGLESS_FORMS and bool(
            re.search(r"\blegs?\b", said(r, "appendages"))
        ),
        wired_kind="robot or mech",
    ),
    *(
        Concern(
            f"a {kind} hull stands on struts",
            lambda r, d, t: bool(re.search(
                r"\b(struts?|stubs?)\b",
                " ".join(said(r, n) for n in ("appendages", "extras", "armament")),
            )),
            wired_kind=kind,
        )
        for kind in ("starship", "wreck")
    ),
    Concern(
        "a station is drawn as a building",
        lambda r, d, t: bool(re.search(
            r"\b(tower|pyramidal|curtain wall|vent stacks?|exhaust)\b", t.lower()
        )),
        wired_kind="space station",
    ),
    *(
        Concern(
            f"a civilian {subkind} carries a weapon",
            lambda r, d, t: bool(r.get("armament")),
            widgets={"entity1_kind": "robot or mech", "entity1_subkind": subkind},
        )
        for subkind in ("survey drone", "repair drone")
    ),
    Concern(
        "a submersible carries a weapon",
        lambda r, d, t: bool(r.get("armament")),
        widgets={"environment": "deep ocean trench of a water world",
                 "entity1_kind": "surface vehicle", "entity1_subkind": "submersible"},
    ),
    Concern(
        "a civilian crew member carries a heavy weapon",
        lambda r, d, t: said(r, "armament") in (
            "shoulder-mounted missile tube", "plasma charge harness",
            "magnetic slug thrower", "shoulder-braced arc lance"
        ),
        widgets={"entity1_kind": "spacefarer", "entity1_subkind": "salvager"},
    ),
    # ---- round XIII (the 2026-09-15 batch) ----
    Concern(
        "a count noun is drawn more times than it can exist",
        lambda r, d, t: any(
            (r.get(count_field) or "") in _MANY_COUNTS
            and (SCIFI_PACK.value_cardinality.get(noun_field) or {}).get(
                r.get(noun_field) or ""
            ) in _AT_MOST_TWO
            for noun_field, count_field in SCIFI_PACK.counts.items()
        ),
    ),
    Concern(
        "a person carries their own hands or boots",
        lambda r, d, t: bool(
            (m := re.search(r"\bcarr(?:y|ies)\b([^.]*)", t.lower()))
            and any(w in m.group(1) for w in _ANATOMY_OR_WORN)
        ),
        widgets={"entity1_kind": "spacefarer"},
    ),
    *(
        Concern(
            f"a {role} carries a weapon",
            lambda r, d, t: bool(r.get("armament")),
            widgets={"entity1_kind": "spacefarer", "entity1_subkind": role},
        )
        for role in ("scientist", "cartographer", "engineer", "archaeologist")
    ),
    Concern(
        "a crew weapon is drawn as a present-day firearm",
        lambda r, d, t: bool(re.search(
            r"\b(sidearms?|rifles?|carbines?|pistols?|bandoliers?|shotguns?)\b", t.lower()
        )),
        widgets={"entity1_kind": "spacefarer"},
    ),
    Concern(
        "a world bears a counted row of moonlets",
        lambda r, d, t: "moonlet" in said(r, "appendages"),
        widgets={"entity1_kind": "celestial body"},
    ),
    Concern(
        "a framing that needs distance is used inside a room",
        lambda r, d, t: bool(re.search(
            r"\b(in the distance|further back|further off|far edge|on the horizon)\b",
            t.lower(),
        )),
        widgets={"environment": "cockpit interior"},
    ),
    Concern(
        "something burns at the bottom of an ocean",
        lambda r, d, t: bool(re.search(
            r"\b(fire|burning|ablaze|igniting|aflame|flames?)\b", said(r, "situation")
        )),
        widgets={"environment": "deep ocean trench of a water world"},
    ),
    Concern(
        "a subject with a silhouette available renders without one",
        lambda r, d, t: r.get("form") is None and bool(pool_for(
            SCIFI_PACK, "form",
            {"kind": r.get("kind"), "subkind": r.get("subkind")},
        )),
        widgets={"environment": "observation cupola", "entity1_kind": "robot or mech"},
    ),
    *(
        Concern(
            f"a {subkind} takes a mobile action with a still body",
            lambda r, d, t: bool(re.search(
                r"(limb|fleeing|retreating|stalking|crawling|rearing|burrowing|"
                r"bursting through|lunge|swarming|weaving)", said(r, "situation")
            )),
            widgets={"entity1_kind": "alien creature", "entity1_subkind": subkind},
        )
        for subkind in ("crystalline growth", "plasma drifter", "sessile brooder")
    ),
    *(
        Concern(
            f"a {kind} is drawn with an Earth colour word, animal or room",
            lambda r, d, t: bool(re.search(
                r"\b(rose|brick|moss|mustard|plum|pearl|jade|ivory|chalk|seafoam|salmon|"
                r"coral|mint|mites|street|mess deck|headlamps?|sail-creatures?)\b", t.lower()
            )),
            wired_kind=kind,
        )
        for kind in ("wreck", "surface vehicle", "spacefarer", "alien creature")
    ),
    Concern(
        "a wreck carries a crew in its action",
        lambda r, d, t: bool(re.search(
            r"\b(crew|crews|team|colonists|cordon|troops)\b", said(r, "situation")
        )),
        wired_kind="wreck",
    ),
    Concern(
        "a sealed helmet is drawn with an open face",
        lambda r, d, t: "helmet" in t.lower() and said(r, "aperture") in (
            "open visor", "hood opening", "respirator grille", "breathing mask vent"
        ),
        widgets={"entity1_kind": "spacefarer"},
    ),
    Concern(
        "a heavy frame is drawn in a cramped room",
        lambda r, d, t: said(r, "subkind") in (
            "exosuit walker", "siege mech", "terraforming walker", "mining loader",
            "combat mech", "scout walker", "cargo hauler unit",
        ) or said(r, "scale") in ("massive", "colossal"),
        widgets={"environment": "cockpit interior", "entity1_kind": "robot or mech"},
    ),
    Concern(
        "a station in a debris belt does not say it floats",
        lambda r, d, t: "out in open space" not in t.lower(),
        widgets={"environment": "orbital debris belt"},
        wired_kind="space station",
    ),
    Concern(
        "a submersible in a trench does not say it is underwater",
        lambda r, d, t: "deep underwater" not in t.lower(),
        widgets={"environment": "deep ocean trench of a water world"},
        wired_kind="surface vehicle",
    ),
    Concern(
        "a world shows a terrain feature a person would have to stand on",
        lambda r, d, t: said(r, "aperture") in (
            "lava tube opening", "polar sink hole", "collapsed cave mouth",
            "sinkhole throat", "geothermal vent mouth",
        ),
        wired_kind="celestial body",
    ),
    Concern(
        "an alien person in vacuum shows a bare face",
        lambda r, d, t: "helmet" not in t.lower(),
        widgets={"environment": "high polar orbit", "entity1_kind": "spacefarer",
                 "entity1_subkind": "tusked mercenary"},
    ),
    # --- Round XIV: the 2026-09-16 batch ---
    *(
        Concern(
            f"a {kind} is abandoned, derelict, crashed or breached instead of being a wreck",
            lambda r, d, t: said(r, "condition") in (
                "abandoned", "derelict", "crashed", "breached"),
            widgets={"entity1_kind": kind},
        )
        for kind in ("starship", "robot or mech", "surface vehicle", "space station")
    ),
    Concern(
        "a wreck shows lit emitters or a live act (engines firing, sparks, fire)",
        lambda r, d, t: bool(r.get("emitters")) or bool(
            re.search(r"\b(spark\w*|fire|smouldering|firing|thrusters?)\b", said(r, "situation"))),
        widgets={"entity1_kind": "wreck"},
    ),
    Concern(
        "a wreck carries cables or boxes that read as plugged in",
        lambda r, d, t: bool(re.search(
            r"\b(conduits?|cables?|junction box\w*|scanner housings?|detector housings?"
            r"|ammunition cassettes?)\b",
            " ".join(said(r, n) for n in ("appendages", "extras", "sensors", "armament")))),
        widgets={"entity1_kind": "wreck"},
    ),
    Concern(
        "a context sentence imposes a stance on its context",
        lambda r, d, t: bool(re.search(
            r"crowds in close|stands further back|\bstands\.|\blies\.|further off,", t.lower())),
    ),
    Concern(
        "a creature inside a hull goes for a craft",
        lambda r, d, t: bool(re.search(
            r"\b(drones?|pods?|hulls?|shuttlecraft|probes?)\b", said(r, "situation"))),
        widgets={"environment": "cockpit interior", "entity1_kind": "alien creature"},
    ),
    Concern(
        "a tiny or small creature takes a craft",
        lambda r, d, t: said(r, "scale") in ("tiny", "small") and bool(re.search(
            r"\b(drones?|pods?|shuttlecraft|probes?|whole hull|across a hull)\b",
            said(r, "situation"))),
        widgets={"environment": "frozen methane flats", "entity1_kind": "alien creature"},
    ),
    Concern(
        "a creature is drawn over a craft at a place where nothing falls",
        lambda r, d, t: said(r, "situation") == "tearing into a fallen hull",
        widgets={"environment": "lagrange point station cluster",
                 "entity1_kind": "alien creature"},
    ),
    Concern(
        "an arachnoid or insectoid wears an Earth arthropod shell",
        lambda r, d, t: said(r, "material") in ("chitinous carapace", "keratinous plate"),
        widgets={"entity1_kind": "alien creature", "entity1_subkind": "arachnoid"},
    ),
    Concern(
        "a creature carries sail, boom or gimbal rigging",
        lambda r, d, t: bool(re.search(r"\b(sail\w*|booms?|gimbal\w*)\b", t.lower())),
        widgets={"entity1_kind": "alien creature", "entity1_subkind": "void grazer"},
    ),
    Concern(
        "a crew works calmly beside a creature",
        lambda r, d, t: "crew" in (d.get("context") or ""),
        widgets={"environment": "station docking ring interior",
                 "entity1_kind": "alien creature"},
    ),
    Concern(
        "an android bears a cockpit hatch",
        lambda r, d, t: "cockpit" in said(r, "aperture"),
        widgets={"entity1_kind": "robot or mech", "entity1_subkind": "android"},
    ),
    Concern(
        "a droid breaks itself apart with no cause in the frame",
        lambda r, d, t: bool(re.search(
            r"\b(spark\w*|severed|shower of parts|losing a|shorting|hip joint|bursting)\b",
            said(r, "situation"))),
        widgets={"entity1_kind": "robot or mech", "entity1_subkind": "android"},
    ),
    Concern(
        "a machine catches fire in a hangar",
        lambda r, d, t: bool(re.search(r"\b(fire|burning|igniting|smouldering)\b",
                                       said(r, "situation"))),
        widgets={"environment": "spacecraft hangar deck", "entity1_kind": "surface vehicle"},
    ),
    Concern(
        "a person eats or shares a meal",
        lambda r, d, t: bool(re.search(r"\b(meal|food|feast|eating)\b", t.lower())),
        widgets={"environment": "hydrothermal vent field of a water world",
                 "entity1_kind": "spacefarer"},
    ),
    Concern(
        "a person's gear or act says patch or stitching",
        lambda r, d, t: bool(re.search(r"\b(patch kit|patched|stitching|patchwork)\b",
                                       t.lower())),
        widgets={"entity1_kind": "spacefarer"},
    ),
    Concern(
        "a mining machine is spoken as construction equipment",
        lambda r, d, t: bool(re.search(r"\b(loader|breaker arms?|booms?)\b", t.lower())),
        widgets={"entity1_kind": "robot or mech", "entity1_subkind": "mining loader"},
    ),
    Concern(
        "a station shows exhaust, vents or welding lights",
        lambda r, d, t: bool(re.search(r"\b(thrusters?|vents?|welding|grilles?|seams?)\b",
                                       said(r, "emitters"))),
        widgets={"entity1_kind": "space station"},
    ),
    Concern(
        "a starship shows exhaust while its act already describes a plume",
        lambda r, d, t: bool(re.search(r"\b(plume|sheath|long burn|stuck open)\b",
                                       said(r, "situation")))
        and bool(re.search(r"\b(thrusters?|nozzles?|torch|exhaust|nacelles?|vents?)\b",
                           said(r, "emitters"))),
        widgets={"entity1_kind": "starship"},
    ),
    Concern(
        "a deep-space scene trails frozen vapour",
        lambda r, d, t: "frozen vapour" in t.lower(),
        widgets={"environment": "emission nebula"},
    ),
    # --- round XV: the 0916-evening sci-fi batch -------------------------------
    *(
        Concern(
            f"a moon in the sky over {place} is a bare or cratered moon",
            lambda r, d, t: bool(re.search(
                r"\b(twin moons|two moons|cratered moon|in front of a moon|a nearby moon)\b",
                t.lower())),
            widgets={"environment": place},
        )
        for place in ("black sand tidal flat", "barren alien wilderness", "basalt mesa badlands")
    ),
    *(
        Concern(
            f"a context in {place} draws smokestacks, an airport, panels or a string of machines",
            lambda r, d, t: bool(re.search(
                r"(venting steam|venting vapour|landing field|string of|queue of|line of dead"
                r"|solar collectors|scaffold of gantries|curtain of vapour)", said(d, "context"))),
            widgets={"environment": place},
        )
        for place in ("crater basin", "orbital debris belt", "hollowed geode cavern",
                      "storm band of a gas giant")
    ),
    Concern(
        "a creature is half inside a cocoon, a shell or a husk",
        lambda r, d, t: bool(re.search(r"(cocoon|shell of hardened resin|husk)",
                                       said(r, "situation"))),
        widgets={"entity1_kind": "alien creature"},
    ),
    Concern(
        "a creature closes on a drone, a probe or a cargo pod",
        lambda r, d, t: bool(re.search(r"\b(drones?|probes?|cargo pods?)\b", said(r, "situation"))),
        widgets={"entity1_kind": "alien creature"},
    ),
    Concern(
        "a starship carries a detached panel, boom, clamp, arm or pod",
        lambda r, d, t: bool(re.search(
            r"(solar|radiator vane|grapple|clamp|outrigger|towed|external fuel|boom arm"
            r"|refuelling probe|mine rack|cargo pod)",
            said(r, "appendages") + " " + said(r, "extras"))),
        widgets={"entity1_kind": "starship"},
    ),
    Concern(
        "a surface vehicle carries a mast, clamp, hoist or outrigger",
        lambda r, d, t: bool(re.search(
            r"(mast|clamp|outrigger|hoist|gantry|whip aerial|array panel|locker)",
            " ".join(said(r, f) for f in ("appendages", "extras", "sensors")))),
        widgets={"entity1_kind": "surface vehicle"},
    ),
    *(
        Concern(
            f"a wheeled or tracked {kind} is under water",
            lambda r, d, t: "rolls" in SCIFI_PACK.value_stances["form"].get(r.get("form"), ()),
            widgets={"environment": "hydrothermal vent field of a water world", "entity1_kind": kind},
        )
        for kind in ("robot or mech", "surface vehicle")
    ),
    Concern(
        "a crewmate in open space is not said to be suited",
        lambda r, d, t: "crewmate" in said(r, "situation") and "suit" not in said(r, "situation"),
        widgets={"environment": "orbital debris belt", "entity1_kind": "spacefarer"},
    ),
    Concern(
        "a starship at a planet's surface flies a fleet manoeuvre",
        lambda r, d, t: bool(re.search(
            r"(formation|escorts|moon|banded world|past a derelict|blockade|interceptors"
            r"|searchlight|signal beacon|wake of particles|long plume|debris curtain)",
            said(r, "situation"))),
        widgets={"environment": "red dust plain of a dead world", "entity1_kind": "starship"},
    ),
    Concern(
        "a ground vehicle with no flight stance burns through re-entry",
        lambda r, d, t: "re-entry" in said(r, "situation") and not (
            {"flies", "hovers"} & set(SCIFI_PACK.value_stances["form"].get(r.get("form"), ()))),
        widgets={"environment": "floating-rock plateau", "entity1_kind": "surface vehicle"},
    ),
    Concern(
        "a rooted growth grows out of a deck",
        lambda r, d, t: said(r, "subkind") in ("fungal colony", "plant-form", "crystalline growth"),
        widgets={"environment": "hydroponics bay", "entity1_kind": "alien creature"},
    ),
    Concern(
        "a bell-bodied swimmer sits on dry ground",
        lambda r, d, t: said(r, "subkind") == "cephalopod",
        widgets={"environment": "cracked salt flat", "entity1_kind": "alien creature"},
    ),
    Concern(
        "a machine is said to carry an arm or a limb",
        lambda r, d, t: bool(re.search(r"\bcarr(y|ies)\b[^.]*\b(arms?|limbs?)\b", t.lower())),
        widgets={"entity1_kind": "robot or mech"},
    ),
    Concern(
        "a submersible shows treads or tracks",
        lambda r, d, t: bool(re.search(r"\b(treads?|tracks?)\b", t.lower())),
        widgets={"entity1_kind": "surface vehicle", "entity1_subkind": "submersible"},
    ),
    # --- round XV: the 0917 fantasy batch ---------------------------------------
    Concern(
        "a giant's size is a vague word",
        lambda r, d, t: said(r, "scale") in ("large", "huge", "colossal", "small", "tiny"),
        widgets={"entity1_kind": "giant-kin"}, pack=FANTASY_PACK,
    ),
    Concern(
        "a forge holds a library's, a temple's or a hall's furniture",
        lambda r, d, t: bool(re.search(r"(books|feasting|pews|altar|lectern)", said(d, "context"))),
        widgets={"environment": "blacksmith's forge"}, pack=FANTASY_PACK,
    ),
    *(
        Concern(
            f"birds or wild horses stand behind a subject in {place}",
            lambda r, d, t: bool(re.search(r"(ravens|gulls|heron|eagles|wild horses)",
                                           said(d, "context"))),
            widgets={"environment": place}, pack=FANTASY_PACK,
        )
        for place in ("rolling highland hills", "shallow river ford", "sea of clouds")
    ),
    Concern(
        "a wizard's tower has a weapon",
        lambda r, d, t: r.get("armament") is not None,
        widgets={"entity1_kind": "structure", "entity1_subkind": "wizard's tower"},
        pack=FANTASY_PACK,
    ),
    *(
        Concern(
            f"a {subkind} is said to carry a body part",
            lambda r, d, t: bool(re.search(
                r"\bcarr(y|ies)\b[^.]*\b(talons?|claws?|arms?|fists?)\b", t.lower())),
            widgets={"entity1_subkind": subkind, "entity1_kind": kind}, pack=FANTASY_PACK,
        )
        for kind, subkind in (("hybrid folk", "harpy"), ("construct", "gargoyle"))
    ),
    Concern(
        "a minotaur carries reed pipes into a fight",
        lambda r, d, t: "pipes" in t.lower(),
        widgets={"entity1_kind": "hybrid folk", "entity1_subkind": "minotaur"}, pack=FANTASY_PACK,
    ),
    Concern(
        "a sea-going ship sits in a shallow ford",
        lambda r, d, t: said(r, "subkind") in ("galleon", "longship", "war galley", "pirate sloop"),
        widgets={"environment": "shallow river ford", "entity1_kind": "vessel"}, pack=FANTASY_PACK,
    ),
    Concern(
        "a wagon carries a ship's parts",
        lambda r, d, t: bool(re.search(r"\b(anchor|stern|waterline|sails?|masts?|barnacled)\b",
                                       t.lower())),
        widgets={"entity1_kind": "vessel", "entity1_subkind": "painted travelling wagon"},
        pack=FANTASY_PACK,
    ),
    Concern(
        "a wheeled vehicle climbs a mountain peak",
        lambda r, d, t: said(r, "subkind") in FANTASY.SUBKIND_GROUPS["land vehicle"],
        widgets={"environment": "snowbound mountain peak", "entity1_kind": "vessel"},
        pack=FANTASY_PACK,
    ),
    Concern(
        "a newly launched vessel is rotting or abandoned",
        lambda r, d, t: bool(re.search(r"(abandoned|peeling|rotting|overgrown|broken)",
                                       said(r, "situation"))),
        widgets={"entity1_kind": "vessel", "entity1_condition": "newly launched"},
        pack=FANTASY_PACK,
    ),
    Concern(
        "a living beast weathers like a statue",
        lambda r, d, t: r.get("situation") in FANTASY._STONE_ACTS
        and r.get("condition") != "petrified",
        widgets={"entity1_kind": "mythic beast"}, pack=FANTASY_PACK,
    ),
    Concern(
        "a structure rings an Earth bell",
        lambda r, d, t: bool(re.search(r"\bbells?\b", t.lower())),
        widgets={"entity1_kind": "structure"}, pack=FANTASY_PACK,
    ),
    Concern(
        "a sea wyrm hangs a lure from its mouth",
        lambda r, d, t: "lure" in t.lower(),
        widgets={"entity1_kind": "dragon", "entity1_subkind": "leviathan"}, pack=FANTASY_PACK,
    ),
    *(
        Concern(
            f"a {kind} in a warm forest coats things in ice",
            lambda r, d, t: bool(re.search(r"\b(rime|freezing|hail|frost-rimed)\b", t.lower())),
            widgets={"environment": "ancient oak forest", "entity1_kind": kind}, pack=FANTASY_PACK,
        )
        for kind in ("artifact", "dragon", "structure")
    ),
    Concern(
        "an artifact hangs in open sky",
        lambda r, d, t: said(r, "kind") == "artifact",
        widgets={"environment": "sea of clouds"}, pack=FANTASY_PACK,
    ),
    Concern(
        "a forest or marsh spirit haunts a crypt",
        lambda r, d, t: said(r, "subkind") in ("forest spirit", "will-o'-wisp", "sylph", "dryad"),
        widgets={"environment": "catacomb crypt", "entity1_kind": "spirit or elemental"},
        pack=FANTASY_PACK,
    ),
    Concern(
        "an act attacks something that is not in the frame",
        lambda r, d, t: bool(re.search(r"(barricade|line of attackers|hunter's net)",
                                       said(r, "situation"))),
        widgets={"environment": "field of standing stones", "entity1_kind": "undead"},
        pack=FANTASY_PACK,
    ),
    Concern(
        "a creature named giant is small",
        lambda r, d, t: said(r, "scale") in ("small", "tiny"),
        widgets={"entity1_kind": "mythic beast", "entity1_subkind": "giant sea turtle"},
        pack=FANTASY_PACK,
    ),
    Concern(
        "an act names a weapon the entity does not carry",
        lambda r, d, t: bool(re.search(r"(arrow|longbow)", said(r, "situation")))
        and bool(re.search(r"(sword|mace|hammer|staff|axe|dagger|rapier|flail|shield)",
                           said(r, "armament"))),
        widgets={"entity1_kind": "folk"}, pack=FANTASY_PACK,
    ),
)


class ConcernRegressionTests(unittest.TestCase):
    def test_no_reported_concern_comes_back(self) -> None:
        for concern in CONCERNS:
            hits = [seed for seed, record, document, text in scenes(concern)
                    if concern.forbidden(record, document, text)]
            with self.subTest(concern=concern.name):
                self.assertEqual(hits, [], f"{concern.name}: seeds {hits[:5]}")


if __name__ == "__main__":
    unittest.main()
