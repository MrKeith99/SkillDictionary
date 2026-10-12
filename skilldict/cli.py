"""skilldict — one command line for the whole pipeline.

  check   [YEAR ...]   build every season, run all checks, write dist/  (the CI gate)
  findings [YEAR]      the TC findings report for a season (default: in force)
  sheets  [YEAR] [-c SLUG ...]   score sheets, HTML + rulebook LaTeX -> build/<year>/sheets/
  prices  [YEAR]       reprice the base season with YEAR's pricing rule -> build/<year>/pricing.*
  pdf     [YEAR]       official vs generated sheets, one PDF -> build/<year>/
  seasons              list the seasons

YEAR defaults to every season for `check`, and to the newest season with the
relevant data otherwise.
"""
import argparse, sys
from . import model, paths
from .checks import RULE, schema, integrity, rulebook, findings
from .model import DataError
from .pricing import rule_of
from .render import sheets as r_sheets, pricing as r_pricing, viz as r_viz, pdf as r_pdf


def _errors(b):
    if b.errors:
        print(RULE)
        print(f"DATA ERRORS — {b.season}")
        for m in b.errors:
            print("  " + m)
        print(f"  -> {len(b.errors)} errors")
    return len(b.errors)


def check_season(year, verbose):
    b = model.load(year)
    print(RULE)
    print(f"SEASON {b.season.year} — {b.season.status}, {len(b.skills)} lines, "
          f"{len(b.challenges)} challenges ({', '.join(b.challenges)})")
    for line in b.reports:
        print(line)
    fail = _errors(b)
    if fail:
        return fail
    fail += integrity.run(b)
    if fail:
        return fail
    fail += schema.run(b)
    if b.season.in_force:
        fail += rulebook.run(b)
        if verbose:
            findings.run(b)
    out = b.write_dist()
    r_viz.write(b)
    rule = rule_of(b.season)
    if rule and b.base is not None:
        rp, _ = r_pricing.write(b.base, rule)
        print(RULE)
        print(f"PRICING {rule.year} on {b.base.season.year}: inversions {len(rp.inv_old)} -> {len(rp.inv_new)}, "
              f"{len(rp.kept)} lines kept at the rulebook value")
    print(f"  wrote {paths.rel(out)}/")
    return fail


def cmd_check(a):
    years = a.years or model.seasons()
    fail = 0
    for y in years:
        fail += check_season(y, verbose=not a.quiet)
    print(RULE)
    print("ALL CHECKS PASSED" if not fail else f"CHECKS FAILED ({fail})")
    return 1 if fail else 0


def cmd_findings(a):
    b = model.load(a.year)
    if _errors(b):
        return 1
    findings.run(b)
    return 0


def cmd_sheets(a):
    b = model.load(a.year)
    if _errors(b):
        return 1
    for slug in a.challenge or b.challenges:
        if slug not in b.challenges:
            sys.exit(f"no challenge {slug} in {b.season}; have {', '.join(b.challenges)}")
        for p in (r_sheets.html(b, slug), r_sheets.tex(b, slug)):
            print(f"wrote {paths.rel(p)}")
    return 0


def cmd_prices(a):
    years = [a.year] if a.year else [y for y in model.seasons() if model.Season(y).pricing()]
    if not years:
        sys.exit("no season has a pricing.yaml")
    season = model.Season(years[-1])
    rule = rule_of(season)
    if rule is None:
        sys.exit(f"{season} has no pricing.yaml")
    base = model.load(season.base if season.base is not None else season.year)
    rp, written = r_pricing.write(base, rule)
    print(RULE)
    print(f"PROPOSED {rule.year} PRICES on season {base.season.year} — proposal, data unchanged")
    print(f"  price inversions within a skill: {len(rp.inv_old)} -> {len(rp.inv_new)}")
    for node, x, y in rp.inv_new:
        print(f"    still: {x[4]} D{x[1]}-{x[2]} = {x[3]}  <  {y[4]} D{y[1]}-{y[2]} = {y[3]}")
    print("  challenge max (positive lines):")
    for s in base.challenges:
        print(f"    {s:16s} {rp.tot_old[s]:6d} -> {rp.tot_new[s]:6d}  ({rp.tot_new[s] - rp.tot_old[s]:+d})")
    print(f"  lines the rule cannot price ({len(rp.kept)}): kept at rulebook value")
    for i, why in rp.kept:
        print(f"    {i:28s} {why}")
    for r in rp.rows:
        if "CONFLICT" in r["rule"]:
            print(f"  CONFLICT {r['id']}: {r['rule']}")
    for p in written:
        print(f"wrote {paths.rel(p)}")
    return 0


def cmd_pdf(a):
    b = model.load(a.year if a.year else model.seasons()[-1])
    if _errors(b):
        return 1
    print(f"wrote {paths.rel(r_pdf.write(b))}")
    return 0


def cmd_seasons(a):
    cur = model.current()
    for y in model.seasons():
        s = model.Season(y)
        extra = f"base {s.base}" if s.base is not None else f"rulebook {s.rulebook.get('version')}"
        print(f"{y}  {s.status:9s} {extra}{'  (dist/)' if y == cur else f'  (dist/{y}/)'}")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="skilldict", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="build every season, run all checks, write dist/")
    c.add_argument("years", nargs="*", type=int)
    c.add_argument("-q", "--quiet", action="store_true", help="skip the findings report")
    c.set_defaults(fn=cmd_check)
    for name, fn, hlp in (("findings", cmd_findings, "TC findings report"),
                          ("sheets", cmd_sheets, "score sheets (HTML + LaTeX)"),
                          ("prices", cmd_prices, "reprice with a season's pricing rule"),
                          ("pdf", cmd_pdf, "official vs generated sheets, one PDF")):
        c = sub.add_parser(name, help=hlp)
        c.add_argument("year", nargs="?", type=int)
        if name == "sheets":
            c.add_argument("-c", "--challenge", action="append", help="only this challenge (repeatable)")
        c.set_defaults(fn=fn)
    sub.add_parser("seasons", help="list the seasons").set_defaults(fn=cmd_seasons)
    a = p.parse_args(argv)
    if getattr(a, "year", None) is None and a.cmd in ("findings",):
        a.year = model.current()
    if getattr(a, "year", None) is None and a.cmd == "sheets":
        a.year = model.seasons()[-1]
    try:
        return a.fn(a)
    except DataError as e:
        print(f"DATA ERROR: {e}", file=sys.stderr)
        return 1
