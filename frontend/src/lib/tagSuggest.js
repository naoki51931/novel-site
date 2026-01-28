const STOP_WORDS = new Set([
  "the",
  "and",
  "or",
  "but",
  "not",
  "with",
  "from",
  "that",
  "this",
  "these",
  "those",
  "have",
  "has",
  "had",
  "are",
  "was",
  "were",
  "will",
  "would",
  "can",
  "could",
  "should",
  "may",
  "might",
  "been",
  "also",
  "just",
  "than",
  "then",
  "into",
  "about",
  "over",
  "under",
  "after",
  "before",
  "more",
  "most",
  "some",
  "such",
  "very",
  "ここ",
  "そこ",
  "あそこ",
  "これ",
  "それ",
  "あれ",
  "この",
  "その",
  "あの",
  "ため",
  "よう",
  "ので",
  "こと",
  "もの",
  "です",
  "ます",
  "いる",
  "ある",
  "なる",
  "する",
  "した",
  "そして",
  "また",
  "しかし",
  "だから",
  "僕",
  "私",
  "俺",
  "彼",
  "彼女",
  "あなた",
  "君",
  "自分",
  "今回",
  "現在",
]);

const WORD_RE =
  /[A-Za-z][A-Za-z0-9_-]{2,24}|[一-龯々〆ヵヶぁ-ゔァ-ヴー]{2,16}/g;

const normalizeTag = (tag) => (tag || "").trim().toLowerCase();

export const parseTagsInput = (input) =>
  (input || "")
    .split(",")
    .map((tag) => tag.trim())
    .filter((tag) => tag.length > 0);

export const mergeTagsInput = (input, tagsToAdd) => {
  const existing = parseTagsInput(input);
  const existingSet = new Set(existing.map(normalizeTag));
  const uniqueAdd = (tagsToAdd || []).filter(
    (tag) => tag && !existingSet.has(normalizeTag(tag))
  );
  return [...existing, ...uniqueAdd].join(", ");
};

export const extractTagCandidates = (text, { limit = 12 } = {}) => {
  const normalized = (text || "")
    .replace(/https?:\/\/\S+/g, " ")
    .replace(/[【】\[\]「」『』（）(){}<>]/g, " ")
    .replace(/[.,:;!?'"-]/g, " ")
    .replace(/\s+/g, " ")
    .trim();

  if (!normalized) return [];

  const counts = new Map();
  const matches = normalized.match(WORD_RE) || [];
  for (const raw of matches) {
    const token = raw.trim();
    if (!token) continue;
    if (/^\d+$/.test(token)) continue;
    const normalizedToken = normalizeTag(token);
    if (STOP_WORDS.has(normalizedToken)) continue;
    const prev = counts.get(token) || 0;
    counts.set(token, prev + 1);
  }

  return Array.from(counts.entries())
    .sort((a, b) => {
      if (b[1] !== a[1]) return b[1] - a[1];
      return b[0].length - a[0].length;
    })
    .map(([token]) => token)
    .slice(0, limit);
};
