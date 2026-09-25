"""English composition helpers: articles, plurals and count phrases.

Pure functions over strings. No pack, no RNG, no ComfyUI -- this module is the
bottom of the engine and everything above it depends on the fact that it is
boring.

**Why the engine owns this and the data does not.** Pool values are authored as
bare, article-less, *singular* noun phrases ("ion thruster"), and the count
pools are word tokens ("a pair of"). Neither half is a phrase on its own; this
module is what makes "a pair of ion thrusters" out of them. Putting the grammar
in the data instead would mean every genre re-authoring English, and every pool
carrying both a singular and a plural spelling of the same thing.

Three things worth knowing before editing:

* **The head noun is what inflects.** "mane of filaments" pluralizes on *mane*,
  not on the trailing "filaments", so every inflection here splits the phrase at
  its first post-modifier and works on the left half.
* **The article follows the SOUND, not the letter.** "a utility manipulator arm"
  and "an hourglass frame" are both right, and a bare vowel-letter test gets
  both wrong.
* **An irregular plural is a data bug, not a table entry.** The table below
  exists so a genre author who writes "wolf" gets "wolves" rather than "wolfs"
  -- but ``tests/test_grammar.py`` asserts that no count-partnered value in a
  shipped pack ever reaches it. When a pool value needs the table, rename the
  value ("pinhole ocellus" became "pinhole eye"); do not add an exception.
"""
from __future__ import annotations

import re

__all__ = [
    "AMBIGUOUS_SINGULARS",
    "IRREGULAR_PLURALS",
    "article_for",
    "count_phrase",
    "head_noun",
    "head_is_plural",
    "is_singular_count",
    "join_clauses",
    "pluralize",
    "with_article",
    "with_article_if_singular",
]


# ---------------------------------------------------------------------------
# Head-noun detection
# ---------------------------------------------------------------------------

#: Splits a noun phrase at its first post-modifier, so the head can be
#: inspected. "mane of filaments" heads on "mane" (singular -> takes "a"),
#: "disc of dust and rock" heads on "disc". Without this the naive last-word
#: test reads both as plural and drops the article.
#:
#: The preposition list includes the directional ones (along, beside, past,
#: toward, within, into) because a context clause uses them where the older
#: list only had "of/with/on/...". "above", "below", "among", "amid" and
#: "atop" joined when "twin gasbags above a long hull" took "a" and "human
#: torso above goat legs" lost it.
_TAIL_RE = re.compile(
    r"\s+(?:of|with|on|in|at|from|for|to|and|over|under|around|through|"
    r"beneath|across|behind|between|along|beside|past|toward|within|into|"
    r"bearing|trailing|carrying|holding|above|below|among|amid|atop)\b"
)

#: Participles that end a noun phrase's head when they follow a noun:
#: "figures moving along a walkway" heads on *figures*, "hatch standing
#: open" on *hatch*. Deliberately a short list rather than every "-ing"/"-ed"
#: word -- "gate ring" and "a docking ring" both end in "-ing" and both keep
#: *ring* as their head, so a blanket suffix rule would break them. "parted"
#: and "split" are here for a ring plane: "tilted ring disc parted by a dark
#: gap" heads on *disc*, not on the trailing noun.
_PARTICIPLE_BOUNDARY: frozenset[str] = frozenset({
    "moving", "standing", "waiting", "holding", "working", "sweeping",
    "rising", "crawling", "parked", "tethered", "spent", "parted", "split",
})

#: Irregular past participles. With every "-ed" word they end the head when a
#: preposition follows: "coins wedged between its scales" heads on *coins*,
#: "halls woven into a giant tree" on *halls*. The preposition is what makes it
#: safe: "tall carved standing stone" keeps its adjective.
_IRREGULAR_PARTICIPLES: frozenset[str] = frozenset({
    "woven", "broken", "frozen", "fallen", "hidden", "sunken", "stolen", "torn",
    "worn", "drawn", "grown", "thrown", "bitten", "eaten", "forgotten", "shaken",
    "spun", "hung", "strung", "bound", "wound", "sewn", "sown", "strewn", "cut",
    "set", "shut", "slung", "stuck",
})

#: "-ed" nouns: "a flower bed of", "a steed with".
_ED_NOUNS: frozenset[str] = frozenset({
    "bed", "shed", "sled", "reed", "steed", "seed", "weed", "speed", "feed",
    "creed", "breed", "deed", "need", "red",
})

#: A determiner never precedes a participle that ends the head: "a spent
#: booster" and "a docking ring" are one noun phrase, not a head plus a verb.
_DETERMINERS: frozenset[str] = frozenset({
    "a", "an", "the", "its", "his", "her", "their", "our", "your", "my",
    "this", "that", "these", "those",
})

_WORD_RE = re.compile(r"\S+")


def _participle_before_preposition(words: list, index: int) -> bool:
    """Whether ``words[index]`` is a past participle that a preposition follows."""
    word = words[index].group().lower()
    if index + 1 >= len(words) or word in _ED_NOUNS:
        return False
    if not (word in _IRREGULAR_PARTICIPLES or (word.endswith("ed") and len(word) > 4)):
        return False
    return bool(_TAIL_RE.match(" " + words[index + 1].group()))


def _first_boundary(phrase: str) -> int:
    """Index of the first post-modifier that ends the head noun, or -1.

    The earliest of a preposition and a noun-following participle, so the head
    is everything before it. Shared by ``head_noun`` and ``pluralize``, which
    must agree on where a phrase's head ends.
    """
    boundary = -1
    match = _TAIL_RE.search(phrase)
    if match:
        boundary = match.start()
    words = list(_WORD_RE.finditer(phrase))
    for index, word_match in enumerate(words):
        word = word_match.group().lower()
        if index == 0 or not (
            word in _PARTICIPLE_BOUNDARY or _participle_before_preposition(words, index)
        ):
            continue
        if words[index - 1].group().lower() in _DETERMINERS:
            continue
        candidate = word_match.start() - 1
        if boundary == -1 or candidate < boundary:
            boundary = candidate
        break
    return boundary


def head_noun(phrase: str) -> str:
    """The inflecting word of ``phrase`` -- the last word before any modifier."""
    if not phrase:
        return ""
    boundary = _first_boundary(phrase)
    head = phrase[:boundary] if boundary != -1 else phrase
    words = head.split()
    return words[-1] if words else ""


# ---------------------------------------------------------------------------
# Articles
# ---------------------------------------------------------------------------

#: Vowel letters that open on a consonant *sound* -- the "yoo" glide and the
#: "wun" of "one": "a utility manipulator arm", "a uniform hull", "a one-piece
#: canopy". Matched on the leading word, so a pool value added later inherits
#: the rule instead of needing to be listed.
_CONSONANT_VOWEL_PREFIXES: tuple[str, ...] = (
    "uni", "use", "usu", "usa", "uti", "ubi", "eu", "ewe", "one", "once",
)

#: Consonant letters that open on a vowel sound: the silent h. "an hourglass
#: hull", "an honest reading".
_VOWEL_CONSONANT_PREFIXES: tuple[str, ...] = (
    "hour", "honest", "honor", "honour", "heir",
)

#: Singular words that end in "s" and are not caught by the two rules below.
_SINGULAR_S: frozenset[str] = frozenset({
    "gas", "canvas", "atlas", "lens", "bus", "plus", "chaos",
})


#: Heads that are mass nouns in descriptive prose, so they take no article:
#: "shows pitted erosion", but "shows a hairline fracture web". English, not
#: genre data -- a fantasy pack's "patina" is the same word. Populated from the
#: heads that actually occur in the surface_detail, markings and material
#: pools, read rather than guessed.
#:
#: A mass noun is uncountable: "a pitted erosion" is wrong the way "a water"
#: is. A singular count noun needs its article, which is why the same rule
#: leaves "a hairline fracture web" alone.
_MASS_HEADS: frozenset[str] = frozenset({
    # surface_detail
    "banding", "blooming", "clutter", "cratering", "crazing", "creasing",
    "crusting", "erosion", "etching", "film", "flaking", "fuzz", "grain",
    "growth", "iridescence", "layering", "patina", "plating", "pocking",
    "polish", "quilting", "regolith", "ribbing", "scaling", "scoring",
    "sheen", "staining", "stitching", "streaking", "texture", "tracery",
    "tubing", "veining", "webbing", "work", "filigree", "gravel",
    # markings
    "blotching", "chipping", "clustering", "dappling", "fluting", "knotting",
    "mottling", "panelling", "patterning", "piping", "polishing", "scarring",
    "striping", "studding",
    # material
    "dust", "flesh", "floss", "glass", "ice", "metal", "obsidian", "resin",
    "rock", "stone", "tissue", "secretion", "lace", "membrane", "mesh",
    "weave", "cuticle", "bark-skin", "scale",
})

#: Endings that mark a singular Latin-ish noun: "torus", "radius", "apparatus",
#: "chassis", "iris", "axis". English has no plural ending in "-us" or "-is", so
#: these two are safe as rules and spare the table an entry per pool value --
#: which matters, because a table entry for a *data* value is the thing this
#: engine is not allowed to accumulate. ("-os" and "-as" are NOT safe: "silos"
#: and "areas" are plurals.)
_SINGULAR_ENDINGS: tuple[str, ...] = ("us", "is", "ss")


def article_for(phrase: str) -> str:
    """The indefinite article ("a" / "an") that fits ``phrase``.

    Sound-based, not letter-based: both exception classes above are live in real
    pools, and a bare ``first_letter in "aeiou"`` test gets each of them
    backwards.
    """
    first = phrase.split(" ", 1)[0].lower() if phrase else ""
    if first.startswith(_VOWEL_CONSONANT_PREFIXES):
        return "an"
    if first.startswith(_CONSONANT_VOWEL_PREFIXES):
        return "a"
    # Numerals are read aloud, so the article follows the SPOKEN first sound:
    # "an 8-metre spar", "an 18-deck hull", but "a 110-metre boom" (one hundred
    # ten). Only a leading 8 and the exact teens 11 and 18 take "an".
    digits = re.match(r"\d+", first)
    if digits:
        run = digits.group()
        return "an" if run.startswith("8") or run in ("11", "18") else "a"
    # `first[:1] in "aeiou"` is True for the EMPTY string, so guard explicitly.
    return "an" if first[:1] and first[0] in "aeiou" else "a"


def with_article(phrase: str) -> str:
    """``phrase`` with its indefinite article: "a needle hull"."""
    if not phrase:
        return ""
    return f"{article_for(phrase)} {phrase}"


def head_is_plural(phrase: str) -> bool:
    """Whether the head noun of ``phrase`` is plural, read off its final "s".

    Shared by ``with_article_if_singular`` (which drops the article for a
    plural head) and the prose renderer (which picks the plural copula "are"
    for a plural subject). A plural is read off the head noun's final "s",
    minus the singular endings above.
    """
    if not phrase:
        return False
    head = head_noun(phrase).lower()
    return (
        head.endswith("s")
        and not head.endswith(_SINGULAR_ENDINGS)
        and head not in _SINGULAR_S
    )


def with_article_if_singular(phrase: str) -> str:
    """``phrase`` articled only when its head noun is singular.

    Pools mix singular and plural heads in one slot -- "cargo pod" sits beside
    "stacked ring tiers" and "mane of filaments" -- and a blanket article gives
    "a hazard chevrons". Plural is read off the head noun's final "s", minus the
    singular endings above.
    """
    if not phrase:
        return ""
    if head_is_plural(phrase) or head_noun(phrase).lower() in _MASS_HEADS:
        return phrase
    return with_article(phrase)


# ---------------------------------------------------------------------------
# Plurals
# ---------------------------------------------------------------------------

#: Heads whose plural cannot be derived mechanically.
#:
#: This table is a *safety net for genre authors*, not a licence to author
#: irregular pool values. ``tests/test_grammar.py`` walks every count-partnered
#: value in the shipped pack and fails if any head appears here, because two
#: values sharing a head can want different plurals ("whip antenna" -> antennas,
#: "feathered antenna" -> antennae) and no single table can hold both. The fix
#: is always to rename the value.
IRREGULAR_PLURALS: dict[str, str] = {
    # Native English
    "man": "men", "woman": "women", "child": "children", "foot": "feet",
    "tooth": "teeth", "goose": "geese", "mouse": "mice", "louse": "lice",
    "ox": "oxen", "person": "people", "die": "dice",
    "leaf": "leaves", "knife": "knives", "wolf": "wolves", "shelf": "shelves",
    "calf": "calves", "half": "halves", "life": "lives", "loaf": "loaves",
    "self": "selves", "thief": "thieves", "hoof": "hooves", "elf": "elves",
    # Latin / Greek loans that keep a classical plural in descriptive prose
    "antenna": "antennae", "larva": "larvae", "alga": "algae",
    "vertebra": "vertebrae", "nucleus": "nuclei", "fungus": "fungi",
    "radius": "radii", "stimulus": "stimuli", "cactus": "cacti",
    "ocellus": "ocelli", "bacillus": "bacilli", "villus": "villi",
    "axis": "axes", "analysis": "analyses", "basis": "bases",
    "spectrum": "spectra", "datum": "data", "stratum": "strata",
    "cilium": "cilia", "flagellum": "flagella", "septum": "septa",
    "labium": "labia", "criterion": "criteria", "ganglion": "ganglia",
    "index": "indices", "matrix": "matrices", "apex": "apices",
    "vortex": "vortices", "genus": "genera", "corpus": "corpora",
    # Unchanged in the plural
    "species": "species", "series": "series", "apparatus": "apparatus",
    "chassis": "chassis", "aircraft": "aircraft", "spacecraft": "spacecraft",
    "offspring": "offspring",
}

#: Every head the table covers, exposed so a validator can assert that a corpus
#: stays clear of it without importing the mapping and inverting it by hand.
AMBIGUOUS_SINGULARS: frozenset[str] = frozenset(IRREGULAR_PLURALS)

#: Endings that take "-es": the sibilants. "gun port" -> ports, but "torpedo
#: hatch" -> hatches and "junction box" -> boxes.
_SIBILANT_ENDINGS: tuple[str, ...] = ("s", "x", "z", "ch", "sh")

_CONSONANT_Y_RE = re.compile(r"[^aeiou]y$")


def _pluralize_word(word: str) -> str:
    lower = word.lower()
    irregular = IRREGULAR_PLURALS.get(lower)
    if irregular is not None:
        return irregular if word.islower() else irregular.capitalize()
    if _CONSONANT_Y_RE.search(lower):
        # "missile battery" -> batteries; "torpedo bay" keeps its vowel + y.
        return f"{word[:-1]}ies"
    if lower.endswith(_SIBILANT_ENDINGS):
        return f"{word}es"
    return f"{word}s"


def pluralize(phrase: str) -> str:
    """Pluralize the head noun of ``phrase``, leaving its modifiers alone.

    "ion thruster" -> "ion thrusters"; "mane of filaments" -> "manes of
    filaments"; "missile battery" -> "missile batteries".
    """
    if not phrase:
        return ""
    boundary = _first_boundary(phrase)
    if boundary != -1:
        head_part, tail = phrase[:boundary], phrase[boundary:]
    else:
        head_part, tail = phrase, ""
    words = head_part.split()
    if not words:
        return phrase
    words[-1] = _pluralize_word(words[-1])
    return " ".join(words) + tail


# ---------------------------------------------------------------------------
# Count phrases
# ---------------------------------------------------------------------------

#: Count tokens that mean exactly one, so their noun stays singular. Every other
#: token a count pool can hold ("a pair of", "four", "banks of", "a ring of")
#: takes a plural noun, so this is stated as the short list rather than as its
#: much longer complement.
#:
#: These are English words, not genre data: a fantasy pack's count pool reaches
#: for the same handful. A pack that invents a new way to say "one" adds the
#: word here, and that one line is the only engine change a count vocabulary can
#: force.
_SINGULAR_COUNT_WORDS: frozenset[str] = frozenset({
    "single", "one", "lone", "solitary", "sole", "solo", "individual",
})


def is_singular_count(token: str) -> bool:
    """Whether ``token`` denotes exactly one, so its noun stays singular."""
    return any(word in _SINGULAR_COUNT_WORDS for word in token.lower().split())


def count_phrase(token: str | None, noun: str, adjective: str = "") -> str:
    """Compose a count token, an optional adjective and a noun.

    ``count_phrase("a pair of", "ion thruster")`` -> "a pair of ion thrusters".
    ``count_phrase("a single", "ion thruster", "cyan")`` -> "a single cyan ion
    thruster". ``count_phrase(None, "ion thruster")`` -> "ion thrusters".

    ``token is None`` is the "no count was resolved" case -- the widget was set
    to None, the filter emptied the pool, or the budget cut it. It voices the
    bare plural rather than an article, because "an ion thruster" would assert a
    count the user did not ask for.

    The adjective goes *inside* the phrase rather than being prefixed by the
    caller, so the head noun stays last and pluralization still lands on it.
    """
    if not noun:
        return ""
    core = f"{adjective} {noun}".strip() if adjective else noun
    if token is None:
        return pluralize(core)
    if is_singular_count(token):
        return f"{token} {core}"
    return f"{token} {pluralize(core)}"


# ---------------------------------------------------------------------------
# Joining
# ---------------------------------------------------------------------------


def join_clauses(clauses: "list[str] | tuple[str, ...]") -> str:
    """Comma-join the non-empty clauses of one entity.

    Deliberately no Oxford "and": an entity's clause list ends with whatever the
    detail budget left standing, so a conjunction in front of a
    randomly-surviving last clause reads as a stronger claim than the pack
    means to make. Commas are also what a text encoder segments on.
    """
    return ", ".join(c for c in clauses if c)
