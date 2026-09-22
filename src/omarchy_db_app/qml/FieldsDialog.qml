import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// The fields of the open table: rename one, or delete one. Every row shows
// the label people see, the name inside the database, and the type.
Dialog {
    id: dialog
    objectName: "fieldsDialog"
    property string error: ""

    function openFor() { error = ""; open() }

    title: "Fields of " + Bridge.currentTable
    modal: true
    anchors.centerIn: parent
    width: Math.min(parent.width - 40, 820)
    height: Math.min(parent.height - 40, 560)
    padding: 20
    closePolicy: Popup.CloseOnEscape
    Overlay.modal: Rectangle { color: Theme.isDark ? "#99000000" : "#55000000" }

    contentItem: ColumnLayout {
        spacing: 10
        RowLayout {
            Layout.fillWidth: true
            spacing: 12
            Label { Layout.preferredWidth: 170; text: "Label"; font.bold: true; color: Theme.lightForeground; elide: Text.ElideRight }
            Label { Layout.preferredWidth: 150; text: "Name inside"; font.bold: true; color: Theme.lightForeground; elide: Text.ElideRight }
            Label { Layout.preferredWidth: 120; text: "Type"; font.bold: true; color: Theme.lightForeground; elide: Text.ElideRight }
            Item { Layout.fillWidth: true }
        }
        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            contentWidth: availableWidth
            ColumnLayout {
                width: parent.width
                spacing: 4
                Repeater {
                    model: Bridge.fields
                    delegate: RowLayout {
                        required property var modelData
                        Layout.fillWidth: true
                        spacing: 12
                        Label { Layout.preferredWidth: 170; Layout.maximumWidth: 170; text: modelData.label; elide: Text.ElideRight; font.pointSize: 12 }
                        Label { Layout.preferredWidth: 150; Layout.maximumWidth: 150; text: modelData.name; elide: Text.ElideRight; font.family: Theme.monoFont; color: Theme.lightForeground }
                        Label { Layout.preferredWidth: 120; Layout.maximumWidth: 120; text: typeWord(modelData.type); elide: Text.ElideRight; color: Theme.lightForeground }
                        Item { Layout.fillWidth: true }
                        ActionButton { text: "Rename…"; onClicked: renameDialog.openFor(modelData) }
                        ActionButton { text: "Delete…"; enabled: Bridge.fields.length > 1; onClicked: deleteConfirm.ask(modelData) }
                    }
                }
            }
        }
        Label {
            Layout.fillWidth: true
            visible: dialog.error !== ""
            text: dialog.error
            color: Theme.red
            wrapMode: Text.WordWrap
        }
    }

    function typeWord(kind) {
        const types = Bridge.fieldTypes()
        for (const t of types) if (t.key === kind) return t.label
        return kind
    }

    footer: DialogButtonBox {
        ActionButton { text: "Done"; primary: true; onClicked: dialog.close() }
    }

    // ---- rename one field ------------------------------------------------------
    Dialog {
        id: renameDialog
        property string oldName: ""
        property string renameError: ""
        function openFor(field) {
            oldName = field.name
            labelField.text = field.label
            nameField.text = field.name
            renameError = ""
            open()
            labelField.forceActiveFocus()
        }
        function go() {
            const r = Bridge.renameField(oldName, nameField.text.trim(), labelField.text.trim())
            if (r.ok) close(); else renameError = r.error
        }
        title: "Rename “" + oldName + "”"
        modal: true
        anchors.centerIn: parent
        width: 460
        padding: 20
        Overlay.modal: Rectangle { color: Theme.isDark ? "#99000000" : "#55000000" }
        contentItem: ColumnLayout {
            spacing: 8
            Label { text: "Label"; font.bold: true }
            TextField { id: labelField; Layout.fillWidth: true; placeholderText: "What people see"; onAccepted: renameDialog.go() }
            Label { text: "Name inside the database"; font.bold: true; Layout.topMargin: 6 }
            TextField {
                id: nameField
                Layout.fillWidth: true
                font.family: Theme.monoFont
                placeholderText: "letters, numbers and underscores"
                onAccepted: renameDialog.go()
            }
            Label {
                Layout.fillWidth: true
                text: "Changing the name inside also updates this table's form and reports."
                color: Theme.lightForeground
                font.pointSize: 10
                wrapMode: Text.WordWrap
            }
            Label {
                Layout.fillWidth: true
                visible: renameDialog.renameError !== ""
                text: renameDialog.renameError
                color: Theme.red
                wrapMode: Text.WordWrap
            }
        }
        footer: DialogButtonBox {
            ActionButton { text: "Cancel"; onClicked: renameDialog.reject() }
            ActionButton { text: "Save"; primary: true; onClicked: renameDialog.go() }
        }
    }

    // ---- delete one field ------------------------------------------------------
    Dialog {
        id: deleteConfirm
        property string fieldName: ""
        property string fieldLabel: ""
        function ask(field) { fieldName = field.name; fieldLabel = field.label; open() }
        title: "Delete the field “" + fieldLabel + "”?"
        modal: true
        anchors.centerIn: parent
        width: 460
        padding: 20
        Overlay.modal: Rectangle { color: Theme.isDark ? "#99000000" : "#55000000" }
        contentItem: Label {
            text: "Everything in that column, in every row, will be gone. This cannot be undone."
            wrapMode: Text.WordWrap
        }
        footer: DialogButtonBox {
            ActionButton { text: "Keep it"; DialogButtonBox.buttonRole: DialogButtonBox.RejectRole }
            ActionButton { text: "Delete it"; primary: true; DialogButtonBox.buttonRole: DialogButtonBox.AcceptRole }
        }
        onAccepted: {
            const r = Bridge.deleteField(fieldName)
            dialog.error = r.ok ? "" : r.error
        }
    }
}
