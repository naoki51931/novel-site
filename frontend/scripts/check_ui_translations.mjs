import fs from "node:fs/promises";
import path from "node:path";

const ROOT = process.cwd();
const SRC_DIR = path.join(ROOT, "src");
const OUT_DICT = path.join(SRC_DIR, "lib", "i18nPretranslated.json");
const OUT_REPORT_DIR = path.join(ROOT, "i18n");
const OUT_REPORT = path.join(OUT_REPORT_DIR, "ui_translation_check_report.json");
const API_BASE = (process.env.UI_I18N_API_BASE || "http://127.0.0.1:8000").replace(/\/+$/, "");
const TARGET_LANGS = ["zh-cn", "zh-tw", "ko"];
const BATCH_SIZE = Math.max(10, Number(process.env.UI_I18N_BATCH_SIZE || 80));

function unquote(raw) {
  const s = String(raw || "").trim();
  if (!s) return "";
  if (s.startsWith("`") && s.endsWith("`")) {
    const body = s.slice(1, -1);
    if (body.includes("${")) return "";
    return body.replace(/\\`/g, "`").replace(/\\\\/g, "\\");
  }
  if ((s.startsWith('"') && s.endsWith('"')) || (s.startsWith("'") && s.endsWith("'"))) {
    try {
      return JSON.parse(
        s.startsWith("'")
          ? `"${s.slice(1, -1).replace(/\\/g, "\\\\").replace(/"/g, '\\"')}"`
          : s
      );
    } catch {
      return "";
    }
  }
  return "";
}

function normalizeJaForCheck(v) {
  return String(v || "")
    .toLowerCase()
    .replace(/[\s\u3000]/g, "")
    .replace(/[、。，．,.!！?？:：;；"'`’”“()\[\]{}<>「」『』【】\-ー～~_/\\|]/g, "");
}

function diceCoefficient(a, b) {
  const aa = normalizeJaForCheck(a);
  const bb = normalizeJaForCheck(b);
  if (!aa && !bb) return 1;
  if (!aa || !bb) return 0;
  if (aa === bb) return 1;
  const grams = (s) => {
    if (s.length === 1) return [s];
    const out = [];
    for (let i = 0; i < s.length - 1; i += 1) out.push(s.slice(i, i + 2));
    return out;
  };
  const g1 = grams(aa);
  const g2 = grams(bb);
  const m = new Map();
  for (const g of g1) m.set(g, (m.get(g) || 0) + 1);
  let inter = 0;
  for (const g of g2) {
    const c = m.get(g) || 0;
    if (c > 0) {
      inter += 1;
      m.set(g, c - 1);
    }
  }
  return (2 * inter) / (g1.length + g2.length);
}

async function listFiles(dir) {
  const entries = await fs.readdir(dir, { withFileTypes: true });
  const out = [];
  for (const e of entries) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) {
      out.push(...(await listFiles(p)));
      continue;
    }
    if (/\.(jsx|js|tsx|ts)$/.test(e.name)) out.push(p);
  }
  return out;
}

function extractFromSource(src, filePath) {
  const rows = [];
  const re = /t\s*\(\s*\{([\s\S]*?)\}\s*(?:,|\))/g;
  let m;
  while ((m = re.exec(src))) {
    const body = m[1] || "";
    const langs = {};
    const kvRe = /(?:^|,)\s*(ja|en)\s*:\s*("(?:\\.|[^"])*"|'(?:\\.|[^'])*'|`(?:\\.|[^`])*`)/g;
    let k;
    while ((k = kvRe.exec(body))) {
      const lang = k[1];
      const val = unquote(k[2]);
      if (val) langs[lang] = val.trim();
    }
    if (!langs.ja && !langs.en) continue;
    const key = langs.ja || langs.en;
    if (!key) continue;
    rows.push({
      key,
      ja: langs.ja || "",
      en: langs.en || "",
      file: path.relative(ROOT, filePath),
    });
  }
  return rows;
}

async function translateBatch({ sourceLang, targetLang, texts }) {
  const controller = new AbortController();
  const timeoutMs = Math.max(30000, Number(process.env.UI_I18N_TIMEOUT_MS || 180000));
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  let res;
  try {
    res = await fetch(`${API_BASE}/api/i18n/translate`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      signal: controller.signal,
      body: JSON.stringify({
        source_lang: sourceLang,
        target_lang: targetLang,
        texts,
      }),
    });
  } finally {
    clearTimeout(timer);
  }
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`translate failed ${sourceLang}->${targetLang}: ${res.status} ${detail}`);
  }
  const data = await res.json();
  return data?.items || {};
}

async function translateBatchResilient({ sourceLang, targetLang, texts }) {
  if (!texts.length) return {};
  try {
    return await translateBatch({ sourceLang, targetLang, texts });
  } catch (e) {
    if (texts.length <= 1) {
      return { [texts[0]]: texts[0] };
    }
    const mid = Math.floor(texts.length / 2);
    const [left, right] = await Promise.all([
      translateBatchResilient({ sourceLang, targetLang, texts: texts.slice(0, mid) }),
      translateBatchResilient({ sourceLang, targetLang, texts: texts.slice(mid) }),
    ]);
    return { ...left, ...right };
  }
}

async function translateMany({ sourceLang, targetLang, texts }) {
  const out = {};
  for (let i = 0; i < texts.length; i += BATCH_SIZE) {
    const chunk = texts.slice(i, i + BATCH_SIZE);
    const items = await translateBatchResilient({ sourceLang, targetLang, texts: chunk });
    Object.assign(out, items);
  }
  return out;
}

async function main() {
  const files = await listFiles(SRC_DIR);
  const rows = [];
  for (const file of files) {
    const src = await fs.readFile(file, "utf8");
    rows.push(...extractFromSource(src, file));
  }

  const dedup = new Map();
  for (const row of rows) {
    if (!dedup.has(row.key)) dedup.set(row.key, row);
  }
  const entries = Array.from(dedup.values());
  const jaTexts = Array.from(new Set(entries.map((v) => v.ja).filter(Boolean)));
  const enOnlyTexts = Array.from(new Set(entries.filter((v) => !v.ja && v.en).map((v) => v.en)));

  const pretranslated = { "zh-cn": {}, "zh-tw": {}, ko: {} };
  const report = {
    generated_at: new Date().toISOString(),
    api_base: API_BASE,
    total_files: files.length,
    total_ui_entries: entries.length,
    ja_source_count: jaTexts.length,
    en_only_source_count: enOnlyTexts.length,
    by_lang: {},
  };

  for (const lang of TARGET_LANGS) {
    const dict = {};
    if (jaTexts.length) {
      const jaResult = await translateMany({
        sourceLang: "ja",
        targetLang: lang,
        texts: jaTexts,
      });
      Object.assign(dict, jaResult);
    }
    if (enOnlyTexts.length) {
      const enResult = await translateMany({
        sourceLang: "en",
        targetLang: lang,
        texts: enOnlyTexts,
      });
      Object.assign(dict, enResult);
    }
    pretranslated[lang] = dict;

    const transTexts = Array.from(new Set(Object.values(dict).filter(Boolean)));
    const backToJa = transTexts.length
      ? await translateMany({
          sourceLang: lang,
          targetLang: "ja",
          texts: transTexts,
        })
      : {};

    const flagged = [];
    for (const item of entries) {
      if (!item.ja) continue;
      const translated = dict[item.ja] || "";
      const back = backToJa[translated] || "";
      const score = diceCoefficient(item.ja, back);
      if (score < 0.55) {
        flagged.push({
          score: Number(score.toFixed(3)),
          key: item.key,
          ja: item.ja,
          translated,
          back_ja: back,
          file: item.file,
        });
      }
    }

    report.by_lang[lang] = {
      translated_count: Object.keys(dict).length,
      backcheck_target_count: entries.filter((v) => !!v.ja).length,
      flagged_count: flagged.length,
      flagged_examples: flagged.slice(0, 300),
    };
  }

  await fs.mkdir(path.dirname(OUT_DICT), { recursive: true });
  await fs.writeFile(OUT_DICT, `${JSON.stringify(pretranslated, null, 2)}\n`, "utf8");
  await fs.mkdir(OUT_REPORT_DIR, { recursive: true });
  await fs.writeFile(OUT_REPORT, `${JSON.stringify(report, null, 2)}\n`, "utf8");

  console.log(
    JSON.stringify(
      {
        ok: true,
        total_ui_entries: report.total_ui_entries,
        ja_source_count: report.ja_source_count,
        en_only_source_count: report.en_only_source_count,
        out_dict: path.relative(ROOT, OUT_DICT),
        out_report: path.relative(ROOT, OUT_REPORT),
        by_lang: Object.fromEntries(
          Object.entries(report.by_lang).map(([k, v]) => [
            k,
            { translated_count: v.translated_count, flagged_count: v.flagged_count },
          ])
        ),
      },
      null,
      2
    )
  );
}

main().catch((e) => {
  console.error(e?.stack || String(e));
  process.exit(1);
});
