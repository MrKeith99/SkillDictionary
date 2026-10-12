#!/usr/bin/env python3
"""Apply the proposed pricing rule (vocabulary/pricing.yaml) to every line.

Reads : dist/*.json (run build_dist.py and check_taxonomy.py first),
        vocabulary/pricing.yaml
Writes: dist/pricing_2027.json   per line: rulebook price, rule price, why
        dist/pricing_2027.csv    the same, for a spreadsheet
        dist/pricing_2027.html   review page for the TC

Nothing here changes dictionary/: the rule is a proposal. The report says what
the rule would do — per line, per challenge total, and to the T2/T3 findings —
so the TC can decide on the rule rather than on individual numbers.
"""
import csv, html, json, os
from collections import defaultdict, OrderedDict
from pricing_rule import RULE, weight, rnd, calibrate

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DIST = os.environ.get("SKILLDICT_DIST", os.path.join(ROOT, "dist"))


def load(name):
    with open(os.path.join(DIST, name)) as fh:
        return json.load(fh)


D = {e["id"]: e for e in load("dictionary.json")["skills"]}
CH = load("challenges.json")["challenges"]
R = load("skill_ratings.json")
NODES = load("vocabulary.json")["taxonomy"]["nodes"]


def dmin(eid):
    r = (R.get(eid) or {}).get("difficulty")
    return None if r is None else r["min"]


def drange(eid):
    r = (R.get(eid) or {}).get("difficulty")
    return "" if r is None else (f'{r["min"]}' if r["min"] == r["max"] else f'{r["min"]}-{r["max"]}')


# A bonus that never hangs off a parent line (e.g. the interleaving bonus) is
# priced like an achievement.
CHILDREN = {it["ref"] for ch in CH.values() for it in ch["entries"] if it.get("related_skill")}


def standalone(e):
    return e["type"] == "achievement" or (e["type"] == "bonus" and e["id"] not in CHILDREN)


# ── calibrate one base per node from the 2026 standalone lines ──────────────
BASE = calibrate([e for e in D.values() if standalone(e)], R)


def rule_price(eid):
    """Price the rule gives the line's own skill at the line's own D."""
    e = D[eid]
    if e["taxonomy"] not in BASE or dmin(eid) is None:
        return None
    return BASE[e["taxonomy"]] * weight(dmin(eid))


# ── parent of every line, per challenge ─────────────────────────────────────
def parents(ch):
    out = {}
    for it in ch["entries"]:
        if it.get("related_skill"):
            out[it["ref"]] = it["related_skill"]
        a = it.get("assistance") or {}
        if a.get("extra_penalty_ref"):
            out.setdefault(a["extra_penalty_ref"], it["ref"])
    return out


# ── price every line ────────────────────────────────────────────────────────
new = {}          # id -> (price, how)
for eid, e in D.items():
    if e["type"] == "administrative":
        continue
    old = e.get("points")
    if standalone(e):
        p = rule_price(eid)
        new[eid] = (rnd(p), f"base {BASE[e['taxonomy']]:.0f} x {weight(dmin(eid)):.2f}") if p is not None \
            else (old, "kept: no difficulty factors")
new_ach = dict(new)

for slug, ch in CH.items():
    par = parents(ch)
    for it in ch["entries"]:
        eid = it["ref"]
        e = D[eid]
        if standalone(e) or e["type"] == "administrative":
            continue
        old = e.get("points")
        parent = par.get(eid)
        fm = e.get("failure_mode")
        if old is None:
            res = (None, "kept: judged on the day")
        elif old == 0:
            res = (0, "kept: explicitly free")
        elif fm in (RULE.get("fixed_penalty") or {}):
            res = (RULE["fixed_penalty"][fm], f"{fm}: fixed conduct penalty")
        elif fm:
            if not parent or new_ach.get(parent, (None,))[0] is None:
                res = (old, "kept: penalty with no priced parent line")
            else:
                share = RULE["penalty_share"][fm]
                res = (-rnd(share * new_ach[parent][0]), f"{fm} {share:.0%} of {parent}")
        else:                                   # bonus or discount on a parent
            rp, pp = rule_price(eid), new_ach.get(parent, (None,))[0] if parent else None
            if rp is None or pp is None:
                res = (old, "kept: no difficulty factors" if rp is None else "kept: no parent line")
            else:
                res = (rnd(rp) - pp, f"rule at D{dmin(eid)} = {rnd(rp)}, minus parent {pp}")
        if eid in new and new[eid][0] != res[0]:
            res = (new[eid][0], new[eid][1] + f"; CONFLICT in {slug}: {res[0]}")
        new.setdefault(eid, res)
        if eid in new and "CONFLICT" in res[1]:
            new[eid] = res


# ── report ──────────────────────────────────────────────────────────────────
rows = []
for slug, ch in CH.items():
    par = parents(ch)
    for it in ch["entries"]:
        eid = it["ref"]
        e = D[eid]
        if e["type"] == "administrative":
            continue
        p, how = new[eid]
        rows.append(OrderedDict(
            challenge=slug, section=it.get("section") or "", id=eid, node=e["taxonomy"], type=e["type"],
            description=e["description"], D=drange(eid), count=it.get("count", 1),
            points_2026=e.get("points"), points_2027=p,
            delta=None if p is None or e.get("points") is None else p - e["points"],
            parent=par.get(eid, ""), rule=how))


def effective(price_of, slug):
    """(node, D-range lo, hi, effective price, id) for every achievement / bonus line."""
    par = parents(CH[slug])
    out = []
    for it in CH[slug]["entries"]:
        e = D[it["ref"]]
        r = (R.get(e["id"]) or {}).get("difficulty")
        if not r or e.get("failure_mode") or e["type"] not in ("achievement", "bonus", "penalty_behavior"):
            continue
        p = price_of(e["id"])
        if p is None:
            continue
        if e["type"] != "achievement":
            parent = par.get(e["id"])
            if not parent or price_of(parent) is None:
                continue
            p += price_of(parent)
        out.append((e["taxonomy"], r["min"], r["max"], p, e["id"]))
    return out


def inversions(price_of):
    lines = [l for s in CH for l in effective(price_of, s)]
    by = defaultdict(list)
    for l in lines:
        by[l[0]].append(l)
    inv = []
    for node, ls in by.items():
        for a in ls:
            for b in ls:
                if a[1] > b[2] and a[3] < b[3]:
                    inv.append((node, a, b))
    return inv


inv_old = inversions(lambda i: D[i].get("points"))
inv_new = inversions(lambda i: new.get(i, (None,))[0])


def penalty_prices(price_of):
    out = defaultdict(set)
    for e in D.values():
        if e.get("failure_mode") and price_of(e["id"]) not in (None,):
            out[e["failure_mode"]].add(price_of(e["id"]))
    return out


pen_old = penalty_prices(lambda i: D[i].get("points"))


def totals(price_of):
    t = {}
    for slug, ch in CH.items():
        t[slug] = sum((price_of(it["ref"]) or 0) * it.get("count", 1) for it in ch["entries"]
                      if D[it["ref"]]["type"] != "administrative" and (price_of(it["ref"]) or 0) > 0)
    return t


tot_old = totals(lambda i: D[i].get("points"))
tot_new = totals(lambda i: new.get(i, (None,))[0])

json.dump({"rule": RULE, "base": {n: round(b, 1) for n, b in sorted(BASE.items())}, "lines": rows,
           "totals": {s: {"2026": tot_old[s], "2027": tot_new[s]} for s in CH},
           "inversions": {"2026": len(inv_old), "2027": len(inv_new)}},
          open(os.path.join(DIST, "pricing_2027.json"), "w"), indent=1)
with open(os.path.join(DIST, "pricing_2027.csv"), "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)

print("=" * 78)
print("PROPOSED 2027 PRICES (vocabulary/pricing.yaml) — proposal, dictionary unchanged")
print(f"  price inversions within a skill: {len(inv_old)} -> {len(inv_new)}")
for node, a, b in inv_new:
    print(f"    still: {a[4]} D{a[1]}-{a[2]} = {a[3]}  <  {b[4]} D{b[1]}-{b[2]} = {b[3]}")
print("  challenge max (positive lines):")
for s in CH:
    print(f"    {s:16s} {tot_old[s]:6d} -> {tot_new[s]:6d}  ({tot_new[s] - tot_old[s]:+d})")
kept = sorted({(r['id'], r['rule']) for r in rows if r['rule'].startswith('kept')})
print(f"  lines the rule cannot price ({len(kept)}): kept at rulebook value")
for i, why in kept:
    print(f"    {i:28s} {why}")
for r in rows:
    if "CONFLICT" in r["rule"]:
        print(f"  CONFLICT {r['id']}: {r['rule']}")


# ── review page ─────────────────────────────────────────────────────────────
def esc(s):
    return html.escape("" if s is None else str(s))


def fmt(v):
    return "—" if v is None else f"{v:+d}" if isinstance(v, int) and v < 0 else str(v)


sections = []
for slug, ch in CH.items():
    trs = []
    for r in (x for x in rows if x["challenge"] == slug):
        d = r["delta"]
        cls = "" if not d else ("up" if d > 0 else "down")
        kept_cls = " kept" if r["rule"].startswith("kept") else ""
        trs.append(
            f'<tr class="{r["type"]}{kept_cls}"><td><span class="id">{esc(r["id"])}</span>'
            f'<span class="desc">{esc(r["description"])}</span></td>'
            f'<td class="node">{esc(r["node"])}</td><td class="num">{esc(r["D"])}</td>'
            f'<td class="num">{esc(r["count"])}×</td>'
            f'<td class="num">{fmt(r["points_2026"])}</td><td class="num strong">{fmt(r["points_2027"])}</td>'
            f'<td class="num {cls}">{"" if not d else f"{d:+d}"}</td><td class="why">{esc(r["rule"])}</td></tr>')
    sections.append(
        f'<section id="{slug}"><h2>{esc(ch["challenge"])}<span class="tot">max {tot_old[slug]} → '
        f'<b>{tot_new[slug]}</b> ({tot_new[slug] - tot_old[slug]:+d})</span></h2>'
        f'<div class="tw"><table><thead><tr><th>Line</th><th>Skill</th><th class="num">D</th>'
        f'<th class="num">×</th><th class="num">2026</th><th class="num">2027</th><th class="num">Δ</th>'
        f'<th>How</th></tr></thead><tbody>{"".join(trs)}</tbody></table></div></section>')

base_rows = "".join(
    f'<tr><td class="node">{esc(n)}</td><td>{esc(NODES[n]["name"])}</td><td class="num">{b:.0f}</td>'
    f'<td class="num">{rnd(b * weight(2))}</td><td class="num">{rnd(b * weight(5))}</td>'
    f'<td class="num">{rnd(b * weight(8))}</td></tr>'
    for n, b in sorted(BASE.items(), key=lambda x: -x[1]))
share_rows = "".join(
    f'<tr><td>{esc(m.replace("_", " "))}</td><td class="num">{s:.0%}</td>'
    f'<td class="num">{len(pen_old.get(m, []))}</td><td>{esc(", ".join(str(p) for p in sorted(pen_old.get(m, []))))}</td></tr>'
    for m, s in RULE["penalty_share"].items())

PAGE = f"""<title>Proposed 2027 Prices</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700&family=Source+Sans+3:wght@400;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
/* Layout: a TC review memo — the rule and its effect first, then every line per challenge. */
:root {{
  --bg: #f5f7f6; --card: #ffffff; --ink: #17212b; --muted: #5d6b76; --rule: #d9e0e3;
  --accent: #0f6b5c; --up: #1d6b3a; --down: #b3261e; --kept: #a86a00; --chip: #eef2f2;
  --display: "Barlow Condensed", "Arial Narrow", sans-serif;
  --body: "Source Sans 3", "Segoe UI", system-ui, sans-serif;
  --mono: "IBM Plex Mono", ui-monospace, monospace;
}}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{
  --bg: #0f1416; --card: #161d20; --ink: #e4eaec; --muted: #94a3ab; --rule: #2a3438;
  --accent: #4fc2a8; --up: #74c995; --down: #ff8a80; --kept: #e7b450; --chip: #20292d; color-scheme: dark; }} }}
:root[data-theme="dark"] {{
  --bg: #0f1416; --card: #161d20; --ink: #e4eaec; --muted: #94a3ab; --rule: #2a3438;
  --accent: #4fc2a8; --up: #74c995; --down: #ff8a80; --kept: #e7b450; --chip: #20292d; color-scheme: dark; }}
body {{ background: var(--bg); color: var(--ink); font: 15px/1.45 var(--body); }}
.wrap {{ max-width: 1120px; margin: 0 auto; padding-block: 28px 56px; padding-inline: 16px; display: grid; gap: 22px; }}
.eyebrow {{ font: 500 12.5px var(--mono); color: var(--muted); letter-spacing: .04em; }}
h1 {{ font: 700 clamp(30px, 6vw, 46px)/1 var(--display); margin: 6px 0 0; text-transform: uppercase; text-wrap: balance; }}
h2 {{ font: 700 22px var(--display); text-transform: uppercase; letter-spacing: .04em; margin: 0;
      padding: 10px 14px; border-bottom: 2px solid var(--ink); display: flex; flex-wrap: wrap; gap: 6px 16px;
      justify-content: space-between; align-items: baseline; }}
h2 .tot {{ font: 400 14px var(--mono); text-transform: none; letter-spacing: 0; color: var(--muted); }}
h2 .tot b {{ color: var(--ink); font-weight: 500; }}
p {{ margin: 0; max-width: 72ch; }}
.lead {{ color: var(--muted); }}
.kpis {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; }}
.kpi {{ background: var(--card); border: 1px solid var(--rule); padding: 12px 14px; display: grid; gap: 4px; }}
.kpi .v {{ font: 700 34px/1 var(--display); font-variant-numeric: tabular-nums; }}
.kpi .l {{ font-size: 13px; color: var(--muted); }}
section, .card {{ background: var(--card); border: 1px solid var(--rule); min-width: 0; }}
.card .body {{ padding: 12px 14px; display: grid; gap: 10px; }}
.cols {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px; }}
.tw {{ overflow-x: auto; }}
table {{ border-collapse: collapse; width: 100%; font-size: 13.5px; }}
th, td {{ padding: 6px 10px; border-top: 1px solid var(--rule); text-align: left; vertical-align: top; }}
thead th {{ border-top: 0; font: 400 11px var(--body); text-transform: uppercase; letter-spacing: .08em; color: var(--muted); white-space: nowrap; }}
.num {{ text-align: right; font-family: var(--mono); font-variant-numeric: tabular-nums; white-space: nowrap; }}
.strong {{ font-weight: 500; }}
.up {{ color: var(--up); }} .down {{ color: var(--down); }}
.id {{ display: block; font: 11.5px var(--mono); color: var(--muted); }}
.desc {{ display: block; }}
.node {{ font: 500 12px var(--mono); color: var(--accent); white-space: nowrap; }}
.why {{ font-size: 12.5px; color: var(--muted); min-width: 180px; }}
tr.kept .why {{ color: var(--kept); }}
tr.bonus td:first-child, tr.penalty_behavior td:first-child {{ padding-left: 26px; }}
code {{ font: 13px var(--mono); background: var(--chip); padding: 1px 5px; }}
nav {{ display: flex; flex-wrap: wrap; gap: 6px 14px; font-size: 14px; }}
nav a {{ color: var(--accent); }}
</style>
<div class="wrap">
<header>
  <div class="eyebrow">RoboCup@Home Skill Dictionary · PROPOSAL · not in force</div>
  <h1>Proposed 2027 Prices</h1>
</header>
<p class="lead">Every line re-priced by one rule, so the same skill at the same difficulty pays the same in every challenge and the same failure costs the same share everywhere. The rule lives in <code>vocabulary/pricing.yaml</code>; change the rule, not the numbers.</p>

<div class="kpis">
  <div class="kpi"><span class="v">{len(inv_old)} → {len(inv_new)}</span><span class="l">harder line pays less than an easier one, same skill</span></div>
  <div class="kpi"><span class="v">{sum(1 for v in pen_old.values() if len(v) > 1)} → 0</span><span class="l">failure modes priced inconsistently (now a fixed share of the parent line)</span></div>
  <div class="kpi"><span class="v">{sum(tot_old.values())} → {sum(tot_new.values())}</span><span class="l">sum of challenge maximums ({sum(tot_new.values()) - sum(tot_old.values()):+d})</span></div>
  <div class="kpi"><span class="v">{len(kept)}</span><span class="l">lines kept at the rulebook value (rule cannot price them yet)</span></div>
</div>

<div class="card"><h2>The rule</h2><div class="body">
  <p><b>Achievement</b> = skill base × (1 + D / {RULE['d_scale']}), with D the easiest instance the line covers. Harder objects are paid by bonus lines, as the rulebook already does.</p>
  <p><b>Bonus or discount</b>: parent + line together pay the rule price at the line's own D.</p>
  <p><b>Penalty</b> = a fixed share of the line it belongs to, per failure mode.</p>
  <p><b>Skill base</b> is calibrated from 2026: the median of price ÷ (1 + D / {RULE['d_scale']}) over the skill's lines. The league's level per skill is kept; only the spread inside a skill goes.</p>
  <p class="lead">Challenge totals are not rescaled: scaling a challenge would make the same skill pay differently again. Balance between challenges is set through the skill bases.</p>
</div></div>

<div class="cols">
  <div class="card"><h2>Skill bases</h2><div class="tw"><table>
    <thead><tr><th>Skill</th><th></th><th class="num">D0</th><th class="num">D2</th><th class="num">D5</th><th class="num">D8</th></tr></thead>
    <tbody>{base_rows}</tbody></table></div></div>
  <div class="card"><h2>Penalty shares</h2><div class="tw"><table>
    <thead><tr><th>Failure</th><th class="num">Share</th><th class="num">2026 prices</th><th>2026 values</th></tr></thead>
    <tbody>{share_rows}</tbody></table></div></div>
</div>

<nav>{"".join(f'<a href="#{s}">{esc(CH[s]["challenge"])}</a>' for s in CH)}</nav>
{"".join(sections)}
</div>
"""
with open(os.path.join(DIST, "pricing_2027.html"), "w") as fh:
    fh.write(PAGE)
print("wrote dist/pricing_2027.{json,csv,html}")
