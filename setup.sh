#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

echo "=== Coeus CI setup ==="

python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"

echo ""
echo "=== Setup complete ==="
echo "Run: source venv/bin/activate && coeus --help"
