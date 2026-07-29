#!/usr/bin/env bash
# Seed files from a local folder into the booted iOS Simulator's
# Files app ("On My iPhone"), so expo-document-picker can pick them.
# Usage: ./seed-sim-files.sh [SOURCE_DIR] [DEST_SUBFOLDER]
set -euo pipefail

SRC="${1:-$HOME/Downloads/files}"
SUBFOLDER="${2:-HIS100}"

if [[ ! -d "$SRC" ]]; then
  echo "Source dir not found: $SRC" >&2
  exit 1
fi

UDID="$(xcrun simctl list devices booted -j | /usr/bin/python3 -c \
  'import json,sys; d=json.load(sys.stdin)["devices"]; \
   ids=[x["udid"] for v in d.values() for x in v if x["state"]=="Booted"]; \
   print(ids[0] if ids else "")')"

if [[ -z "$UDID" ]]; then
  echo "No booted simulator. Boot one in Xcode/Simulator first." >&2
  exit 1
fi

DATA="$HOME/Library/Developer/CoreSimulator/Devices/$UDID/data"
# group.com.apple.FileProvider.LocalStorage backs Files > On My iPhone.
GROUP="$(/usr/bin/grep -rl 'group.com.apple.FileProvider.LocalStorage' \
  "$DATA/Containers/Shared/AppGroup"/*/.com.apple.mobile_container_manager.metadata.plist \
  2>/dev/null | head -1 | xargs -n1 dirname)"

if [[ -z "$GROUP" ]]; then
  echo "Files LocalStorage app group not found. Open the Files app once, then retry." >&2
  exit 1
fi

DEST="$GROUP/File Provider Storage/$SUBFOLDER"
mkdir -p "$DEST"
cp -f "$SRC"/* "$DEST"/
echo "Copied $(ls -1 "$SRC" | wc -l | tr -d ' ') item(s) -> On My iPhone/$SUBFOLDER (device $UDID)"

# Restart Files so it rescans the provider.
xcrun simctl terminate "$UDID" com.apple.DocumentsApp >/dev/null 2>&1 || true
xcrun simctl launch "$UDID" com.apple.DocumentsApp >/dev/null 2>&1 || true
echo "Done. Browse > On My iPhone > $SUBFOLDER in the simulator."
