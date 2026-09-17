# SceneWeaver - genre roadmap: fantasy and horror

**Status: fantasy and horror are built** (`data/fantasy.py`, `data/horror.py`,
their node pairs; see "The fantasy pack" and "The horror pack" in
`docs/architecture.md`). Horror's gore filter shipped as genre labels over the
existing filter axis (R5 there), so no named tag axes were needed for it. The
fantasy Tone filter, cross-genre traits in the payload and `time_of_day` are still
designs. This document keeps the content brainstorm and the decisions behind both
packs, and how each idea maps onto machinery the sci-fi pack proved.

The step-by-step build checklist lives in `docs/architecture.md` ("How to add a
fantasy genre, concretely"). This file does not repeat it; it supplies the
content and the decisions that checklist needs.

---

## 1. What carries over unchanged

Every lesson below cost a sci-fi round to learn. A new pack inherits the
mechanism for free and only has to author the values.

| Sci-fi lesson | Mechanism | What it becomes in fantasy / horror |
|---|---|---|
| A place affords, a value needs | `place_affordances`, `value_needs` | a griffin's dive needs `sky`; a drowned thing needs `submerged` or `shoreline`; a troll turning to stone needs `sunlight` |
| A form says how it holds itself up | `value_stances`, `place_stances` | a naga slithers, a golem walks, a wraith floats, a merfolk swims |
| Two facts that cannot both hold | `value_traits`, `trait_conflicts` | a fire elemental is `combustion`, a sunken shrine is `aqueous`; a skeleton is `bare-bone`, a bloated corpse is `flesh-intact` |
| A dead thing does not act | a closed dormant list, `powered-act` derived for the rest (round XIV) | a petrified basilisk, a statue, a ruined keep: only the acts that need no life or will |
| A dead thing does not glow | `emissive` on every emitter, conflict with `inactive` | a ruined tower has no lit windows; a slain dragon's eyes are dark |
| A small thing cannot take a big one | `craft-prey` / `small-scale` (round XIV) | a pixie does not carry off a knight; a roc can carry off a horse |
| A part fits the body it is bolted to | `part_keywords`, `body_features` | a unicorn has a horn, a centaur has hands and hooves, a naga has no legs |
| A count noun says how many it can be | `value_cardinality` | one horn, a pair of wings, a crown of serpents, a hydra's heads |
| A word is judged by what a model draws | render-trap review, `foreign_nouns` | see the render-trap tables below |
| A context framing imposes no stance | validator check 31 | unchanged; the check is genre-agnostic |
| Variety is kept by adding | `reach_audit.py`, the variety comparison | every rule that removes a value ships with values that replace it |
| Pools are literal | `scripts/builtin_options.py` reads pools with `ast` | a new pack's pools must be literal tuples in its own module (see section 6) |

---

## 2. Widgets: keep one field schema, relabel per genre

**Recommendation: every genre uses the same field *keys*** (`kind`, `subkind`,
`form`, `material`, `primary_color`, `accent_color`, `markings`,
`surface_detail`, `appendages`, `emitters`, `armament`, `sensors`, `aperture`,
`extras`, `condition`, `scale`, `situation`, `environment`, `context`,
`relation`) and changes only the **labels** through `LABELS`.

Why: a `SCENE_ENTITY` payload is matched to the host scene by field key. A shared
schema is what lets a fantasy gorgon wired into a sci-fi station keep its serpent
hair, its bronze scales and its gaze, instead of arriving as a bare noun.

| Field key | Sci-fi label | Fantasy label | Horror label |
|---|---|---|---|
| `material` | Material / Hull | Hide, Coat or Garb | Skin, Remains or Garb |
| `appendages` | Appendages | Horns, Wings and Limbs | Limbs and Growths |
| `emitters` | Emitters / Glow | Glow and Magic | Unnatural Light |
| `armament` | Armament | Weapons (natural or carried) | Weapons and Implements |
| `sensors` | Sensors | Eyes and Senses | Eyes |
| `aperture` | Aperture | Mouth or Opening | Mouth or Wound |
| `extras` | Extras | Trappings | Remnants |
| `condition` | Condition | Age and State | Decay and State |

Genre-specific controls are **appended**, never inserted, because
`widget_order` is positional in saved workflows. Candidates, each with the
contract work it needs:

| Control | Genre | Values | Maps to | Contract work |
|---|---|---|---|---|
| `time_of_day` (scene) | horror, fantasy | Random (default), day, dusk, night, pre-dawn, full moon | a place fact, not rendering: it grants `sunlight`, `moonlight` or `dark`, so a vampire is drawn at night and a troll turns to stone at dawn | a scene field that contributes affordances (today only `environment` does) |
| `tone` (scene filter) | fantasy | Any (default), Whimsical, Heroic, Grim | content tags | generalise `tags` from one axis to named axes |
| `gore` (scene filter) | horror | No gore (default), Any, Gore only | content tags, second axis, the same shape as sci-fi's Peaceful / Conflict | same as above |
| `rider` / relation roles | fantasy | riding, carrying, guarding, hunting | `relation_roles`, `kind_capabilities` | none; declared data |

The existing `scene_filter` (Any / Peaceful / Conflict) keeps working as it is.

---

## 3. Fantasy

### 3.1 Kinds, groups and subkinds

Each kind names its archetype, because the archetype decides how it is spoken
and how much detail it can carry (`detail_cap`, `detail_priority`).

| Kind | Archetype | Subkind groups -> example subkinds |
|---|---|---|
| mythic beast | creature | **equine**: unicorn, pegasus, kelpie, hippogriff - **draconic**: dragon, wyvern, drake, wyrm, amphiptere - **serpentine**: basilisk, sea serpent, amphisbaena - **chimeric**: griffin, manticore, chimera, sphinx - **avian**: phoenix, roc, thunderbird |
| giant-kin | creature (upright) | troll, ogre, hill giant, frost giant, fire giant, cyclops, ettin |
| small folk | figure | goblin, gnome tinkerer, kobold, imp, pixie, brownie, redcap |
| hybrid folk | figure (with body-plan form) | centaur, satyr, minotaur, gorgon, harpy, merfolk, naga |
| folk | figure | **roles**: knight, ranger, cleric, bard, rogue, smith, alchemist - **ancestries** (a group, like sci-fi's alien people): wood elf, high elf, mountain dwarf, halfling, orc, horned folk |
| construct or elemental | machine-like / diffuse | stone golem, clay golem, iron golem, animated armour, fire elemental, water elemental, treant |
| fey spirit | diffuse | will-o'-wisp, dryad, sylph, sprite |
| structure | silhouette (station-like) | castle, watchtower, ruined keep, shrine, bridge, wizard's tower, windmill |
| vessel | silhouette (starship-like) | galleon, longship, airship, war chariot, siege engine |
| artifact | artifact | sword in stone, crystal orb, runestone, cursed idol, portal arch |

### 3.2 Variation comes from fields, not from more subkinds

"Many variations of each creature" is the field matrix, not a longer subkind
list. The subkind names the creature; every other field varies it, scoped by the
subkind group so each value fits the body.

| Creature | `form` | `material` + colours | `appendages` | `emitters` | `armament` | `condition` |
|---|---|---|---|---|---|---|
| unicorn | slender, heavy-boned warhorse build, foal-slight | moon-white coat, dapple-grey coat, obsidian coat; mane silver or storm-dark | a single spiral horn of ivory, crystal or obsidian; feathered fetlocks | a faint horn-glow, star-flecked mane | horn (natural) | ancient, scarred, young |
| troll | hunched, towering, gaunt | stone-grey warty hide, moss-grown hide, frost-blue hide | tusks, long arms, a tail of lichen | none, or ember eyes for a cave troll | a tree-trunk club, bare fists | scarred, moss-covered, frost-rimed |
| gorgon | serpent lower body, upright two-legged | bronze scale skin, green scale skin | a crown of vipers, a coiling tail | a petrifying gaze glow | a bronze shield, a short bow | ancient, battle-worn |
| centaur | light runner build, heavy draught build | chestnut, piebald or grey horse body; leather or bronze harness | a braided tail, hooves shod or bare | none | a longbow, a spear | young, grey-muzzled |
| ogre | pot-bellied, broad-shouldered | pale warty skin, sun-dark skin; hide wraps | a single tusk, a heavy brow | none | a maul, a cleaver | scarred, drunk-heavy |
| goblin | wiry, stooped | grey-green skin, ochre skin; ragged leather | large ears, clawed fingers | lantern-lit eyes | a notched blade, a sling | gap-toothed, scarred |
| gnome | stout, spry | ruddy skin; tinker's apron, embroidered coat | a braided beard, goggles | none | a tinker's hammer | aged, soot-smudged |

Troll *habitat* variants (cave, bridge, frost, moss, river) are **subkinds in a
`troll` group**, because each one changes the needs (a river troll needs
`shoreline`) - the same shape as sci-fi's `hull wreck` group.

### 3.3 Environment bands

| Band | Example places | Affordances |
|---|---|---|
| wilds | enchanted forest, misty moor, mountain pass, glass desert, fen | ground, air, life, sunlight |
| sky | above the cloud sea, among floating islands | sky, air, vast |
| waterside | storm coast, lake shore, kelp shallows | shoreline, submerged (split, like sci-fi) |
| underground | dwarven hall, crystal cavern, crypt, dragon's hoard | floor, structure, dark |
| settlement | market square, tavern interior, throne room, library, alchemist's workshop | floor, structure, crowd |
| otherworld | feywild glade, astral sea, elemental plane of fire | per place |

### 3.4 Situations and tiers

Declared needs do the coherence; tiers price the drama.

* event: a dragon taking flight from its hoard (needs floor or ground, stance flies); a troll turning to stone in the first light (needs sunlight); a kelpie dragging a rider under (needs shoreline)
* activity: a centaur drawing a bow at full gallop (needs ground); a smith quenching a blade
* idle: a unicorn drinking at a pool (needs shoreline)

### 3.5 Render traps (fantasy)

A fantasy word that names an Earth or pop-culture object is the same defect as
sci-fi's "weather balloon". The fix is always the spoken form or a qualifier in
the head noun, never a negation.

| Word | What a model draws | Spoken instead |
|---|---|---|
| medusa | a jellyfish | gorgon |
| gnome | a garden ornament | gnome tinkerer, forest gnome |
| elf | a Christmas helper | wood elf, high elf |
| ogre | one famous green film character | a grey or sun-dark skin ogre, never green-skin in a swamp |
| goblin | a film bank clerk | a cave goblin with ragged leather |
| harpy | a harpy eagle | winged harpy with feathered arms |
| fairy | a pastel sprite with a wand | sprite, fey spirit |
| unicorn | a pastel toy | a war unicorn, a moon-white unicorn |
| dragon | one default Western dragon | vary `form` (serpentine, wyvern-winged, four-legged) |

The **foreign-noun list inverts**: Earth nouns (sword, cart, lantern) are native,
and the anachronisms are foreign - gun, engine, neon, plastic, chrome, laser,
screen.

---

## 4. Horror

### 4.1 Tone rules

* **Dread is staging, not gore.** The strongest horror frame is often an
  `idle`-tier act: a figure standing motionless at the end of the hall. Horror's
  `tier_weights` should price stillness higher than sci-fi does.
* **The pack owns no rendering.** "Creepy", "eerie", "dark and moody" are style
  words and belong in the rendering denylist, exactly as "cinematic lighting"
  does now. Darkness enters as a *place fact* (`time_of_day`, an unlit room).
* **Never negate.** "A ghost with no shadow" draws a shadow. Say "translucent" or
  "lit from within".
* **Gore is a filter, off by default.** `No gore` / `Any` / `Gore only`, the same shape as sci-fi's Peaceful / Conflict: graphic content is fully in scope and one click away, but a first run never surprises anyone.
* **Content guidelines.** No real people or real tragedies; no stigmatising
  mental illness (no "asylum patient" as a monster); no real living religious or
  cultural figures as monsters (no "skinwalker"); no trademarks ("spirit board",
  not the brand name; no named creepypasta characters).

### 4.2 Kinds

| Kind | Archetype | Subkinds | Variation axes |
|---|---|---|---|
| undead | creature / figure | zombie, ghoul, skeleton, mummy, vampire, lich, revenant, bog body | decay stage as `condition` (fresh, rotting, desiccated, skeletal) with conflicts (`bare-bone` vs `flesh-intact`), burial wrappings as `material`, era of clothing |
| spirit | diffuse | ghost, wraith, banshee, shade, poltergeist | `omits` material and armament; `emitters` carries the cold light |
| cryptid | creature | werewolf, antlered stalker, lake thing, moth-winged watcher, hollow-eyed deer | build, fur or hide, antlers, eyes that catch the light |
| eldritch | creature | tentacled mass, many-eyed shape, the thing under the ice | overlaps sci-fi aliens: the cross-genre wire is the feature |
| human threat | figure | cultist, masked stalker, plague doctor, lantern-bearing warden, witch | mask as `aperture`, robes as `material`, lantern as `emitters` |
| cursed object | artifact | porcelain doll, cracked mirror, music box, spirit board, portrait with moved eyes | `condition`: cracked, scorched, water-stained |
| haunted structure | silhouette | farmhouse, lighthouse, chapel, cabin, carnival ride | no lit windows unless something is inside it (`emissive` vs `abandoned`) |

### 4.3 Places

fog-bound moor, dead forest, cornfield at night, flooded cellar, hospital
corridor after closing, crypt, bayou, snowbound cabin, small-town street before
dawn, carnival after closing. Each declares `dark`, `floor`, `structure`,
`submerged` or `shoreline` as it truly has them.

### 4.4 Coherence the horror pack must declare

* **The dormant axis inverts for undead.** On a skeleton "dead" is not
  `inactive` - a dead thing that walks is the point. `inactive` belongs to *at
  rest* states ("lying in its coffin", "slumped against the wall"), and a pack
  declares which acts those states permit. This is exactly why liveness is pack
  data and not engine logic.
* A vampire needs `dark`; a werewolf needs `moonlight`; a drowned thing needs
  `submerged` or `shoreline` - all positive affordances, never "no sunlight".
* A spirit floats and passes through structure; a zombie walks and cannot fly
  (`value_stances`).

---

## 5. Cross-genre: a gorgon in a space station

Today a foreign entity is spoken through the host's `archetypes[POOL_DEFAULT_KEY]`
and **trait conflicts fail open**, because the host pack has never heard of the
foreign values. That is safe, but it means a wired fantasy dragon inside a
starship cockpit is not stopped by the sci-fi `cramped-room` rule.

**Proposal (contract change, sci-fi first):**

1. **A shared trait lexicon.** Trait names that mean the same thing in every
   genre (`small-scale`, `large-scale`, `inactive`, `emissive`, `aqueous`,
   `combustion`, `interior-place`, `craft-prey`) are documented once and reused
   verbatim by every pack.
2. **The payload carries its traits.** `SCENE_ENTITY` records, per field, the
   traits the *origin* pack declared for that value. The host engine unions
   them with its own before expanding `trait_conflicts`, so a colossal dragon is
   `large-scale` in any host and a cockpit still refuses it.

Both are additive and backward compatible: an older payload with no traits keeps
failing open.

---

## 6. Implementation gotchas already known

* **Pools must be literal in the pack's own module.** `scripts/builtin_options.py`
  parses `data/genre.py` and the pack with `ast` and resolves only literals,
  earlier names and `+` concatenation. A pool appended later
  (`POOLS["x"] = POOLS["x"] + (...)`) or imported from a shared module is
  invisible to it, and `tests/test_user_options.py` fails. Shared undead
  vocabulary between fantasy and horror is therefore duplicated as literals, or
  the reader is extended first.
* **Add a value with its whole card**: pool, tag, tier, needs, stances, traits,
  cardinality, spoken form, in the same edit.
* **Measure before and after**: `scripts/coherence_sweep.py` classes for the new
  genre's own incoherence shapes (anachronism, scale, a statue acting), and a
  variety comparison against the previous version so a gate that removes values
  does not quietly narrow the output.
* **Replay a real batch before theorising**: render a batch, pull the bad
  images, run `scripts/replay_batch.py` on the folder.

---

## 7. Suggested phases

| Phase | Scope | Done when |
|---|---|---|
| 0 | Contract prep in sci-fi: shared trait lexicon, traits in the payload, optional named tag axes | sci-fi gates green, a fixture pack in `tests/test_genre_seam.py` proves a foreign trait fires |
| 1 | Fantasy vertical slice: mythic beast, giant-kin, small folk, folk; wilds, underground, settlement bands; creature, figure, structure and default archetypes | validator, sweep and reach audit green on the new pack |
| 2 | Fantasy breadth: the full creature matrix of section 3.2, situations with tiers, a render-trap review from a real batch | a replayed batch carries no new class |
| 3 | Horror pack, reusing creature, figure and diffuse archetypes; `time_of_day`; gore filter | same gates, No gore by default |
| 4 | Cross-genre polish: a gorgon in a station, a sci-fi drone in a crypt | the wired path sweep is as clean as the unwired one |

## 8. Decisions (maintainer, 2026-09-16)

1. **Fantasy tone is a choice, not a fixed voice.** A `tone` filter (Any,
   Whimsical, Heroic, Grim) defaults to **Any**, so an untouched node draws
   across every tone and nothing has to be picked up front.
2. **Horror gore is an option.** A `gore` filter (No gore, Any, Gore only)
   mirrors Peaceful / Conflict; it defaults to No gore.
3. **Separate node pairs, one pack.** Scene Weaver - Fantasy / Scene Entity -
   Fantasy and Scene Weaver - Horror / Scene Entity - Horror ship inside this node
   pack, beside the sci-fi pair. This is the shape the genre seam was built for: a
   genre dropdown on one node cannot work, because ComfyUI fixes a node's widgets
   at registration and a saved workflow stores them by position. The shared field
   schema (section 2) is what makes the separate nodes interoperate.
4. **`time_of_day` goes to fantasy and horror, not sci-fi.** Its value is
   coherence, not lighting: it decides which acts and creatures fit (a vampire at
   night, a troll turning to stone at dawn, a werewolf under a full moon), and a
   user can pin "night" for a whole batch. It defaults to Random so it adds
   variety rather than narrowing it. Sci-fi does not need it: most sci-fi places
   have no day at all, and the places that do already carry `sunlight`. Its one
   risk is a clash with a style prefix ("golden hour" against "night"), which the
   README will call out.
