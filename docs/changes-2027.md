# Changes from rulebook 2026.2 — PROPOSAL for 2027

What this branch changes against the rulebook as published (git tag `2026.2`),
and why. `make check` prints the same changes line by line (stage RULEBOOK),
and `make pdf` sets each official sheet next to the proposed one.

All prices follow one rule ([data/pricing.yaml](../data/pricing.yaml)): the same
skill at the same difficulty pays the same everywhere, and the same failure
costs the same share of the line it belongs to.

---

## GPSR scored by skill

2026 pays a flat 250 per solved command, whatever the command asked for: "go to
the kitchen" and "find a coke, take it and give it to the waving person in the
bedroom" earn the same. The command is drawn at test time (official
CommandGenerator), so a flat price cannot be fair.

A command now earns the skill lines it actually exercises, each at the price
that skill has everywhere else, plus a completion bonus
(`PLN-COMPLETECOMMAND-01B`, 35) when the command's goal holds. PLN.Execute stops
being the score and becomes the bonus for finishing.

`command_steps` in [data/challenges/gpsr.yaml](../data/challenges/gpsr.yaml)
maps every generator template and follow-up to its steps. From it the build
values every command the generator can produce
(`dist/gpsr_commands.json`) and sets the sheet maximum. The bonus was set so
that an average command, at the generator's own weights, is worth 250 — what a
solved command was worth in 2026: 215 in skills + 35.

Retired: `PLN-SOLVECOMMAND-01`, `PLN-SOLVECOMMAND-04P`.

## Doing Laundry: one fold line

2026 prices the same task twice: "Folding a piece of clothing" 800 and "Folding
additional clothes" 400, both MAN.Fold on the same garments (D4). The extra 400
rewards reaching the main goal, not a harder fold. Same for their penalties:
quality −800 / −400, flattening help −200 / −100, folding help up to −800 / −400.

Every garment is now the same fold line (`MAN-FOLD-02`, 400 × 6) with the same
per-item penalties; the main-goal premium becomes an explicit bonus
(`MAN-FOLD-02B`, +400 for the first garment folded without assistance and to
quality), as Pick & Place does with its First Pick Bonus. Values are the 2026
ones, so the maximum is unchanged (4415); only the structure is consistent.

Retired: `MAN-FOLD-01`, `MAN-FOLD-01P1`, `GEN-HUMANASSIST-06P`, `GEN-HUMANASSIST-07P`.

## One neglect penalty

2026 has the same failure twice under two names and two prices:
`HRI-ATTEND-01P` "Not acknowledging people" −200 (HRI) and
`HRI-EYECONTACT-01P` "Not making eye-contact when taking the order" −60
(Restaurant). Both are the league draft's #89 "not attending to interaction
partner".

Now one line, `HRI-ATTEND-01P`, one definition, one fixed price (−100,
`fixed_penalty.neglect`), used by HRI and Restaurant. It is a conduct penalty,
so it does not scale with the line it sits under. Gaze quality stays with the
HRI.Gaze lines; this penalty is only for not engaging at all, so the two never
count the same behaviour twice.

Retired: `HRI-EYECONTACT-01P`.

## Unsafe contact with a person

2026: touching a person is handled only by stopping the robot (general rules
§ Collisions; Restaurant: "Any physical contact with people ... results in
immediate emergency stop"), plus possible disqualification. The score itself
does not record it, so two runs that both stopped look the same whether the
robot ran out of time or bumped into a guest.

Now one line in every challenge, `GEN-UNSAFECONTACT-01P`, fixed price −200
(`fixed_penalty.unsafe_contact`), on top of the stop. Counted once: the run ends
at the first occurrence. Not unsafe: contact the task asks for (a handover the
person completes, functional touching of furniture announced by the robot).

---

## Open for the TC

- The pricing rule's skill bases are the median of the 2026 lines; fix them with
  `base_overrides` once agreed, so a new line cannot move them.
- Penalty shares and the two fixed conduct prices (−100, −200).
- Challenge totals: the rule keeps each skill's 2026 level, it does not rebalance
  challenges against each other.
