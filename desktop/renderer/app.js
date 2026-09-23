const $ = (id) => document.getElementById(id);

async function loadSettings() {
  const settings = await window.lexis.getSettings();
  $("apiKey").value = settings.apiKey || "";
  $("model").value = settings.model || "openrouter/auto";
}

$("saveSettings").addEventListener("click", async () => {
  $("status").textContent = "保存中...";
  try {
    await window.lexis.saveSettings({ apiKey: $("apiKey").value, model: $("model").value });
    $("status").textContent = "設定を保存しました。";
  } catch (e) { $("status").textContent = e.message || String(e); }
});

$("generate").addEventListener("click", async () => {
  $("generate").disabled = true;
  $("status").textContent = "生成中...";
  $("meta").textContent = "";
  try {
    const result = await window.lexis.generateNovel({
      apiKey: $("apiKey").value,
      model: $("model").value,
      titleHint: $("titleHint").value,
      genre: $("genre").value,
      characters: $("characters").value,
      tone: $("tone").value,
      length: $("length").value,
      r18: $("r18").checked,
      maxTokens: Number($("maxTokens").value)
    });
    $("resultTitle").value = result.title || "";
    $("resultBody").value = result.body || "";
    const total = result.usage && result.usage.total_tokens ? " / " + result.usage.total_tokens + " tokens" : "";
    $("meta").textContent = (result.model || "") + total;
    $("status").textContent = "生成完了";
  } catch (e) { $("status").textContent = e.message || String(e); }
  finally { $("generate").disabled = false; }
});

$("saveNovel").addEventListener("click", async () => {
  try {
    const result = await window.lexis.saveNovel({ title: $("resultTitle").value, body: $("resultBody").value });
    if (!result.canceled) $("status").textContent = "保存しました: " + result.filePath;
  } catch (e) { $("status").textContent = e.message || String(e); }
});

loadSettings().catch((e) => { $("status").textContent = e.message || String(e); });