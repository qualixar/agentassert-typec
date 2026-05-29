#!/bin/bash
# scripts/publish-all.sh — Publish all 4 packages to PyPI
set -e

echo "Publishing agentassert-typec packages to PyPI..."

for pkg in core proxy sdk claude-code; do
    echo "--- Building packages/$pkg ---"
    (cd "packages/$pkg" && uv run python -m build)
    echo "--- Publishing agentassert-typec-$pkg ---"
    uv run twine upload "packages/$pkg/dist/"*
    echo "--- agentassert-typec-$pkg published ---"
    sleep 30
done

echo "All packages published. Verify:"
echo "  pip install agentassert-typec-proxy"
echo "  pip install agentassert-typec-sdk"
echo "  pip install agentassert-typec-claude-code"
