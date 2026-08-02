#!/usr/bin/env bash

set -euo pipefail

default_data_dir="$HOME/Library/Application Support/Steam/steamapps/common/News Tower/News Tower.app/Contents/Resources/Data"
data_dir="${1:-$default_data_dir}"
output_file="${2:-$PWD/news-tower-factions.tsv}"

usage() {
  cat <<'EOF'
Usage:
  extract-news-tower-factions.sh [DATA_DIRECTORY] [OUTPUT_FILE]

Extracts the game's quest/faction identities (name + asset GUID) from the
questandnpcs asset bundle. These are the identities the NpcReputationManager
tracks player reputation with. With no arguments, it uses News Tower's default
macOS Steam location and writes ./news-tower-factions.tsv.

Examples:
  ./extract-news-tower-factions.sh
  ./extract-news-tower-factions.sh "/path/to/News Tower.app/Contents/Resources/Data"
  ./extract-news-tower-factions.sh "/path/to/Data" "$HOME/Desktop/factions.tsv"
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

for command_name in strings python3; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "Error: required command '$command_name' was not found." >&2
    exit 1
  fi
done

if [[ ! -d "$data_dir" ]]; then
  echo "Error: News Tower Data directory not found:" >&2
  echo "  $data_dir" >&2
  echo "Pass the correct Data directory as the first argument." >&2
  exit 1
fi

bundle_directory="$data_dir/StreamingAssets/aa/StandaloneOSX"

shopt -s nullglob
bundles=("$bundle_directory"/questandnpcs_assets_all_*.bundle)
shopt -u nullglob

if (( ${#bundles[@]} == 0 )); then
  echo "Error: no questandnpcs asset bundle found in:" >&2
  echo "  $bundle_directory" >&2
  exit 1
fi

if (( ${#bundles[@]} > 1 )); then
  echo "Error: multiple questandnpcs bundles were found; refusing to guess:" >&2
  printf '  %s\n' "${bundles[@]}" >&2
  exit 1
fi

bundle="${bundles[0]}"
output_directory="$(dirname "$output_file")"
mkdir -p "$output_directory"

temporary_file="$(mktemp "${TMPDIR:-/tmp}/news-tower-factions.XXXXXX")"
trap 'rm -f "$temporary_file"' EXIT

LC_ALL=C strings "$bundle" | python3 -c '
import re
import sys

lines = [line.rstrip("\r\n") for line in sys.stdin]

guid_pattern = re.compile(r"^[0-9a-f]{32}$")

# A quest/faction identity serializes as:
#   <descriptor>          ("Mafia Quest Identity", ignored)
#   <32-hex GUID>
#   <display name>        ("The Mafia", "High Society", ...)
#   Quests                (localization table name)
#   <GUID>.ls_identityName
# Requiring the table + ls_identityName key avoids unrelated GUIDs.
records = {}

for index, raw_line in enumerate(lines):
    guid = raw_line.strip()
    if not guid_pattern.fullmatch(guid):
        continue
    if index + 3 >= len(lines):
        continue
    if lines[index + 2].strip() != "Quests":
        continue
    if lines[index + 3].strip() != f"{guid}.ls_identityName":
        continue

    records[guid] = lines[index + 1].strip()

if not records:
    print("Error: no faction identities were recognized in the bundle.", file=sys.stderr)
    sys.exit(1)

print("name\tasset_guid")
for guid, name in sorted(records.items(), key=lambda item: item[1].casefold()):
    print(f"{name}\t{guid}")
' > "$temporary_file"

mv "$temporary_file" "$output_file"
trap - EXIT

record_count="$(( $(wc -l < "$output_file") - 1 ))"

echo "Extracted $record_count faction identities from:"
echo "  $bundle"
echo "Wrote:"
echo "  $output_file"
