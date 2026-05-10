#!/bin/zsh
set -euo pipefail

WORKFLOW_PATH="$HOME/Library/Services/Create Packlight ZIP.workflow"

fail() {
  print -u2 "Packlight uninstaller: $1"
  exit 1
}

notice() {
  print -r -- "$1"
}

display_path() {
  local value="$1"
  if [[ "$value" == "$HOME"* ]]; then
    print -r -- "\$HOME${value#$HOME}"
  else
    print -r -- "$value"
  fi
}

if [ "$(uname -s)" != "Darwin" ]; then
  fail "this uninstaller is for macOS."
fi

if [ -d "$WORKFLOW_PATH" ]; then
  rm -rf "$WORKFLOW_PATH"
  notice "Removed Finder Quick Action: $(display_path "$WORKFLOW_PATH")"
else
  notice "Finder Quick Action was not installed: $(display_path "$WORKFLOW_PATH")"
fi

if [ -n "${PACKLIGHT_PYTHON:-}" ]; then
  PYTHON="$PACKLIGHT_PYTHON"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON="$(command -v python3)"
elif [ -x /usr/bin/python3 ]; then
  PYTHON="/usr/bin/python3"
else
  PYTHON=""
fi

if [ -t 0 ] && [ -t 1 ]; then
  print -n "Also uninstall the Packlight Python package? [y/N] "
  read reply
  case "${reply:l}" in
    y|yes)
      [ -n "$PYTHON" ] || fail "python3 was not found; run python3 -m pip uninstall packlight manually after installing Python 3."
      "$PYTHON" -m pip uninstall -y packlight
      ;;
    *)
      notice "Python package left installed. To remove it later, run: python3 -m pip uninstall packlight"
      ;;
  esac
else
  notice "Python package left installed. To remove it manually, run: python3 -m pip uninstall packlight"
fi

notice "Packlight uninstall complete."
