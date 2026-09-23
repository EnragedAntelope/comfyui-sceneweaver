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

## The fantasy pack (0.5.0)

`data/fantasy.py` is the second genre and the first real test of the seam: it
needed one data module, two registration lines in `__init__.py`, a `"fantasy"`
section in `user_options.json`, and a `--pack` option on two maintainer
scripts. Nothing under `engine/` or `nodes/` changed, and the frontend decorates
the new nodes from the same route payload.

It keeps the sci-fi field keys and their widget order, so an entity of either
genre fills a slot in the other; only `LABELS` differ.

### Decisions

* **F1 Situations are authored in buckets.** A bucket is one tuple whose values
  share a tier, a filter tag, the place they need, the stance they take, and
  whether a dormant or a sleeping thing can be doing them. `_BUCKETS` derives
  `SITUATION_TIERS`, the tags, `value_needs`, `value_stances`, `DORMANT_ACTS`,
  `SLEEP_ACTS`, `powered-act`, `waking-act` and `violent-act`. A situation is
  declared once, and the module refuses to import one with no bucket. Pools
  concatenate buckets as literals, so the ast option reader still sees them.
* **F2 Two closed liveness lists.** A petrified, ruined, wrecked or dormant thing
  draws only `DORMANT_ACTS`; a slumbering one only `SLEEP_ACTS`. Every emitter is
  `emissive` and conflicts with `inactive`.
* **F3 Every type has a spoken form.** Check 16 asks each type of an
  apposition-free kind to say its category. A fantasy type almost always names
  itself ("frost troll", "stone golem"), so the pack declares every type as
  itself and overrides only the ones a model draws as something else ("kelpie
  water horse", "brownie hearth sprite", "phoenix firebird").
* **F4 Underwater affords water only.** The sci-fi trench grants `floor`, which
  supports walking; in fantasy that put a cave bear on a coral reef. (Sci-fi keeps
  its seabed floor and blocks rolling there instead -- see R3.)
* **F5 Weapons are neutral under the scene filter.** A knight keeps a sword in a
  Peaceful scene; the filter reads what is *done* (situations, relations).
* **F6 A form never repeats its type's head noun, and a cap is the clause count
  plus two.** Both were found by `scripts/reach_audit.py --pack fantasy`: a
  "square keep" on a "ruined keep" is silenced by the repeat guard, and the two
  head modifiers come off `detail_cap` before the allowance is spent.

### Measured (3000 scenes per path, seeded)

| measure | result |
|---|---|
| validator findings (`python tests/validate_data.py`) | 0 |
| a petrified, ruined or sleeping subject acting | 0 |
| a body placed where its form cannot stand | 0 |
| fire under water, a huge thing indoors, a civilian fighting | 0 |
| anachronism, stance verb, rendering or negation word in the prose | 0 |
| distinct prompts in the variety run | every one |

The seeded sweep that asserts these is `tests/test_fantasy_pack.py`.

## Round XV: the 0916-evening sci-fi and 0917 fantasy batches

Both batches replayed byte-for-byte (`scripts/replay_batch.py` now picks the pack
from each node's class name). The images were read one by one; most defects were
render traps and parts that did not fit the body or the place, and several were
classes the validator could be taught to find.

### Contract and engine decisions

* **R1 A native subject never speaks the stranger's vocabulary.** Validator check
  32 (`FALLTHROUGH`): where most native subjects resolve a key of their own, a
  native subject that falls through to `_default` is a hole. Every fantasy tower
  and shrine "had a single spear"; the fix is a declared empty pool.
* **R2 Nothing a carry sentence names is a body part.** Check 33 (`CARRYPART`):
  "they carry a single hooked talon" drew a harpy holding a talon, and "it carries a
  pair of hydraulic limbs" a robot holding its arms. Made things now *have* their
  parts.
* **R3 A place can block a stance.** `GenrePack.place_stance_blocks`: a body that
  *has* a blocked stance is kept out of the place entirely, in the stance rules and
  in type feasibility (`blocked_stances`, `stances_fit`). A wheeled robot at rest on
  a vent field is still a wheeled robot; removing `floor` instead starved every
  legitimate seabed act.
* **R4 A requirement fills an empty target.** A `require` rule used to be the
  exclusion of its complement, which says nothing to a field left empty by
  omission. `_required_targets` now draws the target from the allowed values
  (without omission) unless the user locked it empty. Fantasy uses it so a stone
  act ("wreathed in creeping ivy") brings the petrified condition with it.
* **R5 A genre names its own filter.** `scene_filter_labels` maps what the node
  shows to Any / Peaceful / Conflict, with `scene_filter_default` and an optional
  tooltip; `canonical_scene_filter` accepts either spelling and `_meta` keeps the
  label. The shipped labels are a compatibility surface like any dropdown value.
* **R6 The scene filter reaches a wired entity's drawn values.** The Scene Entity
  node has no filter, so its random draws passed straight through: a blood-soaked
  corpse reached a "No gore" scene. A drawn tag-scoped value the filter masks is
  re-drawn with its count; a value the user locked, and the kind and type, are
  kept.
* **R7 The readout is cut to the node's width.** Canvas text is not clipped by the
  node body; a long warning ran past its right edge.

### Data decisions

* **R8 Sci-fi:** fleet manoeuvres need the derived `aloft` affordance (open space or
  above the cloud tops), and a grounded starship got landing, lift-off and low-pass
  acts instead of parking in a ruin field "holding formation"; flight acts declare a
  flight stance; every part that stood off the hull on a boom, arm, mast, clamp or
  outrigger left the component pools (solar vanes drew detached panels, outrigger
  pods drew airliner turbofans, cargo cradles hung boxes on cables); drone- and
  pod-prey acts became body-only acts (a drone fused to a snout); contexts that drew
  smokestacks, an airport, pylons or a string of machines were renamed; every moon
  carries a colour or a ring; a rooted growth needs ground and a bell-bodied swimmer
  needs the derived `water`; surface detail joined the part lint.
* **R9 Fantasy:** a giant, a troll, a goblin and a pixie state a measured size
  (weighted to be voiced most of the time; no comparison objects); contexts are keyed
  by place; vessel parts are scoped by sailing ship, flying ship and land vehicle and
  checked against `keel`, `stern` and `sails` features; ships need `navigable` water
  and wheels need `open-ground`; a relic rests on something and a monument is set
  amid something; spirits keep to their domain; bow and blade acts carry weapon-class
  traits; a new thing is never decaying; a plain bear, wolf, boar, turtle or spider
  body was given a silhouette that is not the Earth animal. A later `**{...}` entry in
  a dict literal had silently replaced `inherently-vast` on the kraken, the leviathan
  and the giant sea turtle; traits are now added, never merged by literal.

### Round XV, measured

| measure | before | after |
|---|---|---|
| sci-fi wired scenes with any sweep class (`coherence_sweep.py`) | 5.4% | 5.1% |
| sci-fi unwired scenes with any sweep class | 5.0% | 4.8% |
| repeated sentence leads, 300 scenes (sci-fi / fantasy / horror) | 0 / 183 / -- | 0 / 0 / 0 |
| fantasy giant-kin with no size stated | 76% | 29% |
| fantasy small folk with no size stated | 70% | 22% |
| fantasy distinct contexts drawn (3000 scenes) | 58 | 130 |
| wired "blood-soaked" horror corpses kept under No gore | 382 of 382 | 0 |

Variety was compared against the branch start (`distinct` and Shannon entropy per
field per kind, 3000 scenes per path). Sci-fi gained entropy in all but one field
(starship armament, slightly more often unsaid). Fantasy gained in most; the fields
that lost entropy kept every distinct value and lost it to intended placement --
ships and wagons keep to water and roads, spirits to their domains, and a tower no
longer carries a weapon. The fantasy context and scale omission weights were lowered
so smaller place-keyed pools and type-scoped scale did not simply say less.

## The horror pack (0.5.0)

`data/horror.py` is the third genre, built on the fantasy module's shape: buckets,
closed liveness, the shared field keys. It needed the R5 filter labels and nothing
else from the contract.

### Decisions

* **H1 Gore is the filter's conflict end.** Graphic situations, conditions, surface
  details, apertures and weapons are tagged `conflict_only`; the node shows "No
  gore" (default), "Any" and "Gore only". `tests/test_horror_pack.py` holds "No gore"
  to zero graphic values on both paths.
* **H2 Stillness is priced up.** `TIER_WEIGHTS` favour idle acts more than the other
  genres, and every kind has place-neutral acts of standing, watching and waiting.
* **H3 Liveness inverts for the dead.** A walking corpse is live; `DORMANT_ACTS` is
  what a thing at rest does -- lying in its coffin, gathering dust, rotting quietly
  into the ground.
* **H4 Placement is declared per kind.** A cursed object belongs in a room, a tomb
  or under water; a haunted place under open sky.
* **H5 Content guidelines** from `docs/genre-roadmap.md`: no real people or
  tragedies, no mental illness as a monster, no living religious or cultural figure
  as a monster, no trademarks, no child in peril.

## Round XVI: the 0917-afternoon concerns batch

162 images pulled by hand from a mixed sci-fi/fantasy/horror batch, the
horror pack's first render test. Four defects traced to mechanism gaps
rather than data mistakes.

### Two pre-existing engine defects, exposed by this round's own data edits

Both measured zero hits on `main` before this round; a pool-size change
anywhere shifts the RNG draw sequence for everything drawn after it in the
same seed, and this round's edits (mostly narrower pools, per
`variety-is-kept-by-adding`, replaced before removed) happened to shift far
enough to reach code paths the old distribution never touched. Neither is a
new risk this round introduced on top of the shared engine - both were
already reachable on every genre, this round's data changes just made them
visible.

* **X1 A rotation slot is a count, not a share of unspent allowance.**
  `engine/budget.py`: when a fixed-head field went unsaid, the surplus
  allowance kept drawing *additional* rotation candidates one at a time until
  the whole remaining budget was spent on rotation, against a declared
  `detail_rotation_slots` of one or two. A courier grew three boarding-tube
  launchers and six telescope panels; an asteroid's `world` archetype (fixed
  head includes both `appendages` and `emitters`) always spoke an emitter
  *and* an appendage together. The draw now stops at
  `reserved = min(slots, allowance)`; a reserved slot nothing could fill
  still falls back to the core order, unchanged.

  Two sci-fi archetypes (`object`, `structure`) turned out to rely on the old
  spillover to satisfy `test_every_entity_speaks_a_component_clause`: their
  rotation pool mixed genuine component fields (`appendages`/`emitters`/
  `armament`/`sensors`/`aperture`/`extras`) with decorative ones
  (`markings`/`accent_color`/`surface_detail`), sharing one slot, so a
  decorative field could legally win it outright and leave the archetype
  with no component spoken. Moved the decorative fields into the fixed head
  (`object`'s cap already had headroom; `structure`'s cap rose from 8 to 11,
  matching the three fields added to its fixed list - never about speaking
  *more*, only about which field a lone rotation slot could spend itself on).
* **X2 A re-offered value is not re-validated.** `engine/scene.py`, the round
  XIII "re-offer what a rule emptied" step (`_apply_constraints`): it fills a
  field the fixed point nulled, once, after the fixed point has already
  settled - so a value re-offered late can conflict with a field that
  settled earlier, while the target still read `None` and excluded nothing.
  A haunted place's `condition` re-offered as `"boarded-up"` (the `inactive`
  trait) landed next to an already-fixed `situation` carrying `powered-act`
  ("shuddering as something moves inside"), a combination the
  `inactive|powered-act` trait conflict already forbids and normally
  prevents. Fixed with a bounded (3x) outer retry around the fixed point +
  re-offer pair: whenever a re-offer actually changes something, the fixed
  point gets one more pass to catch and redraw whatever it now conflicts
  with, using its own existing exclusion logic.

### Genre-agnostic patterns, fixed once each

* **X3 A doll's eyes reach a chair.** `EMITTER_POOLS["cursed object"]`
  (horror) held a painted-eye value at the kind level; the `furnishing`
  subkind (a mirror, a clock, a rocking chair) had no key of its own and fell
  through to it. Same shape as round XV's `FALLTHROUGH` (check 32), a
  different pool; fixed with an empty-key override, the same trick
  `SENSOR_POOLS["furnishing"]` already used.
* **X4 A substance-adjective renders as the substance.** Beyond a bare noun
  ("tether" draws a chain), a hyphenated adjective whose head is a substance
  noun can detach and render literally: "forked tongue" drew a table fork,
  "furled banner" drew fur fringe, "water-stained" (a condition on a cursed
  chair) drew dripping water off a dry floor. The three instances found are
  renamed (cloven tongue, rolled banner, damp-blotched). No automated check
  exists for the class: `FOREIGN_NOUNS` is anachronism-scoped and "fur"/
  "fork" are correct, common fantasy/horror words everywhere else in the
  pack (bear fur, a table fork used correctly); adding them would fail
  validation on every legitimate use. Left as a review habit for new content
  until a narrower signal is found.

### Per-genre

* **Horror:** the `figure` carry-clause joined three fields
  (`{armament, emitters, extras}`, near-guaranteed together) where fantasy
  and sci-fi join two and speak `emitters` in its own sentence; matched.
  `EXTRAS_POOLS["undead"]`'s hospital-band value asserted a modern death and
  reached medieval catacombs and sunken ships alike; dropped and replaced in
  kind (no era/context need token exists to re-scope it safely). A spirit or
  corpse already `submerged` could also be `"slowly dripping water"` or
  `"dripping fresh blood"`; gated both to horror's existing derived `air`
  ("not submerged") token. `VALUE_NEEDS["condition"]` was empty; added
  `overgrown` -> `life` (round XIV's scifi deposit-condition pattern, ported;
  horror has no frost/ice *condition* value to gate the way scifi/fantasy
  do - its cold-only content is already situation-gated). `"rotting
  windmill"` reached a churchyard and a field of grave markers; a
  `funerary-place`/`rural-landmark` trait conflict scopes it out of the four
  explicitly funerary environments only. `EXTRAS_POOLS["cursed object"]`'s
  furnished resting surfaces (a display case, a dusty shelf) reached a reed
  marsh and a flooded church nave; gated to `{structure, air}`, with a
  place-neutral surface added to keep outdoor/underwater objects a place to
  rest. Gore roughly tripled: 9 `"c"`-tagged situations and ~11 `_GORE`
  values before this round; ~29 situations (undead's own situation count
  went from ~15 to 43 total) and ~9 `_GORE` values after, genuinely graphic
  (dismemberment, exposed organs, disembowelment) rather than merely
  implied, tiered `event` where `TIER_WEIGHTS` rewards it, still fully
  hidden by "No gore".
* **Fantasy:** the same resting-surface gating applied to `EXTRAS_POOLS
  ["relic"]` (a velvet cushion, a silk-draped table); the stone/altar
  surfaces stay place-neutral, already fine outdoors and underwater.
  `"forked tongue"` -> `"flicking a cloven tongue"` (X4). Deposit-condition
  gating completed: `"overgrown"` -> `life` alongside the existing
  `"frost-rimed"` -> `cold`.
* **Sci-fi:** `"small body"` (asteroid/comet) fell through to `"celestial
  body"`'s planet-scale volcanic vocabulary (`volcanic vent`, `lava
  fissure`, `geyser vent` on a bare rock) - given its own pool, outgassing/
  sublimation language only, and `"dust plume vent"` dropped the word
  `"vent"` specifically (`"dust plume"`), which read as an engine port on a
  natural body. `"sensor gauntlet"` (a worn sensor) and `"magnetic grapple"`
  (a carried extra) both localise to a spacefarer's hand; a figure drawing
  both fused into one wrist. Shared a `hand-mounted` trait across the two
  fields rather than reword either value - `"magnetic grapple"` is also the
  noun in the established `"latching onto a hull with magnetic grapples"`
  situation, unaffected. Ground vehicles read as present-day military/
  utility hardware (the recurring report): renamed the handful of terms with
  no futuristic reading at all (`pintle-mounted gun`, `intake grille`,
  `driver hatch`, `rear cargo door`, `front`/`tail beacon bar`, `angled
  glacis armour plate`, `cargo bed`) and added repulsor/energy-weapon values
  across form, appendages, emitters, armament and aperture - net wider, not
  narrower. Discovered mid-edit: a ground vehicle's `form` and `appendages`
  are scoped entirely through locomotion sub-groups (`wheeled/tracked`,
  `hovering`, `flying`, `lander`, `underwater`, `legged`); the kind-level
  pool is dead weight for those two fields, the same `SHADOWED` shape as X3
  in a different field, caught by the validator and moved to the sub-group
  that actually resolves.

### Round XVI, measured

Every check in "Build and test" (`AGENTS.md`) is green, including
`coherence_sweep.py --gate` on both paths, `sample_distribution.py` (no
kind/scale/motif ceiling breached), and `coherence_audit.py` (every
archetype's clause-per-scene mean stayed within its pre-round shape;
`structure`'s cap increase to 11 lands exactly at its own measured p95, not
above it). `reach_audit.py --gate` reports the same class of gap as every
prior round - a handful of values confined to a rare place-and-kind or
place-and-subkind combination a 12000-seed sample did not happen to draw,
including two of this round's own new sci-fi armament values; not a
structural gap (the validator's `SHADOWED` check, which is exhaustive, not
sampled, passed clean).

## Round XVII: the 921-concern batch

27 images the maintainer flagged by hand from a mixed sci-fi/fantasy/horror
render test of round XVI, plus (new this round) a plain word/environment
frequency sweep (2000 seeds per pack, `doc["environment"]` and a lowercased
`text` substring count) run to turn "too many X" reports into a number
instead of an impression - the same instrument class `sample_distribution.py`
already is for sci-fi, applied ad hoc to all three packs since a dedicated
per-pack version does not exist yet (left for a future round; see Known gaps
in `AGENTS.md`).

### Findings and fixes

* **XVII1 A colour name that is an object, in horror's shared emitter-colour
  pool.** `EMITTER_COLOR_POOLS["_default"]` (horror) carried `"lantern
  amber"` - correct on `mortal`, where the emitter itself is a literal
  lantern, but the same default pool backs `spirit`, `undead`, `cryptid`,
  `eldritch horror`, `cursed object` and `haunted place` too, where the
  emitter is `"pale inner light"` or `"cold spectral flame"`. "Lantern amber"
  on an apparition read as a literal floating lantern rather than an amber
  glow - the `colour-names-that-are-objects` class (round XI: "dusty rose",
  "brick red"), missed because the value is genuinely correct on one of its
  seven consumers. Renamed the default to `"warm amber"`; `mortal`'s own
  override keeps the literal value. Measured: the share of horror scenes
  containing the word "lantern" fell from 12.7% to 6.5% (2000-seed sweep,
  seed 4242) - this also answers the maintainer's separate "too many lanterns
  overall" report.
* **XVII2 A kind-level pool key reached all three landmark subkinds.**
  `APPENDAGE_POOLS["landmark"]` (horror) held `("rusted access ladder",
  "broken sail")` at the kind level; `lonely lighthouse`, `rotting windmill`
  and `rusted water tower` are its three subkinds, none with an override of
  their own, so a lighthouse and a water tower both grew a windmill's sail.
  Same shape as round XVI's X3 and the ground-vehicle `form`/`appendages`
  finding: a kind-level default is a trap for every subkind that never
  declared its own. Split into three subkind entries; `"broken sail"` stays
  on `rotting windmill` only.
* **XVII3 "Passenger" reads as a present-day airliner.** A `ghost starliner`
  wreck (spoken `"ghost passenger-starship wreck"`) rendered as a crashed
  commercial jet fuselage - a magenta paint stripe and window rows on a
  tube-shaped hull in a desert, the standard "airliner crash" prior a
  diffusion model reaches for on sight of "passenger" plus a tube hull. This
  is the literal example `AGENTS.md`'s own review rule already named ("a
  ghost passenger liner, a wreck" is not safe, because "wreck" names no
  medium) - the pack had drifted from its own stated rule without anyone
  reverifying the one live value it applied to. Renamed both spoken forms
  that carried it: `"ghost starliner"` -> `"ghost liner-starship wreck"`,
  and the live (non-wreck) `"starliner"` subkind -> `"interstellar liner
  starship"`. Measured: the share of sci-fi scenes containing "passenger"
  fell from 1.4% to 0% (2000-seed sweep).
* **XVII4 The one "door" in a pool of hatches.** `APERTURE_POOLS["surface
  vehicle"]` (sci-fi) - the same pool round XVI's ground-vehicle pass already
  renamed for modern-day readings - still had `"side door portal"` sitting
  among `"cabin canopy"`, `"pilot hatch"`, `"roof hatch"`, `"aft cargo
  hatch"`: the only value in the list that says door instead of hatch/vane/
  maw/port/canopy. On a submersible (`underwater` locomotion, staged "deep
  underwater") it read as a literal door opening onto open ocean. Renamed to
  `"side hull hatch"`, matching the pool's own naming convention.
* **XVII5 A standard on a bare skeleton.** `EXTRAS_POOLS["undead"]`
  (fantasy) - carried, not worn - held `("rusted manacle", "tattered
  banner", "clinging grave dirt")` at the kind level, reaching every
  `walking dead` subkind including the `lich`: a solitary undead spellcaster
  carrying a banner with no army in frame read as a flag lashed to a
  skeleton. Narrowed the kind default (dropped the banner, added
  `"bone-carved talisman"`) and gave the two subkinds that plausibly lead
  troops, `skeleton warrior` and `death knight`, their own entry that keeps
  it - the same subkind-override shape as XVII2, applied before it shipped
  rather than after a report.
* **XVII6 A flying ship's situations were mostly altitude-neutral.**
  `SITUATION_POOLS["flying ship"]` (fantasy) = the shared `_S_VESSEL_CORE`
  (~17 situations written for a ship on water: "trailing a long banner",
  "carrying a crowd of cheering passengers", "riding low under a heavy
  load") plus `_S_AIRSHIP_EV_SKY`/`_S_AIRSHIP_ACT_SKY` (4 situations with an
  explicit altitude cue). A flying cloud skiff whose draw landed in the
  shared pool - better than 4-in-1 odds - carried no signal that it was
  aloft at all, and rendered as a boat docked in the mangrove fen it was
  staged in. Per `variety-is-kept-by-adding`, did not trim the shared pool
  (still correct wherever a sailing ship draws it); added six more
  sky-specific situations instead (`"banking hard around a spire of rock"`,
  `"venting steam as it climbs"`, `"casting"`-free wording throughout - an
  early draft's `"casting a long shadow over the ground below"` tripped both
  the rendering denylist on `"shadow"` and the affordance lint on an
  undeclared `"ground"` need, replaced with `"climbing steadily into open
  sky"`), moving the ratio from roughly 4:1 to roughly 2:1.

### Investigated, not changed

* **"Too many motel scenes" (horror).** Measured at 3.5% of horror scenes by
  environment share (2000-seed sweep) - within noise of the ~29-place pool's
  uniform ~3.4% expectation. No structural weighting found; not a
  reproducible bias, so left alone rather than cut on an impression (the
  same caution `variety-is-kept-by-adding` asks for in the other direction).
* **"Too much octopus" (sci-fi and horror).** No pool anywhere contains the
  word; the read comes from several `alien creature` body-plan groups
  (`tentacular`, `amorphous`, `radial form`, `mimic body`, `symbiotic body`,
  `void dweller`, `filter swarm`) each defaulting to tentacle/sucker/frond
  appendages, concentrated into water scenes by the `cephalopod` archetype's
  existing (and correct) water-only gate. A real fix is diversifying each
  body-plan group's non-tentacle appendage options (claw, fin, spine, wing
  are already vocabulary elsewhere in the same pack) - a full-pool pass in
  the shape of round XVI's ground-vehicle fix, not a spot rename, and left
  for a dedicated round rather than forced here.
* **"Very odd protrusions" / "stuff sprayed incoherently".** Plausible
  render-time effects of long multi-part alien anatomy lists and
  action+tool combinations (a foam sprayer sealing a hull breach); no single
  traceable pool value found this round. Flagged for the maintainer's next
  batch rather than guessed at.
* **"Door open underwater".** One plausible source addressed by XVII4; no
  second cause found in this batch.
* The pre-existing `reach_audit.py --pack horror --gate` and `--pack fantasy
  --gate` failures (a handful of never-drawn `sensors`/`situation`/
  `primary_color` values, unrelated fields to every fix above) were
  confirmed identical on `tmp/sceneweaver-fantasy` before this round's edits
  (`git stash` + re-run) - pre-existing, not touched.

### Round XVII, measured

Every check in "Build and test" (`AGENTS.md`) is green: the full
`unittest`/`pytest` suite, both genre validators
(`test_horror_pack.py`/`test_fantasy_pack.py`), `reach_audit.py --pack
scifi/fantasy/horror` (no new never-drawn values introduced by this round's
six fixes; the two packs' pre-existing gaps are unchanged, see above). The
word-frequency sweep is new maintainer tooling for this round only
(`.omo/`-equivalent throwaway script, not committed) - a permanent per-pack
`sample_distribution.py` is future work, not built this round.

## Round XVIII: the 922-concern batch

22 images from a mixed fantasy/horror render test of round XVII (no sci-fi in
this batch). Six confirmed defects, all data-only, horror and fantasy only -
sci-fi untouched, including where the same pattern was found in its own
pools with no render evidence behind it (see "Investigated, not changed").

### Findings and fixes

* **XVIII1 Emitters and aperture shared one clause, in all six horror
  archetypes.** `Sentence(text="{pronoun} bears {emitters, aperture}.")`
  (and its `show`/`features`-adjacent siblings) joined a light source and a
  mouth or opening in one "X and Y" clause everywhere: `dead`, `spirit`,
  `creature`, `figure`, `object`, `furnishing`, `place`, and the stranger
  fallback. Confirmed in render: a flesh mass's "single cold-white pulsing
  inner light and a ring-shaped toothed maw" drew a glowing mouth - the
  light read as coming from the opening beside it. A ghost's "single
  sickly-green cold spectral flame" (meant as a body glow) read as a torch
  held in an outstretched hand for the same reason - the maintainer's
  "things are on fire strangely" and "floating candle" reports. Split into
  two sentences everywhere (`"{pronoun} glimmers with {emitters}."` /
  `"{pronoun} bears {aperture}."`, pronoun/verb form matched per archetype),
  so a light is never grammatically anchored to an opening. Same two
  fields, two sentences instead of one - no field lost, no `detail_cap`
  change.
* **XVIII2 "lantern amber" still collided on the one pool round XVII left
  literal.** Round XVII kept `"lantern amber"` on horror's `mortal`
  emitter-colour override, reasoning it was safe paired with the
  `"hooded lantern"` emitter value - missed that a colour and an emitter are
  drawn independently of each other, so it landed on `"guttering candle"`
  just as often, and a possessed villager's "lantern amber guttering
  candle" rendered as a second, literal lantern beside the candle. Unified
  to `"warm amber"` everywhere; the object-noun colour no longer exists
  anywhere in the pack.
* **XVIII3 "a crown of" render-trap word, confirmed in render:** "a writhing
  thing beneath the ice... unfurling a crown of tentacles" drew an octopus
  wearing a literal jewelled crown. Removed the phrase from both packs'
  cardinality-count vocabulary - the `"a crown"` class now offers
  `"a cluster of"` (horror) / `"a ring of"` (fantasy), both already-safe
  words used elsewhere in the same pack - and from the one hardcoded
  situation string that used it outside the count system
  (`"unfurling a crown of tentacles"` -> `"unfurling a writhing mass of
  tentacles"`). Horror's `"tentacle-crowned body"` form value carried the
  same risk as a bare adjective; renamed `"tentacle-topped body"`. Sci-fi
  has its own `"halo crown"` / `"sensor crown"` part names at a higher word
  share than either genre now carries - left untouched, see below.
* **XVIII4 "thing beneath the ice" could only ever be drawn somewhere with
  no ice.** Its only declared need was `cold`, and `"snowbound pine
  woods"` was the *only* cold place in the whole pack - one with no water
  affordance at all. Every single draw of this subkind therefore landed in
  a place with nothing to be beneath (confirmed in render: the octopus
  above stood in snowy pine woods, no ice or water in sight). Added `water`
  to its need and a new place, `"frozen lake bed"`
  (`submerged`, `floor`, `dark`, `cold`), so the subkind finally has
  somewhere its own name is true - `variety-is-kept-by-adding` again: a
  place added, not a subkind removed.
* **XVIII5 "flooded church nave" fought its own staging suffix.** The
  `underwater` band appends `", deep underwater"` to every place in it;
  "flooded" reads as shallow and walkable, so the sentence asked for a
  knee-deep nave and a fully submerged one at once - the maintainer's
  "strange double-underwater issues" report, and the same place that drew
  attention across two rounds now (round XVI's flesh mass, round XVII's
  apparition). Renamed to `"drowned church nave"`, consistent with its two
  band-mates (`"murky lake bottom"`, `"sunken ship hold"`, both already
  unambiguous). It was also the only underwater place with no per-place
  affordance override, so nothing else about it changed.
* **XVIII6 A single "feather crest" rendered as one stray feather.**
  Correctly classified `"a lone part"` (a bird has one crest), but "feather
  crest" reads as "one feather," not "a crest made of feathers" - the
  maintainer's "bird with a weird head feather" report on a phoenix.
  Renamed to `"plumed crest"`, same cardinality, no count change.

### Investigated, not changed

* **The fantasy/horror `armament, extras` "carry" join** (two fields, one
  clause) is the round-XVI baseline every genre already matches, not a new
  defect - checked all three genres for any surviving three-field join
  (the shape round XVI fixed) and found none. The "holding too much"
  report traced mostly to XVIII1: an emitter reading as an *extra* held
  object on top of what was actually in the carry clause.
* **"Ship on land":** the only instance in this batch was a wrecked sky
  galleon explicitly `"lying broken on a hillside"` - a dormant act,
  correctly grounded. No live (non-wreck) vessel drawn off its required
  affordance was found.
* **"Random eyes":** every instance found was a `"cluster of...eyes"` /
  `"bulging staring eyes"` on an eldritch-horror or amalgam kind, where a
  scattered many-eyed face is the intended Lovecraftian read, not a defect.
  No occurrence found on a kind where it would be incoherent.
* **"Wet bony coverings":** no separate textual cause isolated; the most
  likely contributor (a skeletal or drowned kind staged in the
  self-contradictory "flooded church nave") is addressed by XVIII5.
* **"Floating chalice":** no carry pool anywhere places a chalice in a
  figure's hands; the only "chalice" in the pack is the `jewelled chalice`
  relic subkind, itself a whole entity, already staged by round XVI's
  resting-surface fix. Most likely the same render class as the
  floating-candle finding (XVIII1) rather than a separate defect - not
  independently reproduced in this batch.
* **Sci-fi's own `{emitters, aperture}`-family joins** (nine archetypes,
  some joining up to five fields at once) are structurally the same shape
  as XVIII1 and could in principle suffer the same read. Left untouched:
  zero reported instances against sci-fi in either concern batch, sci-fi's
  apertures are mostly mechanical (vents, hatches) where a nearby glow is
  often literally correct rather than a misread, and it is the most
  mature, most heavily tested pack in the repo - editing it on
  pattern-matching alone, with no render evidence, is exactly the
  cross-pack risk the maintainer asked to avoid. Revisit only if a sci-fi
  render ever shows the same conflation.

### Round XVIII, measured

Full `unittest`/`pytest` suite green (670 tests, 131192 subtests).
`reach_audit.py --pack horror/fantasy --gate` reports the identical
pre-existing gap as round XVII (confirmed unchanged by this round's edits) -
no new never-drawn value from any of the six fixes above, including the new
`"frozen lake bed"` place and the renamed `"drowned church nave"`. The
word-frequency sweep (2000 seeds/pack, same throwaway script as round XVII):
horror's `"lantern"` share fell further, 6.5% -> 4.1% (`"guttering candle"`
no longer doubles as a lantern); `"crown"` fell to 1.4% in horror and 2.1% in
fantasy, both now free of the render-trap phrase entirely (remaining hits
are literal worn/held crowns - a lich's `"iron crown"`, a relic that *is* a
`"jewelled crown"` - which are correct).

## Round XIX: the 922-concern batch (part 2)

53 images from a mixed sci-fi/fantasy/horror batch, the maintainer's render
test of round XVIII plus fresh testing on all three genres together. Nine
fixes this round - the first to touch all three packs in one round, though
each fix stays inside its own pack; sci-fi and fantasy shared no code path
that could let a fix in one cost the other.

### Findings and fixes

* **XIX1 Splitting the emitters/aperture clause (round XVIII) was necessary
  but not sufficient.** "Glow in a mouth" was still reported: a diffusion
  model attends across the whole prompt, not sentence by sentence, so an
  unlocated "pulsing inner light" and a "ring-shaped toothed maw" still read
  as one thing even in separate sentences - both describe the same
  featureless silhouette, so the model puts the light where the mouth is.
  Anchored every unlocated horror emitter to a body location other than the
  face: `"cold spectral flame"` -> `"...in its chest"`,
  `"pale inner light"` -> `"...in its chest"`, `"pulsing inner light"` ->
  `"...beneath its hide"`, `"luminous pustule"` -> `"...on its flank"`.
  Verified each phrase pluralizes correctly (`engine/grammar.py`'s
  preposition-boundary rule needs the location phrase to start with one of
  its recognised prepositions - "in", "beneath", "on" - immediately after
  the noun, not after another adjective; an early draft, `"...deep in its
  chest"`, pluralized "deep" instead of the noun and was caught by direct
  testing before it shipped).
* **XIX2 "dusty ledge" was still the fallback surface underwater.** Round
  XVI declared it place-neutral on purpose, correctly for a reed marsh, but
  dust does not settle underwater - a spirit board resting on a "dusty
  ledge" in a "drowned church nave, deep underwater" rendered as a bone-dry
  room with no water in it at all, confirming the maintainer's "that
  drowned church still isn't looking right." Gated `"dusty ledge"` to `air`
  (excludes submerged) and added `"silt-caked ledge"`, gated to `submerged`,
  so a cursed object always has a surface, wet or dry.
* **XIX3 A nest needs somewhere wild to nest.** `"guarding a clutch of
  eggs"` (every dragon subkind, including a hydra) carried no place need at
  all - confirmed in render: a marsh hydra guarding eggs in a cobbled
  market square, between the stalls. Split it out of the shared
  `_S_DRAGON_CALM` bucket into its own bucket requiring `life`, which
  `settlement`/`cobbled market square` do not grant; `"grooming its scales"`
  (needs nothing) stayed behind.
* **XIX4 Walk-only creatures reached underwater and astral-void places
  through a coarse kind-level gate.** `KIND_POOLS["underwater"]` lists
  `"mythic beast"` and `"hybrid folk"` because some of their members swim
  (kraken, hippocamp, merfolk, naga) - but the gate does not distinguish a
  swimmer from `"unicorn"` (form stance `_WALK` only), confirmed in render:
  "a huge untamed unicorn is charging headlong" through drowned city
  streets. `value_stances`/`place_stances` correctly filters which
  *situations* a walk-only form can do there, but does not exclude the
  *subkind itself* from an incompatible place - a form-vs-place mismatch
  the stance system was never wired to catch at that level. Gave the eight
  walk-only members of `"hoofed beast"` and `"hybrid folk"`
  (`unicorn`, `nightmare steed`, `silver stag`, `centaur`, `satyr`, `faun`,
  `minotaur`, `gorgon`) a `ground` need via `_SUBKIND_NEEDS`, granted by
  wilds/waterside/settlement/underground alike so nothing they already
  correctly appear in is narrowed. Verified empirically (4000/6000-seed
  targeted sweeps): zero walk-only subkinds reach `drowned city streets`
  afterward, only the aquatic members do. A full audit of every remaining
  walk-only subkind against every underwater/sky-only environment (giants,
  most undead, constructs) is not done this round - scoped to the reported
  kinds and their direct siblings; see Known gaps.
* **XIX5 A full-throttle mishap needs room to have built up speed in.** Six
  ground-vehicle situations (`"losing a wheel"`, `"spinning out"`,
  `"throwing a track"`, `"ramming a barricade"`, `"climbing a dune ridge"`,
  all "at full throttle"/"at speed", plus `"racing a storm front toward
  shelter"`) carried no place need, confirmed in render: an amphibious
  crawler "losing a wheel at full throttle" inside a "station docking ring
  interior" - a tight, walled place `KIND_POOLS` allows a vehicle into for
  loading, not racing through. Gated all six to `vast` (`"climbing a dune
  ridge"` also needed `ground`, caught by the affordance lint on the word
  "ridge" - the two zero-need situations that already had a place attached
  to their name still needed the token spelled out).
* **XIX6 A new cross-field trait: a hand can hold one thing.** "Someone
  with a lantern stuck to their wrist while firing a bow," "holding too
  much": a hand-held light (horror's `"hooded lantern"`/`"guttering
  candle"`/`"handheld torch beam"`, fantasy's `"hooded lantern"`) is drawn
  independently of armament, so it could land beside a bow at full draw or
  a shotgun - both already occupying both hands. Declared `hand-occupying`
  on the light values and a new `two-handed-weapon` trait on horror's
  `shotgun`/`fire axe`/`hunting rifle`, conflicting with fantasy's existing
  `bow-weapon` trait (`longbow`, `tiny bow`) - the same declarative
  mechanism `bow-act`/`edged-weapon` already used, extended to a field
  nobody had connected to it before rather than a new engine feature.
* **XIX7 Fantasy's artifact pool was thin.** 15 subkinds across `relic`/
  `monument`, each close to bare self-naming with only a kind-level
  material/colour/markings pool behind it - the maintainer's "artifacts
  kinda suck." Added three, each with its own `form` values (the one
  per-subkind card an artifact needs; everything else already resolves at
  the group level): `"black grail"` and `"singing harp"` (relic),
  `"weeping idol"` (monument).

### Investigated, not changed

* **"Very odd protrusions" / "crystal protrusions."** Traced further than
  round XVII's "diversify the tentacle vocabulary" note: `"alien creature"`'s
  `detail_cap`/rotation is not obviously over-budget in field *count*
  (comparable to sibling archetypes), but several small-scale fungal/
  crystalline-growth subkinds stack multiple independently-counted part
  fields at once (a filter stalk, four acid spore bursts, eight
  light-sensing patches, three phosphorescent tendrils, a feeding slit - 17
  individual named parts on one small body). This is a cardinality-budget
  tension, not a vocabulary bug: the high-count values ("a dozen", "eight")
  exist because "genuinely many" is the right description for some
  creatures, and trimming them globally would cost the variety the
  maintainer also asked to keep. Needs a body-plan-by-body-plan pass with
  measurement, not a rushed cap change touching every scifi creature -
  scoped out of this round, left for a dedicated one with this sharper
  diagnosis to start from.
* **"So many people spraying random stuff that makes no sense."** No single
  traceable pool value found; `"sealing a hull breach with a foam sprayer"`
  and `"spraying sealant on a seam"` are coherent as written. Likely a
  diffusion-rendering limitation for the concept of a directed spray rather
  than a text defect.
* **"Stuff coming out of the dirt where there should not be dirt"
  (sci-fi).** The word "dirt" does not appear anywhere in `data/scifi.py`;
  not text-traceable.
* **"Weird bone decorations on clothes."** `"sewn-on bone charms"` (a
  horror markings value) is a coherent, thematically-intended folk-horror
  detail; no defect found in the text.
* **"Goat holding bow."** A faun's form is already `"goat-legged human
  build"` - correctly bipedal with human arms. The quadrupedal-reading
  render is most likely a model interpretation, not a text bug; no safer
  rewording found without weakening the "goat-legged" cue that makes a
  faun read as a faun at all.
* **A vampire's dry velvet coat, rendered underwater with no waterlogged
  cue.** Identified (`"bloodsucker"` has no submerged-appropriate material,
  unlike `"drowned dead"`'s dedicated sodden rags) but not fixed this round
  - lower confidence and impact than the other findings; noted for a future
  pass rather than rushed.
* **"A ramp down while a vehicle is moving and its engines are firing."**
  Not reproduced from this batch's prompt text; no single situation or
  value combination found that states both at once. Likely a rendering
  combination rather than a text defect.

### Round XIX, measured

Full `unittest`/`pytest` suite green (670 tests, 131327 subtests).
`reach_audit.py --pack scifi/fantasy/horror --gate` reports the same
pre-existing gaps as round XVIII in sci-fi and horror, unchanged by this
round's edits. Fantasy has one new entry, `"small lap harp"` (one of two
`"singing harp"` form values) - the same rare-combination-not-sampled class
already documented above (`"white-gold"`, the five unbucketed situations),
not a structural gap; `singing harp` is one of eleven relic subkinds and the
form is a straight coin flip within it. Verified directly (not just via the
suite) that the two coherence fixes hardest to see from a diff alone hold:
a 4000-seed sweep of `drowned city streets` before XIX4 drew `unicorn`
three times and zero after, sourced only from `kraken`/`hippocamp`/
`kelpie`/`giant sea turtle`/`selkie`/`naga`/`merfolk`; a 6000-seed sweep of
every scene containing `"guarding a clutch of eggs"` after XIX3 drew it only
in `life`-affording places, zero times in a settlement.

## Round XX: the 922-concern batch (part 3)

49 images, all three genres, no maintainer-supplied list this time - the
brief was to scrutinize every image and find what round XIX missed, since
the maintainer had reported real fixes not holding across rounds. Went
through all 49 individually rather than sampling. 19 fixes; three are new
mechanism-level findings (rounds XVII-XIX had established the pattern-vs-
place-need class - this round found the class extends to hand-occupancy on
extras and situations, not just armament, and a new "wrong half drawn first"
class in hybrid-creature form wording), the rest are the same
declared-need-is-missing shape applied to values that had slipped past three
prior rounds of the same check.

### Findings and fixes

* **XX1 Round XIX's emitter fix held; round XVIII's request for it did not,
  and the gap was one field wider than either round scoped.** Re-verified
  in render: `#00560`/`#00566`/`#00591` (poltergeist, poltergeist, tentacled
  abomination) all show their glow at the anchored body location, not the
  mouth - round XIX's fix is confirmed working, not just tested. But
  `"weeping with its face in its hands"` (fantasy `undead`, horror `dead`,
  horror `spirit`) and `"cracking open a ribcage with both hands"` (horror
  `dead`) put both hands to one job while the same entity could also be
  drawn carrying armament or (for `spirit`, via its own `"{pronoun}
  clutches {extras}"` sentence) an extra - confirmed in render, `#00534`'s
  drowned revenant weeping with its face in its hands while also carrying a
  reaping scythe. Reworded both to postures that need no hands at all
  (`"hunched over in silent grief"`, `"cracking open a ribcage"` without
  the hand count) rather than gating them, since a hand-count trait would
  have meant re-drawing a beloved vivid phrase into a blander fallback most
  of the time it fired.
* **XX2 The maintainer flagged the replacement wording itself before it
  shipped.** The first draft of XX1's fix, `"shoulders shaking with a
  silent sob"`, describes motion a still frame cannot show. Replaced with
  `"hunched over in silent grief"` - a posture, not a motion.
* **XX3 Hand-occupancy (round XIX) was scoped to armament; extras and
  situations needed it too.** Empirically swept (5000 seeds/pack): horror's
  `spirit` kind still produced `"weeping with its face in its hands"` +
  `"clutches a tarnished locket"` (fixed by XX1's reword) and five
  `_S_SURVIVOR_ACT`/`_S_SURVIVOR_WALLS` situations
  (`"checking a hunting rifle with shaking hands"`, `"loading shells into a
  shotgun"`, `"clutching a first aid kit to their chest"`, `"bandaging a
  bleeding arm"`, `"barricading a door"`) produced a hunting-rifle-handling
  pose alongside an independently-drawn hand-held emitter (a lantern, a
  torch beam) - confirmed in render, "loading shells into a shotgun" next
  to "a single cold-white handheld torch beam" already somehow in the same
  two hands. Tagged all five `two-handed-weapon`, reusing round XIX's
  conflict with `hand-occupying` rather than inventing a new trait pair.
  Re-swept after: 0 problems in 5000 seeds, fantasy and horror both.
* **XX4 A render-trap word survived three rounds of review for this exact
  class:** `"eyespot rosettes"` (a camouflage marking, like a moth wing's
  false eye) - confirmed in render, `#00434`'s gelatinous mass grew a third
  set of literal glowing eyes from what was meant to be a body marking.
  Renamed `"concentric-ring rosettes"`, describing the same visual pattern
  without the word "eye" in it.
* **XX5 A form that names the animal half first drew two creatures instead
  of one.** Confirmed in render: `#00506`'s centaur rendered as a complete
  horse (with its own head) plus a separate human torso reaching up to pet
  it, from the form text `"horse body below a human torso"` - "horse body"
  read as a complete subject on its own, with "below a human torso" landing
  as an unrelated second object rather than a fusion instruction. Compared
  against the pack's own working examples: `gorgon` (`"human torso and arms
  above a coiled serpent tail"`) and `naga` (the identical pattern) render
  correctly, because the human half is named first and the animal half
  trails as the modifier. Reworded `centaur` and the one other value with
  the same animal-first shape, `merfolk` (`"long fish tail below a human
  torso"`), to match the working pattern: `"human torso above a horse's
  body"`, `"human torso above a long fish tail"`.
* **XX6 A weapon-neutral situation still committed to a weapon shape a bow
  cannot make.** Confirmed in render: `#00512`'s gorgon, carrying a
  longbow, given `"charging with a lowered weapon"`, rendered holding a
  pair of swords instead of the bow the text actually named - "lowered" and
  "brandished high" read as bladed-weapon poses regardless of what
  `armament` says. Round XV's existing `blade-act` trait already exists
  for exactly this shape (conflicts with `bow-weapon`); the two situations
  had just never been added to it. Added `"brandishing a weapon high"` and
  `"charging with a lowered weapon"` to `_BLADE_ACTS`. Verified: 27 distinct
  situations remain available to a bow-carrying `hybrid folk` entity across
  an 8000-seed sweep, zero bad combinations - the fix excludes, it does not
  starve.
* **XX7-XX15: nine more instances of round XVII/XIX's "a situation names a
  physical feature with no matching need" shape**, found by scanning every
  situation's text for a surface/temperature word and cross-checking its
  declared need (a script, not a re-read by eye - the same class had
  already survived three rounds of manual review). Confirmed in render for
  one: `#00472`'s burrowing horror "flattening itself against a rock" in
  `"derelict shipyard orbit, out in open space"`, with nothing solid within
  reach. Sci-fi: `"flattening itself against a rock"`, `"drilling a core
  sample from the bedrock"`, `"crossing cracked ground"` -> need `ground`;
  `"floating above a ruined floor"` -> needs `structure`; `"reversing out
  of a gully"` -> needs `floor` (not `ground` - the one live render of this
  situation, `#00461`, was a submersible in an ocean trench, which has
  `floor` but not `ground`, and was already coherent); `"plunging through a
  sheet of thin ice"`, `"tearing open along a frost-welded seam"`,
  `"surfacing through a sheet of ice"` (already had `submerged`) -> need
  `cold`. Fantasy: `"hammering at a rock face"` (dwarf) -> needs `ground`,
  confirmed practically live (folk-kind is eligible for `interior` places,
  which have no `ground`, unlike every other kind checked in this pass).
  The scan also surfaced matches that were *not* fixed because a
  kind-level restriction already made the place unreachable in practice
  (verified per case, not assumed) - see "Investigated, not changed."

### Investigated, not changed

* **Every keyword-scan hit whose kind is already restricted to places that
  all grant the matching need.** `"sitting slumped against a rock"` (giant,
  needs `vast` already, and every `vast` place giant-kin can reach also has
  `ground`), `"sliding slowly across the floor"` / `"dripping water onto
  the floor"` (horror cursed object/furnishing, every reachable band has
  `floor`), `"shedding a spray of rock chips"` and `"trailing waterfalls
  from its floating rock"` (self-referential - the rock is the speaker's
  own body, not a place feature). Checked each against `KIND_POOLS` x
  `PLACE_AFFORDANCES` before deciding, not assumed safe from the wording
  alone.
* **`"banking hard around a spire of rock"` (round XIX's own addition) in
  `"sea of clouds"`, which has no `ground`.** A real gap, but a soft one -
  the other two `sky`-band places (`floating island archipelago`, a
  mountain range) do have visible rock, so this fires wrong at most 1 time
  in 3 for this one situation, and every candidate fix available right now
  either reuses `ground` (which also carries a stance meaning - "the entity
  stands on it" - this situation does not want to assert of an airborne
  ship) or requires a new token whose only user would be this one value.
  Left as a known, bounded soft spot rather than force a fix that either
  overloads an existing token's meaning or adds a token for one line.
* **`#00512`'s bow visibly not rendering as a bow even after XX6** was not
  re-verified by render (fixing it changes which future seeds draw the
  combination; it does not repaint `#00512` itself) - the fix is verified
  by the situation/armament sweep in XX6, not by regenerating this specific
  seed.
* **Situation-vs-pose mismatches with no text contradiction to fix:**
  `#00447` (siege mech shown firing, not "crouching to inspect wreckage"),
  `#00478` (fire drake shown breathing fire, not "snapping at a hurled
  spear"), `#00531` (revenant shown enthroned, not "clawing out of a stone
  coffin"). In each, the situation text is internally coherent and the
  entity's own identity (a mech with flame projectors, a *fire* drake, an
  ancient revenant) supplies a stronger, always-available visual cue than
  the specific momentary action asked for. This is a model fidelity limit
  general to prompt-based image generation, not a pack defect - there is no
  wording change that asks a fire-breathing dragon to reliably not breathe
  fire in one frame. Flagged for the maintainer rather than claimed fixed.
* **`#00596`'s "slumbering... sleeping breaths" tentacled abomination
  rendered wide-eyed and alert.** `"bulging staring eyes"` is a permanent
  anatomical descriptor (the eye *type*), not a state; asking it to also
  read as closed/resting when the situation is dormant would require a
  separate closed-eyes value for exactly this creature family's dormant
  situations, which does not exist yet. Same category as the previous
  bullet - flagged, not fixed blind.
* **`#00594`'s cursed puzzle box, "glistening with fresh dew" while resting
  on a "dusty ledge."** A soft material/condition tension (dew implies damp,
  dust implies dry) rather than a contradiction on the scale of the
  drowned-church-nave case XIX5 fixed; the render itself reads fine. Left
  alone rather than force a rename with no confirmed defect behind it.
* **`#00420`'s "soot-blackened" carrier starship rendering as a clean black
  hull, not visibly charred**, and **`#00448`'s courier drone "shielding a
  suited crewmate" with no crewmate in frame.** Neither is a text
  contradiction - "soot-blackened" is a legitimate (if subtle) condition
  word, and other situations in the pack already name something the frame
  does not have to fully depict (a wreck "towing a disabled shuttlecraft in
  a tractor beam" does not always show the shuttlecraft either). Flagged
  as a possible pattern worth watching, not fixed on a guess.

### Round XX, measured

Full `unittest`/`pytest` suite green (670 tests, 131553 subtests).
`reach_audit.py --pack scifi/fantasy/horror --gate` reports the same
pre-existing gaps as round XIX in fantasy and horror, unchanged by this
round. Sci-fi shows three additional never-drawn situations this round
(`"rising slowly from the ground"`, `"cutting a snarl of cable away with a
manipulator"`, `"lying half-buried under drifted dust"`) beyond round XIX's
six - not a structural regression (the exhaustive, non-sampled `SHADOWED`
check in the same test run is clean; this round's own `ground`/`cold`/
`floor` additions shifted the RNG draw sequence enough that a 12000-seed
sample missed three more rare place-and-situation combinations, the same
`ground-vehicles-read-as-modern`-adjacent sampling-noise class documented
since round XIII). Verified directly rather than assumed: a 5000-seed
sweep of each of fantasy and horror found zero remaining hand-occupancy
conflicts (XX3); an 8000-seed sweep confirmed a bow-carrying hybrid-folk
entity still has 27 distinct situations available after XX6, none of them
the excluded two.
