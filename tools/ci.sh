#!/usr/bin/env bash
# Full validation gate. Run after any edit to dictionary/ or challenges/.
set -euo pipefail
cd "$(dirname "$0")"

echo ">>> building dist/ from dictionary/, challenges/, vocabulary/"
python3 build_dist.py

echo; echo ">>> viz data"
python3 build_viz_data.py

echo; echo ">>> schema"
python3 check_schema.py

echo; echo ">>> taxonomy + difficulty (vocabulary refs, fairness findings)"
python3 check_taxonomy.py

echo; echo ">>> reconcile (lossless vs legacy scoresheets)"
python3 reconcile.py

echo; echo ">>> scoresheets (vs rulebook LaTeX, 2026.2)"
python3 check_scoresheets.py

echo; echo ">>> validate (TC findings)"
python3 validate.py

echo; echo "ALL CHECKS PASSED"
