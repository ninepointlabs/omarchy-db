#!/usr/bin/env bash
# Put Jubako in the app launcher for this user.
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
  rm -f "$bin_dir/jubako-app" "$bin_dir/jubako" "$bin_dir/jubako-mcp"
  rm -f "$apps_dir/jubako.desktop" "$icon_dir/jubako.svg"
  update-desktop-database "$apps_dir" 2>/dev/null || true
  echo "Removed the Jubako launcher."
  exit 0
fi

for cmd in jubako-app jubako jubako-mcp; do
  if [[ ! -x "$here/.venv/bin/$cmd" ]]; then
    echo "Install the app first (see README): cd $here && uv venv --system-site-packages && uv pip install -e ." >&2
    exit 1
  fi
done

mkdir -p "$bin_dir" "$apps_dir" "$icon_dir"
for cmd in jubako-app jubako jubako-mcp; do
  ln -sf "$here/.venv/bin/$cmd" "$bin_dir/$cmd"
done
install -Dm644 "$here/packaging/jubako.desktop" "$apps_dir/jubako.desktop"
install -Dm644 "$here/packaging/jubako.svg" "$icon_dir/jubako.svg"
update-desktop-database "$apps_dir" 2>/dev/null || true
gtk-update-icon-cache -q "$data_dir/icons/hicolor" 2>/dev/null || true

echo "Jubako is in your launcher. Commands: jubako-app, jubako, jubako-mcp"
