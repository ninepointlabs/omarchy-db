"""The Jubako desktop app: a Qt Quick / QML window over the Python core.

`main.py` is the smallest host that can run QML on Omarchy: PySide6 starts a
`QGuiApplication`, loads `qml/Main.qml`, and hands the QML two objects —
`Bridge` (the only way the window touches the database library) and `Theme`
(the Omarchy colours). Nothing about databases is written in QML or C++.
"""
