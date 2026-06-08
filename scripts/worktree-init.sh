#!/usr/bin/env bash
# worktree 作成時にメインリポジトリのファイル・ディレクトリへシンボリックリンクを張り、
# 依存パッケージを同期する。post-checkout フックから呼び出す。
export PATH="$HOME/.nix-profile/bin:$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

GIT_DIR=$(git rev-parse --git-dir)
COMMON_DIR=$(git rev-parse --git-common-dir)

# worktree でない場合は何もしない
if [ "$GIT_DIR" = "$COMMON_DIR" ]; then
  exit 0
fi

ROOT="$(dirname "$COMMON_DIR")"

for name in .envrc .claude; do
  TARGET="$(pwd)/$name"
  if [ ! -e "$TARGET" ]; then
    ln -sfn "$ROOT/$name" "$TARGET"
  fi
done

uv sync
dagayn build --skip-flows
