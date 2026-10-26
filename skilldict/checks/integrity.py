"""References resolve, every variant is used, and no challenge carries a price."""
from . import RULE


def run(b):
    D, CH = b.variants, b.challenges
    fail = 0
    print(RULE)
    print("INTEGRITY")

    unknown = [(s, it["ref"]) for s, ch in CH.items() for it in ch["entries"] if it["ref"] not in D]
    for s, r in unknown:
        print(f"  {s}: unknown variant {r}")
    fail += len(unknown)

    # A challenge cannot price a variant: drift must be unrepresentable.
    leaked = [(s, it["ref"], k) for s, ch in CH.items() for it in ch["entries"]
              for k in ("points", "points_total") if k in it]
    for s, r, k in leaked:
        print(f"  {s}: {k} field on {r} — price belongs to the variant")
    fail += len(leaked)

    # Every reference inside an entry must name a variant.
    stale = []
    for slug, ch in CH.items():
        for it in ch["entries"]:
            refs = [("related_variant", it.get("related_variant")),
                    ("assistance.extra_penalty_ref", (it.get("assistance") or {}).get("extra_penalty_ref"))]
            stale += [(slug, f"{it['ref']}.{k}", v) for k, v in refs if v and v not in D]
    for s, p, v in stale:
        print(f"  {s}: {p} -> {v} (no such variant)")
    fail += len(stale)

    # Every variant is used somewhere: remove a variant with its last reference.
    used = {it["ref"] for ch in CH.values() for it in ch["entries"]}
    for o in sorted(set(D) - used):
        print(f"  orphan (defined, never referenced): {o}")
        fail += 1

    print(f"  -> {fail} problems")
    return fail
