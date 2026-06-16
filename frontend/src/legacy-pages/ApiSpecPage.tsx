import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { getApiBase } from "../lib/apiBase";
import { getErrorMessage } from "../lib/errorUtils";
import { useI18n } from "../lib/i18n";
import { applySeoMeta, buildSeoDescription } from "../lib/seoMeta";

const API_BASE = getApiBase();

type DocLang = "ja" | "en";

type Block =
  | { type: "h1" | "h2" | "h3"; text: string; id?: string }
  | { type: "p"; text: string }
  | { type: "ul"; items: string[] }
  | { type: "code"; code: string };

type ApiSpecPageProps = {
  docLang?: DocLang;
};

function slugifyHeading(text: string, index: number) {
  const normalized = String(text || "")
    .toLowerCase()
    .replace(/`/g, "")
    .replace(/[^a-z0-9\u3040-\u30ff\u3400-\u9fff\- ]+/g, "")
    .trim()
    .replace(/\s+/g, "-");
  return normalized || `section-${index}`;
}

function parseMarkdown(markdown: string): Block[] {
  const lines = String(markdown || "").split(/\r?\n/);
  const blocks: Block[] = [];
  let i = 0;
  let headingIndex = 0;

  while (i < lines.length) {
    const line = lines[i] ?? "";
    const trimmed = line.trim();

    if (!trimmed) {
      i += 1;
      continue;
    }

    if (trimmed.startsWith("```")) {
      const codeLines: string[] = [];
      i += 1;
      while (i < lines.length && !String(lines[i] || "").trim().startsWith("```")) {
        codeLines.push(lines[i] || "");
        i += 1;
      }
      if (i < lines.length) i += 1;
      blocks.push({ type: "code", code: codeLines.join("\n") });
      continue;
    }

    if (trimmed.startsWith("### ")) {
      const text = trimmed.slice(4).replace(/^`|`$/g, "");
      blocks.push({ type: "h3", text, id: slugifyHeading(text, headingIndex) });
      headingIndex += 1;
      i += 1;
      continue;
    }

    if (trimmed.startsWith("## ")) {
      const text = trimmed.slice(3);
      blocks.push({ type: "h2", text, id: slugifyHeading(text, headingIndex) });
      headingIndex += 1;
      i += 1;
      continue;
    }

    if (trimmed.startsWith("# ")) {
      const text = trimmed.slice(2);
      blocks.push({ type: "h1", text, id: slugifyHeading(text, headingIndex) });
      headingIndex += 1;
      i += 1;
      continue;
    }

    if (trimmed.startsWith("- ")) {
      const items: string[] = [];
      while (i < lines.length) {
        const bullet = String(lines[i] || "").trim();
        if (!bullet.startsWith("- ")) break;
        items.push(bullet.slice(2));
        i += 1;
      }
      blocks.push({ type: "ul", items });
      continue;
    }

    const paragraphLines = [trimmed];
    i += 1;
    while (i < lines.length) {
      const next = String(lines[i] || "").trim();
      if (!next || next.startsWith("#") || next.startsWith("- ") || next.startsWith("```")) {
        break;
      }
      paragraphLines.push(next);
      i += 1;
    }
    blocks.push({ type: "p", text: paragraphLines.join(" ") });
  }

  return blocks;
}

function inlineCode(text: string) {
  const parts = text.split(/(`[^`]+`)/g).filter(Boolean);
  return parts.map((part, index) => {
    if (part.startsWith("`") && part.endsWith("`")) {
      return (
        <code
          key={`code-${index}`}
          style={{
            background: "#f4efe4",
            border: "1px solid rgba(50, 60, 44, 0.09)",
            borderRadius: 7,
            padding: "0.12rem 0.35rem",
            fontSize: "0.92em",
          }}
        >
          {part.slice(1, -1)}
        </code>
      );
    }
    return <span key={`text-${index}`}>{part}</span>;
  });
}

export default function ApiSpecPage({ docLang = "ja" }: ApiSpecPageProps) {
  const { t } = useI18n();
  const [markdown, setMarkdown] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const markdownPath = docLang === "en" ? "/api/api-spec.en.md" : "/api/api-spec.md";
  const canonicalPath = docLang === "en" ? "/api-spec/en" : "/api-spec";
  const switchPath = docLang === "en" ? "/api-spec" : "/api-spec/en";
  const switchLabel = docLang === "en" ? "日本語" : "English";
  const pageTitle =
    docLang === "en" ? "Public API Specification | Shosetsu Toukou Site" : "公開API仕様書 | 小説投稿サイト";
  const pageDescription =
    docLang === "en"
      ? "Public reference for the FastAPI backend, including authentication, novels, payments, AI, and admin endpoints."
      : "FastAPI バックエンドの認証、小説、支援、AI、管理 API をまとめた公開仕様書です。";

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true);
        setError("");
        const res = await fetch(`${API_BASE}${markdownPath}`);
        const text = await res.text();
        if (!res.ok) {
          throw new Error(
            text ||
              (docLang === "en"
                ? "Failed to load API specification."
                : "API仕様書の取得に失敗しました。"),
          );
        }
        setMarkdown(text);
      } catch (e) {
        setError(
          getErrorMessage(
            e,
            docLang === "en" ? "Failed to load API specification." : "API仕様書の取得に失敗しました。",
          ),
        );
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [docLang, markdownPath]);

  const blocks = useMemo(() => parseMarkdown(markdown), [markdown]);
  const sections = useMemo(
    () =>
      blocks.flatMap((block) =>
        block.type === "h2" ? [{ id: String(block.id || ""), text: block.text }] : [],
      ),
    [blocks],
  );

  useEffect(() => {
    return applySeoMeta({
      title: pageTitle,
      description: buildSeoDescription(pageDescription),
      canonicalPath,
      ogType: "article",
      alternateLanguages: [
        { hrefLang: "ja", href: "/api-spec" },
        { hrefLang: "en", href: "/api-spec/en" },
        { hrefLang: "x-default", href: "/api-spec" },
      ],
      jsonLd: [
        {
          "@context": "https://schema.org",
          "@type": "TechArticle",
          headline: docLang === "en" ? "Public API Specification" : "公開API仕様書",
          inLanguage: docLang,
          description: pageDescription,
          url: canonicalPath,
        },
      ],
    });
  }, [canonicalPath, docLang, pageDescription, pageTitle]);

  return (
    <article style={{ maxWidth: 1140, margin: "0 auto", paddingBottom: 48 }}>
      <section
        style={{
          position: "relative",
          overflow: "hidden",
          background:
            "radial-gradient(circle at top left, rgba(240, 205, 133, 0.18), transparent 34%), linear-gradient(135deg, #18263a 0%, #233752 52%, #314a6b 100%)",
          color: "#fff7ea",
          borderRadius: 28,
          padding: "30px 24px 26px",
          boxShadow: "0 24px 64px rgba(24, 38, 58, 0.2)",
          marginBottom: 22,
        }}
      >
        <div
          style={{
            position: "absolute",
            right: -30,
            top: -20,
            width: 180,
            height: 180,
            borderRadius: "50%",
            background: "rgba(255,255,255,0.08)",
            filter: "blur(2px)",
          }}
        />
        <p style={{ margin: 0, letterSpacing: "0.14em", textTransform: "uppercase", fontSize: 12, opacity: 0.8 }}>
          FastAPI Reference
        </p>
        <div
          style={{
            display: "flex",
            alignItems: "flex-start",
            justifyContent: "space-between",
            gap: 16,
            flexWrap: "wrap",
          }}
        >
          <div>
            <h1
              style={{
                margin: "10px 0 12px",
                fontSize: "clamp(2.2rem, 5vw, 3.5rem)",
                lineHeight: 1,
                color: "#fffdf8",
                textShadow: "0 2px 18px rgba(0, 0, 0, 0.18)",
              }}
            >
              {docLang === "en" ? "Public API Specification" : "公開 API 仕様書"}
            </h1>
            <p style={{ margin: 0, maxWidth: 760, lineHeight: 1.8, color: "rgba(255,247,234,0.9)" }}>
              {docLang === "en"
                ? "A direct reference page for the backend API. It stays public, is excluded from the main menu, and ships in both Japanese and English."
                : "backend API を直接参照できる公開ページです。メニューには出さず、日本語版と英語版の両方を用意しています。"}
            </p>
          </div>
          <Link
            to={switchPath}
            style={{
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              minWidth: 110,
              padding: "10px 14px",
              borderRadius: 999,
              textDecoration: "none",
              background: "rgba(255,255,255,0.12)",
              border: "1px solid rgba(255,255,255,0.24)",
              color: "#fff7ea",
              fontWeight: 700,
              backdropFilter: "blur(8px)",
            }}
          >
            {switchLabel}
          </Link>
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
            gap: 12,
            marginTop: 18,
          }}
        >
          {[
            docLang === "en"
              ? { label: "Scope", value: "Auth, novels, feed, payments, AI, admin" }
              : { label: "範囲", value: "認証 / 小説 / フィード / 支援 / AI / 管理" },
            docLang === "en"
              ? { label: "Format", value: "Rendered markdown + raw markdown endpoint" }
              : { label: "形式", value: "整形表示 + raw markdown endpoint" },
            docLang === "en"
              ? { label: "Language", value: "Japanese and English" }
              : { label: "言語", value: "日本語 / 英語" },
          ].map((item) => (
            <div
              key={item.label}
              style={{
                padding: "14px 16px",
                borderRadius: 18,
                background: "rgba(255,255,255,0.1)",
                border: "1px solid rgba(255,255,255,0.12)",
              }}
            >
              <div style={{ fontSize: 12, opacity: 0.72, textTransform: "uppercase", letterSpacing: "0.08em" }}>
                {item.label}
              </div>
              <div style={{ marginTop: 6, fontWeight: 700, lineHeight: 1.5 }}>{item.value}</div>
            </div>
          ))}
        </div>

        <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginTop: 18 }}>
          <a
            href={`${API_BASE}${markdownPath}`}
            target="_blank"
            rel="noreferrer"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 8,
              padding: "10px 14px",
              borderRadius: 999,
              textDecoration: "none",
              border: "1px solid rgba(255,255,255,0.22)",
              color: "#17352c",
              background: "#fff6e6",
              fontWeight: 700,
            }}
          >
            {docLang === "en" ? "Open Markdown" : "Markdown を開く"}
          </a>
          <a
            href="#api-spec-content"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 8,
              padding: "10px 14px",
              borderRadius: 999,
              textDecoration: "none",
              border: "1px solid rgba(255,255,255,0.22)",
              color: "#fff7ea",
              background: "rgba(255,255,255,0.08)",
              fontWeight: 700,
            }}
          >
            {docLang === "en" ? "Jump to spec" : "仕様へ移動"}
          </a>
        </div>
      </section>

      <div style={{ display: "grid", gap: 18, gridTemplateColumns: "minmax(0, 1fr)" }}>
        {sections.length > 0 ? (
          <nav
            aria-label={docLang === "en" ? "API spec sections" : "API仕様セクション"}
            style={{
              background: "#fffdf8",
              border: "1px solid #ece5d7",
              borderRadius: 22,
              padding: "18px 18px 14px",
              boxShadow: "0 12px 34px rgba(29, 34, 20, 0.05)",
            }}
          >
            <p style={{ margin: "0 0 10px", fontSize: 13, letterSpacing: "0.08em", textTransform: "uppercase", color: "#6c685d" }}>
              {docLang === "en" ? "Sections" : "セクション"}
            </p>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
              {sections.map((section) => (
                <a
                  key={section.id}
                  href={`#${section.id}`}
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    padding: "8px 12px",
                    borderRadius: 999,
                    background: "#f6f1e6",
                    color: "#17352c",
                    textDecoration: "none",
                    border: "1px solid #eadfca",
                    fontSize: 14,
                  }}
                >
                  {section.text}
                </a>
              ))}
            </div>
          </nav>
        ) : null}

        {loading ? <p>{docLang === "en" ? "Loading..." : "読み込み中..."}</p> : null}
        {error ? <p style={{ color: "#b42318" }}>{error}</p> : null}
        {!loading && !error ? (
          <div
            id="api-spec-content"
            style={{
              background: "#fffdf8",
              border: "1px solid #ece5d7",
              borderRadius: 24,
              padding: "24px 22px",
              boxShadow: "0 16px 50px rgba(29, 34, 20, 0.06)",
            }}
          >
            {blocks.map((block, index) => {
              if (block.type === "h1") {
                return (
                  <h1 key={index} id={block.id} style={{ margin: index === 0 ? 0 : "28px 0 12px", fontSize: "2rem" }}>
                    {inlineCode(block.text)}
                  </h1>
                );
              }
              if (block.type === "h2") {
                return (
                  <h2
                    key={index}
                    id={block.id}
                    style={{
                      margin: "36px 0 12px",
                      paddingTop: 10,
                      borderTop: "1px solid #ece5d7",
                      fontSize: "1.5rem",
                      scrollMarginTop: 96,
                    }}
                  >
                    {inlineCode(block.text)}
                  </h2>
                );
              }
              if (block.type === "h3") {
                return (
                  <h3
                    key={index}
                    id={block.id}
                    style={{ margin: "24px 0 10px", fontSize: "1.08rem", color: "#17352c", scrollMarginTop: 96 }}
                  >
                    {inlineCode(block.text)}
                  </h3>
                );
              }
              if (block.type === "ul") {
                return (
                  <ul key={index} style={{ margin: "10px 0 16px", paddingLeft: 22, lineHeight: 1.84, color: "#34342f" }}>
                    {block.items.map((item, itemIndex) => (
                      <li key={`${index}-${itemIndex}`}>{inlineCode(item)}</li>
                    ))}
                  </ul>
                );
              }
              if (block.type === "code") {
                return (
                  <pre
                    key={index}
                    style={{
                      margin: "12px 0 18px",
                      padding: "14px 16px",
                      borderRadius: 16,
                      background: "#1b211d",
                      color: "#f5f1e8",
                      overflowX: "auto",
                      fontSize: 13,
                      lineHeight: 1.65,
                    }}
                  >
                    <code>{block.code}</code>
                  </pre>
                );
              }
              return (
                <p key={index} style={{ margin: "10px 0", lineHeight: 1.9, color: "#34342f" }}>
                  {inlineCode(block.text)}
                </p>
              );
            })}
          </div>
        ) : null}
      </div>
    </article>
  );
}
