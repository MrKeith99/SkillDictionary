# Contributing

Thanks for helping maintain the skill dictionary.

This repo follows the [RoboCup@Home RuleBook contribution
guidelines](https://github.com/RoboCupAtHome/RuleBook/wiki/Guidelines:-Contributing)
and [workflow](https://github.com/RoboCupAtHome/RuleBook/wiki/Guidelines:-Workflow).
Where this document is silent, those apply.

Read [README.md](README.md) first if you have not — particularly *Why this
exists*. Most review comments here trace back to one idea: **a skill is defined
once and priced once**, and everything else references it.

---

## Before you start

Install the dependencies and confirm a clean baseline:

```sh
git submodule update --init --recursive
pip install pyyaml jsonschema
tools/ci.sh
```

The submodule is the RuleBook, pinned to the version this dictionary targets.
Without it `check_scoresheets.py` cannot run; see [external/README.md](external/README.md).

It must end with `ALL CHECKS PASSED`. If it does not on an unmodified checkout,
open an issue rather than working around it.

---

## Workflow

1. Open an issue describing the change, unless it is trivial.
2. Branch from `master`. Never commit to `master` directly.
3. Make your edit in `dictionary/` and/or `challenges/`.
4. Run `tools/ci.sh`.
5. Commit source **and** the regenerated `dist/`.
6. Open a PR.

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

`tools/ci.sh` runs six stages. All must pass before review.

| stage | proves |
|---|---|
| `merge_challenges.py` | sources rebuild cleanly into `dist/` |
| `build_viz_data.py` | regenerates `dist/viz_data.json` + `skill_coverage.html` |
| `check_schema.py` | every entry satisfies the JSON Schema |
| `reconcile.py` | the merge is lossless; no orphans or stale refs |
| `check_scoresheets.py` | the dictionary matches the rulebook `.tex` |
| `validate.py` | reports open questions (findings are expected) |

`validate.py` findings are **not** failures. They surface questions for the TC.
The current baseline is 12 open questions, 10 hard dependency gates, 3 dangling
refs, 6 drifting skill families. If your change moves those numbers, say so in
the PR description and explain why.

---

## Rules

### Never put `points` in a challenge file

The schema rejects it (`additionalProperties: false`). Price belongs to the
skill, in `dictionary/`, once. This is the whole point of the repo — a challenge
that could carry its own price could drift from another challenge.

If you find yourself wanting a per-challenge price, the skills are genuinely
different and need separate dictionary entries with different modifiers.

### Never reuse or reassign a `variant_number`

Numbers are permanent. The TC cites ids in writing, so `MAN-APPLIANCE-02` must
keep meaning the dishwasher door forever. Reassigning it silently repoints an
existing citation at a different skill.

New entries take the next free number for their stem. If you must rename an id,
add the mapping to `dist/id_migration.csv` in the same PR.

### Keep modifiers to object and environment properties

Good: `heavy`, `deformable`, `known`, `cluttered`, `from_floor`.

Not acceptable: `two_handed`, `suction`, `force_controlled` — these describe
*how* a robot achieves the task. Scoring mechanism rather than outcome penalises
unconventional and low-cost builds, and forces referees to judge technique
instead of result.

### Every dictionary entry must be referenced

Orphans fail `reconcile.py`. If a skill is no longer used by any challenge,
remove it in the same PR that removes its last reference.

---

## Adding a skill

Add the entry to the area file in `dictionary/`, keeping entries sorted by id:

```yaml
- id: MAN-PICK-14
  area: MAN
  skill: Pick
  variant_number: '14'
  modifiers: [deformable, from_floor]
  description: Picking up a deformable object from the floor
  level: C
  points: 80
  type: achievement
  used_by: [doing_laundry]
```

Then reference it from the challenge:

```yaml
- ref: MAN-PICK-14
  count: 2
  section: Main Goal
  assistance:
    permitted: false
```

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

Two things to know before you set one:

- **No quantitative threshold exists yet.** The tiers are currently descriptive,
  inherited from the original extraction, and nothing validates them. Match the
  level of comparable existing skills in the same area and say in the PR why you
  chose it.
- **Levels are reassigned annually** from empirical team performance, unlike
  `variant_number`, which is permanent. Do not treat an existing level as
  settled — if last competition's results contradict it, that is a legitimate PR
  (and belongs in its own, separate from adding skills).

A `vocabulary/levels.yaml` carrying real empirical criteria is planned and needs
TC sign-off. Until it exists, treat every `level` value as provisional.

Use `administrative` for §3.8 lines that are not robot capabilities
(not-attending, outstanding performance). They are excluded from area-balance
reports.

---

## Changing points

**A price change is a rulebook change, not a refactor.**

It belongs in a PR against the RuleBook repo first. Once the `.tex` scoresheet is
merged there:

1. Move the submodule pin — see [external/README.md](external/README.md).
2. Update the dictionary entry to match.
3. Run `tools/ci.sh`.

`check_scoresheets.py` fails until the dictionary and the rulebook agree, in
either direction. That is deliberate: it is the check that catches the dictionary
drifting away from the rules it is supposed to describe.

### Do not merge skills that carry different prices

If two entries look like the same skill but are priced differently, that is
**score drift** — one of the two problems this repo exists to expose. Collapsing
them invents a price the TC never approved.

Leave them as distinct variants. `validate.py` CHECK 5 reports the family so the
TC can decide. Bringing the prices into line is a rulebook PR, not a
dictionary PR.

---

## Modelling assistance

§3.7.2: an assisted task element scores **zero** unless the task description says
otherwise. The default is forfeiture, not penalty.

Task descriptions override this four ways, all present in the scoresheets:

1. **Forfeit only** — reward text says "without assistance".
2. **Forfeit + fixed penalty** — e.g. Pick & Place handover, −100.
3. **Explicitly free** — e.g. dishwasher door, "−0".
4. **Percentage of test score** — the §3.7.4 ASR ladder.

The common mistake is assuming an unmet dependency blocks downstream points. It
does not, because assistance can satisfy the precondition. If the referee opens
the dishwasher door the robot forfeits those 400 points, but "correctly in the
dishwasher" (3×70) stays fully available.

So `blocking` and `satisfiable_by_assistance` are **separate fields**, and
`assistance.blocks_dependents` defaults to `false`. Set `blocking: true` only
when the dependent line is genuinely impossible without the prerequisite.

---

## Targeting a new rulebook version

Work on a `year/` branch:

1. Move the submodule pin: `git -C external/RuleBook checkout <tag>`, then
   `git add external/RuleBook`.
2. Update the pin note in `external/README.md`.
3. Update `rulebook_version` in `tools/merge_challenges.py`.
4. Add, remove or reprice entries to match.
5. Run `tools/ci.sh`.

`master` currently targets **2026.2**. Restaurant is deliberately included: it
exists in 2026.2 and is removed only in the Current Draft (PR #1059). Removing it
is 2027.1 work — delete `challenges/restaurant.yaml` and its sheet, then rerun
`ci.sh`.

Note `MAN-PICK-02B` (first-pick bonus) is shared between Pick & Place and
Restaurant, so removing Restaurant narrows its `used_by` rather than deleting it.

---

## Pull requests

Describe what changed and why. If the change affects scoring or referee
behaviour, say so explicitly — those get closer review.

Include:

- **What changed**, and the issue it closes.
- **Why**, especially for anything touching points, ids or modifiers.
- **CI output** — confirm `ALL CHECKS PASSED`.
- **Any movement in `validate.py` findings**, with reasoning.

Changes that alter points, merge skills, or modify the ranking model need TC
sign-off before merging. When in doubt, open the PR as a draft and ask.

---

## License

By contributing you agree your work is licensed under the terms in
[LICENSE](LICENSE): BSD 3-Clause for `tools/` and `schema/`, CC BY-SA 4.0 for
dictionary content derived from the RuleBook.
