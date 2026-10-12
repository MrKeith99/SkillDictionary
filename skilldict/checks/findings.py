"""Questions for the TC. Never failures: they say where the data or the rules
deserve a second look.

  T1  intrinsic difficulty vs empirical level, per line
  T2  price inversions inside one skill: a strictly harder line pays less
  T3  penalty prices per failure mode, across challenges
  T4  taxonomy coverage: proposed skills, unscored nodes
  T5  object data quality: estimated values, widest difficulty ranges
  A1  hard gates: a blocking dependency with no assisted route
  A2  assistance permitted, cost unspecified (§3.7.2 default only)
  A3  assistance permitted but not listed in the task description (§3.7.1)
  A4  dependencies on lines that do not exist yet
  A5  sibling variants of one skill priced differently across challenges
  A6  ambiguities flagged in the challenge files
  A7  autonomously-available vs raw points, per challenge
"""
from collections import defaultdict
from . import RULE


def taxonomy(b):
    D, CH, rt = b.skills, b.challenges, b.rater
    print(RULE)
    print("T1 — Intrinsic difficulty (spec) vs level (empirical)")
    print(f"  {'id':28s} {'node':24s} {'D':>5s} tier lvl")
    mism = 0
    for eid, e in D.items():
        r = rt.rated[eid]
        if not r or e["type"] not in ("achievement", "bonus"):
            continue
        lo, hi, _ = r
        ds = f"{lo}" if lo == hi else f"{lo}-{hi}"
        t = rt.tier(hi)
        flag = "" if t == e["level"] else "  <- differs"
        mism += bool(flag)
        print(f"  {eid:28s} {e['taxonomy']:24s} {ds:>5s}  {t}   {e['level']}{flag}")
    print(f"  -> {mism} lines where spec difficulty and empirical level disagree.")
    print("     Not an error: either a factor is missing, or the level needs revisiting.")

    # A bonus or discount attached to a parent via related_skill is not a skill
    # of its own: picking a plate in Pick & Place pays MAN-PICK-01 + MAN-PICK-01B4.
    lines = []
    for slug, ch in CH.items():
        for it in ch["entries"]:
            e = D[it["ref"]]
            r = rt.rated[e["id"]]
            if not r or e.get("failure_mode") or e["type"] not in ("achievement", "bonus", "penalty_behavior"):
                continue
            parent = it.get("related_skill")
            if e["type"] == "achievement" or not parent:
                if e["type"] != "achievement":
                    continue
                price, how = e["points"], f"{e['points']}"
            else:
                price = D[parent]["points"] + e["points"]
                how = f"{D[parent]['points']}{e['points']:+d}"
            lines.append(dict(slug=slug, id=e["id"], node=e["taxonomy"], lo=r[0], hi=r[1], price=price, how=how))

    print(RULE)
    print("T2 — Price inversions within a skill (harder line pays less)")
    by_node = defaultdict(list)
    for l in lines:
        by_node[l["node"]].append(l)
    inv = 0
    for node, ls in sorted(by_node.items()):
        for a in ls:
            for c in ls:
                if a["lo"] > c["hi"] and a["price"] < c["price"]:
                    inv += 1
                    print(f"  {node:20s} {a['id']:24s}[{a['slug'][:12]}] D{a['lo']}-{a['hi']} = {a['how']:>8s}"
                          f"  <  {c['id']}[{c['slug'][:12]}] D{c['lo']}-{c['hi']} = {c['how']}")
    print(f"  -> {inv} inversions. Each is either a factor the model lacks, or price drift.")
    print("-" * 78)
    print("     Price per difficulty point, by skill (lines with D > 0)")
    for node, ls in sorted(by_node.items()):
        pts = [(l["price"] / l["hi"], l) for l in ls if l["hi"] > 0 and l["price"] > 0]
        if len(ls) < 2 or len(pts) < 2:
            continue
        lo, hi = min(pts, key=lambda x: x[0]), max(pts, key=lambda x: x[0])
        print(f"  {node:20s} {lo[0]:6.1f} ({lo[1]['id']}) .. {hi[0]:6.1f} ({hi[1]['id']})"
              f"   spread x{hi[0] / lo[0]:.1f}")

    print(RULE)
    print("T3 — Penalty price per failure mode (same failure, same price?)")
    fm = defaultdict(list)
    for slug, ch in CH.items():
        for it in ch["entries"]:
            e = D[it["ref"]]
            if e.get("failure_mode") and e.get("points") is not None:
                fm[e["failure_mode"]].append((e["points"], e["id"], slug))
    for mode, xs in sorted(fm.items()):
        prices = sorted({p for p, _, _ in xs})
        tag = "consistent" if len(prices) == 1 else f"{len(prices)} prices"
        print(f"  {mode:18s} {tag:11s} " + ", ".join(f"{p}" for p in prices))
        if len(prices) > 1:
            for p, i, s in sorted(set(xs)):
                print(f"      {p:5d}  {i:30s} {s}")

    print(RULE)
    print("T4 — Taxonomy coverage")
    used = defaultdict(int)
    for e in D.values():
        used[e["taxonomy"]] += 1
    N = rt.nodes
    for st in ("proposed", "active"):
        print(f"  {st:9s} {sum(1 for v in N.values() if v['status'] == st):3d} nodes")
    unused = [n for n, v in N.items() if v["status"] == "active" and not used[n] and v.get("scored", True)
              and not any(m.get("parent") == n for m in N.values())]
    proposed_used = [n for n, v in N.items() if v["status"] == "proposed" and used[n]]
    print("  proposed (future skills, no scored line yet): "
          + ", ".join(n for n, v in N.items() if v["status"] == "proposed" and not used[n]))
    if unused:
        print(f"  active but unscored leaf nodes: {', '.join(unused)}")
    if proposed_used:
        print(f"  proposed and already scored: {', '.join(proposed_used)}")

    print(RULE)
    print(f"T5 — Object data quality ({rt.oset['competition']})")
    in_set = set().union(*[rt.expand(g) for g in rt.groups])
    used_o = set()
    for e in D.values():
        for o in e.get("objects", []):
            used_o |= rt.expand(o)
    print(f"  objects in set: {len(in_set)}, used by a scored line: {len(used_o)}")
    for src, msg in (("measured", "measured on the arena object"),
                     ("ycb", "YCB published values"),
                     ("estimate", "estimates — weigh/measure during Setup Days")):
        xs = sorted(o for o in (in_set | used_o) if o in rt.catalog and rt.catalog[o].get("values") == src)
        print(f"  {msg}: {len(xs)}")
        if xs and src != "measured":
            print("    " + ", ".join(xs))
    print("-" * 78)
    print("     Widest difficulty ranges (one line, very different objects)")
    wide = sorted(((r[1] - r[0], i) for i, r in rt.rated.items() if r), reverse=True)[:5]
    for spread, i in wide:
        lo, hi, per = rt.rated[i]
        easy = min(per, key=lambda o: per[o][0])
        hard = max(per, key=lambda o: per[o][1])
        print(f"  {i:22s} D{lo}-{hi}  easiest {easy} (D{per[easy][0]}), hardest {hard} (D{per[hard][1]})")


def assistance(b):
    D, CH = b.skills, b.challenges
    rows = [(slug, ch, it, D[it["ref"]]) for slug, ch in CH.items() for it in ch["entries"]]

    print(RULE)
    print("A1 — Unreachability: blocking dep whose prerequisite forbids assistance")
    hits = 0
    for slug, ch, it, e in rows:
        idx = {x["ref"]: x for x in ch["entries"]}
        for dep in it.get("depends_on", []):
            if dep.get("blocking") and not dep.get("satisfiable_by_assistance"):
                p = idx.get(dep["ref"])
                pa = p.get("assistance", {}).get("permitted") if p else None
                print(f"  [{slug:14s}] {it['ref']:22s} <- {dep['ref']:22s} (prereq assistance: {pa})")
                hits += 1
    print(f"  -> {hits} hard gates (no assisted route). Confirm each is intended.")

    print(RULE)
    print("A2 — Assistance permitted but cost unspecified")
    hits = 0
    for slug, ch, it, e in rows:
        a = it.get("assistance")
        if a and a.get("permitted") and a.get("extra_penalty_ref") is None and "extra_penalty" not in a:
            print(f"  [{slug:14s}] {it['ref']:24s} {e['description'][:44]}")
            hits += 1
    print(f"  -> {hits} entries fall back to the §3.7.2 default only.")

    print(RULE)
    print("A3 — Assistance permitted but NOT listed in task description (§3.7.1)")
    hits = 0
    for slug, ch, it, e in rows:
        a = it.get("assistance")
        if a and a.get("permitted") and a.get("listed_in_task_description") is False:
            print(f"  [{slug:14s}] {it['ref']:24s} {e['description'][:44]}")
            hits += 1
    print(f"  -> {hits} require Team Leader Meeting approval or a rulebook addition.")

    print(RULE)
    print("A4 — Dependencies on lines that do not exist yet")
    hits = 0
    for slug, ch, it, e in rows:
        for dep in it.get("depends_on", []):
            if dep["ref"] not in D:
                print(f"  [{slug:14s}] {it['ref']:22s} -> {dep['ref']} (undefined)")
                hits += 1
    print(f"  -> {hits} placeholder refs to define.")

    print(RULE)
    print("A5 — Cross-challenge price drift (same area+skill, different price)")
    used = b.used_by()
    fam = defaultdict(list)
    for e in D.values():
        if e["type"] == "achievement" and e["skill"] and used[e["id"]]:
            fam[(e["area"], e["skill"])].append(e)
    drift = 0
    for k, ents in sorted(fam.items()):
        chs = {c for e in ents for c in used[e["id"]]}
        if len(chs) > 1 and len({e["points"] for e in ents}) > 1:
            drift += 1
            print(f"  {k[0]}/{k[1]}")
            for e in sorted(ents, key=lambda x: (x["points"] or 0)):
                print(f"      {str(e['points']):>5} pts  {e['id']:22s} {','.join(used[e['id']]):28s} {e['modifiers']}")
    print(f"  -> {drift} skill families priced differently across challenges.")

    print(RULE)
    print("A6 — Flagged ambiguities requiring TC decision")
    n = 0
    for slug, ch, it, e in rows:
        if it.get("ambiguity"):
            n += 1
            print(f"  [{slug:14s}] {it['ref']}\n      {it['ambiguity']}")
    for slug, ch in CH.items():
        for k, v in ch.get("challenge_rules", {}).items():
            if isinstance(v, dict) and v.get("ambiguity"):
                n += 1
                print(f"  [{slug:14s}] rule:{k}\n      {v['ambiguity']}")
    print(f"  -> {n} open questions.")

    print(RULE)
    print("A7 — Autonomously-available vs raw points, by challenge")
    for slug, ch in CH.items():
        raw = auto = 0
        for it in ch["entries"]:
            e = D[it["ref"]]
            if e["type"] not in ("achievement", "bonus"):
                continue
            p = b.points(it["ref"], slug)
            if p is None:
                continue
            pt = p * it.get("count", 1)
            raw += pt
            if "no_assistance" in e["modifiers"] or (it.get("assistance") or {}).get("permitted") is False:
                auto += pt
        print(f"  {ch['challenge'][:34]:34s} raw {raw:5d} | autonomy-defined {auto:5d} ({100 * auto / raw:4.1f}%)")


def run(b):
    taxonomy(b)
    assistance(b)
    return 0
