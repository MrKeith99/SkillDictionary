# SkillDictionary

A versioned, machine-checkable skill dictionary for the RoboCup@Home rulebook.

**In force: season 2026** (RuleBook 2026.2, commit `b844d5a`).
**Proposed: season 2027** (built as 2026 + a set of reviewed changes).

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
  skills/<AREA>.yaml          every scored line: definition + price, once
  vocabulary/                 shared by all seasons
    taxonomy.yaml               what each skill is for, its success criterion, its factors
    difficulty_factors.yaml     what makes an instance harder, and by how much
    global_rules.yaml           rulebook §3 rules the challenges refer to
    objects/catalog.yaml        every real object: mass, size, surface, ...
    objects/fixtures.yaml       doors, racks, caps
  seasons/<year>/
    season.yaml                 status (in_force | proposal), rulebook pin, sheet names
    challenges/<slug>.yaml      in force: how each test uses the skills (no points)
    objects.yaml                the year's object set
    changes/*.yaml              proposal: what it changes on its base season
    pricing.yaml                proposal: the pricing rule for new lines

skilldict/                  the Python package — one CLI for everything
  model.py                    seasons, loading, derived fields (used_by, total_score)
  ratings.py                  vocabulary integrity, intrinsic difficulty D
  overlay.py                  proposal season = base + changes
  pricing.py                  the pricing rule and the repricing of a season
  checks/                     schema, integrity, rulebook, findings
  render/                     score sheets (HTML, LaTeX), pricing page, coverage page, PDF
  cli.py

templates/                  page and LaTeX templates the renderers fill in
schema/                     JSON Schema for a skill and a challenge (as written to dist/)
docs/skill-model.md         how skills, objects and difficulty fit together
external/RuleBook           the RuleBook, git submodule pinned to the in-force version

dist/                       GENERATED, committed: JSON for consumers (CommandGenerator)
  *.json, skill_coverage.html   the season in force
  <year>/                       each proposal season, plus its pricing.json
build/                      GENERATED, not committed: sheets, pricing review, PDFs
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
| `make check` | build every season, run every check, write `dist/` |
| `make findings` | the TC findings report for the season in force |
| `make sheets` | score sheets, HTML + rulebook LaTeX → `build/<year>/sheets/` |
| `make prices` | reprice the base season with the proposal's rule → `build/<year>/pricing.html` |
| `make pdf` | official sheet next to the generated one, per challenge → `build/<year>/*.pdf` |
| `make all` | all of the above |

Each target is `python3 -m skilldict <command> [YEAR]`; `python3 -m skilldict
--help` lists the options (one season, one challenge).

### Consuming the data

| file | use |
|---|---|
| `dist/dictionary.json` | every line of the season in force: definition, price, `used_by` |
| `dist/challenges.json` | per challenge: references, counts, dependencies, `total_score` |
| `dist/vocabulary.json` | taxonomy, difficulty factors and object profiles |
| `dist/skill_ratings.json` | per line: taxonomy node, objects, factors, intrinsic difficulty |
| `dist/global_rules.json` | rulebook §3 rules |
| `dist/viz_data.json` | flattened rows + area matrix + drift, for the visualizer |
| `dist/2027/…` | the same files for the 2027 proposal, plus `gpsr_commands.json` (value of every generator command) and `pricing.json` (every 2026 line under the 2027 rule) |

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

A skill is described by four facets rather than a flat name:

| facet | meaning | example |
|---|---|---|
| `area` | capability area (Roadmap Table 1) | `MAN` |
| `skill` | canonical verb — the extensible axis | `Pick` |
| `modifiers` | object/environment properties | `[known, transport]` |
| `variant_number` + `level` | permanent id + difficulty (E/C/X) | `01`, `C` |

`modifiers` describe the *object and environment*, never grasp technique or
hardware method. Scoring how a robot achieves something rather than whether it
did penalises unconventional and low-cost builds, and forces referees to judge
mechanism instead of outcome.

Every line also says **what capability** it scores and **how hard** that
instance is, so the same skill is judged and compared the same way in every
challenge:

```yaml
- id: MAN-PICK-01B4
  taxonomy: MAN.Pick          # data/vocabulary/taxonomy.yaml: intent, success criterion,
                              #   what the referee must not judge, factors
  description: Plate
  objects: [plate]            # data/vocabulary/objects/ + the season's objects.yaml
  conditions:                 # data/vocabulary/difficulty_factors.yaml
    reach: table
    clutter: nearby
    knowledge: known_instance
```

A harder object is a different *difficulty*, not a different skill, so the
dictionary does not grow as verbs × properties. A condition may be a list of
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

Unlike `variant_number`, which is permanent, **`level` is reassigned annually
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
  area: MAN
  skill: Pick
  variant_number: '01'
  taxonomy: MAN.Pick
  modifiers: [known, transport]
  description: Picking up an object for transportation
  level: C
  points: 50            # priced here, and only here
  type: achievement
```

A **challenge** is usage — how one test employs that skill:

```yaml
# data/seasons/2026/challenges/pick_and_place.yaml
- ref: MAN-PICK-01      # reference, never a redefinition
  count: 12             # how many times this test scores it
  section: Picking
  assistance:
    permitted: true
    extra_penalty_ref: GEN-HUMANASSIST-02P
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

## Seasons and proposals

A **season in force** describes the rulebook exactly as published; the
RULEBOOK check proves it line by line against the pinned `.tex` sheets.

A **proposal season** is never a copy. It names its `base` season and lists
its changes in `changes/*.yaml` — edit a line, add lines, replace a whole
challenge, swap a line in a challenge, add a line to challenges. Each change
file starts with the reasoning, so the TC reviews the change and its reason
together. New lines without explicit points are priced by the season's
`pricing.yaml`, whose skill bases are calibrated on the base season, so a
proposal can never shift the price of an existing skill by accident.
See the docstring of [skilldict/overlay.py](skilldict/overlay.py) for the keys.

When the rulebook adopts a proposal, the season becomes `in_force`: its
challenges are materialised into `seasons/<year>/challenges/`, the skills in
`data/skills/` are updated, and the submodule pin moves.

---

## Checks

`make check` runs, for every season:

| stage | fails on |
|---|---|
| **data** | unknown taxonomy node, object, factor or level; a factor that does not apply to the skill; a penalty without a failure mode |
| **integrity** | a challenge naming an unknown line or carrying a price; a stale `*_ref`; a reused `variant_number`; an unused line in the season in force (a proposal reports its retired lines instead) |
| **schema** | a skill or challenge, as written to `dist/`, violating the JSON Schema |
| **rulebook** | (season in force) any scored line or total that differs from the rulebook's `.tex` sheet |

then writes `dist/`. For the season in force it also prints the **findings**:
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
4. **`MAN-APPLIANCE-02` bundles open and close** with different preconditions.
   Should probably split.

---

## ID stability

`variant_number` is permanent: the TC cites ids in writing. A merged line keeps
the surviving id; the retired id is never reused for something else. The
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
