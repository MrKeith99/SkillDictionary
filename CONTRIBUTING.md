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
| change what a skill is (its definition, factors, failures) | `data/skills.yaml` |
| add or reprice a variant | `data/variants/` |
| change how a test uses variants | `data/challenges/` |
| add an object, a factor, a piece of furniture | `data/vocabulary/` |
| change a page or sheet layout | `templates/` or `skilldict/render/` |
| add a check | `skilldict/checks/` |

### Branch names

Same convention as the RuleBook — lowercase, underscore-separated:

| prefix | use | example |
|---|---|---|
| `feature/` | new skills, schema or tooling changes | `feature/garment_factor` |
| `fix/` | a specific issue | `fix/#12_dangling_hri_refs` |
| `year/` | work targeting one rulebook version | `year/2027.1_remove_restaurant` |

**Never squash.** Rebase to update a branch. PRs are mandatory for merging.

---

## What CI enforces

`make check` runs the data, integrity, schema and rulebook stages; see
README, *Checks*. All must pass before
review.

The findings (T1–T4) are **not** failures. They surface questions for
the TC. If your change moves them, say so in the PR description and explain
why — `make findings` prints them.

---

## Rules

### Never put `points` in a challenge file

The schema rejects it, and so does the integrity check. Price belongs to the
variant, in `data/variants/`, once. If you find yourself wanting a
per-challenge price, the variants are genuinely different and need separate
variants with different `objects` / `conditions` (and so a different
difficulty).

### Never author derived fields

`used_by`, `total_score`, a skill's `name` and `code`, and the penalty
variants (`<variant>-<FAILURE>`, with
`penalty_of` and `share`) are computed by the build. The loader refuses them
in the sources, so they can never go stale.

### Ids: name the skill, never reuse

Ids follow *Ids* in [docs/skill-model.md](docs/skill-model.md); loading fails
otherwise. A new variant takes the next free number for its skill, a bonus
takes its variant's number plus `B`. A retired id is never reused.

### Describe outcome, never technique

A description or a skill's `success` says *what* is achieved, never *how*
(`two_handed`, `suction`, `force_controlled`). Scoring mechanism rather than
outcome penalises unconventional and low-cost builds, and forces referees to
judge technique instead of result; a skill's `not_judged` says so explicitly.

### Every variant is used

An unused variant fails the integrity check: remove it in the same PR that
removes its last reference. Its id is retired, never reused.

### Same skill, same difficulty, same price

Two variants are one variant only if they have the same skill, objects, places
and conditions. Then they must have one price and become one variant. If they
differ in difficulty, they stay separate — difficulty is a difference, so the
price may differ too.

Bringing differently-priced variants into line is a scoring change: say so in
the PR and in the proposal document.

---

## Adding a variant

Add it to the area file in `data/variants/`, keeping variants sorted by id:

```yaml
- id: MAN-PICK-12
  skill: MAN.Pick
  description: Picking up a piece of clothing from the floor
  objects: [clothing]
  at: [floor]
  conditions: {clutter: isolated, knowledge: known_class}
  points: 200                 # 60 x (1 + 9/4) = 195, rounded
  type: achievement
```

Then reference it from the challenge:

```yaml
- ref: MAN-PICK-12
  count: 2
  section: Main Goal
  assistance:
    permitted: false
```

Price it with the rule in [docs/skill-model.md](docs/skill-model.md)
(*Toward a fair price*) and the skill's `base:` in `data/skills.yaml`:
`make check` writes the variant's D to `dist/variant_ratings.json`, and T1
flags a price that breaks the rule.

Before adding a variant, read [docs/skill-model.md](docs/skill-model.md). In
short:

- **Reuse a skill.** A new object or situation is new `objects` /
  `conditions` on a variant of an existing skill, not a new skill. If the object has no
  profile, add one to `data/vocabulary/objects/catalog.yaml` and list it in
  `data/vocabulary/objects/set.yaml`.
- **A genuinely new capability** gets a skill in `data/skills.yaml`
  first — `intent`, `success`, `not_judged`, `factors` — with `status:
  proposed`, and is reviewed on its definition before anything scores it.
- **Penalties** are not written anywhere per task. If a variant can fail in a
  way its skill does not list, add it to the variant (`failures:`); if the
  whole skill can, add it to the skill in `data/skills.yaml`; if no failure mode fits,
  add one to `failure_modes` with its share. Say in the PR which sheets gain
  penalties.

Controlled vocabularies:

| field | allowed |
|---|---|
| file | `data/variants/<AREA>.yaml`: NAV, MAN, OBJ, PPL, HRI, NLU, PLN, GEN, SPECIAL |
| `type` | `achievement`, `bonus`, `penalty_behavior`, `administrative` |
| `id` | `<AREA>-<code>-<NN>` + optional `B`/`P` + index; `code` from the skill; derived penalties add `-<FAILURE>` |

### Difficulty is computed

There is no `level` to choose: the variant's difficulty D is computed from its
objects, places and conditions. If a variant is harder than its D says, the model
is missing a factor; propose the factor (see docs/skill-model.md, *A new
difficulty factor*), not a different price.

Use `administrative` for §3.8 variants that are not robot capabilities
(outstanding performance, start signal). They are excluded from area-balance
reports.

---

## Releases

The tree describes one release (`data/release.yaml`); earlier releases are git
tags. There is no per-year copy of the data: `git diff <tag> -- data/` is the
change set.

### While drafting (`status: draft`)

Edit the data directly. Every scoring change goes in the proposal document,
kept outside this repo, with its reasoning — what the rulebook does today,
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
pin, update the variant, run `make check`. The rulebook stage fails until the
dictionary and the rulebook agree, in either direction — that is the check
that catches the dictionary drifting from the rules it describes.

---

## Modelling assistance

See *Assistance* in [docs/skill-model.md](docs/skill-model.md):
`assistance.permitted: true` only where the rulebook's task description allows
that help (§3.7.1); otherwise open an issue on the RuleBook repo.

---

## Pull requests

Describe what changed and why. If the change affects scoring or referee
behaviour, say so explicitly — those get closer review.

Include:

- **What changed**, and the issue it closes.
- **Why**, especially for anything touching points or ids.
- **CI output** — confirm `ALL CHECKS PASSED`.
- **Any movement in the findings**, with reasoning.

Changes that alter points, merge skills, or modify the ranking model need TC
sign-off before merging. When in doubt, open the PR as a draft and ask.

---

## License

By contributing you agree your work is licensed under the terms in
[LICENSE](LICENSE): BSD 3-Clause for `skilldict/`, `templates/` and `schema/`,
CC BY-SA 4.0 for `data/` and `dist/`, which derive from the RuleBook.
