"""Vocabulary integrity and intrinsic difficulty.

rate(build) checks that every line can be interpreted (known taxonomy node,
objects, places, factors and levels; penalties name a failure mode) and rates
each line: D = sum of the factor weights of its objects, its places (`at:`)
and its conditions. A line covering several objects or places, or a condition
given as a list of levels (drawn at test time), gets a D range.

Errors go to build.errors; build.ratings is the per-line result, written to
dist/skill_ratings.json. build.rater keeps the intermediate tables for the
findings report.
"""


class Rater:
    def __init__(self, build):
        V = build.vocab
        self.tax, self.fac = V["taxonomy"], V["difficulty_factors"]
        self.catalog, self.furniture = V["objects"]["catalog"], V["objects"]["furniture"]
        self.oset = V["objects"]["set"]
        self.nodes, self.fmodes = self.tax["nodes"], self.tax["failure_modes"]
        self.factors = self.fac["factors"]
        # Names a dictionary entry may use in `objects:`: a year-set class,
        # test-object group or category, a catalog object, or a part (x.part).
        self.groups = {**self.oset.get("classes", {}), **self.oset.get("test_objects", {}),
                       **{k: v["members"] for k, v in self.oset.get("categories", {}).items()}}
        self.errors = []
        self.obj = {}                     # object or part id -> {factor: level}
        self.place = {}                   # place id (furniture.place) -> {factor: level}
        self.place_groups = {}            # furniture id or group -> member names
        self.names = {}                   # object, part or place id -> human name
        self.rated = {}                   # id -> (Dmin, Dmax, per-instance) or None
        self._check_vocabulary()
        self._object_levels()
        self._places()
        for g in self.groups:
            self.expand(g)
        for g in self.place_groups:
            self.expand_at(g)
        for eid, e in build.skills.items():
            self._check_entry(e)
        self.rated = {eid: self.rate(e) for eid, e in build.skills.items()}

    def err(self, msg):
        self.errors.append(msg)

    # ── vocabulary ───────────────────────────────────────────────────────────
    def _check_vocabulary(self):
        for nid, n in self.nodes.items():
            area = nid.split(".")[0]
            for ref in [n.get("parent")] + n.get("composed_of", []) + [n.get("replaced_by")]:
                if ref and ref not in self.nodes:
                    self.err(f"taxonomy {nid}: unknown node {ref}")
            if n.get("parent") and not n["parent"].startswith(area + "."):
                self.err(f"taxonomy {nid}: parent {n['parent']} is in another area")
            for f in n.get("factors", []):
                if f not in self.factors:
                    self.err(f"taxonomy {nid}: unknown factor {f}")
            for s in n.get("sources", []):
                if s not in self.tax.get("sources", {}):
                    self.err(f"taxonomy {nid}: unknown source {s}")
            if n.get("status") not in ("active", "proposed", "deprecated"):
                self.err(f"taxonomy {nid}: bad status {n.get('status')}")
            for k in ("name", "intent", "success"):
                if not n.get(k):
                    self.err(f"taxonomy {nid}: missing {k}")
        for fid, f in self.factors.items():
            if f["source"] not in ("object", "place", "condition"):
                self.err(f"factor {fid}: bad source {f['source']}")
            for lv, spec in f["levels"].items():
                if spec["weight"] not in (0, 1, 2):
                    self.err(f"factor {fid}.{lv}: weight must be 0, 1 or 2")

    def _level_from_measure(self, fid, value):
        """Map a number onto the factor's levels: `below` cut-offs in ascending
        order, or `within` ranges; a level with neither takes the rest."""
        levels = self.factors[fid]["levels"]
        if any("within" in s for s in levels.values()):
            for lv, spec in levels.items():
                if any(lo <= value < hi for lo, hi in spec.get("within", [])):
                    return lv
            return next(lv for lv, spec in levels.items() if "within" not in spec)
        for lv, spec in levels.items():
            if spec.get("below") is None or value < spec["below"]:
                return lv

    def _rate_thing(self, what, spec, sources):
        """Factor levels of an object, part or place, from its measured numbers
        and judged levels. `sources`: which factor sources apply."""
        fac = {}
        for fid, f in self.factors.items():
            if f["source"] not in sources:
                continue
            if f.get("measure"):
                if f["measure"] in spec:
                    if not isinstance(spec[f["measure"]], (int, float)):
                        self.err(f"{what}: {f['measure']} must be a number")
                        continue
                    fac[fid] = self._level_from_measure(fid, spec[f["measure"]])
            elif fid in spec:
                fac[fid] = spec[fid]
        for fid, lv in fac.items():
            if lv not in self.factors[fid]["levels"]:
                self.err(f"{what}: {fid}={lv} not a level")
        return fac

    def _places(self):
        F = self.furniture
        if F.get("values") not in ("measured", "estimate"):
            self.err("furniture: values must be measured or estimate")
        for fid, f in F["furniture"].items():
            if "." in fid:
                self.err(f"furniture {fid}: no dots in ids")
            self.names[fid] = f["name"]
            members = []
            for pid, p in (f.get("places") or {}).items():
                key = f"{fid}.{pid}"
                if not isinstance(p.get("height_mm"), (int, float)) or "access" not in p:
                    self.err(f"place {key}: needs height_mm and access")
                self.place[key] = self._rate_thing(f"place {key}", p, ("place",))
                self.names[key] = f"{f['name']}, {pid.replace('_', ' ')}"
                members.append(key)
            if members:
                self.place_groups[fid] = members
            for part, p in (f.get("parts") or {}).items():
                key = f"{fid}.{part}"
                self.obj[key] = self._rate_thing(f"part {key}", p, ("object", "place"))
                self.names[key] = p.get("name", key)
        for g, members in (F.get("groups") or {}).items():
            if g in self.place_groups:
                self.err(f"furniture group {g} collides with a furniture id")
            self.place_groups[g] = members

    def expand_at(self, name, seen=()):
        """Resolve an at: name to the set of place ids it covers."""
        if name in self.place:
            return {name}
        if name not in self.place_groups:
            self.err(f"unknown place, furniture or furniture group {name}")
            return set()
        if name in seen:
            self.err(f"furniture groups: cycle through {name}")
            return set()
        out = set()
        for m in self.place_groups[name]:
            out |= self.expand_at(m, seen + (name,))
        return out

    def _object_levels(self):
        measured = {f["measure"]: fid for fid, f in self.factors.items()
                    if f.get("measure") and f["source"] == "object"}
        judged = [fid for fid, f in self.factors.items() if f["source"] == "object" and not f.get("measure")]
        for oid, o in self.catalog.items():
            fac = {}
            for field, fid in measured.items():
                if not isinstance(o.get(field), (int, float)):
                    self.err(f"catalog {oid}: missing numeric {field}")
                    continue
                fac[fid] = self._level_from_measure(fid, o[field])
            for fid in judged:
                if fid in o:
                    fac[fid] = o[fid]
            self.obj[oid] = fac
        for oid, o in self.catalog.items():
            self.names[oid] = o["name"]
            for part, p in (o.get("parts") or {}).items():
                self.obj[f"{oid}.{part}"] = self._rate_thing(f"part {oid}.{part}", p, ("object",))
                self.names[f"{oid}.{part}"] = p.get("name", f"{oid}.{part}")
        for oid, fac in self.obj.items():
            for fid, lv in fac.items():
                if lv not in self.factors[fid]["levels"]:
                    self.err(f"object {oid}: {fid}={lv} not a level")
        for oid, o in self.catalog.items():
            if o.get("values") not in ("measured", "ycb", "estimate"):
                self.err(f"catalog {oid}: values must be measured, ycb or estimate")
            if o.get("values") == "ycb" and not o.get("ycb"):
                self.err(f"catalog {oid}: values: ycb but no ycb id")
        for k in ("surface", "rigidity", "shape"):
            for oid, o in self.catalog.items():
                if k not in o:
                    self.err(f"catalog {oid}: missing judged factor {k}")
        for name in set(self.groups) & set(self.catalog):
            self.err(f"object set: group name {name} collides with an object id")

    def expand(self, name, seen=()):
        """Resolve an objects: name to the set of physical object ids it covers."""
        if name in self.obj:
            return {name}
        if name not in self.groups:
            self.err(f"unknown object or group {name}")
            return set()
        if name in seen:
            self.err(f"object set: cycle through {name}")
            return set()
        out = set()
        for m in self.groups[name]:
            out |= self.expand(m, seen + (name,))
        if not out:
            self.err(f"object set: group {name} is empty")
        return out

    # ── entries ──────────────────────────────────────────────────────────────
    def node_factors(self, e):
        return set(self.nodes[e["taxonomy"]].get("factors", []))

    def _check_entry(self, e):
        nid = e["taxonomy"]
        if nid not in self.nodes:
            self.err(f"{e['id']}: unknown taxonomy node {nid}")
            return
        if nid.split(".")[0] != e["area"]:
            self.err(f"{e['id']}: node {nid} is not in area {e['area']}")
        if self.nodes[nid]["status"] == "deprecated":
            self.err(f"{e['id']}: node {nid} is deprecated")
        if self.nodes[nid].get("scored", True) is False:
            self.err(f"{e['id']}: node {nid} is decomposition-only (scored: false)")
        applies = self.node_factors(e)
        for o in e.get("objects", []):
            if o not in self.obj and o not in self.groups:
                self.err(f"{e['id']}: unknown object, part or group {o}")
        for a in e.get("at", []):
            if a not in self.place and a not in self.place_groups:
                self.err(f"{e['id']}: unknown place {a} (furniture.yaml)")
        if e.get("at") and not {"height", "access"} & applies:
            self.err(f"{e['id']}: at: on {nid}, which has no place factors")
        for fid, lv in e.get("conditions", {}).items():
            lvs = lv if isinstance(lv, list) else [lv]
            if fid not in self.factors:
                self.err(f"{e['id']}: unknown factor {fid}")
            elif self.factors[fid]["source"] == "place":
                self.err(f"{e['id']}: {fid} is a property of the place, name it in at: (furniture.yaml)")
            elif self.factors[fid]["source"] != "condition":
                self.err(f"{e['id']}: {fid} is an object property, set it in vocabulary/objects/catalog.yaml")
            elif not lvs or any(x not in self.factors[fid]["levels"] for x in lvs):
                self.err(f"{e['id']}: {fid}={lv} not a level")
            elif fid not in applies:
                self.err(f"{e['id']}: factor {fid} does not apply to {nid}")
        fm = e.get("failure_mode")
        if fm and fm not in self.fmodes:
            self.err(f"{e['id']}: unknown failure_mode {fm}")
        if fm and e["type"] in ("achievement", "bonus"):
            self.err(f"{e['id']}: failure_mode on a {e['type']}")
        if e["type"] == "penalty_behavior" and not fm and not e.get("objects"):
            self.err(f"{e['id']}: penalty without failure_mode (or objects, for a price discount)")

    # ── difficulty ───────────────────────────────────────────────────────────
    def weight(self, fid, lv):
        return self.factors[fid]["levels"][lv]["weight"]

    def tier(self, d):
        for t, spec in self.fac["tiers"].items():
            if spec["max"] is None or d <= spec["max"]:
                return t

    def rate(self, e):
        """(Dmin, Dmax, per-instance breakdown) or None if the entry has no factors.

        An instance is one object at one place ("plate@dishwasher.rack_top");
        its values are (dmin, dmax, factors), which differ only when a
        condition is a list of levels."""
        if e["taxonomy"] not in self.nodes:
            return None
        applies = self.node_factors(e)
        if not applies or not (e.get("objects") or e.get("conditions") or e.get("at")):
            return None
        cond = {f: lv for f, lv in e.get("conditions", {}).items() if f in applies}
        try:
            span = {f: [self.weight(f, x) for x in (lv if isinstance(lv, list) else [lv])]
                    for f, lv in cond.items()}
        except KeyError:
            return None                                  # already reported as an error
        lo = sum(min(w) for w in span.values())
        hi = sum(max(w) for w in span.values())
        per = {}
        objs = sorted(set().union(*[self.expand(o) for o in e.get("objects", [])])) or [None]
        places = sorted(set().union(*[self.expand_at(a) for a in e.get("at", [])])) or [None]
        for o in objs:
            for p in places:
                fac = dict(cond)
                for src in (self.obj.get(o) if o else None, self.place.get(p) if p else None):
                    fac.update({f: lv for f, lv in (src or {}).items() if f in applies})
                d = sum(self.weight(f, lv) for f, lv in fac.items() if f not in cond)
                key = "@".join(x for x in (o, p) if x) or "-"
                per[key] = (lo + d, hi + d, fac)
        return min(p[0] for p in per.values()), max(p[1] for p in per.values()), per

    def as_json(self, build):
        out = {}
        for eid, e in build.skills.items():
            r = self.rated[eid]
            out[eid] = {
                "taxonomy": e["taxonomy"],
                "objects": e.get("objects", []),
                "difficulty": None if not r else {
                    "min": r[0], "max": r[1], "tier": self.tier(r[1]),
                    "per_object": {o: {"min": a, "max": b, "factors": f} for o, (a, b, f) in r[2].items()},
                },
                "level": e["level"],
            }
        return out


def rate(build):
    r = Rater(build)
    build.rater, build.errors, build.ratings = r, r.errors, r.as_json(build)
    return build


def dmin(ratings, eid):
    r = (ratings.get(eid) or {}).get("difficulty")
    return None if r is None else r["min"]


def drange(ratings, eid):
    r = (ratings.get(eid) or {}).get("difficulty")
    return "" if r is None else (f'{r["min"]}' if r["min"] == r["max"] else f'{r["min"]}-{r["max"]}')
