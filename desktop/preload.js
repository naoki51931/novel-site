const { contextBridge, ipcRenderer } = require("electron");
contextBridge.exposeInMainWorld("lexis", {
  getSettings: () => ipcRenderer.invoke("settings:get"),
  saveSettings: (settings) => ipcRenderer.invoke("settings:save", settings),
  listModels: (input) => ipcRenderer.invoke("models:list", input),
  generateNovel: (input) => ipcRenderer.invoke("novel:generate", input),
  generateBlocks: (input) => ipcRenderer.invoke("novel:generate-blocks", input),
  continueNovel: (input) => ipcRenderer.invoke("novel:continue", input),
  getHistory: () => ipcRenderer.invoke("history:get"),
  saveTemplate: (template) => ipcRenderer.invoke("templates:save", template),
  getTemplates: () => ipcRenderer.invoke("templates:get"),
  saveDraftLocal: (payload) => ipcRenderer.invoke("draft:save-local", payload),
  listDraftsLocal: () => ipcRenderer.invoke("draft:list-local"),
  lexisLogin: (input) => ipcRenderer.invoke("lexis:login", input),
  uploadToLexis: (payload) => ipcRenderer.invoke("lexis:upload", payload),
  updateApp: () => ipcRenderer.invoke("app:update"),
  uninstallApp: () => ipcRenderer.invoke("app:uninstall"),
  saveNovel: (payload) => ipcRenderer.invoke("novel:save", payload),
  saveLibraryNovel: (payload) => ipcRenderer.invoke("library:save", payload),
  listLibraryNovels: () => ipcRenderer.invoke("library:list"),
  deleteLibraryNovel: (id) => ipcRenderer.invoke("library:delete", id)
});