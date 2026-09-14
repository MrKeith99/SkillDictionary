#!/usr/bin/env python3
"""Emit a single JSON payload for the skills-per-challenge visualizer."""
import json, os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

D = json.load(open(os.path.join(ROOT, "dist", "dictionary.json")))
C = json.load(open(os.path.join(ROOT, "dist", "challenges.json")))
DICT = {e["id"]: e for e in D["skills"]}

rows, matrix = [], defaultdict(lambda: defaultdict(int))
challenges = {}

for slug, ch in C["challenges"].items():
    challenges[slug] = {
        "name": ch["challenge"], "section": ch["rulebook_section"],
        "minutes": ch["max_time_minutes"], "total": ch["total_score"],
    }
    for it in ch["entries"]:
        e = DICT[it["ref"]]
        pts = e.get("points")
        if pts is None and e.get("points_formula"):
            pts = int(0.10 * ch["total_score"])
        cnt = it.get("count", 1)
        total = (pts or 0) * cnt
        rows.append({
            "challenge": slug, "id": e["id"], "area": e["area"],
            "skill": e["skill"], "modifiers": e["modifiers"],
            "description": e["description"], "level": e["level"],
            "type": e["type"], "points": pts, "count": cnt, "total": total,
            "section": it.get("section"), "shared": len(e["used_by"]) > 1,
            "used_by": e["used_by"],
            "deps": [d["ref"] for d in it.get("depends_on", [])],
            "assistance": (it.get("assistance") or {}).get("permitted"),
            "ambiguity": it.get("ambiguity"),
        })
        if e["type"] in ("achievement", "bonus") and pts:
            matrix[e["area"]][slug] += total

# cross-challenge price drift, same family
fam = defaultdict(list)
for e in DICT.values():
    if e["type"] == "achievement" and e["skill"]:
        fam[f'{e["area"]}/{e["skill"]}'].append(e)
drift = []
for k, ents in sorted(fam.items()):
    chs = {c for e in ents for c in e["used_by"]}
    prices = {e["points"] for e in ents}
    if len(chs) > 1 and len(prices) > 1:
        drift.append({"family": k, "variants": sorted(
            ({"id": e["id"], "points": e["points"], "used_by": e["used_by"],
              "modifiers": e["modifiers"]} for e in ents),
            key=lambda x: x["points"] or 0)})

out = {
    "rulebook_version": D.get("rulebook_version"),
    "challenges": challenges,
    "areas": sorted(matrix),
    "matrix": {a: dict(v) for a, v in matrix.items()},
    "rows": rows,
    "drift": drift,
    "shared": sorted(
        ({"id": e["id"], "description": e["description"], "used_by": e["used_by"]}
         for e in DICT.values() if len(e["used_by"]) > 1),
        key=lambda x: -len(x["used_by"])),
}
p = os.path.join(ROOT, "dist", "viz_data.json")
json.dump(out, open(p, "w"), indent=1)
print(f"wrote {p}: {len(rows)} rows, {len(matrix)} areas, {len(drift)} drift families")

# also emit the standalone page with data inlined
tpl = os.path.join(HERE, "viz_template.html")
if os.path.exists(tpl):
    html = open(tpl).read().replace(
        "__DATA__", json.dumps(out, indent=1).replace("</", "<\\/"))
    vp = os.path.join(ROOT, "dist", "skill_coverage.html")
    open(vp, "w").write(html)
    print(f"wrote {vp}")
