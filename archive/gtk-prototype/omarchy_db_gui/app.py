"""The Jubako window.

Phase A is deliberately small: open a database, see its tables, see the rows.
Making a database and importing a spreadsheet are here too, because a first
run with nothing to open should still get somewhere.

GTK4 + Libadwaita, so it follows the system light/dark preference and the
Omarchy theme's fonts without any theming code of our own.
"""

from __future__ import annotations

import sys
from typing import Any

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

from jubako import __version__, catalog  # noqa: E402
from jubako.errors import JubakoError  # noqa: E402
from jubako.importer import import_spreadsheet, plan_import  # noqa: E402
from jubako.paths import default_documents_dir  # noqa: E402
from jubako.storage import BACKENDS, SQLITE, create_database, open_database  # noqa: E402

APP_ID = "org.ninepointlabs.OmarchyDB"
PAGE_SIZE = 200


class Window(Adw.ApplicationWindow):
    """One window: the list of tables on the left, the rows on the right."""

    def __init__(self, application: Adw.Application) -> None:
        super().__init__(application=application, title="Jubako", default_width=1000,
                         default_height=680)
        self.storage: Any = None
        self.current_table: str | None = None

        self.toasts = Adw.ToastOverlay()
        self.set_content(self.toasts)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.toasts.set_child(root)

        header = Adw.HeaderBar()
        root.append(header)

        new_button = Gtk.Button(label="New database")
        new_button.add_css_class("suggested-action")
        new_button.connect("clicked", self.on_new_database)
        header.pack_start(new_button)

        open_button = Gtk.Button(label="Open")
        open_button.connect("clicked", self.on_open_database)
        header.pack_start(open_button)

        self.import_button = Gtk.Button(label="Import spreadsheet")
        self.import_button.connect("clicked", self.on_import)
        self.import_button.set_sensitive(False)
        header.pack_end(self.import_button)

        self.title_widget = Adw.WindowTitle(title="Jubako", subtitle="No database open")
        header.set_title_widget(self.title_widget)

        self.split = Adw.NavigationSplitView()
        self.split.set_vexpand(True)
        root.append(self.split)

        self.table_list = Gtk.ListBox()
        self.table_list.add_css_class("navigation-sidebar")
        self.table_list.connect("row-selected", self.on_table_selected)
        sidebar_scroll = Gtk.ScrolledWindow(child=self.table_list, vexpand=True)
        self.split.set_sidebar(
            Adw.NavigationPage(title="Tables", child=_with_header("Tables", sidebar_scroll))
        )

        self.content_stack = Gtk.Stack()
        self.content_stack.add_named(self._welcome(), "welcome")
        self.grid_scroll = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
        self.content_stack.add_named(self.grid_scroll, "grid")
        self.content_stack.set_visible_child_name("welcome")
        self.split.set_content(
            Adw.NavigationPage(title="Rows", child=_with_header("Rows", self.content_stack))
        )

        self._load_recent()

    # -- screens ---------------------------------------------------------
    def _welcome(self) -> Gtk.Widget:
        status = Adw.StatusPage(
            title="Open a database",
            description=(
                "Press New database to start one, or Open to use one you already made.\n"
                "Then Import spreadsheet turns a CSV into a table."
            ),
            icon_name="view-list-symbolic",
        )
        return status

    def _load_recent(self) -> None:
        entries = [e for e in catalog.recent(1) if e.get("backend") == SQLITE and e.get("path")]
        if entries:
            try:
                self.open_path(entries[0]["path"], quiet=True)
            except JubakoError:
                pass

    # -- actions ----------------------------------------------------------
    def on_new_database(self, _button: Gtk.Button) -> None:
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading="New database",
            body="Pick where your database lives. A file on this computer is the simple choice.",
        )
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin_top=8)
        group = None
        self._backend_buttons = {}
        for choice in BACKENDS:
            button = Gtk.CheckButton(label=choice.title)
            if group is None:
                group = button
                button.set_active(True)
            else:
                button.set_group(group)
            ready = choice.driver_installed()
            button.set_sensitive(ready)
            row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            row.append(button)
            blurb = choice.blurb if ready else f"{choice.blurb}  (needs {choice.driver_package})"
            label = Gtk.Label(label=blurb, wrap=True, xalign=0)
            label.add_css_class("dim-label")
            label.add_css_class("caption")
            label.set_margin_start(28)
            row.append(label)
            box.append(row)
            self._backend_buttons[choice.key] = button
        dialog.set_extra_child(box)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("next", "Next")
        dialog.set_response_appearance("next", Adw.ResponseAppearance.SUGGESTED)
        dialog.connect("response", self._on_backend_chosen)
        dialog.present()

    def _on_backend_chosen(self, dialog: Adw.MessageDialog, response: str) -> None:
        if response != "next":
            return
        picked = next(
            (key for key, button in self._backend_buttons.items() if button.get_active()), SQLITE
        )
        if picked != SQLITE:
            self.toast(
                "Server databases are set up from the command line or an agent in this version."
            )
            return
        chooser = Gtk.FileDialog(title="Save the new database")
        chooser.set_initial_name("my-database.jubadb")
        chooser.set_initial_folder(Gio.File.new_for_path(str(default_documents_dir())))
        chooser.save(self, None, self._on_new_path)

    def _on_new_path(self, dialog: Gtk.FileDialog, result: Gio.AsyncResult) -> None:
        try:
            file = dialog.save_finish(result)
        except GLib.Error:
            return
        path = file.get_path()
        try:
            storage = create_database(title="", backend=SQLITE, path=path, overwrite=True)
        except JubakoError as error:
            self.toast(str(error))
            return
        self._adopt(storage)
        self.toast("New database made. Now import a spreadsheet.")

    def on_open_database(self, _button: Gtk.Button) -> None:
        chooser = Gtk.FileDialog(title="Open a database")
        chooser.set_initial_folder(Gio.File.new_for_path(str(default_documents_dir())))
        chooser.open(self, None, self._on_open_path)

    def _on_open_path(self, dialog: Gtk.FileDialog, result: Gio.AsyncResult) -> None:
        try:
            file = dialog.open_finish(result)
        except GLib.Error:
            return
        self.open_path(file.get_path())

    def open_path(self, path: str, *, quiet: bool = False) -> None:
        try:
            storage = open_database(backend=SQLITE, path=path)
        except JubakoError as error:
            if not quiet:
                self.toast(str(error))
            return
        self._adopt(storage)

    def on_import(self, _button: Gtk.Button) -> None:
        if self.storage is None:
            return
        chooser = Gtk.FileDialog(title="Pick a spreadsheet")
        csv_filter = Gtk.FileFilter()
        csv_filter.set_name("Spreadsheets (CSV)")
        csv_filter.add_pattern("*.csv")
        csv_filter.add_pattern("*.tsv")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(csv_filter)
        chooser.set_filters(filters)
        chooser.open(self, None, self._on_import_path)

    def _on_import_path(self, dialog: Gtk.FileDialog, result: Gio.AsyncResult) -> None:
        try:
            file = dialog.open_finish(result)
        except GLib.Error:
            return
        path = file.get_path()
        try:
            plan = plan_import(path)
        except JubakoError as error:
            self.toast(str(error))
            return

        if self.storage.has_table(plan["table"]):
            self._confirm_replace(path, plan["table"])
            return
        self._do_import(path, if_exists="error")

    def _confirm_replace(self, path: str, table: str) -> None:
        """Never lose rows without asking first."""
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading=f"Replace the table “{table}”?",
            body="It is already in this database. Its rows will be thrown away.",
        )
        dialog.add_response("cancel", "Keep what I have")
        dialog.add_response("replace", "Replace it")
        dialog.set_response_appearance("replace", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.connect(
            "response",
            lambda _d, answer: self._do_import(path, if_exists="replace")
            if answer == "replace"
            else None,
        )
        dialog.present()

    def _do_import(self, path: str, *, if_exists: str) -> None:
        try:
            report = import_spreadsheet(self.storage, path, if_exists=if_exists)
        except JubakoError as error:
            self.toast(str(error))
            return
        self.refresh_tables()
        self.toast(f"Added {report['rows_added']} rows to {report['table']}.")

    # -- showing things ----------------------------------------------------
    def _adopt(self, storage: Any) -> None:
        if self.storage is not None:
            try:
                self.storage.close()
            except Exception:  # noqa: BLE001 - closing a stale handle must not stop us
                pass
        self.storage = storage
        info = storage.describe()
        catalog.remember(
            title=info.title,
            backend=info.backend,
            path=info.location if info.backend == SQLITE else "",
            where="" if info.backend == SQLITE else info.location,
        )
        self.title_widget.set_title(info.title)
        self.title_widget.set_subtitle(info.location)
        self.import_button.set_sensitive(True)
        self.refresh_tables()

    def refresh_tables(self) -> None:
        while (row := self.table_list.get_row_at_index(0)) is not None:
            self.table_list.remove(row)
        names = self.storage.list_tables() if self.storage else []
        for name in names:
            info = self.storage.describe_table(name)
            row = Adw.ActionRow(title=name, subtitle=f"{info.row_count} rows")
            row.table_name = name
            self.table_list.append(row)
        if names:
            self.table_list.select_row(self.table_list.get_row_at_index(0))
        else:
            self.content_stack.set_visible_child_name("welcome")

    def on_table_selected(self, _list: Gtk.ListBox, row: Gtk.ListBoxRow | None) -> None:
        if row is None or self.storage is None:
            return
        self.show_table(getattr(row, "table_name", ""))

    def show_table(self, table: str) -> None:
        try:
            page = self.storage.list_rows(table, limit=PAGE_SIZE)
        except JubakoError as error:
            self.toast(str(error))
            return
        self.current_table = table
        self.grid_scroll.set_child(_build_grid(page))
        self.content_stack.set_visible_child_name("grid")

    def toast(self, text: str) -> None:
        self.toasts.add_toast(Adw.Toast(title=text, timeout=4))


def _with_header(title: str, child: Gtk.Widget) -> Gtk.Widget:
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    box.append(Adw.HeaderBar(title_widget=Adw.WindowTitle(title=title)))
    child.set_vexpand(True)
    box.append(child)
    return box


def _cell_text(value: Any, kind: str | None) -> str:
    """What one cell reads as. Yes/no fields say Yes and No, not True and False."""
    if value is None:
        return ""
    if kind == "boolean":
        return "Yes" if value else "No"
    return str(value)


def _build_grid(page: dict[str, Any]) -> Gtk.Widget:
    """A plain grid of the rows. Read-only in Phase A; editing is Phase B."""
    grid = Gtk.Grid(column_spacing=18, row_spacing=6, margin_top=12, margin_bottom=12,
                    margin_start=12, margin_end=12)
    headings = ["id"] + [field["label"] for field in page["fields"]]
    for column, heading in enumerate(headings):
        label = Gtk.Label(label=heading, xalign=0)
        label.add_css_class("heading")
        grid.attach(label, column, 0, 1, 1)

    kinds = [None] + [field["type"] for field in page["fields"]]
    for row_index, row in enumerate(page["rows"], start=1):
        for column, value in enumerate(row):
            text = _cell_text(value, kinds[column] if column < len(kinds) else None)
            label = Gtk.Label(label=text, xalign=0, selectable=True)
            label.set_ellipsize(3)  # PANGO_ELLIPSIZE_END
            label.set_max_width_chars(40)
            grid.attach(label, column, row_index, 1, 1)

    if not page["rows"]:
        return Adw.StatusPage(
            title="No rows yet",
            description="This table is empty. Import a spreadsheet to fill it.",
            icon_name="view-list-symbolic",
        )

    footer = Gtk.Label(
        label=f"Showing {len(page['rows'])} of {page['total']} rows", xalign=0
    )
    footer.add_css_class("dim-label")
    footer.set_margin_top(12)
    grid.attach(footer, 0, len(page["rows"]) + 1, max(1, len(headings)), 1)
    return grid


class Application(Adw.Application):
    def __init__(self) -> None:
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_OPEN)
        self.connect("open", self._on_open_files)

    def do_activate(self) -> None:
        window = self.props.active_window or Window(self)
        window.present()

    def _on_open_files(
        self, _app: Adw.Application, files: list[Gio.File], _count: int, _hint: str
    ) -> None:
        window = self.props.active_window or Window(self)
        if files:
            window.open_path(files[0].get_path())
        window.present()


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    return Application().run(argv)


if __name__ == "__main__":
    raise SystemExit(main())
