"""One PDF with, per challenge, the rulebook's official sheet next to the
season's generated one, typeset with the rulebook's own macros.

Compiled in build/latex/, a copy of the pinned RuleBook, with the preamble of
the rulebook's own documents/scoresheets.tex, so nothing in the submodule is
touched and no rulebook source is copied into this repo. Needs latexmk and a
TeX distribution.
"""
import os, shutil, subprocess
from .. import paths
from . import sheets


def write(b):
    work = os.path.join(paths.BUILD, "latex")
    shutil.copytree(paths.RULEBOOK, work, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns(".git", ".build"))
    official = (b.season if b.season.in_force else b.base.season).sheets
    ref_version = b.rulebook_version
    label = "generated from the skill dictionary" if b.season.in_force else f"{b.season.year} PROPOSAL (draft)"
    body = []
    for slug in sorted(b.challenges):
        name = b.challenges[slug]["challenge"]
        src = sheets.tex(b, slug)
        mine = f"skilldict_{b.season.year}_{slug}"
        shutil.copy(src, os.path.join(work, "scoresheets", f"{mine}.tex"))
        pages = []
        if official.get(slug):
            pages.append((f"{name} --- official sheet (Rulebook {ref_version})", name, official[slug]))
        pages.append((f"{name} --- {label}", f"{name} ({label})", mine))
        for foot, test, tex in pages:
            body += [rf"\renewcommand{{\footline}}{{{sheets.tex_esc(foot)}}}",
                     rf"\renewcommand{{\currentTest}}{{{sheets.tex_esc(test)}}}",
                     r"\begin{scoresheet}", rf"\input{{scoresheets/{tex}}}", r"\end{scoresheet}"]
    doc = f"skilldict_{b.season.year}"
    with open(os.path.join(work, "documents", "scoresheets.tex")) as fh:
        preamble = fh.read().split(r"\begin{document}")[0]
    paths.write_text(preamble + "\n".join([r"\begin{document}", r"\pagestyle{plain}",
                                           r"\renewcommand{\shortScoresheet}{false}", *body,
                                           r"\end{document}", ""]),
                     os.path.join(work, "documents", f"{doc}.tex"))
    log = os.path.join(work, f"{doc}.log")
    with open(log, "w") as fh:
        r = subprocess.run(["latexmk", "-pdf", "-interaction=nonstopmode", "-outdir=.build",
                            f"documents/{doc}.tex"], cwd=work, stdout=fh, stderr=subprocess.STDOUT)
    pdf = os.path.join(work, ".build", f"{doc}.pdf")
    if r.returncode or not os.path.exists(pdf):
        raise RuntimeError(f"latexmk failed, see {paths.rel(log)}")
    base_year = b.season.year if b.season.in_force else b.base.season.year
    out = os.path.join(b.season.build_dir, f"sheets_{b.season.year}_vs_rulebook_{base_year}.pdf")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    shutil.copy(pdf, out)
    return out
