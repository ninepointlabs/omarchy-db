import QtQuick
import QtQuick.Controls

// A short message at the bottom of the window that goes away by itself.
Rectangle {
    id: toast
    property string text: ""

    function show(message) {
        text = message
        opacity = 1
        timer.restart()
    }

    anchors.horizontalCenter: parent.horizontalCenter
    anchors.bottom: parent.bottom
    anchors.bottomMargin: 28
    width: Math.min(label.implicitWidth + 36, parent.width - 48)
    height: label.implicitHeight + 22
    radius: 8
    z: 100
    color: Theme.lighterBackground
    border.color: Theme.muted
    border.width: 1
    opacity: 0
    visible: opacity > 0

    Behavior on opacity { NumberAnimation { duration: 160 } }

    Label {
        id: label
        anchors.centerIn: parent
        width: Math.min(implicitWidth, toast.parent.width - 84)
        text: toast.text
        color: Theme.foreground
        wrapMode: Text.WordWrap
        horizontalAlignment: Text.AlignHCenter
    }

    Timer {
        id: timer
        interval: 4500
        onTriggered: toast.opacity = 0
    }

    MouseArea {
        anchors.fill: parent
        onClicked: toast.opacity = 0
    }
}
