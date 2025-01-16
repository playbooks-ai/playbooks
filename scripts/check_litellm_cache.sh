#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT/python/packages/playbooks" && poetry run python "$REPO_ROOT/scripts/check_litellm_cache.py" "$@"
