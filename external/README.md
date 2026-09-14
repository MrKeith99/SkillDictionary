# external/

`RuleBook/` is a **git submodule** pinned to the rulebook version this dictionary
targets. It is not vendored — the rulebook text is never copied into this repo.

## Setup

```sh
git submodule update --init --recursive
```

## Current pin

- Repo: https://github.com/RoboCupAtHome/RuleBook
- Tag: **2026.2**
- Commit: `b844d5a6d6ebf4307c3250a01d1eca4ba56f8452`

`2026.2` is an annotated tag: the tag object is `b0cbb5f3…` and it points to
commit `b844d5a6…`. A submodule records the *commit*, so that is what is pinned
here. Use `git rev-parse <tag>^{commit}` when moving the pin.

`tools/check_scoresheets.py` reads `external/RuleBook/scoresheets/*.tex` and
compares every scored line against the dictionary. It prints the checkout's
`git describe` and warns if that does not match the `rulebook_version` stamped
in `dist/dictionary.json`.

## Working without the submodule

Point at any RuleBook checkout:

```sh
RULEBOOK_DIR=/path/to/RuleBook tools/check_scoresheets.py
```

## Moving the pin

Changing the pin is a rulebook-version change — see "Targeting a new rulebook
version" in [../CONTRIBUTING.md](../CONTRIBUTING.md).

```sh
git -C external/RuleBook fetch --tags
git -C external/RuleBook checkout <tag>
git add external/RuleBook          # records the new commit
```
