import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Rename one field: the label people see and/or the name inside. Page level, not nested.
Dialog {
    id: dialog
    objectName: "renameFieldDialog"
    property string oldName: ""
    property string error: ""

    function openFor(field) {
        oldName = field.name
        labelField.text = field.label
        nameField.text = field.name
        error = ""
        open()
        labelField.forceActiveFocus()
    }

    function go() {
        const r = Bridge.renameField(oldName, nameField.text.trim(), labelField.text.trim())
        if (!r.ok) { error = r.error; return }
        close()
        fieldsDialog.openFor()
    }

    title: "Rename “" + oldName + "”"
    modal: true
    parent: Overlay.overlay
    anchors.centerIn: parent
    width: 460
    padding: 20
    closePolicy: Popup.CloseOnEscape
    Overlay.modal: Rectangle { color: Theme.isDark ? "#99000000" : "#55000000" }

    contentItem: ColumnLayout {
        spacing: 8
        Label { text: "Label"; font.bold: true }
        TextField { id: labelField; Layout.fillWidth: true; placeholderText: "What people see"; onAccepted: dialog.go() }
        Label { text: "Name inside the database"; font.bold: true; Layout.topMargin: 6 }
        TextField {
            id: nameField
            Layout.fillWidth: true
            font.family: Theme.monoFont
            placeholderText: "letters, numbers and underscores"
            onAccepted: dialog.go()
        }
        Label {
            Layout.fillWidth: true
            text: "Changing the name inside also updates this table's form, reports and views."
            color: Theme.lightForeground
            font.pointSize: 10
            wrapMode: Text.WordWrap
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
        ActionButton { text: "Cancel"; DialogButtonBox.buttonRole: DialogButtonBox.RejectRole }
        ActionButton { text: "Save"; primary: true; DialogButtonBox.buttonRole: DialogButtonBox.ActionRole; onClicked: dialog.go() }
    }
    onRejected: fieldsDialog.openFor()
}
