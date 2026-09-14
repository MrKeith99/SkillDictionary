# SkillDictionary

A versioned, machine-checkable skill dictionary for the RoboCup@Home rulebook.

**Target version: 2026.2** (RuleBook commit `b844d5a`).

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

## How it is organised

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

### Difficulty levels

`level` rates how hard a skill is **for the field**, not what it is worth. It is
independent of `points`: `MAN-PLACE-02B1` (correctly in the dishwasher, 70 pts)
is `X` because positioning a dish so the machine can clean it is hard, even
though it pays less than many `C` lines.

| level | meaning | entries | reward lines | their range |
|---|---|---|---|---|
| `E` | Entry — most teams achieve it reliably | 7 | 5 | 10–30 |
| `C` | Competent — typical of the mid-field | 51 | 30 | 15–200 |
| `X` | Expert — few teams manage it | 23 | 17 | 70–800 |
| `-` | not a robot capability (assistance, administrative) | 17 | 0 | n/a |

*Entries* counts every line at that level; *reward lines* counts only
achievements and bonuses, which is where the point range is measured. The
difference is penalty lines, which carry a level but a negative value.

Unlike `variant_number`, which is permanent, **`level` is reassigned annually
from empirical team performance**. When most teams can open a dishwasher door,
that skill moves `X` → `C`. A frozen id with a moving level is what makes
year-over-year comparison possible: the skill identity is stable while its
difficulty rating tracks what the field can actually do.

> **Provisional.** These definitions are descriptive of current usage, not a
> ratified specification. No quantitative threshold separates the tiers, nothing
> validates them, and the values were inherited from the original extraction. A
> `vocabulary/levels.yaml` with empirical criteria (e.g. share of teams scoring
> the line last competition) is the intended home for the real definition and
> needs TC sign-off.

98 canonical skills across 9 areas: MAN 38, GEN 16, NAV 12, HRI 11, NLU 6, PLN 6,
OBJ 3, PPL 3, SPECIAL 3. By type: 41 achievement, 43 penalty, 11 bonus,
3 administrative.

### The two halves

The **dictionary** is specification — what a skill is and what it is worth:

```yaml
# dictionary/MAN.yaml
- id: MAN-PICK-01
  area: MAN
  skill: Pick
  variant_number: '01'
  modifiers: [known, transport]
  description: Picking up an object for transportation
  level: C
  points: 50            # priced here, and only here
  type: achievement
```

A **challenge** is usage — how one test employs that skill:

```yaml
# challenges/pick_and_place.yaml
- ref: MAN-PICK-01      # reference, never a redefinition
  count: 12             # how many times this test scores it
  section: Picking
  depends_on:
    - ref: OBJ-RECOGNIZE-01
      nature: informational
      blocking: false
      satisfiable_by_assistance: true
  assistance:
    permitted: true
    extra_penalty_ref: GEN-HUMANASSIST-02P
```

Note there is no `points` field, and there cannot be one.

### Assistance is forfeiture, not penalty

§3.7.2 makes an assisted task element score **zero** unless the task description
says otherwise. This is easy to model wrongly. A dependency going unmet does
*not* block downstream points, because assistance can satisfy the precondition —
if the referee opens the dishwasher door the robot forfeits those 400 points, but
"correctly in the dishwasher" (3×70) stays fully available.

Hence `blocking` and `satisfiable_by_assistance` are separate fields, and
`assistance.blocks_dependents` defaults to false.

---

## Layout

```
extraction/    per-challenge extractions from the scoresheets — the build SOURCE
external/      RuleBook git submodule, pinned @ 2026.2 (see external/README.md)
dictionary/    one file per area — owns definition + points
challenges/    references dictionary by id; NO points field
vocabulary/    global_rules.yaml (§3.7 assistance, §3.7.4 ASR ladder, §3.8.2 DQ)
schema/        JSON Schema, enforced in CI
tools/         merge, validate, reconcile, schema + scoresheet checks, ci.sh
dist/          GENERATED, committed so CommandGenerator can consume by raw URL
```

---

## Usage

Requires Python 3 with `pyyaml` and `jsonschema`, plus the RuleBook submodule:

```sh
git submodule update --init --recursive
pip install pyyaml jsonschema
tools/ci.sh      # rebuild + schema + scoresheets + reconcile + validate
```

Run it after any edit. It must print `ALL CHECKS PASSED`.

**`dist/` is generated — never edit it.** Edit `dictionary/` and `challenges/`,
then regenerate. `dist/*.json` is committed so external consumers (the
CommandGenerator) can fetch it by raw URL.

### Consuming the data

| file | use |
|---|---|
| `dist/dictionary.json` | all 98 skills, canonical definitions and prices |
| `dist/challenges.json` | per-challenge references, counts, dependencies |
| `dist/viz_data.json` | flattened rows + area matrix + drift, for the visualizer |
| `dist/id_migration.csv` | legacy id → canonical id, for anything citing old ids |

### Skill coverage visualizer

`dist/skill_coverage.html` is a self-contained page — no external scripts, no
network, works offline — showing the area × challenge point matrix,
cross-challenge price drift, and every scored line with filters. Open it
directly in a browser.

The matrix is both a control and a view: click an area row or a challenge column
header to toggle it. Selected rows are highlighted and unselected ones dim, but
**every row stays visible and clickable** so you can add a second area — and
totals, bars and the column footer recompute to the selection. A scope line
reports what is in scope and offers a reset. It shares state with the chips
below, so the two always agree.

The standing observation under the matrix is computed from the full dataset, not
the filtered view, so narrowing the table never rewrites the finding.

The challenge and area filters are **multi-select**: chips combine, so Laundry +
Restaurant shows both, and adding MAN + NAV narrows that to those areas within
them (union within an axis, intersection across the two). The *All* chip clears
its own axis.

In the scored-line table, tick individual lines to build an arbitrary subset:
the bar above shows how many are selected, their available and net points, and
the area breakdown. Selections survive changing the challenge/area filters, so a
set can be assembled across challenges. *Show only selected* narrows the table to
it. Selection is per-session and clears on reload.

It is **generated**, so it never goes stale:

```
tools/viz_template.html   the page, with a __DATA__ placeholder
       ↓  tools/build_viz_data.py  (stage 2 of ci.sh)
dist/viz_data.json        derived from dist/dictionary.json + challenges.json
dist/skill_coverage.html  template + data inlined
```

Edit `dictionary/` or `challenges/`, run `tools/ci.sh`, and the page rebuilds
with the new numbers — including the recomputed matrix totals. Edit the template
to change the design; never edit `dist/skill_coverage.html` directly.

The Google Sheets results tracker joins on skill `id`. **43 ids changed spelling
during the merge**, so use `id_migration.csv` before the next sync.

Note the dictionary holds *specification only*. Per-team, per-year results are
observational and live in the tracker, joined on `id`. Do not add normalisation
or year-over-year progress fields here.

---

## Contributing

See **[CONTRIBUTING.md](CONTRIBUTING.md)** for the full workflow, branch
conventions, controlled vocabularies and review expectations.

The short version:

```sh
pip install pyyaml jsonschema
tools/ci.sh          # must print ALL CHECKS PASSED
```

Edit `dictionary/` and `challenges/`, never `dist/`. Commit the regenerated
`dist/` alongside your source edits.

Four rules CI enforces:

- **Never put `points` in a challenge file.** Price belongs to the skill, once.
- **Never reuse or reassign a `variant_number`.** The TC cites ids in writing.
- **Modifiers describe objects and environments**, not grasp technique or hardware.
- **Every dictionary entry must be referenced** by at least one challenge.

A price change is a **rulebook change** — it goes to the RuleBook repo first.
Merging two differently-priced skills invents a price the TC never approved;
leave them distinct and let CHECK 5 report the drift.

---

## Checks

`tools/ci.sh` runs six stages. All must pass.

**`check_scoresheets.py`** — the dictionary vs the **rulebook itself**. Parses
`external/RuleBook/scoresheets/*.tex` from the pinned submodule and diffs every
scored line. This is the only check that catches the extraction going stale when
the TC edits a scoresheet. It also fails if a challenge in the dictionary has no
sheet at the pinned version.

| challenge | lines | reward |
|---|---|---|
| Doing Laundry | 18/18 | 4415 |
| GPSR | 9/9 | 1490 |
| HRI | 22/22 | 1450 |
| Pick & Place | 29/29 | 3515 |
| Restaurant | 18/18 | 2360 |

**`reconcile.py`** — the merge is lossless. Rebuilds each scoresheet from
dictionary × challenge and compares line-by-line against the pre-merge files.
Also fails on orphaned entries, stale `*_ref` pointers, and any `points` field
leaking into a challenge.

**`check_schema.py`** — both JSON Schemas, over every entry.

**`validate.py`** — the seven original checks plus CHECK 8 (id hygiene). These
surface open questions rather than enforcing correctness; findings are expected,
not failures.

Current findings: **12 open TC questions**, 10 hard dependency gates, 3 dangling
refs in HRI, 6 skill families priced differently across challenges.

### Known open questions

Highest priority, all surfaced by `validate.py` CHECK 6:

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

## How the merge worked

The five per-challenge files (111 entries) merged to **98 canonical ids**.

Two were true duplicates — same skill, same modifiers, same price, different id
in different challenges:

| canonical | was | challenges |
|---|---|---|
| `GEN-HUMANASSIST-14P` | `GEN-HUMANASSIST-03` + `-03B` | doing_laundry, pick_and_place |
| `MAN-PICK-02B` | `MAN-PICK-01B1` + `MAN-PICK-05B` | pick_and_place, restaurant |

`SPECIAL-OUTSTANDING` appeared in all five files at five different values
(441/149/145/351/236). That is not five prices but one rule — §3.8.3 awards 10%
of the test maximum — so it became a single entry carrying
`points_formula: floor(0.10 * total_score)`. `floor` reproduces all five printed
sheet values; half-up rounding does not, breaking Laundry and Pick & Place.

**What was deliberately not merged:** entries sharing a skill but differing in
modifiers or price stay separate. `MAN/Pick` is priced 50 / 100 / 100 / 300
across four challenges. Collapsing those would invent a cross-challenge price the
TC never agreed to. The dictionary's job is to make drift **visible**, not to
silently resolve it.

### ID stability

`variant_number` is permanent. The merge preserves the legacy number wherever the
legacy id encoded one, so ids already cited in TC open questions still resolve.

43 ids changed spelling (canonical skill verb, plus a `P`/`B` type marker where
the legacy id lacked one). `dist/id_migration.csv` maps all 100.

---

## License

Two parts, mirroring the RuleBook:

- **`tools/`, `schema/`** — BSD 3-Clause ([LICENSE.BSD-3-Clause](LICENSE.BSD-3-Clause))
- **`dictionary/`, `challenges/`, `vocabulary/`, `dist/`** —
  CC BY-SA 4.0 ([LICENSE.CC-BY-SA-4.0](LICENSE.CC-BY-SA-4.0))

The content files derive from the RoboCup@Home RuleBook, which is CC BY-SA 4.0.
Skill descriptions and point values come from its scoresheets, so share-alike
carries over — that content cannot be relicensed. The rulebook itself is not
redistributed here; it is a pinned submodule. See [LICENSE](LICENSE).
