"""References resolve, ids are hygienic, and no challenge carries a price."""
import re
from . import RULE

ID = re.compile(r"^[A-Z]+-[A-Z]")


def run(b):
    D, CH = b.skills, b.challenges
    fail = 0
    print(RULE)
    print("INTEGRITY")

    unknown = [(s, it["ref"]) for s, ch in CH.items() for it in ch["entries"] if it["ref"] not in D]
    for s, r in unknown:
        print(f"  {s}: unknown line {r}")
    fail += len(unknown)

    # A challenge cannot price a line: drift must be unrepresentable.
    leaked = [(s, it["ref"], k) for s, ch in CH.items() for it in ch["entries"]
              for k in ("points", "points_total") if k in it]
    for s, r, k in leaked:
        print(f"  {s}: {k} field on {r} — price belongs to the skill")
    fail += len(leaked)

    # Every *_ref and related_skill must name a line.
    stale = []

    def walk(node, path, slug):
        if isinstance(node, dict):
            for k, v in node.items():
                if (k.endswith("_ref") or k == "related_skill") and isinstance(v, str) and ID.match(v):
                    if v not in D:
                        stale.append((slug, f"{path}.{k}", v))
                else:
                    walk(v, f"{path}.{k}", slug)
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{path}[{i}]", slug)

    for slug, ch in CH.items():
        walk(ch.get("challenge_rules", {}), "challenge_rules", slug)
        for it in ch["entries"]:
            walk({k: it[k] for k in ("assistance", "related_skill") if k in it}, f"entries.{it['ref']}", slug)
    for s, p, v in stale:
        print(f"  {s}: {p} -> {v} (no such line)")
    fail += len(stale)

    # Every line is used somewhere: remove a line with its last reference.
    used = {it["ref"] for ch in CH.values() for it in ch["entries"]}
    for o in sorted(set(D) - used):
        print(f"  orphan (defined, never referenced): {o}")
        fail += 1

    print(f"  -> {fail} problems")
    return fail
