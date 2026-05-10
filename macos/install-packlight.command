#!/bin/zsh
set -euo pipefail

WORKFLOW_NAME="Create Packlight ZIP.workflow"
SERVICE_NAME="Create Packlight ZIP"

fail() {
  print -u2 "Packlight installer: $1"
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

path_contains() {
  local needle="$1"
  local entry
  local -a entries
  entries=("${(@s/:/)PATH}")
  for entry in "${entries[@]}"; do
    if [ "$entry" = "$needle" ]; then
      return 0
    fi
  done
  return 1
}

if [ "$(uname -s)" != "Darwin" ]; then
  fail "this installer is for macOS."
fi

SCRIPT_PATH="${0:A}"
SCRIPT_DIR="${SCRIPT_PATH:h}"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd -P)"

if [ -n "${PACKLIGHT_PYTHON:-}" ]; then
  PYTHON="$PACKLIGHT_PYTHON"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON="$(command -v python3)"
elif [ -x /usr/bin/python3 ]; then
  PYTHON="/usr/bin/python3"
else
  fail "python3 was not found. Install Python 3, then run this installer again."
fi

if ! "$PYTHON" -m pip --version >/dev/null 2>&1; then
  fail "pip is not available for $PYTHON. Install pip for Python 3, then run this installer again."
fi

notice "Installing Packlight with: $PYTHON -m pip install --user ."
"$PYTHON" -m pip install --user "$PROJECT_ROOT"

USER_BASE="$("$PYTHON" -m site --user-base)"
USER_BIN="$USER_BASE/bin"
PACKLIGHT_EXECUTABLE="$USER_BIN/packlight"

if [ ! -x "$PACKLIGHT_EXECUTABLE" ]; then
  if command -v packlight >/dev/null 2>&1; then
    PACKLIGHT_EXECUTABLE="$(command -v packlight)"
  else
    PACKLIGHT_EXECUTABLE=""
  fi
fi

if [ -n "$PACKLIGHT_EXECUTABLE" ]; then
  "$PACKLIGHT_EXECUTABLE" --version >/dev/null || fail "installed packlight command did not run: $PACKLIGHT_EXECUTABLE"
else
  "$PYTHON" -m packlight --version >/dev/null || fail "Packlight installed, but no runnable command was found."
fi

if ! path_contains "$USER_BIN"; then
  notice "Warning: $(display_path "$USER_BIN") is not on PATH. Finder will use the configured Quick Action command, but Terminal may not find packlight until you add that directory to PATH."
fi

SERVICES_DIR="$HOME/Library/Services"
WORKFLOW_PATH="$SERVICES_DIR/$WORKFLOW_NAME"
mkdir -p "$SERVICES_DIR"

notice "Installing Finder Quick Action: $(display_path "$WORKFLOW_PATH")"
"$PYTHON" "$SCRIPT_DIR/build-quick-action.py" \
  --output "$WORKFLOW_PATH" \
  --wrapper "$SCRIPT_DIR/create-packlight-zip.sh" \
  --packlight-executable "$PACKLIGHT_EXECUTABLE" \
  --python "$PYTHON"

if [ ! -d "$WORKFLOW_PATH" ]; then
  fail "workflow was not installed: $WORKFLOW_PATH"
fi

notice ""
notice "Packlight is installed."
if [ -n "$PACKLIGHT_EXECUTABLE" ]; then
  notice "Command: $(display_path "$PACKLIGHT_EXECUTABLE")"
else
  notice "Command: $PYTHON -m packlight"
fi
notice "Quick Action: $(display_path "$WORKFLOW_PATH")"
notice ""
notice "Next steps:"
notice "1. In Finder, right-click a folder."
notice "2. Choose Quick Actions or Services."
notice "3. Choose \"$SERVICE_NAME\"."
notice ""
notice "Finder menu placement varies by macOS version and user settings."
