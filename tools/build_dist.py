#!/usr/bin/env python3
"""Build dist/ from the hand-maintained sources.

Reads  : dictionary/<AREA>.yaml     — definition + points (the source of truth)
         challenges/<slug>.yaml     — references by id, NO points field
         vocabulary/*.yaml          — taxonomy, difficulty factors
         vocabulary/objects/        — object catalog, fixtures, the year's object set
Writes : dist/dictionary.json, dist/challenges.json, dist/vocabulary.json

dictionary/ and challenges/ used to be regenerated from extraction/ on every CI
run, which silently discarded any edit made to them. That merge was a one-time
migration (tools/migrate_legacy.py); this script only reads and never writes
source files.
"""
import glob, json, os, re, sys
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SCHEMA_VERSION = "0.3.0"
RULEBOOK_VERSION = "2026.2"

VOCAB_FILES = ["taxonomy", "difficulty_factors"]


def id_sort_key(e):
    """Numeric ordering within a stem: MAN-PICK-02 before MAN-PICK-10."""
    m = re.match(r"^(?P<stem>.+?)-(?P<num>\d+)(?P<sfx>[A-Z]?)(?P<idx>\d*)$", e["id"])
    if not m:
        return (e["id"], 0, "", 0)
    return (m.group("stem"), int(m.group("num")), m.group("sfx"),
            int(m.group("idx")) if m.group("idx") else 0)


def load(path):
    with open(path) as fh:
        return yaml.safe_load(fh)


def main():
    skills, seen = [], set()
    for fn in sorted(glob.glob(os.path.join(ROOT, "dictionary", "*.yaml"))):
        doc = load(fn)
        area = os.path.splitext(os.path.basename(fn))[0]
        for e in doc["skills"]:
            if e["area"] != area:
                sys.exit(f"{fn}: {e['id']} has area {e['area']}, expected {area}")
            if e["id"] in seen:
                sys.exit(f"{fn}: duplicate id {e['id']}")
            seen.add(e["id"])
            skills.append(e)
    skills.sort(key=lambda e: (e["area"], id_sort_key(e)))

    # used_by is derived, not authored: recompute it so it can never go stale.
    challenges = {}
    used = {}
    for fn in sorted(glob.glob(os.path.join(ROOT, "challenges", "*.yaml"))):
        slug = os.path.splitext(os.path.basename(fn))[0]
        cd = load(fn)
        challenges[slug] = cd
        for it in cd["entries"]:
            used.setdefault(it["ref"], set()).add(slug)
    for e in skills:
        if "used_by" in e:
            e["used_by"] = sorted(used.get(e["id"], []))

    vocab = {}
    for name in VOCAB_FILES:
        p = os.path.join(ROOT, "vocabulary", f"{name}.yaml")
        if os.path.exists(p):
            vocab[name] = load(p)

    # Objects: the catalog and fixtures are reused across years; the set is the
    # one whose rulebook_version matches this build.
    od = os.path.join(ROOT, "vocabulary", "objects")
    sets = [load(f) for f in sorted(glob.glob(os.path.join(od, "sets", "*.yaml")))]
    active = [s for s in sets if str(s.get("rulebook_version")) == RULEBOOK_VERSION]
    if len(active) != 1:
        sys.exit(f"need exactly one object set for rulebook {RULEBOOK_VERSION}, found {len(active)}")
    vocab["objects"] = {
        "catalog": load(os.path.join(od, "catalog.yaml"))["objects"],
        "fixtures": load(os.path.join(od, "fixtures.yaml"))["fixtures"],
        "set": active[0],
    }

    out = os.path.join(ROOT, "dist")
    os.makedirs(out, exist_ok=True)
    meta = {"schema_version": SCHEMA_VERSION, "rulebook_version": RULEBOOK_VERSION}
    json.dump({**meta, "skills": skills},
              open(os.path.join(out, "dictionary.json"), "w"), indent=2)
    json.dump({**meta, "challenges": challenges},
              open(os.path.join(out, "challenges.json"), "w"), indent=2)
    json.dump({**meta, **vocab},
              open(os.path.join(out, "vocabulary.json"), "w"), indent=2)

    areas = sorted({e["area"] for e in skills})
    print(f"skills     : {len(skills)}  ({', '.join(areas)})")
    print(f"challenges : {len(challenges)}  ({', '.join(challenges)})")
    print(f"vocabulary : {', '.join(vocab) or 'none'}")


if __name__ == "__main__":
    main()
