const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("lexis", {
  getSettings: () => ipcRenderer.invoke("settings:get"),
  saveSettings: (settings) => ipcRenderer.invoke("settings:save", settings),
  generateNovel: (input) => ipcRenderer.invoke("novel:generate", input),
  saveNovel: (payload) => ipcRenderer.invoke("novel:save", payload)
});