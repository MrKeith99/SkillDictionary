"""The scoring page: every challenge's score sheet, and the analysis across them.

render/scoring.html with the data inlined -> <dist>/scoring.html. One tab per
challenge is its referee sheet (tick boxes add up live; nothing stored); the
overview compares the challenges.
"""
import json, os
from .. import paths
from ..difficulty import drange


def _line(b, slug, it):
    e = b.variants[it["ref"]]
    names = b.rater.names
    r = b.ratings[e["id"]]["difficulty"]
    a = it.get("assistance")
    parent = it.get("related_variant")
    return {
        "id": e["id"], "skill": e["skill"], "area": e["area"], "type": e["type"],
        "desc": e["description"], "points": b.points(e["id"], slug), "count": it.get("count", 1),
        "section": it.get("section") or "Main task",
        # a bonus or a failure sits under the line it belongs to
        "parent": parent if parent and (e["type"] == "bonus" or e.get("failure_mode")) else None,
        "fm": e.get("failure_mode"), "d": drange(r) or None, "dmin": r["min"] if r else None,
        "objects": [names.get(o, o.replace("_", " ")) for o in e.get("objects", [])],
        "at": [names.get(p, p.replace("_", " ")) for p in e.get("at", [])],
        "note": it.get("note"),
        "assist": None if a is None else {"permitted": a.get("permitted"), "note": a.get("note")},
    }


def data(b):
    used = b.used_by()
    skills = b.vocab["skills"]
    challenges = []
    for slug, ch in b.challenges.items():
        challenges.append({
            "slug": slug, "name": ch["challenge"], "section": ch["rulebook_section"],
            "minutes": ch["max_time_minutes"], "total": b.total(slug),
            "lines": [_line(b, slug, it) for it in ch["entries"]]})
    # price rule: every achievement of a skill, by D
    rule = {}
    for e in b.variants.values():
        r = b.ratings[e["id"]]["difficulty"]
        if e["type"] == "achievement" and not e.get("failure_mode") and r:
            rule.setdefault(e["skill"], []).append(
                {"id": e["id"], "d": r["min"], "points": e["points"], "desc": e["description"],
                 "used_by": used[e["id"]]})
    for v in rule.values():
        v.sort(key=lambda x: (x["d"], x["id"]))
    # widest difficulty ranges: one price over very different objects or places
    wide = []
    for i, x in b.rater.rated.items():
        if x and x[1] > x[0]:
            per = x[2]
            easy, hard = min(per, key=lambda o: per[o][0]), max(per, key=lambda o: per[o][1])
            wide.append({"id": i, "desc": b.variants[i]["description"], "lo": x[0], "hi": x[1],
                         "points": b.variants[i]["points"], "easy": easy, "hard": hard})
    wide.sort(key=lambda w: (w["lo"] - w["hi"], w["id"]))
    return {
        "release": f"{b.release.year} PROPOSAL" if not b.release.in_force else f"Rulebook {b.rulebook_version}",
        "rulebook_version": b.rulebook_version,
        "areas": ["NAV", "MAN", "OBJ", "PPL", "HRI", "NLU", "PLN"],
        "skills": {s: {"name": n["name"], "intent": n["intent"].strip(), "base": n.get("base")}
                   for s, n in skills.items()},
        "challenges": challenges,
        "rule": rule,
        "wide": wide[:8],
    }


def write(b):
    out = data(b)
    page = paths.template("scoring.html").replace("__DATA__", json.dumps(out).replace("</", "<\\/"))
    paths.write_text(page, os.path.join(paths.DIST, "scoring.html"))
    return out
