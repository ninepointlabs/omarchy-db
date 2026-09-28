import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// "Show rows where  [Field]  [is / is not / is empty / is not empty / contains]  [value]  Apply  Clear   Views…"
// The rule is positive on purpose: to hide people who moved, say "Moved is not Yes".
// A rule worth keeping is saved as a view (Views… → Save view…) inside the database file.
RowLayout {
    id: bar
    objectName: "filterBar"
    spacing: 8
    property var ops: Bridge.filterOps()
    property bool needsValue: ops[opBox.currentIndex] ? ops[opBox.currentIndex].needsValue : true

    function apply() {
        const field = Bridge.fields[fieldBox.currentIndex]
        if (!field) return
        const r = Bridge.setFilter(field.name, ops[opBox.currentIndex].key, needsValue ? valueField.text : "")
        if (!r.ok) toast.show(r.error)
    }

    function clear() {
        valueField.text = ""
        const r = Bridge.clearFilter()
        if (!r.ok) toast.show(r.error)
    }

    // Which table the bar was last showing, so moving to another table starts it fresh.
    property string shownTable: ""

    // When the table (or its filter) changes, show the rule on the bar.
    Connections {
        target: Bridge
        function onTableChanged() {
            const f = Bridge.filter
            const otherTable = Bridge.currentTable !== bar.shownTable
            bar.shownTable = Bridge.currentTable
            if (f && f.field) {
                for (let i = 0; i < Bridge.fields.length; i++) if (Bridge.fields[i].name === f.field) fieldBox.currentIndex = i
                for (let j = 0; j < bar.ops.length; j++) if (bar.ops[j].key === f.op) opBox.currentIndex = j
                valueField.text = f.value === undefined || f.value === null ? "" : String(f.value)
            } else if (otherTable) {
                // No rule on the new table: don't carry the last table's rule over.
                fieldBox.currentIndex = 0
                opBox.currentIndex = 0
                valueField.text = ""
            } else if (fieldBox.currentIndex >= Bridge.fields.length) {
                fieldBox.currentIndex = 0
            }
        }
    }

    Label { text: "Show rows where"; color: Theme.lightForeground }
    ComboBox {
        id: fieldBox
        Layout.preferredWidth: 160
        model: Bridge.fields
        textRole: "label"
        onActivated: valueField.forceActiveFocus()
    }
    ComboBox {
        id: opBox
        Layout.preferredWidth: 130
        model: bar.ops
        textRole: "label"
        onActivated: { if (!bar.needsValue) bar.apply(); else valueField.forceActiveFocus() }
    }
    TextField {
        id: valueField
        objectName: "filterValue"
        Layout.fillWidth: true
        Layout.minimumWidth: 90
        Layout.maximumWidth: 220
        visible: bar.needsValue
        placeholderText: (Bridge.fields[fieldBox.currentIndex] || {}).type === "boolean" ? "yes or no" : "a value"
        onAccepted: bar.apply()
    }
    ActionButton { text: "Apply"; primary: true; onClicked: bar.apply() }
    ActionButton { text: "Clear"; visible: Bridge.filterWords !== ""; onClicked: bar.clear() }
    Item { Layout.fillWidth: true; Layout.minimumWidth: 0 }

    // ---- saved views ----------------------------------------------------------
    ActionButton {
        text: Bridge.currentView !== "" ? "View: " + Bridge.currentView : "Views…"
        objectName: "viewsButton"
        onClicked: viewsMenu.open()
        Menu {
            id: viewsMenu
            objectName: "viewsMenu"
            // The button sits at the right edge: open leftwards, wide enough for "Name · rule".
            x: parent.width - width
            y: parent.height
            onAboutToShow: {
                let w = 240
                for (let i = 0; i < count; i++) {
                    const item = itemAt(i)
                    // A menu item's own implicitWidth follows the menu; its label knows the text width.
                    if (item && item.visible && item.contentItem)
                        w = Math.max(w, item.contentItem.implicitWidth + item.leftPadding + item.rightPadding)
                }
                width = Math.min(w + leftPadding + rightPadding, 640)
            }
            MenuItem {
                visible: Bridge.views.length === 0
                height: visible ? implicitHeight : 0
                enabled: false
                text: "No saved views yet — Apply a filter, then Save view…"
            }
            Repeater {
                model: Bridge.views
                MenuItem {
                    required property var modelData
                    text: modelData.name + (modelData.default ? "  (opens with this)" : "") + "  ·  " + modelData.words
                    onTriggered: { const r = Bridge.applyView(modelData.name); if (!r.ok) toast.show(r.error) }
                }
            }
            MenuSeparator {}
            MenuItem {
                text: "Save view…"
                enabled: Bridge.filterWords !== ""
                onTriggered: saveViewDialog.openFor()
            }
            MenuItem {
                text: "Rename “" + Bridge.currentView + "”…"
                visible: Bridge.currentView !== ""
                height: visible ? implicitHeight : 0
                onTriggered: renameViewDialog.openFor(Bridge.currentView)
            }
            MenuItem {
                text: "Delete “" + Bridge.currentView + "”…"
                visible: Bridge.currentView !== ""
                height: visible ? implicitHeight : 0
                onTriggered: deleteViewConfirm.ask(Bridge.currentView)
            }
        }
    }

    Dialog {
        id: saveViewDialog
        objectName: "saveViewDialog"
        property string saveError: ""
        function openFor() {
            viewName.text = Bridge.currentView
            defaultBox.checked = false
            for (const v of Bridge.views) if (v.name === Bridge.currentView) defaultBox.checked = v.default
            saveError = ""
            open()
            viewName.forceActiveFocus()
            viewName.selectAll()
        }
        function go(replace) {
            const r = Bridge.saveView(viewName.text.trim(), replace, defaultBox.checked)
            if (r.ok) { close(); return }
            if (r.needsConfirm) { replaceViewConfirm.viewName = r.name; replaceViewConfirm.open(); return }
            saveError = r.error
        }
        title: "Save this view"
        modal: true
        parent: Overlay.overlay
        anchors.centerIn: parent
        width: 460
        padding: 20
        Overlay.modal: Rectangle { color: Theme.isDark ? "#99000000" : "#55000000" }
        contentItem: ColumnLayout {
            spacing: 8
            Label { Layout.fillWidth: true; text: "Rows where " + Bridge.filterWords; color: Theme.lightForeground; wrapMode: Text.WordWrap }
            Label { text: "Name"; font.bold: true; Layout.topMargin: 6 }
            TextField { id: viewName; Layout.fillWidth: true; placeholderText: "Like “Still here”"; onAccepted: saveViewDialog.go(false) }
            CheckBox { id: defaultBox; text: "Open this table with this view" }
            Label { Layout.fillWidth: true; text: "Saved inside the database file, so it travels with it."; color: Theme.lightForeground; font.pointSize: 10; wrapMode: Text.WordWrap }
            Label { Layout.fillWidth: true; visible: saveViewDialog.saveError !== ""; text: saveViewDialog.saveError; color: Theme.red; wrapMode: Text.WordWrap }
        }
        footer: DialogButtonBox {
            ActionButton { text: "Cancel"; onClicked: saveViewDialog.reject() }
            ActionButton { text: "Save"; primary: true; enabled: viewName.text.trim() !== ""; onClicked: saveViewDialog.go(false) }
        }
    }

    Dialog {
        id: replaceViewConfirm
        property string viewName: ""
        title: "Replace the view “" + viewName + "”?"
        modal: true
        parent: Overlay.overlay
        anchors.centerIn: parent
        width: 440
        padding: 20
        Overlay.modal: Rectangle { color: Theme.isDark ? "#99000000" : "#55000000" }
        contentItem: Label { text: "There is already a view with that name. It will now show rows where " + Bridge.filterWords + "."; wrapMode: Text.WordWrap }
        footer: DialogButtonBox {
            ActionButton { text: "Keep the old one"; DialogButtonBox.buttonRole: DialogButtonBox.RejectRole }
            ActionButton { text: "Replace it"; primary: true; DialogButtonBox.buttonRole: DialogButtonBox.AcceptRole }
        }
        onAccepted: saveViewDialog.go(true)
    }

    Dialog {
        id: renameViewDialog
        property string oldName: ""
        property string renameError: ""
        function openFor(name) { oldName = name; newViewName.text = name; renameError = ""; open(); newViewName.forceActiveFocus(); newViewName.selectAll() }
        function go() { const r = Bridge.renameView(oldName, newViewName.text.trim()); if (r.ok) close(); else renameError = r.error }
        title: "Rename the view “" + oldName + "”"
        modal: true
        parent: Overlay.overlay
        anchors.centerIn: parent
        width: 440
        padding: 20
        Overlay.modal: Rectangle { color: Theme.isDark ? "#99000000" : "#55000000" }
        contentItem: ColumnLayout {
            spacing: 8
            TextField { id: newViewName; Layout.fillWidth: true; onAccepted: renameViewDialog.go() }
            Label { Layout.fillWidth: true; visible: renameViewDialog.renameError !== ""; text: renameViewDialog.renameError; color: Theme.red; wrapMode: Text.WordWrap }
        }
        footer: DialogButtonBox {
            ActionButton { text: "Cancel"; onClicked: renameViewDialog.reject() }
            ActionButton { text: "Rename"; primary: true; enabled: newViewName.text.trim() !== ""; onClicked: renameViewDialog.go() }
        }
    }

    Dialog {
        id: deleteViewConfirm
        property string viewName: ""
        function ask(name) { viewName = name; open() }
        title: "Delete the view “" + viewName + "”?"
        modal: true
        parent: Overlay.overlay
        anchors.centerIn: parent
        width: 440
        padding: 20
        Overlay.modal: Rectangle { color: Theme.isDark ? "#99000000" : "#55000000" }
        contentItem: Label { text: "The rows stay. Only the saved filter goes."; wrapMode: Text.WordWrap }
        footer: DialogButtonBox {
            ActionButton { text: "Keep it"; DialogButtonBox.buttonRole: DialogButtonBox.RejectRole }
            ActionButton { text: "Delete the view"; primary: true; DialogButtonBox.buttonRole: DialogButtonBox.AcceptRole }
        }
        onAccepted: { const r = Bridge.deleteView(viewName); if (!r.ok) toast.show(r.error) }
    }
}
