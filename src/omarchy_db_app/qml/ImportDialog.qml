import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// The import wizard: what the spreadsheet will become, with the guesses open
// to change. One screen, one button.
Dialog {
    id: dialog
    objectName: "importDialog"
    property string spreadsheet: ""
    property var plan: ({})
    property var fieldTypes: Bridge.fieldTypes()
    property var chosen: []            // [{name, label, type}]
    property string error: ""
    property bool everySheet: false     // off by default: one sheet, one table
    property var sheetPlan: []          // [{sheet, table, exists}] for the every-sheet path

    function openFor(url) {
        spreadsheet = url
        error = ""
        everySheet = false
        everyBox.checked = false
        sheetPlan = []
        replan("")
        open()
    }

    function replan(sheet) {
        const p = Bridge.planImport(spreadsheet, sheet)
        if (!p.ok) { error = p.error; plan = {}; chosen = []; return }
        plan = p
        error = ""
        chosen = p.fields.map(f => ({ "name": f.name, "label": f.label, "type": f.type }))
        tableField.text = p.table
        sheetBox.model = p.sheets
        sheetBox.currentIndex = Math.max(0, p.sheets.indexOf(p.sheet))
        columnsRepeater.model = []
        columnsRepeater.model = chosen
    }

    function setType(index, type) {
        const next = chosen.slice()
        next[index] = Object.assign({}, next[index], { "type": type })
        chosen = next
    }

    property bool working: false

    function go(replace) {
        const r = everySheet
            ? Bridge.importAllSheets(spreadsheet, replace)
            : Bridge.importPlanned(spreadsheet, plan.sheet || "", tableField.text, chosen, replace)
        if (r.ok && r.pending) { working = true; return }
        finished(r)
    }

    function finished(r) {
        working = false
        if (r.ok) {
            if (r.errors && r.errors.length > 0) toast.show("Skipped: " + r.errors.join("  "))
            close()
            return
        }
        if (r.needsConfirm) {
            replaceDialog.table = r.table
            replaceDialog.tables = r.tables || [r.table]
            replaceDialog.spreadsheet = spreadsheet
            replaceDialog.fromWizard = true
            replaceDialog.open()
            return
        }
        error = r.error
    }

    Connections {
        target: Bridge
        function onImportFinished(r) { if (dialog.working) dialog.finished(r) }
    }

    title: "Import a spreadsheet"
    modal: true
    anchors.centerIn: parent
    width: Math.min(parent.width - 40, 760)
    height: Math.min(parent.height - 40, 640)
    padding: 20
    closePolicy: working ? Popup.NoAutoClose : Popup.CloseOnEscape
    Overlay.modal: Rectangle { color: Theme.isDark ? "#99000000" : "#55000000" }

    contentItem: ColumnLayout {
        spacing: 12

        Label {
            Layout.fillWidth: true
            text: (plan.file || Bridge.localPath(spreadsheet))
            color: Theme.lightForeground
            elide: Text.ElideMiddle
        }

        CheckBox {
            id: everyBox
            visible: (plan.sheets || []).length > 1
            text: "Import every sheet as its own table"
            checked: dialog.everySheet
            onToggled: {
                dialog.everySheet = checked
                if (checked) dialog.sheetPlan = Bridge.workbookPlan(dialog.spreadsheet)
            }
        }

        // ---- every sheet: what each one becomes ------------------------------
        ColumnLayout {
            Layout.fillWidth: true
            visible: dialog.everySheet
            spacing: 4
            Label {
                text: "Each sheet becomes a table named after it, using guessed types."
                color: Theme.lightForeground
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }
            Repeater {
                model: dialog.sheetPlan
                delegate: RowLayout {
                    required property var modelData
                    Layout.fillWidth: true
                    spacing: 12
                    Label { Layout.preferredWidth: 220; text: modelData.sheet; elide: Text.ElideRight; font.pointSize: 12 }
                    Label { text: "\u2192  " + modelData.table; font.family: Theme.monoFont }
                    Label { text: modelData.exists ? "(replaces the table there now)" : ""; color: Theme.yellow; font.pointSize: 10 }
                }
            }
        }

        GridLayout {
            Layout.fillWidth: true
            visible: !dialog.everySheet
            columns: 2
            columnSpacing: 12
            rowSpacing: 8
            Label { text: "Sheet"; visible: (plan.sheets || []).length > 1 }
            ComboBox {
                id: sheetBox
                Layout.preferredWidth: 260
                visible: (plan.sheets || []).length > 1
                onActivated: dialog.replan(currentText)
            }
            Label { text: "Table name" }
            TextField { id: tableField; Layout.fillWidth: true }
        }

        Label {
            visible: !dialog.everySheet
            text: "Each column becomes a field. Change a guess if it is wrong."
            font.bold: true
            Layout.topMargin: 4
        }

        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: !dialog.everySheet
            clip: true
            contentWidth: availableWidth
            ColumnLayout {
                width: parent.width
                spacing: 4
                Repeater {
                    id: columnsRepeater
                    delegate: RowLayout {
                        required property var modelData
                        required property int index
                        Layout.fillWidth: true
                        spacing: 12
                        Label {
                            Layout.preferredWidth: 220
                            text: modelData.label
                            elide: Text.ElideRight
                            font.pointSize: 12
                        }
                        ComboBox {
                            Layout.preferredWidth: 220
                            model: dialog.fieldTypes
                            textRole: "label"
                            valueRole: "key"
                            currentIndex: Math.max(0, dialog.fieldTypes.findIndex(t => t.key === modelData.type))
                            onActivated: dialog.setType(index, currentValue)
                        }
                        Label {
                            Layout.fillWidth: true
                            text: ((plan.sample_rows || []).slice(0, 3).map(r => r[index] || "·")).join(",  ")
                            color: Theme.lightForeground
                            font.pointSize: 10
                            elide: Text.ElideRight
                        }
                    }
                }
            }
        }

        RowLayout {
            visible: dialog.working
            BusyIndicator { running: dialog.working; implicitWidth: 28; implicitHeight: 28 }
            Label { text: Bridge.busyText || "Importing…"; color: Theme.lightForeground }
        }
        Item { Layout.fillHeight: true; visible: dialog.everySheet }
        Label {
            visible: !dialog.everySheet
            text: plan.rows_sampled !== undefined
                ? (plan.rows_sampled >= 500 ? "Looked at the first 500 rows." : plan.rows_sampled + " rows.")
                : ""
            color: Theme.lightForeground
            font.pointSize: 10
        }
        Label {
            Layout.fillWidth: true
            visible: dialog.error !== ""
            text: dialog.error
            color: Theme.red
            wrapMode: Text.WordWrap
        }
    }

    footer: DialogButtonBox {
        ActionButton { text: "Cancel"; enabled: !dialog.working; onClicked: dialog.reject() }
        ActionButton {
            text: dialog.everySheet
                ? "Import " + dialog.sheetPlan.length + " sheets"
                : (plan.exists && tableField.text === plan.table ? "Import (replaces the table)" : "Import")
            primary: true
            enabled: dialog.error === "" && (dialog.everySheet ? dialog.sheetPlan.length > 0 : chosen.length > 0) && !dialog.working
            onClicked: dialog.go(false)
        }
    }
}
