#!/usr/bin/env bash
# Put Omarchy-DB in the app launcher for this user.
#
# It links the app's commands into ~/.local/bin, installs the desktop entry
# and the icon, and refreshes the desktop database. Nothing goes outside
# $HOME. Run it again after moving the project; run with --remove to undo.

set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
bin_dir="${HOME}/.local/bin"
data_dir="${XDG_DATA_HOME:-$HOME/.local/share}"
apps_dir="$data_dir/applications"
icon_dir="$data_dir/icons/hicolor/scalable/apps"

if [[ "${1:-}" == "--remove" ]]; then
  rm -f "$bin_dir/omarchy-db-app" "$bin_dir/omarchy-db" "$bin_dir/omarchy-db-mcp"
  rm -f "$apps_dir/omarchy-db.desktop" "$icon_dir/omarchy-db.svg"
  update-desktop-database "$apps_dir" 2>/dev/null || true
  echo "Removed the Omarchy-DB launcher."
  exit 0
fi

for cmd in omarchy-db-app omarchy-db omarchy-db-mcp; do
  if [[ ! -x "$here/.venv/bin/$cmd" ]]; then
    echo "Install the app first (see README): cd $here && uv venv --system-site-packages && uv pip install -e ." >&2
    exit 1
  fi
done

mkdir -p "$bin_dir" "$apps_dir" "$icon_dir"
for cmd in omarchy-db-app omarchy-db omarchy-db-mcp; do
  ln -sf "$here/.venv/bin/$cmd" "$bin_dir/$cmd"
done
install -Dm644 "$here/packaging/omarchy-db.desktop" "$apps_dir/omarchy-db.desktop"
install -Dm644 "$here/packaging/omarchy-db.svg" "$icon_dir/omarchy-db.svg"
update-desktop-database "$apps_dir" 2>/dev/null || true
gtk-update-icon-cache -q "$data_dir/icons/hicolor" 2>/dev/null || true

echo "Omarchy-DB is in your launcher. Commands: omarchy-db-app, omarchy-db, omarchy-db-mcp"
