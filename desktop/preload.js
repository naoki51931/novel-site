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
  saveNovel: (payload) => ipcRenderer.invoke("novel:save", payload)
});