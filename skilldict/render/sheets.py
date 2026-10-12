"""A challenge's score sheet, from a Build.

html(): an interactive referee sheet (tick boxes add up live; nothing stored).
tex():  a {scorelist} for the rulebook's own scoresheet macros
        (external/RuleBook/setup/macros_scoresheets.tex), so it drops into
        documents/scoresheets.tex in place of the hand-written file.

Both keep the rulebook's sections, so a referee fills the sheet in the order
the task runs, and both end with the score per taxonomy node, so the same
skill can be compared across challenges.
"""
import html as _html, os
from collections import OrderedDict
from .. import paths

MAX_BOXES = 24            # above this, the referee writes a count instead


def out_path(b, slug, ext):
    return os.path.join(paths.BUILD, "sheets", f"{slug}.{ext}")


def release_label(b):
    return f"Rulebook {b.rulebook_version}" if b.release.in_force else f"{b.release.year} PROPOSAL"


def node_max(b, slug):
    out = OrderedDict()
    for it in b.challenges[slug]["entries"]:
        e = b.skills[it["ref"]]
        p = e.get("points") or 0
        if p > 0:
            out[e["taxonomy"]] = out.get(e["taxonomy"], 0) + p * it.get("count", 1)
    return out


# ── HTML ─────────────────────────────────────────────────────────────────────
def esc(s):
    return _html.escape(str(s), quote=True)


def pretty(name, names):
    return names.get(name) or name.replace("_", " ")


def html(b, slug):
    D, ch, R = b.skills, b.challenges[slug], b.ratings
    nodes = b.vocab["taxonomy"]["nodes"]
    names = b.rater.names

    # Group lines by section; bonus/discount lines sit under their parent.
    sections, children = OrderedDict(), {}
    for it in ch["entries"]:
        e = D[it["ref"]]
        parent = it.get("related_skill")
        if parent and e["type"] in ("bonus", "penalty_behavior") and not e.get("failure_mode"):
            children.setdefault(parent, []).append(it)
        else:
            sections.setdefault(it.get("section") or "Main task", []).append(it)

    def row(it, child=False, parent_pts=None):
        e = D[it["ref"]]
        n = it.get("count", 1)
        pts = e.get("points")
        node = e["taxonomy"]
        r = (R.get(e["id"]) or {}).get("difficulty")
        objs = [pretty(o, names) for o in e.get("objects", [])]
        at = [pretty(a, names) for a in e.get("at", [])]
        cond_txt = "; ".join(f"{k.replace('_', ' ')}: {', '.join(v) if isinstance(v, list) else v}"
                             for k, v in e.get("conditions", {}).items())
        neg = pts is not None and pts < 0
        kind = "pen" if neg or e["type"] == "penalty_behavior" else ("bonus" if child else "item")

        meta = [f'<span class="id">{esc(e["id"])}</span>',
                f'<span class="node" title="{esc(nodes[node]["intent"].strip())}">{esc(node)}</span>']
        if objs:
            meta.append(f'<span class="objs">{esc(" · ".join(objs))}</span>')
        if at:
            meta.append(f'<span class="objs">at {esc(" · ".join(at))}</span>')
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
            price, maxv = '<span class="pts">referee</span>', ""
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
                f'data-node="{esc(node)}" data-area="{esc(node.split(".")[0])}">'
                f'<div class="boxes">{boxes}</div>'
                f'<div class="what"{title}><div class="desc">{esc(e["description"])}</div>'
                f'<div class="meta">{"".join(meta)}</div></div>'
                f'<div class="price">{price}</div>'
                f'<div class="max">{maxv}</div>'
                f'<output class="got">0</output></div>')

    body = []
    for sec, items in sections.items():
        body.append(f'<section><h2><span>{esc(sec)}</span><output class="sub">0</output></h2>')
        for it in items:
            body.append(row(it))
            for c in children.get(it["ref"], []):
                body.append(row(c, child=True, parent_pts=D[it["ref"]].get("points")))
        body.append("</section>")
    nm = node_max(b, slug)
    max_total = sum(nm.values())
    skills = "".join(
        f'<tr data-node="{esc(n)}"><th scope="row"><span class="node">{esc(n)}</span>'
        f'<span class="nname">{esc(nodes[n]["name"])}</span></th>'
        f'<td class="num">{m}</td><td class="num"><output>0</output></td>'
        f'<td class="bar"><span style="--w:0%"></span></td></tr>'
        for n, m in sorted(nm.items(), key=lambda x: -x[1]))
    rb = b.total(slug)
    check = "" if rb == max_total else f' <span class="warn">sheet maximum {rb}</span>'

    page = paths.template("sheet.html").format(
        title=esc(ch["challenge"]), challenge=esc(ch["challenge"]),
        section=esc(ch.get("rulebook_section", "")), minutes=esc(ch.get("max_time_minutes", "")),
        release=esc(release_label(b)), body="\n".join(body), skills=skills,
        max_total=max_total, check=check)
    path = out_path(b, slug, "html")
    paths.write_text(page, path)
    return path


# ── rulebook LaTeX ───────────────────────────────────────────────────────────
def tex_esc(s):
    s = str(s)
    for a, c in (("\\", r"\textbackslash{}"), ("&", r"\&"), ("%", r"\%"), ("$", r"\$"),
                 ("#", r"\#"), ("_", r"\_"), ("{", r"\{"), ("}", r"\}"), ("~", r"\textasciitilde{}"),
                 ("^", r"\^{}")):
        s = s.replace(a, c)
    return s


def tex(b, slug):
    """Same lines as the HTML sheet, written with the rulebook's macros. Each
    description carries its id; {scorelist} adds the Special Penalties &
    Bonuses itself."""
    D, ch = b.skills, b.challenges[slug]
    # Lines keep the challenge file's order, which follows the rulebook. A line
    # with related_skill in the same section as its parent is a modifier of
    # that parent (\scoremod / \scorepen); everything else is an item.
    entries = [it for it in ch["entries"] if D[it["ref"]]["type"] != "administrative"]
    section_of = {it["ref"]: it.get("section") for it in entries}

    def note(e):
        # Only the id, flush right on the item's own line if it fits, else on
        # the next line without stretching the description (TeXbook p.106).
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

    # the start-signal penalty only where the challenge lists it
    opts = [f"timelimit={ch.get('max_time_minutes', 5)}"]
    if "SPECIAL-02" not in {it["ref"] for it in ch["entries"]}:
        opts.insert(0, "startbutton=false")
    out = ["% GENERATED by `skilldict sheets` from the skill dictionary.",
           "% Do not edit; change data/ and regenerate.",
           # \small, as the rulebook already does for Restaurant: the ids and
           # the skill table must fit on the sheet's page.
           f"\\small\\begin{{scorelist}}[{','.join(opts)}]", ""]
    sec = object()
    for it in entries:
        if it.get("section") != sec:
            sec = it.get("section")
            out += ["", f"\t\\scoreheading{{{tex_esc(sec)}}}"] if sec else [""]
        out.append(line(it))
    out.append("")
    if ch.get("max_score"):                  # not every line is reachable in one run
        out.append(f"\t\\setTotalScore{{{ch['max_score']}}}")
    out += [r"\end{scorelist}", "",
            r"\vspace{0.2em}\noindent\begin{minipage}{\textwidth}\small",   # heading + table stay together
            r"\textbf{Score by skill} {\footnotesize (comparable across challenges; penalties count against their skill)}\\",
            r"\begin{tabularx}{\textwidth}{@{}X r c @{\hspace{2em}} X r c@{}}",
            r"\textbf{Skill} & \textbf{Max} & \textbf{Scored} & \textbf{Skill} & \textbf{Max} & \textbf{Scored}\\\hline"]
    cells = [f"\\texttt{{{tex_esc(n)}}} & \\textit{{{m}}} & \\scoreline[0.1]"
             for n, m in sorted(node_max(b, slug).items(), key=lambda x: -x[1])]
    if len(cells) % 2:
        cells.append("& &")
    half = len(cells) // 2                       # read down the left column first
    out += [f"{x} & {y}\\\\" for x, y in zip(cells[:half], cells[half:])]
    out += [r"\end{tabularx}", r"\end{minipage}", ""]
    path = out_path(b, slug, "tex")
    paths.write_text("\n".join(out), path)
    return path


def all_sheets(b):
    return [p for slug in b.challenges for p in (html(b, slug), tex(b, slug))]
