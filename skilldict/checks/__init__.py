"""Checks over a Build. Each module has run(build) -> number of failures.

  schema     every skill and challenge satisfies the JSON Schema
  integrity  references resolve, ids are hygienic, no price in a challenge
  rulebook   the in-force season matches the rulebook's own .tex score sheets
  findings   questions for the TC (never failures)
"""

RULE = "=" * 78
