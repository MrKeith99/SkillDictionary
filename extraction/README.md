# extraction/

The original per-challenge extractions from the 2026.2 scoresheets — one file per
challenge, every scored line as one entry. **This is the source the canonical
dictionary is built from.**

`tools/merge_challenges.py` reads `*_challenge.json` here and produces
`dictionary/`, `challenges/` and `dist/`.

Kept because it is the provenance record: `reconcile.py` rebuilds each scoresheet
from the merged output and diffs it against these files line by line, which is
how the merge is proven lossless. Deleting them would remove that check's
reference point.

Edit these only when re-extracting from a new rulebook version. For ordinary
changes edit `dictionary/` and `challenges/` instead — but note those are
currently regenerated from here, so a source edit wins. Unifying the two is
tracked as future work.
