"""Build a proposal season: its base season plus the files in changes/.

A change file may hold any of these keys; they are applied in this order,
file by file in name order, then the swaps and additions of all files:

  dictionary_changes:    {ID: {field: value}}   edit existing lines
  dictionary_additions:  [entry, ...]           new lines; an achievement with
                                                no `points` is priced by the
                                                season's pricing rule
  slug + challenge:      a full challenge, replacing the base one
  command_steps:         GPSR-style: what each generator command scores; sets
  completion_bonus:      the completion bonus and the sheet maximum
  replace_refs:          {slug: {OLD-ID: NEW-ID}}  swap a line in a challenge
  add_entries:           {slug: [entry, ...]}   add lines at the end of their
                                                section

The base season's prices of existing skills never move: the rule's skill bases
are calibrated on the base season's lines only.
"""
from collections import Counter
from . import model, ratings
from .model import DataError
from .pricing import rule_of, standalone_lines

COMMANDS_PER_TEST = 3          # GPSR: the robot gets three commands


def expand(cs, name, kind):
    """All step sequences a template or follow-up can produce."""
    spec = cs[kind][name]
    if not spec.get("then"):
        return [list(spec["steps"])]
    return [list(spec["steps"]) + tail
            for f in cs["slots"][spec["then"]] for tail in expand(cs, f, "followups")]


def apply(base, season):
    b = model.copy_build(base, season)
    files = season.changes()
    adds_by_file = {}
    for name, P in files:
        for eid, change in (P.get("dictionary_changes") or {}).items():
            if eid not in b.skills:
                raise DataError(f"{name}: dictionary_changes names unknown line {eid}")
            b.skills[eid].update(change)
        adds = []
        for e in P.get("dictionary_additions") or []:
            e = dict(e)
            if e["id"] in b.skills:
                raise DataError(f"{name}: {e['id']} already exists")
            e.setdefault("points", 0)
            b.skills[e["id"]] = e
            adds.append(e)
        adds_by_file[name] = adds
        if "challenge" in P:
            most = Counter()
            if P.get("command_steps"):
                for t in P["command_steps"]["templates"]:
                    for seq in expand(P["command_steps"], t, "templates"):
                        for step, n in Counter(seq).items():
                            most[step] = max(most[step], n)
            ch = dict(P["challenge"])
            ch["entries"] = [{**it, "count": it.get("count", COMMANDS_PER_TEST * most[it["ref"]]
                                                     if P.get("command_steps") else 1)}
                             for it in ch["entries"]]
            b.challenges[P["slug"]] = ch
    for name, P in files:
        for slug, swaps in (P.get("replace_refs") or {}).items():
            ch = b.challenges[slug]
            ch["entries"] = [{**it, "ref": swaps.get(it["ref"], it["ref"])} for it in ch["entries"]]
    # added lines go at the end of their section, before the Special Penalties
    # & Bonuses the sheet template appends itself
    for name, P in files:
        for slug, items in (P.get("add_entries") or {}).items():
            ents = b.challenges[slug]["entries"]
            for it in items:
                pos = [k for k, e in enumerate(ents) if e.get("section") == it.get("section")]
                spec = [k for k, e in enumerate(ents) if e["ref"].startswith("SPECIAL")]
                ents.insert(pos[-1] + 1 if pos else (spec[0] if spec else len(ents)), dict(it))
    b.skills = model.sort_skills(b.skills)

    ratings.rate(b)
    if b.errors:
        return b

    # price new achievement lines that carry no explicit points
    rule = rule_of(season)
    by_rule = [e for adds in adds_by_file.values() for e in adds
               if e["type"] == "achievement" and not _authored_points(files, e["id"])]
    if by_rule or any(P.get("command_steps") for _, P in files):
        if rule is None:
            raise DataError(f"{season}: lines need pricing but there is no pricing.yaml")
        base_prices = rule.calibrate(standalone_lines(base), base.ratings)
        for e in by_rule:
            d = ratings.dmin(b.ratings, e["id"])
            if e["taxonomy"] not in base_prices or d is None:
                raise DataError(f"{e['id']}: no base for {e['taxonomy']} or no difficulty — add base_like/override")
            e["points"] = rule.rnd(base_prices[e["taxonomy"]] * rule.weight(d))

    for name, P in files:
        if P.get("command_steps"):
            b.extra[f"{P['slug']}_commands.json"] = _command_values(b, P, rule)
        for e in adds_by_file[name]:
            e.pop("points_rule", None)
    _report(b, base, files, adds_by_file)
    return b


def _authored_points(files, eid):
    return any("points" in e for _, P in files for e in P.get("dictionary_additions") or [] if e["id"] == eid)


def _command_values(b, P, rule):
    """Value every generator command; set the completion bonus and the sheet maximum."""
    cs, slug = P["command_steps"], P["slug"]
    chains = {t: expand(cs, t, "templates") for t in cs["templates"]}
    prob = Counter()
    for w in cs["weights"].values():
        tot = sum(w.values())
        for t, x in w.items():
            prob[t] += x / tot / len(cs["weights"])      # one list is drawn, uniformly
    price = lambda i: b.skills[i]["points"]
    value = {}
    for t, seqs in chains.items():
        vals = [sum(price(s) for s in seq) for seq in seqs]
        # follow-ups are drawn uniformly, so every expansion is equally likely
        value[t] = {"min": min(vals), "mean": sum(vals) / len(vals), "max": max(vals), "p": prob[t]}
    mean_cmd = sum(v["mean"] * v["p"] for v in value.values())
    bonus = next(e for e in P["dictionary_additions"] if e.get("points_rule") == "calibrate")
    target = P["completion_bonus"]["calibrate_to"]
    b.skills[bonus["id"]]["points"] = points = max(0, rule.rnd(target - mean_cmd))
    best = max(v["max"] for v in value.values()) + points
    ch = b.challenges[slug]
    fixed = sum((price(it["ref"]) or 0) * it["count"] for it in ch["entries"]
                if it.get("section") != "Command steps" and not it["ref"].startswith("SPECIAL")
                and (price(it["ref"]) or 0) > 0)
    ch["max_score"] = fixed + COMMANDS_PER_TEST * best
    rep = [f"  average command (generator weights): {mean_cmd:.0f} in skills + {points} "
           f"completion bonus = {mean_cmd + points:.0f}  ({b.base.season.year}: flat {target})",
           "  per command type (skills only, before the bonus):"]
    for t, v in sorted(value.items(), key=lambda x: -x[1]["mean"]):
        rng = f"{v['min']}" if v["min"] == v["max"] else f"{v['min']}-{v['max']}"
        rep.append(f"    {t:28s} {v['p']:5.1%}  {rng:>9s}  mean {v['mean']:.0f}")
    rep.append(f"  sheet maximum: {ch['max_score']} (fixed lines + {COMMANDS_PER_TEST} x best command)")
    P["_report"] = rep
    return {"mean_command": round(mean_cmd, 1), "completion_bonus": points, "max_score": ch["max_score"],
            "templates": {t: {**v, "steps": chains[t]} for t, v in value.items()}}


def _report(b, base, files, adds_by_file):
    out = b.reports
    for name, P in files:
        adds = adds_by_file[name]
        out.append("=" * 78)
        if "challenge" in P:
            slug = P["slug"]
            old = base.total(slug) if slug in base.challenges else 0
            out.append(f"{name}: {P['challenge']['challenge']}  (max {old} -> {b.total(slug)})")
        else:
            out.append(f"{name}: line changes")
        for e in adds:
            r = (b.ratings.get(e["id"]) or {}).get("difficulty") or {}
            d = "" if not r else (f"D{r['min']}" if r["min"] == r["max"] else f"D{r['min']}-{r['max']}")
            n = sum(it["count"] for ch in b.challenges.values() for it in ch["entries"] if it["ref"] == e["id"])
            out.append(f"    + {e['id']:26s} {e['taxonomy']:22s} {d:6s} {e['points']:5d}  x{n}")
        for eid in P.get("dictionary_changes") or {}:
            out.append(f"    ~ {eid:26s} {b.skills[eid]['points']:5d}  {' '.join(b.skills[eid]['description'].split())}")
        for slug, swaps in (P.get("replace_refs") or {}).items():
            out.append(f"    {slug}: " + ", ".join(f"{a} -> {c}" for a, c in swaps.items()))
        for slug, items in (P.get("add_entries") or {}).items():
            out.append(f"    {slug}: + " + ", ".join(it["ref"] for it in items))
        out.extend(P.get("_report", []))
