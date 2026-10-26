"""Questions for the TC. Never failures: they say where the data or the rules
deserve a second look.

  T1  price rule: an achievement that does not pay base x (1 + D/4)
  T2  penalties per failure mode: derived shares, and the authored ones
  T3  skill coverage: proposed skills, unscored skills
  T4  object data quality: estimated values, widest difficulty ranges
"""
from collections import defaultdict
from . import RULE
from ..penalties import rounded


def skills(b):
    D, CH, rt = b.variants, b.challenges, b.rater
    print(RULE)
    # Every achievement follows the rule, so a harder variant of a skill never
    # pays less. Bonuses pay for what D does not measure (a goal, a first pick).
    print("T1 — Price rule: base x (1 + D/4), D the easiest instance (data/skills.yaml)")
    off = nobase = 0
    for vid, e in sorted(D.items()):
        r = rt.rated[vid]
        if e["type"] != "achievement" or e.get("failure_mode") or not r:
            continue
        base = rt.skills[e["skill"]].get("base")
        if base is None:
            nobase += 1
            print(f"  {vid:24s} {e['skill']:22s} D{r[0]} = {e['points']:>5}   skill has no base")
            continue
        rule = rounded(base * (1 + r[0] / 4))
        if e["points"] != rule:
            off += 1
            print(f"  {vid:24s} {e['skill']:22s} D{r[0]} = {e['points']:>5}   rule {base} x {1 + r[0] / 4:g} = {rule}")
    print(f"  -> {off} off the rule, {nobase} without a base. Bonuses and unrated lines are not checked.")

    print(RULE)
    print("T2 — Penalties per failure mode (same failure, same share?)")
    # Penalties the build derives are share x their line by construction; only
    # the authored ones (data/variants/) can depart from the failure's share.
    fm = defaultdict(lambda: [0, set()])
    for slug, ch in CH.items():
        for it in ch["entries"]:
            e = D[it["ref"]]
            if not e.get("failure_mode"):
                continue
            if e.get("penalty_of"):
                fm[e["failure_mode"]][0] += 1
            else:
                fm[e["failure_mode"]][1].add((e.get("points"), e["id"], slug))
    shares = b.vocab["failure_modes"]
    for mode, (n, own) in sorted(fm.items()):
        sh = shares[mode].get("share")
        print(f"  {mode:18s} share {'-' if sh is None else f'{sh:.0%}':>4s}  {n:3d} derived, {len(own)} authored")
        for p, i, s in sorted(own, key=lambda x: (x[0] or 0, x[1], x[2])):
            print(f"      {'%' if p is None else p:>5}  {i:30s} {s}")

    print(RULE)
    print("T3 — Skill coverage")
    used = defaultdict(int)
    for e in D.values():
        used[e["skill"]] += 1
    N = rt.skills
    for st in ("proposed", "active"):
        print(f"  {st:9s} {sum(1 for v in N.values() if v['status'] == st):3d} skills")
    unused = [n for n, v in N.items() if v["status"] == "active" and not used[n] and v.get("scored", True)
              and not any(m.get("parent") == n for m in N.values())]
    proposed_used = [n for n, v in N.items() if v["status"] == "proposed" and used[n]]
    future = [n for n, v in N.items() if v["status"] == "proposed" and not used[n]]
    if future:
        print(f"  proposed (future skills, no scored line yet): {', '.join(future)}")
    if unused:
        print(f"  active but unscored skills: {', '.join(unused)}")
    if proposed_used:
        print(f"  proposed and already scored: {', '.join(proposed_used)}")

    print(RULE)
    print(f"T4 — Object data quality ({rt.oset['competition']})")
    in_set = set().union(*[rt.expand(g) for g in rt.groups])
    used_o = set()
    for e in D.values():
        for o in e.get("objects", []):
            used_o |= rt.expand(o)
    cv = b.vocab["objects"]["catalog_values"]
    print(f"  objects in set: {len(in_set)}, used by a variant: {len(in_set & used_o)}; masses and sizes are "
          f"{cv}" + (" — weigh and measure during Setup Days" if cv != "measured" else ""))
    F = rt.furniture
    used_p = set()
    for e in D.values():
        for a in e.get("at", []):
            used_p |= rt.expand_at(a)
    print(f"  furniture: {len(rt.place)} places, {len(used_p)} used by a variant; heights are "
          f"{F.get('values')}" + (" — measure during Setup Days" if F.get("values") != "measured" else ""))
    print("-" * 78)
    print("     Widest difficulty ranges (one line, very different objects or places)")
    wide = sorted(((r[1] - r[0], i) for i, r in rt.rated.items() if r), reverse=True)[:5]
    for spread, i in wide:
        lo, hi, per = rt.rated[i]
        easy = min(per, key=lambda o: per[o][0])
        hard = max(per, key=lambda o: per[o][1])
        print(f"  {i:22s} D{lo}-{hi}  easiest {easy} (D{per[easy][0]}), hardest {hard} (D{per[hard][1]})")


def run(b):
    skills(b)
    return 0
