# The skill model

How a skill and its variants are described so that the same capability is judged and priced
the same way in every challenge, and so that adding a skill or an object next
year is a small, local edit.

---

## The problem it solves

Version 1 of the dictionary gave every scored line of a sheet one canonical
id and one price. That made drift **visible**, but did not say whether a difference in
price was *justified*. Picking is worth 50, 100, 150 or 300 depending on the
line. Is picking a plate three times harder than picking a mug? Is picking a
T‑shirt from a basket easier than picking a plate? Without a shared description
of difficulty, nobody can answer, and benchmarking a team's "manipulation" score
across challenges compares unlike things.

The league's draft skill list tries to fix this by naming
every combination: `PickTinyKnown`, `PickHeavyKnown`, `PickLargeUnknown`, … That
grows as *verbs × properties* and still cannot say "heavy **and** slippery
**and** inside the dishwasher".

## Three layers

```
 data/skills.yaml       SKILL: what capability      MAN.Pick
      │                 (intent, success, factors, failures)
      ▼
 data/variants/*.yaml   VARIANT: one priced         MAN-PICK-08  "Plate"  170
      │                 instance of the skill
      │   objects: [plate]
      │   at: [dinner_table]   conditions: {clutter: nearby, knowledge: known_instance}
      ▼
 vocabulary/            HOW HARD that variant is    D = 7  (thin, flat-lying,
 difficulty_factors.yaml                                     smooth …)
```

| file | answers | changes when |
|---|---|---|
| `data/skills.yaml` | What is this skill for? What does success look like? What must the referee *not* judge? | a new kind of capability appears |
| `data/vocabulary/difficulty_factors.yaml` | Which properties make an instance harder, and by how much? | rarely — TC decision |
| `data/vocabulary/objects.yaml` | What is each real object: mass, grasp width, surface, rigidity, shape? | a new object enters the league |
| `data/vocabulary/furniture.yaml` | Where skills happen: each place's height and access, and the doors and racks to operate | a new arena, a new appliance |
| `data/vocabulary/object_set.yaml` | Which objects are in play this year, in which classes and rulebook categories? | every year, from the published object list |
| `data/variants/<AREA>.yaml` | Which variant of a skill is scored: on which objects, where, in which situation, for how many points? | the rulebook changes |

A harder object is **a different difficulty, not a different skill.** The
dictionary stays short because new objects and situations are profiles and
variants, not new skills. A challenge (`data/challenges/`) only references
variants: which ones it scores, how often, and what help is allowed. It has no
`points` field, and the schema forbids one, so a challenge cannot price a
variant of its own.

### Ids

A variant's id says which skill it is a variant of:

| part | meaning | example |
|---|---|---|
| `AREA` | capability area (Roadmap Table 1) | `MAN` |
| `code` | the skill's code: the last word of its id | `FIXTURE` = MAN.OperateFixture |
| `NN` | the variant's number within that skill | `02` (opening the dishwasher door) |
| `B` (`B1`, `B2`, …) | a bonus on variant `NN` | `MAN-FOLD-01B1`, the first-garment bonus |
| `-<FAILURE>` | a penalty on that variant, named by the failure's code; written by the build | `MAN-PICK-01-DROP` |
| `P` | a conduct penalty, not tied to one variant | `HRI-ATTEND-01P` |

Loading fails when the code does not match the variant's `skill:`. `area` and
`variant_number` are derived from the id, never written. Ids are permanent: the
TC cites them in writing, so a retired id is never reused. Ids were renumbered
once, for 2027, so that each names its skill; the 2026.2 ids are in the
`2026.2` tag.

---

## Skills

Every variant has `skill: <skill>`. A skill is written for a human:

```yaml
MAN.Place:
  intent: >-
    Put a held object down at a target so it stays there, usable and safe —
    as a person would set it down, not drop it.
  success: >-
    Object rests at the location the robot chose or was told, stable, in a
    usable orientation, and was released (not thrown or dropped). Choosing the
    right location is OBJ.DetectPlacement, scored on its own.
  not_judged: Trajectory, speed, whether the object was regrasped.
  composed_of: [OBJ.DetectPlacement]
  factors: [mass, size, rigidity, stability, height, access, placement_tolerance, clutter, knowledge]
  failures: [drop]
  base: 29
  status: active
```

- **`intent`** — why a household robot needs this. If you cannot write it in
  two sentences, the skill is probably two skills.
- **`success`** — the observable end state. This is what makes refereeing
  consistent: every variant under `MAN.Place`, in every challenge, is judged
  against the same sentence.
- **`not_judged`** — the mechanism. Scoring *how* rather than *whether*
  penalises unconventional and low-cost robots and asks referees to judge
  technique.
- **`composed_of`** — sub-skills exercised. Not scored by themselves; used to
  attribute failures ("the pick failed in recognition, not in grasping") and to
  benchmark capabilities that are never scored alone.
- **`factors`** — which difficulty factors matter for this skill. Mass matters
  for Pick; it does not matter for Recognize.
- **`failures`** — the failure modes every variant of the skill can be
  penalised for (see *Penalties*).
- **`base`** — what the league pays for the skill at D 0 (see *Price*).
- **`status: proposed`** — a future skill with a definition but no scored variant
  yet. New tasks pick from these rather than inventing ad-hoc variants. None
  are open while the dictionary is consolidated; future skills are proposed
  after.

Skill ids are permanent, like variant ids. Deprecate, never rename. The id is
all a skill is called: its name (`MAN.OpenContainer` → "Open container") and
its code, the last word (`CONTAINER`), which names its variants
(`<AREA>-<code>-<NN>`), are derived from it, so choose the id so both read
well.

### Grasping

`MAN.Grasp` is `scored: false`: it names the grasp inside `MAN.Pick`,
`MAN.Pour`, `MAN.Fold` and `HRI.Handover` (`composed_of`), and no variant
prices it. There is no grasp class (Feix et al. 2016: power / intermediate /
precision): what makes a grasp hard (mass, size, surface, shape) is already in
the object's factors, and the technique is never judged. A suction-cup robot
that lifts a plate scores the same as a hand using a lateral pinch.

---

## Difficulty factors

Thirty-two factors, each with at most three levels weighted 0 / 1 / 2. Three kinds:

- **object factors** — `mass`, `size`, `surface` (friction), `rigidity`,
  `shape` (is there somewhere to hold it), `stability` (does it stay where it
  is put), `contents`; for clothing `garment` (flat / tubular / limbed) and
  `spread`; for fixture parts (doors, racks) `handle` and `return_force`; for
  container closures `opening` (lift / twist / pry) and `counterpart`; and
  `actuation_force`. Set once per object in `objects.yaml`
  (fixture parts in `furniture.yaml`). **Mass and size are computed** from
  `mass_g` and `grasp_width_mm` using the factor's numeric cut-offs, so they
  cannot be rated differently by different people; the rest are judged.
- **place factors** — `height` (computed from `height_mm`) and `access`, set
  per place in `furniture.yaml`; a variant names its places in `at:`.
- **condition factors** — set per variant in `conditions:`, from the rulebook's
  description of the setup:

  | factor | used mainly by | levels (0 / 1 / 2) |
  |---|---|---|
  | `height`, `access` (from the place, `at:`) | MAN | furniture.yaml |
  | `clutter`, `placement_tolerance`, `carrier` | MAN | see file |
  | `knowledge` | MAN, OBJ, NLU — objects, sounds, names | known instance / known class / unknown |
  | `map_knowledge`, `route_extent`, `obstacle_visibility` | NAV | mapped→unknown; room→building; large→hard to see |
  | `crowd` | NAV, PPL, HRI | none / few / crowd |
  | `perception_range` | OBJ, PPL | near / room / far |
  | `target_motion` | PPL, HRI | static / shifting / walking |
  | `distractors` | OBJ, PPL, HRI | none / few / similar |
  | `ambient_noise` | NLU, HRI, OBJ.DetectEvent | quiet / background / loud |
  | `input_variability` | NLU, PLN | fixed / paraphrase / open |
  | `info_load` | NLU, HRI, PPL | 1 / 2–3 / 4+ items |
  | `retention` | HRI, PPL | immediate / later in task / across tasks |
  | `plan_length` | PLN | 1–2 / 3–4 / 5+ skills |

  When the level is drawn at test time — a GPSR command, a restaurant order —
  the condition is a list (`plan_length: [medium, long]`) and the variant gets a
  range, exactly like a variant over several objects.

Every level has a plain-language guide ("< 1.5 cm — cutlery, plate rim") so a
referee can assign it by looking. The scale is coarse on purpose: a finer one
implies a precision nobody can measure consistently at a competition.

**Intrinsic difficulty D** of a variant is the sum of the weights of the factors
its skill lists. A variant handling several objects has a range, e.g. `D 2–5`.

### D is the only difficulty

There is no hand-set grade next to D. A variant that teams find harder than its D
says is a missing factor, and the fix is the factor: door handles and
self-closing doors (`handle`, `return_force`), holding a soft carton while
twisting its cap (`counterpart`), sleeves and trouser legs (`garment`) all
entered the model that way.

---

## Price

Within one skill, price rises with D. Every achievement variant pays

```
points = base(skill) × (1 + D / 4)
```

with `base` set per skill (`base:` in `data/skills.yaml`), rounded to 10 (to 5
below 50), halves away from zero; D is the variant's easiest instance. A base is
the median over the skill's 2026.2 lines of price ÷ (1 + D/4), so the league's
level per skill is kept. A harder object or place is its own variant, priced at
its own D: picking a plate is `MAN-PICK-08`, not a bonus on a generic pick.
Bonuses are kept for what D does not measure (a first pick, a goal reached) and
are not priced by the rule.

## Penalties

Penalties are not written per challenge. `failure_modes` in `data/skills.yaml`
defines each failure once, with its share; a skill lists the failures all its
variants can suffer (`failures:`), and a variant may add its own. The build
writes each as a penalty variant under every variant in every challenge:
`MAN-PICK-08-DROP` is 0.5 × 170 = −85, rounded to −90. Conduct failures (not
attending, unsafe contact) are not tied to one action, so they are fixed-price
variants added to every challenge.

A penalty charges only for harm or a shortcut. A wrong step is simply not paid;
charging it as well would count one mistake twice.

## Assistance

§3.7.2: an assisted task element scores zero. Here assistance also costs half
the element (the `assistance` failure mode), unless the challenge makes it
free (`extra_penalty: 0`). An entry has `assistance.permitted: true` only
where the rulebook's task description allows that help (§3.7.1); if the
proposal needs help the rulebook does not list, the fix is an issue on the
RuleBook repo.

Assistance forfeits only the assisted line: if the referee opens the
dishwasher door, the robot loses `MAN-FIXTURE-02` (220) and pays half of it,
but placing in the dishwasher (3 × 70) stays available.

## What the checker reports

`skilldict check` runs these checks in CI; `skilldict findings` prints the report.

**Errors (fail the build):** unknown skill, object, factor or factor level; a condition
on a factor the skill does not use; a penalty without a `failure_mode`; a variant
pointing at a decomposition-only skill.

**Findings (questions for the TC, not failures):**

| | finding | example today |
|---|---|---|
| T1 | price rule: an achievement that does not pay `base × (1 + D/4)` | none |
| T2 | penalties per failure mode: derived at the share, authored conduct penalties listed | ignoring the person −100, unsafe contact −200 |
| T3 | proposed skills, unscored skills | none while the dictionary is consolidated |
| T4 | object data: objects and places in use; variants whose objects span a wide difficulty range | `MAN-PICK-05`: mangosteen D1 to seaweed D8 for the same points |

`dist/variant_difficulty.json` carries every variant's skill, objects, factors and D for the scoring page and the results tracker.

---

## Recipes

### Score a skill in a new challenge, same objects

Reference an existing dictionary id. Nothing else.

### Same skill, new object

1. Add the object to `data/vocabulary/objects.yaml`: `mass_g`, `grasp_width_mm`,
   `surface`, `rigidity`, `shape`, and a `note` saying where the numbers come
   from when it is a YCB item or a product spec.
2. Add it to `data/vocabulary/object_set.yaml` under its class.
3. If an existing variant's category already covers it, nothing else changes —
   the variant's difficulty range updates by itself. Otherwise add a variant
   under the existing skill.

No new skill, no new verb.

### A new competition year

1. Replace `data/vocabulary/object_set.yaml` with the new published classes;
   update `source`. The previous year's set stays in its git tag.
2. Re-check `categories` against the new rulebook wording.
3. Add any new objects to the catalog. CI fails on an unknown or empty name.

### A capability the league has never scored

1. Add a skill to `data/skills.yaml` with `status: proposed`, an `intent`, a
   `success` criterion, `not_judged`, and `factors`. Get it reviewed on its
   own — the definition is the hard part.
2. When a task scores it, add the variant and flip the skill to
   `active`.

### A new difficulty factor

Rare, and a TC decision: it changes D for every skill that lists it. Add it
with levels and guides, list it on the relevant skills, and expect T1 to move.
Say so in the PR.

### A new penalty

Penalties are not written per task. Decide who can fail this way: every variant
of a skill (add the failure to the skill's `failures:` in `data/skills.yaml`) or
one variant (its `failures:` in `data/variants/`). If no failure mode fits, add one
to `failure_modes`, with the share of the variant it costs. The build writes the
penalty under every such variant in every challenge.

---

## Known limits

- **Factor weights are uniform across skills.** Clothing scores D 11 for
  `MAN.Pick` because thin + deformable + flat-lying add up, yet grasping cloth is
  comparatively easy; folding it is what is hard. Per-skill weights would fix
  this at the cost of a bigger vocabulary.
- **Object and furniture values are approximations.** The league's object
  list has names and photos but no masses or sizes. The enamel dishes, cutlery
  and Pringles use YCB's published values (their notes say so); the rest come
  from photos and product specs, and furniture heights are typical for the
  type. They are measured on the day; D only needs the right level, not the
  exact number.
- **No empirical check on D yet.** D is reviewed, not measured. Success rates
  per variant from competition results would show where a factor is still
  missing.

## Sources

- T. Feix, J. Romero, H.-B. Schmiedmayer, A. M. Dollar, D. Kragic, "The GRASP
  Taxonomy of Human Grasp Types," *IEEE Trans. Human-Machine Systems* 46(1),
  2016.
- League draft skill list (`SkillDictionary.pdf`, circulated by the TC; not in this repo).
