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

The submodule is the RuleBook, pinned to the version `data/release.yaml`
names; without it the rulebook check cannot run (see
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
| change a skill or its price | `data/skills/` |
| change how a test uses skills | `data/challenges/` |
| change the pricing rule | `data/pricing.yaml` |
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

`make check` runs the data, integrity, schema and rulebook stages; see
README, *Checks*. All must pass before
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

An unused line fails the integrity check: remove it in the same PR that
removes its last reference. Its id is retired, never reused.

### Same skill, same difficulty, same price

Two lines are one skill only if they have the same taxonomy node, objects and
conditions. Then they must have one price and become one line. If they differ
in difficulty, they stay separate — difficulty is a difference, so the price
may differ too.

Bringing differently-priced lines into line is a scoring change: say so in
the PR and in `docs/changes-<year>.md`.

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

Price it with the rule: `make prices` shows what `data/pricing.yaml` gives
the line at its difficulty.

Before adding an entry, read [docs/skill-model.md](docs/skill-model.md). In
short:

- **Reuse a taxonomy node.** A new object or situation is new `objects` /
  `conditions` on an existing node, not a new skill. If the object has no
  profile, add one to `data/vocabulary/objects/catalog.yaml` and list it in
  `data/vocabulary/objects/set.yaml`.
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

## Releases

The tree describes one release (`data/release.yaml`); earlier releases are git
tags. There is no per-year copy of the data: `git diff <tag> -- data/` is the
change set.

### While drafting (`status: draft`)

Edit the data directly. Every scoring change goes in
`docs/changes-<year>.md` with its reasoning — what the rulebook does today,
what is wrong with it, what the change does — because the TC reviews the
reasoning with the numbers. `make check` lists every difference from the
pinned rulebook; `make pdf` sets each rulebook sheet next to the proposed one.

### When the rulebook is published

1. Move the submodule pin: `git -C external/RuleBook checkout <tag>`, then
   `git add external/RuleBook`; update the pin note in `external/README.md`.
2. In `data/release.yaml`: `status: in_force`, the new `rulebook` version and
   commit, and the sheet file per challenge.
3. Replace `data/vocabulary/objects/set.yaml` with the year's published object
   list.
4. `make check` until the rulebook stage matches every sheet.
5. Tag the commit with the rulebook version (`git tag -a 2027.1`), then start
   the next draft: `year` + 1, `status: draft`.

---

## Changing points when in force

While the release is `in_force`, **a price change is a rulebook change, not a
refactor.** It belongs in a PR against the RuleBook repo first. Once the `.tex` sheet is merged there, move the
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
