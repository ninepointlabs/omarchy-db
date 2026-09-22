import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// One open database: its tables down the left, the rows of one table on the right.
Page {
    id: page
    objectName: "databasePage"
    property string mode: "grid"       // "grid" or "form"
    property int selectedRow: grid.currentRow
    background: Rectangle { color: Theme.window }

    function showForm(index) {
        mode = "form"
        formView.load(index)
    }
    function addRow() { showForm(-1) }
    function deleteSelected() {
        const id = page.mode === "form" ? formView.rowId : Bridge.rows.rowId(page.selectedRow)
        if (id > 0) confirmDelete.ask(id)
    }

    Dialog {
        id: confirmDelete
        property int rowId: 0
        function ask(id) { rowId = id; open() }
        title: "Delete this row?"
        modal: true
        anchors.centerIn: parent
        width: 420
        padding: 20
        Overlay.modal: Rectangle { color: Theme.isDark ? "#99000000" : "#55000000" }
        contentItem: Label { text: "It will be gone for good."; wrapMode: Text.WordWrap }
        footer: DialogButtonBox {
            ActionButton { text: "Keep it"; DialogButtonBox.buttonRole: DialogButtonBox.RejectRole }
            ActionButton { text: "Delete it"; primary: true; DialogButtonBox.buttonRole: DialogButtonBox.AcceptRole }
        }
        onAccepted: {
            const r = Bridge.deleteRow(rowId)
            if (!r.ok) toast.show(r.error)
            else if (page.mode === "form") formView.load(Math.min(formView.rowIndex, Bridge.rows.rowCount() - 1))
        }
    }

    header: ToolBar {
        height: 64
        background: Rectangle {
            color: Theme.isDark ? Theme.darkBackground : Theme.darkerBackground
            Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Theme.muted; opacity: 0.5 }
        }
        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 12
            anchors.rightMargin: 12
            spacing: 12

            ToolButton {
                text: "‹  Home"
                font.pointSize: 12
                onClicked: win.goHome()
            }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 0
                Label {
                    Layout.fillWidth: true
                    text: Bridge.title
                    font.pointSize: 14
                    font.bold: true
                    elide: Text.ElideRight
                }
                Label {
                    Layout.fillWidth: true
                    text: Bridge.backendWord + "  ·  " + Bridge.location
                    color: Theme.lightForeground
                    font.pointSize: 9
                    elide: Text.ElideMiddle
                }
            }
            ActionButton { text: "Open another"; onClicked: win.startOpen() }
            ActionButton {
                text: "Import spreadsheet"
                primary: true
                onClicked: win.startImport()
            }
        }
    }

    RowLayout {
        anchors.fill: parent
        spacing: 0

        // ---- tables --------------------------------------------------------
        Rectangle {
            Layout.preferredWidth: Math.max(160, Math.min(260, page.width * 0.28))
            Layout.fillHeight: true
            color: Theme.darkBackground
            Rectangle { anchors.right: parent.right; width: 1; height: parent.height; color: Theme.muted; opacity: 0.5 }

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 12
                spacing: 8
                Label {
                    text: "Tables"
                    font.pointSize: 12
                    font.bold: true
                    color: Theme.lightForeground
                    Layout.leftMargin: 8
                }
                ListView {
                    id: tableList
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    spacing: 2
                    model: Bridge.tables
                    ScrollBar.vertical: ScrollBar {}
                    delegate: ItemDelegate {
                        id: item
                        required property var modelData
                        width: tableList.width
                        height: 48
                        hoverEnabled: true
                        property bool current: modelData.name === Bridge.currentTable
                        onClicked: {
                            const r = Bridge.selectTable(modelData.name)
                            if (!r.ok) toast.show(r.error)
                        }
                        background: Rectangle {
                            radius: 8
                            color: item.current ? Theme.selection
                                 : item.hovered ? Theme.lighterBackground : "transparent"
                        }
                        contentItem: ColumnLayout {
                            spacing: 1
                            Label {
                                Layout.fillWidth: true
                                text: item.modelData.name
                                font.pointSize: 12
                                font.bold: item.current
                                elide: Text.ElideRight
                            }
                            Label {
                                text: item.modelData.rows === 1 ? "1 row" : item.modelData.rows + " rows"
                                color: Theme.lightForeground
                                font.pointSize: 9
                            }
                        }
                    }
                }
                Label {
                    visible: Bridge.tables.length === 0
                    Layout.fillWidth: true
                    Layout.leftMargin: 8
                    text: "No tables yet."
                    color: Theme.lightForeground
                    wrapMode: Text.WordWrap
                }
            }
        }

        // ---- rows ------------------------------------------------------------
        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            EmptyState {
                anchors.fill: parent
                visible: Bridge.tables.length === 0
                title: "No tables yet"
                text: "Drop a spreadsheet on this window, or press the button, and it becomes a table."
                buttonText: "Import spreadsheet"
                onClicked: win.startImport()
            }

            EmptyState {
                anchors.fill: parent
                visible: Bridge.tables.length > 0 && Bridge.totalRows === 0
                title: "No rows yet"
                text: "This table is empty. Adding rows by hand comes in the next step of the project."
            }

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 12
                spacing: 0
                visible: Bridge.tables.length > 0 && (Bridge.totalRows > 0 || page.mode === "form")

                RowLayout {
                    Layout.fillWidth: true
                    Layout.bottomMargin: 10
                    spacing: 8
                    ActionButton {
                        text: "Grid"
                        primary: page.mode === "grid"
                        onClicked: page.mode = "grid"
                    }
                    ActionButton {
                        text: "Form"
                        primary: page.mode === "form"
                        onClicked: page.showForm(page.selectedRow >= 0 ? page.selectedRow : 0)
                    }
                    Item { Layout.fillWidth: true }
                    ActionButton { text: "Add row"; onClicked: page.addRow() }
                    ActionButton {
                        text: "Delete row"
                        enabled: page.mode === "form" ? formView.rowId > 0 : page.selectedRow >= 0
                        onClicked: page.deleteSelected()
                    }
                }

                FormView {
                    id: formView
                    objectName: "formView"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    visible: page.mode === "form"
                    onDeleteRequested: function(id) { confirmDelete.ask(id) }
                }

                HorizontalHeaderView {
                    id: headerView
                    Layout.fillWidth: true
                    visible: page.mode === "grid"
                    syncView: grid
                    clip: true
                    delegate: Rectangle {
                        required property string display
                        implicitWidth: 100
                        implicitHeight: 36
                        color: Theme.lighterBackground
                        Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Theme.muted }
                        Label {
                            anchors.fill: parent
                            anchors.leftMargin: 10
                            anchors.rightMargin: 10
                            verticalAlignment: Text.AlignVCenter
                            text: parent.display
                            font.bold: true
                            elide: Text.ElideRight
                        }
                    }
                }

                TableView {
                    id: grid
                    objectName: "rowsGrid"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    visible: page.mode === "grid"
                    clip: true
                    model: Bridge.rows
                    columnSpacing: 0
                    rowSpacing: 0
                    boundsBehavior: Flickable.StopAtBounds
                    columnWidthProvider: function(column) { return Bridge.rows.columnWidth(column) }
                    ScrollBar.vertical: ScrollBar {}
                    ScrollBar.horizontal: ScrollBar {}

                    // Tap a row to pick it; double-tap (or Enter / F2) a cell to type in it.
                    selectionModel: ItemSelectionModel {}
                    selectionBehavior: TableView.SelectRows
                    editTriggers: TableView.DoubleTapped | TableView.EditKeyPressed

                    delegate: Rectangle {
                        id: cellItem
                        required property string display
                        required property int row
                        required property int column
                        required property bool current
                        implicitWidth: 100
                        implicitHeight: 34
                        color: row === grid.currentRow ? Theme.selection
                             : row % 2 === 0 ? Theme.base : Theme.alternateBase
                        Label {
                            anchors.fill: parent
                            anchors.leftMargin: 10
                            anchors.rightMargin: 10
                            verticalAlignment: Text.AlignVCenter
                            text: cellItem.display
                            elide: Text.ElideRight
                            color: cellItem.column === 0 ? Theme.lightForeground : Theme.foreground
                            font.family: cellItem.column === 0 ? Theme.monoFont : win.font.family
                        }
                        Rectangle {
                            anchors.fill: parent
                            color: "transparent"
                            border.width: cellItem.current && cellItem.column > 0 ? 2 : 0
                            border.color: Theme.accent
                        }

                        TableView.editDelegate: TextField {
                            anchors.fill: parent
                            text: display
                            font.pointSize: 11
                            selectByMouse: true
                            Component.onCompleted: { selectAll(); forceActiveFocus() }
                            TableView.onCommit: display = text
                        }
                    }

                    Connections {
                        target: Bridge
                        function onTableChanged() {
                            grid.contentX = 0
                            grid.contentY = 0
                            grid.forceLayout()
                        }
                    }
                }

                Label {
                    Layout.topMargin: 8
                    text: Bridge.shownRows === Bridge.totalRows
                        ? (Bridge.totalRows === 1 ? "1 row" : Bridge.totalRows + " rows")
                        : "Showing the first " + Bridge.shownRows + " of " + Bridge.totalRows + " rows"
                    color: Theme.lightForeground
                    font.pointSize: 10
                }
            }
        }
    }
}
