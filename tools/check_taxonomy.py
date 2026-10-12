#!/usr/bin/env python3
"""Check the taxonomy / difficulty layer and report scoring-fairness findings.

Two kinds of output, like the rest of CI:

  ERRORS    the vocabulary or an entry is inconsistent (unknown node, object,
            factor or level; a factor that does not apply to the skill). These
            fail the build — they mean the data cannot be interpreted.
  FINDINGS  questions for the TC, not failures:
            T1  intrinsic difficulty vs empirical level, per entry
            T2  price inversions inside one taxonomy node: a line that is
                strictly harder than another pays strictly less
            T3  penalty prices per failure mode, across challenges
            T4  proposed (future) skills and nodes without any entry
            T5  object data quality: estimated values, widest difficulty ranges

Also writes dist/skill_ratings.json: per entry, its node, factor levels and
intrinsic difficulty, for the visualizer and external consumers.
"""
import json, os, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

D = json.load(open(os.path.join(ROOT, "dist", "dictionary.json")))["skills"]
CH = json.load(open(os.path.join(ROOT, "dist", "challenges.json")))["challenges"]
V = json.load(open(os.path.join(ROOT, "dist", "vocabulary.json")))
TAX, FAC = V["taxonomy"], V["difficulty_factors"]
CATALOG, FIXTURES, OSET = V["objects"]["catalog"], V["objects"]["fixtures"], V["objects"]["set"]
NODES, FMODES, FACTORS = TAX["nodes"], TAX["failure_modes"], FAC["factors"]
# Names a dictionary entry may use in `objects:`: a year-set class, test-object
# group or category, a catalog object, or a fixture.
GROUPS = {**OSET.get("classes", {}), **OSET.get("test_objects", {}),
          **{k: v["members"] for k, v in OSET.get("categories", {}).items()}}
DICT = {e["id"]: e for e in D}

errors = []


def err(msg):
    errors.append(msg)


# ── vocabulary integrity ─────────────────────────────────────────────────────
for nid, n in NODES.items():
    area = nid.split(".")[0]
    for ref in [n.get("parent")] + n.get("composed_of", []) + [n.get("replaced_by")]:
        if ref and ref not in NODES:
            err(f"taxonomy {nid}: unknown node {ref}")
    if n.get("parent") and not n["parent"].startswith(area + "."):
        err(f"taxonomy {nid}: parent {n['parent']} is in another area")
    for f in n.get("factors", []):
        if f not in FACTORS:
            err(f"taxonomy {nid}: unknown factor {f}")
    for s in n.get("sources", []):
        if s not in TAX.get("sources", {}):
            err(f"taxonomy {nid}: unknown source {s}")
    if n.get("status") not in ("active", "proposed", "deprecated"):
        err(f"taxonomy {nid}: bad status {n.get('status')}")
    for k in ("name", "intent", "success"):
        if not n.get(k):
            err(f"taxonomy {nid}: missing {k}")

for fid, f in FACTORS.items():
    if f["source"] not in ("object", "condition"):
        err(f"factor {fid}: bad source {f['source']}")
    for lv, spec in f["levels"].items():
        if spec["weight"] not in (0, 1, 2):
            err(f"factor {fid}.{lv}: weight must be 0, 1 or 2")


# ── objects: compute factor levels per physical object ──────────────────────
def level_from_measure(fid, value):
    """Map a number onto the factor's levels using their `below` cut-offs."""
    for lv, spec in FACTORS[fid]["levels"].items():
        if spec.get("below") is None or value < spec["below"]:
            return lv


MEASURED = {f["measure"]: fid for fid, f in FACTORS.items() if f.get("measure")}
JUDGED = [fid for fid, f in FACTORS.items() if f["source"] == "object" and not f.get("measure")]

OBJ = {}                                   # physical object id -> {factor: level}
for oid, o in CATALOG.items():
    fac = {}
    for field, fid in MEASURED.items():
        if not isinstance(o.get(field), (int, float)):
            err(f"catalog {oid}: missing numeric {field}")
            continue
        fac[fid] = level_from_measure(fid, o[field])
    for fid in JUDGED:
        if fid in o:
            fac[fid] = o[fid]
    OBJ[oid] = fac
for oid, o in FIXTURES.items():
    OBJ[oid] = {fid: o[fid] for fid in JUDGED if fid in o}
for oid, fac in OBJ.items():
    for fid, lv in fac.items():
        if lv not in FACTORS[fid]["levels"]:
            err(f"object {oid}: {fid}={lv} not a level")
for oid, o in CATALOG.items():
    if o.get("values") not in ("measured", "ycb", "estimate"):
        err(f"catalog {oid}: values must be measured, ycb or estimate")
    if o.get("values") == "ycb" and not o.get("ycb"):
        err(f"catalog {oid}: values: ycb but no ycb id")
for k in ("surface", "rigidity", "shape"):
    for oid, o in CATALOG.items():
        if k not in o:
            err(f"catalog {oid}: missing judged factor {k}")

for name in set(GROUPS) & (set(CATALOG) | set(FIXTURES)):
    err(f"object set: group name {name} collides with an object id")
if set(CATALOG) & set(FIXTURES):
    err(f"catalog and fixtures share ids: {sorted(set(CATALOG) & set(FIXTURES))}")


def expand(name, seen=()):
    """Resolve an objects: name to the set of physical object ids it covers."""
    if name in OBJ:
        return {name}
    if name not in GROUPS:
        err(f"unknown object or group {name}")
        return set()
    if name in seen:
        err(f"object set: cycle through {name}")
        return set()
    out = set()
    for m in GROUPS[name]:
        out |= expand(m, seen + (name,))
    if not out:
        err(f"object set: group {name} is empty")
    return out


for g in GROUPS:
    expand(g)


# ── entries ──────────────────────────────────────────────────────────────────
def node_factors(e):
    return set(NODES[e["taxonomy"]].get("factors", []))


for e in D:
    nid = e["taxonomy"]
    if nid not in NODES:
        err(f"{e['id']}: unknown taxonomy node {nid}")
        continue
    if nid.split(".")[0] != e["area"]:
        err(f"{e['id']}: node {nid} is not in area {e['area']}")
    if NODES[nid]["status"] == "deprecated":
        err(f"{e['id']}: node {nid} is deprecated")
    if NODES[nid].get("scored", True) is False:
        err(f"{e['id']}: node {nid} is decomposition-only (scored: false)")
    applies = node_factors(e)
    for o in e.get("objects", []):
        if o not in OBJ and o not in GROUPS:
            err(f"{e['id']}: unknown object or group {o}")
    for fid, lv in e.get("conditions", {}).items():
        # A list means the level is drawn at test time (GPSR commands,
        # restaurant orders): the entry is rated over the whole range.
        lvs = lv if isinstance(lv, list) else [lv]
        if fid not in FACTORS:
            err(f"{e['id']}: unknown factor {fid}")
        elif FACTORS[fid]["source"] != "condition":
            err(f"{e['id']}: {fid} is an object property, set it in objects/catalog.yaml")
        elif not lvs or any(x not in FACTORS[fid]["levels"] for x in lvs):
            err(f"{e['id']}: {fid}={lv} not a level")
        elif fid not in applies:
            err(f"{e['id']}: factor {fid} does not apply to {nid}")
    fm = e.get("failure_mode")
    if fm and fm not in FMODES:
        err(f"{e['id']}: unknown failure_mode {fm}")
    if fm and e["type"] in ("achievement", "bonus"):
        err(f"{e['id']}: failure_mode on a {e['type']}")
    if e["type"] == "penalty_behavior" and not fm and not e.get("objects"):
        err(f"{e['id']}: penalty without failure_mode (or objects, for a price discount)")

# ── intrinsic difficulty ─────────────────────────────────────────────────────
def weight(fid, lv):
    return FACTORS[fid]["levels"][lv]["weight"]


def tier(d):
    for t, spec in FAC["tiers"].items():
        if spec["max"] is None or d <= spec["max"]:
            return t


def rate(e):
    """(Dmin, Dmax, per-object breakdown) or None if the entry carries no factors.

    per-object values are (dmin, dmax, factors); they differ only when a
    condition is a list of levels."""
    applies = node_factors(e)
    if not applies or not (e.get("objects") or e.get("conditions")):
        return None
    cond = {f: lv for f, lv in e.get("conditions", {}).items() if f in applies}
    span = {f: [weight(f, x) for x in (lv if isinstance(lv, list) else [lv])]
            for f, lv in cond.items()}
    lo = sum(min(w) for w in span.values())
    hi = sum(max(w) for w in span.values())
    per = {}
    insts = sorted(set().union(*[expand(o) for o in e.get("objects", [])])) or [None]
    for o in insts:
        fac = dict(cond)
        od = 0
        if o:
            ofac = {f: lv for f, lv in OBJ[o].items() if f in applies}
            fac.update(ofac)
            od = sum(weight(f, lv) for f, lv in ofac.items())
        per[o or "-"] = (lo + od, hi + od, fac)
    return min(p[0] for p in per.values()), max(p[1] for p in per.values()), per


RATED = {e["id"]: rate(e) for e in D}

if errors:
    print("=" * 78)
    print("TAXONOMY — ERRORS")
    for m in errors:
        print("  " + m)
    print(f"  -> {len(errors)} errors")
    sys.exit(1)

print("=" * 78)
print("T1 — Intrinsic difficulty (spec) vs level (empirical)")
print(f"  {'id':28s} {'node':24s} {'D':>5s} tier lvl")
mism = 0
for e in D:
    r = RATED[e["id"]]
    if not r or e["type"] not in ("achievement", "bonus"):
        continue
    lo, hi, _ = r
    ds = f"{lo}" if lo == hi else f"{lo}-{hi}"
    t = tier(hi)
    flag = "" if t == e["level"] else "  <- differs"
    mism += bool(flag)
    print(f"  {e['id']:28s} {e['taxonomy']:24s} {ds:>5s}  {t}   {e['level']}{flag}")
print(f"  -> {mism} lines where spec difficulty and empirical level disagree.")
print("     Not an error: either a factor is missing, or the level needs revisiting.")

# ── effective prices per (challenge, line) ───────────────────────────────────
# A bonus or discount attached to a parent via related_skill is not a skill of
# its own: picking a plate in Pick & Place pays MAN-PICK-01 + MAN-PICK-01B4.
lines = []
for slug, ch in CH.items():
    for it in ch["entries"]:
        e = DICT[it["ref"]]
        r = RATED[e["id"]]
        if not r or e.get("failure_mode") or e["type"] not in ("achievement", "bonus", "penalty_behavior"):
            continue
        parent = it.get("related_skill")
        if e["type"] == "achievement" or not parent:
            if e["type"] != "achievement":
                continue
            price, how = e["points"], f"{e['points']}"
        else:
            price = DICT[parent]["points"] + e["points"]
            how = f"{DICT[parent]['points']}{e['points']:+d}"
        lines.append(dict(slug=slug, id=e["id"], node=e["taxonomy"], lo=r[0], hi=r[1],
                          price=price, how=how))

print("=" * 78)
print("T2 — Price inversions within a skill (harder line pays less)")
by_node = defaultdict(list)
for l in lines:
    by_node[l["node"]].append(l)
inv = 0
for node, ls in sorted(by_node.items()):
    for a in ls:
        for b in ls:
            # a strictly harder than b over the whole range, yet paid strictly less
            if a["lo"] > b["hi"] and a["price"] < b["price"]:
                inv += 1
                print(f"  {node:20s} {a['id']:24s}[{a['slug'][:12]}] D{a['lo']}-{a['hi']} = {a['how']:>8s}"
                      f"  <  {b['id']}[{b['slug'][:12]}] D{b['lo']}-{b['hi']} = {b['how']}")
print(f"  -> {inv} inversions. Each is either a factor the model lacks, or price drift.")

print("-" * 78)
print("     Price per difficulty point, by skill (lines with D > 0)")
for node, ls in sorted(by_node.items()):
    if len(ls) < 2:
        continue
    pts = [(l["price"] / l["hi"], l) for l in ls if l["hi"] > 0]
    if len(pts) < 2:
        continue
    lo, hi = min(pts, key=lambda x: x[0]), max(pts, key=lambda x: x[0])
    print(f"  {node:20s} {lo[0]:6.1f} ({lo[1]['id']}) .. {hi[0]:6.1f} ({hi[1]['id']})"
          f"   spread x{hi[0] / lo[0]:.1f}")

print("=" * 78)
print("T3 — Penalty price per failure mode (same failure, same price?)")
fm = defaultdict(list)
for slug, ch in CH.items():
    for it in ch["entries"]:
        e = DICT[it["ref"]]
        if e.get("failure_mode") and e.get("points") is not None:
            fm[e["failure_mode"]].append((e["points"], e["id"], slug))
for mode, xs in sorted(fm.items()):
    prices = sorted({p for p, _, _ in xs})
    tag = "consistent" if len(prices) == 1 else f"{len(prices)} prices"
    print(f"  {mode:18s} {tag:11s} " + ", ".join(f"{p}" for p in prices))
    if len(prices) > 1:
        for p, i, s in sorted(set(xs)):
            print(f"      {p:5d}  {i:30s} {s}")

print("=" * 78)
print("T4 — Taxonomy coverage")
used = defaultdict(int)
for e in D:
    used[e["taxonomy"]] += 1
for st in ("proposed", "active"):
    ns = [n for n, v in NODES.items() if v["status"] == st]
    print(f"  {st:9s} {len(ns):3d} nodes")
unused = [n for n, v in NODES.items() if v["status"] == "active" and not used[n]
          and v.get("scored", True)
          and not any(m.get("parent") == n for m in NODES.values())]
proposed_used = [n for n, v in NODES.items() if v["status"] == "proposed" and used[n]]
print(f"  proposed (future skills, no scored line yet): "
      + ", ".join(n for n, v in NODES.items() if v["status"] == "proposed"))
if unused:
    print(f"  active but unscored leaf nodes: {', '.join(unused)}")
if proposed_used:
    print(f"  proposed but already scored — promote to active: {', '.join(proposed_used)}")

# ── machine-readable ratings ─────────────────────────────────────────────────
out = {}
for e in D:
    r = RATED[e["id"]]
    out[e["id"]] = {
        "taxonomy": e["taxonomy"],
        "objects": e.get("objects", []),
        "difficulty": None if not r else {
            "min": r[0], "max": r[1], "tier": tier(r[1]),
            "per_object": {o: {"min": a, "max": b, "factors": f} for o, (a, b, f) in r[2].items()},
        },
        "level": e["level"],
    }
json.dump(out, open(os.path.join(ROOT, "dist", "skill_ratings.json"), "w"), indent=1)
print("=" * 78)
print(f"T5 — Object data quality ({OSET['competition']})")
in_set = set().union(*[expand(g) for g in GROUPS])
used = set()
for e in D:
    for o in e.get("objects", []):
        used |= expand(o)
print(f"  objects in set: {len(in_set)}, used by a scored line: {len(used)}")
for src, msg in (("measured", "measured on the arena object"),
                 ("ycb", "YCB published values"),
                 ("estimate", "estimates — weigh/measure during Setup Days")):
    xs = sorted(o for o in (in_set | used) if o in CATALOG and CATALOG[o].get("values") == src)
    print(f"  {msg}: {len(xs)}")
    if xs and src != "measured":
        print("    " + ", ".join(xs))
print("-" * 78)
print("     Widest difficulty ranges (one line, very different objects)")
wide = sorted(((r[1] - r[0], i) for i, r in RATED.items() if r), reverse=True)[:5]
for spread, i in wide:
    lo, hi, per = RATED[i]
    easy = min(per, key=lambda o: per[o][0]); hard = max(per, key=lambda o: per[o][1])
    print(f"  {i:22s} D{lo}-{hi}  easiest {easy} (D{per[easy][0]}), hardest {hard} (D{per[hard][1]})")

print("=" * 78)
print("TAXONOMY PASS (findings above are questions, not failures)")
