import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts

// The one window. Two screens live in the stack: Home, and the open database.
// Every flow (new / open / import) starts here so the pages stay simple.
ApplicationWindow {
    id: win
    visible: true
    width: 1080
    height: 720
    minimumWidth: 720
    minimumHeight: 480
    title: Bridge.isOpen ? Bridge.title + " — Omarchy-DB" : "Omarchy-DB"
    color: palette.window
    font.pointSize: 11

    // A spreadsheet picked before any database exists: it becomes a new one.
    property string pendingSpreadsheet: ""

    StackView {
        id: stack
        anchors.fill: parent
        initialItem: homeComponent
        // Keep it calm: no sliding pages.
        pushEnter: Transition {}
        pushExit: Transition {}
        popEnter: Transition {}
        popExit: Transition {}
    }

    Component { id: homeComponent; HomePage {} }
    Component { id: databaseComponent; DatabasePage {} }

    Connections {
        target: Bridge
        function onDatabaseChanged() {
            if (Bridge.isOpen && stack.depth === 1)
                stack.push(databaseComponent)
            else if (!Bridge.isOpen && stack.depth > 1)
                stack.pop(null)
        }
        function onMessage(text) { toast.show(text) }
    }

    // ---- flows -----------------------------------------------------------
    function startNew() { newDialog.openFor("new", "sqlite", "", {}) }
    function startOpen() { openDbDialog.open() }
    function startImport() { importDialog.open() }
    function goHome() { Bridge.closeDatabase() }

    function openRecent(index) {
        const r = Bridge.openRecent(index)
        if (r.ok)
            return
        if (r.needsConnection)
            newDialog.openFor("open", r.backend, r.title, r.connection)
        else
            toast.show(r.error)
    }

    function openFile(url) {
        const r = Bridge.openDatabase("sqlite", url, {})
        if (!r.ok)
            toast.show(r.error)
    }

    function importFile(url) {
        if (!Bridge.isOpen) {
            // First run: the spreadsheet becomes a brand new database.
            win.pendingSpreadsheet = url
            saveDbDialog.selectedFile = Bridge.documentsFolder() + "/" + Bridge.suggestedDatabaseName(url)
            saveDbDialog.open()
            return
        }
        const r = Bridge.importSpreadsheet(url, false)
        if (r.ok)
            return
        if (r.needsConfirm) {
            replaceDialog.table = r.table
            replaceDialog.spreadsheet = url
            replaceDialog.open()
        } else {
            toast.show(r.error)
        }
    }

    function dropped(urls) {
        if (!urls || urls.length === 0)
            return
        const url = String(urls[0])
        const lower = url.toLowerCase()
        if (lower.endsWith(".omadb") || lower.endsWith(".sqlite") || lower.endsWith(".sqlite3") || lower.endsWith(".db"))
            openFile(url)
        else
            importFile(url)
    }

    // ---- dialogs ---------------------------------------------------------
    NewDatabaseDialog {
        id: newDialog
        onSqliteChosen: function(chosenTitle) {
            saveDbDialog.selectedFile = Bridge.documentsFolder() + "/my-database.omadb"
            saveDbDialog.open()
        }
    }

    FileDialog {
        id: saveDbDialog
        title: "Save the new database"
        fileMode: FileDialog.SaveFile
        defaultSuffix: "omadb"
        nameFilters: ["Databases (*.omadb)"]
        currentFolder: Bridge.documentsFolder()
        onAccepted: {
            let r
            if (win.pendingSpreadsheet !== "") {
                r = Bridge.importIntoNew(win.pendingSpreadsheet, selectedFile)
                win.pendingSpreadsheet = ""
            } else {
                r = Bridge.newDatabase("sqlite", selectedFile, newDialog.chosenTitle, {})
            }
            if (!r.ok)
                toast.show(r.error)
        }
        onRejected: win.pendingSpreadsheet = ""
    }

    FileDialog {
        id: openDbDialog
        title: "Open a database"
        nameFilters: ["Databases (*.omadb *.sqlite *.sqlite3 *.db)", "All files (*)"]
        currentFolder: Bridge.documentsFolder()
        onAccepted: win.openFile(selectedFile)
    }

    FileDialog {
        id: importDialog
        title: "Pick a spreadsheet"
        nameFilters: ["Spreadsheets (*.csv *.tsv *.txt)", "All files (*)"]
        currentFolder: Bridge.homeFolder()
        onAccepted: win.importFile(selectedFile)
    }

    Dialog {
        id: replaceDialog
        property string table: ""
        property string spreadsheet: ""
        title: "Replace the table “" + table + "”?"
        modal: true
        anchors.centerIn: parent
        width: 480
        padding: 20
        Overlay.modal: Rectangle { color: Theme.isDark ? "#99000000" : "#55000000" }
        contentItem: Label {
            text: "It is already in this database. Its rows will be thrown away."
            wrapMode: Text.WordWrap
        }
        footer: DialogButtonBox {
            ActionButton {
                text: "Keep what I have"
                DialogButtonBox.buttonRole: DialogButtonBox.RejectRole
            }
            ActionButton {
                text: "Replace it"
                primary: true
                DialogButtonBox.buttonRole: DialogButtonBox.AcceptRole
            }
        }
        onAccepted: {
            const r = Bridge.importSpreadsheet(spreadsheet, true)
            if (!r.ok)
                toast.show(r.error)
        }
    }

    // Drop a spreadsheet (or a database file) anywhere on the window.
    DropArea {
        anchors.fill: parent
        onDropped: function(drop) {
            if (drop.hasUrls) {
                win.dropped(drop.urls)
                drop.accept()
            }
        }
    }

    Toast { id: toast }
}
