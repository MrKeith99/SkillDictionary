"""Challenges whose task is drawn at test time (GPSR): score by the steps.

A challenge with `command_steps` maps every generator template and follow-up
to the skill variants it exercises. From that the build

  - fills in the count of every variant without one: the most any
    COMMANDS_PER_TEST commands can use it,
  - values every command the generator can produce, at its weights
    (dist/<slug>_commands.json),
  - sets the sheet maximum: the fixed variants plus the best commands.
"""
from collections import Counter
from .model import DataError

COMMANDS_PER_TEST = 3          # GPSR: the robot gets three commands


def expand(cs, name, kind):
    """All step sequences a template or follow-up can produce."""
    spec = cs[kind][name]
    if not spec.get("then"):
        return [list(spec["steps"])]
    return [list(spec["steps"]) + tail
            for f in cs["slots"][spec["then"]] for tail in expand(cs, f, "followups")]


def apply(b):
    for slug, ch in b.challenges.items():
        cs = ch.get("command_steps")
        if not cs:
            continue
        chains = {t: expand(cs, t, "templates") for t in cs["templates"]}
        for seqs in chains.values():
            for seq in seqs:
                for step in seq:
                    if step not in b.variants:
                        raise DataError(f"{slug}: command step {step} is not a variant")
        most = Counter()
        for seqs in chains.values():
            for seq in seqs:
                for step, n in Counter(seq).items():
                    most[step] = max(most[step], n)
        for it in ch["entries"]:
            it.setdefault("count", COMMANDS_PER_TEST * most[it["ref"]] or 1)
        _value(b, slug, ch, cs, chains)


def _value(b, slug, ch, cs, chains):
    prob = Counter()
    for w in cs["weights"].values():
        tot = sum(w.values())
        for t, x in w.items():
            prob[t] += x / tot / len(cs["weights"])      # one list is drawn, uniformly
    price = lambda i: b.variants[i].get("points") or 0
    value = {}
    for t, seqs in chains.items():
        vals = [sum(price(s) for s in seq) for seq in seqs]
        # follow-ups are drawn uniformly, so every expansion is equally likely
        value[t] = {"min": min(vals), "mean": sum(vals) / len(vals), "max": max(vals), "p": prob[t]}
    mean_cmd = sum(v["mean"] * v["p"] for v in value.values())
    bonus = price(cs["completion_bonus"]) if cs.get("completion_bonus") else 0
    best = max(v["max"] for v in value.values()) + bonus
    steps = {s for seqs in chains.values() for seq in seqs for s in seq} | {cs.get("completion_bonus")}
    fixed = sum(price(it["ref"]) * it["count"] for it in ch["entries"]
                if it["ref"] not in steps and price(it["ref"]) > 0
                and b.variants[it["ref"]]["type"] != "administrative")
    ch["max_score"] = fixed + COMMANDS_PER_TEST * best
    rep = [f"COMMANDS — {ch['challenge']}",
           f"  average command (generator weights): {mean_cmd:.0f} in skills + {bonus} "
           f"completion bonus = {mean_cmd + bonus:.0f}",
           "  per command type (skills only, before the bonus):"]
    for t, v in sorted(value.items(), key=lambda x: -x[1]["mean"]):
        rng = f"{v['min']}" if v["min"] == v["max"] else f"{v['min']}-{v['max']}"
        rep.append(f"    {t:28s} {v['p']:5.1%}  {rng:>9s}  mean {v['mean']:.0f}")
    rep.append(f"  sheet maximum: {ch['max_score']} (fixed variants + {COMMANDS_PER_TEST} x best command)")
    b.reports += rep
    b.extra[f"{slug}_commands.json"] = {
        "mean_command": round(mean_cmd, 1), "completion_bonus": bonus, "max_score": ch["max_score"],
        "templates": {t: {**v, "steps": chains[t]} for t, v in value.items()}}
