#!/bin/zsh
set -euo pipefail

fail() {
  print -u2 "Packlight Quick Action: $1"
  if is_finder_action; then
    show_finder_alert "Packlight could not create the ZIP" "$1"
    exit 0
  fi
  exit 1
}

warn() {
  print -u2 "Packlight Quick Action: $1"
}

is_finder_action() {
  [ "${PACKLIGHT_FINDER_ACTION:-}" = "1" ]
}

show_finder_alert() {
  local title="$1"
  local message="$2"

  print -u2 -r -- "$title"
  print -u2 -r -- "$message"

  if [ "${PACKLIGHT_SUPPRESS_ALERT:-}" = "1" ]; then
    return 0
  fi

  if [ ! -x /usr/bin/osascript ]; then
    return 0
  fi

  /usr/bin/osascript - "$title" "$message" >/dev/null 2>&1 <<'APPLESCRIPT' &
on run argv
  set alertTitle to item 1 of argv
  set alertMessage to item 2 of argv
  display alert alertTitle message alertMessage as critical buttons {"OK"} default button "OK"
end run
APPLESCRIPT
}

friendly_failure_message() {
  local source="$1"
  local command_output="$2"
  local -a output_lines
  local -a detail_lines
  local line
  local details=""
  local folder_name="${source:t}"

  output_lines=("${(@f)command_output}")
  for line in "${output_lines[@]}"; do
    if [[ "$line" == "- "* ]]; then
      detail_lines+=("$line")
    fi
  done

  if (( ${#detail_lines[@]} > 0 )); then
    details="${(F)detail_lines}"
  fi

  if [[ "$command_output" == *"risky files were found"* ]]; then
    if [ -n "$details" ]; then
      print -r -- "Packlight stopped because risky files were found in \"$folder_name\".

Details:
$details

No ZIP was created or replaced for that folder."
    else
      print -r -- "Packlight stopped because risky files were found in \"$folder_name\".

No ZIP was created or replaced for that folder."
    fi
    return 0
  fi

  if [ -n "$command_output" ]; then
    print -r -- "Packlight could not create the ZIP for \"$folder_name\".

$command_output

No ZIP was created or replaced for that folder."
  else
    print -r -- "Packlight could not create the ZIP for \"$folder_name\".

No ZIP was created or replaced for that folder."
  fi
}

finder_failure_report() {
  local -a failure_messages
  failure_messages=("$@")

  if (( ${#failure_messages[@]} == 1 )); then
    print -r -- "$failure_messages[1]"
    return 0
  fi

  print -r -- "Packlight could not create every selected ZIP.

${(F)failure_messages}

Existing ZIPs for failed folders were not replaced."
}

resolve_python() {
  if [ -n "${PACKLIGHT_PYTHON:-}" ]; then
    if [ -x "$PACKLIGHT_PYTHON" ]; then
      print -r -- "$PACKLIGHT_PYTHON"
      return 0
    fi
    if command -v "$PACKLIGHT_PYTHON" >/dev/null 2>&1; then
      command -v "$PACKLIGHT_PYTHON"
      return 0
    fi
  fi

  if command -v python3 >/dev/null 2>&1; then
    command -v python3
    return 0
  fi

  if [ -x /usr/bin/python3 ]; then
    print -r -- /usr/bin/python3
    return 0
  fi

  return 1
}

load_config() {
  local script_path="${0:A}"
  local script_dir="${script_path:h}"
  local config_path="${PACKLIGHT_CONFIG:-}"

  if [ -z "$config_path" ] && [ -f "$script_dir/packlight.conf" ]; then
    config_path="$script_dir/packlight.conf"
  fi

  if [ -n "$config_path" ]; then
    if [ ! -f "$config_path" ]; then
      fail "configured file was not found: $config_path"
    fi
    source "$config_path"
  fi
}

seed_path() {
  export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$HOME/.local/bin:$PATH"

  local python_bin=""
  if python_bin="$(resolve_python 2>/dev/null)"; then
    local python_user_base=""
    if python_user_base="$("$python_bin" -m site --user-base 2>/dev/null)"; then
      PATH="$python_user_base/bin:$PATH"
    fi
  fi

  local python_user_bin
  for python_user_bin in "$HOME"/Library/Python/*/bin(N); do
    PATH="$python_user_bin:$PATH"
  done
  export PATH
}

discover_packlight() {
  typeset -ga PACKLIGHT_COMMAND
  PACKLIGHT_COMMAND=()

  if [ -n "${PACKLIGHT_EXECUTABLE:-}" ]; then
    if [ -x "$PACKLIGHT_EXECUTABLE" ]; then
      PACKLIGHT_COMMAND=("$PACKLIGHT_EXECUTABLE")
      return 0
    fi
    warn "configured command is not executable: $PACKLIGHT_EXECUTABLE"
  fi

  if command -v packlight >/dev/null 2>&1; then
    PACKLIGHT_COMMAND=("$(command -v packlight)")
    return 0
  fi

  local python_bin=""
  if python_bin="$(resolve_python 2>/dev/null)" && "$python_bin" -c "import packlight" >/dev/null 2>&1; then
    PACKLIGHT_COMMAND=("$python_bin" -m packlight)
    return 0
  fi

  if [ -n "${PACKLIGHT_PROJECT_ROOT:-}" ]; then
    if [ ! -f "$PACKLIGHT_PROJECT_ROOT/packlight/__main__.py" ]; then
      fail "PACKLIGHT_PROJECT_ROOT does not point to a Packlight checkout: $PACKLIGHT_PROJECT_ROOT"
    fi
    if [ -z "$python_bin" ]; then
      python_bin="$(resolve_python)" || fail "python3 was not found."
    fi
    export PYTHONPATH="$PACKLIGHT_PROJECT_ROOT${PYTHONPATH:+:$PYTHONPATH}"
    PACKLIGHT_COMMAND=("$python_bin" -m packlight)
    return 0
  fi

  fail "Packlight is not installed. Run macos/install-packlight.command, add packlight to PATH, or set PACKLIGHT_PROJECT_ROOT for a development checkout."
}

run_packlight() {
  local source="$1"
  local output="$2"
  local command_output=""

  if is_finder_action; then
    if command_output="$("${PACKLIGHT_COMMAND[@]}" "$source" --output "$output" --release --force 2>&1)"; then
      return 0
    fi
    if [ -n "$command_output" ]; then
      print -u2 -r -- "$command_output"
    fi
    FINDER_FAILURE_MESSAGES+=("$(friendly_failure_message "$source" "$command_output")")
    return 1
  fi

  "${PACKLIGHT_COMMAND[@]}" "$source" --output "$output" --release --force
}

if [ "$#" -eq 0 ]; then
  exit 0
fi

load_config
seed_path
discover_packlight

exit_status=0
processed=0
typeset -ga FINDER_FAILURE_MESSAGES
FINDER_FAILURE_MESSAGES=()
for item in "$@"; do
  if [ ! -d "$item" ]; then
    warn "selected item is not a folder: $item"
    if is_finder_action; then
      FINDER_FAILURE_MESSAGES+=("Packlight could not create the ZIP because the selected item is not a folder:
$item

No ZIP was created or replaced for that item.")
    fi
    exit_status=1
    continue
  fi

  source="${item%/}"
  if [ -z "$source" ]; then
    source="$item"
  fi
  output="${source}.zip"
  if run_packlight "$source" "$output"; then
    processed=$((processed + 1))
  else
    exit_status=1
  fi
done

if [ "$processed" -eq 0 ]; then
  warn "no folders were processed."
fi

if is_finder_action && [ "$exit_status" -ne 0 ]; then
  show_finder_alert "Packlight could not create the ZIP" "$(finder_failure_report "${FINDER_FAILURE_MESSAGES[@]}")"
  exit 0
fi

exit "$exit_status"
