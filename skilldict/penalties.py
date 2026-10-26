"""Penalties, defined once for the whole competition.

No challenge lists its own penalties. What can go wrong is `failure_modes` in
data/skills.yaml, and who can suffer it is the skill:

  - a skill lists the failures all its variants share (`failures:`); a
    variant in data/variants/ may add its own (`failures: [drop]`).
    An achievement gets its skill's failures; a bonus only its own;
  - assistance applies to every variant whose challenge permits assistance
    (`assistance.permitted`), unless the challenge makes it free
    (`extra_penalty: 0`);
  - conduct failures (scope: run) are fixed-price variants added to every
    challenge.

expand() writes each failure as the variant <variant>-<code>
(MAN-PICK-01-DROP), priced share x the variant and rounded like every price,
and puts it on the sheet right after the variant it belongs to, as often as
that variant counts.
"""
import math
from .model import DataError


def price(share, parent):
    """share x parent, rounded like every price."""
    return rounded(-share * parent)


def rounded(x):
    """To the nearest 10 (5 below 50), halves away from zero."""
    step = 10 if abs(x) >= 50 else 5
    return int(math.copysign(math.floor(abs(x) / step + 0.5) * step, x))


def failures(b, v, assisted):
    """The failure modes of one variant as a challenge uses it, in sheet order."""
    modes = b.vocab["failure_modes"]
    skill = b.vocab["skills"][v["skill"]]
    own = list(skill.get("failures", [])) if v["type"] == "achievement" else []
    own += [f for f in v.get("failures", []) if f not in own]
    if assisted:
        own.append("assistance")
    for f in own:
        if modes.get(f, {}).get("scope") != "variant":
            raise DataError(f"{v['id']}: failure {f!r} is not a variant failure in failure_modes")
    return own


def expand(b):
    modes = b.vocab["failure_modes"]
    made = {}
    for slug, ch in b.challenges.items():
        out = []
        for it in ch["entries"]:
            out.append(it)
            v = b.variants[it["ref"]]
            if v["type"] not in ("achievement", "bonus") or not (v.get("points") or 0) > 0:
                continue
            a = it.get("assistance") or {}
            assisted = a.get("permitted") and a.get("extra_penalty") != 0
            for f in failures(b, v, assisted):
                m = modes[f]
                pid = f"{v['id']}-{m['code']}"
                if pid not in made:
                    if pid in b.variants:
                        raise DataError(f"{pid} is derived; do not author it in data/variants/")
                    made[pid] = b.variants[pid] = {
                        "id": pid, "area": v["area"],
                        "variant_number": f"{v['variant_number']}-{m['code']}",
                        "skill": v["skill"], "description": m["label"],
                        "failure_mode": f, "points": price(m["share"], v["points"]),
                        "type": "penalty_behavior", "penalty_of": v["id"], "share": m["share"]}
                e = {"ref": pid, "count": it.get("count", 1), "related_variant": v["id"]}
                if it.get("section"):
                    e["section"] = it["section"]
                out.append(e)
                if f == "assistance":
                    a["extra_penalty_ref"] = pid
        for f, m in modes.items():
            if m.get("scope") == "run" and m.get("variant"):
                if m["variant"] not in b.variants:
                    raise DataError(f"failure_modes.{f}: no variant {m['variant']}")
                out.append({"ref": m["variant"], "count": m.get("count", 1), "section": "Penalties"})
        ch["entries"] = out
