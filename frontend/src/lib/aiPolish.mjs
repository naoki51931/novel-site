export function describePolishIntensity(intensity) {
  const level = Math.min(100, Math.max(0, Number(intensity) || 0));
  const strengthText =
    level <= 20
      ? "極めて軽い添削（誤字・表記ゆれ中心）"
      : level <= 40
      ? "軽めの添削（重複や違和感を軽く調整）"
      : level <= 60
      ? "標準の添削（読みやすさを中心に整える）"
      : level <= 80
      ? "強めのリライト（文の組み替えや表現の刷新も可）"
      : "非常に強いリライト（構成の再整理まで許可）";

  return { level, strengthText };
}

export function buildPolishPrompt({
  baseBody,
  tone,
  genre,
  characters,
  isR18,
  intensity,
  maxChars,
}) {
  const r18Note = isR18
    ? "成人向けの内容を許可します。性的描写を含めても構いません。"
    : "一般向けの内容にし、露骨な性描写や過度な暴力描写は避けてください。";
  const toneText = tone || "指定なし";
  const genreText = genre || "指定なし";
  const charactersText = characters || "指定なし";
  const { level, strengthText } = describePolishIntensity(intensity);

  const maxCharsText = Number(maxChars) > 0 ? `最大文字数: ${maxChars}字以内` : "最大文字数: 指定なし";

  return [
    "あなたは日本語の小説編集者です。",
    "以下の本文について、重複表現や不自然な箇所を修正し、読みやすく整えてください。",
    "意味やストーリーは保ちつつ、文章の流れを滑らかにします。",
    maxCharsText,
    `添削の強さ: ${strengthText} (${level}/100)`,
    level >= 70
      ? "必要なら文の並び替えや言い回しの大きな変更も行ってください。"
      : "大幅な改変や新規の内容追加は避けてください。",
    r18Note,
    "",
    "【本文】",
    baseBody || "",
    "",
    "【参考情報】",
    `- ジャンル: ${genreText}`,
    `- 雰囲気: ${toneText}`,
    `- 登場人物・設定: ${charactersText}`,
    "",
    "出力は JSON の body に修正文のみを書いてください（タイトルは変更しない）。",
  ].join("\n");
}

export function applyPolishReplacement(fullText, start, end, replacement) {
  const text = fullText || "";
  const safeStart = Math.max(0, Math.min(text.length, Number(start) || 0));
  const safeEnd = Math.max(safeStart, Math.min(text.length, Number(end) || 0));
  const next = replacement != null ? String(replacement) : "";
  return text.slice(0, safeStart) + next + text.slice(safeEnd);
}
