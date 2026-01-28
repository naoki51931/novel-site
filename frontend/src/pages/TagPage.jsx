import { useEffect, useMemo } from "react";
import { useParams } from "react-router-dom";
import Home from "./Home";
import { useI18n } from "../lib/i18n";

const safeDecode = (value) => {
  if (!value) return "";
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
};

export default function TagPage() {
  const { slug } = useParams();
  const { t, lang } = useI18n();
  const tagName = useMemo(() => safeDecode(slug).trim(), [slug]);

  useEffect(() => {
    if (typeof document === "undefined" || !tagName) return undefined;

    const previousTitle = document.title;
    const metaDescription = document.querySelector('meta[name="description"]');
    const previousDescription = metaDescription?.getAttribute("content");
    const canonicalLink = document.querySelector('link[rel="canonical"]');
    const previousCanonical = canonicalLink?.getAttribute("href");

    const nextTitle = t({
      ja: `${tagName}小説一覧｜小説投稿サイト`,
      en: `Novels tagged "${tagName}" | Novel Submission Site`,
    });
    const nextDescription = t({
      ja: `「${tagName}」をテーマにした小説作品一覧です。一次創作・二次創作を含む${tagName}関連の物語を掲載しています。`,
      en: `A collection of novels tagged "${tagName}". Discover stories and settings related to ${tagName}, including original and fan works.`,
    });

    document.title = nextTitle;

    let createdMeta = null;
    if (metaDescription) {
      metaDescription.setAttribute("content", nextDescription);
    } else {
      const meta = document.createElement("meta");
      meta.setAttribute("name", "description");
      meta.setAttribute("content", nextDescription);
      document.head.appendChild(meta);
      createdMeta = meta;
    }

    let createdCanonical = null;
    if (typeof window !== "undefined") {
      const nextCanonical = `${window.location.origin}/tags/${encodeURIComponent(tagName)}`;
      if (canonicalLink) {
        canonicalLink.setAttribute("href", nextCanonical);
      } else {
        const link = document.createElement("link");
        link.setAttribute("rel", "canonical");
        link.setAttribute("href", nextCanonical);
        document.head.appendChild(link);
        createdCanonical = link;
      }
    }

    return () => {
      document.title = previousTitle;
      if (createdMeta) {
        createdMeta.remove();
      } else if (metaDescription) {
        if (previousDescription === null) {
          metaDescription.removeAttribute("content");
        } else {
          metaDescription.setAttribute("content", previousDescription);
        }
      }

      if (createdCanonical) {
        createdCanonical.remove();
      } else if (canonicalLink) {
        if (previousCanonical === null) {
          canonicalLink.removeAttribute("href");
        } else {
          canonicalLink.setAttribute("href", previousCanonical);
        }
      }
    };
  }, [tagName, lang, t]);

  if (!tagName) {
    return <p>{t({ ja: "タグが見つかりません。", en: "Tag not found." })}</p>;
  }

  return (
    <div>
      <section style={{ margin: "12px 0 20px" }}>
        <h1 style={{ fontSize: 24, marginBottom: 8 }}>
          {t(
            { ja: "{{tag}}小説一覧", en: 'Novels tagged "{{tag}}"' },
            { tag: tagName }
          )}
        </h1>
        <p style={{ color: "var(--muted-text)", lineHeight: 1.7 }}>
          {t(
            {
              ja: "「{{tag}}」をテーマにした小説作品一覧です。感情や関係性の変化、世界観の広がりなど、{{tag}}に関連する物語を掲載しています。",
              en: 'A curated list of novels featuring "{{tag}}". Explore stories that highlight themes, relationships, and worlds connected to {{tag}}.',
            },
            { tag: tagName }
          )}
        </p>
      </section>

      <Home tag={tagName} showRanking={false} />
    </div>
  );
}
