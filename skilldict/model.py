"""Loading the data into a Build.

The tree describes one release (data/release.yaml); earlier ones are git tags.
load() returns a Build: the skills (what each capability is), their variants
(the priced instances the sheets score), the challenges and the vocabulary,
with the derived fields (used_by, total_score, GPSR command counts, penalty
variants) filled in and every variant rated. Everything else (checks, sheets, pages) works on a Build.
"""
import glob, math, os, re
from . import paths

SCHEMA_VERSION = "0.4.0"
VOCAB_FILES = ["difficulty_factors"]
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
    def __init__(self, release, variants, challenges, vocab):
        self.release = release
        self.variants = variants          # id -> variant, as authored plus derived fields
        self.challenges = challenges      # slug -> challenge
        self.vocab = vocab
        self.rulebook_version = release.rulebook.get("version")
        self.ratings = {}                 # id -> difficulty, see difficulty.py
        self.rater = None
        self.errors = []                  # data errors found while rating
        self.reports = []                 # derived numbers worth printing (GPSR commands)
        self.extra = {}                   # extra dist files: name -> JSON object

    # ── prices ──────────────────────────────────────────────────────────────
    def points(self, ref, slug):
        """A variant's price in a challenge; a points_formula is evaluated there."""
        e = self.variants[ref]
        if e.get("points_formula"):
            return int(eval(e["points_formula"], {"floor": math.floor, "round": round},
                            {"total_score": self.total(slug)}))
        return e.get("points")

    def total(self, slug):
        """Maximum score: every reward variant at its count, unless the challenge
        sets max_score because not all variants are reachable in one run."""
        ch = self.challenges[slug]
        if ch.get("max_score"):
            return ch["max_score"]
        return sum(self.variants[it["ref"]]["points"] * it.get("count", 1) for it in ch["entries"]
                   if self.variants[it["ref"]]["type"] in REWARD
                   and self.variants[it["ref"]].get("points") is not None)

    def used_by(self):
        used = {}
        for slug, ch in self.challenges.items():
            for it in ch["entries"]:
                used.setdefault(it["ref"], set()).add(slug)
        return {i: sorted(used.get(i, ())) for i in self.variants}

    # ── output ──────────────────────────────────────────────────────────────
    def meta(self):
        return {"schema_version": SCHEMA_VERSION, "year": self.release.year,
                "status": self.release.status, "rulebook_version": self.rulebook_version}

    def variants_doc(self):
        used = self.used_by()
        return {**self.meta(), "variants": [{**e, "used_by": used[i]} for i, e in self.variants.items()]}

    def skills_doc(self):
        return {**self.meta(), "skills": self.vocab["skills"], "failure_modes": self.vocab["failure_modes"]}

    def challenges_doc(self):
        return {**self.meta(), "challenges": {
            s: {**ch, "total_score": self.total(s)} for s, ch in self.challenges.items()}}

    def write_dist(self):
        out = paths.DIST
        paths.write_json(self.skills_doc(), os.path.join(out, "skills.json"))
        paths.write_json(self.variants_doc(), os.path.join(out, "variants.json"))
        paths.write_json(self.challenges_doc(), os.path.join(out, "challenges.json"))
        paths.write_json({**self.meta(), **{k: v for k, v in self.vocab.items()
                                            if k not in ("skills", "failure_modes")}},
                         os.path.join(out, "vocabulary.json"))
        paths.write_json(self.ratings, os.path.join(out, "variant_difficulty.json"), indent=1)
        for name, obj in self.extra.items():
            paths.write_json(obj, os.path.join(out, name))
        return out


# ── loading ──────────────────────────────────────────────────────────────────
DERIVED = ("area", "variant_number", "used_by", "penalty_of", "share")
ID = re.compile(r"^(?P<area>[A-Z]+)(?:-(?P<code>[A-Z]+))?-(?P<variant>\d{2,}(?:[BP]\d*)?)$")


def _variants(skills):
    """Variants from data/variants/<AREA>.yaml. The id is <AREA>-<code>-<NN>[B|P<n>]
    with the code of its skill; area and variant_number are derived from it,
    never authored. Penalty variants (<variant>-<FAILURE>) are written by
    penalties.py."""
    variants = {}
    for fn in sorted(glob.glob(os.path.join(paths.VARIANTS, "*.yaml"))):
        area = os.path.splitext(os.path.basename(fn))[0]
        doc = paths.load_yaml(fn)
        if doc.get("area") != area:
            raise DataError(f"{paths.rel(fn)}: area {doc.get('area')}, expected {area}")
        for e in doc["variants"]:
            where = f"{paths.rel(fn)}: {e['id']}"
            for k in DERIVED:
                if k in e:
                    raise DataError(f"{where}: {k} is derived from the id, do not author it")
            if e["id"] in variants:
                raise DataError(f"{paths.rel(fn)}: duplicate id {e['id']}")
            m = ID.match(e["id"])
            skill = skills.get(e.get("skill"))
            if not m or m["area"] != area:
                raise DataError(f"{where}: id must be {area}-<code>-<NN>[B|P<n>]")
            if skill is None:
                raise DataError(f"{where}: unknown skill {e.get('skill')}")
            if (m["code"] or "") != skill["code"]:
                raise DataError(f"{where}: id code must be {skill['code']!r}, the code of {e['skill']}")
            variants[e["id"]] = {"id": e["id"], "area": area, "variant_number": m["variant"],
                                 **{k: v for k, v in e.items() if k != "id"}}
    return dict(sorted(variants.items(), key=lambda kv: (kv[1]["area"], id_sort_key(kv[0]))))


def _challenges():
    out = {}
    for fn in sorted(glob.glob(os.path.join(paths.CHALLENGES, "*.yaml"))):
        ch = paths.load_yaml(fn)
        for k in ("total_score", "max_score", "used_by"):
            if k in ch:
                raise DataError(f"{paths.rel(fn)}: {k} is derived, do not author it")
        out[os.path.splitext(os.path.basename(fn))[0]] = ch
    return out


def skill_words(sid):
    return re.findall(r"[A-Z][a-z]*", sid.split(".")[-1])


def skill_code(sid):
    """MAN.OperateFixture -> FIXTURE: the code in the ids of the skill's variants."""
    return "" if sid.startswith("SPECIAL.") else skill_words(sid)[-1].upper()


def skill_name(sid):
    """MAN.OpenContainer -> "Open container"."""
    return " ".join(skill_words(sid)).capitalize()


def _vocab():
    vocab = {n: paths.load_yaml(os.path.join(paths.VOCAB, f"{n}.yaml")) for n in VOCAB_FILES}
    doc = paths.load_yaml(paths.SKILLS)
    vocab["skills"], vocab["failure_modes"] = doc["skills"], doc["failure_modes"]
    for nid, n in vocab["skills"].items():
        for k in ("name", "code"):
            if k in n:
                raise DataError(f"skill {nid}: {k} is derived from the skill id, do not author it")
        n["name"], n["code"] = skill_name(nid), skill_code(nid)
    vocab["objects"] = {
        "catalog": paths.load_yaml(os.path.join(paths.VOCAB, "objects.yaml"))["objects"],
        "furniture": paths.load_yaml(os.path.join(paths.VOCAB, "furniture.yaml")),
        "set": paths.load_yaml(os.path.join(paths.VOCAB, "object_set.yaml")),
    }
    return vocab


def load():
    """The Build of the tree, rated. Data errors found while rating are in
    build.errors; structural errors (duplicate ids, ...) raise DataError."""
    from . import difficulty, gpsr, penalties
    vocab = _vocab()
    b = Build(Release(), _variants(vocab["skills"]), _challenges(), vocab)
    gpsr.apply(b)
    penalties.expand(b)
    difficulty.rate(b)
    return b
