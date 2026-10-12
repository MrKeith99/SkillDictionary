# Contributing

Thanks for helping maintain the skill dictionary.

This repo follows the [RoboCup@Home RuleBook contribution
guidelines](https://github.com/RoboCupAtHome/RuleBook/wiki/Guidelines:-Contributing)
and [workflow](https://github.com/RoboCupAtHome/RuleBook/wiki/Guidelines:-Workflow).
Where this document is silent, those apply.

Read [README.md](README.md) first if you have not — particularly *Why this
exists* and *Layout*. Most review comments here trace back to one idea: **a
skill is defined once and priced once**, and everything else references it.

---

## Before you start

```sh
git submodule update --init --recursive
pip install pyyaml jsonschema
make check
```

The submodule is the RuleBook, pinned to the version the season in force
describes; without it the rulebook check cannot run (see
[external/README.md](external/README.md)). `make check` must end with
`ALL CHECKS PASSED` on an unmodified checkout; if it does not, open an issue
rather than working around it.

---

## Workflow

1. Open an issue describing the change, unless it is trivial.
2. Branch from `master`. Never commit to `master` directly.
3. Edit under `data/` — nowhere else holds data.
4. Run `make check`.
5. Commit the source **and** the regenerated `dist/`. Never commit `build/`.
6. Open a PR.

### Where a change goes

| you want to | edit |
|---|---|
| fix how the in-force rulebook is described | `data/skills/`, `data/seasons/<in force>/challenges/` |
| propose a scoring change for next year | a new file in `data/seasons/<next>/changes/` |
| change the proposed pricing rule | `data/seasons/<next>/pricing.yaml` |
| add an object, a factor, a taxonomy node | `data/vocabulary/` |
| change a page or sheet layout | `templates/` or `skilldict/render/` |
| add a check | `skilldict/checks/` |

### Branch names

Same convention as the RuleBook — lowercase, underscore-separated:

| prefix | use | example |
|---|---|---|
| `feature/` | new skills, schema or tooling changes | `feature/process_spec_field` |
| `fix/` | a specific issue | `fix/#12_dangling_hri_refs` |
| `year/` | work targeting one rulebook version | `year/2027.1_remove_restaurant` |

**Never squash.** Rebase to update a branch. PRs are mandatory for merging.

---

## What CI enforces

`make check` builds every season and runs the data, integrity, schema and
(season in force) rulebook stages; see README, *Checks*. All must pass before
review.

The findings (T1–T5, A1–A7) are **not** failures. They surface questions for
the TC. If your change moves them, say so in the PR description and explain
why — `make findings` prints them.

---

## Rules

### Never put `points` in a challenge file

The schema rejects it, and so does the integrity check. Price belongs to the
skill, in `data/skills/`, once. If you find yourself wanting a per-challenge
price, the skills are genuinely different and need separate lines with
different `objects` / `conditions` (and so a different difficulty).

### Never author derived fields

`used_by` and `total_score` are computed by the build. The loader refuses
them in the sources, so they can never go stale.

### Never reuse or reassign a `variant_number`

Numbers are permanent. The TC cites ids in writing, so `MAN-APPLIANCE-02` must
keep meaning the dishwasher door forever. New lines take the next free number
for their stem; a merged line's id is retired, never reused.

### Keep modifiers to object and environment properties

Good: `heavy`, `deformable`, `known`, `cluttered`, `from_floor`.

Not acceptable: `two_handed`, `suction`, `force_controlled` — these describe
*how* a robot achieves the task. Scoring mechanism rather than outcome penalises
unconventional and low-cost builds, and forces referees to judge technique
instead of result.

### Every line is used

In the season in force an unused line fails the integrity check: remove it in
the same PR that removes its last reference. A proposal season lists the base
lines it retires.

### Same skill, same difficulty, same price

Two lines are one skill only if they have the same taxonomy node, objects and
conditions. Then they must have one price and become one line. If they differ
in difficulty, they stay separate — difficulty is a difference, so the price
may differ too.

In the season in force, merge only lines the rulebook already prices the
same (the rulebook check proves it). Bringing differently-priced lines into
line is a scoring change: it goes in a proposal season.

---

## Adding a skill

Add the entry to the area file in `data/skills/`, keeping entries sorted by id:

```yaml
- id: MAN-PICK-14
  area: MAN
  skill: Pick
  variant_number: '14'
  taxonomy: MAN.Pick
  modifiers: [deformable, from_floor]
  description: Picking up a deformable object from the floor
  objects: [clothing]
  conditions: {reach: low_high, clutter: isolated, knowledge: known_class}
  level: C
  points: 80
  type: achievement
```

Then reference it from the challenge:

```yaml
- ref: MAN-PICK-14
  count: 2
  section: Main Goal
  assistance:
    permitted: false
```

For next year, put both in a change file instead (`dictionary_additions` and
`add_entries`, or a whole `challenge`), and leave out `points` to have the
season's pricing rule price it.

Before adding an entry, read [docs/skill-model.md](docs/skill-model.md). In
short:

- **Reuse a taxonomy node.** A new object or situation is new `objects` /
  `conditions` on an existing node, not a new skill. If the object has no
  profile, add one to `data/vocabulary/objects/catalog.yaml` and list it in the
  season's `objects.yaml`.
- **A genuinely new capability** gets a node in `data/vocabulary/taxonomy.yaml`
  first — `intent`, `success`, `not_judged`, `factors` — with `status:
  proposed`, and is reviewed on its definition before anything scores it.
- **Penalties** name a `failure_mode`. If T3 shows the same failure priced
  differently elsewhere, explain why in the PR.

Controlled vocabularies:

| field | allowed |
|---|---|
| `area` | NAV, MAN, OBJ, PPL, HRI, NLU, PLN, COM, SAF, GEN, SPECIAL |
| `level` | `E`, `C`, `X`, `-` — see below |
| `type` | `achievement`, `bonus`, `penalty_behavior`, `disqualifying`, `administrative` |
| `id` | `^[A-Z]+(-[A-Z]+)?-[0-9]{2,}[A-Z]?[0-9]*$` |

### Choosing a `level`

`level` rates difficulty **for the field**, not point value. The two are
independent — judge how many teams could actually do it, not what it pays.

| level | meaning |
|---|---|
| `E` | Entry — most teams achieve it reliably |
| `C` | Competent — typical of the mid-field |
| `X` | Expert — few teams manage it |
| `-` | not a robot capability; use whenever `skill` is `null` |

- **No quantitative threshold exists yet.** Match the level of comparable
  existing skills in the same area and say in the PR why you chose it. T1
  compares it with the intrinsic difficulty D.
- **Levels are reassigned annually** from empirical team performance, unlike
  `variant_number`. If last competition's results contradict a level, that is a
  legitimate PR of its own.

Use `administrative` for §3.8 lines that are not robot capabilities
(outstanding performance, start signal). They are excluded from area-balance
reports.

---

## Seasons

### Proposing changes for next year

Add a file to `data/seasons/<next>/changes/`. Start it with a comment saying
what the rulebook does today, what is wrong with it, and what the change does —
the TC reviews the reasoning with the data. The keys are documented in
[skilldict/overlay.py](skilldict/overlay.py). Then:

```sh
make check            # builds the proposal season too, writes dist/<next>/
make sheets pdf       # the sheets, official next to proposed
```

### Starting a new proposal season

```yaml
# data/seasons/2028/season.yaml
year: 2028
status: proposal
base: 2027
```

Add `pricing.yaml` if new lines should be priced by rule.

### When the rulebook is published

The proposal becomes the season in force:

1. Move the submodule pin: `git -C external/RuleBook checkout <tag>`, then
   `git add external/RuleBook`; update the pin note in `external/README.md`.
2. In the season's `season.yaml`: `status: in_force`, `rulebook` (version,
   commit), `sheets` (the rulebook's sheet file per challenge); drop `base`.
3. Materialise it: write the challenges to `seasons/<year>/challenges/`, apply
   the line changes to `data/skills/`, copy `objects.yaml` and replace its
   classes with the year's published object list. Delete `changes/`.
4. Set the previous season to `status: proposal` with no `base` — or delete
   it; the git history keeps it.
5. `make check` until the rulebook stage matches every sheet.

Only one season is `in_force`; it is the one `dist/` describes.

---

## Changing points in the season in force

**A price change is a rulebook change, not a refactor.** It belongs in a PR
against the RuleBook repo first. Once the `.tex` sheet is merged there, move the
pin, update the line, run `make check`. The rulebook stage fails until the
dictionary and the rulebook agree, in either direction — that is the check
that catches the dictionary drifting from the rules it describes.

---

## Modelling assistance

§3.7.2: an assisted task element scores **zero** unless the task description
says otherwise. The default is forfeiture, not penalty.

Task descriptions override this four ways, all present in the scoresheets:

1. **Forfeit only** — reward text says "without assistance".
2. **Forfeit + fixed penalty** — e.g. Pick & Place handover, −100.
3. **Explicitly free** — e.g. dishwasher door, "−0".
4. **Percentage of test score** — the §3.7.4 ASR ladder.

The common mistake is assuming an unmet dependency blocks downstream points. It
does not, because assistance can satisfy the precondition. So `blocking` and
`satisfiable_by_assistance` are **separate fields**, and
`assistance.blocks_dependents` defaults to `false`. Set `blocking: true` only
when the dependent line is genuinely impossible without the prerequisite.

---

## Pull requests

Describe what changed and why. If the change affects scoring or referee
behaviour, say so explicitly — those get closer review.

Include:

- **What changed**, and the issue it closes.
- **Why**, especially for anything touching points, ids or modifiers.
- **CI output** — confirm `ALL CHECKS PASSED`.
- **Any movement in the findings**, with reasoning.

Changes that alter points, merge skills, or modify the ranking model need TC
sign-off before merging. When in doubt, open the PR as a draft and ask.

---

## License

By contributing you agree your work is licensed under the terms in
[LICENSE](LICENSE): BSD 3-Clause for `skilldict/`, `templates/` and `schema/`,
CC BY-SA 4.0 for `data/` and `dist/`, which derive from the RuleBook.
