"""Seasons and builds.

A season is data/seasons/<year>/ with a season.yaml. An in-force season holds
its challenges and object set; a proposal season names a `base` season and
lists what it changes in changes/*.yaml.

load(year) returns a Build: every skill, challenge and the vocabulary of that
season, with the derived fields (used_by, total_score) filled in and every
line rated. Everything else (checks, pricing, sheets) works on a Build.
"""
import copy, glob, math, os, re
from . import paths

SCHEMA_VERSION = "0.4.0"
VOCAB_FILES = ["taxonomy", "difficulty_factors"]
REWARD = ("achievement", "bonus")


class DataError(Exception):
    """The sources cannot be interpreted; fix the data."""


class Season:
    def __init__(self, year):
        self.dir = os.path.join(paths.SEASONS, str(year))
        path = os.path.join(self.dir, "season.yaml")
        if not os.path.exists(path):
            raise DataError(f"no season {year}: {paths.rel(path)} missing")
        m = paths.load_yaml(path)
        self.year = m["year"]
        if str(self.year) != str(year):
            raise DataError(f"{paths.rel(path)}: year {self.year} in folder {year}")
        self.status = m["status"]
        if self.status not in ("in_force", "proposal"):
            raise DataError(f"{paths.rel(path)}: status must be in_force or proposal")
        self.base = m.get("base")
        self.rulebook = m.get("rulebook") or {}
        self.sheets = m.get("sheets") or {}

    @property
    def in_force(self):
        return self.status == "in_force"

    def file(self, *parts):
        return os.path.join(self.dir, *parts)

    def pricing(self):
        p = self.file("pricing.yaml")
        return paths.load_yaml(p) if os.path.exists(p) else None

    def changes(self):
        return [(os.path.basename(f), paths.load_yaml(f))
                for f in sorted(glob.glob(self.file("changes", "*.yaml")))]

    @property
    def dist_dir(self):
        return paths.DIST if self.in_force else os.path.join(paths.DIST, str(self.year))

    @property
    def build_dir(self):
        return os.path.join(paths.BUILD, str(self.year))

    def __repr__(self):
        return f"season {self.year} ({self.status})"


def seasons():
    return sorted(int(os.path.basename(os.path.dirname(f)))
                  for f in glob.glob(os.path.join(paths.SEASONS, "*", "season.yaml")))


def current():
    """The season in force: the one dist/ and the rulebook check describe."""
    live = [y for y in seasons() if Season(y).in_force]
    if len(live) != 1:
        raise DataError(f"need exactly one in_force season, found {live}")
    return live[0]


def id_sort_key(eid):
    """Numeric ordering within a stem: MAN-PICK-02 before MAN-PICK-10."""
    m = re.match(r"^(?P<stem>.+?)-(?P<num>\d+)(?P<sfx>[A-Z]?)(?P<idx>\d*)$", eid)
    if not m:
        return (eid, 0, "", 0)
    return (m.group("stem"), int(m.group("num")), m.group("sfx"),
            int(m.group("idx")) if m.group("idx") else 0)


def sort_skills(skills):
    return dict(sorted(skills.items(), key=lambda kv: (kv[1]["area"], id_sort_key(kv[0]))))


class Build:
    def __init__(self, season, skills, challenges, vocab, global_rules=None):
        self.season = season
        self.skills = skills              # id -> entry, as authored (no derived fields)
        self.challenges = challenges      # slug -> challenge
        self.vocab = vocab
        self.global_rules = global_rules
        self.rulebook_version = season.rulebook.get("version")
        self.ratings = {}                 # id -> rating, see ratings.py
        self.rater = None
        self.errors = []                  # data errors found while rating
        self.base = None                  # the base season's Build, for a proposal
        self.reports = []                 # what a proposal changed, for the console
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
        return {"schema_version": SCHEMA_VERSION, "rulebook_version": self.rulebook_version,
                "season": self.season.year, "status": self.season.status}

    def dictionary(self):
        used = self.used_by()
        return {**self.meta(), "skills": [{**e, "used_by": used[i]} for i, e in self.skills.items()]}

    def challenges_doc(self):
        return {**self.meta(), "challenges": {
            s: {**ch, "total_score": self.total(s)} for s, ch in self.challenges.items()}}

    def write_dist(self):
        out = self.season.dist_dir
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
def _skills():
    skills = {}
    for fn in sorted(glob.glob(os.path.join(paths.SKILLS, "*.yaml"))):
        area = os.path.splitext(os.path.basename(fn))[0]
        doc = paths.load_yaml(fn)
        if doc.get("area") != area:
            raise DataError(f"{paths.rel(fn)}: area {doc.get('area')}, expected {area}")
        for e in doc["skills"]:
            if e["area"] != area:
                raise DataError(f"{paths.rel(fn)}: {e['id']} has area {e['area']}, expected {area}")
            if e["id"] in skills:
                raise DataError(f"{paths.rel(fn)}: duplicate id {e['id']}")
            if "used_by" in e:
                raise DataError(f"{paths.rel(fn)}: {e['id']}: used_by is derived, do not author it")
            skills[e["id"]] = e
    return sort_skills(skills)


def _challenges(season):
    out = {}
    for fn in sorted(glob.glob(season.file("challenges", "*.yaml"))):
        ch = paths.load_yaml(fn)
        for k in ("total_score", "used_by"):
            if k in ch:
                raise DataError(f"{paths.rel(fn)}: {k} is derived, do not author it")
        out[os.path.splitext(os.path.basename(fn))[0]] = ch
    return out


def _vocab(season):
    vocab = {n: paths.load_yaml(os.path.join(paths.VOCAB, f"{n}.yaml")) for n in VOCAB_FILES}
    od = os.path.join(paths.VOCAB, "objects")
    vocab["objects"] = {
        "catalog": paths.load_yaml(os.path.join(od, "catalog.yaml"))["objects"],
        "fixtures": paths.load_yaml(os.path.join(od, "fixtures.yaml"))["fixtures"],
        "set": paths.load_yaml(season.file("objects.yaml")),
    }
    return vocab


def load(year=None):
    """The Build of a season (default: the one in force), rated.

    Data errors found while rating are in build.errors; structural errors
    (duplicate ids, unknown base, ...) raise DataError."""
    from . import ratings, overlay
    season = Season(year if year is not None else current())
    if season.base is not None:
        base = load(season.base)
        if base.errors:
            raise DataError(f"base season {season.base} has data errors; run `skilldict check {season.base}`")
        b = overlay.apply(base, season)
    else:
        gr = os.path.join(paths.VOCAB, "global_rules.yaml")
        b = Build(season, _skills(), _challenges(season), _vocab(season),
                  paths.load_yaml(gr) if os.path.exists(gr) else None)
        ratings.rate(b)
    return b


def copy_build(base, season):
    """A proposal starts as a deep copy of its base."""
    b = Build(season, copy.deepcopy(base.skills), copy.deepcopy(base.challenges),
              copy.deepcopy(base.vocab), copy.deepcopy(base.global_rules))
    b.rulebook_version = base.rulebook_version
    b.base = base
    return b
