#!/usr/bin/env bash
# Full validation gate. Run after any edit to dictionary/ or challenges/.
set -euo pipefail
cd "$(dirname "$0")"

echo ">>> rebuilding canonical dictionary from source"
python3 merge_challenges.py

echo; echo ">>> viz data"
python3 build_viz_data.py

echo; echo ">>> schema"
python3 check_schema.py

echo; echo ">>> reconcile (lossless vs legacy scoresheets)"
python3 reconcile.py

echo; echo ">>> scoresheets (vs rulebook LaTeX, 2026.2)"
python3 check_scoresheets.py

echo; echo ">>> validate (TC findings)"
python3 validate.py

echo; echo "ALL CHECKS PASSED"
