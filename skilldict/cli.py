"""skilldict — one command line for the whole pipeline.

  check      build, run all checks, write dist/  (the CI gate)
  findings   the TC findings report
  sheets     score sheets, HTML + rulebook LaTeX -> build/sheets/   (-c SLUG for one)
  pdf        rulebook sheet next to generated, per challenge -> build/*.pdf

The tree describes one release (data/release.yaml); earlier ones are git tags.
"""
import argparse, sys
from . import model, paths
from .checks import RULE, schema, integrity, rulebook, findings
from .model import DataError
from .render import sheets as r_sheets, viz as r_viz, pdf as r_pdf


def _load():
    b = model.load()
    if b.errors:
        print(RULE)
        print("DATA ERRORS")
        for m in b.errors:
            print("  " + m)
        print(f"  -> {len(b.errors)} errors")
        sys.exit(1)
    return b


def cmd_check(a):
    b = _load()
    print(RULE)
    print(f"RELEASE {b.release} — {len(b.skills)} lines, {len(b.challenges)} challenges "
          f"({', '.join(b.challenges)})")
    fail = integrity.run(b)
    if not fail:
        fail += schema.run(b)
        fail += rulebook.run(b)
        print(RULE)
        print("\n".join(b.reports))
        if not a.quiet:
            findings.run(b)
        b.write_dist()
        r_viz.write(b)
        print(f"  wrote {paths.rel(paths.DIST)}/")
    print(RULE)
    print("ALL CHECKS PASSED" if not fail else f"CHECKS FAILED ({fail})")
    return 1 if fail else 0


def cmd_findings(a):
    findings.run(_load())
    return 0


def cmd_sheets(a):
    b = _load()
    for slug in a.challenge or b.challenges:
        if slug not in b.challenges:
            sys.exit(f"no challenge {slug}; have {', '.join(b.challenges)}")
        for p in (r_sheets.html(b, slug), r_sheets.tex(b, slug)):
            print(f"wrote {paths.rel(p)}")
    return 0


def cmd_pdf(a):
    print(f"wrote {paths.rel(r_pdf.write(_load()))}")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="skilldict", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="build, run all checks, write dist/")
    c.add_argument("-q", "--quiet", action="store_true", help="skip the findings report")
    c.set_defaults(fn=cmd_check)
    sub.add_parser("findings", help="TC findings report").set_defaults(fn=cmd_findings)
    c = sub.add_parser("sheets", help="score sheets (HTML + LaTeX)")
    c.add_argument("-c", "--challenge", action="append", help="only this challenge (repeatable)")
    c.set_defaults(fn=cmd_sheets)
    sub.add_parser("pdf", help="rulebook vs generated sheets, one PDF").set_defaults(fn=cmd_pdf)
    a = p.parse_args(argv)
    try:
        return a.fn(a)
    except DataError as e:
        print(f"DATA ERROR: {e}", file=sys.stderr)
        return 1
