"""The proposed 2027 pricing rule (vocabulary/pricing.yaml), as functions.

Shared by propose_prices.py (re-price the 2026 lines) and build_proposal.py
(price new lines in a proposal), so both apply exactly the same rule.
"""
import os, statistics
from collections import defaultdict
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_rule():
    with open(os.path.join(ROOT, "vocabulary", "pricing.yaml")) as fh:
        return yaml.safe_load(fh)


RULE = load_rule()


def weight(d):
    return 1 + d / RULE["d_scale"]


def rnd(x):
    sign = -1 if x < 0 else 1
    for r in RULE["rounding"]:
        if abs(x) >= r["from"]:
            return sign * int(round(abs(x) / r["step"]) * r["step"])
    return sign * int(round(abs(x)))


def dmin(ratings, eid):
    r = (ratings.get(eid) or {}).get("difficulty")
    return None if r is None else r["min"]


def calibrate(lines, ratings):
    """Skill base per node: median of price / weight(D) over the given lines,
    then overrides, then `base_like` for nodes with no line of their own."""
    implied = defaultdict(list)
    for e in lines:
        d = dmin(ratings, e["id"])
        if e.get("points") and d is not None:
            implied[e["taxonomy"]].append(e["points"] / weight(d))
    base = {n: statistics.median(v) for n, v in implied.items()}
    base.update(RULE.get("base_overrides") or {})
    for node, like in (RULE.get("base_like") or {}).items():
        if node not in base and like in base:
            base[node] = base[like]
    return base
