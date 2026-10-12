# Changes from rulebook 2026.2 — PROPOSAL for 2027

What this branch changes against the rulebook as published (git tag `2026.2`),
and why. `make check` prints the same changes line by line (stage RULEBOOK),
and `make pdf` sets each official sheet next to the proposed one.

All prices follow one rule (below): the same skill at the same difficulty pays
the same everywhere, and the same failure costs the same share of the line it
belongs to.

---

## One price per skill and difficulty

2026 prices each line on its own, so the same skill drifts: a pick pays 50 in
one test and 300 in another, and 11 times a strictly harder line of a skill
pays less than an easier one. Every price in `data/skills/` now follows one
rule; the 11 inversions are 0.

**Achievement** = base[skill] × (1 + D / 4), rounded to 10 (to 5 below 50).
D is the intrinsic difficulty of the easiest instance the line covers
(`dist/skill_ratings.json`); harder objects are paid by bonus lines.

**Bonus or discount** on a parent line: parent + line together pay the rule
price at the line's own D; the line pays the difference.

**Penalty** = a share of the line it belongs to:

| failure | share | | failure | share |
|---|---|---|---|---|
| damage, quality, multiple at once | 100 % | | drop, spill, collision | 50 % |
| wrong target, wrong info | 50 % | | assistance (on top of forfeiting the element, §3.7.2) | 50 % |
| alternative input | 25 % | | | |

Conduct failures are not tied to one action, so they cost a fixed amount
everywhere: neglect −100, unsafe contact −200.

**Skill bases** are calibrated, not invented: the median over the skill's
lines in rulebook 2026.2 of price ÷ (1 + D / 4). The league's level per skill is
kept; only the spread inside a skill goes.

| skill | base | skill | base | skill | base |
|---|---|---|---|---|---|
| MAN.Fold | 300 | MAN.Pick | 60 | HRI.ConveyInfo | 35 |
| PLN.Execute | 200 | NLU.UnderstandCommand | 58 | HRI.Handover | 33 |
| MAN.Pour | 160 | MAN.Stack | 50 | MAN.Place | 29 |
| MAN.OperateArticulated | 133 | PPL.Detect¹ | 40 | HRI.Gaze | 27 |
| NAV.Follow | 133 | PPL.DetectGesture | 40 | NAV.Navigate | 23 |
| NAV.Guide¹ | 133 | PPL.Reidentify¹ | 40 | OBJ.DetectEvent | 20 |
| PLN.Interleave | 133 | MAN.Insert | 64 | PPL.DescribeAttribute | 16 |
| MAN.Transport | 119 | HRI.Indicate | 67 | OBJ.DetectPlacement | 15 |
| PLN.Plan | 67 | NAV.SignalIntent | 12 | NLU.Clarify | 9 |
| OBJ.Recognize | 7 | | | | |

¹ no 2026 line: as NAV.Follow / PPL.DetectGesture.

To price a new line: rate it (`make check` writes its D), apply the formula.
`make findings` T2 reports any line that breaks it.

**Not priced by the rule**, kept at their value:

- goal bonuses — they pay for reaching the goal, not for difficulty:
  `MAN-FOLD-02B` (+400), `PLN-COMPLETECOMMAND-01B` (+35);
- discounts the rule would zero or flip: `MAN-PICK-01B2` (+30), `MAN-PLACE-02P2` (−20);
- `GEN-HUMANASSIST-08P` (−100): flattening help is less help than folding
  help (−300); the share does not see the amount of help;
- lines with no difficulty factors, lines judged on the day, explicit 0s.

Challenge maximums:

| challenge | 2026.2 | 2027 |
|---|---|---|
| Doing Laundry | 4415 | 5575 |
| GPSR | 1490 | 1820 |
| HRI | 1450 | 1630 |
| Pick & Place | 3515 | 3940 |
| Restaurant | 2360 | 1920 |

Challenges are not rescaled: scaling one would make the same skill pay
differently again. Balance between challenges is set through the skill bases.

---

## Where a skill happens: furniture places

2026 rates "where" with one typed level per line (`reach`: table / low-high /
enclosed). "Place it in the cabinet" got one guessed level, although the top
and the bottom shelf are different difficulties, and nothing tied the level to
the real furniture.

Now the arena is data ([furniture.yaml](../data/vocabulary/objects/furniture.yaml)):
every place on every piece of furniture, with its height and access, and the
doors and racks to operate. A line names its places in `at:`; two factors
replace `reach`:

| factor | 0 | 1 | 2 |
|---|---|---|---|
| `height` (from `height_mm`) | 0.6–1.1 m | 0.25–0.6 or 1.1–1.5 m | below 0.25 or above 1.5 m |
| `access` | open | bounded (board above, walls around) | enclosed (door, drum, rack) |

A line naming a whole piece of furniture (`at: [cabinet]`) or a group
(`placement_locations`) covers all its places and gets a difficulty range. The
arena is the 2026 Incheon one, written as the 2027 arena; heights are typical
values (`values: estimate`) to be measured at Setup Days.

Repriced by the rule where the easiest instance got harder: dishwasher rack
230 → 300 (bottom rack: low and enclosed), clothes from the basket 200 → 210
and its penalty, clothes from the washing machine 210 → 220 and its penalty,
bag drop on the floor 50 → 60.

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

Every garment is now the same fold line (`MAN-FOLD-02` × 6) with the same
per-item penalties; the main-goal premium becomes an explicit bonus
(`MAN-FOLD-02B`, +400 for the first garment folded without assistance and to
quality), as Pick & Place does with its First Pick Bonus. Under the pricing
rule a fold (D4) pays 600, quality failures cost the fold (−600) and folding
help half of it (−300).

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

- The skill bases (2026 medians): a base is how much the league values a skill.
- Penalty shares and the two fixed conduct prices (−100, −200).
- The lines kept outside the rule, above.
- Challenge maximums: the rule keeps each skill's 2026 level, it does not
  rebalance challenges against each other (Restaurant drops, Laundry rises).
