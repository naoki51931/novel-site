const { app, BrowserWindow, ipcMain, dialog, safeStorage } = require("electron");
const path = require("path");
const fs = require("fs/promises");
const Store = require("electron-store");

const store = new Store({ name: "settings" });

function createWindow() {
  const win = new BrowserWindow({
    width: 1180,
    height: 820,
    minWidth: 900,
    minHeight: 650,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true
    }
  });
  win.loadFile(path.join(__dirname, "renderer", "index.html"));
}

function getStoredApiKey() {
  const encrypted = store.get("openrouterApiKey");
  if (!encrypted || !safeStorage.isEncryptionAvailable()) return "";
  try {
    return safeStorage.decryptString(Buffer.from(encrypted, "base64"));
  } catch {
    return "";
  }
}

function setStoredApiKey(apiKey) {
  if (!apiKey) {
    store.delete("openrouterApiKey");
    return;
  }
  if (!safeStorage.isEncryptionAvailable()) {
    throw new Error("Windows の安全な資格情報ストレージを利用できません。");
  }
  store.set("openrouterApiKey", safeStorage.encryptString(apiKey).toString("base64"));
}

function buildPrompt(input) {
  const lengthMap = {
    short: "およそ 800〜1200 文字の短編",
    medium: "およそ 2000〜3000 文字の中編",
    long: "およそ 4000〜6000 文字のやや長めの中編",
    xlong: "およそ 6000〜8000 文字の長編",
    xxlong: "およそ 8000〜10000 文字の長編"
  };
  const constraints = input.r18
    ? "- 成人向けの内容を含めて構いません。\n- 登場人物は全員18歳以上の成人として扱ってください。\n- 合意のある成人同士の関係として描写してください。\n- 読みやすい段落構成にしてください。"
    : "- 一般向けの内容にし、露骨な性描写や過度な暴力描写は避けてください。\n- 読みやすい段落構成にしてください。";

  return [
    "あなたは日本語の小説家です。以下の条件に合う小説を書いてください。",
    "",
    "# 出力形式",
    "必ず JSON 1個のみを返してください。",
    "{\"title\":\"タイトル\",\"body\":\"本文\"}",
    "",
    "# 制約",
    constraints,
    "",
    "# 要望",
    "- 作品の長さ: " + (lengthMap[input.length] || lengthMap.medium),
    "- ジャンル: " + (input.genre || "ジャンルは特に指定なし"),
    "- 雰囲気: " + (input.tone || "雰囲気は特に指定なし"),
    "- 登場人物・設定: " + (input.characters || "登場人物や設定の指定は特にない"),
    "- タイトルに関する要望: " + (input.titleHint || "内容に合うものを考える")
  ].join("\n");
}

ipcMain.handle("settings:get", async () => ({
  apiKey: getStoredApiKey(),
  model: store.get("model", "openrouter/auto")
}));

ipcMain.handle("settings:save", async (_event, settings) => {
  setStoredApiKey(String(settings.apiKey || "").trim());
  store.set("model", String(settings.model || "openrouter/auto").trim());
  return { ok: true };
});

ipcMain.handle("novel:generate", async (_event, input) => {
  const apiKey = String(input.apiKey || getStoredApiKey() || "").trim();
  if (!apiKey) throw new Error("OpenRouter APIキーを設定してください。");
  const model = String(input.model || store.get("model", "openrouter/auto")).trim();
  if (!model) throw new Error("モデルを指定してください。");

  const response = await fetch("https://openrouter.ai/api/v1/chat/completions", {
    method: "POST",
    headers: {
      "Authorization": "Bearer " + apiKey,
      "Content-Type": "application/json",
      "HTTP-Referer": "https://shosetsu-toukou-site.org",
      "X-Title": "Lexis Novel Desktop"
    },
    body: JSON.stringify({
      model,
      messages: [
        { role: "system", content: "あなたは日本語の小説家です。出力は必ずJSON 1個のみで返してください。" },
        { role: "user", content: buildPrompt(input) }
      ],
      max_tokens: Math.max(512, Math.min(8192, Number(input.maxTokens || 4096)))
    })
  });

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error((data && data.error && data.error.message) || ("OpenRouter API error: " + response.status));
  }

  const raw = data && data.choices && data.choices[0] && data.choices[0].message
    ? (data.choices[0].message.content || "")
    : "";
  if (!raw) throw new Error("AIから空の応答が返りました。");

  let parsed;
  try {
    const cleaned = raw.replace(/^\x60\x60\x60(?:json)?/i, "").replace(/\x60\x60\x60$/, "").trim();
    parsed = JSON.parse(cleaned);
  } catch {
    parsed = { title: "タイトル未設定", body: raw };
  }

  return {
    title: String(parsed.title || parsed.generated_title || "タイトル未設定"),
    body: String(parsed.body || parsed.content || parsed.story || raw),
    model: data.model || model,
    usage: data.usage || null
  };
});

ipcMain.handle("novel:save", async (_event, payload) => {
  const result = await dialog.showSaveDialog({
    title: "小説を保存",
    defaultPath: (payload.title || "novel") + ".txt",
    filters: [
      { name: "Text", extensions: ["txt"] },
      { name: "Markdown", extensions: ["md"] }
    ]
  });
  if (result.canceled || !result.filePath) return { canceled: true };
  await fs.writeFile(result.filePath, (payload.title || "") + "\n\n" + (payload.body || ""), "utf8");
  return { canceled: false, filePath: result.filePath };
});

app.whenReady().then(() => {
  createWindow();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});