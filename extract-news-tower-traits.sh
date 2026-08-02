#!/usr/bin/env bash

set -euo pipefail

default_data_dir="$HOME/Library/Application Support/Steam/steamapps/common/News Tower/News Tower.app/Contents/Resources/Data"
data_dir="${1:-$default_data_dir}"
output_file="${2:-$PWD/news-tower-traits.tsv}"

usage() {
  cat <<'EOF'
Usage:
  extract-news-tower-traits.sh [DATA_DIRECTORY] [OUTPUT_FILE]

With no arguments, the script uses News Tower's default macOS Steam location
and writes ./news-tower-traits.tsv.

Examples:
  ./extract-news-tower-traits.sh
  ./extract-news-tower-traits.sh "/path/to/News Tower.app/Contents/Resources/Data"
  ./extract-news-tower-traits.sh "/path/to/Data" "$HOME/Desktop/traits.tsv"
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
trait_bundles=("$bundle_directory"/traitdata_assets_all_*.bundle)
shopt -u nullglob

if (( ${#trait_bundles[@]} == 0 )); then
  echo "Error: no traitdata asset bundle found in:" >&2
  echo "  $bundle_directory" >&2
  exit 1
fi

if (( ${#trait_bundles[@]} > 1 )); then
  echo "Error: multiple traitdata bundles were found; refusing to guess:" >&2
  printf '  %s\n' "${trait_bundles[@]}" >&2
  exit 1
fi

trait_bundle="${trait_bundles[0]}"
output_directory="$(dirname "$output_file")"
mkdir -p "$output_directory"

temporary_file="$(mktemp "${TMPDIR:-/tmp}/news-tower-traits.XXXXXX")"
trap 'rm -f "$temporary_file"' EXIT

LC_ALL=C strings "$trait_bundle" | python3 -c '
import re
import sys

lines = [line.rstrip("\r\n") for line in sys.stdin]

# Recover each asset category from strings such as:
# Assets/_Data/Traits/Personality/Natural Timekeeper.asset
categories = {}
path_pattern = re.compile(r"^Assets/_Data/Traits/(.+)/([^/]+?)\.asset")

for raw_line in lines:
    match = path_pattern.match(raw_line.strip())
    if match:
        category_path, name = match.groups()
        categories.setdefault(name.strip(), category_path.strip())

guid_pattern = re.compile(r"^[0-9a-f]{32}$")
records = {}

for index, raw_line in enumerate(lines):
    guid = raw_line.strip()
    if not guid_pattern.fullmatch(guid) or index == 0:
        continue

    name = lines[index - 1].strip()

    # A real TraitData record repeats its name after the GUID and then stores
    # its Traits localization-table reference. Checking this avoids unrelated
    # GUIDs elsewhere in the bundle.
    if index + 2 >= len(lines):
        continue
    if lines[index + 1].strip() != name:
        continue
    if lines[index + 2].strip() != "Traits":
        continue

    localization_key = f"{guid}.ls_traitName"
    nearby = {line.strip() for line in lines[index + 2:index + 6]}
    if localization_key not in nearby:
        continue

    records[guid] = (categories.get(name, "Unknown"), name)

if not records:
    print("Error: no trait records were recognized in the bundle.", file=sys.stderr)
    sys.exit(1)

print("category\tname\tasset_guid")
for guid, (category, name) in sorted(
    records.items(), key=lambda item: (item[1][0].casefold(), item[1][1].casefold())
):
    print(f"{category}\t{name}\t{guid}")
' > "$temporary_file"

mv "$temporary_file" "$output_file"
trap - EXIT

trait_count="$(( $(wc -l < "$output_file") - 1 ))"

echo "Extracted $trait_count traits from:"
echo "  $trait_bundle"
echo "Wrote:"
echo "  $output_file"
