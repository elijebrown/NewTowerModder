#!/usr/bin/env bash

set -euo pipefail

default_data_dir="$HOME/Library/Application Support/Steam/steamapps/common/News Tower/News Tower.app/Contents/Resources/Data"
data_dir="${1:-$default_data_dir}"
output_file="${2:-$PWD/news-tower-jobs-skills.tsv}"

usage() {
  cat <<'EOF'
Usage:
  extract-news-tower-jobs-skills.sh [DATA_DIRECTORY] [OUTPUT_FILE]

Extracts the game's Job and Skill definitions (name + asset GUID) from the
jobsandskills asset bundle. With no arguments, it uses News Tower's default
macOS Steam location and writes ./news-tower-jobs-skills.tsv.

Examples:
  ./extract-news-tower-jobs-skills.sh
  ./extract-news-tower-jobs-skills.sh "/path/to/News Tower.app/Contents/Resources/Data"
  ./extract-news-tower-jobs-skills.sh "/path/to/Data" "$HOME/Desktop/jobs-skills.tsv"
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
bundles=("$bundle_directory"/jobsandskills_assets_all_*.bundle)
shopt -u nullglob

if (( ${#bundles[@]} == 0 )); then
  echo "Error: no jobsandskills asset bundle found in:" >&2
  echo "  $bundle_directory" >&2
  exit 1
fi

if (( ${#bundles[@]} > 1 )); then
  echo "Error: multiple jobsandskills bundles were found; refusing to guess:" >&2
  printf '  %s\n' "${bundles[@]}" >&2
  exit 1
fi

bundle="${bundles[0]}"
output_directory="$(dirname "$output_file")"
mkdir -p "$output_directory"

temporary_file="$(mktemp "${TMPDIR:-/tmp}/news-tower-jobs-skills.XXXXXX")"
trap 'rm -f "$temporary_file"' EXIT

LC_ALL=C strings "$bundle" | python3 -c '
import re
import sys

lines = [line.rstrip("\r\n") for line in sys.stdin]

guid_pattern = re.compile(r"^[0-9a-f]{32}$")

# Both Jobs and Skills serialize the same way in the bundle string table:
#   <name>            (sometimes with a trailing space)
#   <32-hex GUID>
#   <name>            (repeated)
#   <TableName>       ("Skills" or "JobData")
#   <GUID>.<key>      (the localized-name key: ls_skillName / ls_title)
# The table name and key distinguish a Skill record from a Job record, and
# avoid matching unrelated GUIDs elsewhere in the bundle.
table_to_category = {"Skills": "Skill", "JobData": "Job"}
category_key = {"Skills": "ls_skillName", "JobData": "ls_title"}

records = {}

for index, raw_line in enumerate(lines):
    guid = raw_line.strip()
    if not guid_pattern.fullmatch(guid) or index == 0:
        continue
    if index + 3 >= len(lines):
        continue

    name = lines[index - 1].strip()
    if lines[index + 1].strip() != name:
        continue

    table = lines[index + 2].strip()
    if table not in table_to_category:
        continue
    if lines[index + 3].strip() != f"{guid}.{category_key[table]}":
        continue

    records[guid] = (table_to_category[table], name)

if not records:
    print("Error: no job or skill records were recognized in the bundle.", file=sys.stderr)
    sys.exit(1)

print("category\tname\tasset_guid")
for guid, (category, name) in sorted(
    records.items(), key=lambda item: (item[1][0], item[1][1].casefold())
):
    print(f"{category}\t{name}\t{guid}")
' > "$temporary_file"

mv "$temporary_file" "$output_file"
trap - EXIT

record_count="$(( $(wc -l < "$output_file") - 1 ))"

echo "Extracted $record_count job/skill records from:"
echo "  $bundle"
echo "Wrote:"
echo "  $output_file"
