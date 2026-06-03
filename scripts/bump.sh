#!/usr/bin/env bash
# バージョンを bump して push する。
# 引数: patch | minor | major
# main ブランチ以外では実行を拒否する。
set -euo pipefail

LEVEL="${1:-}"
if [[ "$LEVEL" != "patch" && "$LEVEL" != "minor" && "$LEVEL" != "major" ]]; then
  echo "使用方法: bump.sh <patch|minor|major>" >&2
  exit 1
fi

CURRENT_BRANCH="$(git branch --show-current)"
if [[ "$CURRENT_BRANCH" != "main" ]]; then
  echo "Error: bump は main ブランチでのみ実行できます（現在: $CURRENT_BRANCH）" >&2
  exit 1
fi

bump-my-version bump "$LEVEL"
git push
git push --tags
