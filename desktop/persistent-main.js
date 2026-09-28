const { app } = require("electron");
const path = require("path");
const fs = require("fs");

// Keep templates/settings/drafts/library metadata outside Electron's default
// AppData location so an uninstall/reinstall does not remove user content.
// Existing novel text files already live under Documents/Lexis/小説.
const persistentUserData = path.join(app.getPath("documents"), "Lexis", "アプリデータ");
fs.mkdirSync(persistentUserData, { recursive: true });
app.setPath("userData", persistentUserData);

require("./main.js");
