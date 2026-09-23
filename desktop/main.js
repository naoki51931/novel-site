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


function auth(input) {
  const apiKey = String((input && input.apiKey) || getStoredApiKey() || "").trim();
  if (!apiKey) throw new Error("OpenRouter APIキーを設定してください。");
  return apiKey;
}

async function openRouterJson(input, prompt, maxTokens) {
  const apiKey = auth(input);
  const model = String(input.model || store.get("model", "openrouter/auto")).trim();
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
        { role: "system", content: "あなたは日本語の小説家です。指定された形式を守り、物語の連続性を維持してください。" },
        { role: "user", content: prompt }
      ],
      max_tokens: Math.max(512, Math.min(8192, Number(maxTokens || input.maxTokens || 4096)))
    })
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error((data.error && data.error.message) || ("OpenRouter API error: " + response.status));
  const raw = data?.choices?.[0]?.message?.content || "";
  if (!raw) throw new Error("AIから空の応答が返りました。");
  return { raw, data, model: data.model || model };
}

function remember(result, input, kind) {
  const history = store.get("history", []);
  history.unshift({
    id: Date.now(),
    createdAt: new Date().toISOString(),
    kind,
    title: result.title || "タイトル未設定",
    body: result.body || "",
    model: result.model || input.model || ""
  });
  store.set("history", history.slice(0, 50));
}

ipcMain.handle("models:list", async (_event, input) => {
  const apiKey = auth(input || {});
  const response = await fetch("https://openrouter.ai/api/v1/models", {
    headers: { "Authorization": "Bearer " + apiKey }
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error((data.error && data.error.message) || "モデル一覧を取得できませんでした。");
  return (data.data || []).map((m) => ({ id: m.id, name: m.name || m.id })).sort((a,b) => a.id.localeCompare(b.id));
});

ipcMain.handle("history:get", async () => store.get("history", []));
ipcMain.handle("templates:get", async () => store.get("templates", []));
ipcMain.handle("templates:save", async (_event, template) => {
  const templates = store.get("templates", []);
  const item = { ...template, id: Date.now(), createdAt: new Date().toISOString() };
  templates.unshift(item);
  store.set("templates", templates.slice(0, 30));
  return item;
});

ipcMain.handle("novel:continue", async (_event, input) => {
  const previous = String(input.body || "").trim();
  if (!previous) throw new Error("続き元の本文がありません。");
  const tail = previous.slice(-12000);
  const prompt = buildPrompt(input) + "\n\n# 既存本文の末尾\n" + tail +
    "\n\n# 指示\n上の本文から自然に続く新しい本文だけを書いてください。既存本文は繰り返さないでください。";
  const r = await openRouterJson(input, prompt, input.maxTokens);
  let body = r.raw;
  try {
    const cleaned = r.raw.replace(/^\x60\x60\x60(?:json)?/i, "").replace(/\x60\x60\x60$/, "").trim();
    const parsed = JSON.parse(cleaned);
    body = String(parsed.body || parsed.content || parsed.story || r.raw);
  } catch {}
  const result = { title: input.title || "続き", body, model: r.model, usage: r.data.usage || null };
  remember(result, input, "continue");
  return result;
});

ipcMain.handle("novel:generate-blocks", async (_event, input) => {
  const count = Math.max(2, Math.min(12, Number(input.blockCount || 4)));
  const plans = Array.isArray(input.blockPlans) ? input.blockPlans : [];
  let title = "";
  let fullBody = "";
  const blocks = [];
  let totalTokens = 0;

  for (let i = 0; i < count; i++) {
    const plan = String(plans[i] || "").trim();
    const context = fullBody.slice(-10000);
    const prompt = buildPrompt(input) +
      "\n\n# ブロック生成\n全" + count + "ブロック中の第" + (i + 1) + "ブロックを書いてください。" +
      (plan ? "\nこのブロックの展開案: " + plan : "") +
      (context ? "\n\n# 直前までの本文\n" + context : "") +
      "\n\n前ブロックと矛盾させず、同じ場面や説明を不必要に繰り返さないでください。" +
      (i < count - 1 ? "\nこのブロックだけで物語を完結させず、次へ自然につながる余地を残してください。" : "\n最終ブロックとして必要なら物語を着地させてください。") +
      "\nJSON形式 {\"title\":\"タイトル\",\"body\":\"このブロックの本文\"} のみ返してください。";

    const r = await openRouterJson(input, prompt, input.blockMaxTokens || input.maxTokens);
    let parsed = { title: title || "タイトル未設定", body: r.raw };
    try {
      const cleaned = r.raw.replace(/^\x60\x60\x60(?:json)?/i, "").replace(/\x60\x60\x60$/, "").trim();
      parsed = JSON.parse(cleaned);
    } catch {}
    if (!title && parsed.title) title = String(parsed.title);
    const blockBody = String(parsed.body || parsed.content || parsed.story || r.raw).trim();
    blocks.push({ index: i + 1, plan, body: blockBody });
    fullBody += (fullBody ? "\n\n" : "") + blockBody;
    totalTokens += Number(r.data?.usage?.total_tokens || 0);
  }

  const result = { title: title || "タイトル未設定", body: fullBody, blocks, model: input.model, usage: totalTokens ? { total_tokens: totalTokens } : null };
  remember(result, input, "blocks");
  return result;
});

ipcMain.handle("draft:save-local", async (_event, payload) => {
  const drafts = store.get("drafts", []);
  const item = {
    id: payload.id || Date.now(),
    savedAt: new Date().toISOString(),
    title: String(payload.title || "タイトル未設定"),
    body: String(payload.body || ""),
    r18: !!payload.r18
  };
  const next = [item, ...drafts.filter((x) => x.id !== item.id)].slice(0, 100);
  store.set("drafts", next);
  return item;
});

ipcMain.handle("draft:list-local", async () => store.get("drafts", []));

ipcMain.handle("lexis:login", async (_event, input) => {
  const response = await fetch("https://shosetsu-toukou-site.org/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username: String(input.username || ""), password: String(input.password || "") })
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || ("Lexisログインに失敗しました: " + response.status));
  const token = data.access_token || data.token;
  if (!token) throw new Error("Lexisの認証トークンを取得できませんでした。");
  if (!safeStorage.isEncryptionAvailable()) throw new Error("認証情報を安全に保存できません。");
  store.set("lexisToken", safeStorage.encryptString(token).toString("base64"));
  store.set("lexisUsername", String(input.username || ""));
  return { ok: true, username: String(input.username || "") };
});

function getLexisToken() {
  const encrypted = store.get("lexisToken");
  if (!encrypted || !safeStorage.isEncryptionAvailable()) return "";
  try { return safeStorage.decryptString(Buffer.from(encrypted, "base64")); } catch { return ""; }
}

ipcMain.handle("lexis:upload", async (_event, payload) => {
  const token = getLexisToken();
  if (!token) throw new Error("先にLexisへログインしてください。");
  const title = String(payload.title || "AI生成小説").trim();
  const body = String(payload.body || "").trim();
  if (!body) throw new Error("アップロードする本文がありません。");
  const headers = { "Content-Type": "application/json", "Authorization": "Bearer " + token };
  const novelRes = await fetch("https://shosetsu-toukou-site.org/api/novels", {
    method: "POST", headers,
    body: JSON.stringify({
      title,
      description: String(payload.description || "Lexis Novel Desktopから投稿"),
      age_limit: payload.r18 ? "r18" : "all",
      is_ai_generated: true,
      tag_names: []
    })
  });
  const novel = await novelRes.json().catch(() => ({}));
  if (!novelRes.ok) throw new Error(novel.detail || ("小説作成に失敗しました: " + novelRes.status));
  if (!novel.id) throw new Error("作成した小説IDを取得できませんでした。");
  const epRes = await fetch("https://shosetsu-toukou-site.org/api/novels/" + novel.id + "/episodes", {
    method: "POST", headers,
    body: JSON.stringify({ episode_number: 1, title: "第1話", body, tag_names: [] })
  });
  const episode = await epRes.json().catch(() => ({}));
  if (!epRes.ok) throw new Error(episode.detail || ("第1話の投稿に失敗しました: " + epRes.status));
  return { ok: true, novelId: novel.id, url: "https://shosetsu-toukou-site.org/novels/" + novel.id };
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