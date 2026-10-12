# extraction/

The original per-challenge extractions from the 2026.2 scoresheets — one file per
challenge, every scored line as one entry. The canonical dictionary was
migrated from these once by `tools/migrate_legacy.py`; it is **no longer
rebuilt from here**.

Kept because it is the provenance record: `reconcile.py` rebuilds each scoresheet
from the merged output and diffs it against these files line by line, which is
how the merge is proven lossless. Deleting them would remove that check's
reference point.

`dictionary/` and `challenges/` are the source of truth and carry fields these
files do not (taxonomy, objects, conditions). Do not re-run the migration: it
would overwrite them, which is why it refuses without `--force`.
