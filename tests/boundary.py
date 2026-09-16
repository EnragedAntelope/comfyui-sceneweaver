"""The two denylists, and the scanners that read them. Not a test module.

``tests/test_boundary.py`` runs these over pool values and over generated
``prompt_text``; ``tests/validate_data.py`` runs them over pool values as part
of its authoring report. The vocabulary lives here, once, so the suite and the
validator can never diverge -- two copies of a denylist means one of them is out
of date and nobody knows which.

**Why there are two lists rather than one.** Stylebook's rule is *a style
describes the rendering, not the subject*; SceneWeaver's is its inverse. The
line is drawn between them, not around colour:

===========================================  ===========================================
Allowed -- subject-intrinsic                 Banned -- rendering
===========================================  ===========================================
hull / skin / integument colour              palette, colour grade, teal-and-orange
markings, livery, patterning                 lighting colour and direction, "lit by"
emissive colour ("cyan exhaust plumes")      time of day, golden hour
material and finish ("pitted", "polished")   atmosphere, haze, volumetrics, god rays
shape, scale, condition, count               medium, artist, era, film stock
                                             framing, shot type, lens, depth of field
===========================================  ===========================================

Both directions are load-bearing and both are asserted. A denylist that has
never been watched reject anything is a claim; a denylist that quietly banned
every colour word would pass just as green while making hull livery and engine
glow inexpressible, which is the specific mistake the previous plan made. Hence
``RENDERING_PROBES`` (must be caught) and ``SUBJECT_PROBES`` (must survive).

A third rule rides along here because it is scanned the same way and over the
same corpus: **never negate**. Absence is expressed by naming what *is* there.
"a smooth sensory dome where a face would be", never "no eyes" -- Identity
Forge's mole drew ears from "no visible ears".
"""
from __future__ import annotations

import re

__all__ = [
    "ARTICLE_RE",
    "NEGATION_PROBES",
    "NEGATION_WORDS",
    "RENDERING_PHRASES",
    "RENDERING_PROBES",
    "RENDERING_WORDS",
    "SUBJECT_PROBES",
    "TEXT_PROBES",
    "TEXT_WORDS",
    "leading_article",
    "negation_findings",
    "readable_text_findings",
    "rendering_findings",
]

# ---------------------------------------------------------------------------
# Denylist 1 -- rendering
# ---------------------------------------------------------------------------

#: Matched as substrings, because a rendering term is a phrase far more often
#: than it is a word and "teal and orange" must be caught however it is spaced.
RENDERING_PHRASES: tuple[str, ...] = (
    # palette and colour grade
    "palette", "color grade", "colour grade", "color graded", "colour graded",
    "teal and orange", "teal-and-orange", "bleach bypass", "duotone", "sepia",
    "monochrome", "desaturated", "high contrast", "low contrast", "vignette",
    # lighting colour and direction
    "lighting", "lit by", "backlit", "back-lit", "rim light", "key light",
    "fill light", "ambient light", "god ray", "godray", "spotlight",
    "floodlight", "sunlight", "sunlit", "moonlight", "moonlit", "starlight",
    "candlelight", "underlit", "uplight", "downlight", "silhouetted",
    "chiaroscuro", "illuminated", "illumination", "catchlight",
    # time of day
    "golden hour", "blue hour", "sunrise", "sunset", "dawn", "dusk",
    "twilight", "midday", "midnight", "nightfall", "daytime", "nighttime",
    "daylight", "at night",
    # atmosphere / volumetrics
    "atmosphere", "atmospheric", "volumetric", "haze", "hazy", "fog", "foggy",
    "mist", "misty", "smog", "bokeh", "blur", "motion blur", "long exposure",
    # medium, artist, era, film stock
    "photograph", "photorealistic", "hyperrealistic", "painting", "watercolor",
    "watercolour", "digital art", "concept art", "3d render", "octane",
    "unreal engine", "artstation", "trending on", "masterpiece", "film still",
    "movie still", "cinematic", "kodak", "portra", "cinestill", "film grain",
    "35mm", "16mm", "70mm", "8k", "4k", "uhd",
    # framing, shot type, lens, depth of field, composition
    "close-up", "closeup", "wide shot", "wide-angle", "establishing shot",
    "medium shot", "rule of thirds", "depth of field", "shallow focus",
    "deep focus", "anamorphic", "fisheye", "telephoto", "focal length",
    "camera", "lens", "low angle", "high angle", "eye level", "dutch angle",
    "tracking shot", "over the shoulder",
)

#: Matched on a word boundary, so "panelling" survives a ban on "panel" and
#: "afterglow" would still be caught while "glowering" is not the point. These
#: are the terms whose *substring* form appears innocently somewhere in English:
#: banning "shot" as a substring would reject "shotgun" and "buckshot".
RENDERING_WORDS: tuple[str, ...] = (
    "shot", "framing", "composition", "shadow", "shadows", "glow", "glowing",
    "glowed", "lighting", "lit", "unlit", "bright", "brightly", "dim", "dimly",
)

# ---------------------------------------------------------------------------
# Denylist 2 -- the subject side. These must SURVIVE.
# ---------------------------------------------------------------------------

#: Subject-intrinsic phrases that the rendering denylist must not reject. The
#: pack is unusable if any of these is caught: a hull has a colour, an engine
#: has an exhaust colour, and a surface has a finish.
SUBJECT_PROBES: tuple[str, ...] = (
    "crimson hull",
    "oxide red",
    "gunmetal grey",
    "bone white",
    "cyan exhaust plumes",
    "violet bioluminescence",
    "sodium orange vent flare",
    "hazard chevrons",
    "squadron insignia",
    "titanium alloy",
    "pitted and scarred",
    "polished mirror finish",
    "chitinous carapace",
    "six ion thrusters",
    "a crown of stalked eyes",
    "colossal",
)

#: Rendering phrases that must be caught. The plan names each category; one
#: probe per category, so a denylist that lost a whole category fails here
#: rather than passing green over a pack that quietly acquired one.
RENDERING_PROBES: tuple[str, ...] = (
    "teal-and-orange grade",          # palette / colour grade
    "cinematic lighting",             # lighting
    "backlit from the rear",          # lighting direction
    "rim light along the spine",      # lighting direction
    "golden hour",                    # time of day
    "volumetric haze",                # atmosphere / volumetrics
    "shot on 35mm film",              # medium / film stock
    "trending on artstation",         # artist / platform
    "shallow depth of field",         # lens / depth of field
    "extreme close-up",               # framing / shot type
    "lit by a single spotlight",      # lighting
    "hull plating in deep shadow",    # lighting
)

# ---------------------------------------------------------------------------
# Never negate
# ---------------------------------------------------------------------------

NEGATION_WORDS: tuple[str, ...] = (
    "no", "not", "without", "lacking", "lack", "absent", "devoid", "missing",
    "never", "neither", "nor", "unarmed", "unlit", "eyeless", "featureless",
    "limbless", "wingless", "sightless", "toothless", "empty of", "free of",
)

NEGATION_PROBES: tuple[str, ...] = (
    "no weapons",
    "an unarmed freighter",
    "eyeless head",
    "hull without markings",
    "devoid of sensors",
)

# ---------------------------------------------------------------------------
# Readable text -- the v1 markings decision
# ---------------------------------------------------------------------------

#: ``markings`` ships no readable-text values in v1: models garble lettering and
#: the base negative fights it. Recorded as a decision in docs/architecture.md,
#: not as a gap.
TEXT_WORDS: tuple[str, ...] = (
    "letter", "lettering", "text", "numeral", "number", "digit", "word",
    "writing", "written", "script", "typography", "font", "alphabet",
    "registry", "serial", "glyph", "rune", "inscription", "inscribed",
    "signage", "sign", "caption", "label", "callsign", "nameplate",
)

TEXT_PROBES: tuple[str, ...] = (
    "registry lettering",
    "painted hull numerals",
    "stencilled serial",
    "a nameplate",
)

ARTICLE_RE = re.compile(r"^(a|an|the)\s", re.IGNORECASE)


def _word_hits(text: str, words: tuple[str, ...]) -> list[str]:
    low = text.lower()
    return [w for w in words if re.search(rf"\b{re.escape(w)}\b", low)]


def rendering_findings(text: str) -> list[str]:
    """Every rendering term in ``text``, as human-readable findings.

    Empty means clean. Returning the terms rather than a bool is what lets a
    failure name the word an author has to change, instead of pointing at a
    pool of two hundred values and saying one of them is wrong.
    """
    low = text.lower()
    found = [f"{p!r}" for p in RENDERING_PHRASES if p in low]
    found += [f"the word {w!r}" for w in _word_hits(text, RENDERING_WORDS)]
    return found


def negation_findings(text: str) -> list[str]:
    """Every negation in ``text``. Absence is named as what *is* there."""
    low = text.lower()
    found = [f"{p!r}" for p in NEGATION_WORDS if " " in p and p in low]
    found += [f"the word {w!r}" for w in _word_hits(text, tuple(w for w in NEGATION_WORDS if " " not in w))]
    return found


def readable_text_findings(text: str) -> list[str]:
    """Every readable-text term in ``text``. Scanned over ``markings`` only."""
    return [f"the word {w!r}" for w in _word_hits(text, TEXT_WORDS)]


def leading_article(value: str) -> bool:
    """Whether ``value`` opens with an article.

    Pool values are bare noun phrases; the engine composes the article, the
    count and the plural. A value carrying its own "a" produces "a a pair of
    ion thrusters" the first time it is counted.
    """
    return bool(ARTICLE_RE.match(value))
