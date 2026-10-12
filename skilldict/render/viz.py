"""The skill coverage page: area x challenge matrix, price drift, every line.

templates/viz.html with the data inlined -> <dist>/skill_coverage.html, plus
the data alone in <dist>/viz_data.json.
"""
import json, os
from collections import defaultdict
from .. import paths


def data(b):
    used = b.used_by()
    rows, matrix, challenges = [], defaultdict(lambda: defaultdict(int)), {}
    for slug, ch in b.challenges.items():
        challenges[slug] = {"name": ch["challenge"], "section": ch["rulebook_section"],
                            "minutes": ch["max_time_minutes"], "total": b.total(slug)}
        for it in ch["entries"]:
            e = b.skills[it["ref"]]
            pts = b.points(e["id"], slug)
            cnt = it.get("count", 1)
            total = (pts or 0) * cnt
            rows.append({
                "challenge": slug, "id": e["id"], "area": e["area"],
                "skill": e["skill"], "modifiers": e["modifiers"],
                "description": e["description"], "level": e["level"],
                "type": e["type"], "points": pts, "count": cnt, "total": total,
                "section": it.get("section"), "shared": len(used[e["id"]]) > 1,
                "used_by": used[e["id"]],
                "deps": [d["ref"] for d in it.get("depends_on", [])],
                "assistance": (it.get("assistance") or {}).get("permitted"),
                "ambiguity": it.get("ambiguity"),
            })
            if e["type"] in ("achievement", "bonus") and pts:
                matrix[e["area"]][slug] += total

    # cross-challenge price drift, same family
    fam = defaultdict(list)
    for e in b.skills.values():
        if e["type"] == "achievement" and e["skill"]:
            fam[f'{e["area"]}/{e["skill"]}'].append(e)
    drift = []
    for k, ents in sorted(fam.items()):
        chs = {c for e in ents for c in used[e["id"]]}
        if len(chs) > 1 and len({e["points"] for e in ents}) > 1:
            drift.append({"family": k, "variants": sorted(
                ({"id": e["id"], "points": e["points"], "used_by": used[e["id"]],
                  "modifiers": e["modifiers"]} for e in ents),
                key=lambda x: x["points"] or 0)})
    return {
        "rulebook_version": b.rulebook_version,
        "challenges": challenges,
        "areas": sorted(matrix),
        "matrix": {a: dict(v) for a, v in matrix.items()},
        "rows": rows,
        "drift": drift,
        "shared": sorted(({"id": i, "description": b.skills[i]["description"], "used_by": u}
                          for i, u in used.items() if len(u) > 1), key=lambda x: -len(x["used_by"])),
    }


def write(b):
    out = data(b)
    d = b.season.dist_dir
    paths.write_json(out, os.path.join(d, "viz_data.json"), indent=1)
    page = paths.template("viz.html").replace("__DATA__", json.dumps(out, indent=1).replace("</", "<\\/"))
    paths.write_text(page, os.path.join(d, "skill_coverage.html"))
    return out
