#!/usr/bin/env python3
"""Build a scoring proposal on top of the current dictionary.

Usage: build_proposal.py proposals/2027/*.yaml
Reads : dist/*.json (run tools/ci.sh first), the proposal file
Writes: dist/proposal_<year>/  dictionary.json, challenges.json, vocabulary.json,
        skill_ratings.json, <slug>_commands.json, scoresheets/<slug>.tex

Steps
  1. overlay the proposal's new lines and challenge on the current build
  2. rate the new lines (check_taxonomy.py on the overlay)
  3. price them with the 2027 rule; the skill bases come from the current
     lines only, so a proposal cannot shift the prices of existing skills
  4. expand every command the generator can produce into its steps, value it,
     and set the completion bonus and the sheet's maximum from that
  5. write the score sheet

Nothing under dictionary/ or challenges/ is touched.
"""
import itertools, json, os, re, shutil, subprocess, sys
from collections import Counter
import yaml
from pricing_rule import weight, rnd, calibrate, dmin

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DIST = os.path.join(ROOT, "dist")


def load(path):
    with open(path) as fh:
        return json.load(fh)


def dump(obj, path):
    with open(path, "w") as fh:
        json.dump(obj, fh, indent=2)


def run(script, out, *args):
    env = dict(os.environ, SKILLDICT_DIST=out)
    r = subprocess.run([sys.executable, os.path.join(HERE, script), *args],
                       env=env, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"{script} failed on the proposal:\n{r.stdout[-3000:]}{r.stderr[-2000:]}")
    return r.stdout


def expand(cs, name, kind):
    """All step sequences a template or follow-up can produce."""
    spec = cs[kind][name]
    if not spec.get("then"):
        return [list(spec["steps"])]
    out = []
    for f in cs["slots"][spec["then"]]:
        for tail in expand(cs, f, "followups"):
            out.append(list(spec["steps"]) + tail)
    return out


def command_values(P, price, entries, adds):
    """GPSR-style proposals: value every generator command, set the completion
    bonus and the sheet maximum. Returns the report lines."""
    cs = P["command_steps"]
    chains = {t: expand(cs, t, "templates") for t in cs["templates"]}
    wp, wo = cs["weights"]["people"], cs["weights"]["objects"]
    prob = Counter()
    for w in (wp, wo):
        tot = sum(w.values())
        for t, x in w.items():
            prob[t] += 0.5 * x / tot        # one list is drawn, 50/50
    value = {}
    for t, seqs in chains.items():
        vals = [sum(price[s] for s in seq) for seq in seqs]
        # follow-ups are drawn uniformly, so every expansion is equally likely
        value[t] = {"min": min(vals), "mean": sum(vals) / len(vals), "max": max(vals), "p": prob[t]}
    mean_cmd = sum(v["mean"] * v["p"] for v in value.values())
    bonus = next(e for e in adds if e.get("points_rule") == "calibrate")
    target = P["completion_bonus"]["calibrate_to"]
    bonus["points"] = max(0, rnd(target - mean_cmd))
    price[bonus["id"]] = bonus["points"]
    best = max(v["max"] for v in value.values()) + bonus["points"]
    fixed = sum((price[it["ref"]] or 0) * it["count"] for it in entries
                if it.get("section") != "Command steps" and not it["ref"].startswith("SPECIAL")
                and (price[it["ref"]] or 0) > 0)
    P["challenge"]["max_score"] = fixed + 3 * best
    rep = [f"  average command (generator weights): {mean_cmd:.0f} in skills + {bonus['points']} "
           f"completion bonus = {mean_cmd + bonus['points']:.0f}  (2026: flat {target})",
           "  per command type (skills only, before the bonus):"]
    for t, v in sorted(value.items(), key=lambda x: -x[1]["mean"]):
        rng = f"{v['min']}" if v["min"] == v["max"] else f"{v['min']}-{v['max']}"
        rep.append(f"    {t:28s} {v['p']:5.1%}  {rng:>9s}  mean {v['mean']:.0f}")
    rep.append(f"  sheet maximum: {P['challenge']['max_score']} (fixed lines + 3 x best command)")
    return rep, {"mean_command": round(mean_cmd, 1), "completion_bonus": bonus["points"],
                 "max_score": P["challenge"]["max_score"],
                 "templates": {t: {**v, "steps": chains[t]} for t, v in value.items()}}


def main(paths):
    props = []
    for path in paths:
        with open(path) as fh:
            props.append(yaml.safe_load(fh))
    years = {P["year"] for P in props}
    if len(years) != 1:
        sys.exit(f"proposals mix years: {sorted(years)}")
    out = os.path.join(DIST, f"proposal_{years.pop()}")
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(out)

    dic = load(os.path.join(DIST, "dictionary.json"))
    chs = load(os.path.join(DIST, "challenges.json"))
    ratings = load(os.path.join(DIST, "skill_ratings.json"))
    vocab = load(os.path.join(DIST, "vocabulary.json"))

    # skill bases from the current standalone lines only
    children = {it["ref"] for ch in chs["challenges"].values() for it in ch["entries"] if it.get("related_skill")}
    base = calibrate([e for e in dic["skills"]
                      if e["type"] == "achievement" or (e["type"] == "bonus" and e["id"] not in children)], ratings)

    # 1-2: overlay every proposal, then rate once
    skills = {e["id"]: dict(e) for e in dic["skills"]}
    challenges = dict(chs["challenges"])
    adds_all = []
    for P in props:
        slug = P.get("slug", "(lines)")
        for eid, change in (P.get("dictionary_changes") or {}).items():
            if eid not in skills:
                sys.exit(f"{slug}: dictionary_changes names unknown line {eid}")
            skills[eid].update(change)
        adds = [dict(e) for e in P.get("dictionary_additions") or []]
        for e in adds:
            if e["id"] in skills:
                sys.exit(f"{slug}: {e['id']} already exists in the dictionary")
            e["priced_by_rule"] = "points" not in e and e["type"] == "achievement"
            e.setdefault("points", 0)
            skills[e["id"]] = e
        P["_adds"] = adds
        adds_all += adds
        if "challenge" not in P:
            continue
        most = Counter()
        if P.get("command_steps"):
            for t in P["command_steps"]["templates"]:
                for seq in expand(P["command_steps"], t, "templates"):
                    for step, n in Counter(seq).items():
                        most[step] = max(most[step], n)
        entries = []
        for it in P["challenge"]["entries"]:
            it = dict(it)
            it.setdefault("count", 3 * most[it["ref"]])     # three commands per test
            entries.append(it)
        P["challenge"]["entries"] = entries
        challenges[slug] = P["challenge"]
    # swaps in challenges that are not otherwise re-proposed
    for P in props:
        for slug, swaps in (P.get("replace_refs") or {}).items():
            ch = dict(challenges[slug])
            ch["entries"] = [{**it, "ref": swaps.get(it["ref"], it["ref"])} for it in ch["entries"]]
            challenges[slug] = ch
    # lines added to a challenge: at the end of their section, before the
    # Special Penalties & Bonuses the sheet template appends itself
    for P in props:
        for slug, items in (P.get("add_entries") or {}).items():
            ents = list(challenges[slug]["entries"])
            for it in items:
                pos = [k for k, e in enumerate(ents) if e.get("section") == it.get("section")]
                spec = [k for k, e in enumerate(ents) if e["ref"].startswith("SPECIAL")]
                at = pos[-1] + 1 if pos else (spec[0] if spec else len(ents))
                ents.insert(at, dict(it))
            challenges[slug] = {**challenges[slug], "entries": ents}
    used = {}
    for slug, ch in challenges.items():
        for it in ch["entries"]:
            used.setdefault(it["ref"], set()).add(slug)
    for e in skills.values():
        e["used_by"] = sorted(used.get(e["id"], []))

    def write():
        dump({**dic, "skills": list(skills.values())}, os.path.join(out, "dictionary.json"))
        dump({**chs, "challenges": challenges}, os.path.join(out, "challenges.json"))
        dump(vocab, os.path.join(out, "vocabulary.json"))
    write()
    run("check_taxonomy.py", out)
    rat = load(os.path.join(out, "skill_ratings.json"))

    # 3: price new achievement lines that carry no explicit points
    price = {i: e.get("points") for i, e in skills.items()}
    for e in adds_all:
        if e.pop("priced_by_rule"):
            d = dmin(rat, e["id"])
            if e["taxonomy"] not in base or d is None:
                sys.exit(f"{e['id']}: no base for {e['taxonomy']} or no difficulty — add base_like/override")
            e["points"] = rnd(base[e["taxonomy"]] * weight(d))
            price[e["id"]] = e["points"]

    # 4: command proposals value their commands
    reports = {}
    for P in props:
        if P.get("command_steps"):
            reports[P["slug"]], data = command_values(P, price, P["challenge"]["entries"], P["_adds"])
            dump(data, os.path.join(out, f"{P['slug']}_commands.json"))
    write()
    run("check_taxonomy.py", out)

    # 5: score sheets and report
    for P in props:
        if "challenge" not in P:
            print("=" * 78)
            print("PROPOSAL: line changes")
            for eid, ch_ in (P.get("dictionary_changes") or {}).items():
                print(f"    ~ {eid:26s} {skills[eid]['points']:5d}  {' '.join(skills[eid]['description'].split())}")
            for slug, swaps in (P.get("replace_refs") or {}).items():
                print(f"    {slug}: " + ", ".join(f"{a} -> {b}" for a, b in swaps.items()))
            changed = set(P.get("dictionary_changes") or {})
            for e in P["_adds"]:
                print(f"    + {e['id']:26s} {e['points']:5d}  {' '.join(e['description'].split())}")
            changed |= {e["id"] for e in P["_adds"]}
            hit = sorted(set(P.get("replace_refs") or {}) | set(P.get("add_entries") or {}) |
                         {sl for sl, c in challenges.items() if changed & {it["ref"] for it in c["entries"]}})
            for slug in hit:                 # every sheet that shows a changed line
                print(run("build_scoresheet.py", out, slug, "--tex").strip())
            continue
        slug, ch = P["slug"], P["challenge"]
        print(run("build_scoresheet.py", out, slug, "--tex").strip())
        old = sum((e["points"] or 0) * it.get("count", 1) for it in chs["challenges"].get(slug, {}).get("entries", [])
                  for e in [skills[it["ref"]]] if (e["points"] or 0) > 0 and e["type"] != "administrative")
        new = ch.get("max_score") or sum((price[it["ref"]] or 0) * it["count"] for it in ch["entries"]
                                         if (price[it["ref"]] or 0) > 0 and not it["ref"].startswith("SPECIAL"))
        print("=" * 78)
        print(f"PROPOSAL: {ch['challenge']}  (max {old} -> {new})")
        for e in P["_adds"]:
            r = (rat.get(e["id"]) or {}).get("difficulty") or {}
            d = "" if not r else (f"D{r['min']}" if r["min"] == r["max"] else f"D{r['min']}-{r['max']}")
            n = sum(it["count"] for it in ch["entries"] if it["ref"] == e["id"])
            print(f"    + {e['id']:26s} {e['taxonomy']:22s} {d:6s} {e['points']:5d}  x{n}")
        for eid in P.get("dictionary_changes") or {}:
            print(f"    ~ {eid:26s} {skills[eid]['description']}")
        for line in reports.get(slug, []):
            print(line)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1:])
