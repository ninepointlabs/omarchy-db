import QtQuick
import QtQuick.Controls

// One big button with a short hint under the word. One job each.
Button {
    id: control
    property string hint: ""
    property bool primary: false

    implicitWidth: 236
    implicitHeight: 96
    hoverEnabled: true

    contentItem: Column {
        spacing: 4
        anchors.centerIn: parent
        Label {
            width: control.width - 24
            text: control.text
            font.pointSize: 14
            font.bold: true
            horizontalAlignment: Text.AlignHCenter
            color: control.primary ? Theme.background : Theme.foreground
        }
        Label {
            width: control.width - 24
            text: control.hint
            font.pointSize: 10
            horizontalAlignment: Text.AlignHCenter
            color: control.primary ? Theme.background : Theme.lightForeground
            opacity: 0.9
            visible: control.hint !== ""
        }
    }

    background: Rectangle {
        radius: 12
        color: {
            if (control.primary)
                return control.down ? Qt.darker(Theme.accent, 1.2)
                     : control.hovered ? Qt.lighter(Theme.accent, 1.08) : Theme.accent
            return control.down ? Theme.selection
                 : control.hovered ? Qt.lighter(Theme.lighterBackground, 1.12) : Theme.lighterBackground
        }
        border.width: control.primary ? 0 : 1
        border.color: control.activeFocus ? Theme.accent : Theme.muted
    }
}
