#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

source .venv/bin/activate

echo "==> ruff"
ruff check .

echo "==> mypy"
mypy src tests

echo "==> pytest"
pytest -q

echo "==> tudo verde"
