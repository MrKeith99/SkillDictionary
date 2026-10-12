"""The repricing review: JSON (dist), CSV and an HTML page for the TC (build)."""
import csv, html, os
from .. import paths
from ..pricing import Repricing


def esc(s):
    return html.escape("" if s is None else str(s))


def fmt(v):
    return "—" if v is None else f"{v:+d}" if isinstance(v, int) and v < 0 else str(v)


def write(base, rule):
    """Reprice `base` with `rule`; returns (Repricing, written paths)."""
    rp = Repricing(base, rule)
    y0, y1 = base.season.year, rule.year
    out_json = os.path.join(paths.DIST, str(y1), "pricing.json")
    out_csv = os.path.join(paths.BUILD, str(y1), "pricing.csv")
    out_html = os.path.join(paths.BUILD, str(y1), "pricing.html")
    paths.write_json(rp.as_json(), out_json, indent=1)
    lines = rp.lines()
    os.makedirs(os.path.dirname(out_csv), exist_ok=True)
    with open(out_csv, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(lines[0]))
        w.writeheader()
        w.writerows(lines)

    CH, nodes = base.challenges, base.vocab["taxonomy"]["nodes"]
    sections = []
    for slug, ch in CH.items():
        trs = []
        for r in (x for x in rp.rows if x["challenge"] == slug):
            d = r["delta"]
            cls = "" if not d else ("up" if d > 0 else "down")
            kept_cls = " kept" if r["rule"].startswith("kept") else ""
            trs.append(
                f'<tr class="{r["type"]}{kept_cls}"><td><span class="id">{esc(r["id"])}</span>'
                f'<span class="desc">{esc(r["description"])}</span></td>'
                f'<td class="node">{esc(r["node"])}</td><td class="num">{esc(r["D"])}</td>'
                f'<td class="num">{esc(r["count"])}×</td>'
                f'<td class="num">{fmt(r["points_old"])}</td><td class="num strong">{fmt(r["points_new"])}</td>'
                f'<td class="num {cls}">{"" if not d else f"{d:+d}"}</td><td class="why">{esc(r["rule"])}</td></tr>')
        o, n = rp.tot_old[slug], rp.tot_new[slug]
        sections.append(
            f'<section id="{slug}"><h2>{esc(ch["challenge"])}<span class="tot">max {o} → '
            f'<b>{n}</b> ({n - o:+d})</span></h2>'
            f'<div class="tw"><table><thead><tr><th>Line</th><th>Skill</th><th class="num">D</th>'
            f'<th class="num">×</th><th class="num">{y0}</th><th class="num">{y1}</th><th class="num">Δ</th>'
            f'<th>How</th></tr></thead><tbody>{"".join(trs)}</tbody></table></div></section>')
    base_rows = "".join(
        f'<tr><td class="node">{esc(n)}</td><td>{esc(nodes[n]["name"])}</td><td class="num">{v:.0f}</td>'
        f'<td class="num">{rule.rnd(v * rule.weight(2))}</td><td class="num">{rule.rnd(v * rule.weight(5))}</td>'
        f'<td class="num">{rule.rnd(v * rule.weight(8))}</td></tr>'
        for n, v in sorted(rp.base.items(), key=lambda x: -x[1]))
    share_rows = "".join(
        f'<tr><td>{esc(m.replace("_", " "))}</td><td class="num">{s:.0%}</td>'
        f'<td class="num">{len(rp.pen_old.get(m, []))}</td>'
        f'<td>{esc(", ".join(str(p) for p in sorted(rp.pen_old.get(m, []))))}</td></tr>'
        for m, s in rule.penalty_share.items())
    so, sn = sum(rp.tot_old.values()), sum(rp.tot_new.values())
    page = paths.template("pricing.html").format(
        year=y1, base_year=y0, d_scale=rule.d_scale,
        inv_old=len(rp.inv_old), inv_new=len(rp.inv_new),
        pen_mixed=sum(1 for v in rp.pen_old.values() if len(v) > 1),
        sum_old=so, sum_new=sn, sum_delta=f"{sn - so:+d}", kept=len(rp.kept),
        base_rows=base_rows, share_rows=share_rows,
        nav="".join(f'<a href="#{s}">{esc(CH[s]["challenge"])}</a>' for s in CH),
        sections="".join(sections))
    paths.write_text(page, out_html)
    return rp, [out_json, out_csv, out_html]
