#!/usr/bin/env bash
# Lay Jubako out under a staging root, the way the .deb and .rpm install it.
#
#   packaging/stage.sh <destdir>
#
# The Python code goes in its own folder, /usr/lib/jubako, rather than the
# distro's site-packages, so one package works whatever Python 3 version the
# distro ships. Small /usr/bin scripts point Python at that folder.

set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
dest="${1:?usage: stage.sh <destdir>}"
lib="$dest/usr/lib/jubako"

mkdir -p "$lib" "$dest/usr/bin"
for pkg in jubako jubako_app jubako_mcp; do
  cp -r "$here/src/$pkg" "$lib/"
done
find "$lib" -name __pycache__ -type d -prune -exec rm -rf {} +

for pair in jubako:jubako jubako-app:jubako_app jubako-mcp:jubako_mcp; do
  cmd="${pair%%:*}"
  module="${pair#*:}"
  cat >"$dest/usr/bin/$cmd" <<EOF
#!/bin/sh
export PYTHONPATH="/usr/lib/jubako\${PYTHONPATH:+:\$PYTHONPATH}"
exec /usr/bin/python3 -m $module "\$@"
EOF
  chmod 755 "$dest/usr/bin/$cmd"
done

install -Dm644 "$here/packaging/jubako.desktop" "$dest/usr/share/applications/jubako.desktop"
install -Dm644 "$here/packaging/jubako.svg" "$dest/usr/share/icons/hicolor/scalable/apps/jubako.svg"
install -Dm644 "$here/README.md" "$dest/usr/share/doc/jubako/README.md"
install -Dm644 "$here/LICENSE" "$dest/usr/share/licenses/jubako/LICENSE"
