import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// "Show rows where  [Field]  [is / is not / is empty / is not empty / contains]  [value]  Apply  Clear"
// The rule is positive on purpose: to hide people who moved, say "Moved is not Yes".
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

    // When the table changes, show its remembered filter (or a fresh bar).
    Connections {
        target: Bridge
        function onTableChanged() {
            const f = Bridge.filter
            if (f && f.field) {
                for (let i = 0; i < Bridge.fields.length; i++) if (Bridge.fields[i].name === f.field) fieldBox.currentIndex = i
                for (let j = 0; j < bar.ops.length; j++) if (bar.ops[j].key === f.op) opBox.currentIndex = j
                valueField.text = f.value === undefined || f.value === null ? "" : String(f.value)
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
        Layout.fillWidth: true
        Layout.minimumWidth: 90
        Layout.maximumWidth: 220
        visible: bar.needsValue
        placeholderText: (Bridge.fields[fieldBox.currentIndex] || {}).type === "boolean" ? "yes or no" : "a value"
        onAccepted: bar.apply()
    }
    ActionButton { text: "Apply"; primary: true; onClicked: bar.apply() }
    ActionButton { text: "Clear"; visible: Bridge.filterWords !== ""; onClicked: bar.clear() }
    Label {
        Layout.leftMargin: 8
        visible: Bridge.filterWords !== ""
        text: "Showing " + Bridge.totalRows + " of " + Bridge.allRows + "  ·  " + Bridge.filterWords
        color: Theme.yellow
        elide: Text.ElideRight
        Layout.fillWidth: true
    }
    Item { Layout.fillWidth: true; visible: Bridge.filterWords === "" }
}
