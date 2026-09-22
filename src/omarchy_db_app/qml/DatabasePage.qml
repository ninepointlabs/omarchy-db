import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// One open database: its tables down the left, the rows of one table on the right.
Page {
    id: page
    background: Rectangle { color: Theme.window }

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
                visible: Bridge.tables.length > 0 && Bridge.totalRows > 0

                HorizontalHeaderView {
                    id: headerView
                    Layout.fillWidth: true
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
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    model: Bridge.rows
                    columnSpacing: 0
                    rowSpacing: 0
                    boundsBehavior: Flickable.StopAtBounds
                    columnWidthProvider: function(column) { return Bridge.rows.columnWidth(column) }
                    ScrollBar.vertical: ScrollBar {}
                    ScrollBar.horizontal: ScrollBar {}

                    delegate: Rectangle {
                        required property string display
                        required property int row
                        required property int column
                        implicitWidth: 100
                        implicitHeight: 34
                        color: row % 2 === 0 ? Theme.base : Theme.alternateBase
                        Label {
                            anchors.fill: parent
                            anchors.leftMargin: 10
                            anchors.rightMargin: 10
                            verticalAlignment: Text.AlignVCenter
                            text: parent.display
                            elide: Text.ElideRight
                            color: parent.column === 0 ? Theme.lightForeground : Theme.foreground
                            font.family: parent.column === 0 ? Theme.monoFont : win.font.family
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
