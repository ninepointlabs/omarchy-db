import QtQuick
import QtQuick.Controls

// A normal-sized button. `primary` fills it with the accent colour.
Button {
    id: control
    property bool primary: false
    hoverEnabled: true
    padding: 10
    leftPadding: 16
    rightPadding: 16

    contentItem: Label {
        text: control.text
        font.pointSize: 11
        font.bold: control.primary
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        color: control.primary ? Theme.background : Theme.foreground
        opacity: control.enabled ? 1 : 0.5
    }

    background: Rectangle {
        radius: 8
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
