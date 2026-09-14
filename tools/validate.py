#!/usr/bin/env python3
"""Validate the canonical cross-challenge dictionary.

Ported from the per-challenge validate.py. Checks 1-4, 6, 7 are preserved
unchanged in meaning; CHECK 5 becomes a genuine cross-challenge drift report now
that skills carry one canonical id, and CHECK 8 is new (id/variant hygiene).
"""
import json, math, os, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

d_doc = json.load(open(os.path.join(ROOT, "dist", "dictionary.json")))
c_doc = json.load(open(os.path.join(ROOT, "dist", "challenges.json")))
DICT = {e["id"]: e for e in d_doc["skills"]}
CH = c_doc["challenges"]


def price(ref, total):
    e = DICT[ref]
    if e.get("points_formula"):
        return int(eval(e["points_formula"],
                        {"floor": math.floor, "round": round},
                        {"total_score": total}))
    return e["points"]


def rows():
    for slug, ch in CH.items():
        for it in ch["entries"]:
            yield slug, ch, it, DICT[it["ref"]]


print("=" * 78)
print("CHECK 1 — Unreachability: blocking dep whose prerequisite forbids assistance")
hits = 0
for slug, ch, it, e in rows():
    idx = {x["ref"]: x for x in ch["entries"]}
    for dep in it.get("depends_on", []):
        if dep.get("blocking") and not dep.get("satisfiable_by_assistance"):
            p = idx.get(dep["ref"])
            pa = p.get("assistance", {}).get("permitted") if p else None
            print(f"  [{slug:14s}] {it['ref']:22s} <- {dep['ref']:22s} (prereq assistance: {pa})")
            hits += 1
print(f"  -> {hits} hard gates (no assisted route). Confirm each is intended.")

print("=" * 78)
print("CHECK 2 — Assistance permitted but cost unspecified")
hits = 0
for slug, ch, it, e in rows():
    a = it.get("assistance")
    if a and a.get("permitted") and a.get("extra_penalty_ref") is None and "extra_penalty" not in a:
        print(f"  [{slug:14s}] {it['ref']:24s} {e['description'][:44]}")
        hits += 1
print(f"  -> {hits} entries fall back to the §3.7.2 default only.")

print("=" * 78)
print("CHECK 3 — Assistance permitted but NOT listed in task description (§3.7.1)")
hits = 0
for slug, ch, it, e in rows():
    a = it.get("assistance")
    if a and a.get("permitted") and a.get("listed_in_task_description") is False:
        print(f"  [{slug:14s}] {it['ref']:24s} {e['description'][:44]}")
        hits += 1
print(f"  -> {hits} require Team Leader Meeting approval or a rulebook addition.")

print("=" * 78)
print("CHECK 4 — Dangling dependency references")
hits = 0
for slug, ch, it, e in rows():
    for dep in it.get("depends_on", []):
        if dep["ref"] not in DICT:
            print(f"  [{slug:14s}] {it['ref']:22s} -> {dep['ref']} (undefined)")
            hits += 1
print(f"  -> {hits} placeholder refs to define.")

print("=" * 78)
print("CHECK 5 — Cross-challenge price drift (same area+skill, different price)")
# With canonical ids a shared skill CANNOT be priced twice -- that is now
# structurally impossible. What remains visible is drift across sibling variants
# of the same skill used by different challenges.
fam = defaultdict(list)
for e in DICT.values():
    if e["type"] == "achievement" and e["skill"]:
        fam[(e["area"], e["skill"])].append(e)
drift = 0
for k, ents in sorted(fam.items()):
    multi = [e for e in ents if e["used_by"]]
    chs = {c for e in multi for c in e["used_by"]}
    prices = {e["points"] for e in multi}
    if len(chs) > 1 and len(prices) > 1:
        drift += 1
        print(f"  {k[0]}/{k[1]}")
        for e in sorted(multi, key=lambda x: (x["points"] or 0)):
            print(f"      {str(e['points']):>5} pts  {e['id']:22s} {','.join(e['used_by']):28s} "
                  f"{[m for m in e['modifiers']]}")
print(f"  -> {drift} skill families priced differently across challenges.")

print("=" * 78)
print("CHECK 6 — Flagged ambiguities requiring TC decision")
n = 0
for slug, ch, it, e in rows():
    if it.get("ambiguity"):
        n += 1
        print(f"  [{slug:14s}] {it['ref']}\n      {it['ambiguity']}")
for slug, ch in CH.items():
    for k, v in ch.get("challenge_rules", {}).items():
        if isinstance(v, dict) and v.get("ambiguity"):
            n += 1
            print(f"  [{slug:14s}] rule:{k}\n      {v['ambiguity']}")
print(f"  -> {n} open questions.")

print("=" * 78)
print("CHECK 7 — Autonomously-available vs raw points, by challenge")
for slug, ch in CH.items():
    raw = auto = 0
    for it in ch["entries"]:
        e = DICT[it["ref"]]
        if e["type"] not in ("achievement", "bonus"):
            continue
        p = price(it["ref"], ch["total_score"])
        if p is None:
            continue
        pt = p * it.get("count", 1)
        raw += pt
        a = it.get("assistance", {})
        if ("no_assistance" in e["modifiers"]) or (a.get("permitted") is False):
            auto += pt
    print(f"  {ch['challenge'][:34]:34s} raw {raw:5d} | autonomy-defined {auto:5d} "
          f"({100*auto/raw:4.1f}%)")

print("=" * 78)
print("CHECK 8 — Canonical id hygiene")
prob = 0
seen = defaultdict(set)
for e in DICT.values():
    stem = e["id"].rsplit("-", 1)[0]
    v = e["variant_number"]
    if v in seen[stem]:
        print(f"  variant_number {v} reused within {stem}")
        prob += 1
    seen[stem].add(v)
used = {it["ref"] for ch in CH.values() for it in ch["entries"]}
for i in sorted(set(DICT) - used):
    print(f"  orphan (defined, never referenced): {i}")
    prob += 1
for slug, ch in CH.items():
    for it in ch["entries"]:
        if "points" in it or "points_total" in it:
            print(f"  points field leaked into challenge {slug}: {it['ref']}")
            prob += 1
print(f"  -> {prob} id/structure problems.")
