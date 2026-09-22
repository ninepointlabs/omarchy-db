# GTK prototype (archived)

This is the Phase A window: GTK4 + Libadwaita, in `omarchy_db_gui/`.

It was the wrong toolkit for the product. Tim wants Omarchy-DB as a Qt/QML
desktop application, which now lives in `src/omarchy_db_app/`. This copy is
kept for reference only: it is not installed, not tested, and not listed in
`pyproject.toml`.

To run it anyway (needs `python-gobject`, GTK 4 and Libadwaita):

```sh
PYTHONPATH=src:archive/gtk-prototype python -m omarchy_db_gui
```
