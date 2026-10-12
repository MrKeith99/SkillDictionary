# SkillDictionary

A versioned, machine-checkable skill dictionary for the RoboCup@Home rulebook.

**This tree: 2027 draft** — the rulebook 2026.2 (RuleBook commit `b844d5a`)
plus the changes proposed for 2027 ([docs/changes-2027.md](docs/changes-2027.md)).
Earlier releases are git tags: `2026.2` is the dictionary exactly as that
rulebook was published.

---

## Why this exists

Two benchmarking problems in the rulebook motivated this work.

**1. Cross-challenge score drift.** The same subtask is priced differently in
different challenges. Because each scoresheet defines its own lines
independently, nothing detects it when picking an object is worth 50 points in
one test and 300 in another. Scores stop being comparable across tests, and
across years.

**2. GPSR referee subjectivity.** The GPSR task is generated at runtime, so there
is no fixed rubric to score against and referees necessarily improvise.

Both problems have the same root cause: *skills are redefined in every place they
are used.* This repo fixes that by defining each skill **once**, pricing it
**once**, and having challenges **reference** it.

The critical property is structural. Challenge files have no `points` field at
all, and the JSON Schema forbids adding one (`additionalProperties: false`). A
challenge therefore *cannot* express a price of its own — drift is not merely
discouraged, it is unrepresentable.

This is the direction the league has already argued for. Matamoros et al.
(arXiv:1902.00758) names referee subjectivity and cross-year incomparability
explicitly; Amigoni et al. (IEEE RAM 22(3), 2015) diagnoses @Home's score
coupling; the faceted schema follows Johannsmeier et al. (Nature MI, 2025).

---

## Layout

```
data/                       SOURCE — the only place you edit
  release.yaml                which year this is, draft | in_force, the rulebook it is checked against
  skills/<AREA>.yaml          every scored line: definition + price, once
  challenges/<slug>.yaml      how each test uses the skills (references, counts; no points)
  vocabulary/
    taxonomy.yaml               what each skill is for, its success criterion, its factors
    difficulty_factors.yaml     what makes an instance harder, and by how much
    global_rules.yaml           rulebook §3 rules the challenges refer to
    objects/catalog.yaml        every real object: mass, size, surface, ...
    objects/furniture.yaml      the arena: every place's height and access, doors and racks
    objects/set.yaml            the year's object set

skilldict/                  the Python package — one CLI for everything
  model.py                    loading, derived fields (used_by, total_score)
  commands.py                 GPSR: value every generator command, fill step counts
  ratings.py                  vocabulary integrity, intrinsic difficulty D
  checks/                     schema, integrity, rulebook, findings
  render/                     score sheets (HTML, LaTeX), coverage page, PDF
  cli.py

templates/                  page templates the renderers fill in
schema/                     JSON Schema for a skill and a challenge (as written to dist/)
docs/                       skill-model.md (how it fits together), changes-<year>.md (why)
external/RuleBook           the RuleBook, git submodule pinned to the rulebook in release.yaml

dist/                       GENERATED, committed: JSON for consumers (CommandGenerator)
build/                      GENERATED, not committed: sheets, PDFs
```

Everything under `dist/` and `build/` is regenerated; never edit it.

---

## Usage

Requires Python 3 with `pyyaml` and `jsonschema`, the RuleBook submodule, and —
for `make pdf` only — `latexmk` with a TeX distribution.

```sh
git submodule update --init --recursive
pip install pyyaml jsonschema
make check       # the CI gate: must end with ALL CHECKS PASSED
```

| command | does |
|---|---|
| `make check` | build, run every check, write `dist/` |
| `make findings` | the TC findings report |
| `make sheets` | score sheets, HTML + rulebook LaTeX → `build/sheets/` |
| `make pdf` | rulebook sheet next to the generated one, per challenge → `build/*.pdf` |
| `make all` | all of the above |

Each target is `python3 -m skilldict <command>`; `python3 -m skilldict --help`
lists the options.

### Consuming the data

| file | use |
|---|---|
| `dist/dictionary.json` | every line: definition, price, `used_by` |
| `dist/challenges.json` | per challenge: references, counts, dependencies, `total_score` |
| `dist/vocabulary.json` | taxonomy, difficulty factors and object profiles |
| `dist/skill_ratings.json` | per line: taxonomy node, objects, factors, intrinsic difficulty |
| `dist/global_rules.json` | rulebook §3 rules |
| `dist/viz_data.json` | flattened rows + area matrix + drift, for the visualizer |
| `dist/gpsr_commands.json` | the value of every command the GPSR generator can produce |

`used_by` and `total_score` are **derived** by the build; the sources never
carry them, so they cannot go stale.

### Skill coverage visualizer

`dist/skill_coverage.html` is a self-contained page — no external scripts, works
offline — showing the area × challenge point matrix, cross-challenge price drift,
and every scored line with filters. Click an area row or challenge column to
toggle it; challenge and area chips combine (union within an axis, intersection
across); tick lines to total an arbitrary subset. It is rebuilt by
`make check` from `templates/viz.html`; edit the template, never the output.

---

## How a skill is described

A line's id says which skill it scores: `<AREA>-<code>-<NN>[B|P<n>]`.

| part | meaning | example |
|---|---|---|
| `AREA` | capability area (Roadmap Table 1) | `MAN` |
| `code` | short code of the taxonomy node — the skill | `OPERATE` = MAN.OperateArticulated |
| `NN` | the line's number within that skill | `02` (the dishwasher door) |
| `B` / `P` (`B1`, `P2`, …) | a bonus / penalty on line `NN` | `MAN-PICK-01B3` — the plate bonus on pick 01 |

CI checks that the code matches the line's `taxonomy:`. `area`, `skill` and
`variant_number` are derived from the id (and still written to `dist/`).
`modifiers` add object/environment properties to the description, and `level`
rates the line E/C/X.

`modifiers` describe the *object and environment*, never grasp technique or
hardware method. Scoring how a robot achieves something rather than whether it
did penalises unconventional and low-cost builds, and forces referees to judge
mechanism instead of outcome.

Every line also says **what capability** it scores and **how hard** that
instance is, so the same skill is judged and compared the same way in every
challenge:

```yaml
- id: MAN-PICK-01B3
  taxonomy: MAN.Pick          # data/vocabulary/taxonomy.yaml: intent, success criterion,
                              #   what the referee must not judge, factors
  description: Plate
  objects: [plate]            # data/vocabulary/objects/catalog.yaml + set.yaml
  at: [dinner_table]          # data/vocabulary/objects/furniture.yaml: height, access
  conditions:                 # data/vocabulary/difficulty_factors.yaml
    clutter: nearby
    knowledge: known_instance
```

A harder object or a harder place is a different *difficulty*, not a different
skill, so the dictionary does not grow as verbs × properties. A line naming a
piece of furniture (`at: [cabinet]`) covers all its places — bottom to top
shelf — and gets a difficulty range, like an object category. A condition may be a list of
levels when it is drawn at test time (GPSR commands, restaurant orders); the
line then has a difficulty range. Full explanation:
**[docs/skill-model.md](docs/skill-model.md)**.

### Difficulty levels

`level` rates how hard a skill is **for the field**, not what it is worth, and
is independent of `points`.

| level | meaning |
|---|---|
| `E` | Entry — most teams achieve it reliably |
| `C` | Competent — typical of the mid-field |
| `X` | Expert — few teams manage it |
| `-` | not a robot capability (assistance, administrative) |

Unlike the id, which is permanent, **`level` is reassigned annually
from empirical team performance**. A frozen id with a moving level is what makes
year-over-year comparison possible.

> **Provisional.** No quantitative threshold separates the tiers yet; the
> values were inherited from the original extraction. Finding T1 compares each
> level with the intrinsic difficulty D.

### Skills and challenges

A **skill** is specification — what it is and what it is worth:

```yaml
# data/skills/MAN.yaml
- id: MAN-PICK-01
  taxonomy: MAN.Pick
  modifiers: [known, transport]
  description: Picking up an object for transportation
  level: C
  points: 50            # priced here, and only here
  type: achievement
```

A **challenge** is usage — how one test employs that skill:

```yaml
# data/challenges/pick_and_place.yaml
- ref: MAN-PICK-01      # reference, never a redefinition
  count: 12             # how many times this test scores it
  section: Picking
  assistance:
    permitted: true
    extra_penalty_ref: GEN-ASSIST-02P
```

There is no `points` field, and there cannot be one.

### Assistance is forfeiture, not penalty

§3.7.2 makes an assisted task element score **zero** unless the task description
says otherwise. A dependency going unmet does *not* block downstream points,
because assistance can satisfy the precondition — if the referee opens the
dishwasher door the robot forfeits those 400 points, but "correctly in the
dishwasher" (3×70) stays fully available. Hence `blocking` and
`satisfiable_by_assistance` are separate fields, and
`assistance.blocks_dependents` defaults to false.

---

## Releases

The tree describes one release, set in `data/release.yaml`. Earlier releases
are git tags (`2026.2`), so `git diff 2026.2 -- data/` shows every change and
`git checkout 2026.2` brings back any earlier dictionary.

While `status: draft`, the tree proposes the next rulebook: the rulebook stage
of `make check` lists every difference from the pinned rulebook's sheets — that
list *is* the proposal — and [docs/changes-2027.md](docs/changes-2027.md) says
why each one is there. Once the rulebook is published and pinned, the release
goes `status: in_force` and any difference fails CI.

---

## Checks

`make check` runs:

| stage | fails on |
|---|---|
| **data** | unknown taxonomy node, object, factor or level; a factor that does not apply to the skill; a penalty without a failure mode |
| **integrity** | a challenge naming an unknown line or carrying a price; a stale `*_ref`; a line no challenge uses (an id whose code does not match its node fails at load) |
| **schema** | a skill or challenge, as written to `dist/`, violating the JSON Schema |
| **rulebook** | when `in_force`: any scored line or total that differs from the rulebook's `.tex` sheet (when `draft`, the differences are listed, not failed) |

then writes `dist/` and prints the **findings**:
questions for the TC, never failures.

| finding | asks |
|---|---|
| T1 | intrinsic difficulty vs empirical level |
| T2 | price inversions: a strictly harder line of a skill pays less |
| T3 | one failure mode priced differently across challenges |
| T4 | taxonomy coverage: proposed skills, unscored nodes |
| T5 | object data quality: estimated values, widest difficulty ranges |
| A1–A3 | assistance: hard gates, unspecified costs, unlisted assistance |
| A4 | dependencies on lines that do not exist yet |
| A5 | sibling variants of a skill priced differently across challenges |
| A6 | ambiguities flagged in the challenge files |
| A7 | autonomously-available vs raw points, per challenge |

### Known open questions

Highest priority, all surfaced by finding A6:

1. **Percentage vs fixed-point conflict (4 lines).** §3.7.4 prices ASR bypass as a
   percentage of maximum attainable; every scoresheet prices it in fixed points,
   and they disagree badly (GPSR custom operator −60 on sheet vs −149 under
   §3.7.4). Is §3.7.4 a floor, a ceiling, or superseded?
2. **Laundry / Pick&Place asymmetry.** Washing-machine-door assistance is unpriced
   (so §3.7.2 makes it cost 300) while the structurally identical dishwasher-door
   assistance is explicitly −0.
3. **HRI bag-on-structure.** §5.1 rule 5 says no points awarded *and* the sheet
   applies −50. Forfeiture plus penalty, or penalty only?
4. **`MAN-OPERATE-02` bundles open and close** with different preconditions.
   Should probably split.

---

## ID stability

Within a release an id is permanent: the TC cites ids in writing. A merged line
keeps the surviving id; the retired id is never reused for something else.
Ids were renumbered once, for 2027, so that each names its skill; the 2026.2
ids are in the `2026.2` tag. The
pre-dictionary per-challenge extraction and its id mapping are in the git
history (before commit `45a982e`), not in the tree.

---

## Contributing

See **[CONTRIBUTING.md](CONTRIBUTING.md)**. The short version: edit `data/`,
run `make check`, commit the source **and** the regenerated `dist/`.

---

## License

Two parts, mirroring the RuleBook:

- **`skilldict/`, `templates/`, `schema/`** — BSD 3-Clause ([LICENSE.BSD-3-Clause](LICENSE.BSD-3-Clause))
- **`data/`, `dist/`** — CC BY-SA 4.0 ([LICENSE.CC-BY-SA-4.0](LICENSE.CC-BY-SA-4.0))

The content files derive from the RoboCup@Home RuleBook, which is CC BY-SA 4.0.
Skill descriptions and point values come from its scoresheets, so share-alike
carries over — that content cannot be relicensed. The rulebook itself is not
redistributed here; it is a pinned submodule. See [LICENSE](LICENSE).
