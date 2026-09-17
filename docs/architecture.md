# SceneWeaver - architecture

## The genre seam

**Genre is node identity, never a wire and never a widget.** ComfyUI fixes a
node's widget set at registration time, so a `genre` dropdown could not change
what the other widgets *are* - it could only change what they mean, silently, in
a saved workflow. Instead each genre ships its own pair of node classes,
generated from a data contract.

The contract is `GenrePack` in `data/genre.py`: a frozen dataclass carrying the
kinds, the field specs, the pools, the per-kind labels, the count pairings, the
content tags, the constraint rules and the prose templates. `data/scifi.py`
declares one. Adding a second genre is **one `data/<genre>.py` and two lines in
the repo-root ``__init__.py``** - no engine change, no node change, and no
existing saved workflow can break, because nothing that already shipped is
touched.

### How to add a fantasy genre, concretely

The whole checklist, because "one data module and two lines" deserves the
exact steps:

1. Create ``data/fantasy.py`` declaring a ``FANTASY_PACK = GenrePack(...)`` with
   its own ``slug``, ``display``, ``class_suffix``, ``entity_fields``,
   ``scene_fields``, ``pools``, ``labels``, ``counts``, ``tags``, ``constraints``
   and ``prose``, plus the declared-coherence vocabularies ``place_affordances``,
   ``value_needs`` / ``default_needs``, ``value_stances`` / ``place_stances``,
   ``value_traits`` / ``trait_conflicts`` and ``kind_capabilities`` /
   ``relation_roles``. Copy the *shape* from ``data/scifi.py``; author the
   *values*.

   **A wired entity from any genre is re-drawn to fit the host scene unless the
   user locked the value.** A foreign payload that does not declare ``locked`` is
   treated as fully unlocked, so a fantasy beast wired into a sci-fi scene is
   placed by the host's rules rather than dropped into a place that cannot hold
   it.
2. Set ``prose.narrative_mode = True`` to opt into the scene-composition pass
   (``compose_scene``), or leave it false for sentence-per-section output.
3. Register it in the repo-root ``__init__.py`` - two lines naming the module
   and mapping its two node classes, mirroring the sci-fi block.
4. Run ``python tests/validate_data.py``, which is written against any pack
   (``validate(pack)``) and will report pool, tag and constraint authoring
   errors before a node is ever built.
5. Declare ``archetypes`` and ``archetype_of_kind`` - one per category of thing
   your genre speaks differently, plus a **required** ``archetypes[POOL_DEFAULT_KEY]``.
   Each archetype answers six questions:
   1. **What is the head noun, and does it need an apposition?** ``HeadPhrase``.
   2. **Is the body plan the subject or a modifier?** ``HeadPhrase.subject``.
      ``subject_leading_kinds`` is the declaration ``ProseSpec`` cross-checks.
   3. **What pronoun, possessive and copula does it take?** ``pronoun``,
      ``possessive``, ``pronoun_copula`` - a person is ``they/their/are``, a
      place is ``it/its/is``.
   4. **What sentences does it speak?** ``sentences`` - written as English, with
      a fallback ladder from richest to barest.
   5. **What does it never have?** ``omits``.
   6. **How many details can a viewer hold of it, and which ones?**
      ``detail_cap`` and ``detail_priority`` - see "An archetype owns how much
      is spoken" below.
6. Declare ``pool_groups`` and set each field's ``scope``. This is where a genre
   stops producing legal-but-contradictory subjects: a field draws from the pool
   its control chain selects, so "a gas giant" and "a ring shape" cannot land in
   one sentence.
7. Write the pack's ``prose.environment_sentence`` and ``scene_frame`` that name
   the genre; the per-archetype ``sentences`` carry the rest of the prose.
8. Declare ``environment_bands`` and write the exclusions that tie your subjects
   and actions to your places. Author only the exceptions. **Author a
   ``_default`` situation pool** or a foreign entity stands still.
9. Declare the **dramatic-weight** axis. Two optional declarations price the
   interesting end of a pool, and one scene field breaks the product shot:

   * ``value_tiers`` / ``tier_weights`` - ``{field: {value: tier}}`` plus
     ``{tier: relative weight}``. Every value of a tiered field must carry a
     tier, or ``tests/validate_data.py`` reports it. This is how a genre says
     which of its own actions are worth a picture: without it, widening a pool
     raises coverage and lowers the mean interest.
   * ``FieldSpec.omission_weight`` - the relative weight of drawing *no* value
     at all. A head-phrase modifier (``scale``, ``condition``) is spoken on
     every entity, and a describing word on every entity stops meaning
     anything; an omission weight lets it go unsaid.
   * ``FieldSpec.weights`` on ``kind`` (``KIND_WEIGHTS``) - which subjects a
     scene is most often about.
   * a ``context`` scene field scoped on ``environment`` - what else is in the
     shot. It is drawn once per scene and spoken after the entities; give it
     per-band pools and ``value_needs``, and give it no form, material or
     components of its own. The sentence it is spoken in is
     ``prose.context_sentences``, a set of whole ``Sentence`` patterns one of
     which is drawn at random per scene; the holes are ``{context}`` (the value
     bare), ``{a_context}`` (its articled form) and ``{pronoun_object}`` (the
     subject's object pronoun - a person is "them", never "it"). Give the
     field an ``omission_weight`` so some scenes have no context sentence at
     all, and record the drawn index in ``prompt_json._meta`` so a document
     round-trips.

   The same declarations, in three genres:

   | declaration | sci-fi | fantasy | horror |
   |---|---|---|---|
   | ``value_tiers`` / ``tier_weights`` | a station venting fire beats one showing its windows | a dragon taking flight beats a smith sharpening a blade | the thing stepping into the light beats a door creaking |
   | ``FieldSpec.omission_weight`` | scale, condition | age, rank | affliction |
   | ``KIND_WEIGHTS`` (plain ``FieldSpec.weights``) | creatures over artifacts | beasts over furniture | the haunting over the house |
   | ``context`` (scene field) | a drifting line of dead hulls | a burning village on the ridge | a congregation waiting at the treeline |
   | ``default_needs`` | every vehicle situation needs a floor | every mounted action needs ground | every stalking action needs enclosure |
   | ``place_affordances`` / ``value_stances`` / ``place_stances`` | a torus only floats or orbits | a wyrm coils, a golem walks | a thing that only crawls |
   | ``prose.context_sentences`` | "Beyond them, a line of service gantries." | "Beyond them, the burning village." | "Further back, the congregation waits." |
   and fails if the genre leaked into either.

10. Declare ``prose.environment_staging`` and the ``part_keywords`` /
    ``part_lint_fields`` pair. Staging appends a suffix to the setting sentence
    when the place affords it (", out in open space"), because a model grounds
    anything it is not told floats. The part lint is what stops a component
    pool -- keyed by kind -- from bolting a track onto a drop pod; both are
    explained in "Round XII decisions" below.
11. Declare the **liveness and scale relations** (round XIV): a closed list of
    dormant acts with `powered-act` derived for every other situation, an
    `emissive` trait on every emitter, and the relative-scale pairs (a small
    body cannot take a craft, an indoor creature cannot cross an outer hull).
    Keep every pool a **literal** in the pack module -- a pool appended after
    its declaration is invisible to `scripts/builtin_options.py`. The content
    brainstorm for fantasy and horror is `docs/genre-roadmap.md`.

**What a new genre inherits, and what it must author.** Nothing in the engine
learns a genre, so the polish round's grammar and scope machinery are free to a
second pack, and only the pattern wording is authoring:

* The **closing apposition** and the **promoted subject that keeps its
  modifiers** are grammar, not vocabulary. A fantasy `beast` archetype that
  promotes its body plan gets "A huge scarred six-limbed frame, a beast, is ..."
  with no authoring beyond the head phrase.
* **Pattern authoring is the work.** A pattern must state the real relationship
  between the subject and the part - `{pronoun} is {form}` says the thing *is*
  its body, `{pronoun} has {form}` says it has one - and the choice is the same
  question in any genre.
* The **scope chain** and the **band rules** are generic. A pack writes its
  `situation` group keys against its own subkind groups and its band rules
  against its own `environment_bands`. The reusable idea is that a band class
  says what a scene *affords* (a floor, air), so an action is excluded by the
  affordance it needs rather than by a list of places it is wrong.
* **An authoring rule no validator can check:** a subkind must not be a word
  that names a real-world object unless the category noun beside it says which
  world it is from. A fantasy `sword` beside a `weapon` category noun reads as a
  museum piece unless something in the phrase places it.
* ``GenrePack.motifs`` is a **contract field**: every genre declares its own
  cross-field word families and gets the same bias report. The engine still
  never reads it. ``tests/test_genre_seam.py`` declares one motif and the sweep
  helper reports it.

**The cross-genre rules, in one place.** A foreign entity wired into a scene is
spoken by the *host* pack:

* The scene's frame is the host's - ``environment_sentence`` and ``scene_frame``
  describe the picture, not the subject.
* The entity keeps its own ``genre`` tag in ``prompt_json``.
* Situation and relations stay the host's; the entity only brings what it *is*.
* A foreign kind narrows no environment: the wired-kind filter skips any value
  the host pack has never heard of, so the environment pool stays full.
* Trait conflicts fail open: a foreign value carries no trait, so no rule fires.
* The entity is spoken through the host's ``archetypes[POOL_DEFAULT_KEY]``, which
  is why that entry is required rather than optional.
* A wired value is re-drawn to fit the host place unless the payload declares it
  ``locked``. A payload with no ``locked`` key - an older saved graph, or a node
  that does not know about locks - is fully unlocked, so a fantasy beast wired
  into a sci-fi scene is placed by the host's rules rather than dropped into a
  place that cannot hold it.

Nothing under ``nodes/`` or ``engine/`` changes. That is the seam.

Three layers, in the order a value travels:

| Layer | What it is | Who writes it |
|---|---|---|
| `FieldSpec` | What a genre *declares* about one field - group, label map, its scope chain (which control fields key its pool), whether the filter touches it, its count partner. | Authored by hand in the pack. |
| `FieldDef` | What `build_field_definitions(pack, slots)` *builds* for one widget on one node: a `FieldSpec` with its options resolved, its slot bound, its widget key and its constraint address computed. | Machine-made. |
| widget | What a node class emits from a `FieldDef`. | `nodes/widgets.py`. |

Two key spaces, deliberately distinct: the **widget key** (`entity2_kind`) is a
legal Python identifier because it arrives at `execute()` as a keyword argument;
the **constraint address** (`entity2.kind`) is dotted and shared by both node
classes so a rule is written once.

What keeps the seam honest rather than aspirational:

- `nodes/` and `engine/` may not name a genre. `tests/test_genre_contract.py`
  greps both packages for every pack slug and fails on a hit.
- The engine must import without importing any pack - asserted, not assumed.
- `tests/test_genre_seam.py` builds a throwaway two-kind fixture pack in memory,
  generates both node classes from it and runs the whole engine over it, with
  zero edits under `nodes/` or `engine/`. If that test ever needs a production
  edit to pass, the seam is not real and the *contract* is what to widen.
- `SCENE_ENTITY` is one socket type shared by every genre, so any genre's entity
  node wires into any genre's scene node. A sci-fi entity in a fantasy scene is a
  supported feature, not an accident: the scene node's genre supplies the
  environment, situations, relations and prose templates, the entity brings its
  own description and carries its own `genre` tag into `prompt_json`, and a
  constraint rule keyed on a kind the scene's pack does not define simply never
  fires. `tests/test_genre_seam.py` pins that path too.

One deliberate exception. `scripts/sample_distribution.py` hardcodes the sci-fi
pack, because it is a maintainer tool whose ceilings are measurements *of* that
pack. `tests/validate_data.py` is written against any pack (`validate(pack)`) and
reads `omitted_pools` and `shared_vocabulary` off the pack rather than by
identity - that is the one that has to be genre-free, and is.

## The generation pipeline

`engine.generate_scene(seed, pack, ...) -> (prompt_text, prompt_json)` is pure
and genre-blind. Everything it knows about a genre it was handed in a
`GenrePack`; everything it knows about the user it was handed in a widget
mapping. Same arguments, same two values - that is the whole of the "same seed
reproduces the same scene" guarantee.

Seven steps, and the order is load-bearing:

1. **`rng = random.Random(seed)`** - one generator, consumed in a fixed
   traversal.
2. **`set_all_fields`** - the bulk edit. It rewrites widgets that say `Random`
   or `None`; it never touches one holding a literal value, because that is a
   lock and a bulk control must not silently undo a deliberate choice.
3. **Merge wired entities**, then settle occupancy. A `SCENE_ENTITY` plugged
   into a slot replaces that slot's *descriptive* fields; the slot's `situation`
   and its relations stay the scene's. The `Entities` control then empties every
   slot past it - it clamps, never commands, so a slot set to `None` inside the
   count stays empty and a locked kind or a wire occupies its slot outside the
   count.
4. **The `scene_filter` pre-pass** masks tagged pools *before* any draw. Masking
   after the draw would mean choosing a weapon and then talking around it.
5. **Resolve** every field from its scope-keyed, filter-masked pool - the whole
   address space, not the widget list, so a supporting slot is described rather
   than named (`build_resolution_definitions`). Fields resolve in widget order,
   each drawing from the pool its `scope` chain selects, so a value locked on a
   scoped field narrows the control draw before it happens.
6. **Constraints** to a fixed point, capped at `MAX_CONSTRAINT_PASSES` (12). The
   pre-pass does not count toward the cap - it is a pool mask, not an iteration.
   A rule that re-draws a `kind` re-scopes that slot, because everything already
   drawn was scoped by the old one.
7. **The detail budget**, last, because it can only cut what has been drawn. It
   applies the archetype's `omits` first, then spends the allowance.

### The three precedence rules

Each is written down here because each is surprising if you meet it by
accident.

**A wired entity beats a locked slot widget.** Wiring a whole node into a slot is
a more explicit statement than choosing a value from that slot's dropdown, and
the alternative - a widget quietly overriding the node the user visibly
connected - is worse. Every field it overrides is named in
`_meta.overridden_fields` and logged at WARNING, so it is reported rather than
discovered.

**A wired value the user chose beats a constraint rule; a wired value the node
drew does not.** A field locked on the Scene Entity is an explicit choice, so it
wins and the rule's `reason` goes to `_meta.warnings`. A field the Entity node
drew at random is not a choice - it is a draw - so it stays an ordinary resolved
value. **The place adapts to the subject before the subject adapts to the
place:** a wired or locked subject narrows the environments to those that hold
its whole description, else its kind and type, else its kind, and only a drawn
field no remaining place can hold is re-drawn - recorded in
`_meta.redrawn_fields` (`schema_version` 3) so the node face can name what
changed. The `locked` list in the `SCENE_ENTITY` payload is what carries the
choice/draw distinction; a payload without it (an older saved graph, a
foreign-genre node) locks nothing. Treating every wired field as a lock is what
let a walker be drawn in vacuum and a torus rest on its ring.

**A reason is warning text, never description.** The rule's `reason` goes to
`_meta.warnings`, never into `prompt_text`: a reason is the pack's one
deliberate exemption from the never-negate rule, and it is warning text, not
description.

## The scope chain

A field's pool used to be keyed by one control token: `kind`. Every draw from
that pool was legal in isolation, and many *pairs* of draws were not - a gas
giant shaped like a spiral coil of gas, a gelatinous mass covered in a
feathered pelt, a spacefarer with eight sidearm holsters. One token could not
say "a subkind decides the shape, and the shape decides the substance".

`FieldSpec.scope` is the ordered chain of **control fields** whose current
values key a field's pool, most specific first: `"form": FieldSpec(...,
scope=("subkind", "kind"))`. Resolution walks the chain - raw value, then that
value's declared **group**, then the next control - and ends at
`POOL_DEFAULT_KEY`. `GenrePack.pool_groups` is `{control: {group: (values)}}`,
so a genre says "every solid world has one of these shapes" once instead of
once per world; a subkind that needs its own pool still overrides its group,
because the raw value is checked first.

The six component fields (`appendages`, `emitters`, `armament`, `sensors`,
`extras`, `markings`) walk the same chain: `scope=("subkind", "kind")`, so a
black hole draws ring arcs and accretion streamers where a planet draws rock
spires and ejecta rays. The `phenomenon` groups get their own keyed pools
(`APPENDAGE_POOLS`, `EMITTER_POOLS`, `MARKINGS_POOLS`); the groups that
deliberately share their kind's vocabulary are declared in `scope_fallthrough`.

Every alien-creature body plan has a key in all five morphology pools
(`appendages`, `armament`, `sensors`, `aperture`, `material`), so a fungal
colony draws fronds and spore defences where a segmented hunter draws scythe
arms and mandibles. The body plan decides what parts exist; the kind pool is
only the fall-through for a slot whose subkind was never drawn.

`scope_fallthrough` is `{(field, scope key)}` that may resolve through the
fall-through rather than a key of its own, so "I forgot to classify sarcophagus
pod" is a validator failure rather than a silent bad render.

Two rules make the chain resolvable in one forward pass:

- A field's scope may only name a control that resolves before it. `kind`
  scopes on `environment` (drawn first), `subkind` on `kind`, `form` on
  `(subkind, kind)`, each count on its noun. `GenrePack` refuses a pack that
  names a forward reference.
- A re-drawn control re-draws what it scopes. A constraint that re-draws
  `subkind` re-draws the `form` under it, and a re-drawn noun re-draws its
  count.

The frontend mirrors the engine exactly - `js/sceneweaver.js` walks the same
chain, so a dropdown never offers a value the engine could not draw. `python
scripts/coherence_audit.py` measures the result: the share of each kind whose
`form` resolves through a group rather than the fall-through, and the
head-noun collision rate.

## Coherence is declared, not listed

The pack used to answer "can this thing, in this place, do this?" with a dozen
hand-maintained tuples. Hand lists do not survive a huge pool: the author of
the four-hundredth situation cannot remember which of eight lists it belongs in.
Four declarative vocabularies on the contract replace them, each expanded into
ordinary `ConstraintRule`s by genre-blind code in `data/genre.py`.

- **Affordances and needs.** `place_affordances` says what a place *provides*
  (ground, floor, shoreline, submerged, sky, open-space, deep-space, structure,
  dock, vast, sunlight, cold, dust, life, plus `gravity` - anything to stand on,
  fly in or sink through - and `vista`, a clear view with no field of rubble to
  set a world on); `value_needs` says what a value
  *requires* of the place. A value is excluded from every environment whose
  affordances lack any of its needs. `default_needs` carries the need of a whole
  pool key, so a key is classified once instead of once per value; a value's own
  entry wins over it (an empty one means "deliberately needs nothing"), and a
  value authored under several keys takes the union of their defaults. The
  needs-free situation cores stay neutral on purpose: a value drawn by several
  subkind groups at once cannot need every place it is drawn under. A raw
  environment's entry replaces its band's; a value with no entry takes its
  band's. `affordances_of` is the one lookup, and `resolved_needs` the one
  resolver.
- **Stances.** `value_stances` says how a body holds itself up (rests, walks,
  rolls, flies, hovers, floats, swims, orbits) and `place_stances` says which
  stances a place's affordances support. A form is excluded from every
  environment that supports none of its stances, and a situation from a form
  whose stances it cannot share. This is the axis that kills the ring standing
  on its ring: the place was legal and the shape was legal, and only the
  pairing was wrong.
- **Traits and conflicts.** `value_traits` says what a value *is* (a role, a size
  class, a state) and `trait_conflicts` says which pairs cannot co-exist on one
  entity, with `trait_reasons` carrying the warning text. The trigger stands and
  the target gives way.
- **Capabilities and roles.** `kind_capabilities` says what a kind *can do*;
  `relation_roles` says what each relation needs of its two endpoints. The
  expander keeps the kinds whose capabilities cover a non-empty need set.
- **Derived feasibility.** From the same two tables: a *type* is excluded from
  every place none of its forms can stand in, and a *kind* from every place none
  of its types can exist in. Without it the stance rule empties a form's pool and
  the subject is described with no silhouette in a place it cannot occupy; with
  it the type is re-drawn instead. Run before the stance rules, so a kind is
  re-drawn before the rules that scope its subkind and form.
- **Derived affordances.** `air` and `cloud-deck` are not authored place by place.
  A need cannot be negated, so absence is derived as a positive affordance: every
  place that has neither `open-space` nor `submerged` affords `air`, and the three
  cloud places afford `cloud-deck`. A bare face, an open garment or a cloud-top
  action then declares the need it has, instead of every place having to declare
  that it has no atmosphere.
- **Furnished rooms.** `value_traits` on `environment` marks the rooms with
  furniture, and the conflict with `small-scale` keeps a small subject off the
  table.

`GenrePack.all_constraints` is the declared rules plus those expansions, computed
once at construction. `engine/scene.py` evaluates it, never the declared-only
tuple, so a derived rule behaves exactly like a hand-written one. The lints in
`tests/validate_data.py` are what make a huge pool safe: foreign nouns
(`FOREIGN`, scanned over spoken forms and every authored sentence), affordance
keywords (`AFFORDANCE`), the classification gate (`UNCLASSIFIED`), an empty need
default (`EMPTYDEFAULT`), a kind a place offers but cannot hold (`DEADKIND`), a
stance for every shape (`STANCE`), a movement word without its stance
(`STANCEWORD`), a body part a body lacks (`BODY`), a subject with no declared
body (`BODYCOVER`), a place that grants no two contradictory affordances
(`CONTRADICTION`), attributive head-phrase modifiers (`ATTRIBUTIVE`), a singular
form after a singular verb (`SINGULAR`), the per-type band floor (`FLOOR`), a
spoken form for every subkind of an apposition-free kind (`SPOKEN`), and a value
no subject can draw (`SHADOWED`).

### A subject is one noun phrase

`spoken` is `{field: {token: spoken form}}`. A dropdown token is a control that
pools, groups, tags and rules are keyed by, so renaming it cascades; a sentence
wants one noun phrase whose head names what the thing is ("hospital starship").
Every value that reaches text routes through `spoken_value` -- the head noun, a
folded colour, a relation reference, the environment -- while `prompt_json`
keeps the token, because a wired payload must round-trip. A compound colour is
hyphenated ("bone-white armour"), and a mass noun takes no article
(`engine.grammar._MASS_HEADS`).

### The value card

Every new value, in any field, is added with all of its declarations in the
same edit. For a lesser model this is the checklist; follow it literally:

1. **Field and key** -- which pool, under which kind / group / band key.
2. **Wording** -- bare, article-less; singular if the field has a count
   partner; attributive if it is a head modifier; describes the subject, never
   the lighting, lens or framing; never negates; contains no foreign noun
   unless allowlisted; for a situation, a gerund phrase that passes camera,
   actor, frame and mechanism.
3. **Spoken form** -- only if the token reads wrong in a sentence (subkinds of
   apposition-free kinds always need one; compound colours are generated).
4. **Needs** -- what the place must afford, on the value's own `value_needs`
   entry (an explicit empty entry is allowed and deliberate; an empty
   `default_needs` entry is not). Run the affordance lint; declare the need or
   allowlist with a comment saying why.
5. **Stances** -- for a situation that moves a body, declare the stance its
   wording implies in `value_stances["situation"]`, or `STANCEWORD` fails it.
6. **Body** -- a situation that names a body part goes in a tail whose bodies
   have it, not in the shared core, or `BODY` names the body that lacks it.
7. **Traits** -- role, size class, state, limb plan, as applicable.
8. **Tag** -- exactly one content tag if the field is `tag_scoped`.
9. **Group** -- for a subkind, its `SUBKIND_GROUPS` entry, and whether its
   group needs its own situation, form, material or colour key.
10. **Run** `python tests/validate_data.py` and
    `python scripts/sample_distribution.py --seeds 1000`.

### Deferred, and why

- **A `megastructure` kind** (orbital ring, stellar gate) overlaps `space
  station` and `alien artifact` today; it needs its own archetype and place
  table.
- **A plural subject -- a fleet, a swarm, a herd** needs `{copula}` and pronoun
  agreement across every pattern and a count on the subject itself.
- **Placement** -- a world *in the sky above* a surface scene. The pack
  describes entities but never places them; this is the concept that would let
  a celestial body return to the planetary-surface band. Surface places now
  name a visible alien sky feature through their `spoken` forms, which is
  scenery rather than a placed entity.
- **Not** lighting, time of day, camera or lens -- those are rendering and
  belong to a style pack (`comfyui-stylebook`); `tests/test_boundary.py`
  enforces the line.


## Prose: archetypes and the sentence grammar

The pack generated coherent *data* and incoherent *prose* for a long time. Two
mechanisms fix that, and both live in the pack rather than in the renderer.

### A genre writes its sentences

An entity used to be one sentence carrying every surviving clause behind a
single "with":

> A large salvager with a long-limbed frame, clad in obsidian black mail-weave
> underlayer, a ring of magnetic safety clamps, a ring of sulphur yellow wrist
> console panels, a fan of energy carbines, banks of targeting monocles is
> running a diagnostic on an open panel.

Thirty tokens separate the subject from its verb, and every field arrived in the
same grammatical relationship to the subject however unrelated it really was -
`, a whale-bodied hull` says the courier *is* a hull. A clause list can only
attach a detail with a comma.

So a genre declares whole English sentences with named holes
(`data.genre.Sentence`) and the renderer fills them. Four constructs, no more:

| construct | meaning |
|---|---|
| `{field}` | a slot: that field's rendered phrase. |
| `{a, b, c}` | a list slot: whichever members resolved, ", "-joined with " and " before the last. Resolves when at least one did. |
| `[ ... ]` | an optional segment, emitted only when every slot inside it resolves. Never nested. |
| anything else | literal text. |

Two rules are the whole control flow. A pattern is spoken only when every slot
**outside** a bracketed segment resolves, and a field spoken once is
**consumed** - so a genre writes a ladder of fallbacks and exactly one rung
fires:

```python
Sentence("{pronoun} has {form}, clad in {material}."),
Sentence("{pronoun} is clad in {material}."),
Sentence("{pronoun} has {form}."),
Sentence("{pronoun} shows {surface_detail}."),
```

**A pattern must state the real relationship between the subject and the
part.** `{pronoun} {pronoun_copula} {form}` said a courier *is* a hull;
`{pronoun} has {form}` says it *has* one, while a wreck still says it *is* a
flattened impact hull section, which is true there. The possessive
construction (`Its {form} is clad in ...`) is unavailable because a clause slot
carries its article - `{form}` renders "a whale-bodied hull" - so `has` carries
the same statement. A genre picks the rung per archetype, and the choice is
the same question in any genre: is this thing its body, or does it have one?

The grammar slots `{subject}`, `{pronoun}`, `{possessive}`, `{copula}` and
`{pronoun_copula}` are never consumed; `{subject}` is, so the entity is
introduced once. The connector, the verb and the possessive are genre data: a
person `wears` their material, a world has `a crust of` it, a hull is `clad in`
it, and the renderer knows none of that.

**An apposition closes itself.** The head phrase voices the category noun as an
apposition and closes it with a comma, because an English apposition is set off
on both sides: `A large weathered passenger starship, a wreck, is venting...`. The
comma is absorbed by `engine.prose._tidy` when the subject *ends* the sentence
(`..., a wreck,.` becomes `..., a wreck.`) or when an authored `[, ...]`
segment follows. That is deliberately the renderer's job rather than every
pattern's: one hole, once, for the whole pack, for the same reason the space
rules live there.

**A promoted subject keeps its modifiers.** When a `HeadPhrase.subject`
promotes a field to the head-noun position (a creature's body plan), its
`modifiers` fold onto it as leading adjectives rather than falling back to a
clause of their own - `A large battle-scarred segmented worm body, an alien
creature, is dragging a kill toward its burrow.` The clause grammar did the
opposite, which forced the creature to carry `{pronoun} {pronoun_copula}
{scale}.` and `{...} {condition}.` patterns and rendered as two filler
sentences per creature. `_always_consumed` mirrors the renderer, so the
coverage check knows the modifiers are voiced by the head phrase.

Two rules that are not stylistic. Every clause head an archetype does not omit
and its head phrase does not consume must be **covered unconditionally** by a
pattern - a solo slot or a list-slot member, never only inside an optional or
behind another required slot - or `GenrePack` refuses the pack, because such a
field would be drawn every render and never voiced. `kind` is the one
exception: it is the spine, not a description, and a document may hold it
unspoken.

### An archetype says how a category of thing is spoken

`kind` decides what an entity is drawn *from*. It turned out not to decide how
the result is *said*: `ProseSpec.templates` was keyed by field name only, so
`"material": "clad in {value}"` applied to a nebula, a person and a warship
alike. A black hole was ice-encrusted, clad in molten rock, with an impact
crater basin.

`data.genre.Archetype` is the missing axis. Each one may override the clause
templates, the head phrase, the sentence patterns and the pronouns, and may `omit`
fields outright. Resolution is most-specific-first: `archetype_of_override`
(keyed on `archetype_override_field`, which sci-fi points at `subkind`), then
`archetype_of_kind`, then a `_default`, then the `ProseSpec` alone.

The sci-fi pack declares nine. Two of them are why the override axis exists:
`celestial body` splits, because a moon is a `world` with a crust and a nebula
is a `phenomenon` with no surface at all, and `alien creature` splits the same
way for the same reason.

**`omits` is applied in the detail budget, not in the renderer.** The budget is
the one place allowed to decide a field is unspoken, and it writes what it
decides back to `None`; suppressing a field at render time would leave the value
standing in `prompt_json`.

The pack had this concept already, five times over, as module-private tuples -
`_LIVING_KINDS`, `_MOVABLE_KINDS`, `_DIFFUSE_CELESTIAL_SUBKINDS` and friends -
each able only to delete values from a pool. Promoting them is what let
`_DIFFUSE_RULES` and `_ARMAMENT_RULES` be deleted: those rules covered two of
the eight fields that presume a surface, where an archetype's `omits` covers all
of them.

### An archetype owns how much is spoken

Grammar was only half the axis. The reference corpus showed the split was by
*kind*, not by luck: a creature or a person renders well, a station, wreck,
artifact or world renders badly, with identical grammar and only the clause
count differing. A creature's component clauses ARE its anatomy; a station's are
six micro-greebles at a scale a model cannot place, and they outweigh the
silhouette.

So an archetype also owns its detail shape:

* ``detail_cap`` - the most optional clause heads it ever speaks, or ``None`` for
  "whatever the caller's allowance says". Applied as a floor on the caller's
  allowance (``min``), never a raise: a four-entity scene must not get *more*
  detail because one slot holds a creature.
* ``detail_priority`` - fields promoted to the front of the spend order. Fields
  not named follow in ``ProseSpec.detail_priority`` order, so an archetype states
  only what it wants differently.

The shipped caps and priorities (a starting point, tuned by
``scripts/coherence_audit.py``):

| archetype | kinds | `detail_cap` | `detail_priority` |
|---|---|---|---|
| `creature` | alien creature | 11 | form, subkind, material, primary_color, appendages, sensors, aperture, scale, armament, extras |
| `figure` | spacefarer | 9 | form, subkind, material, primary_color, markings, accent_color, armament, sensors, condition, scale |
| `machine` | robot or mech | 8 | form, subkind, material, primary_color, scale, sensors, armament, emitters |
| `world` | celestial body | 8 | form, subkind, material, primary_color, scale, condition, appendages, emitters |
| `craft` | starship, surface vehicle | 7 | form, subkind, material, primary_color, emitters, scale, condition |
| `structure` | space station | 7 | form, subkind, material, primary_color, scale, emitters, condition |
| `wreck` | wreck | 6 | form, subkind, material, condition, primary_color, emitters |
| `object` | alien artifact | 6 | form, subkind, material, primary_color, scale, surface_detail, aperture |
| `phenomenon` | star/black hole/nebula/energy being/gaseous drifter | 5 | form, subkind, primary_color, emitters, appendages |
| `_default` | a foreign kind | 8 | form, subkind, material, primary_color, scale |

Every priority opens with the silhouette, the name, the substance and the
colour - the four things a t2i model can actually place. What differs after
those four is what that class of thing *is*: a creature spends the rest on
anatomy, a world on ring arcs and one emitter, a station and a craft on scale
and one emitter, a wreck on condition, an artifact on surface_detail.
`armament`, `markings`, `accent_color` and `extras` fall to the tail for the
built and inert archetypes deliberately: they are the greebles the corpus shows
a model cannot place.

**The Scene Entity node is budgeted too**, at ``allowance_for(1, 1)`` capped by
the archetype, so its own preview is exactly what the entity contributes to a
one-entity scene. It used to pass ``budget=None`` and speak all sixteen heads,
disagreeing with every wired result.

### Trait conflicts

Some contradictions are between two *values*, not two fields. ``VALUE_TRAITS``
tags a value with the traits it asserts (``self-coloured``, ``frost-bound``,
``states-a-colour``, ``already-ruined``, ...) and ``TRAIT_CONFLICTS`` lists the
pairs that cannot both hold. A module-private expander turns each pair into
ordinary multi-value exclusion rules, so the engine never learns what a trait is.

To add a trait: tag the values that carry it in ``VALUE_TRAITS[field]``, then add
the conflicting pair to ``TRAIT_CONFLICTS``. The field a trait lives on is
inferred from the table, so a trait added to a second field is covered
automatically. Direction matters: the trigger stands and the target gives way
(a material outranks a colour; a subkind outranks a condition). A foreign value
carries no trait, so no rule fires on it - correct and intended.


### The genre frame, and the category noun

Every noun in "a large battle-scarred warship with a hammerhead prow hull" is
also a naval noun, and the word `vessel` was **never spoken** - `HeadPhrase.noun`
is a generality ladder and a specific `subkind` suppresses the generic `kind` it
implies. Rendered through Krea-2, that prompt reliably drew a WWII battleship
hull flying through a cave.

Two fixes, both cheap. `HeadPhrase.apposition` names the category the ladder
suppressed ("a large battle-scarred warship, a starship, ..." - set off on
both sides, so it carries a trailing comma), declared per archetype so a
self-naming subkind like "neutron star" does not restate itself.
And `ProseSpec.environment_sentence` carries a genre frame. It is a *frame*, not
appended scenery: a genre written as a trailing noun phrase reads as one more
thing in the scene, which is the failure recorded in
`t2i-prose-needs-a-rendering-frame`.

## Environment bands

`ENVIRONMENT_BANDS` grouped the environment pool into five coarse places from
the day it was authored, and nothing read it. Every scene drew its environment,
its entities and their situations independently:

> ...set in a domed colony concourse. A massive corroded submersible ... It is
> taking hits from a ridge line.

Three legal draws that cannot all be true. `GenrePack.environment_bands`
promotes the table to the contract, and `ConstraintRule.values` lets one rule
name a whole band instead of twenty near-identical rules - twenty chances to
edit nineteen of them.

**Only exceptions are authored.** A situation plausible anywhere appears in no
list, so adding one costs nothing unless it needs ground under it, open space
around it, a roof over it, or a dock to happen at.

**A band class is not only "where the scene is" but "what the scene
affords".** `_BANDS_NO_FLOOR` is a nest's requirement - a floor, rock or deck
plate, it does not care which - and `_FLOOR_BOUND` names the two actions that
need one, so a creature no longer broods over eggs in open orbit. The same
idea gives the surface-vehicle groups their own action pools: `flying` has no
tracks, no winching and no trailer, `underwater` no dust or dunes, `hovering`
and `legged` keep only what they can do, and `wheeled/tracked` is declared
explicitly so the fall-through is not load-bearing. A `small drone` gets the
same treatment. An action is excluded by the affordance it needs, not by a list
of places it is wrong.

**A deposit condition needs a place that could deposit it.** `ice-encrusted`,
`dust-caked` and `overgrown` are gated by `_CONDITION_PLACE_RULES` to the
environments that can produce ice, dust or growth. Cold cuts across bands, so
those rules are keyed on a set of environment *values* and its complement
rather than on bands. Freeing an ice draw in a lava field hands it `scorched`
or `corroded`, which increases variety by construction rather than by culling,
and the condition pools were widened with values that are neither ice nor dust
(`sun-bleached`, `vacuum-pitted`, `radiation-stained`, ...).

**A world seen from the ground has no sky to hang in.** The pack describes an
entity but never *places* it, so `celestial body` is removed from the
`planetary surface` kind pool: otherwise a moon is generated as the subject of
a ground-level scene and the model puts it on the sand. `celestial body` is out
of the `orbit` band too: with the camera already at a world, "an eroded rocky
planet in an orbital debris belt" read as a world set on the ground, the same
failure one level up. A world stays the subject in deep space and a cloud
layer, where it is legitimately the backdrop. This is a decision, not an
omission - bringing it back needs a placement concept the pack does not have.

**A world is drawn only against a clear view.** Round X added the `vista`
affordance - a clear view with no field of rubble to set a world on - and gave
every solid world, gas giant and ring system a need for `deep-space` and
`vista`, so a world is never set down inside an asteroid, comet or wreck field.
Their actions are whole-disc events seen from space; close-up geology belongs to
asteroids and comets, which is why the two carry different situation families.

**An enclosed place carries its own keys.** The caverns, the trench and the
colony street have their own `kind` and `context` pools, so a starship is never
offered inside an ice cavern and a cavern never shows a horizon or a sky. A
surface place says which world it is on through its `spoken` form, which is
scenery rather than a placed entity.

Two consequences worth knowing:

- The environment is drawn first and now *chooses* the kinds: `kind` scopes on
  `environment` and its pool is keyed by band, so a scene is coherent by
  construction rather than by rejection. The kind-excluding band rules are
  gone; the situation bands remain, because environment-to-action is a
  different axis.
- A band is one place to a rule and can be two to a viewer. `interior` holds
  both a hangar deck and a cockpit, so `_TIGHT_INTERIORS` names the rooms with
  no space for a vessel rather than splitting the band and making every rule
  written against "interior" ambiguous.

### A rule that re-draws a kind must re-scope the slot

`kind` scopes every other pool, so a rule that re-draws it invalidates
everything already drawn under the old one. Before `_rescope_slot`, the bands
produced a celestial body whose subkind was "sand crawler", with a low skimmer
hull and a rear ramp - every field individually legal, none legal together. The
same hazard runs the other way: `kind` is drawn *first*, so a value locked on a
kind-scoped field has not been consulted yet, and locking "Type: warship" could
return kind "alien artifact". Both directions are closed, and both are
genre-blind - they read the pools rather than knowing what any of them mean.

## The two denylists

Stylebook's rule is *a style describes the rendering, not the subject*.
SceneWeaver's is its exact inverse. The line is drawn **between** them, not
around colour - a blanket ban on colour terms would make hull livery and engine
glow inexpressible, which is the specific mistake this pack was rewritten to
avoid.

| Allowed - subject-intrinsic | Banned - rendering |
|---|---|
| hull / skin / integument colour | palette, colour grade, teal-and-orange, bleach bypass, duotone, sepia, monochrome, desaturated, contrast, vignette |
| markings, livery, patterning | lighting colour and direction: "lit by", backlit, rim / key / fill / ambient light, god rays, spotlight, silhouetted, illuminated |
| emissive colour ("cyan exhaust plumes", "violet bioluminescence") | time of day: golden hour, blue hour, sunrise, sunset, dawn, dusk, twilight, midday, midnight, daylight |
| material and finish as a property ("pitted", "polished") | atmosphere, atmospheric, volumetric, haze, fog, mist, smog, bokeh |
| shape, silhouette, body plan | medium, artist, era, film stock: photograph, painting, concept art, octane, unreal engine, artstation, masterpiece, cinematic, film grain, 35mm, 8k |
| scale, condition, count | framing, shot type, lens, depth of field, composition: close-up, wide shot, establishing shot, rule of thirds, anamorphic, fisheye, telephoto, camera, low angle, dutch angle |

The vocabulary lives once, in `tests/boundary.py`, so the suite and the validator
cannot diverge - two copies of a denylist means one of them is stale and nobody
knows which. Rendering terms are matched two ways: as **substrings** where the
term is a phrase ("teal and orange" must be caught however it is spaced), and on
a **word boundary** where the substring form appears innocently in English
(banning `shot` as a substring would reject "buckshot"; banning `panel` would
reject "panelling").

**Both directions are asserted, and that is the point.** A denylist nobody has
watched reject anything is a claim. `RENDERING_PROBES` are planted values that
*must* be caught; `SUBJECT_PROBES` - `crimson hull`, `oxide red`, `cyan exhaust
plumes`, `titanium alloy`, `pitted and scarred` - *must* survive. A denylist that
quietly banned every colour word would pass just as green as a correct one
without the second list.

Both run over **every pool value** and over **generated `prompt_text` across a
seed sweep**, because a rendering term can appear by
composition even when no single pool value contains one.

A third rule rides along in the same scanner because it is checked over the same
corpus: **never negate**. Absence is expressed by naming what *is* there - "a
smooth sensory dome where a face would be", never "no eyes". Identity Forge's
mole drew ears from "no visible ears".

## Content tags

The vocabulary is frozen at three values: `neutral`, `peaceful_only`,
`conflict_only`. Exactly one sits on every value in **`situation`, `relation`,
`armament`, `aperture` and `subkind`** - and on nothing else. `environment`,
`condition`, `scale`, `material`, `form` and the colours are deliberately
untagged: the filter does not touch them.

`scene_filter` maps to a set of admissible tags and masks the pools before any
draw:

| `scene_filter` | Tags drawn |
|---|---|
| `Any` | all three |
| `Peaceful` | `neutral`, `peaceful_only` |
| `Conflict` | `neutral`, `conflict_only` |

The subtlety that makes it correct: `armament` is a tagged pool, so a `Peaceful`
scene draws a ship with **no weapons described** - not one described as unarmed.
Absence by omission, never by negation. A filter never *forces* a value; it only
masks pools. A locked conflict value under `Peaceful` survives, with a warning in
`_meta.warnings`, because a lock is an explicit request.

## The detail budget

**Detail is a whole-scene quantity, not a per-slot one.** `ALLOWANCE_BY_COUNT`
says how many optional descriptive fields each occupied slot keeps, given how
many are occupied:

| Entities | Allowance per slot |
|---|---|
| 1 | 9 |
| 2 | 8, 6 |
| 3 | 7, 5, 5 |
| 4 | 6, 5, 4, 4 |

The old model gave slot 1 a fixed nine and halved it for the rest, so a scene
got *more* total description the more subjects it had - exactly backwards. An
image has one subject's worth of attention to spend however many things are in
it, so the allowance falls as the scene fills. Nothing is ever reduced to a bare
name: the smallest allowance is still four details, which is what keeps wiring a
Scene Entity into any slot worth doing.

**Nine is not a token-count decision.** A one-entity scene at nine fields is
about 85 tokens, nowhere near the 320-token ceiling. It is a *sentence*
decision: nine details across the sentence patterns is four readable sentences,
where the same nine in one clause pile was the incoherence this overhaul exists
to fix. Cutting the count further was tried and cost real things - `scale` and
`condition` fell off the priority list, taking the kaiju path and half the
visual variety with them. **Shape, not length, is what a prose encoder chokes
on.**

`TOKEN_CEILING` is 320, raised from 256. The old number came from CLIP, which
holds 77 tokens per chunk and drops detail long before the end of a long one; a
modern prose encoder reads several hundred comfortably, and the multi-sentence
grammar deliberately spends tokens on connectives that make the prompt
parseable. It is a **regression guard, not a target**: the widest scene the node
can build measures about 149.

Five rules, and they are what make the budget honest rather than a truncation:

1. **An archetype's `omits` go first.** A field this kind of thing does not have
   is not a budget question.
2. **A locked field is always rendered** and is never cut. Locking is an
   explicit statement of intent.
3. **A field with a widget on this slot is spent before one without.** A
   supporting slot shows four dropdowns and resolves twenty-one fields; without
   this its `scale` widget competes with fifteen fields the user cannot see,
   loses every time, and is drawn every render and never voiced.
4. **A slot with a wired Scene Entity is promoted to the top allowance** - what
   slot 1 gets for the current count. Wiring a node in *is* the request for
   detail. It is a promotion, never an exemption: four uncapped wired entities
   measure ~320 tokens, which is the mush this module exists to prevent.
5. **A field the budget cuts is `null` in `prompt_json` too** - never "resolved
   but not voiced". A value drawn and silently discarded promises the image a
   detail it was never asked for.

### How many entities, and what a slot is worth

Four slots, and every occupied one is described. A supporting slot has fewer
**widgets**, not fewer fields: it used to resolve every widgetless field to
`None`, so an unwired slot 2 read "A large arachnoid." and nothing more, and
wiring a Scene Entity was the only way to get a second described subject.
`build_resolution_definitions` is the split - what a scene *contains* versus
what the node face *shows*.

The `Entities` control is the authority on occupancy, and it **clamps rather
than commands**: it empties slots past it, but within it a slot is whatever its
own widget says, so a slot deliberately set to None stays empty and a
pure-setting scene is still expressible. A locked kind or a wire occupies its
slot regardless - naming a subject is more specific than saying how many there
are.

## Distribution baseline

**Bias is measured, not assumed.** Identity Forge discovered that 13.7% of its
default male renders were carrying a handbag only by sweeping a thousand seeds -
no test failed, no pool looked wrong, and every individual draw was legal. A
distribution defect has no single-scene symptom, so it needs a measurement rather
than a rule.

Reproduce, and re-run after **any** pool change:

```
python scripts/sample_distribution.py --seeds 1000
```

The script exits non-zero when a ceiling is breached, and
`tests/test_distribution.py` gates the same ceilings on a narrower sweep so a
regression fails the suite rather than waiting for someone to run the script.

### Baseline - 1000 seeds, `scene_filter=Any`, every slot occupied

| Measure | Ceiling | Measured |
|---|---|---|
| Largest single `kind` share of occupied slots | 20% | 19.7% (`alien creature`) |
| Smallest single `kind` share | - | 2.7% (`celestial body`) |
| `colossal` + `planetary` share of drawn `scale` | 10% | 6.2% |
| `scale` extremes on a flat draw, for comparison | - | 50.0% |
| Widest scene (four entities), `prompt_text` tokens | 320 | 149 |

**`celestial body` is deliberately the outlier.** A world is drawn only where the
place affords `deep-space` and `vista`, so it reaches the deep-space band alone;
`surface vehicle` is next, excluded from deep space and orbit by the band-scoped
kind pool. Both are minimums, so nothing fails.

### Motif baseline

A motif is a word family whose share is measured across the WHOLE prompt
(`GenrePack.motifs`), because a bias spread across five fields is invisible to a
per-value check: `ice-encrusted` in the conditions, three ices in the materials,
frost in the surface details, five cold environments and four white colours are
each unremarkable, and together they put ice in a quarter of output. Measured
over 1000 seeds with every slot occupied:

| motif | substrings | share |
|---|---|---|
| `heat` | scorch, molten, lava, ember, flame, soot, burn | 63.8% |
| `dust` | dust, sand, regolith, grit, ash | 45.6% |
| `rust` | rust, oxidis, corrod, verdigris, patina | 40.1% |
| `ice` | ice, frost, glacier, cryo, rime, polar, arctic | 23.1% |
| `growth` | fungal, fungus, overgrown, spore, flora, moss, bark | 18.6% |
| `ring` | ring | 14.1% |

Round XII re-measured this table. `growth` fell because the context flora was
renamed off the Earth words (`grove of chitin-plated fan-spires`), and `ring`
rose because more of a world's tail is drawn; both are inside the ceilings,
which were not changed.

The ceiling is calibrated to this baseline rather than to the 0.25 the plan
started at. `heat` is woven through twelve fields - `scorched` and
`soot-blackened` sit in every condition pool, `molten` and `lava` in materials,
emitters and markings, four situations - so pulling it under 0.25 would mean
culling, which the pack forbids. The ceiling is baseline plus headroom and acts
as a regression gate; a future session that widens the pools can lower it. Each
substring is matched at a WORD START, so `ice` does not fire on `service` and
`ash` not on `crash`.

### Which fields are voiced

There is no single number any more, and the tail is not dead. Two mechanisms
decide what reaches the prompt:

- **The allowance falls as the scene fills** (`ALLOWANCE_BY_COUNT`), so a
  four-entity scene describes each subject with fewer clauses than a one-entity
  scene. That is the budget trading breadth for coherence, not a defect.
- **The archetype's tail rotates.** `detail_cap` bounds how much a class of
  thing speaks, and `detail_rotation_slots` reserves one or two of those slots
  for a weighted draw from `detail_rotation`. A fixed priority spent the
  allowance in the same order on every render, so every field below the line was
  drawn, resolved, written into `prompt_json` and never spoken -- a dead widget.
  With the rotation a batch shows all of them and one frame stays coherent. The
  draw is offered only on a slot that speaks at full depth: a brief supporting
  slot's allowance belongs to the silhouette, not to a random detail.

The gate is `tests/test_dead_widgets.py`: for every kind whose archetype
rotates, every clause-head field that kind shows and does not omit is non-`None`
in the payload on some seed, and the Scene Weaver's budgeted head is voiced on
some seed. A world is not exempt: it rotates its tail like every other
archetype (decision D12), so its world-scale features are drawn and spoken.

`detail_priority` is still what decides the core order, and it is tuned rather
than chosen by taste: `condition` and `scale` sit above the component fields
because they are single words with outsized effect.

### Per-value skew

The script flags any value taking more than 2.5x the uniform share of the values
actually drawn for its field. Five values are flagged at the baseline:
`whip tail` (creature appendages), `arc discharge coil` (emitter), `spherical
drone body` (form), `optic stalk` (sensors) and `welding a seam along a hull
plate` (situation).

**A flag is a question, not a failure.** Each of these is reachable from more
kinds, or from a smaller drawn set, than its neighbours - `accent_color` is
voiced on 1% of slots at four entities, so a handful of draws dominate its own
tiny sample. The check exists so that a value which becomes over-represented for
some *other* reason - a pool that shrank, a constraint that stopped firing - is
visible the next time the sweep runs. Read a new name here as something to look
at; the names above are not pinned, because pinning them would turn every pool
edit into a doc chore.

### Token length

Measured by `engine.budget.count_tokens`, an approximation biased high on
purpose: it is only ever compared against a ceiling, and an under-count would
let a real overrun through.

| Entities | Longest `prompt_text` over 400 seeds |
|---|---|
| 1 | 77 |
| 2 | 109 |
| 3 | 134 |
| 4 | 149 |

`TOKEN_CEILING` is 320 and `tests/test_engine.py` asserts it across a seed
sweep, including the worst case of four Scene Entities wired into every slot.
The headroom is deliberate: length was never what made the output unusable, and
the multi-sentence grammar spends tokens on connectives that earn their place.
Re-run `python scripts/sample_distribution.py --seeds 1000` after any pool
change and confirm the live numbers.

### Shape, per archetype

`python scripts/coherence_audit.py --seeds 2000` reports, per archetype: mean
and p95 optional clause heads spoken, mean and p95 `count_tokens` of the
entity's own sentences, the share that speak an action, and the share that speak
four or more component clauses in one sentence. The last number is the one that
separated the GOOD and BAD buckets of the reference corpus; it should sit near
zero for `structure`, `object`, `wreck` and `world`.

One representative prompt per archetype (the seed varies):

- **craft** (starship, seed 2) - A science fiction scene set in an accretion disc of a black hole. A mid-sized under construction warship, a starship, is trailing fire from a ruptured fuel line. It has a whale-bodied hull, clad in deep navy ferro-ceramic sheathed plate. It shows a pair of ember orange warp coil rings.
- **creature** (alien creature, seed 3) - A science fiction scene set in an ionospheric charge layer. A small soot-blackened helical ribbon body, an alien creature, is moulting a translucent husk. It is a void grazer, covered in bone white self-annealing resin. It has six spindly legs, eight gripping fangs, four pinhole eyes and a mane of filaments. It shows a sieve-plated feeding slit.
- **figure** (spacefarer, seed 13) - A science fiction scene set in an orange sand dune sea. A mid-sized soot-blackened medic, a spacefarer, is signalling a landing craft with a hand lamp. They have a compact wiry frame and wear umber aged canvas. They are marked with shoulder hazard striping and ink blue accents. They carry a single grenade bandolier.
- **machine** (robot or mech, seed 9) - A science fiction scene set in a cryogenic stasis bay. A small soot-blackened android is lifting a cargo container overhead. It has a humanoid android frame, plated in pewter carbon fibre shell. It carries eight chain blades and a single targeting monocle.
- **object** (alien artifact, seed 0) - A science fiction scene set in a domed colony concourse. A small half-disassembled monolith, an alien artifact, is hanging unsupported above the ground. It is a tapering obelisk, cut from polished obsidian. It shows crystalline inclusions.
- **phenomenon** (celestial body, seed 6) - A science fiction scene set in a galactic core star swarm. A hull grey oblate sphere, a neutron star, is projecting a beam from its pole. It shows a ring of solar wind tails and a fan of sulphur yellow coronal discharge arcs.
- **structure** (space station, seed 1) - A science fiction scene set in a geosynchronous orbital lane. A small newly repainted research outpost, a space station, is swinging a cargo cradle out over open space. It is built as paired modules on a long truss boom, clad in umber cast basalt armour tile. It shows four cyan signal mast beacons.
- **world** (celestial body, seed 10) - A science fiction scene set in a globular star cluster. A large scorched ring system is venting geysers along a fracture line. It is a shattered fragment cluster with a crust of titanium white water ice. It shows six ring arcs and three molten gold lava fissures.
- **wreck** (wreck, seed 4) - A science fiction scene set in an ionospheric charge layer. A large radiation-stained burnt-out star cruiser, a wreck, is sheltering a nest of scavengers. It is a split-open pressure hull, clad in bone white delaminated composite.

The built and inert archetypes now read like the reference corpus's tracked
hauler: one subject, its substance and colour, one or two features, one visible
action.

## Decisions recorded here

### `markings` ships no readable text in v1

No `markings` value names lettering, numerals, registry codes, insignia text or
a nameplate. Diffusion models garble text, and the base negative prompt most
users run actively fights it, so a value that asks for painted numerals spends
tokens to make the image worse. `tests/validate_data.py` enforces it against a
vocabulary of text words, and `tests/test_boundary.py` plants
`registry lettering` to prove the check fires. This is a **decision**, not a gap:
revisit it only if the target models stop garbling text.

### Two fields may share one vocabulary, and the pack has to say so

`primary_color`, `accent_color` and `emitter_color` draw from one palette of
pigment words - a hull, its trim and its exhaust are three *roles* over one
vocabulary, and forcing them apart would mean inventing a second word for
copper. Everywhere else, a value shared by two clause-heading fields lets one
entity draw the same string twice ("an oxide red hull, oxide red accents"), so
`tests/validate_data.py` reports it. `GenrePack.shared_vocabulary` is the
declaration that distinguishes the two cases, and `engine.scene` still silences
an exact repeat at run time in case a draw lands one anyway.

### The pack directory must be named `comfyui-sceneweaver` for `pytest` to work

`python -m unittest discover -s tests -t . -v` works under any directory name
and is the documented command and the CI entry point. `pytest tests` also works
- but only when the pack directory's name is **not** a legal Python identifier.

pytest resolves the root `conftest.py`'s module name through the package chain,
walking up for as long as it finds an `__init__.py`. The repo root has one,
because it is a ComfyUI pack. So when the directory is also identifier-safe,
pytest imports the root package - running the entrypoint and its
`from comfy_api.latest import ...` - *before* it imports `conftest.py`, and the
`comfy_api` stub is never registered:

```
git clone <url> comfyui-sceneweaver && pytest tests   # exits 0
git clone <url> sceneweaver         && pytest tests   # exits 4
```

`--import-mode=importlib` does not change it. `pythonpath = ["tests/comfy_stub"]`
in `pyproject.toml` does, but it puts the stub ahead of a real installed
`comfy_api` on exactly the machines that have ComfyUI, which throws away the
real-first property the harness exists to preserve. Left as a documented
constraint: `git clone` uses the repo name, and ComfyUI installs a custom node
under it, so nothing in normal use produces the failing name.


### A place says what it offers; a form says what it can do

The affordance vocabulary alone could not stop a torus standing on its ring:
the place was legal (`ground`) and the shape was legal (`torus`), and only the
pairing was wrong. `value_stances` / `place_stances` are the second axis, and
the rule they compile to excludes a form from every place that supports none of
its stances. The same rule is why a walker no longer hangs in vacuum and a
submersible no longer appears in an armoury.

The count cap on a figure is a data decision, not a new mechanism: its
`armament` and `sensors` count pools each stop at "a single", so two hands
cannot be filled with four objects. A kind-scoped count key cannot express it
because a group key precedes a kind key in the scope chain.

### Round X decisions

- **D2** A suited person and a drone float in vacuum; a station hovers in a
  cloud deck; a wreck falls through air. Stances are declared form by form, so a
  tracked chassis cannot walk and a hover disc cannot stand in vacuum.
- **D3** Worlds, gas giants and ring systems are drawn only against a clear view
  (`vista`), never inside an asteroid, comet or wreck field. Their actions are
  whole-disc events; close-up geology belongs to asteroids and comets.
- **D7** A surface place names a visible alien sky feature and an interior says
  whose it is, through `spoken` forms; the dropdown tokens stay.
- **D8** A person in vacuum or underwater wears a sealed helmet. The sealed
  garments say their helmet in `spoken`, the open ones need `air`, and a face
  condition or an open aperture needs it too. The helmet visor left the sensor
  pool: a helmet is worn, never carried.
- **D9** An Earth-shaped hull stays in open space. A crescent wing in a blue sky
  is an airliner whatever the qualifier says, so the winged, prowed and
  boat-hulled forms need `open-space`, and the atmosphere gets silhouettes of its
  own (gravlift hulls, a lander spire, a teardrop). Renaming alone does not work:
  the model's prior wins over the qualifier.
- **D10** The detail tail rotates; see "Which fields are voiced".
  whose it is, through `spoken` forms; the dropdown tokens stay.

## Concern audit (round X)

`scripts/concern_audit.py` sweeps the wired path (a Scene Entity in slot 1) or the
Scene Weaver alone, and counts the defect classes a user reported, using the
**frozen** definitions in `scripts/concern_flags.py`. `--gate` exits non-zero if a
structural class is present. `scripts/replay_batch.py` reads each image's `prompt`
chunk, re-runs the exact scene and prints the resolved place/subject/action with
its flags, so a batch of images becomes named defects. Do not edit the flags to
make a task pass.

Baseline at the start of round X (1500 wired scenes): 52.9% carried a structural
flag. After the round: 0.1%. The remaining share is `info-claw-*`, which is
reported and never gated.

### Round X, measured

| measure | before (HEAD `a11622d`) | after |
|---|---|---|
| wired scenes with any concern flag | 52.9% | 0.1% |
| unwired scenes with any concern flag | 52.8% | 0.3% |
| silhouette dropped (`noform`), wired | 12.5% | 0 |
| Earth nouns in the prompt, wired | 14.4% | 0 |
| claws in robot armament (`info-claw-robot or mech-armament`) | 2.7% | 0 |
| wired type kept from the Entity node | 91.3% | 100.0% |
| situations with an explicit need entry | 33% | 100% |

Measured with `scripts/concern_audit.py --seeds 1500` on both paths (the gate exits
0 on each), `tests/test_wired_placement.py` for the type/form retention, and
`data.genre.is_classified` over `pool_options(pack, "situation")` for the need
coverage. The 0.1%/0.3% that remains is `info-claw-*`, reported and never gated.

## Concern audit (round XI)

Round X's instrument catches structural illegality -- a thing where it cannot
stand, an action its body cannot take. The 914 batch showed a second class: legal
draws whose *words* a model renders as the wrong object. A tether becomes a
chain, a bladder-pod a balloon, a starliner an airliner. Those definitions live
in `scripts/concern_flags_0914.py`, frozen the same way, and `concern_audit.py`
reports the union of both sets while `--gate` checks the union.

The lesson that produced the second instrument is a rule now: **a word is judged
by what a model draws, not by what it means.** A tether, a bladder, a drum, an
egg and a bone are all correct English for the sci-fi thing and all render as
the Earth object, so the value is renamed or the need is declared. The
foreign-noun denylist grew by that list, and `SPOKEN` is where a sealed garment
says its helmet.

### Round XI, measured

| measure | before | after |
|---|---|---|
| wired scenes with any concern flag | 32.3% | 0.0% |
| unwired scenes with any concern flag | 30.1% | 0.0% |
| the 914 batch caught by the round-X flags | 0 | -- |
| the 914 batch caught by the round-XI flags | 29 | 0 |
| values no subject can draw (`SHADOWED`) | check not live | 0 |

`scripts/replay_batch.py` over the 914 batch now reports `MISMATCH` for the
replayed rows, which is expected -- the engine changed on purpose, so the
recorded prompt no longer replays -- and reports no round-XI flag on any
re-generated scene. Measured with `python scripts/concern_audit.py --seeds 1500`
on both paths; the remainder is `info-claw-*`, reported and never gated.
## Concern audit (round XII)

The 915 batch showed a third class, and it is not about vocabulary or legality:
the subject is legal, the place is legal, and the **part does not fit the body
it is bolted to** -- a drop pod with a spare track, a submersible with mine
ploughs, a survey drone with three plasma cutters. The definitions live in
`scripts/concern_flags_0915.py`, frozen the same way; `concern_audit.py`
reports the union of all three sets and `--gate` checks the union.

The lesson that produced the third instrument is a rule now: **a part must fit
the body it is bolted to.** A rotating tail voices pools nobody checked, and a
pool keyed by *kind* carries no body check, because it was never spoken before.
Two mechanisms close it, and they are not interchangeable:

* `GenrePack.part_keywords` / `part_lint_fields` and check 29 (`PARTFIT`) in
  `tests/validate_data.py`: a value that names a body structure (a track, a leg,
  a jet) is drawn only by a body that declares that feature. The part lint is
  separate from the body lint on purpose -- a *situation* such as "throwing a
  track at speed" is legal for a tracked body and excluded at runtime by the
  stance check, while a *part* is bolted on with no such escape.
* `VALUE_TRAITS` / `TRAIT_CONFLICTS`: `legless-plan` against `leg-appendage`,
  so a tracked chassis grows no crawler leg even where the lint cannot see it.

**A place that floats says so.** `ProseSpec.environment_staging` is an ordered
list of `(affordance, suffix)` pairs; the first pair the environment affords
appends its suffix to the setting sentence ("Set in an orbital debris belt, out
in open space."). A text-to-image model grounds anything it is not told floats,
so a station in a debris belt was drawn standing on the debris. The suffix is
declared once per genre, and the pack's validation rejects a pair naming an
affordance no place offers.

**A value nobody draws is dead.** `check_shadowed_values` proves a value is
*reachable* -- some subject's scope chain resolves the key it is authored under.
Reachable is not drawn. `scripts/reach_audit.py` sweeps real scenes on both
paths, counts every non-`None` value of every head field, and reports the ones
that never came up. A value is exempt when it is stranger vocabulary (authored
under `_default` alone) or when every archetype of every subject whose resolved
pool holds it lists the field in `omits`. There is no allowlist: a never-drawn
value is fixed by scoping, needs, or replacement. `--gate` is for CI.

### Round XII decisions

* **D11** A wired Scene Entity whose `kind` is `None` counts as *not wired*: the
  Weaver slot draws its own subject, and the readout carries
  `slot N's wired entity has no kind, so slot N draws its own subject`. Without
  it the scene was environment-only and the slot was described as nothing.
* **D12** A world rotates its tail like every other archetype, and the rotating
  slot is limited to features that read from space. A small-scale terrain
  feature (a lava tube opening, a dune ripple, a boulder field) leaves the world
  pools; a world-scale one (a storm oval, an ice cap, a crater row) is drawn.
* **D13** A non-combat robot, vehicle or crew member carries **no** armament.
  Every machine, vessel and crew weapon is `military-weapon`, so a
  `civilian-hull` or a `civil-role` excludes the whole pool and the field
  resolves to nothing -- the prose never says "unarmed". Tool arms become
  appendages whose names do not render as blades.
* **D14** A secondary actor in a non-person situation is a **machine, not a
  crowd**: a wreck is examined by a hovering survey drone, not by a survey team.
  A small crew stays only in interiors and in a spacefarer's own situations.
* **D15** Humanoid alien people are a subkind group under `spacefarer`, with
  their own forms, garments and faces. The word "alien" is in the spoken form,
  so a model draws the face and the frame rather than a human in a suit; a
  polymer soft-suit keeps a clear bubble helmet, so the face survives vacuum.

### Round XII, measured

| measure | before | after |
|---|---|---|
| wired scenes with any structural concern flag | 69.1% | 0.0% |
| unwired scenes with any structural concern flag | 71.1% | 0.0% |
| the 915 batch caught by the round-XII flags | 124/171 | 0 |
| values never drawn (`reach_audit --gate`) | 23 situations, 13 creature emitters, 12 world extras, 20 world markings | 0 |
| values no subject can draw (`SHADOWED`) | 0 | 0 |

`scripts/replay_batch.py` over the 915 batch reports `MISMATCH` for 169 of 171
rows (expected -- the engine changed on purpose) and four rows still carry
`earth-creature-or-flora`. In all four the flagged word comes from a value the
recorded workflow had **locked** (`context = "procession of gliding
sail-creatures"`), which the engine keeps and reports rather than overrules; no
scene drawn from the pack's own pools carries the class.

Measured with `python scripts/concern_audit.py --seeds 1500` on both paths and
`python scripts/reach_audit.py --seeds 12000 --path both`; the remainder is
`info-claw-*` and `info-fire-situation`, reported and never gated.

## Concern audit (round XIV)

The 916 batch was replayed byte-for-byte from `main` (all 32 prompts matched) and
every frozen `concern_flags*` list read 0 of 32. The defects were relationships
between fields that each read fine alone, so the round started by adding
*shape* classes to `scripts/coherence_sweep.py` and measuring them, then wrote the
frozen list `scripts/concern_flags_0916.py` for regression.

### Round XIV decisions

* **D16 A dead ship is the `wreck` kind.** `abandoned`, `derelict`, `crashed` and
  `breached` left the made-thing condition pool; they bought "a crashed colony
  ship riding a re-entry sheath in orbit". Every wreck subkind carries `inactive`.
* **D17 Liveness is a closed list.** `DORMANT_ACTS` in the pack names what a thing
  with no power, crew or intent can be doing; every other situation is derived
  `powered-act`. The two hand-kept `powered-act` lists it replaced silently
  passed every act nobody remembered to tag. A new situation is live until it is
  declared dormant, so the safe default is the one that needs no memory.
* **D18 A dead thing shows no light.** Every emitter value is derived `emissive`
  and conflicts with `inactive`; the wreck archetype `omits` emitters outright.
  The validator's part and body lints skip a subject whose archetype omits the
  field (`_reach(..., honour_omits=True)`); the shadowed-value check does not.
* **D19 A craft is prey only for something big, outside.** `craft-prey` conflicts
  with `small-scale` and with `interior-place` (derived from the interior band);
  `outer-hull-act` (a creature crossing a hull) conflicts with both too.
* **D20 One thrust source.** `plume-act` (an act that describes its own exhaust)
  stands and an `exhaust-emitter` gives way, so the emitter draws a light.
* **D21 A context framing names where, never how.** The context sentences carry no
  stance verb, and validator check 31 (`CONTEXTSTANCE`) fails one that does.
* **D22 No open fire, no uncaused breakage.** Combustion acts left the pack except
  atmospheric re-entry and a wreck burning as it falls through a cloud deck; a
  machine no longer loses a limb or sparks apart with nothing in the frame.
* **D23 Variety is kept by adding.** Every pool a rule thinned was measured against
  `main` (distinct values and entropy per field and per kind) and given legible
  replacements rather than a relaxed floor.
* **D24 A pool is a literal.** Additions are named tuples declared before
  `SITUATION_POOLS` and concatenated inside it, because `scripts/builtin_options.py`
  resolves pools with `ast` and cannot see a later subscript assignment.

### Round XIV, measured

| measure | before | after |
|---|---|---|
| wired scenes with any sweep class (`coherence_sweep.py`) | 50.0% | 5.4% |
| unwired scenes with any sweep class | 49.7% | 5.0% |
| context sentence imposes a stance verb | 26.7% | 0 |
| a dead thing lit or acting | 19.0% | 0.1% |
| the 916 batch caught by `concern_flags_0916.py` (same seeds replayed) | 28/32 | 0/32 |
| distinct prompts in the variety comparison | unchanged | unchanged |

`reach_audit.py --gate` reports a few rare-but-feasible situations as never drawn
on **both** `main` and this round (a drone at a trench vent, a station at a
scaffold): the audit samples, and a value confined to a rare place and a rare kind
can miss a 12000-scene run. It is a maintainer instrument, not a CI gate.
