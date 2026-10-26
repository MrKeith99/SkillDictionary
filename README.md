# SkillDictionary

A versioned, machine-checkable skill dictionary for the RoboCup@Home rulebook.

**This tree: 2027 draft** — the rulebook pinned in `data/release.yaml` (2026.2)
plus the changes proposed for 2027. The reasoning for each change is in the
proposal document, which is kept outside this repo.
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
  skills.yaml                 every SKILL: what it is for, its success criterion,
                              its difficulty factors and failures; the failure modes
  variants/<AREA>.yaml        every VARIANT of a skill: objects, place, conditions, price
  challenges/<slug>.yaml      every CHALLENGE: which variants it scores, how often (no points)
  vocabulary/
    difficulty_factors.yaml     what makes a variant harder, and by how much
    objects.yaml                every real object: mass, size, surface, ...
    furniture.yaml              the arena: every place's height and access, doors and racks
    object_set.yaml             the year's object set

skilldict/                  the Python package — one CLI for everything
  model.py                    loading, derived fields (used_by, total_score, names, codes)
  penalties.py                penalty variants, from the failures of each skill
  gpsr.py                     GPSR: value every generator command, fill step counts
  difficulty.py               vocabulary integrity, intrinsic difficulty D
  checks/                     schema, integrity, rulebook, findings
  render/                     scoring page, rulebook LaTeX sheets, PDF
  cli.py

schema/                     JSON Schema for a variant and a challenge (as written to dist/)
docs/                       skill-model.md (how it fits together)
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
| `make sheets` | score sheets in the rulebook's LaTeX → `build/sheets/` |
| `make pdf` | rulebook sheet next to the generated one, per challenge → `build/*.pdf` |
| `make all` | all of the above |

Each target is `python3 -m skilldict <command>`; `python3 -m skilldict --help`
lists the options.

### Consuming the data

| file | use |
|---|---|
| `dist/skills.json` | every skill (with its derived name and code) and the failure modes |
| `dist/variants.json` | every variant: skill, objects, price, `used_by`; penalty variants included |
| `dist/challenges.json` | per challenge: references, counts, assistance, `total_score` |
| `dist/vocabulary.json` | difficulty factors and object profiles |
| `dist/variant_difficulty.json` | per variant: skill, objects, factors, intrinsic difficulty |
| `dist/gpsr_commands.json` | the value of every command the GPSR generator can produce |

`used_by` and `total_score` are **derived** by the build; the sources never
carry them, so they cannot go stale.

### Scoring page

`dist/scoring.html` is one self-contained page (no external scripts, works
offline). Its **overview** compares the challenges: maximum score and how much
of it allows human help, what share of each challenge goes to each capability
area, which skills each challenge scores, every skill's variants under the
price rule, and the variants whose single price covers very different
objects. Each **challenge tab** is its referee sheet: tick boxes add up live,
with the line's notes, whether help is allowed, its penalties beneath it and
the score by skill; `#<challenge>` in the URL opens it, and Print prints that
sheet alone. It is rebuilt by `make check` from `skilldict/render/scoring.html`;
edit the template, never the output.

---

## The model in short

A **skill** (`data/skills.yaml`) says what a capability is and never what it
pays. A **variant** (`data/variants/`) is one priced instance of a skill: which
objects, where, under what conditions. Its difficulty D is computed from those,
and its price follows from D and the skill's `base`. A **challenge**
(`data/challenges/`) only references variants and says how often it scores
them. Penalties are not written per challenge: the build derives them from the
failure modes of each skill.

Full explanation, ids and the price rule: **[docs/skill-model.md](docs/skill-model.md)**.

---

## Releases

The tree describes one release, set in `data/release.yaml`. Earlier releases
are git tags (`2026.2`), so `git diff 2026.2 -- data/` shows every change and
`git checkout 2026.2` brings back any earlier dictionary.

While `status: draft`, the tree proposes the next rulebook: the rulebook stage
of `make check` lists every difference from the pinned rulebook's sheets — that
list *is* the proposal — and the proposal document says why each one is
there. Once the rulebook is published and pinned, the release
goes `status: in_force` and any difference fails CI.

---

## Checks

`make check` runs:

| stage | fails on |
|---|---|
| **data** | unknown skill, object, factor or factor level; a factor that does not apply to the skill; a penalty without a failure mode |
| **integrity** | a challenge naming an unknown variant or carrying a price; a reference to a variant that does not exist; a variant no challenge uses (an id whose code does not match its skill fails at load) |
| **schema** | a variant or challenge, as written to `dist/`, violating the JSON Schema |
| **rulebook** | when `in_force`: any scored variant or total that differs from the rulebook's `.tex` sheet (when `draft`, the differences are listed, not failed) |

then writes `dist/` and prints the **findings**:
questions for the TC, never failures.

| finding | asks |
|---|---|
| T1 | price rule: an achievement that does not pay `base × (1 + D/4)` |
| T2 | penalties per failure mode: derived at its share, and the authored ones |
| T3 | skill coverage: proposed skills, unscored skills |
| T4 | object data: objects and places in use, widest difficulty ranges |

---

## Contributing

See **[CONTRIBUTING.md](CONTRIBUTING.md)**. The short version: edit `data/`,
run `make check`, commit the source **and** the regenerated `dist/`.

---

## License

Two parts, mirroring the RuleBook:

- **`skilldict/`, `schema/`** — BSD 3-Clause ([LICENSE.BSD-3-Clause](LICENSE.BSD-3-Clause))
- **`data/`, `dist/`** — CC BY-SA 4.0 ([LICENSE.CC-BY-SA-4.0](LICENSE.CC-BY-SA-4.0))

The content files derive from the RoboCup@Home RuleBook, which is CC BY-SA 4.0.
Skill descriptions and point values come from its scoresheets, so share-alike
carries over — that content cannot be relicensed. The rulebook itself is not
redistributed here; it is a pinned submodule. See [LICENSE](LICENSE).
