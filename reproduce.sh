#!/usr/bin/env bash
# Reproduce every number, table, and figure in the paper from the checked-in
# data. Two steps: compute the metrics inside the api container (it has the DB),
# then render the LaTeX tables and figures on the host (it has matplotlib).
#
#   bash reproduce.sh
#
# Deterministic: results.json comes out byte-identical each run.
set -euo pipefail
cd "$(dirname "$0")"

echo "[1/2] computing metrics -> backend/research/generated/results.json"
docker compose exec -T api python -m research.make_results

echo "[2/2] rendering tables + figures -> paper/tables, paper/figures"
python paper/build_assets.py

echo
echo "Done. The paper (paper/expensitor.tex) \\input-s the generated tables and"
echo "\\includegraphics-es the generated figures. Compile it in Overleaf or with:"
echo "    cd paper && pdflatex expensitor && bibtex expensitor && pdflatex expensitor && pdflatex expensitor"
