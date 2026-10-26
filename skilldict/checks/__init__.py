"""Checks over a Build. Each module has run(build) -> number of failures.

  schema     every variant and challenge satisfies the JSON Schema
  integrity  references resolve, every variant is used, no price in a challenge
  rulebook   the data vs the rulebook's own .tex score sheets (fails only when in force)
  findings   questions for the TC (never failures)
"""

RULE = "=" * 78
