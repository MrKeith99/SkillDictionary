"""The in-force season against the rulebook's own score sheets (LaTeX).

The only check that catches the dictionary drifting from the rules it
describes, in either direction: the TC edits a .tex sheet, or someone edits
a price here. Sheets are read from the RuleBook submodule pinned in the
season's season.yaml (override with RULEBOOK_DIR).
"""
import os, re, subprocess
from collections import Counter
from .. import paths
from . import RULE

# \scoreitem[count]{points}{description}   -- reward
# \scoremod[count]{points}{description}    -- bonus
# \scorepen[count]{points}{description}    -- penalty inside a reward block
# \penaltyitem[count]{points}{description} -- standalone penalty
ITEM = re.compile(
    r"\\(?P<cmd>scoreitem|scoremod|scorepen|penaltyitem)"
    r"(?:\[(?P<count>\d+)\])?"
    r"\{(?P<points>-?\d+)\}"
    r"\{(?P<desc>(?:[^{}]|\{[^{}]*\})*)\}")
NEG = {"scorepen", "penaltyitem"}   # these are costs; the sign may be implicit


def clean(s):
    s = re.sub(r"\\[a-zA-Z]+\s*", "", s)
    s = s.replace("{", "").replace("}", "").replace("~", " ")
    s = s.replace("\\&", "&").replace("--", "-")
    return re.sub(r"\s+", " ", s).strip().lower()


def parse(path):
    out = []
    for m in ITEM.finditer(open(path).read()):
        pts = int(m.group("points"))
        if m.group("cmd") in NEG:
            pts = -abs(pts)
        # A {0}-valued scoreitem is not a scored line: a rendered note (GPSR
        # percentage penalty) or a container header whose points sit in the
        # \scoremod/\scorepen beneath it (HRI visual attribute).
        if pts == 0 and m.group("cmd") == "scoreitem":
            continue
        out.append({"cmd": m.group("cmd"), "count": int(m.group("count") or 1),
                    "points": pts, "desc": clean(m.group("desc"))})
    return out


def sheets_dir():
    return os.path.join(paths.RULEBOOK, "scoresheets")


def checkout():
    try:
        r = subprocess.run(["git", "-C", paths.RULEBOOK, "describe", "--tags", "--always"],
                           capture_output=True, text=True, timeout=5)
        return r.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def run(b):
    tex = sheets_dir()
    print(RULE)
    print(f"RULEBOOK — {b.season} vs the rulebook's score sheets ({paths.rel(tex)})")
    if not os.path.isdir(tex):
        print(f"  ERROR: no score sheets at {tex}\n"
              f"  The RuleBook is a git submodule: git submodule update --init --recursive\n"
              f"  or point at a checkout: RULEBOOK_DIR=/path/to/RuleBook")
        return 1
    target, actual = b.rulebook_version, checkout()
    print(f"  season targets {target} | rulebook checkout reports {actual}")
    if target and actual != "unknown" and not actual.startswith(target):
        print(f"  WARNING: checkout is not {target}; results may reflect another rulebook version.")
    fail = 0
    for slug in sorted(b.challenges):
        name = b.season.sheets.get(slug)
        path = os.path.join(tex, f"{name}.tex") if name else None
        if not path or not os.path.exists(path):
            # The season models this challenge, so its sheet must exist: a missing
            # one means the rulebook dropped the task or the pin moved.
            print(f"  {slug:16s} FAIL (no score sheet {name or '(not listed in season.yaml)'})")
            fail += 1
            continue
        sheet = parse(path)
        ours = []
        for it in b.challenges[slug]["entries"]:
            e = b.skills[it["ref"]]
            if e["type"] == "administrative" or e.get("points") is None:
                continue          # §3.8 lines are not scorelist items; unpriced lines are judged
            ours.append({"points": e["points"], "count": it.get("count", 1),
                         "desc": e["description"].lower().strip()})
        # Compare as multisets of (points, count): wording differs slightly.
        a = Counter((x["points"], x["count"]) for x in sheet)
        o = Counter((x["points"], x["count"]) for x in ours)
        only_sheet, only_dict = a - o, o - a
        sheet_reward = sum(x["points"] * x["count"] for x in sheet if x["points"] > 0)
        our_reward = sum(x["points"] * x["count"] for x in ours if x["points"] > 0)
        ok = not only_sheet and not only_dict
        print(f"  {slug:16s} sheet {len(sheet):3d} lines / dict {len(ours):3d} | "
              f"reward {sheet_reward:5d} vs {our_reward:5d} | {'MATCH' if ok else 'DIFF'}")
        fail += sheet_reward != our_reward
        for (p, c), n in sorted(only_sheet.items()):
            fail += 1
            ex = next(x["desc"] for x in sheet if (x["points"], x["count"]) == (p, c))
            print(f"      in SHEET only x{n}: {c}x{p:>5}  {ex[:46]}")
        for (p, c), n in sorted(only_dict.items()):
            fail += 1
            ex = next(x["desc"] for x in ours if (x["points"], x["count"]) == (p, c))
            print(f"      in DICT  only x{n}: {c}x{p:>5}  {ex[:46]}")
    return fail
