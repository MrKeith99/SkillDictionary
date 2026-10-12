# The skill model

How a scored line is described so that the same capability is judged and priced
the same way in every challenge, and so that adding a skill or an object next
year is a small, local edit.

---

## The problem it solves

Version 1 of the dictionary gave every scored line one canonical id and one
price. That made drift **visible**, but did not say whether a difference in
price was *justified*. Picking is worth 50, 100, 150 or 300 depending on the
line. Is picking a plate three times harder than picking a mug? Is picking a
T‑shirt from a basket easier than picking a plate? Without a shared description
of difficulty, nobody can answer, and benchmarking a team's "manipulation" score
across challenges compares unlike things.

The league draft (`references/SkillDictionary.pdf`) tries to fix this by naming
every combination: `PickTinyKnown`, `PickHeavyKnown`, `PickLargeUnknown`, … That
grows as *verbs × properties* and still cannot say "heavy **and** slippery
**and** inside the dishwasher".

## Three layers

```
 taxonomy.yaml          WHAT capability            MAN.Pick
      │                 (intent, success, sub-skills)
      ▼
 data/skills/*.yaml     ONE scored line            MAN-PICK-01B4  "Plate"  +100
      │   objects: [plate]
      │   at: [dinner_table]   conditions: {clutter: nearby, knowledge: known_instance}
      ▼
 objects/ +             HOW HARD that line is      D = 6  (thin, flat-lying,
 difficulty_factors.yaml                                    smooth …)
```

| file | answers | changes when |
|---|---|---|
| `data/vocabulary/taxonomy.yaml` | What is this skill for? What does success look like? What must the referee *not* judge? | a new kind of capability appears |
| `data/vocabulary/difficulty_factors.yaml` | Which properties make an instance harder, and by how much? | rarely — TC decision |
| `data/vocabulary/objects/catalog.yaml` | What is each real object: mass, grasp width, surface, rigidity, shape? | a new object enters the league |
| `data/vocabulary/objects/furniture.yaml` | Where skills happen: each place's height and access, and the doors and racks to operate | a new arena, a new appliance |
| `data/vocabulary/objects/set.yaml` | Which objects are in play this year, in which classes and rulebook categories? | every year, from the published object list |
| `data/skills/<AREA>.yaml` | What does this particular line score, on which objects, in which situation, for how many points? | the rulebook changes |

A harder object is **a different difficulty, not a different skill.** The
dictionary stays short because new objects and situations are profiles, not
entries.

---

## Taxonomy nodes

Every dictionary entry has `taxonomy: <node>`. A node is written for a human:

```yaml
MAN.Place:
  name: Place
  intent: >-
    Put a held object down at a target so it stays there, usable and safe —
    as a person would set it down, not drop it.
  success: >-
    Object rests at the target location, stable, in a usable orientation, and
    was released (not thrown or dropped).
  not_judged: Trajectory, speed, whether the object was regrasped.
  composed_of: [OBJ.DetectPlacement]
  factors: [mass, size, rigidity, height, access, placement_tolerance, clutter]
  status: active
```

- **`intent`** — why a household robot needs this. If you cannot write it in
  two sentences, the node is probably two skills.
- **`success`** — the observable end state. This is what makes refereeing
  consistent: every line under `MAN.Place`, in every challenge, is judged
  against the same sentence.
- **`not_judged`** — the mechanism. Scoring *how* rather than *whether*
  penalises unconventional and low-cost robots and asks referees to judge
  technique. This is the existing modifier rule, now stated per skill.
- **`composed_of`** — sub-skills exercised. Not scored by themselves; used to
  attribute failures ("the pick failed in recognition, not in grasping") and to
  benchmark capabilities that are never scored alone.
- **`factors`** — which difficulty factors matter for this skill. Mass matters
  for Pick; it does not matter for Recognize.
- **`status: proposed`** — a future skill with a definition but no scored line
  yet (`MAN.Wipe`, `NAV.Guide`, `PPL.Reidentify`, …). New tasks pick from
  these rather than inventing ad-hoc lines.

Ids are permanent, like `variant_number`. Deprecate, never rename.

### Grasping and the Feix taxonomy

Feix et al. (2016) classify 33 human grasp types; the top-level split is
**power / intermediate / precision**. The model uses that split, but only as a
description of the **demand the object places on a grasp**, never as the
technique the robot must use:

| node | object demand | examples |
|---|---|---|
| `MAN.Grasp.Power` | must be enclosed, load resisted | full milk carton, bag, mug |
| `MAN.Grasp.Intermediate` | held from the side (lateral family) | plate rim, bowl, tray |
| `MAN.Grasp.Precision` | only fits between fingertips | cutlery, dishwasher tab, cloth |

A suction-cup robot that lifts a plate scores the same as a hand using a lateral
pinch.

These nodes are `scored: false`: they decompose `MAN.Pick` and friends for
failure attribution, and no line prices them directly. Objects do not carry a
grasp class — what makes a grasp hard (mass, size, surface, shape) is already
in the object's factors.

---

## Difficulty factors

Twenty-five factors, each with at most three levels weighted 0 / 1 / 2. Two kinds:

- **object factors** — `mass`, `size`, `surface` (friction), `rigidity`,
  `shape`, `contents`, `mechanism`, `actuation_force`. Set once per object in
  `objects/catalog.yaml`. **Mass and size are computed** from `mass_g` and
  `grasp_width_mm` using the factor's numeric cut-offs, so they cannot be rated
  differently by different people; only surface, rigidity and shape are judged.
- **condition factors** — set per line in `conditions:`, from the rulebook's
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
  the condition is a list (`plan_length: [medium, long]`) and the line gets a
  range, exactly like a line over several objects.

Every level has a plain-language guide ("< 1.5 cm — cutlery, plate rim") so a
referee can assign it by looking. The scale is coarse on purpose: a finer one
implies a precision nobody can measure consistently at a competition.

**Intrinsic difficulty D** of a line is the sum of the weights of the factors
its node lists. A line handling several objects has a range, e.g. `D 2–5`.

### D is not `level`

| | `D` (intrinsic) | `level` (empirical) |
|---|---|---|
| describes | the specification | how the field performed |
| computed from | factors | team results |
| changes | when objects or rules change | annually |

When they disagree (T1 lists 26 such lines today), either the factors miss
something — opening the dishwasher is rated `E` by factors but `X` by the field,
which suggests the factors do not yet capture *finding* a handle — or the level
needs revisiting. Both are useful.

---

## What the checker reports

`skilldict check` runs these checks in CI; `skilldict findings` prints the report.

**Errors (fail the build):** unknown node, object, factor or level; a condition
on a factor the node does not use; a penalty without a `failure_mode`; a line
pointing at a decomposition-only node.

**Findings (questions for the TC, not failures):**

| | finding | example today |
|---|---|---|
| T1 | D vs level | `MAN-PICK-01B4` plate: D 7 (`X`) but level `C` |
| T2 | price inversion: a strictly harder line pays strictly less, within one skill | entrance door (D 3) 200 < milk cap (D 2) 400 |
| T3 | one failure mode, many prices | "dropped object" is −40, −50 or −200 |
| T4 | proposed skills, unscored nodes | 13 proposed nodes |
| T5 | object data quality: unmeasured values; lines whose objects span a wide difficulty range | `MAN-PICK-05`: mangosteen D1 to seaweed D8 for the same points |

Bonus and discount lines that name a parent (`related_skill` in the challenge)
are compared at their **effective** price: picking a plate in Pick & Place is
`MAN-PICK-01` + `MAN-PICK-01B4` = 50 + 100. The rulebook already prices object
difficulty this way; the checker makes it explicit and comparable.

`dist/skill_ratings.json` carries every line's node, objects, factors and D for the visualizer and the results tracker.

### Toward a fair price

The model does **not** change any price — that is a rulebook decision. It gives
the TC a basis: within one node, price should rise with D. A simple rule the TC
could adopt is

```
points = base(node) × (1 + D / 4)
```

with `base` set per node. Until then, T2 inversions and the per-node
"price per difficulty point" spread are the measure of how far current sheets
are from consistent.

---

## Recipes

### Score a skill in a new challenge, same objects

Reference an existing dictionary id. Nothing else.

### Same skill, new object

1. Add the object to `data/vocabulary/objects/catalog.yaml`: `mass_g`, `grasp_width_mm`,
   `surface`, `rigidity`, `shape`, and `ycb` if it is a YCB item. Set
   `values:` to `measured` (arena object), `ycb` (YCB published values,
   same kind of item only) or `estimate`.
2. Add it to `data/vocabulary/objects/set.yaml` under its class.
3. If an existing line's category already covers it, nothing else changes —
   the line's difficulty range updates by itself. Otherwise add a dictionary
   line under the existing node.

No new skill, no new verb.

### A new competition year

1. Replace `data/vocabulary/objects/set.yaml` with the new published classes;
   update `source`. The previous year's set stays in its git tag.
2. Re-check `categories` against the new rulebook wording.
3. Add any new objects to the catalog. CI fails on an unknown or empty name.

### A capability the league has never scored

1. Add a node to `taxonomy.yaml` with `status: proposed`, an `intent`, a
   `success` criterion, `not_judged`, and `factors`. Get it reviewed on its
   own — the definition is the hard part.
2. When a task scores it, add the dictionary line and flip the node to
   `active`.

### A new difficulty factor

Rare, and a TC decision: it changes D for every skill that lists it. Add it
with levels and guides, list it on the relevant nodes, and expect T1/T2 to move.
Say so in the PR.

### A new penalty

Pick a `failure_mode`. If none fits, add one to `taxonomy.yaml`
`failure_modes`. Then look at T3: if the same failure is already priced
elsewhere, explain why yours differs.

---

## Known limits

- **Factor weights are uniform across skills.** Clothing scores D 10 for
  `MAN.Pick` because thin + deformable + flat-lying add up, yet grasping cloth is
  comparatively easy; folding it is what is hard. Per-node weights would fix
  this at the cost of a bigger vocabulary. T2's two inversions involving
  `MAN-PICK-03` are this artefact, not drift.
- **Most object values are estimates.** The league's object list has names and
  photos but no masses or sizes. The enamel dishes, cutlery and Pringles can use
  YCB's published values (`values: ycb`); the rest come from photos and product
  specs (`values: estimate`). YCB fruit is plastic, so its masses are not used
  for real fruit. T5 lists both groups; weigh and measure during Setup Days.
- **`PLN.Execute` D only measures plan length.** A GPSR command's real
  difficulty is the skills it draws (pick a cup vs. describe a person), which
  are not known until the test. T1 flags the three `PLN-SOLVECOMMAND` lines for
  this reason; scoring commands per generator category would close the gap.
- **Tier cut points (E ≤ 2, C ≤ 5) are provisional**, like `level` itself.

## Sources

- T. Feix, J. Romero, H.-B. Schmiedmayer, A. M. Dollar, D. Kragic, "The GRASP
  Taxonomy of Human Grasp Types," *IEEE Trans. Human-Machine Systems* 46(1),
  2016.
- League draft skill list, `references/SkillDictionary.pdf`.
