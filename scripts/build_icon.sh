#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname)" == "Darwin" ]]; then
  _lib_paths=()
  if command -v brew &>/dev/null; then
    _lib_paths+=("$(brew --prefix)/lib")
  fi
  if [[ -d "$HOME/.nix-profile/lib" ]]; then
    _lib_paths+=("$HOME/.nix-profile/lib")
  fi
  if [[ ${#_lib_paths[@]} -gt 0 ]]; then
    _joined="$(IFS=:; echo "${_lib_paths[*]}")"
    export DYLD_FALLBACK_LIBRARY_PATH="${_joined}${DYLD_FALLBACK_LIBRARY_PATH:+:$DYLD_FALLBACK_LIBRARY_PATH}"
  fi
fi

exec python "$(dirname "$0")/build_icon.py" "$@"
