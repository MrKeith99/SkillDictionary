#!/usr/bin/env python3
"""Prove the merge is lossless.

Rebuilds every scoresheet from (canonical dictionary x challenge references) and
compares, line by line, against the legacy per-challenge files. Any divergence in
entry count, per-line points_total, or challenge total is a merge bug.
"""
import json, math, os, glob, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LEGACY = os.path.join(ROOT, "extraction")

d_doc = json.load(open(os.path.join(ROOT, "dist", "dictionary.json")))
c_doc = json.load(open(os.path.join(ROOT, "dist", "challenges.json")))
DICT = {e["id"]: e for e in d_doc["skills"]}

SLUG = {"Human Robot Interaction Challenge": "hri",
        "Pick and Place Challenge": "pick_and_place",
        "General Purpose Service Robot Challenge": "gpsr",
        "Doing Laundry Challenge": "doing_laundry",
        "Restaurant Challenge": "restaurant"}

fail = 0


def price(ref, total_score):
    e = DICT[ref]
    if e.get("points_formula"):
        return int(eval(e["points_formula"],
                        {"floor": math.floor, "round": round},
                        {"total_score": total_score}))
    return e["points"]


print("=" * 78)
print("RECONCILE — rebuilt scoresheet vs legacy per-challenge files")
for fn in sorted(glob.glob(os.path.join(LEGACY, "*_challenge.json"))):
    legacy = json.load(open(fn))
    slug = SLUG[legacy["challenge"]]
    ch = c_doc["challenges"][slug]
    total = ch["total_score"]

    if len(ch["entries"]) != len(legacy["skills"]):
        print(f"  FAIL {slug}: entry count {len(ch['entries'])} != {len(legacy['skills'])}")
        fail += 1
        continue

    rebuilt_reward = 0
    for it, old in zip(ch["entries"], legacy["skills"]):
        p = price(it["ref"], total)
        cnt = it.get("count", 1)
        if p is None:
            # Genuinely unpriced in the rulebook (e.g. GPSR partial-solve percentage).
            # Legacy must agree it is unpriced, or the merge dropped a price.
            if old.get("points_total") is not None:
                print(f"  FAIL {slug}: {it['ref']} lost price {old['points_total']}")
                fail += 1
            continue
        pt = p * cnt
        old_pt = old.get("points_total")
        if old_pt is not None and pt != old_pt:
            print(f"  FAIL {slug}: {it['ref']} ({old['id']}) {pt} != {old_pt}")
            fail += 1
        if old["type"] in ("achievement", "bonus"):
            rebuilt_reward += pt

    status = "OK" if rebuilt_reward == total else "MISMATCH"
    if status != "OK":
        fail += 1
    print(f"  {legacy['challenge'][:34]:34s} reward+bonus {rebuilt_reward:5d} "
          f"vs declared {total:5d}  {status}")

# Every dictionary entry must be referenced by at least one challenge.
used = {it["ref"] for ch in c_doc["challenges"].values() for it in ch["entries"]}
orphans = sorted(set(DICT) - used)
print(f"  orphaned dictionary entries: {len(orphans)}")
for o in orphans:
    print(f"     {o}")
    fail += 1

# No challenge file may carry a points field -- drift must be unrepresentable.
leaked = []
for slug, ch in c_doc["challenges"].items():
    for it in ch["entries"]:
        for k in ("points", "points_total"):
            if k in it:
                leaked.append((slug, it["ref"], k))
print(f"  points fields leaked into challenges: {len(leaked)}")
for s, r, k in leaked:
    print(f"     {s} {r} {k}")
    fail += 1

# Every *_ref anywhere in a challenge file must resolve to a canonical id.
import re
stale = []


def walk(node, path, slug):
    if isinstance(node, dict):
        for k, v in node.items():
            if k.endswith("_ref") and isinstance(v, str) and re.match(r"^[A-Z]+-[A-Z]", v):
                if v not in DICT:
                    stale.append((slug, f"{path}.{k}", v))
            else:
                walk(v, f"{path}.{k}", slug)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            walk(v, f"{path}[{i}]", slug)


for slug, ch in c_doc["challenges"].items():
    walk(ch.get("challenge_rules", {}), "challenge_rules", slug)
    for it in ch["entries"]:
        for k in ("assistance", "related_skill"):
            walk({k: it[k]} if k in it else {}, f"entries.{it['ref']}", slug)
print(f"  stale skill refs: {len(stale)}")
for s_, p_, v_ in stale:
    print(f"     {s_} {p_} -> {v_}")
    fail += 1

print("=" * 78)
print("RECONCILE PASS" if not fail else f"RECONCILE FAIL ({fail} problems)")
sys.exit(1 if fail else 0)
