import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getApiBase } from "../lib/apiBase";
import { getErrorMessage } from "../lib/errorUtils";
import { useI18n } from "../lib/i18n";
import { applySeoMeta, buildSeoDescription } from "../lib/seoMeta";

const API_BASE = getApiBase();

type SeoPageData = {
  slug?: string | null;
  title?: string | null;
  description?: string | null;
  h1?: string | null;
  body?: string | null;
  related_tags?: string[] | null;
  canonical_path?: string | null;
};

export default function SeoPage() {
  const { slug } = useParams();
  const { t } = useI18n();
  const [page, setPage] = useState<SeoPageData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const normalizedSlug = useMemo(() => String(slug || "").trim(), [slug]);

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true);
        setError("");
        const res = await fetch(`${API_BASE}/api/seo-pages/${encodeURIComponent(normalizedSlug)}`);
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          throw new Error(data?.detail || t({ ja: "SEOページの取得に失敗しました。", en: "Failed to load page." }));
        }
        setPage(data || null);
      } catch (e) {
        setError(getErrorMessage(e, t({ ja: "SEOページの取得に失敗しました。", en: "Failed to load page." })));
      } finally {
        setLoading(false);
      }
    };
    if (normalizedSlug) load();
    else {
      setLoading(false);
      setError(t({ ja: "ページが見つかりません。", en: "Page not found." }));
    }
  }, [normalizedSlug, t]);

  useEffect(() => {
    if (!page) return undefined;
    return applySeoMeta({
      title: String(page.title || page.h1 || ""),
      description: buildSeoDescription(page.description || page.body || ""),
      canonicalPath: String(page.canonical_path || `/seo/${normalizedSlug}`),
      ogType: "website",
    });
  }, [page, normalizedSlug]);

  if (loading) return <p>{t({ ja: "読み込み中...", en: "Loading..." })}</p>;
  if (error) return <p style={{ color: "red" }}>{error}</p>;
  if (!page) return null;

  const paragraphs = String(page.body || "")
    .split(/\n{2,}/)
    .map((part) => part.trim())
    .filter(Boolean);
  const relatedTags = Array.isArray(page.related_tags) ? page.related_tags.filter(Boolean) : [];

  return (
    <article style={{ maxWidth: 880, margin: "0 auto" }}>
      <h1 style={{ marginBottom: 12 }}>{page.h1 || page.title}</h1>
      {page.description ? (
        <p style={{ color: "var(--muted-text)", fontSize: "1rem", marginBottom: 20 }}>{page.description}</p>
      ) : null}
      <div style={{ display: "grid", gap: 16 }}>
        {paragraphs.map((paragraph, index) => (
          <p key={`${page.slug}-${index}`} style={{ margin: 0, lineHeight: 1.9 }}>
            {paragraph}
          </p>
        ))}
      </div>
      {relatedTags.length > 0 ? (
        <section style={{ marginTop: 28 }}>
          <h2 style={{ fontSize: "1rem", marginBottom: 10 }}>{t({ ja: "関連タグ", en: "Related Tags" })}</h2>
          <div className="tag-chip-row">
            {relatedTags.map((tag) => (
              <Link key={`${page.slug}-${tag}`} to={`/tags/${encodeURIComponent(tag)}`} className="tag-chip">
                #{tag}
              </Link>
            ))}
          </div>
        </section>
      ) : null}
    </article>
  );
}
