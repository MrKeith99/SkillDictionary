#!/usr/bin/env python3
"""Render a challenge's score sheet from the dictionary.

Usage: build_scoresheet.py <challenge-slug> [--tex]   (e.g. pick_and_place)
Reads : dist/dictionary.json, dist/challenges.json, dist/vocabulary.json,
        dist/skill_ratings.json  (run build_dist.py and check_taxonomy.py first)
Writes: dist/scoresheets/<slug>.html, or with --tex dist/scoresheets/<slug>.tex:
        a {scorelist} for the rulebook's own scoresheet macros
        (external/RuleBook/setup/macros_scoresheets.tex), so it drops into
        documents/scoresheets.tex in place of the hand-written file.

The sheet keeps the rulebook's sections, so a referee fills it in the order the
task runs. Every line also carries what the dictionary knows about it — id,
taxonomy node, objects, intrinsic difficulty — and the footer totals the score
per taxonomy node, so the same skill can be compared across challenges.
Tick boxes add up live; nothing is stored.
"""
import html, json, os, sys
from collections import OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DIST = os.environ.get("SKILLDICT_DIST", os.path.join(ROOT, "dist"))

MAX_BOXES = 24            # above this, the referee writes a count instead


def load(name):
    return json.load(open(os.path.join(DIST, name)))


def esc(s):
    return html.escape(str(s), quote=True)


def pretty(name, catalog, fixtures):
    if name in catalog:
        return catalog[name]["name"]
    if name in fixtures:
        return fixtures[name]["name"]
    return name.replace("_", " ")


def main(slug):
    D = {e["id"]: e for e in load("dictionary.json")["skills"]}
    chs = load("challenges.json")
    ch = chs["challenges"][slug]
    V = load("vocabulary.json")
    R = load("skill_ratings.json")
    nodes = V["taxonomy"]["nodes"]
    catalog, fixtures = V["objects"]["catalog"], V["objects"]["fixtures"]

    # Group lines by section; bonus/discount lines sit under their parent.
    sections = OrderedDict()
    children = {}
    for it in ch["entries"]:
        e = D[it["ref"]]
        parent = it.get("related_skill")
        is_child = parent and e["type"] in ("bonus", "penalty_behavior") and not e.get("failure_mode")
        if is_child:
            children.setdefault(parent, []).append(it)
        else:
            sections.setdefault(it.get("section") or "Main task", []).append(it)

    def row(it, child=False, parent_pts=None):
        e = D[it["ref"]]
        n = it.get("count", 1)
        pts = e.get("points")
        node = e["taxonomy"]
        area = node.split(".")[0]
        r = (R.get(e["id"]) or {}).get("difficulty")
        objs = [pretty(o, catalog, fixtures) for o in e.get("objects", [])]
        cond = e.get("conditions", {})
        cond_txt = "; ".join(f"{k.replace('_', ' ')}: {', '.join(v) if isinstance(v, list) else v}"
                             for k, v in cond.items())
        neg = pts is not None and pts < 0
        kind = "pen" if neg or e["type"] == "penalty_behavior" else ("bonus" if child else "item")

        meta = [f'<span class="id">{esc(e["id"])}</span>',
                f'<span class="node" title="{esc(nodes[node]["intent"].strip())}">{esc(node)}</span>']
        if objs:
            meta.append(f'<span class="objs">{esc(" · ".join(objs))}</span>')
        if e.get("failure_mode"):
            meta.append(f'<span class="fm">{esc(e["failure_mode"].replace("_", " "))}</span>')
        if r:
            d = f'{r["min"]}' if r["min"] == r["max"] else f'{r["min"]}–{r["max"]}'
            meta.append(f'<span class="d t{r["tier"]}" title="intrinsic difficulty D (tier {r["tier"]}); '
                        f'empirical level {esc(e["level"])}">D {d}</span>')
        if e.get("level") in ("E", "C", "X"):
            meta.append(f'<span class="lvl" title="empirical level">level {esc(e["level"])}</span>')

        if pts is None:
            boxes = f'<input class="free" id="in-{esc(e["id"])}" type="number" inputmode="numeric" ' \
                    f'aria-label="points for {esc(e["description"])}" placeholder="pts">'
            price = '<span class="pts">referee</span>'
            maxv = ""
        else:
            if n <= MAX_BOXES:
                boxes = "".join(f'<input type="checkbox" aria-label="{esc(e["description"])} #{i + 1}" '
                                f'id="cb-{esc(e["id"])}-{i}">' for i in range(n))
            else:
                boxes = f'<input class="cnt" type="number" min="0" max="{n}" id="in-{esc(e["id"])}">'
            sign = "" if neg else "+" if child else ""
            price = f'<span class="pts">{sign}{pts}</span>'
            if child and parent_pts is not None and not neg:
                price += f'<span class="eff" title="parent + bonus">= {parent_pts + pts}</span>'
            price += f'<span class="times">× {n}</span>' if n > 1 else ""
            maxv = f'{pts * n:+d}' if neg else f'{pts * n}'

        title = f' title="{esc(cond_txt)}"' if cond_txt else ""
        return (f'<div class="row {kind}{" child" if child else ""}" data-pts="{pts if pts is not None else ""}" '
                f'data-node="{esc(node)}" data-area="{esc(area)}">'
                f'<div class="boxes">{boxes}</div>'
                f'<div class="what"{title}><div class="desc">{esc(e["description"])}</div>'
                f'<div class="meta">{"".join(meta)}</div></div>'
                f'<div class="price">{price}</div>'
                f'<div class="max">{maxv}</div>'
                f'<output class="got">0</output></div>')

    body, max_total = [], 0
    node_max = OrderedDict()
    for sec, items in sections.items():
        body.append(f'<section><h2><span>{esc(sec)}</span><output class="sub">0</output></h2>')
        for it in items:
            e = D[it["ref"]]
            body.append(row(it))
            for c in children.get(e["id"], []):
                body.append(row(c, child=True, parent_pts=e.get("points")))
        body.append("</section>")
    for it in ch["entries"]:
        e = D[it["ref"]]
        p = e.get("points") or 0
        if p > 0:
            max_total += p * it.get("count", 1)
            node_max[e["taxonomy"]] = node_max.get(e["taxonomy"], 0) + p * it.get("count", 1)

    skills = "".join(
        f'<tr data-node="{esc(n)}"><th scope="row"><span class="node">{esc(n)}</span>'
        f'<span class="nname">{esc(nodes[n]["name"])}</span></th>'
        f'<td class="num">{m}</td><td class="num"><output>0</output></td>'
        f'<td class="bar"><span style="--w:0%"></span></td></tr>'
        for n, m in sorted(node_max.items(), key=lambda x: -x[1]))

    rb = ch.get("total_score")
    check = "" if rb in (None, max_total) else \
        f' <span class="warn">rulebook says {rb}</span>'
    meta = load("dictionary.json")

    page = TEMPLATE.format(
        title=esc(ch["challenge"]),
        challenge=esc(ch["challenge"]),
        section=esc(ch.get("rulebook_section", "")),
        minutes=esc(ch.get("max_time_minutes", "")),
        rbv=esc(meta["rulebook_version"]),
        body="\n".join(body),
        skills=skills,
        max_total=max_total,
        check=check,
    )
    out = os.path.join(DIST, "scoresheets")
    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, f"{slug}.html")
    open(path, "w").write(page)
    print(f"wrote {os.path.relpath(path, ROOT)}  (max {max_total})")


TEMPLATE = """<title>{title} Score Sheet</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@500;700&family=Source+Sans+3:wght@400;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
/* Layout: a referee's clipboard sheet — rulebook sections top to bottom, one
   ruled row per line, tick boxes left, points right; skill totals at the end. */
:root {{
  --paper: #f6f8f7; --sheet: #ffffff; --ink: #17212b; --muted: #5d6b76;
  --rule: #d9e0e3; --accent: #0f6b5c; --bonus: #0f6b5c; --pen: #b3261e;
  --tE: #2f7d4f; --tC: #a86a00; --tX: #9b2f5a; --chip: #eef2f2; --warn: #a86a00;
  --display: "Barlow Condensed", "Arial Narrow", sans-serif;
  --body: "Source Sans 3", "Segoe UI", system-ui, sans-serif;
  --mono: "IBM Plex Mono", ui-monospace, monospace;
}}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{
  --paper: #0f1416; --sheet: #161d20; --ink: #e4eaec; --muted: #94a3ab;
  --rule: #2a3438; --accent: #4fc2a8; --bonus: #4fc2a8; --pen: #ff8a80;
  --tE: #74c995; --tC: #e7b450; --tX: #e486ad; --chip: #20292d; --warn: #e7b450; color-scheme: dark; }} }}
:root[data-theme="dark"] {{
  --paper: #0f1416; --sheet: #161d20; --ink: #e4eaec; --muted: #94a3ab;
  --rule: #2a3438; --accent: #4fc2a8; --bonus: #4fc2a8; --pen: #ff8a80;
  --tE: #74c995; --tC: #e7b450; --tX: #e486ad; --chip: #20292d; --warn: #e7b450; color-scheme: dark; }}

body {{ background: var(--paper); color: var(--ink); font: 15px/1.4 var(--body); }}
.sheet {{ max-width: 980px; margin: 0 auto; padding-block: 24px 48px; padding-inline: 16px; display: grid; gap: 20px; }}
header {{ display: grid; gap: 12px; }}
.eyebrow {{ font: 500 13px var(--mono); color: var(--muted); letter-spacing: .04em; }}
h1 {{ font: 700 clamp(30px, 6vw, 44px)/1 var(--display); letter-spacing: .01em; text-wrap: balance; margin: 0; text-transform: uppercase; }}
.fields {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 8px 16px; }}
.fields label {{ display: grid; gap: 2px; font-size: 12px; color: var(--muted); text-transform: uppercase; letter-spacing: .06em; }}
.fields input {{ font: 15px var(--body); color: var(--ink); background: transparent; border: 0; border-bottom: 1px solid var(--ink); padding: 4px 0; min-width: 0; }}
.legend {{ display: flex; flex-wrap: wrap; gap: 6px 14px; font-size: 13px; color: var(--muted); align-items: center; }}

section {{ background: var(--sheet); border: 1px solid var(--rule); }}
h2 {{ margin: 0; display: flex; justify-content: space-between; align-items: baseline; gap: 12px;
      font: 700 20px var(--display); text-transform: uppercase; letter-spacing: .05em;
      padding: 8px 12px; border-bottom: 2px solid var(--ink); }}
h2 .sub {{ font: 500 16px var(--mono); }}

.row {{ display: grid; grid-template-columns: minmax(96px, 248px) minmax(0, 1fr) auto 64px 64px;
        gap: 4px 14px; align-items: center; padding: 8px 12px; border-top: 1px solid var(--rule); }}
.row:first-of-type {{ border-top: 0; }}
.row.child {{ padding-left: 36px; background: color-mix(in srgb, var(--chip) 55%, transparent); }}
.boxes {{ display: flex; flex-wrap: wrap; gap: 4px; }}
.boxes input[type=checkbox] {{ appearance: none; width: 16px; height: 16px; margin: 0; border: 1.5px solid var(--ink); background: var(--sheet); cursor: pointer; }}
.boxes input[type=checkbox]:checked {{ background: var(--ink); box-shadow: inset 0 0 0 2px var(--sheet); }}
.row.pen .boxes input[type=checkbox]:checked {{ background: var(--pen); border-color: var(--pen); }}
.boxes input:focus-visible, .fields input:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 2px; }}
.boxes input[type=number] {{ width: 72px; font: 15px var(--mono); color: var(--ink); background: var(--sheet); border: 1.5px solid var(--ink); padding: 2px 6px; }}
.desc {{ font-weight: 600; }}
.child .desc::before {{ content: "+ "; color: var(--bonus); }}
.child.pen .desc::before {{ content: "− "; color: var(--pen); }}
.meta {{ display: flex; flex-wrap: wrap; gap: 4px 8px; margin-top: 3px; font-size: 12.5px; color: var(--muted); }}
.meta .id {{ font: 12px var(--mono); }}
.meta .node {{ font: 500 12px var(--mono); color: var(--accent); }}
.meta .fm {{ color: var(--pen); }}
.meta .d {{ font: 500 12px var(--mono); padding: 0 5px; border: 1px solid currentColor; }}
.tE {{ color: var(--tE); }} .tC {{ color: var(--tC); }} .tX {{ color: var(--tX); }}
.price {{ display: flex; gap: 6px; align-items: baseline; font: 500 15px var(--mono); justify-content: flex-end; white-space: nowrap; }}
.price .eff, .price .times {{ font-size: 12.5px; color: var(--muted); }}
.bonus .pts {{ color: var(--bonus); }} .pen .pts {{ color: var(--pen); }}
.max {{ text-align: right; font: 13px var(--mono); color: var(--muted); font-variant-numeric: tabular-nums; }}
.got {{ text-align: right; font: 500 16px var(--mono); font-variant-numeric: tabular-nums; }}
.pen .got:not(:empty) {{ color: var(--pen); }}
.colhead {{ display: grid; grid-template-columns: minmax(96px, 248px) minmax(0, 1fr) auto 64px 64px; gap: 14px;
            padding: 0 12px; font-size: 11.5px; text-transform: uppercase; letter-spacing: .08em; color: var(--muted); }}
.colhead span:nth-child(n+3) {{ text-align: right; }}

.total {{ display: flex; flex-wrap: wrap; justify-content: space-between; align-items: baseline; gap: 8px 24px;
          border: 2px solid var(--ink); background: var(--sheet); padding: 12px 16px; }}
.total .big {{ font: 700 40px/1 var(--display); font-variant-numeric: tabular-nums; }}
.total .of {{ font: 14px var(--mono); color: var(--muted); }}
.warn {{ color: var(--warn); }}

.skills {{ background: var(--sheet); border: 1px solid var(--rule); }}
.skills p {{ margin: 0; padding: 10px 12px 0; color: var(--muted); font-size: 13.5px; max-width: 70ch; }}
.tablewrap {{ overflow-x: auto; }}
table {{ border-collapse: collapse; width: 100%; font-size: 14px; }}
th, td {{ padding: 6px 12px; border-top: 1px solid var(--rule); text-align: left; }}
thead th {{ font-size: 11.5px; text-transform: uppercase; letter-spacing: .08em; color: var(--muted); font-weight: 400; border-top: 0; }}
th .node {{ font: 500 12.5px var(--mono); color: var(--accent); margin-right: 8px; }}
th .nname {{ color: var(--muted); font-weight: 400; }}
td.num {{ text-align: right; font: 14px var(--mono); font-variant-numeric: tabular-nums; }}
td.bar {{ width: 30%; min-width: 80px; }}
td.bar span {{ display: block; height: 8px; width: var(--w); background: var(--accent); }}

@media (max-width: 640px) {{
  .row, .colhead {{ grid-template-columns: minmax(0, 1fr) auto 52px; }}
  .colhead span:nth-child(1), .colhead span:nth-child(4) {{ display: none; }}
  .row .boxes {{ grid-column: 1 / -1; order: 2; }}
  .row .what {{ grid-column: 1; order: 0; }}
  .row .price {{ order: 1; }}
  .row .max {{ display: none; }}
  .row .got {{ order: 1; }}
}}
</style>

<div class="sheet">
<header>
  <div class="eyebrow">RoboCup@Home · Rulebook {rbv} · §{section} · {minutes} min · DRAFT FORMAT</div>
  <h1>{challenge}</h1>
  <div class="fields">
    <label for="f-team">Team<input id="f-team" type="text"></label>
    <label for="f-round">Round / attempt<input id="f-round" type="text"></label>
    <label for="f-ref">Referee<input id="f-ref" type="text"></label>
    <label for="f-time">Time used<input id="f-time" type="text" placeholder="mm:ss"></label>
  </div>
  <div class="legend">
    <span class="meta"><span class="node">MAN.Pick</span></span><span>skill node — hover for its purpose</span>
    <span>D = intrinsic difficulty from objects and setup:</span>
    <span class="meta"><span class="d tE">E ≤ 2</span><span class="d tC">C ≤ 5</span><span class="d tX">X &gt; 5</span></span>
    <span>“= 150” is the effective price of parent + bonus</span>
  </div>
</header>

<div class="colhead"><span>Tally</span><span>Line</span><span>Points</span><span>Max</span><span>Score</span></div>
{body}

<div class="total" aria-live="polite">
  <div><div class="eyebrow">TOTAL</div><output class="big" id="total">0</output></div>
  <div class="of">max {max_total}{check}</div>
</div>

<div class="skills">
  <h2><span>Score by skill</span></h2>
  <p>The same skill scores the same way in every challenge. These rows are what the league compares across challenges and years; penalties count against the skill they belong to.</p>
  <div class="tablewrap"><table>
    <thead><tr><th>Skill</th><th style="text-align:right">Max</th><th style="text-align:right">Scored</th><th>Share</th></tr></thead>
    <tbody>{skills}</tbody>
  </table></div>
</div>
</div>

<script>
(function () {{
  const rows = [...document.querySelectorAll('.row')];
  function lineScore(r) {{
    const p = r.dataset.pts;
    const free = r.querySelector('input.free');
    if (free) return Number(free.value) || 0;
    const cnt = r.querySelector('input.cnt');
    const n = cnt ? Math.max(0, Number(cnt.value) || 0)
                  : r.querySelectorAll('input[type=checkbox]:checked').length;
    return n * Number(p || 0);
  }}
  function update() {{
    let total = 0;
    const byNode = {{}};
    document.querySelectorAll('section').forEach(sec => {{
      let sub = 0;
      sec.querySelectorAll('.row').forEach(r => {{
        const s = lineScore(r);
        r.querySelector('.got').textContent = s ? s : '';
        sub += s;
        byNode[r.dataset.node] = (byNode[r.dataset.node] || 0) + s;
      }});
      const o = sec.querySelector('h2 .sub');
      if (o) o.textContent = sub;
      total += sub;
    }});
    document.getElementById('total').textContent = total;
    document.querySelectorAll('.skills tbody tr').forEach(tr => {{
      const got = byNode[tr.dataset.node] || 0;
      const max = Number(tr.children[1].textContent) || 1;
      tr.querySelector('output').textContent = got;
      tr.querySelector('.bar span').style.setProperty('--w', Math.max(0, Math.min(100, 100 * got / max)) + '%');
    }});
  }}
  document.addEventListener('input', update);
  update();
}})();
</script>
"""

def tex_esc(s):
    s = str(s)
    for a, b in (("\\", r"\textbackslash{}"), ("&", r"\&"), ("%", r"\%"), ("$", r"\$"),
                 ("#", r"\#"), ("_", r"\_"), ("{", r"\{"), ("}", r"\}"), ("~", r"\textasciitilde{}"),
                 ("^", r"\^{}")):
        s = s.replace(a, b)
    return s


def main_tex(slug):
    """Same lines as the HTML sheet, written with the rulebook's macros.

    Each description carries its dictionary id; the sheet ends with a
    per-skill tally for comparing challenges. Special Penalties & Bonuses are added by {scorelist} itself."""
    D = {e["id"]: e for e in load("dictionary.json")["skills"]}
    ch = load("challenges.json")["challenges"][slug]
    V = load("vocabulary.json")
    R = load("skill_ratings.json")
    nodes = V["taxonomy"]["nodes"]
    catalog, fixtures = V["objects"]["catalog"], V["objects"]["fixtures"]

    # Lines keep the challenge file's order, which follows the rulebook. A
    # line with related_skill in the same section as its parent is a modifier
    # of that parent (\scoremod / \scorepen); everything else is an item.
    entries = [it for it in ch["entries"] if D[it["ref"]]["type"] != "administrative"]
    section_of = {it["ref"]: it.get("section") for it in entries}

    def note(e):
        # Only the id, right-aligned on the item's own line: enough to look the
        # line up, short enough that the sheet keeps the rulebook's layout. The
        # skill node is in the per-skill table; D belongs in analysis, not here.
        # TeXbook p.106: flush right on the same line if it fits; otherwise on
        # the next line, without stretching the description above it.
        return (r"\unskip\nobreak\hfil\penalty50\hskip0.4em\hbox{}\nobreak\hfill"
                r"\mbox{\tiny\color[gray]{0.4}\texttt{" + tex_esc(e["id"]) + r"}}\hspace{0.6em}")

    def line(it):
        e = D[it["ref"]]
        n, pts = it.get("count", 1), e.get("points") or 0
        mult = f"[{n}]" if n > 1 else ""
        desc = tex_esc(e["description"]) + note(e)
        parent = it.get("related_skill")
        if e.get("points") is None:              # judged on the day, e.g. a percentage
            return f"\t\\scoreitem{{0}}{{{desc}}}"
        if parent and section_of.get(parent) == it.get("section"):
            macro = r"\scorepen" if pts < 0 else r"\scoremod"
            return f"\t\t{macro}{mult}{{{pts}}}{{{desc}}}"
        if e["type"] == "penalty_behavior":
            return f"\t\\penaltyitem{mult}{{{abs(pts)}}}{{{desc}}}"
        return f"\t\\scoreitem{mult}{{{pts}}}{{{desc}}}"

    # {scorelist} adds the Special Penalties & Bonuses itself; the start-signal
    # penalty only where the challenge lists it.
    opts = [f"timelimit={ch.get('max_time_minutes', 5)}"]
    if "SPECIAL-02" not in {it["ref"] for it in ch["entries"]}:
        opts.insert(0, "startbutton=false")

    out = [f"% GENERATED by tools/build_scoresheet.py {slug} --tex from the skill dictionary.",
           "% Do not edit; change dictionary/ or challenges/ and regenerate.",
           # \small, as the rulebook already does for Restaurant: the ids and
           # the skill table must fit on the sheet's single page.
           f"\\small\\begin{{scorelist}}[{','.join(opts)}]", ""]
    node_max = OrderedDict()
    sec = object()
    for it in entries:
        if it.get("section") != sec:
            sec = it.get("section")
            out += ["", f"\t\\scoreheading{{{tex_esc(sec)}}}"] if sec else [""]
        out.append(line(it))
    out.append("")
    for it in ch["entries"]:
        e = D[it["ref"]]
        p = e.get("points") or 0
        if p > 0:
            node_max[e["taxonomy"]] = node_max.get(e["taxonomy"], 0) + p * it.get("count", 1)
    if ch.get("max_score"):                  # a proposal whose lines are not all reachable at once
        out.append(f"\t\\setTotalScore{{{ch['max_score']}}}")
    out += [r"\end{scorelist}", "",
            r"\vspace{0.2em}\noindent\begin{minipage}{\textwidth}\small",   # heading + table stay together
            r"\textbf{Score by skill} {\footnotesize (comparable across challenges; penalties count against their skill)}\\",
            r"\begin{tabularx}{\textwidth}{@{}X r c @{\hspace{2em}} X r c@{}}",
            r"\textbf{Skill} & \textbf{Max} & \textbf{Scored} & \textbf{Skill} & \textbf{Max} & \textbf{Scored}\\\hline"]
    cells = [f"\\texttt{{{tex_esc(n)}}} & \\textit{{{m}}} & \\scoreline[0.1]"
             for n, m in sorted(node_max.items(), key=lambda x: -x[1])]
    if len(cells) % 2:
        cells.append("& &")
    half = len(cells) // 2                       # read down the left column first
    out += [f"{a} & {b}\\\\" for a, b in zip(cells[:half], cells[half:])]
    out += [r"\end{tabularx}", r"\end{minipage}", ""]
    path = os.path.join(DIST, "scoresheets", f"{slug}.tex")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w").write("\n".join(out))
    print(f"wrote {os.path.relpath(path, ROOT)}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 1:
        sys.exit(__doc__)
    (main_tex if "--tex" in sys.argv else main)(args[0])
