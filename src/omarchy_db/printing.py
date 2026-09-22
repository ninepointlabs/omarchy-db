"""Draw a report onto pages: PDF, the system printer, or a preview picture.

This is the one part of the core that needs Qt (PySide6), and only when a
report is actually rendered. The same `ReportDocument` paints every target,
so what you preview is what you print.

Units are points (1/72 inch) throughout; the painter is scaled to match.
"""

from __future__ import annotations

import datetime as _dt
import os
import sys
from typing import Any

from .errors import OmarchyDBError
from .reports import fit_columns, page_points

MM_TO_PT = 72.0 / 25.4
CELL_PAD = 4.0
MIN_COLUMN_PT = 36.0


def _qt():
    try:
        from PySide6 import QtCore, QtGui  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - depends on the machine
        raise OmarchyDBError(
            "Making a PDF or printing needs Qt (the 'pyside6' package)."
        ) from exc
    return QtCore, QtGui


def ensure_gui_app():
    """A QGuiApplication must exist to measure fonts. Make an offscreen one if needed."""
    QtCore, QtGui = _qt()
    app = QtGui.QGuiApplication.instance()
    if app is None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        app = QtGui.QGuiApplication(sys.argv[:1] or ["omarchy-db"])
    return app


class ReportDocument:
    """A laid-out report: knows its pages and how to paint each one."""

    def __init__(self, spec: dict[str, Any], rows: list[list[str]]) -> None:
        ensure_gui_app()
        QtCore, QtGui = _qt()
        self.spec = spec
        self.rows = rows
        self.labels = list(spec["labels"])
        if spec.get("show_row_numbers"):
            self.labels = ["#"] + self.labels
            self.rows = [[str(i + 1)] + row for i, row in enumerate(rows)]

        self.page_w, self.page_h = page_points(spec)
        margin = spec["margins_mm"] * MM_TO_PT
        self.content = QtCore.QRectF(margin, margin, self.page_w - 2 * margin, self.page_h - 2 * margin)

        # Pixel sizes, not point sizes: the painter is scaled so one unit is one
        # point on every target, and a pixel-size font ignores the device's DPI.
        # So "10pt" measures and paints the same on paper, in a PDF and on screen.
        self.font = QtGui.QFont()
        self.font.setPixelSize(int(round(spec["font_pt"])))
        self.bold = QtGui.QFont(self.font)
        self.bold.setBold(True)
        self.title_font = QtGui.QFont(self.bold)
        self.title_font.setPixelSize(int(round(spec["font_pt"] + 5)))
        self.small = QtGui.QFont(self.font)
        self.small.setPixelSize(int(round(max(6.0, spec["font_pt"] - 2))))

        self._layout()

    # -- layout ------------------------------------------------------------
    def _layout(self) -> None:
        QtCore, QtGui = _qt()
        metrics = QtGui.QFontMetricsF(self.font)
        bold_metrics = QtGui.QFontMetricsF(self.bold)
        count = len(self.labels)
        natural = [bold_metrics.horizontalAdvance(label) + 2 * CELL_PAD for label in self.labels]
        minimum = [min(natural[i], MIN_COLUMN_PT) for i in range(count)]
        for row in self.rows[:2000]:
            for i, text in enumerate(row[:count]):
                natural[i] = max(natural[i], metrics.horizontalAdvance(text) + 2 * CELL_PAD)
                longest_word = max((metrics.horizontalAdvance(w) for w in text.split()), default=0.0)
                minimum[i] = max(minimum[i], min(longest_word + 2 * CELL_PAD, 120.0))
        self.widths = fit_columns(natural, minimum, self.content.width(), fit=self.spec["fit_to_width"])
        self.table_width = sum(self.widths)

        self.line_h = metrics.height()
        self.title_h = QtGui.QFontMetricsF(self.title_font).height() + 8
        self.header_h = bold_metrics.height() + 2 * CELL_PAD
        self.footer_h = QtGui.QFontMetricsF(self.small).height() + 6

        # Row heights: wrapped text, so a long cell makes its row taller.
        self.row_heights: list[float] = []
        flags = int(QtCore.Qt.TextFlag.TextWordWrap)
        for row in self.rows:
            tallest = self.line_h
            for i, text in enumerate(row[:count]):
                if not text:
                    continue
                rect = QtCore.QRectF(0, 0, max(1.0, self.widths[i] - 2 * CELL_PAD), 10000)
                needed = metrics.boundingRect(rect, flags, text).height()
                tallest = max(tallest, needed)
            self.row_heights.append(tallest + 2 * CELL_PAD)

        # Pages: which rows go on which page. The title is on page one only.
        self.pages: list[tuple[int, int]] = []
        start = 0
        first = True
        total = len(self.rows)
        while start < total or first:
            top = self.content.top() + (self.title_h if first else 0) + self.header_h
            bottom = self.content.bottom() - self.footer_h
            end = start
            used = top
            while end < total and used + self.row_heights[end] <= bottom:
                used += self.row_heights[end]
                end += 1
            if end == start and start < total:
                end = start + 1  # a single row taller than the page still goes somewhere
            self.pages.append((start, end))
            start = end
            first = False

    @property
    def page_count(self) -> int:
        return len(self.pages)

    # -- painting ------------------------------------------------------------
    def paint_page(self, painter, page_index: int) -> None:
        """Paint one page. The painter must already be in points."""
        QtCore, QtGui = _qt()
        Qt = QtCore.Qt
        start, end = self.pages[page_index]
        fg = QtGui.QColor("#111111")
        rule = QtGui.QColor("#9a9a9a")
        band = QtGui.QColor("#e6e6e6")
        stripe = QtGui.QColor("#f4f4f4")
        painter.setPen(QtGui.QPen(fg))

        x0 = self.content.left()
        y = self.content.top()
        if page_index == 0:
            painter.setFont(self.title_font)
            painter.drawText(
                QtCore.QRectF(x0, y, self.content.width(), self.title_h),
                int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                self.spec["title"],
            )
            y += self.title_h

        # Header band
        painter.fillRect(QtCore.QRectF(x0, y, self.table_width, self.header_h), band)
        painter.setFont(self.bold)
        x = x0
        for width, label in zip(self.widths, self.labels):
            painter.drawText(
                QtCore.QRectF(x + CELL_PAD, y, max(1.0, width - 2 * CELL_PAD), self.header_h),
                int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                label,
            )
            x += width
        painter.setPen(QtGui.QPen(rule, 0.8))
        painter.drawLine(QtCore.QPointF(x0, y + self.header_h), QtCore.QPointF(x0 + self.table_width, y + self.header_h))
        y += self.header_h

        painter.setFont(self.font)
        flags = int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap)
        for index in range(start, end):
            height = self.row_heights[index]
            if (index - start) % 2 == 1:
                painter.fillRect(QtCore.QRectF(x0, y, self.table_width, height), stripe)
            painter.setPen(QtGui.QPen(fg))
            x = x0
            for width, text in zip(self.widths, self.rows[index]):
                if text:
                    painter.drawText(
                        QtCore.QRectF(x + CELL_PAD, y + CELL_PAD, max(1.0, width - 2 * CELL_PAD), height - 2 * CELL_PAD),
                        flags,
                        text,
                    )
                x += width
            painter.setPen(QtGui.QPen(rule, 0.4))
            painter.drawLine(QtCore.QPointF(x0, y + height), QtCore.QPointF(x0 + self.table_width, y + height))
            y += height

        if not self.rows and page_index == 0:
            painter.setPen(QtGui.QPen(fg))
            painter.drawText(
                QtCore.QRectF(x0, y + 8, self.content.width(), self.line_h * 2),
                int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop),
                "This table has no rows yet.",
            )

        # Footer
        painter.setFont(self.small)
        painter.setPen(QtGui.QPen(QtGui.QColor("#555555")))
        footer = QtCore.QRectF(x0, self.content.bottom() - self.footer_h, self.content.width(), self.footer_h)
        painter.drawText(footer, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom),
                         f"{self.spec['title']}  ·  {_dt.date.today().isoformat()}")
        painter.drawText(footer, int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom),
                         f"Page {page_index + 1} of {self.page_count}")

    # -- targets ------------------------------------------------------------
    def _page_layout(self):
        QtCore, QtGui = _qt()
        size_id = {"letter": QtGui.QPageSize.PageSizeId.Letter, "a4": QtGui.QPageSize.PageSizeId.A4,
                   "legal": QtGui.QPageSize.PageSizeId.Legal}[self.spec["page_size"]]
        orientation = (QtGui.QPageLayout.Orientation.Landscape if self.spec["orientation"] == "landscape"
                       else QtGui.QPageLayout.Orientation.Portrait)
        # Margins are painted by us, so the device gets none.
        return QtGui.QPageLayout(QtGui.QPageSize(size_id), orientation, QtCore.QMarginsF(0, 0, 0, 0),
                                 QtGui.QPageLayout.Unit.Point)

    def paint_to_device(self, device) -> int:
        """Paint every page onto a paged device (QPdfWriter or QPrinter) already set up."""
        QtCore, QtGui = _qt()
        painter = QtGui.QPainter()
        if not painter.begin(device):
            raise OmarchyDBError("Could not start drawing on that printer or file.")
        try:
            painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
            painter.setRenderHint(QtGui.QPainter.RenderHint.TextAntialiasing)
            # Device units -> points.
            scale = device.logicalDpiX() / 72.0
            for index in range(self.page_count):
                if index > 0:
                    device.newPage()
                painter.resetTransform()
                painter.scale(scale, scale)
                self.paint_page(painter, index)
        finally:
            painter.end()
        return self.page_count

    def write_pdf(self, path: str) -> int:
        QtCore, QtGui = _qt()
        writer = QtGui.QPdfWriter(path)
        writer.setTitle(self.spec["title"])
        writer.setCreator("Omarchy-DB")
        writer.setPageLayout(self._page_layout())
        writer.setResolution(300)
        return self.paint_to_device(writer)

    def print_to(self, printer) -> int:
        """`printer` is a QPrinter the caller (usually a print dialog) set up."""
        printer.setPageLayout(self._page_layout())
        printer.setDocName(self.spec["title"])
        return self.paint_to_device(printer)

    def preview_image(self, page_index: int, width_px: int = 900):
        """One page as a QImage, for the preview on screen."""
        QtCore, QtGui = _qt()
        scale = width_px / self.page_w
        image = QtGui.QImage(int(self.page_w * scale), int(self.page_h * scale),
                             QtGui.QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(QtGui.QColor("white"))
        painter = QtGui.QPainter(image)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QtGui.QPainter.RenderHint.TextAntialiasing)
        painter.scale(scale, scale)
        self.paint_page(painter, max(0, min(page_index, self.page_count - 1)))
        painter.end()
        return image
