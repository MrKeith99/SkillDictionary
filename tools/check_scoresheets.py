#!/usr/bin/env python3
"""Verify the dictionary against the ORIGINAL rulebook scoresheets (LaTeX).

reconcile.py proves the merge is faithful to the extraction. This proves the
extraction is faithful to the rulebook -- it is the only check that can catch the
extraction going stale when the TC edits a .tex sheet.

Sheets are read from the RuleBook git submodule (pinned to a commit), so the
rulebook text is never duplicated into this repo and the pin cannot drift from
what the docs claim. Override the location with an argument or RULEBOOK_DIR.

Usage:  check_scoresheets.py [<dir-of-tex-files>]
"""
import json, os, re, sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SUBMODULE = os.path.join(ROOT, "external", "RuleBook")


def resolve_sheets():
    """Locate the scoresheet .tex files.

    Order: explicit argument, then RULEBOOK_DIR, then the pinned submodule.
    """
    if len(sys.argv) > 1:
        return sys.argv[1]
    env = os.environ.get("RULEBOOK_DIR")
    if env:
        return os.path.join(env, "scoresheets")
    return os.path.join(SUBMODULE, "scoresheets")


TEX = resolve_sheets()

if not os.path.isdir(TEX):
    print(f"ERROR: scoresheets not found at {TEX}\n"
          f"\nThe RuleBook is a git submodule. Initialise it with:\n"
          f"    git submodule update --init --recursive\n"
          f"\nOr point at an existing checkout:\n"
          f"    RULEBOOK_DIR=/path/to/RuleBook tools/check_scoresheets.py",
          file=sys.stderr)
    sys.exit(2)

SHEET = {
    "DoingLaundry": "doing_laundry",
    "GPSR": "gpsr",
    "HumanRobotInteractionChallenge": "hri",
    "PickAndPlaceChallenge": "pick_and_place",
    "Restaurant": "restaurant",
}

# \scoreitem[count]{points}{description}   -- reward
# \scoremod[count]{points}{description}    -- bonus
# \scorepen[count]{points}{description}    -- penalty inside a reward block
# \penaltyitem[count]{points}{description} -- standalone penalty
ITEM = re.compile(
    r"\\(?P<cmd>scoreitem|scoremod|scorepen|penaltyitem)"
    r"(?:\[(?P<count>\d+)\])?"
    r"\{(?P<points>-?\d+)\}"
    r"\{(?P<desc>(?:[^{}]|\{[^{}]*\})*)\}")

NEG = {"scorepen", "penaltyitem"}   # these are costs; sign may be implicit


def clean(s):
    s = re.sub(r"\\[a-zA-Z]+\s*", "", s)
    s = s.replace("{", "").replace("}", "").replace("~", " ")
    s = s.replace("\\&", "&").replace("--", "-")
    return re.sub(r"\s+", " ", s).strip().lower()


def parse(path):
    out = []
    for m in ITEM.finditer(open(path).read()):
        cnt = int(m.group("count") or 1)
        pts = int(m.group("points"))
        if m.group("cmd") in NEG:
            pts = -abs(pts)
        # A {0}-valued scoreitem is not a scored line. It is either a rendered
        # note (GPSR percentage-penalty explanation) or a container header whose
        # real points sit in the \scoremod/\scorepen beneath it (HRI visual
        # attribute). Both are already modelled correctly in the dictionary.
        if pts == 0 and m.group("cmd") == "scoreitem":
            continue
        out.append({"cmd": m.group("cmd"), "count": cnt,
                    "points": pts, "desc": clean(m.group("desc"))})
    return out


dict_doc = json.load(open(os.path.join(ROOT, "dist", "dictionary.json")))
ch_doc = json.load(open(os.path.join(ROOT, "dist", "challenges.json")))
DICT = {e["id"]: e for e in dict_doc["skills"]}

fail = 0


def rulebook_version():
    """Describe the checked-out rulebook, for the header line."""
    import subprocess
    repo = os.path.dirname(TEX.rstrip("/"))
    try:
        out = subprocess.run(["git", "-C", repo, "describe", "--tags", "--always"],
                             capture_output=True, text=True, timeout=5)
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


TARGET = dict_doc.get("rulebook_version")
ACTUAL = rulebook_version()

print("=" * 78)
print(f"SCORESHEET — dictionary vs rulebook LaTeX ({TEX})")
print(f"  dictionary targets {TARGET} | rulebook checkout reports {ACTUAL}")
if TARGET and ACTUAL != "unknown" and not ACTUAL.startswith(TARGET):
    print(f"  WARNING: checkout is not {TARGET}. Results below may reflect a "
          f"different rulebook version.")

for tex, slug in sorted(SHEET.items(), key=lambda x: x[1]):
    path = os.path.join(TEX, tex + ".tex")
    if not os.path.exists(path):
        # The dictionary models this challenge, so its sheet must exist. A missing
        # one means the rulebook removed the task (or the pin moved) while the
        # dictionary still carries it -- precisely the drift this check exists for.
        print(f"  {slug:16s} FAIL (no {tex}.tex at this rulebook version)")
        fail += 1
        continue
    sheet = parse(path)
    ch = ch_doc["challenges"][slug]

    # Build the dictionary's own view of this sheet: (points, count, description).
    ours = []
    for it in ch["entries"]:
        e = DICT[it["ref"]]
        if e["type"] == "administrative":
            continue          # §3.8 lines are not printed as scorelist items
        p = e["points"]
        if p is None:
            continue          # unpriced in the rulebook (e.g. GPSR partial)
        ours.append({"points": p, "count": it.get("count", 1),
                     "desc": e["description"].lower().strip()})

    # Compare as multisets of (points, count) -- description wording differs
    # slightly between sheet and extraction, so match on the scoring facts.
    a = Counter((x["points"], x["count"]) for x in sheet)
    b = Counter((x["points"], x["count"]) for x in ours)

    only_sheet, only_dict = a - b, b - a
    sheet_reward = sum(x["points"] * x["count"] for x in sheet if x["points"] > 0)
    our_reward = sum(x["points"] * x["count"] for x in ours if x["points"] > 0)

    ok = not only_sheet and not only_dict
    print(f"  {slug:16s} sheet {len(sheet):3d} lines / dict {len(ours):3d} | "
          f"reward {sheet_reward:5d} vs {our_reward:5d} | "
          f"{'MATCH' if ok else 'DIFF'}")
    if sheet_reward != our_reward:
        fail += 1
    for (p, c), n in sorted(only_sheet.items()):
        fail += 1
        ex = next(x["desc"] for x in sheet if (x["points"], x["count"]) == (p, c))
        print(f"      in SHEET only x{n}: {c}x{p:>5}  {ex[:46]}")
    for (p, c), n in sorted(only_dict.items()):
        fail += 1
        ex = next(x["desc"] for x in ours if (x["points"], x["count"]) == (p, c))
        print(f"      in DICT  only x{n}: {c}x{p:>5}  {ex[:46]}")

print("=" * 78)
print("SCORESHEET PASS" if not fail else f"SCORESHEET FAIL ({fail} discrepancies)")
sys.exit(1 if fail else 0)
