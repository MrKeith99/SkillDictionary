"""Loading the data into a Build.

The tree describes one release (data/release.yaml); earlier ones are git tags.
load() returns a Build: every skill, challenge and the vocabulary, with the
derived fields (used_by, total_score, GPSR command counts) filled in and every
line rated. Everything else (checks, sheets, pages) works on a Build.
"""
import glob, math, os, re
from . import paths

SCHEMA_VERSION = "0.4.0"
VOCAB_FILES = ["taxonomy", "difficulty_factors"]
REWARD = ("achievement", "bonus")


class DataError(Exception):
    """The sources cannot be interpreted; fix the data."""


class Release:
    def __init__(self):
        path = os.path.join(paths.DATA, "release.yaml")
        m = paths.load_yaml(path)
        self.year = m["year"]
        self.status = m["status"]
        if self.status not in ("draft", "in_force"):
            raise DataError(f"{paths.rel(path)}: status must be draft or in_force")
        self.rulebook = m.get("rulebook") or {}
        self.sheets = m.get("sheets") or {}

    @property
    def in_force(self):
        return self.status == "in_force"

    def __repr__(self):
        return f"{self.year} ({self.status})"


def id_sort_key(eid):
    """Numeric ordering within a stem: MAN-PICK-02 before MAN-PICK-10."""
    m = re.match(r"^(?P<stem>.+?)-(?P<num>\d+)(?P<sfx>[A-Z]?)(?P<idx>\d*)$", eid)
    if not m:
        return (eid, 0, "", 0)
    return (m.group("stem"), int(m.group("num")), m.group("sfx"),
            int(m.group("idx")) if m.group("idx") else 0)


class Build:
    def __init__(self, release, skills, challenges, vocab, global_rules=None):
        self.release = release
        self.skills = skills              # id -> entry, as authored (no derived fields)
        self.challenges = challenges      # slug -> challenge
        self.vocab = vocab
        self.global_rules = global_rules
        self.rulebook_version = release.rulebook.get("version")
        self.ratings = {}                 # id -> rating, see ratings.py
        self.rater = None
        self.errors = []                  # data errors found while rating
        self.reports = []                 # derived numbers worth printing (GPSR commands)
        self.extra = {}                   # extra dist files: name -> JSON object

    # ── prices ──────────────────────────────────────────────────────────────
    def points(self, ref, slug):
        """A line's price in a challenge; a points_formula is evaluated there."""
        e = self.skills[ref]
        if e.get("points_formula"):
            return int(eval(e["points_formula"], {"floor": math.floor, "round": round},
                            {"total_score": self.total(slug)}))
        return e.get("points")

    def total(self, slug):
        """Maximum score: every reward line at its count, unless the challenge
        sets max_score because not all lines are reachable in one run."""
        ch = self.challenges[slug]
        if ch.get("max_score"):
            return ch["max_score"]
        return sum(self.skills[it["ref"]]["points"] * it.get("count", 1) for it in ch["entries"]
                   if self.skills[it["ref"]]["type"] in REWARD
                   and self.skills[it["ref"]].get("points") is not None)

    def used_by(self):
        used = {}
        for slug, ch in self.challenges.items():
            for it in ch["entries"]:
                used.setdefault(it["ref"], set()).add(slug)
        return {i: sorted(used.get(i, ())) for i in self.skills}

    # ── output ──────────────────────────────────────────────────────────────
    def meta(self):
        return {"schema_version": SCHEMA_VERSION, "year": self.release.year,
                "status": self.release.status, "rulebook_version": self.rulebook_version}

    def dictionary(self):
        used = self.used_by()
        return {**self.meta(), "skills": [{**e, "used_by": used[i]} for i, e in self.skills.items()]}

    def challenges_doc(self):
        return {**self.meta(), "challenges": {
            s: {**ch, "total_score": self.total(s)} for s, ch in self.challenges.items()}}

    def write_dist(self):
        out = paths.DIST
        paths.write_json(self.dictionary(), os.path.join(out, "dictionary.json"))
        paths.write_json(self.challenges_doc(), os.path.join(out, "challenges.json"))
        paths.write_json({**self.meta(), **self.vocab}, os.path.join(out, "vocabulary.json"))
        paths.write_json(self.ratings, os.path.join(out, "skill_ratings.json"), indent=1)
        if self.global_rules is not None:
            paths.write_json(self.global_rules, os.path.join(out, "global_rules.json"))
        for name, obj in self.extra.items():
            paths.write_json(obj, os.path.join(out, name))
        return out


# ── loading ──────────────────────────────────────────────────────────────────
DERIVED = ("area", "skill", "variant_number", "used_by")
ID = re.compile(r"^(?P<area>[A-Z]+)(?:-(?P<code>[A-Z]+))?-(?P<variant>\d{2,}(?:[BP]\d*)?)$")


def _skills(nodes):
    """Lines from data/skills/<AREA>.yaml. The id is <AREA>-<code>-<NN>[B|P<n>]
    with the code of its taxonomy node; area, skill and variant_number are
    derived from it, never authored."""
    skills = {}
    for fn in sorted(glob.glob(os.path.join(paths.SKILLS, "*.yaml"))):
        area = os.path.splitext(os.path.basename(fn))[0]
        doc = paths.load_yaml(fn)
        if doc.get("area") != area:
            raise DataError(f"{paths.rel(fn)}: area {doc.get('area')}, expected {area}")
        for e in doc["skills"]:
            where = f"{paths.rel(fn)}: {e['id']}"
            for k in DERIVED:
                if k in e:
                    raise DataError(f"{where}: {k} is derived from the id, do not author it")
            if e["id"] in skills:
                raise DataError(f"{paths.rel(fn)}: duplicate id {e['id']}")
            m = ID.match(e["id"])
            node = nodes.get(e.get("taxonomy"))
            if not m or m["area"] != area:
                raise DataError(f"{where}: id must be {area}-<code>-<NN>[B|P<n>]")
            if node is None:
                raise DataError(f"{where}: unknown taxonomy node {e.get('taxonomy')}")
            if (m["code"] or "") != node.get("code", None):
                raise DataError(f"{where}: id code must be {node.get('code')!r}, the code of {e['taxonomy']}")
            skills[e["id"]] = {"id": e["id"], "area": area, "skill": e["taxonomy"].split(".")[-1],
                               "variant_number": m["variant"], **{k: v for k, v in e.items() if k != "id"}}
    return dict(sorted(skills.items(), key=lambda kv: (kv[1]["area"], id_sort_key(kv[0]))))


def _challenges():
    out = {}
    for fn in sorted(glob.glob(os.path.join(paths.CHALLENGES, "*.yaml"))):
        ch = paths.load_yaml(fn)
        for k in ("total_score", "max_score", "used_by"):
            if k in ch:
                raise DataError(f"{paths.rel(fn)}: {k} is derived, do not author it")
        out[os.path.splitext(os.path.basename(fn))[0]] = ch
    return out


def _vocab():
    vocab = {n: paths.load_yaml(os.path.join(paths.VOCAB, f"{n}.yaml")) for n in VOCAB_FILES}
    od = os.path.join(paths.VOCAB, "objects")
    vocab["objects"] = {
        "catalog": paths.load_yaml(os.path.join(od, "catalog.yaml"))["objects"],
        "furniture": paths.load_yaml(os.path.join(od, "furniture.yaml")),
        "set": paths.load_yaml(os.path.join(od, "set.yaml")),
    }
    return vocab


def load():
    """The Build of the tree, rated. Data errors found while rating are in
    build.errors; structural errors (duplicate ids, ...) raise DataError."""
    from . import ratings, commands
    gr = os.path.join(paths.VOCAB, "global_rules.yaml")
    vocab = _vocab()
    b = Build(Release(), _skills(vocab["taxonomy"]["nodes"]), _challenges(), vocab,
              paths.load_yaml(gr) if os.path.exists(gr) else None)
    commands.apply(b)
    ratings.rate(b)
    return b
