"""A season's pricing rule (data/seasons/<year>/pricing.yaml), as functions.

Rule prices new lines when a proposal season is built (overlay.py), and
reprice() applies the rule to every line of a build so the TC can review what
the rule would do (`skilldict prices`). Both use exactly the same rule.
"""
import statistics
from collections import defaultdict, OrderedDict
from .ratings import dmin, drange


class Rule:
    def __init__(self, spec, year):
        self.spec, self.year = spec, year
        self.d_scale = spec["d_scale"]
        self.fixed_penalty = spec.get("fixed_penalty") or {}
        self.penalty_share = spec["penalty_share"]

    def weight(self, d):
        return 1 + d / self.d_scale

    def rnd(self, x):
        sign = -1 if x < 0 else 1
        for r in self.spec["rounding"]:
            if abs(x) >= r["from"]:
                return sign * int(round(abs(x) / r["step"]) * r["step"])
        return sign * int(round(abs(x)))

    def calibrate(self, lines, ratings):
        """Skill base per node: median of price / weight(D) over the given lines,
        then overrides, then `base_like` for nodes with no line of their own."""
        implied = defaultdict(list)
        for e in lines:
            d = dmin(ratings, e["id"])
            if e.get("points") and d is not None:
                implied[e["taxonomy"]].append(e["points"] / self.weight(d))
        base = {n: statistics.median(v) for n, v in implied.items()}
        base.update(self.spec.get("base_overrides") or {})
        for node, like in (self.spec.get("base_like") or {}).items():
            if node not in base and like in base:
                base[node] = base[like]
        return base


def rule_of(season):
    spec = season.pricing()
    return Rule(spec, season.year) if spec else None


def children(build):
    """Lines that hang off a parent line somewhere (related_skill)."""
    return {it["ref"] for ch in build.challenges.values() for it in ch["entries"] if it.get("related_skill")}


def standalone_lines(build):
    """Lines priced on their own: achievements, and bonuses that never hang
    off a parent (e.g. the interleaving bonus)."""
    kids = children(build)
    return [e for e in build.skills.values()
            if e["type"] == "achievement" or (e["type"] == "bonus" and e["id"] not in kids)]


def parents(ch):
    """The line every bonus, discount or penalty belongs to, in one challenge."""
    out = {}
    for it in ch["entries"]:
        if it.get("related_skill"):
            out[it["ref"]] = it["related_skill"]
        a = it.get("assistance") or {}
        if a.get("extra_penalty_ref"):
            out.setdefault(a["extra_penalty_ref"], it["ref"])
    return out


class Repricing:
    """What the rule does to every line of a build, and to its findings."""

    def __init__(self, build, rule):
        self.build, self.rule = build, rule
        D, R = build.skills, build.ratings
        standalone = {e["id"] for e in standalone_lines(build)}
        self.base = rule.calibrate([D[i] for i in standalone], R)

        def rule_price(eid):
            e = D[eid]
            if e["taxonomy"] not in self.base or dmin(R, eid) is None:
                return None
            return self.base[e["taxonomy"]] * rule.weight(dmin(R, eid))

        new = {}                                     # id -> (price, how)
        for eid, e in D.items():
            if e["type"] != "administrative" and eid in standalone:
                p = rule_price(eid)
                new[eid] = (rule.rnd(p), f"base {self.base[e['taxonomy']]:.0f} x {rule.weight(dmin(R, eid)):.2f}") \
                    if p is not None else (e.get("points"), "kept: no difficulty factors")
        ach = dict(new)
        for slug, ch in build.challenges.items():
            par = parents(ch)
            for it in ch["entries"]:
                eid = it["ref"]
                e = D[eid]
                if eid in standalone or e["type"] == "administrative":
                    continue
                old, parent, fm = e.get("points"), par.get(eid), e.get("failure_mode")
                if old is None:
                    res = (None, "kept: judged on the day")
                elif old == 0:
                    res = (0, "kept: explicitly free")
                elif fm in rule.fixed_penalty:
                    res = (rule.fixed_penalty[fm], f"{fm}: fixed conduct penalty")
                elif fm:
                    if not parent or ach.get(parent, (None,))[0] is None:
                        res = (old, "kept: penalty with no priced parent line")
                    else:
                        share = rule.penalty_share[fm]
                        res = (-rule.rnd(share * ach[parent][0]), f"{fm} {share:.0%} of {parent}")
                else:                                # bonus or discount on a parent
                    rp, pp = rule_price(eid), ach.get(parent, (None,))[0] if parent else None
                    if rp is None or pp is None:
                        res = (old, "kept: no difficulty factors" if rp is None else "kept: no parent line")
                    else:
                        res = (rule.rnd(rp) - pp, f"rule at D{dmin(R, eid)} = {rule.rnd(rp)}, minus parent {pp}")
                if eid in new and new[eid][0] != res[0]:
                    res = (new[eid][0], new[eid][1] + f"; CONFLICT in {slug}: {res[0]}")
                new.setdefault(eid, res)
                if "CONFLICT" in res[1]:
                    new[eid] = res
        self.new = new

        self.rows = []
        for slug, ch in build.challenges.items():
            par = parents(ch)
            for it in ch["entries"]:
                eid = it["ref"]
                e = D[eid]
                if e["type"] == "administrative":
                    continue
                p, how = new[eid]
                self.rows.append(OrderedDict(
                    challenge=slug, section=it.get("section") or "", id=eid, node=e["taxonomy"], type=e["type"],
                    description=e["description"], D=drange(R, eid), count=it.get("count", 1),
                    points_old=e.get("points"), points_new=p,
                    delta=None if p is None or e.get("points") is None else p - e["points"],
                    parent=par.get(eid, ""), rule=how))

        old_of = lambda i: D[i].get("points")
        new_of = lambda i: new.get(i, (None,))[0]
        self.inv_old, self.inv_new = self.inversions(old_of), self.inversions(new_of)
        self.pen_old = defaultdict(set)
        for e in D.values():
            if e.get("failure_mode") and e.get("points") is not None:
                self.pen_old[e["failure_mode"]].add(e["points"])
        self.tot_old, self.tot_new = self.totals(old_of), self.totals(new_of)
        self.kept = sorted({(r["id"], r["rule"]) for r in self.rows if r["rule"].startswith("kept")})

    def effective(self, price_of, slug):
        """(node, Dmin, Dmax, effective price, id) for every achievement / bonus line."""
        D, R = self.build.skills, self.build.ratings
        ch = self.build.challenges[slug]
        par = parents(ch)
        out = []
        for it in ch["entries"]:
            e = D[it["ref"]]
            r = (R.get(e["id"]) or {}).get("difficulty")
            if not r or e.get("failure_mode") or e["type"] not in ("achievement", "bonus", "penalty_behavior"):
                continue
            p = price_of(e["id"])
            if p is None:
                continue
            if e["type"] != "achievement":
                parent = par.get(e["id"])
                if not parent or price_of(parent) is None:
                    continue
                p += price_of(parent)
            out.append((e["taxonomy"], r["min"], r["max"], p, e["id"]))
        return out

    def inversions(self, price_of):
        by = defaultdict(list)
        for s in self.build.challenges:
            for l in self.effective(price_of, s):
                by[l[0]].append(l)
        return [(node, a, b) for node, ls in by.items() for a in ls for b in ls
                if a[1] > b[2] and a[3] < b[3]]

    def totals(self, price_of):
        D = self.build.skills
        return {slug: sum((price_of(it["ref"]) or 0) * it.get("count", 1) for it in ch["entries"]
                          if D[it["ref"]]["type"] != "administrative" and (price_of(it["ref"]) or 0) > 0)
                for slug, ch in self.build.challenges.items()}

    def lines(self):
        """Rows with the years in the column names (points_2026, points_2027)."""
        y = {"points_old": f"points_{self.build.season.year}", "points_new": f"points_{self.rule.year}"}
        return [OrderedDict((y.get(k, k), v) for k, v in r.items()) for r in self.rows]

    def as_json(self):
        y0, y1 = str(self.build.season.year), str(self.rule.year)
        return {"rule": self.rule.spec, "base": {n: round(b, 1) for n, b in sorted(self.base.items())},
                "lines": self.lines(),
                "totals": {s: {y0: self.tot_old[s], y1: self.tot_new[s]} for s in self.build.challenges},
                "inversions": {y0: len(self.inv_old), y1: len(self.inv_new)}}
