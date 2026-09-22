import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Report designer lite: pick columns, a title, the page; see it; print it or
// save a PDF. The preview is the real thing — the same pages that print.
Dialog {
    id: dialog
    objectName: "reportDialog"
    property string table: ""
    property var allFields: []          // [{name, label, type}]
    property var picked: []             // field names in order
    property int page: 0
    property bool ready: false

    function openFor(theTable, fields) {
        table = theTable
        allFields = fields
        picked = fields.map(f => f.name)
        titleField.text = theTable.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase())
        nameField.text = ""
        sizeBox.currentIndex = 0
        landscapeBox.checked = false
        fitBox.checked = true
        numbersBox.checked = false
        marginsBox.value = 15
        fontBox.value = 10
        page = 0
        ready = true
        rebuild()
        open()
    }

    function loadKept(name) {
        const r = Report.load(name)
        if (!r.ok) { toast.show(r.error); return }
        const s = r.spec
        table = s.table
        picked = s.columns
        titleField.text = s.title
        nameField.text = s.name
        sizeBox.currentIndex = Math.max(0, Report.pageSizes().indexOf(s.page_size))
        landscapeBox.checked = s.orientation === "landscape"
        fitBox.checked = s.fit_to_width
        numbersBox.checked = s.show_row_numbers
        marginsBox.value = s.margins_mm
        fontBox.value = s.font_pt
        page = 0
        preview.source = Report.previewSource(0)
    }

    function currentSpec() {
        return {
            "table": table,
            "title": titleField.text,
            "columns": picked,
            "page_size": Report.pageSizes()[sizeBox.currentIndex],
            "orientation": landscapeBox.checked ? "landscape" : "portrait",
            "margins_mm": marginsBox.value,
            "fit_to_width": fitBox.checked,
            "font_pt": fontBox.value,
            "show_row_numbers": numbersBox.checked,
            "name": nameField.text
        }
    }

    function rebuild() {
        if (!ready) return
        const r = Report.build(currentSpec())
        if (r.ok) {
            page = Math.min(page, Math.max(0, r.pages - 1))
            preview.source = Report.previewSource(page)
        }
    }

    // Any change waits a moment, then relays out the whole report.
    Timer { id: settle; interval: 250; onTriggered: dialog.rebuild() }
    function touched() { settle.restart() }

    function toggle(name, on) {
        let next = picked.filter(n => n !== name)
        if (on) {
            // keep table order
            next = allFields.map(f => f.name).filter(n => n === name || next.indexOf(n) >= 0)
        }
        picked = next
        touched()
    }

    title: "Print " + (table || "a table")
    modal: true
    anchors.centerIn: parent
    width: Math.min(parent.width - 40, 1180)
    height: Math.min(parent.height - 40, 780)
    padding: 20
    closePolicy: Popup.CloseOnEscape
    Overlay.modal: Rectangle { color: Theme.isDark ? "#99000000" : "#55000000" }

    contentItem: RowLayout {
        spacing: 20

        // ---- settings -------------------------------------------------------
        ScrollView {
            Layout.preferredWidth: 340
            Layout.fillHeight: true
            clip: true
            contentWidth: availableWidth

            ColumnLayout {
                width: parent.width
                spacing: 10

                Label { text: "Title"; font.bold: true }
                TextField { id: titleField; Layout.fillWidth: true; onTextEdited: dialog.touched() }

                Label { text: "Columns"; font.bold: true; Layout.topMargin: 6 }
                Repeater {
                    model: dialog.allFields
                    delegate: CheckBox {
                        required property var modelData
                        text: modelData.label
                        checked: dialog.picked.indexOf(modelData.name) >= 0
                        onToggled: dialog.toggle(modelData.name, checked)
                    }
                }

                Label { text: "Page"; font.bold: true; Layout.topMargin: 6 }
                RowLayout {
                    ComboBox {
                        id: sizeBox
                        Layout.preferredWidth: 130
                        model: ["Letter", "A4", "Legal"]
                        onActivated: dialog.touched()
                    }
                    CheckBox { id: landscapeBox; text: "Sideways (landscape)"; onToggled: dialog.touched() }
                }
                CheckBox { id: fitBox; text: "Fit the table to the page width"; onToggled: dialog.touched() }
                CheckBox { id: numbersBox; text: "Number the rows"; onToggled: dialog.touched() }
                RowLayout {
                    Label { text: "Margins (mm)" }
                    SpinBox { id: marginsBox; from: 5; to: 40; value: 15; onValueModified: dialog.touched() }
                }
                RowLayout {
                    Label { text: "Text size" }
                    SpinBox { id: fontBox; from: 6; to: 16; value: 10; onValueModified: dialog.touched() }
                }

                Label { text: "Keep this report"; font.bold: true; Layout.topMargin: 6 }
                RowLayout {
                    TextField { id: nameField; Layout.fillWidth: true; placeholderText: "A name, like Monthly list" }
                    ActionButton {
                        text: "Keep"
                        enabled: nameField.text.trim() !== ""
                        onClicked: { dialog.rebuild(); const r = Report.keep(nameField.text.trim()); if (!r.ok) toast.show(r.error); keptRepeater.model = Report.kept() }
                    }
                }
                Repeater {
                    id: keptRepeater
                    model: Report.kept()
                    delegate: ItemDelegate {
                        required property var modelData
                        Layout.fillWidth: true
                        text: modelData.name + "  ·  " + modelData.table
                        onClicked: dialog.loadKept(modelData.name)
                    }
                }

                Label {
                    Layout.fillWidth: true
                    visible: Report.error !== ""
                    text: Report.error
                    color: Theme.red
                    wrapMode: Text.WordWrap
                }
            }
        }

        // ---- preview -----------------------------------------------------------
        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 8

            RowLayout {
                Layout.fillWidth: true
                ActionButton { text: "‹"; enabled: dialog.page > 0; onClicked: { dialog.page--; preview.source = Report.previewSource(dialog.page) } }
                ActionButton { text: "›"; enabled: dialog.page < Report.pageCount - 1; onClicked: { dialog.page++; preview.source = Report.previewSource(dialog.page) } }
                Label {
                    text: Report.pageCount > 0
                        ? "Page " + (dialog.page + 1) + " of " + Report.pageCount + "  ·  " + Report.rowCount + " rows"
                        : ""
                    font.bold: true
                }
                Item { Layout.fillWidth: true }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                color: Theme.isDark ? Theme.darkerBackground : Theme.lighterBackground
                radius: 6
                clip: true
                Image {
                    id: preview
                    anchors.fill: parent
                    anchors.margins: 12
                    fillMode: Image.PreserveAspectFit
                    smooth: true
                    cache: false
                    sourceSize.width: 1000
                }
            }
        }
    }

    footer: DialogButtonBox {
        ActionButton { text: "Close"; onClicked: dialog.close() }
        ActionButton {
            text: "Save PDF…"
            enabled: Report.pageCount > 0
            onClicked: { dialog.rebuild(); pdfDialog.selectedFile = Bridge.documentsFolder() + "/" + (titleField.text || table).replace(/[\/\\]/g, "-") + ".pdf"; pdfDialog.open() }
        }
        ActionButton {
            text: "Print…"
            primary: true
            enabled: Report.pageCount > 0
            onClicked: { dialog.rebuild(); const r = Report.printReport(); if (!r.ok && !r.cancelled) toast.show(r.error) }
        }
    }
}
