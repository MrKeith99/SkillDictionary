#!/usr/bin/env python3
"""Merge the five per-challenge files into a canonical cross-challenge dictionary.

Reads  : dictionary/*_challenge.json   (legacy per-challenge extraction)
Writes : SkillDictionary/dictionary/<AREA>.yaml   — definition + points, one file per area
         SkillDictionary/challenges/<slug>.yaml   — references by id, NO points field

Merge rule
----------
Two legacy entries become ONE canonical entry iff they agree on the full facet
tuple (area, skill, type, sorted(modifiers)) AND on points. Entries that share a
facet tuple but disagree on points are NOT merged -- that is cross-challenge
price drift, and the dictionary must keep it visible rather than silently pick a
winner. They are emitted as separate variant_numbers and reported by CHECK 5.

Canonical id format:  <AREA>-<SKILL>-<NN>[P<n>|B<n>]
  NN is a permanent variant_number, assigned in first-seen order and never reused.
"""
import json, glob, os, re, sys
from collections import OrderedDict, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                      # SkillDictionary/
LEGACY = os.path.join(ROOT, "extraction")

# Administrative lines whose value is derived from the challenge total rather than
# fixed by the dictionary. Keyed by legacy id -> formula expression over `total_score`.
COMPUTED = {
    "SPECIAL-OUTSTANDING": "floor(0.10 * total_score)",
}

CHALLENGE_SLUG = {
    "Human Robot Interaction Challenge": "hri",
    "Pick and Place Challenge": "pick_and_place",
    "General Purpose Service Robot Challenge": "gpsr",
    "Doing Laundry Challenge": "doing_laundry",
    "Restaurant Challenge": "restaurant",
}

# Fields that belong to the DICTIONARY (the specification: what the skill is, what it costs).
DICT_FIELDS = ["id", "area", "skill", "modifiers", "description", "level",
               "points", "type", "penalty_type", "basis", "process_spec"]
# Fields that belong to a CHALLENGE (how this challenge uses the skill). Never "points".
CHAL_FIELDS = ["count", "section", "depends_on", "assistance", "related_skill",
               "note", "ambiguity"]


def facet_key(e):
    """Identity of a skill as a specification: the four facets. Price excluded."""
    return (e["area"], e["skill"], e["type"], tuple(sorted(e["modifiers"])))


def load_legacy():
    out = []
    for fn in sorted(glob.glob(os.path.join(LEGACY, "*_challenge.json"))):
        out.append(json.load(open(fn)))
    if not out:
        sys.exit(f"no *_challenge.json found in {LEGACY}")
    return out


def assign_ids(docs):
    """Build facet -> canonical entry map, allocating permanent variant numbers.

    Returns (canon, legacy_to_canon) where canon maps canonical_id -> dict entry
    and legacy_to_canon maps (challenge, legacy_id) -> canonical_id.
    """
    groups = OrderedDict()
    for d in docs:
        for e in d["skills"]:
            groups.setdefault(facet_key(e), []).append((d["challenge"], e))

    # Within a facet group, split by points: same facets + same price = one entry.
    #
    # variant_number is PERMANENT (CLAUDE.md): it must never be reused or silently
    # reassigned, because the TC already cites ids like MAN-APPLIANCE-02 in open
    # questions. So we keep the legacy number whenever the legacy id already encodes
    # one for this stem, and only allocate fresh numbers above the high-water mark
    # for entries that genuinely have none.
    counters = defaultdict(int)
    canon, legacy_to_canon = OrderedDict(), {}
    taken = defaultdict(set)

    def legacy_variant(stem, legacy_id):
        """Pull the variant number out of a legacy id if it belongs to this stem."""
        m = re.match(r"^(?P<stem>[A-Z]+(?:-[A-Z]+)?)-(?P<num>\d+)(?P<sfx>[A-Z]?\d*)$",
                     legacy_id)
        if not m:
            return None
        if normalise_stem(m.group("stem")) != stem:
            return None
        # Keep the suffix: 01B1 and 01B2 are different skills that merely share a
        # parent. Returning just the number would merge them and destroy prices.
        return m.group("num") + m.group("sfx")

    # Pass 1 -- claim legacy variant numbers so pass 2 cannot collide with them.
    for fk, members in groups.items():
        area, skill, etype, mods = fk
        for ch, e in members:
            stem = skill_stem(area, skill, e["id"])
            v = legacy_variant(stem, e["id"])
            if v is not None:
                taken[stem].add(v)

    for fk, members in groups.items():
        area, skill, etype, mods = fk
        by_price = OrderedDict()
        for ch, e in members:
            # Some administrative lines are a FORMULA over the challenge total, not a
            # fixed price (§3.8.3 outstanding performance = 10% of the test maximum).
            # Grouping those by their evaluated value would mint five variants of one
            # rule and re-introduce exactly the drift this dictionary exists to remove.
            key = COMPUTED.get(e["id"], e["points"])
            by_price.setdefault(key, []).append((ch, e))

        for price, priced in by_price.items():
            stem = skill_stem(area, skill, priced[0][1]["id"])
            # Prefer a legacy number that all merged members agree on.
            cands = {legacy_variant(stem, e["id"]) for _, e in priced}
            cands.discard(None)
            if len(cands) == 1:
                n = cands.pop()
            else:
                # No agreed legacy number (new entry, or a merge of two differently
                # numbered legacy ids): allocate above the numeric high-water mark.
                k = counters[stem] + 1
                while f"{k:02d}" in taken[stem] or str(k) in taken[stem]:
                    k += 1
                n = f"{k:02d}"
                taken[stem].add(n)
                counters[stem] = k
            # Preserve the legacy discriminator verbatim; append a type marker only
            # when the legacy id did not already carry one.
            suffix = {"penalty_behavior": "P", "bonus": "B"}.get(etype, "")
            body = n if isinstance(n, str) else f"{n:02d}"
            cid = f"{stem}-{body}" if (suffix and suffix in body) else f"{stem}-{body}{suffix}"

            ref = priced[0][1]
            formula = COMPUTED.get(ref["id"])
            ent = OrderedDict()
            ent["id"] = cid
            ent["area"] = area
            ent["skill"] = skill
            ent["variant_number"] = body
            ent["modifiers"] = sorted(mods)
            ent["description"] = ref["description"]
            ent["level"] = ref["level"]
            if formula:
                ent["points"] = None
                ent["points_formula"] = formula
            else:
                ent["points"] = price
            ent["type"] = etype
            for f in ("penalty_type", "basis"):
                if ref.get(f) is not None:
                    ent[f] = ref[f]
            ent["used_by"] = sorted({CHALLENGE_SLUG[ch] for ch, _ in priced})
            ent["legacy_ids"] = sorted({e["id"] for _, e in priced})
            canon[cid] = ent
            for ch, e in priced:
                legacy_to_canon[(ch, e["id"])] = cid
    return canon, legacy_to_canon


# Entries with skill: null are not robot capabilities (assistance lines, admin lines).
# They keep a mnemonic stem taken from their legacy id family so referees and
# scoresheet diffs stay readable.
NULL_SKILL_STEM = {
    "GEN-HUMANASSIST": "GEN-HUMANASSIST",
    "GEN-BREAKFAST":   "GEN-BREAKFAST",
    "SPECIAL":         "SPECIAL",
}


def id_sort_key(e):
    """Order entries within an area file by id, numerically.

    Plain string sort puts MAN-PICK-10 before MAN-PICK-02, and interleaves the
    P/B suffixed variants oddly, so split the discriminator into its parts:
    (skill, variant number, suffix letter, suffix index).
    """
    m = re.match(r"^(?P<stem>.+?)-(?P<num>\d+)(?P<sfx>[A-Z]?)(?P<idx>\d*)$", e["id"])
    if not m:
        return (e["id"], 0, "", 0)
    return (m.group("stem"),
            int(m.group("num")),
            m.group("sfx"),
            int(m.group("idx")) if m.group("idx") else 0)


def normalise_stem(stem):
    return stem.upper()


def skill_stem(area, skill, legacy_id=None):
    if not skill:
        if legacy_id:
            for pref, stem in NULL_SKILL_STEM.items():
                if legacy_id.startswith(pref):
                    return stem
        return area
    s = re.sub(r"(?<!^)(?=[A-Z])", "", skill).upper()
    return f"{area}-{s}"


def remap_dep(dep, ch, legacy_to_canon, dangling):
    d = OrderedDict()
    tgt = legacy_to_canon.get((ch, dep["ref"]))
    if tgt is None:
        tgt = dep["ref"]
        dangling.append((ch, dep["ref"]))
        d["unresolved"] = True
    d["ref"] = tgt
    for k in ("nature", "blocking", "satisfiable_by_assistance", "note"):
        if k in dep:
            d[k] = dep[k]
    return d


def remap_assist(a, ch, legacy_to_canon):
    out = OrderedDict()
    for k, v in a.items():
        if k == "extra_penalty_ref" and v:
            out[k] = legacy_to_canon.get((ch, v), v)
        else:
            out[k] = v
    return out


def remap_rules(node, ch, legacy_to_canon):
    """Recursively rewrite any *_ref value that names a legacy skill id."""
    if isinstance(node, dict):
        out = OrderedDict()
        for k, v in node.items():
            if k.endswith("_ref") and isinstance(v, str):
                out[k] = legacy_to_canon.get((ch, v), v)
            else:
                out[k] = remap_rules(v, ch, legacy_to_canon)
        return out
    if isinstance(node, list):
        return [remap_rules(x, ch, legacy_to_canon) for x in node]
    return node


def build(docs, canon, legacy_to_canon):
    dangling = []
    challenges = OrderedDict()

    for d in docs:
        ch = d["challenge"]
        slug = CHALLENGE_SLUG[ch]
        cd = OrderedDict()
        cd["challenge"] = ch
        cd["rulebook_section"] = d["rulebook_section"]
        cd["max_time_minutes"] = d["max_time_minutes"]
        cd["total_score"] = d["total_score"]
        if "method_note" in d:
            cd["method_note"] = d["method_note"]
        cd["dictionary_ref"] = "../dictionary/"
        cd["global_rules_ref"] = "../vocabulary/global_rules.yaml"
        if "challenge_rules" in d:
            # challenge_rules can also cite skills (e.g. alternative_hri.penalty_ref).
            # Remap those too, or the rename leaves a dangling pointer.
            cd["challenge_rules"] = remap_rules(d["challenge_rules"], ch, legacy_to_canon)

        entries = []
        for e in d["skills"]:
            cid = legacy_to_canon[(ch, e["id"])]
            it = OrderedDict()
            it["ref"] = cid
            for f in CHAL_FIELDS:
                if f not in e or e[f] is None:
                    continue
                if f == "depends_on":
                    it[f] = [remap_dep(x, ch, legacy_to_canon, dangling) for x in e[f]]
                elif f == "assistance":
                    it[f] = remap_assist(e[f], ch, legacy_to_canon)
                elif f == "related_skill":
                    it[f] = legacy_to_canon.get((ch, e[f]), e[f])
                else:
                    it[f] = e[f]
            entries.append(it)
        cd["entries"] = entries
        challenges[slug] = cd

    return challenges, dangling


def emit_yaml(obj, ind=0):
    """Minimal deterministic YAML writer (no PyYAML dependency)."""
    sp = "  " * ind
    out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, dict):
                if not v:
                    out.append(f"{sp}{k}: {{}}")
                else:
                    out.append(f"{sp}{k}:")
                    out.append(emit_yaml(v, ind + 1))
            elif isinstance(v, list):
                if not v:
                    out.append(f"{sp}{k}: []")
                else:
                    out.append(f"{sp}{k}:")
                    for item in v:
                        if isinstance(item, (dict, list)):
                            body = emit_yaml(item, ind + 1).split("\n")
                            out.append(f"{sp}- " + body[0].strip())
                            out.extend(body[1:])
                        else:
                            out.append(f"{sp}- {scalar(item)}")
            else:
                out.append(f"{sp}{k}: {scalar(v)}")
    elif isinstance(obj, list):
        for item in obj:
            out.append(f"{sp}- {scalar(item)}")
    return "\n".join(out)


def scalar(v):
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v)
    if s == "" or s[0] in "-?:,[]{}#&*!|>'\"%@`" or ":" in s or "#" in s or "\n" in s \
       or s.strip() != s or s.lower() in ("true", "false", "null", "yes", "no", "on", "off") \
       or re.fullmatch(r"-?\d+(\.\d+)?", s):
        return "'" + s.replace("'", "''") + "'"
    return s


def main():
    docs = load_legacy()
    canon, legacy_to_canon = assign_ids(docs)
    challenges, dangling = build(docs, canon, legacy_to_canon)

    os.makedirs(os.path.join(ROOT, "dictionary"), exist_ok=True)
    os.makedirs(os.path.join(ROOT, "challenges"), exist_ok=True)

    # --- dictionary: one file per area ---
    by_area = defaultdict(list)
    for e in canon.values():
        by_area[e["area"]].append(e)

    for area, ents in sorted(by_area.items()):
        doc = OrderedDict()
        doc["area"] = area
        doc["schema_version"] = "0.2.0"
        doc["rulebook_version"] = "2026.2"
        doc["note"] = ("Canonical cross-challenge definitions. Each entry is defined and "
                       "priced exactly once here; challenges reference it by id.")
        doc["skills"] = sorted(ents, key=id_sort_key)
        p = os.path.join(ROOT, "dictionary", f"{area}.yaml")
        open(p, "w").write(emit_yaml(doc) + "\n")

    # --- challenges: reference by id, no points ---
    for slug, cd in challenges.items():
        p = os.path.join(ROOT, "challenges", f"{slug}.yaml")
        open(p, "w").write(emit_yaml(cd) + "\n")

    # --- combined machine-readable dist ---
    os.makedirs(os.path.join(ROOT, "dist"), exist_ok=True)
    json.dump({"schema_version": "0.2.0", "rulebook_version": "2026.2",
               "skills": sorted(canon.values(), key=lambda e: (e["area"], id_sort_key(e)))},
              open(os.path.join(ROOT, "dist", "dictionary.json"), "w"), indent=2)
    json.dump({"schema_version": "0.2.0", "rulebook_version": "2026.2",
               "challenges": challenges},
              open(os.path.join(ROOT, "dist", "challenges.json"), "w"), indent=2)

    # --- migration map: legacy id -> canonical id, per challenge ---
    # 39 of 98 ids change spelling. Anything outside this repo that cites a legacy
    # id (TC open questions, the Google Sheets tracker, old scoresheets) needs this
    # table to follow the rename, so it ships as a committed artifact.
    mig = OrderedDict()
    for (ch, old), new in sorted(legacy_to_canon.items()):
        mig.setdefault(CHALLENGE_SLUG[ch], OrderedDict())[old] = new
    json.dump(mig, open(os.path.join(ROOT, "dist", "id_migration.json"), "w"), indent=2)

    flat = OrderedDict()
    for slug, m in mig.items():
        for old, new in m.items():
            flat.setdefault(old, set()).add(new)
    with open(os.path.join(ROOT, "dist", "id_migration.csv"), "w") as fh:
        fh.write("legacy_id,canonical_id,changed\n")
        for old in sorted(flat):
            for new in sorted(flat[old]):
                fh.write(f"{old},{new},{'no' if old == new else 'yes'}\n")

    merged = [e for e in canon.values() if len(e["legacy_ids"]) > 1]
    print(f"legacy entries : {sum(len(d['skills']) for d in docs)}")
    print(f"canonical ids  : {len(canon)}")
    print(f"areas          : {', '.join(sorted(by_area))}")
    print(f"merged (dedup) : {len(merged)}")
    for e in merged:
        print(f"   {e['id']:20s} <- {' + '.join(e['legacy_ids'])}  ({', '.join(e['used_by'])})")
    renamed = sum(1 for o, ns in flat.items() for n in ns if o != n)
    print(f"id renames     : {renamed} (see dist/id_migration.csv)")
    if dangling:
        print(f"dangling refs  : {len(dangling)}")
        for ch, r in dangling:
            print(f"   [{ch[:16]:16s}] {r}")


if __name__ == "__main__":
    main()
