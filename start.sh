#!/usr/bin/env bash
#
# Sets up the Python environment (a .venv virtualenv) and launches the
# News Tower Save Editor. Safe to re-run.
#
# tkinter links whatever Tcl/Tk its interpreter was built against, and a venv
# inherits that from its base interpreter -- it can't upgrade Tk on its own.
# macOS's system python3 links the deprecated Tk 8.5 (hence the warning), so we
# prefer an interpreter with a modern Tk (>= 8.6) as the venv base. If none is
# found we fall back to system Python and silence the deprecation warning.

set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$project_dir"

venv_dir="$project_dir/.venv"

# Silences macOS's "system version of Tk is deprecated" warning as a fallback.
export TK_SILENCE_DEPRECATION=1

# Prints the Tk version an interpreter would use, or nothing if tkinter is
# missing/broken.
tk_version() {
  "$1" -c 'import tkinter; print(tkinter.TkVersion)' 2>/dev/null || true
}

# True when a Tk version string is 8.6 or newer (8.5 is the deprecated one).
tk_is_modern() {
  case "$1" in
    ""|8.0|8.1|8.2|8.3|8.4|8.5) return 1 ;;
    *) return 0 ;;
  esac
}

# Find the best available interpreter: first candidate with a modern Tk wins,
# otherwise fall back to the first one that has tkinter at all.
pick_python() {
  local candidates=(
    "$(command -v python3 || true)"
    /opt/homebrew/bin/python3
    /usr/local/bin/python3
    /Library/Frameworks/Python.framework/Versions/Current/bin/python3
    /usr/bin/python3
  )
  local fallback=""
  for candidate in "${candidates[@]}"; do
    [[ -x "$candidate" ]] || continue
    local version
    version="$(tk_version "$candidate")"
    [[ -n "$version" ]] || continue
    if tk_is_modern "$version"; then
      echo "$candidate"
      return 0
    fi
    [[ -z "$fallback" ]] && fallback="$candidate"
  done
  [[ -n "$fallback" ]] && { echo "$fallback"; return 0; }
  return 1
}

base_python="$(pick_python)" || {
  echo "Error: no python3 with a working tkinter was found." >&2
  echo "On macOS install one with a modern Tk, e.g.:  brew install python-tk" >&2
  exit 1
}

base_tk="$(tk_version "$base_python")"
echo "Using $base_python (Tk $base_tk) as the environment's Python."
if ! tk_is_modern "$base_tk"; then
  echo "Warning: only the deprecated Tk $base_tk is available; the app will run"
  echo "         but for a nicer UI install a modern Tk:  brew install python-tk"
fi

# (Re)create the venv if it's missing or was built on a different base Python.
recreate=0
if [[ ! -x "$venv_dir/bin/python" ]]; then
  recreate=1
else
  linked="$("$venv_dir/bin/python" -c 'import sys; print(sys.base_prefix)' 2>/dev/null || true)"
  expected="$("$base_python" -c 'import sys; print(sys.base_prefix)' 2>/dev/null || true)"
  [[ "$linked" != "$expected" ]] && recreate=1
fi

if [[ "$recreate" -eq 1 ]]; then
  echo "Creating virtual environment in .venv ..."
  rm -rf "$venv_dir"
  "$base_python" -m venv "$venv_dir"
fi

python="$venv_dir/bin/python"

echo "Launching News Tower Save Editor ..."
exec "$python" main.py
