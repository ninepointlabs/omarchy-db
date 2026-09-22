"""Omarchy's colours, read from the active theme so the window matches the desktop.

`omarchy theme set` writes the chosen theme to
`~/.local/state/omarchy/current/theme/colors.toml`. We read that file, build a
Qt palette from it, and watch it so a theme change re-colours the open window.
When the file is missing (not on Omarchy, or a very old install) a plain dark
palette is used instead.
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path

from PySide6.QtCore import Property, QFileSystemWatcher, QObject, Signal, Slot
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPalette

FALLBACK = {
    "mode": "dark",
    "accent": "#7daea3",
    "selection": "#504945",
    "muted": "#665c54",
    "background": "#282828",
    "dark_background": "#1e1e1e",
    "darker_background": "#161616",
    "lighter_background": "#3c3836",
    "foreground": "#d4be98",
    "dark_foreground": "#7c6f64",
    "light_foreground": "#bdae93",
    "bright_foreground": "#d4be98",
    "red": "#ea6962",
    "yellow": "#d8a657",
    "green": "#a9b665",
    "blue": "#7daea3",
}

COLOR_KEYS = tuple(key for key in FALLBACK if key != "mode")


def theme_dir() -> Path:
    base = os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
    return Path(base) / "omarchy" / "current" / "theme"


def colors_file() -> Path:
    override = os.environ.get("OMARCHY_DB_THEME_FILE")
    return Path(override) if override else theme_dir() / "colors.toml"


def load_colors(path: Path | None = None) -> dict[str, str]:
    """The theme's colours, with the fallback filling any gap."""
    path = path or colors_file()
    colors = dict(FALLBACK)
    try:
        data = tomllib.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return colors
    for key in FALLBACK:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            colors[key] = value.strip()
    return colors


def build_palette(colors: dict[str, str]) -> QPalette:
    """Turn Omarchy colours into the palette Qt Quick Controls (Fusion) paints with."""
    dark = colors.get("mode", "dark") != "light"
    c = {key: QColor(value) for key, value in colors.items() if key != "mode"}
    window = c["background"] if dark else c["dark_background"]
    base = c["dark_background"] if dark else c["background"]

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, window)
    palette.setColor(QPalette.ColorRole.WindowText, c["foreground"])
    palette.setColor(QPalette.ColorRole.Base, base)
    palette.setColor(QPalette.ColorRole.AlternateBase, c["lighter_background"] if dark else c["dark_background"])
    palette.setColor(QPalette.ColorRole.Text, c["foreground"])
    palette.setColor(QPalette.ColorRole.PlaceholderText, c["dark_foreground"])
    palette.setColor(QPalette.ColorRole.Button, c["lighter_background"])
    palette.setColor(QPalette.ColorRole.ButtonText, c["foreground"])
    palette.setColor(QPalette.ColorRole.BrightText, c["bright_foreground"])
    palette.setColor(QPalette.ColorRole.Highlight, c["accent"])
    palette.setColor(QPalette.ColorRole.HighlightedText, c["background"] if dark else QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.Link, c["blue"])
    palette.setColor(QPalette.ColorRole.ToolTipBase, c["lighter_background"])
    palette.setColor(QPalette.ColorRole.ToolTipText, c["foreground"])
    palette.setColor(QPalette.ColorRole.Light, c["lighter_background"])
    palette.setColor(QPalette.ColorRole.Midlight, c["lighter_background"])
    palette.setColor(QPalette.ColorRole.Mid, c["muted"])
    palette.setColor(QPalette.ColorRole.Dark, c["darker_background"])
    palette.setColor(QPalette.ColorRole.Shadow, c["darker_background"])
    for role in (
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
        QPalette.ColorRole.WindowText,
    ):
        palette.setColor(QPalette.ColorGroup.Disabled, role, c["dark_foreground"])
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Button, window)
    return palette


class Theme(QObject):
    """What QML sees: the colours as properties, and a signal when they change."""

    changed = Signal()

    def __init__(self, app: QGuiApplication | None = None, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._app = app
        self._colors = load_colors()
        self._watcher = QFileSystemWatcher(self)
        self._watch()
        self._watcher.fileChanged.connect(self._reload)
        self._watcher.directoryChanged.connect(self._reload)
        self.apply()

    def _watch(self) -> None:
        path = colors_file()
        for candidate in (path, path.parent):
            if candidate.exists() and str(candidate) not in self._watcher.files() + self._watcher.directories():
                self._watcher.addPath(str(candidate))

    @Slot()
    def _reload(self) -> None:
        fresh = load_colors()
        self._watch()  # the file is replaced on theme change, so re-arm the watch
        if fresh != self._colors:
            self._colors = fresh
            self.apply()
            self.changed.emit()

    def apply(self) -> None:
        if self._app is not None:
            self._app.setPalette(build_palette(self._colors))

    def color(self, key: str) -> str:
        return self._colors.get(key, FALLBACK.get(key, "#000000"))

    @Property(bool, notify=changed)
    def isDark(self) -> bool:  # noqa: N802 - QML property name
        return self._colors.get("mode", "dark") != "light"

    @Property(str, notify=changed)
    def uiFont(self) -> str:  # noqa: N802
        return QFont().family() or "sans-serif"

    @Property(str, notify=changed)
    def monoFont(self) -> str:  # noqa: N802
        return os.environ.get("OMARCHY_DB_MONO_FONT", "JetBrainsMono Nerd Font")

    @Property(str, notify=changed)
    def accent(self) -> str:  # noqa: N802
        return self.color("accent")

    @Property(str, notify=changed)
    def selection(self) -> str:  # noqa: N802
        return self.color("selection")

    @Property(str, notify=changed)
    def muted(self) -> str:  # noqa: N802
        return self.color("muted")

    @Property(str, notify=changed)
    def background(self) -> str:  # noqa: N802
        return self.color("background")

    @Property(str, notify=changed)
    def darkBackground(self) -> str:  # noqa: N802
        return self.color("dark_background")

    @Property(str, notify=changed)
    def darkerBackground(self) -> str:  # noqa: N802
        return self.color("darker_background")

    @Property(str, notify=changed)
    def lighterBackground(self) -> str:  # noqa: N802
        return self.color("lighter_background")

    @Property(str, notify=changed)
    def foreground(self) -> str:  # noqa: N802
        return self.color("foreground")

    @Property(str, notify=changed)
    def darkForeground(self) -> str:  # noqa: N802
        return self.color("dark_foreground")

    @Property(str, notify=changed)
    def lightForeground(self) -> str:  # noqa: N802
        return self.color("light_foreground")

    @Property(str, notify=changed)
    def brightForeground(self) -> str:  # noqa: N802
        return self.color("bright_foreground")

    @Property(str, notify=changed)
    def red(self) -> str:  # noqa: N802
        return self.color("red")

    @Property(str, notify=changed)
    def yellow(self) -> str:  # noqa: N802
        return self.color("yellow")

    @Property(str, notify=changed)
    def green(self) -> str:  # noqa: N802
        return self.color("green")

    @Property(str, notify=changed)
    def blue(self) -> str:  # noqa: N802
        return self.color("blue")
