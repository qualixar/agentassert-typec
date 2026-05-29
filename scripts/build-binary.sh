#!/bin/bash
# scripts/build-binary.sh — Build single binary via PyInstaller
set -e

NAME="${1:-agentassert-proxy-macos-arm64}"

echo "Building $NAME..."

uv run pip install pyinstaller
uv run pyinstaller --onefile \
  --name "$NAME" \
  --hidden-import agentassert_typec_core \
  --hidden-import agentassert_typec_core.models \
  --hidden-import agentassert_typec_core.dsl \
  --hidden-import agentassert_typec_core.evaluator \
  --hidden-import agentassert_typec_core.monitor \
  packages/proxy/src/agentassert_typec_proxy/cli.py

echo "Binary: dist/$NAME"
ls -lh "dist/$NAME"
