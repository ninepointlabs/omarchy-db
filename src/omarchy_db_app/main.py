"""Start the window: the smallest host that runs QML on Omarchy.

    omarchy-db-app                         # the home screen
    omarchy-db-app ~/Documents/pets.omadb  # open a database straight away
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

from omarchy_db import __version__

from .bridge import Bridge
from .theme import Theme

QML_DIR = Path(__file__).resolve().parent / "qml"
APP_ID = "omarchy-db"


def make_app(argv: list[str]) -> QGuiApplication:
    # Fusion is the one built-in Qt Quick style that paints from the palette,
    # which is how the Omarchy theme colours reach every control.
    os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Fusion")
    QQuickStyle.setStyle(os.environ["QT_QUICK_CONTROLS_STYLE"])
    app = QGuiApplication(argv)
    app.setApplicationName("Omarchy-DB")
    app.setApplicationDisplayName("Omarchy-DB")
    app.setOrganizationName("Nine Point Labs")
    app.setOrganizationDomain("ninepointlabs.com")
    app.setApplicationVersion(__version__)
    # On Wayland this is the app id Hyprland sees, so it must match the .desktop name.
    app.setDesktopFileName(APP_ID)
    icon = Path(__file__).resolve().parents[2] / "packaging" / "omarchy-db.svg"
    app.setWindowIcon(QIcon.fromTheme(APP_ID, QIcon(str(icon))))
    return app


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    app = make_app(argv)
    theme = Theme(app)
    bridge = Bridge()

    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("Bridge", bridge)
    engine.rootContext().setContextProperty("Theme", theme)
    engine.load(QUrl.fromLocalFile(str(QML_DIR / "Main.qml")))
    if not engine.rootObjects():
        print("Omarchy-DB could not load its window.", file=sys.stderr)
        return 1

    for arg in argv[1:]:
        if not arg.startswith("-"):
            result = bridge.openDatabase("sqlite", arg, {})
            if not result["ok"]:
                bridge.message.emit(result["error"])
            break

    code = app.exec()
    bridge.closeDatabase()
    return int(code)


if __name__ == "__main__":
    raise SystemExit(main())
